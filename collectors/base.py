"""コレクター共通基底クラス."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """全コレクターの共通基底クラス."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self.conn = conn

    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """生データを取得して DataFrame で返す."""

    @abstractmethod
    def save_raw(self, df: pd.DataFrame) -> None:
        """DuckDB の raw 層に差分保存する."""

    def run(self) -> None:
        """fetch → save_raw を実行する. pipeline.py から呼ぶ."""
        logger.info("%s: データ取得開始", self.__class__.__name__)
        df = self.fetch()
        self.save_raw(df)
        logger.info("%s: 完了", self.__class__.__name__)
