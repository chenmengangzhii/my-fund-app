import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import requests
import re

st.set_page_config(page_title="资产组合投研终端", layout="wide")

# 1. 实时数据抓取
def get_fund_detail_live(code):
    try:
        url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        r = requests.get(url, timeout=3)
        content = re.findall(r"\((.*)\)", r.text)[0]
        data = eval(content)
        return {"名称": data['name'], "净值": data['dwjz'], "日期": data['gztime']}
    except:
        return {"名称": f"代码 {code}", "净值": "---", "日期": "同步中"}

# 2. 兼容性行情抓取
def get_hist_data_safe(symbol, start, end):
    try:
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
        date_col = [c for c in df.columns if '日期' in c or 'date' in c.lower()][0]
        close_col = [c for c in df.columns if '收盘' in c or 'close' in c.lower()][0]
        df = df[[date_col, close_col]].rename(columns={date_col: '日期', close_col: symbol})
        df['日期'] = pd.to_datetime(df['日期'])
        return df
    except:
        return pd.DataFrame()

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码", "513500 513100 510300")
    weights_input = st.text_input("占比 %", "40 30 30")
    money = st.number_input("初始投入 (元)", value=10000)
    
    st.header("📊 基准对标")
    bench_options = {"000300": "沪深300指数", "513500": "标普500ETF"}
    bench_code = st.selectbox("选择基准", list(bench_options.keys()), format_func=lambda x: bench_options[x])
    
    analyze_btn = st.button("生成分析报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- A. 实时基金名片 ---
    st.markdown("### 📋 组合成分实时画像")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        info = get_fund_detail_live(s)
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-top:4px solid #ff4b4b;">
                <h4 style="margin:0;">{info['名称']}</h4>
                <p style="color:gray; font-size:0.8em;">代码: {s}</p>
                <p style="margin:0; font-size:1.1em; color:#ff4b4b;"><b>{info['净值']}</b></p>
                <p style="font-size:0.7em; color:gray;">更新日期: {info['日期']}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- B. 数据处理 ---
    with st.spinner('同步历史数据...'):
        end_d = datetime.date.today().strftime("%Y%m%d")
        start_d = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")
        
        all_df = pd.DataFrame()
        for s in list(set(symbols + [bench_code])):
            df = get_hist_data_safe(s, start_d, end_d)
            if all_df.empty: all_df = df
            else: all_df = pd.merge(all_df, df, on='日期', how='inner')
        
        all_df = all_df.set_index('日期')
        rets = all_df.pct_change().dropna()
        
        # 计算各项指标
        port_ret = (rets[symbols] * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * money
        bench_val = (1 + rets[bench_code]).cumprod() * money
        
        # 计算单个基金的累计收益
        indiv_vals = (1 + rets[symbols]).cumprod() * money

        # --- C. 组合总价值走势 (对标 image_5e91c4.png) ---
        st.markdown("---")
        st.subheader("📈 组合总金额走势 (元)")
        fig_total = go.Figure()
        fig_total.add_trace(go.Scatter(x=port_val.index, y=port_val, name="组合总值", line=dict(color='#ff4b4b', width=3)))
        fig_total.add_trace(go.Scatter(x=bench_val.index, y=bench_val, name="对比基准", line=dict(color='#bdc3c7', dash='dash')))
        
        # 优化日期格式与滑块
        fig_total.update_layout(
            hovermode="x unified",
            xaxis=dict(tickformat="%Y-%m-%d", rangeslider_visible=True), # 强制 YYYY-MM-DD 格式并开启滑块
            yaxis=dict(title="金额 (元)", tickformat=",.0f"), # 取消 k 缩写，直接显示具体金额
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_total, use_container_width=True)

        # --- D. 各基金独立表现 ---
        st.subheader("📊 组合内各基金走势对比 (归一化)")
        fig_indiv = go.Figure()
        for s in symbols:
            fig_indiv.add_trace(go.Scatter(x=indiv_vals.index, y=indiv_vals[s], name=f"基金 {s}"))
        
        fig_indiv.update_layout(
            xaxis=dict(tickformat="%Y-%m-%d", rangeslider_visible=True),
            yaxis=dict(title="金额 (元)"),
            template="none"
        )
        st.plotly_chart(fig_indiv, use_container_width=True)

        # --- E. 绩效统计 ---
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("最终组合总资产", f"¥{port_val.iloc[-1]:,.2f}")
        with c2:
            ret_pct = (port_val.iloc[-1]/money-1)*100
            st.metric("累计百分比收益", f"{ret_pct:.2f}%")
        with c3:
            mdd = ((port_val - port_val.cummax())/port_val.cummax()).min()*100
            st.metric("历史最大回撤", f"{mdd:.2f}%")
