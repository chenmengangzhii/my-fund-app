import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="私人投研终端", layout="wide")

# 1. 稳健的历史行情抓取 (强制前复权，解决价格错误)
@st.cache_data(ttl=3600)
def get_cleaned_data(symbols, start, end):
    all_data = []
    for s in symbols:
        try:
            # 使用东财接口，强制 adjust="qfq" 确保 513100 等基金价格正确
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
            df = df[['日期', '收盘']].copy()
            df.columns = ['date', 'close']
            df['symbol'] = s
            df['date'] = pd.to_datetime(df['date'])
            all_data.append(df)
        except:
            st.warning(f"基金 {s} 行情获取失败，已跳过")
            continue
    
    if not all_data: return pd.DataFrame()
    
    # 纵向合并后再透视，彻底杜绝 KeyError 报错
    big_df = pd.concat(all_data)
    pivot_df = big_df.pivot(index='date', columns='symbol', values='close')
    return pivot_df.ffill().dropna() # 填充停牌日并剔除上市前的空白期

# --- 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 组合配置")
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("占比 % (空格分隔)", "40 30 30")
    money = st.number_input("初始投入 (元)", value=10000)
    
    st.header("📊 基准选择")
    bench_code = st.selectbox("对比基准", ["510300", "513500"], format_func=lambda x: "沪深300ETF" if x=="510300" else "标普500ETF")
    
    analyze_btn = st.button("生成深度回测报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    all_symbols = list(set(symbols + [bench_code]))
    
    # 获取数据
    end_date = datetime.date.today().strftime("%Y%m%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")
    
    with st.spinner('正在调取复权行情数据...'):
        data = get_cleaned_data(all_symbols, start_date, end_date)
    
    if data.empty:
        st.error("无法获取行情数据，请检查网络或代码是否正确")
    else:
        # 计算收益率
        rets = data.pct_change().dropna()
        
        # 计算净值 (初始金额 * 累计收益率)
        port_val = (1 + (rets[symbols] * weights).sum(axis=1)).cumprod() * money
        bench_val = (1 + rets[bench_code]).cumprod() * money
        
        # --- 页面显示：实时画像看板 ---
        st.markdown("### 📋 组合实时画像")
        cols = st.columns(len(symbols))
        for i, s in enumerate(symbols):
            latest_price = data[s].iloc[-1]
            with cols[i]:
                st.metric(f"基金 {s}", f"¥{latest_price:.4f}") # 显示正确的复权价格

        # --- 核心：全功能交互图表 ---
        st.markdown("---")
        st.subheader("📈 累计资产走势 (支持快捷按钮/滑块/精确浮窗)")
        
        fig = go.Figure()
        # 1. 我的组合
        fig.add_trace(go.Scatter(
            x=port_val.index, y=port_val, name="我的组合资产",
            line=dict(color='#ff4b4b', width=3),
            hovertemplate="日期: %{x|%Y-%m-%d}<br>金额: ¥%{y:,.2f}<extra></extra>"
        ))
        # 2. 对标基准
        fig.add_trace(go.Scatter(
            x=bench_val.index, y=bench_val, name="对比基准价值",
            line=dict(color='#bdc3c7', dash='dash'),
            hovertemplate="基准: ¥%{y:,.2f}<extra></extra>"
        ))
        
        # 3. 配置交互功能
        fig.update_xaxes(
            rangeslider_visible=True, # 底部滑块
            rangeselector=dict(       # 左上角切换按钮
                buttons=list([
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=6, label="半年", step="month", stepmode="backward"),
                    dict(count=1, label="今年来", step="year", stepmode="todate"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(step="all", label="全部")
                ])
            )
        )
        
        fig.update_layout(
            hovermode="x unified",     # 悬浮显示所有线
            yaxis=dict(tickformat=",.0f", title="资产总额 (元)"), # 完整显示数字不缩写
            height=600,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # --- 绩效看板 ---
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        final_assets = port_val.iloc[-1]
        total_ret = (final_assets / money - 1) * 100
        max_drawdown = ((port_val / port_val.cummax() - 1).min()) * 100
        
        m1.metric("最终资产总额", f"¥{final_assets:,.2f}")
        m2.metric("累计百分比收益", f"{total_ret:.2f}%")
        m3.metric("区间最大回撤", f"{max_drawdown:.2f}%")
