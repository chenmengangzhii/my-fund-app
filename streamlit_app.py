import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import numpy as np

# 页面配置
st.set_page_config(page_title="私人理财回测终端", layout="wide")

# 1. 建立常用基金名称映射表 (确保 100% 显示中文)
NAME_DICT = {
    "513500": "标普500ETF",
    "513100": "纳指ETF",
    "518880": "黄金ETF",
    "510300": "沪深300ETF",
    "512890": "红利低波ETF",
    "510500": "中证500ETF",
    "159915": "创业板ETF",
    "513050": "中概互联网ETF"
}

with st.sidebar:
    st.header("⚙️ 参数设置")
    codes_input = st.text_input("输入基金代码 (空格分隔)", "513500 513100 518880")
    weights_input = st.text_input("设定比例 % (空格分隔)", "40 30 30")
    initial_cash = st.number_input("初始投入金额 (RMB)", value=10000)
    history_years = st.slider("回测时间跨度 (年)", 1, 10, 3)
    analyze_btn = st.button("开始执行回测", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    with st.spinner('正在获取实时行情数据...'):
        all_data = pd.DataFrame()
        fund_details = []
        
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*history_years)).strftime("%Y%m%d")
        
        for i, s in enumerate(symbols):
            # 优先从映射表查，查不到再显示代码
            f_name = NAME_DICT.get(s, f"基金 {s}")
            
            try:
                # 获取历史价格
                df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
                df = df[['日期', '收盘']].rename(columns={'收盘': f_name})
                df['日期'] = pd.to_datetime(df['日期'])
                
                fund_details.append({"name": f_name, "code": s, "weight": weights[i]})
                
                if all_data.empty: all_data = df
                else: all_data = pd.merge(all_data, df, on='日期', how='inner')
            except Exception as e:
                st.error(f"代码 {s} 数据获取失败，请检查代码是否正确。")
        
        all_data = all_data.set_index('日期')
        rets = all_data.pct_change().dropna()
        port_ret = (rets * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * initial_cash

        # --- 页面展示 ---
        st.subheader("🏁 组合绩效看板")
        c1, c2, c3, c4 = st.columns(4)
        total_ret = (port_val.iloc[-1]/initial_cash - 1) * 100
        ann_ret = ((port_val.iloc[-1]/initial_cash)**(365/(port_val.index[-1]-port_val.index[0]).days)-1)*100
        mdd = ((port_val - port_val.cummax())/port_val.cummax()).min() * 100
        
        c1.metric("最终资产", f"¥{port_val.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{total_ret:.2f}%")
        c3.metric("年化收益率", f"{ann_ret:.2f}%")
        c4.metric("最大回撤", f"{mdd:.2f}%")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="资产净值", line=dict(color='#e63946', width=2)))
        fig.update_layout(template="plotly_white", hovermode="x unified", height=400)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📊 资产配置与收益明细")
        display_list = []
        for i, detail in enumerate(fund_details):
            name = detail["name"]
            gain_rmb = initial_cash * detail["weight"] * (all_data[name].iloc[-1]/all_data[name].iloc[0] - 1)
            display_list.append({
                "基金名称": name,
                "基金代码": detail["code"],
                "配置占比": f"{detail['weight']*100:.0f}%",
                "累计涨跌幅": f"{(all_data[name].iloc[-1]/all_data[name].iloc[0]-1)*100:+.2f}%",
                "收益贡献 (元)": f"{gain_rmb:+.2f}"
            })
        st.table(pd.DataFrame(display_list))
