# 初回実装 要求内容

## 概要

日本マクロ経済ダッシュボードの初回実装。
データ収集・保存・変換・可視化の全パイプラインをゼロから構築する。

---

## 実装する機能

### 1. 環境セットアップ

- `requirements.txt` の作成（依存パッケージの定義）
- `.env.example` の作成（APIキーテンプレート）
- `logs/` ディレクトリの初期化

### 2. データベース基盤（`db/client.py`）

- DuckDB への接続・切断
- raw 層・mart 層のテーブル作成
- データの読み書きユーティリティ

### 3. コレクター群（`collectors/`）

| ファイル | 対象指標 | データソース |
|---------|---------|------------|
| `base.py` | — | 共通基底クラス |
| `estat_collector.py` | CPI・GDP・失業率 | e-Stat API |
| `boj_collector.py` | M2・政策金利・為替 | 日本銀行 API |
| `cao_collector.py` | 需給ギャップ | 内閣府 CSV |

### 4. トランスフォーマー群（`transformers/`）

| ファイル | 処理内容 |
|---------|---------|
| `base_transformer.py` | 型変換・欠損補完 |
| `aggregator.py` | 月次・四半期・年次への集計 |
| `calculator.py` | 前年同月比・前期比の計算 |

### 5. パイプライン（`pipeline.py`）

- 全コレクター・全トランスフォーマーを順次実行
- ログ出力（`logs/pipeline.log`）
- エラー時も他コレクターの処理を継続

### 6. ダッシュボード（`macro_dashboard.py`）

- 全7指標を2列グリッドで表示
- 期間スライダーで表示範囲を絞り込み
- データの最終更新日時を表示

---

## 受け入れ条件

- [ ] `python pipeline.py` でエラーなくデータが取得・保存される
- [ ] `data/macro.db` に raw 層・mart 層のデータが格納される
- [ ] `streamlit run macro_dashboard.py` でダッシュボードが起動する
- [ ] 全7指標のグラフが表示される
- [ ] 期間スライダーで表示範囲を変更できる
- [ ] `logs/pipeline.log` に実行ログが出力される
- [ ] `ruff format . && ruff check . && mypy .` がエラーなく通る

---

## 制約事項

- e-Stat API キーは `.env` で管理する（事前に取得が必要）
- 日本銀行 API は認証不要
- 内閣府の需給ギャップは CSV ダウンロードで取得（スクレイピング不可）
- `data/` と `logs/` は `.gitignore` 対象
