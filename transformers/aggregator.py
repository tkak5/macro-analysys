"""Aggregator: raw 層を読み込み mart_indicators へ書き込む."""

from __future__ import annotations

import logging
from datetime import datetime

import duckdb
import pandas as pd

from transformers.base_transformer import BaseTransformer

logger = logging.getLogger(__name__)


class Aggregator(BaseTransformer):
    """raw_* テーブルを読み込み、mart_indicators に統一フォーマットで書き込む."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        super().__init__(conn)

    def transform(self) -> None:
        """全 raw テーブルから mart_indicators を構築する（全件再構築）."""
        logger.info("Aggregator: 開始")

        frames: list[pd.DataFrame] = [
            self._build_cpi(),
            self._build_gdp(),
            self._build_unemployment(),
            self._build_m2(),
            self._build_policy_rate(),
            self._build_exchange_rate(),
            self._build_output_gap(),
        ]

        non_empty = [f for f in frames if not f.empty]
        if not non_empty:
            logger.warning("Aggregator: 書き込むデータがありません")
            return
        df = pd.concat(non_empty, ignore_index=True)

        df["updated_at"] = datetime.now()

        # 全件再構築
        self.conn.execute("DELETE FROM mart_indicators")
        self.conn.execute("INSERT INTO mart_indicators SELECT * FROM df")
        logger.info("Aggregator: %d 件を mart_indicators に書き込みました", len(df))

    # ------------------------------------------------------------------
    # 各指標の変換メソッド
    # ------------------------------------------------------------------

    def _build_cpi(self) -> pd.DataFrame:
        """raw_cpi → mart_indicators 形式に変換する."""
        try:
            df = self.conn.execute("""
                SELECT date, value, unit
                FROM raw_cpi
                WHERE category = '総合'
                ORDER BY date
            """).df()
        except Exception:
            logger.warning("CPI: raw テーブルが空またはエラー")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        return pd.DataFrame(
            {
                "date": df["date"],
                "indicator_code": "CPI",
                "frequency": "monthly",
                "value": df["value"],
                "yoy_change": None,
                "mom_change": None,
                "unit": df["unit"],
            }
        )

    def _build_gdp(self) -> pd.DataFrame:
        """raw_gdp → mart_indicators 形式に変換する."""
        try:
            df = self.conn.execute("""
                SELECT date, value, unit
                FROM raw_gdp
                ORDER BY date
            """).df()
        except Exception:
            logger.warning("GDP: raw テーブルが空またはエラー")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        return pd.DataFrame(
            {
                "date": df["date"],
                "indicator_code": "GDP",
                "frequency": "quarterly",
                "value": df["value"],
                "yoy_change": None,
                "mom_change": None,
                "unit": df["unit"],
            }
        )

    def _build_unemployment(self) -> pd.DataFrame:
        """raw_unemployment → mart_indicators 形式に変換する."""
        try:
            df = self.conn.execute("""
                SELECT date, value, unit
                FROM raw_unemployment
                ORDER BY date
            """).df()
        except Exception:
            logger.warning("失業率: raw テーブルが空またはエラー")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        return pd.DataFrame(
            {
                "date": df["date"],
                "indicator_code": "UNEMPLOYMENT",
                "frequency": "monthly",
                "value": df["value"],
                "yoy_change": None,
                "mom_change": None,
                "unit": df["unit"],
            }
        )

    def _build_m2(self) -> pd.DataFrame:
        """raw_money_supply → mart_indicators 形式に変換する."""
        try:
            df = self.conn.execute("""
                SELECT date, value, unit
                FROM raw_money_supply
                WHERE series_code = 'MAM1NAM2M2MO'
                ORDER BY date
            """).df()
        except Exception:
            logger.warning("M2: raw テーブルが空またはエラー")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        return pd.DataFrame(
            {
                "date": df["date"],
                "indicator_code": "M2",
                "frequency": "monthly",
                "value": df["value"],
                "yoy_change": None,
                "mom_change": None,
                "unit": df["unit"],
            }
        )

    def _build_policy_rate(self) -> pd.DataFrame:
        """raw_policy_rate → mart_indicators 形式に変換する."""
        try:
            df = self.conn.execute("""
                SELECT date, value, unit
                FROM raw_policy_rate
                ORDER BY date
            """).df()
        except Exception:
            logger.warning("政策金利: raw テーブルが空またはエラー")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        return pd.DataFrame(
            {
                "date": df["date"],
                "indicator_code": "POLICY_RATE",
                "frequency": "monthly",
                "value": df["value"],
                "yoy_change": None,
                "mom_change": None,
                "unit": df["unit"],
            }
        )

    def _build_exchange_rate(self) -> pd.DataFrame:
        """raw_exchange_rate → mart_indicators 形式に変換する."""
        try:
            df = self.conn.execute("""
                SELECT date, value, unit
                FROM raw_exchange_rate
                ORDER BY date
            """).df()
        except Exception:
            logger.warning("為替: raw テーブルが空またはエラー")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        return pd.DataFrame(
            {
                "date": df["date"],
                "indicator_code": "USDJPY",
                "frequency": "monthly",
                "value": df["value"],
                "yoy_change": None,
                "mom_change": None,
                "unit": df["unit"],
            }
        )

    def _build_output_gap(self) -> pd.DataFrame:
        """raw_output_gap → mart_indicators 形式に変換する."""
        try:
            df = self.conn.execute("""
                SELECT date, value, unit
                FROM raw_output_gap
                ORDER BY date
            """).df()
        except Exception:
            logger.warning("需給ギャップ: raw テーブルが空またはエラー")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        return pd.DataFrame(
            {
                "date": df["date"],
                "indicator_code": "OUTPUT_GAP",
                "frequency": "quarterly",
                "value": df["value"],
                "yoy_change": None,
                "mom_change": None,
                "unit": df["unit"],
            }
        )
