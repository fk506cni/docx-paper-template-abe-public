# 操作ガイド (usage-guide.md)

clone してから投稿パッケージを作るまでの手順をまとめる。設計と理由は [`docs/architecture.md`](architecture.md)、
`profile.yaml` のキーは [`docs/profile-schema.md`](profile-schema.md)、原稿の書き方の規約は [`CLAUDE.md`](../CLAUDE.md)、
差分の仕組みは [`docs/design-fullarea-diff.md`](design-fullarea-diff.md)、PDF 変換の Windows 側の配置は
[`docs/roundtrip-windows-watcher.md`](roundtrip-windows-watcher.md) にある。

> **Advanced Biomedical Engineering (ABE) に投稿するなら → [§8 ABE へ投稿する (通し手順)](#8-abe-へ投稿する-通し手順)。**
> 学会テンプレートの置き方から投稿・改訂までを 1 本につないである。投稿当日に 1 枚で確認する表は
> [`docs/abe-submission-checklist.md`](abe-submission-checklist.md)、規定の読み解きと実装の対応は
> [`docs/journal-abe.md`](journal-abe.md)。
>
> **既存の LaTeX 原稿を書き起こすなら → [`docs/migration-latex.md`](migration-latex.md)。**

本テンプレートは日本生体医工学会 (JSMBE) とも *Advanced Biomedical Engineering* の編集部とも関係が無く、学会・誌が作成・承認・確認した
ものではない (公式のテンプレートではない)。規定は変わりうるので、投稿の前に誌の
[Instructions to Authors](https://abe-journal.org/authorinstructions) で確かめること。

各スクリプトの入力ルート (`INPUT_ROOT`) は `.development` マーカーの有無で切り替わる:

| `.development` | 入力ルート | 用途 |
|---------------|-----------|------|
| 有り (`echo dev > .development`) | `data/dummy/` | 同梱のサンプル原稿で動作を確かめる |
| 無し (`rm .development`) | `src/` | 自分の原稿 |

環境変数 `INPUT_ROOT=...` か `--input <dir>` でも上書きできる (優先順は 環境変数 > `--input` > `.development`)。

---

## 0. 初回セットアップ

```bash
git clone <このリポジトリの URL> my-paper && cd my-paper
docker compose -f docker/docker-compose.yml build    # pandoc イメージをビルド
                                                     # mermaid / svg-conversion は初めて使うときに自動でビルドされる
echo dev > .development                              # まず同梱のサンプルで確かめる (入力ルート = data/dummy)
```

動作確認 (汎用の投稿フォーマット `_default` で通す。学会テンプレートは要らない):

```bash
bash scripts/build.sh                                # → data/step02_build/main.docx
bash scripts/package.sh --journal _default --mode draft   # → data/output/_default/
```

**Word のテンプレート `reference.docx` は同梱していない**。初めて `build.sh` / `diff.sh` を回したときに、`_default` のものが
pandoc の既定データと `profile.yaml` から自動で生成される (`-- data/journals/<id>/reference.docx が無いので生成します` と表示される)。
手で作り直すときは `bash data/journals/make-reference.sh <id>`。生成物は何度作っても同じものになる。

**ABE の体裁は学会テンプレート `ABETemplate.docx` から作る**。テンプレートは学会の配布物なので同梱しておらず、
利用者が学会サイトから取って置く (§8.1)。置くまでは `--journal abe` の build / diff は取得元を出して止まるが、`_default` の動作には
影響しない。

---

## 1. 新しい論文を始める

clone した直後の `src/` には、ABE の Original Paper の体裁のサンプル論文 (架空の論文。`data/dummy/abe/` の動作例に TJD の挿絵を足したもの) が入っている。
そのまま `bash scripts/build.sh --journal abe --article-type original` で組める見本で、書き換えて使ってもよい。
別の原稿から始めるときは、先に `bash scripts/remove-sample.sh` でサンプルを消す (中身がサンプルのままのファイルだけを消し、
書き換えたファイル・自分のファイルは残す。`--dry-run` で一覧だけを出す)。自分の `main.md` の隣にサンプルのファイル
(カバーレター・回答書・文献・図・ダミーの書式) が中身もそのまま残っていると、最終モードの package は止まる (`src/` のサンプル論文と、
`src/` に写した `data/dummy/`・`data/dummy/abe/` の動作例が対象。リンクは数えず、消さない)。出力の見本は `samples/` (`samples/README.md`)。

```bash
bash scripts/remove-sample.sh                 # src/ のサンプル論文を消す
cp data/dummy/*.md data/dummy/ref.bib src/   # 汎用のサンプルの原稿・文献・カバーレター・回答書を src/ へ複製
cp -r data/dummy/figs/. src/figs/             # 図
rm -f .development             # 入力ルートを data/dummy → src に切り替える
$EDITOR src/main.md            # 自分の原稿に書き換える
```

**投稿先が ABE と決まっているなら、汎用サンプルではなく原稿骨格から始める** (§8.2)。骨格は規定の節の並び
(表題ページ → 番号つきの本文の節 → 番号なしの Conflicts of interest / Ethics declaration / Acknowledgements → References) を
記入式で持つので、書き漏らしが起きない。

```bash
bash scripts/remove-sample.sh                                       # src/ のサンプル論文を消す
cp data/journals/abe/skeleton/main.md         src/main.md
cp data/journals/abe/skeleton/cover-letter.md src/cover-letter.md   # 任意
#  定型の記述 (利益相反・倫理・資金・AI ツールの開示など) の文例は data/journals/abe/skeleton/statements.md (参照用。ビルドの対象外)
#  記入済みの動作例:  bash scripts/build.sh --journal abe --article-type original --input data/dummy/abe
```

> `data/dummy/` を丸ごと `cp -r data/dummy/. src/` で写すと、サブディレクトリ (`abe/` `abe-csl/` `abe-lint/` `regression/`) の
> 動作例とフィクスチャも `src/` に入り、`src/abe/forms/` のダミーの書式は `.gitignore` の `src/forms/` に当たらないので追跡に入る。
> 上のように汎用のサンプルのファイルと図だけを写す。

`src/main.md` の要点 (詳しくは `CLAUDE.md` の「原稿執筆の規約」):

- **タイトル / 著者 / 所属 / 抄録 / キーワードは YAML メタではなく `custom-style` Div** で書く
  (構造保持 AST 差分がこれらを温存し、中身を差分にするため):
  ```markdown
  ::: {custom-style="Title"}
  論文タイトル
  :::
  ```
- 引用は `[@bibkey]`、文献は `src/ref.bib` に集める。
- 図の参照は `[@fig:foo]`、表の参照は `[@tbl:bar]`、式の参照は `[@eq:baz]` (日本語の文中でも角括弧の形で書く)。
  `Fig. 1` / `Table 1` / `Eq. 1` の語は自動で付くので、`Fig. [@fig:foo]` とは書かない (`Fig. Fig. 1` になる)。
- **見出しに番号を書かない** (`# Introduction`)。番号が要る誌は Word のテンプレートの見出しのスタイルが自動で番号を付ける (ABE)。
  番号の要らない節 (Abstract・謝辞・文献など) は `{.unnumbered}` を付ける。
- **段組を原稿に書かない**。2 段組は誌の `profile.yaml` が後処理で付ける。段の幅を超える図は `{.wide}`、表などは `::: wide` の
  Div で囲む (段抜き。段組の無い誌では何もしない)。同じ原稿を `--journal abe` でも `--journal _default` でも組める。

---

## 2. 図を追加する

図のソースは `src/figs/` に置く。**本文からは常に `.svg` で参照する** (PDF 図も。前処理が SVG に変換するため)。

### 2.1 SVG 図 / PDF 図

```bash
cp my-figure.svg src/figs/fig-foo.svg     # PDF なら src/figs/fig-foo.pdf を置く
```

本文 (`.pdf` を置いた場合も `.svg` で参照する):

```markdown
![図のキャプション](figs/fig-foo.svg){#fig:foo}
```

- 前処理 (step01) が SVG の文字の切り取りを補正し、PDF を SVG に変換し、PNG フォールバックを作る。
  `.pdf` のまま参照すると埋め込みが壊れるので、ビルドがエラーで止める。
- ビルドは docx に **SVG をネイティブで埋め込む**。**Microsoft 365 / Office 2019 以降**はベクターで表示し、
  Office 2016 以前とその他のビューアは PNG フォールバックを表示する。
- **PNG フォールバックは要求 dpi (既定 300) を満たすように作られる**。SVG の公称サイズから必要な画素数を計算して
  ラスタ化し、実画素数を検算する (足りなければエラーで停止)。PNG には物理解像度 (pHYs) も書く。
  確かめるときは `bash scripts/check-figures.sh`。
- **SVG ルートの `width` / `height` は「図の公称サイズ」として 2 つのことを決める**: docx 上の表示寸法と、
  ラスタ化するときの画素数 (公称サイズ × 要求 dpi)。
  - 物理単位 (`80mm` / `144pt` / `2in`) で書けば、それがそのまま図の実寸になる。
  - 単位なしと `px` は **CSS px = 1/96 inch** とみなす (`320` → 3.33 inch)。
  - PDF 図は MediaBox の寸法 (pt) をそのまま公称サイズにする。
  - **印刷したい幅より小さい公称サイズで作ると、その幅で刷ったときの実効解像度が要求 dpi を下回る**。
    300 dpi を求める誌に出す図は、`width="80mm"` のように物理単位で幅を書くのが安全。
  - 物理単位で書くと docx 上の図はその実寸になる。見た目の大きさを変えたいときは原稿側で `{width=...}` を付ける
    (`![..](figs/fig-foo.svg){#fig:foo width=100%}`)。
  - 本文幅を超える図は pandoc が本文幅に縮める (A4・左右の余白 25 mm なら約 159.8 mm)。同じ画素数を狭い幅に
    置くので、実効解像度は上がる側に動く。
  - **2 段組の誌 (ABE) では段の幅が上限になる**。段に置く図は段の幅 (ABE は 83 mm) まで、段抜き (`{.wide}`) の図は
    本文幅 (ABE は 180 mm) まで。段の幅を超える段の図は build が段の幅に縮めて警告する (図の中の文字も同じ比で縮むので、
    警告が出たら `{.wide}` を付けるか、段の幅で作図し直す)。
    ```markdown
    ![本文幅で見せたい図。](figs/fig-wide.svg){#fig:wide .wide}
    ```
- **寸法を持たない SVG** (`width` / `height` も `viewBox` も無い) は、草稿のビルドは警告つきで通るが、
  提出図の生成 (`package.sh --mode final`) はエラーで止まる。SVG のルートに寸法を書けば直る。
- **ラスタ図 (PNG / JPEG / TIFF) を直接参照してもよい**: `src/figs/` に置き `![..](figs/photo.png){#fig:photo}` と書く。
  前処理は変換せずにそのまま使う。
  - **自分で置いたラスタ図は解像度の保証の対象外**である。そのまま複製されるので、解像度は執筆者が担保する。
  - `check-figures.sh` はこれらを**不合格ではなく「注意」として一覧に出す** (ツールでは作り直せないため)。
    PNG なら実画素数と pHYs を表示するので、`実画素数 ÷ 印刷したい幅 (inch)` が要求 dpi 以上かを確かめる。
    JPEG / TIFF は pHYs を持たないので機械では判定できない。
  - 目安: 幅 83 mm (約 3.27 inch) の段に置く図を 300 dpi にするには幅 **981 画素以上**、本文幅 180 mm (約 7.09 inch) なら
    **2126 画素以上**が要る。
- **複数の SVG を 1 ファイルに連結しない**。多パネル図は作図側で 1 枚として出力する (R なら cowplot / patchwork などで
  まとめてから 1 回だけ書き出す)。次の 2 つは SVG としては正しく、ブラウザでも PNG でも正常に見えるのに、
  Word / PowerPoint では崩れる:
  - **svglite の出力を 2 つ入れた SVG** (`<g class='svglite'>` が 2 個以上) — Word が文字だけを片方のパネルの位置に
    寄せて描く (図形は正しい位置のまま)。包み方を変えても直らない。
  - **SVG の中で `id` が重複している** — svglite の `clipPath` の `id` は座標から作られるので、寸法を揃えた 2 つの出力を
    連結すると一致し、片方のパネルが誤った範囲で切り取られる。

  `check-figures.sh` (図ツリー) はこの 2 条件を「注意」として出す。**それ以外の崩れ方は検出できないので、
  roundtrip の PDF (§6) や PowerPoint で図を拡大して目で見ること**。
- **塗り・線の色を `hsl()` で書いた図形は Word / PowerPoint で黒くなる**。CSS のクラスで塗っても `fill` 属性に
  書いても同じで、色の書き方が原因である (16 進 `#rrggbb` なら正常)。本テンプレートの Mermaid の経路 (§2.2) は
  16 進に直してから出す。別の道具で作った SVG を置いた場合は `check-figures.sh` が「注意」に出すので、色を 16 進で
  書き直す。
- **番号つきの図 (`{#fig:..}`) は 1 段落に 1 図**で書く。1 段落に番号つきの図を複数置くと、pandoc-crossref が
  図として扱わず、参照が `Undefined cross-reference` になる (番号の要らない装飾画像は同じ段落に複数置いてよい)。
- **題と凡例を分けたいとき**は、キャプションを題 (短い一文) に留め、凡例を直後の Div に書く
  (`CLAUDE.md` の「図表の題と凡例の書き分け」)。題と凡例に別々の語数上限がある誌では必須。表も同じ書き方で、
  docx では題が表の上・凡例が表の下に出る (表の凡例を表の上に置く誌 = ABE では、後処理が題と表の間へ移す。原稿の書き方は同じ)。
  ```markdown
  ![Processing pipeline from the record to the reviewed event list.](figs/fig-foo.svg){#fig:foo}

  ::: {custom-style="Legend" for="fig:foo"}
  Rectangles denote processing stages. EHR, electronic health record.
  :::
  ```
  - **凡例は段落だけで書く**。とくに**多パネル図の凡例を `(A) …` で始めない** — pandoc は段落の先頭の
    `(A)` / `A)` / `a.` / `(i)` などを番号つきリストとして読むので、凡例が `Legend` 段落にならない
    (図の題と凡例を References の後へ集める誌では、集約から外れて本文に取り残される)。パネルの説明は
    `Panel A shows … Panel B shows …` のように文で書く。`package.sh` の規定チェックが要修正として出す。

### 2.2 Mermaid 図 (フロー図・構成図)

```bash
$EDITOR src/figs/mermaid/flow.mmd          # .mmd が一次ソース
```

本文からは生成される `.svg` を参照する (前処理が `.mmd` から SVG と PDF を作る):

```markdown
![システム構成図](figs/mermaid/flow.svg){#fig:arch}
```

`.mmd` から作った SVG / PDF は作り直せるので git では追跡しない (`.gitignore`)。ビルドの前処理が毎回 `.mmd` から作るので、
**ふだんは単独で描かなくてよい**。見た目だけを確かめたいときは、`.mmd` を `jank/` などへ写してそこで描く
(`bash docker/mermaid/convert.sh jank/flow.mmd both`。同じ名前の出力が既にあると止まるので、描き直すときは `--force`)。
`figs/mermaid/` の中で単独に描いた `.svg` / `.pdf` が残っていても、前処理は同じ名前の `.mmd` から作り直した図を使い、
残骸を読み飛ばして「単独描画の残骸を無視しました」と警告する (残骸は消してよい)。

- **ラベルは SVG の文字 (`<text>`) で出す**。HTML のラベル (`foreignObject`) は Word と PNG フォールバックで消える
  (ブラウザでは正常に見える) ため、`docker/mermaid/config.json` の最上位に `"htmlLabels": false` を置いてある。
  `config.json` を書き換えるときもこの行は消さないこと (`convert.sh` は生成した SVG に `foreignObject` が残っていると
  警告する)。
- `config.json` は `convert.sh` が実行時に読み込むので、書き換えてもイメージの再ビルドは要らない。
- **テーマの色は変えてよい**。Mermaid は色を変えるとサブグラフの枠などの色を `hsl()` で出すが、`convert.sh` の後処理
  (`docker/mermaid/postprocess-svg.js`) が 16 進に直す。**Mermaid Live などで作った SVG を `figs/` に直接置くと
  この後処理を通らない**ので、`.mmd` を `figs/mermaid/` に置いてこの経路で作ること。
- ラベルが箱の中心より少し下に見えることがある。Mermaid のラベル配置そのもので、ブラウザでも Word でも同じに見える。

### 2.3 確認

```bash
bash scripts/build.sh
# ログに「SVG ネイティブ埋込: ... -> word/media/svgN.svg」が図の数だけ出れば埋め込めている
bash scripts/check-figures.sh                    # PNG フォールバックの画素数を SVG の公称サイズから検算する
```

---

## 3. 差分を出す (査読対応)

`scripts/diff.sh` は**論文の全領域** (タイトル / 著者 / 抄録 / キーワード / 本文 / 表 / 脚注 / テキストボックスの中の表) を
構造保持 AST 差分で突き合わせ、追加 = 青・削除 = 赤の取り消し線の docx を作る。

```bash
# 直前のコミットとの差分 (旧版 = HEAD~1 の main.md、新版 = 作業ツリー)
bash scripts/diff.sh HEAD~1

# 任意の revision との差分 (初回投稿時のタグなど)
bash scripts/diff.sh v1-submitted

# 明示した 2 ファイルの差分 (どちらも実在するファイル)
bash scripts/diff.sh old.md src/main.md
#  → data/step03_diff/main_diff.docx
```

- **雑誌の体裁で出すときは build と同じ `--journal` (と `--article-type`) を付ける**
  (`bash scripts/diff.sh v1-submitted --journal abe --article-type original`)。ABE では 2 段組・柱・番号なしの見出し・
  図表の題・式番号の右寄せが build と同じく掛かる。
- revision の形で使うには、`<入力ルート>/main.md` がその revision に存在している必要がある (新しく作ったファイルは
  2 ファイルの形を使う)。初回投稿の版にタグを付けておくと、改訂のたびに同じ旧版と比べられる。
- 図は新版の図ツリー、文献は新版の `ref.bib` で解決する。
- 差分に出るもの: 語単位の書き換え (大文字小文字だけの変更も出る)、表のセルの中、脚注 (参照の記号と本文に色が付く)、
  数式とリンク (相互参照) の削除と追加。番号つきの式を書き換えると、旧の式 (赤・番号なし) と新の式 (青・番号つき) の
  2 段落になる。図表・式のラベルと題の両方を書き換えても、同じ図表・式とみなせるとき (表は題と中身が似ている・図は画像か題が
  同じ・式は TeX が似ている) は付け替えとして扱い、変えていない文の参照は壊れない。既存の表を改訂で `::: wide` で囲んで
  段抜きにしても、表はまるごとの削除 + 追加にならず中身の差分だけが出る。
- 既知の制限 (詳しくは `docs/design-fullarea-diff.md` §7): 段落の「移動」は削除 + 追加として出る。コードブロック・
  水平線・生 OOXML の変更は着色せず新旧を併記する。見出しのレベルだけを変えると、旧い見出しの削除 + 新しい見出しの追加として
  着色される。**消した図表・式を参照する消した文の参照は `¿fig:old?` のようになる** (同じとみなせない差し替え — 画像のファイルも
  ラベルも変えて題も同じでない図・TeX の記号が大きく違う式・題が似ていても中身の違う表 — も同じ)。表の列の増減では後ろの列が
  ずれうる。引用番号・相互参照番号・文献リストは再生成され、差分にはならない。**語の間に空白の無い言語 (日本語など) の本文は、
  変更が語単位ではなく句ごとの削除 + 追加になりうる** (英語の本文は語単位)。
- 差分エンジンを直したときは `bash scripts/check-diff.sh` を回す。旧版と新版の対 (`data/dummy/regression/diff/` の 10 対) を
  差分 docx にし、色の位置と文字・番号と参照に `¿` が残らないことなどを照合する (`_default` と、学会テンプレートを置いていれば
  `abe` で、合わせて 110 項目。`--only <名前>` / `--keep <dir>` / `--no-abe`)。
- リバイスレポート (回答書) は `src/revise-report.md` に書けば、`build.sh` が同じ仕組みで docx にする。誌の体裁 (`--journal`) で
  組まれ、ABE では 1 段組・行番号なし・柱は空・見出しの自動番号なしになる。見本は `data/dummy/abe/revise-report.md` と
  `data/dummy/revise-report.md`。
- **改訂の期限は誌による** (ABE は判定から 3 か月。`docs/journal-abe.md` §7)。査読コメント・回答書・編集部とのやりとりは
  秘密に保つ誌が多い (ABE の規定にも通信の秘密の定めがある) ので、公開のリポジトリや共有の場所に置かない。

---

## 4. 新しい投稿先 (雑誌) を追加する

投稿規定はプロファイルに閉じ込め、本文 (`src/main.md`) は雑誌に依存させない。例として架空の誌
`example-journal` を足す:

```bash
mkdir data/journals/example-journal
cp data/journals/_default/profile.yaml data/journals/example-journal/   # 1. 雛形の profile.yaml を写す
$EDITOR data/journals/example-journal/profile.yaml                      # 2. 投稿規定に合わせて書き換える
bash data/journals/make-reference.sh example-journal                    # 3. 体裁を焼き込んだ reference.docx を作る
bash scripts/build.sh --journal example-journal                         # 4. その誌の体裁でビルドする
```

- 2 では `name` と、体裁 (`line_spacing` / `line_numbers` / `page_numbers` / `font` / `font_size` / `margins` /
  `paper_size` / `text_styles.*`)・図 (`figures.*`)・表 (`tables.*`)・上限 (`limits.*`) を規定に合わせる。キーの一覧と省略したときの動きは
  [`docs/profile-schema.md`](profile-schema.md)。
- `csl:` は、誌の引用様式の CSL を `data/journals/example-journal/` に置いたらそのファイル名、無ければ `null` にする。
  `null` だと `_default` の AMA 系を継承し、build / diff が毎回「csl 未指定。_default (AMA 11th) を継承します」と知らせる
  (規定と違う引用様式のまま提出しないため)。CSL の照合は §4.1。
- 3 は省いてもよい。`reference_doc: reference.docx` (雛形のまま) なら、ファイルが無いときに build / diff が自動で作る。
- **体裁は `reference.docx` に焼き込まれる**。`profile.yaml` の体裁を後から変えたら、**3 を回し直す**。回し直さないと
  build と規定チェックが「`reference.docx` の体裁が `profile.yaml` と食い違っています (line_spacing: profile=1.5 !=
  reference.docx='double')」のように警告する。**比べるのは用紙・余白・行間・級数・行番号などで、`text_styles` は比べない**ので、
  `text_styles` を変えたときは警告が出なくても回し直すこと。
- 生成した `reference.docx` を git で追跡するかは自由 (無くても build / diff が作る)。追跡するなら
  `git check-ignore -v data/journals/example-journal/reference.docx` で無視されていないかを確かめ、無視されていれば
  `.gitignore` に `!data/journals/example-journal/reference.docx` の行を足す。

**雑誌が Word のテンプレート (docx) を配るなら、それを雛形にできる** (ABE の `data/journals/abe/` が実例)。
テンプレートを `data/journals/<id>/` に置き、`profile.yaml` に `reference_base: <ファイル名>` (と任意で指紋 `reference_base_sha256`・
取得元 `reference_base_url`) を書く。

- `make-reference.sh <id>` はテンプレートを雛形にして**体裁を焼き込まずに** `reference.docx` を作る。足すのは pandoc が使う
  スタイルの別名 (テンプレートに無いものだけ)・見出しの番号定義の修正などで、見本の文章と文書を特定しうる情報 (作成者・
  変更履歴・コメント・文書 ID など) は消し、節の骨組みだけを残す。build / diff は生成の元 (テンプレート・`profile.yaml`・
  生成処理) が変われば作り直し、テンプレートが無ければ取得元を出して止まる。
- この誌では体裁キー (`font` / `margins` など) は**照合用** (テンプレートが改版されて値が変わったことの検知) になり、
  `profile.yaml` に書いたキーだけを比べる。`margins` は辺ごとの辞書 (`{top: 25mm, bottom: 20mm, left: 15mm, right: 15mm}`) でも書ける。
- 指紋 `reference_base_sha256` を書いておけば、違う版のテンプレートを置いたとき `make-reference.sh` が止まる
  (build / diff も止まる)。新しい版を使うなら、その値を表示された値に書き換え、出てくる警告と roundtrip の PDF の見た目を確かめ直す。
- 生成のときの警告 (テンプレートに無いスタイルを受け皿で埋めた・見出しの番号定義が想定と違う・想定外のパートを外した など) は
  `data/journals/<id>/.reference.warnings` に記録され、作り直さずに使うときも build・diff のたびに出る。
- **雑誌の配布物とそれから作った `reference.docx` は git で追跡しない** (再配布しないため)。`make-reference.sh` は、テンプレートと
  `reference.docx` が git で追跡されている・無視されていなければ警告する。
- 2 段組・柱・番号なしの見出し・誌別の図表の題などが要るなら、`layout` / `header` / `headings` / `crossref` などのキーを足す
  ([`docs/profile-schema.md`](profile-schema.md) の §3.11〜§3.14)。

`profile.yaml` の主なキー (全項目は `docs/profile-schema.md`):

| キー | 例 | 説明 |
|------|-----|------|
| `line_spacing` / `line_numbers` | `double` / `continuous` | 行間 / 行番号 (`reference.docx` に焼き込む) |
| `page_numbers` | `true` | フッタの中央にページ番号を入れる (既定 `false`。`reference.docx` に焼き込む) |
| `font` / `font_size` / `margins` / `paper_size` | `"Times New Roman"` / `12pt` / `25mm` / `a4` | 体裁 (`reference.docx` に焼き込む。テンプレートを雛形にする誌では照合用) |
| `text_styles.uniform_size` / `heading_color` / `uniform_line_spacing` | `true` / `black` / `true` | 題・見出し・抄録も本文の級数にそろえる / 題・見出しのテーマ色を外す / 段落スタイルごとの行送りを外す (省略すると pandoc の既定のまま。`reference.docx` に焼き込む) |
| `reference_base` | `ABETemplate.docx` | 雑誌が配るテンプレートを雛形にする (体裁を焼き込まない) |
| `figures.embed` | `true` / `false` | `package.sh` の既定のモード。`true` → 草稿 (図を埋め込む) / `false` → 最終 |
| `figures.separate` | `true` / `false` | 最終モードで図を本文から外すか (`false` = 図を本文に埋め込んだまま提出用にする。ABE) |
| `figures.formats` | `[pdf]` / `[pptx, png]` | 図を外す誌の最終提出の図の形式。先頭が主形式。作れるのは `pdf` / `png` / `pptx` |
| `figures.dpi` / `figures.font_handling` | `300` / `outline` | ラスタ図の解像度 / PDF 図の文字の扱い (`outline` = アウトライン化 / `embed` = 埋め込み) |
| `tables.placement` | `inline` / `end` / `separate` | 最終モードで表を本文に残す / 本文の末尾へ移す / 1 表 1 ファイルで出す (§5.3) |
| `limits.word_count` / `abstract_words` / `references` | `4000` / `350` / `null` | 規定チェックの上限 |
| `abstract.structured` | `true` / `false` | 構造化抄録か |
| `layout.columns` | `2` | 本文を段組にする (表題部は 1 段組のまま) |
| `numbering.figure` | `"Figure %d."` | 分離した図のファイル名の書式 (`Figure1.pdf`) |

**必須節の多い誌には原稿骨格 `skeleton/` を添えられる** (任意)。ビルドの対象ではなく、執筆の出発点として写して使う
雛形である (`cp data/journals/<id>/skeleton/main.md src/main.md`)。同梱の例は `abe/skeleton/`
(`main.md` / 任意の `cover-letter.md` / 定型の記述の文例集 `statements.md`)。骨格は写した直後でもビルドが通り、記入欄 `<<...>>` は
規定チェックが要修正として出す。骨格に `README.md` は置かない (`cp -r skeleton/. src/` で `src/README.md` を上書きするため)。

### 4.1 引用様式 (CSL) を自前で用意したときの確認

引用様式の食い違いは目で見ても気づきにくく (括弧の形・ページ範囲の桁・`et al` の閾値・巻の太字など)、
規定と違うと全文献の書き直しになる。規定に**出力例が載っているなら機械で照合する**。

```bash
# フィクスチャ: <dir>/{main.md, ref.bib, expected.txt} の 3 点 (+ 任意で check.yaml)
#   expected.txt = 規定の出力例を 1 行 1 文献で写したもの (# で始まる行はコメント。太字は **…**、斜体は *…*)
#   --fixture を省くと data/dummy/<id>-csl を使う
bash scripts/check-csl.sh --journal <id> --fixture data/dummy/<id>-csl

# docx の OOXML まで見る (上付き・角括弧・巻の太字など、文字列の比較では分からない体裁)
bash scripts/build.sh --input data/dummy/<id>-csl --journal <id>
bash scripts/check-csl.sh --journal <id> --fixture data/dummy/<id>-csl --docx data/step02_build/main.docx
```

誌ごとに違う点はフィクスチャの `check.yaml` に書く (キーの意味は `main/step02_build/check_csl.py` の冒頭):
`journal` (取り違えの防止) / `official_examples` (`expected.txt` の先頭 N 行が規定の例) / `citation_form` (`brackets` = 角括弧で
上付きにしない / `superscript` = 上付き。`--docx` のときに実測する) / `citations` (本文の引用の期待値。書けば 1 件ずつ照合する) /
`bibliography_label` (文献の番号の形。`"[{n}]"` なら、docx の文献の段落が「`[1]` + 区切り + 本文」で始まることも照合する)。
`--docx` のときは docx の文献の段落の文字と太字・斜体も `expected.txt` と照合する。

ABE の実例が `data/journals/abe/abe.csl` + `data/dummy/abe-csl/` にある (`check-csl.sh` の `--journal` と `--fixture` の既定はこの 2 つ。
規定の公式例 6 件 + 本テンプレートの判断の回帰ガード 4 件 + 本文の引用 17 件。`docs/journal-abe.md` §4)。
食い違ったときは、文字列の差を行内の差分とコードポイントで表示する。`--docx` には**フィクスチャからビルドした docx** を渡す
(原稿の docx を渡すと、引用の件数がフィクスチャと合わずに NG になる)。フィクスチャのビルドは `data/step02_build/main.docx` を
上書きするので、照合のあとで原稿をビルドし直す。

**`ref.bib` の側で気をつけること** (pandoc の BibTeX の読み方による。自動化できない):

- 誌名は雑誌が指定する形 (ABE なら PubMed の略記) で `journal` に**直接**書く。CSL には正式誌名から略誌名への変換が無い。
- 題の固有名詞は**波括弧で保護**する (`{Cancer Institute Hospital}`)。保護しないと、pandoc が英語の題を
  センテンスケースに直して規定の例と食い違う。Title Case のまま出したい書名・会議録の名前は全体を保護する
  (`{{Principles of Medical Engineering}}`)。
- オンラインの文献には `url` と `urldate` (参照した日) を持たせる。
- 和文の文献には **`langid = {japanese}`** を書く (BibTeX の `language` は pandoc に捨てられる)。`langid` は pandoc が題を
  センテンスケースに直すのも止める。言語の注記 (`(in Japanese)` など) を出すかは引用様式による (`abe.csl` は出さない)。
- **英語の文献には `langid` を書かない**のが安全である。引用様式によっては、`langid` (pandoc が CSL の `language` に写す) が
  **あるだけで**言語の注記を付ける。書誌管理ソフト (Zotero / Better BibTeX など) は英語の文献にも `langid = {english}` を
  付けて書き出すことが多いので、英語の文献からは消しておく。和文以外の非英語の文献は、`langid` を残したまま (消すと題の
  大文字が崩れる) `note = {in German}` のように言語を書く。

---

## 5. 投稿パッケージを作る

雑誌プロファイルに従って提出物を整形・命名し、`data/output/<id>/` に集める。

```bash
# 雑誌の体裁を本文に反映するため、先にその誌でビルドする
bash scripts/build.sh --journal <id>

# 草稿パッケージ (図を docx に埋め込んだまま)
bash scripts/package.sh --journal <id> --mode draft

# 最終提出パッケージ (図を外す誌では、本文に [Figure N about here] を残して図を figures/ に出す)
bash scripts/package.sh --journal <id> --mode final
#  → data/output/<id>/ に manuscript.docx (+ figures/) / revise-report.docx / cover-letter.docx
#     (+ 差分があれば manuscript-diff.docx。誌によっては SUBMISSION.md・supplementary/・forms/)
```

- `--build` を付けると前段のビルドも一緒に回す: `package.sh --journal <id> --mode final --build`。
- `--mode` を省くと `profile.figures.embed` で決まる (`true` → draft / `false` → final)。
- **図を本文に埋め込んで提出する誌** (ABE。`figures.separate: false`) は、最終モードでも図を外さない —
  `manuscript.docx` は `main.docx` そのもので、`figures/` と `CAPTIONS.md` は作らない。提出用としての照合 (下) と
  `SUBMISSION.md` はそのまま効く (手順は §8.4)。
- **提出用 (最終モード) の `package.sh` は、build したときの誌・`profile.yaml`・`reference.docx` が今と違えば止まる**
  (`--journal` の付け忘れで既定の `_default` の体裁の本文が提出物になるのを防ぐため。草稿モードは注意だけ)。build の後に
  `profile.yaml` やテンプレートを変えたら、`package.sh … --build` で組み直す。
- `.textbox` の中の図は分離せず、本文に残す (テキストボックスは本文の流れの外に置くフロート図表のため)。

### 5.1 図の形式

図を本文から外す誌 (`figures.separate: true`。既定) で、最終モードの図をどの形式で出すかを決める。図を埋め込んだまま出す誌
(ABE) には関係しない。

- 主形式は `figures.formats` の先頭 (`--format` で上書きできる)。**作れるのは `pdf` / `png` / `pptx` の 3 つ**で、
  `eps` → pdf / `tiff` → png は**警告つきで代わりに作る**。それ以外 (綴りの誤りを含む) は**エラーで止まる**
  (作れない形式を黙って別の形式にしない)。代わりの形式が誌の受入形式 (`submission.figure_formats`) に無ければ、それも止まる。
- 受入形式外の形式を `--format` で明示したときも止まる (`png` と `pdf` の打ち間違いで規定違反の図一式が揃うのを防ぐため)。
  承知のうえで出すには `--allow-disallowed-format` を付ける。
- **`pdf`**: SVG を `svg-conversion` コンテナで PDF にする (`figures.font_handling: outline` なら文字をアウトライン化。
  初回は `svg-conversion` イメージのビルドが走る)。Mermaid 図は Mermaid の経路で作った PDF をそのまま使う。
- **`png`**: SVG の公称サイズから `figures.dpi` (または `--dpi`) を満たす画素数で作り、pHYs を書く。
- **`pptx`**: **1 図 = 1 pptx = 1 スライド**で、SVG をベクターのまま埋め込み、PNG フォールバックを同梱する
  (この経路を本テンプレートでは**案 B** と呼ぶ。ログにもこの名前で出る)。図を PowerPoint で求める誌向け。
  - Microsoft 365 / Office 2019 以降の PowerPoint では SVG 側が描画され、グループ化を解除すると文字の選択・編集もできる
    (文字を輪郭化しない `figures.pptx.text_to_path: false` のとき。`true` にすると図中の文字は図形になる)。
    Office 2016 以前では PNG フォールバックが表示される (同梱する PNG は要求 dpi を満たす)。
  - **図の隣に同名の `.pptx` を置くと、それを無変換でコピーする** (**案 A**。PowerPoint で仕上げた図を劣化なしに出す)。
    原稿はそのまま同名の `.svg` をプレビューとして参照する (`figs/fig1.svg` + `figs/fig1.pptx`)。
    **1 ファイル 1 スライド**にすること (2 枚以上は止まる)。マクロを含むファイル (`.pptm` / `vbaProject` 入り) は拒否する。
    中身はテンプレートの検査の対象外になるので、フォント・余白・凡例のキーは PowerPoint で自分で確かめる。
  - **元がラスタの図 (`.png` など) は pptx に包まず、画像ファイルのまま出す**。
  - 図の公称サイズが **1 inch 未満**の軸は、PowerPoint の規格の下限までスライドを広げて図を中央に置く
    (足した余白は警告に出る)。**56 inch を超えるとエラーで止まる**ので、SVG の寸法を直すか `--slide-fit fixed`
    (既定のスライドの大きさに縮めて置く) を使う。
  - `--format png` への切り替えはいつでも効く。
  - PowerPoint から PDF を作るときは「印刷」ではなく「エクスポート → PDF/XPS の作成」を使う。`Microsoft Print to PDF`
    を通すと、ベクターも文字もビットマップになる。

### 5.2 図の解像度を確かめる

`check-figures.sh` には守備範囲の違う 2 つのモードがある。**図を外す誌の提出前は両方を回す**。

```bash
bash scripts/check-figures.sh --journal <id>                                    # 図ツリー
bash scripts/check-figures.sh --journal <id> --figures-dir data/output/<id>/figures   # 分離出力した図
```

- **図ツリー** (`data/step01_figures/figs`。`--tree` で変えられる) — SVG の公称サイズから期待する画素数を出し、
  **実画素数まで検算**する。解像度の確認はこちらが本体。図を本文に埋め込む誌 (ABE) は、PNG フォールバックの確認にこちらだけを回す。
- **分離出力した図** (`--figures-dir`) — ここには元の SVG が無いので期待する画素数を出せず、**pHYs (PNG に書かれた
  申告解像度) の確認だけ**になる。pptx 図は書庫を開き、SVG 拡張の位置・SVG 本体と PNG フォールバックの同梱・
  同梱 PNG の pHYs を検査する。
- 目標 dpi の優先順は `--dpi` > `--journal` の `figures.dpi` > 300。実行時にどこから採ったかを表示する。
- 自分で置いたラスタ図は「注意」として一覧に出る。終了コードには影響しないが、合格の件数にも入らないので、内容を読むこと。
- `bash scripts/check-figures.sh --self-test` は、この検査自体に識別力があるか (わざと壊した pptx を落とせるか) を確かめる。

### 5.3 提出構成の組み替え (最終モード)

原稿 (`src/main.md`) は図表を本文中の自然な位置に書いたまま雑誌に依存させず、「表は末尾 (または別ファイル)」「図の題と凡例は
References の後」という誌の要求は、提出物を作るときに満たす。`--mode final` かつ `--keep-figures` なしのときだけ動き、
何をするかは `profile.yaml` で決まる。**図を本文に埋め込んだまま出す誌 (ABE) では組み替えない** (`figures.separate: false` は
下の `end` / `separate` / `legends_section` と一緒に使えず、profile を読むときに止まる)。

- `tables.placement: end` → 本文中の表を「題 + 表 + **直後に連続する `Legend` 段落すべて**」の 1 組として
  **文書の末尾へ**移し、元の位置に `[Table N about here]` を残す。
- `tables.placement: separate` → 同じ 1 組を**本文から外し**、`data/output/<id>/tables/TableN.docx` に **1 表 1 ファイル**で
  出す (題が上・凡例が下)。元の位置には `[Table N about here]` を残し、本文の流れに表は残らない (テキストボックスの中の表は
  動かさない)。表のファイルは組み替えた本文と同じ書庫から作るので、スタイル・フッタが本文と同じになる。行番号は
  `line_numbers_scope: manuscript` なら外す。`tables.placement` の値の綴りを誤るか、値を空にするとエラーで止まる。
- `figures.legends_section: "Figure Legends"` → 「図の題 + **直後に連続する `Legend` 段落すべて**」を References の後の
  **新しいページ**の見出しの下へ集める。画像の段落は `[Figure N about here]` として本文に残る。
- **`.textbox` の中身は動かさない** (本文の流れの外にあるため)。
- 並びは **References → Figure Legends → 表** (`separate` では表が本文に無いので References → Figure Legends で終わる)。
  図表番号が本文の初出順と一致するか、題の無い画像が混ざっていないかを検算し、ずれがあれば注意を出す。
- 本文の相互参照 (`Fig. 1` / `Table 1`) は、移した後もプレースホルダの位置へ飛ぶ。`end` で末尾に並べた表どうしは、Word が
  1 つの表に結合しないよう間に空の段落を挟む。
- 草稿モードや `--keep-figures` では組み替えない。profile が要求しているのに組み替えなかったときは注意に出すので、
  提出物を作るときは `--mode final` をそのまま回す。
- **`tables.allow_color: false` の誌では、表の網掛け・文字色・蛍光ペン・罫線の色を検出して警告する** (草稿モードでも)。
  数値の桁区切りカンマは Markdown の層の規定チェック (§5.6) が見る。
- **カバーレターと回答書から行番号を外せる** (`line_numbers_scope: manuscript`)。行番号は査読者が本文の位置を指すためのものなので、
  `main.md` だけに付く。ページ番号は残る。
- 提出物は roundtrip がそのまま Word に回す (§6)。`SUBMISSION.md` を持つ提出パッケージの本文と表は、`roundtrip.sh` が
  `<id>-manuscript.docx` / `<id>-Table1.docx` … の名前で集めて PDF にし、パッケージ一式を Drive の `submission-<id>/` に置く。

### 5.4 提出マニフェスト `SUBMISSION.md`

`submission.text_formats` を持つ誌 (同梱では ABE) には `data/output/<id>/SUBMISSION.md` が出る。投稿系のアップロードの
種類 (原稿本体 / 表 / 図 / 動画 / 補足資料 / 提出フォーム) ごとに、**ファイルの一覧・順序・形式・サイズ**と、別途提出する
フォーム (`submission.forms`) のチェック欄を並べる。**投稿画面を開く前にこれを 1 枚見れば、何をどの欄に上げるかが決まる**。

- ABE の `SUBMISSION.md` は、原稿本体 (Word で PDF にした `manuscript.pdf` を上げる旨と、`sections.required` から組んだ構成) /
  表と図 (本文に置いたまま) / 補足資料 (規定の要点・容量の上限と今回の合計) / 提出フォーム (`submission.forms` のチェックリストと
  `forms/` の書式の一覧) / アップロード種別ではないもの (差分 docx の注記は `submission.diff_note`) / 規定チェック の順に並ぶ。
- **図を外す誌では、図は「Figures」の表の順に、表は「Tables」の表の順にアップロードする** (`tables.placement: separate` のとき)。
  表の一覧は、相互参照のラベル `{#tbl:x}` の付いた表 (`TableN.docx`) を番号の順に並べ、ラベルの無い表 (`Table-untitledN.docx`) を
  最後に回してある。投稿系は上げた順に番号を割り当てることが多いので、並べ替えない。ラベルの無い表は本文で番号が振られず、
  本文の表番号と食い違うので、提出する表にはラベルを付けるのが確実。
- **図を外す誌では、投稿画面の Caption / Legend 欄に貼る文面が `CAPTIONS.md` に出る** (最終モードのときだけ)。
  `CAPTIONS.md` は**提出するファイルそのもの** (`manuscript.docx` の Figure Legends 節と `tables/*.docx`) から、書式を除いて
  同じ文字を抜き出し、表 → 図の順に 1 ファイル 1 項目で並べる。欄は書式なしのテキストとみなし、上付き・下付きは Unicode の
  文字 (例: 10⁴) に置き換え、斜体・太字は項目の下に注記する。**数式・脚注の記号・リンクの URL・Unicode にできない上付きは
  欄に入らない**ので、⚠ の注記を付けて `SUBMISSION.md` の注意にも出す — ⚠ の項目は本文と見比べて直すこと。
  `CAPTIONS.md` 自体はアップロードしない。図を本文に埋め込む誌 (ABE) では作らない (本文の題と凡例がそのまま提出物になる)。
- `SUBMISSION.md` には、どの原稿 (入力ルートと `main.md` の SHA-256) から作ったパッケージかと、誌プロファイルと `reference.docx` の
  SHA-256 を書いた行が入る。roundtrip が Drive へ届ける前に、今の原稿・プロファイル・`reference.docx` と照合する (§6)。
  `package.sh` 自身も、`data/step02_build/main.docx` を build した原稿 (`build.sh` が `data/step02_build/.build.source` に残す
  入力ルートと SHA-256) が今回の原稿と同じかを照合し、**最終モードでは食い違えば止まる** (提出物の本文と規定チェックが別の原稿を
  指さないように。草稿モードは注意だけ)。照合するのは `main.md` のほか、`ref.bib` / `cover-letter.md` / `revise-report.md` /
  `figs/` の中身 (シンボリックリンクはリンクの先の中身。ただし数えるのはリポジトリの中を指す相対リンクだけで、絶対パスのリンクや
  リポジトリの外を指すリンクは build も読めないので数えない。`figs/` の中のディレクトリのリンクには図を置かない — 図の前処理が
  たどらない) と、build が書いた `main.docx` そのもの。build の最中に原稿や図が変わると、build は記録を書かずに止まるので、
  もう一度 build する。
  最終モードで図を外す誌の提出物の図は図の前処理の結果 (`data/step01_figures/`) から作るので、その出所も照合する — 図の前処理
  (`main/step01_figures/figures.sh`。build と diff が回す) が入力ルートと `figs/` のハッシュと、作った図の各ファイルのハッシュを
  `data/step01_figures/.figures.source` に残し、最終モードの package は今の原稿と食い違えば・作った図が後から変わっていれば止まる。
  原稿が必ず使う 5 つの入力 (`main.md` / `ref.bib` / `cover-letter.md` / `revise-report.md` / `figs`) が、絶対パスのリンク・
  行き先の無いリンク・物理的にリポジトリの外にあるパスなら、build が理由を出して止まる。
  直すには `build.sh` を同じ `--input` (と `--journal`) で回し直すか、`package.sh … --build` を使う。同じ作業ツリーで build・diff・
  package のどれかを回している間に別のものを回すと、後から始めた方が「別の build / diff / package が実行中です」で止まる
  (どれも `data/step01_figures/` と `data/step02_build/` を使うため。`flock` の無い環境では止まらないので、同時に回さない)。
- **冒頭に ⛔ が出ていたら提出しない**。草稿モードや `--keep-figures` で作ったパッケージは、提出用の照合を通っておらず、
  図を外す誌では構成も組み替えていない。
- **「規定チェック」節の要修正と、末尾の「注意 (この実行で検出したもの)」を必ず読む**。上限を超えた補足資料・動画・受入形式外の
  ファイル・表の色・図と凡例の食い違いなど、この実行で見つかった問題がすべて転記される。規定に反するファイルは表の行にも
  `⚠ 上限超過` のような印が付く。画面のログは流れて消えるが、このファイルは残る。`--no-validate` で作ったときは
  節を出さず、冒頭に「省略した」と書く。
- アップロードの種類は投稿規定の記述から作ったもので、投稿系の実際の画面とは照合していない。食い違ったら画面が優先で、
  その誌の `profile.yaml` の `submission` ブロックを直す。

### 5.5 補足資料・記入済みの書式・動画

- **`<入力ルート>/supplementary/` は無変換で `data/output/<id>/supplementary/` に複製される**。中身には一切手を加えない。
- 容量の上限を持つ誌 (`limits.supplementary_file_mb` / `supplementary_total_mb`。ABE は 1 ファイル 50 MB・合計 50 MB) では、
  超過を規定チェックが要修正にし、`SUBMISSION.md` の補足資料の節にも上限と今回の合計を出す (サイズは 10 進。1 MB = 1 000 000 バイト)。
  動画 (拡張子で判定) は `limits.video_mb` の超過と受入形式外を警告する。
- **OS が作る管理用のファイル (`.DS_Store` / `Thumbs.db` / ドットで始まる名前) は複製しない**。除いたときは
  「管理用ファイル N 件を除外しました」と表示するので、意図して置いたものが落ちていないか確かめる。
- **記入済みの投稿書式** (`submission.collect_forms: true` の誌。ABE): `<入力ルート>/forms/` の直下の書式 (docx / PDF) を
  提出パッケージの `forms/` に無変換で複製し、`SUBMISSION.md` に一覧を出す。拡張子だけは小文字にそろえて写す
  (`X.DOCX` → `X.docx`。そろえた名前が重なれば止まる)。docx の書式は roundtrip が Word で PDF にする (§6)。
  **記入済みの書式は署名と個人情報を含むので git で追跡しない** (`src/forms/` は `.gitignore` 済み)。`--input` で入力ルートを
  `src/` 以外にしたときは、`<入力ルート>/forms/` が git で無視されていなければ `package.sh` が注意を出すので、`.gitignore` に
  その置き場所を足す。置き方は §8.5。
- 書式と補足資料の止まる検査 (読めないディレクトリ・リンク・名前の重なり) は、前回のパッケージ `data/output/<id>/` を消す前に行う
  (止まっても前回のパッケージは残る)。

### 5.6 規定チェック (validate)

`package.sh` の最後に、記事種別ごとの上限 (`--article-type`) と執筆の検査 (lint) を掛け、**「規定違反の可能性 (要修正)」と
「参考情報」に分けて**出す。**エラーにはしない** (終了コードは 0。判断は執筆者に残す)。

- 概算: 本文語数 / 抄録語数 / 文献数 / 図表の点数。本文語数は本文の節の段落の文章だけを数える。
  表題ページと凡例の Div (タイトル・著者・所属・連絡著者・キーワード・抄録・**図表の凡例**) の中身、References・表・キャプションは、
  本文の節の文章として扱わない。凡例の語数は図 / 表に分けて別に出す (編集部の数え方が違えば足し戻せるように)。
  抄録の語数は英数字を含む語の数と空白区切りの語の数の両方を出し、食い違えば上限は大きいほうで判定する。
  `.textbox` の中の図表は点数に数えず、数えなかった点数を概算行に必ず出す。概算の行は `SUBMISSION.md` の「規定チェック」節にも載る。
- 主な検査 (誌の `profile.yaml` のキーで有効になる): タイトルの語数 / キーワードの数と、キーワードが題の語を繰り返していないか /
  抄録の段落数・構造 (見出しつきの構造化抄録の形)・抄録の中の文献引用と図表への言及 / running title の要否と字数 /
  著者の姓の大文字 / 所属の上付きの番号 / 表題ページの Div (Title / Author / Abstract / Keywords) の欠落と重複 /
  必須の節 (`sections.required`。言い換えは `sections.aliases` で同じ節とみなす) / 題の無い図表 / 表の題の属性 (`{#tbl:x .wide}`) /
  図表の題の大文字 / 略語の定義 / 利益相反・倫理・AI ツールの開示・資金の置き場所 (参考) / 引けない文献 (参考) /
  補足資料の容量とアーカイブ / 合成文字 (`℃`) / 数値の桁区切りカンマ / 骨格の記入欄 `<<...>>` の残り / 図表の題と凡例の語数 /
  凡例 Div の `for` 属性と配置 / 凡例 Div の中身が段落だけか / References が本文の最後の節か / 英米の慣用単位。
- **一般的な作法 (合成文字・単位系・記入欄・凡例の配置) は雑誌プロファイルではなく基底に置いてある**ので、どの誌で
  パッケージしても掛かる。その誌の規定を調べたものではないので、指摘の文末に **`(本テンプレ共通の作法)`** が付く
  (付いていない要修正は、その誌の `profile.yaml` に根拠がある)。仕組みは `docs/profile-schema.md` の「lint の 2 層構成」。
- 指摘には原稿の行番号が付く。指摘は `SUBMISSION.md` の「規定チェック」節にも残る。
- ビルドせずに単独でも回せる:
  ```bash
  docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
      python3 main/step05_package/validate.py \
          --input-root data/dummy/abe --journal abe --article-type original
  ```
  動作例 `data/dummy/abe/` は要修正 0 件・参考 0 件になる。
- 指摘の出方を見たいときは、違反を仕込んだフィクスチャ `data/dummy/abe-lint/` を同じコマンドに渡す
  (要修正 12 件 + 参考 15 件が出る。仕込んだ違反の一覧はファイルの冒頭。同時には起こせない違反は `data/dummy/abe-lint/variants/` に置いてある)。
- `validate.py` を直したときは回帰試験を回す。適合原稿・不適合原稿とその変種・補足資料の容量・`data/dummy/abe` を 1 か所ずつ
  変えた変種の件数と文面を、素の assert で 132 件照合する (全件通れば終了コード 0):
  ```bash
  docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
      python3 main/step05_package/test_validate_abe.py
  ```

### 5.7 入力ルートを切り替えるとき

`build.sh` は、`<入力ルート>/revise-report.md` / `cover-letter.md` が無ければ前回の docx を消す。`package.sh` も一次ソースの
有無と照合し、別の原稿でビルドした古い docx が混ざっていそうなら注意を出す。`main.docx` が別の入力ルートの原稿や、build の後に
変えた原稿から作られていれば、最終モードは止まる (§5.4)。それでも、**入力ルートを大きく切り替えるときは
掃除してから回すのが確実**である:

```bash
rm -f data/step02_build/*.docx data/step02_build/*.tsv
rm -rf data/step05_package        # 提出用の派生物 (*.safe.svg / *.outline.svg) の置き場所
bash scripts/build.sh --journal <id> --input <入力ルート>
```

`data/step05_package/` は、`figures.pptx.inline_css: true` のときに作る `<stem>.safe.svg` (CSS を要素へ書き出した SVG) と、
`figures.pptx.text_to_path: true` のときに作る `<stem>.outline.svg` の置き場所で、毎回作り直すので古いものが使われることは無いが、
掃除しておくと分かりやすい。

- `blinded: true` の誌では、著者・所属を伏せる作業を**手で**行う (自動の匿名化は無い。`package.sh` が注意を出す)。

---

## 6. 最終 PDF を作る (roundtrip)

docx → PDF は **Windows の Word (COM) で変換する**経路だけを用意している (任意の機能)。rclone の Google Drive の
リモートと、Windows 側で動く watcher が要る (配置・診断・トラブルシュート: `docs/roundtrip-windows-watcher.md`)。

送出先は Google Drive の **`gdrive:tmp/<リポジトリのディレクトリ名>/`** (算出は `scripts/lib/gdrive-dest.sh`。
環境変数 `RCLONE_REMOTE` / `GDRIVE_BASE_PATH` / `GDRIVE_SUBDIR` で変えられる)。watcher は PDF を**送出先の直下
(docx の隣)** に書く。

```bash
# 初回 (と watcher を更新したとき): Windows 側の 3 ファイルを送る → Windows で watch-and-convert.bat を起動
bash scripts/push-win-tools.sh

# 経路の診断 (読み取りだけ・数秒)。--full を付けると docx を 1 本往復させる
bash scripts/check-pdf-path.sh

bash scripts/roundtrip.sh                 # build → data/output に集約 → Drive へ送る → PDF を待つ → data/products へ取り込む
bash scripts/roundtrip.sh --skip-build    # 既存の docx を集約して変換 (別の誌でビルドした docx を見るときは必ずこちら)
bash scripts/roundtrip.sh --skip-push     # タイムアウトの後の再開 (送り直さず、待ちと取り込みだけ)
bash scripts/roundtrip.sh --dry-run       # rclone を呼ばずに流れを表示 (ビルドはしない。集約は実際に行う。watcher は要らない)
bash scripts/roundtrip.sh --no-package    # 提出パッケージ (data/output/<id>/) を扱わない
```

- 引数なしのときの最初の段は `build.sh` を引数なしで回す (= `_default`)。ABE の体裁などで見たいときは、先にその誌で
  ビルドして `--skip-build` で回す。
- PDF を待つ時間の既定は 10 分 (`--timeout MIN`)。送る前に watcher の生存記録 (`.watcher-alive`) を見て、止まっている・
  ローカルと別の版が動いている・試験用の起動引数のまま、のときは警告する。前回の PDF を退避できなければ中止する
  (古い PDF を今回の結果として持ち帰らないため)。
- Windows 側の watcher は **1 ファイルあたり 120 秒で変換を打ち切り** (Word が固まったとき)、その docx を `error/` へ移して
  次へ進む。止めるのはその変換が起動した Word だけで、開いている Word の文書は巻き込まない。docx は 1 本ずつ順に変換するので、
  固まる docx が続くと合計が上の 10 分を超えうる。
- rclone や watcher が無い環境では docx までで止まる。`--dry-run` は rclone を呼ばないので、リモートが未設定でも流れを表示して
  正常終了する。ただし集約 (`data/output/*.docx` を消して集め直す) は実際に行う。
- **`SUBMISSION.md` を持つ提出パッケージ (`data/output/<id>/`) があると、既定でそれも扱う** — 本文 (図を外す誌では表も。
  原稿本体を PDF で上げる誌では `manuscript.docx` と `forms/` の docx の書式) を PDF 化に回し、PDF がそろったら Drive の
  `submission-<id>/` に置く (§8.6)。その前に、パッケージが今の原稿・プロファイル・`reference.docx` から作られたかを照合し、違えば
  何も送らずに止まる。動作例 (`--input data/dummy/abe`) で作ったパッケージが残っていると、`--dry-run` もここで止まる。
  パッケージを使わないなら `--no-package`、動作例のパッケージを見るなら `INPUT_ROOT=data/dummy/abe` と `--skip-build` を付ける
  (`--skip-build` が無いと最初の段が既定の誌で build し直し、パッケージより新しいビルドができて止まる)。
- **PDF を待つ間に `package.sh` を回さない** — 配送の前に、送ったときのパッケージと今のパッケージを照合し、変わっていれば止まる
  (Word の PDF で確かめていない版を届けないため)。
- **送出先に同じ名前の docx が残っていれば push しない** (前回の分がまだ変換待ち・変換中。上書きすると、変換されないまま
  `processed/` に入りうる)。**push より前に書かれた PDF は今回の成果として取り込まない** (時計のずれを 120 秒まで許す)。
  どちらも `docs/roundtrip-windows-watcher.md` §5・§7。
- 返ってきた PDF は**図を拡大して目で見る**こと。体裁の計測では図の中身の崩れに気づけない。PDF の図がベクターで載っているかは
  `main/step04_pdf/inspect_pdf_figures.py` で判定できる (`docs/roundtrip-windows-watcher.md` の「PDF の確かめ方」)。

---

## 7. パイプライン早見表

| 段 | コード | 入力 | 出力 | スクリプト |
|----|--------|------|------|-----------|
| step01 | `main/step01_figures/` | `<入力ルート>/figs/` | `data/step01_figures/figs/` | (build.sh / diff.sh が回す) |
| step02 | `main/step02_build/` | `<入力ルート>/main.md` + step01 | `data/step02_build/*.docx` | `scripts/build.sh` |
| step03 | `main/step03_diff/` | 旧版 / 新版の main.md | `data/step03_diff/main_diff.docx` | `scripts/diff.sh` |
| step04 | `main/step04_pdf/` (Windows 側は `windows/`) | `data/output/*.docx` (+ 提出パッケージ) | `data/products/*.pdf` | `scripts/roundtrip.sh` (準備 `push-win-tools.sh` / 診断 `check-pdf-path.sh`) |
| step05 | `main/step05_package/` | step02 / step03 の成果 + プロファイル | `data/output/<id>/` | `scripts/package.sh` |
| (検査) | `main/step02_build/check_csl.py` | `data/dummy/<id>-csl/` + `<id>.csl` (+ 任意で docx) | 照合結果 | `scripts/check-csl.sh` |
| (検査) | `main/step01_figures/check_dpi.py` | `data/step01_figures/figs/` または `data/output/<id>/figures/` | 実画素数・pHYs と目標 dpi の照合結果 | `scripts/check-figures.sh` |
| (検査) | `main/step03_diff/test_diff_engine.py` | `data/dummy/regression/diff/<名前>/old.md・new.md` (10 対) | 差分 docx の性質の照合結果 (`_default` と `abe` で 110 項目) | `scripts/check-diff.sh` |
| (検査) | `main/step05_package/test_validate_abe.py` | `data/dummy/abe`・`data/dummy/abe-lint` (+ `variants/`・`supplementary/`) | 規定チェックの件数と文面の照合結果 (132 件) | (コンテナで直に `python3`) |

各段は単独で再実行できる。コード (`main/`) とデータ (`data/stepNN_name/`) は分けてある。

テンプレート自体を直したときの回帰の確かめ方は `CLAUDE.md` の「変更するときの確認」
(`scripts/baseline.sh` / `baseline-abe.sh` / `compare-snapshots.py`)。

---

## 8. ABE へ投稿する (通し手順)

*Advanced Biomedical Engineering* (ABE) への投稿を、学会テンプレートの置き方から投稿・改訂まで 1 本につないだもの。個々の機能の説明は
§1〜§6 にあるので、ここでは**順番と、どの段で何が担保されるか**だけを書く。投稿当日に 1 枚で確認する表は
[`docs/abe-submission-checklist.md`](abe-submission-checklist.md) (自動で担保される項目と、人が目で見るしかない項目を
分けてある)。規定の読み解きと実装の対応は [`docs/journal-abe.md`](journal-abe.md)。

> 本テンプレートは日本生体医工学会 (JSMBE) とも ABE の編集部とも関係の無い独立したツールである。**規定は変わりうるので、
> 誌の [Instructions to Authors](https://abe-journal.org/authorinstructions) で確かめること。**

ABE は**学会テンプレート `ABETemplate.docx` の体裁 (表題ページは 1 段組・本文は 2 段組・行番号・柱・見出しの自動番号) をそのまま使う**。
原稿は誌に依存しない Markdown のまま書き、段組・見出しの番号・図表の題の形・式番号の位置は `profile.yaml` と後処理が付ける
(同じ原稿を `--journal _default` でも組める)。

### 8.1 学会テンプレートを置く (最初に 1 回)

学会サイトの Instructions to Authors のページ (<https://abe-journal.org/authorinstructions>) から `ABETemplate.docx` を取り、
`data/journals/abe/ABETemplate.docx` に置く。**学会の配布物なので本テンプレートには同梱しておらず、git でも追跡しない**
(`.gitignore` 済み)。build / diff はこれを雛形にして `data/journals/abe/reference.docx` (これも追跡しない生成物) を作る。
ダウンロードで `ABETemplate (1).docx` のような名前になったときは、`profile.yaml` の `reference_base` の名前 (`ABETemplate.docx`) に
直して置く。

- 置いていなければ build / diff は取得元と置き場所を標準エラーに出して止まる (終了コード 1)。
- **置いたテンプレートが本テンプレートで確かめた版 (ver.3) と違えば、指紋 (SHA-256) が `profile.yaml` の `reference_base_sha256` と
  違うので build / diff が止まる** (`make-reference.sh` がエラーを出す)。改版でスタイル名や節の構造が変わると後処理が外れうるため
  である。新しい版を使うなら、`data/journals/abe/profile.yaml` の `reference_base_sha256` を表示された「置いたもの」の値に
  書き換えてから回し直し (それが「新しい版を確かめた」印になる)、出てくる警告と §8.6 の roundtrip の PDF の見た目 (2 段組・柱・
  見出しの番号・図表の題) を確かめる。元の版に戻すなら取得し直して置き直す。
- **`reference.docx` を作ったときの警告** (テンプレートから消えた・名前の変わったスタイルを受け皿で埋めた・見出しの番号定義が
  想定と違う・想定外のパートを外した・git の追跡) は `data/journals/abe/.reference.warnings` に記録され、作り直さずに使うときも
  **build・diff のたびに標準エラーに出る**。あわせて build・diff の後処理が毎回、出力の未定義のスタイルと見出しの自動番号の欠けを
  警告する (止めない)。警告が出たら roundtrip の PDF で確かめる。
- `reference.docx` を作るときに、テンプレートの作成者などの識別情報 (最終更新者・変更履歴・コメント・文書 ID など) を外す。
  知らないパートは外して警告し、作成者などの属性が残れば止まる (`docs/journal-abe.md` §8.4)。
- 置けたかの確かめ: `bash scripts/build.sh --journal abe --article-type original --input data/dummy/abe` (動作例がそのまま組める)。

### 8.2 執筆を始める

```bash
rm -f .development
bash scripts/remove-sample.sh                                       # clone した直後の src/ のサンプル論文を消す
cp data/journals/abe/skeleton/main.md         src/main.md
cp data/journals/abe/skeleton/cover-letter.md src/cover-letter.md   # 任意 (規定にカバーレターの記述は無い)
```

clone した直後の `src/` に入っているサンプル論文は、この骨格を埋めた形の架空の論文 (`data/dummy/abe/` の動作例に TJD の挿絵を足したもの) で、書き方の見本になる。
`remove-sample.sh` は中身がサンプルのままのファイルだけを消すので、書き換えて残したいファイルは消えない。自分の `main.md` の隣に
サンプルのファイル (`src/` に写した `data/dummy/` の動作例を含む) が中身もそのまま残っていると、§8.4 の最終モードの package は止まる。

骨格は規定の節の並び (表題ページ → Introduction → Materials and methods → Results → Discussion → Conclusion → Conflicts of interest →
Ethics declaration → Acknowledgements → References) を記入式で持ち、記入欄は `<<...>>` で書かれている。**埋め忘れは §8.4 の規定チェックが
`main.md` / `cover-letter.md` の両方について要修正として出す**。定型の記述 (利益相反・倫理・資金・AI ツールの開示・データ・臨床試験・
画像の加工・報告指針・転載) の文例は `data/journals/abe/skeleton/statements.md` (参照用)。記入済みの動作例は `data/dummy/abe/` で、
`--input data/dummy/abe` を付ければそのままビルドできる。

ABE で原稿の書き方に効くもの (詳細は骨格の各節の頭のコメントと `CLAUDE.md` の「ABE 投稿時の執筆規約」):

- **著者の姓はすべて大文字** (`Taro YAMADA`)。所属は上付きの数字 (`^1^Graduate School of …`。タブは書かない — docx で番号の直後に
  タブが入る)。著者はカンマで区切っても、改行 (行末の `\` の強制改行を含む) で 1 行 1 人に並べてもよい。学位・肩書 (`PhD` など) は
  書かない — 書くと規定チェックが参考で知らせる (姓の大文字の判定からは除く)。
- **表題ページの Div (Title / Author / Abstract / Keywords) は 1 つずつ書く**。無い・2 つあると表題ページの検査が働かないので、
  規定チェックが要修正にする。
- **抄録は見出しの無い 1 段落の文章で書く** (構造化抄録は不可)。`**Background:** …` のような見出しつきの形は規定チェックが
  要修正にする。
- **異動後の新住所は著者名の直後の普通の脚注**に書く (`Hanako CHOKKAN^2^^[Present address: Department of …, City, Country.]`)。
  docx では著者の脚注の参照と番号が出てきた順に上付きの記号 `*` `**` になり、本文の脚注は数字のまま。2 人が同じ新住所なら、
  同じ文面を 2 度書くか同じ `[^addr]` を 2 度参照すれば 1 つの記号と 1 つの脚注にまとまる。新住所を所属の Div に書かない
  (脚注にならない)。
- **running title** (題が空白込みで 50 字を超えるなら 50 字以内) を所属の後の `custom-style="Subtitle"` の Div に書く。柱にもこの文字が入る。
- **見出しに番号を書かない** (テンプレートの自動番号が付く)。番号の無い節 (Abstract・Conflicts of interest・Ethics declaration・
  Acknowledgements・References) は `{.unnumbered}` を付ける。
- **2 段組の指示を書かない**。段の幅 (83 mm) に収まらない図は `{.wide}`、表などは `::: wide` の Div で囲む (段抜き)。表の題に
  `{#tbl:x .wide}` と書くと番号が付かないので、build が警告し規定チェックが要修正にする。
- 式・図・表の参照は `[@eq:x]` / `[@fig:x]` / `[@tbl:x]` だけを書く (`Eq. 1` / `Fig. 1` / `Table 1` の語は自動で付く)。
- **AI ツールの使用は Materials and methods で開示する** (骨格の末尾の小節。文例は `statements.md` の AI ツールの節)。使ったツールと版は、
  書き始めた時点から **git で追跡するファイル**に記録していく (執筆が長引くと途中で版が変わるため)。
- 資金は Acknowledgements に**資金提供者と助成番号の両方**で書く。利益相反が無ければ規定の定型文 (`statements.md`)。

日本語などで下書きを書くなら、原稿の入力ルート (`src/`) の外に置く。ビルドが読むのは `<入力ルート>/main.md`・`cover-letter.md`・
`revise-report.md`・`ref.bib`・`figs/`・`forms/`・`supplementary/` なので、`src/` に別の Markdown を置いても組まれはしないが、
`cp -r` や規定チェックで取り違えないよう分けておく。

### 8.3 図を用意する

- 本文からは常に `.svg` で参照する (§2)。SVG ルートの `width` / `height` は**物理単位**で書く (§2.1)。
- **段に置く図は幅 83 mm まで、段抜き (`{.wide}`) の図は本文幅 180 mm まで**。段の幅を超える図は build が段の幅に縮めて警告する
  (図の中の文字も縮むので、警告が出たら `{.wide}` を付けるか作図し直す)。
- 図は本文に埋め込んだまま提出する (分離提出しない。`docs/journal-abe.md` §5)。解像度・形式の規定は無いが、PNG フォールバックは
  300 dpi で作られる (`bash scripts/check-figures.sh --journal abe`)。
- 多パネル図は 1 ファイルに合成し、余白は SVG の側で切り詰める (自動化されない)。

### 8.4 ビルドして中身を確かめる

```bash
bash scripts/build.sh   --journal abe --article-type original
bash scripts/package.sh --journal abe --article-type original --mode final
bash scripts/check-figures.sh --journal abe
```

骨格から書き始めたばかりで**図がまだ 1 枚も無いとき**は、`check-figures.sh` は「検査する図がありません」と出して終了コード 0 で
終わる。図を足したら回し直す。

`package.sh --mode final` は ABE では**図を外さない** (`figures.separate: false`)。`manuscript.docx` は `main.docx` そのもので、
最後に**規定チェック (validate)** を走らせ、指摘を画面と **`data/output/abe/SUBMISSION.md` の「規定チェック」節**の両方に出す —
画面のログは流れて消えるので、**最終確認は `SUBMISSION.md` で行う**。出力は 2 段に分かれる。

- **規定違反の可能性 (要修正)** — 直す。語数・抄録の段落と構造化の形・キーワード・running title・姓の大文字・必須の節・題の無い図表・
  表の題の属性・表題ページの Div の欠落と重複・記入欄など
- **参考情報** — 判断が要るもの。題の略語・所属の上付き・利益相反の定型文・倫理の節・AI の開示の置き場所・資金・略語の定義・
  引けない文献など (語から推し量る)

**どちらもエラーにはしない** (終了コードは 0)。CI で落としたい場合は出力を自分で判定する。

**build と package は同じ誌で回す** — `--journal abe` を付け忘れた build (既定は `_default` = 1 段組) の本文を、提出用の
`package.sh --journal abe` は止める。build の後に `profile.yaml` やテンプレートを変えたときも止まるので、`package.sh … --build` で組み直す。

引用の書式を変えたら `bash scripts/check-csl.sh --journal abe --fixture data/dummy/abe-csl` と、フィクスチャをビルドした docx での
`--docx` の照合を回す (§4.1)。フィクスチャのビルドは `data/step02_build/main.docx` を上書きするので、照合のあとで原稿をビルドし直す。

### 8.5 記入済みの書式を置く

`src/forms/` に記入済みの書式を置く (**git で追跡しない**。`.gitignore` 済み)。`package.sh` が提出パッケージの `forms/` に無変換で
複製し、docx は §8.6 の roundtrip が Word で PDF にする (§5.5)。

| 置くもの | 置き方 |
|---------|--------|
| Submission Form and Author Statement (1 通。全著者の署名) | 署名を入れてスキャンした PDF を、docx と**同じ名前**の `.pdf` で置く (例 `submission-form.docx` と `submission-form.pdf`)。その PDF がそのまま使われ、docx は Word に回らない |
| COI 開示書式 (**著者ごと**に 1 通) | `coi-<著者>.docx` など。docx なら Word で PDF にする |
| 英文校正の証明・倫理の承認書・転載許諾の写し | PDF のまま置く (そのまま上げる) |

書式そのもの (Submission Form・COI 開示書式) は学会サイトから取る。置き方の見本は動作例の `data/dummy/abe/forms/`
(学会の書式ではなく、架空のダミー書式 4 本)。

### 8.6 Word で PDF にする (roundtrip)

Windows 側で watcher が動いていることが前提 (§6。止まっていると 10 分待ってタイムアウトするので、先に
`bash scripts/check-pdf-path.sh` で [4/5] が「稼働中」・watcher が 1 個であることを見る)。

```bash
bash scripts/roundtrip.sh --skip-build   # → data/products/abe-manuscript.pdf など + Drive の submission-abe/
```

`roundtrip.sh` は **`data/output/` に集めた docx を何本でもまとめて送り、全部の PDF がそろうまで待つ**。草稿の `main.docx`・
`cover-letter.docx`・`revise-report.docx`・差分の `main_diff.docx` と、提出パッケージ `data/output/abe/` の本文と docx の書式
(`abe-manuscript.docx` / `abe-forms-<名前>.docx` の名前で集める) を一度に Word に回し、PDF はまとめて `data/products/` に届く。
PDF がそろうと、**最後の段がパッケージ一式を Drive の `submission-abe/` に置く** (`manuscript.pdf` と `forms/<名前>.pdf` を含む。
中身はパッケージと一致させ、消えた・置き換わったファイルは送出先の `__archives` フォルダへ退避し、手元の写し
`data/products/submission-abe/` と照合する。watcher は送出先の直下の docx しか見ないので、このフォルダは変換されない)。

**送る前に止まる条件** (何も送らない): パッケージが草稿モード (`--keep-figures` を含む) で作られている / パッケージより新しい
原稿・ビルド・差分 docx・誌のプロファイルがある / `SUBMISSION.md` に書いた入力ルート・原稿・プロファイル・`reference.docx` の SHA-256 が
今のものと違う・書かれていない / `--package` で `SUBMISSION.md` の無いパッケージを指定した / `--skip-push` で再開したのに、PDF に
するために送った docx と今のパッケージが違う / `--skip-push` で再開したのに、その送出先に push した記録 (時刻) が無い
(か送出先が違う。`--skip-push` を付けずに回し直す)。動作例のパッケージを確かめるときは
`INPUT_ROOT=data/dummy/abe bash scripts/roundtrip.sh --skip-build`。提出パッケージを使わないときは `--no-package`、
1 誌に絞るときは `--package <id>`。

- **`--skip-build` を必ず付ける** — 付けないと最初の段が `build.sh` を引数なしで回し直し、ABE の体裁の docx を `_default` の
  体裁で上書きする (そのうえパッケージより新しいビルドができるので、Drive へ届ける前に止まる)。
- **PDF を待つ間に `package.sh` を回さない** — パッケージが変わると、配送の前に止まる (§6)。
- **build と package と roundtrip は同じ誌・同じ `profile.yaml`・同じテンプレートで回す**。変えたら `package.sh … --build` で
  組み直してから送る。

届いた `manuscript.pdf` では、表題ページの独立・2 段組・行番号・柱・見出しの番号・図表の題・段抜きの図表・式番号の位置・文献の
`[1]` と巻の太字を目で見る (こう出れば正常、の値は `docs/abe-submission-checklist.md` の付録と `docs/journal-abe.md` §11.7)。
図は拡大して見る (§6)。

### 8.7 投稿する

Editorial Manager (<http://www.editorialmanager.com/abe/default.aspx>) に上げる。**Google Drive からファイルを選ぶときは
`submission-abe/` から取る** (送出先の直下や `processed/` には草稿と提出用の docx・PDF が並び、`processed/` では同じ名前が既にあると
時刻付きの名前になるので、取り違えやすい)。

- 原稿本体は **`manuscript.pdf`** (図表を埋め込んだ Word の PDF)。書式は `forms/*.pdf` を書式ごとに上げる。
- **本テンプレートは本文と書式を 1 本の PDF に結合しない** (規定は 1 本にまとめるよう "should" で書く。投稿画面が別々の
  アップロードを受け付けないなら結合が要る。`docs/journal-abe.md` §6.1 と §15)。
- 初回投稿では `manuscript-diff.docx` と `revise-report.docx` を上げない (`SUBMISSION.md` の「アップロード種別ではないもの」)。
- 投稿当日の確認は `docs/abe-submission-checklist.md` を上から順に。

> ⚠ `SUBMISSION.md` のアップロード種別は**規定から作ったもの**で、Editorial Manager の実際の画面とは照合していない。
> 画面と食い違ったら実際の画面が優先で、`data/journals/abe/profile.yaml` の `submission` ブロックを直すこと。

投稿の前から要る作業 (どれもツールの外にある。詳しくは `docs/abe-submission-checklist.md` の §0):

- **英文校正** — 英語を母語としない著者は、専門の校正会社の証明書などを出す。日程に余裕を見る。
- **COI 開示書式は著者ごとに 1 通**、**Submission Form and Author Statement は全著者の署名**が要るので、共著者への依頼に日数がかかる。
- **既発表の扱い** — 会議録として刊行されたものは既発表になりうる (例外の範囲は規定で確かめる)。関連原稿があれば編集者に知らせる。
- **連絡著者は投稿後に変えられない**。
- **研究データ** — 査読中に編集者と査読者へ全量を開示し、出版日までに公開することが規定で求められる。倫理審査・同意・契約で
  許されるかを先に確かめる。
- **掲載料** — 筆頭か連絡著者が学会の会員かで額が変わる (`docs/journal-abe.md` §1)。

### 8.8 記事種別を変える

`--article-type` を差し替えると本文語数の上限が切り替わる (抄録は全種別 350 語・1 段落)。定義は `data/journals/abe/profile.yaml` の
`article_types`。

| 種別 | 名前 (Submission Form の記事種別) | 本文 |
|------|-------------------------------|------|
| `original` (既定) | Original Paper | 4 000 |
| `letter` | Research Letter | 2 500 |
| `technical` | Technical Note | 1 500 |
| `review` | Review Paper | (編集委員会が論文ごとに決める。照合しない) |

本文語数の数え方は規定に定めが無いので、本テンプレートは本文の節の文章だけを数える (§5.6)。**Review Paper でも、規定チェックは方法・
結果の節が無いと要修正を出す** (規定の文言どおりにしてある)。総説で節の立て方が違うなら、規定の要素を満たしているかを人が判断する。
存在しない種別を渡すと、**有効な種別の一覧を出してエラーで止まる** (綴りの誤りで上限の検査が黙って外れないように)。

### 8.9 改訂稿を出す

- **期限は判定から 3 か月** (`docs/journal-abe.md` §7)。差分 docx は `bash scripts/diff.sh <旧版の commit かタグ> --journal abe --article-type original`
  (2 段組・柱・図表の題・式番号は build と同じ。残る制限は §3 と `docs/abe-submission-checklist.md` §8)。初回投稿の版にタグを
  付けておくと、改訂のたびに同じ旧版と比べられる。
- 大文字小文字だけの変更 (姓の大文字化・題のセンテンスケース化・単位の `mS` → `ms` など) も差分に色が付く。既存の表を改訂で
  `::: wide` で囲んで段抜きにしても、中身の差分だけが出る。番号つきの式の番号 `(N)` にも差分の色が付く。
- 回答書は `src/revise-report.md` に書く (`#` / `##` の見出し・査読コメントは引用ブロック。docx では見出しに番号が付かない・
  1 段組・行番号なし。見本は `data/dummy/abe/revise-report.md`)。回答書で示す行番号は、改訂稿の `manuscript.pdf` のページと行で数える
  (ABE の行番号はページごとに 1 から数え直す)。
- **査読コメント・回答書・編集部とのやりとりは秘密に保つ** (規定の通信の秘密)。公開のリポジトリや共有の場所に置かない。
- 受理後の校正刷りは受領から短い期限 (規定では 2 日以内) で返送する。

---

## 9. 動作例とフィクスチャ (data/dummy/)

`data/dummy/` の原稿はすべて**明らかなフィクション**で、<https://github.com/fk506cni/jami-pandoc-public> の
「tremendous hunch」(TJD/THS) の物語のパロディである。著者・機関・結果は架空で、実在の原稿が無くても全機能を
ビルドして確かめられるように置いてある。`data/dummy/abe/forms/` の書式も学会の書式ではなく、架空のダミーである。

| ディレクトリ | 中身 | 使い方 |
|-------------|------|--------|
| `data/dummy/` (直下) | 汎用の完結した原稿 (タイトル・著者・抄録・SVG / PDF / Mermaid の図・引用・表・テキストボックス) + リバイスレポート + カバーレター | `.development` を置いて `build.sh` / `diff.sh` / `package.sh` |
| `data/dummy/abe/` | ABE の骨格を埋めた完結原稿 (+ 段の図と段抜きの図・表・式・回答書・カバーレター・架空のダミー書式 4 本の `forms/`) | `--input data/dummy/abe --journal abe --article-type original` (学会テンプレートが要る)。規定チェックは要修正 0 件・参考 0 件 |
| `data/dummy/abe-lint/` | 規定に**合わない**原稿 (違反を仕込んである。一覧は `main.md` の冒頭) + `variants/` (同時には起こせない違反の変種: running title が無い・資金が節の外・AI の開示が無い / 表題ページの Div の欠落と重複) + `supplementary/` (容量とアーカイブの検査用) | validate に渡すと要修正 12 件 + 参考 15 件。件数と文面は `test_validate_abe.py` が照合する |
| `data/dummy/abe-csl/` | 規定の文献の出力例 6 件 + 回帰ガード 4 件の `expected.txt` + 本文の引用 17 件の `check.yaml` | `bash scripts/check-csl.sh` (既定のフィクスチャ)。`--docx` にはこのフィクスチャをビルドした docx を渡す |
| `data/dummy/regression/` | 回帰用の図 (PNG 図・段落内の複数図・テキストボックス内の図表・物理単位 / px 単位の SVG・Word で崩れる SVG の例) | `--input data/dummy/regression` を明示したときだけ回る |
| `data/dummy/regression/diff/` | 差分エンジンの受入テストの旧版と新版の対 10 組 (text / case / cell / tables / equation / figure / footnote / footnote-eq / relabel / wide) | `bash scripts/check-diff.sh` |
