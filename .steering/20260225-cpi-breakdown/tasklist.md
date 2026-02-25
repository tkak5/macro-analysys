# tasklist.md — CPI 品目別内訳表示

## タスク一覧

### フェーズ1: データ収集の拡張

- [x] **T1** `collectors/estat_collector.py` — `_fetch_cpi` メソッドを修正
  - `TARGET_CATEGORIES` セットを定義（11品目）
  - カテゴリフィルタを完全一致方式に変更
  - `rows.append` の `"category"` に品目名をそのまま格納するよう確認

### フェーズ2: データ変換の拡張

- [x] **T2** `transformers/aggregator.py` — `_build_cpi` メソッドを修正
  - 全カテゴリを読み込むよう SQL を変更（`WHERE category = '総合'` を削除）
  - category ごとにループし indicator_code を生成
    - `"総合"` → `"CPI"`（既存互換）
    - それ以外 → `"CPI_{category}"`（例: `"CPI_食料"`）

### フェーズ3: ダッシュボードの拡張

- [x] **T3** `macro_dashboard.py` — `CPI_CATEGORY_CODES` 定数を追加
  - 品目別 indicator_code のリストを定数として定義

- [x] **T4** `macro_dashboard.py` — `render_cpi_breakdown` 関数を追加
  - 対象 indicator_code に絞り込み
  - 直近月のデータのみ取得
  - 前年同月比の横棒グラフを描画（上昇=赤、下落=青）
  - ゼロライン（vline）を追加

- [x] **T5** `macro_dashboard.py` — `main` 関数内の CPI グリッドセルに呼び出しを追加
  - `render_chart(df, "CPI", year_range)` の直後に `render_cpi_breakdown(df, year_range)` を追加

### フェーズ4: 動作確認

- [x] **T6** `python pipeline.py` を実行し、データ取得・変換が正常に完了することを確認
  - `raw_cpi` に 11 品目のデータが格納されていること
  - `mart_indicators` に `CPI_食料` 等が存在すること

- [ ] **T7** `streamlit run macro_dashboard.py` を起動し、ダッシュボードを目視確認
  - 既存の CPI 折線チャートが正常表示されること
  - 品目別バーチャートが CPI セクション内に表示されること
  - 上昇品目が赤、下落品目が青で表示されること

## 完了条件

- `raw_cpi` に 11 品目 × 期間分のレコードが存在する
- `mart_indicators` に `CPI_*` の indicator_code が存在する
- ダッシュボード上に品目別バーチャートが表示される
- 既存のすべての指標チャートが正常に表示される（デグレなし）
