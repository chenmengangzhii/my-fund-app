import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import numpy as np

# 页面配置
st.set_page_config(page_title="私人理财回测终端", layout="wide")

st.markdown("""
    <style>
    .stMetric { background: white; border-radius: 10px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #f0f2f6; }
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ 资产组合投资回测分析系统")

# 侧边栏：参数设置 (参考 image_50829f.jpg)
with st.sidebar:
    st.header("⚙️ 参数设置")
    codes_input = st.text_input("输入基金代码 (空格分隔)", "510300 512890 518880 513100")
    weights_input = st.text_input("设定比例 % (空格分隔)", "25 25 25 25")
    initial_cash = st.number_input("初始投入金额 (RMB)", value=10000)
    history_years = st.slider("回测时间跨度 (年)", 1, 10, 3)
    analyze_btn = st.button("开始执行回测", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    with st.spinner('正在同步金融大数据...'):
        # 获取数据逻辑
        all_data = pd.DataFrame()
        name_map = {}
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*history_years)).strftime("%Y%m%d")
        
        for s in symbols:
            try:
                name = ak.fund_individual_detail_info_hold_em(symbol=s).iloc[0, 1]
            except: name = s
            name_map[s] = name
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
            df = df[['日期', '收盘']].rename(columns={'收盘': name})
            df['日期'] = pd.to_datetime(df['日期'])
            if all_data.empty: all_data = df
            else: all_data = pd.merge(all_data, df, on='日期', how='inner')
        
        all_data = all_data.set_index('日期')
        rets = all_data.pct_change().dropna()
        port_ret = (rets * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * initial_cash

        # 1. 绩效指标 (复现 image_5082ba.png)
        st.subheader("🏁 绩效指标对比")
        c1, c2, c3, c4, c5 = st.columns(5)
        total_ret = (port_val.iloc[-1]/initial_cash - 1) * 100
        ann_ret = ((port_val.iloc[-1]/initial_cash)**(365/(port_val.index[-1]-port_val.index[0]).days)-1)*100
        mdd = ((port_val - port_val.cummax())/port_val.cummax()).min() * 100
        vol = port_ret.std() * np.sqrt(252) * 100
        
        c1.metric("最终资产", f"¥{port_val.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{total_ret:.2f}%")
        c3.metric("年化收益率", f"{ann_ret:.2f}%")
        c4.metric("最大回撤", f"{mdd:.2f}%")
        c5.metric("年化波动率", f"{vol:.2f}%")

        # 2. 净值曲线走势
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="组合净值", line=dict(color='#e63946', width=2)))
        fig.update_layout(template="plotly_white", hovermode="x unified", height=450)
        st.plotly_chart(fig, use_container_width=True)

        # 3. 深度分解 (复现 image_50855f.jpg)
        st.markdown("---")
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("📊 收益风险分解")
            contributions = []
            for i, name in enumerate(all_data.columns):
                gain = initial_cash * weights[i] * (all_data[name].iloc[-1]/all_data[name].iloc[0] - 1)
                contributions.append(gain)
            
            risk_pct = [(rets[name].std()/rets.std().sum())*100 for name in all_data.columns]
            
            breakdown_df = pd.DataFrame({
                "产品": all_data.columns,
                "收益贡献 (元)": [f"{v:+.2f}" for v in contributions],
                "风险占比": [f"{v:.2f}%" for v in risk_pct]
            })
            st.table(breakdown_df)

        with col_r:
            st.subheader("📅 相关系数矩阵")
            corr = rets.corr()
            fig_corr = go.Figure(data=go.Heatmap(z=corr.values, x=corr.index, y=corr.columns, colorscale='RdYlGn', zmin=-1, zmax=1))
            st.plotly_chart(fig_corr, use_container_width=True)
