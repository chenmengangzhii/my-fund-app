import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="私人投研终端", layout="wide")

# 1. 智能数据抓取
@st.cache_data(ttl=3600)
def get_data_smart(symbol):
    try:
        # 尝试基金/ETF接口
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date="20100101", end_date="20261231", adjust="hfq")
        if df.empty: raise ValueError
        df = df[['日期', '收盘']].rename(columns={'日期': 'date', '收盘': symbol})
    except:
        try:
            # 尝试指数接口
            df = ak.stock_zh_index_daily_em(symbol=symbol)
            df = df[['date', 'close']].rename(columns={'close': symbol})
        except:
            return pd.DataFrame()
    
    df['date'] = pd.to_datetime(df['date'])
    return df.set_index('date')

# --- 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 资产配置")
    codes_input = st.text_input("组合代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("对应权重 %", "40 30 30")
    money = st.number_input("每一段起点的初始投入 (元)", value=10000)
    
    st.header("📊 基准选择")
    bench_code = st.text_input("对比基准 (指数或ETF)", "000300")
    
    analyze_btn = st.button("生成动态回测报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    all_syms = list(set(symbols + [bench_code]))
    
    with st.spinner('正在同步全球复权行情...'):
        all_dfs = []
        for s in all_syms:
            df_temp = get_data_smart(s)
            if not df_temp.empty:
                all_dfs.append(df_temp)
        
        if len(all_dfs) < len(all_syms):
            st.error("部分代码无效，请检查（尤其是指数代码是否正确）")
            st.stop()
            
        data = pd.concat(all_dfs, axis=1, join='inner').sort_index()
        
    rets = data.pct_change()

    # --- 核心：动态回测函数 ---
    def calc_dynamic_assets(start_date, initial_money):
        sub_rets = rets.loc[start_date:].dropna()
        if sub_rets.empty: return None, None
        
        # 计算走势
        p_val = (1 + (sub_rets[symbols] * weights).sum(axis=1)).cumprod() * initial_money
        b_val = (1 + sub_rets[bench_code]).cumprod() * initial_money
        
        # 补上起点
        first_date = sub_rets.index[0] - timedelta(days=1)
        p_val[first_date] = initial_money
        b_val[first_date] = initial_money
        
        # 构建对齐的 DataFrame 方便绘图
        res_df = pd.DataFrame({
            'portfolio': p_val,
            'benchmark': b_val
        }).sort_index()
        
        # 计算净值用于悬停显示 (当前资产 / 初始投入)
        res_df['p_nav'] = res_df['portfolio'] / initial_money
        res_df['b_nav'] = res_df['benchmark'] / initial_money
        
        return res_df

    st.markdown("### 📈 动态起点回测")
    st.info(f"💡 **提示**：鼠标在图表上移动即可同步查看 **{money}元** 在不同时间的变值及收益倍数。")
    
    now = data.index[-1]
    periods = {
        "1月": now - timedelta(days=30),
        "6月": now - timedelta(days=180),
        "1年": now - timedelta(days=365),
        "3年": now - timedelta(days=365*3),
        "全部": data.index[0]
    }
    
    tabs = st.tabs(list(periods.keys()))
    
    for tab, (label, start_dt) in zip(tabs, periods.items()):
        with tab:
            plot_df = calc_dynamic_assets(start_dt, money)
            
            if plot_df is not None:
                fig = go.Figure()

                # 1. 组合曲线
                fig.add_trace(go.Scatter(
                    x=plot_df.index, 
                    y=plot_df['portfolio'],
                    name="我的组合",
                    line=dict(color='#ff4b4b', width=3),
                    customdata=plot_df['p_nav'], # 传入净值数据
                    hovertemplate="资产: ¥%{y:,.2f}<br>净值: %{customdata:.3f}<extra></extra>"
                ))

                # 2. 基准曲线
                fig.add_trace(go.Scatter(
                    x=plot_df.index, 
                    y=plot_df['benchmark'],
                    name=f"基准: {bench_code}",
                    line=dict(color='#bdc3c7', dash='dash', width=2),
                    customdata=plot_df['b_nav'],
                    hovertemplate="基准: ¥%{y:,.2f}<br>净值: %{customdata:.3f}<extra></extra>"
                ))

                # 图表布局美化
                fig.update_layout(
                    hovermode="x unified", # 统一悬停关键设置
                    hoverlabel=dict(bgcolor="rgba(255,255,255,0.9)", font_size=13),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    yaxis=dict(tickformat=",.0f", title="资产值 (元)", gridcolor='whitesmoke'),
                    xaxis=dict(title="日期", gridcolor='whitesmoke', rangeslider_visible=False),
                    height=550,
                    margin=dict(l=10, r=10, t=50, b=10),
                    plot_bgcolor='white'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 指标汇总渲染
                m1, m2, m3 = st.columns(3)
                final_v = plot_df['portfolio'].iloc[-1]
                total_r = (final_v / money - 1) * 100
                # 计算回撤
                mdd = ((plot_df['portfolio'] / plot_df['portfolio'].cummax() - 1).min()) * 100
                
                m1.metric(f"期末总资产 ({label})", f"¥{final_v:,.2f}")
                m2.metric("阶段收益率", f"{total_r:.2f}%")
                m3.metric("阶段最大回撤", f"{mdd:.2f}%")
