import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import numpy as np

# 页面配置
st.set_page_config(page_title="基金回测详细版", layout="wide")

st.markdown("""
    <style>
    .stMetric { background: white; border-radius: 10px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #f0f2f6; }
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ 资产组合回测（详细信息版）")

# 侧边栏
with st.sidebar:
    st.header("⚙️ 参数设置")
    codes_input = st.text_input("输入基金代码 (空格分隔)", "513500 513100")
    weights_input = st.text_input("设定比例 % (空格分隔)", "50 50")
    initial_cash = st.number_input("初始投入金额 (RMB)", value=20000)
    history_years = st.slider("回测时间跨度 (年)", 1, 10, 3)
    analyze_btn = st.button("开始执行回测", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    with st.spinner('正在同步金融大数据...'):
        all_data = pd.DataFrame()
        fund_info_list = [] # 用于存储基金详细信息
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*history_years)).strftime("%Y%m%d")
        
        for i, s in enumerate(symbols):
            try:
                # 获取基金详细名称信息
                info = ak.fund_individual_detail_info_hold_em(symbol=s)
                name = info.iloc[0, 1]
                # 构造详细信息行
                fund_info_list.append({
                    "序号": i+1,
                    "基金名称": name,
                    "基金代码": s,
                    "配置比例": f"{weights[i]*100:.0f}%"
                })
            except: 
                name = s
                fund_info_list.append({"序号": i+1, "基金名称": "未知", "基金代码": s, "配置比例": f"{weights[i]*100:.0f}%"})

            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
            df = df[['日期', '收盘']].rename(columns={'收盘': name})
            df['日期'] = pd.to_datetime(df['日期'])
            if all_data.empty: all_data = df
            else: all_data = pd.merge(all_data, df, on='日期', how='inner')
        
        all_data = all_data.set_index('日期')
        rets = all_data.pct_change().dropna()
        port_ret = (rets * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * initial_cash

        # 1. 核心指标卡片
        st.subheader("🏁 绩效指标对比")
        c1, c2, c3, c4 = st.columns(4)
        total_ret = (port_val.iloc[-1]/initial_cash - 1) * 100
        ann_ret = ((port_val.iloc[-1]/initial_cash)**(365/(port_val.index[-1]-port_val.index[0]).days)-1)*100
        mdd = ((port_val - port_val.cummax())/port_val.cummax()).min() * 100
        
        c1.metric("最终资产", f"¥{port_val.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{total_ret:.2f}%")
        c3.metric("年化收益率", f"{ann_ret:.2f}%")
        c4.metric("最大回撤", f"{mdd:.2f}%")

        # 2. 基金详细信息表格 (复现 image_50829f.jpg 的内容)
        st.subheader("📋 资产配置详情")
        st.table(pd.DataFrame(fund_info_list))

        # 3. 净值曲线走势
        st.subheader("📈 资产组合净值曲线")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="组合净值", line=dict(color='#e63946', width=2)))
        fig.update_layout(template="plotly_white", hovermode="x unified", height=450)
        st.plotly_chart(fig, use_container_width=True)

        # 4. 收益贡献分析 (参考 image_50855f.jpg 上半部分)
        st.subheader("💰 各资产收益贡献")
        contributions = []
        for i, name in enumerate(all_data.columns):
            gain = initial_cash * weights[i] * (all_data[name].iloc[-1]/all_data[name].iloc[0] - 1)
            contributions.append(gain)
        
        breakdown_df = pd.DataFrame({
            "基金名称": all_data.columns,
            "历史涨跌幅": [f"{(all_data[name].iloc[-1]/all_data[name].iloc[0]-1)*100:.2f}%" for name in all_data.columns],
            "收益贡献 (元)": [f"{v:+.2f}" for v in contributions]
        })
        st.dataframe(breakdown_df, use_container_width=True)
