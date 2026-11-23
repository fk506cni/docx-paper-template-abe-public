<!-- 差分の受入テスト (main/step03_diff/test_diff_engine.py): 番号つきの式を含む脚注の書き換え (pandoc-crossref の Duplicate label で止まらない) -->

Text with a note.^[In the note, $$ x = 2 $$ {#eq:fn} holds.]

See [@eq:fn].
