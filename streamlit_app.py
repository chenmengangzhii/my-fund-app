import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="私人投研终端", layout="wide")

# 1. 智能数据抓取：自动识别基金/指数，强制复权
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
    money = st.number_input("每一段起点的初始投入 (元)", value=10000)
    
    st.header("📊 基准选择")
    bench_code = st.text_input("对比基准 (指数或ETF)", "000300")
    
    # 这里的分析逻辑改了：我们拉取全部数据，在图表端做动态重置
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
            
        # 统一日期对齐，避免红屏
        data = pd.concat(all_dfs, axis=1, join='inner').sort_index()
        
    # 计算每日收益率
    rets = data.pct_change()

    # --- 核心：动态回测函数 ---
    def calc_dynamic_assets(start_date, initial_money):
        sub_rets = rets.loc[start_date:].dropna()
        if sub_rets.empty: return None, None
        
        # 假设在 start_date 投入 money，计算此后的净值走势
        p_val = (1 + (sub_rets[symbols] * weights).sum(axis=1)).cumprod() * initial_money
        b_val = (1 + sub_rets[bench_code]).cumprod() * initial_money
        
        # 补上起点：让曲线从 initial_money 开始
        first_date = sub_rets.index[0] - timedelta(days=1)
        p_val[first_date] = initial_money
        b_val[first_date] = initial_money
        return p_val.sort_index(), b_val.sort_index()

    # --- 页面展示 ---
    st.markdown("### 📈 动态起点回测")
    st.info(f"下方图表展示了：假设你在选定周期的**第一天**投入 {money} 元，到今天的资产变化。")
    
    # 定义时间段
    now = data.index[-1]
    periods = {
        "1月": now - timedelta(days=30),
        "6月": now - timedelta(days=180),
        "1年": now - timedelta(days=365),
        "3年": now - timedelta(days=365*3),
        "全部": data.index[0]
    }
    
    # 使用 Streamlit 原生 Tab 切换，实现点击不同时间段重置起点的效果
    tabs = st.tabs(list(periods.keys()))
    
    for tab, (label, start_dt) in zip(tabs, periods.items()):
        with tab:
            p_val, b_val = calc_dynamic_assets(start_dt, money)
            if p_val is not None:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=p_val.index, y=p_val, name="我的组合", line=dict(color='#ff4b4b', width=3),
                                         hovertemplate="日期: %{x}<br>资产: ¥%{y:,.2f}<extra></extra>"))
                fig.add_trace(go.Scatter(x=b_val.index, y=b_val, name=f"基准: {bench_code}", line=dict(color='#bdc3c7', dash='dash'),
                                         hovertemplate="基准: ¥%{y:,.2f}<extra></extra>"))
                
                fig.update_layout(
                    hovermode="x unified",
                    yaxis=dict(tickformat=",.0f", title="资产总额 (元)"),
                    xaxis=dict(rangeslider_visible=True, title="日期"),
                    height=500,
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 指标汇总
                m1, m2, m3 = st.columns(3)
                final_v = p_val.iloc[-1]
                total_r = (final_v / money - 1) * 100
                mdd = ((p_val / p_val.cummax() - 1).min()) * 100
                m1.metric(f"期末总资产 ({label})", f"¥{final_v:,.2f}")
                m2.metric("阶段收益率", f"{total_r:.2f}%")
                m3.metric("阶段最大回撤", f"{mdd:.2f}%")
