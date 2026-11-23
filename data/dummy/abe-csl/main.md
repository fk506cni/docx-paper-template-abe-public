<!--
data/dummy/abe-csl/main.md — abe.csl 受入フィクスチャ

目的: Advanced Biomedical Engineering の引用様式 (docs/journal-abe.md §4) を実機で検証する。
  - 文献リストの文字列が規定の公式例 6 件 (expected.txt の 1〜6 行目) と 1 文字ずつ一致し、巻が太字か
  - 本文の引用が規定の形 [1] / [3, 4] / [7–10] になるか (check.yaml の citations と照合。上付きでないことも docx で見る)
  - 表の中・図の題の中の引用も同じ形で出るか

【重要】文献番号は初出順に振られる。expected.txt と番号を合わせるため、
下の "文献の初出" 10 か所の順序 (hohne → born → chandler → heel → white → abe → yokan → dan → chokkan → hunch) を変えないこと。
複数引用の検証はすべてその後ろに置く。引用を足したり並べ替えたりしたら check.yaml の citations も直す。

使い方:
  bash scripts/check-csl.sh --journal abe --fixture data/dummy/abe-csl          # 文献リストと本文の引用の文字列の照合
  bash scripts/build.sh --input data/dummy/abe-csl --journal abe                # docx を作ってから
  bash scripts/check-csl.sh --journal abe --fixture data/dummy/abe-csl --docx data/step02_build/main.docx

内容は明らかなフィクション (公式例 6 件の文献を除く)。figs/fig-overview.svg は data/dummy/figs/fig-overview.svg の複製で
(図の題の中の引用を見るためだけの図)、元図を直してもこちらへは波及しない。
-->

::: {custom-style="Title"}
Citation Style Fixture for Advanced Biomedical Engineering
:::

::: {custom-style="Author"}
Test FIXTURE^1^
:::

::: {custom-style="Affiliation"}
^1^Graduate School of Hunch Engineering, University of the Tremendous, Tremendo, Hunchshire, Fictionia
:::

::: {custom-style="Subtitle"}
ABE citation style fixture
:::

# Abstract {.unnumbered}

::: {custom-style="Abstract"}
This fixture exercises the reference style of Advanced Biomedical Engineering; it is not a
manuscript. Each of the six reference examples in the instructions to authors is cited once, in the
order in which the examples appear, and the rendered reference list is compared character by
character with the examples.
:::

::: {custom-style="Keywords"}
**Keywords**: citation style, Vancouver, reference management.
:::

# Introduction

Each reference is cited once here, in the order of the examples, so that the citation numbers match
`expected.txt`.

An article in a journal is the first example [@hohne1986]. A book with an edition statement is the
second [@born1988]. A chapter in an edited book is the third [@chandler1985]. A paper in conference
proceedings with a volume number is the fourth [@heel1988]. A patent is the fifth [@white1982]. An
online document with an access date is the sixth [@abe2020].

Four forms that are absent from the examples are cited last so that their numbers stay after the
first six: an article with seven authors and no issue number [@yokan2099], a chapter with two editors
and an edition statement [@dan2100], an article published ahead of print with a DOI only
[@chokkan2101], and a report available online [@hunch2101].

# Materials and methods

Multiple citations in one bracket are rendered here. Two adjacent references stay separate
[@chandler1985; @heel1988], four adjacent references collapse into a range [@yokan2099; @dan2100;
@chokkan2101; @hunch2101], and two non-adjacent references given in reverse order are sorted
[@white1982; @hohne1986].

A citation carrying a locator is also rendered [@born1988, p. 70].

# Results

A citation inside a table cell must use the same format as the body text (Table 1). A citation inside
a figure title must do the same ([@fig:fixture]).

: Citations rendered inside a table. {#tbl:fixture}

| Item               | Reference       |
|--------------------|-----------------|
| Article in journal | [@hohne1986]    |
| Patent             | [@white1982]    |

![Fixture figure; the title cites a reference [@born1988] to confirm that titles use the same
citation format.](figs/fig-overview.svg){#fig:fixture width=80mm}

# Discussion

The reference list below is the artifact under test. Its expected content is
`data/dummy/abe-csl/expected.txt`.

# References {.unnumbered}

::: {#refs}
:::
