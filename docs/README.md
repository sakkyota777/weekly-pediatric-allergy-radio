# 毎週月曜、自分の専門領域の新着論文が「対話ラジオ」になって届く

PubMed の新着論文を Claude が毎週勝手に読み、2人の対話形式のラジオ台本に書き起こし、
音声合成で MP3 にして、要点をまとめた画像と一緒に Notion に届ける — という仕組みを作りました。
一度設定すれば、以降は何もしなくても毎週届きます。

この記事は、**実際の出力を見せたうえで、同じものを再現できる**ように書いています。

---

## 実際に届くもの

毎週、次の4点が生成されます。

### 1. 対話形式のラジオ台本

進行役と解説役の2人が、その週の論文を掘り下げます。以下は実際の出力の抜粋です。

> **ナオ:** SGLT2阻害薬というと、最近よく腎臓を守る薬として名前を聞きますね。
>
> **マキ先生:** はい。ただ、腎保護がしっかり確立しているのは、主に2型糖尿病や慢性腎臓病の
> 患者さんで、1型糖尿病では、実はまだ確立していないんです。そこがこの研究の出発点でした。
> 対象は、12歳から21歳の1型糖尿病で、しかも過剰濾過、つまり糸球体が働きすぎている状態を
> 示す若者98人。これを、ダパグリフロジンという薬と、プラセボに割り付けました。
>
> **ナオ:** 過剰濾過、というのは早い段階のサインなんですか。

抄録の要約ではなく、**背景 → 試験デザイン → 結果 → 臨床的含意**まで踏み込む構成です。
各トピックの最後に、解説役が「今日の Take Home」を3点はっきり述べます。
PMID は口頭でも読み上げるので、聞きながら原著にあたれます。

### 2. 音声（MP3）

Gemini のマルチスピーカー音声合成で、2人の声を割り当てて読み上げます。8〜10分程度。
通勤中に聞ける長さに収めています。

### 3. インフォグラフィック

その週の新着ヒット数、選んだ論文、各論文の Take Home 3点を1枚にまとめた画像。

### 4. Notion ページ

上記すべてを収めた「◯月◯日号」のページ。**音声はページ内で直接再生できます。**
週ごとにデータベースに蓄積されるので、あとから検索できます。

---

## 仕組み

```
毎週月曜 7:00
    ↓
Routine が発火 → クラウドセッションが起動（リポジトリを clone）
    ↓
PubMed で直近7日の新着を検索、数本を選定        ← コネクタ経由
    ↓
対話台本を執筆（script.md / script.txt）
    ↓
Gemini TTS で MP3 化、インフォグラフィックを PNG 化  ← 環境変数の API キー
    ↓
GitHub にコミット & push
    ↓
raw URL 経由で Notion に添付し、ページを作成      ← コネクタ経由
    ↓
完了通知が届く
```

設計上のポイントが3つあります。**再現するだけなら読み飛ばして構いません**が、
自分で作り替えるときに効いてきます。

### ポイント1: 認証情報を2系統に分ける

外部サービスへの繋ぎ方を、意図的に2通り使い分けています。

| | 置き場所 | 通信経路 |
|---|---|---|
| **PubMed / Notion** | Claude アカウントのコネクタ連携 | Anthropic のサーバ側 |
| **Gemini（音声合成）** | 実行環境の環境変数 `GEMINI_API_KEY` | サンドボックスから直接 |

この分け方には実利があります。クラウドセッションのネットワークは既定で
「Trusted」（許可リスト方式）ですが、

- **Gemini** は `*.googleapis.com` が既定の許可リストに入っているのでそのまま通る
- **PubMed / Notion** はコネクタ経由なので、そもそも許可リストの対象外

結果として、**ネットワーク設定を一切変更せずに動きます**。
実際、PubMed の API (`eutils.ncbi.nlm.nih.gov`) や Notion の API (`api.notion.com`) を
サンドボックスから直接叩くと 403 で弾かれます。コネクタを使う理由はここにあります。

### ポイント2: Routine のプロンプトは「手順書を読め」とだけ書く

Routine に貼り付けるプロンプトには、番組の中身を書いていません。
代わりに「リポジトリの `prompts/weekly_radio_prompt.md` を読んで、その通りにやれ」と指示しています。

こうすると、**番組の内容を変えたいときはリポジトリのファイルを編集して push するだけ**で、
次回の実行から反映されます。設定画面を開き直す必要がなく、変更履歴も Git に残ります。

### ポイント3: Notion への音声埋め込みは raw URL を経由する

Notion に音声を埋め込むには、まず GitHub に push して
`raw.githubusercontent.com/...` の URL を得て、それを Notion の添付作成に渡します。
そのため **リポジトリは Public である必要があります**（Private だと Notion 側から取得できない）。

この raw URL は**ブランチ名ではなくコミット SHA** で組み立てています。Routine の push 先が
`main` になるとは限らない（後述のブランチ制限）ためです。SHA なら push 先がどちらでも
同じ手順で配信でき、URL も後から変わりません。

---

## 再現する

自分のペースで進められます。所要はおおむね20〜30分です。

### 必要なもの

- GitHub アカウント
- Notion アカウント（無料プランで可）
- Google アカウント（Gemini API キーの取得に使用）
- Claude の Pro または Max プラン（定期実行に必要）

### 手順1. リポジトリを作る

このリポジトリの **Use this template**（または Fork）から、自分のリポジトリを作ります。
**Public** を選んでください（理由は上記ポイント3）。

### 手順2. GitHub と Claude をつなぐ

クラウドセッションがリポジトリを clone / push できるようにします。どちらか一方でOKです。

- **ターミナルから（速い）**: Claude Code で `/web-setup` を実行。ローカルの `gh` CLI の
  トークンが Claude アカウントに同期されます。
- **ブラウザから**: [claude.ai/code](https://claude.ai/code) を開き、案内に従って
  **Claude GitHub App** を認可、対象リポジトリを選択。

どちらでも clone / push はできます。GitHub App を入れると、加えて PR のイベントに
反応する機能（CI 失敗の自動修正など）が使えます。

### 手順3. コネクタを接続する

[claude.ai/customize/connectors](https://claude.ai/customize/connectors) で2つ追加します。

| コネクタ | 手順 |
|---|---|
| **PubMed** | 一覧から追加するだけ（**認証不要**） |
| **Notion** | 追加 → Notion のログイン → **アクセスを許可するページを選択** |

> Notion の認可画面で、書き込みを許可するページを**必ず1つ以上**選んでください。
> 選び忘れると、後で「掲載先データベースを作れない」というエラーになります。

> **GitHub はコネクタではありません。** リポジトリへの clone / push は、手順2で繋いだ仕組み
> （`/web-setup` または Claude GitHub App）が担当します。コネクタ一覧に GitHub を追加する
> 必要はありません。実際、この記事の実行環境には GitHub コネクタは入っていませんが、
> `main` への push は問題なく動いています。

### 手順4. Gemini API キーを取得する

[aistudio.google.com/apikey](https://aistudio.google.com/apikey) でキーを作成してコピーします。
無料枠で使え、クレジットカード登録は不要です。

### 手順5. Routine を設定する

[claude.ai/code/routines](https://claude.ai/code/routines) で **New routine** をクリック。

1. **名前**: 任意（例: `週刊ラジオ（毎週月曜 7:00）`）
2. **Instructions**: [`template/routine-prompt.md`](template/routine-prompt.md) の
   コードブロックの中身をそのまま貼り付け（編集不要）
3. **リポジトリ**: 手順1で作ったものを追加
4. **環境変数**: Instructions 欄の下の**雲のアイコン** → 環境にカーソルを乗せて**歯車アイコン**
   → 環境変数欄に次の1行を追加

   ```
   GEMINI_API_KEY=取得したキー
   ```

   **引用符で囲まないでください**（`"..."` を付けると引用符ごと値になります）。
   **Network access は Trusted のまま変更不要**です。

5. **スケジュール**: **Select a trigger** → **Schedule** → Weekly / 曜日 / 時刻
   （ローカル時間で入力すれば自動変換されます）
6. **コネクター** タブ: **PubMed** と **Notion** が含まれていることを確認し、
   使わないコネクタは外す（実行中は許可なく全ツールが使われるため）

> **ブランチについて（設定は不要です）。** 公式ドキュメントでは、Routine は既定で `claude/` で
> 始まるブランチにしか push できないとされています。これを解除する «Allow unrestricted branch
> pushes» も記載されていますが、**現行の UI には該当項目がありません**（「動作」タブにあるのは
> プルリクエストの自動修正のみ）。
> ただし**実際に運用したところ、`main` への push は成功しました**。連携方法によって挙動が
> 異なるようです。手順書は `main` を試し、拒否された場合だけ `claude/weekly` に
> フォールバックするので、どちらでも動きます。

### 手順6. テスト実行する

Routine の詳細ページで **Run now** をクリックします。完走まで10〜15分ほど。
ブラウザを閉じてもクラウドで走り続け、終われば通知が届きます。

> **通知は既定でプッシュ通知のみ**です。メールでも受け取りたい場合は、Routine 編集画面の
> **「通知」タブ**でメールを有効にしてください。

確認するのは4点です。

- PubMed 検索が走り、論文が選ばれたか
- `radio.mp3` が生成されたか（= Gemini キーが正しく設定できている）
- GitHub の `reports/<日付>/` に成果物が push されたか
- Notion にページができ、**音声がページ内で再生できる**か

> 実行一覧の緑色の表示は「セッションが異常終了しなかった」という意味で、
> 「やりたいことが成功した」という意味ではありません。中身を開いて確認してください。

---

## 自分のテーマに変える

`prompts/weekly_radio_prompt.md` の冒頭にある**設定欄だけ**を書き換えます。

```yaml
show_name: "週刊・新生児医療ラジオ"
pubmed_query: >-
  (neonate OR neonatal OR preterm OR very low birth weight)
  AND (intensive care OR outcome)
topic_count: 3
hosts:
  - { role: "進行役", name: "ナオ",     voice: "Puck" }
  - { role: "解説役", name: "ソラ先生", voice: "Kore" }
```

push すれば次回の実行から反映されます。Routine の設定を触る必要はありません。

検索クエリの例:

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

編集そのものを Claude Code に頼むのが手軽です。

```
prompts/weekly_radio_prompt.md の設定欄を、私の専門領域である〇〇に合わせて書き換えて push して
```

---

## つまずきポイント

| 症状 | 原因と対処 |
|---|---|
| push が `claude/` 以外で拒否される | 手順書が `claude/weekly` に自動フォールバックします（対処不要） |
| 完了メールが来ない | 既定はプッシュ通知のみ。Routine 編集 → 「通知」タブでメールを有効化 |
| 音声ができない | `GEMINI_API_KEY` の設定漏れ、または値を引用符で囲んでいる |
| Notion にページができない | Notion 連携時にページを選んでいない。再認可する |
| Notion で音声が再生できない | リポジトリが Private |
| 論文が0件 | その週に新着が無い領域。手順書は自動で14日に広げる設計 |
| コネクタのツールが無い | Routine の **Connectors** タブで外れている |

## 費用

- **Gemini API** — 無料枠の範囲内（週1回の音声合成なら十分収まります）
- **Claude** — Pro / Max の通常の利用枠を消費。Routine には1日あたりの実行回数上限もあります
- **GitHub / Notion** — 無料プランで可（Notion 無料プランのファイル上限に合わせ、
  MP3 は 5MB 未満に収める設計）

## 注意

生成される内容は自動要約であり、医学的な判断の根拠には使えません。
台本・ページには必ず PMID と DOI が入るので、**原著にあたる前提**で使ってください。

## リポジトリ構成

| パス | 内容 |
|---|---|
| `prompts/weekly_radio_prompt.md` | 正典手順書。**設定欄はここ** |
| `docs/template/routine-prompt.md` | Routine に貼る文面 |
| `scripts/tts_gemini.py` | Gemini マルチスピーカー音声合成 |
| `scripts/render_infographic.py` | HTML → PNG 変換 |
| `scripts/pubmed_fetch.py` | PubMed 取得（コネクタが使えない環境向けの予備） |
| `reports/<日付>/` | 週次の成果物 |
