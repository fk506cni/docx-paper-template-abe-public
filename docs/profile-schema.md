# profile.yaml のキー (profile-schema.md)

雑誌プロファイル `data/journals/<id>/profile.yaml` のキーの一覧。省略したときの動きと、どのモジュールが読むかを書く。
雑誌を足す手順は [`docs/usage-guide.md`](usage-guide.md) の §4、プロファイルが処理のどこで効くかは
[`docs/architecture.md`](architecture.md) にある。例は同梱の 2 誌 (`data/journals/_default/profile.yaml` と
`data/journals/abe/profile.yaml`) から採り、どちらも持たないキーには書き方の例を置いた。ABE のキーの値の根拠 (規定と学会テンプレートの
どこから採ったか) は `abe/profile.yaml` のコメントと [`docs/journal-abe.md`](journal-abe.md) の §14。

---

## 1. 読み方の約束

- **プロファイルは基底の既定値の上に重ねて読む**。既定値は `main/00_setup/lib/journal_profile.py` の `DEFAULTS` の 1 か所にあり、
  `load_resolved()` が「既定値 → `profile.yaml` → 記事種別」の順に重ねる (辞書は再帰的に重ね、リストはまるごと置き換える。
  例外は §5 の lint の禁止集合)。build (`build_docx.py`)・差分 (`diff_docx.py`)・パッケージ (`package.py`)・規定チェック
  (`validate.py`) はすべてこの解決済みのプロファイルを使う。
- **キーはすべて省略できる**。省略したときは「何もしない」側か、汎用の投稿フォーマットの値になる。新しいキーを足すときも
  この約束を守る (ほかの誌の出力を変えないため)。
- **誌の id で処理を分けない**。誌固有の要件はキーで表し、後処理はキーで発火させる。同じ要求を持つ別の誌は、同じキーを書けば
  同じ処理を受ける。
- **★ 印** — `journal_profile.py` のコメントにある ★ は、**誌固有の要件のために足した拡張キー**の目印である。汎用の投稿フォーマット
  (`_default`) は使わず、既定値はどれも「何もしない」側 (検査しない・組み替えない・制限しない・後処理を掛けない) になっている。
  つまり ★ のキーを書かない誌の出力は、そのキーが無かったときと変わらない。下の表では「拡張」の列に ★ を付けた。
- **体裁キー** (`line_spacing` など §3.2) の扱いは、`reference.docx` の作り方で 2 通りある (`docs/architecture.md` §3):
  - **体裁を焼き込む誌** (`_default` など): 体裁キーは `reference.docx` に焼き込む値で、読むのは `data/journals/make-reference.sh`
    だけ (build の実行時には読まない)。体裁を変えたら `bash data/journals/make-reference.sh <id>` を回し直す。忘れると build と
    規定チェックが、焼き込み済みの体裁と `profile.yaml` の食い違いを警告する。体裁キーの既定値は `make-reference.sh` の側にあり、
    `DEFAULTS` には置かない (同じ既定を 2 か所に書かないため)。
  - **雑誌のテンプレートを雛形にする誌** (`reference_base` を持つ誌。ABE): 体裁はテンプレートが持ち、焼き込まない。体裁キーは
    **照合用**で、`profile.yaml` に書いたキーだけを `reference.docx` と比べる (テンプレートが改版されて値が変わったことの検知)。
    行番号は `reference.docx` の最後の節 (= 本文の節) と比べる。
- 診断はすべて標準エラーに出る (`package.py figure-plan` の標準出力は機械が読む TSV のため)。
- `journal_profile.py` は `main/00_setup/lib/` にあり、ディレクトリ名が数字で始まるのでパッケージとして import できない。
  呼び出し側 (`main/stepNN_*/xxx.py`) は `sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))` で
  このディレクトリを足してから `import journal_profile` する。

---

## 2. ファイルの構成

```
data/journals/<id>/
├── profile.yaml         # このファイル
├── <id>.csl             # 引用様式 (csl: で指す。無ければ _default.csl を継承)
├── reference.docx       # pandoc の体裁の雛形 (reference_doc: で指す。生成物。git で追跡しない)
├── <テンプレート>.docx   # (任意) 雑誌が配る Word のテンプレート (reference_base: で指す。利用者が置く。git で追跡しない)
└── skeleton/            # (任意) 原稿骨格。ビルドの対象ではなく、写して書き始める雛形
```

---

## 3. キー一覧

「読み手」はそのキーを読むモジュール (`main/` の下のファイル名)。`make-reference.sh` は `data/journals/make-reference.sh`、
`ensure-reference.sh` は `scripts/lib/ensure-reference.sh`。

### 3.1 基本

| キー | 拡張 | 既定 | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `name` | | — | `"Advanced Biomedical Engineering"` | 表示名。`SUBMISSION.md` の見出しに出る | `package.py` |
| `publisher` | ★ | — | `"<発行者の名前>"` | 発行者 (記録用) | (なし) |
| `submission_system` | ★ | — | `"https://<投稿系の URL>"` | 投稿系の URL。`SUBMISSION.md` に出る | `package.py` |
| `csl` | | `null` | `abe.csl` | 引用様式 (このディレクトリからの相対パス)。`null` か、指すファイルが無ければ `_default.csl` (AMA 11th) を継承し、**build / diff が毎回その旨を警告する** (規定と違う引用様式のまま提出しないため) | `build_docx.py` / `diff_docx.py` |
| `reference_doc` | | `null` | `reference.docx` | pandoc の体裁の雛形。`null` か、指すファイルが無ければ `_default` のものを継承し、継承した体裁と `profile.yaml` の体裁キーの食い違いを警告する。`reference.docx` を指していてファイルが無ければ、build / diff が `make-reference.sh` で作る。別の名前 (雑誌が配るテンプレートをそのまま使う) は作らない | `build_docx.py` / `diff_docx.py` / `validate.py` / `ensure-reference.sh` |
| `reference_base` | ★ | `null` | `ABETemplate.docx` | **雑誌が配る Word のテンプレート** (このディレクトリからの相対名。利用者が置き、git で追跡しない)。あれば `make-reference.sh` (`patch_reference_docx.py --base`) がそれを雛形に `reference.docx` を作り、**体裁を焼き込まない** — 足すのは pandoc が使うスタイルの別名 (テンプレートに同名が無いものだけ)・見出しの番号定義の修正・題と副題の語の途中での改行の禁止で、見本の文章と文書を特定しうる情報は消して節の骨組みだけを残す。`ensure-reference.sh` は生成の元 (テンプレート・`profile.yaml`・生成処理。記録は `.reference.source`) が変われば作り直し、テンプレートが無ければ `reference_base_url` を出して止まる。生成の警告は `.reference.warnings` に記録し、作り直さずに使うときも build・diff のたびに出し直す。この誌では体裁キーは照合用 (§1) | `make-reference.sh` / `patch_reference_docx.py` / `ensure-reference.sh` / `journal_profile.py` |
| `reference_base_sha256` | ★ | `null` | (64 桁の 16 進) | テンプレートの指紋。違うテンプレート (改版など) が置かれたら `make-reference.sh` が**エラーで止まり** (build / diff も止まる)、新しい版を使うならこの値を書き換えるよう案内する (書き換えることが「新しい版を確かめた」印になる)。`null` なら照合しない | `make-reference.sh` / `ensure-reference.sh` |
| `reference_base_url` | ★ | `null` | `https://abe-journal.org/authorinstructions` | テンプレートが無いときの案内に出す取得元 (配布物への直接のリンクではなく、それを載せているページを書くのが安全) | `ensure-reference.sh` |

### 3.2 体裁 (焼き込む誌では reference.docx に焼き込み、テンプレートを雛形にする誌では照合する)

| キー | 拡張 | 既定 (`make-reference.sh`) | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `line_spacing` | | `double` | `double` (`_default`) | 行間 (`single` / `1.5` / `double`)。テンプレートの行間がこの 3 つで表せないとき (ABE の「最小 12 pt」など) は書かない | `make-reference.sh` |
| `line_numbers` | | `continuous` | `continuous` (`_default`) / `per-page` (`abe`) | 行番号 (`none` / `continuous` / `per-page`)。1 行目を 1 から数える | `make-reference.sh` |
| `page_numbers` | ★ | `false` | `true` | フッタの中央にページ番号 (`PAGE` フィールド)。`false` ならフッタの部品を作らない (焼き込む誌)。テンプレートを雛形にする誌ではフッタの有無の照合 | `make-reference.sh` |
| `font` | | `"Times New Roman"` | `"Times New Roman"` | 本文のフォント | `make-reference.sh` |
| `font_size` | | `12` | `12pt` (`_default`) / `10.5pt` (`abe`) | 本文の文字の大きさ。焼き込む誌では抄録 (`Abstract` スタイル) も同じ大きさにする (pandoc の既定は 10pt)。題と見出しは本文より大きいまま | `make-reference.sh` |
| `margins` | | `25` | `25mm` (`_default`) / `{top: 25mm, bottom: 20mm, left: 15mm, right: 15mm}` (`abe`) | 余白。スカラは四辺一律の値。**辺ごとの辞書も書ける**が、照合にだけ使う (テンプレートを雛形にする誌で辺ごとに比べる)。体裁を焼き込む誌で辞書を書くと `make-reference.sh` が止まる (焼き込みは四辺一律) | `make-reference.sh` |
| `paper_size` | | `a4` | `a4` | 用紙 (`a4` / `letter`) | `make-reference.sh` |
| `text_styles.uniform_size` | ★ | `false` | `true` | `true` なら級数を持つ段落・文字スタイル (題・副題・著者・日付・抄録・見出し 1〜3 など) をすべて本文の級数 (`font_size`) にそろえ、見出しの階層を強調で付ける (題・見出し 1 = 太字 / 見出し 2 = 太字斜体 / 見出し 3 = 斜体)。題を継ぐ著者・日付・副題には、継いだ強調を打ち消す (焼き込む誌) | `make-reference.sh` |
| `text_styles.heading_color` | ★ | `keep` | `black` | `black` なら題・見出しのテーマ色 (pandoc の既定は青) を外して自動色にする (焼き込む誌) | `make-reference.sh` |
| `text_styles.uniform_line_spacing` | ★ | `false` | `true` | `true` なら段落スタイルが個別に持つ行送りを外し、文書全体の行送り (`line_spacing`) にそろえる (段落の前後の空きは残す)。題 (`Title`) の行送りは、このキーが無くても本文の行送りに直す (焼き込む誌) | `make-reference.sh` |
| `line_numbers_scope` | ★ | `all` | `manuscript` | 行番号を付ける文書。`all` = すべて / `manuscript` = `main.md` だけ (cover-letter / revise-report の docx から行番号を外す)。**体裁キーで唯一 build が読む** (節設定から外す形で効かせるので、`make-reference.sh` の再実行は要らない) | `build_docx.py` |

食い違いの検算 (build と規定チェック) は `line_spacing` / `line_numbers` / `page_numbers` / `font` / `font_size` /
`margins` / `paper_size` を `reference.docx` と比べる (テンプレートを雛形にする誌では `profile.yaml` に書いたものだけ)。
焼き込む誌の `font_size` は抄録 (`Abstract` スタイル) の大きさとも比べる (抄録が本文より小さい古い `reference.docx` を見つけるため)。
`text_styles.*` は比べないので、変えたら `make-reference.sh` を回し直すのを忘れないこと。

### 3.3 図 (`figures`)

| キー | 拡張 | 既定 | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `figures.embed` | | `true` | `true` | `package.sh` の既定のモード。`true` → 草稿 (図を埋め込む) / `false` → 最終。`--mode` で上書き | `package.py` |
| `figures.separate` | ★ | `true` | `false` (`abe`) | 提出用 (`--mode final` かつ `--keep-figures` なし) で図を本文から外して別ファイルにするか。`true` = 図を外し、表の移設・図凡例の集約も行う / `false` = **図を本文に埋め込んだまま提出用にする** (`main.docx` をそのまま `manuscript.docx` にし、`figures/` と `CAPTIONS.md` を作らない。出所の照合・`SUBMISSION.md`・roundtrip の配送は提出用として働く)。`false` では `figures.formats` / `numbering` を使わない。`tables.placement` の `end` / `separate`・`figures.legends_section` とは併用できない (profile を読むときに止まる)。設計は `docs/journal-abe.md` §14.1 | `journal_profile.py` (`figures_separate()`) / `package.py` / `relocate.py` / `validate.py` |
| `figures.formats` | | `[pdf]` | `[pdf]` (`_default`) / `[pptx, png, tif]` | 図を外す誌の最終提出の図の形式。**先頭が主形式**。作れるのは `pdf` / `png` / `pptx`。`eps` → pdf / `tiff` (`tif`) → png は警告つきで代わりに作り、作れない形式は止まる。`--format` で上書き | `package.py` |
| `figures.dpi` | | `300` | `300` | ラスタ図と PNG フォールバックの解像度。`--dpi` で上書き。`check-figures.sh --journal <id>` の目標にもなる | `package.py` / `check_dpi.py` |
| `figures.font_handling` | | `outline` | `outline` | PDF 図の文字 (`outline` = アウトライン化 / `embed` = 埋め込み)。pptx の経路では PNG フォールバックの生成にだけ効く | `package.py` |
| `figures.keep_together` | ★ | `false` | `true` (`abe`) | 図 → 題 → 凡例を keepNext でつなぎ、段・ページで分けない | `captions.py` |
| `figures.pptx.mode` | ★ | `svg-blob` | `svg-blob` | pptx の作り方。`svg-blob` = 案 B (SVG を埋め込んで生成。図の隣に同名の `.pptx` があれば案 A) / `passthrough` = 案 A (執筆者の pptx を無変換でコピー) / `native-shapes` = 案 B′ (作っていない。指定すると止まる)。呼び名は `docs/architecture.md` §2.5。綴りの誤りも止まる | `package.py` |
| `figures.pptx.slide_fit` | ★ | `figure` | `figure` | スライドの寸法。`figure` = 図の公称サイズ (1 inch 未満の軸は広げて中央に置き、56 inch 超は止まる) / `fixed` = 既定の寸法に縮めて置く。`--slide-fit` で上書き | `package.py` |
| `figures.pptx.png_fallback_dpi` | ★ | `null` | `null` | pptx に同梱する PNG の解像度。`null` なら `figures.dpi` を写す (同じ値を 2 か所に書かないため) | `package.py` / `journal_profile.py` |
| `figures.pptx.text_to_path` | ★ | `false` | `true` | 埋め込む SVG の文字をアウトライン化するか (`true` なら svg-conversion を使う)。既定は `false` — 組版で組み直す誌では文字を図形にすると直せなくなるため。投稿系が図をどの描画系で描くか分からない誌では `true` にすると、受け側の書体と文字の描き方に左右されない | `package.py` |
| `figures.pptx.inline_css` | ★ | `false` | `true` | 埋め込む SVG の CSS (svglite・Mermaid・matplotlib の `<style>`) を各要素の `style` へ書き出し、`<style>` を外すか (`main/00_setup/lib/svg_safe.py`)。SVG の CSS を適用しない描画系 (例: Aspose.Slides) は、塗りの指定の無い図形を既定の黒で塗る (svglite の図ではパネルの枠がパネルを隠す)。あわせて `rgba()` / `hsl()` と `grey` 系の色名・合計 0 や奇数個の値の点線・線の無い図形の `opacity`・要素の `!important` を、CSS を読む描画系では同じ見た目の形に直す。書き換えの前後を Chromium で描くと画素が一致する。`text_to_path` と併用すると、書き出してから輪郭化する。対応外の CSS (`+` `~` の結合子・擬似クラス・`@media`・定義の無い変数・ルート以外での変数の定義・`foreignObject` の中の HTML に当たる規則 (Mermaid の journey 図) など) を見つけたら止まる。案 A の pptx には掛からない | `package.py` / `journal_profile.py` |
| `figures.legends_section` | ★ | `null` | `"Figure Legends"` | 最終モードで図の題 + 凡例を References の後へ集めるときの見出し。`null` なら集めない | `relocate.py` / `package.py` / `validate.py` |
| `figures.title_words` | ★ | `null` | `15` | 図の題の語数の上限 (キャプションだけを数え、`Figure 1: ` は含めない) | `validate.py` |
| `figures.legend_words` | ★ | `null` | `300` | 図の凡例 (直後の `Legend` Div) の語数の上限 | `validate.py` |
| `figures.keys_in_graphic` | ★ | `false` | `true` | 凡例のキーを画像の中に入れる要件 (記録用。画像の中身は判定できないので検査しない) | (なし) |
| `figures.multipanel_single_file` | ★ | `false` | `true` | 多パネル図を 1 ファイルに合成する要件 (記録用。同上) | (なし) |
| `figures.vector_container` | ★ | `null` | `pptx` | ベクターを載せる容器 (予約キー。主形式は `figures.formats` の先頭が決めるので、今は読まない) | (なし) |
| `figures.placement` | | `inline` | `inline` (`_default`) | 図表の置き場所 (予約キー。**読まない**。組み替えの発火には `figures.legends_section` と `tables.placement` を使う) | (なし) |

### 3.4 表 (`tables`)

| キー | 拡張 | 既定 | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `tables.placement` | ★ | `inline` | `inline` (`abe`) / `separate` | 最終モードでの表 (題 + 表 + 直後の `Legend` 段落) の置き場所。`end` なら文書の末尾へ移し、`separate` なら本文から外して `tables/TableN.docx` に 1 表 1 ファイルで出す (テキストボックスの中の表は動かさない)。どちらも元の位置に `[Table N about here]` を残す。`inline` / `end` / `separate` 以外の綴りと空の値は止める | `relocate.py` / `package.py` / `validate.py` |
| `tables.legend_position` | ★ | `below` | `above` (`abe`) | 表の凡例 (`Legend` Div) の位置。`below` = 表の下 / `above` = 後処理が表の直後の凡例を題と表の間へ移し、題 → 凡例 → 表を keepNext でつなぐ (「表の題とキャプションは表の上」の誌。原稿では凡例を表の後に書くまま)。`tables.placement` の `end` / `separate` とは併用できない (build・diff・package が止まる) | `captions.py` / `build_docx.py` / `package.py` |
| `tables.section_title` | ★ | `null` | `null` | `end` で末尾へ移した表の前に置く見出し。`null` なら見出しを置かず改ページだけ (規定に無い文字列を提出物に足さない) | `relocate.py` |
| `tables.allow_color` | ★ | `true` | `false` | `false` なら表の網掛け・文字色・蛍光ペン・罫線の色を警告する (草稿モードでも) | `relocate.py` |
| `tables.thousands_separator` | ★ | `true` | `false` | `false` なら `1,234` の形の数値を指摘する (本文と表の両方。URL・References・コードは除く) | `validate.py` |
| `tables.title_words` | ★ | `null` | `15` | 表の題 (キャプション) の語数の上限 | `validate.py` |
| `tables.legend_words` | ★ | `null` | `300` | 表の凡例の語数の上限 | `validate.py` |
| `tables.object` | ★ | `null` | `word` | 表の作り方の要件 (`word` = Word の表で作る)。`SUBMISSION.md` の注記に出る | `package.py` |
| `tables.separate_file_allowed` | ★ | `true` | `true` | 表を別ファイルで出してよいか。`SUBMISSION.md` の注記に出る | `package.py` |

### 3.5 上限 (`limits`)

| キー | 拡張 | 既定 | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `limits.word_count` | | `null` | `4000` | 本文語数の上限 (数え方は `docs/architecture.md` §2.5 の「規定チェック」)。記事種別ごとに変わる誌は `article_types` に書く | `validate.py` |
| `limits.abstract_words` | | `null` | `250` (`_default`) / `350` (`abe`) | 抄録の語数の上限 (英数字を含む語の数と空白区切りの語の数の大きいほうで判定する) | `validate.py` |
| `limits.references` | | `null` | `null` | 文献数の上限 | `validate.py` |
| `limits.figures_tables` | ★ | `null` | `8` | 図表の合計点数の上限。本文の流れの上にある図と表を数える (番号の無い装飾画像も数える。`.grid` の中は数え、`.textbox` の中は数えない)。値があると、数えなかった `.textbox` の中の図表を要修正にする | `validate.py` |
| `limits.title_words` | ★ | `null` | `30` | タイトルの語数の上限。あわせてタイトルの全大文字の語 (略語らしい語) を参考情報に挙げる | `validate.py` |
| `limits.keywords` | | `null` | `5` (`abe`) / `[3, 5]` | キーワードの数。`[下限, 上限]`、またはスカラ `N` (= 上限だけ。`[1, N]` と読む) | `validate.py` |
| `limits.running_title_chars` | ★ | `null` | `50` (`abe`) | 題 (空白込みの字数) がこれを超えるなら running title (`header.running_title_from` の custom-style。未指定なら `Subtitle`) が要り、running title もこれ以内 (どちらも要修正) | `validate.py` |
| `limits.supplementary_file_mb` / `limits.supplementary_total_mb` | ★ | `null` | `50` / `50` (`abe`) | `<入力ルート>/supplementary/` の 1 ファイルの上限と合計の上限 (MB = 1 000 000 バイト。動画に限らない。超過は要修正。`SUBMISSION.md` の補足資料の節にも出る) | `validate.py` / `package.py` |
| `limits.video_mb` | ★ | `null` | `50` | 補足資料の動画 1 ファイルの上限 (MB。10 進) | `package.py` |

### 3.6 抄録・匿名化・番号 (`abstract` / `blinded` / `numbering`)

| キー | 拡張 | 既定 | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `abstract.structured` | | `false` | `false` | 構造化抄録か | `validate.py` |
| `abstract.labels` | ★ | `null` | `[Objective, Methods, Results, Conclusion]` | 構造化抄録の見出し。書いた誌では全ラベルの有無を 1 つずつ確かめ、欠けたものを名指しする。書かない誌は既定の 4 ラベル (Background / Methods / Results / Conclusions) のどれか 1 つで合格 | `validate.py` |
| `abstract.citations_allowed` | ★ | `true` | `false` (`abe`) | `false` なら抄録の中の文献引用 (`@key`) を指摘する。手で書いた番号の引用 (`[2]`) は参考情報で知らせる | `validate.py` |
| `abstract.single_paragraph` | ★ | `false` | `true` (`abe`) | `true` なら抄録が 2 段落以上のとき要修正 | `validate.py` |
| `abstract.floats_allowed` | ★ | `true` | `false` (`abe`) | `false` なら抄録が図表に触れていたら参考情報 | `validate.py` |
| `abstract.keyword_source` | ★ | `null` | `MeSH` | キーワードの語彙 (記録用。シソーラスを同梱しないので検査しない。数は `limits.keywords` が見る) | (なし) |
| `blinded` | | `false` | `false` | 匿名版を求める誌か。`true` なら `package.sh` が「伏せる作業は手で」と注意を出す (自動の匿名化は無い) | `package.py` |
| `numbering.figure` | | `"Figure %d."` | `"Figure %d."` (`_default`) | 図を外す誌で、分離した図のファイル名に使う書式 (`"Figure %d."` → `Figure1.pdf` / `"Fig. %d"` → `Fig1.pdf`)。本文と題の `Figure 1` / `Fig. 1` は `crossref` (§3.13) が決める | `package.py` |
| `numbering.table` | | `"Table %d."` | `"Table %d."` | 表の番号の書式 (記録用。本文の表の番号は pandoc-crossref の設定が決める) | (なし) |

### 3.7 記事種別 (`article_type` / `article_types`)

| キー | 拡張 | 既定 | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `article_type` | ★ | `null` | `original` | 既定の記事種別。`--article-type` で上書き | `journal_profile.py` |
| `article_types.<id>` | ★ | `null` | (下) | 種別ごとの上限と構成。解決のときに `limits` / `abstract` に重ねる (§4) | `journal_profile.py` |

`article_types.<id>` の中のキー:

| キー | 重ねる先 | 例 |
|------|---------|-----|
| `word_count` | `limits.word_count` | `4000` (`abe` の `original`) / `null` (`abe` の `review` = 照合しない) |
| `abstract_words` | `limits.abstract_words` | `300` |
| `figures_tables` | `limits.figures_tables` | `8` |
| `abstract_structured` | `abstract.structured` | `true` |
| `abstract_labels` | `abstract.labels` | `[Objective, Methods, Results, Conclusion]` |
| `name` | (参照用) | `"Original Paper"` (`abe`。`SUBMISSION.md` に出る) |
| `sections` | (参照用) | 規定の本文の構成の写し。節の検査には使わない (必須の節の検査は §3.14 の `sections.required`) |
| `note` | (参照用) | 種別ごとの補足 |

### 3.8 Declarations (`declarations`)

Declarations の節に必須の項目を並べる誌のためのキー。同梱の 2 誌は持たない。

| キー | 拡張 | 既定 | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `declarations.required` | ★ | `null` | `["Funding", "Competing interests"]` | 必須の Declarations の項目名。`# Declarations` から次の同じレベル以上の見出しまでを範囲にし、項目名と見出しを正規化 (小文字化・空白の畳み込み・アポストロフィの統一) して突き合わせる。最上位の節を探す `sections.required` (§3.14) とは別物 | `validate.py` |
| `declarations.abbreviations_section` | ★ | `false` | `true` | Abstract と Introduction の間に略語の一覧を置く誌か。`true` なら `# Abbreviations` 節を本文語数の対象にせず、位置を確かめる (節が無いことは参考情報にとどめる) | `validate.py` |
| `declarations.credit` | ★ | `false` | `true` | 著者の貢献を CRediT で書く誌か (記録用) | (なし) |

### 3.9 提出物 (`submission`)

| キー | 拡張 | 既定 | 例 | 説明 | 読み手 |
|------|------|------|-----|------|--------|
| `submission.text_formats` | ★ | `null` | `[pdf]` (`abe`) / `[docx]` | 本文の受入形式。**これがある誌にだけ `SUBMISSION.md` を出す**。`[pdf]` の誌は、roundtrip が `manuscript.docx` を Word で PDF にして `manuscript.pdf` を作る (`.upload-as-pdf` に載せる) | `package.py` |
| `submission.table_formats` | ★ | `null` | `[docx, xlsx, pptx]` | 表の受入形式 (`SUBMISSION.md` の注記) | `package.py` |
| `submission.figure_formats` | ★ | `null` | `[jpeg, tif, png, pptx]` | 図の受入形式。書いた誌では、実際に作る形式をこれと照合し、外れたら止める (代わりの形式なら止め、明示した形式なら `--allow-disallowed-format` を求める)。受入形式の記録なので、ここにあっても作れるとは限らない (`jpeg` は作らない) | `package.py` |
| `submission.video_formats` | ★ | `null` | `[mp4]` | 動画の受入形式 (動画の分類は拡張子で行い、これは照合にだけ使う) | `package.py` |
| `submission.forms` | ★ | `null` | `["Submission Form and Author Statement (1 通。…)", "COI 開示書式 (著者ごとに 1 通。…)", …]` (`abe`) | 別に出すフォーム・書類。文字列のまま `SUBMISSION.md` のチェック欄になるので、通数と記入者は注記として書く | `package.py` |
| `submission.collect_forms` | ★ | `false` | `true` (`abe`) | `<入力ルート>/forms/` の直下の記入済みの書式 (docx / PDF) を提出パッケージの `forms/` に無変換で複製し、`SUBMISSION.md` に一覧を出す。docx の書式は roundtrip が Word で PDF にして `submission-<id>/forms/` に置く (同じ名前の PDF を置いた書式はその PDF を使う)。拡張子は小文字にそろえて写す (名前が重なれば止まる) | `package.py` |
| `submission.supplementary` | ★ | `null` | `as-is` / 文字列 (`abe`) | 補足資料の扱い。`as-is` なら「受理後は変更できない」旨の決まった文を注意に出し、それ以外の文字列はそのまま `SUBMISSION.md` の補足資料の節に書く (複製はどの誌でも無変換) | `package.py` |
| `submission.diff_note` | ★ | `null` | 文字列 (`abe`) | `SUBMISSION.md` で差分 docx (`manuscript-diff.docx`) の行の下に書く注記 | `package.py` |

### 3.10 執筆の検査 (`lint`)

既定値は基底 (`DEFAULTS`) に置いてあり、`lint` を書かない誌にも効く (§5)。基底で有効なのは上の 4 つ (`forbid_chars` /
`units` / `placeholder_markers` / `legend_placement`) で、ほかは誌が有効にしたときだけ働く。

| キー | 拡張 | 既定 (基底) | 例 | 説明 | 読み手 |
|------|------|------------|-----------|------|--------|
| `lint.forbid_chars` | ★ | `["℃", "℉", "㎎", "㎏", "㎜", "㎝", "㎡", "㎥", "㎕", "㎖", "㎗"]` | (基底のまま) | 使ってはいけない合成済みの 1 文字。行番号つきで指摘し、`°C` などの書き方を案内する。**誌の値は基底に足される** (§5) | `validate.py` |
| `lint.units` | ★ | `SI` | (基底のまま) | 英米の慣用単位 (`°F` / Fahrenheit / inch / lb / pound / ounce / mile / gallon。大文字と小文字を区別する) を拾って参考情報に出す (SI に従っていることの証明ではない) | `validate.py` |
| `lint.placeholder_markers` | ★ | `true` | (基底のまま) | 骨格の記入欄 `<<...>>` の残り (`main.md` / `cover-letter.md` / `revise-report.md`) | `validate.py` |
| `lint.legend_placement` | ★ | `true` | (基底のまま) | 凡例 Div の配置 (直前が図表か・`for` が実在し直前の図表と一致するか・`for` の欠落) と、中身が段落だけか | `validate.py` |
| `lint.device_notation` | ★ | `false` | `true` | 統計ソフト (綴りの決まった 11 種) に版と括弧内の製造元があるか (機器一般は文面から判定できないので見ない) | `validate.py` |
| `lint.corresponding_author` | ★ | `false` | `true` | `custom-style="Corresponding"` Div が 1 つで、住所・電話・E-mail を備えているか (表題ページに連絡著者を書く誌) | `validate.py` |
| `lint.langid_japanese_only` | ★ | `false` | `true` | `ref.bib` に、`note` が無いまま日本語以外の `langid` (または `hyphenation`) を持つ文献が無いか。英語の文献は `langid` を消し、和文以外の非英語は `langid` を残して `note` を足すよう案内する (`note` の無い文献では `langid` があるだけで言語の注記を付ける引用様式を使う誌で有効にする) | `validate.py` |
| `lint.author_surname_caps` | ★ | `false` | `true` (`abe`) | **要修正**: 著者 (`Author` の Div) の姓がすべて大文字か。著者はカンマ・強制改行・改行で割り、`Jr.` / `II` などは名前の一部とし、学位・敬称 (`PhD` / `MD` / `Dr.` など) は姓の判定から除いて参考で知らせる | `validate.py` |
| `lint.keywords_not_in_title` | ★ | `false` | `true` (`abe`) | **要修正**: キーワードが題の語 (冠詞・前置詞などを除く) を繰り返していないか。ハイフンの接頭辞 (`non` / `self` / `real` など) を外し、不規則な複数形も同一視する | `validate.py` |
| `lint.float_titles` | ★ | `false` | `true` (`abe`) | **要修正**: 題 (キャプション) の無い図表 | `validate.py` |
| `lint.unstructured_abstract` | ★ | `false` | `true` (`abe`) | **要修正**: 抄録が見出しつきの構造化抄録の形 (`**Background:** …` / `Objective:` など) か。`abstract.structured` が偽の誌で使う。`abstract.single_paragraph` の段落数の助言も、見出しがあれば「見出しの無い 1 段落の文章に直す」にする | `validate.py` |
| `lint.front_matter_divs` | ★ | `null` | `["Title", "Author", "Abstract", "Keywords"]` (`abe`) | **要修正**: ここに挙げた custom-style の Div がちょうど 1 つずつあるか (無い・2 つ以上で要修正)。表題ページの検査は Div を読むので、Div が無い・重なると黙って空振りするため | `validate.py` |
| `lint.table_caption_attrs` | ★ | `false` | `true` (`abe`) | **要修正**: 表の題の属性に `{#tbl:x}` 以外のもの (`{#tbl:x .wide}` など) があるか (pandoc-crossref が番号を付けられず、題に属性の文字が残り参照が `¿tbl:x?` になる。段抜きは `::: wide` の Div)。段組の誌の build でも `wide-blocks.lua` が警告する | `validate.py` |
| `lint.affiliation_superscript` | ★ | `false` | `true` (`abe`) | 参考: 機関が 2 つ以上なら所属と著者が上付きの数字で対応づけられているか | `validate.py` |
| `lint.title_conventions` | ★ | `false` | `true` (`abe`) | 参考: 題の略語 (分野で一般的なもの以外) とシリーズ番号 (Part II など) | `validate.py` |
| `lint.caption_minimal_caps` | ★ | `false` | `true` (`abe`) | 参考: 図表の題が Title Case らしい (最小限の大文字を求める誌) | `validate.py` |
| `lint.abbreviation_definitions` | ★ | `false` | `true` (`abe`) | 参考: 略語を本文の初出で括弧で定義しているか (題と抄録での定義は本文の初出とみなさない) | `validate.py` |
| `lint.uncitable_references` | ★ | `false` | `true` (`abe`) | 参考: 引けない文献 (社内資料・未発表原稿・未発表の学位論文・私信・カタログ。`ref.bib` の型と `note` から推し量る) | `validate.py` |
| `lint.supplementary_archives` | ★ | `false` | `true` (`abe`) | 参考: 補足資料にアーカイブ・実行形式のファイルがある (拡張子で見る) | `validate.py` |
| `lint.coi_section` / `lint.coi_standard_sentence` | ★ | `null` | `"Conflicts of interest"` / 規定の定型文 (全文) (`abe`) | 参考: この節に、利益相反が無い場合の定型文も具体的な申告も無さそうなら知らせる (定型文は誌が定めるものなのでコードに置かない) | `validate.py` |
| `lint.ethics_section` | ★ | `null` | `"Ethics declaration"` (`abe`) | 参考: 人・動物を扱うらしい語があるのにこの節が無い | `validate.py` |
| `lint.ai_disclosure_section` | ★ | `null` | `"Materials and methods"` (`abe`) | 参考: AI ツールらしき語がこの節の外にだけある・どこにも無い (開示の置き場所は誌によって違う) | `validate.py` |
| `lint.funding_section` | ★ | `null` | `"Acknowledgements"` (`abe`) | 参考: 資金らしき語があるのにこの節に無い・この節に助成番号らしき語が無い | `validate.py` |

`lint.*_section` の節の名前は、`sections.aliases` (§3.14) の言い換えも同じ節とみなす。

### 3.11 見出し・柱・表題ページ (`headings` / `header` / `title_page`)

雑誌のテンプレートの見出し・柱・表題ページの形に合わせる後処理のキー。どれも省略すれば何もしない。

| キー | 拡張 | 既定 | 例 (`abe`) | 説明 | 読み手 |
|------|------|------|-----------|------|--------|
| `headings.unnumbered_style` | ★ | `null` | `NoNumberSectionHeader` | `{.unnumbered}` の見出しを置き換える段落スタイルの名前 (見出しの段によらず 1 つ)。テンプレートの見出しのスタイルが自動番号を持つ誌で、番号の要らない節を番号なしにする。build / diff が citeproc の後に `unnumbered-style.lua` を掛ける (`null` なら pandoc の引数も足さない) | `unnumbered-style.lua` / `build_docx.py` / `diff_docx.py` |
| `headings.numbered_scope` | ★ | `all` | `manuscript` | 見出しの自動番号を残す文書の範囲。`all` = すべて / `manuscript` = 本文 (`main.md` と差分) 以外 (回答書・カバーレター) の見出しの段落に番号の打ち消し (`w:numPr/w:numId=0`) を直に置く (見出しのスタイルは残る) | `frontmatter.py` |
| `header.running_title_from` | ★ | `null` | `Subtitle` | この custom-style の最初の段落の文字を柱の中央に入れる (その段落が無い文書は中央を空にする。差分 docx は削除の文字を除く) | `frontmatter.py` |
| `header.clear_template_labels` | ★ | `false` | `true` | 柱の左右のテンプレートの表示を消す。柱が「左 TAB 中央 TAB 右」の 1 段落でなければ警告して触らない | `frontmatter.py` |
| `title_page.affiliation_label_tab` | ★ | `false` | `true` | 所属 (custom-style `Affiliation`) の段落の先頭の上付きの番号の直後にタブだけの run を入れる (番号の後の空白は消す。番号の無い所属は触らない)。テンプレートの所属のぶら下げ字下げにそろえるため | `frontmatter.py` |
| `title_page.author_footnote_marks` | ★ | `null` | `["*", "**", "***", "****"]` | 著者 (custom-style `Author`) の段落の中の脚注 (原稿は著者名の直後の `^[Present address: …]`) の参照と脚注の番号を、出てきた順にこの記号にする (Word の記号の脚注 = `w:customMarkFollows`。Word の自動番号は記号の脚注を数えない)。**文面の同じ脚注は先の脚注と同じ記号にし、脚注は 1 つにまとめる**。記号が足りなければ残りは数字のまま (警告)。差分 docx では削除した脚注を旧版の並び、ほかを新版の並びで数える。ほかの脚注は数字のまま。リストでない・空・同じ記号が 2 度ある値は警告して使わない | `frontmatter.py` |

### 3.12 段組 (`layout`)

本文を段組にする誌のためのキー。`layout.columns` が 2 以上のときだけ働く。原稿には段組を書かない (同じ原稿を段組の無い誌でも組める)。

| キー | 拡張 | 既定 | 例 (`abe`) | 説明 | 読み手 |
|------|------|------|-----------|------|--------|
| `layout.columns` | ★ | `null` | `2` | 本文の節の段数。**2 以上のときだけ働く**。reference.docx が節を 2 つ持てば本文の節はその最後の `sectPr` の写しで、この値は照合に使う (違えば警告)。1 つしか持たなければこの値と `column_space` で本文の節を作る | `layout.py` / `build_docx.py` / `diff_docx.py` |
| `layout.column_space` | ★ | `null` | `13.3mm` | 段間 (単位必須)。照合か、本文の節を作るときの値 | `layout.py` |
| `layout.title_block_until` | ★ | `null` | `Keywords` | このスタイルの段落の並びの最後までを 1 段組の表題部の節にする。本文に無ければ警告して組み立てない。表題部の節が 2 段組以上の雛形でも 1 段組に直して警告する | `layout.py` |
| `layout.title_page_break` | ★ | `false` | `true` | 表題部の後で改ページし、表題ページを独立させる (表題部の最後の段落の後に改ページだけの段落 → 表題部の `sectPr` を持つ段落) | `layout.py` |
| `layout.scope` | ★ | `manuscript` | `manuscript` | `manuscript` = 本文 (`main.md` と差分) だけを段組にする / `all` = カバーレターと回答書も段組にする | `layout.py` |

段抜き (段をまたいで本文幅に置く) は原稿の記法で書く: 図は `{.wide}`、表など任意のブロックは `::: wide` の Div
(`wide-blocks.lua` が目印を付け、`layout.py` が 1 段組の節で挟む)。段の幅を超える段の図は `layout.py` が段の幅に縮めて警告する。

### 3.13 図表の題・式・文献 (`crossref` / `equations` / `bibliography`)

| キー | 拡張 | 既定 | 例 (`abe`) | 説明 | 読み手 |
|------|------|------|-----------|------|--------|
| `crossref` | ★ | `null` | `{figureTitle: "Fig.", tableTitle: "Table", titleDelim: "", figPrefix: ["Fig.", "Figs."], tblPrefix: ["Table", "Tables"]}` | `main/00_setup/defaults.yaml` の pandoc-crossref の metadata の誌ごとの上書き (同じ名前と形で書く。知らない名前は警告して渡す)。build と diff が metadata だけを書いた 2 つ目の `--defaults` にして渡す。図表の題 (`Fig. 1 題`) と本文の参照の語 (`Fig. 1` / `Table 1`) が変わる | `build_docx.py` / `diff_docx.py` / `journal_profile.py` |
| `equations.style` | ★ | `null` | `Equation` | pandoc-crossref が番号を付けた別行立ての式 (`$$ … $$ {#eq:x}`) の段落をこのスタイルの「`m:oMath` TAB `(N)`」にする (式番号がスタイルの右タブで段の右端に寄る。段抜きの節ではタブを本文幅に置き直す)。タブの基準の段の幅は reference.docx の本文の節から取る。差分 docx では番号 `(N)` にも差分の色が付く。`null` なら番号は式のすぐ右・中央 | `equations.py` |
| `bibliography.label_separator` | ★ | `space-tab` | `tab` | 文献の段落の番号と本文の区切り。`space-tab` = pandoc の「番号 空白 TAB 本文」のまま / `tab` = 番号の後の空白を消す (番号 + 空白がぶら下げ字下げを越えて本文の頭が次のタブ位置へ飛ぶのを防ぐ)。引用の受入テスト (`check-csl.sh --docx`) は、フィクスチャの `check.yaml` の `bibliography_label` があれば、文献の段落が「番号 + この区切り + 本文」で始まることを照合する | `postprocess.py` / `check_csl.py` |

### 3.14 必須の節 (`sections`)

| キー | 拡張 | 既定 | 例 (`abe`) | 説明 | 読み手 |
|------|------|------|-----------|------|--------|
| `sections.required` | ★ | `null` | `["Introduction", "Materials and methods", "Results", "Discussion", "Conflicts of interest", "References"]` | 必ず要る**最上位の節**の名前。原稿のいちばん浅い段の見出しで探し、無ければ要修正 (pandoc が足す文献の見出しも数える)。図を本文に埋め込む誌の `SUBMISSION.md` の構成の行にも使う | `validate.py` / `package.py` |
| `sections.aliases` | ★ | `null` | `[["Materials and methods", "Methods", "Patients and methods", "Subjects and methods", "Methodology"], ["Acknowledgements", "Acknowledgments"], …]` | 同じ節とみなす名前の組の list。`sections.required` と `lint.*_section` が使う。大文字小文字・語末の s・`&` と `and` の違いは組に書かなくても同一視する。照合は語の境界での一致 (`Resultant observations` を `Results` とみなさない) | `validate.py` |

---

## 4. 記事種別の解決

- **優先順**: `--article-type` > `profile.article_type` > (どちらも無い) `limits` / `abstract` をそのまま使う。
- **(a) 重ね方は深さ 1 の部分的な上書き** (まるごと置き換えない)。まるごと置き換えると、誌全体の規定
  (`abstract.citations_allowed` など) まで消えるため。ただし `abstract_structured: false` の種別では `abstract.labels` を空にする
  (前の種別のラベルが残らないように)。
- **(b) 重ねる先**は §3.7 の表のとおり。`name` / `note` / `sections` は解決に使わない。`word_count: null` の種別 (ABE の Review Paper) は
  本文語数を照合しない。
- **(c)** `article_types` はあるが種別の指定が無い → `limits` / `abstract` をそのまま使い、警告する。
- **(d)** 存在しない種別を指定 → **有効な一覧を出して止まる** (綴りの誤りで上限の検査が黙って外れないように)。
- **(e)** `article_types` を持たない誌に `--article-type` を渡す → 警告して無視する。
- **(f)** `limits.keywords` はスカラ `N` を `[1, N]` に直す。
- 解決は冪等 (解決済みのプロファイルを渡しても二重に重ねない)。build と差分は種別で出力を変えないが、未知の種別を早く止めるために
  `--article-type` を受け付ける。

---

## 5. lint の 2 層構成

- 合成済みの文字を避けること (`forbid_chars`) と SI 単位 (`units`) は欧文の組版と医学系の誌の一般則で、記入欄
  (`placeholder_markers`) と凡例の配置 (`legend_placement`) は本テンプレートの記法の規約である。特定の誌のプロファイルにだけ
  置くと、同じ原稿を別の誌でパッケージしたとたんに検査が消え、「原稿は雑誌に依存させない」という原則と食い違う。
  そこで**既定値を基底 (`DEFAULTS`) に置き、誌の側は上書きと追加だけ**にした。誌ごとに要否が分かれるもの (`device_notation`・
  `corresponding_author`・表題ページと節と定型の記述の検査など) は基底で無効にしてある。
- **基底から来た指摘には出所を添える**。その誌の `profile.yaml` が自分で書いていない `lint` のキーから出た指摘には、文末に
  **`(本テンプレ共通の作法)`** が付く (その誌の規定を調べた結果ではないため)。
- **禁止集合 (`forbid_` で始まるリストのキー) は「基底 ∪ 誌」で解決する**。リストをまるごと置き換えると、誌が基底より少ない
  文字を書いたときに、規定を持つその誌でだけ残りの文字が素通りするため。一覧を狭めたい誌は `forbid_chars: null` と書いて
  **検査そのものを無効にする** (意思表示をはっきりさせる)。`null` を見ると警告を 1 行出す (YAML では値を書き忘れても `null` に
  なり、区別できないため)。基底に無い `lint` のキー (`lint.forbid_char` のような綴りの誤り) にも警告を出す。
- **この規則を lint の外へ広げない**。`figures.formats` / `abstract.labels` / `submission.*_formats` は「誌の値で置き換える」が
  正しい意味である。将来 lint に許可リスト (`allow_*`) を足すときも、和集合にすると誌が範囲を狭められなくなるので入れない。

---

## 6. 読み手の無いキー

次のキーは値を書いてもプログラムは読まない。「値があるから検査が効いている」と読み替えないこと。

| キー | 理由 |
|------|------|
| `figures.placement` | 予約キー。組み替えの発火は `figures.legends_section` と `tables.placement` が担う (このキーで発火させると、値を書いてある誌が意図せず組み替わる) |
| `figures.vector_container` | 予約キー。主形式は `figures.formats` の先頭が決めるので、役目が重なる。「ラスタが主形式だが一部の図だけベクターで出す」を作るときのために残す |
| `figures.keys_in_graphic` / `figures.multipanel_single_file` | 画像ファイルの中身への要求で、判定の材料が無い。執筆の規約 (`CLAUDE.md`) で扱う |
| `abstract.keyword_source` | 語が MeSH 由来かはシソーラスを引かないと決まらない。キーワードの数は `limits.keywords` が見る |
| `declarations.credit` / `publisher` / `numbering.table` / `article_types.<id>.sections` / `article_types.<id>.note` | 記録用 |

---

## 7. 新しい誌のプロファイルを書くときの注意

- `_default/profile.yaml` を写して始める (手順は `docs/usage-guide.md` §4)。書かなかったキーは基底の既定値になる。
- **読み手のあるキーだけを書く**。値を書いても読まれないキー (§6) を「効いている」と読み違えないため、使わないキーは書かない。
- ブロック名だけを書いて中身を空にしない (`tables:` だけの行など)。空のブロックは `null` と読まれてそのブロックの既定値を
  まるごと消すので、使わないブロックは名前ごと消す。
- 体裁キーを変えたら `make-reference.sh` を回し直す (§1)。
- **雑誌が Word のテンプレートを配るなら `reference_base` を使う** (§3.1)。テンプレートと生成した `reference.docx` は git で追跡せず、
  `reference_base_sha256` で版を固定し、`reference_base_url` に取得元のページを書く。体裁キーは照合したいものだけを書く (テンプレートの
  値を写す)。テンプレートの行間が `single` / `1.5` / `double` で表せないなら `line_spacing` は書かない。段組・柱・番号なしの見出しなどが
  要るなら §3.11〜§3.14 のキーを足し、roundtrip の PDF で見た目を確かめる。
- 図を本文に埋め込んだまま提出する誌は `figures.separate: false` にし、`figures.formats` と `numbering` は書かない (使わない)。
  `tables.placement` は `inline` のまま (`end` / `separate` とは併用できない)。
- 誌の受入形式を `submission.figure_formats` に書いておくと、受入形式外の図を出す前に止まる。書かなければ照合しない。
- `submission.text_formats` を書くと `SUBMISSION.md` が出る。ほかの `submission` のキーを調べていないうちは書かない
  (値の無い項目は「プロファイルに記録なし (規定を確認すること)」と出る)。
- 図の種類ごとの解像度 (線画 1200 dpi / 写真 300 dpi など) は表せない。`figures.dpi` には代表値を書き、必要なら
  `--dpi` で全図を高くする。体裁を焼き込む誌の `margins` は四辺一律の値になる。
