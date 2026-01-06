import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="全动态投研终端", layout="wide")

# 自动抓取函数：尝试从多个维度获取基金画像
def fetch_fund_data(code):
    try:
        # 抓取基本概况（包含经理、规模等）
        info = ak.fund_individual_detail_info_hold_em(symbol=code)
        return {
            "名称": info.iloc[0, 1],
            "经理": info.iloc[14, 1],
            "规模": info.iloc[11, 1],
            "类型": info.iloc[1, 1]
        }
    except:
        try:
            # 如果概况抓不到，从净值接口尝试抓取名称
            name_df = ak.fund_etf_category_chinese_free_em()
            name = name_df[name_df['代码'] == code]['名称'].values[0]
            return {"名称": name, "经理": "需查阅官网", "规模": "实时计算中", "类型": "ETF"}
        except:
            return {"名称": f"基金 {code}", "经理": "未知", "规模": "未知", "类型": "未知"}

with st.sidebar:
    st.header("🔍 组合配置")
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 510300")
    weights_input = st.text_input("占比 % (空格分隔)", "40 30 30")
    invest_type = st.radio("投资模式", ["一次性投入", "月定投"])
    money = st.number_input("投入金额 (RMB)", value=10000)
    history_years = st.slider("回测跨度 (年)", 1, 10, 3)
    analyze_btn = st.button("开始实时分析", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    
    # 1. 动态生成基金名片 (对标天天基金 image_5d4006.png)
    st.markdown("### 📋 实时基金画像")
    card_cols = st.columns(len(symbols))
    
    all_data = pd.DataFrame()
    fund_names = {}

    with st.spinner('正在多源抓取实时金融数据...'):
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*history_years)).strftime("%Y%m%d")
        
        for i, s in enumerate(symbols):
            # 获取画像
            profile = fetch_fund_data(s)
            fund_names[s] = profile['名称']
            
            # 渲染名片
            with card_cols[i]:
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-top: 4px solid #ff4b4b; box-shadow: 2px 2px 10px rgba(0,0,0,0.05);">
                    <h4 style="margin:0; color:#1f1f1f;">{profile['名称']}</h4>
                    <p style="color: #666; font-size: 0.8em; margin:5px 0;">代码: {s} | {profile['类型']}</p>
                    <div style="font-size: 0.9em; margin-top:10px;">
                        <p>👤 <b>经理:</b> {profile['经理']}</p>
                        <p>💰 <b>规模:</b> {profile['规模']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # 获取历史净值 (对标 image_525efb.png)
            try:
                df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
                df = df[['日期', '收盘']].rename(columns={'收盘': profile['名称']})
                df['日期'] = pd.to_datetime(df['日期'])
                if all_data.empty: all_data = df
                else: all_data = pd.merge(all_data, df, on='日期', how='inner')
            except:
                st.error(f"无法获取代码 {s} 的行情数据，请检查代码是否正确。")

        if not all_data.empty:
            all_data = all_data.set_index('日期')
            rets = all_data.pct_change().dropna()
            port_ret = (rets * weights).sum(axis=1)
            port_val = (1 + port_ret).cumprod() * money

            # 2. 绩效看板 (对标 image_5d31be.png)
            st.markdown("---")
            st.subheader("🏁 组合绩效表现")
            c1, c2, c3, c4 = st.columns(4)
            total_ret = (port_val.iloc[-1]/money-1)*100
            
            c1.metric("最终资产", f"¥{port_val.iloc[-1]:,.2f}")
            c2.metric("累计收益率", f"{total_ret:.2f}%")
            c3.metric("年化收益率", f"{((port_val.iloc[-1]/money)**(365/(port_val.index[-1]-port_val.index[0]).days)-1)*100:.2f}%")
            c4.metric("最大回撤", f"{((port_val - port_val.cummax())/port_val.cummax()).min()*100:.2f}%")

            # 3. 净值走势图
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="组合净值", line=dict(color='#ff4b4b', width=3)))
            fig.update_layout(template="plotly_white", height=450, margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig, use_container_width=True)
