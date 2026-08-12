# 週刊ラジオ — 週次パイプライン手順書（汎用テンプレート）

毎週の自動実行(Routine)が新しいセッションに渡す**正典手順**です。
実行セッションはこのファイルに従い、PubMed の新着から自分の専門領域のトピックを選び、
ラジオ台本・音声(MP3)・インフォグラフィックを生成し、GitHub にコミット、Notion に掲載します。

---

## ▼ ここだけ編集してください（設定欄）

```yaml
# 番組名（Notion のデータベース名にも使われます）
show_name: "週刊・小児腎臓病ラジオ"

# PubMed 検索クエリ（自分の専門領域に差し替える）
pubmed_query: >-
  (pediatric OR paediatric OR children OR childhood)
  AND (kidney disease OR nephrology OR nephrotic OR nephritis OR renal)

# 1回あたりに取り上げる論文数
topic_count: 3

# 2話者の設定（name は台本の話者ラベルと完全一致させる。voice は Gemini の音声名）
hosts:
  - { role: "進行役", name: "ナオ",     voice: "Puck" }   # 聞き手・リスナー代弁
  - { role: "解説役", name: "マキ先生", voice: "Kore" }   # その領域の専門家
```

**差し替え例**

| 領域 | `pubmed_query` の例 |
|---|---|
| 新生児・NICU | `(neonate OR neonatal OR preterm OR very low birth weight) AND (intensive care OR outcome)` |
| 小児循環器 | `(congenital heart disease OR Kawasaki disease) AND (children OR pediatric)` |
| 小児神経 | `(children OR pediatric) AND (epilepsy OR seizure OR neurodevelopmental outcome)` |
| 小児アレルギー | `(children OR pediatric) AND (asthma OR food allergy OR atopic dermatitis)` |
| 小児感染症 | `(children OR infant) AND (RSV OR influenza OR vaccine OR sepsis)` |
| 小児内分泌 | `(children OR adolescent) AND (type 1 diabetes OR growth hormone OR obesity)` |
| 発達・こころ | `(children OR adolescent) AND (autism OR ADHD OR mental health)` |
| 小児血液腫瘍 | `(childhood OR pediatric) AND (leukemia OR lymphoma OR solid tumor)` |

> 話者名を変えたら、番組の性格に合う `voice` も選び直してください。
> Gemini のマルチスピーカーは **最大2話者** です。

---

## 前提

- リポジトリ: **このセッションがクローンしたリポジトリ**
  - オーナー名/リポジトリ名は `git remote get-url origin` から取得し、raw URL を組み立てる
    （手順書にハードコードしない）
  - push 先ブランチは手順6で自動的に決まる（追加の権限設定は不要）
- 利用コネクタ(MCP): **PubMed**（検索）/ **Notion**（掲載）
- 環境変数 `GEMINI_API_KEY`（未設定なら音声はスキップし、その旨を成果物と通知に明記）

## 手順

### 0. 準備
- `git fetch origin main && git checkout main && git pull` で最新化。
- `pip install -r scripts/requirements.txt`。
- 当日(JST)の日付を `DATE`（YYYY-MM-DD）とし、`reports/<DATE>/` を作業ディレクトリにする。
- `git remote get-url origin` から `OWNER/REPO` を取得しておく。

### 1. PubMed 検索（直近7日の新着）
`mcp__PubMed__search_articles` を次で実行:
- `query`: 設定欄の `pubmed_query`
- `datetype`: `edat`（PubMed 収載日） / `date_from`: DATE の7日前 / `date_to`: DATE
- `sort`: `pub_date` / `max_results`: 30
- ヒットが多すぎる場合は
  `AND (Review[Publication Type] OR Randomized Controlled Trial[Publication Type] OR Guideline[Publication Type])`
  などで絞る。
- 各候補は `mcp__PubMed__get_article_metadata` でタイトル/著者/誌名/日付/DOI/抄録を取得。

> **ヒットが0件のとき**: 期間を14日に広げ、それでも0件ならクエリを段階的に緩める。
> 最終的に選べた本数で続行し、その旨を最終メッセージに明記する（空のまま終了しない）。

### 2. 選定（`topic_count` 本）
- 臨床的インパクト・新規性・領域との関連度で選ぶ（似た主題の重複は避ける）。
- 症例報告・関連の薄いものは優先度を下げる。
- 結果を `reports/<DATE>/articles.json` に保存（各: pmid, title, journal, date, doi, url, one_line,
  および **`take_home`（3点の配列）**）。選外候補は `not_selected_this_week` に理由付きで残す。

### 3. ラジオ台本 `script.md` と読み上げ用 `script.txt`
- **2話者の対話形式**（設定欄の `hosts`）。
- 構成:
  1. オープニング（`show_name`、今週の日付、2人の自己紹介、今週の本数）
  2. 各トピック: 問いを挟みつつ 背景→デザイン→結果→臨床的含意 まで**詳しく**。
     誌名と発表時期に触れ、**PMID を口頭でも述べる**（例:「PMID は 12345678」）。
     各トピックの最後に **解説役が「今日の Take Home」を3点**はっきり述べる。
  3. クロージング（全体を貫く共通テーマ、出典は概要欄参照の案内）
- 8〜10分相当（およそ 3,000〜4,000字）。医学的な断定は避け、原著参照を促す。
- `script.txt` は Markdown 記号や URL を除いた素のテキスト。
  **各発話を `<話者名>: …` の話者ラベル付き**にし、発話ごとに空行で区切る。

### 4. 音声 MP3（2話者マルチスピーカー）
```bash
python scripts/tts_gemini.py reports/<DATE>/script.txt reports/<DATE>/radio.mp3 \
  --speakers "<話者1>=<voice1>,<話者2>=<voice2>"
```
- `--speakers` の名前は `script.txt` の話者ラベルと**完全一致**させる。
- 終了コード 2（キー未設定）の場合は音声をスキップし、以降のリンク欄に
  「音声: キー未設定のため未生成」と記す。

### 5. インフォグラフィック
- `reports/<DATE>/infographic.html` を**自己完結 HTML**（インライン CSS、外部リクエストなし）で作成。
  内容: 番組名/日付、2話者の表示、今週の新着件数・紹介本数などの統計、
  各論文の要点カード（タイトル・誌名・一言要約・PMID・**Take Home 3点**）。
  配色・可読性は `dataviz` スキルの指針に沿う。ダーク背景・幅約 1120–1200px を推奨。
- `python scripts/render_infographic.py reports/<DATE>/infographic.html reports/<DATE>/infographic.png`

### 6. 成果物をコミット & プッシュ（raw 配信のため先に実施）
- `reports/<DATE>/` 一式（script.md, script.txt, articles.json, infographic.html,
  **infographic.png, radio.mp3**）をコミット。
  ※ Notion へは raw URL 経由で取り込むため、**PNG と(あれば)MP3 も必ずコミット**する。
- **push 先はブランチ制限の有無で自動的に決める**:
  1. まず `git push -u origin main` を試す（ネットワーク起因の失敗は指数バックオフで最大4回）。
  2. **ブランチ制限で拒否された場合**（Routine は既定で `claude/` 接頭辞のブランチにしか
     push できない）は、`git checkout -B claude/weekly && git push -u origin claude/weekly`
     にフォールバックする。
- push 後、**配信に使うコミット SHA** を `git rev-parse HEAD` で取得する。
- 配信 raw URL は**ブランチ名ではなく SHA** で組み立てる（`OWNER/REPO` は手順0で取得したもの）。
  ブランチ名に依存せず、URL も不変になる:
  - `https://raw.githubusercontent.com/OWNER/REPO/<SHA>/reports/<DATE>/radio.mp3`
  - `https://raw.githubusercontent.com/OWNER/REPO/<SHA>/reports/<DATE>/infographic.png`
- どちらのブランチに push したかを、最終メッセージに記す。

### 7. Notion 掲載（初回はデータベースごと自動作成）

**7-1. 掲載先データベースを確保する（update-or-create）**
- `notion-search` で `show_name` を名前に含むデータベースを探す。
- **見つからなければ `notion-create-database` で新規作成**する。名前は `<show_name>（各号）`。
  プロパティ構成:

  | プロパティ名 | 型 |
  |---|---|
  | 週 | タイトル |
  | 公開日 | 日付 |
  | トピック数 | 数値 |
  | PMIDs | テキスト |
  | MP3 | URL |
  | インフォグラフィックPNG | URL |

- 作成先の親ページは、ユーザーのワークスペース直下（`notion-search` で書き込み可能な
  ページを1つ選ぶ）。作成した database の id は最終メッセージに記録する。

> ツールの引数は**推測で書かず**、実行時にツールスキーマと
> NFM 仕様 `notion://docs/enhanced-markdown-spec` を参照すること。

**7-2. 添付を作成**（`notion-create-attachment` の `source_url` に **上記 raw URL** を渡す）
- MP3 → 返る `file-upload://…` を `<audio src="file-upload://…"></audio>` に使う（インライン再生可）
- PNG → 返る `file-upload://…` を `![caption](file-upload://…)` に使う
- ※ 添付は取得から1時間以内にページへ配置する。MP3 は無料ワークスペースで **5MiB 未満**に収める。

**7-3. 当週ページを update-or-create**（重複防止）
- まず `notion-search` で「`<DATE>` 号」を当該 DB 内から探す。
- 有れば `notion-update-page`（`replace_content` で本文差し替え＋`update_properties`）、
  無ければ `notion-create-pages`（parent = 7-1 の data_source_id）。
- properties: 週(タイトル=「YYYY-MM-DD 号」)、公開日、トピック数、PMIDs、MP3(raw URL)、
  インフォグラフィックPNG(raw URL)
- content（Notion-flavored Markdown）: 冒頭 callout（出典・2話者・Take Home の案内）→
  `## 🔊 今週の音声` に `<audio>` → `## 🖼️ インフォグラフィック` に画像 →
  `## 今週のトピック` に各論文（見出し=タイトル、誌名・日付・種別・PMID・DOI リンク
  ＋詳しい要約＋`<callout icon="🎯">` に Take Home 3点）。

### 8. 最終メッセージ（= 完了通知の本文になる）
次を簡潔にまとめて出力:
- 今週紹介した論文の見出し（各 Take Home も一言）
- Notion ページ URL（初回は作成した DB の URL も）
- 音声（MP3）の raw リンク（未生成ならその旨）
- 補足（キー未設定・push 権限・検索ヒット0件など、注意があれば必ず明記）
