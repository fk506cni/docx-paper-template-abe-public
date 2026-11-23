<!--
data/journals/abe/skeleton/cover-letter.md — ABE のカバーレターの雛形。【任意】

ABE の規定にカバーレターの記述は無い (docs/journal-abe.md §6.2)。投稿系 (Editorial Manager) に欄があれば任意で添える
(要否は投稿画面で確かめる)。使わないなら写さない (入力ルートに cover-letter.md が無ければ build は作らない)。

それでも雛形を置くのは、規定が「編集者に知らせる」ことを求める事柄の置き場所になるため (投稿画面の欄で済ませてもよい):
  (1) 関連原稿 — 他所で審査中・印刷中・刊行済みの関連原稿があれば知らせる義務がある ("Authors must inform the editors if any related
      manuscripts are under consideration, in press or published elsewhere")。会議録 (Proceedings) として
      刊行されたものは長さ・図表によらず既発表で、投稿できない。既発表にならないのはプレプリントと、図表を含まず 400 語未満の抄録だけ
  (2) 非生成 AI の使用 — 綴り・文法の確認などの非生成 AI の使用は "should be declared to the editors upon submission" (Methods の開示に加えて)
既発表でない・他所に投稿していないことの確約は Submission Form の Author Statement (全著者の署名) でも行う (docs/journal-abe.md §6.4)。

使い方: cp data/journals/abe/skeleton/cover-letter.md src/cover-letter.md
        bash scripts/build.sh --journal abe --article-type original   # cover-letter.docx も出る (1 段組・行番号なし・柱の文字なし)

【本文は custom-style の Div を使わない素の Markdown でよい】(差分の対象は原稿の本体だけでよいため)。
記入欄 `<<...>>` が残っていれば規定チェックが要修正として出す (cover-letter.md も読む)。
-->

<<投稿日, 2027-01-01>>

To the Editor-in-Chief\
Advanced Biomedical Engineering

Dear Editor,

We are pleased to submit our manuscript entitled **"<<論文の題, Title of the Manuscript>>"** for consideration as
<<記事種別, an Original Paper / a Research Letter / a Technical Note / a Review Paper>> in Advanced Biomedical Engineering.

<!-- 本誌に載せる意義: 扱う問題・何が新しいか・医学と工学のどちらの読者に何をもたらすか (本誌は学際の研究を特に歓迎する。§2) -->

<<本稿が扱う問題と新規性、本誌の読者にとっての意義を 3〜5 文で>>

<!-- 既発表・重複投稿でないこと。関連原稿があれば下の 2 文目を、審査中・印刷中・刊行済みの関連原稿の書誌と本稿との違いに置き換える。
     プレプリントがあればその場所 (サーバと DOI) も書く (プレプリントは既発表に数えない) -->

This manuscript has not been published previously, in whole or in part and in any language, and is not in press or under
consideration for publication elsewhere. <<関連原稿, No related manuscript is under consideration, in press, or published elsewhere.>>

<!-- 非生成 AI (綴り・文法の確認など) を使ったなら申告する。Materials and methods の開示と同じ内容にする。使っていなければ段落ごと削る。
     生成 AI を使ったなら、Materials and methods の開示を参照する形で書く (data/journals/abe/skeleton/statements.md の §4) -->

<<AI ツールの使用, As described in the Materials and methods, the authors used a non-generative AI tool only to check spelling and grammar.>>

All authors have read and approved the submitted version and agree to its submission to Advanced Biomedical Engineering.

Sincerely,

<<連絡著者, Given-name FAMILY-NAME>>, on behalf of all authors\
<<所属, Laboratory, Department, Institution>>\
<<所在地, City, Country>>\
E-mail: <<連絡著者の E-mail, name@example.org>>
