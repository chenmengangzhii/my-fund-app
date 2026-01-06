import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 页面配置：沉浸式宽屏
st.set_page_config(page_title="私人资产回测终端", layout="wide", initial_sidebar_state="expanded")

def get_data(symbol):
    """
    真正的码农方案：抓取后复权数据计算真实收益。
    后复权能真实反映：如果我当时买入1块钱，现在变成了多少钱。
    """
    try:
        # 抓取日线行情，使用后复权(hfq)以确保跨越拆分窗口时的收益连续
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", 
                                 start_date="20150101", 
                                 end_date=datetime.now().strftime("%Y%m%d"), 
                                 adjust="hfq")
        df = df[['日期', '收盘']].copy()
        df.columns = ['date', symbol]
        df['date'] = pd.to_datetime(df['date'])
        return df.set_index('date')
    except Exception:
        return pd.DataFrame()

# --- 侧边栏：精准控制 ---
with st.sidebar:
    st.title("🛡️ 组合回测引擎")
    codes = st.text_input("代码 (空格分隔)", "513500 513100 510300").split()
    weights = st.text_input("权重 % (空格分隔)", "40 30 30").split()
    init_money = st.number_input("初始投入 (RMB)", value=10000, step=1000)
    bench_code = st.selectbox("对比基准", ["000300", "513500"], format_func=lambda x: "沪深300" if x=="000300" else "标普500")
    run = st.button("开始深度执行", type="primary", use_container_width=True)

if run:
    try:
        # 1. 权重校验
        w_list = [float(w)/100 for w in weights]
        if sum(w_list) != 1.0:
            st.error("❌ 权重加和不等于100%，请修正后再运行")
            st.stop()

        # 2. 并行数据对齐
        with st.spinner('🚀 正在同步全球复权行情...'):
            all_list = []
            for s in list(set(codes + [bench_code])):
                all_list.append(get_data(s))
            
            # 使用 inner join 确保所有基金在同一天都有交易，彻底杜绝 KeyError
            df_final = pd.concat(all_list, axis=1, join='inner').sort_index()
        
        # 3. 核心计算：基于日收益率的资产规模演变
        # 收益率矩阵
        returns = df_final.pct_change().dropna()
        
        # 组合日收益 = (基金A收益 * 权重A) + (基金B收益 * 权重B) ...
        port_daily_ret = (returns[codes] * w_list).sum(axis=1)
        # 基准日收益
        bench_daily_ret = returns[bench_code]
        
        # 累计资产 = 初始资金 * (1 + 累计日收益率)
        port_assets = (1 + port_daily_ret).cumprod() * init_money
        bench_assets = (1 + bench_daily_ret).cumprod() * init_money

        # --- 4. 极致交互图表 ---
        st.subheader("📈 资产增长曲线")
        
        fig = go.Figure()
        
        # 组合主线：悬浮显示精确到分的金额
        fig.add_trace(go.Scatter(
            x=port_assets.index, y=port_assets,
            name="我的资产组合",
            line=dict(color='#E63946', width=3),
            hovertemplate="日期: %{x|%Y-%m-%d}<br>总资产: ¥%{y:,.2f}<extra></extra>"
        ))
        
        # 基准曲线
        fig.add_trace(go.Scatter(
            x=bench_assets.index, y=bench_assets,
            name=f"基准: {bench_code}",
            line=dict(color='#A8DADC', dash='dot'),
            hovertemplate="基准价值: ¥%{y:,.2f}<extra></extra>"
        ))

        # 整合：点击切换 + 底部滑块 + 坐标轴格式
        fig.update_xaxes(
            rangeslider_visible=True, # 保留手动拉动滑块
            rangeselector=dict(       # 回归时间点击模块
                buttons=list([
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=3, label="3月", step="month", stepmode="backward"),
                    dict(count=6, label="6月", step="month", stepmode="backward"),
                    dict(count=1, label="今年来", step="year", stepmode="todate"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(step="all", label="全部视图")
                ])
            )
        )
        
        fig.update_layout(
            hovermode="x unified", # 移动鼠标同时看两根线的净值
            yaxis=dict(tickformat=",.0f", title="资产规模 (RMB)"), # 格式化数字，禁止k缩写
            template="plotly_white",
            height=650,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # --- 5. 核心绩效看板 ---
        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        total_ret = (port_assets.iloc[-1] / init_money - 1) * 100
        mdd = ((port_assets / port_assets.cummax() - 1).min()) * 100
        
        c1.metric("期末资产", f"¥{port_assets.iloc[-1]:,.2f}")
        c2.metric("累计收益率", f"{total_ret:.2f}%")
        c3.metric("最大回撤", f"{mdd:.2f}%")
        c4.metric("跑赢基准", f"{total_ret - ((bench_assets.iloc[-1]/init_money-1)*100):.2f}%")

    except Exception as e:
        st.error(f"⚠️ 执行出错: {str(e)}")
        st.info("提示：请确认输入的代码是否存在，且权重数量与代码数量匹配。")
