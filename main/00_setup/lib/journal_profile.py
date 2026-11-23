#!/usr/bin/env python3
"""journal_profile.py — 雑誌プロファイルの読み込み・スキーマ既定値・記事種別解決 (共通モジュール)。

docs/profile-schema.md。profile.yaml の読み込み (load)・スキーマ既定値 (DEFAULTS)・記事種別の解決 (resolve) を
本モジュールに集約する。build_docx.py / package.py / validate.py がそれぞれ profile.yaml を読み、
既定値を各呼び出し側の `.get()` に書くと、30 個を超えるキーの既定値が呼び出し側ごとに
食い違いうるため。

【読み込み経路】`main/00_setup/lib/` は先頭が数字のディレクトリ名でパッケージ import
できず `__init__.py` も無いため、呼び出し側 (main/stepNN_*/xxx.py) は次の 1 行で
本ディレクトリを sys.path に足してから import する (docs/profile-schema.md に記録):

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
    import journal_profile

基準パスは呼び出し側スクリプトの実体位置 (`__file__`) から辿る (parents[1] = main/)。
CWD 非依存で、コンテナ内 (/workspace) とホストのどちらでも同じ式で解決できる。
一方 profile.yaml 自体の探索 (JOURNALS_DIR) は CWD 相対 (リポジトリルートで
実行する規約。build.sh / package.sh が cd で保証する)。

【記事種別の解決規則】(docs/profile-schema.md):
  優先順: article_type 引数 (--article-type) > profile.article_type > 指定なし。
  (a) 上書きは深さ 1 の部分マージ (全置換にしない)。ただし種別の
      abstract_structured が false のときは abstract.labels を明示的に空 [] にする
      (部分マージだと前種別の構造化ラベルが残るため)。
  (b) キー写像: word_count→limits.word_count / abstract_words→limits.abstract_words /
      figures_tables→limits.figures_tables / abstract_structured→abstract.structured /
      abstract_labels→abstract.labels。name / note / sections は解決対象外 (参照用)。
  (c) article_types はあるが種別未指定 → limits/abstract をそのまま使い警告。
  (d) 存在しない種別 → 即エラーで停止 (綴り違いで上限検証が無効化されるのを防ぐ)。
  (e) article_types を持たない誌に種別指定 → 警告して無視。
  (f) limits.keywords はスカラとリストの両形式を受理する。
      スカラ N は「上限のみ指定」として [1, N] に正規化する (`keywords: 5` とだけ書いた
      プロファイルを、リストの形に書き直さずに使えるようにするため)。

【png_fallback_dpi の一本化】figures.pptx.png_fallback_dpi が null / 未指定なら
figures.dpi の値を写す (同じ値を 2 か所に書かないため)。

診断メッセージはすべて stderr に出す (package.py figure-plan の stdout は機械読取の
TSV であるため。stdout を汚すと package.sh の変換計画が壊れる)。
"""

import copy
import re
import sys
from pathlib import Path

import yaml

JOURNALS_DIR = Path("data/journals")

# ---------------------------------------------------------------------
# スキーマ既定値 (docs/profile-schema.md)。「未指定ならどう動くか」を 1 箇所で定義する。
# 値は呼び出し側 (package.py の resolve_* / figure_label) が前提にしている既定と
# 一致させてある。★ 印のキーの既定はすべて「何もしない」側。
# 体裁キー (line_spacing 等) は python 側の消費者がいないため本辞書に含めない
# (それらの既定は data/journals/make-reference.sh 内の焼き込み時既定が正)。
# ---------------------------------------------------------------------
DEFAULTS = {
    "csl": None,                     # null = _default の CSL を継承
    "reference_doc": None,           # null = _default の reference.docx を継承
    # ★ 雑誌が配るテンプレート (誌のディレクトリからの相対名)。あれば make-reference.sh はこれを雛形にして reference.docx を作り、
    # 体裁を焼き込まない (テンプレートが正。patch_reference_docx.py --base)。テンプレートは git で追跡せず人が置く。
    # ensure-reference.sh は生成の元 (テンプレート・profile・生成処理) が変われば作り直す。
    # 体裁キーの照合 (layout_mismatches) は、この誌では profile に書いたキーだけを見る
    "reference_base": None,
    "reference_base_sha256": None,   # ★ テンプレートの指紋。違うテンプレートが置かれたら make-reference.sh が止まる (改版の検知)
    "reference_base_url": None,      # ★ テンプレートの取得元 (無いときの案内に出す)
    # page_numbers はここに置かない。本辞書の方針は上記コメントどおり
    # 「体裁キーは python 側の消費者がいないため含めない (既定は make-reference.sh 側が正)」
    # であり、page_numbers も体裁キーで python 側に消費者がいない (docs/profile-schema.md の「読み手は
    # make-reference.sh であり build / package の実行時ではない」)。ここにも書くと
    # make-reference.sh の flag() 既定との二重定義になる。
    # ★ 行番号の適用範囲。体裁キーだが**唯一 python 側に消費者がある**
    # (build_docx.py が読む) ので DEFAULTS に置く。reference.docx へ焼き込むのではなく、
    # 焼き込み済みの sectPr から `w:lnNumType` を外す形で効かせるため make-reference.sh は読まない。
    #   all        = 全文書に行番号 (既定。_default はこれ)
    #   manuscript = 本文 (main.md) だけに行番号。cover-letter.md / revise-report.md からは外す
    "line_numbers_scope": "all",
    # ★ 見出し。テンプレートが見出しのスタイルに自動番号を持たせ、番号の無い節のために別の段落スタイルを
    # 用意している誌のためのキー。unnumbered_style は {.unnumbered} の見出しを置き換える段落スタイルの名前で、
    # build / diff が citeproc の後に filters/unnumbered-style.lua を掛ける。null = 掛けない (heading のまま)。
    # numbered_scope は見出しの自動番号を残す文書の範囲:
    #   all        = すべての文書 (既定)
    #   manuscript = 本文 (main.md と差分) だけ。回答書 (revise-report.md) とカバーレターの見出しは段落に numId=0 を置いて
    #                番号だけを外す (見出しのスタイルは残る。後処理は step02_build/frontmatter.py の suppress_heading_numbers)
    "headings": {
        "unnumbered_style": None,
        "numbered_scope": "all",
    },
    # ★ 柱 (ヘッダ) の差し替え。テンプレートの柱が「左 TAB 中央 TAB 右」の 1 段落である誌のためのキー。
    # running_title_from は custom-style の名前で、その段落スタイルの最初の段落の文字列を柱の中央に入れる
    # (その段落が無い文書 (カバーレターなど) では中央を空にする)。clear_template_labels が真なら左右の文字も消す。
    # どちらも既定は「何もしない」で、後処理 (step02_build/frontmatter.py) は両方とも未指定なら呼ばれない
    "header": {
        "running_title_from": None,
        "clear_template_labels": False,
    },
    # ★ 表題ページ。affiliation_label_tab が真なら、所属 (custom-style Affiliation) の段落の先頭の上付きの番号の
    # 直後に docx でタブを入れる (テンプレートの所属のスタイルが「番号 + TAB + 本文」前提のぶら下げ字下げを持つ誌のため。
    # 原稿は `^1^Graduate …` のまま)。既定 false = 何もしない
    # author_footnote_marks は記号の並び (例 ["*", "**", "***"])。指定があれば、著者 (custom-style Author) の
    # 段落の中の脚注 (原稿は著者名の直後の ^[Present address: …]) の参照と脚注の番号を、出てきた順に記号にする (w:customMarkFollows)。
    # 文面の同じ脚注は 1 つの記号と 1 つの脚注にまとめる。ほかの脚注は数字のまま。既定 null = 何もしない。解釈は author_footnote_marks()
    "title_page": {
        "affiliation_label_tab": False,
        "author_footnote_marks": None,
    },
    # ★ 段組の節構造。表題部を 1 段組の節、本文を columns 段の節にする誌のためのキー。
    # columns が 2 以上のときだけ働く (既定 null = 何もしない。1 も何もしない)。後処理は step02_build/layout.py。
    #   columns            本文の節の段数。reference.docx が節を 2 つ持つ (雑誌のテンプレートから作った) なら、本文の節は
    #                      reference.docx の最終の節を写し、この値はその照合に使う (テンプレートが正)。1 つしか持たないなら、
    #                      この値と column_space で本文の節を作る
    #   column_space       段間 (`13.3mm` など)。照合か、本文の節を作るときの値
    #   title_block_until  表題部の最後の段落の段落スタイルの名前 (例 Keywords)。その段落までを 1 段組の表題部の節にする。
    #                      本文に無ければ警告して組み立てない
    #   title_page_break   真なら表題部の後で改ページする (表題ページを独立させる)
    #   scope              manuscript (本文 main.md と差分だけ) / all (カバーレターと回答書も)
    # 段の幅を超える図は段の幅に縮め (警告)、`{.wide}` の図と `::: wide` の Div は 1 段組の節で挟んで段抜きにする
    "layout": {
        "columns": None,
        "column_space": None,
        "title_block_until": None,
        "title_page_break": False,
        "scope": "manuscript",
    },
    # ★ pandoc-crossref の設定の誌ごとの上書き。main/00_setup/defaults.yaml の metadata (figureTitle /
    # titleDelim / figPrefix など) と同じ名前と形で書く (例 figureTitle: "Fig."・titleDelim: ""・figPrefix: ["Fig.", "Figs."])。
    # build と diff の描画が「metadata だけを書いた 2 つ目の --defaults」にして defaults.yaml の後に渡す
    # (--metadata-file は defaults.yaml の metadata に負けて効かず、-M はリストの値と重なって pandoc-crossref が止まる)。
    # null = 渡さない (pandoc の引数も出力も変わらない)
    "crossref": None,
    # ★ 別行立ての番号つき数式。style は段落スタイルの名前で、指定があれば pandoc-crossref が番号を付けた
    # 式 ($$…$$ {#eq:x}) の段落をそのスタイルにし、「式 TAB (1)」の形にする (式番号をスタイルの右タブで右に寄せる。
    # 後処理は step02_build/equations.py)。null = 何もしない (番号は式の中で式のすぐ右・式と一緒に中央)
    "equations": {
        "style": None,
    },
    # ★ 文献の段落の番号と本文の区切り。pandoc は second-field-align の CSL の文献を「番号 空白 TAB 本文」で書く
    #   (citeproc が番号の Span の末尾に空白を足し、docx ライタがその Span の後にタブを置く)。
    #   space-tab = そのまま (既定) / tab = 後処理 (postprocess.py) が番号の後の空白を消して「番号 TAB 本文」にする。
    #   空白があると、Word では [10] 以降の番号で「番号 + 空白」がぶら下げ字下げ (ABE のテンプレートは 7.5 mm) を越え、
    #   タブが次の既定のタブ位置まで飛んで 1 行目の本文の頭がずれる (Word 実機で確かめた)。解釈は bibliography_label_separator()
    "bibliography": {
        "label_separator": "space-tab",
    },
    "article_type": None,           # ★ 既定の記事種別 (無指定なら limits をそのまま使用)
    "article_types": None,           # ★ 記事種別ごとの上限・構成の辞書
    "figures": {
        "embed": True,               # 草稿は docx 埋込 (package.resolve_mode の既定)
        "formats": ["pdf"],          # 最終図の形式 (package.resolve_format の既定)
        "dpi": 300,                  # ラスタ図解像度 (package.resolve_dpi の既定)
        "font_handling": "outline",  # svg→pdf のフォント処理 (package.resolve_font_handling の既定)
        "placement": "inline",       # 注: 現状どのコードも読まない
        # ★ ベクターを載せる容器 (pptx / null)。**どのコードも読まない予約キー**
        # (主形式は figures.formats の先頭が決めるため役目が重複する。formats: [png,...] と
        #  vector_container: pptx を同時に書いても pptx は出ない)。将来「ラスタ主形式だが一部の図
        #  だけベクターで出す」を入れるときのために残す。placement と同じ扱い
        "vector_container": None,
        "pptx": {                    # ★ pptx 経路の設定 (package.resolve_pptx_cfg が読む)
            "mode": "svg-blob",
            "slide_fit": "figure",
            "png_fallback_dpi": None,   # null = figures.dpi を継承 (resolve() が写す)
            "text_to_path": False,      # 既定 false
            "inline_css": False,        # 既定 false。true で埋め込む SVG の CSS を要素へ書き出す
                                        # (svg_safe.py。CSS を読まない描画系で描かれても崩れないように)
        },
        "legends_section": None,     # ★ null = 図凡例の集約をしない (値があれば relocate.py が集約する)
        "title_words": None,         # ★ 図の題の語数上限 (検証用)
        "legend_words": None,        # ★ 図凡例の語数上限 (検証用)
        "keys_in_graphic": False,    # ★ 凡例キーを画像内に入れる要件 (注意喚起用)
        "multipanel_single_file": False,  # ★ 多パネル図 1 ファイル合成の要件 (注意喚起用)
        # ★ 図 → 題 → 凡例を段・ページで分けない。真なら後処理 (step02_build/captions.py) が、図の段落と、
        # 凡例が続く題・凡例の段落 (最後の 1 つを除く) に keepNext を付ける。既定 false = 何もしない
        "keep_together": False,
        # ★ 提出用 (package.sh --mode final) で図を本文から外して別ファイルにするか。
        #   true  = 既定 (図を [Figure N about here] にして figures/ へ分離。表の移設・図凡例の集約も行う)
        #   false = 図を本文に埋め込んだまま提出用にする (図表を本文に埋め込んで提出する誌)。提出用かどうか (出所の照合を
        #           止める側にする・SUBMISSION.md に「提出用ではない」を書かない・roundtrip が配送する) は true のときの final と同じ。
        #           figures.formats / numbering は使わない。tables.placement の end / separate・figures.legends_section とは併用できない
        # 解釈は figures_separate()
        "separate": True,
    },
    "tables": {                      # ★ ブロックごと新規
        "placement": "inline",       # inline = 末尾移設しない (既定。end なら relocate.py が末尾へ移す)
                                     # end = 本文末尾へ移す / separate = 本文から外し
                                     # 1 表 1 ファイルで出す。解釈は
                                     # relocate.table_placement() (未知の綴りはエラーで停止)
        # ★ 末尾へ移した表の前に置く見出し。null = 見出しを置かず改ページのみ。
        # BHI の規定は原稿本体の構成として "Tables" を列挙するだけで見出しの文言を定めていないため
        # 既定は null にした (規定に無い文字列を提出物へ勝手に足さない)。見出しを要求する誌のための
        # 逃げ道として profile 側で指定できるようにしてある (figures.legends_section と対の関係)。
        "section_title": None,
        # ★ 表の凡例 (custom-style="Legend" の Div) の位置。原稿では凡例を表の後に書く (記法は誌によらない)。
        #   below = そのまま表の下 (既定) / above = 後処理 (step02_build/captions.py) が表の直後の凡例を題と表の間へ移し、
        #   題 → 凡例 → 表を keepNext でつなぐ (「表の題とキャプションは表の上」の誌)。
        # placement の end / separate とは併用できない (提出構成の組み替え (relocate.py) は凡例が表の後にある前提)。解釈は table_legend_position()
        "legend_position": "below",
        "object": None,
        "allow_color": True,         # true = 制限なし
        "thousands_separator": True, # true = 制限なし
        "title_words": None,
        "legend_words": None,
        "separate_file_allowed": True,
    },
    "limits": {
        "word_count": None,
        "abstract_words": None,
        "references": None,
        "figures_tables": None,      # ★
        "title_words": None,         # ★
        "keywords": None,            # スカラ N も可。resolve() が [下限, 上限] に正規化
        "video_mb": None,            # ★
        # ★ running_title_chars は題と running title の字数 (空白込み) の上限: 題がこれを超えるなら
        # running title (header.running_title_from の custom-style。未指定なら Subtitle) が要り、running title もこれ以内
        "running_title_chars": None,
        # ★ <INPUT_ROOT>/supplementary/ の 1 ファイルの上限と合計の上限 (MB = 1 000 000 バイト。動画に限らない)
        "supplementary_file_mb": None,
        "supplementary_total_mb": None,
    },
    "blinded": False,
    "abstract": {
        "structured": False,
        "labels": None,              # ★ 構造化抄録の見出しラベル
        "citations_allowed": True,   # ★ true = 制限なし
        "keyword_source": None,      # ★
        "single_paragraph": False,   # ★ true = 抄録が 2 段落以上なら要修正
        "floats_allowed": True,      # ★ false = 抄録が図表に触れていたら参考情報
    },
    # ★ 最上位の節。article_types.<種別>.sections (一次資料の転記で参照用) とは別物で、こちらは検査に使う。
    #   required  必ず要る節の名前の list。最上位の見出し (原稿のいちばん浅い段の見出し) で探し、無ければ要修正
    #             (pandoc が {#refs} の Div の無い原稿に足す文献の見出し = defaults.yaml の reference-section-title も数える)
    #   aliases   同じ節とみなす名前の組の list (例 ["Materials and methods", "Methods"])。required と lint の *_section が使う。
    #             大文字小文字・語末の s (単複)・& と and の違いは組に書かなくても同一視する
    # BHI の declarations.required は「Declarations」見出しの下だけを探すので、最上位の節には使えない
    "sections": {
        "required": None,
        "aliases": None,
    },
    "declarations": {                # ★ ブロックごと新規
        "required": None,
        "credit": False,
        "abbreviations_section": False,
    },
    "submission": {                  # ★ ブロックごと新規
        "text_formats": None,
        "table_formats": None,
        "figure_formats": None,      # 定義された場合、代替図形式がここに無ければエラー停止
        "video_formats": None,
        "forms": None,
        # "as-is" = 無変換で公開・査読対象・受理後は変更不可の決まった文 (BHI)。ほかの文字列はそのまま SUBMISSION.md の補足資料の節に書く
        # null = 「補足資料。」だけ
        "supplementary": None,
        # ★ 記入済みの書式 (<INPUT_ROOT>/forms/) を提出パッケージの forms/ に複製するか。true なら
        #   SUBMISSION.md に一覧を出し、docx の書式は roundtrip が Word で PDF にして submission-<journal>/forms/ に置く
        #   (同じ名前の PDF を置いた書式は、その PDF をそのまま使う)。記入済みの書式は署名・個人情報を含むので git で追跡しない
        "collect_forms": False,
        # ★ SUBMISSION.md で差分 docx (manuscript-diff.docx) の行の下に書く注記。null = 書かない
        "diff_note": None,
    },
    # ★ 執筆 lint (ブロックごと新規)。
    #
    # 【2 層構成】
    # `forbid_chars` の合成文字回避・`units: SI`・記入欄 `<<...>>` の残存・凡例 Div の配置規則は
    # **BHI 固有ではない** — 前 2 つは欧文組版と医学系誌の一般則、後ろ 2 つは本テンプレの記法の
    # 規約である。BHI プロファイルにだけ置くと、同じ原稿を別の誌でパッケージした瞬間に
    # 検査が消え、「本文は雑誌非依存に保つ」原則と矛盾する。そこで**基底 (ここ) に既定値を置き、
    # 雑誌側は上書き・追加のみ**とする。lint ブロックを持たない誌 (_default など) にも
    # 基底の値がそのまま効くが、いずれの検査も**該当する記述が原稿に無ければ沈黙する**ので
    # ダミー原稿の出力は変わらない。
    # 逆に `device_notation` と `corresponding_author` は誌ごとに温度差があるため既定は無効に
    # しておき、要求する誌 (BHI) がプロファイルで有効にする。
    "lint": {
        # 合成 1 文字は「度記号 + C」等に分解して書く (BHI Units 節 4。他誌でも組版事故のもと)
        "forbid_chars": ["℃", "℉", "㎎", "㎏", "㎜", "㎝", "㎡", "㎥", "㎕", "㎖", "㎗"],
        "units": "SI",               # 非 SI 単位らしき語の狭い検出 (参考情報)
        "device_notation": False,    # 統計ソフトのバージョン・製造元の記載 (誌ごと)
        "placeholder_markers": True, # 骨格の記入欄 `<<...>>` の残存 (テンプレ共通の規約)
        "legend_placement": True,    # 凡例 Div の配置規則と中身 (テンプレ共通の記法)
        "corresponding_author": False,  # 連絡著者ブロックの検査 (誌ごと)
        # ref.bib の langid が japanese 以外なら要修正 (誌ごと)。langid があるだけで
        # "(in Japanese)" を付ける引用様式を使う誌で true にする
        "langid_japanese_only": False,
        # --- 誌ごとに有効にする検査 (どれも既定は無効。要求する誌がプロファイルで有効にする) ---
        "author_surname_caps": False,     # 要修正: 著者 (Author の Div) の姓がすべて大文字か
        "affiliation_superscript": False, # 参考: 機関が 2 つ以上なら所属と著者が上付きの数字で対応づけられているか
        "keywords_not_in_title": False,   # 要修正: キーワードが題の語 (冠詞・前置詞などを除く) を繰り返していないか
        "title_conventions": False,       # 参考: 題の略語・シリーズ番号 (Part II など) の題
        "float_titles": False,            # 要修正: 題 (キャプション) の無い図表
        "caption_minimal_caps": False,    # 参考: 図表の題が Title Case らしい (最小限の大文字の誌)
        "abbreviation_definitions": False,  # 参考: 略語を本文の初出で括弧で定義しているか
        "uncitable_references": False,    # 参考: 引けない文献 (未発表原稿・学位論文・私信など。ref.bib の型と note で見る)
        # 次の 4 つは節の名前 (sections.aliases の言い換えも同じ節とみなす)。null = 検査しない
        "coi_section": None,              # 参考: この節に定型文 (coi_standard_sentence) も具体的な申告も無さそうなら
        "coi_standard_sentence": None,    #   利益相反が無い場合の定型文 (誌が定めるもの)
        "ethics_section": None,           # 参考: 人・動物を扱うらしい語があるのにこの節が無い
        "ai_disclosure_section": None,    # 参考: AI ツールらしき語がこの節の外にだけある / どこにも無い
        "funding_section": None,          # 参考: 資金らしき語があるのにこの節に無い / この節に助成番号らしき語が無い
        "supplementary_archives": False,  # 参考: 補足資料にアーカイブ・実行形式のファイルがある
        # 要修正: 抄録が見出しつきの構造化抄録の形 (**Objective:** … など) でないか。abstract.structured が偽の誌で使う
        "unstructured_abstract": False,
        # 要修正: ここに挙げた custom-style の Div がちょうど 1 つずつあるか (例 ["Title", "Author", "Abstract",
        #   "Keywords"])。表題ページの検査は Div を読むので、Div が無い・2 つ以上あると黙って空振りする。null = 検査しない
        "front_matter_divs": None,
        # 要修正: 表の題の属性に {#tbl:x} 以外のもの (.wide など) があるか (pandoc-crossref が番号を付けられない)
        "table_caption_attrs": False,
    },
    "numbering": {
        "figure": "Figure %d.",      # package.figure_label の既定
        "table": "Table %d.",
    },
}

# (b) 記事種別 → profile 本体へのキー写像 (深さ 1 の部分マージ)
_TYPE_KEYMAP = {
    "word_count": ("limits", "word_count"),
    "abstract_words": ("limits", "abstract_words"),
    "figures_tables": ("limits", "figures_tables"),
    "abstract_structured": ("abstract", "structured"),
    "abstract_labels": ("abstract", "labels"),
}
# name / note / sections は解決対象外 (参照用。sections は一次資料 "Main Text" 欄の転記で
# あり実節順の検査に使わない)


def _warn(msg):
    print(f"  [journal_profile] {msg}", file=sys.stderr)


def _section(prof, name):
    """prof[name] を必ず dict として返す (無い / null なら空 dict を入れてから返す)。

    profile.yaml で `limits:` のようにブロック名だけ書いて中身を
    省くと値が None になり、_deep_merge は None で既定の dict を上書きする。そのとき
    `prof.setdefault(sect, {})[dst_key] = ...` と書くと、キーが存在して値が None なので
    setdefault が None を返し `TypeError: 'NoneType' object does not support item
    assignment` で異常終了する (新規誌を起こすときの落とし穴)。
    """
    if not isinstance(prof.get(name), dict):
        prof[name] = {}
    return prof[name]


_MISSING = object()


def _merge_forbid_lists(prof, raw_profile):
    """lint の **禁止集合** (`forbid_*` の list) を「基底 ∪ 誌」で解決する。

    `_deep_merge` は list をまるごと置換するので、誌のプロファイルが `lint.forbid_chars` を
    書くと**基底の検査を弱められる** (誌が基底より少ない文字を書くと、規定を持つその誌でだけ
    残りの文字が素通りする。値をそろえても、同じ形の事故はキーが増えるたびに再発しうる)。
    lint の 2 層構成は「基底に既定・誌は**上書きと追加**」(DEFAULTS["lint"] の説明) なので、
    禁止集合については加算で解決するのが趣旨に合う。

    **`forbid_` で始まる list のキーだけ**を対象にする。lint 以外のブロック
    (`figures.formats` / `abstract.labels` / `submission.*_formats` 等) は「誌の値で
    置き換える」が正しい意味なので触らない。同じ理由で、将来 lint に許可リスト
    (`allow_*`) を足すときもここへ入れてはならない — 和集合は許可を広げる側に効き、
    誌が範囲を狭められなくなる。

    **無効化したい誌は `null` を書く** (`forbid_chars: null` → 検査そのものが沈黙する)。
    空リストではなく null を要求するのは、意思表示を明示させるためである。

    **`null` を受け取ったら警告を 1 行出す**。YAML では
    `forbid_chars:` と書いて値を省略した場合も `null` になるため、**書き忘れと明示的な無効化を
    区別できない**。値を書きかけて保存した・一覧を別の場所へ移そうとして中身だけ切り取った、
    といった編集の途中状態が、黙っていればそのまま**検査の無効化**として通る (上で塞いだ
    「誌が基底の検査を弱められる」経路が、置き換えから書き忘れに移るだけになる)。
    明示的な無効化なら警告は正しい情報であり、書き忘れなら気づける。

    **基底に存在しない `lint` キーにも警告を出す**。`lint.forbid_char`
    のように綴りを間違えると、基底に同名キーが無いので本関数は触らず、意図した文字が
    黙って効かない (検査は基底のまま残るので弱まりはしないが、書いた側は気づけない)。
    """
    raw_lint = raw_profile.get("lint") if isinstance(raw_profile.get("lint"), dict) else {}
    out = _section(prof, "lint")
    for key, base_val in DEFAULTS["lint"].items():
        if not (key.startswith("forbid_") and isinstance(base_val, list)):
            continue
        own = raw_lint.get(key, _MISSING)
        if own is _MISSING:
            continue                       # 未指定 = 基底のまま
        if own is None:
            # null は「明示的な無効化」だが YAML の値書き忘れと同じ形になる
            _warn(f"lint.{key} が null のため、この検査を行いません "
                  f"(無効化の意思表示なら正しい動作です。値の書き忘れなら基底の "
                  f"{len(base_val)} 件が効かなくなっています)")
            continue
        if isinstance(own, list):
            merged = list(base_val)
            merged += [v for v in own if v not in merged]
            out[key] = merged
    # 綴り違いのキーは黙って無視されるので名指しで知らせる
    for key in raw_lint:
        if key not in DEFAULTS["lint"]:
            _warn(f"lint.{key} は既知の検査ではありません (綴り違いの可能性)。"
                  f"この指定は無視されます")


def _deep_merge(base, override):
    """dict を再帰マージした新しい dict を返す (override 優先。list はまるごと置換)。

    例外は lint の禁止集合 (`forbid_*`) で、resolve() が `_merge_forbid_lists` で
    「基底 ∪ 誌」に解き直す。理由は同関数の説明を参照。
    """
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load(journal_id, journals_dir=None):
    """data/journals/<id>/profile.yaml を読んで生 dict を返す。無ければ空 dict (警告)。"""
    path = (journals_dir or JOURNALS_DIR) / journal_id / "profile.yaml"
    if not path.is_file():
        _warn(f"{path} が無いため _default 既定を使います")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve(profile, article_type=None):
    """スキーマ既定値を敷き、記事種別で limits / abstract を解決した profile を返す。

    冪等: 解決済み profile (_resolved マーカー付き) を同じ種別 (または種別無指定) で
    再度渡された場合はそのまま返す (package.py → validate.py の受け渡しで二重解決と
    警告の重複を防ぐ)。

    判定は `article_type in (None, profile["article_type"])` だけでは足りない。
    article_types を持たない誌では解決後も article_type が None のままなので、
    同じ種別を渡し直した package.py → validate.py の 2 回目で素通りせず再解決し、規則 (e) の
    警告が二重に出る (実測)。そこで要求された種別そのものを `_resolved_for` に控えて判定に
    加える。別の種別を渡し直したときは解き直す。
    """
    profile = profile or {}
    if profile.get("_resolved") and article_type in (
            None, profile.get("_resolved_for"), profile.get("article_type")):
        return profile

    prof = _deep_merge(DEFAULTS, profile)
    # 禁止集合だけは list 置換ではなく「基底 ∪ 誌」にする
    _merge_forbid_lists(prof, profile)

    # **その誌が自分で宣言した lint キー**を控える。lint の 2 層構成
    # (基底に既定・誌は上書き) では、解決後の profile を見ても値の出所が分からない。
    # 出所が分からないと、規定を調べていない誌の指摘まで「規定違反の可能性」として出すことに
    # なる (合成文字・記入欄・凡例の配置は基底では欧文組版とテンプレの記法の規約に過ぎない)。
    # validate.py が指摘の文末に出所を添えるために使う。
    # 既に控えられていれば上書きしない — 解決済み profile を別の記事種別で渡し直したとき、
    # 解決後の全キー (= 基底由来を含む) で塗り潰さないため。
    if "_lint_declared" not in prof:
        raw_lint = profile.get("lint")
        prof["_lint_declared"] = sorted(raw_lint) if isinstance(raw_lint, dict) else []

    types = prof.get("article_types")

    if types:
        atype = article_type or prof.get("article_type")
        if atype is None:
            # (c) 種別未指定: limits / abstract をそのまま使う
            _warn("既定の記事種別が未指定です (article_type / --article-type)。"
                  "limits / abstract をそのまま使います")
        elif atype not in types:
            # (d) 未知の種別は即エラー (黙って素通しすると上限検証が無効化されたまま投稿されうる)
            sys.exit(f"エラー: 記事種別 '{atype}' は article_types に存在しません "
                     f"(有効: {', '.join(sorted(types))})")
        else:
            spec = types[atype] or {}
            for src_key, (sect, dst_key) in _TYPE_KEYMAP.items():
                if src_key in spec:  # (a) 深さ 1 の部分マージ (null も明示値として写す)
                    _section(prof, sect)[dst_key] = copy.deepcopy(spec[src_key])
            if spec.get("abstract_structured") is False:
                # (a) 非構造化の種別ではラベルを明示的に空にする (前種別のラベル残留を防ぐ)
                _section(prof, "abstract")["labels"] = []
            prof["article_type"] = atype
    elif article_type:
        # (e) article_types を持たない誌への種別指定は警告して無視
        _warn(f"この雑誌プロファイルは article_types を持たないため "
              f"--article-type '{article_type}' を無視します")

    # (f) limits.keywords の正規化: スカラ N → [1, N]
    kw = (prof.get("limits") or {}).get("keywords")
    if isinstance(kw, (int, float)) and not isinstance(kw, bool):
        _section(prof, "limits")["keywords"] = [1, int(kw)]

    # png_fallback_dpi の一本化: null なら figures.dpi を写す。
    # figures が null でも _section() で prof に dict を入れてから書く (局所変数に書くと捨てられる)
    figures = _section(prof, "figures")
    if not isinstance(figures.get("pptx"), dict):
        figures["pptx"] = {}
    pptx = figures["pptx"]
    if pptx.get("png_fallback_dpi") is None:
        pptx["png_fallback_dpi"] = figures.get("dpi", DEFAULTS["figures"]["dpi"])

    prof["_resolved"] = True
    prof["_resolved_for"] = article_type   # 冪等ガードの判定に使う
    return prof


def load_resolved(journal_id, article_type=None, journals_dir=None):
    """load() → resolve() の一括呼び出し (build_docx.py / package.py / validate.py が使う)。"""
    return resolve(load(journal_id, journals_dir=journals_dir), article_type)


# ---------------------------------------------------------------------
# 体裁キーの値の解釈と、reference.docx との突合
#
# 体裁は profile.yaml (意図) と reference.docx (実体) の二重管理になる。値の解釈を
# data/journals/make-reference.sh (焼き込み側) と build / validate (検査側) が別々に持つと、
# それ自体が「既定値の二重定義」を作ることになるため、
# 解釈は本モジュールに 1 つだけ置き、make-reference.sh からも import して使う。
# ---------------------------------------------------------------------

LAYOUT_KEYS = ("line_spacing", "line_numbers", "page_numbers", "font", "font_size",
               "margins", "paper_size")
TRUE_WORDS = {"true", "yes", "on", "y", "1"}
FALSE_WORDS = {"false", "no", "off", "n", "0"}


def as_flag(v, key="(キー名不明)", default=False):
    """真偽値キーを解釈する。認識できない値は default に落としたうえで警告する。

    落ち先が「機能を無効にする」なので、page_numbers: enabled のような
    1 語の誤記でページ番号が静かに落ち、BHI では規定違反の docx がそのまま提出物になる。
    y / n も真偽語として受ける (YAML 1.1 は y 単独を真偽値に解決しないため文字列で届く)。
    """
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    word = str(v).strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    _warn(f"{key}: {v!r} は真偽値として解釈できないため {default} として扱います "
          f"(真: {'/'.join(sorted(TRUE_WORDS))} / 偽: {'/'.join(sorted(FALSE_WORDS))})")
    return default


def as_choice(v, allowed, default, key=None):
    """列挙キーを解釈する (候補外・未指定は default)。make-reference.sh の choice() と同一。

    候補外の値は**警告して** default にする (黙って既定値にすると、`heading_color: red` や `paper_size: b5` のような
    1 語の誤記で機能が静かに落ちる)。key はその警告に出すキーの名前。
    """
    word = (str(v).strip().lower() if v is not None else "")
    if word in allowed:
        return word
    if word:
        print(f"[警告] profile の {key or '値'} = '{v}' は候補 ({' / '.join(sorted(allowed))}) に無いので、"
              f"既定の '{default}' を使います", file=sys.stderr)
    return default


def _style_name(v, key):
    """スタイルの名前を書くキーの値を解釈する (未指定・空は None。文字列でなければ警告して None)。"""
    if v is None:
        return None
    if not isinstance(v, str):
        _warn(f"{key}: {v!r} はスタイルの名前 (文字列) ではないので使いません")
        return None
    return v.strip() or None


def unnumbered_style(profile):
    """headings.unnumbered_style (番号なしの見出しにする段落スタイルの名前) を返す。未指定なら None。

    build_docx.py と diff_docx.py が同じ解釈で filters/unnumbered-style.lua を掛けるために 1 か所に置く。
    """
    return _style_name((profile.get("headings") or {}).get("unnumbered_style"), "headings.unnumbered_style")


def heading_numbers_kept(profile, is_manuscript):
    """この文書で見出しの自動番号を残すか (headings.numbered_scope)。

    all (既定) ならどの文書でも真。manuscript なら本文 (main.md と差分) だけ真で、回答書とカバーレターは偽
    (build が見出しの段落の番号を外す)。候補外の値は警告して all。
    """
    scope = as_choice((profile.get("headings") or {}).get("numbered_scope"), {"all", "manuscript"}, "all",
                      key="headings.numbered_scope")
    return scope == "all" or is_manuscript


def running_header(profile):
    """header.* (柱の差し替え) を {running_title_from, clear_template_labels} で返す。どちらも無ければ None。

    None のとき後処理は柱に触らない (キーを持たない誌の出力は変わらない)。
    """
    sect = profile.get("header") or {}
    src = _style_name(sect.get("running_title_from"), "header.running_title_from")
    clear = as_flag(sect.get("clear_template_labels"), "header.clear_template_labels", default=False)
    if src is None and not clear:
        return None
    return {"running_title_from": src, "clear_template_labels": clear}


def affiliation_label_tab(profile):
    """title_page.affiliation_label_tab (所属の番号の後にタブを入れるか) を真偽値で返す。"""
    return as_flag((profile.get("title_page") or {}).get("affiliation_label_tab"),
                   "title_page.affiliation_label_tab", default=False)


def author_footnote_marks(profile):
    """title_page.author_footnote_marks (著者の脚注に使う記号の並び) を文字列のリストで返す。未指定・解釈できなければ None。

    リストの要素は空でない文字列 (`"*"` / `"**"` / `"†"` など)。1 つの文字列だけを書いたら 1 要素のリストとみなす。
    同じ記号が 2 度出る並びは、別の脚注に同じ記号が付いて見分けられなくなるので使わない (警告して None)。
    """
    v = (profile.get("title_page") or {}).get("author_footnote_marks")
    if v is None:
        return None
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list) or not v or not all(isinstance(m, str) and m.strip() for m in v):
        _warn(f"title_page.author_footnote_marks: {v!r} は記号 (空でない文字列) のリストではないので使いません "
              '(例 ["*", "**", "***"])')
        return None
    marks = [m.strip() for m in v]
    if len(set(marks)) != len(marks):
        _warn(f"title_page.author_footnote_marks: {marks!r} に同じ記号が 2 度あるので使いません (別の脚注が同じ記号になる)")
        return None
    return marks


LENGTH_TWIP = {"mm": 1440 / 25.4, "cm": 1440 / 2.54, "in": 1440.0, "pt": 20.0}


def as_length_twip(v, key):
    """`13.3mm` / `0.5in` / `12pt` / `1.2cm` のような長さを twip (1/20 pt) の実数で返す。未指定・解釈できなければ None (後者は警告)。

    単位の無い数は受け付けない (mm か twip かを取り違えると、段間が 50 倍違っても気づけないため)。
    """
    if v is None:
        return None
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*(mm|cm|in|pt)\s*", str(v).lower())
    if not m:
        _warn(f"{key}: {v!r} は長さとして解釈できません (`13.3mm` のように単位 mm / cm / in / pt を付けて書く)。使いません")
        return None
    return float(m.group(1)) * LENGTH_TWIP[m.group(2)]


def layout(profile):
    """layout.* (段組の節構造) を解釈して返す。働かない (columns が無い・2 未満・誤記) なら None。

    返り値: {columns, column_space_twip, title_block_until, title_page_break, scope}。title_block_until は None でありうる
    (そのときは後処理が警告して組み立てない)。build_docx.py と diff_docx.py が同じ解釈で使うために 1 か所に置く。
    """
    sect = profile.get("layout")
    if sect is None:
        return None
    if not isinstance(sect, dict):
        _warn(f"layout: {sect!r} は辞書ではないので使いません (columns / title_block_until などのキーを持つブロックで書く)")
        return None
    cols = sect.get("columns")
    if cols is None:
        return None
    if isinstance(cols, bool) or not isinstance(cols, int):
        _warn(f"layout.columns: {cols!r} は段数 (整数) ではないので、段組の節を組み立てません")
        return None
    if cols < 2:
        return None
    return {
        "columns": cols,
        "column_space_twip": as_length_twip(sect.get("column_space"), "layout.column_space"),
        "title_block_until": _style_name(sect.get("title_block_until"), "layout.title_block_until"),
        "title_page_break": as_flag(sect.get("title_page_break"), "layout.title_page_break", default=False),
        "scope": as_choice(sect.get("scope"), {"manuscript", "all"}, "manuscript", key="layout.scope"),
    }


# pandoc-crossref の設定の名前 (main/00_setup/defaults.yaml の metadata と、pandoc-crossref の主な設定)。crossref ブロックに
# これ以外の名前があれば警告する (そのまま渡す)。pandoc-crossref は知らない名前を黙って無視するので、figuretitle のような
# 綴りの誤りは出力の題が変わらないことでしか気づけないため
CROSSREF_KEYS = {
    # 題と参照の語 (defaults.yaml にあるもの)
    "figureTitle", "tableTitle", "listingTitle", "titleDelim",
    "figPrefix", "tblPrefix", "eqnPrefix", "secPrefix", "lstPrefix",
    "linkReferences", "nameInLink", "cref", "chapters", "autoEqnLabels", "numberSections",
    # 書式のテンプレートと区切り
    "figureTemplate", "tableTemplate", "listingTemplate", "subfigureTemplate", "subfigureChildTemplate",
    "figPrefixTemplate", "tblPrefixTemplate", "eqnPrefixTemplate", "secPrefixTemplate", "lstPrefixTemplate",
    "refIndexTemplate", "eqnIndexTemplate", "eqnInlineTemplate", "eqnBlockTemplate", "eqnBlockInlineMath",
    "equationNumberTeX", "tableEqns", "ccsDelim", "ccsLabelSep", "ccsTemplate",
    "rangeDelim", "pairDelim", "lastDelim", "refDelim", "chapDelim", "chaptersDepth", "sectionsDepth",
    "figLabels", "tblLabels", "eqnLabels", "secLabels", "lstLabels", "subfigLabels", "subfigGrid",
    "autoSectionLabels", "setLabelAttribute", "listings", "codeBlockCaptions", "adjacentCodeBlockCaptions",
    "secHeaderTemplate", "secHeaderDelim", "secLevelLabels",
}


def _crossref_value_ok(v):
    if isinstance(v, (str, bool, int, float)):
        return True
    return isinstance(v, list) and bool(v) and all(isinstance(x, (str, int, float)) and not isinstance(x, bool) for x in v)


def crossref(profile):
    """crossref (pandoc-crossref の設定の誌ごとの上書き) を {名前: 値} で返す。無い・空・使えないなら None。

    build_docx.py と diff_docx.py が同じ解釈で 2 つ目の --defaults を書くために 1 か所に置く。値は文字列・数・真偽値か、
    文字列のリスト (figPrefix: ["Fig.", "Figs."] のような単数と複数の形) だけを受け付け、それ以外 (null・辞書など) は警告して渡さない。
    知らない名前 (CROSSREF_KEYS に無い) は警告してそのまま渡す。
    """
    sect = profile.get("crossref")
    if sect is None:
        return None
    if not isinstance(sect, dict):
        _warn(f"crossref: {sect!r} は辞書ではないので使いません (figureTitle などの pandoc-crossref の設定を持つブロックで書く)")
        return None
    out = {}
    for key, val in sect.items():
        if not isinstance(key, str) or not key:
            _warn(f"crossref: 名前 {key!r} は使えません。この項目は渡しません")
            continue
        if val is None:
            _warn(f"crossref.{key} の値がありません (null)。この項目は渡しません (空の文字列にするなら \"\" と書く)")
            continue
        if not _crossref_value_ok(val):
            _warn(f"crossref.{key}: {val!r} は文字列・数・真偽値か文字列のリストではないので渡しません")
            continue
        if key not in CROSSREF_KEYS:
            _warn(f"crossref.{key} は本テンプレートの知らない pandoc-crossref の設定です (綴りの誤りなら効きません)。そのまま渡します")
        out[key] = copy.deepcopy(val)
    return out or None


def table_legend_position(profile):
    """tables.legend_position (表の凡例の位置) を 'above' / 'below' で返す。

    above は tables.placement の end / separate と併用できないので止める。提出構成の組み替え (relocate.py) は「題 + 表 + 表の後の凡例」を
    1 組として動かすので、凡例を表の上へ移した docx を組み替えると、題と凡例が本文に取り残されるため。
    """
    tables = profile.get("tables") or {}
    pos = as_choice(tables.get("legend_position"), {"above", "below"}, "below", key="tables.legend_position")
    if pos == "above":
        placement = str(tables.get("placement") or "inline").strip().lower()
        if placement in ("end", "separate"):
            sys.exit(f"エラー: tables.legend_position: above と tables.placement: {placement} は併用できません "
                     "(表を本文から移す組み替えは、凡例が表の後にある前提で題・表・凡例を 1 組として動かすため)。"
                     "どちらかを profile.yaml から外してください")
    return pos


def figures_keep_together(profile):
    """figures.keep_together (図 → 題 → 凡例を段・ページで分けない) を真偽値で返す。"""
    return as_flag((profile.get("figures") or {}).get("keep_together"), "figures.keep_together", default=False)


def figures_separate(profile):
    """figures.separate (提出用で図を本文から外すか) を真偽値で返す。既定 true = 図を分離する。

    false (図を本文に埋め込んだまま提出用にする) は、提出構成の組み替え (relocate.py) を通さないので、組み替えを求めるキー
    (tables.placement の end / separate・figures.legends_section) とは併用できない。黙って効かなくなるのを防ぐため止める。
    """
    figures = profile.get("figures") or {}
    separate = as_flag(figures.get("separate"), "figures.separate", default=True)
    if not separate:
        placement = str((profile.get("tables") or {}).get("placement") or "inline").strip().lower()
        clash = []
        if placement in ("end", "separate"):
            clash.append(f"tables.placement: {placement}")
        if figures.get("legends_section"):
            clash.append(f"figures.legends_section: {figures['legends_section']}")
        if clash:
            sys.exit(f"エラー: figures.separate: false と {' / '.join(clash)} は併用できません "
                     "(図を本文に埋め込んだまま提出用にするときは提出構成の組み替えを行わないので、そのキーが黙って効かなくなるため)。"
                     "図を分離して提出するなら figures.separate を外し、図を埋め込むなら上のキーを profile.yaml から外してください")
    return separate


def equation_style(profile):
    """equations.style (番号つきの別行立て数式の段落スタイルの名前) を返す。未指定なら None。"""
    return _style_name((profile.get("equations") or {}).get("style"), "equations.style")


def bibliography_label_separator(profile):
    """bibliography.label_separator (文献の番号と本文の区切り) を 'space-tab' / 'tab' で返す。

    tab なら後処理が文献の段落の「番号 空白 TAB」の空白を消す (build と diff が同じ解釈で掛けるために 1 か所に置く)。
    """
    return as_choice((profile.get("bibliography") or {}).get("label_separator"), {"space-tab", "tab"}, "space-tab",
                     key="bibliography.label_separator")


def as_number(v, default):
    """`12pt` / `25mm` のような単位つきの値から数値部分を取り出す (未指定は default)。"""
    if v is None:
        return default
    m = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(v))
    return m.group(0) if m else default


def layout_mismatches(profile, reference_docx):
    """profile.yaml の体裁と reference.docx に焼き込まれた実体裁の食い違いを返す。

    戻り値は [(キー, profile の値, reference.docx の実値)]。体裁は
    reference.docx 側に焼き込む設計なので、profile.yaml を編集して make-reference.sh の
    再実行を忘れると古い体裁のまま投稿まで進む (BHI は行間・行番号・ページ番号がいずれも
    規定必須なので規定違反に直結する)。実体側を読んで機械的に突き合わせる。

    数値は丸め差を許容する (font_size は 0.1pt、margins は 0.05mm。0.5mm だと 25mm と 25.4mm を見分けられない)。reference.docx から
    読み取れなかったキーは判定しない (欠落を不一致と報告しない)。

    雑誌が配るテンプレートから作る誌 (reference_base がある) では、体裁はテンプレートが正で焼き込まない。
    profile の体裁キーはテンプレートの値を写した照合用 (テンプレートの改版の検知) なので、**profile に書いたキーだけ**を見る
    (書かなければ照合しない。page_numbers も、書かなければフッタの有無と比べない)。
    余白は辞書形 `{top, bottom, left, right}` でも書ける (非対称の余白。辺ごとに比べる。書いた辺だけ)。
    行番号は reference.docx の**最終の節** (テンプレートでは本文の節) と比べる (read_layout の説明)。
    """
    import patch_reference_docx  # 遅延 import (lxml を要するのはこの経路だけ)

    try:
        actual = patch_reference_docx.read_layout(reference_docx)
    except Exception as exc:                                    # noqa: BLE001
        _warn(f"{reference_docx} の体裁を読めませんでした ({exc})。突合を省略します")
        return []

    template_mode = bool(profile.get("reference_base"))
    tol = {"font_size": 0.1, "margins": 0.05}   # 余白は twip の丸め (0.02mm 未満) だけを許す
    out = []
    for key in LAYOUT_KEYS:
        want, got = profile.get(key), actual.get(key)
        if got is None:
            continue
        if template_mode and want is None:
            continue
        if key == "margins" and isinstance(want, dict):
            for extra in sorted(set(want) - {"top", "bottom", "left", "right"}):
                _warn(f"margins.{extra} は知らない辺です (top / bottom / left / right のどれか)。照合しません")
            sides = actual.get("margins_sides") or {}
            for side in ("top", "bottom", "left", "right"):
                w_num = as_number(want.get(side), None)
                if w_num is None or side not in sides:
                    continue
                if abs(float(w_num) - float(sides[side])) > tol["margins"]:
                    out.append((f"margins.{side}", want.get(side), round(float(sides[side]), 2)))
            continue
        if key == "page_numbers":
            if as_flag(want, key) != bool(got):
                out.append((key, as_flag(want, key), bool(got)))
        elif key in tol:
            w_num = as_number(want, None)
            if w_num is not None and abs(float(w_num) - float(got)) > tol[key]:
                out.append((key, want, round(float(got), 2)))
        else:
            if want is not None and str(want).strip().lower() != str(got).strip().lower():
                out.append((key, want, got))
    # 抄録 (Abstract スタイル) の大きさも本文と同じであること (pandoc の既定は 10pt。古い reference.docx の検出)
    abs_got, w_num = actual.get("abstract_font_size"), as_number(profile.get("font_size"), None)
    if abs_got is not None and w_num is not None and abs(float(w_num) - float(abs_got)) > tol["font_size"]:
        out.append(("font_size (抄録の Abstract スタイル)", profile.get("font_size"), round(float(abs_got), 2)))
    return out


def layout_fix_hint(journal_id, profile):
    """layout_mismatches の食い違いの直し方 (build と validate の警告文の後半) を返す。

    reference.docx を profile から焼き込む誌は作り直せば直る。テンプレートから作る誌 (reference_base) では生成の元が変われば
    build / diff が作り直すので、残る食い違いはテンプレートと profile の値の違い (テンプレートの改版か profile の書き誤り) である。
    """
    if profile.get("reference_base"):
        return (f"テンプレート ({profile.get('reference_base')}) の体裁と profile の値が違います。"
                "テンプレートが改版されたなら、テンプレートの値に合わせて profile.yaml を直してください")
    return f"'bash data/journals/make-reference.sh {journal_id}' で再生成してください"
