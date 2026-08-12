# 週刊・小児腎臓病ラジオ — 無人実行(トークン方式)手順書

これは **MCP コネクタを持たない無人クラウドセッション**(週次 Routine が起動)向けの手順です。
コネクタの代わりに、外部アクセスは**環境変数のトークン＋公開 HTTP API** で行います。

## この方式が動く前提(環境側の設定)

無人セッションは egress プロキシ経由で通信するため、**ネットワークポリシーで下記ホストの許可が必須**です
（環境設定 → Network access を「Full access」にするか、許可リストに個別追加）:

- `eutils.ncbi.nlm.nih.gov`（PubMed 検索）
- `api.notion.com`（Notion 掲載）
- `generativelanguage.googleapis.com`（Gemini 音声）※既定で許可済みのことが多い
- `raw.githubusercontent.com`（成果物の配信）※既定で許可済みのことが多い

必要な環境変数:

| 変数 | 用途 | 必須 |
|---|---|---|
| `GEMINI_API_KEY` | 音声(MP3)生成 | 音声を出すなら必須 |
| `NOTION_API_KEY` | Notion 掲載(内部インテグレーションのトークン) | Notion 掲載に必須 |
| `NOTION_PARENT_ID` | 掲載先 DB/データソース id（既定: `1a961a49-2238-4dcb-87fc-53c23ffcb5d7`） | 任意 |
| `NCBI_API_KEY` / `NCBI_EMAIL` | PubMed のレート上限緩和 | 任意 |

Notion 側: 内部インテグレーションを作成し、掲載先 DB に「接続」を追加して共有しておくこと。

## 手順

### 0. 準備
- `git fetch origin main && git checkout main && git pull`。`pip install -r scripts/requirements.txt`。
- 当日(UTC)の日付を `DATE`（YYYY-MM-DD）とし、`reports/<DATE>/` を作業ディレクトリにする。
- リポジトリのフルネーム（例 `mynrminto/weekly_reports`）を `REPO` として控える（raw URL に使う）。

### 1. PubMed 候補取得(公開 API)
```bash
python scripts/pubmed_fetch.py --date-to <DATE> --days 7 --max 30 \
  --out reports/<DATE>/candidates.json
```
`candidates.json` の `candidates[]`（pmid/title/journal/pubdate/doi/authors/abstract/url）を読む。

### 2. 選定(3 本)
- 臨床的インパクト・新規性・小児腎臓病との関連度で **3 本**を選ぶ（深掘り重視、主題の重複を避ける／症例報告・関連薄は下げる）。
- `reports/<DATE>/articles.json` に保存（`issue_date`, `search`, `selected[]`。各: pmid, title, journal, date, type, doi, url, one_line, **`take_home`（3点配列）**）。選外候補は `not_selected_this_week` に理由付きで残す。

### 3. 台本 `script.md` / 読み上げ用 `script.txt`
- **2話者の対話形式**。進行役 **ナオ**（聞き手）× 解説役 **マキ先生**（小児腎臓病専門）。
- オープニング（2人の自己紹介＋今週は3本を深掘り）→各トピック（ナオの問いを挟み、背景→デザイン→結果→臨床的含意まで詳しく。PMID を口頭でも。**末尾にマキ先生が「今日の Take Home」を3点**明言）→クロージング（共通テーマ）。
- 8〜10 分相当（約 3,000〜4,000 字）。断定を避け原著参照を促す。
- `script.txt` は Markdown 記号・URL を除いた素のテキスト。**各発話を `ナオ: …` / `マキ先生: …` の話者ラベル付き**にし、発話ごとに空行で区切る。

### 4. 音声 MP3（2話者マルチスピーカー）
```bash
python scripts/tts_gemini.py reports/<DATE>/script.txt reports/<DATE>/radio.mp3 --speakers "ナオ=Puck,マキ先生=Kore"
```
- `--speakers` の名前は `script.txt` の話者ラベルと**完全一致**させる（Gemini マルチスピーカーは最大2話者）。声は `GEMINI_TTS_SPEAKERS` でも指定可。
- 終了コード 2（`GEMINI_API_KEY` 未設定）なら音声はスキップし、以降 `mp3_url` は null。

### 5. インフォグラフィック
- `reports/<DATE>/infographic.html` を**自己完結 HTML**で作成（`dataviz` 指針、ダーク背景・幅約 1120–1200px）。
```bash
python scripts/render_infographic.py reports/<DATE>/infographic.html reports/<DATE>/infographic.png
```

### 6. 成果物をコミット＆push(raw 配信のため先に push)
- `git add reports/<DATE>` → コミット（`git config user.email noreply@anthropic.com && git config user.name Claude`）→ `git push -u origin main`。
  ※ raw URL で配信するため **PNG と(あれば)MP3 もコミット**する。
- raw URL の形:
  `https://raw.githubusercontent.com/<REPO>/main/reports/<DATE>/infographic.png`
  `https://raw.githubusercontent.com/<REPO>/main/reports/<DATE>/radio.mp3`

### 7. Notion 掲載(REST)
- `reports/<DATE>/notion_payload.json` を作成:
  ```json
  {
    "title": "<DATE> 号", "date": "<DATE>", "topic_count": <n>,
    "pmids": ["...", "..."],
    "intro": "出典: According to PubMed / 検索: ...",
    "infographic_image_url": "https://raw.githubusercontent.com/<REPO>/main/reports/<DATE>/infographic.png",
    "mp3_url": "https://raw.githubusercontent.com/<REPO>/main/reports/<DATE>/radio.mp3",
    "articles": [
      {"title":"...","journal":"...","date":"...","pmid":"...","doi":"...","summary":"..."}
    ]
  }
  ```
  （`articles[].summary` は `articles.json` の `one_line` を使う。`mp3_url` は未生成なら null。）
- 掲載:
  ```bash
  python scripts/notion_publish.py reports/<DATE>/notion_payload.json
  ```
  出力の最後の行が新規ページ id、直前が URL。

### 8. 仕上げのコミット
- `articles.json` / `script.md` / `script.txt` / `candidates.json` / `notion_payload.json` を push（PNG/MP3 は手順 6 で済み）。

### 9. 完了メッセージ(= 通知メール本文)
- 紹介 3 本の見出し / Notion ページ URL / MP3 の raw リンク(未生成ならその旨) / 注意点。
