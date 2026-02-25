"""e-Stat API コレクター（CPI・GDP・失業率）."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime

import duckdb
import pandas as pd
import requests

from collectors.base import BaseCollector
from db.client import get_latest_date, upsert_raw

logger = logging.getLogger(__name__)

BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

# 統計表 ID
STATS_ID_CPI = "0003427113"  # 消費者物価指数（2020年基準）
STATS_ID_GDP = "0003109750"  # 四半期別GDP速報 実質季節調整系列
STATS_ID_UNEMPLOYMENT = "0003005865"  # 労働力調査 完全失業率（月次）


class EStatCollector(BaseCollector):
    """e-Stat API から CPI・GDP・失業率を収集するコレクター."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        super().__init__(conn)
        self.api_key = os.environ["ESTAT_API_KEY"]

    def fetch(self) -> pd.DataFrame:
        """使用しない（run() が各指標を個別に処理するため）."""
        return pd.DataFrame()

    def save_raw(self, df: pd.DataFrame) -> None:
        """使用しない（run() が各指標を個別に処理するため）."""

    def run(self) -> None:
        """CPI・GDP・失業率をそれぞれ取得・保存する."""
        logger.info("EStatCollector: 開始")
        self._run_cpi()
        self._run_gdp()
        self._run_unemployment()
        logger.info("EStatCollector: 完了")

    # ------------------------------------------------------------------
    # CPI
    # ------------------------------------------------------------------

    def _run_cpi(self) -> None:
        latest = get_latest_date(self.conn, "raw_cpi")
        df = self._fetch_cpi(since=latest)
        if not df.empty:
            upsert_raw(self.conn, "raw_cpi", df, pk=["date", "category"])

    def _fetch_cpi(self, since: date | None = None) -> pd.DataFrame:
        """CPI 品目別指数（全国・11カテゴリ）を取得する.

        e-Stat はデフォルト 100,000 件上限のため、対象カテゴリを cdCat01 で絞り込む。
        ステップ1: limit=1 でメタデータ（CLASS_INF）を取得しカテゴリコードを特定
        ステップ2: cdCat01 で絞り込んだデータを取得
        """
        base_params: dict[str, str] = {
            "appId": self.api_key,
            "statsDataId": STATS_ID_CPI,
            "cdArea": "00000",  # 全国
            "lang": "J",
        }

        # ステップ1: メタデータ取得（時間フィルタなし・limit=1）
        class_info = self._get_class_info({**base_params, "limit": "1"})

        # 「指数」（前年比除く）の表章項目コードを抽出
        tab_codes = {
            code
            for code, name in class_info.get("tab", {}).items()
            if "指数" in name and "前年" not in name
        }
        # 取得対象カテゴリ（完全一致）
        # e-Stat の名称は "0001 総合" 形式のためスペース以降を取り出して照合
        target_categories = {
            "総合", "食料", "住居", "光熱・水道", "家具・家事用品",
            "被服及び履物", "保健医療", "交通・通信", "教育", "教養娯楽", "諸雑費",
        }
        cat_code_to_name = {
            code: full_name.split(" ", 1)[-1]
            for code, full_name in class_info.get("cat01", {}).items()
            if full_name.split(" ", 1)[-1] in target_categories
        }
        if not cat_code_to_name:
            logger.warning("CPI: 対象カテゴリコードが見つかりません")
            return pd.DataFrame()

        # ステップ2: 対象カテゴリコードを cdCat01 で絞り込んでデータ取得
        data_params: dict[str, str] = {
            **base_params,
            "cdCat01": ",".join(cat_code_to_name.keys()),
        }
        if since:
            data_params["cdTimeFrom"] = since.strftime("%Y%m")

        values, _ = self._request(data_params)
        if not values:
            return pd.DataFrame()

        rows = []
        for v in values:
            if v.get("@tab") not in tab_codes:
                continue
            cat_code = v.get("@cat01")
            if cat_code not in cat_code_to_name:
                continue
            val_str = v.get("$", "")
            if val_str in ("", "-", "***", "…", "..."):
                continue
            rows.append(
                {
                    "date": _parse_monthly_time(v["@time"]),
                    "category": cat_code_to_name[cat_code],
                    "value": float(val_str),
                    "unit": "指数（2020年=100）",
                    "fetched_at": datetime.now(),
                }
            )

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).dropna(subset=["date"])
        logger.info("CPI: %d 件取得", len(df))
        return df

    # ------------------------------------------------------------------
    # GDP
    # ------------------------------------------------------------------

    def _run_gdp(self) -> None:
        latest = get_latest_date(self.conn, "raw_gdp")
        df = self._fetch_gdp(since=latest)
        if not df.empty:
            upsert_raw(self.conn, "raw_gdp", df, pk=["date"])

    def _fetch_gdp(self, since: date | None = None) -> pd.DataFrame:
        """実質 GDP（支出側、季節調整済）を取得する."""
        params: dict[str, str] = {
            "appId": self.api_key,
            "statsDataId": STATS_ID_GDP,
            "lang": "J",
        }
        # 四半期データの cdTimeFrom は YYYYQ 形式（Q: 1〜4）
        if since:
            q = (since.month - 1) // 3 + 1
            params["cdTimeFrom"] = f"{since.year}{q:02d}"

        values, class_info = self._request(params)
        if not values:
            return pd.DataFrame()

        # 「国内総生産（支出側）」を含む項目コードを探す
        gdp_codes = {
            code
            for code, name in class_info.get("cat01", {}).items()
            if "国内総生産" in name and "支出" in name
        }
        if not gdp_codes:
            # フォールバック: 最初の項目コード
            gdp_codes = {next(iter(class_info.get("cat01", {"0000": ""})))}

        rows = []
        for v in values:
            if v.get("@cat01") not in gdp_codes:
                continue
            val_str = v.get("$", "")
            if val_str in ("", "-", "***", "…", "..."):
                continue
            parsed_date = _parse_quarterly_time(v["@time"])
            if parsed_date is None:
                continue
            rows.append(
                {
                    "date": parsed_date,
                    "value": float(val_str),
                    "unit": "億円",
                    "fetched_at": datetime.now(),
                }
            )

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).dropna(subset=["date"])
        logger.info("GDP: %d 件取得", len(df))
        return df

    # ------------------------------------------------------------------
    # 失業率
    # ------------------------------------------------------------------

    def _run_unemployment(self) -> None:
        latest = get_latest_date(self.conn, "raw_unemployment")
        df = self._fetch_unemployment(since=latest)
        if not df.empty:
            upsert_raw(self.conn, "raw_unemployment", df, pk=["date"])

    def _fetch_unemployment(self, since: date | None = None) -> pd.DataFrame:
        """完全失業率（全国・総数）を取得する."""
        params: dict[str, str] = {
            "appId": self.api_key,
            "statsDataId": STATS_ID_UNEMPLOYMENT,
            "cdArea": "00000",  # 全国
            "lang": "J",
        }
        if since:
            params["cdTimeFrom"] = since.strftime("%Y%m")

        values, class_info = self._request(params)
        if not values:
            return pd.DataFrame()

        # 「完全失業率」を含む表章項目コードを抽出
        unemp_codes = {
            code
            for code, name in class_info.get("tab", {}).items()
            if "完全失業率" in name
        }
        # 性別: 「総数」を含むコードを抽出（「0001 総数」等の名称形式に対応）
        sex_codes = {
            code
            for code, name in class_info.get("cat01", {}).items()
            if any(t in name for t in ("総数", "男女計", "合計"))
        }

        rows = []
        for v in values:
            if unemp_codes and v.get("@tab") not in unemp_codes:
                continue
            if sex_codes and v.get("@cat01") not in sex_codes:
                continue
            val_str = v.get("$", "")
            if val_str in ("", "-", "***", "…", "..."):
                continue
            rows.append(
                {
                    "date": _parse_monthly_time(v["@time"]),
                    "value": float(val_str),
                    "unit": "%",
                    "fetched_at": datetime.now(),
                }
            )

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).dropna(subset=["date"])
        logger.info("失業率: %d 件取得", len(df))
        return df


    # ------------------------------------------------------------------
    # 共通
    # ------------------------------------------------------------------

    def _get_class_info(self, params: dict[str, str]) -> dict[str, dict[str, str]]:
        """e-Stat API から CLASS_INF（メタデータ）のみ取得する.

        STATUS=1（データなし）でも CLASS_INF は返るため、独立したメソッドとして分離。
        """
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        stat_data = body["GET_STATS_DATA"]["STATISTICAL_DATA"]
        class_info: dict[str, dict[str, str]] = {}
        for class_obj in stat_data["CLASS_INF"]["CLASS_OBJ"]:
            obj_id: str = class_obj["@id"]
            classes = class_obj["CLASS"]
            if isinstance(classes, dict):
                classes = [classes]
            class_info[obj_id] = {c["@code"]: c["@name"] for c in classes}
        return class_info

    def _request(
        self, params: dict[str, str]
    ) -> tuple[list[dict], dict[str, dict[str, str]]]:
        """e-Stat API にリクエストし、(values, class_info) を返す."""
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()

        result = body["GET_STATS_DATA"]["RESULT"]
        if result["STATUS"] == 1:
            # STATUS=1: 正常終了だが該当データなし（差分更新で新データなし時に発生）
            logger.info("e-Stat API: 該当データなし（STATUS=1）")
            return [], {}
        if result["STATUS"] != 0:
            raise RuntimeError(f"e-Stat API エラー: {result['ERROR_MSG']}")

        stat_data = body["GET_STATS_DATA"]["STATISTICAL_DATA"]
        values: list[dict] = stat_data["DATA_INF"]["VALUE"]

        # CLASS_INF を解析して {次元ID: {コード: 名称}} のマップを生成
        class_info: dict[str, dict[str, str]] = {}
        for class_obj in stat_data["CLASS_INF"]["CLASS_OBJ"]:
            obj_id: str = class_obj["@id"]
            classes = class_obj["CLASS"]
            if isinstance(classes, dict):
                classes = [classes]
            class_info[obj_id] = {c["@code"]: c["@name"] for c in classes}

        return values, class_info


# ------------------------------------------------------------------
# 時刻パーサー
# ------------------------------------------------------------------


def _parse_monthly_time(time_str: str) -> date | None:
    """e-Stat の月次時刻コードを date に変換する.

    e-Stat の時刻コードは YYYY00MMFF 形式（例: '2026000101' → 2026年1月）。
    年は先頭4桁、月は6〜7桁目。
    """
    s = str(time_str).strip()
    try:
        year = int(s[:4])
        month = int(s[6:8])
        return date(year, month, 1)
    except (ValueError, IndexError):
        return None


def _parse_quarterly_time(time_str: str) -> date | None:
    """e-Stat の四半期時刻コードを date に変換する.

    e-Stat の時刻コードは YYYY00MMQQ 形式（例: '1994000103' → 1994年Q1）。
    年は先頭4桁、開始月は6〜7桁目。各四半期の開始月（1/4/7/10）を返す。
    """
    s = str(time_str).strip()
    try:
        year = int(s[:4])
        month = int(s[6:8])
        return date(year, month, 1)
    except (ValueError, IndexError):
        return None
