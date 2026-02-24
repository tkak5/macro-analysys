# 初回実装 設計

## 実装アプローチ

実装順序は依存関係に従い、下位レイヤーから上位レイヤーへ進める。

```
1. 環境セットアップ（requirements.txt, .env.example）
2. db/client.py（DB基盤）
3. collectors/（データ収集）
4. transformers/（データ変換）
5. pipeline.py（統合・実行）
6. macro_dashboard.py（可視化）
```

---

## 各コンポーネントの設計

### 1. `db/client.py`

DuckDB への接続と操作を一元管理する。

```python
DB_PATH = "data/macro.db"

def get_connection() -> duckdb.DuckDBPyConnection:
    """DuckDB への接続を返す"""

def initialize_tables(conn) -> None:
    """raw 層・mart 層の全テーブルを作成する（存在する場合はスキップ）"""

def upsert_raw(conn, table: str, df: pd.DataFrame, pk: list[str]) -> None:
    """主キーで重複除外しながら raw テーブルへ追記する"""

def get_latest_date(conn, table: str) -> date | None:
    """raw テーブルの最終日付を返す（差分更新の起点）"""
```

### 2. `collectors/base.py`

```python
class BaseCollector(ABC):
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None: ...

    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """生データを取得して DataFrame で返す"""

    @abstractmethod
    def save_raw(self, df: pd.DataFrame) -> None:
        """DuckDB の raw 層に差分保存する"""

    def run(self) -> None:
        """fetch → save_raw を実行する。pipeline.py から呼ぶ"""
        df = self.fetch()
        self.save_raw(df)
```

### 3. `collectors/estat_collector.py`

- e-Stat API から CPI・GDP・失業率を取得
- 取得する統計表 ID は定数として定義する
- APIキーは `os.environ["ESTAT_API_KEY"]` から取得
- 差分更新：`get_latest_date()` で最終日付を取得し、それ以降のデータのみ取得

**取得対象の統計表 ID（実装前に e-Stat サイトで確認）:**

| 指標 | raw テーブル |
|------|------------|
| CPI（消費者物価指数） | `raw_cpi` |
| GDP（国内総生産） | `raw_gdp` |
| 完全失業率 | `raw_unemployment` |

### 4. `collectors/boj_collector.py`

- 日本銀行 時系列統計 API からM2・政策金利・為替を取得
- 認証不要
- 差分更新：`get_latest_date()` で最終日付を取得し、それ以降のデータのみ取得

**取得対象のシリーズコード（実装前に BOJ サイトで確認）:**

| 指標 | raw テーブル |
|------|------------|
| マネーサプライ（M2） | `raw_money_supply` |
| 政策金利 | `raw_policy_rate` |
| 円ドル為替レート | `raw_exchange_rate` |

### 5. `collectors/cao_collector.py`

- 内閣府の需給ギャップ CSV を URL ダウンロードで取得
- スクレイピング不可。ダウンロード URL は定数として定義する
- CSV のカラム構造は実装前に内閣府サイトで確認する

| 指標 | raw テーブル |
|------|------------|
| 需給ギャップ | `raw_output_gap` |

### 6. `transformers/base_transformer.py`

```python
class BaseTransformer(ABC):
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None: ...

    @abstractmethod
    def transform(self) -> None:
        """raw 層を読み込み、mart 層に書き込む"""
```

### 7. `transformers/aggregator.py`

- `raw_*` テーブルから全指標を読み込む
- 各指標を `indicator_code` と `frequency`（monthly / quarterly）で統一フォーマットに変換
- `mart_indicators` テーブルへ書き込む（全件再構築）

### 8. `transformers/calculator.py`

- `mart_indicators` の `value` を使って `yoy_change`・`mom_change` を計算
- pandas の `pct_change()` を活用
- 計算結果で `mart_indicators` を更新する

### 9. `pipeline.py`

```
1. logs/ ディレクトリ作成（なければ）
2. logging 設定（logs/pipeline.log + stdout）
3. DuckDB 接続・テーブル初期化
4. コレクター順次実行（例外があっても継続）
5. トランスフォーマー順次実行
6. 完了ログ出力・接続クローズ
```

### 10. `macro_dashboard.py`

```
1. DuckDB から mart_indicators を全件読み込む
2. 期間スライダー（開始年・終了年）をサイドバーに配置
3. スライダーの値でデータをフィルタリング
4. 2列グリッドで6指標のグラフを表示
5. 需給ギャップを全幅で表示
6. データの最終更新日時をヘッダーに表示
```

---

## データフロー

```
e-Stat API  ──┐
BOJ API     ──┼──→ collectors/ ──→ raw_* テーブル
内閣府 CSV  ──┘
                                         │
                                         ↓
                               transformers/
                               aggregator.py → mart_indicators（値）
                               calculator.py → mart_indicators（変化率）
                                         │
                                         ↓
                               macro_dashboard.py
```

---

## 影響範囲の分析

| コンポーネント | 依存先 | 備考 |
|-------------|-------|------|
| `db/client.py` | DuckDB | 他の全コンポーネントが依存する基盤 |
| `collectors/*` | `db/client.py`、外部API | APIの仕様変更で修正が必要になる場合がある |
| `transformers/*` | `db/client.py`、pandas | raw 層のスキーマ変更で修正が必要になる場合がある |
| `pipeline.py` | `collectors/*`、`transformers/*` | 全コンポーネントを統合 |
| `macro_dashboard.py` | `db/client.py`、mart 層 | mart 層のスキーマ変更で修正が必要になる場合がある |

---

## 未確定事項（実装前に確認が必要）

| 項目 | 確認方法 |
|------|---------|
| e-Stat の統計表 ID（CPI・GDP・失業率） | e-Stat サイトで検索・確認 |
| BOJ API のシリーズコード（M2・政策金利・為替） | BOJ 時系列統計サイトで確認 |
| 内閣府 需給ギャップ CSV の URL とカラム構造 | 内閣府サイトで確認 |
| e-Stat API キーの取得 | e-Stat サイトで無料登録 |
