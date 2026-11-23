---
title: "Ordering of Three Interaction Conditions"
author:
  - Taro YOKAN
  - Bonta DAN
---

<!--
data/dummy/abe-lint/variants/missing-divs/main.md — ABE の規定チェックの受入フィクスチャ【不適合原稿の変種】

表題ページの Div (custom-style) が無い・2 つある原稿。表題ページの検査 (running title・姓・抄録・キーワードと題) は Div を読むので、
Div が無いと黙って空振りする。lint.front_matter_divs がそれを要修正にすることを確かめる (ほかの検査はすべて黙る形にしてある)。
main/step05_package/test_validate_abe.py が回す。単独でも:

  docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
      python3 main/step05_package/validate.py \
          --input-root data/dummy/abe-lint/variants/missing-divs --journal abe --article-type original

【内容は明らかなフィクション】data/dummy/abe/ と同じ TJD/THS の物語。実在の人名・所属は使わない。

【期待される指摘】要修正 3 件
   1. 題を YAML の title に書き、Title の Div が無い                         → 要修正 (lint.front_matter_divs)
   2. 著者を YAML の author に書き、Author の Div が無い                      → 要修正 (同)
   3. Abstract の Div が 2 つある (検査は最初の 1 つしか見ない)               → 要修正 (同)
-->

::: {custom-style="Affiliation"}
Graduate School of Hunch Engineering, University of the Tremendous, Tremendo, Hunchshire, Fictionia
:::

::: {custom-style="Normal"}
Received ………….. [Do not enter]

Revised ………….. [Do not enter]
:::

# Abstract {.unnumbered}

<!-- 違反 3: 抄録を 2 つの Div に分けた -->

::: {custom-style="Abstract"}
The tremendous hunch felt on waking has been measured with a heavy apparatus, but the ordering of the
three interaction conditions has not been compared across mornings.
:::

::: {custom-style="Abstract"}
We repeated the measurement on eight mornings with one operator and found that the ordering held on
every morning, whereas the absolute scores moved by an order of magnitude.
:::

::: {custom-style="Keywords"}
**Keywords**: intuition, psychophysics, reproducibility, cold sweat.
:::

# Introduction

The hunch on waking was first measured with a heavy apparatus that converts it into a physical
quantity. Whether the ordering of the interaction conditions depends on the morning has not been
examined.

# Materials and methods

One operator ran the apparatus on eight mornings and recorded the score of each trial under the three
interaction conditions.

## Use of artificial intelligence tools

No artificial intelligence tool was used in this study.

# Results

The ordering of the three conditions held on all eight mornings.

# Discussion

The ordering, not the magnitude, is the reproducible part of the measurement.

# Conflicts of interest {.unnumbered}

The authors declare no conflicts of interest with any companies or commercial organizations per the
definition of Japanese Society for Medical and Biological Engineering.

# References {.unnumbered}

::: {#refs}
:::
