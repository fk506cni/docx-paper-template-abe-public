<!-- 差分の受入テスト (main/step03_diff/test_diff_engine.py): 既存の表を ::: wide で囲む (段抜きの Div を透過して表を対にする) -->

The mean score is in [@tbl:w].

: Mean score for each condition. {#tbl:w}

| Condition | Mean |
|:----------|-----:|
| Staring   |  2.6 |
| Touch     |  1.2 |

::: {custom-style="Legend" for="tbl:w"}
Values are arithmetic means over the trials in each condition.
:::

Closing sentence.
