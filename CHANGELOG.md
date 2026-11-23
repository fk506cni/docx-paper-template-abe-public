# Changelog

All notable changes to this project are recorded in this file.
Versions follow [Semantic Versioning](https://semver.org/).

## 0.1.0 — first public release

### Added

- **Build**: Markdown → .docx with pandoc 3.6.4, pandoc-crossref and citeproc. Title, authors,
  affiliations, abstract and keywords are written as `custom-style` blocks in the body.
  Each journal profile supplies its reference document and CSL style; the manuscript carries no
  layout instructions, so the same `main.md` builds for every profile.
- **Diff**: a structure-preserving diff of two manuscript versions on the pandoc AST. Changes are
  highlighted word by word in the title, authors, abstract, keywords, body, tables, equations,
  footnotes, and tables inside text boxes, with the same journal layout as the build. Works with a
  git revision or with two files. `scripts/check-diff.sh` tests the engine on pairs of old and new
  manuscripts.
- **Figures**: SVG clip fixes, PDF → SVG conversion, Mermaid rendering, native SVG embedding with
  a PNG fallback whose resolution is computed from the figure's nominal size and verified, and
  `scripts/check-figures.sh` for resolution and for SVG constructs that Word or PowerPoint render
  incorrectly.
- **Journal profiles**: `_default` (generic submission format) and `abe` (*Advanced Biomedical
  Engineering*).
- **Reference documents built from a journal's own template** (`reference_base`): the template is
  used as is for fonts, sizes, margins, header and footer; only style aliases that pandoc needs and
  fixes to the heading numbering are added, the sample text is removed, and identifying data
  (author fields, document IDs, revision marks, comments) is stripped. A SHA-256 fingerprint
  (`reference_base_sha256`) stops the build when a different template version is placed. Neither
  the template nor the generated reference document is bundled.
- **ABE layout**, each part switched on by an optional `profile.yaml` key: a one-column title page
  followed by a two-column body with line numbers (`layout`), wide figures and tables across both
  columns (`{.wide}` / `::: wide`) and column-width capping of figures, the running title in the
  page header (`header`), the template's unnumbered heading style for `{.unnumbered}` sections and
  automatic heading numbers limited to the manuscript (`headings`), affiliation numbers followed by
  a tab and present-address footnotes marked `*` / `**` (`title_page`), `Fig. 1` / `Table 1`
  captions and references (`crossref`), figures kept with their captions and table legends above
  the table (`figures.keep_together`, `tables.legend_position`), equation numbers at the right edge
  of the column (`equations`), and reference numbers followed by a tab (`bibliography`).
- **ABE citation style** (`abe.csl`, unofficial): modified Vancouver with `[1]` / `[3, 4]` /
  `[7–10]` in the text, all authors and bold volume numbers in the list, with an acceptance test
  against the six reference examples in the rules plus regression cases.
- **Submission package** (`scripts/package.sh`): for ABE, the figures stay embedded
  (`figures.separate: false`), filled-in forms are collected from `forms/`
  (`submission.collect_forms`), and `SUBMISSION.md` lists the uploads, supplementary-file sizes and
  the rule-check results. For other journals: figures exported as PowerPoint (vector SVG with a
  PNG fallback), PNG, or PDF; tables moved to the end or written as one file per table; figure
  legends collected after the references; `CAPTIONS.md` for caption fields.
- **Rule checks** (`main/step05_package/validate.py`): word limits per article type, abstract
  length and structure, keywords, running title, capitalized surnames, affiliation numbers,
  required sections, figure and table captions, supplementary-file limits, standard statements
  (conflicts of interest, ethics, AI-tool disclosure, funding), uncitable references, and common
  writing issues. `main/step05_package/test_validate_abe.py` is the regression test for the ABE checks.
- **Manuscript skeleton** for ABE (`data/journals/abe/skeleton/`): a fill-in manuscript, a
  collection of standard statements, and an optional cover letter. A complete fictional sample
  is in `data/dummy/abe/`.
- **Sample paper in `src/`**: a fresh clone has a complete sample paper in `src/` (`main.md`,
  `ref.bib`, `cover-letter.md` and three figures), so the ABE build and package run without
  `.development`. It is the clearly fictional "TJD / THS" parody written to the ABE Original Paper
  format, the paper of `data/dummy/abe/` with an added two-column illustration of the apparatus. `scripts/remove-sample.sh` removes it, but only the
  files whose contents still match the sample (`scripts/lib/sample-files.sha256`); a final package
  stops while files of the sample remain next to a `main.md` of your own.
- **Sample outputs** (`samples/`): the ABE sample paper and its diff as PDF made by Word, and the
  generic sample and its diff as .docx and PDF. For ABE only the PDFs are included, because the
  .docx files carry the society's template. `scripts/make-samples.sh` rebuilds them.
- **PDF (optional)**: conversion with Microsoft Word on Windows through Google Drive and rclone,
  with a watcher that converts each file in a separate process under a time limit, plus setup
  and diagnosis scripts. The manuscript and the filled-in forms of the final submission package are
  converted as well, and the package is placed in its own Drive folder (`submission-<journal>/`),
  after checking that it is up to date and was built from the current manuscript, profile and
  reference document.
- **Regression snapshots**: `scripts/baseline.sh`, `scripts/baseline-abe.sh` and
  `scripts/compare-snapshots.py`.
