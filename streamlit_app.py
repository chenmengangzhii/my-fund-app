import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import requests
import re

st.set_page_config(page_title="私人理财投研终端", layout="wide")

# 1. 稳健的名片抓取 (解决 image_5e9dff.png 中的名称缺失)
def get_fund_detail_fast(code):
    try:
        url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        r = requests.get(url, timeout=3)
        content = re.findall(r"\((.*)\)", r.text)[0]
        data = eval(content)
        return {"名称": data['name'], "净值": data['dwjz'], "更新": data['gztime']}
    except:
        return {"名称": f"基金 {code}", "净值": "--", "更新": "待同步"}

# 2. 智能行情同步 (修复 KeyError)
def fetch_data(symbol, start, end):
    try:
        # 尝试 ETF 接口
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
        if df.empty: raise ValueError
        df = df[['日期', '收盘']].rename(columns={'日期': 'date', '收盘': symbol})
    except:
        # 尝试指数接口 (如 000300)
        df = ak.stock_zh_index_daily_em(symbol=f"sh{symbol}" if symbol.startswith("000") else f"sz{symbol}")
        df = df[['date', 'close']].rename(columns={'close': symbol})
    
    df['date'] = pd.to_datetime(df['date'])
    return df

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码", "513500 513100 510300")
    weights_input = st.text_input("占比 %", "40 30 30")
    money = st.number_input("初始投入 (元)", value=10000)
    
    st.header("📊 对比基准")
    bench_map = {"000300": "沪深300指数", "513500": "标普500ETF"}
    bench_code = st.selectbox("选择基准", list(bench_map.keys()), format_func=lambda x: bench_map[x])
    
    analyze_btn = st.button("生成多维回测报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- A. 实时画像卡片 ---
    st.markdown("### 📋 组合成分实时画像")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        info = get_fund_detail_fast(s)
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-top:4px solid #ff4b4b;">
                <h4 style="margin:0; font-size:1.1em;">{info['名称']}</h4>
                <p style="color:gray; font-size:0.8em; margin:5px 0;">代码: {s}</p>
                <p style="margin:10px 0 0 0; color:#ff4b4b; font-size:1.2em;"><b>¥{info['净值']}</b></p>
                <p style="color:gray; font-size:0.7em;">更新: {info['更新']}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- B. 数据处理 (修复 image_5e9dff.png 逻辑) ---
    with st.spinner('同步 10 年历史数据...'):
        end_str = datetime.date.today().strftime("%Y%m%d")
        start_str = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")
        
        # 循环抓取并合并
        merged_df = None
        for s in list(set(symbols + [bench_code])):
            df = fetch_data(s, start_str, end_str)
            if merged_df is None: merged_df = df
            else: merged_df = pd.merge(merged_df, df, on='date', how='inner')
        
        merged_df = merged_df.set_index('date')
        rets = merged_df.pct_change().dropna()
        
        # 计算核心数值
        port_val = (1 + (rets[symbols] * weights).sum(axis=1)).cumprod() * money
        bench_val = (1 + rets[bench_code]).cumprod() * money
        indiv_vals = (1 + rets[symbols]).cumprod() * money # 各基金走势

        # --- C. 组合总价值走势 (元) ---
        st.markdown("---")
        st.subheader("📈 组合总金额走势 (元) [支持滑块缩放]")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=port_val.index, y=port_val, name="组合总资产", line=dict(color='#ff4b4b', width=3)))
        fig1.add_trace(go.Scatter(x=bench_val.index, y=bench_val, name=f"基准: {bench_map[bench_code]}", line=dict(color='#bdc3c7', dash='dash')))
        
        # 日期格式与滑块优化
        fig1.update_layout(
            hovermode="x unified",
            xaxis=dict(tickformat="%Y-%m-%d", rangeslider_visible=True), # 统一日期格式并开启滑块
            yaxis=dict(title="金额 (元)", tickformat=",.0f"), # 取消 k，显示千分位
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig1, use_container_width=True)

        # --- D. 成分基金独立表现 ---
        st.subheader("📊 成分基金走势对比 (以 {money}元 为基点)")
        fig2 = go.Figure()
        for s in symbols:
            fig2.add_trace(go.Scatter(x=indiv_vals.index, y=indiv_vals[s], name=f"基金 {s}"))
        
        fig2.update_layout(
            hovermode="x unified",
            xaxis=dict(tickformat="%Y-%m-%d", rangeslider_visible=True),
            yaxis=dict(title="累计价值 (元)", tickformat=",.0f"),
            template="none"
        )
        st.plotly_chart(fig2, use_container_width=True)

        # --- E. 收益指标 ---
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        total_ret = (port_val.iloc[-1]/money-1)*100
        c1.metric("最终组合总资产", f"¥{port_val.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{total_ret:.2f}%", f"{total_ret - (bench_val.iloc[-1]/money-1)*100:+.2f}% 较基准")
        c3.metric("历史最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")
