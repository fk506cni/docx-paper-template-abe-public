# LaTeX の原稿を本テンプレートへ書き起こす (migration-latex.md)

LaTeX (IEEEtran などの 2 段組のクラス) で書いた原稿を、本テンプレートの Markdown に書き起こすときの対応表である。
投稿先は ABE (*Advanced Biomedical Engineering*) を例にするが、§1 と §4 は誌によらず使える (`_default` に出すときは
§2・§5 の ABE の規定の部分を読み飛ばす)。執筆の規約は [`CLAUDE.md`](../CLAUDE.md)、ABE の規定は
[`docs/journal-abe.md`](journal-abe.md)、投稿までの手順は [`docs/usage-guide.md`](usage-guide.md) §8 にある。

> **これは「機械変換の後始末」ではなく「書き起こし」の手引きである。** 元の原稿の内容を写して、同等の
> (同一ではない) 投稿原稿を新しく作る。**レイアウトの同等性は求めない** — 元のクラスの体裁・`.textbox` の絶対配置・
> 原稿に書いた段組の指示は引き継がず、**最初から本文の流れに図表を置き、本テンプレートの規約で書く**。
> ABE も 2 段組だが、表題ページを 1 段組にして本文を 2 段組にするのは誌のプロファイル (`profile.yaml` の `layout`) と後処理の
> 仕事で、原稿には段組を書かない (同じ原稿を `--journal _default` でも組めるようにするため)。
> 変換の補助スクリプトは用意していない。下の (a)〜(e) はどれも書き起こしの一部で、機械化しても目で見る作業が残る
> (とくに表は列の意味を見ないと直せない)。

下の例はすべて**架空の最小原稿** (IEEEtran の 2 段組。題・著者・抄録・キーワード・図 2 つ・表 2 つ・`\thanks{}` 2 つ) を
pandoc 3.6.4 (`docx-paper-template-pandoc` コンテナ) の `pandoc -f latex -t markdown` に通した、そのままの出力である。

---

## 0. 全体の流れ

```bash
# 0. 学会テンプレートを置き (ABE。最初に 1 回。docs/usage-guide.md §8.1)、骨格を写す (必須節の抜けが起きない)
#    ABETemplate.docx は学会サイトの Instructions to Authors のページから取って data/journals/abe/ に置く (git で追跡しない)
cp data/journals/abe/skeleton/main.md         src/main.md
cp data/journals/abe/skeleton/cover-letter.md src/cover-letter.md   # 任意
# 文例集: data/journals/abe/skeleton/statements.md (ビルドの対象外。利益相反・倫理・資金・AI ツールの開示などを書くときに見る)
rm -f .development

# 1. 下書きを得る (参考。そのままは使わない)。元の原稿はリポジトリの中 (コンテナから見える場所) に置く
docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
    pandoc -s -f latex -t markdown --wrap=none jank/orig/main.tex -o jank/draft.md

# 2. jank/draft.md を見ながら src/main.md の骨格を埋める (本文書 §1〜§5)

# 3. 図を置く (PDF はそのまま置いてよい。原稿からは .svg で参照する)
cp jank/orig/figs/*.pdf src/figs/

# 4. 回して直す
bash scripts/build.sh   --journal abe --article-type original
bash scripts/package.sh --journal abe --article-type original --mode final   # 最後に「規定チェック」が出る
bash scripts/check-figures.sh --journal abe
```

- コンテナはリポジトリのルートを `/workspace` として見るので、**元の原稿と下書きはリポジトリの中に置く**
  (`jank/` は git 管理の外で、コンテナからも見える)。
- **`-s` を付ける。** 付けないと、題・著者・抄録が下書きから**消える** (メタデータに入り、本文としては書き出されない)。
  `-s` を付けると YAML の前置きに出てくるので、それを骨格の `custom-style` の Div (Title / Author / Affiliation /
  Abstract) へ移す。**YAML のまま残さない** — YAML のメタデータは全領域差分の対象にならない (`CLAUDE.md` の
  「原稿執筆の規約」)。

```markdown
<!-- -s を付けたときの下書きの先頭 (抜粋) -->
---
abstract: |
  Ward messages were triaged by a rule-based classifier. We evaluated it on 240 messages from a fictional hospital [@doe2020].
author:
- Alex Example, Robin Sample, and Kim Placeholder [^1] [^2]
bibliography:
- ref.bib
title: Automated Triage of Ward Messages with a Rule-Based Classifier
---
```

`pandoc -f latex -t markdown` を通すと、**引用 (`\cite{key}` → `[@key]`、複数は `[@a; @b]`)・見出し・箇条書き・
イタリック・数式はそのまま使える**。使えないのは下の 5 種である。

---

## 1. pandoc の変換で使えない 5 種

### (a) 図の拡張子 — `.pdf` のままでは埋め込みが壊れる

```markdown
<!-- pandoc の出力 (使えない) -->
![Workflow of the triage classifier. Messages are split into sentences, …](figs/fig_workflow.pdf){#fig:workflow width="\\columnwidth"}

<!-- 本テンプレートの書き方 -->
![Workflow of the message triage classifier.](figs/fig_workflow.svg){#fig:workflow}
```

**PDF の図もファイルは `figs/*.pdf` のまま置き、原稿からは `.svg` で参照する。** 図の前処理 (step01) が pdf2svg で
SVG に変換し、SVG のネイティブ埋め込みと PNG フォールバックの経路に載せるためである。`.pdf` で参照すると埋め込みが
壊れるので、ビルドがエラーで止める。

### (b) 無効な属性 — `width="\columnwidth"` / `width="86%"`

pandoc は LaTeX の長さをそのまま属性に残す (`\includegraphics[width=0.86\linewidth]` は `width="86%"` になる)。
**消す**か、見た目を保ちたいときだけ `{width=80mm}` のように**実寸で置き換える**。`width="\\columnwidth"` は docx にするときに
**黙って無視され** (警告は出ない)、図は公称サイズ (SVG ルートの `width` / `height`) で置かれる。原稿に意味の無い指定が残るので消しておく。

段の幅で置きたいなら、指定ではなく**図そのものの公称サイズ**で決める。ABE の段の幅は 83 mm、本文幅は 180 mm なので、
段に置く図は SVG の幅を 83 mm 以下の物理単位で、段抜きの図は 180 mm 以下で作る (§5.5)。段抜きにしない図が段の幅を
超えると、build が段の幅に縮めて警告する (図の中の文字も一緒に縮む)。

### (c) 相互参照 — 番号が固定される

```markdown
<!-- pandoc の出力 (使えない。番号 1 が本文に焼き付いている) -->
Fig. [1](#fig:workflow){reference-type="ref" reference="fig:workflow"}

<!-- 本テンプレートの書き方 -->
[@fig:workflow]
```

そのままだと **pandoc-crossref の初出順の採番が効かない**。ABE の本文と題の `Fig. 1` / `Table 1` / 式の番号も crossref が
振るので、`Fig. [@fig:workflow]` とも書かない (`Fig. Fig. 1` と二重になる)。参照は `[@fig:x]` / `[@tbl:x]` / `[@eq:x]` だけを書く。

### (d) 表 — 名前の付いた Div + simple table + `tab:` 接頭辞

```markdown
<!-- pandoc の出力 (使えない。\begin{center} で囲んだ表) -->
:::: center
::: {#tab:messages}
  **Feature**                     **Value**
  --------------------------- -------------
  Length (words), mean (SD)     41.3 (12.6)
  Sender, n (%)
  Nurse                         151 (62.9%)
  Physician                      89 (37.1%)

  : Message Set Used for Evaluation (n = 240)
:::
::::

<!-- 本テンプレートの書き方 (pipe table + 題はキャプションの記法、凡例は直後の Legend Div) -->
: Features of the 240 messages used for evaluation. {#tbl:messages}

| Feature                   | Value       |
|:--------------------------|------------:|
| Length (words), mean (SD) | 41.3 (12.6) |
| Sender: nurse, n (%)      | 151 (62.9%) |
| Sender: physician, n (%)  |  89 (37.1%) |

::: {custom-style="Legend" for="tbl:messages"}
Percentages are column proportions of the 240 messages. SD, standard deviation.
:::
```

- **識別子の接頭辞を `tab:` から `tbl:` に変える。** `tab:` では pandoc-crossref が解決しない。
- 題と凡例は `CLAUDE.md` の「図表の題と凡例の書き分け」に従って分ける (題 = キャプション / 凡例 = 直後の
  `custom-style="Legend"` の Div。**表の凡例も原稿では表の後に書く**。ABE では docx で後処理が題と表の間へ移す)。
  ABE の題とキャプションは**最小限の大文字** (文頭と固有名詞だけ) で、**本文を読まずに理解できるように完結させる**。
  IEEE 系の Title Case の題 (`Message Set Used for Evaluation`) はセンテンスケースに直す。
- `\begin{center}` は `:::: center`、2 段抜きの `\begin{table*}` は `::: table*`、IEEEtran のキーワードは
  `::: IEEEkeywords` のように、**名前の付いた Div** に包まれて出てくる。どれも **Div を外して、中身を本テンプレートの
  記法に書き直す** (キーワードは `custom-style="Keywords"` の Div へ)。
- **2 段抜きの `\begin{table*}` / `\begin{figure*}` は、段抜きの記法に書き直す**。図は `{#fig:x .wide}`、表は題と表を
  `::: wide` の Div で囲む (表の題の `{#tbl:x}` に `.wide` を足さない — pandoc-crossref が番号を付けられなくなる。規定チェックが
  要修正で出し、build も警告する)。直後の凡例も本文幅に入る。段組の無い誌 (`_default`) では `.wide` は何もしない。
- 題 (`\caption{}`) を持たない表への参照は、番号ではなく**識別子そのもの**に化ける。
  見た目がかなり違うので見落としやすい。(c) と同じく `[@tbl:rules]` に書き直す (表には題を付ける。ABE は題の無い図表を
  規定チェックが要修正にする)。

  ```markdown
  The rules are listed in Table [\[tab:rules\]](#tab:rules){reference-type="ref" reference="tab:rules"}.
  ```

### (e) 脚注 — `\thanks{}` が本文の脚注になる

IEEEtran の `\thanks{}` は Markdown の脚注定義になり、下書きの末尾に並ぶ (`-s` を付けたときは著者の行に
`[^1] [^2]` の参照が付く)。

```markdown
<!-- pandoc の出力 (使えない) -->
[^1]: (Corresponding author: Alex Example; e-mail: (address)).

[^2]: R. Sample is also with the Department of Nursing, Example University Hospital.
```

**本文に脚注として残さない。** 中身に応じて行き先を分ける。

- **連絡著者の情報** → ABE は表題ページに連絡先を書かない (Submission Form と投稿系に入力する)。原稿からは消す
- **所属の補足** (「〜にも所属する」) → `custom-style="Affiliation"` の Div に 1 機関 1 段落で足し、著者名に上付きの数字
  (`^2^`) で対応づける
- **異動後の新住所** → その著者名 (と所属の番号) の直後に**普通の脚注**で書く
  (`Robin SAMPLE^2^^[Present address: Department of …, City, Country.]`)。ABE では docx で上付きの記号 `*` `**` になる

放っておくと docx に本物の脚注として出て、表題ページに求められる書き方から外れる。
**規定チェックは本文中の脚注を指摘しない**ので、機械では拾えない (凡例の Div の中の脚注だけは検出する)。

---

## 2. 表題ページと図表の題を ABE の規定に合わせる

IEEE 系の表題の書き方は ABE の規定と何か所か食い違う。骨格の記入欄 (`<<...>>`) を埋めるときに直す
(根拠は `docs/journal-abe.md` §3.1)。

| 要素 | IEEE 系の原稿によくある形 | ABE の書き方 | 規定チェック |
|------|------------------------|-------------|------------|
| 題 | 略語を含む・Part I / Part II | 略語を使わない (分野で一般的なものを除く)・シリーズ番号つきにしない | 参考 |
| 著者 | `Alex Example`・学位つき | **姓はすべて大文字** (`Alex EXAMPLE`)。ミドルネームは頭文字、学位・肩書は書かない | 要修正 (姓) / 参考 (学位) |
| 所属 | 脚注・記号 | 異なる機関の著者がいるときだけ上付きの**数字**で対応づける (記号 `*` は新住所の脚注用) | 参考 |
| running title | (無い) | 題が空白込みで **50 字を超えるなら 50 字以内**の running title が要る (`custom-style="Subtitle"`。柱の中央に入る) | 要修正 |
| 抄録 | 見出しつき・文献の引用つき | **1 段落・350 語以内**。見出し (`**Background:**` など) を付けない。文献の番号の引用と図表への言及を使わない | 要修正 (段落・語数・見出し) / 参考 (引用) |
| Keywords | `\begin{IEEEkeywords}` | **5 語まで**。**題の語を繰り返さない** | 要修正 |

例の題 "Automated Triage of Ward Messages with a Rule-Based Classifier" は空白込みで 62 字あるので、running title が要る。
キーワードに `triage` などの題の語が入っていれば外す。

### 図表の題と凡例を割り直す

LaTeX の `\caption{}` は説明文を丸ごと抱えていることが多い。ABE に題の語数の上限は無いが、本テンプレートは題 (短い一文) と
凡例 (説明) を分けて書く (CLAUDE.md の「図表の題と凡例の書き分け」)。題はセンテンスケースに直す。

```markdown
<!-- 元のキャプション (37 語) -->
\caption{Workflow of the triage classifier. Messages are split into sentences, matched against the rule
list, and given one of three priority labels; any message that no rule matches waits in a separate list
for the charge nurse.}

<!-- 書き起こし後: 題 6 語 + 凡例 -->
![Workflow of the message triage classifier.](figs/fig_workflow.svg){#fig:workflow}

::: {custom-style="Legend" for="fig:workflow"}
Messages are split into sentences, matched against the rule list and given one of three priority
labels. Any message that no rule matches waits in a separate list for the charge nurse.
:::
```

**凡例は段落だけで書く。** 箇条書き・表・定義リスト・空白 4 個以上の字下げ (コードブロック) などを入れると、pandoc が
`Legend` 以外の段落スタイルを付ける (検出する構造と注意点は `CLAUDE.md` の「図表の題と凡例の書き分け」)。とくに
**凡例の中の略語の定義を定義リスト (`用語` の次の行に `:   説明`) で書くと事故になる** — 普通の文で
`EHR, electronic health record;` のように並べる。元のキャプションがパネルを `(a) … (b) …` と説明しているときも、凡例を `(A)` で
始めると番号つきリストになるので、`Panel A shows … Panel B shows …` のように文で書き直す。

---

## 3. `.textbox` は使わない

2 段組の詳細抄録などのテンプレートに合わせた原稿は、図表を `.textbox` の絶対配置で置いていることがある
(Markdown で書いた原稿を別の誌へ移すときにも起きる)。書き起こすときはこれを引き継がず、**本文の流れの図表にする**。
本文幅の図表が要るなら、§1 (d) の段抜き (`{.wide}` / `::: wide`) で足りる。

理由は 2 つある。

1. **位置を手で合わせることになる。** `.textbox` はページと座標を指定する絶対配置で、置かれるページは build が見積もる。
   2 段組と独立した表題ページのある誌 (ABE) では見積もりが 1 ページずれうるので、roundtrip の PDF を見て `page` などの属性を
   手で合わせる。改稿のたびに合わせ直しになる。段抜きの記法なら、図表は参照の近くの本文の流れに置かれる。
2. **提出構成の組み替えと図表点数の検査から外れる。** `.textbox` の中身は表の移設・図の題と凡例の集約の対象外で、
   図表の点数は「本文の流れの上にある図表」だけを数える。外れた点数は規定チェックの概算の行に
   「うち .textbox 内 図 N 点・表 M 点は上限の対象外」として必ず出る (図表点数の上限を持つ誌では要修正としても出る)。

---

## 4. 文献の誌名を PubMed の略誌名に直す

LaTeX の原稿の bib は誌名を正式名で持っていることが多い。ABE は文献の誌名を **PubMed の略記**で書くよう求めるが、
CSL では正式誌名から略誌名へ変換できないので、**入力の側 (bib の `journal`) で直すしかない** (`CLAUDE.md` の
「ABE 投稿時の執筆規約」の文献の項)。PubMed の略誌名は NLM Catalog の `MedlineTA` である。

**略誌名は記憶で書かず、NLM Catalog で 1 件ずつ確かめる。** 確かめ方 (NCBI の E-utilities):

```bash
# 正式誌名 → NLM Catalog の uid
curl -s 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nlmcatalog&retmode=json&term=%22Scientific+Reports%22[Title]+AND+ncbijournals[filter]'
# uid → MedlineTA (= PubMed の略誌名)
curl -s 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nlmcatalog&id=101563288&retmode=xml' | grep MedlineTA
#   → <MedlineTA>Sci Rep</MedlineTA>
```

> **題での検索は紛らわしい別の誌を返す。** たとえば `Scientific Reports` は `Sci Rep Ist Super Sanita` などの近縁の
> 誌と並んで返り、誌によっては**目当ての誌が 1 件も出ない**こともある。
> **候補が 2 件以上出たら ISSN で引き直す** (`term=<ISSN>[ISSN]`)。
>
> **MEDLINE に収載されていない誌**も、NLM Catalog に登録があればその略誌名を使う (登録が無ければ正式誌名)。

あわせて bib の側で行うこと:

- **全著者を書く。** ABE の文献リストは全著者を出す (et al. で打ち切らない) ので、bib の `author` を `and others` で
  省いていれば補う。
- **題を保護する。** pandoc は英語の題をセンテンスケースに直すので、題の固有名詞は波括弧で保護する (`{Japan}` /
  `{TriageBot}`)。**Title Case の書名・会議録の名前は全体を二重の波括弧で**保護する (`{{Principles of Medical Engineering}}`)。
- **英語以外の題を守る。** 和文などの文献は `langid` (`japanese` など) を付けておくと、pandoc がその題をセンテンスケースに
  直さない (`abe.csl` は言語の注記を出さない)。`language` フィールドは pandoc に捨てられて効かない。
- **オンラインの文献**は `url` と `urldate` (参照日) を持たせる。
- **引けないものを外す。** 社内資料・未発表原稿・未発表の学位論文・私信・カタログは ABE では文献にできない
  (規定チェックが型と `note` から推し量って参考情報で出す)。
- **引用されない文献は落とす** (bib に残っていても出力には出ないが、入力を提出に要るものだけにしておくほうが
  後の照合が楽になる)。

誌名の略記は**目で見て**確かめる。`bash scripts/check-csl.sh` は引用様式 (CSL) が規定の出力例どおりかを照合する道具で、
自分の bib の中身は見ない (`docs/usage-guide.md` §4.1)。

---

## 5. 内容の側で必ず当たる 5 点

どれもテンプレートの不足ではなく**執筆の作業**である。書き起こしの時点で片付けるのがいちばん安い。

### 5.1 抄録を見出しの無い 1 段落にする

ABE の抄録は全種別で **1 段落・350 語以内**で、**構造化抄録 (見出しつき) は受け付けない**。会議録や他誌向けの原稿から
移すときに `**Background:** … **Methods:** …` の形が残っていれば、見出しを外して 1 段落の文章にする (規定チェックが要修正で出す)。
扱う問題・方法・主な結果・結論を含め、**文献の番号の引用と図表への言及を外す** (§0 の下書きの抄録にも `[@doe2020]` が
残っている)。先行文献に触れるなら、題を省いた形 (`Kawada T, Mukkamala R, Sugimachi M: Adv Biomed Eng. 8, 110-123, 2019`) で
本文中に書く。抄録で定義した略語も、本文の初出で改めて定義する。

### 5.2 表の階層行 — pipe table では行頭の空白が落ちる

`Sender, n (%)` の下に `\quad Nurse` / `\quad Physician` を字下げして並べる形は、(d) の出力のとおり **pandoc の時点で
行頭の空白が落ちて階層が消える**。対処は 2 つ:

- 行のラベルを `Sender: nurse, n (%)` のように書き換える (**推奨**。docx でも PDF でも崩れない)
- `&nbsp;` を使う (見た目は保てるが、語数の数え方と検索のしやすさが落ちる)

### 5.3 定型の記述を ABE の置き場所に移す

元の原稿の謝辞や脚注にまとめて書いてあった記述は、ABE では置き場所が決まっている。文例は
`data/journals/abe/skeleton/statements.md` にある。

| 記述 | ABE での置き場所 |
|------|----------------|
| AI ツールの使用 (生成・非生成を問わず。綴りと文法の確認ツールも) | **Materials and methods** (骨格は末尾の小節 `## Use of artificial intelligence tools`)。どのツールをどう使ったかを書く |
| 利益相反 | 番号なしの節 `# Conflicts of interest {.unnumbered}`。無ければ規定の定型文をそのまま書く |
| 倫理審査・同意 | 番号なしの節 `# Ethics declaration {.unnumbered}` (人・動物を扱うときだけ。規定の例文に合わせる) |
| 資金 | 番号なしの節 `# Acknowledgements {.unnumbered}` に、**資金提供者と助成番号の両方**を |
| データの入手先・臨床試験の登録・画像の加工・報告指針 | 規定が置き場所を決めていないので、本テンプレートは Materials and methods の末尾の小節に置く |

見出しには番号を書かない (`# Introduction`。学会テンプレートの自動番号が付く)。IEEE 系の `I. INTRODUCTION` のような
番号と大文字の見出しは直す。

### 5.4 段抜きにする図表を決め、段組を原稿に書かない

元の原稿の `figure*` / `table*` に加えて、**段の幅 (83 mm) に収まらない図表**を段抜きにする (§1 (d))。列の多い表や長い数字の
表は、段の中に置くと Word が段の幅に押し込んでセルの中で数字が折り返す。build は段に収まらない表を、折り返せない語から幅を
見積もって警告する。

元の原稿の `\onecolumn` / `\twocolumn` や、Markdown の原稿に生 OOXML で書いた節区切り (`w:sectPr` / `w:cols`) は**持ち込まない**。
段組は誌のプロファイルが後処理で付けるので、原稿に書くと二重に効いて体裁が崩れる。

### 5.5 図の公称サイズ — px 単位の大きな SVG と、MediaBox の大きな PDF

- **段の幅に合わせて作る。** ABE に出す図は、段に置くなら幅 83 mm 以下、段抜きなら 180 mm 以下の物理単位で SVG を作る。
  元の原稿が `\includegraphics[width=\columnwidth]` で縮めて置いていた図は、公称サイズが段の幅よりずっと大きいことが多い
  (build が段の幅に縮めると、図の中の文字も同じ割合で縮む)。
- **px 単位の大きな SVG は巨大な PNG を生む。** px と単位なしは CSS px (1/96 inch) とみなすので、たとえば
  1600×1200 px の SVG は公称 16.67×12.5 インチで、300 dpi では 5000×3750 px (18.75 MP) になる。書き起こしのときに
  **SVG ルートの `width` / `height` を物理単位 (mm) に直す** (`CLAUDE.md` の規約)。図を pptx で出す誌
  (`--format pptx`) では、スライドの寸法にも公称サイズがそのまま出る。
- **PDF の図は MediaBox の実寸がそのまま公称サイズになる** (pdf2svg が書き出す寸法を pt として読む)。元の図が大きく
  作ってあると提出図も大きくなる — たとえば MediaBox が 2000×1700 pt なら 27.78×23.61 インチで、PNG フォールバックは
  8333×7083 px (約 59 MP) になる (docx の上では段の幅か本文幅に縮めて置かれるが、埋め込む PNG は大きいまま)。**規定違反ではない**が、
  刷り面に対して極端に大きい図は元のデータの側で作り直すのが筋である (pptx で出すときは**56 インチを超えるとエラーで止まる**。
  `--slide-fit fixed` で既定の寸法へ縮めて置くこともできる。`docs/architecture.md` §2.5)。

---

## 6. 受入 — 書き起こせたかの判定

```bash
bash scripts/build.sh   --journal abe --article-type original                    # 警告なしで終わる
bash scripts/package.sh --journal abe --article-type original --mode final       # 最後に「規定チェック」
bash scripts/check-figures.sh --journal abe                                      # 図ツリー (実画素数まで検算)
```

次が揃えば、記法の書き起こしは終わっている。

- [ ] ビルドがエラーも警告も出さずに終わる (`.pdf` で参照した図はエラー、寸法の無い SVG・段の幅を超える図・段に収まらない表・
      表の題の `.wide` は警告になる)
- [ ] 相互参照がすべて解決している — docx の本文に `Fig. 1` / `Table 1` が初出順に並び、**`¿tbl:rules?` のような
      `¿…?` が 1 つも無い**。pandoc-crossref は解決できなかった参照をこの形で出すが、**ビルドは終了コード 0 で通る**
      (ログに `Undefined cross-reference: tbl:rules` が出るだけ) ので、ビルドのログと docx の中を `¿` で検索して確かめる。(c)・(d) の書き直し漏れ (とくに `tab:` のまま残った接頭辞) はここで見つかる
- [ ] 規定チェックに**記法に由来する指摘が無い** (凡例の配置と中身・記入欄 `<<...>>` の残り・抄録の見出し・表の題の `.wide`・
      表題ページの Div の欠落と重複)。残る指摘が**内容の判断が要るもの** (題の略語が分野で一般的か・キーワードと題の語・
      姓の大文字・語数) だけになっていればよい
- [ ] `check-figures.sh` が合格し、「注意」(自分で置いたラスタ図・連結した SVG・`hsl()` の色) を読んで片付けた
- [ ] 脚注 (§1 (e)) が本文に残っていない (機械では拾えないので目で見る)

本文の語数 (Original Paper は 4 000 語) は規定チェックの概算の行に内訳つきで出る (規定に数え方の定めは無く、本テンプレートの
数え方は `docs/journal-abe.md` §2)。最後の確認は `docs/abe-submission-checklist.md` を上から順に。
