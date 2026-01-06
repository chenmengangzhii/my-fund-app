import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import numpy as np

# 页面基础配置
st.set_page_config(page_title="雪球同款回测系统", layout="wide")

# 自定义 CSS 样式，模仿雪球的卡片式美感
st.markdown("""
    <style>
    .reportview-container { background: #f8f9fa; }
    .stMetric { background: white; border-radius: 8px; padding: 15px; border: 1px solid #e1e4e8; }
    div[data-testid="stTable"] { background: white; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 资产组合回测终端")

# 侧边栏设置 (对标 image_50829f.jpg)
with st.sidebar:
    st.header("📝 组合配置")
    codes = st.text_input("基金代码 (空格分隔)", "510300 512890 518880 513100")
    weights = st.text_input("占比 % (空格分隔)", "25 25 25 25")
    money = st.number_input("初始资金 (元)", value=10000)
    years = st.slider("时间跨度 (年)", 1, 10, 3)
    run = st.button("开始分析", type="primary")

if run:
    with st.spinner('正在同步金融数据库...'):
        symbol_list = codes.split()
        weight_list = [float(w)/100 for w in weights.split()]
        
        # 准备数据容器
        all_data = pd.DataFrame()
        details = []
        
        # 获取起止日期
        end_date = datetime.date.today().strftime("%Y%m%d")
        start_date = (datetime.date.today() - datetime.timedelta(days=365*years)).strftime("%Y%m%d")

        for i, s in enumerate(symbol_list):
            try:
                # 获取基金详细名称 (对标 image_50829f.jpg)
                fund_info = ak.fund_individual_detail_info_hold_em(symbol=s)
                name = fund_info.iloc[0, 1]
            except:
                name = f"基金 {s}"
            
            # 抓取历史净值
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            df = df[['日期', '收盘']].rename(columns={'收盘': name})
            df['日期'] = pd.to_datetime(df['日期'])
            
            # 计算单支基金涨幅
            growth = (df.iloc[-1]['收盘'] / df.iloc[0]['收盘'] - 1)
            profit = money * weight_list[i] * growth
            
            # 记录详细信息 (对标 image_50855f.jpg)
            details.append({
                "基金名称": name,
                "代码": s,
                "配置比例": f"{weight_list[i]*100:.0f}%",
                "期间涨跌幅": f"{growth*100:+.2f}%",
                "收益贡献": f"¥{profit:+.2f}"
            })
            
            if all_data.empty: all_data = df
            else: all_data = pd.merge(all_data, df, on='日期', how='inner')

        # 计算组合整体表现
        all_data.set_index('日期', inplace=True)
        rets = all_data.pct_change().dropna()
        port_ret = (rets * weight_list).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * money

        # --- 页面展示 ---
        
        # 1. 核心绩效指标 (对标 image_5082ba.png)
        st.subheader("🏁 核心绩效指标")
        m1, m2, m3, m4 = st.columns(4)
        total_ret = (port_val.iloc[-1]/money - 1) * 100
        ann_ret = ((port_val.iloc[-1]/money)**(365/(port_val.index[-1]-port_val.index[0]).days)-1)*100
        mdd = ((port_val - port_val.cummax())/port_val.cummax()).min() * 100
        
        m1.metric("最终资产", f"¥{port_val.iloc[-1]:,.2f}")
        m2.metric("累计收益率", f"{total_ret:.2f}%")
        m3.metric("年化收益率", f"{ann_ret:.2f}%")
        m4.metric("最大回撤", f"{mdd:.2f}%")

        # 2. 资产明细表 (重点优化：显示名称和详细贡献)
        st.subheader("📋 资产配置与贡献明细")
        st.table(pd.DataFrame(details))

        # 3. 组合走势图
        st.subheader("📈 组合净值走势")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="组合净值", line=dict(color='#ee3c3c', width=2.5)))
        fig.update_layout(template="plotly_white", hovermode="x unified", margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
