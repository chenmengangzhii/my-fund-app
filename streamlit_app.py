import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="私人投研终端", layout="wide")

# 1. 预置基金名片数据库 (直接对标天天基金数据)
FUND_DB = {
    "513500": {"名称": "博时标普500ETF", "经理": "万琼", "规模": "220.38亿元", "风险": "⭐⭐⭐⭐"},
    "513100": {"名称": "纳指ETF", "经理": "刘杰", "规模": "152.10亿元", "风险": "⭐⭐⭐⭐⭐"},
    "518880": {"名称": "黄金ETF", "经理": "许之彦", "规模": "105.40亿元", "风险": "⭐⭐⭐"},
    "510300": {"名称": "华泰柏瑞沪深300ETF", "经理": "柳军", "规模": "1300.20亿元", "风险": "⭐⭐⭐"},
    "512890": {"名称": "红利低波ETF", "经理": "亚家辉", "规模": "55.60亿元", "风险": "⭐⭐"}
}

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("代码 (空格分隔)", "513500 513100")
    weights_input = st.text_input("占比 % (空格分隔)", "50 50")
    invest_type = st.radio("投资模式", ["一次性投入", "月定投"])
    money = st.number_input("金额 (RMB)", value=10000)
    history_years = st.slider("回测跨度 (年)", 1, 5, 3)
    analyze_btn = st.button("生成深度分析报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- 核心：专业化名片布局 (对标 image_5d4006.png) ---
    st.markdown("### 📋 基金底层画像")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        info = FUND_DB.get(s, {"名称": f"基金 {s}", "经理": "未知", "规模": "计算中", "风险": "--"})
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;">
                <h4 style="margin:0;">{info['名称']}</h4>
                <p style="color: gray; margin:5px 0;">代码: {s}</p>
                <hr style="margin:10px 0;">
                <p>👤 <b>经理:</b> {info['经理']}</p>
                <p>💰 <b>规模:</b> {info['规模']}</p>
                <p>🛡️ <b>评级:</b> {info['风险']}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- 数据抓取与回测 ---
    with st.spinner('正在同步天天基金实时净值...'):
        all_data = pd.DataFrame()
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*history_years)).strftime("%Y%m%d")
        
        for s in symbols:
            # 获取历史数据
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
            f_name = FUND_DB.get(s, {"名称": s})["名称"]
            df = df[['日期', '收盘']].rename(columns={'收盘': f_name})
            df['日期'] = pd.to_datetime(df['日期'])
            if all_data.empty: all_data = df
            else: all_data = pd.merge(all_data, df, on='日期', how='inner')
        
        all_data = all_data.set_index('日期')
        rets = all_data.pct_change().dropna()
        port_ret = (rets * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * money

        # --- 绩效看板 ---
        st.markdown("---")
        st.subheader("🏁 绩效表现")
        c1, c2, c3, c4 = st.columns(4)
        total_ret = (port_val.iloc[-1]/money-1)*100
        c1.metric("最终资产", f"¥{port_val.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{total_ret:.2f}%")
        c3.metric("年化收益率", f"{((port_val.iloc[-1]/money)**(1/history_years)-1)*100:.2f}%")
        c4.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")

        # 绘图
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="组合净值", line=dict(color='#ff4b4b', width=3)))
        fig.update_layout(template="plotly_white", height=450, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
