#!/usr/bin/env python3
"""test_diff_engine.py — 差分エンジンの受入テスト。

回帰スナップショット (scripts/baseline*.sh) の差分の段は旧版と新版が同じ原稿なので、差分エンジンの出力が変わっても
(壊れても) 検出できない。ここでは旧版と新版の対 (data/dummy/regression/diff/<名前>/old.md・new.md) を実際の経路
(diff_docx.build_diff = pandoc → pandoc-crossref → color-diff.lua → 色の後処理 → OOXML の後処理) で差分 docx にし、
出来上がった docx の**性質**を照合する:

  - docx が開ける (zip と XML として読める)
  - 削除 (DiffDel) と追加 (DiffAdd) の文字が、期待した段落に期待した文字で付く (それ以外の段落には付かない)
  - 番号と参照に `¿` (pandoc-crossref の未定義の参照) と `{#…}` (読めなかったラベル) が残らない
  - 目印のブックマーク DiffAddMark / DiffDelMark が本文・脚注のどこにも残らない
  - 脚注の参照・脚注の番号・脚注の本文に差分の書式が付く

守るもの: 差分エンジンの全誌共通の扱い (表・式・図の追加と削除・ラベルの付け替え・脚注の色・大文字小文字だけの変更・
段抜きの Div の透過・差分の式番号の色・脚注の中の番号つきの式・1 段組の文書の式番号のタブ)。
差分 docx を作らずに確かめられるもの (付け替えの判定・式番号の後処理) は部品を直に呼ぶ。

誌は _default (reference.docx を profile から生成する誌。プロファイルのある誌だけを回す)。--abe を付けると abe でも回す (学会テンプレートと、
それから作る reference.docx が要る。scripts/check-diff.sh はテンプレートがあれば付ける)。

pytest は導入していないので素の assert 相当で書く (test_caption_matches.py と同じ形)。コンテナで回す:
  bash scripts/check-diff.sh                     # reference.docx を確かめてから下を回す
  docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \\
      python3 main/step03_diff/test_diff_engine.py [--abe] [--keep <dir>] [--only <名前>]
全件通れば exit 0、1 件でも外れれば exit 1。--keep で差分 docx とログを残す (既定は一時ディレクトリで消す)。
"""

import argparse
import contextlib
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "main" / "step03_diff"))
sys.path.insert(0, str(ROOT / "main" / "step02_build"))
sys.path.insert(0, str(ROOT / "main" / "00_setup" / "lib"))

from lxml import etree  # noqa: E402

import ast_diff  # noqa: E402
import diff_docx  # noqa: E402
import equations  # noqa: E402
import patch_reference_docx as prd  # noqa: E402

FIXTURES = Path("data/dummy/regression/diff")
INPUT_ROOT = "data/dummy/regression"          # 図 (figs/fig-photo.png) と文献 (ref.bib) の入力ルート
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NBSP = "\xa0"

NG = []


def w(tag):
    return f"{{{W_NS}}}{tag}"


def m(tag):
    return f"{{{M_NS}}}{tag}"


def check(name, cond, detail=""):
    print(f"  {'ok' if cond else 'NG'}: {name}" + (f"\n      {detail}" if detail and not cond else ""))
    if not cond:
        NG.append(name)


# =====================================================================
# 差分 docx を作る・読む
# =====================================================================

@contextlib.contextmanager
def _redirect(path):
    """標準出力と標準エラーを (pandoc の子プロセスの分も) ファイルへ向ける。"""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    with open(path, "w", encoding="utf-8") as f:
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])


def run_diff(case, journal, workdir):
    """フィクスチャ case の差分 docx を journal で作る。(Docx か None, ログの文字列) を返す。"""
    out = Path(workdir) / f"{case}__{journal}.docx"
    log = Path(workdir) / f"{case}__{journal}.log"
    ok, reason = True, ""
    with _redirect(log):
        try:
            diff_docx.build_diff(INPUT_ROOT, journal, FIXTURES / case / "old.md", FIXTURES / case / "new.md", out,
                                 article_type="original" if journal == "abe" else None)
        except SystemExit as exc:
            ok = exc.code in (0, None)
            reason = "" if ok else f"\n(SystemExit) {exc.code}"
    text = log.read_text(encoding="utf-8") + reason
    return (Docx(out) if ok and out.is_file() else None), text


def _run_text(r):
    out = []
    for ch in r.iter(w("t"), m("t"), w("tab")):
        out.append("\t" if ch.tag == w("tab") else (ch.text or ""))
    return "".join(out)


def _run_kind(r):
    """run (w:r / m:r) の差分の種類 ('+' / '-' / None)。式の m:r は中の w:rPr を見る。"""
    rs = r.find(f"{w('rPr')}/{w('rStyle')}")
    val = rs.get(w("val")) if rs is not None else None
    return {"DiffAdd": "+", "DiffDel": "-"}.get(val)


class Para:
    def __init__(self, p):
        self.el = p
        self.style = (p.find(f"{w('pPr')}/{w('pStyle')}").get(w("val"))
                      if p.find(f"{w('pPr')}/{w('pStyle')}") is not None else None)
        runs = [r for r in p.iter(w("r"), m("r"))
                if not (r.tag == w("r") and r.getparent() is not None and r.getparent().tag == m("r"))]
        self.text = "".join(_run_text(r) for r in runs)
        self.marks = []           # [('+' / '-', 文字)]。続いた同じ種類の run はまとめる (印の無い run が挟まれば切る)
        last = None
        for r in runs:
            k = _run_kind(r)
            t = _run_text(r)
            if k is None:
                if t:
                    last = None
                continue
            if last == k:
                self.marks[-1] = (k, self.marks[-1][1] + t)
            else:
                self.marks.append((k, t))
            last = k
        self.bookmarks = [b.get(w("name")) for b in p.iter(w("bookmarkStart"))]

    def __repr__(self):
        return f"<{self.style} {self.text[:60]!r} {self.marks} bm={self.bookmarks}>"


class Docx:
    def __init__(self, path):
        with zipfile.ZipFile(path) as z:       # 開けること (zip と XML として読める) をここで確かめる
            self.parts = {n: z.read(n) for n in z.namelist()}
        self.roots = {n: etree.fromstring(d) for n, d in self.parts.items()
                      if n.startswith("word/") and n.endswith(".xml")}
        self.doc = self.roots["word/document.xml"]
        self.notes = self.roots.get("word/footnotes.xml")
        self.paras = [Para(p) for p in self.doc.iter(w("p"))]

    def note_paras(self):
        """{脚注の w:id: [Para]} (区切りの脚注を除く)。"""
        out = {}
        if self.notes is None:
            return out
        for fn in self.notes.findall(w("footnote")):
            if fn.get(w("type")) in ("separator", "continuationSeparator"):
                continue
            out[fn.get(w("id"))] = [Para(p) for p in fn.iter(w("p"))]
        return out

    def find(self, start):
        hits = [p for p in self.paras if p.text.startswith(start)]
        return hits[0] if hits else None

    def all_marks(self):
        return [mk for p in self.paras for mk in p.marks]

    def text_of_parts(self):
        return {n: "".join(t.text or "" for t in r.iter(w("t"), m("t"))) for n, r in self.roots.items()}


def common_checks(name, d):
    """どの差分 docx にも成り立つ性質: ¿ と {#…} が残らない・目印のブックマークが残らない。"""
    texts = d.text_of_parts()
    bad_q = {n: t.count("¿") for n, t in texts.items() if "¿" in t}
    check(f"{name}: 番号と参照に ¿ が無い", not bad_q, bad_q)
    bad_l = {n: t.count("{#") for n, t in texts.items() if "{#" in t}
    check(f"{name}: ラベルの文字 {{#…}} が残らない", not bad_l, bad_l)
    marks = [b.get(w("name")) for r in d.roots.values() for b in r.iter(w("bookmarkStart"))
             if (b.get(w("name")) or "").startswith(("DiffAddMark", "DiffDelMark"))]
    check(f"{name}: 目印のブックマーク DiffAddMark / DiffDelMark が残らない", not marks, marks)


def _rpr_color(r):
    c = r.find(f"{w('rPr')}/{w('color')}")
    return c.get(w("val")) if c is not None else None


def _rpr_strike(r):
    return r.find(f"{w('rPr')}/{w('strike')}") is not None


# =====================================================================
# 照合 (フィクスチャごと)
# =====================================================================

def case_text(name, d):
    p = d.find("The quick")
    check(f"{name}: 書き換えた語だけに色", p is not None and p.marks == [("-", "brown"), ("+", "red")], p)
    p = d.find("An unchanged paragraph")
    check(f"{name}: 変えていない段落は色なし", p is not None and p.marks == [], p)


def case_case(name, d):
    p = d.find("Measuring")
    check(f"{name}: 題の大文字小文字の変更に色",
          p is not None and p.marks == [("-", "The"), ("+", "the"), ("-", "Tremendous"), ("+", "tremendous"),
                                        ("-", "Hunch"), ("+", "hunch")], p)
    p = d.find("Taro")
    check(f"{name}: 姓の大文字化に色", p is not None and ("-", "Yokan") in p.marks and ("+", "YOKAN") in p.marks, p)
    p = d.find("The temperature")
    check(f"{name}: 文中の式 T → t と地の文 DNA → dna に色",
          p is not None and [("-", "T"), ("+", "t")] == p.marks[:2] and ("-", "DNA") in p.marks
          and ("+", "dna") in p.marks, p)
    old_eq = [p for p in d.paras if p.marks == [("-", "T=kΔx")]]
    new_eq = [p for p in d.paras if "eq:temp" in p.bookmarks]
    check(f"{name}: 番号つきの式 (\\Delta → \\delta) は旧 (削除・番号なし) と新 (追加・番号つき)",
          len(old_eq) == 1 and not any(b and b.startswith("eq:") for b in old_eq[0].bookmarks)
          and len(new_eq) == 1 and new_eq[0].marks and new_eq[0].marks[0][0] == "+"
          and "t=kδx" in new_eq[0].marks[0][1] and "(1)" in new_eq[0].text, (old_eq, new_eq))
    check(f"{name}: ラベルなしの式 N → n に色",
          any(p.marks == [("-", "N=10")] for p in d.paras) and any(p.marks == [("+", "n=10")] for p in d.paras))
    check(f"{name}: セルの大文字小文字の変更に色",
          any(p.marks == [("-", "T"), ("+", "t")] for p in d.paras)
          and any(p.marks == [("-", "Temperature"), ("+", "temperature")] for p in d.paras))
    p = d.find("Table 1")
    check(f"{name}: 表の題の大文字小文字の変更に色", p is not None and ("-", "Used") in p.marks and ("+", "used") in p.marks, p)
    p = d.find("See ")
    check(f"{name}: 変えていない参照は色なし", p is not None and p.marks == [] and f"Eq.{NBSP}1" in p.text, p)


def case_cell(name, d):
    hits = [p for p in d.paras if p.marks == [("-", "2"), ("+", "3")]]
    check(f"{name}: セルの書き換えは 1 段落の中で -2 +3", len(hits) == 1 and hits[0].text == "2 3", hits)
    p = d.find("Table 1")
    check(f"{name}: 表の題は番号つき・色なし", p is not None and p.marks == [], p)


def case_tables(name, d):
    p = d.find("Table 1")
    check(f"{name}: 足した表に番号 (Table 1) と追加の色",
          p is not None and p.marks == [("+", "Table that the new version adds.")], p)
    p = d.find("Table 2")
    check(f"{name}: 残した表は Table 2・色なし", p is not None and p.marks == [] and "Kept table." in p.text, p)
    hits = [p for p in d.paras if p.marks == [("-", "Table that the new version deletes.")]]
    check(f"{name}: 消した表の題は番号を使わない (Table N の接頭辞なし)",
          len(hits) == 1 and hits[0].text == "Table that the new version deletes.", hits)
    p = d.find("See ")
    check(f"{name}: 足した参照だけに追加の色",
          p is not None and p.marks == [("+", f"Table{NBSP}1 and")] and f"Table{NBSP}2" in p.text, p)


def case_equation(name, d, abe=False):
    p = d.find("The rule is")
    check(f"{name}: 式の参照は変更なし (式の書き換え + ラベルの付け替え・ラベルだけの付け替え)",
          p is not None and p.marks == [] and f"Eq.{NBSP}1" in p.text and f"Eq.{NBSP}2" in p.text, p)
    old_eq = [p for p in d.paras if p.marks == [("-", "S=a+b")]]
    check(f"{name}: 旧の式は削除の色・番号なし",
          len(old_eq) == 1 and not any(b and b.startswith("eq:") for b in old_eq[0].bookmarks), old_eq)
    new_eq = [p for p in d.paras if "eq:score" in p.bookmarks]
    check(f"{name}: 新の式は追加の色・番号 (1)",
          len(new_eq) == 1 and new_eq[0].marks and new_eq[0].marks[0][0] == "+" and "S=a+2b" in new_eq[0].marks[0][1]
          and "(1)" in new_eq[0].text, new_eq)
    unit = [p for p in d.paras if "eq:one" in p.bookmarks]
    check(f"{name}: ラベルだけを付け替えた式は色なし・番号 (2)",
          len(unit) == 1 and unit[0].marks == [] and "(2)" in unit[0].text, unit)
    left = [b for p in d.paras for b in p.bookmarks if b in ("eq:rule", "eq:unit")]
    check(f"{name}: 旧のラベルは残らない", not left, left)
    if abe and new_eq:
        # 式番号の後処理 (equations.style) が作る番号の w:r に、外した番号の m:r の書式を移す
        nums = [r for r in new_eq[0].el.findall(w("r")) if _run_text(r) == "(1)"]
        check(f"{name}: 「式 TAB (1)」の番号 (1) に追加の書式",
              len(nums) == 1 and _run_kind(nums[0]) == "+" and _rpr_color(nums[0]) == prd.DIFF_ADD_COLOR,
              [etree.tostring(r) for r in nums])


def case_figure(name, d):
    n_draw = sum(1 for _ in d.doc.iter(w("drawing")))
    check(f"{name}: 図は 2 つ", n_draw == 2, n_draw)
    p = d.find("Figure 2")
    check(f"{name}: 足した図に番号 (Figure 2) と題に追加の色", p is not None and p.marks == [("+", "Second figure.")], p)
    p = d.find("Figure 1")
    check(f"{name}: 残した図は色なし", p is not None and p.marks == [], p)
    p = d.find("See ")
    check(f"{name}: 足した参照に追加の色",
          p is not None and len(p.marks) == 1 and p.marks[0][0] == "+" and f"Fig.{NBSP}2" in p.marks[0][1], p)


def case_footnote(name, d):
    p = d.find("A sentence")
    refs = [r for r in p.el.iter(w("r")) if r.find(w("footnoteReference")) is not None] if p else []
    check(f"{name}: 書き換えた脚注の参照は旧 (取消線 + 削除の色) と新 (追加の色)",
          len(refs) == 2 and _rpr_strike(refs[0]) and _rpr_color(refs[0]) == prd.DIFF_DEL_COLOR
          and not _rpr_strike(refs[1]) and _rpr_color(refs[1]) == prd.DIFF_ADD_COLOR,
          [etree.tostring(r) for r in refs])
    p = d.find("Another sentence")
    refs2 = [r for r in p.el.iter(w("r")) if r.find(w("footnoteReference")) is not None] if p else []
    check(f"{name}: 変えていない脚注の参照は色なし", len(refs2) == 1 and _rpr_color(refs2[0]) is None)
    notes = d.note_paras()
    ids = [r.find(w("footnoteReference")).get(w("id")) for r in refs + refs2]
    if len(ids) == 3 and all(i in notes for i in ids):
        def num_run(fid):
            return next((r for pp in notes[fid] for r in pp.el.iter(w("r")) if r.find(w("footnoteRef")) is not None),
                        None)
        d_num, a_num, u_num = (num_run(i) for i in ids)
        check(f"{name}: 脚注の番号の色 (削除 = 取消線 + 削除の色・追加 = 追加の色・変えていない = 色なし)",
              d_num is not None and _rpr_strike(d_num) and _rpr_color(d_num) == prd.DIFF_DEL_COLOR
              and a_num is not None and _rpr_color(a_num) == prd.DIFF_ADD_COLOR
              and u_num is not None and _rpr_color(u_num) is None)
        check(f"{name}: 脚注の本文の色",
              [mk for pp in notes[ids[0]] for mk in pp.marks] == [("-", "The original note text.")]
              and [mk for pp in notes[ids[1]] for mk in pp.marks] == [("+", "The revised note text.")]
              and [mk for pp in notes[ids[2]] for mk in pp.marks] == [], {i: notes[i] for i in ids})
    else:
        check(f"{name}: 脚注が 3 つ (削除・追加・変えていない)", False, (ids, list(notes)))


def case_footnote_eq(name, d):
    bms = [b.get(w("name")) for r in d.roots.values() for b in r.iter(w("bookmarkStart"))]
    check(f"{name}: 脚注の中の式のラベル eq:fn は 1 つだけ (新の式)", bms.count("eq:fn") == 1, bms)
    note_marks = [mk for ps in d.note_paras().values() for pp in ps for mk in pp.marks]
    check(f"{name}: 脚注の中の旧の式は削除・新の式は追加の色",
          any(k == "-" and "x=1" in t for k, t in note_marks) and any(k == "+" and "x=2" in t for k, t in note_marks),
          note_marks)
    p = d.find("See ")
    check(f"{name}: 参照は色なし・番号つき", p is not None and p.marks == [] and f"Eq.{NBSP}1" in p.text, p)


def case_relabel(name, d):
    p = d.find("The summary")
    check(f"{name}: 変えていない文の参照は変更なし (Table 1・Fig. 1。¿ にならない)",
          p is not None and p.marks == [] and f"Table{NBSP}1" in p.text and f"Fig.{NBSP}1" in p.text, p)
    p = d.find("Table 1")
    check(f"{name}: 表の題の差分 (表は対のまま)",
          p is not None and p.marks == [("-", "Mean score for each of the three interaction conditions."),
                                        ("+", "Summary of outcomes.")], p)
    p = d.find("Figure 1")
    check(f"{name}: 画像の同じ図は対のまま題の差分",
          p is not None and p.marks == [("-", "Photograph of the device on the bench."),
                                        ("+", "Schematic drawing of the apparatus.")], p)
    check(f"{name}: 色は 2 つの題だけ (セルは色なし)", len(d.all_marks()) == 4, d.all_marks())


def case_wide(name, d):
    check(f"{name}: 表を ::: wide で囲んだだけなら色は 1 つも無い", d.all_marks() == [], d.all_marks())
    caps = [p for p in d.paras if p.text.startswith("Table 1")]
    check(f"{name}: 表は 1 つ (削除 + 追加にならない)", len(caps) == 1, caps)
    leg = [i for i, p in enumerate(d.paras) if p.text.startswith("Values are")]
    check(f"{name}: 凡例は 1 つ", len(leg) == 1, leg)


CASES = {
    "text": case_text,
    "case": case_case,
    "cell": case_cell,
    "tables": case_tables,
    "equation": case_equation,
    "figure": case_figure,
    "footnote": case_footnote,
    "footnote-eq": case_footnote_eq,
    "relabel": case_relabel,
    "wide": case_wide,
}
ABE_CASES = ("equation", "wide", "case", "footnote")


# =====================================================================
# 部品の試験 (差分 docx を作らない)
# =====================================================================

def unit_label_renames():
    """付け替えの判定: 題が似ていても中身・画像の違う図表は付け替えとみなさない。正しい付け替えは保つ。"""
    print("== 部品: ラベルの付け替えの判定 (ast_diff._label_renames)")
    import io
    import subprocess
    import panflute as pf

    def doc(md):
        r = subprocess.run(["pandoc", "--defaults", diff_docx.DEFAULTS_YAML, "-t", "json"], input=md,
                           capture_output=True, text=True, check=True)
        return pf.load(io.StringIO(r.stdout))

    tbl = ": {cap} {{#tbl:{lbl}}}\n\n| Condition | {col} |\n|:--|--:|\n| {a} | {x} |\n| {b} | {y} |\n"
    o = doc(tbl.format(cap="Mean score for each condition.", lbl="score", col="Mean", a="Staring", x="2.6",
                       b="Touch", y="1.2")
            + "\n![Overview of the apparatus.](figs/a.png){#fig:app}\n")
    n = doc(tbl.format(cap="Number of trials for each condition.", lbl="trials", col="Trials", a="Alpha", x="12",
                       b="Beta", y="5")
            + "\n![Overview of the results.](figs/b.png){#fig:res}\n")
    r = ast_diff._label_renames(o, n)
    check("題が似ていても中身の違う表・画像の違う図は付け替えとみなさない", r == {}, r)
    o = doc(tbl.format(cap="Mean score per condition.", lbl="a", col="Mean", a="Staring", x="2.6", b="Touch", y="1.2")
            + "\n![Overview of the apparatus.](figs/a.png){#fig:app}\n")
    n = doc(tbl.format(cap="Mean score for each condition.", lbl="b", col="Mean", a="Staring", x="2.6", b="Touch",
                       y="1.2")
            + "\n![A schematic view.](figs/a.png){#fig:sch}\n")
    r = ast_diff._label_renames(o, n)
    check("題が似て中身の同じ表・画像の同じ図は付け替え", r == {"tbl:a": "tbl:b", "fig:app": "fig:sch"}, r)


def _xml(s):
    return etree.fromstring(f'<w:document xmlns:w="{W_NS}" xmlns:m="{M_NS}"><w:body>{s}</w:body></w:document>')


def unit_equation_number_rpr():
    """番号の m:r の w:rPr を「式 TAB (N)」の番号の w:r に移す。w:rPr が無ければ (build) 書式なしのまま。"""
    print("== 部品: 式番号の後処理の書式 (equations.convert)")
    rpr = f'<w:rPr><w:rStyle w:val="DiffAdd"/><w:color w:val="{prd.DIFF_ADD_COLOR}"/></w:rPr>'
    eq = ('<w:p><w:pPr/><w:bookmarkStart w:id="{i}" w:name="eq:{i}"/><m:oMathPara><m:oMath>'
          '<m:r>{rpr}<m:t>x</m:t></m:r><m:r>{rpr}<m:t>  </m:t></m:r><m:r>{rpr}<m:t>({i})</m:t></m:r>'
          '</m:oMath></m:oMathPara><w:bookmarkEnd w:id="{i}"/></w:p>')
    root = _xml(eq.format(i=1, rpr=rpr) + eq.format(i=2, rpr=""))
    done, skipped = equations.convert(root, "Equation")
    check("2 つの式を組み替える", len(done) == 2 and not skipped, (done, skipped))
    nums = [[r for r in p.findall(w("r")) if _run_text(r).startswith("(")] for p in done]
    check("差分の書式つきの番号は書式ごと移る",
          len(nums[0]) == 1 and _run_kind(nums[0][0]) == "+" and _rpr_color(nums[0][0]) == prd.DIFF_ADD_COLOR,
          [etree.tostring(r) for r in nums[0]])
    check("書式の無い番号 (build) は書式なしのまま",
          len(nums[1]) == 1 and nums[1][0].find(w("rPr")) is None, [etree.tostring(r) for r in nums[1]])


def unit_equation_tabs():
    """1 段組の文書でも、本文の節の段の幅 (reference.docx から) との差だけ右タブをずらす。"""
    print("== 部品: 1 段組の文書の式番号の右タブ (equations.fit_tabs)")
    styles = etree.fromstring(
        f'<w:styles xmlns:w="{W_NS}"><w:style w:type="paragraph" w:styleId="Equation"><w:name w:val="Equation"/>'
        '<w:pPr><w:tabs><w:tab w:val="right" w:pos="4678"/></w:tabs></w:pPr></w:style></w:styles>')
    style = styles.find(w("style"))
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1418" w:right="851" w:bottom="1134" w:left="851" w:gutter="0"/><w:cols w:space="425"/></w:sectPr>')
    para = '<w:p><w:pPr><w:pStyle w:val="Equation"/></w:pPr></w:p>'
    root = _xml(para + sect)
    p = root.find(f"{w('body')}/{w('p')}")
    n = equations.fit_tabs(root, styles, [p], style, body_colw=(11906 - 851 * 2 - 754) / 2)
    tabs = [(t.get(w("val")), t.get(w("pos"))) for t in p.iter(w("tab"))]
    check("本文の節 (2 段組・段の幅 4 725 twip) の基準で 1 段組の文書の右タブを 10 157 twip に",
          n == 1 and tabs == [("clear", "4678"), ("right", "10157")], (n, tabs))
    root = _xml(para + sect)
    p = root.find(f"{w('body')}/{w('p')}")
    n = equations.fit_tabs(root, styles, [p], style)
    check("段の幅を渡さなければ既定のまま (出力の最終の節を本文の節とみなし、タブを変えない)", n == 0, n)


def unit_wide_ast():
    """マージ AST で、表は wide の Div の中に 1 つだけ・差分の Span は無い。"""
    print("== 部品: 段抜きの Div の透過 (ast_diff.diff_documents)")
    old = diff_docx._pandoc_to_ast(FIXTURES / "wide" / "old.md")
    new = diff_docx._pandoc_to_ast(FIXTURES / "wide" / "new.md")
    merged = ast_diff.diff_documents(old, new)
    spans = []
    merged.walk(lambda e, _d: spans.append(e) if e.tag == "Span" and set(e.classes) & {"diff-add", "diff-del"}
                else None)
    wides = [b for b in merged.content if b.tag == "Div" and list(b.classes) == ["wide"]]
    tables = []
    merged.walk(lambda e, _d: tables.append(e) if e.tag == "Table" else None)
    check("差分の Span が無い・表は wide の Div の中に 1 つ",
          not spans and len(tables) == 1 and len(wides) == 1 and wides[0].content[0].tag == "Table",
          (len(spans), len(tables), [b.tag for b in merged.content]))


# =====================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--abe", action="store_true", help="abe でも回す (学会テンプレートから作った reference.docx が要る)")
    ap.add_argument("--keep", help="差分 docx とログを残すディレクトリ (既定は一時ディレクトリで消す)")
    ap.add_argument("--only", action="append", help="このフィクスチャだけ (複数可)")
    ap.add_argument("--require-journal", action="append", default=[], metavar="ID",
                    help="この誌のプロファイルが無ければ不合格にする (既定は黙って飛ばす。複数可)")
    args = ap.parse_args(argv)
    # --require-journal で求めた誌が無ければ不合格にする (黙って飛ばすと、誌が欠けても件数が減るだけで合格するため)
    for journal in args.require_journal:
        if not (ROOT / "data" / "journals" / journal / "profile.yaml").is_file():
            check(f"{journal} のプロファイルがある (--require-journal)", False,
                  f"無い: data/journals/{journal}/profile.yaml")

    unit_label_renames()
    unit_equation_number_rpr()
    unit_equation_tabs()
    unit_wide_ast()

    # 誌のプロファイルが無い誌は黙って飛ばす (bhi は BHI 版のテンプレートにある誌。scripts/check-diff.sh と同じ条件)
    journals = [j for j in ("_default", "bhi") if (ROOT / "data" / "journals" / j / "profile.yaml").is_file()]
    journals += ["abe"] if args.abe else []
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(args.keep) if args.keep else Path(tmp)
        workdir.mkdir(parents=True, exist_ok=True)
        for journal in journals:
            for case, fn in CASES.items():
                if args.only and case not in args.only:
                    continue
                if journal == "abe" and case not in ABE_CASES:
                    continue
                name = f"{case} ({journal})"
                print(f"== {name}")
                d, log = run_diff(case, journal, workdir)
                if d is None:
                    tail = "\n      ".join(log.strip().splitlines()[-8:])
                    check(f"{name}: 差分 docx ができる", False, tail)
                    continue
                common_checks(name, d)
                if case == "equation":
                    fn(name, d, abe=(journal == "abe"))
                else:
                    fn(name, d)
    print(f"NG {len(NG)}" + (f": {NG}" if NG else ""))
    return 1 if NG else 0


if __name__ == "__main__":
    sys.exit(main())
