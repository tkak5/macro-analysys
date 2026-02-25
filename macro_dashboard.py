"""日本マクロ経済ダッシュボード."""

from __future__ import annotations

import logging

import pandas as pd
import plotly.express as px
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
                render_chart(df, code, year_range)

    # ------------------------------------------------------------------
    # 全幅: 需給ギャップ
    # ------------------------------------------------------------------
    st.divider()
    for code in FULL_WIDTH_INDICATORS:
        if code in codes_in_data:
            render_chart(df, code, year_range)


if __name__ == "__main__":
    main()
