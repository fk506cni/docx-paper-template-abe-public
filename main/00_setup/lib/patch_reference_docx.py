#!/usr/bin/env python3
"""patch_reference_docx.py — reference.docx に汎用投稿フォーマットの体裁を焼き込む。

pandoc の既定 reference.docx をベースに、雑誌プロファイルの体裁 (行間・行番号・本文フォント・余白) を
OOXML 直接編集で適用し、差分用の文字スタイル DiffAdd / DiffDel と隠し段落スタイル TextBoxMarker を注入する。
コンテナ内 (docx-paper-template-pandoc; lxml 同梱) で実行する。ホストの Python は使わない。

使い方 (例: _default の reference.docx を作る):
    python3 patch_reference_docx.py base.docx -o reference.docx \
        --line-spacing double --line-numbers continuous \
        --font "Times New Roman" --font-size 12 --margin 25 [--page-numbers]

使い方 (雑誌が配るテンプレートから作る。profile の reference_base):
    python3 patch_reference_docx.py --base ABETemplate.docx -o reference.docx
    → 体裁は焼き込まない (テンプレートが正)。pandoc が使うのに足りないスタイルを名前で引いて別名として足し、
      見出しの番号定義と題のハイフネーションを直し、見本の文章と文書を特定しうる情報を消す (下の「テンプレートから作る」節)

設計上の位置づけ:
- 体裁 (行間/行番号/フォント/余白/ページ番号) は reference.docx 側に持たせ、main.md 本文は雑誌非依存に
  保つ (docs/architecture.md §3)。
- DiffAdd/DiffDel は _default では事前定義するが、雑誌提供テンプレ (これらを持たない) でも差分色が出るよう、
  step03/step04 の後処理が生成 docx の styles.xml へ同じ 2 スタイルを冪等注入する (docs/architecture.md §2.3)。
  本スクリプトの注入ロジックはその後処理と同じ定義を用いる (単一の真実)。
- 冪等: 同名スタイル / pgMar / lnNumType / フッタは一度削除してから付け直すため、複数回適用しても結果は同じ。
"""

import argparse
import os
import posixpath
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

import docx_styles

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": W}

# OPC パッケージ側の名前空間 (フッタのパート追加に使う)
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PKGREL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

XML_NS = "http://www.w3.org/XML/1998/namespace"

FOOTER_PART = "word/footer1.xml"
FOOTER_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"
FOOTER_REL_TYPE = f"{R_NS}/footer"
# word/footer.xml / footer1.xml / footer2.xml ... を拾う (雑誌提供テンプレは複数持ちうる)。
# これ単独ではフッタを取りこぼす。_footer_part_names() が本正規表現に
# 加えて Override / Relationship 由来の名前も集める (パートの撤去だけを本正規表現で判定し、
# Override と Relationship を種類で判定すると、基準が食い違う)。
FOOTER_PART_RE = re.compile(r"^word/footer\d*\.xml$")

# CT_SectPr の子要素の並び (ECMA-376 Part 1)。先頭に EG_HdrFtrReferences (header/footer は
# 相互にどの順でもよい)、続いて EG_SectPrContents、最後に sectPrChange。
# pgSz/pgMar/lnNumType を sectPr の末尾へ付け足すと、
# ベース docx の sectPr に lnNumType より後ろに来る要素 (titlePg / cols / docGrid / pgNumType 等)
# があるときに順序違反になる (実測: footerReference → footnotePr → titlePg → pgSz → pgMar →
# lnNumType)。pandoc は sectPr の子要素を逐語コピーするため違反は全生成 docx へ波及する。
# 本定数で正しい位置へ挿し込み、最後に _check_sectpr_order で検算する。
SECTPR_ORDER = (
    "headerReference", "footerReference",   # EG_HdrFtrReferences (順不同なので同 rank)
    "footnotePr", "endnotePr", "type", "pgSz", "pgMar", "paperSrc", "pgBorders",
    "lnNumType", "pgNumType", "cols", "formProt", "vAlign", "noEndnote", "titlePg",
    "textDirection", "bidi", "rtlGutter", "docGrid", "printerSettings",
    "sectPrChange",
)
# headerReference / footerReference は同 rank (0)、以降は並び順そのものを rank にする
_SECTPR_RANK = {name: (0 if i < 2 else i) for i, name in enumerate(SECTPR_ORDER)}


def w(tag):
    return f"{{{W}}}{tag}"


# 差分文字スタイルの色 (docs/architecture.md §2.0 / §2.3)。後処理 (step03/04) と同一定義にすること。
DIFF_ADD_COLOR = "2E74B5"  # 青
DIFF_DEL_COLOR = "C00000"  # 赤

# 行間 (w:spacing@w:line, lineRule="auto" の 240ths/line)
LINE_VALUES = {"single": "240", "1.5": "360", "double": "480"}

MM_TO_TWIP = 1440.0 / 25.4  # 1mm → twips

# 用紙寸法 (twips)。A4=210×297mm / Letter=8.5×11in
PAPER_SIZES = {"a4": (11906, 16838), "letter": (12240, 15840)}


def _find_or_create(parent, tag, prepend=False):
    """parent 直下に <w:tag> が無ければ作って返す (冪等)。"""
    el = parent.find(w(tag))
    if el is None:
        el = etree.SubElement(parent, w(tag))
        if prepend:
            parent.remove(el)
            parent.insert(0, el)
    return el


def _localname(el):
    """要素のローカル名を返す (コメント / 処理命令なら None)。"""
    return etree.QName(el.tag).localname if isinstance(el.tag, str) else None


def _sectpr_rank(name):
    """CT_SectPr の子要素名から並び順の rank を返す (未知の要素は末尾扱い)。"""
    return _SECTPR_RANK.get(name, len(SECTPR_ORDER))


def _sectpr_insert(sect, tag):
    """sect 直下へ <w:tag> を CT_SectPr の順序位置に挿し込んで返す。"""
    el = etree.Element(w(tag))
    rank = _sectpr_rank(tag)
    pos = len(sect)
    for i, child in enumerate(sect):
        name = _localname(child)
        if name is not None and _sectpr_rank(name) > rank:
            pos = i
            break
    sect.insert(pos, el)
    return el


def _normalize_sectpr_order(sect):
    """sect の子要素を CT_SectPr の並びへ整列する (同 rank 内の相対順は保つ)。

    ベース docx の sectPr がもとから順序違反のこともある (雑誌提供テンプレ / 手編集)。CT_SectPr の
    子要素の順序は規格で決まっているため、規格順へ並べ替えても意味は変わらない。並べ替えで救える
    ものは救い、_check_sectpr_order は最後の事後条件として残す。戻り値は並べ替えたか否か。
    """
    children = list(sect)
    ranks, last = [], -1
    for child in children:
        name = _localname(child)
        if name is not None:
            last = _sectpr_rank(name)
        ranks.append(last)   # コメント等は直前の要素に付き従わせる
    order = sorted(range(len(children)), key=lambda i: (ranks[i], i))
    if order == list(range(len(children))):
        return False
    for i in order:
        sect.append(children[i])   # append は既存ノードを末尾へ移動する
    return True


def _check_sectpr_order(sect, where):
    """sect の子要素が CT_SectPr の順序に沿っているか検算する。

    順序違反の reference.docx を pandoc に渡すと無警告で通り、出力側も同じ違反になって
    全生成 docx へ波及する。「順序は準拠している」を主張で終わらせず、
    ここで機械的に確かめて違反なら止める。
    """
    names = [n for n in (_localname(c) for c in sect) if n is not None]
    ranks = [_sectpr_rank(n) for n in names]
    if ranks != sorted(ranks):
        raise RuntimeError(
            f"{where} の sectPr の要素順が CT_SectPr に反しています: {names}\n"
            "  (ECMA-376 の並びは EG_HdrFtrReferences → footnotePr → endnotePr → type → "
            "pgSz → pgMar → … → lnNumType → pgNumType → cols → … → titlePg → … → docGrid)"
        )


def patch_styles(styles_root, *, font, font_size_pt, line_spacing, inject_diff):
    """docDefaults に本文フォント・サイズ・行間を設定し、差分/マーカースタイルを注入。"""
    # --- docDefaults (rPrDefault / pPrDefault) ---
    doc_defaults = _find_or_create(styles_root, "docDefaults", prepend=True)

    # rPrDefault → rPr → rFonts / sz / szCs
    rpr_default = _find_or_create(doc_defaults, "rPrDefault")
    rpr = _find_or_create(rpr_default, "rPr")
    rfonts = _find_or_create(rpr, "rFonts")
    for attr in ("ascii", "hAnsi", "cs"):
        rfonts.set(w(attr), font)
    # pandoc 既定 reference.docx の docDefaults rFonts はテーマ参照 (asciiTheme 等) を併せ持つ。
    # OOXML (ECMA-376 §17.3.2.26) ではテーマ属性が直接指定を上書きするため、テーマ参照を残すと
    # 本文が theme フォント (Aptos) で解決され Times が効かない。直接指定だけを残す
    # (theme1.xml 側も patch_theme で Times へ書換)。
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        rfonts.attrib.pop(w(attr), None)
    half = str(int(round(font_size_pt * 2)))  # pt → half-points
    _find_or_create(rpr, "sz").set(w("val"), half)
    _find_or_create(rpr, "szCs").set(w("val"), half)

    # pPrDefault → pPr → spacing (行間)
    ppr_default = _find_or_create(doc_defaults, "pPrDefault")
    ppr = _find_or_create(ppr_default, "pPr")
    spacing = _find_or_create(ppr, "spacing")
    spacing.set(w("line"), LINE_VALUES[line_spacing])
    spacing.set(w("lineRule"), "auto")
    # 段落間の余白は 0 にして「行間=規定値」を素直に見せる
    spacing.set(w("before"), "0")
    spacing.set(w("after"), "0")

    # pandoc の既定の Title スタイルは行間を single (line=240) で上書きしている。題が 2 行以上になると
    # 「全体を同じ行間で」(BHI は "double-spaced throughout") から外れるので、Title の行間も本文の行間に
    # 揃える (段落の前後の余白はそのまま)。pPr が無ければ rPr の前に作る (w:style の子の順序)
    for st in styles_root.findall(w("style")):
        if st.get(w("type")) != "paragraph" or st.get(w("styleId")) != "Title":
            continue
        st_ppr = st.find(w("pPr"))
        if st_ppr is None:
            st_ppr = etree.Element(w("pPr"))
            rpr_el = st.find(w("rPr"))
            if rpr_el is not None:
                rpr_el.addprevious(st_ppr)
            else:
                st.append(st_ppr)
        st_sp = _find_or_create(st_ppr, "spacing")
        st_sp.set(w("line"), LINE_VALUES[line_spacing])
        st_sp.set(w("lineRule"), "auto")

    # pandoc の既定の Abstract / AbstractTitle スタイルは文字の大きさを 10pt (sz=20) で上書きしている。
    # 原稿の抄録 (custom-style="Abstract") だけが本文より小さく出ると、「全体を同じ大きさで」(BHI は
    # "12-point type face") から外れるので、本文の大きさに揃える。題 (Title) と見出し (Heading) は本文より
    # 大きいまま残す (見出しを大きくするのは一般的な組み方で、規定の 12-point は本文の文字の大きさと読む)
    for st in styles_root.findall(w("style")):
        if st.get(w("type")) != "paragraph" or st.get(w("styleId")) not in ("Abstract", "AbstractTitle"):
            continue
        st_rpr = _find_or_create(st, "rPr")
        _find_or_create(st_rpr, "sz").set(w("val"), half)
        _find_or_create(st_rpr, "szCs").set(w("val"), half)

    if inject_diff:
        inject_diff_styles(styles_root)
    inject_textbox_marker_style(styles_root)
    inject_metadata_styles(styles_root)


# ---------------------------------------------------------------------
# 題・見出し・抄録の級数と色 (profile の text_styles。省略時は手を加えない)
#
# pandoc 既定 reference.docx は Title 28pt / Heading 1〜3 = 20/16/14pt (テーマ色 accent1 = 青) /
# Abstract 10pt を持つ。docDefaults を 12pt にしてもこれらは各スタイルの sz で上書きされたまま残る。
# BHI の規定は "12-point type face" なので、級数を本文にそろえる誌はこの段で題・見出し・抄録まで
# そろえる (roundtrip の計測は本文の最頻値しか見ないので、ここが崩れていても数字には出ない)。
# ---------------------------------------------------------------------

# 色を外す対象 (題・見出しの段落スタイルと、対応する文字スタイル)
HEADING_STYLE_IDS = frozenset(
    ("Title", "TitleChar", "Subtitle", "SubtitleChar", "TOCHeading")
    + tuple(f"Heading{i}" for i in range(1, 10))
    + tuple(f"Heading{i}Char" for i in range(1, 10))
)
# 級数をそろえると見出しの階層が級数で見分けられなくなるので、強調で見分ける。
# styleId → (太字, 斜体)。Heading 4 以下は pandoc 既定の斜体 (4/6/8) をそのまま残す。
UNIFORM_EMPHASIS = {
    "Title": (True, False), "TitleChar": (True, False),
    "Heading1": (True, False), "Heading1Char": (True, False),
    "Heading2": (True, True), "Heading2Char": (True, True),
    "Heading3": (False, True), "Heading3Char": (False, True),
}
# CT_RPr (EG_RPrBase) の子要素の並びのうち、強調の挿入位置を決めるのに要る先頭部分
_RPR_HEAD = ("rStyle", "rFonts", "b", "bCs", "i", "iCs")


def _set_rpr_toggle(rpr, tag, on=True):
    """rPr に <w:tag/> (on) / <w:tag w:val="0"/> (off) を順序制約どおりの位置で置く。

    on=True で既にあれば w:val を外してオンにする。on=False は要素が無いときだけ足す
    (継承した強調の打ち消し用。スタイル自身の明示値は尊重する)。
    """
    el = rpr.find(w(tag))
    if el is not None:
        if on:
            el.attrib.pop(w("val"), None)
        return
    el = etree.Element(w(tag))
    if not on:
        el.set(w("val"), "0")
    rank = _RPR_HEAD.index(tag)
    pos = 0
    for i, child in enumerate(rpr):
        name = _localname(child)
        if name in _RPR_HEAD and _RPR_HEAD.index(name) < rank:
            pos = i + 1
    rpr.insert(pos, el)


def normalize_text_styles(styles_root, *, font_size_pt, uniform_size, heading_color):
    """題・見出し・抄録などの級数を本文にそろえ、題・見出しの色を黒にする。

    uniform_size: 級数 (sz / szCs) を明示しているスタイルをすべて本文の級数にする
                  (Title / Subtitle / Author / Date / AbstractTitle / Abstract / Heading 1〜3 と
                  その文字スタイル / VerbatimChar)。あわせて UNIFORM_EMPHASIS で階層を付ける。
    heading_color: "black" なら HEADING_STYLE_IDS の w:color を外す (= 自動色。テーマの青を消す)。
                   "keep" なら触らない。リンク (Hyperlink) と差分 (DiffAdd / DiffDel) の色は対象外。
    戻り値は変更したスタイルの一覧 (表示用)。
    """
    half = str(int(round(font_size_pt * 2)))
    changed = []
    for st in styles_root.findall(w("style")):
        sid = st.get(w("styleId"))
        rpr = st.find(w("rPr"))
        if rpr is None:
            continue
        notes = []
        if uniform_size:
            for tag in ("sz", "szCs"):
                el = rpr.find(w(tag))
                if el is not None and el.get(w("val")) != half:
                    if tag == "sz":
                        notes.append(f"{int(el.get(w('val'))) / 2:g}pt→{font_size_pt:g}pt")
                    el.set(w("val"), half)
            bold, italic = UNIFORM_EMPHASIS.get(sid, (False, False))
            if bold:
                _set_rpr_toggle(rpr, "b")
                _set_rpr_toggle(rpr, "bCs")
                notes.append("太字")
            if italic:
                _set_rpr_toggle(rpr, "i")
                _set_rpr_toggle(rpr, "iCs")
                notes.append("斜体")
        if heading_color == "black" and sid in HEADING_STYLE_IDS:
            color = rpr.find(w("color"))
            if color is not None:
                rpr.remove(color)
                notes.append("色を外す")
        if notes:
            changed.append(f"{sid}({', '.join(notes)})")

    # 強調を付けたスタイルを basedOn にしている他のスタイルは、その強調を継承してしまう
    # (実測: Author / Date / Subtitle は Title を basedOn に持つため、題を太字にすると著者行まで
    #  太字になった)。強調の対象でない子には、継承した太字・斜体を明示的に打ち消す。
    if uniform_size:
        for st in styles_root.findall(w("style")):
            sid = st.get(w("styleId"))
            based = st.find(w("basedOn"))
            parent = based.get(w("val")) if based is not None else None
            if sid in UNIFORM_EMPHASIS or parent not in UNIFORM_EMPHASIS:
                continue
            pbold, pitalic = UNIFORM_EMPHASIS[parent]
            rpr = st.find(w("rPr"))
            if rpr is None:
                rpr = etree.SubElement(st, w("rPr"))
            notes = []
            if pbold and rpr.find(w("b")) is None:
                _set_rpr_toggle(rpr, "b", on=False)
                _set_rpr_toggle(rpr, "bCs", on=False)
                notes.append("継承した太字を打ち消す")
            if pitalic and rpr.find(w("i")) is None:
                _set_rpr_toggle(rpr, "i", on=False)
                _set_rpr_toggle(rpr, "iCs", on=False)
                notes.append("継承した斜体を打ち消す")
            if notes:
                changed.append(f"{sid}({', '.join(notes)})")
    return changed


def uniform_line_spacing(styles_root):
    """段落スタイルが個別に持つ行送り (w:spacing の w:line / w:lineRule) を外す。

    外したスタイルは docDefaults の行送り (BHI はダブル = 480) を継承する。段落前後の空き
    (w:before / w:after) は行送りではないので残す。
    pandoc 既定の reference.docx は `Title` に `w:line="240"` (シングル) を持ち、`Author` /
    `Date` / `Subtitle` はそれを basedOn で継承する。`patch_styles()` は Title の行送りを本文の
    行送りに書き換えるが、この関数は Title に限らず個別の行送りをすべて外す (`TOCHeading` なども
    docDefaults を継ぐ)。BHI の規定 "typed double-spaced throughout" を、スタイルごとの指定に
    頼らずに満たすため。戻り値は変更したスタイルの一覧 (表示用)。
    """
    changed = []
    for st in styles_root.findall(w("style")):
        if st.get(w("type")) != "paragraph":
            continue
        sp = st.find(f"{w('pPr')}/{w('spacing')}")
        if sp is None or sp.get(w("line")) is None:
            continue
        old = sp.get(w("line"))
        for attr in ("line", "lineRule"):
            sp.attrib.pop(w(attr), None)
        if not sp.attrib:
            sp.getparent().remove(sp)
        changed.append(f"{st.get(w('styleId'))}(行送り {old}→継承)")
    return changed


def _remove_styles_by_id(styles_root, style_ids):
    for st in styles_root.findall(w("style")):
        if st.get(w("styleId")) in style_ids:
            styles_root.remove(st)


def inject_diff_styles(styles_root):
    """DiffAdd (青) / DiffDel (赤+取消線) 文字スタイルを冪等注入する。

    step03/step04 の後処理が任意 reference.docx へ注入するのと同じ定義 (docs/architecture.md §2.3)。
    pandoc は custom-style="DiffAdd" を <w:rStyle w:val="...styleId..."/> へ写像し、styleId は w:name で照合する。
    """
    _remove_styles_by_id(styles_root, {"DiffAdd", "DiffDel"})

    add = etree.SubElement(styles_root, w("style"))
    add.set(w("type"), "character")
    add.set(w("customStyle"), "1")
    add.set(w("styleId"), "DiffAdd")
    etree.SubElement(add, w("name")).set(w("val"), "DiffAdd")
    add_rpr = etree.SubElement(add, w("rPr"))
    etree.SubElement(add_rpr, w("color")).set(w("val"), DIFF_ADD_COLOR)

    dele = etree.SubElement(styles_root, w("style"))
    dele.set(w("type"), "character")
    dele.set(w("customStyle"), "1")
    dele.set(w("styleId"), "DiffDel")
    etree.SubElement(dele, w("name")).set(w("val"), "DiffDel")
    del_rpr = etree.SubElement(dele, w("rPr"))
    etree.SubElement(del_rpr, w("color")).set(w("val"), DIFF_DEL_COLOR)
    etree.SubElement(del_rpr, w("strike"))


def inject_textbox_marker_style(styles_root):
    """TextBoxMarker 段落スタイル (隠し) を冪等注入。generic-style.lua の境界マーカー用。"""
    _remove_styles_by_id(styles_root, {"TextBoxMarker"})
    st = etree.SubElement(styles_root, w("style"))
    st.set(w("type"), "paragraph")
    st.set(w("customStyle"), "1")
    st.set(w("styleId"), "TextBoxMarker")
    etree.SubElement(st, w("name")).set(w("val"), "TextBoxMarker")
    rpr = etree.SubElement(st, w("rPr"))
    etree.SubElement(rpr, w("vanish"))


def inject_metadata_styles(styles_root):
    """custom-style Div 用の Affiliation / Keywords / Corresponding / Legend 段落スタイルを冪等注入する。

    pandoc 既定 reference.docx は Title/Author/Abstract を持つが Affiliation/Keywords を持たず、
    定義が無いと pandoc が空スタイルを自動生成する。テンプレ提供物として明示定義しておく。
    _default は投稿フォーマット (素の体裁) のため、体裁は本文同等とし
    (左寄せ・本文フォント/サイズ/行間を Normal から継承)、独自の見た目は与えない。スタイル定義を
    残すのは構造保持差分 (step03 diff) がこれらを温存・差分化するため。

    Corresponding (連絡著者ブロック: 氏名・住所全文・電話・E-mail を 1 名分) は必須にしてある。
    validate.py の連絡著者検査は
    `custom-style="Corresponding"` Div を検出対象にするため、スタイル定義が無いと検査そのものが
    成立しない。誌に依存しない構造要素なので _default にも入れる (体裁は他のメタ Div と同じく素)。

    Legend (図表の凡例ブロック): BHI は図表の【題】(15 語以内) と
    【凡例】(300 語以内) を別物として要求するが、pandoc のキャプションは図にも表にも 1 本しか
    付けられない。そこで「題=キャプション / 凡例=直後の custom-style='Legend' Div」を原稿記法に
    定めた (執筆規約「図表の題と凡例の書き分け」)。docx 側にこの段落スタイルが
    あって初めて、relocate.py の Figure Legends 集約が凡例段落を pStyle で特定でき、validate.py の
    語数検査が題と凡例を別々に数えられる。pandoc の Caption 系 (ImageCaption / TableCaption /
    CaptionedFigure / Caption) とは styleId が衝突しないことを確認済み。
    凡例は誌に依存しない構造要素なので _default にも入れる (体裁は他のメタ Div と同じく素)。
    """
    _remove_styles_by_id(styles_root, {"Affiliation", "Keywords", "Corresponding", "Legend"})
    for style_id in ("Affiliation", "Keywords", "Corresponding", "Legend"):
        st = etree.SubElement(styles_root, w("style"))
        st.set(w("type"), "paragraph")
        st.set(w("customStyle"), "1")
        st.set(w("styleId"), style_id)
        etree.SubElement(st, w("name")).set(w("val"), style_id)
        etree.SubElement(st, w("basedOn")).set(w("val"), "Normal")
        etree.SubElement(st, w("next")).set(w("val"), "BodyText")
        etree.SubElement(st, w("qFormat"))


# ---------------------------------------------------------------------
# ページ番号フッタ (profile の page_numbers: true で有効化)
#
# 誌によっては行番号とページ番号の【両方】を要求する (例: "Line and page numbers must be indicated")。
# 行番号は sectPr の lnNumType で足りるが、ページ番号は
# フッタのパート自体が要る。pandoc 3.6.4 は reference.docx の word/footer1.xml を出力へ
# 引き継ぎ、Override と Relationship を作り直し rId も振り直す (実測)。
# ---------------------------------------------------------------------


def _footer_rpr(parent, font, half_pt):
    """フッタ用の rPr (本文フォントとサイズ) を parent の末尾に足す。

    rFonts → sz → szCs の順は CT_ParaRPr / EG_RPrBase の順序制約に従う。
    本関数は行間を触らない (行間の設定と、なぜ single に上書きするかの説明は
    build_footer_part の w:spacing 側にある)。
    """
    rpr = etree.SubElement(parent, w("rPr"))
    rfonts = etree.SubElement(rpr, w("rFonts"))
    for attr in ("ascii", "hAnsi", "cs"):
        rfonts.set(w(attr), font)
    etree.SubElement(rpr, w("sz")).set(w("val"), half_pt)
    etree.SubElement(rpr, w("szCs")).set(w("val"), half_pt)
    return rpr


def build_footer_part(font, font_size_pt):
    """中央揃えの PAGE フィールドだけを持つ word/footer1.xml を組み立てて bytes で返す。

    要素順は CT_PPrBase 準拠 (suppressLineNumbers → spacing → jc → rPr)。PAGE フィールドは
    begin → instrText → separate → 結果 → end の 5 run で書く (結果 run は Word が再計算する)。

    行間を single に上書きしているのは、フッタ段落も docDefaults を継承するためである。
    上書きしないと本文のダブルスペースがそのまま効いてフッタが 2 行分の高さになる
    (行間は本関数の w:spacing で設定する。_footer_rpr は行間を触らない)。

    段落に w:suppressLineNumbers を入れて行番号の対象から明示的に外す。
    Word の行番号は本文のみが対象とされるが、LibreOffice はフッタ段落にも行番号を振ることが
    実測されている (左余白に 1、中央にページ番号が並ぶ)。「Word では出ないはず」という
    推測に頼らず、本要素で実装によらず抑止する。
    """
    half = str(int(round(font_size_pt * 2)))

    ftr = etree.Element(w("ftr"), nsmap=NSMAP)
    para = etree.SubElement(ftr, w("p"))

    ppr = etree.SubElement(para, w("pPr"))
    etree.SubElement(ppr, w("suppressLineNumbers"))
    spacing = etree.SubElement(ppr, w("spacing"))
    spacing.set(w("before"), "0")
    spacing.set(w("after"), "0")
    spacing.set(w("line"), LINE_VALUES["single"])
    spacing.set(w("lineRule"), "auto")
    etree.SubElement(ppr, w("jc")).set(w("val"), "center")
    _footer_rpr(ppr, font, half)

    def run():
        r = etree.SubElement(para, w("r"))
        _footer_rpr(r, font, half)
        return r

    etree.SubElement(run(), w("fldChar")).set(w("fldCharType"), "begin")
    instr = etree.SubElement(run(), w("instrText"))
    instr.set(f"{{{XML_NS}}}space", "preserve")
    instr.text = " PAGE "
    etree.SubElement(run(), w("fldChar")).set(w("fldCharType"), "separate")
    etree.SubElement(run(), w("t")).text = "1"
    etree.SubElement(run(), w("fldChar")).set(w("fldCharType"), "end")

    return etree.tostring(ftr, xml_declaration=True, encoding="UTF-8", standalone=True)


def _footer_part_names(parts, ct_root, rels_root):
    """既存フッタのパート名を 3 系統 (Override / Relationship / 名前) から集める。

    パートの撤去だけを名前の正規表現 FOOTER_PART_RE で判定し、
    Override と Relationship を種類 (ContentType / Type) で判定すると、判定基準が食い違う。
    word/footerFirst.xml のように命名規則から外れたフッタでは、パートが残るのに Override と
    Relationship だけが消え、種類宣言と実体が合わない孤立パートになる (実測。
    警告にも出ない)。3 系統の和集合を撤去対象にして基準を揃える。
    """
    names = set()
    for override in ct_root.findall(f"{{{CT_NS}}}Override"):
        if override.get("ContentType") == FOOTER_CT:
            names.add((override.get("PartName") or "").lstrip("/"))
    for rel in rels_root.findall(f"{{{PKGREL_NS}}}Relationship"):
        if rel.get("Type") == FOOTER_REL_TYPE:
            target = (rel.get("Target") or "").lstrip("/")
            if target:
                names.add(target if target.startswith("word/") else f"word/{target}")
    names |= {n for n in parts if FOOTER_PART_RE.match(n)}
    return {n for n in names if n}


def install_page_number_footer(parts, parser, *, font, font_size_pt):
    """word/footer1.xml + Content_Types Override + Relationship を冪等に追加し rId を返す。

    冪等性は本スクリプトの既存 idiom (「一旦削除してから付け直す」) に揃える。既存のフッタ
    パート・Override・Relationship をすべて撤去してから 1 枚だけ入れ直すため、複数回適用しても
    結果は同じになる。雑誌提供テンプレが独自のフッタを持っていた場合は置き換わるので警告する
    (--page-numbers はオプトインであり、テンプレのフッタを活かすなら渡さない運用になる)。

    警告は「撤去したフッタが本スクリプトの生成物と違う」ときだけ出す。
    撤去したフッタが自分で入れた word/footer1.xml でも同じ警告を出すと、冪等性を
    確認する再適用で毎回「既存のフッタを置き換えます」が出る。重大な場面 (テンプレの
    フッタを壊した) の警告が無害な場面と同じ文面になると読み飛ばされる。
    """
    ct_root = etree.fromstring(parts["[Content_Types].xml"], parser)
    rels_name = "word/_rels/document.xml.rels"
    if rels_name not in parts:
        raise RuntimeError(f"{rels_name} が無いためフッタを関連付けできません (壊れた docx?)")
    rels_root = etree.fromstring(parts[rels_name], parser)

    new_footer = build_footer_part(font, font_size_pt)
    removed = sorted(_footer_part_names(parts, ct_root, rels_root))
    # 本スクリプトが前回入れたものと内容が違うフッタ = テンプレ由来。これだけを警告する
    foreign = [n for n in removed if n in parts and parts[n] != new_footer]
    for name in removed:
        parts.pop(name, None)
        parts.pop(f"word/_rels/{Path(name).name}.rels", None)
    if foreign:
        print(f"  警告: テンプレ由来のフッタを置き換えます: {', '.join(foreign)}")

    # --- [Content_Types].xml の Override ---
    for override in ct_root.findall(f"{{{CT_NS}}}Override"):
        if override.get("ContentType") == FOOTER_CT:
            ct_root.remove(override)
    override = etree.SubElement(ct_root, f"{{{CT_NS}}}Override")
    override.set("PartName", f"/{FOOTER_PART}")
    override.set("ContentType", FOOTER_CT)
    parts["[Content_Types].xml"] = etree.tostring(
        ct_root, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    # --- word/_rels/document.xml.rels の Relationship (未使用の rId を採る) ---
    used = set()
    for rel in rels_root.findall(f"{{{PKGREL_NS}}}Relationship"):
        if rel.get("Type") == FOOTER_REL_TYPE:
            rels_root.remove(rel)
        else:
            used.add(rel.get("Id") or "")
    nums = [int(m.group(1)) for m in (re.fullmatch(r"rId(\d+)", i) for i in used) if m]
    rid = f"rId{max(nums, default=0) + 1}"
    rel = etree.SubElement(rels_root, f"{{{PKGREL_NS}}}Relationship")
    rel.set("Id", rid)
    rel.set("Type", FOOTER_REL_TYPE)
    rel.set("Target", Path(FOOTER_PART).name)
    parts[rels_name] = etree.tostring(
        rels_root, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    # --- パート本体 ---
    parts[FOOTER_PART] = new_footer
    return rid


# drawingml (テーマ) 名前空間
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _a(tag):
    return f"{{{A_NS}}}{tag}"


def patch_theme(theme_root, font):
    """テーマの major/minor フォント (latin) を指定フォントへ書き換える (冪等)。

    pandoc 既定テーマは latin=Aptos / Aptos Display。Title・Heading 系スタイルは
    asciiTheme="majorHAnsi" 等のテーマ参照のみを持つため、テーマ側を直さないと Times にならない
    本文 docDefaults はテーマ参照を除去済みだが、テーマも揃えて二重に担保する。
    """
    fs = theme_root.find(f".//{_a('fontScheme')}")
    if fs is None:
        return False
    changed = False
    for slot in ("majorFont", "minorFont"):
        fnt = fs.find(_a(slot))
        if fnt is None:
            continue
        latin = fnt.find(_a("latin"))
        if latin is not None:
            latin.set("typeface", font)
            latin.attrib.pop("panose", None)   # Aptos の panose は Times と不一致なので除去
            changed = True
    return changed


def patch_document(document_root, *, margin_mm, line_numbers, paper, footer_rid=None):
    """本文 sectPr に用紙寸法 (pgSz)・余白 (pgMar)・行番号 (lnNumType) を設定する (冪等)。

    要素順は CT_SectPr 準拠で footerReference → footnotePr → pgSz → pgMar → lnNumType になるよう、
    既存の pgSz/pgMar/lnNumType を一旦除去してから SECTPR_ORDER の位置へ挿し直す
    最後に _check_sectpr_order で順序を検算する。

    footer_rid が与えられたとき (--page-numbers) だけ footerReference を貼り直す。pandoc は
    sectPr の子要素を逐語コピーするため、順序違反の reference.docx を渡すと出力側も同じ順序違反に
    なり全生成 docx へ波及する。footerReference は CT_SectPr の EG_HdrFtrReferences に属し
    footnotePr より前なので sectPr の先頭へ入れる。
    footer_rid が None のときは既存 footerReference に触らない (雑誌提供テンプレのフッタを壊さない)。

    footerReference は**文書内のすべての sectPr** から撤去する。
    docx では最後の節以外の設定が段落内の sectPr (`w:p/w:pPr/w:sectPr`) に入るため、表紙と本文で
    フッタを分けているテンプレはこの形になる。body 直下の sectPr しか掃除しないと、
    install_page_number_footer がフッタの関係定義を全撤去した後に段落内 sectPr の footerReference
    だけが残り、**消えた rId を指す壊れた docx** ができる (実測。適用前は開けたのに
    適用後は LibreOffice が読み込みを拒否した)。入出力を同じパスにすると .tmp 退避も消えるため
    テンプレ本体を失う経路でもある。
    """
    body = document_root.find(w("body"))
    if body is None:
        raise RuntimeError("word/document.xml に <w:body> が無い")
    sect = body.find(w("sectPr"))
    if sect is None:
        sect = etree.SubElement(body, w("sectPr"))

    # 段落内 sectPr (= 最後の節より前の節) の一覧。体裁の焼き込みは本文 sectPr にしか効かない
    inner_sects = [s for s in document_root.iter(w("sectPr")) if s is not sect]

    # ベースがもとから順序違反のこともあるので、まず規格順へ整列する
    for target in [sect] + inner_sects:
        if _normalize_sectpr_order(target):
            print("  注: sectPr の要素順を CT_SectPr の並びへ整列しました")

    for tag in ("pgSz", "pgMar", "lnNumType"):
        for old in sect.findall(w(tag)):
            sect.remove(old)

    # --- フッタ参照 (footerReference) --- default 以外 (first/even) も、段落内 sectPr の分も撤去する
    # (install_page_number_footer がフッタのパートと関係定義を 1 枚に置き換えているため、参照だけ
    #  残ると存在しない rId を指す)
    if footer_rid is not None:
        for target in [sect] + inner_sects:
            for old in target.findall(w("footerReference")):
                target.remove(old)
        ref = _sectpr_insert(sect, "footerReference")
        ref.set(w("type"), "default")
        ref.set(f"{{{R_NS}}}id", footer_rid)
        if inner_sects:
            print(f"  警告: 段落内 sectPr が {len(inner_sects)} 個あります。"
                  "体裁 (用紙/余白/行番号) の焼き込みは最後の節にしか効きません")

    # --- 用紙寸法 (pgSz) --- A4/Letter を明示し環境依存 (用紙未指定) を排除
    pw, ph = PAPER_SIZES[paper]
    pgsz = _sectpr_insert(sect, "pgSz")
    pgsz.set(w("w"), str(pw))
    pgsz.set(w("h"), str(ph))

    # --- 余白 (pgMar) ---
    twip = int(round(margin_mm * MM_TO_TWIP))
    # ヘッダ/フッタの用紙端からの距離。708 twips (約 12.5mm) 固定にすると、余白が 12.5mm を
    # 下回る誌ではページ番号が本文領域に食い込む
    # (実測: --margin 10 で w:bottom=567 < w:footer=708)。本文余白の半分で上限を掛けて必ず内側に収める
    # (--margin 25 では 1417//2 = 708 で、上限の 708 と同じ値になる)。
    hf = min(708, max(0, twip // 2))
    if hf != 708:
        print(f"  注: 余白 {margin_mm}mm に合わせてヘッダ/フッタ余白を {hf} twips へ縮めました")
    pgmar = _sectpr_insert(sect, "pgMar")
    for side in ("top", "right", "bottom", "left"):
        pgmar.set(w(side), str(twip))
    pgmar.set(w("header"), str(hf))
    pgmar.set(w("footer"), str(hf))
    pgmar.set(w("gutter"), "0")

    # --- 行番号 (lnNumType) ---
    #
    # w:start は **"0"** にする (Word 実機で確かめた)。
    # Word はこの属性を「1 行目に振る番号」ではなく「**最初の行の 1 つ前の番号**」として扱う。
    # w:start="1" では原稿の 1 行目 (タイトル行) に番号が付かず、行番号が 2 から始まる
    # (規定 "Line and page numbers must be indicated." は満たすが、査読者が line 1 を指せない)。
    #
    # **机上では決められない挙動なので実機で比べた** (roundtrip = Windows の Word COM 変換)。
    # 同じ原稿を 2 通りの reference.docx でビルドし、Windows の
    # Word COM が返した PDF の左余白の数字を読んだ:
    #     w:start="1" → 2〜164 (163 個・欠番なし)
    #     w:start="0" → 1〜163 (163 個・欠番なし)
    # 番号の個数は同じで開始値だけが 1 ずれる = **"0 から始まる" のではなく "1 行目が 1 になる"**。
    # 雑誌プロファイルの reference.docx は `bash data/journals/make-reference.sh <id>` で
    # 作り直せば、この値で焼き込まれる。
    if line_numbers != "none":
        ln = _sectpr_insert(sect, "lnNumType")
        ln.set(w("countBy"), "1")
        ln.set(w("start"), "0")
        ln.set(w("restart"), "continuous" if line_numbers == "continuous" else "newPage")

    _check_sectpr_order(sect, "word/document.xml (本文)")


def read_layout(docx_path):
    """reference.docx に【実際に焼き込まれている】体裁を profile.yaml と同じキーで読み出す。

    体裁は profile.yaml (意図) と reference.docx (実体) の二重管理になる。
    ずれても誰も気づけないため、実体側を読み出して突き合わせられるようにする。読み出しを
    書き込みと同じモジュールに置くのは、焼き込む値と読み出す値の定義 (LINE_VALUES / PAPER_SIZES /
    MM_TO_TWIP / FOOTER_PART_RE) を 1 箇所に保つためである。

    返す dict のキーは profile.yaml と同名 (line_spacing / line_numbers / page_numbers / font /
    font_size / margins / paper_size)。読み取れなかったキーは None にする (欠落と不一致を
    呼び出し側が区別できるようにする)。
    ほかに abstract_font_size (Abstract スタイルの文字の大きさ。本文の font_size と比べる) と、
    margins_sides (四辺の余白 {top, bottom, left, right} mm。profile の margins を辺ごとに書く誌の照合用) を返す。

    節が 2 つ以上ある雛形 (学会テンプレートから作った reference.docx) では、用紙・余白・行番号は**最終の節**
    (w:body 直下の sectPr) から読む。テンプレートの最終の節は本文の節 (ABE なら 2 段組・行番号つき) である
    (pandoc が出力に写すのは最初の節だが、本文の節を組み立てるのは後処理の役目)。
    文字の大きさは docDefaults に無ければ既定の段落スタイル (Normal) の値を読む (学会テンプレートは Normal に持つ)。
    """
    layout = dict.fromkeys(
        ("line_spacing", "line_numbers", "page_numbers", "font", "font_size",
         "margins", "paper_size", "abstract_font_size", "margins_sides"))
    with zipfile.ZipFile(docx_path, "r") as zin:
        names = set(zin.namelist())
        styles = etree.fromstring(zin.read("word/styles.xml")) if "word/styles.xml" in names else None
        doc = etree.fromstring(zin.read("word/document.xml")) if "word/document.xml" in names else None
        ct = zin.read("[Content_Types].xml").decode("utf-8", "ignore") if "[Content_Types].xml" in names else ""

    # --- フッタ (ページ番号) --- パートの実在と Override の両方を見る
    layout["page_numbers"] = bool(
        any(FOOTER_PART_RE.match(n) for n in names) or FOOTER_CT in ct)

    if styles is not None:
        defaults = styles.find(w("docDefaults"))
        if defaults is not None:
            ppr = defaults.find(f"{w('pPrDefault')}/{w('pPr')}")
            spacing = ppr.find(w("spacing")) if ppr is not None else None
            if spacing is not None:
                line = spacing.get(w("line"))
                rev = {v: k for k, v in LINE_VALUES.items()}
                layout["line_spacing"] = rev.get(line, line)
            rpr = defaults.find(f"{w('rPrDefault')}/{w('rPr')}")
            if rpr is not None:
                rfonts = rpr.find(w("rFonts"))
                if rfonts is not None:
                    layout["font"] = rfonts.get(w("ascii"))
                sz = rpr.find(w("sz"))
                if sz is not None and (sz.get(w("val")) or "").isdigit():
                    layout["font_size"] = int(sz.get(w("val"))) / 2.0  # half-point → pt
        if layout["font_size"] is None:
            normal = docx_styles.default_style(styles)
            sz = normal.find(f"{w('rPr')}/{w('sz')}") if normal is not None else None
            if sz is not None and (sz.get(w("val")) or "").isdigit():
                layout["font_size"] = int(sz.get(w("val"))) / 2.0
        for st in styles.findall(w("style")):
            if st.get(w("styleId")) == "Abstract":
                sz = st.find(f"{w('rPr')}/{w('sz')}")
                if sz is not None and (sz.get(w("val")) or "").isdigit():
                    layout["abstract_font_size"] = int(sz.get(w("val"))) / 2.0

    if doc is not None:
        body = doc.find(w("body"))
        sect = body.find(w("sectPr")) if body is not None else None
        if sect is not None:
            pgsz = sect.find(w("pgSz"))
            if pgsz is not None:
                dims = (pgsz.get(w("w")), pgsz.get(w("h")))
                for name, (pw, ph) in PAPER_SIZES.items():
                    if dims == (str(pw), str(ph)):
                        layout["paper_size"] = name
                        break
            pgmar = sect.find(w("pgMar"))
            if pgmar is not None and (pgmar.get(w("top")) or "").isdigit():
                layout["margins"] = int(pgmar.get(w("top"))) / MM_TO_TWIP
            if pgmar is not None:
                sides = {side: int(pgmar.get(w(side))) / MM_TO_TWIP
                         for side in ("top", "bottom", "left", "right")
                         if (pgmar.get(w(side)) or "").lstrip("-").isdigit()}
                layout["margins_sides"] = sides or None
            ln = sect.find(w("lnNumType"))
            layout["line_numbers"] = (
                "none" if ln is None
                else ("continuous" if ln.get(w("restart")) == "continuous" else "per-page"))
    return layout


def check_relationships(document_root, rels_bytes):
    """document.xml が参照する rId が document.xml.rels に実在するか検算する。

    宙に浮いた参照 (関係定義が無い rId) を含む docx は Word / LibreOffice のいずれも開けない。
    壊れたファイルを黙って書き出さないための最後の関門として、書き出し前に必ず通す。
    """
    rels_root = etree.fromstring(rels_bytes)
    defined = {r.get("Id") for r in rels_root.findall(f"{{{PKGREL_NS}}}Relationship")}
    missing = set()
    for el in document_root.iter():
        if not isinstance(el.tag, str):
            continue
        for name, value in el.attrib.items():
            if name.startswith(f"{{{R_NS}}}") and value and value not in defined:
                missing.add((_localname(el), value))
    if missing:
        detail = ", ".join(f"{tag}→{rid}" for tag, rid in sorted(missing))
        raise RuntimeError(
            "word/document.xml が関係定義に存在しない rId を参照しています "
            f"(壊れた docx になるため中止): {detail}")


# =====================================================================
# 雑誌が配るテンプレートから作る (--base。profile の reference_base)
#
# 学会テンプレート (ABE の ABETemplate.docx) をそのまま pandoc の --reference-doc に渡すと、
# (1) pandoc 固有のスタイル (First Paragraph / Image Caption / Bibliography / Hyperlink / 表の Table など) が
#     テンプレートに無いので、出力の pStyle が未定義の ID を指して Normal で描かれる。custom-style (Abstract / Keywords) は
#     pandoc が basedOn="BodyText" で自動定義するが、テンプレートの Body Text の ID は a0 なので基が無く、Word は 10 pt で描く
#     (docs/journal-abe.md §11.1)
# (2) 見出しの番号定義の小節に lvlRestart w:val="0" (= 戻さない) があり、Word では「3.」の下が「3.5」になる
# (3) settings.xml (文書の補助ツールが書いた docVars・文書 ID・編集履歴の rsid) がそのまま全出力に移る。テンプレート自体の core.xml には
#     最終更新者の個人名がある (§8.4)
# (改版で増えうる変更履歴 (作成者名)・コメント・people.xml・独自のプロパティ・文書の保護・参照されない画像も
#  外し、残すパートは許可リスト (KEEP_PART_RE) にし、最後に作成者などの属性が残っていないことを確かめる。ver.3 にはどれも無い)
# ので、テンプレートを正としたまま、足りないものだけを足し、要らないものだけを消す。**体裁 (書体・寸法・行間・余白・
# 行番号・ページ番号) は焼き込まない** — profile の体裁キーは build / validate がテンプレートとの照合にだけ使う
# (journal_profile.layout_mismatches)。
# 本文 (document.xml) は見本の文章 (学会の著作物) を消し、節の骨組み (改ページの段落・節の sectPr を持つ段落・最終の sectPr)
# だけを残す。pandoc は雛形の本文で最初に現れる sectPr を出力に写すので、最終の sectPr だけにすると本文の節
# (2 段組・行番号) が写って柱とページ番号が消える。
# スタイルは ID を決め打ちせず名前で引く (docx_styles)。テンプレートの ID は和文 Word の自動 ID (a / a0 / ae …) のため。
# 手本は Word 実機で確かめた形 (docs/journal-abe.md §11.3)。
# =====================================================================

W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
EP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"


class TemplateError(RuntimeError):
    """テンプレートが読めない・想定の形でない (改版を含む) ときに止めるための例外。"""


# pandoc が出力に書くのにテンプレートに無いことがあるスタイルの別名。
# (種類, 足す ID, 名前, 基にするスタイルの名前の候補 (テンプレートにある最初のものを使う), next の名前, 足す pPr / rPr)
# - **テンプレートに同じ名前のスタイルがあれば足さない** (大文字と小文字を区別しない。pandoc も名前で引く)。
# - 足す ID は pandoc の既定の ID にそろえる。後処理 (relocate.py の ImageCaption / TableCaption / Legend など) が
#   ID で探すため。テンプレートに同じ ID の別のスタイルがあれば止まる。
# - 上から順に足すので、後ろの別名は前で足したものを基にできる (テンプレートに Caption が無くても Image Caption が作れる)。
# - 書式は基のスタイルから継承し、足すのは段落の流れ (図と題を離さない keepNext・図の中央揃え) と等幅の書体と、
#   凡例 (題のスタイルを基にする) の太字を外す指定だけ。
#   最初の 10 種 (First Paragraph 〜 Keywords の印のもの) は Word 実機で確かめた定義 (docs/journal-abe.md §11.3) と同じ
TEMPLATE_ALIASES = (
    # 雛形がふつう持つスタイル。無いテンプレートのための受け皿 (ABE のテンプレートは持っているので足さない)。
    # 足したら警告する (TEMPLATE_EXPECTED_STYLES。Author / Affiliation も同じ扱い)
    ("paragraph", "BodyText", "Body Text", ("Normal",), None, ""),
    ("paragraph", "Title", "Title", ("Normal",), None, ""),
    ("paragraph", "Subtitle", "Subtitle", ("Title",), None, ""),
    ("paragraph", "Caption", "Caption", ("Normal",), None, ""),
    ("paragraph", "FootnoteText", "Footnote Text", ("Normal",), None, ""),
    ("character", "FootnoteReference", "Footnote Reference", ("Default Paragraph Font",), None,
     '<w:rPr><w:vertAlign w:val="superscript"/></w:rPr>'),
    # pandoc 固有 (§11.3 の 10 種を含む)
    ("paragraph", "FirstParagraph", "First Paragraph", ("Body Text",), "Body Text", ""),          # §11.3
    ("paragraph", "Compact", "Compact", ("Normal",), None, ""),                                     # §11.3
    ("paragraph", "Figure", "Figure", ("Normal",), None, '<w:pPr><w:jc w:val="center"/></w:pPr>'),
    ("paragraph", "CaptionedFigure", "Captioned Figure", ("Normal",), None,
     '<w:pPr><w:keepNext/><w:jc w:val="center"/></w:pPr>'),                                        # §11.3
    ("paragraph", "ImageCaption", "Image Caption", ("Caption",), None, ""),                        # §11.3
    ("paragraph", "TableCaption", "Table Caption", ("Caption",), None,
     "<w:pPr><w:keepNext/></w:pPr>"),                                                               # §11.3
    ("paragraph", "Bibliography", "Bibliography", ("Reference", "Normal"), None, ""),               # §11.3
    ("paragraph", "AbstractTitle", "Abstract Title", ("NoNumberSectionHeader", "Normal"), None, ""),
    ("paragraph", "Date", "Date", ("Normal",), None, ""),
    ("paragraph", "BlockText", "Block Text", ("Body Text",), None, ""),
    ("paragraph", "FootnoteBlockText", "Footnote Block Text", ("Footnote Text",), None, ""),
    ("paragraph", "DefinitionTerm", "Definition Term", ("Normal",), None, "<w:pPr><w:keepNext/></w:pPr>"),
    ("paragraph", "Definition", "Definition", ("Normal",), None, ""),
    ("character", "Hyperlink", "Hyperlink", ("Default Paragraph Font",), None, ""),                # §11.3 (書式なし)
    ("character", "VerbatimChar", "Verbatim Char", ("Default Paragraph Font",), None,
     '<w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/></w:rPr>'),
    # コードブロックの段落。雛形に無いと pandoc が basedOn="Normal" (ID の決め打ち) で足し、Normal の ID が違う雛形では
    # 基の無いスタイルになる (出力を検査して確かめた)。字形は中の文字スタイル (Verbatim Char と *Tok) が決める
    ("paragraph", "SourceCode", "Source Code", ("Normal",), None, '<w:pPr><w:wordWrap w:val="off"/></w:pPr>'),
    ("table", "Table", "Table", ("Normal Table",), None, ""),                                       # §11.3 (罫線は後処理)
    # 本テンプレートの記法の custom-style (generic-style.lua が温存する Div。CLAUDE.md の「原稿執筆の規約」)
    ("paragraph", "Abstract", "Abstract", ("Body Text",), None, ""),                                # §11.3
    ("paragraph", "Keywords", "Keywords", ("Normal",), None, ""),                                   # §11.3
    ("paragraph", "Author", "Author", ("Normal",), None, ""),
    ("paragraph", "Affiliation", "Affiliation", ("Normal",), None, ""),
    ("paragraph", "Corresponding", "Corresponding", ("Normal",), None, ""),
    # 凡例 (図表の題の後に続く説明)。テンプレートの題 (caption) の書式 (行番号を打たない) を継ぎ、太字だけを外す
    # (題 = 太字の 1 文、凡例 = 地の文の説明。ABE の規定の「題とキャプション」)。題の無いテンプレートなら Normal
    ("paragraph", "Legend", "Legend", ("Caption", "Normal"), None,
     '<w:rPr><w:b w:val="0"/><w:bCs w:val="0"/></w:rPr>'),
)

# 雛形がふつう持つスタイル (の名前)。テンプレートに無くて受け皿の別名を足したら、標準エラーに警告する。
# 上の表の最初の 6 種と、表題ページの著者と所属 (学会のテンプレートは著者と所属の段落の書式を持つのがふつう。ABE の ver.3 も持つ)。
# Abstract / Keywords / Corresponding など本テンプレートの記法のスタイルと pandoc 固有のスタイルは、テンプレートに無いのがふつうなので
# 足しても警告しない (ver.3 から作るときに警告を出さないため)。基の候補が 2 つ以上ある別名で 2 番目以降の基を使ったときも警告する
# (Bibliography ← Normal・Abstract Title ← Normal。テンプレートの Reference・NoNumberSectionHeader が無い。caption が無ければ
#  先に Caption の受け皿を足して警告するので、Legend などはそれを基にする)。
# (警告は標準エラーに出す。build / diff から呼ぶ scripts/lib/ensure-reference.sh は make-reference.sh の標準出力を捨てるので、
#  標準出力にだけ出すと、改版で caption・Author・Affiliation・Subtitle が消えたか名前が変わっても誰にも見えず、
#  その段落が Normal や Title の書式で黙って組まれる)
TEMPLATE_EXPECTED_STYLES = frozenset({
    "Body Text", "Title", "Subtitle", "Caption", "Footnote Text", "Footnote Reference", "Author", "Affiliation"})

# 語の途中で切らないスタイル (テンプレートは settings.xml で自動ハイフネーションを有効にしており、それは残す。
# 切ると両端揃えの語間が広がるため。題は「Appa-ratus」と切られた。§11.1。揃え方はテンプレートのまま = 両端揃え)
NO_HYPHENATION_STYLES = ("Title", "Subtitle")


def _xml(fragment):
    """w: を前置した XML の断片を要素にする。"""
    return etree.fromstring(f'<x xmlns:w="{W}">{fragment}</x>')[0]


def add_template_aliases(styles_root):
    """TEMPLATE_ALIASES のうちテンプレートに無いものを足す。戻り値は ([(ID, 基にしたスタイルの名前)], [警告の文])。

    警告は受け皿を使ったとき = 雛形がふつう持つスタイル
    (TEMPLATE_EXPECTED_STYLES) が無くて足したときと、基の 2 番目以降の候補を使ったときに 1 件ずつ。
    """
    added, warnings = [], []
    for typ, sid, name, bases, next_name, extra in TEMPLATE_ALIASES:
        if docx_styles.style_by_name(styles_root, name, typ) is not None:
            continue
        clash = docx_styles.style_by_id(styles_root, sid)
        if clash is not None:
            raise TemplateError(
                f"別名スタイル '{name}' を ID '{sid}' で足せません。テンプレートに同じ ID の別のスタイル "
                f"'{docx_styles.style_name(clash)}' があります")
        base = next((b for b in bases if docx_styles.style_by_name(styles_root, b, typ) is not None), None)
        if base is None:
            raise TemplateError(
                f"別名スタイル '{name}' の基にするスタイル ({' / '.join(bases)}) がテンプレートにありません")
        st = etree.SubElement(styles_root, w("style"))
        st.set(w("type"), typ)
        st.set(w("customStyle"), "1")
        st.set(w("styleId"), sid)
        etree.SubElement(st, w("name")).set(w("val"), name)
        etree.SubElement(st, w("basedOn")).set(
            w("val"), docx_styles.style_id_by_name(styles_root, base, typ))
        if next_name:
            etree.SubElement(st, w("next")).set(
                w("val"), docx_styles.style_id_by_name(styles_root, next_name, "paragraph"))
        etree.SubElement(st, w("qFormat"))
        if extra:
            st.append(_xml(extra))
        added.append((sid, base))
        if name in TEMPLATE_EXPECTED_STYLES:
            warnings.append(f"雛形がふつう持つスタイル '{name}' がテンプレートにありません。'{base}' を基にした受け皿を足しました "
                            f"('{name}' の段落は '{base}' の書式で組まれます)")
        elif base != bases[0]:
            warnings.append(f"別名スタイル '{name}' の基にするスタイル '{bases[0]}' がテンプレートにありません。"
                            f"代わりに '{base}' を基にしました ('{name}' の段落は '{base}' の書式で組まれます)")
    return added, warnings


def suppress_hyphenation(styles_root, names=NO_HYPHENATION_STYLES):
    """名前で引いたスタイルの w:pPr に w:suppressAutoHyphens を足す。戻り値は足したスタイルの名前。"""
    done = []
    for name in names:
        st = docx_styles.style_by_name(styles_root, name, "paragraph")
        if st is None:
            continue
        docx_styles.ppr_set(docx_styles.style_ppr(st), etree.Element(w("suppressAutoHyphens")))
        done.append(name)
    return done


def _effective_numpr(styles_root, style):
    """段落スタイルの自動番号 (numId, ilvl) を basedOn をたどって返す (近いほうの指定が勝つ。ilvl の既定は 0)。"""
    num_id = ilvl = None
    seen = set()
    st = style
    while st is not None and st.get(w("styleId")) not in seen:
        seen.add(st.get(w("styleId")))
        npr = st.find(f"{w('pPr')}/{w('numPr')}")
        if npr is not None:
            if num_id is None and npr.find(w("numId")) is not None:
                num_id = npr.find(w("numId")).get(w("val"))
            if ilvl is None and npr.find(w("ilvl")) is not None:
                ilvl = npr.find(w("ilvl")).get(w("val"))
        based = st.find(w("basedOn"))
        st = docx_styles.style_by_id(styles_root, based.get(w("val"))) if based is not None else None
    return num_id, (ilvl if ilvl is not None else "0")


def fix_heading_numbering(styles_root, numbering_root):
    """見出しの番号定義の小節 (ilvl 1 以上) から w:lvlRestart w:val="0" (= 上の段で戻さない) を外す (小節の番号を上の段ごとに 1 から振り直す)。

    想定の形は「heading 1〜3 が同じ番号定義 (abstractNum) の ilvl 0〜2 で、各段の pStyle がその見出し」(テンプレート ver.3)。
    形が違えば警告する (テンプレートの改版の検知)。戻り値は (外した ilvl の一覧, 警告の一覧)。
    """
    warnings = []
    heads = [docx_styles.style_by_name(styles_root, f"heading {k}", "paragraph") for k in (1, 2, 3)]
    if heads[0] is None:
        return [], ["heading 1 のスタイルがありません。見出しの番号定義を直せません"]
    num_id, _ = _effective_numpr(styles_root, heads[0])
    if num_id is None or numbering_root is None:
        return [], ["heading 1 に自動番号がありません。見出しの番号定義を直せません"]
    num = next((n for n in numbering_root.findall(w("num")) if n.get(w("numId")) == num_id), None)
    aid_el = num.find(w("abstractNumId")) if num is not None else None
    absn = None
    if aid_el is not None:
        absn = next((a for a in numbering_root.findall(w("abstractNum"))
                     if a.get(w("abstractNumId")) == aid_el.get(w("val"))), None)
    if absn is None:
        return [], [f"heading 1 の番号 (numId {num_id}) の番号定義が numbering.xml にありません"]
    if num is not None and num.find(w("lvlOverride")) is not None:
        warnings.append(f"numId {num_id} に lvlOverride があります (想定外)")
    lvls = {lv.get(w("ilvl")): lv for lv in absn.findall(w("lvl"))}
    for k, head in enumerate(heads):
        if head is None:
            warnings.append(f"heading {k + 1} のスタイルがありません")
            continue
        nid, ilvl = _effective_numpr(styles_root, head)
        lv = lvls.get(str(k))
        pst = lv.find(w("pStyle")) if lv is not None else None
        if nid != num_id or ilvl != str(k) or pst is None or pst.get(w("val")) != head.get(w("styleId")):
            warnings.append(f"heading {k + 1} の番号が想定の形 (numId {num_id} の ilvl {k}) と違います "
                            f"(numId {nid} / ilvl {ilvl})")
    removed = []
    for ilvl, lv in sorted(lvls.items()):
        restart = lv.find(w("lvlRestart"))
        if ilvl != "0" and restart is not None and restart.get(w("val")) == "0":
            lv.remove(restart)
            removed.append(ilvl)
    return removed, warnings


def _strip_identifiers(root):
    """編集履歴の識別子 (w:rsid* 属性・w:rsid 要素) と段落の識別子 (w14:paraId / w14:textId) を外す (§8.4)。"""
    n = 0
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        if el.tag == w("rsid"):
            el.getparent().remove(el)
            n += 1
            continue
        for attr in list(el.attrib):
            if attr.startswith(f"{{{W}}}rsid") or attr in (f"{{{W14}}}paraId", f"{{{W14}}}textId"):
                del el.attrib[attr]
                n += 1
    return n


def clean_settings(settings_root):
    """settings.xml から文書を特定しうる情報 (docVars・rsids・w14:docId・w15:docId) を外す。

    自動ハイフネーションなどの組版の設定は残す (settings.xml は pandoc の出力にそのまま移る。§11.1)。
    戻り値は外した要素の名前。

    改版で増えうる次の 4 つも外す (どれも ver.3 には無い)。
    - w:documentProtection / w:writeProtection: 文書の保護 (パスワードのハッシュとソルトを持ちうる)。全出力に移ると、
      出力の docx も保護される
    - w:trackRevisions: 変更履歴の記録。テンプレートの変更履歴は確定させるので (accept_revisions)、記録の設定も残さない
      (残すと全出力が変更履歴を記録する状態で開く)
    - w:mailMerge: 差し込み印刷の設定 (データの元のパス = 作った人の手元のパスを持ちうる)
    """
    removed = []
    for tag, label in ((w("docVars"), "w:docVars"), (w("rsids"), "w:rsids"), (f"{{{W14}}}docId", "w14:docId"),
                       (f"{{{W15}}}docId", "w15:docId"), (w("attachedTemplate"), "w:attachedTemplate"),
                       (w("documentProtection"), "w:documentProtection"),
                       (w("writeProtection"), "w:writeProtection"),
                       (w("trackRevisions"), "w:trackRevisions"), (w("mailMerge"), "w:mailMerge")):
        for el in settings_root.findall(tag):
            settings_root.remove(el)
            removed.append(label)
    return removed


def drop_settings_rels(parts):
    """settings.xml の関係定義から、添付テンプレート (attachedTemplate) を指すものを外す。戻り値は外した数。

    添付テンプレートの行き先は作った人の手元のパス (Windows のユーザーのフォルダの下の .dotm など) になりうる。
    clean_settings が w:attachedTemplate を外すので、それが指していた関係定義も残さない。
    """
    name = "word/_rels/settings.xml.rels"
    if name not in parts:
        return 0
    rels = etree.fromstring(parts[name])
    n = 0
    for rel in rels.findall(f"{{{PKGREL_NS}}}Relationship"):
        if (rel.get("Type") or "").endswith("/attachedTemplate"):
            rels.remove(rel)
            n += 1
    parts[name] = etree.tostring(rels, xml_declaration=True, encoding="UTF-8", standalone=True)
    return n


def clean_doc_props(parts):
    """docProps/core.xml の作成者・最終更新者などと app.xml の会社名などを空にする (§8.4)。

    作成日時・更新日時・版数は残す (人を特定しないうえ、空にすると Word が読み込みで直す値がある)。
    """
    cleared = []
    if "docProps/core.xml" in parts:
        core = etree.fromstring(parts["docProps/core.xml"])
        for el in core:
            if not isinstance(el.tag, str):
                continue
            local = etree.QName(el).localname
            if local in ("created", "modified", "revision"):
                continue
            if (el.text or "").strip():
                cleared.append(f"core.{local}")
            el.text = None
            for child in list(el):
                el.remove(child)
        parts["docProps/core.xml"] = etree.tostring(core, xml_declaration=True, encoding="UTF-8", standalone=True)
    if "docProps/app.xml" in parts:
        app = etree.fromstring(parts["docProps/app.xml"])
        for local in ("Company", "Manager", "HyperlinkBase"):
            for el in app.findall(f"{{{EP_NS}}}{local}"):
                if (el.text or "").strip():
                    cleared.append(f"app.{local}")
                el.text = None
        for el in app.iter(f"{{{VT_NS}}}lpstr"):
            # TitlesOfParts は文書の題を持ちうる (HeadingPairs の「タイトル」などの見出し語は残す)
            if el.getparent() is not None and el.getparent().getparent() is not None and \
                    etree.QName(el.getparent().getparent()).localname == "TitlesOfParts":
                if (el.text or "").strip():
                    cleared.append("app.TitlesOfParts")
                el.text = None
        parts["docProps/app.xml"] = etree.tostring(app, xml_declaration=True, encoding="UTF-8", standalone=True)
    return cleared


def drop_custom_xml(parts):
    """customXml/ (Word の文献管理の置き場など) のパートと、それを指す関係定義・種類の宣言を外す。戻り値は外したパート数。"""
    names = [n for n in parts if n.startswith("customXml/")]
    for n in names:
        parts.pop(n)
    rels_name = "word/_rels/document.xml.rels"
    if rels_name in parts:
        rels = etree.fromstring(parts[rels_name])
        for rel in rels.findall(f"{{{PKGREL_NS}}}Relationship"):
            if "customXml/" in (rel.get("Target") or ""):
                rels.remove(rel)
        parts[rels_name] = etree.tostring(rels, xml_declaration=True, encoding="UTF-8", standalone=True)
    ct = etree.fromstring(parts["[Content_Types].xml"])
    for ov in ct.findall(f"{{{CT_NS}}}Override"):
        if (ov.get("PartName") or "").startswith("/customXml/"):
            ct.remove(ov)
    parts["[Content_Types].xml"] = etree.tostring(ct, xml_declaration=True, encoding="UTF-8", standalone=True)
    return len(names)


# ---------------------------------------------------------------------
# 改版で増えうる識別情報の除去
# (除去を ver.3 にあった種類 (最終更新者・docVars・rsid・docId・customXml・段落の ID) だけの列挙にすると、改版で変更履歴の作成者名・
#  コメント (comments.xml)・people.xml・docProps/custom.xml・文書の保護・本文から参照されない画像が増えたとき、reference.docx に
#  そのまま残り、一部 (柱の変更履歴の作成者名・保護の設定・画像) は build の出力にも移る)
# 方針: (1) 全パートの変更履歴を確定させ、コメントの範囲と参照を外す (2) 残すパートを許可リストにし、それ以外は外す
#       (許可リストに無いパートは止めずに外し、標準エラーに警告する。外したパートをどこかが指したままなら (3) の後の検算で止める)
#       (3) どこからも指されないパートと、本文から参照されない関係 (見本の図・リンクの残り) を外す
#       (4) 最後に、残ったパートに作成者などの属性 (author / initials / userId / providerId / ed) が無いことを確かめ、あれば止める
# ---------------------------------------------------------------------

# 中身を残して包みだけ外す変更履歴 (挿入・移動先) と、中身ごと消す変更履歴 (削除・移動元)
_REV_UNWRAP = frozenset({"ins", "moveTo"})
_REV_DROP = frozenset({"del", "moveFrom"})
# 目印だけ消すもの: 移動の範囲・カスタム XML の変更の範囲・書式の変更履歴 (*Change。今の書式を残す)・表のセルの変更履歴
_REV_REMOVE = frozenset({
    "moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd",
    "customXmlInsRangeStart", "customXmlInsRangeEnd", "customXmlDelRangeStart", "customXmlDelRangeEnd",
    "customXmlMoveFromRangeStart", "customXmlMoveFromRangeEnd", "customXmlMoveToRangeStart", "customXmlMoveToRangeEnd",
    "rPrChange", "pPrChange", "sectPrChange", "tblPrChange", "tblPrExChange", "trPrChange", "tcPrChange",
    "tblGridChange", "numberingChange", "cellIns", "cellDel", "cellMerge"})
_REV_ALL = _REV_UNWRAP | _REV_DROP | _REV_REMOVE
# コメントの範囲と参照。編集の制限の例外の範囲 (w:permStart / End) も同じく外す (w:ed に編集を許す人のアカウント名を持ちうる。
# 文書の保護 (w:documentProtection) を外すので、例外の範囲は意味を失う)
_COMMENT_MARKS = frozenset({"commentRangeStart", "commentRangeEnd", "commentReference", "permStart", "permEnd"})


def _remove_keep_tail(el):
    """el を外す (後ろの文字 (tail) は前の兄弟か親へ寄せて残す)。"""
    parent = el.getparent()
    if parent is None:
        return
    if el.tail:
        prev = el.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + el.tail
        else:
            parent.text = (parent.text or "") + el.tail
    parent.remove(el)


def _unwrap(el):
    """el の子を el の位置へ移してから el を外す (中身を残して包みだけ外す)。"""
    parent = el.getparent()
    if el.text:
        prev = el.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + el.text
        else:
            parent.text = (parent.text or "") + el.text
    idx = parent.index(el)
    for k, child in enumerate(list(el)):
        parent.insert(idx + k, child)
    _remove_keep_tail(el)


def _merge_with_next_paragraph(p):
    """段落記号の削除を確定させる: p の中身 (w:pPr 以外) を次の段落の頭へ移し、p を外す (段落記号は次の段落のものが残る)。

    節の区切りを持つ段落・次が段落でないときは合わせない (段落記号の削除の印だけを外したまま)。
    """
    if p is None or p.tag != w("p") or p.find(f"{w('pPr')}/{w('sectPr')}") is not None:
        return
    nxt = p.getnext()
    while nxt is not None and not isinstance(nxt.tag, str):
        nxt = nxt.getnext()
    if nxt is None or nxt.tag != w("p"):
        return
    ppr = nxt.find(w("pPr"))
    idx = nxt.index(ppr) + 1 if ppr is not None else 0
    for k, child in enumerate([c for c in p if c.tag != w("pPr")]):
        nxt.insert(idx + k, child)
    _remove_keep_tail(p)


def accept_revisions(root):
    """パートの変更履歴をすべて確定させる (Word の「すべての変更を反映」と同じ向き)。戻り値は確定させた変更履歴の数。

    挿入 (w:ins)・移動先 (w:moveTo) は中身を残し、削除 (w:del)・移動元 (w:moveFrom) は中身ごと消す。段落記号の削除
    (w:pPr/w:rPr/w:del) は次の段落と合わせ、行の削除 (w:trPr/w:del) は行を消す。書式の変更履歴 (*Change) は今の書式を残して外す。
    変更履歴の要素は作成者名 (w:author) と日時を持つ。文書の後ろから処理するので、入れ子は内側から片づく。
    """
    targets = [el for el in root.iter() if isinstance(el.tag, str) and etree.QName(el).namespace == W
               and etree.QName(el).localname in _REV_ALL]
    for el in reversed(targets):
        local = etree.QName(el).localname
        parent = el.getparent()
        if parent is None:
            continue
        plocal = _localname(parent)
        grand = parent.getparent()
        if local in _REV_REMOVE:
            _remove_keep_tail(el)
        elif plocal == "rPr" and grand is not None and _localname(grand) == "pPr":
            # 段落記号の変更履歴 (挿入は印を外すだけ、削除は次の段落と合わせる)
            _remove_keep_tail(el)
            if local in _REV_DROP:
                _merge_with_next_paragraph(grand.getparent())
        elif plocal == "trPr":
            # 行の変更履歴 (挿入は印を外すだけ、削除は行を消す)
            _remove_keep_tail(el)
            if local in _REV_DROP and grand is not None and grand.tag == w("tr"):
                _remove_keep_tail(grand)
        elif plocal == "numPr":
            _remove_keep_tail(el)                   # 番号の挿入の印 (番号は残す)
        elif local in _REV_UNWRAP:
            _unwrap(el)
        else:
            _remove_keep_tail(el)
    return len(targets)


def strip_comment_anchors(root):
    """コメントの範囲 (w:commentRangeStart / End) と参照 (w:commentReference)、編集の例外の範囲 (w:permStart / End) を外す。

    参照だけになった run も外す。戻り値は外した数。
    """
    found = [el for el in root.iter() if isinstance(el.tag, str) and etree.QName(el).namespace == W
             and etree.QName(el).localname in _COMMENT_MARKS]
    for el in found:
        parent = el.getparent()
        _remove_keep_tail(el)
        if parent is not None and parent.tag == w("r") and \
                all(c.tag == w("rPr") for c in parent if isinstance(c.tag, str)):
            _remove_keep_tail(parent)
    return len(found)


def scrub_xml_parts(parts, parser):
    """XML のパートすべてで変更履歴を確定させ、コメントの範囲と参照を外す。変わったパートだけ書き戻す。戻り値は (変更履歴, コメント) の数。"""
    n_rev = n_comment = 0
    for name in list(parts):
        if not name.endswith(".xml") or name == "[Content_Types].xml":
            continue
        root = etree.fromstring(parts[name], parser)
        k_rev, k_comment = accept_revisions(root), strip_comment_anchors(root)
        if k_rev or k_comment:
            parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            n_rev, n_comment = n_rev + k_rev, n_comment + k_comment
    return n_rev, n_comment


# reference.docx に残すパートの許可リスト (pandoc が雛形から読むパートと、それが指す画像・埋め込みの書体)。
# 関係定義 (*.rels) は元のパートが残るときだけ残す。ここに無いパートは外す (外したことは表示し、想定外のものは警告する)
KEEP_PART_RE = re.compile(
    r"\[Content_Types\]\.xml|docProps/(core|app)\.xml"
    r"|word/(document|styles|numbering|settings|webSettings|fontTable|footnotes|endnotes)\.xml"
    r"|word/(header|footer)\d*\.xml|word/theme/theme\d*\.xml|word/media/[^/]+|word/fonts/[^/]+")
# 識別情報を持ちうるので外すと決めているパート (許可リストに無いので外れる。警告にしないための区別)。
# コメント (作成者名と本文)・コメントの付属・people.xml (作成者の一覧とアカウント)・独自のプロパティ・縮小版の画像 (見本の 1 ページ目)
IDENTIFYING_PART_RE = re.compile(
    r"word/comments(Extended|Ids|Extensible)?\.xml|word/people\.xml|docProps/custom\.xml|docProps/thumbnail\.[^/]+")
# 元のパートの中から r:id / r:embed などで指す関係の種類 (Type の最後の部分)。指されていなければ外す
# (見本の文章を消した後の図・リンクの残りや、外した設定 (添付テンプレート・差し込み印刷) が指していたもの)。
# styles / numbering / footnotes などは指さずに使う種類なので入れない
_REFERENCED_REL_TYPES = frozenset({
    "image", "hyperlink", "oleObject", "package", "chart", "video", "audio", "media", "hdphoto",
    "diagramData", "diagramLayout", "diagramQuickStyle", "diagramColors", "diagramDrawing",
    "control", "aFChunk", "subDocument", "header", "footer",
    "attachedTemplate", "mailMergeSource", "mailMergeHeaderSource", "recipientData", "font"})


def _rels_name(part):
    """パートの関係定義の名前 (word/document.xml → word/_rels/document.xml.rels。'' はパッケージの _rels/.rels)。"""
    d, _, f = part.rpartition("/")
    return f"{d}/_rels/{f}.rels" if d else f"_rels/{f}.rels"


def _rels_source(name):
    """関係定義の元のパート (word/_rels/document.xml.rels → word/document.xml。_rels/.rels → '')。関係定義でなければ None。"""
    m = re.fullmatch(r"(?:(.*)/)?_rels/([^/]*)\.rels", name)
    if m is None:
        return None
    return f"{m.group(1)}/{m.group(2)}" if m.group(1) else m.group(2)


def _rel_target(source, rel):
    """関係の行き先のパート名 (外部なら None)。"""
    if rel.get("TargetMode") == "External":
        return None
    target = rel.get("Target") or ""
    if target.startswith("/"):
        return target.lstrip("/")
    base = source.rpartition("/")[0]
    return posixpath.normpath(posixpath.join(base, target)) if base else posixpath.normpath(target)


def _referenced_ids(data):
    """XML のパートが r: の属性 (r:id / r:embed / r:link …) で指す関係の ID の集合。"""
    ids = set()
    for el in etree.fromstring(data).iter():
        if isinstance(el.tag, str):
            ids.update(v for k, v in el.attrib.items() if k.startswith(f"{{{R_NS}}}") and v)
    return ids


def prune_package(parts):
    """許可リストに無いパート・どこからも指されないパート・元のパートから指されない関係を外す。

    戻り値は {"identifying": [...], "unknown": [...], "orphan": [...], "rels": 外した関係の数}。種類の宣言 ([Content_Types].xml の
    Override) は外したパートの分だけ消す (元から実在しないパートの宣言には触らない = ver.3 の出力を変えない)。
    """
    removed = {"identifying": [], "unknown": [], "orphan": [], "rels": 0}
    for name in list(parts):
        if name.endswith("/"):
            parts.pop(name)                     # zip のディレクトリの項目 (パートではない。Word は書かないが、zip し直すと付く)
            continue
        if _rels_source(name) is not None or KEEP_PART_RE.fullmatch(name):
            continue
        parts.pop(name)
        removed["identifying" if IDENTIFYING_PART_RE.fullmatch(name) else "unknown"].append(name)
    gone = set(removed["identifying"]) | set(removed["unknown"])
    while True:
        # 元のパートが無くなった関係定義を外す
        for name in list(parts):
            src = _rels_source(name)
            if src and src not in parts:
                parts.pop(name)
        # 外したパートを指す関係・元のパートから指されない関係を外す
        for name in list(parts):
            src = _rels_source(name)
            if src is None:
                continue
            rels = etree.fromstring(parts[name])
            used = _referenced_ids(parts[src]) if src.endswith(".xml") and src in parts else None
            changed = False
            for rel in rels.findall(f"{{{PKGREL_NS}}}Relationship"):
                kind = (rel.get("Type") or "").rsplit("/", 1)[-1]
                target = _rel_target(src, rel)
                if (target is not None and target in gone) or \
                        (used is not None and kind in _REFERENCED_REL_TYPES and rel.get("Id") not in used):
                    rels.remove(rel)
                    removed["rels"] += 1
                    changed = True
            if changed:
                parts[name] = etree.tostring(rels, xml_declaration=True, encoding="UTF-8", standalone=True)
        # パッケージの関係定義からたどれないパートを外す (見本の図を消した後に残った画像など)
        reach, queue = set(), [""]
        while queue:
            src = queue.pop()
            rels_name = _rels_name(src) if src else "_rels/.rels"
            if rels_name not in parts:
                continue
            for rel in etree.fromstring(parts[rels_name]).findall(f"{{{PKGREL_NS}}}Relationship"):
                target = _rel_target(src, rel)
                if target is not None and target in parts and target not in reach:
                    reach.add(target)
                    queue.append(target)
        orphans = [n for n in parts
                   if n != "[Content_Types].xml" and _rels_source(n) is None and n not in reach]
        if not orphans:
            break
        for n in orphans:
            parts.pop(n)
            removed["orphan"].append(n)
            gone.add(n)
    if gone:
        ct = etree.fromstring(parts["[Content_Types].xml"])
        changed = False
        for ov in ct.findall(f"{{{CT_NS}}}Override"):
            if (ov.get("PartName") or "").lstrip("/") in gone:
                ct.remove(ov)
                changed = True
        if changed:
            parts["[Content_Types].xml"] = etree.tostring(ct, xml_declaration=True, encoding="UTF-8", standalone=True)
    return removed


def check_all_relationships(parts):
    """残ったすべてのパートについて、r: の属性が指す ID が自分の関係定義に実在するかを確かめる (無ければ止める)。

    check_relationships (document.xml だけ) を全パートに広げたもの。許可リストに無いパートを外した結果、柱などが
    それを指したままになったら (埋め込みのオブジェクトなど)、壊れた reference.docx を書かずに止める。
    """
    missing = []
    for name, data in parts.items():
        if not name.endswith(".xml") or name == "[Content_Types].xml":
            continue
        used = _referenced_ids(data)
        if not used:
            continue
        rels_name = _rels_name(name)
        defined = set()
        if rels_name in parts:
            defined = {r.get("Id") for r in etree.fromstring(parts[rels_name]).findall(f"{{{PKGREL_NS}}}Relationship")}
        missing += [f"{name}→{rid}" for rid in sorted(used - defined)]
    if missing:
        raise TemplateError("パートが関係定義に無い ID を指しています (外したパートを指していた可能性。壊れた docx になるため中止): "
                            + ", ".join(missing))


# 人を特定しうる属性の名前 (名前空間は問わない)。変更履歴・コメント (w:author / w:initials)、people.xml (w15:userId /
# w15:providerId)、編集の例外の範囲 (w:permStart の w:ed) が持つ。除去を通った後に残っていたら、想定していない置き場所なので止める
_PERSONAL_ATTRS = frozenset({"author", "initials", "userId", "providerId", "ed"})


def check_no_personal_attrs(parts):
    """残ったパートに作成者などの属性が無いことを確かめる (あれば TemplateError)。"""
    found = {}
    for name, data in parts.items():
        if not (name.endswith(".xml") or name.endswith(".rels")):
            continue
        for el in etree.fromstring(data).iter():
            if not isinstance(el.tag, str):
                continue
            for attr in el.attrib:
                if etree.QName(attr).localname in _PERSONAL_ATTRS:
                    key = (name, etree.QName(attr).localname)
                    found[key] = found.get(key, 0) + 1
    if found:
        raise TemplateError("除去の後も作成者などの属性が残っています (想定外の置き場所。テンプレートの改版の可能性): "
                            + ", ".join(f"{n} の {a} {k} 件" for (n, a), k in sorted(found.items())))


def _has_text(el):
    return any((t.text or "").strip() for t in el.iter(w("t"), w("instrText"), w("delText")))


def _is_page_break_only(p):
    """改ページ (w:br w:type="page") を持ち、文字の無い段落か。"""
    return (p is not None and p.tag == w("p") and not _has_text(p)
            and any(br.get(w("type")) == "page" for br in p.iter(w("br"))))


def reduce_to_skeleton(doc_root):
    """本文を節の骨組みだけにする。戻り値は残した節の説明 (表示用)。

    残すもの: 節の区切りを持つ段落 (w:pPr/w:sectPr。中の文字は消し w:pPr だけにする)・その直前の改ページだけの段落・最終の sectPr。
    見本の文章・表・ブックマークはすべて消す。消した後に文字が残っていれば止まる。
    """
    body = doc_root.find(w("body"))
    if body is None:
        raise TemplateError("word/document.xml に w:body がありません")
    final = body.find(w("sectPr"))
    if final is None:
        raise TemplateError("word/document.xml に最終の sectPr (w:body の直下) がありません")
    stray = [s for s in doc_root.iter(w("sectPr"))
             if s is not final and not (s.getparent().tag == w("pPr")
                                        and s.getparent().getparent().getparent() is body)]
    if stray:
        raise TemplateError(f"本文の段落以外 (表の中など) に節の区切りが {len(stray)} 個あります (想定外。改版の可能性)")
    keep = [final]
    for p in body.findall(w("p")):
        if p.find(f"{w('pPr')}/{w('sectPr')}") is None:
            continue
        for child in list(p):
            if child.tag != w("pPr"):
                p.remove(child)
        keep.append(p)
        prev = p.getprevious()
        if _is_page_break_only(prev):
            keep.append(prev)
    for el in list(body):
        if not any(el is k for k in keep):
            body.remove(el)
    if _has_text(body):
        raise TemplateError("節の骨組みに文字が残りました (想定外。改版の可能性)")
    out = []
    sects = [s for s in body.iter(w("sectPr"))]
    for k, s in enumerate(sects, 1):
        cols = s.find(w("cols"))
        ncol = (cols.get(w("num")) if cols is not None else None) or "1"
        typ = s.find(w("type"))
        refs = [r.get(w("type")) for r in s if r.tag in (w("headerReference"), w("footerReference"))]
        out.append(f"節{k}: {typ.get(w('val')) if typ is not None else 'nextPage'}・{ncol} 段・"
                   f"行番号{'あり' if s.find(w('lnNumType')) is not None else 'なし'}・"
                   f"ヘッダ/フッタの参照 {len(refs)}")
    n_break = sum(1 for p in body.findall(w("p")) if _is_page_break_only(p))
    return out, n_break


def _write_docx_atomic(parts, out_path):
    """パートを時刻固定 (1980-01-01) で zip にし、一時名に書いてから置き換える。

    build と diff が同時に作り直しても、読む側が書きかけの reference.docx を掴まないように (中身は同じになる)。
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{out_path.name}.", suffix=".tmp", dir=out_path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, data in parts.items():
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                zout.writestr(info, data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, out_path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def process_template(base_path, out_path, *, inject_diff=True):
    """雑誌が配るテンプレート base_path から reference.docx を out_path に作る (体裁は焼き込まない)。"""
    base_path, out_path = Path(base_path), Path(out_path)
    if base_path.resolve() == out_path.resolve():
        raise TemplateError("出力先がテンプレートそのものです (テンプレートを上書きしないよう止めました)")
    if not base_path.is_file():
        raise TemplateError(f"テンプレート {base_path} がありません")
    try:
        with zipfile.ZipFile(base_path, "r") as zin:
            parts = {item.filename: zin.read(item.filename) for item in zin.infolist()}
    except zipfile.BadZipFile as exc:
        raise TemplateError(f"テンプレート {base_path} を docx (zip) として読めません ({exc})") from exc
    # _rels/.rels も要る (どこからも指されないパートを外すとき、パッケージの関係定義からたどるため。
    # 無ければ全パートが外れる)
    for need in ("[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml",
                 "word/_rels/document.xml.rels"):
        if need not in parts:
            raise TemplateError(f"テンプレート {base_path} に {need} がありません (docx ではないか壊れています)")
    parser = etree.XMLParser(remove_blank_text=False)
    log = []

    # --- styles.xml: 別名・題のハイフネーション・差分の文字スタイル・境界マーカー ---
    styles_root = etree.fromstring(parts["word/styles.xml"], parser)
    added, alias_warnings = add_template_aliases(styles_root)
    log.append("別名スタイルを足した: " + (", ".join(f"{sid}←{base}" for sid, base in added) or "(なし)"))
    # 受け皿を使ったことは標準エラーに出す (build / diff の ensure-reference.sh は標準出力を捨てる)
    for msg in alias_warnings:
        print(f"  警告: {msg}。テンプレートの改版でスタイルが消えたか名前が変わった可能性があります。出力を確かめてください",
              file=sys.stderr)
    log.append("語の途中で切らない: " + (", ".join(suppress_hyphenation(styles_root)) or "(該当なし)"))
    if inject_diff:
        inject_diff_styles(styles_root)
    inject_textbox_marker_style(styles_root)
    _strip_identifiers(styles_root)
    parts["word/styles.xml"] = etree.tostring(styles_root, xml_declaration=True, encoding="UTF-8", standalone=True)

    # --- numbering.xml: 見出しの小節の番号を節で戻す ---
    numbering_root = (etree.fromstring(parts["word/numbering.xml"], parser)
                      if "word/numbering.xml" in parts else None)
    removed, warnings = fix_heading_numbering(styles_root, numbering_root)
    log.append("見出しの番号定義: " + (f"ilvl {', '.join(removed)} の lvlRestart=0 を外した" if removed
                                     else "外す lvlRestart=0 は無かった"))
    for msg in warnings:
        print(f"  警告: 見出しの番号定義が想定の形と違います — {msg} (テンプレートの改版の可能性)", file=sys.stderr)
    if numbering_root is not None:
        parts["word/numbering.xml"] = etree.tostring(
            numbering_root, xml_declaration=True, encoding="UTF-8", standalone=True)

    # --- document.xml: 節の骨組みだけにする ---
    doc_root = etree.fromstring(parts["word/document.xml"], parser)
    # 骨組みにする前に変更履歴を確定させ、コメントの範囲を外す (節の区切りの書式の変更履歴
    # w:sectPrChange は古い w:sectPr を中に持ち、reduce_to_skeleton が「段落以外の節の区切り」とみなして止まるため)
    n_rev, n_comment = accept_revisions(doc_root), strip_comment_anchors(doc_root)
    sections, n_break = reduce_to_skeleton(doc_root)
    _strip_identifiers(doc_root)
    parts["word/document.xml"] = etree.tostring(doc_root, xml_declaration=True, encoding="UTF-8", standalone=True)
    log.append(f"本文を節の骨組みにした (改ページの段落 {n_break}): " + " / ".join(sections))

    # --- ヘッダ・フッタ・脚注・文末脚注: 識別子だけを外す (中身はテンプレートのまま。柱の差し替えは build の後処理) ---
    # comments はここで扱わない (コメントのパートは prune_package が外す)
    for name in sorted(parts):
        if re.fullmatch(r"word/(header\d*|footer\d*|footnotes|endnotes)\.xml", name):
            root = etree.fromstring(parts[name], parser)
            _strip_identifiers(root)
            parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    # --- settings.xml・docProps・customXml: 文書を特定しうる情報を外す (§8.4) ---
    if "word/settings.xml" in parts:
        settings_root = etree.fromstring(parts["word/settings.xml"], parser)
        dropped = clean_settings(settings_root)
        parts["word/settings.xml"] = etree.tostring(
            settings_root, xml_declaration=True, encoding="UTF-8", standalone=True)
        if drop_settings_rels(parts):
            dropped.append("添付テンプレートの関係定義")
        log.append("settings.xml から外した: " + (", ".join(dropped) or "(なし)"))
    cleared = clean_doc_props(parts)
    log.append("docProps で空にした: " + (", ".join(cleared) or "(なし)"))
    log.append(f"customXml のパートを外した: {drop_custom_xml(parts)}")

    # --- 変更履歴・コメント・許可リストに無いパート・参照されない画像を外し、作成者などの属性が無いことを確かめる ---
    # (ver.3 にはどれも無いので、ver.3 から作る reference.docx は変わらない。変わったパートだけを書き戻す)
    k_rev, k_comment = scrub_xml_parts(parts, parser)
    n_rev, n_comment = n_rev + k_rev, n_comment + k_comment
    log.append(f"変更履歴を確定させた: {n_rev} か所 / コメントの範囲と参照・編集の例外の範囲を外した: {n_comment} か所")
    pruned = prune_package(parts)
    for need in ("word/document.xml", "word/styles.xml", "word/_rels/document.xml.rels"):
        if need not in parts:
            raise TemplateError(f"{need} がパッケージの関係定義からたどれません (テンプレートの構造が想定外)")
    log.append("外したパート: 識別情報を持ちうるもの " + (", ".join(pruned["identifying"]) or "(なし)")
               + " / どこからも指されないもの " + (", ".join(pruned["orphan"]) or "(なし)")
               + " / 許可リストに無いもの " + (", ".join(pruned["unknown"]) or "(なし)")
               + f" / 外した関係 {pruned['rels']}")
    if pruned["unknown"]:
        print("  警告: テンプレートに想定外のパートがあったので reference.docx に入れませんでした: "
              + ", ".join(pruned["unknown"]) + "。テンプレートの改版の可能性があります。出力を確かめてください",
              file=sys.stderr)
    check_all_relationships(parts)
    check_no_personal_attrs(parts)

    check_relationships(etree.fromstring(parts["word/document.xml"]), parts["word/_rels/document.xml.rels"])
    _write_docx_atomic(parts, out_path)
    print(f"wrote {out_path} (テンプレート {base_path} から。体裁は焼き込んでいない)")
    for line in log:
        print("  " + line)


def process(in_path, out_path, args):
    in_path = Path(in_path)
    out_path = Path(out_path)
    if in_path.resolve() == out_path.resolve():
        # 同一パスはまず一時退避してから書き戻す
        tmp = in_path.with_suffix(in_path.suffix + ".tmp")
        shutil.copy2(in_path, tmp)
        in_path = tmp

    with zipfile.ZipFile(in_path, "r") as zin:
        parts = {item.filename: zin.read(item.filename) for item in zin.infolist()}

    parser = etree.XMLParser(remove_blank_text=False)

    styles_root = etree.fromstring(parts["word/styles.xml"], parser)
    patch_styles(
        styles_root,
        font=args.font,
        font_size_pt=args.font_size,
        line_spacing=args.line_spacing,
        inject_diff=not args.no_diff_styles,
    )
    # 題・見出し・抄録の級数と色。どちらの引数も無ければ何もしない (既存誌の出力は不変)
    text_style_changes = []
    if args.uniform_style_size or args.heading_color != "keep":
        text_style_changes = normalize_text_styles(
            styles_root,
            font_size_pt=args.font_size,
            uniform_size=args.uniform_style_size,
            heading_color=args.heading_color,
        )
    # 行送りの個別指定を外す。引数が無ければ何もしない (既存誌の出力は不変)
    if args.uniform_line_spacing:
        text_style_changes += uniform_line_spacing(styles_root)
    parts["word/styles.xml"] = etree.tostring(
        styles_root, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    # ページ番号フッタ。sectPr の footerReference が指す rId を先に確定させる
    footer_rid = None
    if args.page_numbers:
        footer_rid = install_page_number_footer(
            parts, parser, font=args.font, font_size_pt=args.font_size
        )

    doc_root = etree.fromstring(parts["word/document.xml"], parser)
    patch_document(doc_root, margin_mm=args.margin, line_numbers=args.line_numbers,
                   paper=args.paper, footer_rid=footer_rid)
    parts["word/document.xml"] = etree.tostring(
        doc_root, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    # 宙に浮いた rId が無いことを書き出し前に検算する
    check_relationships(doc_root, parts["word/_rels/document.xml.rels"])

    # テーマフォント (Aptos) を本文フォントへ書き換える
    theme_name = "word/theme/theme1.xml"
    if theme_name in parts:
        theme_root = etree.fromstring(parts[theme_name], parser)
        patch_theme(theme_root, args.font)
        parts[theme_name] = etree.tostring(
            theme_root, xml_declaration=True, encoding="UTF-8", standalone=True
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            # パート名だけを渡すと zipfile が格納時刻に「その時の時刻」を入れるため、パートの内容がまったく同じでも
            # 生成のたびにバイト列が変わる (同じ引数で作り直した reference.docx が長さまで同じなのにバイト一致しない)。
            # それでは「意味のある変更」と「作り直しただけ」を後から区別できないので、時刻を固定して再現可能にする
            #  (ZIP の最小値である 1980-01-01。scripts/compare-snapshots.py が言うとおり
            #   pandoc 出力の docx は依然バイト比較できないが、本スクリプトの生成物は比較できる)。
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zout.writestr(info, data)

    if str(in_path).endswith(".tmp"):
        in_path.unlink(missing_ok=True)

    print(f"wrote {out_path}")
    print(
        f"  font={args.font} {args.font_size}pt  spacing={args.line_spacing}  "
        f"line-numbers={args.line_numbers}  page-numbers={'yes' if args.page_numbers else 'no'}  "
        f"margin={args.margin}mm  paper={args.paper}  "
        f"diff-styles={'no' if args.no_diff_styles else 'yes'}"
    )
    if text_style_changes:
        print(f"  text-styles: uniform-size={'yes' if args.uniform_style_size else 'no'}  "
              f"heading-color={args.heading_color}  "
              f"uniform-line-spacing={'yes' if args.uniform_line_spacing else 'no'}")
        print("    " + " / ".join(text_style_changes))


# 焼き込むモードの引数の既定値。--base (テンプレートから作る) では体裁を焼き込まないので、これらの引数を受け付けない。
# 既定値を argparse に持たせると「指定したか」が分からないので、ここに置いて焼き込むモードでだけ埋める
_BAKE_DEFAULTS = {"line_spacing": "double", "line_numbers": "continuous", "font": "Times New Roman",
                  "font_size": 12.0, "margin": 25.0, "paper": "a4", "heading_color": "keep"}
_BAKE_FLAGS = ("page_numbers", "uniform_style_size", "uniform_line_spacing")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", nargs="?", help="ベース reference.docx (pandoc 既定など)。--base と同時には使わない")
    p.add_argument("--base", metavar="DOCX",
                   help="雑誌が配るテンプレートから作る (profile の reference_base)。体裁は焼き込まず、足りないスタイルの "
                        "別名・見出しの番号定義・題のハイフネーションを直し、見本の文章と文書を特定しうる情報を消す")
    p.add_argument("-o", "--output", required=True, help="出力 reference.docx")
    p.add_argument("--line-spacing", choices=["single", "1.5", "double"], default=None, help="既定: double")
    p.add_argument("--line-numbers", choices=["none", "continuous", "per-page"], default=None,
                   help="既定: continuous")
    p.add_argument("--page-numbers", action="store_true",
                   help="フッタに中央揃えの PAGE フィールドを入れる (既定 off。profile の page_numbers)")
    p.add_argument("--font", default=None, help="本文フォント (既定: Times New Roman)")
    p.add_argument("--font-size", type=float, default=None, help="本文フォントサイズ pt (既定: 12)")
    p.add_argument("--margin", type=float, default=None, help="四辺余白 mm (既定: 25)")
    p.add_argument("--paper", choices=["a4", "letter"], default=None, help="用紙寸法 (既定: a4)")
    p.add_argument("--no-diff-styles", action="store_true", help="DiffAdd/DiffDel を注入しない")
    p.add_argument("--uniform-style-size", action="store_true",
                   help="題・見出し・抄録など級数を持つスタイルをすべて本文の級数にそろえ、見出しの階層を "
                        "太字/斜体で付ける (既定 off。profile の text_styles.uniform_size)")
    p.add_argument("--heading-color", choices=["keep", "black"], default=None,
                   help="題・見出しの色。black でテーマ色 (青) を外す (既定 keep。profile の "
                        "text_styles.heading_color)")
    p.add_argument("--uniform-line-spacing", action="store_true",
                   help="段落スタイルが個別に持つ行送りを外し、文書全体の行送り (--line-spacing) に "
                        "そろえる (既定 off。profile の text_styles.uniform_line_spacing。題の Title は "
                        "pandoc 既定でシングル)")
    args = p.parse_args(argv)
    if args.base:
        if args.input:
            p.error("入力の docx は --base か位置引数のどちらか 1 つで指定してください")
        given = [k for k in _BAKE_DEFAULTS if getattr(args, k) is not None] + \
                [k for k in _BAKE_FLAGS if getattr(args, k)]
        if given:
            p.error("--base (テンプレートから作る) では体裁を焼き込まないので、次の引数は使えません: "
                    + ", ".join("--" + k.replace("_", "-") for k in given))
        try:
            process_template(args.base, args.output, inject_diff=not args.no_diff_styles)
        except (TemplateError, RuntimeError, etree.XMLSyntaxError) as exc:
            # RuntimeError は同じ名前のスタイルが 2 つ (docx_styles) と宙に浮いた rId (check_relationships)。
            # どれもテンプレートの形の問題なので、トレースバックではなく理由だけを出す (出力は書いていない)
            print(f"エラー: {exc}", file=sys.stderr)
            return 2
        return 0
    if not args.input:
        p.error("ベースの docx (位置引数) か --base を指定してください")
    for key, value in _BAKE_DEFAULTS.items():
        if getattr(args, key) is None:
            setattr(args, key, value)
    process(args.input, args.output, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
