"""DuckDB 接続・操作ユーティリティ."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = "data/macro.db"

logger = logging.getLogger(__name__)


def get_connection() -> duckdb.DuckDBPyConnection:
    """DuckDB への接続を返す."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(DB_PATH)


def initialize_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """raw 層・mart 層の全テーブルを作成する（存在する場合はスキップ）."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_cpi (
            date        DATE      NOT NULL,
            category    VARCHAR   NOT NULL,
            value       DOUBLE,
            unit        VARCHAR,
            fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp,
            PRIMARY KEY (date, category)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_gdp (
            date        DATE      NOT NULL PRIMARY KEY,
            value       DOUBLE,
            unit        VARCHAR,
            fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_unemployment (
            date        DATE      NOT NULL PRIMARY KEY,
            value       DOUBLE,
            unit        VARCHAR,
            fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_money_supply (
            date        DATE      NOT NULL,
            series_code VARCHAR   NOT NULL,
            value       DOUBLE,
            unit        VARCHAR,
            fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp,
            PRIMARY KEY (date, series_code)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_policy_rate (
            date        DATE      NOT NULL PRIMARY KEY,
            value       DOUBLE,
            unit        VARCHAR,
            fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_exchange_rate (
            date        DATE      NOT NULL PRIMARY KEY,
            value       DOUBLE,
            unit        VARCHAR,
            fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_output_gap (
            date        DATE      NOT NULL PRIMARY KEY,
            value       DOUBLE,
            unit        VARCHAR,
            fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS indicator_master (
            indicator_code    VARCHAR NOT NULL PRIMARY KEY,
            indicator_name    VARCHAR,
            indicator_name_en VARCHAR,
            category          VARCHAR,
            source            VARCHAR,
            description       VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mart_indicators (
            date           DATE    NOT NULL,
            indicator_code VARCHAR NOT NULL,
            frequency      VARCHAR NOT NULL,
            value          DOUBLE,
            yoy_change     DOUBLE,
            mom_change     DOUBLE,
            unit           VARCHAR,
            updated_at     TIMESTAMP NOT NULL DEFAULT current_timestamp,
            PRIMARY KEY (date, indicator_code, frequency)
        )
    """)

    _seed_indicator_master(conn)
    logger.info("テーブル初期化完了")


def _seed_indicator_master(conn: duckdb.DuckDBPyConnection) -> None:
    """indicator_master に初期データを投入する（存在する場合はスキップ）."""
    masters = [
        (
            "CPI",
            "消費者物価指数",
            "Consumer Price Index",
            "物価",
            "e-Stat",
            "総務省 消費者物価指数",
        ),
        (
            "GDP",
            "国内総生産",
            "Gross Domestic Product",
            "経済規模",
            "e-Stat",
            "内閣府 四半期別GDP速報",
        ),
        (
            "UNEMPLOYMENT",
            "完全失業率",
            "Unemployment Rate",
            "雇用",
            "e-Stat",
            "総務省 労働力調査",
        ),
        (
            "M2",
            "マネーサプライ",
            "Money Supply M2",
            "金融",
            "BOJ",
            "日本銀行 マネーストック統計",
        ),
        (
            "POLICY_RATE",
            "政策金利",
            "Policy Interest Rate",
            "金融",
            "BOJ",
            "日本銀行 基準割引率および基準貸付利率",
        ),
        (
            "USDJPY",
            "円ドル為替レート",
            "USD/JPY Exchange Rate",
            "為替",
            "BOJ",
            "日本銀行 外国為替相場",
        ),
        (
            "OUTPUT_GAP",
            "需給ギャップ",
            "Output Gap",
            "経済",
            "CAO",
            "内閣府 需給ギャップ・潜在成長率",
        ),
    ]
    for row in masters:
        conn.execute(
            """
            INSERT INTO indicator_master
                (indicator_code, indicator_name, indicator_name_en, category, source, description)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (indicator_code) DO NOTHING
        """,
            row,
        )


def upsert_raw(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    df: pd.DataFrame,
    pk: list[str],
) -> None:
    """主キーで重複除外しながら raw テーブルへ追記する.

    Args:
        conn:  DuckDB 接続
        table: 書き込み先テーブル名
        df:    書き込むデータ
        pk:    主キーのカラム名リスト
    """
    if df.empty:
        logger.warning("%s: 書き込むデータがありません", table)
        return

    # テーブルのカラム順を取得してDFを並べ替える
    col_order = [
        row[0]
        for row in conn.execute(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = '{table}' ORDER BY ordinal_position"
        ).fetchall()
    ]
    # fetched_at は DEFAULT 付きなので df になくてもよい
    df_cols = [c for c in col_order if c in df.columns]
    df = df[df_cols]

    tmp = f"_tmp_{table}"
    conn.execute(f"DROP TABLE IF EXISTS {tmp}")
    conn.execute(
        f"CREATE TEMP TABLE {tmp} AS SELECT * FROM {table} WHERE false"
    )
    conn.execute(f"INSERT INTO {tmp} SELECT * FROM df")

    conflict_cols = ", ".join(pk)
    conn.execute(f"""
        INSERT INTO {table}
        SELECT * FROM {tmp}
        ON CONFLICT ({conflict_cols}) DO NOTHING
    """)
    conn.execute(f"DROP TABLE {tmp}")

    logger.info("%s: %d 件を書き込みました", table, len(df))


def get_latest_date(conn: duckdb.DuckDBPyConnection, table: str) -> date | None:
    """raw テーブルの最終日付を返す（差分更新の起点）.

    Args:
        conn:  DuckDB 接続
        table: 対象テーブル名

    Returns:
        最終日付。データがない場合は None
    """
    result = conn.execute(f"SELECT MAX(date) FROM {table}").fetchone()
    if result is None or result[0] is None:
        return None
    return result[0]
