"""トランスフォーマー共通基底クラス."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import duckdb

logger = logging.getLogger(__name__)


class BaseTransformer(ABC):
    """全トランスフォーマーの共通基底クラス."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self.conn = conn

    @abstractmethod
    def transform(self) -> None:
        """raw 層を読み込み、mart 層に書き込む."""
