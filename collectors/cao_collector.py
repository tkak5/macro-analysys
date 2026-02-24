"""内閣府 需給ギャップ コレクター."""

from __future__ import annotations

import io
import logging
from datetime import date, datetime

import pandas as pd
import requests

from collectors.base import BaseCollector
from db.client import get_latest_date, upsert_raw

logger = logging.getLogger(__name__)

# 内閣府 月例経済報告 インデックスページ（gap xlsx リンクを動的に取得する）
_INDEX_URL = "https://www5.cao.go.jp/keizai3/getsurei/getsurei-index.html"
_CAO_BASE = "https://www5.cao.go.jp/keizai3/getsurei/"

# 四半期コード（ローマ数字）→ 開始月
_QUARTER_TO_MONTH: dict[str, int] = {
    "Ⅰ": 1,
    "Ⅱ": 4,
    "Ⅲ": 7,
    "Ⅳ": 10,
    "I": 1,
    "II": 4,
    "III": 7,
    "IV": 10,
    "1": 1,
    "2": 4,
    "3": 7,
    "4": 10,
}


class CaoCollector(BaseCollector):
    """内閣府から需給ギャップデータを収集するコレクター."""

    def fetch(self) -> pd.DataFrame:
        """需給ギャップ Excel をダウンロードして DataFrame を返す."""
        excel_bytes = self._download_latest_excel()
        df = self._parse_excel(excel_bytes)
        return df

    def save_raw(self, df: pd.DataFrame) -> None:
        """raw_output_gap テーブルに差分保存する."""
        latest = get_latest_date(self.conn, "raw_output_gap")
        if latest is not None:
            df = df[df["date"] > latest]
        if not df.empty:
            upsert_raw(self.conn, "raw_output_gap", df, pk=["date"])

    def _download_latest_excel(self) -> bytes:
        """最新の需給ギャップ Excel ファイルをダウンロードする.

        インデックスページをスクレイプして gap.xlsx のリンクを動的に取得する。
        """
        import re

        headers = {"User-Agent": "Mozilla/5.0 (compatible; macro-dashboard/1.0)"}
        index_resp = requests.get(_INDEX_URL, timeout=30, headers=headers)
        index_resp.raise_for_status()

        links = re.findall(r'href=["\']([^"\']*gap\.xlsx)["\']', index_resp.text, re.IGNORECASE)
        if not links:
            raise RuntimeError("内閣府インデックスページから gap.xlsx リンクが見つかりません")

        # 最初に見つかったリンクを使用（最新版）
        gap_path = links[0]
        url = gap_path if gap_path.startswith("http") else _CAO_BASE + gap_path
        resp = requests.get(url, timeout=30, headers=headers)
        resp.raise_for_status()
        logger.info("CAO: %s を取得しました", url)
        return resp.content

    def _parse_excel(self, excel_bytes: bytes) -> pd.DataFrame:
        """Excel の「四半期」シートを解析して DataFrame を返す.

        カラム構成（A〜C列）:
            A: 年（西暦）
            B: 四半期（Ⅰ〜Ⅳ）
            C: 需給ギャップ（%）
        """
        xls = pd.ExcelFile(io.BytesIO(excel_bytes))

        # シート名を柔軟に探す
        quarterly_sheet = None
        for name in xls.sheet_names:
            if "四半期" in str(name) or "quarterly" in str(name).lower():
                quarterly_sheet = name
                break

        if quarterly_sheet is None:
            raise RuntimeError(
                f"「四半期」シートが見つかりません。シート一覧: {xls.sheet_names}"
            )

        raw = pd.read_excel(
            io.BytesIO(excel_bytes),
            sheet_name=quarterly_sheet,
            header=None,
        )

        rows = []
        for _, row in raw.iterrows():
            year_val = row.iloc[0]
            quarter_val = row.iloc[1]
            gap_val = row.iloc[2]

            # ヘッダー行・空行をスキップ
            try:
                year = int(float(str(year_val)))
            except (ValueError, TypeError):
                continue
            if year < 1990 or year > 2100:
                continue

            quarter_str = str(quarter_val).strip()
            month = _QUARTER_TO_MONTH.get(quarter_str)
            if month is None:
                continue

            try:
                value = float(str(gap_val).replace(",", ""))
            except (ValueError, TypeError):
                continue

            rows.append(
                {
                    "date": date(year, month, 1),
                    "value": value,
                    "unit": "%",
                    "fetched_at": datetime.now(),
                }
            )

        df = pd.DataFrame(rows)
        logger.info("需給ギャップ: %d 件取得", len(df))
        return df
