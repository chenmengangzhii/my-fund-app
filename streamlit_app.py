import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import requests
import re

st.set_page_config(page_title="私人理财投研终端", layout="wide")

# 1. 稳健的名片抓取：直接对接天天基金接口 (解决 image_5db51c.png 的未知问题)
def get_fund_detail_fast(code):
    try:
        url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        r = requests.get(url, timeout=3)
        content = re.findall(r"\((.*)\)", r.text)[0]
        data = eval(content)
        return {"名称": data['name'], "净值": data['dwjz'], "更新": data['gztime']}
    except:
        return {"名称": f"基金 {code}", "净值": "--", "更新": "待同步"}

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("占比 % (空格分隔)", "40 30 30")
    money = st.number_input("初始投入 (RMB)", value=10000)
    
    st.header("📊 对比基准")
    # 修复基准选择逻辑 (对标 image_5d405e.png)
    bench_map = {"000300": "沪深300", "513500": "标普500", "513100": "纳指ETF"}
    bench_code = st.selectbox("对比基准", list(bench_map.keys()), format_func=lambda x: bench_map[x])
    
    analyze_btn = st.button("开始实时分析报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- A. 实时基金画像 (专业卡片布局) ---
    st.markdown("### 📋 实时基金画像")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        info = get_fund_detail_fast(s)
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-top:4px solid #ff4b4b; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                <h4 style="margin:0; font-size:1.1em;">{info['名称']}</h4>
                <p style="color:gray; font-size:0.8em; margin:5px 0;">代码: {s}</p>
                <div style="font-size:0.9em; margin-top:10px; border-top:1px solid #eee; padding-top:10px;">
                    <p>💰 <b>最新净值:</b> {info['净值']}</p>
                    <p>📅 <b>更新日期:</b> {info['更新']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # --- B. 数据处理 (修复 image_5e30e4.png 的 KeyError 报错) ---
    with st.spinner('正在同步 10 年历史数据以支持滑块缩放...'):
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")
        
        # 统一使用代码作为列名，防止中文导致的 Key 错乱
        data_store = {}
        target_symbols = list(set(symbols + [bench_code]))
        
        for s in target_symbols:
            try:
                df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
                # 兼容性列名处理
                date_col = '日期' if '日期' in df.columns else df.columns[0]
                close_col = '收盘' if '收盘' in df.columns else df.columns[2]
                
                df = df[[date_col, close_col]].rename(columns={date_col: 'date', close_col: s})
                df['date'] = pd.to_datetime(df['date'])
                data_store[s] = df
            except:
                st.warning(f"代码 {s} 行情抓取失败")

        # 合并所有数据
        final_df = None
        for s, df in data_store.items():
            if final_df is None: final_df = df
            else: final_df = pd.merge(final_df, df, on='date', how='inner')
        
        if final_df is not None:
            final_df = final_df.set_index('date')
            rets = final_df.pct_change().dropna()
            
            # 计算组合与基准
            port_ret = (rets[symbols] * weights).sum(axis=1)
            port_val = (1 + port_ret).cumprod() * money
            bench_val = (1 + rets[bench_code]).cumprod() * money

            # --- C. 净值曲线 + 时间轴滑块 (复现 image_5d4028.png) ---
            st.markdown("---")
            st.subheader("📈 累计净值走势对标 (可拉动底部时间轴)")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="我的组合", line=dict(color='#ff4b4b', width=2.5)))
            fig.add_trace(go.Scatter(x=bench_val.index, y=bench_val, name=f"基准: {bench_map[bench_code]}", line=dict(color='#bdc3c7', dash='dash')))
            
            # 注入天天基金同款时间控制组件
            fig.update_xaxes(
                rangeslider_visible=True, # 底部拉动滑块
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1月", step="month", stepmode="backward"),
                        dict(count=3, label="3月", step="month", stepmode="backward"),
                        dict(count=6, label="半年", step="month", stepmode="backward"),
                        dict(count=1, label="今年来", step="year", stepmode="todate"),
                        dict(count=1, label="1年", step="year", stepmode="backward"),
                        dict(count=5, label="5年", step="year", stepmode="backward"),
                        dict(step="all", label="全部")
                    ])
                )
            )
            fig.update_layout(template="plotly_white", height=600, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            # --- D. 核心指标看板 ---
            c1, c2, c3, c4 = st.columns(4)
            total_ret = (port_val.iloc[-1]/money-1)*100
            c1.metric("累计收益率", f"{total_ret:.2f}%")
            c2.metric("基准收益", f"{(bench_val.iloc[-1]/money-1)*100:.2f}%")
            c3.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")
            c4.metric("相对超额", f"{total_ret - (bench_val.iloc[-1]/money-1)*100:+.2f}%")
