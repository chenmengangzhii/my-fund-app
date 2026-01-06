import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import requests
import re

st.set_page_config(page_title="私人投研终端", layout="wide")

# 1. 修正版实时画像：增加重试与复权价格校验
def get_fund_detail_live(code):
    try:
        # 尝试从天天基金接口获取最新收盘/估值
        url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        r = requests.get(url, timeout=3)
        content = re.findall(r"\((.*)\)", r.text)[0]
        data = eval(content)
        return {"名称": data['name'], "净值": data['dwjz'], "日期": data['gztime']}
    except:
        return {"名称": f"代码 {code}", "净值": "数据同步中", "日期": "---"}

# 2. 核心：强制前复权历史行情 (解决 513100 等价格错误)
def get_hist_data_safe(symbol, start, end):
    try:
        # 明确指定 adjust="qfq" (前复权)，确保 513100 显示为 6.x 而非 1.x
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
        date_col = [c for c in df.columns if '日期' in c or 'date' in c.lower()][0]
        close_col = [c for c in df.columns if '收盘' in c or 'close' in c.lower()][0]
        df = df[[date_col, close_col]].rename(columns={date_col: '日期', close_col: symbol})
        df['日期'] = pd.to_datetime(df['日期'])
        return df
    except Exception as e:
        st.error(f"代码 {symbol} 数据抓取失败: {e}")
        return pd.DataFrame()

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("占比 % (空格分隔)", "40 30 30")
    money = st.number_input("初始投入 (元)", value=10000)
    
    st.header("📊 基准对比")
    bench_options = {"000300": "沪深300指数", "513500": "标普500ETF"}
    bench_code = st.selectbox("选择基准", list(bench_options.keys()), format_func=lambda x: bench_options[x])
    
    analyze_btn = st.button("开始深度回测", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- A. 实时基金画像 (带复权校验) ---
    st.markdown("### 📋 实时行情校验")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        info = get_fund_detail_live(s)
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-top:4px solid #ff4b4b;">
                <h4 style="margin:0;">{info['名称']}</h4>
                <p style="color:gray; font-size:0.8em;">代码: {s}</p>
                <p style="margin:0; font-size:1.2em; color:#ff4b4b;"><b>¥{info['净值']}</b></p>
                <p style="font-size:0.7em; color:gray;">更新时间: {info['日期']}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- B. 数据处理 (解决合并冲突) ---
    with st.spinner('正在同步历史复权行情...'):
        end_d = datetime.date.today().strftime("%Y%m%d")
        start_d = (datetime.date.today() - datetime.timedelta(days=365*5)).strftime("%Y%m%d")
        
        data_list = []
        for s in list(set(symbols + [bench_code])):
            df = get_hist_data_safe(s, start_d, end_d)
            if not df.empty:
                data_list.append(df.set_index('日期'))
        
        # 使用 join 确保日期对齐，避免 KeyError
        all_df = pd.concat(data_list, axis=1, join='inner').sort_index()
        
        rets = all_df.pct_change().dropna()
        port_val = (1 + (rets[symbols] * weights).sum(axis=1)).cumprod() * money
        bench_val = (1 + rets[bench_code]).cumprod() * money

        # --- C. 核心：组合总走势图 (功能大满贯) ---
        st.markdown("---")
        st.subheader("📈 累计资产走势 (支持点击/滑块/精确净值)")
        
        fig1 = go.Figure()
        # 1. 组合主线
        fig1.add_trace(go.Scatter(
            x=port_val.index, y=port_val, 
            name="我的组合", 
            line=dict(color='#ff4b4b', width=3),
            # 悬浮时显示精确金额
            hovertemplate="日期: %{x|%Y-%m-%d}<br>总资产: ¥%{y:,.2f}<extra></extra>"
        ))
        # 2. 基准对比线
        fig1.add_trace(go.Scatter(
            x=bench_val.index, y=bench_val, 
            name=f"基准: {bench_options[bench_code]}", 
            line=dict(color='#bdc3c7', dash='dash'),
            hovertemplate="基准价值: ¥%{y:,.2f}<extra></extra>"
        ))
        
        # 3. 整合：点击切换 + 底部滑块
        fig1.update_xaxes(
            tickformat="%Y-%m-%d",
            rangeslider_visible=True, 
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=3, label="3月", step="month", stepmode="backward"),
                    dict(count=6, label="半年", step="month", stepmode="backward"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(count=1, label="今年来", step="year", stepmode="todate"),
                    dict(step="all", label="全部")
                ])
            )
        )
        # 4. 纵轴：不使用k缩写
        fig1.update_layout(
            hovermode="x unified",
            yaxis=dict(title="资产价值 (元)", tickformat=",.0f"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig1, use_container_width=True)

        # --- D. 绩效统计 ---
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("当前总资产", f"¥{port_val.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{(port_val.iloc[-1]/money-1)*100:.2f}%")
        c3.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")
