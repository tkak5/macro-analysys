# 日本マクロ経済ダッシュボード

日本の主要マクロ経済指標を一元的に可視化・分析するローカルダッシュボードです。
公的機関の公開データを自動収集し、インタラクティブなグラフで経済動向を把握できます。

## 表示指標

| 指標 | データソース | 更新頻度 |
|------|------------|---------|
| 消費者物価指数（CPI） | e-Stat API | 月次 |
| GDP（国内総生産） | e-Stat API | 四半期 |
| 完全失業率 | e-Stat API | 月次 |
| マネーサプライ（M2） | 日本銀行 API | 月次 |
| 政策金利 | 日本銀行 API | 月次 |
| 円ドル為替レート | 日本銀行 API | 月次 |
| 需給ギャップ | 内閣府 | 四半期 |

## 必要な環境

- Docker Desktop
- VS Code + Dev Containers 拡張機能

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <このリポジトリのURL>
cd macro-analysys
```

### 2. devcontainer で開く

VS Code で `Ctrl+Shift+P` → `Dev Containers: Reopen in Container` を選択します。

コンテナ起動後、依存パッケージが自動でインストールされます。

### 3. e-Stat APIキーの設定

CPI・GDP・失業率の取得には [e-Stat](https://www.e-stat.go.jp/api/) の APIキーが必要です（無料登録）。

`.env` ファイルをプロジェクトルートに作成して設定します。

```bash
# .env
ESTAT_API_KEY=ここにAPIキーを入力
```

> **注意:** `.env` はリポジトリに含まれません。各自で作成してください。

## 使い方

### データ更新（パイプライン実行）

最新データを取得してデータベースに保存します。

```bash
python pipeline.py
```

実行ログは `logs/pipeline.log` にも保存されます。

### ダッシュボード起動

```bash
streamlit run macro_dashboard.py
```

ブラウザで `http://localhost:8501` が自動的に開きます。
devcontainer 使用時はポートフォワードが自動設定されます。

## プロジェクト構成

```
macro-analysys/
├── pipeline.py              # データ更新エントリーポイント
├── macro_dashboard.py       # Streamlit ダッシュボード
├── collectors/              # データ収集（e-Stat / 日銀 / 内閣府）
├── transformers/            # データ変換・集計・変化率計算
├── db/                      # DuckDB 接続・操作
├── data/                    # データベースファイル（macro.db）
├── logs/                    # パイプラインログ
├── docs/                    # 設計ドキュメント
├── .steering/               # 開発作業ドキュメント
├── .env                     # APIキー（要作成・gitignore対象）
└── requirements.txt         # 依存パッケージ
```

## 技術スタック

| 区分 | 技術 |
|------|------|
| 言語 | Python 3.13 |
| データベース | DuckDB |
| ダッシュボード | Streamlit |
| グラフ描画 | Plotly |
| データ処理 | pandas |
| 開発環境 | Docker devcontainer |
