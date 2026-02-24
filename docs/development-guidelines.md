# 開発ガイドライン

## コーディング規約

### 基本方針

- Python 3.13 の機能を活用する
- 型ヒントを必ず付与する
- 関数・クラスには docstring を記載する
- 1 関数の責務は 1 つに限定する

### 型ヒント

```python
# 良い例
def fetch(self) -> pd.DataFrame:
    ...

def save_raw(self, df: pd.DataFrame) -> None:
    ...

# 悪い例（型ヒントなし）
def fetch(self):
    ...
```

---

## 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| ファイル名 | snake_case | `estat_collector.py` |
| クラス名 | PascalCase | `EStatCollector` |
| 関数名・変数名 | snake_case | `fetch_data`, `raw_df` |
| 定数 | UPPER_SNAKE_CASE | `DB_PATH`, `API_BASE_URL` |
| indicator_code | UPPER_SNAKE_CASE | `CPI`, `OUTPUT_GAP` |

---

## スタイリング規約

### フォーマッター・リンター

`ruff` を使用してフォーマットとリントを統一する。

```bash
# フォーマット
ruff format .

# リント
ruff check .

# 型チェック
mypy .
```

### コミット前チェック

コードを変更した際は必ず以下を実行する。

```bash
ruff format . && ruff check . && mypy .
```

---

## コンポーネント実装規約

### コレクター

`BaseCollector` を継承して実装する。

```python
from collectors.base import BaseCollector
import pandas as pd

class EStatCollector(BaseCollector):
    def fetch(self) -> pd.DataFrame:
        """e-Stat API から生データを取得して返す"""
        ...

    def save_raw(self, df: pd.DataFrame) -> None:
        """DuckDB の raw 層に差分保存する"""
        ...
```

- `fetch()` は必ず `pd.DataFrame` を返す
- `save_raw()` は差分追記（重複除外）を行う
- APIキーは環境変数から取得し、ハードコードしない

```python
import os
api_key = os.environ["ESTAT_API_KEY"]
```

### トランスフォーマー

- raw 層のデータのみを入力とする
- mart 層への書き込みは `db/client.py` のユーティリティを使う

---

## 環境変数管理

```bash
# .env.example（リポジトリに含める）
ESTAT_API_KEY=your_api_key_here

# .env（gitignore 対象。実際のキーを記載）
ESTAT_API_KEY=xxxxxxxxxx
```

アプリケーション起動時に `python-dotenv` で読み込む。

```python
from dotenv import load_dotenv
load_dotenv()
```

---

## ログ設計

### 出力先

`logs/pipeline.log` にファイル出力する。標準出力にも同時に出力する。

### 設定

Python 標準の `logging` モジュールを使用する。`pipeline.py` の起動時に一度だけ設定する。

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
```

### ログレベル

| レベル | 用途 |
|--------|------|
| `INFO` | 正常な処理の進行状況（コレクター開始・完了など） |
| `WARNING` | 軽微な問題（データが空など）。処理は継続する |
| `ERROR` | コレクター・トランスフォーマーの例外。処理を継続しつつ記録する |

### 各コンポーネントでの使用

```python
import logging

logger = logging.getLogger(__name__)

logger.info("EStatCollector: データ取得開始")
logger.error(f"EStatCollector: 取得失敗 - {e}")
```

---

## エラーハンドリング

### パイプライン実行時

コレクターの失敗が他のコレクターの実行を止めないよう、例外を捕捉してログ出力し処理を継続する。

```python
for collector in collectors:
    try:
        df = collector.fetch()
        collector.save_raw(df)
    except Exception as e:
        logger.error(f"{collector.__class__.__name__}: {e}")
```

### API レスポンス検証

各コレクターでレスポンスのスキーマを検証し、想定外のデータ形式に早期に気づけるようにする。

---

## テスト規約

本プロジェクトはローカル分析ツールのため、自動テストは必須としない。
ただし、以下の観点で動作確認を行う。

| 確認項目 | 方法 |
|---------|------|
| コレクターの動作確認 | 各コレクターを単体で実行し、DataFrame が返ることを確認 |
| パイプラインの動作確認 | `python pipeline.py` を実行し、エラーなく完了することを確認 |
| ダッシュボードの動作確認 | `streamlit run macro_dashboard.py` でグラフが表示されることを確認 |

---

## Git 規約

### ブランチ戦略

`main` ブランチへ直接コミットする（個人利用のため簡易運用）。

### コミットメッセージ

```
[種別] 変更内容の概要

種別:
  feat    : 新機能追加
  fix     : バグ修正
  docs    : ドキュメント変更
  refactor: リファクタリング
  chore   : 設定・依存関係の変更
```

**例:**
```
feat: e-Stat コレクターを実装
docs: architecture.md にデータソース仕様を追記
fix: BOJ コレクターの日付パースエラーを修正
```

### gitignore 対象

```
data/
.env
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
```
