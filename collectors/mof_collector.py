"""財務省 国債金利情報 コレクター（長期金利・10年国債）."""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd
import requests

from collectors.base import BaseCollector
from db.client import get_latest_date, upsert_raw

logger = logging.getLogger(__name__)

CSV_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"

# 元号オフセット（元号1年の西暦年 - 1）
_ERA_OFFSET: dict[str, int] = {
    "M": 1867,  # 明治
    "T": 1911,  # 大正
    "S": 1925,  # 昭和
    "H": 1988,  # 平成
    "R": 2018,  # 令和
}


class MofCollector(BaseCollector):
    """財務省 国債金利情報 CSV から長期金利（10年国債利回り月次平均）を収集する."""

    def fetch(self) -> pd.DataFrame:
        """使用しない（run() が処理するため）."""
        return pd.DataFrame()

    def save_raw(self, df: pd.DataFrame) -> None:
        """使用しない（run() が処理するため）."""

    def run(self) -> None:
        """長期金利を取得・保存する."""
        logger.info("MofCollector: 開始")
        self._run_long_rate()
        logger.info("MofCollector: 完了")

    def _run_long_rate(self) -> None:
        latest = get_latest_date(self.conn, "raw_long_rate")
        df = self._fetch_long_rate(since=latest)
        if not df.empty:
            upsert_raw(self.conn, "raw_long_rate", df, pk=["date"])

    def _fetch_long_rate(self, since: date | None = None) -> pd.DataFrame:
        """10年国債利回りの月次平均を取得する."""
        resp = requests.get(CSV_URL, timeout=30)
        resp.raise_for_status()

        # CP932 でデコード、先頭1行（タイトル）をスキップ
        text = resp.content.decode("cp932", errors="replace")
        df_raw = pd.read_csv(
            io.StringIO(text),
            skiprows=1,
            header=0,
        )

        # 列名: 「基準日」「1年」...「10年」...
        df_raw.columns = df_raw.columns.str.strip()
        if "10年" not in df_raw.columns:
            logger.error("MofCollector: '10年' 列が見つかりません: %s", df_raw.columns.tolist())
            return pd.DataFrame()

        df_raw = df_raw[["基準日", "10年"]].copy()
        df_raw["基準日"] = df_raw["基準日"].astype(str).str.strip()
        df_raw["10年"] = pd.to_numeric(df_raw["10年"], errors="coerce")
        df_raw = df_raw.dropna(subset=["10年"])

        # 元号日付 → date に変換
        df_raw["date"] = df_raw["基準日"].apply(_parse_japanese_date)
        df_raw = df_raw.dropna(subset=["date"])

        # since でフィルタリング（差分更新）
        if since:
            df_raw = df_raw[df_raw["date"] > since]

        if df_raw.empty:
            logger.info("MofCollector: 新規データなし")
            return pd.DataFrame()

        # 月次平均に集計
        df_raw["month"] = df_raw["date"].apply(lambda d: date(d.year, d.month, 1))
        monthly = (
            df_raw.groupby("month")["10年"]
            .mean()
            .reset_index()
            .rename(columns={"month": "date", "10年": "value"})
        )

        # since が指定されている場合、取得済み月を除外（月途中データが既にある場合）
        if since:
            monthly = monthly[monthly["date"] > since]

        monthly["unit"] = "%"
        monthly["fetched_at"] = datetime.now()

        logger.info("MofCollector: 長期金利 %d 件取得", len(monthly))
        return monthly


def _parse_japanese_date(date_str: str) -> date | None:
    """元号形式の日付文字列（例: 'S49.9.24', 'R6.1.15'）を date に変換する."""
    m = re.match(r"([MTSHR])(\d+)\.(\d+)\.(\d+)", date_str.strip())
    if not m:
        return None
    era, year_str, month_str, day_str = m.group(1), m.group(2), m.group(3), m.group(4)
    offset = _ERA_OFFSET.get(era)
    if offset is None:
        return None
    try:
        year = offset + int(year_str)
        return date(year, int(month_str), int(day_str))
    except ValueError:
        return None
