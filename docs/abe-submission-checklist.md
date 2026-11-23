# ABE 投稿前チェックリスト

**Advanced Biomedical Engineering (ABE) へ Original Paper を投稿する直前に、人が 1 枚で確認するための表。**
投稿系は Editorial Manager (<http://www.editorialmanager.com/abe/default.aspx>)。規定の読み解きと実装の対応は [`docs/journal-abe.md`](journal-abe.md)、
執筆開始から投稿までの通し手順は [`docs/usage-guide.md`](usage-guide.md) §8 にある。本書はその要約ではなく、**「投稿の当日に手を動かす順番」**で並べ直したものである。

> 本テンプレートは日本生体医工学会 (JSMBE) と ABE の編集部が作成・承認・確認したものではなく、学会・誌と関係が無い (公式のテンプレートではない)。
> 本書は 2026-11 時点の規定 (Instructions to Authors, 1 April 2026) に基づく。投稿の前に <https://abe-journal.org/authorinstructions> で規定が変わっていないかを確かめること。

## この表の読み方

各項目に次の印を付けてある。**印の意味を取り違えると、機械が見ていないものを見たつもりになる。**

| 印 | 意味 |
|----|------|
| 🤖 | **ツールが機械的に担保する。** 指定のコマンドを回して指摘が出なければよい。人が読み直す必要はない |
| 👁 | **人が目で見るしかない。** ツールは検出できない (判断が要る / 外部の情報が要る / 対象がファイルの外にある) |
| 📮 | **事務局か投稿画面で確かめないと決まらない** (§9) |

> **🤖 の多くは「参考情報」止まりである。** ABE の規定チェックのうち、題の略語・所属の上付き・利益相反の定型文・倫理の節・AI の開示の置き場所・
> 資金・略語の定義・引けない文献・図表の題の大文字は、語の有無から推し量る**参考情報**で、規定に合っていることの証明ではない (誤検出も見逃しもある)。
> 各項目にその限界を書いてある。

---

## 0. 投稿の 2〜4 週間前にやること (どのツールも催促しないもの)

**ここは全部 👁 である。** ツールを回しても催促されない。投稿日に気づくと間に合わないものばかりなので先頭に置く。

| | 項目 | 中身 | 出典 |
|---|------|------|------|
| 👁 | **生成 AI の使い方の方針** | 生成・非生成を問わず AI ツールの使用は **Materials and methods で開示する** (must)。**生成 AI の使用は研究の方法の不可欠な一部である場合に限って原則として認められ、それ以外 (原稿の英訳・文章の改善など) は編集者の個別の判断**。英語化に生成 AI を使うなら、投稿前に (1) 事務局に相談するか、(2) 生成 AI を使わない英語化 (専門業者の翻訳・校正。英文校正の証明と兼ねられる) を確保するかを決める。**書かずに済ませる選択肢は無い** | 規定 "Use of artificial intelligence tools" (`journal-abe.md` §3.2) / `skeleton/statements.md` §4 |
| 👁 | **使った AI ツールと版の記録** | 開示は実際に使ったものを書く。執筆が長くなると途中で版が変わるので、**git で追跡する作業記録のファイル**に 1 回の使用ごとに書き足す (コミットのたびに退避・削除される一時ファイルには書かない)。投稿の直前に §2 の開示の文と突き合わせる | `skeleton/statements.md` §5 |
| 👁 | **既発表でないことの確認** | どの言語であれ全部または一部が既発表・印刷中・他誌で審査中なら投稿できない。**会議録 (Proceedings) として刊行されたものは長さ・図表によらず既発表**。既発表にならない例外は**プレプリント**と**図表を含まず 400 語未満の抄録**だけ。元になった発表の形式 (会議録か抄録か・語数・図表・刊行物か) を記録して判断し、迷えば事務局に確かめる。**関連原稿 (他所で審査中・印刷中・刊行済み) は編集者に知らせる義務がある** (カバーレターか投稿画面。Submission Form にも問いがある) | 規定 "Duplicate submission" (`journal-abe.md` §1) / Submission Form (`journal-abe.md` §6.4) |
| 👁 | **著者・著者の順・連絡著者の確定** | **投稿後は連絡著者を変えられない**。著者の追加・削除・順の変更は全著者と編集者の承認が要る。AI ツールは著者にできない。ICMJE の 4 基準 | 規定 "Authorship" (`journal-abe.md` §1) |
| 👁 | **英文校正と証明書** | 英語を母語としない著者は**専門の校正会社の証明書 (か請求書)** を出す。英語の不備は査読の前に返却されうる。発注から納品まで 1〜2 週間を見込む。Submission Form には「著者の 1 人が校正したなら、その著者が筆頭か連絡著者の英文の査読つき論文 2〜3 本を添える」道もある | 規定 / Submission Form (`journal-abe.md` §6.2・§6.4) |
| 👁 | **COI 開示書式の回収** | **著者ごとに 1 通** (1 通にまとめない)。9 項目の Yes/No (金額の閾値は円)。全共著者への依頼が要るので、共著者が多いほど日数がかかる。書式は学会サイト (<https://abe-journal.org/COI_Form.docx>) | 規定 / `journal-abe.md` §6.3 |
| 👁 | **Submission Form and Author Statement の署名** | 書式は学会サイトの Instructions to Authors のページから取る (`journal-abe.md` §6.4)。**Author Statement には全著者が氏名・署名・日付を入れる**。記入済みの書式は個人情報と署名を含むので、`src/forms/` (git で追跡しない) に置く | `journal-abe.md` §6.4・§6.5 |
| 👁 | **倫理審査の証拠書類** | 人・動物を扱う研究は、倫理委員会の承認などの証拠書類を**原稿とともに**出す | 規定 "Ethics declaration" (`journal-abe.md` §3.3) |
| 👁 | **データの全量開示と公開** | 査読中にデータ一式を編集者と査読者へ**全量開示**し、**出版日までに公開**する (どちらも must。5 年以上保存)。**倫理審査の承認・同意の範囲・共同研究の契約が公開を許すか**を先に確かめる (変更の申請には時間がかかる)。許さないなら投稿の前に事務局に相談する。J-STAGE Data への登録が推奨 (無料) | 規定 "Availability of data and materials" (`journal-abe.md` §1) / `skeleton/statements.md` §6 |
| 👁 | **臨床試験の登録** | 臨床試験なら登録番号と登録先 (ICMJE / CONSORT) を原稿に書く。登録は試験の前に済んでいるはず — 番号を手元に用意する | `journal-abe.md` §3.2 / `skeleton/statements.md` §7 |
| 👁 | **報告指針** | 研究デザインに応じて EQUATOR Network の指針に従う。**系統的レビューとメタ解析は PRISMA が必須** | `journal-abe.md` §3.2 / `skeleton/statements.md` §9 |
| 👁 | **転載許諾の写し** | 著者の著作権下にない素材・既発表の素材は権利者 (と出版社) の許諾を取り、**写しを初回投稿時に出す** (投稿当日には間に合わない)。JSMBE の誌と会議録からの転載は許諾が要らない (Submission Form の注記)。該当が無いなら「無い」と確かめておく | `journal-abe.md` §6.2 / `skeleton/statements.md` §10 |
| 👁 | **元画像の保管** | 画像の加工は最小限・画像全体に・原稿に明記。編集者は**加工前の画像**を求めうるので保管しておく | `journal-abe.md` §5 / `skeleton/statements.md` §8 |
| 👁 | **会員資格と掲載料** | 掲載料は非会員 **1 600 USD**、筆頭か連絡著者が JSMBE 会員なら **600 USD** (投稿前に入会を申請し、受理前に承認されれば会員の扱い)。Submission Form に会員番号の欄がある | `journal-abe.md` §1 / `journal-abe.md` §6.4 |
| 👁 | **学会テンプレートの取得** | `ABETemplate.docx` を学会サイトの Instructions to Authors のページ (<https://abe-journal.org/authorinstructions>) から取って `data/journals/abe/ABETemplate.docx` に置く (git で追跡しない・再配布しない)。無ければ build / diff は取得元を出して止まる。**改版されていれば指紋 (SHA-256) が profile の `reference_base_sha256` と違うので build / diff が止まる** — 新しい版を使うなら `data/journals/abe/profile.yaml` の `reference_base_sha256` を表示された値に書き換えてから回し直し、出てくる警告と roundtrip の PDF の見た目 (2 段組・柱・見出しの番号・図表の題) を確かめ直す。ダウンロードで `ABETemplate (1).docx` のような名前になったら、profile の `reference_base` の名前 (`ABETemplate.docx`) に直して置く (`.gitignore` は誌のディレクトリの docx をまとめて外すので、どちらの名前でも追跡には入らない) | `docs/journal-abe.md` §0 |
| 👁 | **プレプリントの扱い** | 投稿前・投稿と同時のプレプリントは推奨。ただし**査読を受けて直した版・受理版・刊行版はプレプリントのサーバに載せない** (刊行版へのリンクは可) | `journal-abe.md` §1 |
| 👁 | **Editorial Manager の画面を見ておく** | 連絡著者がアカウントを作り、**アップロード種別の実物**を確かめる (本文と書式を別々に上げられるか・COI を別に上げるか・英文校正の証明の置き場所・カバーレターの欄・査読者の推薦の欄。§9)。本テンプレートの `SUBMISSION.md` は**規定から作った一覧で、実画面を見て作ったものではない** | §9 |

---

## 1. パッケージを作る (この 5 行で提出物がそろう)

```bash
bash scripts/build.sh     --journal abe --article-type original     # 原稿 docx (本文・カバーレター・回答書)
bash scripts/diff.sh      <旧版の revision> --journal abe --article-type original   # 再投稿のときだけ
bash scripts/package.sh   --journal abe --article-type original --mode final        # 提出物一式 + SUBMISSION.md
bash scripts/check-figures.sh --journal abe                                         # 図の PNG フォールバックの解像度
bash scripts/roundtrip.sh --skip-build                                              # Word で PDF にして Drive の submission-abe/ へ
```

- `--input` は**原稿が `src/` に無いときだけ**足す (動作例を回すなら `--input data/dummy/abe` と `INPUT_ROOT=data/dummy/abe bash scripts/roundtrip.sh --skip-build`)。
- **build と package は同じ誌・同じ profile・同じテンプレートで回す**。提出用 (`--mode final`) の `package.sh` は、`main.docx` を build したときの誌が
  `--journal` と違う・build の後に `profile.yaml` やテンプレート (`reference.docx`) を変えた、のどれでも止まる (草稿は注意だけ)。止まったら
  `bash scripts/build.sh --journal abe …` から回し直すか、`package.sh … --build` で一度に組み直す。`SUBMISSION.md` には誌プロファイルと `reference.docx` の
  SHA-256 が書かれ、roundtrip も送る前と配送の前にそれを今のファイルと照合する (食い違えば届けない)。
- `package.sh` の最後に**規定チェック (validate)** が自動で走り、結果は `data/output/abe/SUBMISSION.md` の「規定チェック」節にも転記される。
  **画面のログは流れて消えるので、最終的な確認は `SUBMISSION.md` で行うこと。**
- **ABE の提出用パッケージは図を本文に埋め込んだまま** (`figures.separate: false`)。`manuscript.docx` は `main.docx` そのもので、
  **投稿系に上げるのは Word で PDF にした `manuscript.pdf`** (roundtrip が作る)。
- **`roundtrip.sh` には `--skip-build` を付ける** — 付けないと roundtrip の最初の段が `build.sh` を引数なしで回し直し、`_default` で上書きする
  (そのうえパッケージより新しいビルドができるので配送の前で止まる)。roundtrip には Windows の PC で watcher が動いていることが要る
  (先に `bash scripts/check-pdf-path.sh` で watcher が「稼働中」・1 個であることを見る。[`docs/roundtrip-windows-watcher.md`](roundtrip-windows-watcher.md))。
- roundtrip は本文と docx の書式を Word で PDF にし、**Drive の `submission-abe/` に `manuscript.pdf` と `forms/<名前>.pdf` を置く**。
  パッケージが草稿モード・古い・別の入力ルートから作られた、のどれかなら何も送らずに止まる。
- **roundtrip が PDF を待つ間に `package.sh` を回さない** — 回し直してパッケージが変わると、配送の前に止まる (PDF にする前に取ったパッケージの
  全ファイルの SHA-256 と照合する。Word の PDF で確かめていない版を届けないため)。止まったら `roundtrip.sh --skip-build` を `--skip-push` なしで回し直す。
- `package.sh` は、書式と補足資料の止まる検査 (読めないディレクトリ・リンク・名前の重なり) を前回のパッケージを消す前に行う。止まっても前回のパッケージは残る。

---

## 2. 原稿 (manuscript.pdf)

### 🤖 ツールが担保する

| | 項目 | 担保するもの | 限界 |
|---|------|------------|------|
| 🤖 | 体裁 (A4・余白 上 25 / 下 20 / 左右 15 mm・Times New Roman 10.5 pt・見出し Arial・2 段組 (段の幅 83.3 mm・段間 13.3 mm)・行番号・柱・ページ番号 n/N) | 学会テンプレートを雛形にした `reference.docx` と後処理 (`docs/journal-abe.md` §11.3 の形)。Word で確かめた値は付録 | **テンプレートが改版されると後処理が外れうる** — 指紋が違えば build / diff が止まり (profile の `reference_base_sha256` を書き換えるまで進まない)、build・diff のたびに体裁の照合の食い違い・生成の警告 (受け皿のスタイル・見出しの番号定義・想定外のパート)・出力のスタイルの欠け (未定義の段落スタイル・見出しの自動番号の欠け) を警告する。**警告は止めないので、build の標準エラーに `警告` が出たら roundtrip の PDF で確かめる** |
| 🤖 | 学会テンプレートの作成者などの識別情報が出力に移らない (文書の情報に作成者名なし) | `make-reference.sh` が reference.docx を作るときに除く (最終更新者・docVars・文書 ID・rsid・customXml・変更履歴・コメント・文書の保護など。残すパートは許可リスト。`docs/journal-abe.md` §8.4) | **知っている置き場所だけ**を外す。許可リストに無いパートは外して警告し、作成者などの属性 (`author` / `initials` / `userId` / `providerId` / `ed`) が残れば止まる。文書の情報は roundtrip の PDF のプロパティでも見る |
| 🤖 | 表題ページの独立 (1 ページ目は題〜Keywords だけ・行番号なし・1 段組。本文は 2 ページ目から 2 段組) | `layout.title_page_break`。表題部の節が 2 段組以上の雛形なら 1 段組に直して警告する | — |
| 🤖 | 見出しの番号 (`1.` / `2.1` / `2.1.1`) と番号なしの節 (Abstract・Conflicts of interest・Ethics declaration・Acknowledgements・References) | テンプレートの自動番号 (小節の番号は節で戻る) と `headings.unnumbered_style` | 原稿に `{.unnumbered}` を書き忘れた節は番号が付く (目で見る) |
| 🤖 | 柱 = running title (表題ページの Subtitle の段落) | `header.running_title_from` | — |
| 🤖 | 図の題は図の下に `Fig. 1 題`、表の題と凡例は表の上に `Table 1 題` (番号の後は空白 1 個・題は太字) | `crossref`・`tables.legend_position`・`figures.keep_together` | 題の文の書き方 (センテンスケース・完結したキャプション) は 👁 |
| 🤖 | 番号つきの式の番号は段の右端 (段抜きなら本文幅の右端。回答書・カバーレターも本文幅の右端) | `equations.style` | 分数・総和は Word が文中の式の大きさで描く (テンプレートの見本と同じ形。付録) |
| 🤖 | 段の幅を超える図は段の幅に縮めて警告、段に収まらない見込みの表も警告 | build の後処理 | **縮めた図の中の文字は小さくなる** (160 mm の図で 52 %)。警告が出たら `{.wide}` / `::: wide` を付けるか作図し直す (👁) |
| 🤖 | 本文語数が記事種別の上限内 (Original 4 000 / Letter 2 500 / Technical 1 500 / Review は照合しない) | `validate.py` (`--article-type`) | **概算**。何を数えるかは規定に書かれていない。本テンプレートの語数は本文の節の段落で、外した凡例の語数を内訳に出す (📮 §9) |
| 🤖 | 抄録 350 語以内・1 段落・文献の引用なし・**構造化抄録でない** (見出しつきの形 `**Background:** …` が無い) | `validate.py` (要修正。構造化抄録は `lint.unstructured_abstract`。語数は 2 つの数え方の大きいほうで判定)。**抄録を `Abstract` の Div で書いたとき**。Div が無い・2 つあれば要修正 (`lint.front_matter_divs`) | 図表に触れていないかは**参考情報** (`Fig. 1` / `Table 2` / `Supplementary Fig. S1` の語で見る)。手で書いた番号の引用 `[2]` も参考情報 (区間などの番号と区別できない) |
| 🤖 | キーワード 5 語以内・題の語を繰り返さない | `validate.py` (要修正。複数形 (不規則な複数形を含む)・ハイフンでつないだ語の各部分を同一視し、`non-` / `self-` / `real-` などの接頭辞は語に数えない)。**題とキーワードを `Title` / `Keywords` の Div で書いたとき**。Div が無い・2 つあれば要修正 | — |
| 🤖 | 題が 50 字 (空白込み) を超えるなら running title があり、50 字以内 | `validate.py` (`limits.running_title_chars`。題の数式は描画に近い字数で数える)。**題を `Title` の Div、running title を `Subtitle` の Div で書いたとき** | 数式の字数は近似 (分数などは 1〜2 字ずれうる) |
| 🤖 | 著者の姓がすべて大文字 | `validate.py` (`lint.author_surname_caps`。要修正)。**著者を `Author` の Div で書いたとき**。著者はカンマ・強制改行・改行のどれで区切ってもよい | 2 字以上の全部大文字の語が 1 つでもあれば通す。**学位・敬称 (`PhD` / `MD` / `Dr.` など) と `Jr.` / `II` などは判定から除き**、学位・敬称は参考で知らせる。辞書に無い学位の略語は見逃しうる |
| 🤖 | 異動後の新住所の脚注が上付きの記号 (`*` `**`)・本文の脚注は上付きの数字 | 後処理 (`title_page.author_footnote_marks`) | **著者の段落の中の脚注だけ**を記号にする — 新住所を所属の Div に書くと脚注にならない (👁)。記号は 4 つまでで、5 個目からは数字のまま (build が警告) |
| 🤖 | 必須の節 (Introduction・Materials and methods・Results・Discussion・Conflicts of interest・References) | `validate.py` (`sections.required`。綴りの揺れを同一視) | **Review Paper でも方法・結果の節が無いと要修正になる** (規定の文言 "All manuscripts must contain …" のまま)。総説で節の立て方が違うなら、規定の要素を満たしているかを人が判断する |
| 🤖 | 題のある図表 (題の無い図・表が無い) | `validate.py` (`lint.float_titles`。要修正)。表は pipe table に加えてパイプでない表 (simple / grid / multiline table) と `Table:` で始まる題も読む。表の題に `{#tbl:x .wide}` と書いた表 (番号が付かない) も要修正 (`lint.table_caption_attrs`。build も警告する) | — |
| 🤖 | 骨格の記入欄 `<<...>>` が残っていない | `validate.py` (`main.md` / `cover-letter.md` の両方) | — |
| 🤖 | 参考: 題の略語・シリーズ番号 / 所属の上付き数字 / 利益相反の定型文か申告 / 倫理の節 / AI の開示が Materials and methods にあるか / 資金と助成番号 / 略語の本文での初出の定義 / 引けない文献 / reference.docx に無い custom-style | `validate.py` (参考情報) | **どれも語の有無から推し量る** (`mouse` は装置のマウスにも当たる・略語は括弧の位置だけを見る)。出なくても規定どおりとは限らない → 下の 👁 |

### 👁 人が目で見る

- [ ] **英語が米式・英式のどちらかに統一されている** (英文校正の納品物をそのまま入れたか)。**規定とテンプレート自身の綴りも揺れる**
      (`Conflicts of interest` / `interests`、`Acknowledgments` / `Acknowledgements`)。骨格の節名は英式 (`Acknowledgements`) なので、米式の原稿なら直す
- [ ] **抄録が 4 要素 (課題・方法・主な結果・結論) を 1 段落で含む** (規定。語数と段落数だけが 🤖)
- [ ] **量の記号は斜体、単位と元素記号は立体** (規定。数式の中は pandoc が斜体にするが、地の文の記号は原稿の書き方しだい)
- [ ] **running title が所属の後にある** (表題ページの並び: Title → Author → Affiliation → running title → Received / Revised → Abstract → Keywords)
- [ ] **異動後の新住所がある著者は、名前の後に上付きの記号 (`*` `**`) があり、1 ページ目の下にその記号の脚注 (`Present address: …`) がある**
      (原稿は著者名の直後の `^[…]`。2 人が同じ新住所なら記号と脚注は 1 つ。所属の段落に新住所を書いていない)
- [ ] **題に略語が無い** (分野で一般的なものを除く) / **シリーズ番号つきの題でない** (validate は参考情報)
- [ ] **略語を本文での初出で定義している** (題と抄録で定義していても、本文の初出で定義し直す)
- [ ] **図表の題とキャプションが最小限の大文字** (文頭と固有名詞だけ) で、**本文を読まずに理解できる** (validate は Title Case らしい題を参考情報で出すだけ)
- [ ] **珍しい試薬・動物・菌株・装置に供給元の所在地 (市・国) を括弧で書いた** (Materials and methods)
- [ ] **Discussion に限界と矛盾する結果を書いた** (規定の Discussion の要点)
- [ ] **原稿に 2 段組の指示や見出しの番号を手で書いていない** (段組と番号は後処理とテンプレートが付ける。`Eq. [@eq:x]` と書くと `Eq. Eq. 1` になる)
- [ ] **段抜きにすべき図表に `{.wide}` / `::: wide` を付けた** (build の警告を見る)。段抜きの直前の短い 2 段組は高さがそろわないことがある
- [ ] **テキストボックス (`.textbox`) を使ったなら、roundtrip の PDF で置き場所 (`page` / `pos-y`) を確かめた**。位置の見積もりは 2 段組と表題ページで
      1 ページずれうる。**図表の番号は原稿の順で付く**ので、置き場所によっては番号の順と紙面の順が食い違う。本文幅の段落は箱を避けて折り返す
- [ ] **凡例には行番号が付かない** (凡例のスタイルは caption を基にしている)。査読者は凡例の位置をページと図表の番号で示すことになる
- [ ] **図の中の文字が読める大きさか** (段の幅に縮めた図・段抜きの図とも roundtrip の PDF を拡大して見る)

#### 👁 Materials and methods の開示と規定上の義務 (文例は `data/journals/abe/skeleton/statements.md`)

- [ ] **AI ツールの開示が Materials and methods にあり**、要素 6 つ (ツール名と提供元・**版**・使い方・範囲・人が確かめた方法・著者の責任) を持つ。
      版は §0 の作業記録から確定した (`statements.md` §4・§5。**版は規定ではなく本テンプレートの上乗せ**)
- [ ] **非生成 AI (綴り・文法の確認) も、投稿時に編集者へ申告した** (カバーレターか投稿画面。骨格の `cover-letter.md` に段落がある)
- [ ] **データの入手先と公開の記述がある** — 「要請に応じて提供」は規定の must を満たさない。**受理後、公開先の DOI に書き換える** (`statements.md` §6)
- [ ] 臨床試験なら**登録番号と登録先**を書いた (`statements.md` §7)
- [ ] 画像を加工したなら**加工の内容**を書いた (`statements.md` §8)
- [ ] **報告指針**に従ったことを書いた (系統的レビューは PRISMA。`statements.md` §9)
- [ ] 転載した図表の凡例に**出典**を書いた (`statements.md` §10)
- [ ] **Conflicts of interest** に規定の定型文 (無い場合) か、全著者の具体的な申告がある (`statements.md` §1)。COI 書式 (著者ごと) の申告と食い違わない
- [ ] **Ethics declaration** に倫理的な扱いの記述 (規定の例文 3 つのどれかに沿う。承認番号) がある (`statements.md` §2)。人・動物を扱わないなら節の要否を判断する
- [ ] **Acknowledgements に資金源をすべて、資金提供者と助成番号の両方で**書いた (`statements.md` §3)

---

## 3. 図表 (本文に埋め込む)

### 🤖 ツールが担保する

| | 項目 | 担保するもの | 限界 |
|---|------|------------|------|
| 🤖 | 図は SVG のままベクターで本文に入り、Word の PDF でもベクター (ラスタ画像 0) | 図の前処理とビルド (SVG のネイティブ埋め込み + 300 dpi の PNG フォールバック) | 執筆者が置いたラスタ図 (写真) の解像度は保証しない (`check-figures.sh` が「注意」に出す) |
| 🤖 | PNG フォールバックが 300 dpi | `bash scripts/check-figures.sh --journal abe` (実画素数まで検算) | 規定に解像度の定めは無い (受理後に別ファイルを求められるかは 📮 §9) |
| 🤖 | 図と題・題と凡例・凡例と表が段・ページで分かれない | `figures.keep_together`・`tables.legend_position` (keepNext) | — |

### 👁 人が目で見る

- [ ] **番号が本文での引用順** (`Fig. 1` → `Fig. 2`。pandoc-crossref は原稿の順に付ける。テキストボックスの図表は §2 の注意)
- [ ] **画像の加工が最小限・画像全体に・分野の基準内** で、原稿に明記してある。部分的な移動・削除・追加・強調をしていない
- [ ] **図中の項目が文法上必要な場合を除き小文字** (テンプレートの注記)
- [ ] **表は画像でなくテキストの表** (差分が効き、Word の PDF でも文字として読める)
- [ ] **転載した図表の許諾の写しがある** (§0)

---

## 4. 引用・文献 (References)

### 🤖 ツールが担保する

| | 項目 | 担保するもの | 限界 |
|---|------|------------|------|
| 🤖 | 本文の引用が角括弧の番号 (`[1]` / `[3, 4]` / `[7–10]`)・文献が全著者・「姓 頭文字」・巻が太字・ページ範囲がエンダッシュ | `abe.csl`。受入テスト `bash scripts/check-csl.sh --journal abe --docx <フィクスチャからビルドした docx>` (フィクスチャ `data/dummy/abe-csl`。公式例 6 件 + 本テンプレートの判断 4 件を 1 文字ずつ・太字まで照合し、本文の引用 17 件と、文献の番号の形 `[1]` と docx の「番号 TAB 本文」も照合する) | `--docx` に渡すのは**フィクスチャからビルドした docx** (原稿の docx を渡すと件数が合わずに NG)。Word の描画は付録 |
| 🤖 | 文献の番号と本文の間がタブだけ (`[1] TAB 本文`)。`[1]`〜`[99]` の 1 行目の本文の頭がぶら下げ字下げ (7.5 mm) にそろう | `bibliography.label_separator: tab` (pandoc の「番号 空白 TAB」の空白を消す) | **`[100]` 以上は番号だけで 7.5 mm を越え、1 行目の本文の頭が次の既定のタブ位置 (段の左 + 14.8 mm) に出る**。Word が両端揃えで語間を詰めた行は、タブも詰まって本文の頭が 0.9 mm 手前に出ることがある (付録) |
| 🤖 | 参考: 引けない文献 (未発表・私信・学位論文・社内資料・カタログなど) | `validate.py` (`lint.uncitable_references`。bib の型と note などの語で見る) | 標準的な手段で見つけにくい文献は判定しない → 👁 |

### 👁 人が目で見る

- [ ] **誌名が PubMed の略記** (`ref.bib` の `journal` に略記で持つ。CSL では正式誌名から略記に直せない)
- [ ] **題を省略していない**・Title Case の書名と会議録の名前を bib で波括弧に入れた (入れないと pandoc がセンテンスケースに直す)
- [ ] **オンライン文献に参照日** (`urldate`) がある
- [ ] **標準的な手段で見つけにくい文献を避けた** (規定)

---

## 5. 提出フォーム (`forms/`)

| | 項目 | 中身 |
|---|------|------|
| 🤖 | `src/forms/` の直下の書式がパッケージの `forms/` に無変換で複製され、docx は Word で PDF になって Drive の `submission-abe/forms/` に置かれる | `submission.collect_forms` と roundtrip。署名してスキャンした PDF は **docx と同じ名前の `.pdf`** で置けば、その PDF がそのまま使われ docx は Word に回らない。拡張子は小文字にそろえて写す (`X.DOCX` → `X.docx`。そろえた名前が重なれば止まる) |
| 🤖 | `SUBMISSION.md` の「提出フォーム」節に 8 項目のチェックリスト (Submission Form and Author Statement・著者ごとの COI・英文校正の証明・倫理の証拠書類・転載許諾・研究データ・関連原稿の通知・査読者の推薦) と書式の一覧 | `submission.forms` |
| 👁 | **書式の PDF を開いて目で見た** (署名・日付・全著者の氏名・ページの欠け。Word で PDF にした書式の版面は学会の書式のまま) | 学会の書式は Word の docx なので、Word で開いた見た目が正 |
| 👁 | **COI 書式が著者の人数分ある**・申告が原稿の Conflicts of interest と食い違わない | — |
| 👁 | 記入済みの書式・署名・倫理の承認書・英文校正の証明を **git に入れていない** (`git status` に出ない) | `.gitignore` の `src/forms/`。`--input` で入力ルートを `src/` 以外にしたときは `<入力ルート>/forms/` が外れないので、`package.sh` が「git で無視されていない (追跡されている)」と注意を出す — `.gitignore` に足す |

---

## 6. 補足資料 (Supplementary)

| | 項目 | 中身 |
|---|------|------|
| 🤖 | 1 ファイル 50 MB 以内・合計 50 MB 以内 | `validate.py` (要修正。10 進のバイトで比べる) と `SUBMISSION.md` の容量の行 (超過に印) |
| 🤖 | 参考: アーカイブ (圧縮) と実行形式のファイルが無い | `validate.py` (`lint.supplementary_archives`。拡張子で見る) |
| 👁 | **最終形で初回投稿時に出す** (受理後は変更できない・査読の対象・受理すると公開される) | — |
| 👁 | 補足資料も**英語で書き、英文校正を受けた**。ソースを含むなら読者の利用の制限の有無と中身を書いた | Submission Form の確認項目 |
| 👁 | Submission Form にファイルごとの名前・形式・査読を望むかを書いた | `journal-abe.md` §6.4 |

---

## 7. Editorial Manager での操作

- **Drive からファイルを選ぶときは `submission-abe/` から取る** (roundtrip の最後の段が置く)。送出先の直下や `processed/` には草稿の `main_…` と
  提出用の `abe-manuscript_…` が時刻付きで並ぶので、そこから選ぶと取り違えやすい。
- **原稿本体は `manuscript.pdf`** (図表を埋め込んだ Word の PDF)。書式は `forms/*.pdf` を書式ごとに上げる。
  **本テンプレートは本文と書式を結合しない**。規定は 1 本の PDF にまとめるよう書く ("should") ので、
  **投稿画面が別々のアップロードを受け付けないなら結合が要る** (📮 §9。`docs/journal-abe.md` §6.1)。
- **初回投稿では `manuscript-diff.docx` と `revise-report.docx` を上げない** (`SUBMISSION.md` の「アップロード種別ではないもの」)。カバーレターは任意 (規定に記述が無い。📮 §9)。
- 査読者の推薦・除外は任意 (編集者は従う義務を負わない)。

> ⚠ `SUBMISSION.md` のアップロード種別は**規定から作ったもの**で、Editorial Manager の実画面を見て作ったものではない。画面と食い違ったら実画面が優先で、
> `data/journals/abe/profile.yaml` の `submission` ブロックを直すこと。

---

## 8. 改訂 (再投稿) と受理後

- [ ] **改訂の期限は判定から 3 か月** (過ぎると取り下げの扱いで新規の投稿になる)。改訂が 2 回以上になることもある。
- [ ] 差分 docx: `bash scripts/diff.sh <旧版の commit> --journal abe --article-type original` (2 段組・柱・題・式番号は build と同じ)。
      **残る制限**: 消した図表・式を参照する消した文の参照は `¿…?` (赤) になる。**画像のファイルもラベルも変えた図 (題も変えた)・ラベルも変えて大きく書き換えた式・
      題が似ていても中身の違う表への差し替え**は削除 + 追加になり、消した文の参照は `¿fig:old?` などになる。文の途中に書いた番号つきの式を書き換えると
      右寄せが掛からないことがある (式を独立した段落に書けば起きない)。削除と追加の間に空白は入らない (`[2][3]`)。
      脚注を書き換えると、旧の脚注 (赤の取消線) と新の脚注 (青) が番号・記号ごと 2 つ並ぶ (脚注の中だけの小さな変更も脚注まるごと)。
      新住所の記号は、消した脚注が旧版の並び、ほかが新版の並びで付く (`docs/journal-abe.md` §13・[`docs/design-fullarea-diff.md`](design-fullarea-diff.md) §7)
- [ ] 回答書は `src/revise-report.md` (`#` / `##` の見出しのまま。docx では番号が付かない・1 段組・行番号なし)。**回答書で示す行番号は改訂稿の PDF
      (`manuscript.pdf`) のページと行で数える** (行番号はページごとに 1 から振り直す)。
- [ ] **査読コメント・回答書・事務局とのやりとりは秘密に保つ** (規定の通信の秘密。公開するリポジトリやほかの原稿に持ち出さない)。
- [ ] **査読を受けて直した版・受理版をプレプリントのサーバに載せない**。
- [ ] 受理後: データの公開先の DOI を原稿に書き入れる / License to Publish に署名する (ライセンスは CC BY / CC BY-SA / CC BY-NC から選ぶ) /
      **校正刷りは受領から 2 日以内に返送** (誤植と脱落の修正だけ。不在の予定は前もって事務局へ伝える)。

---

## 9. 📮 事務局か投稿画面で確かめないと決まらないこと

| | 事項 | 確かめ方 | 本テンプレートの扱い |
|---|------|---------|------------------|
| 📮 | 本文と書式を別々のアップロードで受け付けるか | Editorial Manager のアップロード種別 | 結合しない。受け付けなければ PDF をつなぐ道具を足して `manuscript.pdf` と `forms/*.pdf` をつなぐ |
| 📮 | COI 書式の PDF を 1 本の PDF に入れるのか別か | 同上 | 著者ごとの PDF を別々に上げる |
| 📮 | 英文校正の証明の提出場所 | 同上 | `forms/` に置けば PDF の一覧に載る |
| 📮 | 語数に何を数えるか | 規定に書かれていない。必要なら事務局に確かめる | 本文の節の段落を数え、外した凡例の語数を内訳に出す |
| 📮 | 受理後に図の別ファイル (解像度・形式) を求められるか | 受理後に分かる | 図は SVG (か `.mmd`) が一次ソースなので、求められたら作り直せる (分離提出の形式は受理後の指示に合わせて profile に足す) |
| 📮 | カバーレターの要否 | 投稿画面 | 骨格に任意の `cover-letter.md` (関連原稿の開示と非生成 AI の申告の置き場所) |
| 📮 | 英語化に生成 AI を使ってよいか | 事務局に相談する | §0 で方針を決める |
| 📮 | データを公開できないとき | 事務局に相談する | §0 で確かめる |

---

## 付録: 通し検証で実測した値 (「こう出れば正常」の基準)

動作例 `data/dummy/abe/` の提出用 PDF (`manuscript.pdf`) を Word (Microsoft 365) で作って計測した値。詳細は `docs/journal-abe.md` §11.7。
PDF の文字の大きさは 10.5 pt が 10.6 と出る。座標は PDF の左上が原点の mm。

| 項目 | 値 |
|------|-----|
| 用紙・ページ | A4 (210.0 × 297.0)・5 ページ。フォントはすべて埋め込み (Times New Roman・Arial・Cambria Math のサブセット)・ラスタ画像 0・文書の情報に作成者名なし |
| 表題ページ (1 ページ目) | 題 Arial 太字 16 pt (2 行) → 著者 10.5 pt (所属の番号は上付き 7 pt) → 所属 (番号 x 15.0・本文 x 20.0) → running title Arial 太字 14 pt → Received / Revised → Abstract の見出し Arial 太字 11 pt → 抄録 1 段落 (1 行目の字下げ x 18.8) → Keywords。**行番号なし** |
| 本文の版面 | 本文の上端 y 25.5〜25.9 (余白 25.0)・下端 ≤ 275.3 (余白 20.0 → 277.0)。左の段 x 15.0〜(100.1)・右の段 x 111.7〜(196.8) (段の幅 83.3・段間 13.3。行が段の右端から 1.7 出るのは Body Text の右字下げ −0.45 字でテンプレートの設計どおり) |
| 本文 | Times New Roman 10.5 pt・行送り 4.3 mm・段落の字下げ 1 字 |
| 見出し | `1.`〜`5.` は Arial 太字 12 pt で段の中央、`2.1`〜`3.4` は 11 pt で左、`2.2.1` / `2.2.2` は 10.5 pt。`3. Results` の下は `3.1` から。番号なしの節 (Conflicts of interest / Ethics declaration / Acknowledgements / References) は Arial 太字 11 pt で番号なし |
| 行番号 | 8 pt。ページごとに 1 から、左の段 → 右の段へ通し (p2 1〜68・p3 1〜78・p4 1〜79・p5 1〜30)。位置は左の段の左 (右端 x 11.8) と段間 (右端 x 108.5)。段抜きの範囲の行にも通しで付く。題・凡例・表のセルには付かない |
| 柱・フッタ | 柱は running title `Quantifying the tremendous hunch` (Times New Roman 太字斜体 9 pt・x 82.0〜128.1・y 16.1)。フッタは `n/5` (x 102.7〜107.4・y 275.8)。全ページ |
| 図 | 段抜きの `Fig. 1` は本文幅の中央 x 25.4〜184.7 (幅 159.3)・題は図の直下、凡例は題の下で太字でない。段の `Fig. 2` は右の段 x 113.6〜193.1 |
| 表 | 段の `Table 1` は題 → 凡例 → 表 (三本線) の順で表の上に題と凡例。段抜きの `Table 2` (9 列) は本文幅 x 15.0〜195.1 で数字の折り返しなし |
| 式 | 番号 `(1)` / `(2)` は左の段の右端 x 92.4〜97.6。式は x 18.8 から。分数の分子・分母は 7.6 pt (文中の式の大きさ) |
| 脚注 | 左の段の下 (y 264.0〜275.3・x 15.0〜98.3)、8 pt。番号は `1` から (表題ページの記号の脚注は番号を消費しない) |
| 新住所の脚注 | 著者行は `CHOKKAN²*` (記号は所属の番号と同じ 7.0 pt の上付き)。1 ページ目の下 (表題ページは 1 段組なので用紙の左から) に `*` (5.0 pt) + `Present address: …` (8 pt) |
| 文献 | 見出し Arial 太字 11 pt。`[1]`〜`[3]` は番号 x 15.0〜19.4・本文の頭と続きの行 x 22.5 (ぶら下げ字下げ 7.5 mm)。巻が太字・ページ範囲は U+2013 (エンダッシュ) |
| 引用のフィクスチャ (`data/dummy/abe-csl`) | 2 ページ。文献 10 件の巻の太字は雑誌論文の 2 件だけ (公式例 4 の `Vol. 2` は太字でない)。区切りはすべて U+2013。`[1]`〜`[10]` の本文の頭は段の左 + 7.5 mm (`[2]` は Word が語間を詰めた行で + 6.6 mm) |
| 文献 120 件の試験用の原稿 | `[1]`〜`[99]` は段の左 + 7.5 mm にそろう。`[100]`〜`[120]` は番号の幅 8.1 mm で + 14.8 mm (既知の制限) |
| 差分・回答書・カバーレター | 差分 5 ページ (本文と同じ構成。色は削除 `C00000` の取消線・追加 `2E74B5`)。回答書 1 ページ・カバーレター 1 ページ (1 段組・行番号なし・柱は空・フッタ `1/1`・回答書の見出しに番号なし) |

**コマンドの出力の基準** (学会テンプレートを置いた状態):

| コマンド | こう出れば正常 |
|---------|--------------|
| 規定チェック: `validate.py --input-root data/dummy/abe --journal abe --article-type original` | 要修正 **0**・参考 **0** |
| 規定チェック: `validate.py --input-root data/dummy/abe-lint --journal abe --article-type original` (違反を仕込んだ原稿) | 要修正 **12**・参考 **15** (検査が発火することの確認) |
| 規定チェックの回帰試験: `python3 main/step05_package/test_validate_abe.py` | **132 件**がすべて通り、終了コード 0 |
| 引用様式: `bash scripts/check-csl.sh --journal abe --docx <data/dummy/abe-csl からビルドした docx>` | 文献 **10 件** (公式例 6 + 本テンプレートの判断 4) と本文の引用 **17 件**がすべて一致 |
| 差分エンジン: `bash scripts/check-diff.sh` | **110 項目** (`_default` と `abe`) がすべて通る |

規定チェックと回帰試験は pandoc コンテナで回す (`docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc python3 …`)。
