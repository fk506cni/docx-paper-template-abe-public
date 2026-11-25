# Sample outputs

Files built from the bundled sample manuscripts, so that you can see the results before installing
anything. The manuscripts are obvious fiction: a parody of the "tremendous hunch" (TJD/THS) story,
with invented authors, institutions and results. This project is not affiliated with any journal or
society, and these files are not official templates.

| File | What it is |
|---|---|
| `abe/manuscript.pdf` | The sample paper in `src/` built with the `abe` profile (a one-column title page and a two-column body with line numbers, from the society's Word template), converted to PDF by Microsoft Word |
| `abe/manuscript-diff.pdf` | The change-highlighted diff between an earlier version and the same paper, in the same layout (the earlier version differs in four places: a word of the title, a number in the abstract, a word in the introduction and a table cell) |
| `_default/manuscript.docx`, `_default/manuscript.pdf` | The generic sample (`data/dummy/main.md`) built with the `_default` profile (double spacing, continuous line numbers) |
| `_default/manuscript-diff.docx`, `_default/manuscript-diff.pdf` | The diff of the generic sample after the change made in the quick start (`Twenty trials` → `Twenty-four trials`) |

For ABE only the PDFs are included. The .docx files carry the styles, theme and numbering of the
society's Word template, which this repository does not redistribute; place the template and build
them yourself (see the quick start in the README).

On page 1 of the generic sample the floating "Summary box" sits over the title, squeezing it into a
narrow column. The box is a text box placed at a fixed position on the page (`.textbox` with
`pos-x` / `pos-y`), and such positions have to be adjusted by hand while looking at the PDF made by
Word; this sample shows the box before that adjustment. The ABE sample has no text box.

To rebuild these files after changing a manuscript, a profile or the processing:

```bash
bash scripts/make-samples.sh --journal _default
bash scripts/make-samples.sh --journal abe       # needs data/journals/abe/ABETemplate.docx
```

The PDF step uses the optional conversion through Google Drive and Word on Windows
(`scripts/roundtrip.sh`); `--no-pdf` builds only the .docx files and the diffs.

---

## 出力のサンプル (日本語)

同梱のサンプル原稿から作った出力で、何も入れずに結果の見た目を確かめられるように置いている。原稿は明らかなフィクション
(「とてつもない予感」(TJD/THS) の物語のパロディ) で、著者・所属・結果はすべて架空。本プロジェクトはどの学会・雑誌とも関係が無く、
これらのファイルは公式のテンプレートではない。

| ファイル | 中身 |
|---|---|
| `abe/manuscript.pdf` | `src/` のサンプル論文を `abe` のプロファイルで組み (学会の Word テンプレートの 1 段組の表題ページと行番号つきの 2 段組の本文)、Microsoft Word で PDF にしたもの |
| `abe/manuscript-diff.pdf` | 旧版と同じ論文との差分 (同じ体裁)。旧版は 4 か所 (題の語・抄録の数・序論の語・表のセル) が違う |
| `_default/manuscript.docx`・`_default/manuscript.pdf` | 汎用のサンプル (`data/dummy/main.md`) を `_default` のプロファイル (ダブルスペース・連続行番号) で組んだもの |
| `_default/manuscript-diff.docx`・`_default/manuscript-diff.pdf` | クイックスタートの書き換え (`Twenty trials` → `Twenty-four trials`) の後の、汎用のサンプルの差分 |

ABE は PDF だけを置く。docx は学会の Word テンプレートのスタイル・テーマ・番号の定義を持ち、このリポジトリはテンプレートを再配布しないため。
テンプレートを置いて自分で組めば docx が得られる (README のクイックスタート)。

汎用のサンプルの 1 ページ目では、浮動の表「Summary box」が題に重なり、題が細い段に押し込まれている。この表はページの決まった位置に置く
テキストボックス (`.textbox` の `pos-x` / `pos-y`) で、位置は Word で作った PDF を見ながら手で合わせる必要がある。この見本は合わせる前の例である。
ABE のサンプルにテキストボックスは無い。

原稿・プロファイル・処理を変えたら `bash scripts/make-samples.sh --journal _default` と `--journal abe` で作り直す
(abe は `data/journals/abe/ABETemplate.docx` が要る)。PDF は Google Drive と Windows の Word を使う任意の変換 (`scripts/roundtrip.sh`) で作る。
`--no-pdf` は docx と差分だけを作る。
