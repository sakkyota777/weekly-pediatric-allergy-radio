# 週刊・小児腎臓病ラジオ — 週次パイプライン手順書

これは毎週月曜の自動実行(Routine)が新しいセッションに渡す**正典手順**です。
実行セッションはこのファイルの指示に従い、PubMed の新着から小児腎臓病トピックを選び、
ラジオ台本・音声(MP3)・論文要約・インフォグラフィックを生成し、GitHub へコミット(raw 配信)、
Notion 掲載（音源を再生できる形で埋め込み）まで行います。

---

## ▼ ここだけ編集してください（設定欄）

番組の内容を変えたいときは、**この欄だけ**を書き換えて push すれば次回実行から反映されます
（Routine のプロンプトを貼り直す必要はありません）。

```yaml
# 番組名
show_name: "週刊・小児腎臓病ラジオ"

# PubMed 検索クエリ（専門領域を変えるならここ）
pubmed_query: >-
  (pediatric OR paediatric OR children OR childhood)
  AND (kidney disease OR nephrology OR nephrotic OR nephritis OR renal)

# 1回あたりに取り上げる論文数
topic_count: 3

# 2話者の設定（name は台本の話者ラベルと完全一致させる。voice は Gemini の音声名）
hosts:
  - { role: "進行役", name: "ナオ",     voice: "Puck" }   # 聞き手・リスナー代弁
  - { role: "解説役", name: "マキ先生", voice: "Kore" }   # 小児腎臓病が専門
```

> 話者は **最大2名**（Gemini マルチスピーカーの上限）。以降の手順に出てくる
> 「ナオ」「マキ先生」「3本」などの記述は、すべてこの設定欄の値を正とします。

---

## 前提
- リポジトリ: `mynrminto/weekly_reports`（push 先ブランチは手順6で自動的に決まる）
- 利用コネクタ(MCP): PubMed / Notion（Google Drive は任意のバックアップ）
- 環境変数 `GEMINI_API_KEY`（未設定なら音声はスキップし、その旨を成果物と通知に明記）
- Notion 掲載先データベース(data_source_id): **`1a961a49-2238-4dcb-87fc-53c23ffcb5d7`**
  （「週刊・小児腎臓病ラジオ（各号）」DB。ハブページ: https://app.notion.com/p/3a84bd470a818169afbcefb2f3b7f11b ）

## 手順

### 0. 準備
- `git fetch origin main && git checkout main && git pull` で最新化。
- `pip install -r scripts/requirements.txt`。
- 当日(JST)の日付を `DATE`（YYYY-MM-DD）とし、`reports/<DATE>/` を作業ディレクトリにする。

### 1. PubMed 検索（直近7日の新着）
`mcp__PubMed__search_articles` を次で実行:
- `query`:
  ```
  (pediatric OR paediatric OR children OR childhood) AND (kidney disease OR nephrology OR nephrotic OR nephritis OR renal)
  ```
- `datetype`: `edat`（PubMed 収載日）
- `date_from`: DATE の 7 日前 / `date_to`: DATE
- `sort`: `pub_date` / `max_results`: 30
- ヒットが多い場合や質を優先したい場合は、`AND (Review[Publication Type] OR Randomized Controlled Trial[Publication Type] OR Guideline[Publication Type])`
  や主要誌フィルタで追加抽出して候補を絞る。
- 各候補は `mcp__PubMed__get_article_metadata` でタイトル/著者/誌名/日付/DOI/抄録を取得。

### 2. 選定（3 本）
- 臨床的インパクト・新規性・小児腎臓病領域との関連度で **3 本**を選ぶ（深掘り重視。似た主題の重複は避ける）。
- 症例報告・純粋な基礎のみ・関連薄のものは優先度を下げる。
- 選定結果を `reports/<DATE>/articles.json` に保存（各: pmid, title, journal, date, doi, url, one_line,
  および **`take_home`（3点の配列）**）。選外に回した候補は `not_selected_this_week` に理由付きで残す。

### 3. ラジオ台本 `reports/<DATE>/script.md` と読み上げ用 `script.txt`
- **2話者の対話形式**。進行役 **ナオ**（聞き手・リスナー代弁）× 解説役 **マキ先生**（小児腎臓病専門）。
- 構成:
  1. オープニング（番組名「週刊・小児腎臓病ラジオ」、今週の日付、2人の自己紹介、今週は3本を深掘りする旨）
  2. 各トピック（1本ずつ）: ナオの問いを挟みつつ、背景→方法/デザイン→結果→臨床的含意まで**詳しく**。
     誌名と発表時期に触れ、**PMID を口頭でも述べる**（例:「PMID は 12345678」）。
     各トピックの最後に **マキ先生が「今日の Take Home」を3点**、はっきり口頭で述べる（聞き手が持ち帰れるように）。
  3. クロージング（3本を貫く共通テーマ、出典は概要欄参照の案内）
- 8〜10 分相当（およそ 3,000〜4,000 字）。医学的な断定は避け、原著参照を促す。
- 読み上げ用 `script.txt` は Markdown 記号や URL を除いた素のテキスト。
  **各発話を `ナオ: …` / `マキ先生: …` の話者ラベル付き**にし、発話ごとに空行で区切る（マルチスピーカー TTS 用）。

### 4. 音声 MP3（2話者マルチスピーカー）
- `python scripts/tts_gemini.py reports/<DATE>/script.txt reports/<DATE>/radio.mp3 --speakers "ナオ=Puck,マキ先生=Kore"`
  - `--speakers` の名前は `script.txt` の話者ラベルと**完全一致**させる（Gemini マルチスピーカーは最大2話者）。
  - 声は環境変数 `GEMINI_TTS_SPEAKERS` でも指定可。単一話者に戻す場合は `--speakers` を省略。
- 終了コード 2（キー未設定）の場合は音声をスキップし、以降のリンク欄に「音声: キー未設定のため未生成」と記す。

### 5. インフォグラフィック
- `reports/<DATE>/infographic.html` を**自己完結 HTML**（インライン CSS、外部リクエストなし）で作成。
  内容: 番組名/日付、対話の2話者（ナオ×マキ先生）表示、今週の新着件数・紹介本数などの統計、
  各論文の要点カード（タイトル・誌名・一言要約・PMID・**Take Home 3点**）。
  配色・可読性は `dataviz` スキルの指針に沿う。ダーク背景・幅約 1120–1200px を推奨。
- `python scripts/render_infographic.py reports/<DATE>/infographic.html reports/<DATE>/infographic.png`

### 6. 成果物をコミット & プッシュ（raw 配信のため先に実施）
- `reports/<DATE>/` 一式（script.md, script.txt, articles.json, infographic.html, **infographic.png, radio.mp3**）をコミット。
  ※ Notion へは raw URL 経由で取り込むため、**PNG と(あれば)MP3 も必ずコミット**する。
- **push 先はブランチ制限の有無で自動的に決める**:
  1. まず `git push -u origin main` を試す（ネットワーク起因の失敗は指数バックオフで最大 4 回）。
  2. **ブランチ制限で拒否された場合**（Routine は既定で `claude/` 接頭辞のブランチにしか
     push できない）は、`git checkout -B claude/weekly && git push -u origin claude/weekly`
     にフォールバックする。
- push 後、**配信に使うコミット SHA** を `git rev-parse HEAD` で取得する。
- 配信 raw URL は**ブランチ名ではなく SHA** で組み立てる（ブランチ名に依存せず、URL も不変になる）:
  - `https://raw.githubusercontent.com/mynrminto/weekly_reports/<SHA>/reports/<DATE>/radio.mp3`
  - `https://raw.githubusercontent.com/mynrminto/weekly_reports/<SHA>/reports/<DATE>/infographic.png`
- どちらのブランチに push したかを、最終メッセージに記す。

### 7. Notion 掲載（音源を再生できる形で埋め込む）
- 添付を作成（**source_url に上記 raw URL** を渡す。`notion-create-attachment`）:
  - MP3 → 返る `file-upload://…` を音声ブロック `<audio src="file-upload://…">…</audio>` に使う（インライン再生可）。
  - PNG → 返る `file-upload://…` を画像 `![caption](file-upload://…)` に使う。
  - ※ 添付は取得から1時間以内にページへ配置すること。MP3 は無料WSで 5MiB 未満に収める（TTS の qscale で調整可）。
- 当週ページは **update-or-create**（重複防止）:
  - まず `notion-search`(data_source_url = `collection://1a961a49-2238-4dcb-87fc-53c23ffcb5d7`) で「<DATE> 号」を検索。
  - 有れば `notion-update-page`（`replace_content` で本文差し替え＋`update_properties`）、無ければ
    `notion-create-pages`（parent = `data_source_id: 1a961a49-2238-4dcb-87fc-53c23ffcb5d7`）。
  - properties: 週(タイトル=「YYYY-MM-DD 号」)、公開日、トピック数=3、PMIDs、MP3(URL=raw)、インフォグラフィックPNG(URL=raw)。
  - content（Notion-flavored Markdown）: 冒頭 callout（出典・2話者・Take Home の案内）→ `## 🔊 今週の音声` に
    `<audio>` → `## 🖼️ インフォグラフィック` に画像 → `## 今週のトピック（3本）` に各論文（見出し=タイトル、
    誌名・日付・種別・PMID・DOI リンク＋詳しい要約＋`<callout icon="🎯">` に Take Home 3点）。
  - 実装時に NFM 仕様 `notion://docs/enhanced-markdown-spec` を参照（推測で書かない）。

### 8. （任意）Google Drive バックアップ
- 必要に応じて `mcp__Google_Drive__create_file` で `radio.mp3` / `infographic.png` を保管し、
  共有リンクを `reports/<DATE>/links.txt` に記録（主たる配信は上記 raw URL + Notion 埋め込み）。

### 9. 最終メッセージ（= 完了通知の本文になる）
次を簡潔にまとめて出力:
- 今週紹介した 3 本の見出し（各トピックの Take Home も一言）
- Notion ページ URL
- 音声（MP3）の raw リンク（未生成ならその旨）
- 補足（キー未設定などの注意があれば）
