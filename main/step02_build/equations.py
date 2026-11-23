#!/usr/bin/env python3
"""equations.py — 番号つきの別行立て数式を「式 TAB (1)」の形にする後処理 (build / diff 共用)。

pandoc-crossref は番号つきの式 (`$$ … $$ {#eq:x}`) の番号を式の中に足す (`… \\qquad{(1)}`)。pandoc の docx では
式は段落の中の m:oMathPara (中央揃えの別行立て) になり、番号は式のすぐ右に付いて式と一緒に段・本文の中央に寄る。
雑誌のテンプレートが式の段落スタイル (ABE の学会テンプレートの Equation: 右タブ 4 678 twip ≒ 段の幅) を持ち、
「式 TAB (1)」で番号を右端に寄せる誌のために、誌の profile の equations.style で次の形に組み替える
(docs/journal-abe.md §11.3。Word 実機で確かめたテンプレートの見本と同じ形):

  <w:p><w:pPr><w:pStyle w:val="(equations.style の ID)"/></w:pPr><w:bookmarkStart w:name="eq:x"/>
       <m:oMath>…(式)…</m:oMath><w:r><w:tab/></w:r><w:r><w:t>(1)</w:t></w:r><w:bookmarkEnd/></w:p>

- 対象は pandoc-crossref の式のラベル (`eq:` で始まるブックマーク) を持ち、中身が m:oMathPara 1 つだけの段落。
  番号は m:oMath の直下の末尾の「空白だけの m:r (\\qquad) + 番号の m:r の並び」から取り、`(…)` の形でなければ警告して触らない
- 番号の無い別行立ての式 (`$$ … $$` だけ) は変えない (中央揃えの m:oMathPara のまま)
- 番号の w:r には書式を付けない (テンプレートの見本どおり、段落スタイルの書体になる)。ただし差分 docx では、外した番号の m:r が持つ
  削除・追加の書式 (w:rPr) を移す
- 右タブの位置: スタイルの右タブは本文の節の段の幅に合わせてある。段の幅の違う節 (段抜きの 1 段組の節・表題部の節・
  段組の節を組み立てない 1 段組の文書 (回答書・カバーレター) の節。本文の節の段の幅は reference.docx から取る) の式には、
  段の幅の差だけずらした右タブを段落に足す (段落の w:tabs でスタイルのタブを消して置き直す)。スタイルに右タブが無ければ、
  どの節の式にも段の幅の位置の右タブを足す。テキストボックスの中の式は位置を変えない (箱の幅は節と関係が無い)

段組の節の組み立て (layout.py) の**後**に掛ける (式の節を知るため)。既定 (equations.style が無い誌) では呼ばれない。

コンテナ内 (docx-paper-template-pandoc; lxml 同梱) で使う。
"""

import copy
import re
import sys
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
import docx_styles  # noqa: E402

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
w = docx_styles.w
_SKIP = {"bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd", "commentRangeStart", "commentRangeEnd"}
_NUMBER = re.compile(r"\(\s*([^()\s]+)\s*\)")


def m(tag):
    return f"{{{M_NS}}}{tag}"


def _local(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def _mtext(el):
    return "".join(t.text or "" for t in el.iter(m("t")))


def _eq_label(p):
    """段落の中の pandoc-crossref の式のラベル (eq: で始まるブックマーク名)。無ければ None。"""
    for bm in p.findall(w("bookmarkStart")):
        name = bm.get(w("name")) or ""
        if name.startswith("eq:"):
            return name
    return None


def _number_tail(omath):
    """m:oMath の末尾の「空白だけの m:r + 番号」を (外す m:r の一覧, '(1)') で返す。形が違えば None。"""
    kids = [k for k in omath if isinstance(k.tag, str)]
    ws = [i for i, k in enumerate(kids) if k.tag == m("r") and _mtext(k) and not _mtext(k).strip()]
    if not ws:
        return None
    k = ws[-1]
    tail = kids[k + 1:]
    if not tail or any(x.tag != m("r") for x in tail):
        return None
    mt = _NUMBER.fullmatch("".join(_mtext(x) for x in tail).strip())
    if not mt:
        return None
    return kids[k:], f"({mt.group(1)})"


def convert(root, style_id):
    """番号つきの式の段落を「式 TAB 番号」の形にする。([組み替えた段落], [組み替えなかった式のラベル]) を返す。"""
    done, skipped = [], []
    for p in list(root.iter(w("p"))):
        label = _eq_label(p)
        if label is None:
            continue
        content = [k for k in p if isinstance(k.tag, str) and _local(k) not in _SKIP and k.tag != w("pPr")]
        if len(content) != 1 or content[0].tag != m("oMathPara"):
            continue                                   # 式だけの段落でない (pandoc は別行立ての式を段落に分けるので、ふつう無い)
        omp = content[0]
        maths = omp.findall(m("oMath"))
        tail = _number_tail(maths[0]) if len(maths) == 1 else None
        if tail is None:
            skipped.append(label)
            continue
        runs, number = tail
        om = maths[0]
        # 外す番号の m:r が持つ w:rPr (差分 docx の削除・追加の書式。diff_docx._color_diff_marks が付ける) を番号の w:r に移す
        # (書式の無い w:r を作ると、書き換えた・足した式の番号が差分の色を失う)。build の番号の m:r は
        # w:rPr を持たないので、build では書式なしのまま
        num_rpr = next((r.find(w("rPr")) for r in runs[1:] if r.find(w("rPr")) is not None), None)
        for r in runs:
            om.remove(r)
        omp.addprevious(om)                            # 段落の直下の m:oMath にする (テンプレートの見本の形)
        p.remove(omp)
        ppr = p.find(w("pPr"))
        if ppr is None:
            ppr = etree.Element(w("pPr"))
            p.insert(0, ppr)
        ps = etree.Element(w("pStyle"))
        ps.set(w("val"), style_id)
        docx_styles.ppr_set(ppr, ps)
        r_tab = etree.Element(w("r"))
        etree.SubElement(r_tab, w("tab"))
        r_num = etree.Element(w("r"))
        if num_rpr is not None:
            r_num.append(copy.deepcopy(num_rpr))
        etree.SubElement(r_num, w("t")).text = number
        om.addnext(r_tab)
        r_tab.addnext(r_num)
        done.append(p)
    return done, skipped


def _style_right_tab(styles_root, style):
    """段落スタイル (basedOn をたどる) の右タブの位置 (twip)。無ければ None。近いほうの指定が勝つ。"""
    seen = set()
    st = style
    while st is not None and st.get(w("styleId")) not in seen:
        seen.add(st.get(w("styleId")))
        tabs = st.find(f"{w('pPr')}/{w('tabs')}")
        if tabs is not None:
            rights = [int(t.get(w("pos"))) for t in tabs.findall(w("tab"))
                      if t.get(w("val")) == "right" and (t.get(w("pos")) or "").lstrip("-").isdigit()]
            if rights:
                return max(rights)
        based = st.find(w("basedOn"))
        st = docx_styles.style_by_id(styles_root, based.get(w("val"))) if based is not None else None
    return None


def _section_of(body):
    """body の直下の子 → その子を含む節の sectPr の対応 (段落の sectPr はその段落を含む節を閉じる)。"""
    out, pending = {}, []
    for el in body:
        if el.tag == w("sectPr"):
            for x in pending:
                out[x] = el
            pending = []
            continue
        pending.append(el)
        sp = el.find(f"{w('pPr')}/{w('sectPr')}") if el.tag == w("p") else None
        if sp is not None:
            for x in pending:
                out[x] = sp
            pending = []
    return out


def fit_tabs(root, styles_root, paras, style, body_colw=None):
    """式の段落の右タブを、式のある節の段の幅に合わせる。位置を変えた段落の数を返す。

    body_colw: スタイルの右タブが合わせてある段の幅 (twip) = reference.docx の本文の節の段の幅 (layout.reference_body_column_twip)。
    None なら出力の最終の節の段の幅を使う。最終の節をいつも本文の段組の節とみなすと、段組の節を組み立てない 1 段組の文書
    (回答書・カバーレター) では、番号が本文幅 180 mm の文書の中で段の幅の位置 (約 83 mm) に残るため、reference.docx から渡す。
    """
    import layout                                       # 節の寸法 (段数・段の幅) は layout.py の読み方を使う

    body = root.find(w("body"))
    final = body.find(w("sectPr")) if body is not None else None
    if final is None:
        return 0
    if body_colw is None:
        _, body_colw = layout.columns_of(final)
    style_tab = _style_right_tab(styles_root, style)
    if body_colw is None:
        return 0
    sect_of = _section_of(body)
    n = 0
    for p in paras:
        if any(_local(a) == "txbxContent" for a in p.iterancestors()):
            continue
        top = p
        while top.getparent() is not body:
            top = top.getparent()
        sect = sect_of.get(top)
        if sect is None:
            continue
        _, colw = layout.columns_of(sect)
        if colw is None:
            continue
        if style_tab is not None:
            if abs(colw - body_colw) < 1:
                continue                                 # 本文の節と同じ段の幅 (スタイルのタブのまま)
            pos = style_tab + (colw - body_colw)
        else:
            pos = colw
        tabs = etree.Element(w("tabs"))
        if style_tab is not None:
            clear = etree.SubElement(tabs, w("tab"))
            clear.set(w("val"), "clear")
            clear.set(w("pos"), str(style_tab))
        tab = etree.SubElement(tabs, w("tab"))
        tab.set(w("val"), "right")
        tab.set(w("pos"), str(int(round(pos))))
        docx_styles.ppr_set(p.find(w("pPr")), tabs)
        n += 1
    return n


def apply(parts, root, style_name, body_column_twip=None):
    """番号つきの式を equations.style の段落スタイルで「式 TAB (1)」の形にする (root = word/document.xml のルート)。

    body_column_twip: reference.docx の本文の節の段の幅 (twip。fit_tabs の body_colw)。"""
    styles_root = etree.fromstring(parts["word/styles.xml"])
    style = docx_styles.style_by_name(styles_root, style_name, "paragraph")
    if style is None:
        has_eq = any(_eq_label(p) for p in root.iter(w("p")))
        if has_eq:
            print(f"  警告: equations.style の段落スタイル '{style_name}' が reference.docx にありません。"
                  "番号つきの式は従来の形 (番号は式のすぐ右・中央揃え) のままにします")
        return
    done, skipped = convert(root, style.get(w("styleId")))
    if not done and not skipped:
        return
    moved = fit_tabs(root, styles_root, done, style, body_column_twip) if done else 0
    extra = f" (うち段の幅の違う節の {moved} 件はタブの位置を節に合わせた)" if moved else ""
    print(f"  式番号: 番号つきの式 {len(done)} 件を '{style_name}' の「式 TAB 番号」にした{extra}")
    if skipped:
        print(f"  警告: 番号つきの式 {', '.join(skipped)} は番号の形 (式の末尾の空白 + `(番号)`) を見つけられないので、"
              "従来の形 (番号は式のすぐ右・中央揃え) のままにします")
