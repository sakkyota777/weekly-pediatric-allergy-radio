# 定期実行(Routine)のセットアップ手順 — claude.ai の Routines UI で登録

毎週月曜の自動実行は **claude.ai の Routines 画面**で登録します。
（MCP コネクタは組織ポリシーにより API 経由でトリガーに付与できないため、UI から作成します。
コネクタはサンドボックスのネットワーク制限の外側で通信するので、**この方式なら
ネットワーク許可リストの変更も API トークンの追加も不要**です。）

## 登録手順

1. **[claude.ai/code/routines](https://claude.ai/code/routines)** を開き、**New routine** をクリック
2. 各項目を次のように設定:

   | 項目 | 設定値 |
   |---|---|
   | 名前 | `週刊・小児腎臓病ラジオ（毎週月曜 07:00 JST）` |
   | Instructions | 下の「貼り付け用プロンプト」をそのままコピー |
   | リポジトリ | `mynrminto/weekly_reports` |
   | 環境 | このプロジェクトの環境（`GEMINI_API_KEY` が設定済みのもの） |
   | Select a trigger | **Schedule** → Weekly / 月曜 / 07:00（ローカル時刻で入力すれば自動変換） |
   | **Connectors** タブ | **PubMed** と **Notion** が含まれていること（不要なものは外す） |
   | **動作** タブ | 変更不要（下記参照） |

3. **Create** をクリック
4. 詳細ページの **Run now** で 1 回テスト実行

> ### ブランチ制限について（設定は不要）
>
> Routine は既定では **`claude/` で始まるブランチにしか push できません**。
> 公式ドキュメントにはこれを解除する «Allow unrestricted branch pushes» が記載されていますが、
> **現行の日本語 UI（コネクター / 動作 / 通知）には該当項目がありません**
> （「動作」タブにあるのはプルリクエストの自動修正のみ）。
>
> そのため手順書側で、**`main` を試し、拒否されたら `claude/weekly` にフォールバック**し、
> raw URL は**コミット SHA** で組み立てる設計にしてあります。**追加の設定は不要**です。

## 事前確認（1回だけ）

- 環境変数 **`GEMINI_API_KEY`** がその環境に設定されていること（音声生成に使用）。
  未設定でも台本・インフォグラフィック・Notion 掲載までは動き、音声のみスキップされます。
  → 2026-07-25 時点で設定済み・疎通確認済み。**登録画面で入力する項目ではありません**（下記参照）。

## 認証情報の置き場所（よくある疑問）

外部サービスへの繋ぎ方が **2 系統** あり、設定する場所が異なります。

| | 置き場所 | 通信経路 | Routines 登録画面での操作 |
|---|---|---|---|
| **PubMed / Notion** | claude.ai アカウントのコネクタ連携 | Anthropic のサーバ側 | 登録時に**選択する** |
| **Gemini（音声合成）** | 実行環境の環境変数 `GEMINI_API_KEY` | サンドボックスから直接 | **触らない**（環境側に設定済み） |

つまり Gemini のキーは「登録時には不要、実行時には必要」です。登録画面で
**このプロジェクトと同じ環境**を選べば自動的に引き継がれます。別の環境を選ぶと
キーが無い扱いになり、音声だけがスキップされるので注意してください。

（補足: このサンドボックスのネットワークポリシーは `generativelanguage.googleapis.com`
を許可する一方、`eutils.ncbi.nlm.nih.gov` と `api.notion.com` は遮断しています。
PubMed と Notion をコネクタ経由にしているのはこのためで、コネクタの通信は
サンドボックスの外で行われるため制限を受けません。）

## 人に説明するとき

概要を一言で:

> 毎週月曜の朝、claude.ai の定期実行が新しい作業セッションを立ち上げます。そのセッションが
> PubMed で先週の新着論文を検索して3本選び、対話形式のラジオ台本を書き、Gemini の音声合成で
> MP3 にして、図解画像と一緒に GitHub に保存し、Notion に音声つきのページとして掲載します。
> 人の操作は要りません。

技術的な相手には、設計の勘所を添えると伝わります:

> 外部サービスへの繋ぎ方が2通りあります。PubMed と Notion は Claude のコネクタ機能で繋いでいて、
> 通信は Anthropic 側で行われます。音声合成の Gemini だけは実行環境から直接呼ぶので、API キーを
> 環境変数で持たせています。台本の作り方はリポジトリの手順書ファイル
> （`prompts/weekly_radio_prompt.md`）に書いてあり、定期実行はそれを読んで従うだけの構造なので、
> 内容を変えたいときはそのファイルを編集すれば次回から反映されます。

---

## 貼り付け用プロンプト

```
あなたは「週刊・小児腎臓病ラジオ」の週次自動実行セッションです。以下を最初から最後まで自律実行してください（毎回まっさらな状態から始まります）。

## 前提
- リポジトリ `mynrminto/weekly_reports`（このセッションにクローン済み）。
- 環境変数 GEMINI_API_KEY で Gemini TTS を使用（未設定なら音声のみスキップし、成果物と通知にその旨を明記）。
- MCP コネクタ: PubMed（文献検索）と Notion（掲載）を使う。ツールが見つからない場合は ToolSearch で探す。

## 手順
1. main を最新化: `git fetch origin main && git checkout main && git pull`。続けて `pip install -r scripts/requirements.txt`。
2. **`prompts/weekly_radio_prompt.md` を読み、その正典手順に厳密に従うこと**。仕様を推測で補わず、Notion 掲載時は NFM 仕様 `notion://docs/enhanced-markdown-spec` を必ず参照する。
3. 当日(JST)を DATE(YYYY-MM-DD) とし `reports/<DATE>/` に生成する。要点:
   - PubMed を「直近7日・(pediatric OR paediatric OR children OR childhood) AND (kidney disease OR nephrology OR nephrotic OR nephritis OR renal)・datetype=edat」で検索し、臨床インパクトと新規性を重視して **3本を厳選**（主題の重複は避け、症例報告や関連の薄いものは下げる）。
   - 日本語の **2話者の対話台本**（進行役 ナオ × 解説役 マキ先生）。背景→試験デザイン→結果→臨床的含意まで深く掘り下げ、PMID を口頭でも述べ、各トピックの最後に **マキ先生が Take Home を3点**はっきり述べる。`script.md`（読み物）と `script.txt`（話者ラベル `ナオ:` / `マキ先生:` 付き、発話ごとに空行区切り）を作成。
   - 音声: `python scripts/tts_gemini.py reports/<DATE>/script.txt reports/<DATE>/radio.mp3 --speakers "ナオ=Puck,マキ先生=Kore"`（MP3 は 5MiB 未満に収める）。
   - インフォグラフィック: 3本・各 Take Home・2話者表示の自己完結 HTML を作り、`python scripts/render_infographic.py reports/<DATE>/infographic.html reports/<DATE>/infographic.png` で PNG 化。
   - `reports/<DATE>/` 一式（script.md, script.txt, articles.json, infographic.html, infographic.png, radio.mp3）を commit し push する。push 先は手順書の指示に従う（main を試し、ブランチ制限で拒否されたら `claude/weekly`）。
   - Notion 掲載: raw URL（`https://raw.githubusercontent.com/mynrminto/weekly_reports/<コミットSHA>/reports/<DATE>/...`）を `notion-create-attachment` の source_url に渡し、MP3 は `<audio src="file-upload://…">`、PNG は `![](file-upload://…)` として使う。DB `1a961a49-2238-4dcb-87fc-53c23ffcb5d7` に「<DATE> 号」ページを **update-or-create**（まず notion-search で重複を確認し、あれば update-page、なければ create-pages）。プロパティ: 週(タイトル「<DATE> 号」)・公開日・トピック数=3・PMIDs・MP3(raw URL)・インフォグラフィックPNG(raw URL)。本文: 冒頭 callout → 🔊今週の音声(`<audio>`) → 🖼️インフォグラフィック画像 → 今週のトピック3本（各: 誌名・日付・種別・PMID・DOIリンク＋詳しい要約＋🎯Take Home 3点の callout）。
4. **最終メッセージ**（完了通知メールの本文になる）に、今週の3本の見出しと各 Take Home の一言、Notion ページ URL、音声(MP3)の raw リンク、注意点（キー未設定などあれば）を簡潔にまとめる。

医学的な断定は避け、原著(PMID/DOI)の参照を促すこと。途中でエラーが出た場合も、可能な範囲で成果物を仕上げ、未完了の点を最終メッセージに明記すること。
```

---

## 動作確認

登録後、Routines 画面の「今すぐ実行」で 1 回テスト発火すると確実です。
確認ポイント:

- PubMed 検索が走り、3本が選定される
- `radio.mp3` が生成される（= `GEMINI_API_KEY` がその環境で有効）
- Notion に当週ページが作られ、**音声がページ内で再生できる**
- 完了通知メールが届く

## 停止・変更

- 停止/再開・時刻変更は Routines 画面から。
- 台本の構成（本数・話者・Take Home など）を変えたいときは、リポジトリの
  `prompts/weekly_radio_prompt.md` を編集すれば、次回以降の実行に自動で反映されます
  （UI のプロンプトは「手順書を読んで従う」構造のため、貼り直し不要）。
