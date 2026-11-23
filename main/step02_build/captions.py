#!/usr/bin/env python3
"""captions.py — 図表の題と凡例の並びの後処理 (build / diff 共用)。

本テンプレートの記法では、図表の題はキャプション、凡例は図表の直後の `custom-style="Legend"` の Div で書く
(CLAUDE.md「図表の題と凡例の書き分け」)。pandoc は表の題を表の上・図の題を図の下に出すので、docx の並びは
  図: 図の段落 (Captioned Figure) → 題 (Image Caption) → 凡例 (Legend …)
  表: 題 (Table Caption) → 表 (w:tbl) → 凡例 (Legend …)
になる。「表の題とキャプション (凡例) は表の上」とする誌 (ABE。docs/journal-abe.md §5) のために、誌の profile のキーで次を行う:

- tables.legend_position: above — 表の直後に続く凡例の段落を、表の直前 (題の後) へ移す。題 → 凡例 → 表を keepNext でつなぐ
  (凡例と題が表と別の段・ページに分かれないように)。原稿の書き方 (凡例は表の後) は変えないので、規定チェックの凡例の配置
  (validate の legend_placement) もそのまま効く
- figures.keep_together: true — 図の段落と、凡例が続く題・凡例の段落 (最後の 1 つを除く) に keepNext を付ける
  (図・題・凡例が段・ページで分かれないように。最後の段落に付けないのは、続く本文の 1 行目まで道連れにしないためと、
  段抜きの範囲の最後の段落は節の区切りを持つので、次の節へ keepNext を掛けないため)

どちらも既定 (未指定) では呼ばれない (キーを持たない誌の出力は変わらない)。段組の節の組み立て (layout.py) より**前**に掛ける —
段抜きの範囲の後ろの節の区切りは範囲の最後の段落に付くので、組み立てた後に凡例を動かすと区切りも一緒に表の上へ動く。
前に動かせば範囲は表で終わり、layout.py が表の直後に区切りだけの段落を足す (docs/journal-abe.md §11.3)。
スタイルは名前で引く (docx_styles。テンプレートの ID は和文 Word の自動 ID でありうる)。

コンテナ内 (docx-paper-template-pandoc; lxml 同梱) で使う。
"""

import sys
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
import docx_styles  # noqa: E402

w = docx_styles.w

# 並びを調べるときに読み飛ばす要素 (ブックマークなどの目印。layout.py の _SKIP と同じ)
_SKIP = {"bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd", "commentRangeStart", "commentRangeEnd"}


def _local(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def _pstyle(p):
    ps = p.find(f"{w('pPr')}/{w('pStyle')}")
    return ps.get(w("val")) if ps is not None else None


def _neighbor(el, step):
    """el の前 (step=-1) / 後 (+1) の、ブックマークなどの目印を飛ばした兄弟。"""
    x = el.getprevious() if step < 0 else el.getnext()
    while x is not None and _local(x) in _SKIP:
        x = x.getprevious() if step < 0 else x.getnext()
    return x


def _following(el, style_id):
    """el の後ろに (目印を飛ばして) 続く、段落スタイル style_id の段落を順に返す。"""
    out = []
    x = _neighbor(el, +1)
    while x is not None and x.tag == w("p") and _pstyle(x) == style_id:
        out.append(x)
        x = _neighbor(x, +1)
    return out


def _keep_next(p):
    """段落に keepNext を付ける (w:pPr は先頭に作り、子は CT_PPr の順に保つ)。"""
    ppr = p.find(w("pPr"))
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        p.insert(0, ppr)
    if ppr.find(w("keepNext")) is None:
        docx_styles.ppr_set(ppr, etree.Element(w("keepNext")))


def move_table_legends_above(root, legend_id, caption_id=None):
    """表の直後に続く凡例の段落を表の直前へ移し、題 → 凡例 → 表を keepNext でつなぐ。凡例を移した表の数を返す。

    表はどこにあっても扱う (本文の流れ・テキストボックスの中・表のセルの中。移すのは同じ親の中だけ)。
    凡例が節の区切り (段落の w:sectPr) を持つときは動かさずに警告する (区切りまで動くと節の構造が変わるため。
    段組の組み立ての前に掛けるので、ふつうは起きない)。
    """
    moved = 0
    for tbl in list(root.iter(w("tbl"))):
        legends = _following(tbl, legend_id)
        if not legends:
            continue
        if any(lg.find(f"{w('pPr')}/{w('sectPr')}") is not None for lg in legends):
            print("  警告: 表の後ろの凡例が節の区切りを持つので、凡例を表の上へ移しません")
            continue
        for lg in legends:                  # 順に表の直前へ入れる (並びは保たれる)
            tbl.addprevious(lg)
            _keep_next(lg)
        cap = _neighbor(legends[0], -1)
        if cap is not None and cap.tag == w("p") and caption_id and _pstyle(cap) == caption_id:
            _keep_next(cap)
        moved += 1
    return moved


def keep_figures_together(root, legend_id, caption_id):
    """図の段落 → 題 → 凡例を keepNext でつなぐ。(図の題の数, そのうち凡例の続く題の数) を返す。

    図の段落 (題の直前の、図を含む段落) と、凡例が続くときは題と凡例 (最後の 1 つを除く) に keepNext を付ける。
    """
    n = n_legend = 0
    for cap in [p for p in root.iter(w("p")) if _pstyle(p) == caption_id]:
        n += 1
        img = _neighbor(cap, -1)
        if img is not None and img.tag == w("p") and img.find(f".//{w('drawing')}") is not None:
            _keep_next(img)
        legends = _following(cap, legend_id)
        if not legends:
            continue
        _keep_next(cap)
        for lg in legends[:-1]:
            _keep_next(lg)
        n_legend += 1
    return n, n_legend


def apply(parts, root, legend_position="below", keep_figures=False):
    """profile のキーに従って題と凡例の並びを整える (root = word/document.xml のルート。styles.xml は読むだけ)。"""
    if legend_position != "above" and not keep_figures:
        return
    styles_root = etree.fromstring(parts["word/styles.xml"])
    legend_id = docx_styles.style_id_by_name(styles_root, "Legend", "paragraph")
    if legend_id is None:
        # 凡例の Div が 1 つも無い原稿では pandoc が Legend のスタイルを作らない (reference.docx にも無いとき)。移すものが無い
        legend_id = "\0no-legend"
    msgs = []
    if legend_position == "above":
        n = move_table_legends_above(
            root, legend_id, docx_styles.style_id_by_name(styles_root, "Table Caption", "paragraph"))
        if n:
            msgs.append(f"表の凡例を題の後 (表の上) へ {n} 件")
    if keep_figures:
        cap_id = docx_styles.style_id_by_name(styles_root, "Image Caption", "paragraph")
        n, n_legend = keep_figures_together(root, legend_id, cap_id) if cap_id else (0, 0)
        if n:
            msgs.append(f"図と題 (と凡例) をつなぐ {n} 件 (うち凡例つき {n_legend} 件)")
    if msgs:                                # 図表の無い文書 (カバーレターなど) では何も出さない
        print("  題と凡例: " + " / ".join(msgs))
