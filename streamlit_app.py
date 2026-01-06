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
            # 尝试指数接口 (如 000300)
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
    money = st.number_input("初始投入 (元)", value=10000)
    
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
            st.error("部分代码无效或数据获取失败")
            st.stop()
            
        # 核心：先对齐原始价格数据，再计算收益率
        price_data = pd.concat(all_dfs, axis=1, join='inner').sort_index()
        
    # --- 核心：动态回测函数 ---
    def calc_dynamic_assets(start_date, initial_money):
        # 截取选定时间段之后的数据
        sub_price = price_data.loc[start_date:]
        if sub_price.empty: return None
        
        # 计算相对于起点的日收益率 (第一行置为0以便从起点开始计算)
        sub_rets = sub_price.pct_change().fillna(0)
        
        # 计算组合每日净值走势 (累乘)
        portfolio_cum_ret = (1 + (sub_rets[symbols] * weights).sum(axis=1)).cumprod()
        # 计算基准每日净值走势 (累乘)
        benchmark_cum_ret = (1 + sub_rets[bench_code]).cumprod()
        
        res_df = pd.DataFrame({
            'portfolio': portfolio_cum_ret * initial_money,
            'benchmark': benchmark_cum_ret * initial_money,
            'p_nav': portfolio_cum_ret,
            'b_nav': benchmark_cum_ret
        })
        return res_df

    st.markdown("### 📈 动态起点回测")
    
    now = price_data.index[-1]
    periods = {
        "1月": now - timedelta(days=30),
        "6月": now - timedelta(days=180),
        "1年": now - timedelta(days=365),
        "3年": now - timedelta(days=365*3),
        "全部": price_data.index[0]
    }
    
    tabs = st.tabs(list(periods.keys()))
    
    for tab, (label, start_dt) in zip(tabs, periods.items()):
        with tab:
            plot_df = calc_dynamic_assets(start_dt, money)
            
            if plot_df is not None:
                fig = go.Figure()

                # 组合曲线
                fig.add_trace(go.Scatter(
                    x=plot_df.index, 
                    y=plot_df['portfolio'],
                    name="我的组合",
                    line=dict(color='#ff4b4b', width=3),
                    customdata=plot_df['p_nav'],
                    hovertemplate="<b>我的组合</b><br>资产: ¥%{y:,.2f}<br>累计净值: %{customdata:.4f}<extra></extra>"
                ))

                # 基准曲线
                fig.add_trace(go.Scatter(
                    x=plot_df.index, 
                    y=plot_df['benchmark'],
                    name=f"基准: {bench_code}",
                    line=dict(color='#95a5a6', width=2, dash='dot'),
                    customdata=plot_df['b_nav'],
                    hovertemplate="<b>对标基准</b><br>资产: ¥%{y:,.2f}<br>累计净值: %{customdata:.4f}<extra></extra>"
                ))

                fig.update_layout(
                    hovermode="x unified",
                    hoverlabel=dict(bgcolor="rgba(255,255,255,0.9)"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    yaxis=dict(tickformat=",.0f", title="资产总值 (元)"),
                    xaxis=dict(
                        title="日期", 
                        rangeslider_visible=True  # 滑块回来了！
                    ),
                    height=600,
                    margin=dict(l=10, r=10, t=50, b=10),
                    template="plotly_white"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 数据统计
                m1, m2, m3 = st.columns(3)
                final_v = plot_df['portfolio'].iloc[-1]
                total_r = (plot_df['p_nav'].iloc[-1] - 1) * 100
                mdd = ((plot_df['portfolio'] / plot_df['portfolio'].cummax() - 1).min()) * 100
                
                m1.metric(f"期末资产 ({label})", f"¥{final_v:,.2f}")
                m2.metric("阶段收益率", f"{total_r:.2f}%", delta=f"{total_r - (plot_df['b_nav'].iloc[-1]-1)*100:.2f}% vs 基准")
                m3.metric("最大回撤", f"{mdd:.2f}%")
