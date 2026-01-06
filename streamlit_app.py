import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="高级投研终端", layout="wide")

# 1. 动态抓取画像 (解决 image_5e2ca7.png 中的同步中问题)
def get_fund_name_safe(code):
    try:
        # 获取ETF基本信息表
        fund_list = ak.fund_etf_category_chinese_free_em()
        name = fund_list[fund_list['代码'] == code]['名称'].values[0]
        return name
    except:
        return f"基金 {code}"

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("占比 % (空格分隔)", "40 30 30")
    money = st.number_input("初始投入 (RMB)", value=10000)
    
    st.header("📊 对比基准")
    bench_code = st.selectbox("对比基准", ["510300", "513500", "513100"], 
                             format_func=lambda x: "沪深300" if x=="510300" else "大盘指数")
    analyze_btn = st.button("生成深度分析报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # --- 基金名片展示 ---
    st.subheader("📋 实时基金画像")
    card_cols = st.columns(len(symbols))
    for i, s in enumerate(symbols):
        fname = get_fund_name_safe(s)
        with card_cols[i]:
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-top:4px solid #ff4b4b;">
                <h4 style="margin:0;">{fname}</h4>
                <p style="color:gray; font-size:0.8em;">代码: {s}</p>
            </div>
            """, unsafe_allow_html=True)

    # --- 核心数据抓取 (修复 image_5e2ca7.png 的 KeyError) ---
    with st.spinner('正在同步金融大数据...'):
        end_date = datetime.date.today().strftime("%Y%m%d")
        start_date = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")
        
        all_data = pd.DataFrame()
        
        # 抓取所有目标基金与基准
        for s in symbols + [bench_code]:
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            # 自动寻找日期列和收盘列 (解决列名不一致问题)
            date_col = [c for c in df.columns if '日期' in c][0]
            close_col = [c for c in df.columns if '收盘' in c][0]
            
            temp_df = df[[date_col, close_col]].rename(columns={date_col: '日期', close_col: s})
            temp_df['日期'] = pd.to_datetime(temp_df['日期'])
            
            if all_data.empty: all_data = temp_df
            else: all_data = pd.merge(all_data, temp_df, on='日期', how='inner')

        all_data = all_data.set_index('日期')
        
        # 计算净值
        rets = all_data.pct_change().dropna()
        port_ret = (rets[symbols] * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * money
        bench_val = (1 + rets[bench_code]).cumprod() * money

        # --- 绘图：集成时间按钮与滑块 (复现 image_5d4028.png) ---
        st.markdown("---")
        st.subheader("📈 累计净值走势对标")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="我的组合", line=dict(color='#ff4b4b', width=2)))
        fig.add_trace(go.Scatter(x=bench_val.index, y=bench_val, name=f"基准: {bench_code}", line=dict(color='#bdc3c7', dash='dash')))
        
        # 配置天天基金同款工具栏
        fig.update_xaxes(
            rangeslider_visible=True, # 底部滑块
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=3, label="3月", step="month", stepmode="backward"),
                    dict(count=1, label="今年来", step="year", stepmode="todate"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(count=5, label="5年", step="year", stepmode="backward"),
                    dict(step="all", label="全部视图")
                ])
            )
        )
        fig.update_layout(template="plotly_white", height=550, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # --- 阶段绩效 ---
        c1, c2, c3 = st.columns(3)
        total_ret = (port_val.iloc[-1]/money - 1) * 100
        c1.metric("累计总收益", f"{total_ret:.2f}%")
        c2.metric("基准总收益", f"{(bench_val.iloc[-1]/money - 1) * 100:.2f}%")
        c3.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")
