<!--
data/journals/abe/skeleton/main.md — Advanced Biomedical Engineering (ABE) の原稿骨格

用途: ABE へ投稿する原稿の【雛形】。書き始めるときは本ファイルを原稿の入力ルートへ写す。

    cp data/journals/abe/skeleton/main.md src/main.md                  # 本番 (.development 無し)
    cp data/journals/abe/skeleton/cover-letter.md src/cover-letter.md  # 任意 (規定にカバーレターの記述は無い)
    bash scripts/build.sh --journal abe --article-type original        # 写した直後でもビルドが通る

  ※ 定型の記述の文例 (利益相反・倫理・資金・AI ツールの開示・データ・臨床試験・画像の加工・報告指針・転載) は
    data/journals/abe/skeleton/statements.md にある (参照専用。ビルドの対象ではない)。
  ※ 記入済みの動作例は data/dummy/abe/ (ビルドが通る完結原稿。--input data/dummy/abe を付けて回す)。書き方に迷ったらそちらを見る。
  ※ ビルドには学会テンプレート ABETemplate.docx が要る (data/journals/abe/ に置く。git で追跡しない)。
    無ければ build が取得元 (学会サイトの Instructions to Authors のページ) を出して止まる。

【この雛形の約束ごと】
  - `<<...>>` は記入欄。提出前にすべて置き換える。残っていれば package.sh の「規定チェック」(validate.py) が要修正として出す
    (本ファイルと cover-letter.md の両方を読む)。本骨格の記入欄は、どれも docx に `<<…>>` のまま出ることを確かめてある —
    pandoc は `<<Department>>` や `<<結論>>` のように HTML のタグとして読める記入欄を docx で消してしまい (`<>` だけが残る)、
    docx を通し読みしても書き忘れに見えないので、記入欄の中身はタグとして読めない形 (カンマ・読点・空白の後の数字を含む) にした。記入欄を足すときも同じようにする。
  - 規定の要点は各節の頭の HTML コメントに書いた (出典は docs/journal-abe.md の節番号。pandoc はコメントを docx に出さず、
    規定チェックもコメントの中を見ない)。提出前にコメントを消す必要は無い。
  - 表題ページの要素 (題・著者・所属・running title・抄録・キーワード) は【YAML のメタデータではなく custom-style の Div】で書く。
    全領域差分 (diff.sh) がこれらを温存して中身を語単位で差分にするため (CLAUDE.md「原稿執筆の規約」)。
  - 【2 段組の指示は原稿に書かない】。表題ページ (題〜キーワード) を 1 段組、本文を 2 段組 (行番号つき) にするのは
    data/journals/abe/profile.yaml の layout と後処理の仕事 (同じ原稿を --journal _default でも組める)。
    段の幅 (83 mm) に収まらない図表は段抜き (本文幅) にする: 図は {.wide} を付け、表は ::: wide の Div で囲む (下の Results のコメント)。
  - 【見出しの番号は書かない】(学会テンプレートの自動番号 1. / 2.1 / 2.1.1 が付く)。番号の無い節は {.unnumbered} を付ける
    (Abstract・Conflicts of interest・Ethics declaration・Acknowledgements・References)。
  - 式・図・表の参照は [@eq:x] / [@fig:x] / [@tbl:x] だけを書く (Fig. 1 / Table 1 / Eq. 1 の語は自動で付く。
    `Eq. [@eq:x]` と書くと "Eq. Eq. 1" と二重になる)。複数は [@fig:a; @fig:b]。
  - 節の並び (docs/journal-abe.md §3・§8.3。学会テンプレートの見本の並び):
      表題ページ: Title → Author → Affiliation → Subtitle (running title) → Received / Revised → Abstract → Keywords
      本文 (番号つき): Introduction → Materials and methods → Results → Discussion → Conclusion
      後ろの節 (番号なし): Conflicts of interest → Ethics declaration → Acknowledgements → References
    規定が「欠かせない要素」とするのは 表題ページ・著者と所属・キーワード・序論・方法・結果・考察・題のある図表 で
    (§3)、利益相反の申告と文献も要る (§3.3)。規定チェックは Introduction / Materials and methods / Results / Discussion /
    Conflicts of interest / References の節が無ければ要修正にする (節の名前の揺れ (Methods・Acknowledgments など) は同一視する)。
  - 記事種別と本文語数の上限 (§2): Original Paper 4 000 語 / Research Letter 2 500 語 / Technical Note 1 500 語 /
    Review Paper は編集委員会が決める。--article-type original / letter / technical / review で切り替える。
    本テンプレートの語数は本文だけを数える (表題ページ (題〜キーワード)・文献・図表の題と凡例は数えない。規定に数え方の定めは無い)。
  - 綴りは米式か英式のどちらかに統一する。規定とテンプレート自身の節名も揺れている (Conflicts of interest / interests、
    Acknowledgments / Acknowledgements。§9 の 6)。本骨格の節名は英式 (Acknowledgements) で、米式の原稿は Acknowledgments に直してよい。
-->

::: {custom-style="Title"}
<<論文の題 (英語), informative and concise>>
:::

<!-- 題 (§3.1): 簡潔で情報量があること (第三者のサービスでの検索に効く)。
     【略語を使わない】(分野で一般的なものを除く)。【シリーズ番号つきの題 (同じ主題の Part I / Part II など) にしない】。
     大文字の使い方は規定に無い (テンプレートの見本は Title Case)。
     題が空白込みで 50 字を超えるなら、下の running title が必須になる (50 字以内)。 -->

::: {custom-style="Author"}
<<Given-name FAMILY-NAME (姓は全部大文字)>>^1^, <<Given-name M. FAMILY-NAME (ミドルネームは頭文字)>>^1,2^, <<Given-name FAMILY-NAME (姓は全部大文字)>>^2^
:::

<!-- 著者 (§3.1): 名 (given name) と姓 (family name) をフルで書き、ミドルネームは頭文字にする。
     【姓はすべて大文字】(例 Taro YAMADA。規定 "All surnames must be fully capitalized"。テンプレートの見本 `Taroh Seitai` は
     大文字でないが規定を優先する)。学位・肩書は書かない。
     所属は上付きの数字 ^1^ で対応づける (【異なる機関に属する著者がいるときだけ】。全員が同じ機関なら番号は付けない)。
     ※ 投稿後は連絡著者を変えられず、著者の追加・削除・順序の変更には全著者と編集者の承認が要る。投稿前に確定させる
       連絡著者の連絡先は表題ページに書かない (Submission Form と投稿系に入力する。§3.1)。
     ※ 異動後の新住所 (研究を行った機関から移った著者) は、その著者名 (と所属の番号) の直後に【普通の脚注】で書く
       (例 `Hanako CHOKKAN^2^^[Present address: Department of …, City, Country.]`)。docx では著者の脚注の参照と番号が出てきた順に
       上付きの記号 * ** になり (規定の "superscript symbols (such as * and **)")、本文の脚注は数字のまま (profile の
       title_page.author_footnote_marks)。2 人が同じ新住所なら、同じ文面の脚注を 2 度書くか同じ [^addr] を 2 度参照すれば、
       1 つの記号と 1 つの脚注にまとまる。番号と記号の間に区切りが要るなら `^2,^^[…]` (→ 2,*) と書く。
       新住所を所属の Div に書かない (脚注にならず、ページの下に出ない)。 -->

::: {custom-style="Affiliation"}
^1^<<Laboratory, Department, Institute and/or University, City, State/Prefecture, Country>>

^2^<<Laboratory, Department, Institute and/or University, City, State/Prefecture, Country>>
:::

<!-- 所属 (§3.1): 機関の正式名と所在地 (研究室・部門・研究所・大学、市・州・国) を書く。1 機関 1 段落。
     番号の後にタブや空白は書かない (docx で番号の直後にタブが入り、折り返した行の頭がそろう。profile の title_page.affiliation_label_tab)。 -->

<!-- running title (§3.1・§9 の 5): 題が 50 字 (空白込み) を超えるなら、所属の後に 50 字以内の running title を置く。
     規定は別に「abbreviated title を出す」とも書くので、題が 50 字以下でも書いておく (この行の文字が本文のページの柱の中央に入る)。
     学会テンプレートの「abbreviated title」の位置とスタイル (Subtitle) に置く。 -->
::: {custom-style="Subtitle"}
<<Running title, 空白込み 50 字以内>>
:::

<!-- 受付日と改訂日は編集部が記入する欄 (学会テンプレートの見本の文面のまま。[Do not enter])。書き換えない。本文の語数には入らない -->
::: {custom-style="Normal"}
Received ………….. [Do not enter]

Revised ………….. [Do not enter]
:::

# Abstract {.unnumbered}

<!-- 抄録 (§3.1): 【1 段落】・【350 語以内】(全種別)。【構造化抄録 (Objective: … などの見出しつき) は不可】。
     扱う問題・実験の方法 (アプローチ)・主な結果・結論を含める。特定の略語と【図表の引用を避ける】。
     【文献の番号の引用を使わない】— 先行文献に触れるなら題を省いて本文中に書く (例: Kawada T, Mukkamala R, Sugimachi M: Adv Biomed Eng. 8, 110-123, 2019)。
     略語は抄録で定義しても本文の初出で改めて定義する (規定は題と抄録での定義を本文の初出とみなさない。§3.2)。 -->

::: {custom-style="Abstract"}
<<抄録を 1 段落で。扱う問題、実験の方法、主な結果、結論の順に書く。350 語以内>>
:::

<!-- キーワード (§3.1): 【5 語まで】。【題の語を繰り返さない】(キーワードの中の語が 1 つでも題の語と同じなら規定チェックが要修正にする。
     大文字小文字と複数形の語尾は区別しない)。区切りはカンマ、末尾はピリオド (テンプレートの見本 `Keywords: a, b, c.`)。 -->

::: {custom-style="Keywords"}
**Keywords**: <<キーワード 1>>, <<キーワード 2>>, <<キーワード 3>>, <<キーワード 4>>, <<キーワード 5>>.
:::

<!-- ここから本文 (2 段組・行番号つき。表題ページは改ページで独立する)。見出しの番号は書かない -->

# Introduction

<!-- 序論 (§3.2): 新規性と妥当性が読者と査読者に分かるように。研究の目的・先行研究との関係・先行研究から見えた問題の定義を書く。
     網羅的な文献レビューや周知の事柄の繰り返しは要らない。問題を解く全体の方針を書くとよい。
     Original Paper と Research Letter は (i) 目的と応用上の利点 (ii) 新規性の根拠 (iii) 実験結果または計算 (iv) 主な成果 を含むこと (§2)。
     文献は出現順の番号を角括弧で引く ([1] / [3, 4] / [7–10]。CSL が付ける)。原稿には [@bibkey] と書き、文献は ref.bib に持つ。
     略語は本文の初出で正式名とともに括弧で定義する (例: electronic health record (EHR))。 -->

<<背景、先行研究との関係、問題の定義、本研究の目的。文献は `[@bibkey]` の形で引く>>

# Materials and methods

<!-- 方法 (§3.2): 簡潔に、ただし実験や手順を【再現できる詳しさ】で。
     【珍しい試薬・動物・菌株・装置は供給元を書き、製造元か供給元の所在地 (市・国) を括弧で】(例: (HB-0000, Fictional Scales, Tremendo, Fictionia))。
     式と図は適切に使い簡潔に説明する。理論は検証する問いに関係するものだけにし、長い説明の代わりに文献を引く。
     単位はできる限り SI。【量の記号は斜体、単位と元素記号は立体】— 原稿では量の記号を数式 ($P$・$T_1$) で書くと斜体になる。
     数値と単位の間は空白 (4 °C・12 mm)。温度は度記号 + 大文字 C の 2 文字で書く (合成済みの 1 文字の記号は規定チェックが止める)。
     臨床試験は登録番号と登録先を、研究デザインに応じた報告指針 (EQUATOR Network。系統的レビューとメタ解析は PRISMA が必須) を書く。
     画像を加工したならその内容を書く。文例は statements.md の §6〜§9。
     脚注は最小限 (pandoc の ^[脚注] は上付きの数字になり、規定の例と同じ。§3.2)。
     本骨格の既定は、規定が置き場所を決めていない定型の記述 (データの入手先と公開・臨床試験の登録・画像の加工・報告指針) を
     本節の末尾の小節に置き、AI ツールの開示 (規定が Methods と指定) を最後の小節にする (statements.md の冒頭) -->

## <<小節の題 (例: Study design, Apparatus, Analysis)>>

<<方法の記述。供給元は (型番, 会社名, 市, 国) の形で>>

<!-- 番号つきの別行立ての式は次の形で書く (式番号は段の右端に寄る。参照は `[@eq:ラベル]`)。番号の要らない式は {#eq:…} を付けない (中央に置かれる)。
     使うときは、下のコメントの開始行と終了行の 2 行を消す。数式の中の文字は斜体になる (量の記号)。単位は \mathrm{mm} のように立体にする -->

<!--
$$ y = a x + b $$ {#eq:<<式のラベル, 英数字>>}
-->

## Availability of data and materials

<!-- データと材料の入手先と公開 (§1。規定の "Availability of data and materials"):
     公開のデータ・材料は入手先を【受託番号 (accession number) か会社名】で書く。
     自分のデータは【査読中に編集者と査読者へ全量を開示し、出版日までに公開する】(どちらも must。J-STAGE Data への登録を推奨。無料)。
     出版日から 5 年以上保存する。倫理審査・同意の範囲・契約が公開を許さないなら、投稿前に編集事務局に相談する。
     文例は statements.md の §6。データを扱わない研究ならこの小節ごと削る。 -->

<<データと材料の入手先、公開する場所 (J-STAGE Data など)、査読中に編集者と査読者へ開示する方法>>

## Use of artificial intelligence tools

<!-- AI ツールの使用の開示 (§3.2。規定 "Use of artificial intelligence tools"):
     【生成・非生成を問わず】(綴り・文法の確認ツールや LLM を含む)、使った AI ツールを【Methods の節で】開示し、
     【どのツールをどう使ったか】を詳しく書く (データの収集・解析、図の作成・修正、原稿の全部または一部の執筆を含む)。
     【生成 AI の使用は研究デザイン・方法の不可欠な一部である場合に限って原則として認められ、それ以外は編集者が個別に判断する】。
     綴り・文法の確認などで読みやすくする非生成 AI の使用は認められるが、投稿時に編集者へも申告する (cover letter か投稿画面)。
     いずれの場合も原稿の全内容の責任は著者にある。AI ツールは著者にできない。
     ※ 誌によっては Acknowledgments に開示するが、【ABE は Methods】に置く。
     文例 (非生成だけ / 研究の方法の一部としての生成 AI / それ以外の生成 AI) と、使った道具と版を残す作業記録の書き方は statements.md の §4・§5。
     AI ツールを使っていなければこの小節ごと削る (使っていない旨を書く義務は規定に無い。規定チェックは開示が無いことを参考情報で知らせる)。 -->

<<使った人工知能 (AI) ツールの名前、版、提供元と、何にどう使ったか (原稿・データ・図のどの部分か)。著者が全内容に責任を負う旨で結ぶ>>

# Results

<!-- 結果 (§3.2): 考察で使う結果を書く。図表で示したデータの説明を本文で繰り返さない。比べる結果は同じ図か表にまとめる。
     図表 (§5): 本文中の適切な位置に、PDF 版の見た目を写す大きさで埋め込む (分離提出しない)。番号は本文での引用順で
     Fig. 1 / Table 1 (自動)。【図の題とキャプションは図の下、表の題とキャプションは表の上】(docx で自動でそうなる)。
     【題とキャプションは最小限の大文字】(文頭と固有名詞だけ。図中の語も同じ)。【キャプションは本文を読まずに理解できるように完結させる】。
     題 = キャプション (![題](…) / `: 題 {#tbl:x}`)、凡例 (説明) = 直後の custom-style="Legend" の Div で書き分ける。
     凡例は段落だけで書き、(A) / a. で始めない (番号つきリストになる)。凡例の中の略語は改めて定義する。
     画像の加工は最小限・画像全体に・分野の基準内で、原稿に明記する (部分的な移動・削除・追加・強調は不可。元画像を求められうる)。
     他者の著作物の図を使うなら権利者 (と出版社) の許諾を取り、許諾の写しを初回投稿時に添える (statements.md の §10)。 -->

<<結果。図表は本文中の適切な位置に置き、`[@fig:ラベル]` / `[@tbl:ラベル]` で引く>>

<!-- 図表の例が 4 つある。どれも HTML コメントで囲んであるので、使う例のコメントの開始行と終了行の 2 行を消し、<<...>> を埋め、
     図の実ファイルを <入力ルート>/figs/ に置く (PDF の図も原稿では .svg で参照する)。ラベル (fig: / tbl: の後) は英数字とハイフンで、図表ごとに変える。
     囲んであるのは、記入欄の画像 figs/<<図のファイル名>>.svg が実在しないので、そのまま build.sh を掛けると画像の数の照合で止まるから
     (骨格を写した直後でもビルドが通るようにしてある)。記入済みの図表 (段抜きの図と表を含む) は data/dummy/abe/main.md にある。 -->

<!-- 例 1: 段の幅 (83 mm) に置く図。段の幅を超える図は段の幅に縮められ、build が警告する -->

<!--
![<<図の題, 最小限の大文字>>](figs/<<図のファイル名>>.svg){#fig:<<図のラベル, 英数字>>}

::: {custom-style="Legend" for="fig:<<図のラベル, 英数字>>"}
<<図の説明 (キャプション)。本文を読まずに理解できるように完結させる。図中の略語はここで定義する>>
:::
-->

<!-- 例 2: 本文幅に置く図 (段抜き)。{.wide} を足す。凡例は図の直後に置けば一緒に本文幅になる -->

<!--
![<<図の題, 最小限の大文字>>](figs/<<図のファイル名>>.svg){#fig:<<図のラベル, 英数字>> .wide}

::: {custom-style="Legend" for="fig:<<図のラベル, 英数字>>"}
<<図の説明 (キャプション)。本文を読まずに理解できるように完結させる。図中の略語はここで定義する>>
:::
-->

<!-- 例 3: 段の幅に置く表。題は表の上の `: 題` の行。凡例は原稿では表の後に書く (docx で題の直後 = 表の上へ移る) -->

<!--
: <<表の題, 最小限の大文字>> {#tbl:<<表のラベル, 英数字>>}

| <<変数, Variable>> | <<群 A, Group A>> | <<群 B, Group B>> |
|:-------------------|------------------:|------------------:|
| <<項目, item>>     | <<12.3, 値>>      | <<45.6, 値>>      |

::: {custom-style="Legend" for="tbl:<<表のラベル, 英数字>>"}
<<表の説明 (キャプション)。表中の略語と記号の意味をここで書く>>
:::
-->

<!-- 例 4: 段の幅に収まらない表 (列が多い・数字が長い) は、題と表を ::: wide の Div で囲む (段抜き)。凡例は Div の直後に置けば一緒に本文幅になる。
     表の題の {#tbl:x} に .wide を足すと番号が付かないので Div で囲む。build は段に収まらない表を警告して ::: wide を案内する -->

<!--
::: wide
: <<表の題, 最小限の大文字>> {#tbl:<<表のラベル, 英数字>>}

| <<列 1, Trial>> | <<列 2, Value>> | <<列 3, Value>> | <<列 4, Value>> | <<列 5, Value>> | <<列 6, Value>> |
|----------------:|----------------:|----------------:|----------------:|----------------:|----------------:|
| <<1, 値>>       | <<12.345, 値>>  | <<12.345, 値>>  | <<12.345, 値>>  | <<12.345, 値>>  | <<12.345, 値>>  |
:::

::: {custom-style="Legend" for="tbl:<<表のラベル, 英数字>>"}
<<表の説明 (キャプション)。表中の略語と記号の意味をここで書く>>
:::
-->

# Discussion

<!-- 考察 (§3.2): 結果を文脈に位置づけ、手法の妥当性を示す。【研究の限界と、矛盾する結果】をできる限り説明する。
     序論・結果の繰り返しを避ける。 -->

<<主な知見、先行研究との比較、手法の妥当性、研究の限界>>

# Conclusion

<!-- 結論: 規定に節の定めは無いが、学会テンプレートには番号つきの節としてある。不要なら節ごと削ってよい (規定チェックは見ない)。 -->

<<結論。主な成果と、その意味を短く>>

<!-- ここから番号なしの節 (学会テンプレートの番号なしの見出しの段落になる)。{.unnumbered} を消さない -->

# Conflicts of interest {.unnumbered}

<!-- 利益相反 (§3.3・§6.3): 全著者の利益相反を申告する。【無い場合は規定の定型文をそのまま書く】(下の文。変えない)。
     ある場合は関係する会社・団体と内容を著者ごとに書く (文例は statements.md の §1)。判断の基準は学会の COI 開示書式の 9 項目
     (役員・顧問の報酬・株式・特許使用料・講演料・原稿料・研究費など。金額の閾値は円)。
     別に【著者ごとに 1 通の COI 開示書式】を連絡著者がまとめて PDF で出す (提出物。本文の記述と食い違わないこと)。 -->

The authors declare no conflicts of interest with any companies or commercial organizations per the
definition of Japanese Society for Medical and Biological Engineering.

# Ethics declaration {.unnumbered}

<!-- 倫理 (§3.3): 【人や動物を対象にした研究】なら倫理的な扱いの記述を書く。下は規定の例文 1 (ヘルシンキ宣言 + インフォームドコンセント)。
     動物実験は例文 2、ヒトゲノム・遺伝子解析研究は例文 3 (statements.md の §2)。規定の例文の [ ] の欄を記入欄 << >> にしてある。
     承認番号は規定の例文に無いが書いてよい (statements.md の §2 の注意)。
     人を対象にするなら、研究への参加と結果の公表についての同意の取り方を書き、個人を特定できないようにする。
     【倫理委員会の承認などの証拠書類を原稿とともに出す】(提出物)。
     人も動物も扱わない研究なら節ごと削る (規定チェックは、人や動物を扱うらしい語があるのに節が無いときだけ参考情報で知らせる)。 -->

This study was conducted in accordance with the ethical principles of the Helsinki Declaration, and
after obtaining informed consent from each subject. The study was approved by the <<倫理委員会の正式名, ethics committee>>
of <<所属機関の正式名, the affiliated institution>>.

# Acknowledgements {.unnumbered}

<!-- 謝辞 (§3.3): 簡潔に。著者の基準 (ICMJE の 4 基準) を満たさない貢献者への謝辞はここに書く。
     【資金源はすべてこの節に、資金提供者と助成番号の両方を書く】(規定 "both the research funder and the grant number")。
     科研費は "JSPS KAKENHI Grant Number JP…" の形 (statements.md の §3)。
     資金も謝辞も無ければ節ごと削ってよい (規定上の必須の節ではない)。AI ツールの開示はここではなく Materials and methods に書く。 -->

<<謝辞 (著者でない貢献者)。無ければこの段落を削る>>

This work was supported by <<資金提供者の正式名, funder>> (grant number <<助成番号, JP00X00000>>).

# References {.unnumbered}

::: {#refs}
:::

<!-- 文献 (§4。modified Vancouver。data/journals/abe/abe.csl が付ける): 本文は出現順の番号を角括弧で。文献リストは【全著者】
     (et al. で打ち切らない)・題は省略しない・【誌名は PubMed の略記】(ref.bib の journal に略記で持つ。CSL では正式名から略記に直せない)・
     巻は太字 (CSL が付ける)。題の固有名詞と Title Case の書名・会議録の名前は BibTeX の波括弧で保護する
     (pandoc は英語の題を文頭だけ大文字に直す)。
     【引けないもの】: 社内資料・未発表原稿・未発表の学位論文・私信・カタログ・個人的な通信 (規定チェックが参考情報で知らせる)。
     見つけにくい文献は避ける。引用書式の受入テストは bash scripts/check-csl.sh --journal abe。 -->
