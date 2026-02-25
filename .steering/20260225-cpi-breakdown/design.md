# design.md — CPI 品目別内訳表示

## 実装アプローチ

既存アーキテクチャ（Collector → raw → Aggregator → mart → Calculator → Dashboard）を
そのまま拡張する。新規テーブル・新規クラスは作成しない。

---

## 変更するコンポーネント

### 1. `collectors/estat_collector.py`

#### 変更箇所: `_fetch_cpi` メソッド

**現在の実装（問題点）**
```python
cat_codes = {
    code
    for code, name in class_info.get("cat01", {}).items()
    if "総合" in name and "食料" not in name and "住居" not in name
}
```
→ 「総合」1カテゴリのみ取得。食料・住居を明示的に除外している。

**変更後**
```python
TARGET_CATEGORIES = {
    "総合", "食料", "住居", "光熱・水道", "家具・家事用品",
    "被服及び履物", "保健医療", "交通・通信", "教育", "教養娯楽", "諸雑費",
}
cat_codes = {
    code
    for code, name in class_info.get("cat01", {}).items()
    if name in TARGET_CATEGORIES
}
```
→ e-Stat の `@name` が TARGET_CATEGORIES に完全一致するカテゴリのみ取得。
→ `rows.append` の `"category"` フィールドに品目名をそのまま格納。

**注意点**
- `raw_cpi` の PK は `(date, category)` のため、スキーマ変更不要
- `upsert_raw` の呼び出しは変更不要

---

### 2. `transformers/aggregator.py`

#### 変更箇所: `_build_cpi` メソッド + `transform` メソッド

**現在の実装（問題点）**
```python
# _build_cpi: WHERE category = '総合' で1系列のみ返す
# transform: frames に _build_cpi() の1系列のみ追加
```

**変更後**
```python
def _build_cpi(self) -> pd.DataFrame:
    """raw_cpi → mart_indicators 形式に変換する（総合 + 品目別）."""
    # 全カテゴリを読み込む
    df = self.conn.execute("""
        SELECT date, category, value, unit FROM raw_cpi ORDER BY date
    """).df()

    rows = []
    for category, group in df.groupby("category"):
        if category == "総合":
            code = "CPI"
        else:
            code = f"CPI_{category}"   # 例: CPI_食料, CPI_住居
        for _, row in group.iterrows():
            rows.append({
                "date": row["date"],
                "indicator_code": code,
                "frequency": "monthly",
                "value": row["value"],
                "yoy_change": None,
                "mom_change": None,
                "unit": row["unit"],
            })
    return pd.DataFrame(rows)
```

→ `CPI`（総合）はコード名を変えず既存互換を維持
→ 品目別は `CPI_食料` 等の indicator_code で mart_indicators に格納
→ `Calculator` は indicator_code ループで動作するため**変更不要**

---

### 3. `macro_dashboard.py`

#### 変更箇所1: 定数定義

```python
# CPI 品目別の indicator_code → 表示ラベルのマップ
CPI_CATEGORY_CODES = [
    "CPI_食料", "CPI_住居", "CPI_光熱・水道", "CPI_家具・家事用品",
    "CPI_被服及び履物", "CPI_保健医療", "CPI_交通・通信",
    "CPI_教育", "CPI_教養娯楽", "CPI_諸雑費",
]
```

#### 変更箇所2: `render_cpi_breakdown` 関数を新規追加

```python
def render_cpi_breakdown(df: pd.DataFrame, year_range: tuple[int, int]) -> None:
    """CPI 品目別前年同月比の横棒グラフを描画する."""
    # 対象 indicator_code に絞る
    breakdown_df = df[df["indicator_code"].isin(CPI_CATEGORY_CODES)].copy()
    # 期間フィルタ
    breakdown_df = breakdown_df[
        (breakdown_df["date"].dt.year >= year_range[0])
        & (breakdown_df["date"].dt.year <= year_range[1])
    ]
    if breakdown_df.empty:
        return

    # 直近月のみ
    latest_date = breakdown_df["date"].max()
    latest_df = breakdown_df[breakdown_df["date"] == latest_date].copy()
    latest_df = latest_df.dropna(subset=["yoy_change"])
    if latest_df.empty:
        return

    # カテゴリ名をラベルに変換（"CPI_食料" → "食料"）
    latest_df["label"] = latest_df["indicator_code"].str.replace("CPI_", "", regex=False)
    # 前年比降順ソート
    latest_df = latest_df.sort_values("yoy_change", ascending=True)
    # 色: 正=赤、負=青
    latest_df["color"] = latest_df["yoy_change"].apply(
        lambda x: "上昇" if x >= 0 else "下落"
    )

    fig = px.bar(
        latest_df,
        x="yoy_change",
        y="label",
        orientation="h",
        color="color",
        color_discrete_map={"上昇": "#e74c3c", "下落": "#3498db"},
        labels={"yoy_change": "前年同月比（%）", "label": ""},
        title=f"CPI 品目別 前年同月比（{latest_date.strftime('%Y年%m月')}）",
    )
    fig.add_vline(x=0, line_width=1, line_color="gray")
    fig.update_layout(showlegend=True, margin={"t": 40, "b": 10})
    st.plotly_chart(fig, use_container_width=True)
```

#### 変更箇所3: `main` 関数内の CPI セクション

```python
# 既存の render_chart(df, "CPI", year_range) の直後に追加
render_cpi_breakdown(df, year_range)
```

→ 既存の CPI グリッドセルの中に、折線チャートの下に品目別バーチャートが入る

---

## 影響範囲の分析

| 対象 | 変更種別 | 影響 |
|------|----------|------|
| `raw_cpi` テーブル | データ増加のみ | スキーマ変更なし |
| `mart_indicators` テーブル | レコード増加のみ | スキーマ変更なし |
| 既存 CPI 折線チャート | 変更なし | indicator_code="CPI" は維持 |
| `Calculator` | 変更なし | indicator_code ループで自動対応 |
| `BojCollector` / `CaoCollector` | 変更なし | 無関係 |

---

## 実装後のダッシュボードイメージ

```
┌──────────────────────────────────────────────────────────┐
│  消費者物価指数（CPI）                                     │
│  単位: 指数（2020年=100）                                  │
│                                                          │
│  ［折線グラフ: CPI 総合 時系列］                           │
│                                                          │
│  直近値: 108.5    前年同月比: +2.1%    前月比: +0.2%      │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ CPI 品目別 前年同月比（2026年01月）                  │  │
│  │                                                    │  │
│  │ 光熱・水道  ████████████████████  +8.2%  ← 赤      │  │
│  │ 食料        ████████████          +4.5%  ← 赤      │  │
│  │ 住居        ████                  +1.8%  ← 赤      │  │
│  │ 保健医療    ██                    +0.9%  ← 赤      │  │
│  │ 諸雑費      █                     +0.3%  ← 赤      │  │
│  │ 家具・家事  ▏                     0.0%             │  │
│  │ 教養娯楽    ▏              -0.5%  ← 青             │  │
│  │ 被服及び履物▌             -1.2%  ← 青             │  │
│  │ 交通・通信  ████          -2.8%  ← 青             │  │
│  │ 教育        █████         -3.1%  ← 青             │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## データ構造の変更

### raw_cpi（変更なし）

| カラム | 型 | 備考 |
|--------|-----|------|
| date | DATE | PK |
| category | VARCHAR | PK（"総合"〜"諸雑費" の 11 種） |
| value | DOUBLE | 指数値 |
| unit | VARCHAR | "指数（2020年=100）" |
| fetched_at | TIMESTAMP | 取得日時 |

### mart_indicators（増加のみ）

新たに追加される indicator_code（最大 10 種）:

| indicator_code | 内容 |
|----------------|------|
| CPI_食料 | 食料品物価指数 |
| CPI_住居 | 住居費指数 |
| CPI_光熱・水道 | 光熱・水道費指数 |
| CPI_家具・家事用品 | 家具・家事用品指数 |
| CPI_被服及び履物 | 被服・履物指数 |
| CPI_保健医療 | 保健医療費指数 |
| CPI_交通・通信 | 交通・通信費指数 |
| CPI_教育 | 教育費指数 |
| CPI_教養娯楽 | 教養娯楽費指数 |
| CPI_諸雑費 | 諸雑費指数 |
