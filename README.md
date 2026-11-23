# docx-paper-template-abe

**Write your manuscript in Markdown and get a submission-ready Word (.docx) file.**
This is a template repository: copy it, write `src/main.md`, choose a journal profile, and build.
It covers the parts of journal submission that are usually done by hand in Word:
change-highlighted diffs for peer review, vector figures without quality loss,
journal-specific formatting, and the final submission package.
The main target is *Advanced Biomedical Engineering* (ABE), whose two-column layout is built
from the society's own Word template; a generic profile works for any other journal.

日本語版: [README.ja.md](README.ja.md)

> **Not affiliated with any journal or society.** This project is an independent tool. It is not
> provided, endorsed, or reviewed by the Japanese Society for Medical and Biological Engineering
> (JSMBE) or the editorial office of *Advanced Biomedical Engineering*, and it is not an official
> template. The `abe` profile is our reading of the journal's public Instructions to Authors
> (version of 1 April 2026), and those rules can change at any time. **Always check the current
> [Instructions to Authors](https://abe-journal.org/authorinstructions) before you submit.**

---

## Features

- **Markdown → .docx** with pandoc. Title, authors, affiliations, abstract and keywords are written
  as styled blocks in the body, so they are formatted by the journal's reference document and take
  part in the diff. The manuscript never contains layout instructions such as columns, so the same
  `main.md` builds for any journal profile.
- **Full-manuscript diff for peer review.** Compares two versions of `main.md` on the pandoc AST
  and marks added words in blue and deleted words in red strikethrough — in the title, authors,
  abstract, keywords, body text, tables, equations, footnotes, and tables inside text boxes. The
  document structure is kept intact, and the diff gets the same journal layout as the build.
- **Vector figures.** SVG figures are embedded natively in the .docx, with a PNG fallback
  rendered at the profile's resolution (300 dpi by default). PDF figures are converted to SVG
  first. Mermaid diagrams (`.mmd`) are rendered in a container and handled the same way.
- **Journal profiles** (`data/journals/<id>/`): one directory per journal holds the formatting
  (`profile.yaml`), the citation style (CSL), and the Word reference document (`reference.docx`,
  generated on your machine the first time it is needed). The manuscript itself stays
  journal-independent.
  - `_default` — a generic submission format: double spacing, continuous line numbers,
    Times New Roman 12 pt, A4 with 25 mm margins, AMA-style numbered citations. Works out of the box.
  - `abe` — *Advanced Biomedical Engineering*. Needs the society's Word template, which you download
    yourself (see the quick start).
- **ABE support:**
  - a reference document built from the society's `ABETemplate.docx` (version 3) without baking in
    any formatting: the template stays the source of the fonts, sizes, margins, header and footer.
    Identifying data in the template (author fields, document IDs, revision marks) is removed
  - the template's layout: a one-column title page (title, authors, affiliations, running title,
    abstract, keywords) followed by a two-column body with line numbers, the running title in the
    page header, and automatic heading numbers (`1.` / `2.1` / `2.1.1`); unnumbered sections
    (`{.unnumbered}`) such as Conflicts of interest and References get the template's unnumbered style
  - wide figures and tables across both columns (`{.wide}` / `::: wide`); a figure wider than a
    column is scaled to the column width with a warning
  - captions and references in the journal's form (`Fig. 1 …` / `Table 1 …`, table captions and
    legends above the table, figure captions below), figures kept together with their captions,
    and equation numbers at the right edge of the column
  - affiliations numbered with superscripts, and a footnote after an author's name (a present
    address) marked `*` / `**` while other footnotes keep their numbers
  - a citation style (`abe.csl`) for the journal's modified Vancouver format — `[1]`, `[3, 4]`,
    `[7–10]` in the text; all authors and the volume in bold in the list — with an acceptance test
    against the six reference examples in the rules
  - rule checks: word limits per article type (Original Paper / Research Letter / Technical Note /
    Review Paper), a single-paragraph unstructured abstract of up to 350 words, keywords that do not
    repeat the title, the running title for long titles, capitalized surnames, required sections,
    supplementary-file size limits, and writing checks such as composed characters (`℃`)
  - a submission package that keeps the figures embedded (the journal wants one PDF of the
    manuscript with the figures in place), collects your filled-in forms from `forms/`, and writes
    `SUBMISSION.md` with the upload list and the rule-check results
  - a manuscript skeleton with all required sections and a collection of standard statements
    (conflicts of interest, ethics, funding, AI-tool disclosure, data availability)
    (`data/journals/abe/skeleton/`)
- **Other journals:** figures delivered as PowerPoint files (one figure per file, vector SVG plus a
  PNG fallback) or as PNG/PDF, tables moved to the end or into one file per table, and figure
  legends collected after the references — each switched on by a key in `profile.yaml`.
- **Optional PDF output through Microsoft Word.** The .docx is sent to Google Drive with rclone,
  a watcher on a Windows PC converts it with Word, and the PDF comes back. This shows the layout
  as Word renders it. LibreOffice is deliberately not used for PDF output. For a final submission
  package, the manuscript and the filled-in forms are converted as well, and the package is placed in
  its own Drive folder (`submission-<journal>/`) so that the files to upload can be picked from one place.

## Requirements

- **Docker** (Engine with Compose v2), **bash**, and **git**. All conversion runs in containers;
  nothing is installed on the host.
- An **x86-64 (amd64)** host. The pandoc image installs amd64 release binaries. The tooling is
  developed on Linux; other environments have not been tested.
- **Network access on the first build.** The images download pandoc and pandoc-crossref, the
  Mermaid CLI with headless Chromium, and (for the `svg-conversion` image) the Microsoft Core Fonts.
- To view the native SVG figures as vectors: **Microsoft 365 or Office 2019 and later**.
  Office 2016 and other viewers show the PNG fallback.
- For the `abe` profile: **the society's template `ABETemplate.docx`**, downloaded from the
  [Instructions to Authors](https://abe-journal.org/authorinstructions) page. It is not included in
  this repository.

Optional:

- **PDF output:** rclone configured with a Google Drive remote (default name `gdrive:`), and a
  Windows PC with Microsoft Word that syncs the same Drive folder. See
  [docs/roundtrip-windows-watcher.md](docs/roundtrip-windows-watcher.md).
- **`svg-conversion` image** (used only to outline the text of figures exported as separate files:
  PDF figures, e.g. the `_default` profile in final mode, and PowerPoint figures with
  `figures.pptx.text_to_path: true`; the `abe` profile keeps its figures embedded and does not use
  it, and neither does the quick start below): proprietary fonts such as Calibri or Yu Gothic are
  **not included**. Put the font files you are licensed to use in `fonts/` before the image is built.
  Without them the image still builds and substitutes other fonts. The image is built only when it
  is missing, so if you add fonts after it has been built, remove it
  (`docker image rm docx-paper-template-svg-converter`) and it is rebuilt the next time it is needed.
  Building this image downloads the Microsoft Core Fonts from the `corefonts` project; **by building it
  you accept Microsoft's End-User License Agreement for these fonts** (<https://corefonts.sourceforge.net/eula.htm>).

## Quick start

These commands build the bundled sample manuscripts. Run them from the repository root.
To look at the results first, open the files in [`samples/`](samples/README.md): the ABE sample paper
and its diff as PDF made by Word, and the generic sample as .docx and PDF.

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

Open the resulting files in Word. In `data/step03_diff/main_diff.docx` the changed number in the
abstract is highlighted. `data/output/abe/manuscript.docx` has the title page on page 1 and the
two-column body with line numbers and the running title from page 2, with the figures in place.
`data/output/abe/SUBMISSION.md` lists the files to upload (the manuscript as a PDF made by Word,
and the forms), the rule-check results (none for this sample), and the points to review before
submitting. In this walkthrough `SUBMISSION.md` also carries three notes: `manuscript-diff.docx` was
made from a different manuscript (the package collects the diff of the generic sample made in 4.),
the manuscript in `src/` is the bundled sample paper itself, and `src/forms/` (where your filled-in
forms go) does not exist yet. The same paper with placeholder forms is in `data/dummy/abe/`; add
`--input data/dummy/abe` to the two commands of 8. to see the forms collected into the package.
`src/` holds the complete sample paper right after cloning (`main.md`, `ref.bib`, `cover-letter.md`
and three figures), so it can also serve as a starting point. The citation check in 9. prints `OK` for each of the 17
in-text citations and 10 reference lines it compares, and a note that the Word formatting
(brackets, bold volume numbers) was not checked: for that, build the fixture `data/dummy/abe-csl/`
and pass the .docx with `--docx` (see [docs/usage-guide.md](docs/usage-guide.md) §4.1). The rule
check in 10. reports 12 items to fix and 15 notes.

If you place a different version of the template, the build stops because its SHA-256 differs from
`reference_base_sha256` in `data/journals/abe/profile.yaml` (version 3). To use a new version,
replace that value with the one printed, build again, and check the warnings and the layout.

### Start your own manuscript

```bash
rm -f .development              # the input root is src/
rm -f data/step03_diff/*.docx data/step03_diff/.main_diff.source   # drop the sample diff made above
bash scripts/remove-sample.sh   # remove the sample paper in src/ (only files unchanged from the sample)
cp data/journals/abe/skeleton/main.md src/main.md   # ABE skeleton; fill in the <<...>> fields
```

`scripts/remove-sample.sh` removes only the files whose content is still that of the sample, so it
never removes a file you wrote, and running it again is harmless (`--dry-run` lists what it would
remove). A final package stops while files of the sample remain next to a `main.md` of your own, so
that the sample cover letter, references and figures do not end up in your submission.

For ABE, follow the walkthrough in [docs/usage-guide.md](docs/usage-guide.md) §8 and the checklist
[docs/abe-submission-checklist.md](docs/abe-submission-checklist.md) on submission day. For another
journal, start from the generic sample instead
(`cp data/dummy/*.md data/dummy/ref.bib src/ && cp -r data/dummy/figs/. src/figs/`; this leaves out the
subdirectories of `data/dummy/`, which hold the ABE sample and the test fixtures).
Keep your manuscript under `src/` and commit it as usual; generated files go to `data/` and are
ignored by git, and so are the society's template, the reference documents and your filled-in forms
in `src/forms/`.

## Main commands

| Command | What it does |
|---|---|
| `bash scripts/build.sh [--journal <id>] [--article-type <type>]` | Figures → `data/step02_build/main.docx` (also `cover-letter.docx` and `revise-report.docx` when those files exist) |
| `bash scripts/diff.sh [REVISION \| old.md new.md] [--journal <id>]` | Diff against a git revision (default `HEAD~1`) or between two files → `data/step03_diff/main_diff.docx` |
| `bash scripts/package.sh --journal <id> --mode draft\|final` | Submission package → `data/output/<id>/`, with the rule checks |
| `bash scripts/check-figures.sh [--journal <id>] [--figures-dir <dir>]` | Checks figure resolution and SVG constructs that Word renders incorrectly |
| `bash scripts/check-csl.sh [--journal <id>] [--docx <file>]` | Compares formatted references with a fixture of expected output (default: `abe` and `data/dummy/abe-csl/`) |
| `bash scripts/check-diff.sh` | Acceptance test of the diff engine on pairs of old and new manuscripts |
| `bash data/journals/make-reference.sh <id>` | Generates a journal's `reference.docx` (from `profile.yaml`, or from the journal's template for `abe`). `build.sh` and `diff.sh` run it when the file is missing or out of date |
| `bash docker/mermaid/convert.sh <file.mmd> both` | Renders a Mermaid diagram to SVG and PDF on its own (not needed for builds, which render `figs/mermaid/*.mmd` themselves) |
| `bash scripts/push-win-tools.sh` / `check-pdf-path.sh` / `roundtrip.sh` | Optional PDF output through Word (setup / diagnosis / conversion; `roundtrip.sh` also places a final submission package in the Drive folder `submission-<journal>/`, after checking that it was built from the current manuscript; right after the quick start, add `--skip-build`) |
| `bash scripts/remove-sample.sh [--dry-run]` | Removes the bundled sample paper from `src/` (only the files whose content is unchanged) |
| `bash scripts/make-samples.sh --journal _default\|abe [--no-pdf]` | Rebuilds the output examples in `samples/` (the PDF step uses the optional Word conversion) |
| `bash scripts/baseline.sh <suffix>` / `baseline-abe.sh <suffix>` / `scripts/compare-snapshots.py` | Regression snapshots of the build outputs and their comparison |

`build.sh`, `diff.sh`, `package.sh`, `check-figures.sh`, `check-csl.sh`, `check-diff.sh`, `remove-sample.sh`,
`make-samples.sh`, `baseline.sh`, `baseline-abe.sh` and the three PDF scripts print their usage with `--help`. Script messages and the
detailed guides are in Japanese.

## Repository layout

```
.
├── src/              # your manuscript: main.md, ref.bib, figs/ (+ cover-letter.md, revise-report.md, forms/)
│                     #   right after cloning: the ABE sample paper (remove it with scripts/remove-sample.sh)
├── samples/          # output examples built from the sample papers (PDF for ABE; .docx and PDF for _default)
├── data/
│   ├── journals/     # journal profiles: _default/ and abe/ (abe/skeleton/ = manuscript skeleton;
│   │                 #   put ABETemplate.docx in abe/)
│   ├── dummy/        # sample manuscripts and test fixtures (used while .development exists)
│   └── step*/ output/ products/   # generated files (ignored by git)
├── main/             # processing code, one directory per pipeline stage
│   ├── 00_setup/     #   shared settings, Lua filters, OOXML helpers
│   ├── step01_figures/  step02_build/  step03_diff/  step04_pdf/  step05_package/
├── scripts/          # entry points (build / diff / package / checks / PDF round trip)
├── docker/           # pandoc, Mermaid and svg-conversion images (no ports are exposed)
├── fonts/            # optional proprietary fonts for svg-conversion (ignored by git)
└── docs/             # detailed guides (Japanese)
```

## Documentation

The detailed guides are written in Japanese.

| Document | Contents |
|---|---|
| [docs/usage-guide.md](docs/usage-guide.md) | Step-by-step usage: figures, journals, diffs, packages, PDF, and the ABE walkthrough |
| [docs/journal-abe.md](docs/journal-abe.md) | ABE rules and the society's template mapped to the implementation |
| [docs/abe-submission-checklist.md](docs/abe-submission-checklist.md) | One-page checklist for submission day |
| [docs/architecture.md](docs/architecture.md) | Processing flow and design decisions |
| [docs/profile-schema.md](docs/profile-schema.md) | Every `profile.yaml` key, its default, and what reads it |
| [docs/design-fullarea-diff.md](docs/design-fullarea-diff.md) | How the structure-preserving diff works |
| [docs/migration-latex.md](docs/migration-latex.md) | Moving an existing LaTeX manuscript to this template |
| [docs/roundtrip-windows-watcher.md](docs/roundtrip-windows-watcher.md) | Setting up and diagnosing the Word PDF conversion |
| [CLAUDE.md](CLAUDE.md) | Conventions in short form (also read by AI coding assistants) |

## Sample manuscripts

The manuscripts in `src/` and `data/dummy/` are obvious fiction: a parody of the "tremendous hunch"
(TJD/THS) story from <https://github.com/fk506cni/jami-pandoc-public>. The authors, institutions,
and results are invented. They exist so that every feature can be built and checked without a
real manuscript. The paper in `src/` is the ABE sample (`data/dummy/abe/` holds the same paper without the
illustration of the apparatus, for the checks); [`samples/`](samples/README.md) has the outputs built from it and from the generic
sample. The forms in `data/dummy/abe/forms/` are placeholders, not the society's forms.

## Limitations

- **PDF output needs Windows and Microsoft Word.** Without them you still get every .docx, but no PDF.
- **The ABE layout depends on the society's template.** If the template is revised, the build stops
  until you accept the new version (see the quick start), and some post-processing may no longer
  match; missing styles and missing heading numbers are reported as warnings on every build.
- **References from `[100]` on**: the number alone is wider than the hanging indent, so the first
  line of those entries starts further right than `[1]`–`[99]`.
- **Diff:** a moved paragraph is shown as a deletion plus an addition. Tables with merged cells
  can be aligned imperfectly. The reference list is regenerated rather than diffed. Text without
  spaces between words (such as Japanese) is compared phrase by phrase rather than word by word.
  A cross-reference in deleted text to a figure, table or equation that was itself deleted shows
  as `¿fig:label?`, because the target no longer exists in the new version.
- **Text boxes** (`.textbox`) are placed by page and position; in the two-column layout check their
  positions in the Word PDF and adjust them by hand.
- **Figures:** resolution is guaranteed only for images generated from SVG or PDF. Raster images
  you place yourself are copied as they are. Some valid SVG files render incorrectly in Word or
  PowerPoint (several SVG files concatenated into one, or colors written as `hsl()`);
  `scripts/check-figures.sh` lists them as warnings.
- **Rule checks are aids, not guarantees.** English quality, prior publication, permissions, and
  the content of the forms cannot be checked automatically; see the checklist.
- **Two journal profiles are included.** Other journals are added by copying the `_default`
  profile (see the usage guide).

## License

The code in this repository is released under the [MIT License](LICENSE).
The two bundled CSL citation styles are under CC BY-SA 3.0. The Word reference documents and the
society's template are not bundled: the generic reference document is generated on your machine from
pandoc's default data, and the ABE one from the template you download.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Documents you write and build with this template are your own work.
