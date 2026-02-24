# 初回実装 タスクリスト

## ステータス凡例
- [ ] 未着手
- [x] 完了

---

## フェーズ 1: 環境セットアップ

- [x] 1-1. `requirements.txt` を作成する
- [x] 1-2. `.env.example` を作成する
- [x] 1-3. `logs/.gitkeep` を作成する（ディレクトリをgit管理対象にする）
- [x] 1-4. `data/.gitkeep` を作成する（ディレクトリをgit管理対象にする）

---

## フェーズ 2: DB 基盤

- [x] 2-1. `db/client.py` を実装する
  - [x] `get_connection()` — DuckDB 接続
  - [x] `initialize_tables()` — 全テーブル作成（raw 層・mart 層）
  - [x] `upsert_raw()` — 差分追記
  - [x] `get_latest_date()` — 最終日付取得

---

## フェーズ 3: コレクター

- [x] 3-1. `collectors/base.py` を実装する（`BaseCollector` 抽象クラス）
- [x] 3-2. e-Stat の統計表 ID を確認する（CPI: 0003427113 / GDP: 0003109750 / 失業率: 0003005865）
- [ ] 3-3. e-Stat API キーを取得して `.env` に設定する
- [x] 3-4. `collectors/estat_collector.py` を実装する
  - [x] CPI 取得
  - [x] GDP 取得
  - [x] 失業率 取得
- [x] 3-5. BOJ API のシリーズコードを確認する（M2: MAM1NAM2M2MO / 政策金利: STRACLUCON / 為替: FXERM07）
- [x] 3-6. `collectors/boj_collector.py` を実装する
  - [x] M2 取得
  - [x] 政策金利 取得
  - [x] 為替レート 取得
- [x] 3-7. 内閣府 需給ギャップ Excel の URL とカラム構造を確認する
- [x] 3-8. `collectors/cao_collector.py` を実装する

---

## フェーズ 4: トランスフォーマー

- [x] 4-1. `transformers/base_transformer.py` を実装する（`BaseTransformer` 抽象クラス）
- [x] 4-2. `transformers/aggregator.py` を実装する
  - [x] raw 層から全指標を読み込み、統一フォーマットに変換
  - [x] `mart_indicators` テーブルへ書き込む
- [x] 4-3. `transformers/calculator.py` を実装する
  - [x] 前年同月比（`yoy_change`）を計算
  - [x] 前期比（`mom_change`）を計算
  - [x] `mart_indicators` を更新

---

## フェーズ 5: パイプライン

- [x] 5-1. `pipeline.py` を実装する
  - [x] ログ設定（`logs/pipeline.log` + stdout）
  - [x] DuckDB 接続・テーブル初期化
  - [x] 全コレクター順次実行（例外があっても継続）
  - [x] 全トランスフォーマー順次実行
  - [x] 完了ログ出力
- [x] 5-2. `python pipeline.py` を実行し、動作確認する

---

## フェーズ 6: ダッシュボード

- [x] 6-1. `macro_dashboard.py` を実装する
  - [x] `mart_indicators` からデータ読み込み
  - [x] 期間スライダーを配置
  - [x] CPI・GDP・失業率・M2・政策金利・為替を2列グリッドで表示
  - [x] 需給ギャップを全幅で表示
  - [x] 最終更新日時をヘッダーに表示
- [x] 6-2. `streamlit run macro_dashboard.py` を実行し、動作確認する

---

## フェーズ 7: 品質チェック

- [x] 7-1. `ruff format .` を実行する
- [x] 7-2. `ruff check .` を実行する
- [x] 7-3. `mypy .` を実行する
- [x] 7-4. 受け入れ条件をすべて確認する

---

## 完了条件

`requirements.md` の受け入れ条件がすべて満たされていること。

- [x] `python pipeline.py` でエラーなくデータが取得・保存される
- [x] `data/macro.db` に raw 層・mart 層のデータが格納される
- [x] `streamlit run macro_dashboard.py` でダッシュボードが起動する
- [x] 全7指標のグラフが表示される
- [x] 期間スライダーで表示範囲を変更できる
- [x] `logs/pipeline.log` に実行ログが出力される
- [x] `ruff format . && ruff check . && mypy .` がエラーなく通る
