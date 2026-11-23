#!/usr/bin/env python3
"""layout.py — 段組の節構造の後処理: 表題部 1 段組 → 本文 N 段組・段抜き・段の幅の頭打ち (build / diff 共用)。

本文を 2 段組にし、表題ページ (題・著者・抄録・キーワード) だけを 1 段組にする雑誌 (ABE の学会テンプレート。
docs/journal-abe.md §8.1) のための処理。pandoc は段組を知らないので、節の区切りはすべて docx の後処理で組み立てる。
誌の profile の `layout.*` (journal_profile.layout()) で発火し、既定 (未指定) では呼ばれない (キーを持たない誌の出力は変わらない)。

■ 本文の節の出所 (テンプレートが正)
reference.docx が節を 2 つ持つ (雑誌のテンプレートから作った。表題部の節 + 本文の節) なら、本文の節は reference.docx の
**最終の節 (sectPr) を写す** (段数・段間・行番号・グリッド)。profile の columns / column_space はその照合にだけ使う
(違えばテンプレートの改版か profile の書き誤りとして警告する)。build / diff の実行時にテンプレート本体は読まない。
reference.docx が節を 1 つしか持たない誌 (体裁を焼き込んだ reference.docx) では、出力の最終の節を写して段数と段間を
profile の値にしたものを本文の節にする。

■ 組み立てた後の形 (docs/journal-abe.md §11.3。Word 実機で確かめた形)
  … 表題部の最後の段落 (layout.title_block_until。例 Keywords)
  <w:p><w:r><w:br w:type="page"/></w:r></w:p>                       ← layout.title_page_break が真のとき
  <w:p><w:pPr><w:sectPr>表題部の節</w:sectPr></w:pPr></w:p>        ← pandoc が出力の最終に写した節 (柱とフッタの参照つき・1 段組)。行番号は外す
  … 本文
  <w:sectPr>本文の節</w:sectPr>                                     ← continuous・N 段組・行番号 (柱とフッタの参照は持たない = 表題部の節から引き継ぐ)

■ 段抜き (連続の節区切りで 1 段組の節を挟む)
wide-blocks.lua が `.wide` の図・`::: wide` の Div (+ 直後の凡例) の前後に置いた目印 WIDE_START / WIDE_END を、連続の節区切りに置き換える:
  前: 範囲の直前の段落の w:pPr に本文の節 (N 段組) の写し — そこで段組の節を閉じる
  後: 範囲の最後の段落 (図の題・凡例) の w:pPr に 1 段組の節 — 範囲が表で終わるなら表の直後に空の段落を足して持たせる
1 段組の節は本文の節の写しで、w:cols を表題部の節のもの (1 段) にし、行番号の位置を段組の節とそろえる w:distance を足す
(段組の節の既定の距離は 1 段組の節より狭く、無いと行番号が段組の節より 3 mm 左に出る。Word 実機で確かめた)。

■ 段の幅の頭打ちと表の幅
段組の節の中の図 (wp:inline) が段の幅を超えたら、縦横比を保って段の幅に縮め、警告する (縮めないと Word は図を用紙の外まで出す。Word 実機で確かめた)。
表は幅を変えない (Word が段の幅に押し込む) が、セルの中で折り返せない語 (数字など) の幅から表の最小幅を見積もり、
段の幅を超える見込みなら警告して `::: wide` を案内する (押し込まれると数字がセルの中で割れて読めない。Word 実機で確かめた)。
pandoc が書く w:tblGrid は幅の指定の無い表ではいつも合計 7 920 twip (5.5 インチ) なので、手がかりにならない。

コンテナ内 (docx-paper-template-pandoc; lxml 同梱) で使う。
"""

import copy
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
import docx_styles  # noqa: E402
import journal_profile  # noqa: E402

W_NS = docx_styles.W
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
w = docx_styles.w

EMU_PER_TWIP = 635
TWIP_PER_MM = 1440 / 25.4
MARKERS = ("WIDE_START", "WIDE_END")
# 1 段組の節の行番号の位置 (twip)。段組の節で w:distance を書かないときの Word の既定 (段から約 3.2 mm) に合わせる
# (Word 実機で、180 にすると 1 段組の節の行番号が段組の節と同じ x 11.8 mm にそろう)
ONE_COLUMN_LN_DISTANCE = "180"
# 範囲が表で終わる・範囲の前が段落でないときに足す、節の区切りだけを持つ空の段落の形。
#   nonumber: 行番号を付けない (高さはふつうの 1 行)
#   compact:  行番号を付けず高さ 1 pt
#   plain:    何も付けない (行番号が 1 つ付く)
BREAK_PARAGRAPH = "nonumber"


def _local(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def _pstyle(p):
    ps = p.find(f"{w('pPr')}/{w('pStyle')}")
    return ps.get(w("val")) if ps is not None else None


def _para_sect(p):
    return p.find(f"{w('pPr')}/{w('sectPr')}") if p.tag == w("p") else None


def _marker_text(p):
    if p.tag != w("p") or _pstyle(p) != "TextBoxMarker":
        return None
    return "".join(t.text or "" for t in p.iter(w("t")))


def _is_wide_marker(el):
    return _marker_text(el) in MARKERS


def strip_markers(root):
    """段抜きの目印を消す (段組を組み立てない文書・誌のため)。消した数を返す。"""
    n = 0
    for p in [p for p in root.iter(w("p")) if _is_wide_marker(p)]:
        p.getparent().remove(p)
        n += 1
    return n


# =====================================================================
# 節の寸法
# =====================================================================

def _int(el, attr, default=0):
    v = el.get(w(attr)) if el is not None else None
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


def text_width_twip(sect):
    """節の本文幅 (twip)。用紙か余白の指定が無ければ None。"""
    pg, mar = sect.find(w("pgSz")), sect.find(w("pgMar"))
    if pg is None or mar is None or pg.get(w("w")) is None:
        return None
    return _int(pg, "w") - _int(mar, "left") - _int(mar, "right") - _int(mar, "gutter")


def columns_of(sect):
    """節の (段数, 段の幅 twip)。段の幅が段ごとに違う (w:col) なら最も狭い段の幅。本文幅が分からなければ (段数, None)。"""
    cols = sect.find(w("cols"))
    n = _int(cols, "num", 1) if cols is not None else 1
    n = max(n, 1)
    text = text_width_twip(sect)
    if cols is not None:
        col_elems = cols.findall(w("col"))
        if col_elems and cols.get(w("equalWidth")) in ("0", "false", "off"):
            return len(col_elems), min(_int(c, "w") for c in col_elems)
    if text is None:
        return n, None
    space = _int(cols, "space", 720) if cols is not None else 720
    return n, (text - space * (n - 1)) / n


# =====================================================================
# 準備 (reference.docx の節を読み、profile と照合する)
# =====================================================================

def _reference_sections(reference_doc):
    """reference.docx の本文の節 (sectPr) を文書の順に返す。前の段落が改ページだけかも返す: ([sectPr...], 改ページの有無)。"""
    with zipfile.ZipFile(reference_doc) as z:
        doc = etree.fromstring(z.read("word/document.xml"))
    body = doc.find(w("body"))
    sects, page_break = [], False
    prev = None
    for el in body:
        sp = _para_sect(el) if el.tag == w("p") else (el if el.tag == w("sectPr") else None)
        if sp is not None:
            if not sects and el.tag == w("p") and prev is not None and prev.tag == w("p"):
                page_break = any(br.get(w("type")) == "page" for br in prev.iter(w("br")))
            sects.append(sp)
        if el.tag == w("p"):
            prev = el
    return sects, page_break


def _drop_part_refs(sect):
    """節の柱・フッタの参照を外す (r:id は reference.docx の関係定義のもので、出力では指す先が違う)。外した数を返す。"""
    n = 0
    for tag in ("headerReference", "footerReference"):
        for ref in sect.findall(w(tag)):
            sect.remove(ref)
            n += 1
    return n


def prepare(profile, reference_doc):
    """profile と reference.docx から段組の設定を作る。働かなければ None (警告は出す)。

    返り値の body_sect は reference.docx の最終の節の写し (bytes。テンプレートから作った reference.docx のとき) か None
    (reference.docx が節を 1 つしか持たない。apply が出力の最終の節から作る)。
    """
    cfg = journal_profile.layout(profile)
    if cfg is None:
        return None
    if not cfg["title_block_until"]:
        print("  警告: layout.columns があるのに layout.title_block_until (表題部の最後の段落のスタイル) がありません。"
              "段組の節を組み立てません")
        return None
    try:
        sects, page_break = _reference_sections(reference_doc)
    except Exception as exc:                                          # noqa: BLE001
        print(f"  警告: {reference_doc} の節を読めませんでした ({exc})。段組の節を組み立てません")
        return None
    cfg = dict(cfg)
    hint = "テンプレートが改版されたなら、テンプレートの値に合わせて profile.yaml の layout を直してください"
    if len(sects) >= 2:
        if len(sects) > 2:
            print(f"  警告: {reference_doc} の本文に節が {len(sects)} つあります (想定は表題部と本文の 2 つ)。"
                  f"最初の節を表題部、最後の節を本文の節として使います。{hint}")
        body_ref = copy.deepcopy(sects[-1])
        n_ref, _ = columns_of(body_ref)
        if n_ref != cfg["columns"]:
            print(f"  警告: layout.columns: profile={cfg['columns']} != reference.docx の本文の節={n_ref}。"
                  f"reference.docx の値を使います。{hint}")
        cols = body_ref.find(w("cols"))
        if cfg["column_space_twip"] is not None and cols is not None:
            got = _int(cols, "space", 720)
            if abs(got - cfg["column_space_twip"]) > 0.1 * TWIP_PER_MM:
                print(f"  警告: layout.column_space: profile={cfg['column_space_twip'] / TWIP_PER_MM:.1f}mm != "
                      f"reference.docx の本文の節={got / TWIP_PER_MM:.1f}mm。reference.docx の値を使います。{hint}")
        # 表題部の節の段数の検査は apply で行う (節の数によらず、出力の表題部の節を見て 1 段組に直す)。
        # ここで節が 2 つ以上のときだけ見ると、節が 1 つで 2 段組のテンプレートでは表題部も黙って 2 段組になるため
        if page_break != cfg["title_page_break"]:
            print(f"  警告: layout.title_page_break: profile={cfg['title_page_break']} だが、reference.docx の表題部の節の前の"
                  f"改ページの段落は{'ある' if page_break else '無い'}。profile の値を使います。{hint}")
        if _drop_part_refs(body_ref):
            print("  注意: reference.docx の本文の節が柱かフッタの参照を持っています。使わずに表題部の節の柱とフッタを引き継ぎます")
        for k in list(body_ref.attrib):
            del body_ref.attrib[k]
        cfg["body_sect"] = etree.tostring(body_ref)
        cfg["source"] = "reference.docx の本文の節"
    else:
        cfg["body_sect"] = None
        cfg["source"] = "profile の layout"
    return cfg


def reference_body_column_twip(profile, reference_doc):
    """reference.docx の本文の節の段の幅 (twip)。読めなければ None。

    式の段落スタイルの右タブ (equations.style) はこの段の幅に合わせてある。段組の節を組み立てない文書 (回答書・カバーレター) でも
    同じ値を使うために、出力の最終の節ではなく reference.docx から取る。本文の節は prepare と同じく reference.docx の最後の節で、
    reference.docx が節を 1 つしか持たず profile に layout があれば、その節を profile の段数と段間にしたもの (_profile_body_sect)。
    """
    try:
        sects, _ = _reference_sections(reference_doc)
    except Exception:                                                  # noqa: BLE001
        return None
    if not sects:
        return None
    body_ref = sects[-1]
    cfg = journal_profile.layout(profile)
    if len(sects) < 2 and cfg is not None:
        body_ref = _profile_body_sect(body_ref, cfg)
    return columns_of(body_ref)[1]


# =====================================================================
# 組み立て
# =====================================================================

def _profile_body_sect(final, cfg):
    """reference.docx が節を 1 つしか持たない誌の本文の節: 出力の最終の節を写し、段数と段間を profile の値にする。"""
    sect = copy.deepcopy(final)
    _drop_part_refs(sect)
    typ = sect.find(w("type"))
    if typ is None:
        typ = docx_styles.sectpr_set(sect, etree.Element(w("type")))
    typ.set(w("val"), "continuous")
    cols = sect.find(w("cols"))
    if cols is None:
        cols = docx_styles.sectpr_set(sect, etree.Element(w("cols")))
    for c in cols.findall(w("col")):
        cols.remove(c)
    cols.attrib.pop(w("equalWidth"), None)
    cols.set(w("num"), str(cfg["columns"]))
    if cfg["column_space_twip"] is not None:
        cols.set(w("space"), str(round(cfg["column_space_twip"])))
    return sect


def _single_column(sect):
    """節の w:cols を 1 段にする (段間の w:space だけを残し、段数・段ごとの幅・区切り線を外す)。"""
    cols = sect.find(w("cols"))
    if cols is None:
        return
    for c in cols.findall(w("col")):
        cols.remove(c)
    for attr in ("num", "equalWidth", "sep"):
        cols.attrib.pop(w(attr), None)


def _one_column_sect(body_sect, title_sect):
    """段抜きの 1 段組の節: 本文の節の写しで、段は表題部の節のもの (1 段)、行番号の位置を段組の節にそろえる。"""
    sect = copy.deepcopy(body_sect)
    cols = sect.find(w("cols"))
    tcols = title_sect.find(w("cols"))
    new = copy.deepcopy(tcols) if tcols is not None and _int(tcols, "num", 1) <= 1 else etree.Element(w("cols"))
    new.tail = cols.tail if cols is not None else None
    docx_styles.sectpr_set(sect, new)
    ln = sect.find(w("lnNumType"))
    if ln is not None and ln.get(w("distance")) is None:
        ln.set(w("distance"), ONE_COLUMN_LN_DISTANCE)
    return sect


def _title_block_end(body, style_id):
    """表題部の最後の段落: 本文で最初に現れる style_id の段落と、それに続く同じスタイルの段落の最後。無ければ None。"""
    last = None
    for el in body:
        if el.tag == w("p") and _pstyle(el) == style_id:
            last = el
        elif last is not None and el.tag in (w("p"), w("tbl"), w("sdt"), w("sectPr")):
            break
    return last


def _set_sect(p, sect):
    ppr = p.find(w("pPr"))
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        p.insert(0, ppr)
    docx_styles.ppr_set(ppr, sect)


def _break_paragraph(sect, form=None):
    """節の区切りだけを持つ空の段落 (BREAK_PARAGRAPH の形)。"""
    form = form or BREAK_PARAGRAPH
    p = etree.Element(w("p"))
    ppr = etree.SubElement(p, w("pPr"))
    if form in ("nonumber", "compact"):
        docx_styles.ppr_set(ppr, etree.Element(w("suppressLineNumbers")))
    if form == "compact":
        sp = etree.Element(w("spacing"))
        for k, v in (("before", "0"), ("after", "0"), ("line", "20"), ("lineRule", "exact")):
            sp.set(w(k), v)
        docx_styles.ppr_set(ppr, sp)
        rpr = etree.Element(w("rPr"))
        for tag in ("sz", "szCs"):
            etree.SubElement(rpr, w(tag)).set(w("val"), "2")
        docx_styles.ppr_set(ppr, rpr)
    docx_styles.ppr_set(ppr, sect)
    return p


_SKIP = {"bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd", "commentRangeStart", "commentRangeEnd"}


def _neighbor(el, step):
    """el の前 (step=-1) / 後 (+1) の、ブックマークなどの目印を飛ばした兄弟。"""
    x = el.getprevious() if step < 0 else el.getnext()
    while x is not None and _local(x) in _SKIP:
        x = x.getprevious() if step < 0 else x.getnext()
    return x


def _convert_wide(body, body_sect, one_col, form):
    """WIDE_START / WIDE_END を節の区切りに置き換える。段抜きにした範囲の数を返す。"""
    n, open_start = 0, None
    for el in list(body):
        text = _marker_text(el)
        if text == "WIDE_START":
            if open_start is not None:                      # 閉じない START (ふつう起きない) は捨てる
                body.remove(open_start)
            open_start = el
            continue
        if text != "WIDE_END":
            continue
        start, end = open_start, el
        open_start = None
        if start is None:
            body.remove(end)
            continue
        last = _neighbor(end, -1)
        if last is None or last is start:                    # 中身の無い範囲
            body.remove(start)
            body.remove(end)
            continue
        prev = _neighbor(start, -1)
        if prev is not None and prev.tag == w("p"):
            if _para_sect(prev) is None:
                _set_sect(prev, copy.deepcopy(body_sect))
        else:
            start.addprevious(_break_paragraph(copy.deepcopy(body_sect), form))
        if last.tag == w("p") and _para_sect(last) is None:
            _set_sect(last, copy.deepcopy(one_col))
        elif last.tag != w("p"):
            last.addnext(_break_paragraph(copy.deepcopy(one_col), form))
        body.remove(start)
        body.remove(end)
        n += 1
    if open_start is not None:
        body.remove(open_start)
    return n


def sections(body):
    """body の子を節ごとに [(sectPr, [子…])] で返す (段落の sectPr はその段落を含む節を閉じる)。"""
    out, cur = [], []
    for el in body:
        if el.tag == w("sectPr"):
            out.append((el, cur))
            cur = []
            continue
        cur.append(el)
        sp = _para_sect(el)
        if sp is not None:
            out.append((sp, cur))
            cur = []
    if cur:
        out.append((None, cur))
    return out


# =====================================================================
# 段の幅の頭打ち (図) と表の幅の見積もり
# =====================================================================

def _in_textbox(el):
    return any(_local(a) == "txbxContent" for a in el.iterancestors())


def _cap_inline(inline, max_emu):
    ext = inline.find(f"{{{WP_NS}}}extent")
    if ext is None:
        return None
    cx, cy = int(ext.get("cx", "0")), int(ext.get("cy", "0"))
    if cx <= max_emu or cx <= 0:
        return None
    ratio = max_emu / cx
    ext.set("cx", str(max_emu))
    ext.set("cy", str(round(cy * ratio)))
    for a_ext in inline.iter(f"{{{A_NS}}}ext"):
        if a_ext.get("cx") is not None and a_ext.get("cy") is not None:
            a_ext.set("cx", str(round(int(a_ext.get("cx")) * ratio)))
            a_ext.set("cy", str(round(int(a_ext.get("cy")) * ratio)))
    return cx, ratio


def _figure_name(inline):
    dp = inline.find(f"{{{WP_NS}}}docPr")
    name = (dp.get("descr") or dp.get("name") or "") if dp is not None else ""
    name = " ".join(name.split())
    return name if len(name) <= 60 else name[:57] + "…"


# 欧文の字幅 (em)。Times New Roman の字幅に近い粗い値で、表の最小幅の見積もりにだけ使う
_NARROW = set(".,:;'!|ijlft")
_MID = set("-()[]/rs\"*")


def _char_em(ch):
    if ch.isdigit():
        return 0.5
    if ch in _NARROW:
        return 0.27
    if ch in _MID:
        return 0.34
    if ch in "mwMW%@":
        return 0.9
    if ch.isupper():
        return 0.68
    if ch.islower():
        return 0.47
    if ch.isspace():
        return 0.25
    return 0.6


def _token_em(tok, hyphenate):
    """折り返せない語の幅 (em)。自動ハイフネーションが効くなら 6 字以上の英字の語は半分で切れるとみなす。"""
    core = tok.strip(".,:;()[]\"'")
    if hyphenate and core.isalpha() and len(core) >= 6:
        half = core[: (len(core) + 1) // 2]
        return sum(_char_em(c) for c in half) + _char_em("-")
    return sum(_char_em(c) for c in tok)


def _font_size_pt(styles_root, style_id):
    """段落スタイル (無ければ既定の段落スタイル) から basedOn を辿った文字の大きさ (pt)。無ければ docDefaults、それも無ければ 10。"""
    if style_id is None:
        dflt = docx_styles.default_style(styles_root, "paragraph")
        style_id = dflt.get(w("styleId")) if dflt is not None else None
    seen = set()
    while style_id and style_id not in seen:
        seen.add(style_id)
        st = docx_styles.style_by_id(styles_root, style_id)
        if st is None:
            break
        sz = st.find(f"{w('rPr')}/{w('sz')}")
        if sz is not None and sz.get(w("val")):
            return int(sz.get(w("val"))) / 2
        b = st.find(w("basedOn"))
        style_id = b.get(w("val")) if b is not None else None
    sz = styles_root.find(f"{w('docDefaults')}/{w('rPrDefault')}/{w('rPr')}/{w('sz')}")
    return int(sz.get(w("val"))) / 2 if sz is not None else 10.0


def _cell_margins(tbl, styles_root):
    """表のセルの左右の余白 (twip)。表・表スタイル・既定の表スタイルの順に探し、無ければ Word の既定 108 ずつ。"""
    def find_in(tblpr):
        if tblpr is None:
            return None
        mar = tblpr.find(w("tblCellMar"))
        if mar is None:
            return None
        # lxml の要素は子が無いと偽になるので `or` でつながない
        l = mar.find(w("left")) if mar.find(w("left")) is not None else mar.find(w("start"))
        r = mar.find(w("right")) if mar.find(w("right")) is not None else mar.find(w("end"))
        if l is None and r is None:
            return None
        return _int(l, "w", 108) + _int(r, "w", 108)
    got = find_in(tbl.find(w("tblPr")))
    if got is not None:
        return got
    ts = tbl.find(f"{w('tblPr')}/{w('tblStyle')}")
    sid = ts.get(w("val")) if ts is not None else None
    seen = set()
    while sid and sid not in seen:
        seen.add(sid)
        st = docx_styles.style_by_id(styles_root, sid)
        if st is None:
            break
        got = find_in(st.find(w("tblPr")))
        if got is not None:
            return got
        b = st.find(w("basedOn"))
        sid = b.get(w("val")) if b is not None else None
    dflt = docx_styles.default_style(styles_root, "table")
    got = find_in(dflt.find(w("tblPr"))) if dflt is not None else None
    return got if got is not None else 216


def table_min_width_twip(tbl, styles_root, hyphenate):
    """表の最小幅の見積もり (twip): 各列の「折り返せない語」の最大幅 + セルの左右の余白 の合計。列が分からなければ None。"""
    widths = {}
    margin = _cell_margins(tbl, styles_root)
    for tr in tbl.findall(w("tr")):
        col = 0
        for tc in tr.findall(w("tc")):
            span = _int(tc.find(f"{w('tcPr')}/{w('gridSpan')}"), "val", 1)
            if span == 1:
                best = 0.0
                for p in tc.iter(w("p")):
                    size = _font_size_pt(styles_root, _pstyle(p))
                    text = "".join((t.text or "") if _local(t) == "t" else " "
                                   for t in p.iter(w("t"), w("tab"), w("br")))
                    for tok in re.split(r"[ \t\r\n]+", text):
                        if tok:
                            best = max(best, _token_em(tok, hyphenate) * size * 20)
                widths[col] = max(widths.get(col, 0.0), best)
            col += span
    if not widths:
        return None
    return sum(widths.values()) + margin * len(widths)


def _table_name(tbl):
    cap = tbl.find(f"{w('tblPr')}/{w('tblCaption')}")
    name = cap.get(w("val")) if cap is not None else ""
    name = " ".join((name or "").split()) or "(題の無い表)"
    return name if len(name) <= 60 else name[:57] + "…"


def check_widths(body, styles_root, hyphenate):
    """段組の節の図を段の幅に縮め、表の最小幅の見積もりが段 (1 段組なら本文幅) を超えるものを数える。

    返り値: (縮めた図 [(名前, 元の幅 mm, 倍率)], 収まらない見込みの表 [(名前, 見積もり mm, 使える幅 mm, 段組か)])
    """
    capped, wide_tables = [], []
    for sect, elems in sections(body):
        if sect is None:
            continue
        n, colw = columns_of(sect)
        if colw is None:
            continue
        max_emu = int(colw * EMU_PER_TWIP)
        for el in elems:
            if n > 1:
                for inline in el.iter(f"{{{WP_NS}}}inline"):
                    if _in_textbox(inline):
                        continue
                    got = _cap_inline(inline, max_emu)
                    if got:
                        capped.append((_figure_name(inline), got[0] / 36000, got[1]))
            tbls = [el] if el.tag == w("tbl") else []
            for tbl in tbls:
                est = table_min_width_twip(tbl, styles_root, hyphenate)
                if est is not None and est > colw:
                    wide_tables.append((_table_name(tbl), est / TWIP_PER_MM, colw / TWIP_PER_MM, n > 1))
    return capped, wide_tables


def _auto_hyphenation(parts):
    """settings.xml で自動ハイフネーションが有効か (表の最小幅の見積もりで、長い英字の語を切れるとみなすか)。"""
    data = parts.get("word/settings.xml")
    if not data:
        return False
    el = etree.fromstring(data).find(w("autoHyphenation"))
    return el is not None and el.get(w("val"), "true") not in ("0", "false", "off")


# =====================================================================
# 入口
# =====================================================================

def apply(parts, root, cfg, break_form=None):
    """段組の節を組み立てる (root = word/document.xml のルート。parts の他のパートは読むだけ)。組み立てたら True。"""
    body = root.find(w("body"))
    final = body.find(w("sectPr")) if body is not None else None
    if final is None:
        print("  警告: 本文の最終の節 (w:sectPr) がありません。段組の節を組み立てません")
        strip_markers(root)
        return False
    styles_root = etree.fromstring(parts["word/styles.xml"])
    until = cfg["title_block_until"]
    sid = docx_styles.style_id_by_name(styles_root, until, "paragraph")
    end_p = _title_block_end(body, sid) if sid else None
    if end_p is None:
        print(f"  警告: 表題部の最後の段落 (段落スタイル '{until}'。layout.title_block_until) が本文にありません。"
              "段組の節を組み立てません (1 段組のまま)")
        strip_markers(root)
        return False

    # 表題部の中の段抜きの目印は使えない (表題部はもともと 1 段組)
    dropped = 0
    for el in list(body):
        if _is_wide_marker(el):
            body.remove(el)
            dropped += 1
        if el is end_p:
            break
    if dropped:
        print(f"  警告: 表題部の中の .wide ({(dropped + 1) // 2} か所) は無視します (表題部はもともと 1 段組)")

    if cfg.get("body_sect"):
        body_sect = etree.fromstring(cfg["body_sect"])
    else:
        body_sect = _profile_body_sect(final, cfg)

    # 表題部の節 = pandoc が写した最終の節 (柱とフッタの参照つき)。行番号は外す (本文の節だけ)
    title_sect = final
    for ln in title_sect.findall(w("lnNumType")):
        title_sect.remove(ln)
    # 表題部の節の段数を (reference.docx の節の数によらず) 確かめ、2 段組以上なら 1 段組に直して警告する。
    # 節が 1 つで 2 段組の雛形では、pandoc が写す節 = 本文の 2 段組の節なので、直さないと表題部まで 2 段組になる
    # (直さないと、下の「表題部 … を 1 段組」の表示が事実と違ってしまう)
    n_title, _ = columns_of(title_sect)
    if n_title != 1:
        _single_column(title_sect)
        origin = ("reference.docx の最初の節" if cfg.get("body_sect")
                  else "reference.docx のただ 1 つの節。表題部と本文の節の区別が無い")
        print(f"  警告: 表題部の節 ({origin}) が {n_title} 段組だったので、1 段組に直しました (想定は 1 段組)。"
              "テンプレートが改版されたなら、出力の表題部と profile.yaml の layout を確かめてください")
    body.replace(final, body_sect)
    anchor = end_p
    if cfg["title_page_break"]:
        pb = etree.Element(w("p"))
        etree.SubElement(etree.SubElement(pb, w("r")), w("br")).set(w("type"), "page")
        anchor.addnext(pb)
        anchor = pb
    sp = etree.Element(w("p"))
    etree.SubElement(sp, w("pPr")).append(title_sect)
    anchor.addnext(sp)

    one_col = _one_column_sect(body_sect, title_sect)
    n_wide = _convert_wide(body, body_sect, one_col, break_form)
    # 節に置き換えられなかった目印 (本文の直下に無いもの) は消す。wide-blocks.lua は本文の流れの上にしか置かないので、ふつうは無い
    left = strip_markers(root)
    if left:
        print(f"  警告: 段抜きの目印 {left} 個を本文の流れの上に見つけられず、段抜きにしませんでした")

    capped, wide_tables = check_widths(body, styles_root, _auto_hyphenation(parts))

    n_cols, colw = columns_of(body_sect)
    colw_txt = f"段の幅 {colw / TWIP_PER_MM:.1f} mm" if colw else "段の幅 不明"
    print(f"  段組: 表題部 ('{until}' まで{'・改ページ' if cfg['title_page_break'] else ''}) を 1 段組、本文を {n_cols} 段組に "
          f"({colw_txt}。本文の節 = {cfg['source']})。段抜き {n_wide} か所")
    for name, mm, ratio in capped:
        print(f"  警告: 図 '{name}' の幅 {mm:.1f} mm が段の幅を超えるので、縦横比を保って段の幅に縮めました "
              f"(図の中の文字も {ratio:.0%} になります)。本文幅で置くなら、原稿の図に {{.wide}} を付けてください")
    for name, est, avail, in_cols in wide_tables:
        if in_cols:
            print(f"  警告: 表 '{name}' は段の幅 ({avail:.1f} mm) に収まらない見込みです (折り返せない語から見積もった最小幅 {est:.1f} mm)。"
                  "Word は段の幅に押し込むので、数字などがセルの中で割れて読めなくなります。"
                  "表を ::: wide の Div で囲むと段抜き (本文幅) になります")
        else:
            print(f"  警告: 表 '{name}' は本文幅 ({avail:.1f} mm) にも収まらない見込みです (見積もりの最小幅 {est:.1f} mm)。"
                  "列を減らすか、表を分けてください")
    return True
