#!/usr/bin/env python3
"""test_validate_abe.py — validate.py の ABE の検査の回帰試験。

ABE の検査 15 種の一部 (補足資料の容量とアーカイブ・running title が無い・資金が節の外・AI の開示が無い) は、適合原稿と
不適合原稿のどちらでも発火しないので、壊れても気づけない。本試験はそれらと、誤検出・見逃しを起こしやすい形を、
追跡するフィクスチャと、適合原稿 data/dummy/abe を 1 か所ずつ変えた変種で固定する。

  1. 適合原稿 data/dummy/abe … 要修正 0・参考 0
  2. 不適合原稿 data/dummy/abe-lint … 要修正 12・参考 15 (指摘ごとに文面の一部を照合する)
  3. 不適合原稿の変種 data/dummy/abe-lint/variants/ (abe-lint と同時には起こせない違反):
       run-funding-ai … running title が無い・資金が節の外・AI の開示が無い / missing-divs … 表題ページの Div の欠落と重複
  4. 補足資料の容量 … 50 MB のファイルは追跡に向かないので、abe-lint の補足資料 (数百バイト) を、この試験の中だけで
     上限を数百バイトに下げた profile で検査する
  5. data/dummy/abe を 1 か所ずつ変えた変種 (一時ディレクトリに書く) … 誤検出しないこと (要修正 0・参考 0 のまま) と、
     見逃さないこと (決まった指摘が出ること)
  6. 走査層と照合の部品の単体の確認 (setext の見出し・パイプでない表・数式の字数・複数形・著者名の切り分け・構造化抄録のラベル)
  7. ほかの誌のフィクスチャの件数 (data/dummy = _default 0/0。誌 bhi とその動作例があれば、適合原稿 0/0・不適合原稿 23/4) が
     変わらないこと (bhi は BHI 版 docx-paper-template-jbi-public にある誌。無ければ黙って飛ばす)

誌のプロファイルや動作例が無い誌の試験は黙って飛ばす。--require-journal <誌> を付けると、その誌が欠けていれば
不合格にする (誌を同梱する作業ツリーで、試験の抜けを止めるため)。

reference.docx の有無で指摘が変わる検査 (体裁の突合・custom-style の有無) は除くため、validate() に journal_id を渡さない。
pytest は導入していないので素の assert 相当で書く。コンテナ内で実行する:
  docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \\
      python3 main/step05_package/test_validate_abe.py [--require-journal <誌>]
全件通れば exit 0、1 件でも外れれば exit 1。
"""

import copy
import io
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import validate  # noqa: E402
import journal_profile  # noqa: E402

DUMMY = ROOT / "data" / "dummy"
ABE = DUMMY / "abe"
ABE_LINT = DUMMY / "abe-lint"
BASE_MD = (ABE / "main.md").read_text(encoding="utf-8")

RESULTS = []
REQUIRED = set()   # --require-journal で求めた誌 (欠けていれば不合格にする)


def present(journal, *roots):
    """誌のプロファイルと動作例がすべてあるか。無ければ False を返し、その試験を飛ばす。

    飛ばすときは黙って飛ばす (誌を同梱しない作業ツリーで、毎回「飛ばした」と出すと利用者を惑わせるため)。
    ただし --require-journal で求めた誌が欠けていれば、欠けたパスを示して不合格にする (黙って飛ばすと、誌が欠けても
    件数が減るだけで合格するため)。"""
    paths = (ROOT / "data" / "journals" / journal / "profile.yaml", *roots)
    missing = [p for p in paths if not p.exists()]
    if missing and journal in REQUIRED:
        check(f"{journal} のプロファイルと動作例がある (--require-journal)", False,
              "無い: " + ", ".join(str(p.relative_to(ROOT)) for p in missing))
    return not missing


def check(desc, ok, detail=""):
    RESULTS.append((desc, bool(ok), detail))


def run(root, journal="abe", article_type="original", profile=None):
    """validate() を回して (要修正の文面の list, 参考の文面の list, 概算の行の list) を返す。"""
    prof = profile if profile is not None else journal_profile.load(journal)
    est = []
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        found = validate.validate(str(root), prof, article_type, estimate=est)
    must = [validate.finding_text(f) for f in found if f.level == validate.LEVEL_MUST]
    info = [validate.finding_text(f) for f in found if f.level == validate.LEVEL_INFO]
    return must, info, est


def has(rows, *parts):
    """rows のどれか 1 行が parts をすべて含むか。"""
    return any(all(p in r for p in parts) for r in rows)


def show(must, info):
    return " | ".join([f"[要修正] {m[:90]}" for m in must] + [f"[参考] {i[:90]}" for i in info]) or "(指摘なし)"


def expect_counts(desc, got, n_must, n_info):
    must, info = got[0], got[1]
    check(f"{desc}: 要修正 {n_must}・参考 {n_info}", len(must) == n_must and len(info) == n_info,
          f"実際は 要修正 {len(must)}・参考 {len(info)}: {show(must, info)}")


def expect_rows(desc, got, wants):
    """wants = [(区分, (文面の一部, …)), …] がすべて出ているか。"""
    must, info = got[0], got[1]
    for level, parts in wants:
        rows = must if level == "要修正" else info
        check(f"{desc}: [{level}] {' … '.join(parts)}", has(rows, *parts), show(must, info))


# ---------------------------------------------------------------------
# 1〜4. 追跡するフィクスチャ
# ---------------------------------------------------------------------

def test_fixtures():
    expect_counts("data/dummy/abe (適合)", run(ABE), 0, 0)

    got = run(ABE_LINT)
    expect_counts("data/dummy/abe-lint", got, 12, 15)
    expect_rows("abe-lint", got, [
        ("要修正", ("抄録語数", "上限 350")),
        ("要修正", ("キーワード数 6",)),
        ("要修正", ("抄録に文献引用があります (yokan2099)",)),
        ("要修正", ("記入欄", "<<Describe the third part of the series>>")),
        ("要修正", ("構造化抄録の形です (見出し: Background / Results)",)),
        ("要修正", ("抄録が 2 段落あります", "見出しを外して 1 段落の文章に")),
        ("要修正", ("キーワードが題の語を繰り返しています: hunch。",)),
        ("要修正", ("running title が 63 字",)),
        ("要修正", ("姓がすべて大文字になっていない著者があります: Taro Yokan, Bonta Dan。",)),
        ("要修正", ("必須の節が見当たりません: Results / Discussion (",)),
        ("要修正", ("題 (キャプション) の無い図表があります: 図 (L", "), 表 (L", "), 表 (L")),
        ("要修正", ("表の題の属性に {#tbl:x} 以外のものがあります: {#tbl:supervisors .wide}", "::: wide")),
        ("参考", ("略語らしき語があります (TJD)",)),
        ("参考", ("シリーズ番号らしき部分があります (Part II)",)),
        ("参考", ("手で書いた引用らしい番号があります ([2])",)),
        ("参考", ("抄録が図表に触れています (Fig. 1, Supplementary Fig. S1)",)),
        ("参考", ("学位・敬称らしい語があります (PhD)",)),
        ("参考", ("上付きの数字 (^1^ など) で始まらない所属があります",)),
        ("参考", ("上付きの数字で所属を示していない著者があります: Taro Yokan, Hanako CHOKKAN, Bonta Dan",)),
        ("参考", ("Title Case のようです: fig:ths",)),
        ("参考", ("括弧の定義が見当たらない略語があります: THS",)),
        ("参考", ("Conflicts of interests の節", "定型文も具体的な申告も見当たりません")),
        ("参考", ("人や動物を扱うらしい語があります",)),
        ("参考", ("AI ツールらしき語が Materials and methods の節の外にだけあります (ChatGPT",)),
        ("参考", ("Acknowledgements の節", "助成番号らしき語が見当たりません")),
        ("参考", ("引けない文献の可能性があります: chokkan2100",)),
        ("参考", ("アーカイブ (圧縮) か実行形式らしいファイルがあります: analysis-code.tgz",)),
    ])
    check("abe-lint: 概算の表の点数に simple table を数える (表 3 点)", any("表 3 点" in e for e in got[2]), " / ".join(got[2]))

    got = run(ABE_LINT / "variants" / "run-funding-ai")
    expect_counts("abe-lint/variants/run-funding-ai", got, 1, 2)
    expect_rows("run-funding-ai", got, [
        ("要修正", ("題が 72 字", "running title", "がありません")),
        ("参考", ("資金らしき語が Acknowledgements の節の外にだけあります (funded",)),
        ("参考", ("AI ツールの使用の開示が見当たりません",)),
    ])

    got = run(ABE_LINT / "variants" / "missing-divs")
    expect_counts("abe-lint/variants/missing-divs", got, 3, 0)
    expect_rows("missing-divs", got, [
        ("要修正", ("Title の Div (custom-style=\"Title\") が見当たりません",)),
        ("要修正", ("Author の Div (custom-style=\"Author\") が見当たりません",)),
        ("要修正", ("Abstract の Div が 2 個あります",)),
    ])

    # 4. 補足資料の容量: この試験の中だけで上限を数百バイトに下げる (profile.yaml の 50 MB は変えない)
    supp = sorted((ABE_LINT / "supplementary").iterdir())
    sizes = {p.name: p.stat().st_size for p in supp}
    biggest = max(sizes, key=sizes.get)
    per = (sizes[biggest] - 1) / 1e6                       # いちばん大きいファイルだけが 1 バイト超える
    total = (sum(sizes.values()) - 1) / 1e6                # 合計が 1 バイト超える
    prof = copy.deepcopy(journal_profile.load("abe"))
    prof["limits"]["supplementary_file_mb"] = per
    prof["limits"]["supplementary_total_mb"] = total
    got = run(ABE_LINT, profile=prof)
    expect_rows("abe-lint (補足資料の上限を試験だけで下げる)", got, [
        ("要修正", ("1 ファイルの上限", f"{biggest} ({sizes[biggest]:,} バイト)")),
        ("要修正", ("補足資料の合計", f"{sum(sizes.values()):,} バイト ({len(sizes)} ファイル)")),
    ])
    others = [n for n in sizes if n != biggest]
    check("abe-lint (補足資料の上限): 上限以下のファイルは名指ししない",
          not any(f"{n} (" in m for m in got[0] for n in others), show(got[0], got[1]))

    # BHI の動作例 (構造化抄録が必須の誌の原稿) を ABE で検査すると構造化抄録を要修正にする (動作例が無ければ飛ばす)
    if present("bhi", DUMMY / "bhi"):
        got = run(DUMMY / "bhi")
        expect_rows("bhi の動作例を --journal abe で", got, [
            ("要修正", ("構造化抄録の形です (見出し: Objective / Methods / Results / Conclusion)",)),
            ("要修正", ("4 段落あります", "見出しを外して 1 段落の文章に")),
        ])


# ---------------------------------------------------------------------
# 5. data/dummy/abe を 1 か所ずつ変えた変種
# ---------------------------------------------------------------------

AUTH_FN = "^[Present address: Department of Gut Feeling, Hunch Institute of Technology, Gutsby, Fictionia.]"
TITLE = "Quantifying the Tremendous Hunch with a Purpose-Built Apparatus and a New Dimensional Scale"
KW = "**Keywords**: intuition, psychophysics, equipment design, reproducibility, cold sweat."
RUN = '::: {custom-style="Subtitle"}\nQuantifying the tremendous hunch\n:::'
COI = ("The authors declare no conflicts of interest with any companies or commercial organizations per the\n"
       "definition of Japanese Society for Medical and Biological Engineering.")
ACK_FUND = ("This work was supported by the Tremendous Hunch Promotion Foundation (grant\n"
            "number THPF-0000).")
ABS_END = "input is the step that would most improve the scale."
TBL_CAP = ": Mean score for each of the three interaction conditions. {#tbl:conditions}"
ADD_OBS = "## Additional observations"


def _abstract_block():
    s = BASE_MD.index('::: {custom-style="Abstract"}')
    return BASE_MD[s:BASE_MD.index("\n:::", s) + 4]


def _kw(*words):
    return "**Keywords**: " + ", ".join(words) + "."


def mutated(pairs):
    """data/dummy/abe/main.md の文字列を置き換えた原稿を一時ディレクトリに書いて検査する。置き換える文字列は 1 回だけ現れること。"""
    md = BASE_MD
    for old, new in pairs:
        n = md.count(old)
        if n != 1:
            raise SystemExit(f"変種の置き換え元 '{old[:50]}' が data/dummy/abe/main.md に {n} 回あります (1 回であること)")
        md = md.replace(old, new)
    tmp = Path(tempfile.mkdtemp(prefix="test_validate_abe_"))
    try:
        (tmp / "main.md").write_text(md, encoding="utf-8")
        shutil.copy(ABE / "ref.bib", tmp / "ref.bib")
        return run(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# 誤検出しないこと (要修正 0・参考 0 のまま)
NEGATIVE = [
    ("著者名の Jr. を著者と読まない", [("Taro YOKAN^1^", "John SMITH, Jr.^1^")]),
    ("カンマの後で折り返した著者の並び", [(", Bonta DAN^1^", ",\nBonta DAN^1^")]),
    ("名前の途中で折り返した著者を割らない", [("Taro YOKAN^1^", "Taro\nYOKAN^1^")]),
    ("姓の Ma を学位と取り違えない", [("Taro YOKAN^1^", "Wei MA^1^")]),
    ("新住所の脚注の中のリンク",
     [(AUTH_FN, "^[Present address: see [the lab page](https://example.org/lab), Gutsby, Fictionia.]")]),
    ("キーワードの接頭辞 non", [(TITLE, TITLE.replace("Purpose-Built", "Non-Invasive")),
                                    (KW, _kw("intuition", "psychophysics", "non-contact sensing", "reproducibility",
                                             "cold sweat"))]),
    ("キーワードの接頭辞 real", [(TITLE, TITLE.replace("Purpose-Built", "Real-Time")),
                                     (KW, _kw("intuition", "psychophysics", "real-world data", "reproducibility",
                                              "cold sweat"))]),
    ("キーワードの接頭辞 self", [(TITLE, TITLE.replace("Purpose-Built", "Self-Powered")),
                                     (KW, _kw("intuition", "psychophysics", "self-report", "reproducibility",
                                              "cold sweat"))]),
    ("setext の見出し", [("\n# Introduction\n", "\nIntroduction\n============\n")]),
    ("Methodology は Materials and methods の言い換え", [("\n# Materials and methods\n", "\n# Methodology\n")]),
    ("COI の具体的な申告と否定の文が並ぶ節", [(COI, "The first author received consulting fees from Fictional Scales, "
                                                 "and the other authors declare no conflicts of interest.")]),
    ("本文の supported by (資金ではない) と資金の無い謝辞",
     [(ACK_FUND, "We thank everyone."),
      ("\n# Discussion\n", "\n# Discussion\n\nThis view is supported by Smith et al. [@yokan2099].\n")]),
    ("抄録の 1 つだけのラベルらしい語 (In summary:)", [(ABS_END, ABS_END + " In summary: the ordering held.")]),
    ("Table: で題を書いた simple table",
     [(ADD_OBS, "Table: Scores of two extra trials. {#tbl:extra}\n\n  Trial   Score\n  -----   -----\n"
                "  21      2.4\n  22      0.9\n\n" + ADD_OBS)]),
    ("題のある grid table", [(ADD_OBS, ": Scores of two extra trials. {#tbl:extra}\n\n+-------+-------+\n"
                                     "| Trial | Score |\n+=======+=======+\n| 21    | 2.4   |\n+-------+-------+\n\n"
                                     + ADD_OBS)]),
    ("題のある multiline table", [(ADD_OBS, "-------------------\nTrial   Score\n-----   -----\n21      2.4\n\n"
                                          "22      0.9\n-------------------\n\n: Scores of two extra trials. "
                                          "{#tbl:extra}\n\n" + ADD_OBS)]),
    ("段落の間の水平線", [(ADD_OBS, "---\n\n" + ADD_OBS)]),
]

# 見逃さないこと: (説明, 置き換え, [(区分, (文面の一部, …))], 要修正の件数, 参考の件数)
POSITIVE = [
    ("学位 MD を大文字の姓と見なさない", [("Taro YOKAN^1^", "Taro Yokan MD^1^")],
     [("要修正", ("姓がすべて大文字になっていない著者があります: Taro Yokan。",)), ("参考", ("学位・敬称らしい語があります (MD)",))],
     1, 1),
    ("強制改行で並べた著者", [(f"Taro YOKAN^1^, Hanako CHOKKAN^2^{AUTH_FN}, Bonta DAN^1^",
                                    "Taro YOKAN^1^\\\nHanako Chokkan^2^\\\nBonta DAN^1^")],
     [("要修正", ("姓がすべて大文字になっていない著者があります: Hanako Chokkan。",))], 1, 0),
    ("改行で並べた著者", [(f"Taro YOKAN^1^, Hanako CHOKKAN^2^{AUTH_FN}, Bonta DAN^1^",
                                 "Taro YOKAN^1^\nHanako Chokkan^2^\nBonta DAN^1^")],
     [("要修正", ("姓がすべて大文字になっていない著者があります: Hanako Chokkan。",))], 1, 0),
    ("不規則な複数形 apparatuses",
     [(KW, _kw("intuition", "psychophysics", "apparatuses", "reproducibility", "cold sweat"))],
     [("要修正", ("キーワードが題の語を繰り返しています: apparatuses。",))], 1, 0),
    ("不規則な複数形 analyses",
     [(TITLE, TITLE.replace("Apparatus", "Analysis")),
      (KW, _kw("intuition", "psychophysics", "analyses", "reproducibility", "cold sweat"))],
     [("要修正", ("キーワードが題の語を繰り返しています: analyses。",))], 1, 0),
    ("Resultant を Results と見なさない", [("\n# Results\n", "\n# Resultant observations\n")],
     [("要修正", ("必須の節が見当たりません: Results (",))], 1, 0),
    ("定型文でない COI に否定した資金の語",
     [(COI, "The authors declare no conflicts of interest. No funding was received for this work.")],
     [("参考", ("Conflicts of interest の節", "定型文も具体的な申告も見当たりません"))], 0, 1),
    ("supported by だけの資金の記述",
     [(ACK_FUND, "This work was supported by the Tremendous Hunch Promotion Foundation.")],
     [("参考", ("Acknowledgements の節", "助成番号らしき語が見当たりません"))], 0, 1),
    ("見出しつきの 1 段落の抄録",
     [(_abstract_block(), '::: {custom-style="Abstract"}\n**Background:** ' + "word " * 10 + "**Methods:** "
       + "word " * 10 + "**Results:** " + "word " * 10 + "**Conclusions:** " + "word " * 10 + "\n:::")],
     [("要修正", ("構造化抄録の形です (見出し: Background / Methods / Results / Conclusions)",))], 1, 0),
    ("抄録の Div が無い", [(_abstract_block(), "word " * 50)],
     [("要修正", ("Abstract の Div (custom-style=\"Abstract\") が見当たりません",))], 1, 0),
    ("抄録の補足資料の図",
     [(_abstract_block(), '::: {custom-style="Abstract"}\n' + "word " * 20 + "(Supplementary Fig. S1).\n:::")],
     [("参考", ("抄録が図表に触れています (Supplementary Fig. S1)",))], 0, 1),
    ("抄録の手で書いた番号の引用",
     [(_abstract_block(), '::: {custom-style="Abstract"}\n' + "word " * 20 + "as reported earlier [1].\n:::")],
     [("参考", ("手で書いた引用らしい番号があります ([1])",))], 0, 1),
    ("抄録の語数を空白区切りでも数える",
     [(_abstract_block(), '::: {custom-style="Abstract"}\n' + " ".join(["a – b"] * 117) + "\n:::")],
     [("要修正", ("抄録語数 351 が上限 350 を超過",))], 1, 0),
    ("題の無い simple table",
     [(ADD_OBS, "  Trial   Score\n  -----   -----\n  1       2.6\n  2       1.2\n\n" + ADD_OBS)],
     [("要修正", ("題 (キャプション) の無い図表があります: 表 (L",))], 1, 0),
    ("題の無い grid table",
     [(ADD_OBS, "+-------+-------+\n| Trial | Score |\n+=======+=======+\n| 21    | 2.4   |\n+-------+-------+\n\n"
       + ADD_OBS)],
     [("要修正", ("題 (キャプション) の無い図表があります: 表 (L",))], 1, 0),
    ("題と著者を YAML に書いた原稿", "YAML",
     [("要修正", ("Title の Div",)), ("要修正", ("Author の Div",))], 2, 0),
    ("表の題の .wide", [(TBL_CAP, TBL_CAP.replace("}", " .wide}"))],
     [("要修正", ("表の題の属性に {#tbl:x} 以外のものがあります: {#tbl:conditions .wide}",))], 1, 0),
    ("running title の無い題の数式は描画の字数で数える",
     [(TITLE, "Tremendous $\\mathrm{CO}_2$ hunch measured by an apparatus"), (RUN, "")],
     [("参考", ("略語らしき語があります (CO)",))], 0, 1),
]


def _yaml_variant():
    s = BASE_MD.index('::: {custom-style="Title"}')
    e = BASE_MD.index('::: {custom-style="Affiliation"}')
    return [(BASE_MD[s:e], ""), ("<!--\ndata/dummy/abe/main.md", "---\ntitle: \"" + TITLE + "\"\nauthor:\n  - Taro YOKAN\n"
                                 "---\n\n<!--\ndata/dummy/abe/main.md")]


def test_mutations():
    for desc, pairs in NEGATIVE:
        expect_counts(f"変種 (誤検出しない) {desc}", mutated(pairs), 0, 0)
    for desc, pairs, wants, n_must, n_info in POSITIVE:
        got = mutated(_yaml_variant() if pairs == "YAML" else pairs)
        expect_counts(f"変種 (見逃さない) {desc}", got, n_must, n_info)
        expect_rows(f"変種 (見逃さない) {desc}", got, wants)
    got = mutated([(ADD_OBS, "  Trial   Score\n  -----   -----\n  1       2.6\n\n" + ADD_OBS)])
    check("変種: 題の無い simple table を表の点数に数える (表 3 点)", any("表 3 点" in e for e in got[2]), " / ".join(got[2]))


# ---------------------------------------------------------------------
# 6. 部品の単体の確認
# ---------------------------------------------------------------------

def _kinds(text):
    return [(b["kind"], b.get("level"), b.get("text") if b["kind"] == "heading" else b.get("title"))
            for b in validate.scan_blocks(text)]


def test_units():
    k = _kinds("Intro {.unnumbered}\n===========\n\nSub\n---\n\nPara one\nline two\n=====\n")
    check("走査: setext の見出し 2 つと、2 行の段落の後の下線 (段落の続き)",
          k == [("heading", 1, "Intro {.unnumbered}"), ("heading", 2, "Sub"), ("para", None, None)], k)
    tables = {
        "simple": "  A   B\n  --  --\n  1   2\n",
        "見出しの無い simple": "--  --\n1   2\n--  --\n",
        "grid": "+---+---+\n| a | b |\n+===+===+\n| 1 | 2 |\n+---+---+\n",
        "multiline": "----------\nA    B\n---  ---\n1    2\n\n3    4\n----------\n",
        "先頭の | の無い pipe": "a | b\n--|--\n1 | 2\n",
    }
    for name, src in tables.items():
        k = _kinds("Text.\n\n" + src + "\nMore text.\n")
        check(f"走査: {name} table を表と読む", k == [("para", None, None), ("table", None, None), ("para", None, None)], k)
    k = _kinds("Text.\n\n---\n\nMore.\n")
    check("走査: 段落の間の水平線は表でも見出しでもない", all(x[0] == "para" for x in k), k)
    k = _kinds("Table: Cap one. {#tbl:x}\n\n  A   B\n  --  --\n  1   2\n")
    check("走査: Table: の題を表に畳む", k == [("table", None, "Cap one.")], k)

    for src, want in [("Tremendous $\\mathrm{CO}_2$ hunch", "Tremendous CO2 hunch"), ("$P$ and $T_1$", "P and T1"),
                      ("costs $5 and $10", "costs $5 and $10"), ("rate $\\alpha$", "rate x")]:
        got = validate._plain(src)
        check(f"数式の字: {src!r} → {want!r}", got == want, got)

    same = [("apparatuses", "apparatus"), ("analyses", "analysis"), ("studies", "study"), ("hunches", "hunch"),
            ("matrices", "matrix"), ("scales", "scale"), ("processes", "process")]
    for a, b in same:
        check(f"複数形: {a} と {b} を同じ語とみなす", validate._fold_forms(a) & validate._fold_forms(b))
    for a, b in [("uses", "us"), ("goes", "go"), ("class", "clas")]:
        check(f"複数形: {a} と {b} を同じ語とみなさない", not (validate._fold_forms(a) & validate._fold_forms(b)))

    cases = [
        ("Taro YOKAN^1^, Hanako CHOKKAN^2^^[Present address: see [lab](https://example.org), Gutsby.], Bonta DAN^1^",
         ["Taro YOKAN", "Hanako CHOKKAN", "Bonta DAN"]),
        ("John SMITH, Jr.^1^, Mary JONES III^2^", ["John SMITH, Jr.", "Mary JONES III"]),
        ("Taro YOKAN, MD, PhD^1^\\\nDr. Hanako CHOKKAN^2^", ["Taro YOKAN", "Hanako CHOKKAN"]),
        ("Taro\nYOKAN^1^, Hanako CHOKKAN^2^,\nBonta DAN^1^", ["Taro YOKAN", "Hanako CHOKKAN", "Bonta DAN"]),
        ("Taro YOKAN\nHanako Chokkan", ["Taro YOKAN", "Hanako Chokkan"]),
    ]
    for src, want in cases:
        got = [n for n, _labels in validate._split_authors(src)]
        check(f"著者名の切り分け: {src[:40]!r}…", got == want, got)
    e = validate._author_entries("Taro YOKAN, MD, PhD^1^\\\nDr. Hanako CHOKKAN^2^")
    check("著者名の切り分け: 学位・敬称を extras に、番号は前の名前に",
          [x["extras"] for x in e] == [["MD", "PhD"], ["Dr."]] and [x["labels"] for x in e] == [["1"], ["2"]], e)

    labels = [
        ("**Objective:** a.\n\n**Methods:** b.\n\n**Results:** c.\n\n**Conclusion:** d.",
         ["Objective", "Methods", "Results", "Conclusion"]),
        ("Background: a b c. Methods: d e f.", ["Background", "Methods"]),
        ("**Purpose** We did things.", ["Purpose"]),
        ("We measured it. In summary: the ordering held.", []),
        ("The *Escherichia coli* strain grew at 10:00 and 12:30.", []),
    ]
    for src, want in labels:
        got = validate.abstract_labels(src)
        check(f"構造化抄録のラベル: {src[:40]!r}…", got == want, got)


# ---------------------------------------------------------------------
# 7. ほかの誌のフィクスチャ
# ---------------------------------------------------------------------

def src_sample_state():
    """src/ の同梱のサンプル論文の状態 (scripts/lib/sample-files.sha256 の指紋で見る。読み方は sample_files.py = package.py と同じ)。

    "sample"  = src/main.md がサンプルそのもの (試験する)
    "drift"   = src/main.md は一覧に無いのに、一覧のほかのファイルが中身もそのまま残っている (サンプルの本文を直して
                一覧に行を足し忘れた疑い。このまま公開すると、サンプルのままの原稿でも最終パッケージで止まるので、不合格にする)
    "absent"  = サンプルを消して自分の原稿を書いた後 (その原稿は試験の対象外なので黙って飛ばす)"""
    import sample_files
    lst = ROOT / "scripts" / "lib" / "sample-files.sha256"
    if not lst.is_file():
        return "absent"
    is_sample, left = sample_files.list_state(ROOT / "src", lst)
    if is_sample:
        return "sample"
    return "drift" if left else "absent"


def test_existing_journals():
    expect_counts("data/dummy (_default)", run(DUMMY, journal="_default", article_type=None), 0, 0)
    # 同梱のサンプル論文 (src/) は data/dummy/abe と同じ論文なので、要修正 0・参考 0 (サンプルが無ければ黙って飛ばす)
    state = src_sample_state()
    if state == "sample":
        expect_counts("同梱のサンプル論文 src/ (abe)", run(ROOT / "src"), 0, 0)
    elif state == "drift":
        check("同梱のサンプル論文 src/ の指紋の一覧が古くない", False,
              "src/main.md が scripts/lib/sample-files.sha256 に無いのに、一覧のほかのファイルが中身もそのまま残っている。"
              "サンプルの本文を直したなら、直したファイルの行を一覧に足す (bash scripts/remove-sample.sh --check で確かめる)")
    if present("bhi", DUMMY / "bhi", DUMMY / "bhi-lint"):
        expect_counts("bhi の動作例 (bhi)", run(DUMMY / "bhi", journal="bhi"), 0, 0)
        expect_counts("bhi の不適合フィクスチャ (bhi)", run(DUMMY / "bhi-lint", journal="bhi"), 23, 4)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="validate.py の ABE の検査の回帰試験")
    ap.add_argument("--require-journal", action="append", default=[], metavar="ID",
                    help="この誌のプロファイルと動作例が無ければ不合格にする (既定は黙って飛ばす。複数可)")
    REQUIRED.update(ap.parse_args(argv).require_journal)
    for journal in sorted(REQUIRED):
        profile = ROOT / "data" / "journals" / journal / "profile.yaml"
        if not profile.is_file():
            check(f"{journal} のプロファイルがある (--require-journal)", False, f"無い: {profile.relative_to(ROOT)}")
    test_fixtures()
    test_mutations()
    test_units()
    test_existing_journals()
    ng = [r for r in RESULTS if not r[1]]
    for desc, ok, detail in RESULTS:
        print(f"  {'OK' if ok else 'NG'}: {desc}" + ("" if ok else f"\n        → {detail}"))
    print("")
    if ng:
        print(f"== NG {len(ng)} 件 / 全 {len(RESULTS)} 件 ==")
        return 1
    print(f"== 全 {len(RESULTS)} 件が期待どおり ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
