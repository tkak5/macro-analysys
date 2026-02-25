# 設計書: 指標追加（長期金利）

## 実装アプローチ

財務省 国債金利情報 CSV を取得する `MofCollector` を新規作成し、
既存パターンに従って DB・Aggregator・ダッシュボードを拡張する。

```
db/client.py              ← raw_long_rate テーブル追加 + indicator_master シード追加
collectors/mof_collector.py  ← 新規作成（財務省 CSV 取得）
transformers/aggregator.py   ← _build_long_rate メソッド追加
macro_dashboard.py           ← ラベル・グリッド定義追加
pipeline.py                  ← MofCollector 追加 + load_dotenv() 追加
pyproject.toml               ← 新規作成（mypy の plotly スタブ除外設定）
```

---

## 変更したコンポーネント詳細

### 1. `db/client.py`

#### 追加テーブル

```sql
CREATE TABLE IF NOT EXISTS raw_long_rate (
    date        DATE      NOT NULL PRIMARY KEY,
    value       DOUBLE,
    unit        VARCHAR,
    fetched_at  TIMESTAMP NOT NULL DEFAULT current_timestamp
)
```

#### `_seed_indicator_master` に追加

| indicator_code | indicator_name | category | source |
|---|---|---|---|
| `LONG_RATE` | 長期金利（10年国債） | 金融 | MOF |

---

### 2. `collectors/mof_collector.py`（新規）

- CSV URL: `https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv`
- エンコーディング: CP932
- 先頭1行（タイトル行）をスキップして読み込み
- 元号日付パーサー `_parse_japanese_date()` を実装
  - S（昭和）= 1925 + 年数
  - H（平成）= 1988 + 年数
  - R（令和）= 2018 + 年数
- 「10年」列を抽出し、日次 → 月次平均に集計
- 差分更新: `since` 以降のデータのみ処理

---

### 3. `transformers/aggregator.py`

```python
def _build_long_rate(self) -> pd.DataFrame:
    # raw_long_rate → indicator_code="LONG_RATE", frequency="monthly"
```

`transform()` の `frames` リストに追加。

---

### 4. `macro_dashboard.py`

```python
INDICATOR_LABELS = {
    ...,
    "LONG_RATE": "長期金利（10年国債）",
}

GRID_INDICATORS = [
    "CPI", "GDP", "UNEMPLOYMENT", "M2", "POLICY_RATE", "USDJPY",
    "LONG_RATE",
]
```

---

### 5. 付随修正

#### `collectors/estat_collector.py`
- `_request()` で STATUS=1（該当データなし）を RuntimeError ではなく
  空リスト返却で処理するよう修正

#### `pipeline.py`
- `load_dotenv()` を追加（`.env` ファイルが読み込まれていなかった）
- `MofCollector` をコレクターリストに追加

#### `pyproject.toml`（新規作成）
- mypy の `plotly` スタブ未検出エラーを `ignore_missing_imports = true` で除外

---

## データ構造の変更

| 変更種別 | 対象 | 内容 |
|---|---|---|
| テーブル追加 | `raw_long_rate` | 財務省 長期金利の raw データ（月次平均） |
| レコード追加 | `indicator_master` | LONG_RATE のマスタ情報 |
| レコード追加 | `mart_indicators` | 475件（1974-09〜2026-01）|

---

## 影響範囲

| 既存機能 | 影響 |
|---|---|
| 既存7指標の収集 | なし |
| Aggregator の全件再構築 | `frames` リストへの追加のみ |
| ダッシュボードの表示 | `GRID_INDICATORS` への追加のみ |
