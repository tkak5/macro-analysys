# タスクリスト: 指標追加（長期金利）

## タスク一覧

### フェーズ1: DB スキーマ拡張

- [x] **T1** `db/client.py` に `raw_long_rate` テーブルを追加する
- [x] **T2** `db/client.py` の `_seed_indicator_master` に `LONG_RATE` を追加する
- [x] ~~`raw_trade_balance` テーブル追加~~ → スコープ外
- [x] ~~`raw_iip` テーブル追加~~ → スコープ外

### フェーズ2: コレクター拡張

- [x] **T3** `collectors/mof_collector.py` を新規作成（財務省 CSV・元号日付パース・月次集計）
- [x] **T4** `pipeline.py` に `MofCollector` を追加・`load_dotenv()` を追加する
- [x] **T5** `collectors/estat_collector.py` の STATUS=1 エラーを修正する

### フェーズ3: Aggregator 拡張

- [x] **T6** `transformers/aggregator.py` に `_build_long_rate` を追加し `frames` に追記する

### フェーズ4: ダッシュボード拡張

- [x] **T7** `macro_dashboard.py` の `INDICATOR_LABELS` と `GRID_INDICATORS` に `LONG_RATE` を追加する
- [x] **T8** `macro_dashboard.py` の `st.line_chart` を `plotly.express.line` に変更し y軸自動スケーリングを有効化する
- [x] **T9** `pyproject.toml` を新規作成（mypy の plotly スタブ除外）

### フェーズ5: 品質チェック

- [x] **T10** `ruff check .` でリントエラーがないことを確認する
- [x] **T11** `mypy .` で型エラーがないことを確認する
- [x] **T12** `python pipeline.py` が正常完了することを確認する

## 完了条件（達成済み）

- [x] `python pipeline.py` 実行後、`mart_indicators` に `LONG_RATE` の 475件が格納される
- [x] ダッシュボードの2列グリッドに長期金利チャートが表示される
- [x] 既存7指標のデータ件数・表示に変化がない
- [x] リント・型チェックがエラーなし

## 取得データ実績

| 指標 | 件数 | 期間 |
|---|---|---|
| 長期金利（LONG_RATE） | 475件 | 1974-09〜2026-01 |
