import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta

# ================= 页面配置 =================
st.set_page_config(
    page_title="私人投研终端",
    layout="wide"
)

st.title("📊 私人投研终端（数据校验版）")

# ================= 智能行情抓取 =================
@st.cache_data(ttl=3600)
def get_data_smart(symbol: str) -> pd.DataFrame:
    """
    优先 ETF / 基金 → 再尝试指数
    返回：index=datetime，列名=symbol（复权收盘价）
    """
    try:
        df = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date="20000101",
            end_date="20300101",
            adjust="hfq"
        )
        if df.empty:
            raise ValueError
        df = df[['日期', '收盘']].rename(columns={'日期': 'date', '收盘': symbol})
    except Exception:
        try:
            df = ak.stock_zh_index_daily_em(symbol=symbol)
            df = df[['date', 'close']].rename(columns={'close': symbol})
        except Exception:
            return pd.DataFrame()

    df['date'] = pd.to_datetime(df['date'])
    return df.set_index('date').sort_index()

# ================= 侧边栏 =================
with st.sidebar:
    st.header("⚙️ 组合配置")

    codes_input = st.text_input(
        "基金 / ETF 代码（空格分隔）",
        "513500 513100 510300"
    )
    weights_input = st.text_input(
        "对应权重 %（顺序一致）",
        "40 30 30"
    )
    initial_money = st.number_input(
        "初始投入金额（元）",
        value=10000,
        step=1000
    )

    st.divider()

    st.header("📈 基准设置")
    bench_code = st.text_input("基准代码（指数或 ETF）", "000300")

    st.divider()

    analyze_btn = st.button("🚀 生成回测报告", type="primary")

# ================= 主逻辑 =================
if analyze_btn:
    # ---------- 参数校验 ----------
    symbols = codes_input.split()
    weights = [float(w) / 100 for w in weights_input.split()]

    if len(symbols) != len(weights):
        st.error("❌ 基金数量与权重数量不一致")
        st.stop()

    if abs(sum(weights) - 1) > 1e-6:
        st.error("❌ 权重之和必须等于 100%")
        st.stop()

    all_symbols = list(set(symbols + [bench_code]))

    # ---------- 数据获取 ----------
    with st.spinner("📡 正在同步复权行情数据..."):
        dfs = []
        for s in all_symbols:
            df_tmp = get_data_smart(s)
            if df_tmp.empty:
                st.error(f"❌ 无法获取行情数据：{s}")
                st.stop()
            dfs.append(df_tmp)

        price_data = pd.concat(dfs, axis=1, join="inner").sort_index()

    st.success("✅ 行情数据加载完成")

    # ================= 回测函数 =================
    def run_backtest(start_date):
        sub_price = price_data.loc[start_date:]
        if sub_price.empty:
            return None

        # 日收益率
        daily_ret = sub_price.pct_change().fillna(0)

        # 组合净值（收益率法）
        portfolio_nav = (1 + (daily_ret[symbols] * weights).sum(axis=1)).cumprod()

        # 基准净值（真实价格归一）
        benchmark_nav = sub_price[bench_code] / sub_price[bench_code].iloc[0]

        # 各基金净值
        fund_navs = sub_price[symbols] / sub_price[symbols].iloc[0]

        result = pd.DataFrame({
            "portfolio_nav": portfolio_nav,
            "benchmark_nav": benchmark_nav,
            "portfolio_value": portfolio_nav * initial_money,
            "benchmark_value": benchmark_nav * initial_money
        })

        return result, fund_navs, daily_ret

    # ================= 回测区间 =================
    now = price_data.index[-1]
    periods = {
        "近1月": now - timedelta(days=30),
        "近6月": now - timedelta(days=180),
        "近1年": now - timedelta(days=365),
        "近3年": now - timedelta(days=365 * 3),
        "全部": price_data.index[0]
    }

    tabs = st.tabs(periods.keys())

    for tab, (label, start_dt) in zip(tabs, periods.items()):
        with tab:
            res = run_backtest(start_dt)
            if res is None:
                st.warning("该区间无数据")
                continue

            result_df, fund_navs, daily_ret = res

            # ================= 主图：组合 vs 基准 =================
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=result_df.index,
                y=result_df["portfolio_value"],
                name="我的组合",
                line=dict(width=3),
                hovertemplate="资产：¥%{y:,.2f}<extra></extra>"
            ))

            fig.add_trace(go.Scatter(
                x=result_df.index,
                y=result_df["benchmark_value"],
                name=f"基准：{bench_code}",
                line=dict(width=2, dash="dot"),
                hovertemplate="资产：¥%{y:,.2f}<extra></extra>"
            ))

            fig.update_layout(
                title=f"📈 组合 vs 基准（{label}）",
                hovermode="x unified",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                xaxis=dict(title="日期", rangeslider_visible=True),
                yaxis=dict(title="资产价值（元）", tickformat=",.0f"),
                height=600,
                template="plotly_white",
                margin=dict(l=10, r=10, t=60, b=10)
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False}
            )

            # ================= 指标 =================
            final_value = result_df["portfolio_value"].iloc[-1]
            total_return = (result_df["portfolio_nav"].iloc[-1] - 1) * 100
            bench_return = (result_df["benchmark_nav"].iloc[-1] - 1) * 100
            max_dd = ((result_df["portfolio_value"] /
                       result_df["portfolio_value"].cummax()) - 1).min() * 100

            c1, c2, c3 = st.columns(3)
            c1.metric("期末资产", f"¥{final_value:,.2f}")
            c2.metric("阶段收益率", f"{total_return:.2f}%", delta=f"{total_return - bench_return:.2f}% vs 基准")
            c3.metric("最大回撤", f"{max_dd:.2f}%")

            # ================= 子图：组合内基金趋势 =================
            fig2 = go.Figure()
            for s in symbols:
                fig2.add_trace(go.Scatter(
                    x=fund_navs.index,
                    y=fund_navs[s],
                    name=s,
                    hovertemplate="净值：%{y:.4f}<extra></extra>"
                ))

            fig2.update_layout(
                title="📌 组合内基金净值趋势（起点=1）",
                hovermode="x unified",
                yaxis=dict(title="累计净值"),
                xaxis=dict(title="日期"),
                height=350,
                template="plotly_white",
                margin=dict(l=10, r=10, t=50, b=10)
            )

            st.plotly_chart(
                fig2,
                use_container_width=True,
                config={"displayModeBar": False}
            )

            # ================= 超额净值 =================
            excess_nav = result_df["portfolio_nav"] / result_df["benchmark_nav"]

            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=excess_nav.index,
                y=excess_nav,
                name="超额净值"
            ))

            fig3.update_layout(
                title="📊 相对基准超额净值",
                yaxis=dict(title="超额净值"),
                xaxis=dict(title="日期"),
                height=300,
                template="plotly_white"
            )

            st.plotly_chart(
                fig3,
                use_container_width=True,
                config={"displayModeBar": False}
            )

            # ================= 单基金贡献度 =================
            contrib = (daily_ret[symbols] * weights).sum().sort_values(ascending=False)
            st.subheader("📐 单基金收益贡献度（区间累计）")
            st.bar_chart(contrib)

    st.caption(
        "📌 数据来源：AkShare（东方财富等官方公开行情）｜"
        "历史回测仅供研究，不构成任何投资建议"
    )
