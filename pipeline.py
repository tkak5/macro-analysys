"""データ収集・変換パイプライン."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def setup_logging() -> None:
    """ログ設定: logs/pipeline.log + stdout に出力する."""
    Path("logs").mkdir(exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


def main() -> None:
    """パイプラインのエントリーポイント."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("パイプライン開始")

    # ------------------------------------------------------------------
    # DB 接続・テーブル初期化
    # ------------------------------------------------------------------
    from db.client import get_connection, initialize_tables

    conn = get_connection()
    initialize_tables(conn)

    # ------------------------------------------------------------------
    # コレクター実行（例外があっても継続）
    # ------------------------------------------------------------------
    from collectors.boj_collector import BojCollector
    from collectors.cao_collector import CaoCollector
    from collectors.estat_collector import EStatCollector
    from collectors.mof_collector import MofCollector

    collectors = [
        EStatCollector(conn),
        BojCollector(conn),
        CaoCollector(conn),
        MofCollector(conn),
    ]

    for collector in collectors:
        try:
            collector.run()
        except Exception:
            logger.exception(
                "%s: エラーが発生しました（スキップ）", collector.__class__.__name__
            )

    # ------------------------------------------------------------------
    # トランスフォーマー実行
    # ------------------------------------------------------------------
    from transformers.aggregator import Aggregator
    from transformers.calculator import Calculator

    transformers = [
        Aggregator(conn),
        Calculator(conn),
    ]

    for transformer in transformers:
        try:
            transformer.transform()
        except Exception:
            logger.exception("%s: エラーが発生しました", transformer.__class__.__name__)

    # ------------------------------------------------------------------
    # 完了
    # ------------------------------------------------------------------
    conn.close()
    logger.info("パイプライン完了")


if __name__ == "__main__":
    main()
