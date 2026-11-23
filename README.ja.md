# docx-paper-template-abe

**論文を Markdown で書き、投稿用の Word ファイル (.docx) を生成するテンプレートリポジトリです。**
複製して `src/main.md` を書き、雑誌プロファイルを選んでビルドします。
投稿の作業のうち、ふだん Word で手作業になる部分 — 査読対応の差分の色付け、ベクター図の劣化のない貼り込み、
雑誌ごとの体裁、最終提出物の組み立て — を受け持ちます。
主な対象は *Advanced Biomedical Engineering* (ABE) で、その 2 段組の体裁は学会が配る Word のテンプレートから組みます。
ほかの誌には汎用のプロファイルで対応します。

English: [README.md](README.md)

> **雑誌・学会とは無関係です。** 本プロジェクトは独立した道具で、日本生体医工学会 (JSMBE) と
> *Advanced Biomedical Engineering* の編集部が提供・承認・確認したものではなく、公式のテンプレートでもありません。
> `abe` プロファイルは同誌の公開されている Instructions to Authors (1 April 2026 の版) を私たちが読み解いたもので、
> 規定はいつでも変わりえます。**投稿の前に必ず最新の
> [Instructions to Authors](https://abe-journal.org/authorinstructions) で確かめてください。**

---

## できること

- **Markdown → .docx** (pandoc)。タイトル・著者・所属・抄録・キーワードは本文中のスタイル付きブロックとして書くので、
  雑誌の reference document で整形され、差分の対象にもなります。原稿には段組などの体裁の指示を書かないので、
  同じ `main.md` をどの雑誌プロファイルでも組めます。
- **原稿全体の差分 (査読対応)**。2 版の `main.md` を pandoc の AST で突き合わせ、追加した語を青、削除した語を赤の
  取り消し線で示します。タイトル・著者・抄録・キーワード・本文・表・数式・脚注・テキストボックス内の表まで対象で、
  文書の構造は壊しません。差分の docx にもビルドと同じ雑誌の体裁が付きます。
- **ベクター図**。SVG 図を .docx にネイティブで埋め込み、プロファイルの解像度 (既定 300 dpi) の PNG を
  フォールバックとして添えます。PDF 図はまず SVG に変換します。Mermaid 図 (`.mmd`) はコンテナで描画して同じ経路に載せます。
- **雑誌プロファイル** (`data/journals/<id>/`)。体裁 (`profile.yaml`)・引用様式 (CSL)・Word の reference document
  (`reference.docx`。初めて要るときに手元で生成します) を雑誌ごとに 1 ディレクトリで持ちます。原稿そのものは雑誌に依存させません。
  - `_default` — 汎用の投稿フォーマット。ダブルスペース・連続行番号・Times New Roman 12 pt・A4 余白 25 mm・AMA 系の番号引用。
    そのまま動きます
  - `abe` — *Advanced Biomedical Engineering*。学会の Word のテンプレートを各自が取得して置く必要があります (クイックスタート)
- **ABE 対応**:
  - 学会の `ABETemplate.docx` (ver.3) を雛形にした reference document。体裁は焼き込まず、書体・寸法・余白・柱・フッタは
    テンプレートが正です。テンプレートの識別情報 (作成者の欄・文書 ID・変更履歴) は取り除きます
  - テンプレートの体裁: 1 ページ目は 1 段組の表題ページ (題・著者・所属・running title・抄録・キーワード)、2 ページ目からは
    行番号つきの 2 段組の本文、柱に running title、見出しの自動番号 (`1.` / `2.1` / `2.1.1`)。番号の無い節 (`{.unnumbered}`。
    Conflicts of interest・References など) はテンプレートの番号なしの見出しのスタイルになります
  - 両方の段にまたがる図表 (段抜き。`{.wide}` / `::: wide`)。段の幅を超える図は段の幅に縮めて警告します
  - 誌の形の題と参照 (`Fig. 1 …` / `Table 1 …`。表の題と凡例は表の上、図の題は図の下)、図と題を分けない改ページの制御、
    段の右端にそろえた式番号
  - 所属の上付きの番号と、著者名の後の脚注 (異動後の新住所) を `*` / `**` の記号にすること (ほかの脚注は数字のまま)
  - 誌の modified Vancouver の引用様式 (`abe.csl`)。本文は `[1]` / `[3, 4]` / `[7–10]`、文献リストは全著者・巻は太字。
    規定の文献の例 6 件との照合テストつき
  - 規定チェック: 記事種別 (Original Paper / Research Letter / Technical Note / Review Paper) ごとの語数、350 語以内・1 段落の
    非構造化抄録、題の語を繰り返さないキーワード、長い題の running title、大文字の姓、必須の節、補足資料の容量、
    合成文字 (`℃`) などの執筆チェック
  - 図を本文に埋め込んだまま組む提出パッケージ (誌は図を置いた原稿 1 本の PDF を求めるため)。記入済みの書式を `forms/` から
    集め、アップロードの一覧と規定チェックの結果を `SUBMISSION.md` に書きます
  - 必須の節をすべて含む原稿の骨格と、定型の記述 (利益相反・倫理・資金・AI ツールの使用の開示・データの入手先) の文例集
    (`data/journals/abe/skeleton/`)
- **ほかの誌のための機能**: 図を PowerPoint (1 図 1 ファイル。ベクターの SVG と PNG のフォールバック) や PNG / PDF で出す、
  表を末尾へ移す・1 表 1 ファイルにする、図の凡例を References の後へ集める — どれも `profile.yaml` のキーで有効にします。
- **Microsoft Word による PDF 化 (任意)**。.docx を rclone で Google Drive に送り、Windows の PC で動く watcher が
  Word で変換し、PDF が戻ってきます。Word で開いたときの体裁で確かめるためで、PDF 化に LibreOffice は意図して使いません。
  最終提出用のパッケージでは本文と記入済みの書式も PDF にしたうえで、パッケージを Drive の専用のフォルダ (`submission-<journal>/`) に置くので、
  アップロードするファイルを 1 か所から選べます。

## 必要なもの

- **Docker** (Compose v2 つき)、**bash**、**git**。変換はすべてコンテナの中で行い、ホストには何も入れません。
- **x86-64 (amd64)** のホスト。pandoc のイメージは amd64 版のバイナリを入れます。開発は Linux で行っており、
  ほかの環境では試していません。
- **初回ビルド時のネットワーク接続**。pandoc と pandoc-crossref、Mermaid CLI と headless Chromium、
  (`svg-conversion` イメージでは) Microsoft Core Fonts を取得します。
- 埋め込んだ SVG をベクターで表示するには **Microsoft 365 または Office 2019 以降**。
  Office 2016 などでは PNG のフォールバックが表示されます。
- `abe` プロファイルには**学会のテンプレート `ABETemplate.docx`**。
  [Instructions to Authors](https://abe-journal.org/authorinstructions) のページから取得します。本リポジトリには含めていません。

任意:

- **PDF 化**: Google Drive のリモート (既定の名前は `gdrive:`) を設定した rclone と、同じ Drive のフォルダを同期する
  Microsoft Word 入りの Windows の PC。[docs/roundtrip-windows-watcher.md](docs/roundtrip-windows-watcher.md) を参照。
- **`svg-conversion` イメージ** (別ファイルで出す図の文字をアウトライン化するときだけ使います: PDF の図 (`_default` の最終モードなど) と、
  `figures.pptx.text_to_path: true` の PowerPoint の図。`abe` プロファイルは図を本文に埋め込んだままなので使わず、下のクイックスタートも使いません):
  Calibri や游ゴシックなどの専有フォントは**同梱していません**。使用許諾を持っているフォントのファイルを、イメージを作る前に `fonts/` に置いてください。
  置かなくてもイメージは作れ、別のフォントで代替されます。イメージは無いときだけ作られるので、作った後にフォントを足したときは
  イメージを消してください (`docker image rm docx-paper-template-svg-converter`)。次に要るときに作り直されます。
  このイメージを作ると `corefonts` プロジェクトから Microsoft Core Fonts を取得します。**イメージを作ることは、これらのフォントについての
  Microsoft の使用許諾契約 (EULA) に同意することを意味します** (<https://corefonts.sourceforge.net/eula.htm>)。

## クイックスタート

同梱のサンプル原稿をビルドします。リポジトリの最上位で実行してください。
先に結果だけを見たいときは [`samples/`](samples/README.md) のファイルを開いてください (ABE のサンプル論文とその差分を Word で PDF にしたもの、
汎用のサンプルの .docx と PDF)。

```bash
git clone https://github.com/fk506cni/docx-paper-template-abe-public.git
cd docx-paper-template-abe-public

# 1. Build the main conversion image (pandoc, pandoc-crossref, Python, librsvg, LibreOffice)
docker compose -f docker/docker-compose.yml build

# 2. Use the bundled samples (data/dummy/) as the input instead of src/
echo dev > .development

# 3. Generic profile: Markdown -> .docx (the first run also builds the Mermaid image and
#    generates the generic reference.docx)
bash scripts/build.sh
#    -> data/step02_build/main.docx

# 4. Change-highlighted diff between two versions of the manuscript
mkdir -p jank
sed 's/Twenty trials/Twenty-four trials/' data/dummy/main.md > jank/main-new.md
bash scripts/diff.sh data/dummy/main.md jank/main-new.md
#    -> data/step03_diff/main_diff.docx

# 5. Draft package with the generic profile (figures stay embedded)
bash scripts/package.sh --journal _default --mode draft
#    -> data/output/_default/

# 6. The sample paper in src/ is written for ABE. Without .development the input root is src/.
#    ABE needs the society's template: without it the build stops and prints where to get it
rm -f .development
bash scripts/build.sh --journal abe --article-type original || echo "-> place ABETemplate.docx first (next step)"

# 7. Download ABETemplate.docx from https://abe-journal.org/authorinstructions
#    and put it in data/journals/abe/ (git ignores it; do not commit or redistribute it)
cp ~/Downloads/ABETemplate.docx data/journals/abe/ABETemplate.docx

# 8. ABE sample paper: build (two-column layout from the template), then assemble the final package
bash scripts/build.sh   --journal abe --article-type original
bash scripts/package.sh --journal abe --article-type original --mode final
#    -> data/output/abe/ (manuscript.docx, SUBMISSION.md, ...)

# 9. Citation style check: abe.csl against the reference examples in the rules
bash scripts/check-csl.sh

# 10. Rule check of a sample that breaks the rules on purpose
docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
    python3 main/step05_package/validate.py --input-root data/dummy/abe-lint --journal abe --article-type original
```

(コマンドは英語版と同じです。コメントも揃えるため英語のままにしています。7. の `~/Downloads/` は、テンプレートを保存した場所に読み替えてください。)

できたファイルを Word で開いてください。`data/step03_diff/main_diff.docx` では抄録の数字の変更が色付けされています。
`data/output/abe/manuscript.docx` は 1 ページ目が表題ページ、2 ページ目からが行番号と柱 (running title) つきの 2 段組の本文で、
図は本文の中に置かれています。`data/output/abe/SUBMISSION.md` には、アップロードするファイル (Word で PDF にした原稿と書式) の一覧、
規定チェックの結果 (このサンプルでは指摘なし)、投稿前に見直す点が並びます。この手順では `SUBMISSION.md` に注記が 3 つ出ます。
「`manuscript-diff.docx` は別の原稿から作られた」(パッケージが 4. で作った汎用のサンプルの差分を集めたため)・「`src/` の原稿は同梱のサンプル論文
そのもの」・「記入済みの書式の置き場所 `src/forms/` が無い」です。同じ論文 (TJD の挿絵を除いたもの) にダミーの書式を付けたものが `data/dummy/abe/` にあり、8. の 2 つのコマンドに
`--input data/dummy/abe` を付けると、書式がパッケージに集められる様子を見られます。clone した直後の `src/` にはサンプル論文一式 (`main.md`・`ref.bib`・
`cover-letter.md`・図 3 点) が入っているので、書き換えて使う雛形にもなります。9. は照合した本文の引用 17 件と文献 10 行をそれぞれ `OK` と出し、Word の書式 (角括弧・巻の太字) は
確かめていないという注意も出します。書式まで確かめるには、フィクスチャ `data/dummy/abe-csl/` をビルドしてその .docx を `--docx` で渡します
([docs/usage-guide.md](docs/usage-guide.md) §4.1)。10. は要修正 12 件・参考 15 件を出します。

違う版のテンプレートを置くと、SHA-256 が `data/journals/abe/profile.yaml` の `reference_base_sha256` (ver.3 の値) と違うので
ビルドが止まります。新しい版を使うなら、その値を表示された値に書き換えてビルドし直し、出てくる警告と体裁を確かめてください。

### 自分の原稿を始める

```bash
rm -f .development              # the input root is src/
rm -f data/step03_diff/*.docx data/step03_diff/.main_diff.source   # drop the sample diff made above
bash scripts/remove-sample.sh   # remove the sample paper in src/ (only files unchanged from the sample)
cp data/journals/abe/skeleton/main.md src/main.md   # ABE skeleton; fill in the <<...>> fields
```

`scripts/remove-sample.sh` は、中身がサンプルのままのファイルだけを消すので、自分で書いたファイルを消すことは無く、何度回しても害はありません
(`--dry-run` で消すものの一覧だけを出します)。自分の `main.md` の隣にサンプルのファイルが残っていると、最終モードのパッケージは止まります
(サンプルのカバーレター・文献・図が自分の提出物に入らないようにするため)。

ABE に出すなら [docs/usage-guide.md](docs/usage-guide.md) §8 の通し手順に沿い、投稿当日は
[docs/abe-submission-checklist.md](docs/abe-submission-checklist.md) を上から確かめてください。ほかの誌に出すなら、
汎用のサンプルから始めます (`cp data/dummy/*.md data/dummy/ref.bib src/ && cp -r data/dummy/figs/. src/figs/`。
`data/dummy/` のサブディレクトリにある ABE の動作例と試験用のフィクスチャは写しません)。
原稿は `src/` に置いてふつうに commit してください。生成物は `data/` に出て git では無視されます。
学会のテンプレート、reference document、`src/forms/` に置く記入済みの書式も git では無視されます。

## 主なコマンド

| コマンド | 内容 |
|---|---|
| `bash scripts/build.sh [--journal <id>] [--article-type <種別>]` | 図の前処理 → `data/step02_build/main.docx` (`cover-letter.md` と `revise-report.md` があればそれらの docx も) |
| `bash scripts/diff.sh [REVISION \| old.md new.md] [--journal <id>]` | git の revision (既定 `HEAD~1`) または 2 ファイルとの差分 → `data/step03_diff/main_diff.docx` |
| `bash scripts/package.sh --journal <id> --mode draft\|final` | 投稿パッケージ → `data/output/<id>/`。規定チェックも走る |
| `bash scripts/check-figures.sh [--journal <id>] [--figures-dir <dir>]` | 図の解像度と、Word で崩れる SVG の検査 |
| `bash scripts/check-csl.sh [--journal <id>] [--docx <file>]` | 文献の整形結果を期待値のフィクスチャと照合 (既定は `abe` と `data/dummy/abe-csl/`) |
| `bash scripts/check-diff.sh` | 旧版と新版の原稿の対で差分エンジンを確かめる受入テスト |
| `bash data/journals/make-reference.sh <id>` | 雑誌の `reference.docx` を生成 (`profile.yaml` から。`abe` は誌のテンプレートから)。無いときと生成の元が変わったときは `build.sh` と `diff.sh` が実行します |
| `bash docker/mermaid/convert.sh <file.mmd> both` | Mermaid 図を単独で SVG と PDF にする (ビルドは `figs/mermaid/*.mmd` を自分で描画するので不要) |
| `bash scripts/push-win-tools.sh` / `check-pdf-path.sh` / `roundtrip.sh` | Word による PDF 化 (準備 / 診断 / 変換。任意。`roundtrip.sh` は最終提出用のパッケージを Drive の `submission-<journal>/` に置く。その前に、いまの原稿から作ったパッケージかを確かめる。クイックスタートの直後なら `--skip-build` を付ける) |
| `bash scripts/remove-sample.sh [--dry-run]` | 同梱のサンプル論文を `src/` から消す (中身がサンプルのままのファイルだけ) |
| `bash scripts/make-samples.sh --journal _default\|abe [--no-pdf]` | `samples/` の出力のサンプルを作り直す (PDF は任意の Word の変換を使う) |
| `bash scripts/baseline.sh <接尾辞>` / `baseline-abe.sh <接尾辞>` / `scripts/compare-snapshots.py` | ビルド結果の回帰スナップショットとその比較 |

`build.sh`・`diff.sh`・`package.sh`・`check-figures.sh`・`check-csl.sh`・`check-diff.sh`・`remove-sample.sh`・`make-samples.sh`・`baseline.sh`・`baseline-abe.sh` と
PDF 化の 3 本は `--help` で使い方を表示します。スクリプトのメッセージと詳しいガイドは日本語です。

## 構成

```
.
├── src/              # 原稿: main.md, ref.bib, figs/ (+ cover-letter.md, revise-report.md, forms/)
│                     #   clone した直後は ABE のサンプル論文入り (scripts/remove-sample.sh で消す)
├── samples/          # サンプル論文から作った出力の見本 (ABE は PDF、_default は .docx と PDF)
├── data/
│   ├── journals/     # 雑誌プロファイル: _default/ と abe/ (abe/skeleton/ = 原稿の骨格。
│   │                 #   ABETemplate.docx は abe/ に置く)
│   ├── dummy/        # サンプル原稿と検査用のフィクスチャ (.development があるあいだ使う)
│   └── step*/ output/ products/   # 生成物 (git では無視)
├── main/             # 処理コード。パイプラインの段ごとに 1 ディレクトリ
│   ├── 00_setup/     #   共通設定・Lua フィルタ・OOXML の補助
│   ├── step01_figures/  step02_build/  step03_diff/  step04_pdf/  step05_package/
├── scripts/          # 入口 (build / diff / package / 検査 / PDF の往復)
├── docker/           # pandoc・Mermaid・svg-conversion のイメージ (ポートは公開しない)
├── fonts/            # svg-conversion 用の専有フォント (任意。git では無視)
└── docs/             # 詳しいガイド (日本語)
```

## 文書

| 文書 | 内容 |
|---|---|
| [docs/usage-guide.md](docs/usage-guide.md) | 操作ガイド: 図・雑誌・差分・パッケージ・PDF、ABE の通し手順 |
| [docs/journal-abe.md](docs/journal-abe.md) | ABE の規定と学会テンプレートの読み解きと、実装との対応 |
| [docs/abe-submission-checklist.md](docs/abe-submission-checklist.md) | 投稿当日に 1 枚で見るチェックリスト |
| [docs/architecture.md](docs/architecture.md) | 処理の流れと設計上の判断 |
| [docs/profile-schema.md](docs/profile-schema.md) | `profile.yaml` の全キー・既定値・読み手 |
| [docs/design-fullarea-diff.md](docs/design-fullarea-diff.md) | 構造を保つ差分のしくみ |
| [docs/migration-latex.md](docs/migration-latex.md) | 既存の LaTeX 原稿を本テンプレートへ移す |
| [docs/roundtrip-windows-watcher.md](docs/roundtrip-windows-watcher.md) | Word による PDF 化の配置と診断 |
| [CLAUDE.md](CLAUDE.md) | 規約の短い版 (AI のコーディング支援も読む) |

## サンプル原稿

`src/` と `data/dummy/` の原稿は明らかな作り話です。<https://github.com/fk506cni/jami-pandoc-public> の
「とてつもない予感」(TJD/THS) の物語のパロディで、著者・機関・結果はすべて架空です。実際の原稿が無くても
すべての機能をビルドして確かめられるように置いています。`src/` の論文は ABE のサンプル (`data/dummy/abe/` には、そこから TJD の挿絵を除いた同じ論文を検査用に置いています) で、
[`samples/`](samples/README.md) にはそれと汎用のサンプルから作った出力があります。`data/dummy/abe/forms/` の書式は学会の書式ではなく、置き方を示すための架空のものです。

## 制限

- **PDF 化には Windows と Microsoft Word が要ります。** 無くてもすべての .docx はできますが、PDF はできません。
- **ABE の体裁は学会のテンプレートに依存します。** テンプレートが改版されると、新しい版を受け入れる (クイックスタートの最後の段落) まで
  ビルドは止まり、後処理が合わなくなることがあります。スタイルの欠けと見出しの自動番号の欠けは、ビルドのたびに警告します。
- **`[100]` 以降の文献**は番号だけでぶら下げの字下げの幅を超えるので、1 行目の本文の頭が `[1]`〜`[99]` より右にずれます。
- **差分**: 段落を動かすと「削除 + 追加」として示されます。セルを結合した表は対応づけが不完全になることがあります。
  文献リストは差分ではなく作り直します。語の間に空白の無い文 (日本語など) は語ではなく句の単位で比べます。
  削除した文の中の、同じく削除した図表・式への参照は `¿fig:label?` のように出ます (新しい版に参照先が無いため)。
- **テキストボックス** (`.textbox`) はページと位置で置くので、2 段組では Word の PDF で位置を確かめて手で合わせてください。
- **図**: 解像度を保証するのは SVG / PDF から生成した画像だけです。自分で置いたラスタ画像はそのまま複製されます。
  SVG として正しくても Word や PowerPoint で崩れるもの (複数の SVG を 1 ファイルに連結したもの、色を `hsl()` で書いたもの) があり、
  `scripts/check-figures.sh` が注意として一覧に出します。
- **規定チェックは補助で、保証ではありません。** 英語の質・既発表かどうか・転載の許諾・書式の中身は機械では確かめられません
  (チェックリストを参照)。
- **同梱する雑誌プロファイルは 2 つです。** ほかの誌は `_default` のプロファイルを写して足します (操作ガイドを参照)。

## ライセンス

本リポジトリのコードは [MIT License](LICENSE) で公開しています。
同梱の CSL の引用様式 2 本は CC BY-SA 3.0 です。Word の reference document と学会のテンプレートは同梱していません。
汎用の reference document は手元で pandoc の既定データから、ABE のものは取得したテンプレートから生成します。
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照してください。

本テンプレートで書いてビルドした文書は、あなた自身の著作物です。
