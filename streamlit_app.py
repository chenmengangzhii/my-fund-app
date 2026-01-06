import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="高级资产回测终端", layout="wide")

# 1. 增强型画像抓取 (复现 image_5d4006.png 的关键字段)
def get_fund_info_dynamic(code):
    try:
        # 尝试获取基础名称和经理信息
        info = ak.fund_individual_detail_info_hold_em(symbol=code)
        return {
            "名称": info.iloc[0, 1],
            "经理": info.iloc[14, 1],
            "规模": info.iloc[11, 1],
            "风险": "⭐⭐⭐⭐" if "513" in code else "⭐⭐⭐"
        }
    except:
        return {"名称": f"基金 {code}", "经理": "同步中", "规模": "点击查看", "风险": "--"}

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("占比 % (空格分隔)", "40 30 30")
    money = st.number_input("投入金额 (RMB)", value=10000)
    
    st.header("📊 对比基准")
    # 修复 image_5dbc80.png 中的基准选择错误
    bench_map = {"000300": "沪深300", "513500": "标普500", "513100": "纳指ETF"}
    bench_code = st.selectbox("对比基准", list(bench_map.keys()), format_func=lambda x: f"{x} ({bench_map[x]})")
    
    analyze_btn = st.button("生成深度分析报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- A. 实时基金画像卡片 (解决 image_5db51c.png 的未知问题) ---
    st.subheader("📋 实时基金画像")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        p = get_fund_info_dynamic(s)
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; border-left:5px solid #ff4b4b;">
                <h4 style="margin:0;">{p['名称']}</h4>
                <p style="color:gray; font-size:0.8em; margin:2px 0;">代码: {s}</p>
                <p style="margin:5px 0; font-size:0.9em;">👤 经理: {p['经理']}<br>💰 规模: {p['规模']}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- B. 数据处理 (修复 image_5dbc80.png 的日期列错误) ---
    with st.spinner('正在处理 10 年历史数据以支持滑块缩放...'):
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")
        
        all_df = pd.DataFrame()
        # 抓取基金数据
        for s in symbols:
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
            df = df[['日期', '收盘']].rename(columns={'收盘': s})
            df['日期'] = pd.to_datetime(df['日期'])
            if all_df.empty: all_df = df
            else: all_df = pd.merge(all_df, df, on='日期', how='inner')
        
        # 抓取基准数据并修复列名
        b_df = ak.fund_etf_hist_em(symbol=bench_code, period="daily", start_date=start, end_date=end, adjust="qfq")
        b_df = b_df[['日期', '收盘']].rename(columns={'收盘': 'BENCH'})
        b_df['日期'] = pd.to_datetime(b_df['日期'])
        
        final_df = pd.merge(all_df, b_df, on='日期', how='inner').set_index('日期')
        
        # 计算收益率
        rets = final_df.pct_change().dropna()
        port_ret = (rets[symbols] * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * money
        bench_val = (1 + rets['BENCH']).cumprod() * money

        # --- C. 净值曲线 + 时间滑块 (复现 image_5d4028.png) ---
        st.markdown("---")
        st.subheader("📈 资产组合净值走势")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="我的组合", line=dict(color='#ff4b4b', width=2.5)))
        fig.add_trace(go.Scatter(x=bench_val.index, y=bench_val, name=f"基准: {bench_map[bench_code]}", line=dict(color='#bdc3c7', dash='dash')))
        
        # 注入时间滑块与快捷按钮
        fig.update_xaxes(
            rangeslider_visible=True, # 底部拉动滑块
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=6, label="半年", step="month", stepmode="backward"),
                    dict(count=1, label="今年来", step="year", stepmode="todate"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(count=5, label="5年", step="year", stepmode="backward"),
                    dict(step="all", label="全部")
                ])
            )
        )
        fig.update_layout(template="plotly_white", height=500, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # --- D. 绩效看板 ---
        c1, c2, c3 = st.columns(3)
        c1.metric("累计收益率", f"{(port_val.iloc[-1]/money-1)*100:.2f}%", f"{(port_val.iloc[-1]-bench_val.iloc[-1])/money*100:+.2f}% 较基准")
        c2.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")
        c3.metric("基准收益", f"{(bench_val.iloc[-1]/money-1)*100:.2f}%")
