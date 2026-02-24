"""Calculator: mart_indicators の yoy_change / mom_change を計算・更新する."""

from __future__ import annotations

import logging

import duckdb
import pandas as pd

from transformers.base_transformer import BaseTransformer

logger = logging.getLogger(__name__)


class Calculator(BaseTransformer):
    """mart_indicators の前年同月比・前期比を計算して更新する."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        super().__init__(conn)

    def transform(self) -> None:
        """yoy_change と mom_change を計算し mart_indicators を更新する."""
        logger.info("Calculator: 開始")

        df = self.conn.execute("""
            SELECT date, indicator_code, frequency, value
            FROM mart_indicators
            ORDER BY indicator_code, date
        """).df()

        if df.empty:
            logger.warning("Calculator: mart_indicators が空です")
            return

        df["date"] = pd.to_datetime(df["date"])
        results: list[pd.DataFrame] = []

        for code, group in df.groupby("indicator_code"):
            g = group.sort_values("date").copy()
            freq = g["frequency"].iloc[0]

            if freq == "monthly":
                yoy_periods = 12
                mom_periods = 1
            else:  # quarterly
                yoy_periods = 4
                mom_periods = 1

            g["yoy_change"] = g["value"].pct_change(periods=yoy_periods) * 100
            g["mom_change"] = g["value"].pct_change(periods=mom_periods) * 100
            results.append(g)

        result_df = pd.concat(results, ignore_index=True)

        # 計算結果を mart_indicators へ反映
        for _, row in result_df.iterrows():
            yoy = float(row["yoy_change"]) if pd.notna(row["yoy_change"]) else None
            mom = float(row["mom_change"]) if pd.notna(row["mom_change"]) else None
            self.conn.execute(
                """
                UPDATE mart_indicators
                SET yoy_change = ?, mom_change = ?
                WHERE date = ? AND indicator_code = ?
            """,
                [yoy, mom, row["date"].date(), row["indicator_code"]],
            )

        logger.info(
            "Calculator: 変化率の計算・更新完了（%d 指標）",
            len(df["indicator_code"].unique()),
        )
