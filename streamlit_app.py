import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="专业版投研终端", layout="wide")

# 1. 核心保底数据库 (复现 image_5d4006.png 的关键信息)
def get_fund_profile(code):
    try:
        # 获取基金基本概况
        info = ak.fund_individual_detail_info_hold_em(symbol=code)
        profile = {
            "名称": info.iloc[0, 1],
            "规模": f"{info.iloc[11, 1]}", # 对应截图中的“规模”
            "经理": info.iloc[14, 1],      # 对应截图中的“基金经理”
            "成立日期": info.iloc[4, 1]
        }
        return profile
    except:
        return None

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
    
    # 展示基金画像 (复现 image_5d4006.png)
    st.subheader("📋 基金底层画像")
    cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        p = get_fund_profile(s)
        if p:
            with cols[i]:
                st.info(f"**{p['名称']} ({s})**\n\n👤 经理: {p['经理']}\n\n💰 规模: {p['规模']}\n\n📅 成立: {p['成立日期']}")

    with st.spinner('计算精准收益曲线...'):
        all_data = pd.DataFrame()
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*history_years)).strftime("%Y%m%d")
        
        for s in symbols:
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
            name = get_fund_profile(s)['名称'] if get_fund_profile(s) else s
            df = df[['日期', '收盘']].rename(columns={'收盘': name})
            df['日期'] = pd.to_datetime(df['日期'])
            if all_data.empty: all_data = df
            else: all_data = pd.merge(all_data, df, on='日期', how='inner')
        
        all_data = all_data.set_index('日期')
        rets = all_data.pct_change().dropna()
        port_ret = (rets * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * money

        # 核心看板 (复现 image_5d31be.png)
        st.subheader("🏁 绩效看板")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最终资产", f"¥{port_val.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{(port_val.iloc[-1]/money-1)*100:.2f}%")
        c3.metric("年化收益率", f"{((port_val.iloc[-1]/money)**(1/history_years)-1)*100:.2f}%")
        c4.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")

        # 绘图
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="组合净值", line=dict(color='#e63946')))
        fig.update_layout(template="plotly_white", height=400)
        st.plotly_chart(fig, use_container_width=True)
