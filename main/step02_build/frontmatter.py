#!/usr/bin/env python3
"""frontmatter.py — 前付けと見出しの後処理: 柱 (ヘッダ) の running title と、所属の番号の後のタブ (build / diff 共用)、
本文以外の文書の見出しの自動番号の除去 (build)、著者の脚注の記号 (build / diff 共用)。

雑誌が配るテンプレートの体裁と規定に合わせるための 4 つの処理を置く。どれも誌の profile のキーで発火し、既定では呼ばれない
(キーを持たない誌の出力は変わらない)。

1. 柱 (apply_running_header。profile の `header.*`)
2. 所属の番号の後のタブ (apply_affiliation_tabs。profile の `title_page.affiliation_label_tab`。説明は関数の docstring)
3. 本文以外の文書の見出しの自動番号を外す (suppress_heading_numbers。profile の `headings.numbered_scope`。
   説明は関数の docstring)
4. 著者の脚注 (異動後の新住所) を記号にする (apply_author_footnote_marks。profile の `title_page.author_footnote_marks`。
   説明は関数の docstring)

■ 1. 柱
雑誌が配るテンプレートの柱が「左 TAB 中央 TAB 右」の 1 段落で、中央を論文の running title に置き換えるよう
指示している誌のための処理 (ABE の学会テンプレートは `distributed` TAB `Template for ABE` TAB `ver.3`。
docs/journal-abe.md §8.1)。誌の profile の `header.*` で発火し、既定 (どちらも未指定) では呼ばれない。

  header.running_title_from    custom-style の名前 (例 Subtitle)。その段落スタイルの最初の段落の文字列を柱の中央に入れる。
                               その段落が無い文書 (カバーレター・回答書。本文と同じ reference.docx で build する) では中央を空にする
                               (テンプレートの見本の文字 `Template for ABE` を残さない)
  header.clear_template_labels 真なら左右の文字も消す。偽なら左右はテンプレートのまま

【区切りの判定】テンプレートの柱の文字は複数の w:r に分かれ、タブも文字と同じ w:r の中にある (`<w:r><w:tab/><w:t>Template </w:t></w:r>`)。
w:r の単位ではなく、段落の中の文字とタブの並び (トークン) で左・中央・右を区切る。柱の形が想定と違う
(文字のある段落が 2 つ以上・タブが 2 個でない・フィールドや図など文字とタブ以外のものがある) なら、警告して触らない
(テンプレートの改版の検知を兼ねる)。段落の書式 (w:pPr。ABE は header スタイル + 斜体) はそのまま残す。

【差し替えた後の形】docs/journal-abe.md §11.3 の「柱」(Word 実機で確かめた形)。左右を消すときは
`<w:r><w:rPr>(中央の文字の書式)</w:rPr><w:tab/><w:t>running title</w:t></w:r>` の 1 つの w:r にする。
中央の文字の書式から `w:rFonts/@w:hint="eastAsia"` は外す — この指定があると、引用符・ダッシュ・省略記号のように
欧文と和文で共有する文字が和文の書体で描かれる (テンプレートの見本の文字は ASCII だけなので表に出ないが、
running title には `’` や `–` が入りうる)。

【差分 docx】running title の段落に削除 (文字スタイル DiffDel) と追加 (DiffAdd) の文字が両方入るので、削除の文字を除いた
文字列 (= 新版の running title) を柱に使う。変更履歴の削除 (w:del / w:moveFrom) の中の文字も除く。

【柱のパート】本文の全ての w:sectPr の w:headerReference が指すパートを扱う (ヘッダの rId は pandoc の出力で振り直されるので
関係定義から引く。段組で節が増えても、柱を持つ節がどれでも同じパートを指す)。文字の無いヘッダ (空のヘッダ) は何もしない。

コンテナ内 (docx-paper-template-pandoc; lxml 同梱) で使う。
"""

import re
import sys
from copy import deepcopy
from pathlib import Path, PurePosixPath

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
import docx_styles  # noqa: E402

W_NS = docx_styles.W
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_HEADER = R_NS + "/header"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

w = docx_styles.w

# 削除の文字スタイル (差分。color-diff.lua → diff_docx.py の注入)。ID はふつう名前と同じだが、名前でも引く
DEL_STYLE_NAME = "DiffDel"
# 文字として数えない run の子 (書式・改ページの目印・脚注の参照など)。w:t / w:tab / w:br / w:cr / w:noBreakHyphen 以外は読み飛ばす
_TEXT_LIKE = {"t": None, "tab": " ", "br": " ", "cr": " ", "noBreakHyphen": "-"}
# 柱の段落の中で読み飛ばしてよい子 (中身を持たない目印)
_SKIP_IN_P = {"pPr", "proofErr", "bookmarkStart", "bookmarkEnd", "permStart", "permEnd"}
_SKIP_IN_R = {"rPr", "lastRenderedPageBreak"}
# これがあると「文字のある段落」とみなす (形の判定で数える)
_CONTENT = {"t", "tab", "fldChar", "fldSimple", "instrText", "drawing", "pict", "object", "sym", "ptab"}


def _local(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def _owner_p(el):
    """el を直接含む (いちばん近い) w:p を返す。"""
    return next(el.iterancestors(w("p")), None)


def _in_deleted(r, p):
    """r が p の中の変更履歴の削除 (w:del / w:moveFrom) の中にあるか。"""
    for anc in r.iterancestors():
        if anc is p:
            return False
        if _local(anc) in ("del", "moveFrom"):
            return True
    return False


def visible_text(p, del_style_ids=()):
    """段落 p の文字列 (削除の文字を除く。タブと改行は空白、空白は 1 つにまとめる)。"""
    out = []
    for r in p.iter(w("r")):
        if _owner_p(r) is not p or _in_deleted(r, p):
            continue
        rs = r.find(f"{w('rPr')}/{w('rStyle')}")
        if rs is not None and rs.get(w("val")) in del_style_ids:
            continue
        for ch in r:
            name = _local(ch)
            if name == "t":
                out.append(ch.text or "")
            elif name in _TEXT_LIKE:
                out.append(_TEXT_LIKE[name])
    return " ".join("".join(out).split())


def running_title_text(doc_root, styles_root, style_name):
    """段落スタイル style_name (名前) の最初の段落の文字列を返す。その段落が無ければ None。"""
    sid = docx_styles.style_id_by_name(styles_root, style_name, "paragraph")
    if sid is None:
        return None
    del_ids = {DEL_STYLE_NAME}
    del_id = docx_styles.style_id_by_name(styles_root, DEL_STYLE_NAME, "character")
    if del_id:
        del_ids.add(del_id)
    body = doc_root.find(w("body"))
    for p in (body if body is not None else doc_root).iter(w("p")):
        ps = p.find(f"{w('pPr')}/{w('pStyle')}")
        if ps is not None and ps.get(w("val")) == sid:
            return visible_text(p, del_ids)
    return None


def header_parts(parts, doc_root):
    """本文の w:sectPr の w:headerReference が指すヘッダのパート名を、出てきた順に重複なく返す。"""
    rels_name = "word/_rels/document.xml.rels"
    if rels_name not in parts:
        return []
    rels = etree.fromstring(parts[rels_name])
    targets = {}
    for rel in rels.findall(f"{{{REL_NS}}}Relationship"):
        if rel.get("Type") == REL_HEADER and rel.get("TargetMode") != "External":
            tgt = rel.get("Target") or ""
            name = tgt.lstrip("/") if tgt.startswith("/") else str(PurePosixPath("word") / tgt)
            targets[rel.get("Id")] = name
    out = []
    for sect in doc_root.iter(w("sectPr")):
        for ref in sect.findall(w("headerReference")):
            name = targets.get(ref.get(f"{{{R_NS}}}id"))
            if name and name in parts and name not in out:
                out.append(name)
    return out


def _has_content(p):
    for el in p.iter():
        name = _local(el)
        if name in _CONTENT and not (name == "t" and not (el.text or "")):
            return True
    return False


def _tokens(p):
    """段落を [(w:rPr または None, 'text' | 'tab', 文字)] の並びにする。文字とタブ以外のものがあれば None。"""
    toks = []
    for child in p:
        name = _local(child)
        if name is None or name in _SKIP_IN_P:
            continue
        if name != "r":
            return None
        rpr = child.find(w("rPr"))
        for ch in child:
            cname = _local(ch)
            if cname is None or cname in _SKIP_IN_R:
                continue
            if cname == "t":
                if ch.text:
                    toks.append((rpr, "text", ch.text))
            elif cname == "tab":
                toks.append((rpr, "tab", "\t"))
            else:
                return None
    return toks


def _clean_rpr(rpr):
    """新しく書く running title の文字の書式: 中央の文字の書式の写しから rFonts の hint を外す (空になれば None)。"""
    if rpr is None:
        return None
    rpr = deepcopy(rpr)
    for rf in rpr.findall(w("rFonts")):
        rf.attrib.pop(w("hint"), None)
        if not rf.attrib and len(rf) == 0:
            rpr.remove(rf)
    return rpr if len(rpr) else None


def _rpr_key(rpr):
    return etree.tostring(rpr) if rpr is not None else b""


def _write_tokens(p, toks):
    """p の中身 (w:pPr 以外) を toks で書き直す。書式の同じ隣り合うトークンは 1 つの w:r にまとめる。"""
    for child in list(p):
        if _local(child) != "pPr":
            p.remove(child)
    run, key = None, None
    for rpr, kind, text in toks:
        k = _rpr_key(rpr)
        if run is None or k != key:
            run = etree.SubElement(p, w("r"))
            if rpr is not None:
                run.append(deepcopy(rpr))
            key = k
        if kind == "tab":
            etree.SubElement(run, w("tab"))
        else:
            t = etree.SubElement(run, w("t"))
            t.text = text
            if text != text.strip() or "  " in text:
                t.set(XML_SPACE, "preserve")


def rewrite_header(hdr_root, title, replace_center, clear_labels):
    """ヘッダ 1 つを書き換える。返り値は (結果の種類, 説明)。

    title: 中央に入れる文字列 (None または空なら中央を空にする)。replace_center が偽なら中央はそのまま。
    結果の種類: 'replaced' (書き換えた) / 'empty' (文字の無いヘッダ。何もしない) / 'skipped' (形が想定と違う。触らない)
    """
    paras = [p for p in hdr_root.iter(w("p")) if _has_content(p)]
    if not paras:
        return "empty", "文字の無いヘッダ"
    if len(paras) > 1:
        return "skipped", f"文字のある段落が {len(paras)} つある (想定は 1 つ)"
    p = paras[0]
    if p.getparent() is not hdr_root:
        return "skipped", "柱の段落が表などの中にある"
    toks = _tokens(p)
    if toks is None:
        return "skipped", "柱の段落に文字とタブ以外のもの (フィールド・図など) がある"
    tabs = [i for i, (_, kind, _) in enumerate(toks) if kind == "tab"]
    if len(tabs) != 2:
        return "skipped", f"柱の段落のタブが {len(tabs)} 個 (想定は「左 TAB 中央 TAB 右」の 2 個)"
    i1, i2 = tabs
    left, tab1, center, tab2, right = toks[:i1], toks[i1], toks[i1 + 1:i2], toks[i2], toks[i2 + 1:]

    if replace_center:
        # 書式は中央の最初の文字の書式 (無ければ中央の前のタブの書式) に倣う
        base = next((rpr for rpr, kind, _ in center if kind == "text"), tab1[0])
        rpr = _clean_rpr(base)
        new_center = [(rpr, "text", title)] if title else []
        lead_tab = (rpr, "tab", "\t")
    else:
        new_center = center
        lead_tab = tab1

    if clear_labels:
        new = [lead_tab] + new_center if new_center else []
    else:
        new = left + [tab1] + new_center + [tab2] + right
    _write_tokens(p, new)
    return "replaced", ""


def apply_running_header(parts, doc_root, cfg, is_manuscript=False):
    """柱を差し替える (parts のヘッダのパートを書き換える)。結果を 1 行ずつ表示し、書き換えたパートの数を返す。

    cfg: journal_profile.running_header() の値 ({running_title_from, clear_template_labels})。
    is_manuscript: 本文 (main.md・差分) なら真。running title の段落が見つからないときに知らせる。
    """
    src = cfg.get("running_title_from")
    clear = bool(cfg.get("clear_template_labels"))
    title = None
    if src:
        styles_root = etree.fromstring(parts["word/styles.xml"])
        title = running_title_text(doc_root, styles_root, src)
        if title is None and is_manuscript:
            print(f"  注意: running title の段落 (段落スタイル '{src}') が本文にありません。柱の中央は空にします")
    names = header_parts(parts, doc_root)
    if not names:
        print("  注意: 本文の節に柱 (ヘッダ) の参照がありません。柱の差し替えは行いません")
        return 0
    n = 0
    for name in names:
        root = etree.fromstring(parts[name])
        kind, why = rewrite_header(root, title, replace_center=bool(src), clear_labels=clear)
        if kind == "replaced":
            parts[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            n += 1
            what = []
            if src:
                what.append(f"中央 = {title!r}" if title else "中央を空に")
            if clear:
                what.append("左右の文字を消した")
            print(f"  柱: {name} ({'・'.join(what)})")
        elif kind == "skipped":
            print(f"  警告: 柱 ({name}) の形がテンプレートの想定と違うので触りません: {why}。"
                  "テンプレートが改版されたなら、柱の差し替え (header.*) の扱いを見直してください")
    return n


# =====================================================================
# 2. 所属の番号の後のタブ
# =====================================================================

AFFILIATION_STYLE = "Affiliation"   # 本テンプレートの記法の custom-style (CLAUDE.md「原稿執筆の規約」)。名前で引く


def _is_superscript(r):
    va = r.find(f"{w('rPr')}/{w('vertAlign')}")
    return va is not None and va.get(w("val")) == "superscript"


def _run_text(r):
    return "".join(t.text or "" for t in r.findall(w("t")))


def apply_affiliation_tabs(parts, doc_root):
    """所属 (段落スタイル Affiliation) の先頭の上付きの番号の直後にタブを入れる。入れた段落の数を返す。

    雑誌のテンプレートの所属のスタイルが「番号 (記号) + TAB + 本文」を前提にぶら下げ字下げを持つ誌のための処理
    (ABE の Affiliation はぶら下げ 283 twip = 5.0 mm・タブ位置 426。docs/journal-abe.md §8.2)。原稿は誌に依存しない書き方
    (`^1^Graduate School of …`) のままにし、docx でだけタブを足す。タブが無いと、所属が 2 行に折り返したときに
    2 行目 (ぶら下げの位置) と 1 行目の本文 (番号の直後) の頭がそろわない。

    - 先頭の連続した上付きの w:r を番号とみなす (差分 docx で番号が DiffDel / DiffAdd の 2 つになっても、どちらも上付きなので
      まとめて番号として扱い、その後ろに 1 つだけ入れる)。先頭が上付きでない段落 (機関が 1 つで番号の無い所属) には何もしない
    - 番号の直後の空白 (原稿の `^1^ Graduate` の空白) は消す (タブの後ろに空白が残ると本文の頭がずれる)
    - すでに番号の直後にタブがあれば何もしない (2 度掛けても同じ)
    """
    if "word/styles.xml" not in parts:
        return 0
    styles_root = etree.fromstring(parts["word/styles.xml"])
    sid = docx_styles.style_id_by_name(styles_root, AFFILIATION_STYLE, "paragraph")
    if sid is None:
        return 0
    body = doc_root.find(w("body"))
    n = 0
    for p in (body if body is not None else doc_root).iter(w("p")):
        ps = p.find(f"{w('pPr')}/{w('pStyle')}")
        if ps is None or ps.get(w("val")) != sid:
            continue
        runs = [c for c in p if _local(c) not in _SKIP_IN_P and _local(c) is not None]
        label = []
        for c in runs:
            if _local(c) == "r" and _is_superscript(c) and c.find(w("tab")) is None:
                label.append(c)
            else:
                break
        if not label or not "".join(_run_text(r) for r in label).strip():
            continue
        rest = runs[len(label):]
        if rest and _local(rest[0]) == "r" and rest[0].find(w("tab")) is not None:
            continue
        # 番号の直後の空白を消す (空白だけの w:r は w:r ごと、文字の頭の空白は w:t から)
        for c in rest:
            if _local(c) != "r":
                break
            ts = c.findall(w("t"))
            if not ts:
                break
            if not _run_text(c).strip():
                p.remove(c)
                continue
            first = ts[0]
            for t in ts:
                if (t.text or "").strip():
                    first = t
                    break
                t.text = ""
            first.text = (first.text or "").lstrip()
            break
        tab_run = etree.Element(w("r"))
        etree.SubElement(tab_run, w("tab"))
        label[-1].addnext(tab_run)
        n += 1
    if n:
        print(f"  所属: {n} 段落の番号の後にタブを入れた")
    return n


# =====================================================================
# 3. 本文以外の文書の見出しの自動番号を外す
# =====================================================================

_HEADING_NAME = re.compile(r"^heading [1-9]$", re.IGNORECASE)


def _numbered_heading_ids(styles_root):
    """自動番号を持つ見出しの段落スタイルの ID の集合。

    スタイル (と basedOn で辿った基) の名前が heading 1〜9 で、w:numPr (numId が 0 以外) をスタイル (か基) から受け継ぐもの。
    番号の定義は最も近いスタイルの w:numPr で決まる (numId 0 は「番号なし」)。
    """
    out = set()
    for st in docx_styles.styles_of(styles_root, "paragraph"):
        seen, cur, is_heading, num = set(), st, False, None
        while cur is not None and cur.get(w("styleId")) not in seen:
            seen.add(cur.get(w("styleId")))
            if _HEADING_NAME.match(docx_styles.style_name(cur) or ""):
                is_heading = True
            if num is None:
                np_ = cur.find(f"{w('pPr')}/{w('numPr')}/{w('numId')}")
                if np_ is not None:
                    num = np_.get(w("val"))
            based = cur.find(w("basedOn"))
            cur = docx_styles.style_by_id(styles_root, based.get(w("val"))) if based is not None else None
        if is_heading and num not in (None, "0"):
            out.add(st.get(w("styleId")))
    return out


def suppress_heading_numbers(parts, doc_root):
    """見出しの段落に w:numPr/w:numId=0 を直に置き、スタイルが持つ自動番号を外す (profile の `headings.numbered_scope`)。

    雑誌のテンプレートが見出しのスタイル (heading 1〜3) に自動番号を持たせている誌で、本文 (main.md と差分) 以外の文書
    (回答書・カバーレター) の見出しに「1. Response to Reviewers」「1.1 Reviewer 1」と番号が付かないようにする。
    見出しのスタイル (大きさ・書体) はそのまま残り、番号だけが消える。段落に w:numPr がすでにあれば触らない。
    書き換えた段落の数を返す。
    """
    styles_root = etree.fromstring(parts["word/styles.xml"])
    ids = _numbered_heading_ids(styles_root)
    if not ids:
        return 0
    n = 0
    for p in doc_root.iter(w("p")):
        ppr = p.find(w("pPr"))
        ps = ppr.find(w("pStyle")) if ppr is not None else None
        if ps is None or ps.get(w("val")) not in ids or ppr.find(w("numPr")) is not None:
            continue
        num = etree.Element(w("numPr"))
        etree.SubElement(num, w("numId")).set(w("val"), "0")
        docx_styles.ppr_set(ppr, num)
        n += 1
    if n:
        print(f"  見出し: {n} 段落の自動番号を外した (headings.numbered_scope。本文以外の文書)")
    return n


# =====================================================================
# 4. 著者の脚注 (異動後の新住所) を記号にする
# =====================================================================

AUTHOR_STYLE = "Author"             # 本テンプレートの記法の custom-style (CLAUDE.md「原稿執筆の規約」)。名前で引く
ADD_STYLE_NAME = "DiffAdd"          # 追加の文字スタイル (差分。DEL_STYLE_NAME と対)
REL_FOOTNOTES = R_NS + "/footnotes"


def _footnotes_part(parts):
    """本文の関係定義が指す脚注のパート名 (ふつう word/footnotes.xml)。無ければ None。"""
    rels_name = "word/_rels/document.xml.rels"
    if rels_name in parts:
        for rel in etree.fromstring(parts[rels_name]).findall(f"{{{REL_NS}}}Relationship"):
            if rel.get("Type") == REL_FOOTNOTES and rel.get("TargetMode") != "External":
                tgt = rel.get("Target") or ""
                name = tgt.lstrip("/") if tgt.startswith("/") else str(PurePosixPath("word") / tgt)
                if name in parts:
                    return name
    return "word/footnotes.xml" if "word/footnotes.xml" in parts else None


def _style_ids(styles_root, name):
    """文字スタイルの名前 name の ID の集合 (pandoc の custom-style の ID は名前と同じなので、名前そのものも入れる)。"""
    ids = {name}
    sid = docx_styles.style_id_by_name(styles_root, name, "character")
    if sid:
        ids.add(sid)
    return ids


def _footnote_state(fn, add_ids, del_ids):
    """脚注 fn の差分の状態: 'del' (文字がすべて削除の文字スタイル) / 'add' (すべて追加) / 'same' (それ以外・差分でない docx)。

    差分 docx では、差分の Span の中の脚注の本文に color-diff.lua が差分の文字スタイルを付ける。
    脚注の番号 (w:footnoteRef) の run と空白だけの run は見ない。
    """
    styles = []
    for r in fn.iter(w("r")):
        if r.find(w("footnoteRef")) is not None or not _run_text(r).strip():
            continue
        rs = r.find(f"{w('rPr')}/{w('rStyle')}")
        styles.append(rs.get(w("val")) if rs is not None else None)
    if styles and all(s in del_ids for s in styles):
        return "del"
    if styles and all(s in add_ids for s in styles):
        return "add"
    return "same"


def _mark_t(mark):
    t = etree.Element(w("t"))
    t.text = mark
    return t


def apply_author_footnote_marks(parts, doc_root, marks):
    """著者 (段落スタイル Author) の段落の中の脚注の参照と、その脚注の番号を記号にする。

    規定が「異動後の新住所は脚注に書き、上付きの記号 (* と ** など) で示す」と決め、ほかの脚注は上付きの数字とする誌のための処理
    (ABE。docs/journal-abe.md §3.1・§3.2)。原稿は誌に依存しない書き方のまま、著者名の直後に普通の脚注を書く
    (`Hanako CHOKKAN^2^^[Present address: …]`)。キーの無い誌では数字の脚注のまま出る。

    - 参照は Word が記号の脚注に書く形にする: `<w:footnoteReference w:customMarkFollows="1" w:id="N"/><w:t>*</w:t>` (同じ w:r。
      run の文字スタイル (footnote reference = 上付き) はそのまま)。脚注の側は番号 (w:footnoteRef) を記号の文字に替える。
      Word の自動番号は記号の脚注を数えないので、本文の脚注は 1 から数字で続く (Word 実機で確かめた)
    - 記号は著者の段落の中の参照の順に marks から振る。**文面の同じ脚注** (2 人が同じ新住所) は先の脚注と同じ記号にし、後の参照は
      記号の文字だけの run (上付き) にして脚注を消す (脚注は 1 つ。原稿で同じ `[^addr]` を 2 度参照したときも pandoc は脚注を 2 つ作る)
    - 差分 docx では、新版の並び (変わらない脚注と追加した脚注) と旧版の並び (変わらない脚注と削除した脚注) を別々に数え、
      削除した脚注は旧版の記号、ほかは新版の記号にする (状態は脚注の本文の差分の文字スタイルで見る。_footnote_state)
    - marks が足りなければ、残りは数字のまま (警告)。すでに w:customMarkFollows を持つ参照には触らない (2 度掛けても同じ)
    返り値: 記号にした参照の数。
    """
    fn_name = _footnotes_part(parts)
    if not marks or fn_name is None or "word/styles.xml" not in parts:
        return 0
    styles_root = etree.fromstring(parts["word/styles.xml"])
    sid = docx_styles.style_id_by_name(styles_root, AUTHOR_STYLE, "paragraph")
    if sid is None:
        return 0
    refs = []
    for ref in doc_root.iter(w("footnoteReference")):
        if (ref.get(w("customMarkFollows")) or "").lower() in ("1", "true", "on"):    # ST_OnOff の真
            continue
        p = _owner_p(ref)
        ps = p.find(f"{w('pPr')}/{w('pStyle')}") if p is not None else None
        if ps is not None and ps.get(w("val")) == sid:
            refs.append(ref)
    if not refs:
        return 0
    fn_root = etree.fromstring(parts[fn_name])
    notes = {fn.get(w("id")): fn for fn in fn_root.findall(w("footnote"))}
    add_ids, del_ids = _style_ids(styles_root, ADD_STYLE_NAME), _style_ids(styles_root, DEL_STYLE_NAME)

    items = []                                      # [参照, 脚注, 状態, 文面]
    for ref in refs:
        fn = notes.get(ref.get(w("id")))
        if fn is None:
            continue
        text = " ".join("".join(t.text or "" for t in fn.iter(w("t"))).split())
        items.append([ref, fn, _footnote_state(fn, add_ids, del_ids), text])

    # 新版の並び (same + add) と旧版の並び (same + del) を別々に数える。差分でない docx は全部 same なので 1 通り
    chosen = {}                                     # 参照の位置 → (記号 or None, 先の脚注と同じ文面か)
    short = 0
    for states, show in ((("same", "add"), ("same", "add")), (("same", "del"), ("del",))):
        seen, k = {}, 0
        for i, (_ref, _fn, state, text) in enumerate(items):
            if state not in states:
                continue
            if text in seen:
                mark, dup = seen[text], True
            elif k < len(marks):
                mark, dup = marks[k], False
                seen[text] = mark
                k += 1
            else:
                mark, dup = None, False
                if state in show:
                    short += 1
            if state in show:
                chosen[i] = (mark, dup)

    n = merged = 0
    for i, (ref, fn, _state, _text) in enumerate(items):
        mark, dup = chosen.get(i, (None, False))
        if mark is None:
            continue
        if dup:
            ref.getparent().replace(ref, _mark_t(mark))       # 記号の文字だけの run (上付きの文字スタイルは run に残る)
            fn.getparent().remove(fn)
            merged += 1
        else:
            ref.set(w("customMarkFollows"), "1")
            ref.addnext(_mark_t(mark))
            num = fn.find(f".//{w('footnoteRef')}")
            if num is not None:
                num.getparent().replace(num, _mark_t(mark))
        n += 1
    if short:
        print(f"  警告: 著者の脚注が記号の数 ({len(marks)} 個: {' '.join(marks)}) より多いので、{short} 個は数字のままにしました "
              "(title_page.author_footnote_marks に記号を足してください)")
    if n:
        parts[fn_name] = etree.tostring(fn_root, xml_declaration=True, encoding="UTF-8", standalone=True)
        used = sorted({m for m, _ in chosen.values() if m}, key=marks.index)
        extra = f"。文面の同じ {merged} 個は先の脚注にまとめた" if merged else ""
        print(f"  著者の脚注: {n} 個の参照を記号にした ({' '.join(used)}{extra})")
    return n
