<!--
data/dummy/abe/revise-report.md — ABE の動作例の回答書 (response to reviewers)

改訂稿を出すときの回答書の見本。build.sh が本文と同じ reference.docx (学会テンプレート) で docx にする:
  bash scripts/build.sh --journal abe --article-type original --input data/dummy/abe   # → data/step02_build/revise-report.docx

【内容は明らかなフィクション】data/dummy/abe/main.md と同じ TJD/THS の物語。査読コメントも架空で、実在の査読・事務局のやりとりは使わない
(規定は投稿の通信を秘密に保つよう求める)。

【書き方】ABE には回答書の形式の規定が無い (docs/journal-abe.md §7) ので、既定の動作例 (data/dummy/revise-report.md) と同じ書き方にした:
  査読コメントは引用ブロック (>)、回答は地の文。見出しは # / ## のまま書く ({.unnumbered} は要らない)。
  - 1 段組・行番号なし・柱は空 (ページ番号だけ) になる (profile の layout.scope / line_numbers_scope / header)
  - 見出しにテンプレートの自動番号は付かない (profile の headings.numbered_scope: manuscript)
  - 本文の箇所は「ページと行」で示す。行番号は本文の節にページごとに付く (各ページで 1 から) ので、改訂稿の PDF
    (roundtrip で Word が作ったもの) を見て書く。下の行番号は架空
  - 変更箇所は全領域差分の docx (bash scripts/diff.sh …) でも示せる。差分 docx を出すかは投稿画面しだい (規定に記述なし)
改訂の期限は判定から 3 か月 (規定。docs/journal-abe.md §7)。
-->

# Response to Reviewers

We thank the editor and the two reviewers for their careful reading of our manuscript. We have revised
the manuscript accordingly; our point-by-point responses follow. Reviewer comments are quoted in italics,
and page and line numbers refer to the revised manuscript.

## Reviewer 1

> *Comment 1.1 — The title does not say that the scale is new.*

We agree. The title now reads "… and a New Dimensional Scale" (page 1). The running title is unchanged,
because it remains within 50 characters.

> *Comment 1.2 — The mean score for staring in the Abstract disagrees with the table.*

Thank you for spotting this. The Abstract stated 2.5 units; the correct value is 2.6 units, as in Table 1.
We corrected the Abstract (page 1).

> *Comment 1.3 — Please report the inputs of the individual trials, not only the condition means.*

We added Table 2, which lists the inputs and scores of the first eight trials, with a sentence that
introduces it in the Results (page 4, lines 21–26). The table spans both columns because it does not fit
in a single column.

## Reviewer 2

> *Comment 2.1 — The proportional margin seems arbitrary. Why five times the score?*

The factor follows from the spread of the exasperation term across the trials. We corrected the margin
from four to five times the score in Eq. 2 and in the sentence that follows it (page 3, lines 30–34); the
value of plus or minus 500% used throughout the manuscript was already based on the factor of five.

> *Comment 2.2 — The discussion of composite indices should cite the earlier proposal of a dimensional
> treatment of cold sweat.*

We now cite that proposal, in place of the informal testimony cited before, at the end of the second
paragraph of the Discussion (page 5, line 18).

We believe that these revisions address all the comments, and we hope that the manuscript is now
suitable for publication in Advanced Biomedical Engineering.
