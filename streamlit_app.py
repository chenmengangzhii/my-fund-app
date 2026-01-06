import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import requests
import re

st.set_page_config(page_title="私人投研终端", layout="wide")

# 1. 强化版名片抓取 (解决 image_5e37ca.png 中的同步问题)
def get_fund_detail_live(code):
    try:
        url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        r = requests.get(url, timeout=3)
        content = re.findall(r"\((.*)\)", r.text)[0]
        data = eval(content)
        return {"名称": data['name'], "净值": data['dwjz'], "日期": data['gztime']}
    except:
        return {"名称": f"代码 {code}", "净值": "---", "日期": "同步中"}

# 2. 兼容性行情抓取 (修复 image_5e37ca.png 的 KeyError)
def get_hist_data_safe(symbol, start, end):
    try:
        # 优先尝试 ETF 接口
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
        if df.empty: raise ValueError
    except:
        # 如果失败，尝试指数接口 (如 000300)
        df = ak.stock_zh_index_daily_em(symbol=f"sh{symbol}" if symbol.startswith("000") else f"sz{symbol}")
    
    # 统一列名处理
    date_col = [c for c in df.columns if '日期' in c or 'date' in c.lower()][0]
    close_col = [c for c in df.columns if '收盘' in c or 'close' in c.lower()][0]
    df = df[[date_col, close_col]].rename(columns={date_col: '日期', close_col: symbol})
    df['日期'] = pd.to_datetime(df['日期'])
    return df

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("占比 % (空格分隔)", "40 30 30")
    money = st.number_input("投入金额 (RMB)", value=10000)
    
    st.header("📊 对比基准")
    # 预设常用基准 (对标 image_5d405e.png)
    bench_options = {"000300": "沪深300指数", "513500": "标普500ETF", "513100": "纳指ETF"}
    bench_code = st.selectbox("对比基准", list(bench_options.keys()), format_func=lambda x: bench_options[x])
    
    analyze_btn = st.button("生成深度分析报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- A. 实时基金画像卡片 ---
    st.markdown("### 📋 实时基金画像")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        info = get_fund_detail_live(s)
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-top:4px solid #ff4b4b;">
                <h4 style="margin:0;">{info['名称']}</h4>
                <p style="color:gray; font-size:0.8em; margin:5px 0;">代码: {s}</p>
                <p style="margin:5px 0; font-size:0.9em;">💰 实时净值: {info['净值']}<br>📅 更新: {info['日期']}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- B. 数据处理与回测 (修复 image_5e37ca.png 逻辑) ---
    with st.spinner('正在同步 10 年历史数据以支持滑块缩放...'):
        end_d = datetime.date.today().strftime("%Y%m%d")
        start_d = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")
        
        all_df = pd.DataFrame()
        # 抓取所有成分基金
        for s in symbols:
            df = get_hist_data_safe(s, start_d, end_d)
            if all_df.empty: all_df = df
            else: all_df = pd.merge(all_df, df, on='日期', how='inner')
        
        # 抓取对比基准
        bench_df = get_hist_data_safe(bench_code, start_d, end_d)
        final_df = pd.merge(all_df, bench_df, on='日期', how='inner').set_index('日期')
        
        # 计算净值走势
        rets = final_df.pct_change().dropna()
        port_ret = (rets[symbols] * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * money
        bench_val = (1 + rets[bench_code]).cumprod() * money

        # --- C. 核心功能：时间按钮与滑块 (复现 image_5d4028.png) ---
        st.markdown("---")
        st.subheader("📈 累计净值走势对标 (支持时间拉动)")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="我的资产组合", line=dict(color='#ff4b4b', width=2.5)))
        fig.add_trace(go.Scatter(x=bench_val.index, y=bench_val, name=f"基准: {bench_options[bench_code]}", line=dict(color='#bdc3c7', dash='dash')))
        
        # 注入时间滑块与快捷按钮
        fig.update_xaxes(
            rangeslider_visible=True, # 底部滑块
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=3, label="3月", step="month", stepmode="backward"),
                    dict(count=6, label="半年", step="month", stepmode="backward"),
                    dict(count=1, label="今年来", step="year", stepmode="todate"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(count=5, label="5年", step="year", stepmode="backward"),
                    dict(step="all", label="全部视图")
                ])
            )
        )
        fig.update_layout(template="plotly_white", height=600, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # --- D. 绩效看板 ---
        c1, c2, c3 = st.columns(3)
        total_ret = (port_val.iloc[-1]/money-1)*100
        b_total_ret = (bench_val.iloc[-1]/money-1)*100
        c1.metric("累计收益率", f"{total_ret:.2f}%", f"{total_ret - b_total_ret:+.2f}% 较基准")
        c2.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")
        c3.metric("对比基准收益", f"{b_total_ret:.2f}%")
