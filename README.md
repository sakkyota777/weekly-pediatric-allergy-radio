# weekly_reports — 週刊・小児腎臓病ラジオ

毎週月曜、PubMed の新着から**小児腎臓病(pediatric kidney disease)**のトピックを自動で探し、
ラジオ番組風に紹介する**音声(MP3)**を Gemini TTS で生成し、論文要約と**インフォグラフィック**を
**Notion** に掲載、**完了通知メール**でリンクを届ける自動化です。

> **📻 はじめての方へ** — 何ができるのか、実際の出力、そして**自分の専門領域で再現する手順**は
> **[docs/README.md](docs/README.md)** にまとめています。まずはそちらをご覧ください。
> 本ファイルは実装寄りのリファレンスです。

## 仕組み

| 処理 | 実行 | 手段 |
|---|---|---|
| 新着検索・メタ取得 | エージェント | PubMed MCP |
| ラジオ台本・論文要約・インフォグラフィック | 生成 | 日本語 / 自己完結 HTML |
| 台本 → MP3 | `scripts/tts_gemini.py` | Gemini TTS → WAV → MP3(imageio-ffmpeg) |
| HTML → PNG | `scripts/render_infographic.py` | Playwright + 同梱 Chromium |
| Notion 掲載 / Drive 保存 | エージェント | Notion / Google Drive MCP |
| 週次実行 + 通知メール | Routine | Claude Code Remote トリガー |

週次の詳細手順は [`prompts/weekly_radio_prompt.md`](prompts/weekly_radio_prompt.md) を参照。
成果物は `reports/<YYYY-MM-DD>/` に保存されます。

## 実行モード

| モード | 実行者 | 外部アクセス | 追加設定 |
|---|---|---|---|
| **A. 半自動(コネクタ)** | あなたが開く対話セッション | Notion/Drive/PubMed **MCP コネクタ** | ほぼ不要(Gemini キーのみ) |
| **B. 無人(トークン)** | 週次 Routine が起動する無人セッション | **公開 HTTP + env トークン** | ネットワーク許可 + Notion トークン |

無人セッションは MCP コネクタを持てないため、モード B は外部アクセスを HTTP + トークンで行います
（PubMed=E-utilities、Notion=REST、音声=Gemini、配信=GitHub raw）。手順は
[`prompts/weekly_radio_auto.md`](prompts/weekly_radio_auto.md) を参照。

### モード B の前提(環境設定)
1. **ネットワーク許可**（環境設定 → Network access を Full access、または許可リストに追加）:
   `eutils.ncbi.nlm.nih.gov` / `api.notion.com`
   （`generativelanguage.googleapis.com` / `raw.githubusercontent.com` は既定で許可されていることが多い）
2. **環境変数**: `GEMINI_API_KEY`（音声）、`NOTION_API_KEY`（Notion 内部インテグレーションのトークン）。
   任意で `NOTION_PARENT_ID`、`NCBI_API_KEY`。
3. **Notion 共有**: 内部インテグレーションを作成し、掲載先 DB に「接続」を追加して共有。
4. 配信は Google Drive ではなく **公開リポジトリの raw URL**（PNG/MP3 をコミットして配信）。

## セットアップ

### 1. 依存関係
```bash
pip install -r scripts/requirements.txt
```
Chromium はこの実行環境に同梱済み（`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`）。ffmpeg は
`imageio-ffmpeg` が同梱するため別途インストール不要。

### 2. Gemini API キー（音声生成に必須）
[Google AI Studio](https://aistudio.google.com/) で API キーを取得し、**実行環境の環境変数**に
`GEMINI_API_KEY` として追加してください（Claude Code on the web の環境設定画面）。新しいセッションに
継承されます。**未設定でもパイプラインは動作**し、台本・要約・インフォグラフィックまで生成、音声のみスキップします。

任意の上書き環境変数:
- `GEMINI_TTS_MODEL`（既定 `gemini-2.5-flash-preview-tts`）
- `GEMINI_TTS_VOICE`（既定 `Kore`）

### 3. Notion 掲載先データベース
Notion に新規ハブページ「[週刊・小児腎臓病ラジオ](https://app.notion.com/p/3a84bd470a818169afbcefb2f3b7f11b)」と
その配下のデータベース「週刊・小児腎臓病ラジオ（各号）」を作成済み。掲載先の `data_source_id` は
`1a961a49-2238-4dcb-87fc-53c23ffcb5d7`（`prompts/weekly_radio_prompt.md` に設定済み）。

## 手動実行（1 週分）
```bash
pip install -r scripts/requirements.txt
# 1) PubMed 検索〜台本作成（エージェント/prompts の手順に従う）
# 2) 音声
python scripts/tts_gemini.py reports/<DATE>/script.txt reports/<DATE>/radio.mp3
# 3) インフォグラフィック
python scripts/render_infographic.py reports/<DATE>/infographic.html reports/<DATE>/infographic.png
# 4) Drive 保存 / Notion 掲載（エージェント）
```

## 既知の制約
- Gmail は下書き作成のみで自動送信 API が無いため、配信は **Drive 保存 + 完了通知メール + Notion 掲載**で行います。
- 生成内容は自動作成のため、臨床判断には必ず原著(PMID/DOI)を確認してください。
