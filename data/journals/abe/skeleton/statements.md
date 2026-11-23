<!--
data/journals/abe/skeleton/statements.md — ABE の定型の記述の文例集

用途: 参照専用の【文例集】。ビルドの対象ではない (build.sh が読むのは main.md / revise-report.md / cover-letter.md の 3 つだけ)。
      骨格 main.md の該当する節・小節に、下の文例から当てはまるものを写して使う。

出典: Instructions to Authors (PDF、末尾の日付 1 April 2026) の該当の節。読み解きは docs/journal-abe.md の §1・§3・§5・§6。
      【規定の文】と書いたものは規定の文面のまま (規定の [ ] の記入欄だけを本テンプレートの記入欄 << >> に置き換えた)。
      【本テンプレートの文案】は規定の要求を満たすように書いた例なので、自分の研究の事実に合わせて必ず書き換える。

記入欄 `<<...>>` は書き換え忘れを規定チェック (validate.py) が要修正として出す。記入欄の中身はカンマか読点を含む形にしてある
(pandoc は `<<funder>>` のように HTML のタグとして読める記入欄を docx で消してしまう。骨格 main.md の冒頭のコメント)。
綴りは英式 (analysed など) で書いた。米式の原稿は直す (原稿の中で統一する)。
-->

# 定型の記述の文例集 (ABE)

## 0. 置き場所

ABE には定型の記述をまとめる節 (Declarations など) が無い。規定が置き場所を決めている記述はその節に、決めていない記述は
**Materials and methods の末尾の小節**に置くのを本テンプレートの既定にした。

| 記述 | 置き場所 (骨格 main.md) | 根拠 |
|------|------------------------|------|
| 利益相反 (§1) | `# Conflicts of interest {.unnumbered}` | 規定 ("in the 'Conflicts of Interest' section") |
| 倫理 (§2) | `# Ethics declaration {.unnumbered}` | 規定 (Manuscript Preparation の Ethics declaration) |
| 資金と謝辞 (§3) | `# Acknowledgements {.unnumbered}` | 規定 ("list all funding sources … in the Acknowledgements") |
| AI ツールの使用の開示 (§4) | Materials and methods の最後の小節 `## Use of artificial intelligence tools` | 規定 ("in the Methods section") |
| データと材料の入手先と公開 (§6) | Materials and methods の末尾の小節 `## Availability of data and materials` | 規定は "in their manuscript" で場所を決めていない → 本テンプレートの既定 |
| 臨床試験の登録 (§7) | Materials and methods (研究デザインの小節か末尾) | 規定は "Manuscripts … must include" で場所を決めていない → 同上 |
| 画像の加工 (§8) | Materials and methods (画像を扱う小節か末尾) | 規定は "clearly described in the manuscript" → 同上 |
| 報告指針 (§9) | Materials and methods (研究デザインの小節か末尾) | 規定は指針に従うことを求め、記述の場所を決めていない → 同上 |
| 転載の出典 (§10) | その図表の凡例 (`Legend` の Div) | 規定は原典を引くことを求める → 本テンプレートの既定 |

**Materials and methods にした理由** (本テンプレートの判断): (1) どれも研究の材料と方法の性質で、規定の Methods の要求
("sufficient detail to enable experiments or procedures to be repeated") と同じ向き。(2) AI ツールの開示 (規定が Methods と指定) と
近くに置くと、投稿前に見落としを確かめやすい。(3) 番号なしの後ろの節を足すと、学会テンプレートの節の並び (Conflicts of interest →
Ethics declaration → Acknowledgements → References) から外れる。研究デザインの小節など、内容の上でより近い小節があればそこに書いてよい
(規定チェックは置き場所を見ない — AI ツールの開示だけは Materials and methods の外にあると参考情報で知らせる)。

---

## 1. Conflicts of interest — 利益相反

**無い場合** 【規定の文】(一字一句このまま。規定チェックはこの文があるかを見る)

> The authors declare no conflicts of interest with any companies or commercial organizations per the definition of Japanese Society for Medical and Biological Engineering.

**ある場合** 【本テンプレートの文案】— 申告のある著者ごとに、関係する会社・団体と内容を書き、残りの著者は無い旨を書く

> <<著者名, A. YAMADA>> received <<講演料など, lecture fees>> from <<会社名, Company Name>>. <<著者名, B. SATO>> holds <<株式など, stock>> in <<会社名, Company Name>>. The other authors declare no conflicts of interest with any companies or commercial organizations per the definition of Japanese Society for Medical and Biological Engineering.

- 申告するかの判断は、学会の COI 開示書式の 9 項目 (役員・顧問の報酬 / 株式 / 特許使用料 / 講演料 / 原稿料 / 臨床研究費 /
  受託・共同・寄付の研究費 / 寄付講座への所属 / 研究と無関係の旅費・贈答。1 年間・1 団体あたりの金額の閾値は円) に合わせる
  (`docs/journal-abe.md` §6.3)。定型文の "per the definition of Japanese Society for Medical and Biological Engineering" はこの基準を指す。
- 別に **著者ごとに 1 通の COI 開示書式**を連絡著者がまとめて PDF で出す (提出物)。**本文の申告と書式の中身を食い違わせない**。
- 研究の資金そのものは §3 (Acknowledgements) に書く。資金提供者が利益相反に当たる関係 (顧問など) を持つなら、ここにも書く。

## 2. Ethics declaration — 倫理

人や動物を対象にした研究では倫理的な扱いの記述が要る ("must include statements concerning their ethical treatment and conduct")。
規定は例文を 3 つ示している。

**例文 1 — 人を対象にした研究** 【規定の文】

> This study was conducted in accordance with the ethical principles of the Helsinki Declaration, and after obtaining informed consent from each subject. The study was approved by the <<倫理委員会の正式名, ethics committee>> of <<所属機関の正式名, the affiliated institution>>.

**例文 2 — 動物実験** 【規定の文】

> This study was conducted in accordance with the Fundamental Guidelines for Proper Conduct of Animal Experiment and Related Activities in Academic Research Institutions. The study was approved by the <<動物実験委員会の正式名, ethics committee>> of <<所属機関の正式名, the affiliated institution>>.

**例文 3 — ヒトゲノム・遺伝子解析研究** 【規定の文】

> This study was conducted in accordance with the Ethical Guidelines for Human Genome/Gene Analysis Research by the Ministry of Education, Culture, Sports, Science and Technology; the Ministry of Health, Labour and Welfare; and the Ministry of Economy, Trade and Industry (Japan), and was approved by the <<倫理委員会の正式名, ethics committee>> of <<所属機関の正式名, the affiliated institution>>.

**書くときの注意**

- **承認番号**は規定の例文に無いが、書き足してよい (本テンプレートの上乗せ。例: `… of the University of X (approval number <<承認番号, 0000-000>>).`)。
  承認書 (証拠書類) を原稿とともに出すので、番号と委員会の正式名は承認書の字どおりにする。
- 人を対象にするなら、**研究への参加と結果の公表**についての同意の取り方を書く (規定 Animal/human experimentation の "describes the procedures for
  obtaining informed consent from participants regarding participation in the research and publication of the research")。同意を省略・免除した研究は、
  その理由と承認の内容を書く (本テンプレートの文案: `The requirement for informed consent was waived by the <<委員会名, committee>> because <<理由, the study used anonymised existing data>>, and an opt-out opportunity was provided.`)。
  **個人を特定できないようにする** ("Anonymity must be strictly maintained")。
- 動物実験は所属機関の承認した指針に加え、国内外の法令と指針に従うことを求められる (規定 Animal/human experimentation)。
- **例文 3 の指針は 2021 年に「人を対象とする生命科学・医学系研究に関する倫理指針」(Ethical Guidelines for Life Science and Medical Research
  Involving Human Subjects) に統合されている** (本テンプレートの注記)。いま承認を受ける研究は、承認書にある指針の名前で書く
  (例文 1 の形に、従った指針の名前を足す書き方もできる)。
- **倫理委員会の承認などの証拠書類を原稿とともに出す** ("must be supplied with the manuscript"。提出物)。
- 規定は、正式な承認を得ていても倫理の水準が保たれていなければ不採択にできるとしている。
- 人も動物も扱わない研究なら節ごと削る。

## 3. Acknowledgements — 謝辞と資金

**資金** — 規定は「**資金源をすべて Acknowledgements に、資金提供者と助成番号の両方を**書く」("For each funding source, both the research funder
and the grant number should be given")。

【本テンプレートの文案】

> This work was supported by <<資金提供者の正式名, funder>> (grant number <<助成番号, JP00X00000>>).

> This work was supported by JSPS KAKENHI Grant Numbers <<助成番号, JP00X00000>> and <<助成番号, JP00X00001>>, and by the <<財団の正式名, foundation>> (grant number <<助成番号, 0000-00>>).

- 科研費 (JSPS KAKENHI) は JSPS が案内する "This work was supported by JSPS KAKENHI Grant Number JP…" の形で書く (番号の `JP` を落とさない。
  最新の案内は JSPS の Web で確かめる)。ほかの資金配分機関にも指定の書き方があれば従う。
- 規定チェックは、資金らしき語が Acknowledgements 以外の節にだけある・Acknowledgements に助成番号らしき語が無い、を参考情報で知らせる。
- **資金が無い**なら書かなくてよい (規定に「資金が無い」旨の文の要求は無い)。

**謝辞** — 簡潔に ("This section should be brief")。著者の基準 (ICMJE の 4 基準) を満たさない貢献者への謝意はここに書く
(規定 Authorship: 満たさない人は "should be mentioned in the Acknowledgements section, not added as an author")。

> We thank <<氏名と所属, Hanako SUZUKI of the University of X>> for <<貢献の内容, technical assistance with the measurements>>.

- **AI ツールの開示はここに書かない** (ABE は Materials and methods。§4。Acknowledgments に開示する誌の原稿から写すときは動かす)。
- AI ツールは著者にできない。謝辞の対象 (人) でもない。

## 4. Materials and methods — AI ツールの使用の開示

**規定** ("Use of artificial intelligence tools"。`docs/journal-abe.md` §3.2):

- 生成・非生成を問わず AI ツール (LLM を含む) の使用を **Methods の節で開示し、詳しく記述する**。データの収集・解析、図や画像の作成・修正、
  原稿の全部または一部の執筆を含む。**どのツールを、どう使ったか**を書く。
- **生成 AI の使用は、研究デザイン・方法の不可欠な一部である場合に限って原則として認められ、それ以外は編集者が個別に判断する**。
- 綴り・文法の確認など、読みやすくするための**非生成 AI** の使用は認められるが、**投稿時に編集者へも申告する** ("should be declared to the editors
  upon submission"。cover letter か投稿画面。骨格の cover-letter.md に段落がある)。
- いずれの場合も、原稿の全内容の責任は著者にある。AI が生成した内容の著作権の扱いには議論があるので、転載の規定 (§10) と著作権法に従う。

**入れる要素**

| # | 要素 | 根拠 |
|---|------|------|
| 1 | ツールの名前と提供元 | 規定 "which tools were used" |
| 2 | **版** (モデルの識別子・アプリの版) | **本テンプレートの上乗せ** (規定は版を求めていない。同じ名前でも版で挙動が変わるので、版まで書いて特定する) |
| 3 | 使い方 — 何に・どう使ったか (データの収集・解析 / 図 / 執筆・翻訳・校正) | 規定 "how the tools were used" |
| 4 | 範囲 — 原稿・データ・図の**どの部分**に使ったか / 使っていないこと | 規定 "fully describe" (範囲が分からないと「どう使ったか」が伝わらない) |
| 5 | 出力を人が確かめた方法 | 本テンプレートの上乗せ (個別判断の材料になる) |
| 6 | 著者が全内容に責任を負う旨 | 規定 "authors remain responsible for all the contents" |

**(a) 非生成 AI だけを使った場合** 【本テンプレートの文案】

> No generative artificial intelligence (AI) tool was used in this study. The authors used <<ツール名, Tool Name>> (version <<版, 0.0>>, <<提供元, Provider>>, <<所在地, City, Country>>), a non-generative AI tool, only to check the spelling and grammar of the manuscript. The tool was not used to collect or analyse data, to produce or amend figures, or to write any part of the text, and the authors take full responsibility for the entire content of the manuscript.

- 生成か非生成かは**使った機能**で決まる。綴りの確認ツールでも、文を書き換えて提案する機能 (生成) を使ったなら (b) か (c) として書く。

**(b) 生成 AI が研究の方法の不可欠な一部である場合** (例: LLM でデータを分類した) 【本テンプレートの文案】

> As part of the method described in Section <<小節の番号, 2.3>>, <<モデル名, Model Name>> (<<モデルの識別子, model-id-0000>>, <<提供元, Provider>>; accessed through <<経路, the web API>> between <<期間, January and March 2027>>) was used to <<使途, classify free-text reports into four categories>>. The prompts and settings are given in Supplementary Material <<番号, 1>>, and the outputs were <<確かめ方, checked against manual labels by two authors>>. The authors take full responsibility for the entire content of the manuscript.

- 方法の詳しい記述 (プロンプト・設定・検証) は、それを使った方法の小節に書き、この小節には要約と参照を置く。

**(c) それ以外の生成 AI の使用** (例: 日本語の草案の英訳・文章の改善) — **編集者が個別に判断する**側 【本テンプレートの文案】

> The authors used <<ツール名, Tool Name>> (<<モデルの識別子, model-id-0000>>, <<提供元, Provider>>) to <<使途, translate the authors' Japanese draft into English and to suggest improvements to the wording of the Introduction and Discussion>>. The tool was not used to collect or analyse data, to produce or amend figures, or to generate the scientific content of the manuscript; all data, analyses, and conclusions are the authors' own. The authors reviewed and edited all output and take full responsibility for the entire content of the manuscript. <<英文校正, The final manuscript was edited by a professional English-editing service.>>

- **規定はこの使い方を原則として認めておらず、編集者の個別判断になる**。日本語の草案から英語の原稿を作る工程で生成 AI を使うなら、
  投稿の前に方針を決める — (1) 編集事務局に相談する、または (2) 生成 AI を使わない英語化
  (専門業者の翻訳・校正。英文校正の証明と兼ねられる) を確保する。
- **書かずに済ませるという選択肢は無い** (開示は must)。

**使っていない場合**: 小節ごと削る (使っていない旨を書く義務は規定に無い)。規定チェックは AI ツールの開示が見当たらないことを参考情報で知らせる。

## 5. 作業記録 — 使った AI ツールと版を残す

§4 の開示は**実際に使った道具と版**を書くので、執筆の間に記録を残し、投稿の直前に開示の文を記録から確定させる。

- 原稿と同じリポジトリの **git で追跡するファイル** (作業記録の Markdown ファイルなど) に書き足していく。git で追跡しない場所
  (`.gitignore` の対象の一時ファイルの置き場など) には置かない。
- **コミットのたびに退避・削除される一時ファイル (コミットメッセージの下書きなど) には書かない** — セッションをまたぐと記録が手元から消える。
- 査読コメントや事務局とのやりとりの中身は書かない (規定の通信の秘密)。

**残す項目** (1 回の使用ごとに 1 行)

| 列 | 中身 | 例 |
|----|------|----|
| 日付 | 使った日 | 2027-01-15 |
| ツール | 名前と提供元 | <<ツール名, Tool Name>> (<<提供元, Provider>>) |
| 版 | モデルの識別子・アプリの版 (画面や API の応答に出る字のまま) | <<model-id-0000, 版>> |
| 経路 | Web の画面 / API / エディタの拡張 など | API |
| 種類 | 生成 / 非生成 (使った機能で決める) | 生成 |
| 使途 | 翻訳・文章の改善・綴りの確認・コード・図・データの解析 など | 英訳 |
| 入力の範囲 | 渡した原稿の節・データ (個人情報・未公開のデータを渡していないこと) | Discussion の草案 |
| 出力の扱い | 採用 / 直して採用 / 不採用 | 直して採用 |
| 確かめた人 | 出力を確かめた著者 | <<イニシャル, T.Y.>> |

```markdown
| 日付 | ツール | 版 | 経路 | 種類 | 使途 | 入力の範囲 | 出力の扱い | 確かめた人 |
|------|--------|----|------|------|------|------------|------------|------------|
| 2027-01-15 | <<ツール名, Tool Name>> (<<提供元, Provider>>) | <<model-id-0000, 版>> | API | 生成 | 英訳 | Discussion の草案 | 直して採用 | <<イニシャル, T.Y.>> |
```

- 患者の情報や共同研究の契約で守られたデータを外部の AI サービスに渡すと、倫理審査の承認や契約に反しうる (本テンプレートの注意)。

## 6. Materials and methods — データと材料の入手先と公開

**規定** ("Availability of data and materials"):

- 公開のデータ・材料 (公共のリポジトリ・市販品) は、**入手先を受託番号 (accession number) か会社の情報**で原稿に書く。
- 自分のデータは補足資料に入れるか、分野で認められた公共のデータベース・リポジトリにリンクしてよい。**J-STAGE Data への登録を推奨** (無料。
  公開時に DOI が付く。登録の方法は学会の編集委員会が指定する)。
- **データ一式を査読中に編集者と査読者へ全量開示し、出版日までに公開する** (どちらも must)。出版日から **5 年以上**保存する。

【本テンプレートの文案】

**自分のデータを J-STAGE Data で公開する場合** (投稿の時点では DOI が無い)

> The data sets generated and analysed in this study will be made publicly available in J-STAGE Data by the date of publication. During peer review, the data sets are available to the editors and reviewers <<開示の方法, as Supplementary Material 1>>.

  → 受理後・校正の段階で DOI の形に直す: `The data sets … are available in J-STAGE Data (https://doi.org/<<DOI, 10.0000/…>>).`

**補足資料に入れる場合**

> The data sets supporting the conclusions of this study are included in Supplementary Material <<番号, 1>>.

**公開のデータを使った場合**

> The <<データセットの名前, Data Set Name>> data set was obtained from <<リポジトリ名, Repository Name>> (accession number <<受託番号, AB000000>>).

- 市販の試薬・装置の供給元は、方法の本文で `(型番, 会社名, 市, 国)` の形で書く (規定 Materials and methods)。
- **「要請に応じて提供する」(available on reasonable request) や「公開できない」は、出版日までの公開を must とする規定を満たさない**ので文例を置かない。
  倫理審査の承認・同意の範囲・共同研究の契約・所属のデータポリシーが公開を許さないなら、**投稿前に編集事務局に相談する**。
- 補足資料は 1 ファイル 50 MB・合計 50 MB 以下で、受理後は変えられない (規定チェックが容量を見る)。

## 7. Materials and methods — 臨床試験の登録

**規定** ("Clinical trial registration"): ICMJE と CONSORT に従い、臨床試験は最初の参加者の登録の時点かそれより前に公共の登録先に登録する。
**臨床試験を報告する原稿は、試験の登録番号と登録先の名前を書く** (must)。

【本テンプレートの文案】

> This trial was registered with <<登録先の名前, jRCT / UMIN-CTR / ClinicalTrials.gov>> (registration number <<登録番号, 000000>>) on <<登録日, 1 April 2027>>, before the enrolment of the first participant.

## 8. Materials and methods — 画像の加工

**規定** ("Image integrity"): 画像の加工は**最小限・画像全体に一様に・分野の基準の範囲内**で、**原稿に明記**する場合に限って認められる。
**画像の一部だけを移動・削除・追加・強調してはならない**。編集者は加工前の元画像を求めることがあり、出せなければ不採択・撤回になりうる。

【本テンプレートの文案】

> The brightness and contrast of <<対象の画像, the microscopy images in Fig. 2>> were adjusted with <<ソフトウェアと版, Software Name version 0.0 (Company, City, Country)>>; each adjustment was applied uniformly to the entire image and identically to all images that are compared. No part of any image was moved, removed, added, or enhanced individually.

- **元画像 (加工前のファイル) を残しておく** (求められたら出す)。
- 図の作成・修正に AI ツールを使ったなら §4 にも書く。

## 9. Materials and methods — 報告指針

**規定** ("Reporting guidelines"): 健康研究の報告は **EQUATOR Network の報告指針**に従う (ランダム化試験・観察研究・系統的レビュー・症例報告・質的研究・
診断と予後の研究・経済評価・動物の前臨床研究・研究計画書など)。**系統的レビューとメタ解析は PRISMA に従う** (must)。

【本テンプレートの文案】

> This study is reported in accordance with the <<指針の名前, STROBE>> guidelines [@<<文献キー, strobe>>].

- 研究の種類と代表的な指針 (EQUATOR Network の主な指針。本テンプレートの注記): ランダム化試験 CONSORT / 観察研究 STROBE / 系統的レビュー PRISMA /
  症例報告 CARE / 質的研究 SRQR・COREQ / 診断の精度 STARD / 予測モデル TRIPOD (TRIPOD+AI) / 経済評価 CHEERS / 動物実験 ARRIVE / 研究計画書 SPIRIT。
- 指針の文献を ref.bib に入れて `[@key]` で引く (文例の `[@<<文献キー, strobe>>]` は記入欄。ref.bib の文献のキーが strobe なら `[@strobe]` と書く)。

## 10. 図表の転載 — 出典と許諾

**規定** ("Reproducing copyrighted material"): 著者の著作権下にない素材は権利者の許諾を、既発表の素材は権利者と原著の出版社の許諾を得て、
**原典を原稿で引く**。**すべての許諾の写しを初回投稿時に原稿とともに出す**。Submission Form は、著者と JSMBE 以外が権利を持つ図を使うかと、
その図の番号を尋ねる (`docs/journal-abe.md` §6.4)。

【本テンプレートの文案】(その図表の凡例 = `Legend` の Div の最後に書く)

> Reproduced from [@<<文献キー, key>>] with permission from <<権利者, Publisher Name>>.

> Adapted from [@<<文献キー, key>>] with permission from <<権利者, Publisher Name>>.

- 改変した図も原典の許諾が要る。CC ライセンスの図はライセンスの条件 (表示・改変の可否) に従い、ライセンス名を書く。
- AI が生成した図や文章は著作権の扱いに議論があるので、この規定と著作権法に従う (規定 "Use of artificial intelligence tools")。
