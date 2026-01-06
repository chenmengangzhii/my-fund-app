import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import requests

st.set_page_config(page_title="私人理财投研终端", layout="wide")

# 1. 深度抓取函数：直接对接天天基金底层 API
def get_fund_detail_live(code):
    try:
        # 获取实时净值与名称 (替代 image_5db51c.png 中的未知状态)
        url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        r = requests.get(url, timeout=5)
        import re
        content = re.findall(r"\((.*)\)", r.text)[0]
        data = eval(content)
        return {"名称": data['name'], "类型": "实时行情", "经理": "查看详情", "规模": "实时更新中"}
    except:
        return {"名称": f"基金 {code}", "类型": "ETF/指数", "经理": "未知", "规模": "未知"}

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码", "513500 513100 510300")
    weights_input = st.text_input("占比 %", "40 30 30")
    invest_type = st.radio("投资模式", ["一次性投入", "月定投"])
    money = st.number_input("金额 (RMB)", value=10000)
    
    st.header("📊 对标基准")
    bench_option = st.selectbox("对比基准", ["000300 (沪深300)", "513100 (纳指ETF)", "518880 (黄金ETF)"])
    analyze_btn = st.button("生成深度分析报告", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    bench_code = bench_option.split()[0]
    
    # 渲染画像卡片 (对标 image_5d4006.png)
    st.markdown("### 📋 实时基金画像")
    card_cols = st.columns(len(symbols))
    all_data = pd.DataFrame()
    
    # 设置最长抓取时间（10年）以支持滑块缩放
    end = datetime.date.today().strftime("%Y%m%d")
    start = (datetime.date.today() - datetime.timedelta(days=365*10)).strftime("%Y%m%d")

    with st.spinner('正在同步金融大数据...'):
        for i, s in enumerate(symbols):
            p = get_fund_detail_live(s)
            with card_cols[i]:
                st.markdown(f"""
                <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-top:4px solid #ff4b4b;">
                    <h4 style="margin:0;">{p['名称']}</h4>
                    <p style="color:gray; font-size:0.8em;">{s} | {p['类型']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # 抓取历史数据
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
            df = df[['日期', '收盘']].rename(columns={'收盘': p['名称']})
            df['日期'] = pd.to_datetime(df['日期'])
            if all_data.empty: all_data = df
            else: all_data = pd.merge(all_data, df, on='日期', how='inner')

        # 抓取基准数据 (对标 image_5d405e.png)
        bench_df = ak.fund_etf_hist_em(symbol=bench_code, period="daily", start_date=start, end_date=end, adjust="qfq")
        bench_df = bench_df[['日期', '收盘']].rename(columns={'收盘': '基准'})
        bench_df['日期'] = pd.to_datetime(bench_df['日期'])
        all_data = pd.merge(all_data, bench_df, on='日期', how='inner').set_index('日期')

        # 计算收益
        rets = all_data.pct_change().dropna()
        port_ret = (rets.drop(columns=['基准']) * weights).sum(axis=1)
        port_val = (1 + port_ret).cumprod() * money
        bench_val = (1 + rets['基准']).cumprod() * money

        # --- 绘图部分：增加时间滑块与按钮 (对标 image_5d4028.png) ---
        st.markdown("---")
        st.subheader("📈 资产组合净值走势 (支持缩放与对比)")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="我的组合", line=dict(color='#ff4b4b', width=3)))
        fig.add_trace(go.Scatter(x=bench_val.index, y=bench_val, name=f"基准({bench_option})", line=dict(color='#bdc3c7', dash='dash')))
        
        # 增加时间拉动滑块和周期快速切换
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
                    dict(step="all", label="全部")
                ])
            )
        )
        fig.update_layout(template="plotly_white", height=600, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        # 核心绩效 (对标 image_5db51c.png)
        st.subheader("🏁 阶段涨幅对标")
        c1, c2, c3 = st.columns(3)
        total_ret = (port_val.iloc[-1]/money-1)*100
        bench_ret = (bench_val.iloc[-1]/money-1)*100
        c1.metric("累计收益率", f"{total_ret:.2f}%", f"{total_ret-bench_ret:+.2f}% 较基准")
        c2.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")
        c3.metric("对比基准收益", f"{bench_ret:.2f}%")
