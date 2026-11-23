# CLAUDE.md — AI アシスタント向けの要約

本ファイルは、このリポジトリで作業する人と AI のコーディング支援のための**規約の短い版**である。
使い方の詳細は `docs/usage-guide.md`、設計は `docs/architecture.md`、`profile.yaml` のキーは
`docs/profile-schema.md`、ABE の規定とテンプレートの読み解きは `docs/journal-abe.md` にある。

## 概要

Markdown で論文を書き、投稿用の docx を生成する**テンプレートリポジトリ**。査読対応の全領域の差分ハイライト、
ベクター図 (SVG/PDF) の劣化のない docx 埋め込み、雑誌ごとの投稿規定への切り替えに対応する。
投稿先が変わっても雑誌プロファイル (`data/journals/<id>/`) を差し替えるだけで使い回せることを目指す。

同梱の雑誌プロファイルは `_default` (汎用の投稿フォーマット) と `abe` (*Advanced Biomedical Engineering*) の 2 つ。
`abe` は日本生体医工学会 (JSMBE) が配る Word のテンプレート `ABETemplate.docx` を雛形にして体裁を組むので、
利用者がテンプレートを取得して `data/journals/abe/` に置いてから使う (同梱しない)。
**テンプレートを特定の誌の専用にしない** — 誌固有の要件は `profile.yaml` のキーと、そのキーで発火する後処理で吸収し、
誌の id で処理を分けない。新しいキーはすべて省略可能 (未指定なら何もしない) にする。同じ `main.md` を `--journal abe` でも
`--journal _default` でも組めるよう、原稿には段組などの体裁の指示を書かない。

## 設計上の確定事項

| 項目 | 採用方式 | 理由 |
|------|---------|------|
| docx → PDF | **roundtrip のみ** (Google Drive → Windows の Word COM 変換。任意の機能) | 最終体裁の再現性を最優先する。LibreOffice での PDF 化は採用しない |
| ベクター図の挿入 | **ネイティブ SVG 埋め込み + PNG フォールバック** | PDF 図は SVG に変換して同じ経路に載せる。ベクター表示は Microsoft 365 / Office 2019 以降 (Office 2016 は PNG を表示する) |
| 全領域差分 | **構造保持 AST 差分 → 色ハイライト** | タイトル / 著者 / 抄録 / キーワード / 本文 / 表 / 数式 / 脚注 / テキストボックスをすべて差分の対象にする。pandiff は使わない (Div・表・生 OOXML を壊すため) |
| 既定書式 (雑誌テンプレートが無いとき) | **汎用投稿フォーマット** | ダブルスペース・連続行番号・標準余白・Times 相当 12pt |
| 雑誌がテンプレートを配る誌 (ABE) | **テンプレートを雛形にして `reference.docx` を作る** (profile の `reference_base`) | 体裁は焼き込まずテンプレートを正とする。足すのは pandoc が使うスタイルの別名と番号定義などの修正だけで、見本の文章と識別情報は消す。2 段組・柱・見出しの写像などはキーで発火する後処理が付ける。テンプレートと生成した `reference.docx` は git で追跡しない |

## 構成

```
.
├── src/                 # 原稿 (人が編集する一次ソース): main.md / ref.bib / figs/ (+ mermaid/)
│                        #   revise-report.md / cover-letter.md (任意) / forms/ (記入済みの書式。git で追跡しない)
│                        #   clone した直後は ABE のサンプル論文入り (scripts/remove-sample.sh で消す)
├── samples/             # サンプル論文から作った出力の見本 (ABE は PDF だけ、_default は docx と PDF。scripts/make-samples.sh で作り直す)
├── main/                # パイプラインの段ごとの処理コード
│   ├── 00_setup/        #   共通設定 (defaults.yaml)・Lua フィルタ・lib/ (OOXML 操作・SVG 埋め込み・
│   │                    #     ラスタ化・pptx 生成・雑誌プロファイルの解決・reference.docx の生成)
│   ├── step01_figures/  #   図の前処理 (SVG 修正 / PDF→SVG / SVG→PNG) + 解像度の検査
│   ├── step02_build/    #   main.md → docx (pandoc + 後処理: 段組・柱・図表の題・式番号など) + 引用様式の検査
│   ├── step03_diff/     #   全領域差分 docx + 差分エンジンの受入テスト
│   ├── step04_pdf/      #   docx → PDF (roundtrip)。windows/ = Windows 側の watcher
│   └── step05_package/  #   投稿パッケージ (package.py)・提出構成の組み替え (relocate.py)・規定チェック (validate.py)
├── data/
│   ├── journals/        #   雑誌プロファイル: _default/ と abe/ (abe/skeleton/ = 原稿骨格。ABETemplate.docx は abe/ に置く)
│   ├── dummy/           #   動作例とフィクスチャ (git 管理。abe/ = ABE の記入済みの動作例)
│   ├── source/          #   本番の素材 (git 管理外)
│   ├── step01_figures/ step02_build/ step03_diff/   # 各段の中間・成果物 (git 管理外)
│   ├── output/          #   提出物の集約 (git 管理外)
│   └── products/        #   Word で変換した PDF (git 管理外)
├── docker/              # pandoc / mermaid / svg-conversion のコンテナ (ポートは公開しない)
├── scripts/             # 入口のスクリプト (build / diff / package / 検査 / roundtrip / 回帰スナップショット)
├── fonts/               # svg-conversion 用の専有フォント (git 管理外。利用者が置く)
└── docs/                # 詳しいガイド
```

## Step-by-Step Pipeline

- 各ステップの**コード**は `main/stepNN_name/` に置く。
- 各ステップの**中間・成果データ**は `data/stepNN_name/` に出す (コードとデータを分ける)。
- 提出物は `data/output/`、Windows で変換した PDF は `data/products/` に集める。
- 各ステップは単独で再実行できること。連番を保つ。

## 主なコマンド

```bash
docker compose -f docker/docker-compose.yml build    # pandoc イメージのビルド (mermaid / svg-conversion は初回に自動ビルド)

bash scripts/build.sh                                # 図の前処理 → docx (data/step02_build/main.docx)
bash scripts/diff.sh HEAD~1                          # 直前のコミットとの全領域差分 (data/step03_diff/main_diff.docx)
bash scripts/diff.sh old.md new.md                   # 任意の 2 版の差分
bash scripts/package.sh --journal _default --mode final   # 投稿パッケージ (data/output/<id>/)
bash data/journals/make-reference.sh <id>            # reference.docx を作り直す (profile.yaml から。abe はテンプレートから)

# ABE (先に学会テンプレートを data/journals/abe/ABETemplate.docx に置く。無ければ build / diff は取得元を出して止まる)
bash scripts/build.sh   --journal abe --article-type original          # 本文・カバーレター・回答書の docx
bash scripts/diff.sh    <旧版の revision> --journal abe --article-type original   # 改訂のとき (2 段組の差分 docx)
bash scripts/package.sh --journal abe --article-type original --mode final       # data/output/abe/ (図は本文に埋め込んだまま。
                                                     #   forms/ の書式を複製し、SUBMISSION.md に一覧と規定チェックを書く)
bash scripts/check-figures.sh --journal abe          # PNG フォールバックの解像度
bash scripts/build.sh --input data/dummy/abe-csl --journal abe        # 引用様式の照合: フィクスチャをビルドして
bash scripts/check-csl.sh --docx data/step02_build/main.docx          #   規定の文献の例・本文の引用・docx の書式を照合する

# 規定チェックだけを回す (ビルド不要)
docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
    python3 main/step05_package/validate.py --input-root data/dummy/abe --journal abe --article-type original

# 受入テスト
bash scripts/check-diff.sh                           # 差分エンジン (テンプレートがあれば abe でも回す)
docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
    python3 main/step05_package/test_validate_abe.py # ABE の規定チェックの回帰試験

# PDF (任意。Windows 側の watcher が要る)
bash scripts/push-win-tools.sh     # Windows 側の 3 ファイルを Drive の送出先へ送る
bash scripts/check-pdf-path.sh     # 経路の診断 (読み取りのみ。--full で docx を 1 本往復)
bash scripts/roundtrip.sh --skip-build   # data/output/*.docx → PDF (data/products/)。SUBMISSION.md を持つ提出パッケージは
                                   #   本文と書式も PDF にし、パッケージ一式を Drive の submission-<journal>/ に置く
                                   #   (別の誌でビルドした docx には --skip-build。動作例のパッケージは INPUT_ROOT=data/dummy/abe を付ける)
```

## 原稿執筆の規約 (src/main.md)

- **Markdown 拡張構文** (Pandoc)。`--from markdown+east_asian_line_breaks`。
- **タイトル / 著者 / 所属 / 抄録 / キーワードは YAML メタではなく本文中の `custom-style` Div** で書く。
  構造保持 AST 差分がこれらを温存して中身を差分にするため (YAML メタは差分の対象にならない)。
  ```markdown
  ::: {custom-style="Title"}
  論文タイトル
  :::
  ```
- **引用**: `[@bibkey]`。文献は `src/ref.bib` (BibTeX) に集める。様式は雑誌プロファイルの CSL。
- **見出し**: **番号を書かない** (`1. Introduction` ではなく `# Introduction`)。番号が要る誌は reference.docx の見出しのスタイルが
  自動番号を持つ (ABE)。番号の無い節 (Abstract・謝辞・文献など) は `{.unnumbered}` を付ける — 誌が `headings.unnumbered_style` を
  持てばその段落スタイルになる。
- **段組を原稿に書かない**。2 段組は誌の profile (`layout`) が後処理で付けるので、`sectPr` / `w:cols` を生 OOXML で手書きしない。
  **段の幅を超える図表は段抜きにする**: 図は `![…](figs/x.svg){#fig:x .wide}`、表など任意のブロックは `::: wide` の Div で囲む
  (表の題の `{#tbl:x}` に `.wide` を足さない — pandoc-crossref が番号を付けられなくなる。段組の誌の build は警告する)。
  直後の凡例も本文幅に入る。段組の無い誌では何もしない。段の幅を超える図に `{.wide}` が無ければ、build が段の幅に縮めて警告する。
- **図**: `![キャプション](figs/foo.svg){#fig:foo}`、参照は `[@fig:foo]` (CJK の文中でも角括弧の形で書く)。
  題つきの図は **1 段落に 1 図**。
  - 草稿の段階では**図を docx に埋め込む** (共著者が見られるように)。
  - **PDF 図も原稿では `.svg` で参照する** (`figs/foo.pdf` を置き、本文は `figs/foo.svg`)。前処理が SVG に変換する。
    `.pdf` で参照すると埋め込みが壊れるので、ビルドがエラーで止める。
  - **SVG ルートの `width` / `height` は図の公称サイズ**で、docx 上の表示寸法と、ラスタ化するときの画素数
    (公称サイズ × 要求 dpi) の両方を決める。物理単位 (`160mm` / `144pt` / `2in`) ならそれが実寸、単位なしと
    `px` は **CSS px = 1/96 inch** とみなす。印刷したい幅より小さい公称サイズで作ると、その幅での実効解像度が
    要求 dpi を下回るので、**300 dpi を求める誌に出す図は物理単位で幅を書く**。見た目の大きさを変えたいときは
    原稿側で `{width=...}` を付ける。本文幅を超える図は pandoc が本文幅 (`_default` の A4・余白 25 mm で約 159.8 mm) に縮める。
  - **自分で置いたラスタ図 (PNG / JPEG / TIFF) は解像度の保証の対象外**。そのまま複製されるので、解像度は
    執筆者が担保する (本文幅いっぱいで 300 dpi なら幅 1890 画素以上)。検査は不合格ではなく「注意」として出す。
  - **寸法を持たない SVG** は、草稿のビルドは警告つきで通るが、提出図の生成 (`--mode final`) はエラーで止まる。
  - **複数の SVG を 1 ファイルに連結しない**。多パネル図は作図側で 1 枚として出力する。svglite の出力を 2 つ入れた
    SVG は Word が文字だけを片方のパネルへ寄せ、連結で `id` が重複すると切り取り範囲を取り違える。ブラウザでも
    PNG でも正常に見えるので、`bash scripts/check-figures.sh` の「注意」と、roundtrip の PDF の拡大での目視で見つける。
    塗り・線の色を `hsl()` で書いた SVG も Word / PowerPoint が黒く塗るので同じ「注意」に出る。
  - **Mermaid 図**: `src/figs/mermaid/*.mmd` を置けば前処理が SVG / PDF にする (`.mmd` が一次ソース)。
    ラベルは SVG の `<text>` で出し、`hsl()` の色は生成時に 16 進へ直す。**別の道具で作った SVG を `figs/` に
    直接置くとこの後処理を通らない**ので、`.mmd` を置いてこの経路で作ること。
  - **最終提出図** (図を別ファイルで出す誌): `docker/svg-conversion/convert.sh` の svg→pdf は文字をアウトライン化する
    (選択・検索はできなくなる)。埋め込みとアウトラインは `profile.yaml` の `figures.font_handling` で切り替える。
  - **図を PowerPoint で出す誌で、図を PowerPoint で仕上げたいときは、図の隣に同名の `.pptx` を置く**
    (`figs/fig1.svg` + `figs/fig1.pptx`)。最終提出ではそれが無変換でコピーされる。1 ファイル 1 スライドで、マクロを含むものは拒否する。
- **テキストボックス (フロート図表)**: `.textbox` Div に `width/height/pos-x/pos-y/page/valign` 属性。
  中身は提出構成の組み替え (表の移設・凡例の集約) の対象外で、図表点数の上限検査からも外れる
  (外れた点数は規定チェックの概算行に必ず出る)。2 段組の誌では、位置は roundtrip の PDF を見て手で合わせる。
- **表**: 既定は三本線 (booktabs)。全罫線が要るときは `.grid` Div。
- **数式**: LaTeX 構文 (`$...$` / `$$...$$`)。番号つきの式は `$$ … $$ {#eq:x}` を**独立した段落**に書き、参照は `[@eq:x]`。
  誌が `equations.style` を持てば (ABE) 式番号がスタイルの右タブで段の右端に寄る (文の途中に書いた番号つきの式は、
  差分 docx で右寄せが外れることがある)。
- **単位**: SI または SI 派生単位。温度は `°C` (度記号 + 大文字 C の 2 文字) と書き、合成済み 1 文字の `℃` を使わない
  (`㎎` `㎏` などの合成 1 文字も同様。規定チェックが指摘する)。
- **機器・製品**: 型番 + 製造元 + 所在地 (市・州・国) を括弧内に書く。統計ソフトはバージョンも書く。
- **生 OOXML**: 細かい体裁は ```` ```{=openxml} ```` ブロックで入れる (段組は上のとおり profile に任せる)。

### 図表の題と凡例の書き分け

**題 = キャプション / 凡例 = 直後の `custom-style="Legend"` Div** と書き分ける。誌によって題と凡例の語数上限が
別々に決まっているが、pandoc のキャプションは 1 本しか付けられないため。

```markdown
![Processing pipeline from the record to the reviewed event list.](figs/fig-flow.svg){#fig:flow}

::: {custom-style="Legend" for="fig:flow"}
Rectangles denote processing stages. EHR, electronic health record.
:::
```

- 表も同じで、キャプション (`: 題 {#tbl:x}`) が題、直後の Legend Div が凡例。
- **Legend Div は対象の図 (画像段落) / 表の直後に置く**。`for` は対応先の明示で docx には出ない。Div の中で段落を
  分けてもよいが、対象の直後に連続して置く (提出構成の組み替えは「直後に連続する `Legend` 段落」を 1 組で動かす)。
- pandoc は表の題を表の上、図の題を図の下に出す。**「表の題とキャプションは表の上」の誌** (ABE) は profile の
  `tables.legend_position: above` で、後処理が表の直後の凡例を題と表の間へ移す (原稿では凡例を表の後に書くまま)。
- **凡例は段落だけで書く**。箇条書き・表・見出し・コードブロックなどを入れると pandoc が `Legend` 以外の段落スタイルを
  付け、そこで集約が止まって以降が本文に取り残される。規定チェックが要修正として指摘する。とくに次の 3 つは
  そのつもりがなくても書けてしまう:
  - **凡例を `(A)` や `a.` で始めない** — pandoc は番号つきリストとして読む。パネルの説明は
    `Panel A shows … Panel B shows …` のように文で書く。
  - **空行のあとを空白 4 個以上で字下げしない** — コードブロックになる。
  - **定義リストを使わない** — 略語の再定義は `EHR, electronic health record; ICU, intensive care unit.` のように文で書く。
- 凡例が要らない図表では Legend Div を省いてよい。
- 題の語数は執筆者が書いたキャプションだけを数え、pandoc-crossref が付ける `Figure 1: ` は含めない。

## ABE 投稿時の執筆規約

詳細と出典は `docs/journal-abe.md`、通し手順は `docs/usage-guide.md` §8、投稿当日の確認は `docs/abe-submission-checklist.md`。
**本テンプレートは日本生体医工学会 (JSMBE) と ABE の編集部が作成・承認・確認したものではなく、公式のテンプレートでもない。
規定は変わりうるので、投稿前に [Instructions to Authors](https://abe-journal.org/authorinstructions) で確かめる。**
ここに挙げるのは、体裁 (2 段組・見出しの番号・柱・図表の題の形・式番号の位置・文献の書式。profile と後処理が付ける) ではなく、
**原稿の書き方に踏み込むもの**だけ。規定と学会テンプレートの見本が食い違えば規定に従う。

- **学会テンプレートを先に置く**: Instructions to Authors のページから `ABETemplate.docx` を取得し、`data/journals/abe/ABETemplate.docx` に置く
  (git で追跡しない。再配布しない)。無ければ build / diff は取得元と置き場所を出して止まる。本テンプレートが確かめた版 (ver.3) と違うものを
  置くと、指紋 (SHA-256) が profile の `reference_base_sha256` と違うので止まる — 改版でスタイル名や節の構造が変わると後処理が外れうるため。
  新しい版を使うなら、その値を表示された値に書き換え、出てくる警告と roundtrip の PDF の見た目を確かめ直す。
- **骨格から書き始める**: clone した直後の `src/` には記入済みのサンプル論文 (`data/dummy/abe/` の動作例に TJD の挿絵を足したもの) が入っているので、
  先に `bash scripts/remove-sample.sh` で消し (中身がサンプルのままのファイルだけを消す)、それから
  `cp data/journals/abe/skeleton/main.md src/main.md`。自分の `main.md` の隣にサンプルのファイルが残っていると、最終モードの package は止まる。
  記入欄は `<<...>>` (埋め忘れは規定チェックが要修正にする)。
  定型の記述の文例は `data/journals/abe/skeleton/statements.md` (参照専用)、任意のカバーレターは `skeleton/cover-letter.md`。
  記入済みの動作例は `data/dummy/abe/` (`--input data/dummy/abe` でビルドできる)。規定の要点は骨格の各節の頭のコメントにある。
- **節の順** (Original Paper): 表題ページ (Title → Author → Affiliation → running title → Received / Revised → Abstract → Keywords) →
  Introduction → Materials and methods → Results → Discussion → (Conclusion) → **番号なしの節** Conflicts of interest → (Ethics declaration) →
  (Acknowledgements) → References。規定チェックは Introduction / Materials and methods / Results / Discussion / Conflicts of interest /
  References が無ければ要修正にする (`Methods` / `Acknowledgments` などの言い換えは同一視)。Review Paper でも同じ節を求める。
- **表題ページ**:
  - 題は簡潔に。分野で一般的なもの以外の略語を使わず、シリーズ番号つきの題 (Part I / Part II) にしない。
  - **著者の姓はすべて大文字** (`Taro YAMADA`)。名と姓はフルで、ミドルネームは頭文字。学位・肩書は書かない (書けば規定チェックが参考で知らせる)。
    著者はカンマで区切っても、改行 (行末の `\` の強制改行を含む) で 1 行 1 人に並べてもよい。
  - **表題ページの Div (Title / Author / Abstract / Keywords) は 1 つずつ書く** — 無い・2 つ以上あると規定チェックが要修正にする。
  - **所属**: 研究室・部門・研究所・大学、市・州・国まで。異なる機関の著者がいるときだけ上付きの数字で対応づける
    (`^1^Graduate School of …`。番号の後にタブも空白も書かない — docx で番号の直後にタブが入る)。1 機関 1 段落。
  - **異動後の新住所**は著者名 (と所属の番号) の直後に普通の脚注で書く (`Hanako CHOKKAN^2^^[Present address: …]`)。docx では
    著者の段落の脚注が出てきた順に上付きの記号 `*` `**` になり、本文の脚注は数字のまま。2 人が同じ新住所なら同じ文面を 2 度書くか
    同じ `[^addr]` を 2 度参照する (1 つの記号と 1 つの脚注にまとまる)。新住所を所属の Div に書かない。
  - **running title**: 題が空白込みで 50 字を超えるなら 50 字以内の running title が要る。所属の後の `custom-style="Subtitle"` の Div に書く
    (規定は abbreviated title も求めるので 50 字以下でも書いておく)。この文字が本文のページの柱の中央に入る。
  - 受付日と改訂日の欄 (`Received … [Do not enter]`) は編集部が記入するので書き換えない。連絡著者の連絡先は表題ページに書かない
    (Submission Form と投稿系に入力する)。
- **抄録**: 1 段落・350 語以内 (全種別)・**構造化抄録 (見出しつき) は不可**。扱う問題・方法・主な結果・結論を含める。文献の番号の引用を
  使わない (先行文献に触れるなら `Kawada T, Mukkamala R, Sugimachi M: Adv Biomed Eng. 8, 110-123, 2019` の形で本文中に)。図表に触れない。
- **Keywords**: 5 語まで。**題の語を繰り返さない** (1 語でも題の語と同じなら要修正)。`**Keywords**: a, b, c.` の 1 行。
- **略語**: 本文での初出で正式名と括弧で定義する。題と抄録で定義していても、本文の初出で改めて定義する。
- **量の記号は斜体、単位と元素記号は立体** — 量の記号は数式 (`$P$`・`$T_1$`) で書くと斜体になる。
- **Materials and methods**: 再現できる詳しさで。珍しい試薬・動物・菌株・装置は供給元と所在地 (市・国) を括弧で。脚注は最小限。
- **AI ツールの使用は Materials and methods で開示する** (骨格は末尾の小節 `## Use of artificial intelligence tools`)。生成・非生成を問わず
  (綴り・文法の確認ツールも)、どのツールをどう使ったかを書く。生成 AI の使用は研究デザイン・方法の不可欠な一部である場合に限って原則として認められ、
  それ以外は編集者の個別の判断になる。AI ツールは著者にできない。文例は `statements.md`。使った道具と版は、書き始めた時点から
  git で追跡する作業記録のファイルに残しておく。
- **規定が置き場所を決めていない定型の記述は Materials and methods の末尾の小節**に置く (本テンプレートの既定): データと材料の入手先と公開
  (規定は査読中の編集者と査読者への全量の開示と、出版日までの公開を求める)・臨床試験の登録番号と登録先・画像の加工の内容・報告指針
  (EQUATOR Network。系統的レビューとメタ解析は PRISMA が必須)。
- **Conflicts of interest**: 全著者の利益相反を申告する。無い場合は規定の定型文をそのまま書く ("The authors declare no conflicts of interest with any
  companies or commercial organizations per the definition of Japanese Society for Medical and Biological Engineering.")。別に著者ごとに 1 通の
  COI 開示書式を出す (本文と食い違わないこと)。
- **Ethics declaration**: 人・動物を対象にしたなら規定の例文 (`statements.md`) で書き、倫理委員会の承認などの証拠書類を原稿とともに出す。
  人も動物も扱わないなら節ごと削る。
- **Acknowledgements**: 簡潔に。**資金源はすべてここに、資金提供者と助成番号の両方を書く**。節名の綴りは規定の中でも揺れる
  (`Acknowledgments` / `Acknowledgements`、`Conflicts of interest` / `interests`)。骨格と動作例は英式の `Acknowledgements`。
  英語は米式か英式のどちらかに統一する (母語でない著者は専門業者の英文校正の証明書が要る)。
- **図表**:
  - 図は本文中の適切な位置に埋め込んだまま提出する (分離提出しない。`figures.separate: false`)。PNG フォールバックは 300 dpi。
  - 段の幅は 83 mm、本文幅は 180 mm。段に収まらない図は `{.wide}`、表は題ごと `::: wide` の Div で囲む。
  - **参照は `[@fig:x]` / `[@tbl:x]` / `[@eq:x]` だけを書く** (`Fig. 1` / `Table 1` / `Eq. 1` の語は自動で付く。`Fig. [@fig:x]` と書くと `Fig. Fig. 1` になる)。
  - 図の題は図の下、表の題とキャプションは表の上 (原稿は「図表の題と凡例の書き分け」のまま。表の凡例も表の後に書く)。
  - 題とキャプションは最小限の大文字 (文頭と固有名詞だけ)。キャプションは本文を読まずに理解できるように完結させる。
  - 画像の加工は最小限・画像全体に・分野の基準内で、原稿に明記する。他者の著作物の図表は権利者 (と出版社) の許諾を取り、許諾の写しを初回投稿時に添える。
- **引用・文献** (modified Vancouver。`abe.csl`):
  - 本文は出現順の番号を角括弧で (`[1]` / `[3, 4]` / `[7–10]`)。原稿は `[@key]` のまま。文献リストは全著者・題を省略しない・巻は太字・
    ページ範囲はエンダッシュ。
  - **誌名は PubMed の略記**を `ref.bib` の `journal` に持つ (CSL では正式誌名から略記に直せない)。**Title Case の書名・会議録の名前は全体を
    波括弧で保護する** (`{{Principles of Medical Engineering}}`。保護しないと pandoc がセンテンスケースに直す)。オンライン文献は `url` と `urldate`。
  - 引けないもの: 社内資料・未発表原稿・未発表の学位論文・私信・カタログ (規定チェックは型と `note` から推し量って参考で出す)。
  - 引用様式を変えたら、フィクスチャ `data/dummy/abe-csl/` をビルドして `bash scripts/check-csl.sh --docx <その docx>` で規定の例と照合する
    (`docs/usage-guide.md` §4.1。原稿の docx を渡すと引用の件数が合わずに NG になる)。
- **本文語数**: 上限は Original Paper 4 000 / Research Letter 2 500 / Technical Note 1 500 語 (Review Paper は編集委員会が決める。`--article-type` で
  切り替える)。規定に数え方の定めが無いので、本テンプレートの概算は本文の節の語を数え、図表の題と凡例の語数は内訳として別に出す
  (表題ページと文献の語は概算に入らない)。事務局の数え方は違いうるので、上限に近いときは内訳も見て見積もる。
- **提出物**: 原稿本体は Word で PDF にした `manuscript.pdf` (図表を埋め込んだもの)。記入済みの書式 (Submission Form and Author Statement・
  著者ごとの COI 開示書式・英文校正の証明・倫理の証拠書類・転載許諾の写し) は `src/forms/` に置き、git で追跡しない。署名を入れてスキャンした PDF は
  docx と同じ名前の `.pdf` で置けばそれが使われる。本テンプレートは本文と書式を 1 本の PDF に結合しない (投稿画面が受け付けなければ結合が要る)。
- **補足資料**: `src/supplementary/` に置く (無変換で複製)。最終形で初回投稿時に出す。1 ファイル 50 MB・合計 50 MB 以下 (超過は要修正)。
  バイナリ・アーカイブのファイルを含めない (参考で知らせる)。
- **投稿前に決めること**: 既発表かどうか (会議録として刊行されたものは長さ・図表によらず既発表。例外はプレプリントと図表を含まない 400 語未満の抄録)・
  連絡著者 (投稿後に変えられない)・データの公開が倫理審査・同意・契約で許されるか・掲載料 (筆頭か連絡著者が JSMBE 会員かで違う)。
- **改訂**: 判定から 3 か月以内に再投稿する。差分 docx は `diff.sh <旧版> --journal abe` (2 段組・柱・図表の題・式番号は build と同じ)。
  回答書は `src/revise-report.md` に書く (docx では見出しの番号が外れ、1 段組・行番号なし)。
  **査読コメント・回答書・事務局とのやりとりは秘密に保ち**、公開するリポジトリやほかの原稿に持ち出さない (規定の通信の秘密)。

## 雑誌プロファイル (data/journals/<id>/)

投稿先ごとに次を 1 セットで持つ。テンプレートを提供しない誌は `_default/profile.yaml` を写して作る。

- `profile.yaml` — 図の要件 (形式・解像度)、行番号、行間、余白、題・見出しの級数と色 (`text_styles`)、
  表の置き場所 (`tables.placement`)、語数の上限、図表番号の書式など。キーの一覧と省略時の挙動は `docs/profile-schema.md`
- `<id>.csl` — 引用様式 (無ければ `_default` の AMA 系を継承)
- `reference.docx` — pandoc の体裁の雛形 (`bash data/journals/make-reference.sh <id>` で生成)。
  - 体裁を profile から焼き込む誌 (`_default`) は pandoc の既定データから作る生成物なので同梱しない。`build.sh` / `diff.sh` が、`_default` のものと、
    `reference_doc` が `reference.docx` を指す対象誌のものを、無ければ自動で生成する。**`profile.yaml` の体裁を変えたら自分で作り直す**
    (古いままだと build と規定チェックが食い違いを警告する。ただし `text_styles` は比べないので、変えたら必ず作り直す)
  - **雑誌がテンプレートを配る誌は、そのテンプレートを profile の `reference_base` に名前で書いて誌のディレクトリに置く** (ABE は `ABETemplate.docx`)。
    `make-reference.sh` はそれを雛形にして体裁を焼き込まずに `reference.docx` を作り、build / diff は生成の元 (テンプレート・profile・生成処理) が
    変われば作り直す。テンプレートの指紋を `reference_base_sha256` に書いておけば、違う版を置いたとき止まる。
  - `.gitignore` は誌のディレクトリの `*.docx` / `*.dotx` / `*.docm` / `*.dotm` をまとめて無視する (学会の配布物とその生成物を git に載せない)。
    **生成した reference.docx や出版社の雛形を追跡したい誌は `.gitignore` に `!data/journals/<id>/reference.docx` のような行を足す**
- `skeleton/` (任意) — 誌固有の原稿骨格 (ビルドの対象ではなく、写して書き始める雛形。`README.md` は置かない — `cp -r skeleton/. src/` で
  `src/README.md` を上書きするため)

**記事種別** (`article_types`): 種別ごとに語数・抄録の要件が違う誌のために `article_types.<id>` を持てる。
優先順は `--article-type` > `profile.article_type` > (種別なし) `limits` そのまま。存在しない種別は一覧を出して止まる。

## データの置き場所

- 原稿の正本は常に `src/`。`data/source/` は本番の素材を置く git 管理外の補助領域、`data/dummy/` は自己検証用の
  完結したサンプル (`src/` と同じ構成)。誌の動作例 (`data/dummy/abe/`) は `--input` で明示する。clone した直後の `src/` には、ABE の
  Original Paper の体裁のサンプル論文 (TJD/THS のパロディ。`data/dummy/abe/` の動作例に TJD の挿絵 (段抜きのラスタ図) を足し、コメントを書き分けたもの) が入っている。
  `samples/` はそれと汎用のサンプルから作った出力の見本で、原稿・プロファイル・処理を変えたら `bash scripts/make-samples.sh` で作り直す。
- **`.development` マーカーで入力ルートを切り替える**: 有り → `data/dummy/`、無し → `src/`。存在だけで判定する
  (`echo dev > .development` / `rm .development`)。環境変数 `INPUT_ROOT` か `--input <dir>` でも上書きできる。
- **開発時はまずダミーで動作を確かめる**。
- **記入済みの投稿書式は `<入力ルート>/forms/` に置き git で追跡しない** (`.gitignore` の `src/forms/`。署名と個人情報を含むため)。
  `--input` で入力ルートを `src/` 以外にしたときは、その `forms/` を `.gitignore` に足す (`package.sh` が無視されていなければ注意を出す)。
- **学会テンプレートと、それから作った `reference.docx` を git にも公開物にも入れない**。
- 一時ファイルは `jank/` に置く (git 管理外。`diff.sh` と回帰スナップショットもここを使う)。

## コンテナ運用の原則

- **テキストファイルの確認以外はコンテナの中で実行する**。ホストの Python は汚さない。
- ホストで Python を使ってファイルを見る必要があるときは **uv** で隔離する (`uv run --with <pkg> python ...`)。
- 変換処理は必ずコンテナ経由。コンテナはすべて変換専用 (常駐しない) なので、ポートは公開しない。
- イメージ名はプロジェクト名を前に付ける (`docx-paper-template-pandoc` など)。版を固定するのは pandoc / pandoc-crossref /
  panflute / lxml / mermaid-cli と、ベースイメージのタグ (ダイジェストではない) である。apt / apk のパッケージ
  (librsvg・LibreOffice・Inkscape など) は固定しておらず、イメージを作った時点の版になるので、作り直すと PNG の描画や
  読み込み検査の結果が変わりうる。mermaid-cli の依存の描画の本体 (`mermaid`) も 11.x の範囲で作った時点の版になる。pandoc と pandoc-crossref は組で更新する (片方だけ上げると crossref が動かない)。

## 変更するときの確認

- 回帰の確認: 変更の前後で `bash scripts/baseline.sh <接尾辞>` (`_default`) と `bash scripts/baseline-abe.sh <接尾辞>` (`abe`。テンプレートが要る) を撮り、
  `docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc python3 scripts/compare-snapshots.py <前> <後>`
  で比べる (docx は zip の部品ごとに内容で比べる。`data/journals/*/profile.yaml` の誌が前後のどちらかに無ければ不合格になるので、
  撮らなかった誌は `--expect-missing <誌>` で外す)。diff の旧版は環境変数 `DIFF_REV` (既定 `HEAD~1`) と `ABE_DIFF_REV` (既定なし) で、
  比べる 2 つは同じ値で撮る。**clone した直後は `HEAD~1` に原稿が無い**ので `DIFF_REV=HEAD` / `ABE_DIFF_REV=HEAD` を付ける。
- スナップショットの差分の段は旧版と新版が同じ原稿なので、差分エンジンの変化は `bash scripts/check-diff.sh` で、規定チェックの変化は
  `main/step05_package/test_validate_abe.py` で確かめる。
- `profile.yaml` に足すキーは省略可能にし、未指定なら何もしないようにする (ほかの誌の出力を変えない)。誌の id で処理を分けない。
