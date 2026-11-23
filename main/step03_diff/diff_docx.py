#!/usr/bin/env python3
"""diff_docx.py — 旧/新 2 版の Markdown から全領域差分 docx を生成する (コンテナ内本体)。

docs/architecture.md §2.3 / docs/design-fullarea-diff.md。pandiff は使わない。処理は次の通り:

  1. 旧版・新版を各 `pandoc -t json` で AST 化する (pandoc は全構造を無損失で保持)。
     フィルタは掛けない (crossref/citeproc は描画段で掛ける)。reader は defaults.yaml の
     `markdown+east_asian_line_breaks`、crossref メタも defaults から両版に注入される。
  2. ast_diff.diff_documents() で構造保持 二層差分 → マージ AST (構造温存 + 差分 span)。
  3. マージ AST を `pandoc -f json` で docx 化する。引数は build (§2.2) と同粒度:
     crossref → generic-style.lua → citeproc → (unnumbered-style.lua) → color-diff.lua の順でフィルタを掛け、
     reference.docx / CSL / bibliography / resource-path / defaults.yaml (と誌の crossref の上書き) を渡す。
     pandoc が色を付けない差分の中の式とリンク (図表・式の参照) と脚注の参照に、目印のブックマークを頼りに差分の書式を付ける
     (_color_diff_marks)。
  4. OOXML 後処理 (step02 共用 postprocess): 表罫線・ネイティブ SVG 埋込・textbox。
     さらに生成 docx の word/styles.xml へ文字スタイル DiffAdd/DiffDel を冪等注入する
     (雑誌提供テンプレが 2 スタイルを持たなくても差分色が出る)。注入定義は
     reference.docx を焼く patch_reference_docx.inject_diff_styles と同一 (単一の真実)。

雑誌プロファイル解決 (reference.docx / CSL の _default 継承) は build_docx と共通実装を流用する。

使い方 (通常は scripts/diff.sh 経由):
    python3 diff_docx.py --input-root data/dummy --journal _default \
        --old jank/old.md --new data/dummy/main.md \
        --out data/step03_diff/main_diff.docx [--no-embed-svg] [--no-relocate]
"""

import argparse
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from lxml import etree

# step02_build (build_docx の profile 解決 / postprocess) と 00_setup/lib (styles 注入) を import 可能に
_THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS))
sys.path.insert(0, str(_THIS.parent / "step02_build"))
sys.path.insert(0, str(_THIS.parent / "00_setup" / "lib"))

import panflute as pf  # noqa: E402

import ast_diff  # noqa: E402
import postprocess  # noqa: E402
import patch_reference_docx as prd  # noqa: E402
import docx_styles  # noqa: E402
# profile は共通モジュール journal_profile で読む (build_docx の内部の読み込み関数は借りない)。
#   profile を読む処理を使う側は build_docx / package / validate と本ファイルの 4 箇所あり、
#   共通モジュール経由に揃えることで、差分経路もスキーマ既定値と記事種別の解決を通るようにする。
import journal_profile  # noqa: E402
from build_docx import (_resolve_asset, caption_options, crossref_defaults, layout_for,  # noqa: E402
                        post_citeproc_args)

DEFAULTS_YAML = "main/00_setup/defaults.yaml"
GENERIC_FILTER = "main/00_setup/filters/generic-style.lua"
COLOR_DIFF_FILTER = "main/00_setup/filters/color-diff.lua"


def _pandoc_to_ast(md_path):
    """Markdown を pandoc -t json でフィルタ無し AST 化し panflute Doc を返す。

    defaults.yaml を渡すので reader 拡張 (east_asian_line_breaks) と crossref メタが入る。
    crossref / citeproc / generic-style は描画段で掛けるため、ここでは掛けない。
    """
    cmd = ["pandoc", str(md_path), "--defaults", DEFAULTS_YAML, "-t", "json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"エラー: pandoc -t json が失敗しました ({md_path})\n{res.stderr}")
    return pf.load(io.StringIO(res.stdout))


def _inject_diff_styles_into_docx(docx_path):
    """生成 docx の word/styles.xml へ DiffAdd/DiffDel を冪等注入する。

    定義は patch_reference_docx.inject_diff_styles と共通 (単一の真実)。_default の
    reference.docx は既に 2 スタイルを持つが、雑誌提供テンプレ (持たない) でも差分色が出るよう
    描画後にも必ず注入する。inject_diff_styles は同 id を一度消してから付け直すため冪等。
    """
    with zipfile.ZipFile(docx_path, "r") as zin:
        parts = {item.filename: zin.read(item.filename) for item in zin.infolist()}
    styles_name = "word/styles.xml"
    if styles_name not in parts:
        print("  警告: word/styles.xml が無く DiffAdd/DiffDel を注入できません")
        return
    root = etree.fromstring(parts[styles_name])
    prd.inject_diff_styles(root)
    parts[styles_name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                        standalone=True)
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            zout.writestr(name, data)
    print("  DiffAdd/DiffDel を styles.xml へ注入 (冪等)")


M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_DIFF_MARK = re.compile(r"^(DiffAdd|DiffDel)Mark\d+$")


def _w(tag):
    return f"{{{W_NS}}}{tag}"


def _math_run_rpr(style):
    """式の文字 (m:r) に付ける w:rPr。差分の文字スタイルの参照と、そのスタイルと同じ書式 (色・取消線) を直に持たせる
    (Word が式の中で文字スタイルを読まない場合にも色が出るように)。値は patch_reference_docx の定義と同じ (単一の真実)。
    子の順は CT_RPr の順 (rStyle → strike → color)。"""
    rpr = etree.Element(_w("rPr"))
    etree.SubElement(rpr, _w("rStyle")).set(_w("val"), style)
    if style == "DiffDel":
        etree.SubElement(rpr, _w("strike"))
    color = prd.DIFF_DEL_COLOR if style == "DiffDel" else prd.DIFF_ADD_COLOR
    etree.SubElement(rpr, _w("color")).set(_w("val"), color)
    return rpr


NOTE_PARTS = (("footnote", "word/footnotes.xml"), ("endnote", "word/endnotes.xml"))


def _note_ref_rpr(r, style):
    """脚注の参照・脚注の番号の run (w:r) に差分の書式 (削除は取消線 + 色) を直に付ける。文字スタイル (脚注の参照 = 上付き) は残す。
    値は patch_reference_docx の定義と同じ (単一の真実)。"""
    rpr = r.find(_w("rPr"))
    if rpr is None:
        rpr = etree.Element(_w("rPr"))
        r.insert(0, rpr)
    if style == "DiffDel":
        docx_styles.rpr_set(rpr, etree.Element(_w("strike")))
    color = etree.Element(_w("color"))
    color.set(_w("val"), prd.DIFF_DEL_COLOR if style == "DiffDel" else prd.DIFF_ADD_COLOR)
    docx_styles.rpr_set(rpr, color)


def _scan_diff_marks(root):
    """パート 1 つの中の目印のブックマークと、その範囲の中の式の文字・リンクの文字・脚注の参照の run を集める。"""
    active = {}            # ブックマークの w:id → スタイル名 (開いた順)
    marks, math_runs, link_runs, ref_runs = [], [], [], []
    for el in root.iter(_w("bookmarkStart"), _w("bookmarkEnd"), f"{{{M_NS}}}r", _w("r")):
        if el.tag == _w("bookmarkStart"):
            m = _DIFF_MARK.match(el.get(_w("name")) or "")
            if m:
                active[el.get(_w("id"))] = m.group(1)
                marks.append(el)
        elif el.tag == _w("bookmarkEnd"):
            if el.get(_w("id")) in active:
                del active[el.get(_w("id"))]
                marks.append(el)
        elif not active:
            continue
        elif el.tag == f"{{{M_NS}}}r":
            math_runs.append((el, list(active.values())[-1]))
        elif el.find(_w("footnoteReference")) is not None or el.find(_w("endnoteReference")) is not None:
            ref_runs.append((el, list(active.values())[-1]))
        elif el.getparent() is not None and el.getparent().tag == _w("hyperlink"):
            link_runs.append((el, list(active.values())[-1]))
    return marks, math_runs, link_runs, ref_runs


def _color_diff_marks(docx_path):
    """差分の Span の中の式・リンク・脚注の参照に差分の書式を付ける。

    pandoc の docx ライタは、式 (OMML) には文字スタイル (custom-style) を掛けず、リンク (pandoc-crossref の Fig. 1 / Table 2 /
    Eq. 1 などの参照) の文字には Hyperlink の文字スタイルを、脚注の参照には脚注の参照の文字スタイルを掛けるので、差分の Span で
    包んでも式は黒・参照はリンクの色・脚注の番号は黒のままになる (旧と新が見分けられずに並ぶ)。color-diff.lua が式・リンク・脚注を含む
    差分 Span に識別子 DiffAddMark<N> / DiffDelMark<N> を付け、pandoc がそれをブックマークとして書くので、その範囲の中の
      - 式の文字 (m:r) に w:rPr (_math_run_rpr) を付け、
      - リンクの中の文字 (w:hyperlink の中の w:r) の文字スタイルを差分の文字スタイルに替え (リンクは残る)、
      - 脚注の参照の run と、その脚注の番号 (w:footnoteRef) の run に差分の書式を直に付け (_note_ref_rpr。脚注の本文には
        color-diff.lua が差分の文字スタイルを付けてある)、
    ブックマークを消す。本文のほか脚注・文末脚注のパートも見る (脚注の本文の式とリンク)。範囲は文書の順に追う (式が段落を分けて
    出ても範囲は保たれる)。後処理 (式番号の右寄せ・著者の脚注の記号など) の前に掛ける — 目印のブックマークが残ると「式だけの段落」の
    判定に掛からなくなるため。戻り値: (式の文字の数, リンクの文字の数, 脚注の参照の数)。
    """
    with zipfile.ZipFile(docx_path, "r") as zin:
        parts = {item.filename: zin.read(item.filename) for item in zin.infolist()}
    names = [n for n in ("word/document.xml", *(part for _k, part in NOTE_PARTS)) if b"Mark" in parts.get(n, b"")]
    if not names:
        return 0, 0, 0
    roots, changed = {}, set()
    n_math = n_link = n_ref = 0
    note_styles = {}       # (footnote / endnote, w:id) → スタイル名
    for name in names:
        root = roots[name] = etree.fromstring(parts[name])
        marks, math_runs, link_runs, ref_runs = _scan_diff_marks(root)
        if not marks:
            continue
        for mr, style in math_runs:
            old = mr.find(_w("rPr"))
            if old is not None:
                mr.remove(old)
            mrpr = mr.find(f"{{{M_NS}}}rPr")
            mr.insert(0 if mrpr is None else list(mr).index(mrpr) + 1, _math_run_rpr(style))
        for r, style in link_runs:
            rpr = r.find(_w("rPr"))
            if rpr is None:
                rpr = etree.Element(_w("rPr"))
                r.insert(0, rpr)
            rs = rpr.find(_w("rStyle"))
            if rs is None:
                rs = etree.Element(_w("rStyle"))
                rpr.insert(0, rs)
            rs.set(_w("val"), style)
        for r, style in ref_runs:
            _note_ref_rpr(r, style)
            for kind, _part in NOTE_PARTS:
                ref = r.find(_w(kind + "Reference"))
                if ref is not None:
                    note_styles[(kind, ref.get(_w("id")))] = style
        for el in marks:
            el.getparent().remove(el)
        changed.add(name)
        n_math, n_link, n_ref = n_math + len(math_runs), n_link + len(link_runs), n_ref + len(ref_runs)
    # 脚注の側の番号 (w:footnoteRef / w:endnoteRef) の run にも同じ書式を付ける
    for kind, part in NOTE_PARTS:
        ids = {i: st for (k, i), st in note_styles.items() if k == kind}
        if not ids or part not in parts:
            continue
        root = roots.get(part)
        if root is None:
            root = roots[part] = etree.fromstring(parts[part])
        for note in root.findall(_w(kind)):
            st = ids.get(note.get(_w("id")))
            if st is None:
                continue
            for num in note.iter(_w(kind + "Ref")):
                _note_ref_rpr(num.getparent(), st)
                changed.add(part)
    if not changed:
        return 0, 0, 0
    for name in changed:
        parts[name] = etree.tostring(roots[name], xml_declaration=True, encoding="UTF-8", standalone=True)
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for n, data in parts.items():
            zout.writestr(n, data)
    return n_math, n_link, n_ref


def build_diff(input_root, journal_id, old_md, new_md, out, embed_svg=True, no_relocate=False,
               article_type=None):
    input_root = Path(input_root)
    out = Path(out)
    old_md = Path(old_md)
    new_md = Path(new_md)
    for p in (old_md, new_md):
        if not p.is_file():
            sys.exit(f"エラー: 原稿が見つかりません: {p}")

    # 記事種別を解決する (差分は種別で出力を変えないが、未知種別の早期エラーのためここで解決。
    # build_docx.build() と同じ扱い)
    profile = journal_profile.load_resolved(journal_id, article_type)
    reference_doc = _resolve_asset(journal_id, profile.get("reference_doc"),
                                   "reference.docx", "reference_doc")
    csl = _resolve_asset(journal_id, profile.get("csl"), "_default.csl", "csl")
    # 題と凡例・式番号の後処理の指定 (build と同じ解釈。併用できない指定なら変換の前に止める)
    caption_opts = caption_options(profile, reference_doc)   # 式番号の段の幅は reference.docx から

    resource_path = ["data/step01_figures", str(input_root / "figs"), "."]
    bib = input_root / "ref.bib"

    out.parent.mkdir(parents=True, exist_ok=True)

    # --- 1+2. 旧/新 AST 化 → 構造保持 二層差分 → マージ AST ---
    print(f"== 差分: {old_md} (旧) vs {new_md} (新) -> {out} ==")
    print(f"  journal={journal_id}  reference={reference_doc}  csl={csl}")
    old_doc = _pandoc_to_ast(old_md)
    new_doc = _pandoc_to_ast(new_md)
    merged = ast_diff.diff_documents(old_doc, new_doc)

    merged_json = str(out) + ".merged.json"
    with open(merged_json, "w", encoding="utf-8") as f:
        pf.dump(merged, f)

    # --- 3. マージ AST を docx 化 (crossref → generic-style → citeproc → color-diff) ---
    manifest = str(out) + ".images.tsv"
    # 誌ごとの crossref の上書き (build と同じく defaults.yaml の後の 2 つ目の --defaults。json 入力でも効く)。
    # 旧版・新版の AST 化 (_pandoc_to_ast) には渡さない — crossref の設定は描画で掛ける pandoc-crossref だけが読むため
    crossref_yaml = out.with_name(f".{out.stem}.crossref.yaml")
    crossref_args, crossref_note = crossref_defaults(profile, crossref_yaml)
    if crossref_note:
        print(crossref_note)
    cmd = [
        "pandoc", merged_json,
        "--defaults", DEFAULTS_YAML,
        *crossref_args,
        "--from", "json",                     # defaults の from(markdown) を上書き
        "-M", f"image-manifest={manifest}",
        "--to", "docx",
        f"--reference-doc={reference_doc}",
        f"--resource-path={':'.join(resource_path)}",
        "--filter", "pandoc-crossref",
        "--lua-filter", GENERIC_FILTER,
        "--citeproc",
        f"--csl={csl}",
        # 番号なしの見出しの写像 (headings.unnumbered_style のある誌だけ。build と同じく citeproc の後) と
        # 段抜きの目印 (layout.columns のある誌だけ)
        *post_citeproc_args(profile, reference_doc),
        "--lua-filter", COLOR_DIFF_FILTER,    # citeproc の後 (引用解決後に span を写像)
        f"--output={out}",
    ]
    if bib.is_file():
        cmd.append(f"--bibliography={bib}")
    else:
        print(f"  注意: {bib} が無いため文献解決なし")
    print("  pandoc " + " ".join(cmd[1:]))
    try:
        res = subprocess.run(cmd)
    finally:
        crossref_yaml.unlink(missing_ok=True)
    if res.returncode != 0:
        sys.exit(f"エラー: pandoc (描画) が失敗しました (exit {res.returncode})")

    # 式とリンクと脚注の差分の色 (pandoc は式に文字スタイルを掛けず、リンクには Hyperlink を、脚注の参照には脚注の参照の文字スタイルを
    # 掛ける。後処理の前に目印のブックマークを消す)
    n_math, n_link, n_ref = _color_diff_marks(str(out))
    if n_math or n_link:
        print(f"  差分の式と参照: 式の文字 {n_math} 個・リンクの文字 {n_link} 個に削除・追加の書式を付けた")
    if n_ref:
        # 行を分けるのは、脚注の無い差分 (既存の誌の回帰スナップショット) のログを変えないため
        print(f"  差分の脚注: 脚注の参照 {n_ref} 個と脚注の番号に削除・追加の書式を付けた")

    # --- 4. OOXML 後処理 (表罫線 / SVG 埋込 / textbox / 前付け (柱・所属のタブ・著者の脚注の記号) / 段組の節) + DiffAdd/DiffDel 注入 ---
    # 柱 (header.*) は running title の段落から削除 (DiffDel) の文字を除いた文字列を使う。
    # 段組の節 (layout.*) は本文の差分なので build の main.md と同じく組み立てる
    postprocess.process_docx(
        str(out),
        source_md=None,                       # 画像はマニフェスト (マージ AST 由来) で照合
        resource_path=resource_path,
        embed_svg=embed_svg,
        no_relocate=no_relocate,
        image_manifest=manifest,
        running_header=journal_profile.running_header(profile),
        affiliation_label_tab=journal_profile.affiliation_label_tab(profile),
        # 著者の脚注の記号。削除した脚注は旧版の並びの記号、ほかは新版の並びの記号 (脚注の本文の差分の文字スタイルで見分ける)
        author_footnote_marks=journal_profile.author_footnote_marks(profile),
        # 出力の見出しのスタイルが自動番号を持つかを毎回確かめる (テンプレートの自動番号で見出しに番号を付ける誌 = headings.unnumbered_style のある誌の、
        # 番号を残す文書だけ)
        expect_numbered_headings=(journal_profile.unnumbered_style(profile) is not None
                                  and journal_profile.heading_numbers_kept(profile, is_manuscript=True)),
        is_manuscript=True,
        layout_cfg=layout_for(profile, reference_doc, is_manuscript=True),
        **caption_opts,                       # 題と凡例・式番号 (tables.legend_position / figures.keep_together / equations.style)・
                                              # 文献の番号の区切り (bibliography.label_separator)
    )
    _inject_diff_styles_into_docx(str(out))

    Path(manifest).unlink(missing_ok=True)
    Path(merged_json).unlink(missing_ok=True)
    print(f"== 完了: {out} ==")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input-root", required=True, help="図/文献の入力ルート (data/dummy または src)")
    p.add_argument("--journal", default="_default", help="雑誌プロファイル id (既定 _default)")
    p.add_argument("--old", required=True, help="旧版 Markdown")
    p.add_argument("--new", required=True, help="新版 Markdown")
    p.add_argument("--out", required=True, help="出力 diff docx パス")
    p.add_argument("--no-embed-svg", action="store_true", help="ネイティブ SVG 埋込をしない")
    p.add_argument("--no-relocate", action="store_true", help="textbox の page 配置移動をしない")
    # 注意: 記事種別は差分の出力を変えない (差分が profile から読むのは体裁のキーで、記事種別ごとの上限などは読まない)。
    # --article-type を受けるのは (1) 未知種別の早期エラー (2) build.sh と引数を揃えて README の
    # 例 (diff.sh --journal abe --article-type original) で利用者が異常終了に当たらないようにするため。
    p.add_argument("--article-type", default=None,
                   help="記事種別 (article_types を持つ誌のみ。差分の出力は変えない)")
    args = p.parse_args(argv)
    build_diff(
        args.input_root, args.journal, args.old, args.new, args.out,
        embed_svg=not args.no_embed_svg, no_relocate=args.no_relocate,
        article_type=args.article_type,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
