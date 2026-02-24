# リポジトリ構造定義書

## フォルダ・ファイル構成

```
macro-analysys/
├── pipeline.py                  # データ更新エントリーポイント
├── macro_dashboard.py           # Streamlit ダッシュボード
│
├── collectors/                  # データ収集コンポーネント
│   ├── base.py                  # 共通基底クラス（BaseCollector）
│   ├── estat_collector.py       # e-Stat API（CPI・GDP・失業率）
│   ├── boj_collector.py         # 日本銀行 API（M2・政策金利・為替）
│   └── cao_collector.py         # 内閣府 CSV（需給ギャップ）
│
├── transformers/                # データ変換コンポーネント
│   ├── base_transformer.py      # 共通変換処理（型変換・欠損補完）
│   ├── aggregator.py            # 月次・四半期・年次への集計
│   └── calculator.py            # 前年同月比・前期比の計算
│
├── db/
│   └── client.py                # DuckDB 接続・操作ユーティリティ
│
├── data/                        # データファイル（gitignore 対象）
│   └── macro.db                 # DuckDB データファイル
│
├── logs/                        # ログファイル（gitignore 対象）
│   └── pipeline.log             # パイプライン実行ログ
│
├── docs/                        # 永続的ドキュメント
│   ├── product-requirements.md  # プロダクト要求定義書
│   ├── functional-design.md     # 機能設計書
│   ├── architecture.md          # 技術仕様書
│   ├── repository-structure.md  # リポジトリ構造定義書（本ファイル）
│   ├── development-guidelines.md# 開発ガイドライン
│   └── glossary.md              # ユビキタス言語定義
│
├── .steering/                   # 作業単位のドキュメント
│   └── [YYYYMMDD]-[タイトル]/   # 各作業ディレクトリ
│       ├── requirements.md
│       ├── design.md
│       └── tasklist.md
│
├── .devcontainer/               # devcontainer 設定
│   └── devcontainer.json
│
├── .env                         # APIキー（gitignore 対象）
├── .env.example                 # APIキーのテンプレート
├── .gitignore
├── requirements.txt             # Python 依存パッケージ
└── CLAUDE.md                    # プロジェクトメモリ（Claude Code 用）
```

---

## ディレクトリの役割

### `collectors/`

データソースごとに 1 ファイルで実装するデータ収集コンポーネント。
`base.py` に定義された `BaseCollector` を継承し、`pipeline.py` から統一的に呼び出される。

- 新しいデータソースを追加する際は、このディレクトリに 1 ファイル追加するだけでよい

### `transformers/`

raw 層のデータを mart 層へ変換・集計するコンポーネント。
型変換・欠損補完・集計・変化率計算の処理を分離して管理する。

### `db/`

DuckDB への接続・テーブル操作を一元管理するユーティリティ。
コレクターおよびトランスフォーマーからインポートして使用する。

### `data/`

DuckDB のデータファイル（`macro.db`）を格納する。
生成物であるためリポジトリには含めない（`.gitignore` 対象）。

### `docs/`

アプリケーション全体の設計を定義する永続的ドキュメント。
基本設計が変わらない限り更新されない。

### `.steering/`

特定の開発作業における作業ドキュメントを格納する。
作業ごとに日付付きサブディレクトリを作成し、完了後も履歴として保持する。

---

## ファイル配置ルール

| ルール | 内容 |
|--------|------|
| コレクターの追加 | `collectors/` 直下に `[指標名]_collector.py` として配置 |
| トランスフォーマーの追加 | `transformers/` 直下に配置 |
| データファイル | `data/` 直下のみ。サブディレクトリは作らない |
| 環境変数 | `.env` で管理。リポジトリにはコミットしない |
| ドキュメント | 永続的なものは `docs/`、作業単位は `.steering/` |

---

## gitignore 対象

```
data/           # DuckDB データファイル
logs/           # ログファイル
.env            # APIキー
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
```
