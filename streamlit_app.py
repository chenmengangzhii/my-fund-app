import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import datetime
import numpy as np

st.set_page_config(page_title="高级基金投研终端", layout="wide")

# 保底翻译字典，解决名称加载不出问题
NAME_MAP = {
    "513500": "标普500ETF", "513100": "纳指ETF", "518880": "黄金ETF",
    "510300": "沪深300ETF", "512890": "红利低波ETF", "510500": "中证500ETF"
}

with st.sidebar:
    st.header("⚙️ 组合配置")
    codes_input = st.text_input("基金代码 (空格分隔)", "513500 513100 518880")
    weights_input = st.text_input("设定比例 % (空格分隔)", "40 30 30")
    
    st.header("💵 投资模式")
    invest_type = st.radio("选择模式", ["一次性投入", "按月定投"])
    money = st.number_input("金额 (RMB)", value=10000)
    
    st.header("📅 时间与基准")
    history_years = st.slider("回测时长 (年)", 1, 10, 3)
    benchmark_code = st.selectbox("对比基准", ["510300 (沪深300)", "513100 (纳指ETF)", "518880 (黄金ETF)"])
    analyze_btn = st.button("开始分析", type="primary")

if analyze_btn:
    symbols = codes_input.split()
    weights = [float(w)/100 for w in weights_input.split()]
    bench_symbol = benchmark_code.split()[0]
    
    with st.spinner('正在同步全球金融数据...'):
        all_data = pd.DataFrame()
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=365*history_years)).strftime("%Y%m%d")
        
        # 1. 获取组合数据
        for i, s in enumerate(symbols):
            f_name = NAME_MAP.get(s, s)
            df = ak.fund_etf_hist_em(symbol=s, period="daily", start_date=start, end_date=end, adjust="qfq")
            df = df[['日期', '收盘']].rename(columns={'收盘': f_name})
            df['日期'] = pd.to_datetime(df['日期'])
            if all_data.empty: all_data = df
            else: all_data = pd.merge(all_data, df, on='日期', how='inner')
        
        # 2. 获取基准数据
        bench_df = ak.fund_etf_hist_em(symbol=bench_symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
        bench_df['日期'] = pd.to_datetime(bench_df['日期'])
        bench_df = bench_df[['日期', '收盘']].rename(columns={'收盘': '基准'})
        
        all_data = pd.merge(all_data, bench_df, on='日期', how='inner').set_index('日期')
        
        # 3. 计算收益
        rets = all_data.pct_change().dropna()
        port_ret = (rets.drop(columns=['基准']) * weights).sum(axis=1)
        
        if invest_type == "一次性投入":
            # 净值计算
            port_val = (1 + port_ret).cumprod() * money
            bench_val = (1 + rets['基准']).cumprod() * money
            total_invested = money
        else:
            # 定投模拟逻辑
            port_val = []
            bench_val = []
            current_port_hold = 0
            current_bench_hold = 0
            total_invested = 0
            
            # 简化逻辑：每月第一个交易日扣款
            last_month = -1
            for date, ret in port_ret.items():
                if date.month != last_month:
                    current_port_hold += money
                    current_bench_hold += money
                    total_invested += money
                    last_month = date.month
                
                current_port_hold *= (1 + ret)
                current_bench_hold *= (1 + rets['基准'][date])
                port_val.append(current_port_hold)
                bench_val.append(current_bench_hold)
            
            port_val = pd.Series(port_val, index=port_ret.index)
            bench_val = pd.Series(bench_val, index=port_ret.index)

        # --- 显示结果 ---
        st.subheader(f"🏁 绩效分析 ({invest_type})")
        c1, c2, c3, c4 = st.columns(4)
        
        port_final = port_val.iloc[-1]
        bench_final = bench_val.iloc[-1]
        total_ret = (port_final / total_invested - 1) * 100
        bench_ret = (bench_final / total_invested - 1) * 100
        
        c1.metric("最终资产", f"¥{port_final:,.2f}", f"{port_final-bench_final:+.2f} 较基准")
        c2.metric("组合收益率", f"{total_ret:.2f}%")
        c3.metric("基准收益率", f"{bench_ret:.2f}%")
        c4.metric("累计投入", f"¥{total_invested:,.0f}")

        # 曲线图
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=port_val.index, y=port_val, name="我的组合", line=dict(color='#e63946', width=2)))
        fig.add_trace(go.Scatter(x=bench_val.index, y=bench_val, name=f"基准({benchmark_code})", line=dict(color='#bdc3c7', dash='dash')))
        fig.update_layout(template="plotly_white", hovermode="x unified", height=450)
        st.plotly_chart(fig, use_container_width=True)

        # 详细收益列表
        st.subheader("📋 资产明细")
        asset_names = [NAME_MAP.get(s, s) for s in symbols]
        detail_df = pd.DataFrame({
            "资产": asset_names,
            "代码": symbols,
            "占比": [f"{w*100:.0f}%" for w in weights],
            "区间涨跌": [f"{(all_data[n].iloc[-1]/all_data[n].iloc[0]-1)*100:+.2f}%" for n in asset_names]
        })
        st.table(detail_df)
