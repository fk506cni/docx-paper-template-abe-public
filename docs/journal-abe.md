# ABE (Advanced Biomedical Engineering) の投稿規定 ⇔ 実装 対応表

*Advanced Biomedical Engineering* (ABE) の投稿規定と学会テンプレートを読み解き、本テンプレートがそれをどう実装しているかをまとめた資料である。
規定の要点・学会テンプレートの構造・Word で確かめた形・規定と実装の対応・既知の制限・`profile.yaml` の要点を置く。

> **本テンプレートは、日本生体医工学会 (Japanese Society for Medical and Biological Engineering, JSMBE) と ABE の編集部が作成・承認・確認した
> ものではなく、学会・誌と関係が無い** (公式のテンプレートではない)。本書は **2026-11 時点の公開ページ** (規定は末尾の日付 1 April 2026 の版) に基づく。
> 規定は変わりうるので、投稿の前に必ず誌の Instructions to Authors (<https://abe-journal.org/authorinstructions>) で確かめること。
> 規定の引用は短くとどめた。全文は上のページで読む。

- 投稿の通し手順は [`docs/usage-guide.md`](usage-guide.md) §8、投稿の当日に人が確かめる表は [`docs/abe-submission-checklist.md`](abe-submission-checklist.md)。
- 原稿の書き方の要約は `CLAUDE.md` の「ABE 投稿時の執筆規約」、`profile.yaml` のキーの一覧は [`docs/profile-schema.md`](profile-schema.md)。
- 下のコードのコメントと `data/journals/abe/profile.yaml` のコメントの「§N」は本書の節番号である。

---

## 0. 一次資料

| 資料 | 入手先 | 版 | 本書での扱い |
|------|--------|----|------------|
| Instructions to Authors (PDF) | <https://abe-journal.org/authorinstructions> のページのリンク | 末尾の日付 **1 April 2026** | 正本として読む |
| Instructions to Authors (Web) | <https://abe-journal.org/authorinstructions> | 2026-11 時点 | PDF と全文を突き合わせた。違いは下の 4 点だけ |
| 学会テンプレート `ABETemplate.docx` | 同じページのリンク (**本テンプレートには同梱しない**) | 柱の表記 **ver.3** | 構造は §8。本テンプレートの reference.docx の雛形にする |
| Submission Form and Author Statement | 同じページのリンク (`SubmissionForm-2026.docx`) | 2026 年版 | 記入欄は §6.4。同梱しない |
| COI 開示書式 | 誌のサイト (`COI_Form.docx`。Instructions to Authors の案内に従って取得する) | 2026-11 時点 | 項目は §6.3。同梱しない |
| 投稿系 | Editorial Manager (<http://www.editorialmanager.com/abe/default.aspx>) | — | 画面は見ていない (§15) |

**PDF 版と Web 版の違い** (規定の中身 — 上限・必須の要素・文献の書式・提出物 — に食い違いは無い):
(1) 「1 本の PDF」の文 (§6.1) で、Web 版は対象に **"statement"** を足し、PDF 版の "(available at the relevant ABE webpage)" が無い /
(2) 補足資料の推奨形式から、Web 版は **"Word" が抜けている** (§6.2) / (3) 謝辞の見出しが Web 版は `Acknowledgements`・PDF 版は `Acknowledgments` (§9 の 6) /
(4) 章名が Web 版は "OPEN ACCESS, COPYRIGHT AND PUBLICATION FEES"。

**学会テンプレートの版と指紋**: `data/journals/abe/profile.yaml` の `reference_base_sha256` に、2026-11 時点で配布されている ver.3 の SHA-256 を書いてある。
利用者が置いたテンプレートの指紋がこれと違えば、`make-reference.sh` (と、それを呼ぶ build / diff) が止まる — 改版でスタイル名や節の構造が変わると
後処理 (§11.3) が外れうるため。新しい版を使うなら profile の値を表示された値に書き換え (それが「新しい版を確かめた」印)、出てくる警告と
Word の PDF の見た目 (2 段組・柱・見出しの番号・図表の題) を確かめ直す。テンプレートが無いときは、build / diff が取得元 (上のページ。profile の
`reference_base_url`) と置き場所 (`data/journals/abe/ABETemplate.docx`) を出して止まる。

---

## 1. 誌の概要

- 発行: 日本生体医工学会 (JSMBE)。J-STAGE で公開する完全オープンアクセスの英文誌。
- 投稿系: **Editorial Manager**。
- 査読: **single-blind** (著者名を伏せない → profile の `blinded: false`)。編集委員長の初期審査 → 担当編集者 → 査読者 2 名 (割れたら 3 人目)。
- 改訂: 判定から **3 か月以内**に再投稿する。過ぎると取り下げの扱いになり、新規の投稿になる (§7)。
- 掲載料: 非会員 **1 600 USD**、筆頭または連絡著者が JSMBE 会員なら **600 USD**、編集委員会の依頼論文は無料
  (投稿前に入会を申請し、受理前に承認されれば会員の扱い)。規定に適用の開始日は書かれていない。
- ライセンス: CC BY / CC BY-SA / CC BY-NC から著者が選ぶ。著作権は著者に残り、License to Publish に署名する。
- **データ**: 研究データは査読中に編集者・査読者へ**全量を開示**し、**出版日までに公開**し、5 年以上保存する (いずれも "must")。
  J-STAGE Data への登録が推奨 (無料)。骨格はデータの入手先と公開の記述を Materials and methods の末尾の小節に置く (§3.4)。
- **既発表と重複投稿**: どの言語であれ、全部または一部が既発表・印刷中・他誌で審査中の原稿は投稿できない。
  **会議録 (Proceedings) として刊行されたものは長さ・図表によらず既発表**で、既発表にならない例外は**プレプリント**と**図表を含まず 400 語未満の抄録**だけ
  (規定の "Proceedings articles often contain one or more pages, figures and tables" は会議録の典型の説明で、条件ではない)。
  関連原稿 (他所で審査中・印刷中・刊行済み) は編集者に知らせる。ABE の判定の前に他誌へ出すなら、先に ABE から取り下げる。
- **プレプリント**: 投稿前・投稿と同時の掲載は推奨。ただし**査読を受けて直した版・受理版・刊行版はプレプリントのサーバに載せない** (刊行版へのリンクは可)。
- **著者**: ICMJE の 4 基準。**投稿後は連絡著者を変えられない**。著者の追加・削除・順序の変更は全著者と編集者の承認が要る。AI ツールは著者にできない。
- **通信の秘密**: 著者は事務局・編集者・査読者との通信をすべて秘密に保つ ("in strict confidence")。査読コメント・回答書・事務局とのやりとりを公開しない。

## 2. 記事種別と長さ

| 種別 (`--article-type`) | 上限 | 抄録 | 備考 |
|------|---------|------|------|
| Original Papers (`original`。既定) | **4 000 語** | 350 語・1 段落 | 学際 (医学 × 工学) の研究を特に歓迎する |
| Research Letters (`letter`) | **2 500 語** | 同上 | 早期の発表に値する新しい概念・現象 |
| Technical Notes (`technical`) | **1 500 語** | 同上 | 設計パラメータ・実験結果・調査結果 |
| Review Papers (`review`) | 編集委員会が論文ごとに決める | 同上 | 原則は依頼。著者からの提案も可 |

- 記事種別の節は上限を **"recommended length"** と書くが、Manuscript Preparation に "authors must comply with article length limits, which are provided in the
  'Manuscript Types' section" もあるので、本テンプレートは上限として扱う (超過は規定チェックの要修正)。Review Papers は語数を照合しない。
- 何を語数に数えるかは規定に書かれていない。本テンプレートの数え方は §12。
- Original Papers と Research Letters は (i) 目的と応用上の利点 (ii) 新規性の根拠 (iii) 実験結果または計算 (iv) 主な成果、を含む。
- 図表の点数・文献数の上限は**無い**。

## 3. 原稿の構成と書き方

規定は **format-free** で、体裁・レイアウトは自由、図表は本文中に置いてよい。ただし評価に必要な要素
(**表題ページ・著者と所属・キーワード・序論・方法・結果・考察・題のある図表**) は必須である。
学会テンプレートは「原稿の作り方に不慣れな著者向け」の任意の雛形だが、**本テンプレートは学会テンプレートの体裁 (表題ページは 1 段組・本文は 2 段組) を既定にする**
(テンプレートで書くほかの著者の原稿と同じ見え方になり、査読者が読み慣れた形になるため)。
節の並びは学会テンプレートの見本 (§8.3) に合わせる: 表題ページ → Introduction → Materials and methods → Results → Discussion → (Conclusion) →
番号なしの節 Conflicts of interest → (Ethics declaration) → (Acknowledgements) → References。

### 3.1 表題ページ (1 ページ目)

| 要素 | 規定 | 本テンプレートでの書き方 |
|------|------|------------------------|
| Title | 簡潔で情報量があること。**シリーズ番号つきの同一主題の題 (Part I / Part II) を使わない**。**略語を使わない** (分野で一般的なものを除く) | `::: {custom-style="Title"}` |
| Authors | 名 (given) と姓 (family) をフルで、ミドルネームは頭文字。**姓はすべて大文字** (`Taro YAMADA`)。学位・肩書は書かない | `::: {custom-style="Author"}`。カンマで区切っても、改行で 1 行 1 人に並べてもよい |
| Affiliations | 研究室・部門・研究所・大学、市・州・国まで。**異なる機関に属する著者がいるとき**は**上付きの数字**で対応づける (1 機関だけなら要らない) | `::: {custom-style="Affiliation"}` に `^1^Graduate School of …` (1 機関 1 段落。番号の後にタブも空白も書かない — docx で番号の直後にタブが入る) |
| 新住所 | 異動後の新住所は**脚注**に書き、**上付きの記号** ("such as * and **") で示す | 著者名の直後に普通の脚注 `^[Present address: …]` を書く。docx では著者の段落の中の脚注の参照と番号が出てきた順に `*` `**` になる (★ `title_page.author_footnote_marks`)。文面の同じ脚注は 1 つの記号・1 つの脚注にまとまる |
| Running title | 題が **50 字 (空白込み) を超える**なら、所属の後に **50 字以内**の running title を置く | `::: {custom-style="Subtitle"}` (テンプレートの abbreviated title の位置とスタイル)。この段落の文字が本文のページの柱の中央に入る (§9 の 5) |
| Abstract | 1 段落・**350 語以内** (全種別)・**構造化抄録は不可** ("Structured abstracts cannot be accommodated")。扱う問題・方法・主な結果・結論を含める。特定の略語と図表の引用を避ける ("Avoid … citing figures or tables")。**文献の番号の引用を使わず**、先行文献に触れるなら題を省いて本文中に書く (例: `Kawada T, Mukkamala R, Sugimachi M: Adv Biomed Eng. 8, 110-123, 2019`) | 見出し `# Abstract {.unnumbered}` + `::: {custom-style="Abstract"}` |
| Keywords | **5 語まで**。**題の語を繰り返さない** ("Do not repeat words from the manuscript title") | `::: {custom-style="Keywords"}` (`**Keywords**: a, b, c.` の 1 行) |
| Received / Revised | テンプレートの見本に `Received ………….. [Do not enter]` の欄がある | 骨格はそのまま置く (編集部が記入する。書き換えない) |

**連絡著者 (corresponding author) の連絡先を表題ページに書く規定は無い** (テンプレートにも欄が無い)。連絡先は Submission Form (§6.4) と投稿系に入力する。

### 3.2 本文

| 節 | 規定の要点 |
|----|-----------|
| Introduction | 新規性と妥当性が分かるように。目的・先行研究との関係・問題の定義。網羅的な文献レビューは要らない |
| Materials and methods | 再現できる詳しさで。**珍しい試薬・動物・菌株・装置は供給元の所在地 (市・国) を括弧で**。式と図は簡潔に。理論は検証する問いに関係するものだけ |
| Results | 考察で使う結果。図表の説明を繰り返さない。比べる結果は同じ図表に |
| Discussion | 結果の位置づけと手法の妥当性。**限界と矛盾する結果**。序論・結果の繰り返しを避ける |
| (Conclusion) | 規定には無いが、テンプレートには番号つきの節としてある |

- **略語**: 本文の初出で正式名と括弧で定義する。**題と抄録で定義していても、本文の初出で改めて定義する** (規定は題と抄録を本文の初出とみなさない)。
  Title では分野で一般的なもの以外の略語を使わず、Abstract では特定の略語を避ける。
- **単位と記号**: できる限り SI。**量の記号は斜体、単位と元素記号は立体**。
- **脚注**: 規定の文は "indicated by symbols such as ¹ and ²" で、例は**上付きの数字**である。当該ページの下に置き、最小限に。
  pandoc の脚注 (上付きの数字) がそのまま規定に合う。記号 (`*` `**`) にするのは所属の**新住所の脚注**だけ (§3.1)。
- **AI ツール** ("Use of artificial intelligence tools"): 生成・非生成を問わず、AI ツール (LLM を含む) の使用は **Methods の節で開示し詳しく記述する**
  (データの収集・解析、図の作成・修正、原稿の全部または一部の執筆を含む)。どのツールをどう使ったかを書く。
  **生成 AI の使用は、研究デザイン・方法の不可欠な一部である場合に限って原則として認められ、それ以外は編集者が個別に判断する**。
  綴り・文法の確認など**非生成 AI** で読みやすさを改善するのは可だが、これも投稿時に編集者へ申告する ("should be declared to the editors upon submission")。
  → 骨格は Materials and methods の末尾に小節 `## Use of artificial intelligence tools` を置き、文例は `statements.md` の §4 (§3.4)。
- **臨床試験**: 登録番号と登録先 (ICMJE / CONSORT)。
- **報告ガイドライン**: EQUATOR Network に従う。系統的レビューとメタ解析は **PRISMA が必須**。

### 3.3 本文の後ろの節 (番号なし)

| 節 | 規定の要点 |
|----|-----------|
| Conflicts of interest | 全著者の利益相反を申告する。**無い場合の定型文**: "The authors declare no conflicts of interest with any companies or commercial organizations per the definition of Japanese Society for Medical and Biological Engineering." (「定義」は §6.3 の COI 開示書式の基準)。別に著者ごとの COI 開示書式を出す (§6.2) |
| Ethics declaration | 人・動物を対象にしたなら倫理的な扱いの記述。**例文 3 つ** (ヘルシンキ宣言 + インフォームド・コンセント / 動物実験の基本指針 / ヒトゲノム・遺伝子解析研究の倫理指針)。**倫理委員会の承認などの証拠書類を原稿とともに出す** |
| Acknowledgements | 簡潔に。**資金源はすべてここに、資金提供者と助成番号の両方を書く** |
| References | §4 |

節名の綴りは規定の中でも揺れる (`Acknowledgments` / `Acknowledgements`、`Conflicts of interest` / `Conflicts of interests`)。§9 の 6。

### 3.4 骨格と文例集

`data/journals/abe/skeleton/` に、執筆の出発点として写して使う雛形を置いてある (ビルドの対象ではない)。

| ファイル | 中身 |
|---------|------|
| `main.md` | 記入式の原稿 (記入欄は `<<…>>`)。表題ページ (題・著者・所属・running title・受付日と改訂日の欄・Abstract・Keywords) → 番号つきの 5 節 → 番号なしの 4 節 (§3.3)。Materials and methods の末尾に `Availability of data and materials` と `Use of artificial intelligence tools` の小節。Conflicts of interest は規定の定型文、Ethics declaration は規定の例文 1、Acknowledgements は資金提供者 + 助成番号の文。各節の頭に規定の要点を HTML コメントで (出典は本書の節番号)。図表 4 例 (段の図・段抜きの図・段の表・段抜きの表) と式 1 例は HTML コメントで囲んである (コメントの開始行と終了行を消せば使える) |
| `statements.md` | 定型の記述の文例集 (参照専用)。利益相反・倫理 (規定の例文 3 つ)・資金 (科研費の形)・AI ツールの開示 (要素 6 つと 3 つの場合: 非生成だけ / 研究の方法の一部としての生成 AI / それ以外の生成 AI)・AI の作業記録の項目・データの入手先と公開・臨床試験の登録・画像の加工・報告指針・転載の出典。冒頭に置き場所の表 |
| `cover-letter.md` | **任意** (規定にカバーレターの記述は無い。§6.2・§15)。関連原稿の開示 (規定の "must inform the editors") と非生成 AI の申告 (規定の "should be declared to the editors upon submission") の置き場所として置いた |

判断:

- **規定が置き場所を決めていない定型の記述** (データの入手先と公開・臨床試験の登録・画像の加工・報告指針) は **Materials and methods の末尾**に置く。
  どれも方法の性質で、規定の Methods の要求 (再現できる詳しさ) と同じ向きであり、Methods と指定された AI の開示と並べれば見落としにくく、
  番号なしの節を足すとテンプレートの節の並びから外れるため。転載の出典はその図表の凡例に書く。
- **AI の作業記録の書式は `statements.md` の §5** に置いた (骨格に `README.md` を置くと、`cp -r skeleton/. src/` で `src/README.md` を上書きするため)。
  記録は git で追跡するファイルに書き足す (コミットのたびに退避・削除される一時ファイルには書かない)。
- **記入欄は docx でも見える形にした**: pandoc は `<<Department>>` のように HTML のタグとして読める記入欄を docx で消す。骨格の記入欄は中身にカンマ・読点・
  空白の後の数字を入れ (`<<Department, 部門>>`)、docx に `<<…>>` のまま出る形にしてある。規定チェックは残った記入欄を要修正にする。
- 写した直後の骨格の規定チェックは、要修正が記入欄の指摘だけ (`main.md` と `cover-letter.md` で 1 件ずつ)・参考 0 件になる。

## 4. 引用と文献 (modified Vancouver)

- 本文: **出現順の番号を角括弧で** — `[1]`、`[3, 4]`、`[7–10]` (範囲はエンダッシュ、複数はカンマ + 空白)。
- 文献リスト: **全著者の姓と頭文字** (et al. で打ち切らない)。**題を省略しない**。**誌名は PubMed の略記**。**巻は太字**。
- 引けないもの: 社内資料・未発表原稿・未発表の学位論文・私信・カタログ・個人的な通信。標準的な手段で見つけにくい文献は避ける。
- 規定の例 (**公式例**。受入テストの正解 `data/dummy/abe-csl/expected.txt` の 1〜6 行目。下の表記はページ範囲をエンダッシュにしたもの):

```
[1] Hohne KH, Bernstein R: Shading 3D-images from CT using gray-level gradients. IEEE Trans Med Imag. 5(1), 45–47, 1986.
[2] Born M, Wolf E: Principles of Medical Engineering, 2nd ed. Pergamon Press, New York, pp. 69–94, 1988.
[3] Chandler S: Adaptive model control applied to real time blood pressure regulation. In: Black C ed. Pattern Recognition and Machine Learning, McGraw-Hill, Berlin, pp. 310–324, 1985.
[4] Heel N: Automated blood pressure control using a self-tuning regulator. Proc of NCGA’S Computer Graphics Conference ’87, Vol. 2. Am Med Eng Soc., New York, pp. 152–161, 1988.
[5] White AG: US Patent No. 1234567. 1982.
[6] Advanced Biomedical Engineering: Instructions to Authors. <https://abe-journal.org/submission/> [accessed on January 1, 2020].
```

  - 巻 (例 1 の `5`) は太字。PDF のテキスト抽出では太字が落ちるので、受入テストは docx の `w:b` で見る。規定 PDF で太字なのは例 1 の `5` だけで、
    例 4 の `Vol. 2` は太字でない。
  - **ページ範囲の区切り**: 規定 PDF の文献の例は U+2012 (FIGURE DASH `‒`) で書かれているが、同じ PDF は事務局の住所・郵便番号・FAX 番号にも U+2012 を使い、
    本文の `[7–10]` はエンダッシュ、抄録の例 (`110-123`) はハイフンである (組版で数字の間のハイフンが置き換わった可能性がある)。
    **本テンプレートはエンダッシュ (U+2013) にした** — J-STAGE に載った ABE の掲載論文の文献欄では、ページ範囲がエンダッシュで書かれているため。
    掲載論文の文献の形も公式例 1 と同じ `Author: Title. Journal. 巻(号), ページ, 年.` である。
  - オンライン文献の一般形は `Web page or author (for PDF, etc.): Name of web page or name of document <Web address> [date accessed].` で、
    文書名の後にピリオドが無いが、例 (`e.g.`) にはある。`abe.csl` は例に合わせた。
  - 特許 `[5]` は区切りが `: ... . 1982.` と他と違う。発明の名称は出さない形 (bib の `type` = `US Patent` が CSL の `genre`、`number` が番号)。
  - `[6]` は規定では一般形の行で、例の行 (`e.g. Advanced Biomedical Engineering: …`) には番号が無い。上の 6 行目は例の行に `[6]` を前置したもの。
    受入テストの正解は番号を書かない形 (番号は行順で、docx の番号 `[n]` は別に照合する)。
- 規定とテンプレートの文献の例は食い違う (テンプレートは `pp.` つき・巻 `MI-5`。§9 の 3)。**規定の例を採った**。
- **CSL の公開の様式は無い** (CSL のリポジトリに ABE の様式は無い) ので、本テンプレートが書いた: **`data/journals/abe/abe.csl`** (誌の公式ではない)。

**`abe.csl` の実装**:

- 本文は `[1]` / `[3, 4]` / `[7–10]` (`collapse="citation-number"` は 3 件以上の連番だけをまとめ、2 件の連番はまとめない)。ページの指定は `[2, p. 70]`。
- 文献は `[n]` + 本文 (`second-field-align="flush"`)。段落は学会テンプレートの Reference スタイルを基にした別名 Bibliography (ぶら下げ字下げ 7.5 mm)。
  全著者 (et-al を書かない)・「姓 頭文字」・著者の後に `: `・誌名は bib の `journal` (略記) から末尾のピリオドを外す・巻は太字。
  ページ範囲は省略しない (公式例と掲載論文が `152–161` の形)。
- 型ごとの形は公式例の 6 種 (雑誌論文 / 本 / 章 / 会議録 / 特許 / オンライン)。公式例に無い型 (報告書・学位論文・データセットなど) は本の形で出し、
  URL (公式例 6 の形) か DOI を後ろに足す。本・章・会議録には URL を出さない。雑誌論文の DOI は巻・号・ページがどれも無いとき (早期公開) だけ出す。
  判断の一覧は `abe.csl` の冒頭のコメント。
- `<info>` は `<title>` に `(unofficial)`・`<id>` と `rel="self"` は本リポジトリでの置き場所・`rel="template"` は元にした AMA の様式とその作者・寄稿者・
  `<summary>` に「誌の公式ではない」。ライセンスは元の様式と同じ CC BY-SA 3.0 (`THIRD_PARTY_NOTICES.md`)。
- pandoc の citeproc の挙動: `page-range-delimiter` は効く。版の語を `ed.` にして後ろの `.` と重なっても 1 個に畳まれる。
  **pandoc は英語の題をセンテンスケースに直す**ので、Title Case の書名・会議録の名前は bib で全体を波括弧に入れる (`{{Principles of Medical Engineering}}`)。
- **文献の番号の後の空白**: pandoc は文献の番号の後に「空白 + タブ」を書く。Word では `[10]` で「番号 + 空白」がぶら下げ字下げ (7.5 mm) を越え、
  1 行目の本文の頭が次の既定のタブ位置 (段の左 + 14.8 mm) に飛ぶ。★ `bibliography.label_separator: tab` で後処理が空白を消し、テンプレートの見本と同じ
  「`[1]` TAB 本文」にする。`[1]`〜`[99]` はそろう。`[100]` 以上は番号だけで 8.1 mm あるので本文の頭は + 14.8 mm に出る (§13)。
- **受入テスト**: フィクスチャ `data/dummy/abe-csl/` (`main.md`・`ref.bib`・`expected.txt`・`check.yaml`)。`expected.txt` は公式例 6 行 + 本テンプレートの判断の
  回帰の確認 4 行 (著者 7 名と号なし・編者 2 名と版・DOI だけの論文・URL つきの報告書)。`check.yaml` の `citations` で本文の引用 17 件
  (`[3, 4]` / `[7–10]` / `[1, 5]` / `[2, p. 70]`・表のセル・図の題) を、`bibliography_label: "[{n}]"` で文献の番号の形と docx の「番号 + TAB + 本文」を照合する。

```bash
bash scripts/build.sh --input data/dummy/abe-csl --journal abe --article-type original
bash scripts/check-csl.sh --journal abe --docx data/step02_build/main.docx    # 文献 10 件 + 本文の引用 17 件
```

## 5. 図表

- **本文中の適切な位置に、PDF 版の見た目を写す大きさと形式で埋め込む** (分離提出しない。profile の `figures.separate: false` = §14.1)。
- 番号は本文での引用順。本文と題は **`Fig. 1`, `Fig. 2`** / **`Table 1`, `Table 2`** (アラビア数字)。
- **図の題とキャプションは図の下、表の題とキャプションは表の上**。
- 題とキャプションは**最小限の大文字** ("minimal capitalization"。文頭と固有名詞だけ)。図中の項目も文法上必要な場合を除き大文字にしない (テンプレートの注記)。
- キャプションは**本文を読まずに理解できるように完結させる**。
- 画像の加工は最小限・画像全体に・分野の基準内で、原稿に明記する。部分的な移動・削除・追加・強調は不可。編集者は加工前の画像を求めうる。
- 他者の著作物の図表は権利者 (と出版社) の許諾を取り、許諾の写しを初回投稿時に添える (§6.2)。
- 解像度・ファイル形式の規定は**無い** (format-free で 1 本の PDF に埋め込むため)。受理後の制作で別に求められるかは分からない (§15)。

本テンプレートでの書き方は図表の題と凡例の書き分け (題 = キャプション / 凡例 = 直後の `Legend` Div。`CLAUDE.md` の「図表の題と凡例の書き分け」) のままで、
表の凡例も表の後に書く。docx では後処理が表の凡例を題と表の間へ移し (★ `tables.legend_position: above`)、図 → 題 → 凡例・題 → 凡例 → 表を段・ページで
分けない (★ `figures.keep_together`)。題の形は §8.3 と §11.4。

## 6. 提出物 (初回投稿)

### 6.1 原稿本体と書式の PDF

規定の文 (Web 版): "Authors should convert the submission form, statement, manuscript text, and tables and figures **into one PDF file** for upload to the system."
PDF 版の同じ文は "statement" が無く "(available at the relevant ABE webpage)" がある (§0)。配布される書式は 1 つの docx に Submission Form と
Author Statement の 2 部が入っている (§6.4) ので、どちらの文に従っても 1 本の PDF の中身は同じになる。

**本テンプレートは結合しない**。本文 (図表を埋め込んだもの) と書式をそれぞれ Word で PDF にし、Editorial Manager に別々に上げる。
規定の文は "should" で、別々のアップロードを受け付けるかは投稿画面を見ないと分からない (§15)。受け付けないと分かったら、
PDF をつなぐ道具 (qpdf など) をイメージに足し、`manuscript.pdf` と `forms/*.pdf` (§6.5) をつなぐ処理を足せばよい。

### 6.2 その他の提出物

| 提出物 | 規定 | 本テンプレートの扱い |
|--------|------|------|
| COI 開示書式 | **著者ごとに 1 通**。連絡著者が**全員分を PDF で**上げる | `forms/` に著者ごとに置く (§6.5) |
| 英文校正の証明 | 英語を母語としない著者は**専門の校正会社の証明書 (または請求書)**、または認定・専門の校正者による校正の証明を出す。出せないなら編集事務局に連絡する。英語の不備は査読の前に返却されうる。Submission Form は、**著者の 1 人が校正したなら、その著者が筆頭か連絡著者の英文の査読つき論文 2〜3 本を添える**道も挙げている (§6.4) | 提出の方法・時期は規定に書かれていない (§15) |
| 倫理審査の証拠書類 | 倫理委員会の承認など。**原稿とともに** | `forms/` に置ける |
| 転載許諾 | 著者の著作権下にない素材・既発表の素材は権利者 (と出版社) の許諾。**許諾の写しを初回投稿時に** | 同上 |
| Supplementary Material | **最終形で初回投稿時に**。受理後は変更不可。**1 ファイル 50 MB・合計 50 MB 以下**。画像・動画・音声・Word・Excel を推奨 (Web 版は Word が抜けている)。標準のソフトで開けなければ別の形式を求められうる。Submission Form は加えて、**バイナリ (実行形式) とアーカイブ (圧縮) のファイルを含まない**・英語で書く・英文校正の証明・ソースを含むなら利用の制限の有無と中身を補足資料に書く、を確かめさせる (§6.4) | `<INPUT_ROOT>/supplementary/` を無変換で複製。容量は要修正、アーカイブ・実行形式は参考で知らせる (★ `limits.supplementary_*`・`lint.supplementary_archives`) |
| 査読者の推薦・除外 | 任意。編集者は従う義務を負わない | 投稿系の入力欄 |
| カバーレター | **規定に記述が無い** | 投稿系に欄があれば任意 (§15)。骨格に任意の `cover-letter.md` (§3.4) |

### 6.3 COI 開示書式の項目

著者名・所属・申告日 (dd/mm/yyyy)・投稿論文の題を記入し、次の 9 項目それぞれに No / Yes (団体名) を付ける (1 年間・1 団体あたり。金額の閾値は円):
役員・顧問の報酬 100 万円以上 / 株式の利益 100 万円以上または 5 % 以上の保有 / 特許使用料 100 万円以上 / 講演料など 50 万円以上 /
原稿料 50 万円以上 / 臨床研究費 200 万円以上 / 研究費 (受託・共同・寄付) 200 万円以上 / 寄付講座への所属 / 研究と無関係の旅費・贈答 5 万円以上。

Conflicts of interest の定型文の "per the definition of Japanese Society for Medical and Biological Engineering" は、この基準を指す。
**著者ごとに 1 通**なので、全共著者に記入を頼む必要がある (共著者が多いほど日数がかかる)。本文の Conflicts of interest の申告と食い違わないこと。

### 6.4 Submission Form and Author Statement の項目

1 つの docx に 2 部が入っている (どちらも英文。書式の文面は写さず、項目だけを書く)。

**Submission Form** (事務局が記入する受付番号・受付日・改訂日の欄は記入しない):

| 項目 | 記入のしかた | 本テンプレートとの関係 |
|------|------------|---------------------|
| 記事種別 | Review / Original Paper / Research Letter / Technical Note から不要なものを消す | `article_types` の 4 種と一致 (§2) |
| 題 | 記入 | — |
| 著者 | 会員番号と氏名を並べ、**連絡著者に丸印** | 連絡著者は投稿後に変えられない (§1)・掲載料の会員の扱い (§1) |
| 所属・連絡著者の連絡先 | 機関・住所・郵便番号・電話・FAX・E-mail | 規定は表題ページに連絡先を求めない (§3.1)。この書式で渡す |
| 書式の準拠 | 文献の書式が規定どおりか・**テンプレートを使ったか** (Yes/No) | 本テンプレートは学会テンプレートを雛形にする (§3) |
| 英文 | 英文校正の証明を添付したか。**著者が校正したなら、その著者が筆頭か連絡著者の英文の査読つき論文 2〜3 本を添付したか** | §6.2 |
| 既発表・投稿中 | 他誌・書籍・会議録に一部でも出した・出しているか。Yes なら詳細と転載の許諾の書類 (JSMBE の誌と会議録なら許諾は要らない) | §1 の既発表 |
| 著作権のある図 | 著者と JSMBE 以外が権利を持つ図を使うか (Used/Not used)。使うなら**図の番号**と許諾の書類 | 転載許諾 (§6.2) |
| 倫理 | 所属に倫理委員会があるか・原稿に倫理的配慮を書いたか | Ethics declaration (§3.3) |
| 補足資料 | 添付の有無。ファイルごとの名前・形式・査読を望むか。**合計 50 MB 以下・1 ファイル 50 MB 以下・バイナリを含まない・アーカイブを含まない・英語・英文校正済み・その証明を添付**のチェック。ソースを含むなら読者の利用の制限の有無と中身を補足資料に書いたか | 容量とアーカイブは規定チェック (§6.2) |
| 掲載料 | 筆頭か連絡著者が JSMBE 会員か (Yes: US$ 600 / No: US$ 1,600) | §1 |

**Author Statement** (編集委員長あて): 日付・題を記入し、既発表でなく他所に投稿していないこと・ヘルシンキ宣言などの倫理規定に従うこと・
Submission Form を正しく記入したこと・利益相反を適切に開示したこと・全著者が原稿を読み内容を知っていることを確約する。
**全著者が氏名を書き、署名と日付を入れる** (足りなければ用紙の写しを足す)。→ 記入済みの書式は署名と個人情報を含むので、`<INPUT_ROOT>/forms/` に置いて
git で追跡しない (`.gitignore` は `src/forms/` を外す)。

### 6.5 提出パッケージの実装

`bash scripts/package.sh --journal abe --mode final` の出力 (`data/output/abe/`) と、`bash scripts/roundtrip.sh` が Google Drive の `submission-abe/` に置くもの:

| ファイル | 中身 | 作るもの |
|---------|------|---------|
| `manuscript.docx` | **`main.docx` そのもの** (図表は埋め込んだまま。★ `figures.separate: false` = §14.1) | package |
| `manuscript.pdf` | 上の docx を Word で PDF にしたもの。**投稿系に上げる原稿本体** (`submission.text_formats: [pdf]`) | roundtrip |
| `forms/<名前>.docx` / `.pdf` | `<INPUT_ROOT>/forms/` の直下の記入済みの書式を無変換で複製したもの (★ `submission.collect_forms: true`)。拡張子だけは小文字にそろえて写す (そろえた名前が重なれば止まる)。入力ルートが `src/` 以外で `<INPUT_ROOT>/forms/` が git で無視されていなければ注意を出す | package |
| `forms/<名前>.pdf` (docx から) | docx の書式を Word で PDF にしたもの。同じ名前の PDF を置いた書式 (署名を入れてスキャンしたもの) は、その PDF をそのまま使い docx は Word に回さない | roundtrip |
| `SUBMISSION.md` | 提出物の一覧 (下) | package |
| `supplementary/` | `<INPUT_ROOT>/supplementary/` を無変換で複製 | package |
| `cover-letter.docx` / `manuscript-diff.docx` | 任意 (規定に記述が無い / 再投稿で使う) | package |

`SUBMISSION.md` の節: 原稿本体 (受入形式 PDF・構成は `sections.required` から・`manuscript.pdf` を上げる旨) / 表 (本文中に置いたまま) /
図 (本文に埋め込み) / 動画 / 補足資料 (`submission.supplementary` の規定の要点 + 容量の上限と今回の合計。超過は行に印) /
提出フォーム — `submission.forms` のチェックリスト 8 項目 (Submission Form and Author Statement・著者ごとの COI・英文校正の証明・倫理の証拠書類・転載許諾・
研究データの全量の開示・関連原稿の通知・査読者の推薦 (任意)) と、`forms/` の書式の一覧 / アップロード種別ではないもの (差分 docx の注記は ★ `submission.diff_note`) /
規定チェックの転記。`CAPTIONS.md` は書かない (図表を分離しないので、本文の題と凡例がそのまま提出物になる)。

止まる検査: 書式と補足資料の止まる検査 (読めないディレクトリ・リンク・名前の重なり) は前回のパッケージを消す前に行う (止まっても前回のパッケージは残る)。
`tables.legend_position: above` と `tables.placement: end` / `separate` の併用は build と package が止める。提出用の package は、`main.docx` を build したときの誌・
profile・reference.docx が今と違えば止まる。roundtrip は、PDF を待つ間に package を回し直してパッケージが変わっていれば配送の前に止まる
([`docs/roundtrip-windows-watcher.md`](roundtrip-windows-watcher.md))。

動作例 `data/dummy/abe/forms/` には、学会の書式ではなく**架空のダミー書式** 4 本 (`submission-form.docx`・`coi-yokan.docx`・`coi-chokkan.docx`・`coi-dan.docx`。
1 ページで「DUMMY — … (placeholder)」と書いた表だけ) を置いてある。学会の書式はリポジトリに入れない。

## 7. 改訂と受理後

- 改訂の期限は判定から **3 か月**。改訂が 2 回以上になることもある。査読者のコメントは原則そのまま著者へ渡される。
- **回答書 (response to reviewers) と変更箇所の示し方の形式は規定に無い**。本テンプレートは回答書 `src/revise-report.md` と全領域の差分 docx をそのまま使う。
  - 差分 docx (`bash scripts/diff.sh <旧版> --journal abe`) には build と同じ後処理 (番号なしの見出し・柱・所属のタブ・題と凡例・2 段組の節・段抜き・段の幅の頭打ち・
    式番号・新住所の記号) が掛かる。差分の文字スタイル DiffAdd / DiffDel は reference.docx と差分の後処理の両方にある。Word での見え方は §11.5。
  - 回答書は 1 段組・行番号なし・柱は空。学会テンプレートの見出しのスタイルは自動番号を持つので、★ `headings.numbered_scope: manuscript` で本文以外の文書の
    見出しの番号を外す。書き方は `#` / `##` の見出し・査読コメントは引用ブロック。動作例は `data/dummy/abe/revise-report.md`。
  - 回答書で示す行番号は、改訂稿の PDF のページと行で数える (行番号はページごとに 1 から振り直す。§8.1)。
- **査読コメント・回答書・事務局とのやりとりは秘密に保つ** (§1 の通信の秘密)。
- 受理後: 編集部の軽い校正 → 連絡著者の承認 → 組版 → **校正刷りは受領から 2 日以内に返送** (誤植・脱落の修正のみ)。不在の予定は前もって事務局へ伝える。

---

## 8. 学会テンプレート `ABETemplate.docx` (ver.3) の構造

OOXML を直接読んで確かめた値。

### 8.1 ページと節

| 項目 | 値 |
|------|-----|
| 用紙 | A4 (11 906 × 16 838 twip) |
| 余白 | **上 25.0 mm (1 418) / 下 20.0 mm (1 134) / 左右 15.0 mm (851)**。ヘッダ 15.0 mm・フッタ 17.5 mm |
| 本文幅 | 180.0 mm (10 204 twip) |
| 節 1 (表題部) | **1 段組**・行番号なし・ヘッダとフッタの参照あり。**Keywords の次の段落は改ページ (`<w:br w:type="page"/>`) だけを持ち、その次の空の段落が節 1 の `w:sectPr` を持つ** → 1 ページ目は表題ページだけで、本文 (節 2) は 2 ページ目から始まる (規定の "The first page should be the title page, which should include … the Abstract and the Keywords" と一致)。Word では 2 ページ目の先頭に空行は出ない |
| 節 2 (本文) | `w:type="continuous"`・**2 段組** (`w:cols w:num="2" w:space="754"` = 段間 13.3 mm、**段の幅 83.3 mm**)・**行番号** `w:lnNumType w:countBy="1"` (`w:restart` を省いた既定 = **ページごと**)・`docGrid linesAndChars` |
| ヘッダ (柱) | 斜体 (スタイルは太字 9 pt)。`distributed` ⟶TAB⟶ `Template for ABE` ⟶TAB⟶ `ver.3`。本文に「中央の "template for ABE" を running title に置き換える」と指示がある |
| フッタ | 中央に `PAGE / NUMPAGES` のフィールド (`3/3` の形) |

規定に行番号の要求は無い (行番号はテンプレートの本文の節の設定)。

### 8.2 スタイル (名前 → ID)

ID はテンプレートが和文の Word で作られたため日本語版の自動 ID (`a`, `a0`, `1` …) になっている。**pandoc は名前で引くので ID の違いは吸収される** (§11.1)。
本テンプレートのコードも ID を決め打ちせず、名前から引く (`main/00_setup/lib/docx_styles.py`)。

| 名前 | ID | 中身 | 用途 |
|------|----|------|------|
| Normal | `a` | Times New Roman (和文は ＭＳ Ｐ明朝)、**10.5 pt**、両端揃え、行間 最小 12 pt、`snapToGrid=0` | 既定 |
| Body Text | `a0` | Normal + 字下げ 1 字・段落後 0.5 行 | 本文 |
| Title | `a7` | **Arial 太字 16 pt**、行番号抑止、後 12 pt | 題 |
| Subtitle | `af2` | Title を基に 14 pt | abbreviated title (running title) |
| Author | `Author` (独自) | Normal + keepNext・後 0.5 行 | 著者 |
| Affiliation | `Affiliation` (独自) | **ぶら下げ字下げ 283 twip (5.0 mm)・タブ位置 426** | 所属。見本は `*` + TAB + 本文。本テンプレートは原稿の `^1^Graduate …` の番号の直後に docx でタブを入れ、2 行目の頭をそろえる (★ `title_page.affiliation_label_tab`) |
| heading 1 | `1` | **Arial 太字 12 pt・中央揃え・自動番号 (`%1.`)** | 節 |
| heading 2 | `2` | heading 1 を基に 11 pt・左揃え・`%1.%2`。**番号定義の小節の段 (ilvl 1) に `w:lvlRestart w:val="0"` (= 戻さない)** があり、そのままでは Word で小節の番号が節で戻らない (`3.` の下が `3.5`)。reference.docx を作るときに外す (§11.3) | 小節 |
| heading 3 | `3` | Arial 太字 10.5 pt・`%1.%2.%3` | 小小節 |
| NoNumberSectionHeader | 同 (独自) | Arial 太字 11 pt・前 0.5 行・**番号なし** | Abstract / Conflicts of interest / Ethics declaration / Acknowledgements / References。本テンプレートは `{.unnumbered}` の見出しをこのスタイルの段落にする (★ `headings.unnumbered_style`。`main/00_setup/filters/unnumbered-style.lua`) |
| caption | `ae` | **太字**・行番号抑止 | 図表の題 (`Fig.` `SEQ Figure` / `Table` `SEQ Table`) |
| Reference | `Reference` (独自) | ぶら下げ字下げ 424 twip (7.5 mm) | 文献 (`[1]` + TAB) |
| Equation | `Equation` (独自) | Body Text を基に、**右タブ 4 678 twip (≒ 段の幅)** + Cambria Math | 別行立ての式と式番号 `(1)` |
| footnote text | `a5` | 8 pt | 脚注 |

**改版で上のスタイルが消える・名前が変わったとき**: reference.docx を作るとき、雛形がふつう持つスタイル (Body Text / Title / Subtitle / Caption /
Footnote Text / Footnote Reference / Author / Affiliation) が無ければ受け皿の別名を足して警告し (その段落は基にしたスタイルの書式で組まれる)、別名の基の
2 番目以降の候補を使ったとき (Reference が無くて Bibliography を Normal から作ったなど) も警告する。警告は `.reference.warnings` に記録して build・diff のたびに
出し直し、build・diff の後処理が毎回、出力の未定義のスタイルと heading 1〜3 の自動番号の欠けを警告する。表題部の節が 2 段組以上の雛形でも、build が 1 段組に直して警告する。

### 8.3 本文の構成 (テンプレートの見本)

表題 → 著者 (`Taroh Seitai*, …`) → 所属 (`*` TAB …) → abbreviated title (`(abbreviated title)`) →
`Received ………….. [Do not enter]` / `Revised ………….. [Do not enter]` → `Abstract` → 抄録 1 段落 → `Keywords: a, b, c.` → **改ページ** (改ページだけの段落) →
**節区切り** (節 1 の `w:sectPr` を持つ空の段落) →
1 Introduction / 2 Method (2.1 Subsection / 2.1.1 Subsubsection, Figure and table, Equation) / 3 Results / 4 Discussion / 5 Conclusion →
Conflicts of interests / Ethics declaration / Acknowledgements / References (いずれも番号なし)。

- 図の見本は**インラインのテキストボックスの中に画像と題** (`Fig. 1 An example of figure.`) を入れている。表は `w:tbl` で、題は表の上に caption スタイル。
- 題の形: **`Fig. 1 An example of figure.`** / **`Table 1 Table is an example ….`** — 番号の後にコロンもピリオドも無く、空白 1 個。
- 文献は `[1]` + TAB + 本文 (Reference スタイル)。
- 表題部の最後の段落 (Keywords) までを 1 段組の節にする (★ `layout.title_block_until: Keywords`)。

### 8.4 メタデータと、reference.docx から消すもの

テンプレートの `docProps/core.xml` の最終更新者 (`cp:lastModifiedBy`) には個人名が入っている (作成者 `dc:creator` は空)。
ほかに文書を特定しうる情報として、`word/settings.xml` に文書の補助ツールが書いた `w:docVars` (文書 ID と作業回の番号)・文書 ID (`w14:docId` / `w15:docId`)・
編集履歴の識別子 `w:rsids` があり、本文の段落にも `w:rsid*` と `w14:paraId` がある。`customXml/item1.xml` は Word の文献管理の置き場 (中身は空)。
pandoc の出力の `core.xml` には個人名は移らないが、**`settings.xml` はそのまま出力に移り**、**テンプレートから作る reference.docx 自体には全部残る**。

そこで `make-reference.sh abe` (`main/00_setup/lib/patch_reference_docx.py --base`) は reference.docx を作るときに次を消す:

- core.xml の作成者・最終更新者など (作成日時・更新日時・版数は残す)・app.xml の会社名など
- settings.xml の `w:docVars` / `w:rsids` / `w14:docId` / `w15:docId` / `w:attachedTemplate` (と、それが指す関係定義)・`w:documentProtection` / `w:writeProtection`
  (パスワードのハッシュを持ちうる)・`w:trackRevisions`・`w:mailMerge` (データの元のパスを持ちうる)
- 本文とヘッダ・フッタ・脚注の `w:rsid*` / `w14:paraId` / `w14:textId`・styles.xml の `w:rsid`
- `customXml/` (と関連の関係定義・種類の宣言)・コメントのパート・`people.xml`・`docProps/custom.xml`・縮小版の画像
- 全パートの変更履歴を確定させる (挿入・移動先は中身を残し、削除・移動元は中身ごと消す。書式の変更履歴は今の書式を残す)。コメントの範囲と参照・
  編集の例外の範囲 (`w:permStart` / `w:permEnd`。`w:ed` にアカウント名を持ちうる) を外す
- どこからも指されないパートと、本文から参照されない関係 (見本の図・リンクの残り)

**残すパートは許可リスト** (pandoc が雛形から読むパートとそれが指す画像・埋め込みの書体) にし、許可リストに無いパートは外して警告する。最後に、どのパートも
関係定義に無い ID を指していないこと、作成者などの属性 (`author` / `initials` / `userId` / `providerId` / `ed`) が残っていないことを確かめ、あれば止める。
見本の文章は消して節の骨組み (改ページの段落・節 1 の sectPr を持つ空の段落・最終の sectPr) だけを残す (pandoc は雛形の本文で最初に現れる sectPr を出力に写すため。§11.1)。
pandoc は出力の settings.xml に**中身の空の** `<w:rsids>` を自分で書く (識別子は入らない)。

**学会テンプレートと、それから作った reference.docx は公開しない・コミットしない** (`.gitignore` は誌のディレクトリの docx をまとめて外す)。
学会テンプレートを雛形にして作った docx は、試験用の原稿 (フィクスチャ) としてもコミットしない (settings.xml などが移るため)。

## 9. 規定とテンプレートの食い違い

規定とテンプレートが食い違うときは**規定を優先する**。

| # | 項目 | 規定 (1 April 2026) | テンプレート (ver.3) | 本テンプレートの扱い |
|---|------|-----------------|-------------------|------------------------------|
| 1 | 著者の姓 | **すべて大文字** ("All surnames must be fully capitalized") | `Taroh Seitai` (大文字でない) | 規定に従う (`Taro YAMADA`)。規定チェック (★ `lint.author_surname_caps`) が要修正にする |
| 2 | 所属の対応づけ | **上付きの数字**。記号は新住所の脚注に使う | `*`, `**` の記号 | 規定に従う (`^1^`)。記号は新住所の脚注にだけ使う (§3.1) |
| 3 | 雑誌論文の文献の例 | `5(1), 45‒47, 1986.` (pp. なし、U+2012) | `MI-5(1), pp. 45–47, 1986.` (pp. あり、エンダッシュ) | 規定の例を正解にする (`abe.csl` は pp. なし・巻だけ太字)。区切りの字だけはエンダッシュにする (掲載論文の字。§4) |
| 4 | 方法の節名 | Materials and methods | Method | 原稿に任せる (骨格は `Materials and methods`。規定チェックは `Methods` などを同一視する) |
| 5 | abbreviated / running title | 題が 50 字を超えるなら running title (50 字以内)。別に「the title page に abbreviated title を supply する」とも書く | `(abbreviated title)` を Subtitle で 1 行 | 1 行で兼ねる。題が 50 字以下でも書いてよい (柱に使う) |
| 6 | 節名の綴り | 方針の節は `Conflicts of interest`、**Manuscript Preparation の見出しは `Conflicts of interests`**。`Acknowledgments` と `Acknowledgements` も混在 (PDF 版が `Acknowledgments`・Web 版が `Acknowledgements`) | `Conflicts of interests` / `Acknowledgements` | 骨格は `Conflicts of interest` / `Acknowledgements` (英式でそろえる)。規定自身が揺れているので、規定チェックは綴りの揺れを同一視する (★ `sections.aliases`) |
| 7 | 図の番号の書式 | 本文 `Fig. 1` | 題 `Fig. 1 …` | 一致。題も `Fig. 1 …` |

---

## 10. 規定 ⇔ 実装の対応一覧

★ は誌固有の要件のために足した `profile.yaml` の拡張キー (どれも省略可能で、既定では何もしない。[`docs/profile-schema.md`](profile-schema.md))。
規定チェックは `main/step05_package/validate.py` で、区分は「要修正」(規定に合わない可能性が高い) と「参考」(語の有無から推し量る) の 2 つ。

| 要件 | 規定 | 実装 | 確かめ方 |
|------|------|------|---------|
| 学会テンプレートの体裁 (A4・非対称の余白・Times 10.5 pt・Arial の見出し) | テンプレート | `make-reference.sh abe` が学会テンプレートを雛形に reference.docx を作る (★ `reference_base`。体裁は焼き込まない。別名スタイル・見出しの番号定義・題のハイフネーション・見本の文章とメタデータの除去)。build / diff は生成の元 (テンプレート・profile・生成処理) が変われば作り直す。指紋が ★ `reference_base_sha256` と違えば止まる。profile の体裁キーはテンプレートの値を写した照合用で、書いたキーだけを照合する (改版の検知) | build の警告・Word の PDF (§11.7) |
| 表題部 1 段組 → 本文 2 段組 (連続の節区切り) | テンプレート | ★ `layout` (`columns` / `column_space` / `title_block_until` / `title_page_break` / `scope`)。`main/step02_build/layout.py` が Keywords の後に改ページの段落と表題部の節の段落を置き、最終の節を reference.docx の本文の節の写しにする。カバーレターと回答書は 1 段組 | §11.3 の形と照合・Word (§11.2) |
| 本文の節の行番号 (ページごと) | テンプレート (規定には無い) | 本文の節はテンプレートの `lnNumType countBy=1` を持ち、表題部の節には付けない。段抜きの 1 段組の節は `w:distance="180"` で位置をそろえる。カバーレターと回答書は行番号なし (`line_numbers_scope: manuscript`) | Word (§11.2・§11.7) |
| 柱 = running title、フッタ = `n/N` | テンプレート | ★ `header.running_title_from` / `clear_template_labels`。`main/step02_build/frontmatter.py` が柱を TAB + running title にし、左右の文字を消す。カバーレターと回答書は柱を空にする。差分は削除の文字を除く | Word (§11.7) |
| 段の幅 (83.3 mm) を超える図表 | §5・テンプレート | 段組の節の図が段の幅を超えたら縦横比を保って縮め、警告する。表は折り返せない語 (数字など) から最小幅を見積もり、段に収まらなければ警告して `::: wide` を案内する。段抜きは図の `{.wide}` と `::: wide` の Div (+ 直後の凡例) を `main/00_setup/filters/wide-blocks.lua` が目印で囲み、後処理が 1 段組の節で挟む。表の題に `{#tbl:x .wide}` と書いた表 (番号が付かない) は build が警告し、★ `lint.table_caption_attrs` が要修正にする | Word (§11.2) |
| 表題ページの要素と順序 | §3.1 | 骨格 (§3.4) がテンプレートの見本と同じ並び・同じスタイルで書く。所属の番号の直後にタブ (★ `title_page.affiliation_label_tab`)。新住所の脚注を記号に (★ `title_page.author_footnote_marks`)。表題ページの Div (Title / Author / Abstract / Keywords) が無い・2 つ以上なら要修正 (★ `lint.front_matter_divs`。表題ページの検査が黙って空振りしないように) | 動作例の build・Word (§11.6) |
| 番号つきの見出し / 番号なしの見出し | テンプレート | 番号つきの節はテンプレートの自動番号。★ `headings.unnumbered_style` で、citeproc の後の Lua フィルタが `{.unnumbered}` の見出しを NoNumberSectionHeader の段落にする (References の見出しは citeproc が足すため、後に掛ける) | Word (§11.7) |
| `Fig. 1 …` / `Table 1 …`、図の題は下・表の題は上 | §5・テンプレート | ★ `crossref` (`figureTitle: "Fig."`・`titleDelim: ""` など) を build と差分が 2 つ目の `--defaults` で pandoc-crossref に渡す | Word (§11.4) |
| 題と凡例 (キャプション)・表の凡例は表の上 | §5 | 記法は題 = キャプション / 凡例 = 直後の `Legend` Div。★ `tables.legend_position: above` で `main/step02_build/captions.py` が表の凡例を題の後へ移し、題 → 凡例 → 表を keepNext でつなぐ。★ `figures.keep_together` で図 → 題 → 凡例をつなぐ | Word (§11.4) |
| 式番号を段の右端に | テンプレート | ★ `equations.style: Equation`。`main/step02_build/equations.py` が番号つきの式を「式 TAB (N)」にする。段の幅の違う節の式は段落のタブを置き直す | Word (§11.4) |
| modified Vancouver・角括弧・巻の太字 | §4 | `abe.csl` と ★ `bibliography.label_separator: tab` | `bash scripts/check-csl.sh --journal abe --docx …` (§4) |
| 記事種別ごとの語数 (4 000 / 2 500 / 1 500) | §2 | `article_types`。本文語数は本文の節だけ (§12) | 規定チェック |
| 抄録 350 語・1 段落・構造化抄録でない・引用なし・図表に触れない | §3.1 | 350 語と引用は共通の検査。★ `abstract.single_paragraph` (要修正)・★ `lint.unstructured_abstract` (要修正。`**Background:** …` のような見出しつきの形)・★ `abstract.floats_allowed: false` (参考)・手で書いた番号の引用 `[2]` (参考)。語数は英数字を含む語と空白区切りの 2 つの数え方の大きいほうで判定する | 規定チェック |
| キーワード 5 語・題の語を繰り返さない | §3.1 | 語数の上限は共通の検査。★ `lint.keywords_not_in_title` (要修正。キーワードの語のどれかが題の語と同じなら。大文字小文字・複数形・ハイフンでつないだ語の各部分を同一視し、冠詞・前置詞・接続詞と `non-` などの接頭辞は除く) | 規定チェック |
| running title (題 > 50 字なら 50 字以内) | §3.1 | ★ `limits.running_title_chars: 50` (要修正 2 種。字数は行内の記法を落とした空白込みの長さ) | 規定チェック |
| 姓の大文字・所属の上付きの数字 | §3.1 | ★ `lint.author_surname_caps` (要修正。学位・敬称と `Jr.` / `II` などは判定から除き、学位・敬称は参考で知らせる)・★ `lint.affiliation_superscript` (参考) | 規定チェック |
| 題の略語・シリーズ番号 | §3.1 | ★ `lint.title_conventions` (参考) | 規定チェック |
| 必須の要素 (序論・方法・結果・考察の節・利益相反・文献、題のある図表) | §3・§3.3 | ★ `sections.required` / `sections.aliases` (要修正。最上位の見出しを語の境界で照合)・★ `lint.float_titles` (要修正) | 規定チェック |
| 利益相反の定型文・倫理の節・AI の開示の置き場所・資金と助成番号・略語の定義・図表の題の大文字・引けない文献 | §3.2・§3.3・§4・§5 | ★ `lint.coi_section` + `coi_standard_sentence`・`ethics_section`・`ai_disclosure_section`・`funding_section`・`abbreviation_definitions`・`caption_minimal_caps`・`uncitable_references` (どれも参考。語の有無から推し量る) | 規定チェック |
| 補足資料 1 ファイル 50 MB・合計 50 MB・アーカイブなし | §6.2・§6.4 | ★ `limits.supplementary_file_mb` / `supplementary_total_mb` (要修正。10 進のバイトで比べる)・★ `lint.supplementary_archives` (参考。拡張子で見る)。`SUBMISSION.md` にも容量の行 | 規定チェック・`SUBMISSION.md` |
| 図を本文に埋め込んだまま提出する・本文と書式の PDF | §5・§6.1 | ★ `figures.separate: false` (§14.1)・★ `submission.collect_forms`・roundtrip。本文と書式は結合しない (§6.1) | §6.5 |
| 提出物の一覧 | §6.2 | `SUBMISSION.md` (§6.5) | — |
| 改訂稿と回答書・差分 | §7 | 差分 docx に build と同じ後処理が掛かる。回答書の見出しの番号は ★ `headings.numbered_scope: manuscript` で外す | `bash scripts/check-diff.sh`・Word (§11.5) |
| reference.docx に無い custom-style | — | pandoc は reference.docx に無い custom-style の段落スタイルを `basedOn="BodyText"` で自動定義するが、テンプレートの Body Text の ID は `a0` なので基が無く、Word では 10 pt で描かれる。本テンプレートの記法の custom-style は reference.docx に足してあり、原稿が新しい custom-style を使えば規定チェックが参考で知らせる | 規定チェック |

規定チェックの回帰試験は `main/step05_package/test_validate_abe.py` (132 件)、差分エンジンの受入テストは `bash scripts/check-diff.sh`
(学会テンプレートがあれば `_default` と `abe` で 110 項目)。

---

## 11. 学会テンプレートを pandoc で使うときの観察と、Word で確かめた形

学会テンプレートを pandoc 3.6.4 の `--reference-doc` に渡した出力の OOXML を読み、さらに Word (Microsoft 365) に PDF 化させて計測した。
「Word で確かめた」は roundtrip ([`docs/roundtrip-windows-watcher.md`](roundtrip-windows-watcher.md)) で Word に PDF 化させた結果である。
PDF の座標は左上が原点の mm。PDF の文字の大きさは 10.5 pt が 10.6 と出る。

### 11.1 観察と含意

| 観察 | 結果 (OOXML) | Word で確かめたこと | 含意 (本テンプレートの実装) |
|------|-------------|--------------------|------|
| custom-style と見出しのスタイル | `Title`→`a7`、`Subtitle`→`af2`、`Author` / `Affiliation` / `NoNumberSectionHeader`→同名、見出し 1/2→`1`/`2`、本文→`a0` | テンプレートの書体で描かれる (題 Arial 太字 16 pt、running title Arial 太字 14 pt、見出し 1 Arial 太字 12 pt 中央、本文 Times New Roman 10.5 pt・字下げ 1 字) | **pandoc は名前で引いて ID をテンプレートのものにする**。英語名のスタイルを持つテンプレートなら名前の対応表は要らない |
| pandoc 固有のスタイル | `FirstParagraph` / `Compact` / `CaptionedFigure` / `ImageCaption` / `TableCaption` / `Bibliography` は ID だけが書かれ、styles.xml に定義が無い。文字スタイル `Hyperlink` と表スタイル `Table` も無い。pandoc が custom-style のために自動で足す段落スタイル (`Abstract` / `Keywords`) は `basedOn="BodyText"` で、雛形に無い ID を指す | 未定義の段落は Normal として描かれ、1 段落目の字下げなし・図表の題が太字でない・文献にぶら下げなし。**抄録とキーワードは 10 pt** (基のスタイルが無いので文書の既定の大きさになる) | **別名スタイルを足す** (§11.3)。build と diff が使う custom-style は全部 reference.docx に足す |
| settings.xml | テンプレートの `word/settings.xml` がそのまま出力に移る (自動ハイフネーションが有効・`w:docVars`・文書 ID・`w:rsid`) | 自動ハイフネーションは効く。切ると両端揃えの語間が広がる (2.5 mm を超える語間のある行が約 4 倍)。題も語の途中で切られる → Title / Subtitle に `w:suppressAutoHyphens` を足すと切れない。Title は Normal から両端揃えを継承するので、長い題の 1 行目の語間が約 5 mm に広がる | **自動ハイフネーションは残し**、Title / Subtitle に `suppressAutoHyphens` を足す。題の揃えはテンプレートのまま (両端揃え。テンプレートで書くほかの著者の原稿と同じ見え方で、受理後は誌が組み直す)。識別子は reference.docx を作るときに消す (§8.4) |
| 見出しの自動番号 | テンプレートの番号定義 (`%1.` / `%1.%2` / `%1.%2.%3`) が残り、pandoc の定義が足される | `1. Introduction` (番号の後は空白)、`2.2` + タブ + 本文、`2.2.1` が出る。**ただし小節の番号が節で戻らない** (`3. Results` の下が `3.5`)。番号定義の小節の段の `lvlRestart w:val="0"` を外すと `3.1` に戻る。比べた形 (`--number-sections` + 雛形の番号を外す) は番号は正しいが `1<TAB>Introduction` (既定のタブで約 15 mm 空く・ピリオドなし) | **テンプレートの自動番号を使い**、`lvlRestart w:val="0"` を外す (§11.3) |
| `{.unnumbered}` の見出し | **番号つきの heading 1 のまま** | `6. Conflicts of interest` / `7. Acknowledgements` / `8. References` (番号つき・中央)。citeproc の後の Lua フィルタで NoNumberSectionHeader の段落にすると、番号なし・Arial 太字 11 pt・左。citeproc が足す References の見出しも同じく変わる | ★ `headings.unnumbered_style`。**フィルタは citeproc の後に掛ける** |
| 図表の題 | `Figure 1: …` / `Table 1: …` (pandoc-crossref の既定) | 2 つ目の `--defaults` で `figureTitle: "Fig."`・`titleDelim: ""` にすると `Fig. 1 Mean score …` / `Table 1 Mean score …` (空白 1 個)。題全体が太字 (caption) | ★ `crossref` |
| 本文の相互参照 | `Fig. 1` | `Fig. 1`・`Table 2`・`Eq. 1`。別名の `Hyperlink` を書式なしで定義すると地の文と同じ黒。**原稿に `Eq. [@eq:x]` と書くと `Eq. Eq. 2` と接頭辞が二重になる** | 骨格と手引きで「`[@eq:x]` だけを書く」と案内する |
| 節 (`sectPr`) | 出力の最終の `sectPr` は**テンプレートの節 1 (表題部: 1 段組・行番号なし・ヘッダ参照あり) と同じ値**。節 2 の 2 段組と行番号は出力に無い。**pandoc は雛形の本文で最初に現れる sectPr を写す**ので、雛形から本文を全部消して最終の sectPr (節 2) だけを残すと、出力は 2 段組になるが柱とフッタの参照が無くなる | 後処理で組み立てると (§11.3) テンプレートどおり: 1 ページ目は表題部だけ、2 ページ目から 2 段組・行番号。改ページの段落 → 節 1 の空の段落 (テンプレートの並び) と、改ページの段落を置かず本文の節を `nextPage` にした形は全ページ同じ。改ページを置かないと本文が 1 ページ目の途中から始まる | **2 段組と行番号は後処理で組み立てる** (★ `layout`)。雛形の本文は骨組みだけ残す (§8.4) |
| ヘッダ・フッタ | テンプレートのものが引き継がれ、柱は `Template for ABE` のまま | 左 `distributed`・中央 `Template for ABE`・右 `ver.3`。段落の書式を残して TAB + running title だけにすると、中央に running title (Times New Roman 太字斜体 9 pt、用紙の中央)。フッタは中央に `n/N` | ★ `header.*` |
| メタデータ | 出力の `core.xml` の作成者は空 | 雛形を骨組みにし、識別情報を消した reference.docx から組んだ出力は、テンプレートそのものから組んだ出力と全ページ同じ (語の位置まで) | テンプレートの作成者名は出力に移らない。reference.docx 自体からは消す (§8.4) |

### 11.2 Word で計測した値 (表題ページ・段・行番号・段抜き)

本実装の出力 (動作例 `data/dummy/abe` と、確かめるために組んだ試験用の原稿) を Word で PDF にして計測した値:

- **用紙・余白**: 210.0 × 297.0。本文の 1 行目の上端 25.6 (余白 25.0)、最終行の下端 ≤ 275.3 (余白 20.0 → 277.0)。柱の文字の上端 16.1、フッタ `n/N` の文字の上端 275.8
- **段**: 左の段 15.0〜98.4、右の段 111.7〜195.0、**段間 13.3・段の幅 83.35**。本文の行は Body Text の右字下げ −0.45 字 (`w:rightChars="-45"`) で段の右端から 1.7 出る
  (左の段の行は 〜100.1、右は 〜196.8)。テンプレートの設計どおり
- **行送り**: 本文 4.3 (≒ 12.2 pt。Normal の最小 12 pt)
- **表題ページ**: 1 ページ目は Title (16 pt) → Author (10.5 pt、上付き 7 pt) → Affiliation → Subtitle (14 pt) → Received / Revised → Abstract の見出し (11 pt) →
  抄録 (字下げ 1 字) → Keywords で終わり、行番号なし。本文は 2 ページ目の上端から 2 段組で始まる
- **行番号**: 8 pt。**段ごとには戻らず、各ページで左の段の上から 1 で始まり右の段へ続けて数え、ページで 1 に戻る**。表題ページ・図表の題 (caption の行番号抑止)・
  表のセルには打たれない。位置は左の段が右端 x 11.8 (段から 3.2)、右の段が段間の中 x 108.5。**1 段組の節では既定の位置が x 8.7 (段から 6.3) にずれる**
  (`w:distance` を省いた既定が段数で違う) → 段抜きの節に `w:distance="180"` を足すと 11.8 にそろう
- **見出し**: `1. Introduction` は段の中央、`2.2` の後の本文は 10 mm 右 (番号定義のぶら下げ 567 twip)
- **脚注**: 段の幅 (参照のある段の下)、8 pt、番号は上付きの数字
- **図**: 段に収まる図 (80 mm) は段の中央、題は直下。**本文幅の図 (160 mm) を段にそのまま置くと用紙の外まではみ出す** → 後処理が段の幅に縮める
  (縮めた図は右の段の x 111.9〜194.8・幅 83.0 mm。図の中の文字は 52 % に縮む。build が警告し `{.wide}` を案内する)
- **広い表** (9 列・数字 6〜7 字): 段の中では Word が段の幅に押し込み、**数字がセルの中で折り返して読めない** (`81.` / `250` に割れる)。段抜きの節では折り返さない
  (build の見積もりは最小幅 125.2 mm・Word の実測は 124.2 mm)
- **段抜き** (図の `{.wide}`・表の `::: wide`): 区切りの直前の 2 段は高さがそろう。図は本文幅の中央 (x 25.4〜184.7)、題は図の直下に本文幅で左揃え。
  表は本文幅 x 15.0〜195.1 で数字の折り返しなし。行番号はページの中で通しで続き、1 段組の節の図の行と凡例にも打たれる
- **範囲が表で終わる段抜き**: 表の直後に区切りだけの空の段落を足す。この段落は**行番号なし・ふつうの高さ**にした — 何も付けないと空行に行番号が 1 つ付き、
  高さを 1 pt に詰めると、続く 2 段組の節がページの末尾で左の段に 2 行だけ入り、右の段を空けたまま次のページへ送られるため
- **題と図・題と表の分かれ**: 起きない (別名の CaptionedFigure と TableCaption に `keepNext`)

### 11.3 採用した OOXML の形

本実装の後処理が書く形 (Word で確かめた形)。`r:id` の値・スタイルの ID (`a0` / `ae` / `a` / `a1` / `a2` / `Reference`) は出力ごと・テンプレートごとに違いうるので、
コードは**名前から引いた ID** で書く。`w:rsid*` は除いて写した。

**節の区切り** (`main/step02_build/layout.py`。★ `layout`) — Keywords の段落の直後に 2 段落を置く。節 1 の sectPr は pandoc が出力の最終に写したもの (柱とフッタの参照つき) を移す:

```xml
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
<w:p><w:pPr><w:sectPr><w:headerReference r:id="rId9" w:type="default"/><w:footerReference r:id="rId10" w:type="default"/><w:pgSz w:code="9" w:h="16838" w:w="11906"/><w:pgMar w:bottom="1134" w:footer="992" w:gutter="0" w:header="851" w:left="851" w:right="851" w:top="1418"/><w:cols w:space="425"/><w:docGrid w:linePitch="286" w:type="lines"/></w:sectPr></w:pPr></w:p>
```

**文書末の sectPr** (本文の節。テンプレートの節 2 と同じ値) — 柱とフッタの参照は持たない (節 1 から引き継ぐ):

```xml
<w:sectPr><w:type w:val="continuous"/><w:pgSz w:w="11906" w:h="16838" w:code="9"/><w:pgMar w:top="1418" w:right="851" w:bottom="1134" w:left="851" w:header="851" w:footer="992" w:gutter="0"/><w:lnNumType w:countBy="1"/><w:cols w:num="2" w:space="754"/><w:docGrid w:type="linesAndChars" w:linePitch="286"/></w:sectPr>
```

**段抜き** — 区切りは既存の段落に持たせる。前: 段抜きの図表の直前の本文段落の `w:pPr` に、上の本文の節と同じ sectPr (2 段組)。
後: 図題の段落 (表なら表の直後に置く空の段落) の `w:pPr` に 1 段組の sectPr。1 段組の sectPr は本文の節の写しで、`w:cols` を 1 段にし、行番号の位置をそろえる `w:distance="180"` を足す:

```xml
<w:p><w:pPr><w:pStyle w:val="ImageCaption"/><w:sectPr><w:type w:val="continuous"/><w:pgSz w:w="11906" w:h="16838" w:code="9"/><w:pgMar w:top="1418" w:right="851" w:bottom="1134" w:left="851" w:header="851" w:footer="992" w:gutter="0"/><w:lnNumType w:countBy="1" w:distance="180"/><w:cols w:space="425"/><w:docGrid w:type="linesAndChars" w:linePitch="286"/></w:sectPr></w:pPr>…</w:p>
<!-- 範囲が表で終わるときの表の直後の空の段落 (行番号なし・ふつうの高さ。§11.2) -->
<w:p><w:pPr><w:suppressLineNumbers/><w:sectPr>…(上と同じ 1 段組の sectPr)…</w:sectPr></w:pPr></w:p>
```

段抜きの範囲の**前**の区切りは直前の段落の `w:pPr` に持たせる。直前が段落でない (表の直後に段抜きが来る) ときだけ、上と同じ形の空の段落に 2 段組の sectPr を持たせて足す。
直前の段落がすでに節の区切りを持つ (表題部の節の段落・前の段抜きの範囲の最後) ときは足さない。表の凡例を表の前に動かす (`captions.py`) と範囲は表で終わり、
`layout.py` が表の直後に区切りだけの段落を足す。

**柱** (`word/header1.xml` の段落。`main/step02_build/frontmatter.py`。★ `header.*`) — 段落の書式 (header スタイル・斜体) を残し、`w:r` を `TAB` + running title の 1 つにする:

```xml
<w:p><w:pPr><w:pStyle w:val="a9"/><w:rPr><w:i/></w:rPr></w:pPr><w:r><w:rPr><w:i/></w:rPr><w:tab/><w:t>Quantifying the tremendous hunch</w:t></w:r></w:p>
```

**別名スタイル** (`word/styles.xml`。`main/00_setup/lib/patch_reference_docx.py --base`) — 基にするスタイルは名前から引いた ID (`a0` = Body Text、`a` = Normal、`ae` = caption、
`Reference`、`a1` = Default Paragraph Font、`a2` = Normal Table)。最初の 10 種は下のとおりで、ほかに build と diff が使う custom-style (`Author` / `Affiliation` /
`Legend` など) と pandoc が使うスタイルを足す (テンプレートに同名があれば足さない):

```xml
<w:style w:type="paragraph" w:customStyle="1" w:styleId="FirstParagraph"><w:name w:val="First Paragraph"/><w:basedOn w:val="a0"/><w:next w:val="a0"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="Compact"><w:name w:val="Compact"/><w:basedOn w:val="a"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="CaptionedFigure"><w:name w:val="Captioned Figure"/><w:basedOn w:val="a"/><w:qFormat/><w:pPr><w:keepNext/><w:jc w:val="center"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="ImageCaption"><w:name w:val="Image Caption"/><w:basedOn w:val="ae"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="TableCaption"><w:name w:val="Table Caption"/><w:basedOn w:val="ae"/><w:qFormat/><w:pPr><w:keepNext/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="Bibliography"><w:name w:val="Bibliography"/><w:basedOn w:val="Reference"/><w:qFormat/></w:style>
<w:style w:type="character" w:customStyle="1" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:basedOn w:val="a1"/><w:qFormat/></w:style>
<w:style w:type="table" w:customStyle="1" w:styleId="Table"><w:name w:val="Table"/><w:basedOn w:val="a2"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="Abstract"><w:name w:val="Abstract"/><w:basedOn w:val="a0"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="Keywords"><w:name w:val="Keywords"/><w:basedOn w:val="a"/><w:qFormat/></w:style>
```

Title と Subtitle の `w:pPr` には `<w:suppressAutoHyphens/>` を足す (`w:pPr` の子の順を守る。Title なら `w:suppressLineNumbers` の後・`w:spacing` の前)。
凡例のスタイル (`Legend`) は caption を基に太字を外したもの (題と同じく行番号が付かない)。

**見出しの番号定義** (`word/numbering.xml`) — heading 1 のスタイルが指す番号定義の小節の段 (ilvl 1) から `<w:lvlRestart w:val="0"/>` を外した形。
heading 1〜3 が同じ番号定義の ilvl 0〜2 でなければ警告する:

```xml
<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="2"/><w:lvlText w:val="%1.%2"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:hanging="567" w:left="567"/></w:pPr><w:rPr><w:rFonts w:hint="eastAsia"/></w:rPr></w:lvl>
```

**番号なしの見出し** — `{.unnumbered}` の見出しは NoNumberSectionHeader の段落になる (識別子はブックマークで残る。`unnumbered-style.lua`)。

**式** (`main/step02_build/equations.py`。★ `equations.style`) — pandoc-crossref の番号つきの式 (`m:oMathPara` の中に `\qquad (2)`) は番号が式のすぐ右に付いて式と一緒に
段の中央に寄る。テンプレートの見本の形にする: `m:oMathPara` をほどいて段落直下の `m:oMath` にし、式の中の番号の部分を外して `w:tab` + 番号の `w:r` を置く:

```xml
<w:p><w:pPr><w:pStyle w:val="Equation"/></w:pPr><w:bookmarkStart w:id="31" w:name="eq:err"/><m:oMath>…(式)…</m:oMath><w:r><w:tab/></w:r><w:r><w:t>(2)</w:t></w:r><w:bookmarkEnd w:id="31"/></w:p>
```

本文の節と段の幅の違う節 (段抜きの 1 段組の節・表題部の節・段組を組まない回答書とカバーレター) の式には、スタイルの右タブを消して段の幅の差だけずらした右タブを段落に置く
(本文幅 10 204 twip の節なら 4 678 + (10 204 − 4 725) = 10 157):

```xml
<w:pPr><w:pStyle w:val="Equation"/><w:tabs><w:tab w:val="clear" w:pos="4678"/><w:tab w:val="right" w:pos="10157"/></w:tabs></w:pPr>
```

**新住所の脚注の記号** (`frontmatter.py`。★ `title_page.author_footnote_marks`) — 著者 (custom-style `Author`) の段落の中の脚注の参照を Word が記号の脚注に書く形
`<w:footnoteReference w:customMarkFollows="1"/><w:t>*</w:t>` にし、脚注の側の番号 (`w:footnoteRef`) を記号の文字にする。記号は参照の順。
文面の同じ脚注は先と同じ記号にし、後の参照は記号の文字だけにして脚注を消す。記号が足りなければ残りは数字のまま (警告)。

### 11.4 図表の題・凡例・式番号

動作例を Word で PDF にした値:

- **題**: `Fig. 1 Overview of …` (段抜き・図の直下)・`Fig. 2 …` (右の段・図の直下)・`Table 1 Mean score …` (右の段)・`Table 2 Inputs …` (段抜き)。
  どれも Times New Roman **太字** 10.5 pt・題の全体が太字 (caption)・番号の後は空白 1 個。本文の参照は `Fig. 1` / `Table 1` / `Eq. 1`
- **凡例**: 図は題の直下、**表は題の直下で表の上** (題 → 凡例 → 表)。凡例は Times New Roman の**太字でない** 10.5 pt。**題と凡例に行番号は付かない** (図の行には付く)。
  図と題・題と凡例・凡例と表はどれも同じ段・同じページ
- **凡例が 2 段落・凡例の無い図表**: 凡例 2 段落の図は題 → 凡例 2 段落、凡例の無い図は題の直後に本文。凡例 2 段落の表は題 → 凡例 2 段落 → 表。
  テキストボックスの中の表も題 → 凡例 → 表
- **式**: Equation スタイルで、番号 `(1)` / `(2)` は**段の右端** (左の段なら x 92.4〜97.6)、式は字下げ 1 字の x 18.8 から始まり、式の行に行番号が付く。
  段抜き (`::: wide`) の式の番号は本文幅の右端 (x 194.2)。番号の無い式は段の中央
- **分数は文中の式の大きさで描かれる** (分子・分母 7.6 pt)。テンプレートの見本の式と同じ形 (段落の中の `m:oMath`) なので Word は文中の式として描く

### 11.5 差分 docx と回答書

動作例を 10 か所書き換えた旧版 (表題の語・抄録の数・本文の語・表のセル・段抜きの図の題の語・文献の引用・段抜きの表とそれを紹介する段落・番号つきの式の係数・
文中の式の記号・図表の参照の行き先) と動作例との差分を Word で PDF にした値。色は削除 = `C00000` (取消線つき)・追加 = `2E74B5`:

| 文書 | ページ | 結果 |
|------|-------|------|
| 差分 docx | 本文と同じ 5 | **2 段組・ページごとの行番号・柱・フッタ `n/5`・表題ページの独立・段抜きの図と表は build と同じ**。表題の語 (Arial 太字 16 pt) も色が付く。**文中の式**: 旧の記号が赤の取消線 → 新が青。**番号つきの式**: 旧の式は赤の取消線で番号なし・段の中央、新の式は青で Equation の形 (番号 `(2)` は段の右端。番号にも差分の色)。**表のセル**: `1.1` (赤の取消線) と `1.2` (青) が 1 行に並ぶ。**参照**: `Table 1` が赤の取消線・`Fig. 2` が青 (リンクの色ではなく差分の色)。**足した段抜きの表**: 題は `Table 2` (番号が付く)・凡例と表の全セルと表を紹介する段落が青。文献の引用 `[2]` が赤の取消線 → `[3]` が青。`Undefined cross-reference` は 0 件 |
| 回答書 (`revise-report.docx`) | 1 | 1 段組・行番号なし・柱は空・フッタ `1/1`。**見出しに番号が付かない** (`Response to Reviewers` / `Reviewer 1` / `Reviewer 2`。heading 1 / 2 のスタイル (Arial 太字・heading 1 は中央) のまま)。査読コメントは Block Text の斜体 |
| カバーレター | 1 | 1 段組・行番号なし・柱は空・フッタ `1/1` |

差分の残る制限は §13 と [`docs/design-fullarea-diff.md`](design-fullarea-diff.md) §7。

### 11.6 新住所の脚注の記号

原稿の著者行だけを変えて Word で PDF にした値:

| 原稿の著者行 | Word の著者行 (上付き) | 1 ページ目の下の脚注 | 本文の脚注 |
|------------|----------------------|-------------------|---------------|
| 1 人に `^[Present address: …]` (動作例) | `CHOKKAN²*` | `*` Present address: … (表題ページは 1 段組なので用紙の左から) | **`1`** |
| 2 人に別々の脚注 | `CHOKKAN²*`・`DAN¹**` | `*` / `**` の 2 つ | **`1`** |
| 同じ脚注 `[^a]` を 2 人で参照・別の 1 人に `[^b]` | `YOKAN¹*`・`CHOKKAN²**`・`DAN¹*` | `*` / `**` の **2 つ** (同じ文面はまとまる) | **`1`** |
| 5 人に別々の脚注 (記号は 4 つ) | `¹*`・`²**`・`¹***`・`¹****`・`²1` | `*`〜`****` と数字の **`1`** | **`2`** |

- 記号は著者行で 7.0 pt (所属の番号と同じ上付き)、脚注の行頭で 5.0 pt。**記号の脚注は Word の自動番号を消費しない** — 本文の脚注は記号の脚注の後でも `1` から。
  記号が足りずに数字のまま残った著者の脚注があれば、それが `1` で本文の脚注が `2` になる
- LibreOffice (`soffice --headless`) は 2 文字以上の記号を二重に描く (`**` が `****`)。Word では二重にならない (LibreOffice は読み込みの確認にしか使わない)
- **差分 docx**: 削除した脚注は旧版の並びの記号、変わらない脚注と追加した脚注は新版の並びの記号で出る。脚注を書き換えると、旧の脚注 (赤の取消線) と
  新の脚注 (青) が記号・番号ごと 2 つ並ぶ。脚注の番号と記号と本文の間の空白は色を持たない

### 11.7 通し検証の実測値

動作例 `data/dummy/abe` で build → diff → package (final) → roundtrip を通し、Word の PDF を計測した値 (「こう出れば正常」の基準。投稿前チェックリストの付録と同じ):

| 項目 | 規定・テンプレート | 実測 (提出用 `manuscript.pdf`。草稿の `main.pdf` と同じ) |
|------|------------------|---------------------------------------------------------|
| 用紙・ページ数 | A4 | 210.0 × 297.0・**5 ページ**。フォントはすべて埋め込み (Times New Roman・Arial・Cambria Math のサブセット)・ラスタ画像 0・文書の情報に作成者名なし |
| 余白 | 上 25 / 下 20 / 左右 15 mm | 本文の上端 y 25.5〜25.9・最下行の下端 ≤ 275.3 (277.0 まで)・左端 x 15.0・柱の上端 y 16.1・フッタ y 275.8 |
| 段 | 段の幅 83.3・段間 13.3 | 左の段 x 15.0〜・右の段 x 111.7〜 (段間 13.3)。行の右端は左 100.1・右 196.8 (§11.2) |
| 表題ページの独立 | 1 ページ目は題〜Keywords | 1 ページ目は Keywords で終わり**行番号なし**。2 ページ目の上端から 2 段組 |
| 表題ページの要素 | §3.1 | 題 Arial 太字 16 pt (2 行。1 行目は両端揃え) → 著者 10.5 pt (上付きの番号 7 pt) → 所属 (番号 x 15.0・本文 x 20.0) → running title Arial 太字 14 pt → Received / Revised → `Abstract` Arial 太字 11 pt → 抄録 1 段落 (1 行目 x 18.8) → Keywords |
| 本文 | Times New Roman 10.5 pt | Times New Roman 10.5 pt・行送り 4.3 mm・段落の字下げ 1 字 |
| 見出し | Arial・自動番号 | `1.`〜`5.` Arial 太字 12 pt・段の中央 / `2.1`〜`2.6`・`3.1`〜`3.4` 11 pt・左 / `2.2.1`・`2.2.2` 10.5 pt。`3. Results` の下は `3.1` から |
| 番号なしの節 | NoNumberSectionHeader | `Abstract`・`Conflicts of interest` / `Ethics declaration` / `Acknowledgements` / `References` は Arial 太字 11 pt・番号なし・左 |
| 行番号 | 本文の節だけ・ページごと | 8 pt。p1 なし・p2 1〜68・p3 1〜78・p4 1〜79・p5 1〜30 (欠番・重複なし)。左の段 → 右の段 → (段抜きの行) と通しで数え、ページで 1 に戻る |
| 柱 | running title | 全ページ `Quantifying the tremendous hunch` (Times New Roman 太字斜体 9 pt・用紙の中央) |
| ページ番号 | `n/N` | 全ページ `1/5`〜`5/5` |
| 図題 `Fig.` (図の下) | §5 | 段抜きの `Fig. 1` は図 x 25.4〜184.7 (幅 159.3)、題は直下 (Times 太字)・凡例はその下 (太字でない)。段の `Fig. 2` は右の段 x 113.6〜193.1・題は直下 |
| 表題 `Table` (表の上) | §5 | 段の `Table 1` は題 → 凡例 → 表 (三本線)。段抜きの `Table 2` は題 → 凡例 → 表 x 15.0〜195.1 (幅 180.0。数字の折り返しなし) |
| 段抜きの直前の 2 段 | — | `Table 2` の直前の 2 段組は左 7 行・右 8 行でほぼそろう (段落の切れ目しだいで、短い 2 段組は高さがそろわないことがある) |
| 式 | 番号は段の右端 | `(1)` / `(2)` は x 92.4〜97.6・式は x 18.8 から。分数の分子・分母は 7.6 pt (§11.4) |
| 脚注 | 上付きの数字・ページの下 | 左の段の下・8 pt。番号は `1` から (表題ページの記号の脚注は番号を消費しない。§11.6) |
| 文献 | 角括弧・巻の太字・エンダッシュ | 見出し Arial 太字 11 pt。`[1]`〜`[3]` は番号 x 15.0〜19.4・1 行目の本文の頭と続きの行 x 22.5 (= 段の左 + 7.5 mm)。巻は Times 太字。ページ範囲は U+2013 |

- **引用のフィクスチャ** (`data/dummy/abe-csl`。公式例 6 件 + 本テンプレートの判断 4 件): 巻の太字は雑誌論文の 2 件だけで、公式例 4 の `Vol. 2` は太字でない (規定 PDF と同じ)。
  ページ範囲の区切りはすべて U+2013。`[1]`〜`[10]` の 1 行目の本文の頭は段の左 + 7.5 mm にそろい (★ `bibliography.label_separator: tab`)、続きの行もすべて + 7.5 mm。
  `[2]` は Word が両端揃えで語間を詰めた行で、タブも詰まって本文の頭が + 6.6 mm に出る (本テンプレートの処理ではなく Word の行の詰め方)
- **文献 120 件の試験用の原稿**: `[1]`〜`[99]` は 1 行目の本文の頭が段の左 + 7.5 mm にそろう。`[100]`〜`[120]` は番号の幅が 8.1 mm (`[10]`〜`[99]` は 6.2 mm、`[1]`〜`[9]` は 4.4 mm) で、
  本文の頭は + 14.8〜14.9 mm に出る (§13)。続きの行はすべて + 7.5 mm
- **テキストボックスと段抜きの近接**: 段抜きの図の凡例の直後と段抜きの表の直前にテキストボックス (`page` を指定した表) を置いた原稿では、2 つとも指定のページと位置に置かれ、
  節の構成も崩れない (本文幅の凡例は箱を避けて折り返す)。ただし**図表の番号は原稿の順で付く**ので、箱の表の番号が紙面の順と食い違うことがある (置き場所を決めるのは執筆者)
- **そのほかの文書**: 差分は 5 ページで本文と同じ構成 (§11.5)。回答書とカバーレターは 1 ページ・1 段組・行番号なし・柱は空・フッタ `1/1`。
  ダミー書式 4 本は各 1 ページ (pandoc の既定で作ったので Letter 判。学会の書式なら学会の版面)

---

## 12. 規定に明記が無い点と、本テンプレートの判断

| 点 | 規定 | 本テンプレートの判断と理由 |
|----|------|--------------------------|
| 本文語数の数え方 | 何を数えるかは書かれていない | 本テンプレートの概算は**本文の節の段落の語**で、表題ページの段落と文献は概算に入らない。図表の題と凡例の語数は内訳として別に出す (事務局の数え方が違ったら足し戻せるように)。英数字を含む語で数える |
| 1 本の PDF | "should convert … into one PDF file" | 結合しない (§6.1)。別々のアップロードを受け付けるかは投稿画面で確かめる (§15) |
| 文献のページ範囲の字 | 規定 PDF は U+2012 | エンダッシュ (U+2013)。掲載論文の字 (§4) |
| 定型の記述の置き場所 | データの入手先と公開・臨床試験の登録・画像の加工・報告指針は置き場所が書かれていない | Materials and methods の末尾の小節 (§3.4) |
| running title と abbreviated title | 両方の語が出てくる | 1 行 (Subtitle の段落) で兼ね、柱にも使う (§9 の 5) |
| 節名の綴り | 規定の中でも揺れる | 骨格は英式 (`Acknowledgements`)。規定チェックは揺れを同一視する (§9 の 6) |
| Review Papers の節 | "All manuscripts must contain the essential elements" | 文言どおり、Review Papers でも Introduction / Materials and methods / Results / Discussion を必須の節として照合する。総説で節の立て方が違うなら、規定の要素を満たしているかを人が判断する |
| 表の凡例の位置 | 表の題とキャプションは表の上 | 原稿では凡例を表の後に書き (誌によらない書き方)、docx で題の後へ移す (§5) |
| 行番号 | 規定に要求は無い | テンプレートの本文の節の設定 (ページごと) をそのまま使う。回答書は改訂稿の PDF のページと行で位置を示す |
| 題の揃え | — | テンプレートのまま両端揃え (長い題の 1 行目の語間が広がる。§11.1) |
| 自動ハイフネーション | — | テンプレートのまま有効 (切ると語間が広がる。§11.1) |
| 段抜き | — | 図は `{.wide}`、表など任意のブロックは `::: wide` の Div。記法は誌によらず固定し、段組の無い誌では何もしない (同じ原稿を別の誌で組めるように) |
| AI の開示の「版」 | 版は求められていない | 骨格の文例は版も書く (実際に使ったものを書けるよう、作業記録を残す。`statements.md` の §4・§5) |
| カバーレター | 記述が無い | 任意の雛形を置く (§3.4)。要否は投稿画面で確かめる (§15) |

## 13. 既知の制限と確かめていないこと

**既知の制限**:

- **文献が 100 件を超えると `[100]` 以上の 1 行目の本文の頭がずれる** (段の左 + 14.8 mm。`[1]`〜`[99]` は 7.5 mm にそろう。§11.7)。
- **Word が両端揃えで語間を詰めた文献の行は、タブも詰まって本文の頭が少し手前に出る** (Word の行の詰め方。§11.7)。
- **差分**: 消した図表・式を参照する消した文の参照は `¿…?` (赤) になる。同じ図表・式とみなせないもの (画像のファイルもラベルも変えて題も同じでない図・
  ラベルも変えて大きく書き換えた式・題が似ていても中身の違う表に差し替えたもの) は削除 + 追加になり、消した文の旧ラベルの参照は `¿fig:old?` などになる。
  文の途中に書いた番号つきの式を書き換えると、新の式が後ろの文と同じ段落に出て式番号の右寄せが掛からないことがある (番号は付く。式を独立した段落に書けば起きない)。
  削除と追加の間に空白は入らない (`[2][3]`)。脚注の中だけの小さな変更も脚注まるごとの削除 + 追加になる。詳細は [`docs/design-fullarea-diff.md`](design-fullarea-diff.md) §7。
- **テキストボックス (`.textbox`) の位置の見積もりは 2 段組と表題ページで 1 ページずれうる**。`page` / `pos-y` は roundtrip の PDF を見て手で合わせる。
  図表の番号は原稿の順で付くので、置き場所によっては番号の順と紙面の順が食い違う (§11.7)。
- **段の幅に縮めた図の中の文字は小さくなる** (160 mm の図で 52 %)。build の警告が出たら `{.wide}` / `::: wide` にするか作図し直す。
- **分数・総和などは Word が文中の式の大きさで描く** (テンプレートの見本と同じ形。§11.4)。
- **凡例には行番号が付かない** (凡例のスタイルは caption を基にしている)。査読者は凡例の位置をページと図表の番号で示すことになる。
- **新住所の記号は 4 つ** (`*`〜`****`) まで。5 つ目からは数字のまま (build が警告する)。新住所を所属の Div に書くと脚注にならない。
- **学会テンプレートが改版されると後処理が外れうる**。指紋が違えば止まり (§0)、スタイルの欠け・見出しの自動番号の欠けは build・diff のたびに警告する。
  警告は止めないので、build の標準エラーに警告が出たら Word の PDF で確かめる。
- **規定チェックの参考情報は語の有無から推し量る** (題の略語・所属の上付き・利益相反の定型文・倫理の節・AI の開示の置き場所・資金・略語の定義・引けない文献・
  図表の題の大文字)。出なくても規定どおりとは限らず、誤検出もある。量の記号の斜体と、抄録が 4 要素 (課題・方法・主な結果・結論) を含むかは見ない。
- **段抜きの直前の短い 2 段組は高さがそろわないことがある** (Word が段落を分けずに右の段へ送る。§11.7)。

**確かめていないこと**:

- Editorial Manager の実際の画面 (アップロード種別・カバーレターの欄・差分 docx の扱い)。`SUBMISSION.md` は規定から作った一覧である (§15)。
- 受理後の制作で図の別ファイル (解像度・形式) を求められるか (§15)。
- Word 以外 (LibreOffice・Mac の Word・Word Online) での見え方。体裁の確かめは Windows の Word (Microsoft 365) の PDF で行っている。
- 掲載料の適用の開始日 (規定に書かれていない)。

## 14. `profile.yaml` の要点

実物は `data/journals/abe/profile.yaml` (コメントの「§N」は本書の節番号)。キーの一覧と既定は [`docs/profile-schema.md`](profile-schema.md)。
★ のキーはどれも省略可能で、既定では何もしない (ほかの誌の出力を変えない)。誌の ID で分岐するコードは無く、ABE 固有の動きはすべてこのキーで発火する。

| 群 | キー | 値と意味 |
|----|------|---------|
| 雛形 | `reference_doc` / ★ `reference_base` / ★ `reference_base_sha256` / ★ `reference_base_url` | `reference.docx` を `ABETemplate.docx` から作る。指紋が違えば止まる。無ければ取得元の案内を出して止まる (§0) |
| 体裁 (照合用) | `line_numbers: per-page` / `page_numbers: true` / `font` / `font_size: 10.5pt` / `margins: {top: 25mm, bottom: 20mm, left: 15mm, right: 15mm}` (★ 辞書形) / `paper_size: a4` / `line_numbers_scope: manuscript` | 焼き込まない。テンプレートの値を写してあり、reference.docx と食い違えば build が警告する (改版の検知)。行間 (最小 12 pt) は表せないので書かない |
| 段組 | ★ `layout` (`columns: 2` / `column_space: 13.3mm` / `title_block_until: Keywords` / `title_page_break: true` / `scope: manuscript`) | §11.3。段抜きの記法 (`{.wide}` / `::: wide`) は誌によらず固定 |
| 見出し | ★ `headings.unnumbered_style: NoNumberSectionHeader` / ★ `headings.numbered_scope: manuscript` | `{.unnumbered}` の写像 / 回答書とカバーレターの見出しの番号を外す |
| 柱 | ★ `header.running_title_from: Subtitle` / ★ `header.clear_template_labels: true` | §11.3 |
| 表題ページ | ★ `title_page.affiliation_label_tab: true` / ★ `title_page.author_footnote_marks: ["*", "**", "***", "****"]` | 所属の番号の後のタブ / 新住所の脚注の記号 |
| 題と式と文献 | ★ `crossref` (`figureTitle: "Fig."` / `tableTitle: "Table"` / `titleDelim: ""` / `figPrefix` / `tblPrefix`) / ★ `equations.style: Equation` / ★ `bibliography.label_separator: tab` / `csl: abe.csl` | §11.4・§4 |
| 図表 | `figures.embed: true` / ★ `figures.separate: false` / `figures.dpi: 300` / ★ `figures.keep_together: true` / `tables.placement: inline` / ★ `tables.legend_position: above` | §14.1。`dpi` は規定ではなく `check-figures.sh --journal abe` の目標 |
| 記事種別と上限 | `article_type: original` / `article_types` (4 種) / `limits` (`abstract_words: 350` / `keywords: 5` / ★ `running_title_chars: 50` / ★ `supplementary_file_mb: 50` / ★ `supplementary_total_mb: 50`) / `abstract` (`structured: false` / `citations_allowed: false` / ★ `single_paragraph: true` / ★ `floats_allowed: false`) / `blinded: false` | §2・§3.1・§6.2 |
| 節と検査 | ★ `sections.required` / ★ `sections.aliases` / ★ `lint.*` (§10) | 区分 (要修正 / 参考) は §10 |
| 提出物 | `submission.text_formats: [pdf]` / ★ `submission.collect_forms: true` / `submission.forms` (チェックリスト 8 項目) / `submission.supplementary` / ★ `submission.diff_note` | §6.5 |

`tables.legend_position: above` は `tables.placement: end` / `separate` と併用できない (提出構成の組み替えは凡例が表の後にある前提のため。build と package が止まる)。

### 14.1 図を本文に埋め込んだまま提出用にする — ★ `figures.separate` の設計

**問題**: package の「提出用」を「`--mode final` かつ `--keep-figures` なし」の 1 通りで表すと、それが次の 6 つを同時に決める:
(1) 図を本文から外して `[Figure N about here]` にし `figures/` に分離出力する / (2) 提出構成の組み替え (表の末尾移設・別ファイル化・図凡例の集約) /
(3) 図の形式の検査 / (4) 出所の照合の強さ (build と図の前処理が今と食い違えば止める) / (5) `SUBMISSION.md` の「⛔ 提出用ではない」・図の節・`CAPTIONS.md` /
(6) roundtrip が配送を止めるか。図を本文に埋め込む ABE で `--keep-figures` を使うと (1) は避けられるが、(4)〜(6) がすべて「提出用ではない」側に倒れる。

**設計**: package.py の判定を 2 つに分ける — **提出用か (`for_submission`)** = 「`--mode final` かつ `--keep-figures` なし」((4)〜(6) を決める) と、
**図を本文から外すか (`separate`)** = 「提出用 かつ `figures.separate`」((1)〜(3) を決める)。既定 (`separate: true`) の誌では 2 つが常に一致する。

| 項目 | `figures.separate: false` のときの動き |
|------|------|
| 最終モード | `main.docx` をそのまま `manuscript.docx` にする (図を外さない・relocate を通さない・`figures/` を作らない)。表の体裁の検査は読むだけで掛ける |
| 併用の禁止 | `tables.placement: end` / `separate`・`figures.legends_section` とは同時に指定できない (relocate を通さないので黙って効かなくなる)。profile を読むときに止まる (草稿でも) |
| 出所の照合 | 最終モードと同じく厳格 — build の出所と図の前処理の出所が今と食い違えば止める (埋め込んだ図がそのまま提出物の本文に入るため) |
| 図の形式 (`figures.formats`) | 使わない (形式の検査も主形式の解決もしない)。`--format` を付けると「使わない」と注意を出す |
| `SUBMISSION.md` | **提出用として書く** (⛔ を出さない)。図の節は「本文に埋め込み」、構成の行は `sections.required` と `tables.placement` から組む |
| `CAPTIONS.md` | 書かない (本文の題と凡例がそのまま提出物になる) |
| `--keep-figures` | 意味は同じ (「提出用ではない」パッケージを作る指定)。付けると、図の扱いは同じで提出用でなくなる旨を 1 行出す |
| roundtrip | `SUBMISSION.md` に ⛔ が無いので配送を止めない。`manuscript.docx` は Word で `manuscript.pdf` になる。`figures/` が無いのは正常 |
| 草稿モード | `true` のときと同じ (提出用ではない) |

補足資料の容量と記入済みの書式 (§6.5) は、`figures.separate` と別のキー (`limits.supplementary_*`・`submission.collect_forms`) で発火する。

## 15. 投稿画面・事務局で確かめないと決まらないこと

| # | 事項 | 確かめ方 | 本テンプレートの扱い |
|---|------|---------|------------------|
| 1 | Editorial Manager が本文と書式を別々のアップロードで受け付けるか (規定は 1 本の PDF にまとめるよう書く。§6.1) | 投稿画面のアップロード種別 | 結合しない。受け付けなければ PDF をつなぐ道具を足して `manuscript.pdf` と `forms/*.pdf` をつなぐ |
| 2 | COI 書式の PDF を本文と同じ PDF に入れるのか別か | 同上 | 著者ごとの PDF を別々に上げる |
| 3 | 英文校正の証明の提出場所 | 同上 | `forms/` に置けば PDF の一覧に載る (Submission Form は「添付した」かを確かめる。§6.4) |
| 4 | 語数に何を数えるか | 規定に書かれていない。必要なら事務局に確かめる | 本文の節だけを数え、外した凡例の語数を内訳に出す (§12) |
| 5 | 受理後に図の別ファイル (解像度・形式) を求められるか | 受理後に分かる | 図は SVG (か `.mmd`) が一次ソースなので、求められたら作り直せる (分離提出の形式は受理後の指示に合わせて profile に足す。ABE の profile は図の形式を持たない) |
| 6 | カバーレターの要否 | 投稿画面 | 骨格に任意の `cover-letter.md` (関連原稿の開示と非生成 AI の申告の置き場所。§3.4) |
| 7 | 差分 docx を回答書と一緒に上げるか | 投稿画面 | 規定に変更箇所の示し方の定めは無い (§7)。`SUBMISSION.md` に注記 (★ `submission.diff_note`) |

`SUBMISSION.md` のアップロード種別は**規定から作ったもの**で、画面と食い違ったら画面が優先する。そのときは `data/journals/abe/profile.yaml` の `submission` ブロックを直す。
