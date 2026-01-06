import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import requests
import re

st.set_page_config(page_title="私人理财投研终端", layout="wide")

# 1. 实时基金画像抓取 (修复 image_5db51c.png 未知显示)
def get_fund_detail_live(code):
    try:
        url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        r = requests.get(url, timeout=3)
        content = re.findall(r"\((.*)\)", r.text)[0]
        data = eval(content)
        return {"名称": data['name'], "净值": data['dwjz'], "日期": data['gztime']}
    except:
        return {"名称": f"代码 {code}", "净值": "---", "日期": "同步中"}

# 2. 稳健历史行情获取 (修复 image_5f0263.png 的 KeyError)
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
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("占比 % (空格分隔)", "40 30 30")
    money = st.number_input("初始投入 (元)", value=10000)
    
    st.header("📊 基准对标")
    bench_options = {"000300": "沪深300指数", "513500": "标普500ETF"}
    bench_code = st.selectbox("对比基准", list(bench_options.keys()), format_func=lambda x: bench_options[x])
    
    analyze_btn = st.button("开始深度回测", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- A. 实时基金画像名片 ---
    st.markdown("### 📋 组合成分实时画像")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        info = get_fund_detail_live(s)
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-top:4px solid #ff4b4b;">
                <h4 style="margin:0;">{info['名称']}</h4>
                <p style="color:gray; font-size:0.8em;">代码: {s}</p>
                <p style="margin:5px 0; font-size:1.1em; color:#ff4b4b;"><b>¥{info['净值']}</b></p>
                <p style="font-size:0.7em; color:gray;">更新: {info['日期']}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- B. 数据对齐处理 (修复合并冲突) ---
    with st.spinner('正在同步 10 年数据...'):
        end_d = datetime.date.today().strftime("%Y%m%d")
        start_d = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")
        
        all_df = pd.DataFrame()
        for s in list(set(symbols + [bench_code])):
            df = get_hist_data_safe(s, start_d, end_d)
            if all_df.empty: all_df = df
            else: all_df = pd.merge(all_df, df, on='日期', how='inner')
        
        all_df = all_df.set_index('日期')
        rets = all_df.pct_change().dropna()
        
        # 计算净值走势
        port_val = (1 + (rets[symbols] * weights).sum(axis=1)).cumprod() * money
        bench_val = (1 + rets[bench_code]).cumprod() * money
        indiv_vals = (1 + rets[symbols]).cumprod() * money

        # --- C. 核心：组合总走势图 (功能大满贯) ---
        st.markdown("---")
        st.subheader("📈 组合总资产走势")
        
        fig1 = go.Figure()
        # 1. 我的组合曲线
        fig1.add_trace(go.Scatter(
            x=port_val.index, y=port_val, 
            name="我的资产组合", 
            line=dict(color='#ff4b4b', width=3),
            hovertemplate="<b>日期:</b> %{x|%Y-%m-%d}<br><b>组合资产:</b> ¥%{y:,.2f}<extra></extra>" # 悬浮显示具体元
        ))
        # 2. 对比基准曲线
        fig1.add_trace(go.Scatter(
            x=bench_val.index, y=bench_val, 
            name=f"基准: {bench_options[bench_code]}", 
            line=dict(color='#bdc3c7', dash='dash'),
            hovertemplate="<b>基准价值:</b> ¥%{y:,.2f}<extra></extra>"
        ))
        
        # 3. 注入快捷按钮 + 滑块 + 日期格式化
        fig1.update_xaxes(
            tickformat="%Y-%m-%d",
            rangeslider_visible=True, # 手动滑块
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
        # 4. 纵坐标金额显示优化 (不显示 40k)
        fig1.update_layout(
            hovermode="x unified",
            yaxis=dict(title="金额 (元)", tickformat=",.0f"), # 取消 k，显示完整数字
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=600
        )
        st.plotly_chart(fig1, use_container_width=True)

        # --- D. 各基金独立走势图 (同样具备滑块与点击) ---
        st.subheader("📊 成分基金明细走势")
        fig2 = go.Figure()
        for s in symbols:
            fig2.add_trace(go.Scatter(
                x=indiv_vals.index, y=indiv_vals[s], 
                name=f"基金 {s}",
                hovertemplate="<b>日期:</b> %{x|%Y-%m-%d}<br><b>资产:</b> ¥%{y:,.2f}<extra></extra>"
            ))
        
        fig2.update_xaxes(
            tickformat="%Y-%m-%d", 
            rangeslider_visible=True,
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(step="all", label="全部")
                ])
            )
        )
        fig2.update_layout(hovermode="x unified", yaxis=dict(tickformat=",.0f"), height=500)
        st.plotly_chart(fig2, use_container_width=True)

        # --- E. 绩效统计 ---
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("最终总资产", f"¥{port_val.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{(port_val.iloc[-1]/money-1)*100:.2f}%")
        c3.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")
