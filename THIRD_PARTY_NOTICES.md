# Third-party notices

The [MIT License](LICENSE) covers the code and documentation written for this repository.
The components below are covered by their own licenses or belong to their owners. This file
describes how the repository handles them; it is not legal advice.

## 1. Citation styles (CSL) — CC BY-SA 3.0

| File | What it is |
|---|---|
| `data/journals/_default/_default.csl` | *AMA Manual of Style 11th edition* (`http://www.zotero.org/styles/american-medical-association`) from the Citation Style Language style repository, <https://github.com/citation-style-language/styles>. Author: Julian Onions. Contributors: Christian Pietsch, Daniel W. Chan, Patrick O'Brien, Andrew Dunning. Not modified in this repository. |
| `data/journals/abe/abe.csl` | A style adapted in this repository from the AMA style above to reproduce the reference examples in the Instructions to Authors of *Advanced Biomedical Engineering*. The authors and contributors of the AMA style are listed in its `<info>` element as contributors, with a `rel="template"` link to the original. It is **not** an official style of the journal and has not been provided or reviewed by the journal or the Japanese Society for Medical and Biological Engineering. |

Both files are licensed under the
[Creative Commons Attribution-ShareAlike 3.0 Unported License](https://creativecommons.org/licenses/by-sa/3.0/),
as stated in the `<rights>` element of each file. If you modify and share either style,
keep the attribution and share it under the same license.

## 2. The society's Word template (`ABETemplate.docx`) — not included

The `abe` profile builds its reference document from `ABETemplate.docx`, the Word template that the
Japanese Society for Medical and Biological Engineering (JSMBE) distributes with the Instructions to
Authors of *Advanced Biomedical Engineering* (<https://abe-journal.org/authorinstructions>).
The template belongs to the society. This repository **does not include it, nor any file derived
from it**:

- You download the template yourself and place it at `data/journals/abe/ABETemplate.docx`.
- `bash data/journals/make-reference.sh abe` (run by `scripts/build.sh` and `scripts/diff.sh` when
  needed) generates `data/journals/abe/reference.docx` from it on your machine. The generated file
  keeps the template's formatting, so treat it like the template: do not commit or redistribute it.
- The bundled `.gitignore` ignores `.docx`, `.dotx`, `.docm` and `.dotm` files in each journal
  directory, so neither file is committed by accident.
- The forms in `data/dummy/abe/forms/` are placeholders written for the sample; they are not the
  society's forms.

## 3. pandoc and its default data

pandoc (<https://pandoc.org>) is Copyright (C) 2006–2024 John MacFarlane and contributors.
Its COPYRIGHT file releases pandoc under the GNU General Public License, version 2 or later,
with listed exceptions (for example, pandoc's document templates are dual-licensed under the
GPL or the BSD 3-clause license). The default Word and PowerPoint reference documents
(`reference.docx` / `reference.pptx`) are not among the listed exceptions.

For that reason this repository **does not include pandoc's reference documents or files derived
from them**:

- The generic reference document is generated on your machine by
  `bash data/journals/make-reference.sh <id>`, which takes pandoc's default reference document
  (`pandoc --print-default-data-file reference.docx`) inside the container and applies the
  journal's page setup and styles from `profile.yaml`. `scripts/build.sh` and `scripts/diff.sh`
  run it for you when the file is missing.
- PowerPoint figure files (for journals that ask for them) are built at run time from pandoc's
  default `reference.pptx`, which is read from pandoc inside the container.

pandoc itself is not distributed with this repository. It is downloaded from the pandoc
releases on GitHub when you build the `docx-paper-template-pandoc` image, and runs as a separate
program inside the container.

## 4. Software installed when the images are built

The Docker images install third-party software from its upstream distributions at build time:
pandoc, pandoc-crossref, panflute, lxml, LibreOffice (Writer and Impress), librsvg, pdf2svg,
Inkscape, Ghostscript, the Mermaid CLI with headless Chromium, and the Noto CJK and IPA fonts.
None of it is part of this repository. Each component is subject to its own license.

## 5. Fonts

- **Microsoft Core Fonts** (Arial, Times New Roman, and others): the `svg-conversion` image
  downloads the original installers from the `corefonts` project on SourceForge when it is built,
  verifies them against `docker/svg-conversion/mscorefonts.sha256`, and extracts the fonts into
  the image. The fonts are not included in this repository and remain subject to Microsoft's
  End-User License Agreement (<https://corefonts.sourceforge.net/eula.htm>). **Building the image
  means accepting that agreement.** The installers, which carry the license text, are deleted after
  the fonts are extracted, so the text is not kept inside the image. The image is built
  automatically the first time it is needed: when a figure is exported as a separate PDF file (for
  example by `_default` in final mode) or when the text of a PowerPoint figure is outlined. The `abe`
  profile keeps its figures embedded and does not use it, nor does the quick start in the README.
- **Proprietary fonts** (for example Calibri or Yu Gothic) are not included. If you need them in
  final figures, place the font files you are licensed to use in `fonts/`; that directory is
  ignored by git.

Because the built `svg-conversion` image contains these font files, keep it on your own machine
and do not push it to a public registry.
