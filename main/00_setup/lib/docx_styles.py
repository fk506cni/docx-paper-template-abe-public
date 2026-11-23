#!/usr/bin/env python3
"""docx_styles.py — docx の styles.xml のスタイルを【名前】で扱う共通部。

雑誌が配るテンプレート (ABE の ABETemplate.docx など) は和文の Word で作られていることがあり、
スタイル ID が日本語版の自動 ID (`a` = Normal / `a0` = Body Text / `1` = heading 1 / `ae` = caption) になる。
pandoc は reference.docx のスタイルを名前で引いて ID を合わせるので、出力の pStyle もこの ID になる。
後処理が ID を決め打ちすると、こうしたテンプレートから作った docx では空振りする。
そこで、テンプレート由来の docx を扱う処理は**スタイル名から ID を引く**。その関数をここに 1 つだけ置く。

名前の照合は大文字と小文字を区別しない。Word は組み込みのスタイル名を小文字 (`heading 1` / `caption` /
`footnote text`) で styles.xml に書き、pandoc は `Heading 1` / `Caption` / `Footnote Text` の名前で引いて一致させる。

コンテナ内 (docx-paper-template-pandoc; lxml 同梱) で使う。
"""

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def w(tag):
    return f"{{{W}}}{tag}"


def _norm(name):
    return (name or "").strip().lower()


def styles_of(styles_root, style_type=None):
    """styles.xml の w:style を返す (style_type を渡せば paragraph / character / table / numbering で絞る)。"""
    return [st for st in styles_root.findall(w("style"))
            if style_type is None or st.get(w("type")) == style_type]


def style_name(style):
    """w:style の名前 (w:name/@w:val) を返す。無ければ None。"""
    n = style.find(w("name"))
    return n.get(w("val")) if n is not None else None


def style_by_name(styles_root, name, style_type=None):
    """名前 (大文字と小文字を区別しない) が一致する w:style を返す。無ければ None。

    同じ名前のスタイルが 2 つ以上あると、どれを pandoc や Word が使うかが定まらないので止める。
    """
    hits = [st for st in styles_of(styles_root, style_type) if _norm(style_name(st)) == _norm(name)]
    if len(hits) > 1:
        ids = ", ".join(st.get(w("styleId")) or "?" for st in hits)
        raise RuntimeError(f"styles.xml にスタイル名 '{name}' が {len(hits)} 個あります (ID: {ids})")
    return hits[0] if hits else None


def style_id_by_name(styles_root, name, style_type=None):
    """名前 (大文字と小文字を区別しない) からスタイル ID を引く。無ければ None。"""
    st = style_by_name(styles_root, name, style_type)
    return st.get(w("styleId")) if st is not None else None


def style_by_id(styles_root, style_id):
    """スタイル ID が一致する w:style を返す。無ければ None。"""
    for st in styles_root.findall(w("style")):
        if st.get(w("styleId")) == style_id:
            return st
    return None


def style_ids(styles_root):
    """定義されているスタイル ID の集合。"""
    return {st.get(w("styleId")) for st in styles_root.findall(w("style"))}


def default_style(styles_root, style_type="paragraph"):
    """その種類の既定のスタイル (w:default="1") を返す。無ければ None。"""
    for st in styles_of(styles_root, style_type):
        if st.get(w("default")) in ("1", "true", "on"):
            return st
    return None


def undefined_based_on(styles_root):
    """basedOn / next / link が未定義の ID を指すスタイルを [(スタイル ID, 要素名, 指す先)] で返す。

    pandoc は reference.docx に無い custom-style の段落スタイルを basedOn="BodyText" で自動定義する。
    雛形の Body Text の ID が BodyText でないと基が無いことになり、Word は文書の既定の大きさ (10 pt) で描く。
    出力にこの形が残っていないかを確かめるのに使う。
    """
    ids = style_ids(styles_root)
    out = []
    for st in styles_root.findall(w("style")):
        for tag in ("basedOn", "next", "link"):
            el = st.find(w(tag))
            if el is not None and el.get(w("val")) not in ids:
                out.append((st.get(w("styleId")), tag, el.get(w("val"))))
    return out


# CT_PPr (段落の書式) の子要素の並び (ECMA-376 Part 1 §17.3.1.26)。w:pPr に要素を足すときはこの順を守る
# (順序が崩れた docx も Word は開くことが多いが、検証器や他の実装が拒むことがある)
PPR_ORDER = (
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
    "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
    "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc",
    "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
)

# CT_Style の子要素の並び (§17.7.4.17)。w:style に w:pPr を足すときの位置を決める
STYLE_ORDER = (
    "name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden", "uiPriority",
    "semiHidden", "unhideWhenUsed", "qFormat", "locked", "personal", "personalCompose",
    "personalReply", "rsid", "pPr", "rPr", "tblPr", "trPr", "tcPr", "tblStylePr",
)


def _insert_ordered(parent, el, order):
    """parent の子を order の並びに保って el を足す。同名の子があれば置き換える。"""
    name = etree.QName(el).localname
    old = parent.find(w(name))
    if old is not None:
        parent.replace(old, el)
        return el
    rank = order.index(name)
    for k, child in enumerate(parent):
        if not isinstance(child.tag, str):
            continue
        cname = etree.QName(child).localname
        if cname in order and order.index(cname) > rank:
            parent.insert(k, el)
            return el
    parent.append(el)
    return el


def ppr_set(ppr, el):
    """w:pPr に el を CT_PPr の順序で足す (同名があれば置き換える)。"""
    return _insert_ordered(ppr, el, PPR_ORDER)


# CT_RPr (文字の書式) の子要素の並び (§17.3.2.28 の EG_RPrBase と rPrChange)。w:rPr に要素を足すときはこの順を守る
# (差分の脚注の参照に色と取消線を直に付けるときに使う)
RPR_ORDER = (
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline", "shadow",
    "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern",
    "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs",
    "em", "lang", "eastAsianLayout", "specVanish", "oMath", "rPrChange",
)


def rpr_set(rpr, el):
    """w:rPr に el を CT_RPr の順序で足す (同名があれば置き換える)。"""
    return _insert_ordered(rpr, el, RPR_ORDER)


# CT_SectPr (節の書式) の子要素の並び (§17.6.17)。柱とフッタの参照 (headerReference / footerReference) は先頭に何個でも並ぶので
# 1 つに置き換える用途には使わない (sectpr_set はそれ以外の要素に使う)。段組の節を組み立てるときに使う
SECTPR_ORDER = (
    "headerReference", "footerReference", "footnotePr", "endnotePr", "type", "pgSz", "pgMar", "paperSrc",
    "pgBorders", "lnNumType", "pgNumType", "cols", "formProt", "vAlign", "noEndnote", "titlePg",
    "textDirection", "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange",
)


def sectpr_set(sect, el):
    """w:sectPr に el を CT_SectPr の順序で足す (同名があれば置き換える)。"""
    return _insert_ordered(sect, el, SECTPR_ORDER)


def style_ppr(style):
    """w:style の w:pPr を返す。無ければ CT_Style の順序の位置に作って返す。"""
    ppr = style.find(w("pPr"))
    if ppr is None:
        ppr = _insert_ordered(style, etree.Element(w("pPr")), STYLE_ORDER)
    return ppr
