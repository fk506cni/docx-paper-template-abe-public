#!/usr/bin/env python3
"""check_csl.py — 雑誌 CSL の出力を規定の公式例と 1 文字ずつ突き合わせる受入テスト。

引用様式は投稿可否に直結するため、
規定に載っている出力例そのものを期待値として持ち、citeproc の実出力と機械的に照合する。
引用書式 (CSL・bib の書き方) を変えたら再実行する。

誌に依存しない形にしてある (ABE の公式例と扱いは docs/journal-abe.md §4)。
誌ごとに違う点 (本文の引用の形・公式例の件数・本文の引用の期待値) はフィクスチャの check.yaml に書く。

入力:
  --fixture <dir>   main.md / ref.bib / expected.txt (+ 任意で check.yaml) を置いたフィクスチャ
                    (既定: data/dummy/<journal>-csl)
  --journal <id>    profile.yaml の csl を解決する雑誌 (既定: abe)
  --docx <path>     フィクスチャからビルドした docx。OOXML の書式も実測する

check.yaml (任意。無ければ下の既定で動く):
  journal: <id>                 このフィクスチャを書いた誌。--journal と違えば止まる (取り違えの防止)
  official_examples: <N>        expected.txt の先頭 N 行が規定の公式例 (残りは本テンプレートが足した検証用)。結果の表示にだけ使う
  citation_form: superscript | brackets
                                本文の引用の形。superscript = `1)` 全体が上付き、
                                brackets = 角括弧で上付きにしない (`[1]`)。--docx のときに docx で実測する。無ければ見ない
  citations: [ "[1]", ... ]     本文の引用の期待値 (AST の出現順。図の代替テキストの中は数えない)。書けば 1 件ずつ照合し、
                                書かなければ実出力を記録するだけ (規定に複数引用の書式が無い誌のため)
  bibliography_label: "<形>"    文献リストの番号の形。{n} が番号 (1 から順) に置き換わる (abe = "[{n}]" / 番号 + ピリオドの誌 = "{n}.")。
                                書けば、AST で番号が本文と分かれて (second-field-align) この形であることを、--docx のときは
                                docx の文献の段落が「番号 + 区切り + 本文」であることを厳密に照合する。区切りは誌の profile の
                                bibliography.label_separator で決まる (tab = TAB だけ / 既定の space-tab = 空白 + TAB。
                                pandoc の出力の形)。書かなければ番号の形は緩く見る (`[n]` か `n.` で 1 から順か) だけ
                                (書かないと、番号を `1.` にした CSL や、second-field-align を外して番号と著者が
                                くっつく CSL (`[1]Hohne…`) も --docx つきの照合まで合格する)

判定:
  文献リストの各エントリを expected.txt の各行と完全一致で比較する。太字は **…**、斜体は *…* で表し、
  書式も文字と同じく照合する (ABE の「巻は太字」)。1 件でも不一致なら exit 1。差異は行内の差分 (difflib) と、
  最初に食い違った文字位置・コードポイントを出す (en dash とハイフン等、目視で判別できない差のため)。
  check.yaml に bibliography_label があれば、文献の番号の形も照合する (上記)。
  --docx のときは、docx の文献の段落 (スタイル Bibliography) の文字と w:b / w:i も同じ期待値と照合し、
  本文の引用の形 (citation_form) を w:vertAlign で確かめる。

副次の出力 (citations を書かないときは判定に使わない・記録が目的):
  本文中の引用の実出力を data-cites つきで一覧する。複数引用・連続引用の書式は
  規定に記述が無い誌では「規定と矛盾しない」の判定ができないため、実出力の記録を残す。
  上付きは ^{...} で示す。

コンテナ内で実行する (driver: scripts/check-csl.sh)。
"""

import argparse
import difflib
import io
import re
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path

import panflute as pf
import yaml
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
import docx_styles  # noqa: E402
import journal_profile  # noqa: E402

JOURNALS_DIR = Path("data/journals")
DEFAULT_CSL = JOURNALS_DIR / "_default" / "_default.csl"


def resolve_csl(journal_id):
    """profile.yaml の csl を解決する (build_docx.py の _resolve_asset と同じ規則)。"""
    profile = journal_profile.load(journal_id)
    value = profile.get("csl")
    if value:
        cand = JOURNALS_DIR / journal_id / value
        if cand.is_file():
            return cand
        sys.exit(f"エラー: csl='{cand}' がありません")
    print(f"  警告: {journal_id} は csl 未指定です。_default (AMA 11th) で照合します")
    return DEFAULT_CSL


def render(md, csl, bib):
    """pandoc(crossref → citeproc) を通した AST を返す。"""
    cmd = [
        "pandoc", str(md),
        "--from", "markdown+east_asian_line_breaks",
        "--to", "json",
        "--filter", "pandoc-crossref",
        "--citeproc",
        f"--csl={csl}",
        f"--bibliography={bib}",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"エラー: pandoc が失敗しました (exit {res.returncode})\n{res.stderr}")
    if res.stderr.strip():
        for line in res.stderr.strip().splitlines():
            print(f"  [pandoc] {line}")
    return pf.load(io.StringIO(res.stdout))


def to_text(elem):
    """書式を記号で示す stringify (引用書式の照合と記録用)。

    panflute.stringify は書式を落とすため、上付き ^{...}・下付き _{...}・太字 **...**・斜体 *...* を手で括る
    (太字と斜体は、ABE の規定の「巻は太字」のように、文字列だけの照合では確かめられない書式のため)。
    引用符 (Quoted) は stringify と同じく “…” / ‘…’ で戻す。
    """
    if isinstance(elem, pf.Superscript):
        return "^{" + "".join(to_text(c) for c in elem.content) + "}"
    if isinstance(elem, pf.Subscript):
        return "_{" + "".join(to_text(c) for c in elem.content) + "}"
    if isinstance(elem, pf.Strong):
        return "**" + "".join(to_text(c) for c in elem.content) + "**"
    if isinstance(elem, pf.Emph):
        return "*" + "".join(to_text(c) for c in elem.content) + "*"
    if isinstance(elem, pf.Quoted):
        q = ("“", "”") if elem.quote_type == "DoubleQuote" else ("‘", "’")
        return q[0] + "".join(to_text(c) for c in elem.content) + q[1]
    if isinstance(elem, (pf.Space, pf.SoftBreak, pf.LineBreak)):
        return " "
    if isinstance(elem, pf.Str):
        return elem.text
    if hasattr(elem, "content"):
        return "".join(to_text(c) for c in elem.content)
    return pf.stringify(elem)


def collect_entries(doc):
    """文献リスト (Div.csl-entry) の各エントリを (番号, 番号を除いた文字列) で返す。

    second-field-align="flush" のとき pandoc は番号を csl-left-margin の Span に分けるので、その Span を番号として
    取り出し、本文からは読み飛ばす (番号の形は誌で違う: `1.` / `[1]`)。Span が無いスタイルでは番号を None にし
    (番号と本文が分かれていない)、本文の先頭の番号を split_number で落とす。
    番号も返すのは番号の形を照合するため (番号を除いた文字列だけでは、番号の形をどこも確かめない)。
    """
    entries = []

    def entry_text(div):
        spans = [e for e in div.content if isinstance(e, pf.Para) for e in e.content]
        margin = [s for s in spans if isinstance(s, pf.Span) and "csl-left-margin" in s.classes]
        if margin:
            label = "".join(to_text(s) for s in margin).strip()
            return label, "".join(to_text(s) for s in spans
                                  if not (isinstance(s, pf.Span) and "csl-left-margin" in s.classes)).strip()
        return None, split_number(to_text(div))

    def walk(elem, doc):
        if isinstance(elem, pf.Div) and "csl-entry" in elem.classes:
            entries.append(entry_text(elem))
        return None

    doc.walk(walk)
    return entries


_LEADING_NUMBER_RE = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)\.)\s*")
_LABEL_RE = re.compile(r"\s*(?:\[(\d+)\]|(\d+)\.)\s*")       # 番号だけの断片 (docx の「番号 TAB」の番号側)


def split_number(text):
    """'1. Author…' / '[1] Author…' から番号を落とす。番号が付いていなければそのまま返す。"""
    m = _LEADING_NUMBER_RE.match(text)
    if m:
        return text[m.end():].strip()
    return text.strip()


def _inside_image(elem):
    """Image の alt テキスト内かどうか。

    pandoc 3 の Figure は Caption と Image を持ち、図キャプションは【両方】に入る。
    Image 側は docx では docPr@descr (代替テキスト) になり本文の run にはならないので、
    docx の上付き run と件数を突き合わせるときは数えない。
    """
    parent = getattr(elem, "parent", None)
    while parent is not None:
        if isinstance(parent, pf.Image):
            return True
        parent = getattr(parent, "parent", None)
    return False


def collect_citations(doc):
    """本文中の引用 (Cite) を (bib キー, 実出力) で返す。"""
    found = []

    def walk(elem, doc):
        if isinstance(elem, pf.Cite) and not _inside_image(elem):
            keys = " ".join(c.id for c in elem.citations)
            found.append((keys, to_text(elem)))
        return None

    doc.walk(walk)
    return found


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def W(tag):
    return f"{{{W_NS}}}{tag}"


def docx_segments(docx_path):
    """docx の段落ごとに (テキスト, 上付きか) の連なりを返す。

    連続する同一書式の run はまとめる (pandoc は書式が変わる境目で run を割るため、
    `1)` が 2 run に分かれることがある)。
    """
    with zipfile.ZipFile(docx_path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    paras = []
    for p in root.iter(W("p")):
        segs = []
        for r in p.iter(W("r")):
            rpr = r.find(W("rPr"))
            va = rpr.find(W("vertAlign")) if rpr is not None else None
            is_sup = va is not None and va.get(W("val")) == "superscript"
            text = "".join(t.text or "" for t in r.iter(W("t")))
            if not text:
                continue
            if segs and segs[-1][1] == is_sup:
                segs[-1] = (segs[-1][0] + text, is_sup)
            else:
                segs.append((text, is_sup))
        if segs:
            paras.append(segs)
    return paras


# 引用らしい上付き断片: 数字で始まり閉じ括弧で終わる (`1)` / `1,4)` / `1–3)` / `4, p. 23)`)
# 文字集合は `p` だけでなく `a-z` にして、`sec.` / `chap.` / `para.` 等の
# locator ラベルを含む上付き (`4, sec. 3)`) も引用として数える (`p` だけだと数え落として誤って失敗する)。
CITE_SUP_RE = re.compile(r"^\d[\d,\s.a-z)–-]*\)$")
# 括弧がベースラインに落ちた形: 上付きが数字だけで終わり、直後の地の文が `)` で始まる
BARE_NUM_RE = re.compile(r"\d$")


def check_docx_superscript(docx_path, expected_citations, build_hint):
    """docx の OOXML で `1)` 全体が上付きかを実測する (check.yaml の citation_form: superscript)。

    引用番号を `1)` の形で上付きにする誌のための検査。`1)` の右の括弧だけが地の文の高さに落ちていないことを、
    w:rPr/w:vertAlign val="superscript" で直接確かめる (目で見ても気づきにくい差のため)。
    build_hint はフィクスチャから docx を作るコマンド (取り違えのヒントに出す)。
    """
    print("")
    print(f"-- docx の上付き実測: {docx_path} --")
    if not Path(docx_path).is_file():
        print(f"  NG: {docx_path} がありません (先に scripts/build.sh を実行してください)")
        return 1

    ng = 0
    cites = []
    for segs in docx_segments(docx_path):
        for i, (text, is_sup) in enumerate(segs):
            if not is_sup:
                continue
            nxt = segs[i + 1][0] if i + 1 < len(segs) else ""
            if BARE_NUM_RE.search(text) and nxt.startswith(")"):
                print(f"  NG: 閉じ括弧がベースラインに落ちています: 上付き='{text}' 直後='{nxt[:20]}'")
                ng += 1
            if CITE_SUP_RE.match(text):
                cites.append(text)

    for text in cites:
        print(f"  OK: 上付き run = '{text}' (数字と閉じ括弧が同一の上付き run)")

    if len(cites) < expected_citations:
        print(f"  NG: 上付きの引用が {len(cites)} 件しかありません "
              f"(AST 上の引用は {expected_citations} 件)")
        # 期待件数はフィクスチャの main.md から数えた値なので、
        # 別原稿からビルドした docx を --docx に渡すと必ず件数が合わない。上の NG だけでは
        # 「上付きが足りない」と読め、入力の取り違えを引用様式の不具合と誤診させるのでヒントを添える。
        print(f"      ヒント: --docx に渡した docx がフィクスチャからビルドされたものか確認してください ({build_hint})")
        ng += 1
    else:
        print(f"  引用 {len(cites)} 件 / AST 上の引用 {expected_citations} 件")
    return ng


# ---------------------------------------------------------------------------
# docx の文献リストと角括弧の引用
# ---------------------------------------------------------------------------

_OFF = {"0", "false", "off"}


def _flag(rpr, tag):
    """w:rPr の w:b / w:i が立っているか (w:val が 0 / false / off なら立っていない)。"""
    if rpr is None:
        return False
    el = rpr.find(W(tag))
    return el is not None and el.get(W("val"), "1").lower() not in _OFF


def docx_paragraphs(docx_path):
    """docx の段落ごとに (段落スタイル ID, [(テキスト, 上付きか, 太字か, 斜体か), …]) を返す。

    w:hyperlink の中の run も含める。w:tab は "\\t" として読む (pandoc は文献の番号の後のタブを w:t の中の
    タブ文字で書くが、Word で開き直した docx は w:tab になるので両方を同じに扱う)。連続する同じ書式の run はまとめる。
    """
    with zipfile.ZipFile(docx_path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    paras = []
    for p in root.iter(W("p")):
        ppr = p.find(W("pPr"))
        pst = ppr.find(W("pStyle")) if ppr is not None else None
        style = pst.get(W("val")) if pst is not None else None
        segs = []
        for r in p.iter(W("r")):
            if next(r.iterancestors(W("p"))) is not p:    # テキストボックスの中の段落の run は、その段落の側で読む
                continue
            rpr = r.find(W("rPr"))
            va = rpr.find(W("vertAlign")) if rpr is not None else None
            fmt = (va is not None and va.get(W("val")) == "superscript", _flag(rpr, "b"), _flag(rpr, "i"))
            text = "".join((c.text or "") if c.tag == W("t") else "\t"
                           for c in r if c.tag in (W("t"), W("tab")))
            if not text:
                continue
            if segs and segs[-1][1:] == fmt:
                segs[-1] = (segs[-1][0] + text,) + fmt
            else:
                segs.append((text,) + fmt)
        paras.append((style, segs))
    return paras


def _marked(segs):
    """書式つきの断片を to_text と同じ記号 (**太字** / *斜体* / ^{上付き}) の文字列にする。

    記号は書式の掛かった文字だけを囲む (前後の空白は外に出す。pandoc の AST の Strong も空白を含まない)。
    """
    out = []
    for text, sup, bold, ital in segs:
        core = text.strip(" ")
        if not core or not (sup or bold or ital):
            out.append(text)
            continue
        lead = text[:len(text) - len(text.lstrip(" "))]
        tail = text[len(text.rstrip(" ")):]
        if ital:
            core = f"*{core}*"
        if bold:
            core = f"**{core}**"
        if sup:
            core = f"^{{{core}}}"
        out.append(lead + core + tail)
    return "".join(out)


def _bibliography_style_id(docx_path):
    """docx の styles.xml から文献の段落スタイル (名前 Bibliography) の ID を引く (ID を決め打ちしない)。"""
    with zipfile.ZipFile(docx_path) as z:
        styles = etree.fromstring(z.read("word/styles.xml"))
    return docx_styles.style_id_by_name(styles, "Bibliography", "paragraph")


def label_text(label_form, n):
    """check.yaml の bibliography_label の形 ("[{n}]" など) に番号を入れた文字列。"""
    return label_form.replace("{n}", str(n))


def check_docx_bibliography(docx_path, expected, label_form=None, separator=None):
    """docx の文献の段落を expected.txt と照合する (文字・番号・太字・斜体)。NG の件数を返す。

    文字列の照合は AST で済んでいるので、ここで見るのは docx に書かれた書式 (ABE の巻の w:b) と、
    番号の並び ([1] / 1. が 1 から順に付いているか) と、番号の後に本文が続くこと。
    label_form (check.yaml の bibliography_label) と separator (profile の bibliography.label_separator から決めた区切り) を
    渡すと、段落が「番号の形 + 区切り + 本文」で始まることを 1 文字ずつ照合する (番号が `[n]` か `n.` で
    あればよいとし、区切りも見ないと、番号を `1.` にした CSL や番号と著者がくっつく `[1]Hohne…` まで合格する)。
    """
    print("")
    print(f"-- docx の文献リスト実測 (文字と w:b / w:i): {docx_path} --")
    if label_form is not None:
        print(f"  番号と区切りの形: {label_text(label_form, 1) + separator!r} … (check.yaml の bibliography_label + "
              "profile の bibliography.label_separator)")
    sid = _bibliography_style_id(docx_path)
    if sid is None:
        print("  NG: docx に段落スタイル Bibliography がありません (文献リストが出力されていない)")
        return 1
    entries = [_marked(segs) for style, segs in docx_paragraphs(docx_path) if style == sid and segs]
    ng = 0
    for i in range(max(len(entries), len(expected))):
        got = entries[i] if i < len(entries) else None
        want = expected[i] if i < len(expected) else None
        if got is None:
            print(f"  [{i + 1}] NG: docx の文献が足りません (期待: {want})")
            ng += 1
            continue
        if want is None:
            print(f"  [{i + 1}] NG: 期待値に無い文献が docx にあります: {got}")
            ng += 1
            continue
        if label_form is not None:                    # 番号の形と区切りを厳密に
            prefix = label_text(label_form, i + 1) + separator
            if not got.startswith(prefix):
                print(f"  [{i + 1}] NG: 番号と区切りが {prefix!r} ではありません: {got[:40]!r}")
                ng += 1
                continue
            body = got[len(prefix):].rstrip(" ")
            if body != body.lstrip():
                print(f"  [{i + 1}] NG: 区切りの後に空白があります: {got[:40]!r}")
                ng += 1
                continue
            num = str(i + 1)
        else:
            if "\t" in got:                           # 「番号 TAB 本文」(second-field-align="flush" の様式)
                label, body = got.split("\t", 1)
                m = _LABEL_RE.fullmatch(label)
                body = body.strip()
            else:                                     # 番号の後にタブが無い様式
                m = _LEADING_NUMBER_RE.match(got)
                body = got[m.end():].strip() if m else got.strip()
            num = (m.group(1) or m.group(2)) if m else None
        if num != str(i + 1):
            print(f"  [{i + 1}] NG: 番号が {i + 1} ではありません: {got[:40]!r}")
            ng += 1
            continue
        if body == want:
            print(f"  [{i + 1}] OK: {body}")
            continue
        ng += 1
        print(f"  [{i + 1}] NG")
        print(f"      期待: {want}")
        print(f"      docx: {body}")
        d = first_diff(want, body)
        if d:
            pos, w_, g = d
            print(f"      最初の相違: {pos} 文字目  期待={describe(w_)}  実際={describe(g)}")
    if not ng:
        print(f"  docx の文献 {len(entries)} 件が期待値と一致 (太字・斜体を含む)")
    return ng


# 本文の角括弧の引用: [1] / [3, 4] / [7–10] / [2, p. 70]。数字で始まる角括弧の中身だけを拾う
_BRACKET_CITE_RE = re.compile(r"\[\d[^\[\]]*\]")


def check_docx_brackets(docx_path, ast_citations):
    """本文の引用が角括弧で、上付きになっていないことを docx で実測する。NG の件数を返す。

    文献の段落 (番号 [n]) は除く。上付きの断片に角括弧の引用があれば NG。上付きでない断片から拾った引用の並びを、
    AST の引用 (図の代替テキストの中を除いた出現順) と 1 件ずつ照合する。
    """
    print("")
    print(f"-- docx の角括弧の引用の実測: {docx_path} --")
    sid = _bibliography_style_id(docx_path)
    ng = 0
    found = []
    for style, segs in docx_paragraphs(docx_path):
        if style == sid:
            continue
        for text, sup, _b, _i in segs:
            hits = _BRACKET_CITE_RE.findall(text)
            if sup and hits:
                print(f"  NG: 角括弧の引用が上付きになっています: {hits}")
                ng += 1
            elif not sup:
                found.extend(hits)
    if found != ast_citations:
        ng += 1
        print(f"  NG: docx の角括弧の引用 {len(found)} 件が AST の引用 {len(ast_citations)} 件と一致しません")
        for i in range(max(len(found), len(ast_citations))):
            a = ast_citations[i] if i < len(ast_citations) else "(なし)"
            b = found[i] if i < len(found) else "(なし)"
            print(f"      {i + 1:2d}. AST {a:12s} docx {b}{'' if a == b else '   <- 相違'}")
        print("      ヒント: --docx に渡した docx が --fixture のフィクスチャからビルドされたものか確認してください")
    else:
        print(f"  OK: 角括弧の引用 {len(found)} 件 (上付きなし・AST の出現順と一致): {' '.join(found)}")
    return ng


def load_expected(path):
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines


# language-note のマクロ (和文の文献に "(in Japanese)" を付ける CSL が持つ) は footgun を持つ。
#   - note を無条件に括弧で出す → 書誌管理ソフトの控えが文献リストに露出する
#   - language があるだけで "(in Japanese)" を出す → 非日本語言語が誤表示される
# CSL 側では自動で気づけないため、ここで bib を走査して助言的に警告する。
# 助言のみで exit code は変えない (note = {in German} という正規の回避策で誤失敗させないため)。
_BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)")
_BIB_NOTE_RE = re.compile(r"^note\s*=", re.IGNORECASE)
_BIB_LANG_RE = re.compile(r"^lang(?:id|uage)\s*=\s*\{?\s*([A-Za-z][A-Za-z\-]*)", re.IGNORECASE)


def csl_variables(csl_path):
    """CSL が参照する変数名の集合 (variable 属性の値。空白区切りの複数も分ける)。"""
    root = etree.parse(str(csl_path)).getroot()
    names = set()
    for el in root.iter():
        names.update((el.get("variable") or "").split())
    return names


def lint_bib(bib_path, csl_vars):
    """ref.bib の language-note 系 footgun を助言的に警告する (判定には影響しない)。

    note / language を出力に使う様式 (language-note のマクロを持つ CSL) のときだけ、その変数の警告を出す
    (abe.csl はどちらも出力しないので、この警告は誤りになる)。
    """
    warnings = []
    key = "?"
    for raw in bib_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        m = _BIB_ENTRY_RE.match(line)
        if m:
            key = m.group(1)
            continue
        if _BIB_NOTE_RE.match(line) and "note" in csl_vars:
            warnings.append(
                f"  警告: [{key}] に note フィールドがあります。note は文献リスト末尾へ"
                f"そのまま露出します。言語表記 (in German 等) 以外の控えが入っていないか"
                f"確認してください")
        ml = _BIB_LANG_RE.match(line)
        if ml and ml.group(1).lower() not in ("japanese", "ja", "ja-jp") and "language" in csl_vars:
            warnings.append(
                f"  警告: [{key}] の言語指定 '{ml.group(1)}' は出力が (in Japanese) になります"
                f" (CSL は変数の値を判定できないため)。非日本語文献は "
                f"note = {{in {ml.group(1)}}} を使ってください")
    return warnings


def first_diff(a, b):
    """最初に食い違う位置とコードポイントを返す (en dash / hyphen の見分けのため)。"""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    if len(a) != len(b):
        i = min(len(a), len(b))
        x = a[i] if i < len(a) else ""
        y = b[i] if i < len(b) else ""
        return i, x, y
    return None


def describe(ch):
    if ch == "":
        return "(なし)"
    try:
        name = unicodedata.name(ch)
    except ValueError:
        name = "?"
    return f"{ch!r} U+{ord(ch):04X} {name}"


CITATION_FORMS = ("superscript", "brackets")


def load_config(fixture, journal):
    """フィクスチャの check.yaml を読む (無ければ既定)。値の誤りはエラーで止める (受入テストが空振りしないように)。"""
    path = fixture / "check.yaml"
    cfg = {"journal": None, "official_examples": None, "citation_form": None, "citations": None,
           "bibliography_label": None}
    if not path.is_file():
        return cfg, None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        sys.exit(f"エラー: {path} は辞書ではありません")
    unknown = sorted(set(data) - set(cfg))
    if unknown:
        sys.exit(f"エラー: {path} に知らないキーがあります: {', '.join(unknown)} (使えるのは {', '.join(cfg)})")
    cfg.update(data)
    if cfg["journal"] is not None and str(cfg["journal"]) != journal:
        sys.exit(f"エラー: フィクスチャ {fixture} は journal '{cfg['journal']}' 用です (--journal {journal} と食い違い)。"
                 f" --journal {cfg['journal']} を付けるか、{journal} 用のフィクスチャを --fixture で渡してください")
    n = cfg["official_examples"]
    if n is not None and (not isinstance(n, int) or isinstance(n, bool) or n < 0):
        sys.exit(f"エラー: {path} の official_examples は 0 以上の整数にしてください (値: {n!r})")
    if cfg["citation_form"] is not None and cfg["citation_form"] not in CITATION_FORMS:
        sys.exit(f"エラー: {path} の citation_form は {' / '.join(CITATION_FORMS)} のどれかです (値: {cfg['citation_form']!r})")
    c = cfg["citations"]
    if c is not None and not (isinstance(c, list) and c and all(isinstance(x, str) for x in c)):
        sys.exit(f"エラー: {path} の citations は文字列の空でないリストにしてください")
    lab = cfg["bibliography_label"]
    if lab is not None and not (isinstance(lab, str) and lab.count("{n}") == 1 and lab == lab.strip()):
        # 前後の空白は書かせない (区切りの空白とタブは profile の bibliography.label_separator で決まる)
        sys.exit(f"エラー: {path} の bibliography_label は {{n}} (番号) を 1 つ含み、前後に空白の無い文字列にしてください "
                 f"(例: \"[{{n}}]\" / \"{{n}}.\"。値: {lab!r})")
    return cfg, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal", default="abe")
    ap.add_argument("--fixture", default=None, help="既定: data/dummy/<journal>-csl")
    ap.add_argument("--docx", default=None,
                    help="フィクスチャ (--fixture) をビルドした docx を渡すと OOXML の書式も実測する "
                         "(例: build.sh --input data/dummy/abe-csl --journal abe の後の data/step02_build/main.docx。"
                         "原稿の docx を渡すと引用の件数が合わずに NG になる)")
    args = ap.parse_args()

    fixture = Path(args.fixture or f"data/dummy/{args.journal}-csl")
    md, bib, exp = fixture / "main.md", fixture / "ref.bib", fixture / "expected.txt"
    for p in (md, bib, exp):
        if not p.is_file():
            sys.exit(f"エラー: {p} がありません")
    cfg, cfg_path = load_config(fixture, args.journal)
    build_hint = f"bash scripts/build.sh --input {fixture} --journal {args.journal}"

    csl = resolve_csl(args.journal)
    print(f"== CSL 受入テスト: journal={args.journal}  csl={csl} ==")
    print(f"  fixture = {fixture}" + (f"  (設定 {cfg_path.name}: 本文の引用の形 = {cfg['citation_form'] or '見ない'})"
                                       if cfg_path else ""))

    doc = render(md, csl, bib)
    labeled = collect_entries(doc)                 # [(番号 or None, 本文)]
    entries = [body for _label, body in labeled]
    expected = load_expected(exp)
    if not expected:
        sys.exit(f"エラー: {exp} に期待値が 1 件もありません (全行コメント/空)。"
                 f"受入テストが空振りするため中止します")
    citations = collect_citations(doc)

    lint_warnings = lint_bib(bib, csl_variables(csl))
    if lint_warnings:
        print("")
        print("-- bib の助言的検査 (lint。判定には影響しない) --")
        for w in lint_warnings:
            print(w)

    ng = 0
    print("")
    if cfg["citations"] is None:
        print("-- 本文中の引用 (実出力の記録。判定には使わない) --")
        for keys, text in citations:
            print(f"  [{keys}] -> {text}")
    else:
        print(f"-- 本文中の引用の突合 ({cfg_path.name} の citations と出現順に) --")
        want_c = cfg["citations"]
        for i in range(max(len(citations), len(want_c))):
            keys, got = citations[i] if i < len(citations) else ("-", None)
            want = want_c[i] if i < len(want_c) else None
            if got == want:
                print(f"  OK: [{keys}] -> {got}")
                continue
            ng += 1
            print(f"  NG: [{keys}] -> {got if got is not None else '(出力なし)'}  期待: {want if want is not None else '(期待値なし)'}")

    print("")
    print("-- 文献リストの突合 --")
    for i in range(max(len(entries), len(expected))):
        got = entries[i] if i < len(entries) else None
        want = expected[i] if i < len(expected) else None
        if got is None:
            print(f"  [{i + 1}] NG: 出力が足りません (期待: {want})")
            ng += 1
            continue
        if want is None:
            print(f"  [{i + 1}] NG: 期待値に無いエントリが出ました: {got}")
            ng += 1
            continue
        if got == want:
            print(f"  [{i + 1}] OK: {got}")
            continue
        ng += 1
        print(f"  [{i + 1}] NG")
        print(f"      期待: {want}")
        print(f"      実際: {got}")
        d = first_diff(want, got)
        if d:
            pos, w, g = d
            print(f"      最初の相違: {pos} 文字目  期待={describe(w)}  実際={describe(g)}")
        for line in difflib.unified_diff([want], [got], "expected", "actual",
                                         lineterm="", n=0):
            print(f"      {line}")

    # 文献の番号の形 (check.yaml の bibliography_label)。AST で、番号が本文と分かれ (second-field-align。
    # 分かれていないと docx で「番号 TAB 本文」にならない)、指定の形で 1 から順に付いているかを見る
    label_form = cfg["bibliography_label"]
    separator = None
    if label_form is not None:
        sep_key = journal_profile.bibliography_label_separator(journal_profile.load(args.journal))
        separator = "\t" if sep_key == "tab" else " \t"     # 既定の space-tab は pandoc の出力の形 (番号 空白 TAB)
        print("")
        print(f"-- 文献の番号の形 ({cfg_path.name} の bibliography_label = {label_form!r}) --")
        bad = 0
        for i, (label, _body) in enumerate(labeled):
            want = label_text(label_form, i + 1)
            if label is None:
                print(f"  [{i + 1}] NG: 番号が本文と分かれていません (CSL の bibliography に second-field-align=\"flush\" が"
                      f"無い。docx で「番号 TAB 本文」にならない)。期待する番号: {want!r}")
                bad += 1
            elif label != want:
                print(f"  [{i + 1}] NG: 番号が {label!r} です (期待: {want!r})")
                bad += 1
        if not bad and labeled:
            print(f"  OK: {len(labeled)} 件とも番号が本文と分かれ、{label_text(label_form, 1)!r} … "
                  f"{label_text(label_form, len(labeled))!r} の形")
        ng += bad

    total = max(len(entries), len(expected))
    form = cfg["citation_form"]
    form_label = {"superscript": "上付きの引用番号 (`1)` 全体が上付きか)",
                  "brackets": "本文の引用の角括弧 (上付きでないか)"}.get(form)
    if args.docx:
        if not Path(args.docx).is_file():
            print("")
            print(f"  NG: {args.docx} がありません (先に {build_hint} を実行してください)")
            ng += 1
        else:
            if form == "superscript":
                ng += check_docx_superscript(args.docx, len(citations), build_hint)
            elif form == "brackets":
                ng += check_docx_brackets(args.docx, [text for _keys, text in citations])
            else:
                print("")
                print(f"  注意: フィクスチャに check.yaml の citation_form が無いので、docx の本文の引用の形は見ていません")
            ng += check_docx_bibliography(args.docx, expected, label_form, separator)
    else:
        print("")
        print(f"  警告: --docx 未指定のため、docx の書式{' (' + form_label + ' と文献の太字・斜体)' if form_label else ''} は"
              "未検証です。")
        print("        フィクスチャをビルドした docx を渡すと OOXML (w:vertAlign / w:b / w:i) で実測します")
        print(f"        ({build_hint} の後に --docx data/step02_build/main.docx。"
              "原稿の docx では引用の件数が合わずに NG になる)。")   # 案内を原稿の docx と読まれない形に

    print("")
    if ng:
        print(f"== NG {ng} 件 (文献リスト 全 {total} 件"
              f"{' + 本文の引用' if cfg['citations'] is not None else ''}"
              f"{' + 文献の番号の形' if label_form is not None else ''}{' + docx 実測' if args.docx else ''}) ==")
        return 1
    # 規定の公式例は expected.txt の先頭 official_examples 件だけで、残りは本テンプレートが足した例 (公式例に無い文献型など)
    n = cfg["official_examples"]
    official = (f" (うち規定の公式例は 1〜{n} 件目)" if n and n < len(expected)
                else " (すべて規定の公式例)" if n == len(expected) else "")
    done = []
    if cfg["citations"] is not None:
        done.append(f"本文の引用 {len(citations)} 件も一致")
    if label_form is not None:
        done.append(f"文献の番号の形 ({label_text(label_form, 1)!r}…) も一致")
    if args.docx:
        done.append({"superscript": "docx の上付き", "brackets": "docx の角括弧"}.get(form, "docx") + "と文献の書式も一致")
    print(f"== 全 {len(expected)} 件が期待値と一致{official}{' / ' + ' / '.join(done) if done else ''} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
