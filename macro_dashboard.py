"""日本マクロ経済ダッシュボード."""

from __future__ import annotations

import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db.client import get_connection

logger = logging.getLogger(__name__)

# 表示ラベルの定義
INDICATOR_LABELS: dict[str, str] = {
    "CPI": "消費者物価指数（CPI）",
    "GDP": "国内総生産（GDP）",
    "UNEMPLOYMENT": "完全失業率",
    "M2": "マネーサプライ（M2）",
    "POLICY_RATE": "政策金利",
    "USDJPY": "円ドル為替レート（USD/JPY）",
    "OUTPUT_GAP": "需給ギャップ",
    "LONG_RATE": "長期金利（10年国債）",
}

# CPI 品目別の indicator_code リスト
CPI_CATEGORY_CODES = [
    "CPI_食料", "CPI_住居", "CPI_光熱・水道", "CPI_家具・家事用品",
    "CPI_被服及び履物", "CPI_保健医療", "CPI_交通・通信",
    "CPI_教育", "CPI_教養娯楽", "CPI_諸雑費",
]

# 2列グリッドで表示する指標（ORDER を保証）
GRID_INDICATORS = [
    "CPI", "GDP", "UNEMPLOYMENT", "M2", "POLICY_RATE", "USDJPY",
    "LONG_RATE",
]

# 全幅で表示する指標
FULL_WIDTH_INDICATORS = ["OUTPUT_GAP"]


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    """mart_indicators を全件読み込む."""
    conn = get_connection()
    df = conn.execute("""
        SELECT date, indicator_code, frequency, value, yoy_change, mom_change, unit
        FROM mart_indicators
        ORDER BY indicator_code, date
    """).df()
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_latest_updated_at() -> str:
    """mart_indicators の最終更新日時を取得する."""
    conn = get_connection()
    result = conn.execute("SELECT MAX(updated_at) FROM mart_indicators").fetchone()
    conn.close()
    if result and result[0]:
        return str(result[0])[:16]
    return "データなし"


def render_chart(df: pd.DataFrame, code: str, year_range: tuple[int, int]) -> None:
    """指定指標のグラフを描画する."""
    indicator_df = df[
        (df["indicator_code"] == code)
        & (df["date"].dt.year >= year_range[0])
        & (df["date"].dt.year <= year_range[1])
    ].copy()

    label = INDICATOR_LABELS.get(code, code)
    st.subheader(label)

    if indicator_df.empty:
        st.info("データがありません")
        return

    unit = indicator_df["unit"].iloc[0] if not indicator_df.empty else ""
    st.caption(f"単位: {unit}")

    fig = px.line(
        indicator_df,
        x="date",
        y="value",
        labels={"date": "", "value": unit},
    )
    fig.update_layout(margin={"t": 10, "b": 10})
    st.plotly_chart(fig, use_container_width=True)

    # 直近値・前年同月比・前期比をメトリクスで表示
    latest = indicator_df.iloc[-1]
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "直近値", f"{latest['value']:.2f}" if pd.notna(latest["value"]) else "N/A"
    )
    col2.metric(
        "前年同月比" if latest["frequency"] == "monthly" else "前年同期比",
        f"{latest['yoy_change']:.2f}%" if pd.notna(latest["yoy_change"]) else "N/A",
    )
    col3.metric(
        "前月比" if latest["frequency"] == "monthly" else "前期比",
        f"{latest['mom_change']:.2f}%" if pd.notna(latest["mom_change"]) else "N/A",
    )


def render_output_gap_chart(df: pd.DataFrame, year_range: tuple[int, int]) -> None:
    """需給ギャップ専用グラフを描画する（0を境に正負で色分け）."""
    indicator_df = df[
        (df["indicator_code"] == "OUTPUT_GAP")
        & (df["date"].dt.year >= year_range[0])
        & (df["date"].dt.year <= year_range[1])
    ].copy()

    st.subheader("需給ギャップ")

    if indicator_df.empty:
        st.info("データがありません")
        return

    unit = indicator_df["unit"].iloc[0]
    st.caption(f"単位: {unit}")

    colors = indicator_df["value"].apply(
        lambda x: "#e74c3c" if x >= 0 else "#3498db"
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=indicator_df["date"],
        y=indicator_df["value"],
        marker_color=colors,
        hovertemplate="%{x|%Y年%m月}<br>需給ギャップ: %{y:.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_width=1.5, line_color="gray")

    y_max = float(indicator_df["value"].max())
    y_min = float(indicator_df["value"].min())

    fig.add_annotation(
        xref="paper", yref="y",
        x=0.01, y=y_max * 0.85 if y_max > 0 else 0.3,
        text="▲ 需要超過（インフレ圧力）",
        showarrow=False,
        font={"color": "#e74c3c", "size": 12},
        xanchor="left",
    )
    fig.add_annotation(
        xref="paper", yref="y",
        x=0.01, y=y_min * 0.85 if y_min < 0 else -0.3,
        text="▼ 供給超過（デフレ圧力）",
        showarrow=False,
        font={"color": "#3498db", "size": 12},
        xanchor="left",
    )

    fig.update_layout(
        margin={"t": 10, "b": 10},
        yaxis_title=unit,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    latest = indicator_df.iloc[-1]
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "直近値", f"{latest['value']:.2f}" if pd.notna(latest["value"]) else "N/A"
    )
    col2.metric(
        "前年同期比",
        f"{latest['yoy_change']:.2f}%" if pd.notna(latest["yoy_change"]) else "N/A",
    )
    col3.metric(
        "前期比",
        f"{latest['mom_change']:.2f}%" if pd.notna(latest["mom_change"]) else "N/A",
    )


def render_cpi_multi_line(df: pd.DataFrame, year_range: tuple[int, int]) -> None:
    """CPI 品目別の指数推移を1グラフに重ねて表示する."""
    category_df = df[
        df["indicator_code"].isin(CPI_CATEGORY_CODES)
        & (df["date"].dt.year >= year_range[0])
        & (df["date"].dt.year <= year_range[1])
    ].copy()

    st.subheader("消費者物価指数（CPI）- 品目別推移")

    if category_df.empty:
        st.info("データがありません")
        return

    unit = category_df["unit"].iloc[0]
    st.caption(f"単位: {unit}")

    category_df["品目"] = category_df["indicator_code"].str.replace("CPI_", "", regex=False)

    fig = px.line(
        category_df,
        x="date",
        y="value",
        color="品目",
        labels={"date": "", "value": unit, "品目": "品目"},
    )
    # 品目別の線を細くして背景に退かせる
    fig.update_traces(line_width=1, opacity=0.5)

    # 総合 CPI を太い黒線で重ねて強調
    total_df = df[
        (df["indicator_code"] == "CPI")
        & (df["date"].dt.year >= year_range[0])
        & (df["date"].dt.year <= year_range[1])
    ]
    if not total_df.empty:
        fig.add_trace(go.Scatter(
            x=total_df["date"],
            y=total_df["value"],
            mode="lines",
            name="総合",
            line={"color": "black", "width": 3},
        ))

    fig.update_layout(margin={"t": 10, "b": 10})
    st.plotly_chart(fig, use_container_width=True)

    # 直近値メトリクスは総合 CPI を参照
    cpi_df = df[
        (df["indicator_code"] == "CPI")
        & (df["date"].dt.year >= year_range[0])
        & (df["date"].dt.year <= year_range[1])
    ]
    if not cpi_df.empty:
        latest = cpi_df.iloc[-1]
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "総合 直近値", f"{latest['value']:.2f}" if pd.notna(latest["value"]) else "N/A"
        )
        col2.metric(
            "前年同月比",
            f"{latest['yoy_change']:.2f}%" if pd.notna(latest["yoy_change"]) else "N/A",
        )
        col3.metric(
            "前月比",
            f"{latest['mom_change']:.2f}%" if pd.notna(latest["mom_change"]) else "N/A",
        )


def render_cpi_breakdown(df: pd.DataFrame, year_range: tuple[int, int]) -> None:
    """CPI 品目別前年同月比の横棒グラフを描画する."""
    breakdown_df = df[
        df["indicator_code"].isin(CPI_CATEGORY_CODES)
        & (df["date"].dt.year >= year_range[0])
        & (df["date"].dt.year <= year_range[1])
    ].copy()

    if breakdown_df.empty:
        return

    latest_date = breakdown_df["date"].max()
    latest_df = breakdown_df[breakdown_df["date"] == latest_date].dropna(subset=["yoy_change"]).copy()

    if latest_df.empty:
        return

    latest_df["label"] = latest_df["indicator_code"].str.replace("CPI_", "", regex=False)
    latest_df = latest_df.sort_values("yoy_change", ascending=True)
    latest_df["方向"] = latest_df["yoy_change"].apply(lambda x: "上昇" if x >= 0 else "下落")

    fig = px.bar(
        latest_df,
        x="yoy_change",
        y="label",
        orientation="h",
        color="方向",
        color_discrete_map={"上昇": "#e74c3c", "下落": "#3498db"},
        labels={"yoy_change": "前年同月比（%）", "label": ""},
        title=f"品目別 前年同月比（{latest_date.strftime('%Y年%m月')}）",
    )
    fig.add_vline(x=0, line_width=1, line_color="gray")
    fig.update_layout(showlegend=True, margin={"t": 40, "b": 10})
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    """ダッシュボードのエントリーポイント."""
    st.set_page_config(
        page_title="日本マクロ経済ダッシュボード",
        page_icon="📊",
        layout="wide",
    )

    # ------------------------------------------------------------------
    # ヘッダー
    # ------------------------------------------------------------------
    st.title("📊 日本マクロ経済ダッシュボード")
    updated_at = get_latest_updated_at()
    st.caption(f"最終更新: {updated_at}")

    # ------------------------------------------------------------------
    # データ読み込み
    # ------------------------------------------------------------------
    df = load_data()

    if df.empty:
        st.warning(
            "データが存在しません。先に `python pipeline.py` を実行してください。"
        )
        return

    # ------------------------------------------------------------------
    # サイドバー: 期間スライダー
    # ------------------------------------------------------------------
    min_year = int(df["date"].dt.year.min())
    max_year = int(df["date"].dt.year.max())

    with st.sidebar:
        st.header("表示期間")
        year_range = st.slider(
            "年範囲",
            min_value=min_year,
            max_value=max_year,
            value=(max(min_year, max_year - 10), max_year),
            step=1,
        )

    # ------------------------------------------------------------------
    # 2列グリッド: 6指標
    # ------------------------------------------------------------------
    st.divider()
    codes_in_data = df["indicator_code"].unique()
    grid_codes = [c for c in GRID_INDICATORS if c in codes_in_data]

    for i in range(0, len(grid_codes), 2):
        cols = st.columns(2)
        for j, code in enumerate(grid_codes[i : i + 2]):
            with cols[j]:
                if code == "CPI":
                    render_cpi_multi_line(df, year_range)
                    render_cpi_breakdown(df, year_range)
                else:
                    render_chart(df, code, year_range)

    # ------------------------------------------------------------------
    # 全幅: 需給ギャップ
    # ------------------------------------------------------------------
    st.divider()
    if "OUTPUT_GAP" in codes_in_data:
        render_output_gap_chart(df, year_range)


if __name__ == "__main__":
    main()
