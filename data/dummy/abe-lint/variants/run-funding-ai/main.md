<!--
data/dummy/abe-lint/variants/run-funding-ai/main.md — ABE の規定チェックの受入フィクスチャ【不適合原稿の変種】

data/dummy/abe-lint/main.md と同時には起こせない違反を、小さな原稿で 1 つずつ発火させる (ほかの検査はすべて黙る形にしてある)。
main/step05_package/test_validate_abe.py が回す。単独でも:

  docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
      python3 main/step05_package/validate.py \
          --input-root data/dummy/abe-lint/variants/run-funding-ai --journal abe --article-type original

【内容は明らかなフィクション】data/dummy/abe/ と同じ TJD/THS の物語。実在の人名・所属は使わない。

【期待される指摘】要修正 1 件 / 参考 2 件
   1. 題が 50 字を超えるのに running title (Subtitle の Div) が無い          → 要修正 (limits.running_title_chars)
   a. 資金 (funded / grant) を Materials and methods にだけ書き、Acknowledgements に書いていない
                                                                            → 参考 (lint.funding_section)
   b. AI ツールの使用の開示がどこにも無い (AI ツールらしき語が 1 つも無い)   → 参考 (lint.ai_disclosure_section)
-->

::: {custom-style="Title"}
Ordering of Three Interaction Conditions Measured with a Heavy Apparatus
:::

::: {custom-style="Author"}
Taro YOKAN, Bonta DAN
:::

::: {custom-style="Affiliation"}
Graduate School of Hunch Engineering, University of the Tremendous, Tremendo, Hunchshire, Fictionia
:::

<!-- 違反 1: running title (Subtitle の Div) を置いていない (題は 72 字) -->

::: {custom-style="Normal"}
Received ………….. [Do not enter]

Revised ………….. [Do not enter]
:::

# Abstract {.unnumbered}

::: {custom-style="Abstract"}
The tremendous hunch felt on waking has been measured with a heavy apparatus, but the ordering of the
three interaction conditions has not been compared across mornings. We repeated the measurement on
eight mornings with one operator and found that the ordering held on every morning, whereas the
absolute scores moved by an order of magnitude. The ordering is therefore a property of the hunch
rather than of the morning.
:::

::: {custom-style="Keywords"}
**Keywords**: intuition, psychophysics, reproducibility, cold sweat.
:::

# Introduction

The hunch on waking was first measured with a heavy apparatus that converts it into a physical
quantity. Whether the ordering of the interaction conditions depends on the morning has not been
examined.

# Materials and methods

<!-- 違反 a: 資金をここに書いた (規定は Acknowledgements)。違反 b: AI ツールの使用の開示の小節を置いていない -->

One operator ran the apparatus on eight mornings and recorded the score of each trial under the three
interaction conditions. This study was funded by the Tremendous Hunch Promotion Foundation (grant
number THPF-0000).

# Results

The ordering of the three conditions held on all eight mornings.

# Discussion

The ordering, not the magnitude, is the reproducible part of the measurement.

# Conflicts of interest {.unnumbered}

The authors declare no conflicts of interest with any companies or commercial organizations per the
definition of Japanese Society for Medical and Biological Engineering.

# Acknowledgements {.unnumbered}

We thank Mushi Shirase for calibrating the sigh detector.

# References {.unnumbered}

::: {#refs}
:::
