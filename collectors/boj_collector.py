"""日本銀行 時系列統計 API コレクター（M2・政策金利・為替）."""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd
import requests

from collectors.base import BaseCollector
from db.client import get_latest_date, upsert_raw

logger = logging.getLogger(__name__)

BASE_URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"

# シリーズコードと DB 名
M2_DB = "MD02"
M2_CODE = "MAM1NAM2M2MO"  # M2 平均残高（億円）

POLICY_RATE_DB = "FM02"
POLICY_RATE_CODE = "STRACLUCON"  # 無担保コールレート翌日物 月中平均（%/年）

EXCHANGE_DB = "FM08"
EXCHANGE_CODE = "FXERM07"  # 米ドル/円 月中平均



class BojCollector(BaseCollector):
    """日本銀行 API から M2・政策金利・為替レートを収集するコレクター."""

    def fetch(self) -> pd.DataFrame:
        """使用しない（run() が各指標を個別に処理するため）."""
        return pd.DataFrame()

    def save_raw(self, df: pd.DataFrame) -> None:
        """使用しない（run() が各指標を個別に処理するため）."""

    def run(self) -> None:
        """M2・政策金利・為替をそれぞれ取得・保存する."""
        logger.info("BojCollector: 開始")
        self._run_money_supply()
        self._run_policy_rate()
        self._run_exchange_rate()
        logger.info("BojCollector: 完了")

    # ------------------------------------------------------------------
    # M2
    # ------------------------------------------------------------------

    def _run_money_supply(self) -> None:
        latest = get_latest_date(self.conn, "raw_money_supply")
        df = self._fetch_series(
            db=M2_DB,
            code=M2_CODE,
            since=latest,
            unit="億円",
        )
        if not df.empty:
            df["series_code"] = M2_CODE
            upsert_raw(self.conn, "raw_money_supply", df, pk=["date", "series_code"])

    # ------------------------------------------------------------------
    # 政策金利
    # ------------------------------------------------------------------

    def _run_policy_rate(self) -> None:
        latest = get_latest_date(self.conn, "raw_policy_rate")
        df = self._fetch_series(
            db=POLICY_RATE_DB,
            code=POLICY_RATE_CODE,
            since=latest,
            unit="%",
        )
        if not df.empty:
            upsert_raw(self.conn, "raw_policy_rate", df, pk=["date"])

    # ------------------------------------------------------------------
    # 為替レート
    # ------------------------------------------------------------------

    def _run_exchange_rate(self) -> None:
        latest = get_latest_date(self.conn, "raw_exchange_rate")
        df = self._fetch_series(
            db=EXCHANGE_DB,
            code=EXCHANGE_CODE,
            since=latest,
            unit="円/ドル",
        )
        if not df.empty:
            upsert_raw(self.conn, "raw_exchange_rate", df, pk=["date"])

    # ------------------------------------------------------------------
    # 共通フェッチ
    # ------------------------------------------------------------------

    def _fetch_series(
        self,
        db: str,
        code: str,
        since: date | None,
        unit: str,
    ) -> pd.DataFrame:
        """BOJ API から指定シリーズのデータを取得する."""
        params: dict[str, str] = {
            "format": "json",
            "lang": "en",
            "db": db,
            "code": code,
        }
        if since:
            params["startDate"] = since.strftime("%Y%m")

        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()

        dates, values = self._extract_data(body)
        if not dates or not values:
            logger.warning("BOJ API: %s のデータが空です", code)
            return pd.DataFrame()

        rows = []
        for date_int, val in zip(dates, values):
            if val is None:
                continue
            try:
                value = float(val)
            except (ValueError, TypeError):
                continue
            parsed_date = _parse_boj_date(str(date_int))
            if parsed_date is None:
                continue
            rows.append(
                {
                    "date": parsed_date,
                    "value": value,
                    "unit": unit,
                    "fetched_at": datetime.now(),
                }
            )

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        # since でフィルタリング
        if since:
            df = df[df["date"] > since]
        logger.info("BOJ %s: %d 件取得", code, len(df))
        return df

    def _extract_data(self, body: dict) -> tuple[list, list]:
        """BOJ API レスポンスからデータポイントを抽出する.

        実際のレスポンス形式:
        {
            "RESULTSET": [{
                "VALUES": {
                    "SURVEY_DATES": [202301, 202302, ...],
                    "VALUES":        [1234.5, 1235.6, ...]
                }
            }]
        }
        """
        result_set = body.get("RESULTSET", [])
        if not result_set:
            return [], []
        values_block = result_set[0].get("VALUES", {})
        dates = values_block.get("SURVEY_DATES", [])
        vals = values_block.get("VALUES", [])
        return dates, vals


# ------------------------------------------------------------------
# 時刻パーサー
# ------------------------------------------------------------------


def _parse_boj_date(date_str: str) -> date | None:
    """BOJ API の日付文字列（例: '202001'）を date に変換する."""
    s = date_str.strip()
    try:
        return datetime.strptime(s[:6], "%Y%m").date()
    except ValueError:
        return None
