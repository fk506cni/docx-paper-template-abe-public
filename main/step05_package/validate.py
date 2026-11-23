#!/usr/bin/env python3
"""validate.py — 原稿を雑誌プロファイルの limits / lint と照合し警告する (提出前の機械検査)。

docs/architecture.md §2.5 / §5、docs/profile-schema.md。語数・抄録語数・文献数を profile.yaml の limits と比べ、超過を警告
として返す (エラーにはしない。最終判断は実物で行う)。package.py から import され、単独でも動く。

【数え方は近似】Markdown 段階の語数なので、docx レンダリング後のページ数や厳密な語数とは
ずれうる。あくまで提出前の目安。本文 = メタ Div (Title/Author/Affiliation/Corresponding/
Keywords/Abstract/**Legend**) と References 節を除いた散文。抄録 = Abstract custom-style Div の
中身。文献数 = 本文中の一意な引用キー (@key) 数 (相互参照 @fig:/@tbl:/@eq:/@sec: は除外)。

【読むファイル】語数・文献数・lint の大半は `<INPUT_ROOT>/main.md` だけを読む。**例外は記入欄
`<<...>>` の残存検査だけ**で、`cover-letter.md` / `revise-report.md` も読む (どちらも編集部に
届く提出物であるため)。

【語数の数え方と lint】
  - 本文語数から**図表の凡例 (`custom-style="Legend"` Div) を除外**する。
  - **誌の規定の lint 群** (どれも profile のキーで発火する): タイトル語数・タイトル中の略語・キーワード数・抄録内引用・Declarations の
    6 項目・Abbreviations 節の位置・合成文字 (℃ 等)・数値の桁区切りカンマ・記入欄 `<<...>>` の
    残存・図表の合計点数・図表の題 15 語 / 凡例 300 語・`Legend` Div の `for` 属性と配置・
    `Legend` Div の中身が段落だけか・References が本文の最終節か・連絡著者ブロック。
  - 出力を **「規定違反の可能性 (要修正)」と「参考情報」に区分**する (戻り値は Finding の list)。
  - lint 規則はすべて profile 駆動。**一般作法 (合成文字・単位系・記入欄・凡例の配置) は
    基底 (`journal_profile.DEFAULTS`) に置き**、雑誌側は上書き・追加のみとする 2 層構成
    (判断の記録は docs/profile-schema.md)。

使い方 (単独):
    python3 validate.py --input-root data/dummy --journal _default
    python3 validate.py --input-root data/dummy/abe --journal abe --article-type original
"""

import argparse
import os
import re
import sys
import zipfile
from collections import namedtuple
from pathlib import Path

# profile の読み込み・既定値・記事種別解決は共通モジュールに集約 (docs/profile-schema.md)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
import journal_profile  # noqa: E402

# ---------------------------------------------------------------------
# 指摘の区分
#
# LEVEL_MUST … 規定違反の可能性。投稿前に直すことを想定する (上限超過・必須記載の欠落・
#              禁止表記・提出物の構造が壊れる配置規則違反)。
# LEVEL_INFO … 参考情報。判断が要る / 機械では断定できない / 規定に照らして「望ましい」止まり。
#
# どちらも**エラーにはしない** (validate は終了コードを 0 のまま返す)。最終判断は実物で行う
# という §2.5 の方針を変えないため。
# ---------------------------------------------------------------------
#
# origin … 検査規則の出所。**基底 (journal_profile.DEFAULTS) 由来のときだけ
#              文字列が入り**、指摘の文末に添えられる。lint の 2 層構成では、合成文字・記入欄・
#              凡例の配置は基底では「欧文組版の一般則」「本テンプレの記法の規約」に過ぎず、
#              その誌の規定を調べた結果ではない。それを「規定違反の可能性」の見出しの下に
#              素のまま並べると、規定に無い事柄を規定違反として突きつけることになる
#              (誤検出と同じく lint への信頼を損なう)。区分そのものは変えず、出所を注記で添える
#              (2 区分は SUBMISSION.md の「規定チェック」節と文書が前提にしているため)。
# ---------------------------------------------------------------------
LEVEL_MUST = "要修正"
LEVEL_INFO = "参考"

Finding = namedtuple("Finding", "level message origin")
Finding.__new__.__defaults__ = (None,)

ORIGIN_BASE = "本テンプレ共通の作法"


def must(msg, origin=None):
    return Finding(LEVEL_MUST, msg, origin)


def info(msg, origin=None):
    return Finding(LEVEL_INFO, msg, origin)


def _origin_note(profile, key):
    """lint.<key> が基底由来なら ORIGIN_BASE を返す (誌が宣言していれば None)。

    `journal_profile.resolve()` が控えた `_lint_declared` (その誌の profile.yaml が自分で
    書いた lint キーの一覧) を見る。控えが無い (resolve() を通していない) profile では None を返し、
    注記を付けない。
    """
    declared = profile.get("_lint_declared")
    if declared is None:
        return None
    return None if key in declared else ORIGIN_BASE


def finding_text(finding):
    """指摘 1 件の表示文 (出所の注記込み)。画面とマニフェストで共用する。"""
    return finding.message + (f" ({finding.origin})" if finding.origin else "")


# custom-style Div のうち本文語数から除外するメタ領域
#
# corresponding (連絡著者ブロック) も除外する。氏名・住所全文・電話・E-mail は
# 規定上 Title page の構成要素であって本文ではない。
#
# legend (図表の凡例) も除外する。判断は「**図の凡例も表の凡例も除外する**」。
# 根拠 (語数の上限から図キャプションを除く誌の規定 = BHI の規定で考えた):
#   (a) 規定が本文語数から除外するのは「表・図 / 文献 / 図キャプション」で、**図キャプションは
#       明示的に除外**されている。本テンプレの書き分け規約では凡例が画像記法の外 (Legend Div)
#       にあるので、明示的に落とさないと本文に算入されてしまう。
#   (b) **表の凡例は規定に明示が無い**。ただし規定は表の題を「表の上」・凡例を「表の下」と
#       定めており、題も凡例も**表という提出物の構成要素**として書かれている。除外対象の
#       「表」に題と凡例が含まれると読むのが素直で、図と表で扱いを変える根拠が規定に無い。
#   (c) 図と表の凡例は同じ `Legend` 段落スタイルを共有するため、算入/除外を分けるには
#       「直前が図か表か」の判定に語数計算を依存させることになる。その判定は配置規則が
#       守られている前提に立つので、**規則違反があると語数が静かにずれる**。
# 除外は**費用の見積もりを甘くする側**に効く (BHI の規定では超過ページは 1 ページ 2 万円 + 税) ため、
# 除外した語数は概算行に**内訳として必ず表示する** — 編集室の数え方が違ったときに
# 足し戻せるようにするため。
#
# subtitle (running title) と normal (受付日・改訂日の行) も除外する。どちらも表題ページの要素で、
# 学会テンプレートの見本どおり Subtitle / Normal の Div で書く。この 2 つの Div を使わない原稿では語数は変わらない。
META_STYLES = {"title", "author", "affiliation", "keywords", "abstract", "corresponding", "legend",
               "subtitle", "normal"}

LEGEND_STYLE = "legend"


# =====================================================================
# テキスト前処理
# =====================================================================

def _read_main(input_root):
    md = Path(input_root) / "main.md"
    if not md.is_file():
        return None
    return md.read_text(encoding="utf-8")


def _blank_out(m):
    """マッチを同じ行数の空行に置き換える (行番号を原文と一致させたまま中身だけ落とす)。"""
    return "\n" * m.group(0).count("\n")


FENCE_MARK = "~~~"


def _blank_fence(m):
    """コードフェンスを**目印 1 行 + 同じ行数の空行**に潰す。

    空行に潰すと、`Legend` Div の中身にコードフェンス (本テンプレが正式に
    案内する `{=openxml}` 生ブロックを含む) を書いても、凡例の中身の検査には**空行しか見えず
    原理的に検出できない** — 除去が検査より前に走るためで、規則を足しても直らない。
    pandoc はフェンスを `SourceCode` 段落として出すので、最終パッケージの凡例の集約はそこで止まり
    以降が本文に取り残される (実測で確認した失敗モード)。

    目印に `~~~` を選んだ理由: 英数字を含まないので `_word_tokens()` が語として数えず、
    `#` / `|` / `:::` / `>` を含まないので見出し・表・Div フェンス・引用の判定にも掛からない。
    pandoc は `~~~` も正規のコードフェンス記法として認めるため、原稿に元からある `~~~` の
    フェンスも同じ目印として扱われる (副産物として穴が 1 つ減る)。
    """
    n = m.group(0).count("\n")
    return FENCE_MARK + "\n" * n if n else FENCE_MARK


def _blank_inline(m):
    """インラインコードを空白 1 個に潰す。ただし改行数は保つ。

    `re.sub(r"`[^`]*`", " ", text)` のように改行ごと 1 個の空白に置換してはいけない。
    Markdown のインラインコードは段落内で改行をまたげるので、そういう原稿では
    **以降の指摘の行番号が原文とずれる** (実測: 4 行目の合成文字が L3 と報告された)。
    `_strip_noise` の他の 3 経路も行数を保つ。
    """
    return " " + "\n" * m.group(0).count("\n")


def _strip_noise(text):
    """YAML フロントマター・HTML コメント・コードフェンス・インラインコードを除去。

    YAML フロントマターを除去する (メタ値や連絡先メールが本文語数・文献数に
    紛れ込むのを防ぐ。package.py の _strip_yaml_and_code と挙動を揃える)。

    複数行にまたがる構文は**削除せず、同じ行数の空行に潰す**。
    lint は指摘に行番号を添えるので、除去で行がずれると原稿の別の場所を指してしまう。
    語数・文献数の計算結果は空行が増えても変わらない。
    HTML コメントを落とすのは骨格のためでもある — 骨格
    `data/journals/abe/skeleton/main.md` は執筆の手引きをコメントで持っており、これを写した原稿には
    日本語の解説文が残る。pandoc は docx に出さないので実害は無いが、Markdown 層の lint は素通しに
    読むため誤検出源になる (禁止文字・記入欄 `<<...>>`・桁区切りカンマのいずれもコメントに現れうる)。
    """
    text = re.sub(r"^---\n.*?\n---\n", _blank_out, text, count=1, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", _blank_out, text, flags=re.DOTALL)
    # フェンスは空行ではなく目印 (~~~) に潰す。凡例の中身の検査から
    # 見えなくなるのを防ぐため (下の _blank_fence の説明を参照)。
    text = re.sub(r"```.*?```", _blank_fence, text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", _blank_inline, text)
    return text


# =====================================================================
# ブロック走査
#
# lint の多くは「凡例 Div の直前が図か表か」「Abbreviations 節が Abstract と Introduction の
# 間にあるか」のように **文書順の位置関係**を見る。行単位の正規表現では位置関係を持てないので、
# 原稿を文書順のブロック列に均す層を 1 つ置く。
#
# 走査は `.textbox` / `.grid` / `#refs` のような**構造 Div の中へは入り**、
# custom-style Div (Title / Abstract / Legend …) の中へは入らない (中身は散文なので
# ブロックに割る意味がない)。テキストボックスの中に入ったブロックには in_textbox 印を付ける —
# 本文の流れの外なので、図表の点数にも最終パッケージの移設にも数えないため。
# =====================================================================

_RE_DIV_OPEN = re.compile(r"^(:::+)\s*(\{.*\})\s*$")
_RE_DIV_CLOSE = re.compile(r"^:::+\s*$")
_RE_HEADING = re.compile(r"^(#+)\s+(.*?)\s*$")
_RE_TABLE_ROW = re.compile(r"^\s*\|")
# `:` のほかに `Table:` / `table:` で始まる題も読む (pandoc の table_captions)。
# 下の simple table などの題をこの形で書いた原稿で、題の無い表と取り違えないため
_RE_TBL_CAPTION = re.compile(r"^\s*(?:[Tt]able)?:\s+(\S.*?)\s*$")
_RE_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]*)\)(?:\{(?P<attr>[^}]*)\})?")
# setext の見出しの下線 (`====` は 1 段目・`----` は 2 段目)。pandoc は 1 行だけの段落の直後の
# 下線を見出しとして読む (2 行以上の段落の後の下線は段落の続き。pandoc 3.6.4 の出力で確かめた)。見出しと読まないと、
# `Introduction` + `====` と書いた原稿で必須の節の欠落を誤って要修正にする
_RE_SETEXT_UNDERLINE = re.compile(r"^(=+|-+)[ \t]*$")
# パイプでない表 (pandoc の simple table・multiline table・grid table) と、先頭の `|` の無い pipe table。
# 先頭が `|` の行だけを表と読むと、ほかの書き方の表は題が無くても要修正にならず、表の点数にも入らない。
# 区切りの形は凡例の中身の検査 (_LEGEND_RULES の「表」) と同じ。simple table の区切りは 2 列以上 (1 列の `----` は setext の見出し)
_RE_SIMPLE_SEP = re.compile(r"^ {0,3}(?:(?=[^\n]*-{2})-+(?:[ \t]+-+)+|-+(?:[ \t]{2,}-+)+)[ \t]*$")
_RE_PIPE_SEP = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:[|+][ \t]*:?-+:?[ \t]*)+\|?[ \t]*$")
_RE_GRID_BORDER = re.compile(r"^ {0,3}\+(?:[-=:]+\+)+[ \t]*$")
_RE_DASH_RULE = re.compile(r"^ {0,3}-{3,}[ \t]*$")


def _custom_style(attr):
    m = re.search(r'custom-style\s*=\s*"([^"]+)"', attr)
    return m.group(1).strip() if m else None


def _attr_ident(attr):
    m = re.search(r"#([A-Za-z][\w:.-]*)", attr or "")
    return m.group(1) if m else None


def _div_attrs(attr):
    m = re.search(r'\bfor\s*=\s*"([^"]*)"', attr)
    return {
        "style": _custom_style(attr),
        "classes": re.findall(r"\.([A-Za-z][\w-]*)", attr),
        "for": m.group(1).strip() if m else None,
        "ident": _attr_ident(attr),
    }


def _split_ident(caption):
    """`題 {#tbl:x}` を (題, 識別子) に割る。"""
    m = re.search(r"\{([^}]*)\}\s*$", caption)
    if not m:
        return caption.strip(), None
    return caption[:m.start()].strip(), _attr_ident(m.group(1))


def _caption_attr(caption):
    """表の題の末尾の属性 `{…}` の中身 (無ければ None)。表の題の .wide の検査に使う。"""
    m = re.search(r"\{([^}]*)\}\s*$", caption)
    return m.group(1) if m else None


def _plain_line(line):
    """setext の見出しや simple table の見出しの行になりうる素の行か。

    字下げ 4 以上 (コード)・箇条書き・引用・表の行・Div のフェンス・コードの目印 (~~~) の行は除く。
    """
    return bool(line.strip()) and not (
        re.match(r" {4,}|\s*(?:[-*+][ \t]|>|~~~)", line) or _RE_TABLE_ROW.match(line)
        or _RE_DIV_OPEN.match(line) or _RE_DIV_CLOSE.match(line) or _RE_HEADING.match(line)
        or _RE_TBL_CAPTION.match(line))


def _table_extent(lines, i, end):
    """lines[i] がパイプでない表 (と先頭の `|` の無い pipe table) の始まりなら (表の次の行, 形) を返す。違えば None。

    pandoc の 4 つの書き方 (pipe / simple / multiline / grid。pandoc 3.6.4 の出力で確かめた):
      - grid table: `+---+---+` の罫線で始まる
      - simple table: 見出しの行の次の行が列の区切り (`-----  -----`)。見出しの無い形は区切りで始まる
      - 先頭の `|` の無い pipe table: 見出しの行 (`a | b`) の次の行が `---|---`
      - multiline table: 本文幅の `-----` で始まり、中に列の区切りがあり、`-----` + 空行で終わる (行の間に空行を挟める)
    表の終わりは空行 (multiline table は閉じの罫線)。Div のフェンスと表の題の行 (`: 題`) の手前でも止める。
    """
    def run_to_blank(j):
        while j < end and lines[j].strip() and not (_RE_DIV_OPEN.match(lines[j]) or _RE_DIV_CLOSE.match(lines[j])
                                                   or _RE_TBL_CAPTION.match(lines[j])):
            j += 1
        return j

    line = lines[i]
    nxt = lines[i + 1] if i + 1 < end else ""
    if _RE_GRID_BORDER.match(line):
        return run_to_blank(i + 1), "grid"
    if _RE_SIMPLE_SEP.match(line) and nxt.strip():
        return run_to_blank(i + 1), "simple"
    if _plain_line(line) and _RE_SIMPLE_SEP.match(nxt):
        return run_to_blank(i + 2), "simple"
    if "|" in line and _plain_line(line) and _RE_PIPE_SEP.match(nxt):
        return run_to_blank(i + 2), "pipe"
    if _RE_DASH_RULE.match(line) and nxt.strip() and not _RE_DASH_RULE.match(nxt):
        has_sep, blank_run = False, 0
        for j in range(i + 1, end):
            cur = lines[j]
            if _RE_DIV_OPEN.match(cur) or _RE_DIV_CLOSE.match(cur) or _RE_HEADING.match(cur):
                return None
            if not cur.strip():
                blank_run += 1
                if blank_run >= 2:              # 空行が 2 つ続けば表ではない
                    return None
                continue
            blank_run = 0
            if _RE_SIMPLE_SEP.match(cur):
                has_sep = True
            elif _RE_DASH_RULE.match(cur) and (j + 1 >= end or not lines[j + 1].strip()):
                return (j + 1, "multiline") if has_sep else None
    return None


def _find_div_close(lines, i, end):
    depth = 1
    while i < end:
        if _RE_DIV_OPEN.match(lines[i]):
            depth += 1
        elif _RE_DIV_CLOSE.match(lines[i]):
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return end        # 閉じ忘れ: 領域の終わりまでを中身とみなす


def _scan_region(lines, start, end, in_textbox, out):
    i = start
    while i < end:
        line = lines[i]

        m = _RE_DIV_OPEN.match(line)
        if m:
            attr = m.group(2)
            close = _find_div_close(lines, i + 1, end)
            a = _div_attrs(attr)
            # close は閉じフェンスの行 (閉じ忘れなら領域の終わり)。Div の行を空けて本文だけを見る lint が使う
            out.append({"kind": "div", "line": i, "close": close, "attr": attr, "style": a["style"],
                        "classes": a["classes"], "for": a["for"], "ident": a["ident"],
                        "inner": "\n".join(lines[i + 1:close]), "in_textbox": in_textbox})
            if a["style"] is None:      # 構造 Div (.textbox / .grid / #refs) は中身も走査する
                _scan_region(lines, i + 1, close,
                             in_textbox or "textbox" in a["classes"], out)
            i = close + 1
            continue

        if _RE_DIV_CLOSE.match(line):   # 対応しない閉じフェンス (壊れた入力) は読み飛ばす
            i += 1
            continue

        if not line.strip():
            i += 1
            continue

        m = _RE_HEADING.match(line)
        if m:
            out.append({"kind": "heading", "line": i, "level": len(m.group(1)),
                        "text": m.group(2).strip(), "in_textbox": in_textbox})
            i += 1
            continue

        if _RE_TABLE_ROW.match(line):
            j = i
            while j < end and _RE_TABLE_ROW.match(lines[j]):
                j += 1
            # end は表の次の行 (本文の語数から表の行を外すのに使う)
            out.append({"kind": "table", "line": i, "end": j, "title": None, "ident": None,
                        "title_line": None, "title_attr": None, "in_textbox": in_textbox})
            i = j
            continue

        m = _RE_TBL_CAPTION.match(line)
        if m:
            cap, ident = _split_ident(m.group(1))
            out.append({"kind": "table_caption", "line": i, "text": cap, "ident": ident,
                        "attr": _caption_attr(m.group(1)), "in_textbox": in_textbox})
            i += 1
            continue

        # パイプでない表 (simple / multiline / grid) と先頭の `|` の無い pipe table
        ext = _table_extent(lines, i, end)
        if ext:
            out.append({"kind": "table", "line": i, "end": ext[0], "title": None, "ident": None,
                        "title_line": None, "title_attr": None, "in_textbox": in_textbox})
            i = ext[0]
            continue

        # setext の見出し (1 行だけの段落 + 下線)。ブロックの頭でだけ読む (pandoc も同じ)
        if i + 1 < end and _plain_line(line):
            um = _RE_SETEXT_UNDERLINE.match(lines[i + 1])
            if um:
                out.append({"kind": "heading", "line": i, "level": 1 if um.group(1)[0] == "=" else 2,
                            "text": line.strip(), "in_textbox": in_textbox})
                i += 2
                continue

        # 段落 (空行 / フェンス / 見出し / 表 / キャプション行のいずれかまで)
        j, buf = i, []
        while j < end:
            nxt = lines[j]
            if (not nxt.strip() or _RE_DIV_OPEN.match(nxt) or _RE_DIV_CLOSE.match(nxt)
                    or _RE_HEADING.match(nxt) or _RE_TABLE_ROW.match(nxt)
                    or _RE_TBL_CAPTION.match(nxt)):
                break
            buf.append(nxt)
            j += 1
        para = "\n".join(buf)
        images = [{"alt": im.group("alt"), "src": im.group("src"),
                   "ident": _attr_ident(im.group("attr") or "")}
                  for im in _RE_IMAGE.finditer(para)]
        out.append({"kind": "image" if images else "para", "line": i, "text": para,
                    "images": images, "in_textbox": in_textbox})
        i = j


def scan_blocks(text):
    """原稿を文書順のブロック列に均す。

    表のキャプション行は隣接する表に畳んで消す — pandoc は `: 題 {#tbl:x}` を表の**前にも後にも**
    書けるので (実際 data/dummy/main.md は後に書いている)、畳まないと
    「凡例 Div の直前が表か」の判定がキャプションの位置で変わってしまう。
    """
    blocks = []
    lines = text.splitlines()
    _scan_region(lines, 0, len(lines), False, blocks)
    for idx, b in enumerate(blocks):
        if b["kind"] != "table":
            continue
        for j in (idx - 1, idx + 1):
            if 0 <= j < len(blocks) and blocks[j]["kind"] == "table_caption" \
                    and not blocks[j].get("_merged"):
                b["title"] = blocks[j]["text"]
                b["ident"] = blocks[j]["ident"]
                b["title_line"] = blocks[j]["line"]
                b["title_attr"] = blocks[j]["attr"]      # lint_table_caption_attrs が見る
                blocks[j]["_merged"] = True
                break
    return [b for b in blocks if not b.get("_merged")]


def _iter_divs(blocks):
    """pandoc fenced Div を (attr_text, inner) で yield する (文書順)。

    走査は scan_blocks に一本化してあり、**入れ子の Div も yield する** — そうしないと
    `.textbox` の中に置いた `Legend` Div が本文語数の除外対象から漏れる
    (回帰フィクスチャ data/dummy/regression/ が実際にその形を持つ)。

    引数は**走査済みの blocks** (呼び出し側が 1 回だけ走査したもの) を取る。
    """
    for b in blocks:
        if b["kind"] == "div":
            yield b["attr"], b["inner"]


# =====================================================================
# 語数
# =====================================================================

def _word_tokens(text):
    """英数字を含むトークンを語として数える (記号のみのトークンは除外)。

    画像記法の除去は**属性ブロック `{#fig:x}` まで含める**。
    規定が本文語数から除外する「図の題」は `![…](…)` 全体を落とせば除外できるが、
    識別子は括弧の外にあるので、それも落とさないと `{#fig:workflow}` が記号除去後に
    `fig` `workflow` の **2 語**として数えられる (1 図あたり 2 語)。
    """
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?", " ", text)   # 画像 (属性ブロック込み)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)     # リンクはテキストのみ
    text = re.sub(r"[#>*_~|`:]", " ", text)                  # markdown 記号
    return [t for t in text.split() if re.search(r"[0-9A-Za-z]", t)]


def _div_inner(blocks, style):
    """指定 custom-style の Div の中身を文書順に返す (list[str])。

    引数は走査済みの blocks (呼び出し側が 1 回だけ走査したもの)。
    """
    return [b["inner"] for b in blocks
            if b["kind"] == "div" and (b["style"] or "").lower() == style]


def _abstract_inner(blocks):
    """Abstract custom-style Div の中身を返す (無ければ None)。"""
    inners = _div_inner(blocks, "abstract")
    return inners[0] if inners else None


def count_abstract_words(blocks):
    inner = _abstract_inner(blocks)
    if inner is None:
        return None
    # "**Background:**" 等のラベルも語に含む (誌の数え方に近い側へ倒す)
    return len(_word_tokens(inner))


def count_abstract_words_ws(blocks):
    """抄録の語数を空白区切りで出す (Word の語数に近い)。

    英数字を含むトークンだけを語とする count_abstract_words() は、`±` `<` `=` や空白で挟んだダッシュを語にしないので、
    統計の文の多い抄録で少なく出る (42 語の文が 34 語)。上限が must の誌 (ABE の 350 語) では超過を見逃しうるので、
    こちらも数えて、食い違えば両方を表示し、上限の判定は大きいほうで行う (validate())。画像は落とし、リンクは文字だけにし、
    Markdown の記号だけのトークン (`**` や行末の `\\`) と、句読点だけのトークン (_strip_noise がインラインコードを空白にした
    後に残る `.` など) は数えない。逆に `10:00` は英数字の数え方のほうが多い (2 語)。
    """
    inner = _abstract_inner(blocks)
    if inner is None:
        return None
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?", " ", inner)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return len([t for t in s.split() if not re.fullmatch(r"[#>*_~|`:\\.,;!?\"'’”)\]]+", t)])


def count_legend_words(floats):
    """図表の凡例 (`Legend` Div) の語数を (図, 表, 対応不明) に分けて返す。

    本文語数からは 3 つとも除外する (META_STYLES の判断記録を参照)。分けて数えるのは
    **除外した内訳を概算行に出す**ためで、編集室の数え方が違ったときに足し戻せるようにする。
    振り分けは「凡例 Div の直前のブロックが画像か表か」で行う — 図と表の凡例は同じ
    `Legend` スタイルを共有しており、他に手がかりが無い。
    「対応不明」は配置規則を破った凡例で、lint が別途 要修正として指摘する。

    floats (analyze_floats() の結果) は必須引数 (走査は呼び出し側で 1 回だけ行う)。
    """
    fig = tbl = other = 0
    for leg in floats["legends"]:
        n = len(_word_tokens(leg["inner"]))
        if leg["target_kind"] == "fig":
            fig += n
        elif leg["target_kind"] == "tbl":
            tbl += n
        else:
            other += n
    return fig, tbl, other


def _drop_abbreviations_section(text, blocks):
    """`Abbreviations` 見出しから、同レベル以上の次の見出しの直前までを落とす。

    正規表現 1 本 (`^#+\\s*Abbreviations\\b.*?(?=^#\\s|\\Z)`) では先読みが
    **第 1 レベルの見出し `^#\\s` に固定**される。節見出しを `##` で書いた原稿では
    Abbreviations から文書末尾までがまるごと落ち、**本文語数が 0 語になりうる**
    (実測 22 語 → 0 語)。そこで走査層の見出し列を使ってレベルで範囲を決める
    (`lint_declarations` が節の範囲を切るのと同じ流儀)。

    blocks は呼び出し側が走査済みのものを渡す。

    **必ず加工前の `text` に対して最初に呼ぶこと**。本関数は `blocks` が持つ
    行番号で切る範囲を決めるので、`text` を先に別の加工に掛けると行番号がずれる。
    しかも本関数は落とした範囲を**1 行の空白に潰す**ため、呼んだ後の文字列は `blocks` の
    行番号と一致しなくなる。ずれてもエラーにはならず略語一覧の除去範囲が別の場所に移るだけなので、
    気づけない形の壊れ方になる (現状の `count_body_words` は `out = text` の直後に呼ぶので一致する)。
    """
    heads = [b for b in blocks if b["kind"] == "heading" and not b["in_textbox"]]
    start = next((b for b in heads if _is_abbrev_heading(b["text"])), None)
    if start is None:
        return text
    lines = text.splitlines()
    end = next((b["line"] for b in heads
                if b["line"] > start["line"] and b["level"] <= start["level"]), len(lines))
    return "\n".join(lines[:start["line"]] + [" "] + lines[end:])


def count_body_words(text, blocks, drop_abbreviations=False, keep_legends=()):
    """本文 (メタ Div と References 節を除いた散文) の概算語数。

    keep_legends に渡した中身を持つ `Legend` Div は**除去せず本文語数に算入する**。
    想定する用途は「対応不明の凡例」= 配置規則を破って直前に図表が無い
    凡例で、最終パッケージの集約から漏れて**提出物では本文に残る**ため、語数の側も実態に
    合わせる。すべての `Legend` を落とすと、規則を破った原稿でだけ語数が実際より少なく出る
    (超過ページは 1 ページ 2 万円 + 税なので、甘い側の誤差になる)。

    drop_abbreviations=True のとき 'Abbreviations' 節 (次の同レベル以上の見出しまで) も除く。
    BHI のプロファイル (本テンプレートの扱い) では抄録と Abbreviations を除き、Declarations は数える
    (規定の文面だけでは決まらない部分の本テンプレートの扱い)。誌が declarations.abbreviations_section: true を
    持つ場合にのみ除外する (同キーを持たない誌では除外しない)。
    """
    # メタ Div を内容ごと除去
    out = text
    # 表の行を落とす (走査層が表と読んだ範囲。パイプでない表も含む)。行の数は保つので、下の
    # _drop_abbreviations_section が使う blocks の行番号とずれない (下の正規表現は先頭が `|` の行しか落とせない)
    table_lines = {k for b in blocks if b["kind"] == "table" for k in range(b["line"], b.get("end", b["line"] + 1))}
    if table_lines:
        out = "\n".join("" if k in table_lines else ln for k, ln in enumerate(out.splitlines()))
    if drop_abbreviations:
        # 'Abbreviations' 見出しから次の同レベル以上の見出しの直前までを落とす
        out = _drop_abbreviations_section(out, blocks)
    keep = {s for s in keep_legends if s}
    for attr, inner in _iter_divs(blocks):
        style = (_custom_style(attr) or "").lower()
        if style == LEGEND_STYLE and inner in keep:
            continue                    # 対応不明の凡例は算入する
        if style in META_STYLES:
            # 空の inner だと str.replace("", " ") が全文を 1 文字ずつ分断して
            # 破壊するためスキップ。置換も最初の 1 回に限定して偶然一致の過剰除去を防ぐ。
            if not inner.strip():
                continue
            out = out.replace(inner, " ", 1)
    # References 節以降を除去 (見出し '# References' から末尾)
    out = re.split(r"^#+\s*References\b.*$", out, maxsplit=1, flags=re.MULTILINE | re.IGNORECASE)[0]
    # refs Div ({#refs}) を除去
    out = re.sub(r"^:::+\s*\{#refs\}.*?^:::+\s*$", " ", out, flags=re.DOTALL | re.MULTILINE)
    # 表行・キャプション行・Div フェンス行を落とす
    kept = []
    for line in out.splitlines():
        if re.match(r"^\s*\|", line):            # 表
            continue
        if re.match(r"^:::+", line):             # Div フェンス
            continue
        if re.match(r"^\s*(?:[Tt]able)?:\s+\S", line):   # 表/図キャプション (: caption と Table: caption)
            continue
        if _RE_HEADING.match(line):
            # 見出しの属性 ({.unnumbered} / {#sec:x}) は語ではないので外す。
            # 抄録の見出し (`# Abstract`) は抄録の一部で、本文の語ではない (抄録を Div だけで書く原稿では起きない)
            line = _heading_title(line)
            if _norm(re.sub(r"^#+", "", line)) == "abstract":
                continue
        kept.append(line)
    return len(_word_tokens("\n".join(kept)))


def count_references(text):
    """本文中の一意な引用キー数 (相互参照 fig:/tbl:/eq:/sec: は除外)。"""
    # refs Div を除外
    body = re.sub(r"^:::+\s*\{#refs\}.*?^:::+\s*$", " ", text, flags=re.DOTALL | re.MULTILINE)
    keys = set()
    for m in re.finditer(r"@([A-Za-z0-9_][\w:.-]*)", body):
        # @ の直前が英数字ならメール (user@example.com) とみなし除外。
        if m.start() > 0 and body[m.start() - 1].isalnum():
            continue
        key = m.group(1).rstrip(".")     # 末尾ピリオド (@key.) を落とす (ハイフンは bibkey の一部なので残す)
        if not key:
            continue
        if key.split(":", 1)[0].lower() in ("fig", "tbl", "eq", "sec", "lst"):
            continue
        keys.add(key)
    return len(keys)


def _citation_keys(text):
    """引用キーの出現位置つき一覧 (相互参照・メールアドレスは除外)。"""
    out = []
    for m in re.finditer(r"@([A-Za-z0-9_][\w:.-]*)", text):
        if m.start() > 0 and text[m.start() - 1].isalnum():
            continue
        key = m.group(1).rstrip(".")
        if not key or key.split(":", 1)[0].lower() in ("fig", "tbl", "eq", "sec", "lst"):
            continue
        out.append(key)
    return out


# =====================================================================
# 図・表・凡例の対応づけ
# =====================================================================

def analyze_floats(blocks):
    """図・表・凡例を文書順に拾い、凡例を直前の図表へ結びつける。

    対応づけの根拠は **位置だけ**である。`for="fig:x"` 属性は docx に出ず、
    最終パッケージの集約 (relocate.py) も位置しか見ない。つまり `for` は「冗長だが検算に使える情報」であり、
    ここで位置と突き合わせて初めて意味を持つ。

    凡例が図表の直後に無い場合 (前置き / 間に本文段落 / 節の頭) は target を結びつけず
    orphan として返す — その凡例は最終パッケージの集約から漏れて本文に取り残される。
    """
    figures, tables, legends = [], [], []
    last_float = None
    prev = None       # 直前の意味のあるブロックの種別
    for b in blocks:
        kind = b["kind"]
        if kind == "image":
            for im in b["images"]:
                rec = {"kind": "fig", "ident": im["ident"], "title": im["alt"],
                       "line": b["line"], "in_textbox": b["in_textbox"], "legends": []}
                figures.append(rec)
                last_float = rec
            # kind == "image" は「画像が 1 つ以上ある」ことを意味するので b["images"] では分岐しない
            # (`"float" if b["images"] else "para"` の else 側には到達しない)。
            prev = "float"
        elif kind == "table":
            rec = {"kind": "tbl", "ident": b["ident"], "title": b["title"],
                   "line": b["line"], "title_line": b["title_line"],
                   "in_textbox": b["in_textbox"], "legends": []}
            tables.append(rec)
            last_float = rec
            prev = "float"
        elif kind == "div" and (b["style"] or "").lower() == LEGEND_STYLE:
            leg = {"line": b["line"], "for": b["for"], "inner": b["inner"],
                   "in_textbox": b["in_textbox"], "target": None, "target_kind": None}
            # 直前が図表そのものか、直前が同じ図表に付いた凡例なら結びつける
            # (凡例 Div を 2 つ続けて書いてもよい。最終パッケージは「直後に連続する Legend 段落すべて」を
            #  1 組として動かすので、複数 Div でも同じ扱いになる)
            #
            # **テキストボックスの内外をまたぐ結合はしない**。
            # 走査層は構造 Div の中へ入るので、箱の中の図表と外の図表が同じ列に並ぶ。またいで結合すると、
            # 箱を閉じた直後に置いた凡例が箱の中の図に結びつき、`for` を書いていない原稿では
            # **指摘が 1 件も出ないまま**その凡例が本文に取り残される (最終パッケージの集約は箱の中を
            # 対象外にするため)。しかも語数だけは除外されるので本文語数が過少になる。
            # 結合しなければ「直前に図・表がありません」が要修正として出る。
            if (prev in ("float", "legend") and last_float is not None
                    and last_float["in_textbox"] == b["in_textbox"]):
                leg["target"] = last_float
                leg["target_kind"] = last_float["kind"]
                last_float["legends"].append(leg)
            legends.append(leg)
            prev = "legend"
        elif kind == "table_caption":
            # 表に畳めなかった孤立キャプション (表と隣接していない)。図表としては数えない
            prev = "para"
        else:
            prev = "para"
            last_float = None
    return {"figures": figures, "tables": tables, "legends": legends}


# =====================================================================
# lint 群 (すべて profile 駆動。キーが無い雑誌では発火しない)
# =====================================================================

def _norm(s):
    """見出し・項目名の照合用に正規化する (小文字化 / 空白の畳み込み / アポストロフィ統一)。"""
    s = (s or "").replace("’", "'").replace("‘", "'")
    s = re.sub(r"[*_`]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower().rstrip(":.")


def _loc(line):
    """指摘に添える位置 (1 始まりの行番号)。_strip_noise が行数を保つので原文と一致する。

    「行数を保つ」は 4 経路すべてで成り立つ。ただし**対応の取れない引用符**
    (奇数個のバックティック等) のような壊れた入力では、除去範囲そのものが意図とずれるため
    一致を保証しない。
    """
    return f"L{line + 1}"


# シリーズ番号つきの題。規定 (ABE) は "Do not use the same main title with numbered minor
# (serial) titles, even for a series of manuscripts by the same authors." 番号の形 3 つ: Part II / Report 2 / Series 3、
# 括弧の番号 (II) / (2nd report)、2nd report / second report
_RE_TITLE_SERIES = [
    re.compile(r"\b(?i:part|report|series)\s+(?:[IVX]{1,4}|\d{1,2})\b"),
    re.compile(r"\(\s*(?:[IVX]{1,4}|\d{1,2})(?:st|nd|rd|th)?(?:\s+(?i:report))?\s*\)"),
    re.compile(r"(?i:\b(?:\d{1,2}(?:st|nd|rd|th)|first|second|third|fourth|fifth)\s+report\b)"),
]


def lint_title(blocks, profile):
    """タイトルの語数と、略語らしき全大文字語。

    **どちらも `limits.title_words` を持つ誌でだけ掛ける**。規定でタイトルの語数制限と
    「略語は分野で一般的なもの以外不可」は同じ Title 節にあり、片方だけ定める誌が考えにくいため、
    略語の検査に別キーを起こさず同じキーで発火させる (キー増殖を避ける)。
    """
    out = []
    limit = (profile.get("limits") or {}).get("title_words")
    # 語数の上限の無い誌でも、lint.title_conventions で略語とシリーズ番号を見る (どちらも参考)
    conventions = journal_profile.as_flag((profile.get("lint") or {}).get("title_conventions"),
                                          "lint.title_conventions")
    inners = _div_inner(blocks, "title")
    if not inners:
        return out
    title = inners[0]
    words = _word_tokens(title)
    if limit and len(words) > int(limit):
        out.append(must(f"タイトルの語数 {len(words)} が上限 {limit} 語を超過しています"))
    series = []
    if conventions:
        # 重なる一致 ((2nd report) と 2nd report) は長いほうだけを残す
        for m in sorted((m for pat in _RE_TITLE_SERIES for m in pat.finditer(title)),
                        key=lambda m: (m.start(), -(m.end() - m.start()))):
            if not any(m.start() < s.end() and s.start() < m.end() for s in series):
                series.append(m)
    if limit or conventions:
        # 略語の可否は「分野で一般的か」の判断が要るので参考情報に留める (規定 Title 節)。
        # 2 文字以上の全大文字語だけを拾う (I / A などの 1 文字は落とす)。
        # シリーズ番号として拾った部分 (Part II の II など) は略語に数えない
        abbrs = sorted({m.group(0) for m in re.finditer(r"\b[A-Z][A-Z0-9-]{1,}\b", title)
                        if not any(s.start() <= m.start() < s.end() for s in series)})
        if abbrs:
            out.append(info(f"タイトルに略語らしき語があります ({', '.join(abbrs)})。"
                            "規定は「分野で一般的なもの以外は不可」としています"))
    if series:
        out.append(info("タイトルにシリーズ番号らしき部分があります ("
                        + ", ".join(sorted({re.sub(r"\s+", " ", m.group(0).strip()) for m in series}))
                        + ")。規定は、同じ著者の一連の論文でも、同じ主題に番号つきの副題を付けた題を使わないよう求めています"))
    return out


def _keyword_items(blocks):
    """Keywords の Div を (区切り, 語の list) に割る。Div が無ければ None。lint_keywords の規約 (下) で割る。"""
    inners = _div_inner(blocks, "keywords")
    if not inners:
        return None
    body = re.sub(r"^\s*\**\s*key\s*words?\s*\**\s*[:：]\s*\**\s*", "", inners[0].strip(),
                  flags=re.IGNORECASE)
    sep = ";" if ";" in body else ","
    words = [w.strip(" .　") for w in body.split(sep)]
    return sep, [w for w in words if w]


def lint_keywords(blocks, profile):
    """キーワード数が limits.keywords ([下限, 上限]) の範囲内か。

    Keywords Div の中身は `**Keywords:** a; b; c` のようなラベル込みの自由文なので、
    (1) 先頭のラベル (`**Keywords:**` / `Keywords:`) を落とし、
    (2) `;` があれば `;` で、無ければ `,` で割る、という規約にした。
        医学用語 (MeSH) は "Drug-Related Side Effects and Adverse Reactions" のように
        語中にカンマを含みうるので、セミコロンを優先する。
    """
    rng = (profile.get("limits") or {}).get("keywords")
    if not rng:
        return []
    lo, hi = (list(rng) + [None, None])[:2] if isinstance(rng, (list, tuple)) else (1, rng)
    parsed = _keyword_items(blocks)
    if parsed is None:
        return [must("Keywords の Div (custom-style=\"Keywords\") が見当たりません")]
    sep, words = parsed
    n = len(words)
    if (lo and n < int(lo)) or (hi and n > int(hi)):
        return [must(f"キーワード数 {n} が規定の {lo}〜{hi} 語の範囲外です "
                     f"(区切りは '{sep}' とみなしました: {' / '.join(words)})")]
    return []


def lint_abstract_citations(blocks, profile):
    """抄録内の文献引用 (abstract.citations_allowed: false のとき)。"""
    if (profile.get("abstract") or {}).get("citations_allowed", True):
        return []
    inner = _abstract_inner(blocks)
    if inner is None:
        return []
    out = []
    keys = _citation_keys(inner)
    if keys:
        out.append(must(f"抄録に文献引用があります ({', '.join(sorted(set(keys)))})。"
                        "この雑誌は抄録での引用を認めていません"))
    # 手で書いた番号の引用 ([1] / [3, 4] / [7–10]) も拾う ([@key] だけを見ると見逃す)。
    # 区間 ([0, 1]) などと見分けられないので参考情報。0 を含むもの・リンク ([1](…)) は数えない
    manual = []
    for m in re.finditer(r"\[\s*(\d{1,3}(?:\s*[-–,]\s*\d{1,3})*)\s*\](?![(\[{])", inner):
        if "0" not in re.split(r"\s*[-–,]\s*", m.group(1)) and m.group(0) not in manual:
            manual.append(m.group(0))
    if manual:
        out.append(info(f"抄録に手で書いた引用らしい番号があります ({', '.join(manual)})。"
                        "この雑誌は抄録での引用を認めていません (区間などの番号なら直さなくてよい)"))
    return out


def _norm_item(s):
    """項目名の照合用の正規化 (アポストロフィ除去 + 単複の畳み込み)。

    `Authors' contributions` と `Author contributions` を同じものとして扱うために、
    アポストロフィを落とし、4 文字以上の語の末尾 `s` を落とす
    (`authors' contributions` → `author contribution`)。両辺に同じ処理を掛けるので
    単複の取り違えだけが吸収され、別語同士が一致することはない。
    """
    s = _norm(s).replace("'", "")
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in s.split())


def _item_matches(present, want):
    """原稿の見出し present が要求項目 want に相当するか (双方向の前方一致)。

    `present == want or present.startswith(want)` の一方向だけでは、原稿の見出しが
    要求名より**短い**ときに一致しない。`Author contributions` (単数) や
    `Data availability` (statement なし) という医学系誌で普通の表記が「欠落」と報告されてしまう。
    逆向きの前方一致を許すと `Data` のような 1 語の見出しまで通ってしまうので、
    短い側が 2 語以上のときに限る。

    前方一致は**語の境界での一致**で見る (短い側の直後が空白であること)。文字列の前方一致だと、
    `Resultant observations` を Results の節と、`Data avail` を Data availability statement と見なしてしまう。
    `Results and discussion` は Results に当たる。
    """
    if present == want or present.startswith(want + " "):
        return True
    return want.startswith(present + " ") and len(present.split()) >= 2


def lint_declarations(blocks, profile):
    """Declarations の必須 6 項目が見出しとして揃っているか。"""
    required = (profile.get("declarations") or {}).get("required")
    if not required:
        return []
    # テキストボックス内の見出しを除く (本文の流れの外にあるものを
    # 必須節と数えないため)。lint_abbreviations / lint_references_last と規則を揃えた。
    headings = [b for b in blocks if b["kind"] == "heading" and not b["in_textbox"]]
    out = []
    # Declarations 節の範囲 (見出し 'Declarations' から次の同レベル以上の見出しまで) を切る
    start = next((i for i, h in enumerate(headings) if _norm(h["text"]) == "declarations"), None)
    if start is None:
        out.append(must("Declarations 節の見出しが見当たりません "
                        "(規定は 6 項目すべてを必須としています)"))
        scope = headings
    else:
        level = headings[start]["level"]
        end = next((i for i in range(start + 1, len(headings))
                    if headings[i]["level"] <= level), len(headings))
        scope = headings[start + 1:end]
    present = [_norm_item(h["text"]) for h in scope]
    missing = [str(r) for r in required
               if not any(_item_matches(p, _norm_item(r)) for p in present)]
    if missing:
        out.append(must("Declarations の必須項目が見当たりません: " + " / ".join(missing)
                        + " (該当が無い場合も \"Not applicable\" と書く必要があります)"))
    return out


def _is_abbrev_heading(heading_text):
    """`Abbreviations` / `Abbreviations and acronyms` のような見出しか。"""
    return _norm(heading_text).startswith("abbreviations")


def lint_abbreviations(text, blocks, profile):
    """Abbreviations 節が Abstract と Introduction の間にあるか。

    **節そのものが無い場合は参考情報に留める** — 規定は「Abstract と Introduction の間に置く」と
    いう**配置**を定めており、略語を使わない原稿にまで一覧を要求してはいないため。
    節はあるが位置が違う場合は規定の配置に反するので要修正にする。

    位置は「Abbreviations が文書の最初の見出しか」(`idx != 0`) ではなく
    **「Abbreviations の直後の見出しが Introduction か」**で判定する。前者は本テンプレの規約
    (タイトル・抄録を見出しではなく Div で書く) に暗黙に依存しており、原稿に `# Abstract` という
    見出しを 1 つ足しただけで、配置が規定どおりでも要修正が出る (実測)。「位置」ではなく
    「見出しの順番の番号」を見ることになるためである。
    """
    if not (profile.get("declarations") or {}).get("abbreviations_section"):
        return []
    headings = [b for b in blocks if b["kind"] == "heading" and not b["in_textbox"]]
    idx = next((i for i, h in enumerate(headings) if _is_abbrev_heading(h["text"])), None)
    if idx is None:
        return [info("Abbreviations 節が見当たりません。略語を使う場合は "
                     "Abstract と Introduction の間に一覧を置いてください")]
    out = []
    loc = _loc(headings[idx]["line"])
    nxt = headings[idx + 1] if idx + 1 < len(headings) else None
    if nxt is None:
        out.append(must(f"Abbreviations 節 ({loc}) の後ろに節がありません。"
                        "規定は Abstract と Introduction の間に置くよう定めています"))
    elif not _norm(nxt["text"]).startswith("introduction"):
        out.append(must(f"Abbreviations 節 ({loc}) の直後の節が "
                        f"'{nxt['text']}' です。規定は Abstract と Introduction の"
                        "間に置くよう定めています"))
    abs_div = next((b for b in blocks if b["kind"] == "div"
                    and (b["style"] or "").lower() == "abstract"), None)
    if abs_div is not None and abs_div["line"] > headings[idx]["line"]:
        out.append(must(f"Abbreviations 節 ({loc}) が Abstract "
                        f"({_loc(abs_div['line'])}) より前にあります"))
    return out


# 合成 1 文字 → 規定が求める書き方 (Units 節 4: 度記号 "°" + 大文字 "C" で書く)
_FORBID_HINTS = {"℃": "°C", "℉": "°F", "㎎": "mg", "㎏": "kg", "㎜": "mm",
                 "㎝": "cm", "㎡": "m^2^", "㎥": "m^3^", "㎕": "µL", "㎖": "mL", "㎗": "dL"}


def lint_forbidden_chars(text, profile):
    """lint.forbid_chars に挙げた合成文字の使用。"""
    chars = (profile.get("lint") or {}).get("forbid_chars")
    if not chars:
        return []
    origin = _origin_note(profile, "forbid_chars")
    lines = text.splitlines()
    hits = {}
    for i, line in enumerate(lines):
        for ch in chars:
            if ch and ch in line:
                hits.setdefault(ch, []).append(_loc(i))
    out = []
    for ch, locs in hits.items():
        hint = _FORBID_HINTS.get(ch)
        out.append(must(f"合成 1 文字 '{ch}' を使っています ({', '.join(locs[:8])}"
                        + ("…" if len(locs) > 8 else "") + ")"
                        + (f" — '{hint}' と書いてください" if hint else ""), origin))
    return out


_RE_URL = re.compile(r"https?://\S+|www\.\S+")
# 全角カンマ (，) による桁区切りも拾う (日本語入力で書かれた原稿では起こりうる)。
_RE_THOUSANDS = re.compile(r"(?<![\w.,，])\d{1,3}(?:[,，]\d{3})+(?![\w])")


def lint_thousands_separator(text, profile):
    """数値の桁区切りカンマ (tables.thousands_separator: false のとき)。

    誤検出の除外範囲:
      - **HTML コメント / コードは `_strip_noise` が既に落としている** (骨格の日本語解説文が
        誤検出源になるため)。
      - **URL** は行から取り除いてから照合する (クエリ文字列に `1,000` 形式が現れうる)。
      - **References 節と `#refs` Div** は照合しない (文献の巻号ページに桁区切りは出ないが、
        原稿側で手書きした文献リストを持つ誌もあるため範囲から外す)。
      - パターンは `1,234` / `12,345,678` のような**桁区切りの形をしたものだけ**に絞る
        (前後が英数字なら拾わない)。`^1,2^` のような上付き所属番号や日付は掛からない。
    **表の中も照合する** — 規定は Tables 節でこの規則を述べているが、同じ原稿の本文だけ
    カンマ区切りにする理由が無く、実際 BHI の検証用ダミーは本文でも "12 000" と書いている。
    """
    if (profile.get("tables") or {}).get("thousands_separator", True):
        return []
    body = re.split(r"^#+\s*References\b.*$", text, maxsplit=1,
                    flags=re.MULTILINE | re.IGNORECASE)[0]
    body = re.sub(r"^:::+\s*\{#refs\}.*?^:::+\s*$", " ", body, flags=re.DOTALL | re.MULTILINE)
    hits = []
    for i, line in enumerate(body.splitlines()):
        for m in _RE_THOUSANDS.finditer(_RE_URL.sub(" ", line)):
            hits.append(f"{m.group(0)} ({_loc(i)})")
    if not hits:
        return []
    return [must("数値の桁区切りカンマを使っています: " + ", ".join(hits[:8])
                 + ("…" if len(hits) > 8 else "")
                 + " — 規定は空白区切り (10 000) を求めています")]


# 記入欄は**改行をまたぐ**ことがある (骨格 main.md に 3 件 / cover-letter.md に 3 件。実測)。
# 行単位で照合すると取りこぼすので全文に対して掛ける。中身に `<` `>` が単独で現れても
# (引用ブロックの `> ` など) 拾えるよう、境界は `<<` / `>>` の不在で表す。
#
# 境界には**空行 (段落の切れ目)** も使う。境界が「`<<` と `>>` が一定の文字数以内に
# あること」だけだと、本文に単独で現れた `<<`
# (左シフト演算子や「はるかに小さい」の意味) が、段落をまたいで無関係な `>>` と対になり、
# 巨大な文字列を記入欄として要修正で報告する (実測)。骨格の記入欄は改行はまたぐが
# 空行はまたがないので、この境界で誤検出だけが落ちる。上限は 2000 文字
# (段落境界が効くので暴走の心配が無い。400 文字では長い記入欄を
# **1 件も報告せず取り逃す**)。
_RE_PLACEHOLDER = re.compile(r"<<(?:(?!<<|>>|\n[ \t]*\n).){1,2000}>>", re.DOTALL)

# 記入欄が残ったまま提出される文書 (validate が読むのは main.md だけなので、任意文書はここで補う)
_PLACEHOLDER_FILES = ("cover-letter.md", "revise-report.md")


def lint_placeholders(text, profile, input_root=None):
    """骨格の記入欄 `<<...>>` の残存。

    タイトルや所属が記入欄のまま編集部へ届くと形式審査で差し戻される。骨格の解説は
    HTML コメントで書かれており `_strip_noise` が落とすので、コメント中の `<<...>>` は掛からない。

    **pandoc の扱いは記入欄の中身によって 3 通りに分かれる** (実測。骨格
    BHI 向けの骨格の記入欄 34 種 = 48 箇所を pandoc に通して確認した。
    種類 = 同じ文面の記入欄を 1 つに数えたもの):
      (a) そのまま残る … 中身にカンマ・日本語・先頭が数字 のいずれかがある場合
          (`<<Title of the Manuscript in Title Case, Not Exceeding 30 Words>>` など 18 種)
      (b) **中身が消えて `<>` だけが残る** … 中身が HTML タグとして解釈できる場合
          (`<<Given-name Family-name>>` `<<Department>>` など **15 種 = 28 箇所**。pandoc が
          `<Given-name Family-name>` を生の HTML タグとみなし docx 出力で捨てる)
      (c) メールリンクになる … `<<name@example.org>>` (pandoc の自動リンク)
    **危ないのは (b)** である — 記入欄が消えて `<>` だけになるので、docx を通し読みしても
    「書き忘れ」ではなく組版のごみに見え、著者名や所属が空欄のまま投稿されうる。
    「記入欄はそのまま docx に出るので見れば分かる」は (a) にしか当てはまらない。
    **Markdown 層で捕まえるほかない**。
    """
    if not (profile.get("lint") or {}).get("placeholder_markers"):
        return []
    origin = _origin_note(profile, "placeholder_markers")
    targets = [("main.md", text)]
    out = []
    if input_root:
        for name in _PLACEHOLDER_FILES:
            path = Path(input_root) / name
            if not path.is_file():
                continue
            # 読み込みを例外処理で囲む。read_text をそのまま
            # 呼ぶと、任意提出物が UTF-8 でない / 読み取り権限が無いだけで validate が
            # 例外で落ち、提出物を組み立てる最終工程 (package.sh) が異常終了する。
            try:
                targets.append((name, _strip_noise(path.read_text(encoding="utf-8"))))
            except OSError as e:
                out.append(info(f"{name} を読めなかったので記入欄の検査をしていません ({e})"))
            except UnicodeDecodeError:
                out.append(info(f"{name} が UTF-8 として読めなかったので"
                                "記入欄の検査をしていません"))
    for name, body in targets:
        hits = []
        for m in _RE_PLACEHOLDER.finditer(body):
            frag = re.sub(r"\s+", " ", m.group(0)).strip()
            hits.append(f"{frag[:60]}{'…' if len(frag) > 60 else ''} "
                        f"({_loc(body.count(chr(10), 0, m.start()))})")
        if hits:
            out.append(must(f"{name} に骨格の記入欄 `<<...>>` が {len(hits)} 箇所残っています: "
                            + ", ".join(hits[:6]) + ("…" if len(hits) > 6 else ""), origin))
    return out


# 凡例 Div の中身は段落だけであること。箇条書き・表・見出し・引用・入れ子 Div は
# pandoc が `Legend` 以外の段落スタイルを付けるため、最終パッケージの凡例の集約がそこで止まる。
#
# 見落としやすいのは次の 3 つで、いずれも生成 docx で `Legend` の間に別スタイルの段落が
# 挟まることを実測した。
#   - コードフェンス (` ``` ` / `~~~`)  → `SourceCode`。**目印 `~~~` で拾う** (_blank_fence)
#   - 空白 4 個以上の字下げ            → `SourceCode`。長い凡例を読みやすくしようとして
#                                        **偶然起きる**のがいちばん厄介である
#   - 定義リスト (`用語` の次行に `: 説明`) → `DefinitionTerm` / `Definition`。
#                                        「凡例で略語を再定義する」という BHI の要求を
#                                        素直に書くと出てくる形である
# 脚注定義と水平線も同じ理由で拾う (どちらも段落にならない)。
#
# **判定は pandoc の読み方に合わせてある**。正解は pandoc 3.6.4 の AST で決めた (候補 約 200 行 × 位置)。
#   - **番号つきリストは数字だけではない**。凡例を `(A) …` で
#     始めると pandoc は `OrderedList (UpperAlpha, TwoParens)` として読み、段落スタイルが `Legend`
#     でなくなって**集約されずに本文へ取り残される**。pandoc の fancy list
#     (英字 1 字・ローマ数字・`#`・`@`、区切り `.` / `)` / `(…)`) を `_ordered_list_start()` で見る。
#   - **規則を全行に掛けると、段落の途中の行で誤検出する**。pandoc の markdown は
#     リスト・見出し・引用・字下げのコードブロック・表・脚注定義・水平線を**ブロックの先頭でしか
#     始めない** (段落の途中の行は前の行の続きとして読む)。長い凡例を折り返した行が
#     `2020. Data were …` や `(A) and (B) …` で始まっても、それは段落の続きであって事故ではない。
#     そこで規則ごとに「どの位置の行に掛けるか」を持たせた (下の _LEGEND_RULES の 3 列目)。
#     「長い凡例の**続きの行**を字下げするとコードブロックになる」は誤りで、
#     続きの行の字下げは段落に吸収される (生成 docx でも `Legend` 1 段落のまま)。
#     コードブロックになるのは**空行のあとの字下げ** (= 字下げした新しい段落) である。
#   - 位置によってだけ現れる構造も拾う: 1 行だけの段落の直後の `===` / `---` (setext 見出し)、
#     `***` / `___` / `* * *` (水平線)、`~ 説明` (定義リストのもう 1 つの記法)。
_ROMAN_RE = r"M*(?:CM)?D?(?:CD)?C*(?:XC)?L?(?:XL)?X*(?:IX)?V?(?:IV)?I*"
# 区切りの前までの「番号」。pandoc の読み方 (Text.Pandoc.Parsing の anyOrderedListMarker) に揃える:
# 数字 (ASCII) / `#` / `@` + ラベル / 英字 1 字 / ローマ数字 (大小どちらか一方で綴ったもの)。
_RE_OL_MARKER = re.compile(
    r" {0,3}(?P<open>\()?"
    r"(?P<num>[0-9]+|#|@[\w-]*|[A-Za-z]|(?=[ivxlcdm])" + _ROMAN_RE.lower()
    + r"|(?=[IVXLCDM])" + _ROMAN_RE + r")"
    r"(?P<delim>[.)])(?P<rest>.*)")
_ROMAN_VALUE = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_value(s):
    vals = [_ROMAN_VALUE[c] for c in s.upper()]
    return sum(-v if i + 1 < len(vals) and v < vals[i + 1] else v for i, v in enumerate(vals))


def _ordered_list_start(line):
    """ブロックの先頭にあるこの行を、pandoc が番号つきリストの始まりとして読むか。

    pandoc 3.6.4 の AST を正解にして決めた規則:
      - 番号: 数字 / `#` / `@` (+ 英数字・`_`・`-` のラベル) / 英字 1 字 (a〜z・A〜Z) /
        ローマ数字 (`iv` `XII` など。`IIV` `ivx` のような綴りの崩れたものは読まない)
      - 区切り: `X.` / `X)` / `(X)`。直後は空白か行末でなければならない (`(A)x` `(A):` は段落)
      - **大文字 1 字 + ピリオドは空白が 2 個要る** (`A. Smith` のような頭文字を誤読しないため)。
        ローマ数字で値が 1 / 5 / 10 / 50 / 100 / 500 / 1000 のもの (`I.` `C.` …) も同じ扱い。
        行末で終わる場合はリストになる (`A.` だけの行)
      - `p. 5` (小文字の p・ピリオド・空白 1 個・数字) はページ番号とみなしてリストにしない
      - 行頭の空白は 3 個まで (4 個以上は字下げのコードブロック)
    タブは呼び出し側で 4 桁の位置へ展開しておくこと (pandoc も読む前に展開する)。
    """
    if re.match(r" {0,3}p\. [0-9]", line):
        return False
    m = _RE_OL_MARKER.match(line)
    if not m or not m.group("num"):
        return False
    num, delim, rest = m.group("num"), m.group("delim"), m.group("rest")
    if m.group("open") and delim != ")":
        return False
    if delim == "." and not m.group("open") and num.isalpha() and num.isupper() \
            and (len(num) == 1 or _roman_value(num) in _ROMAN_VALUE.values()):
        return rest.strip() == "" or rest.startswith("  ")
    return rest == "" or rest[0] == " "


# 凡例 Div の中身の規則: (判定, 種類, どの位置の行に掛けるか)。**1 行につき先に当たった 1 つ**を採る
# (`* * *` を箇条書きと水平線の両方に数えないため。字下げのコードブロックを最初に置くのは、
# 空白 4 個以上で始まる行は中身が何であれコードブロックになるため)。
#   "start" … ブロックの先頭 (Div の 1 行目か、空行の直後の行)
#   "setext" … 1 行だけの段落の 2 行目 (直前の行がブロックの先頭で、この行がブロックの先頭でない)
#   "deflist" … 直前の空行でない行が 1 行だけの段落で、間の空行が 1 行以下
#   "any" … どこでも (コードフェンスは段落の途中でも始まる。Div のフェンスは外側の Div を閉じうる)
#   表は区切りの行で見分ける (pandoc の 3 つの書き方。docx ではどれも `Legend` の外の表になり、題の無い表として
#   末尾へ移される): pipe table の区切り (`---|---`。先頭の `|` の有無を問わない) と simple table の区切り
#   (`----  ----`) はブロックの 2 行目、grid table の罫線 (`+---+---+`) はブロックの先頭。1 列の pipe table は区切りが
#   1 つで縦棒で閉じる (`|---|` / `---|`)。simple table の列の下線は 1 字でもよいが、2 字以上の区切りを 1 つは含む形に
#   限る (`- -` を表と取り違えないため)。
#   先頭が `|` の 1 行だけ (行ブロック) と脚注の定義 (`[^n]: …`) は docx でも `Legend` 段落のまま並ぶので拾わない。
#   単独の画像の段落 (`![…](…)`) は docx で図とキャプションになり、集約がそこで止まる。図になるのは alt が空でない画像だけが
#   1 行の段落を作るとき (`![x](y) and text` の行内の画像と alt が空の画像は `Legend` 段落のまま)。"single" はブロックの先頭で、
#   次の行が空行か終わりの行に掛ける。
#   コードのフェンス (_blank_fence が `~~~` の印にする) は 1〜3 個の空白で字下げしてもフェンスになる。pipe table の区切りの
#   列の区切りは `|` のほかに `+` も pandoc が読む (docx を正解にした突き合わせで確かめた形)。
_LEGEND_RULES = [
    (re.compile(r" {0,3}~~~").match, "コードブロック", "any"),
    (re.compile(r":::+").match, "入れ子の Div", "any"),
    (re.compile(r" {4,}\S").match, "字下げのコードブロック", "start"),
    (re.compile(r" {0,3}\+(?:[-=:]+\+)+[ \t]*$").match, "表", "start"),
    (re.compile(r" {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$").match, "水平線", "start"),
    (re.compile(r" {0,3}[-*+](?:[ \t]|$)").match, "箇条書き", "start"),
    (_ordered_list_start, "番号つきリスト", "start"),
    (re.compile(r" {0,3}!\[[^\]\n]+\]\([^)\n]*\)(?:\{[^}\n]*\})?[ \t]*$").match, "画像", "single"),
    # 参照の形の画像 (`![x]` / `![x][ref]`。定義 `[x]: y.png` は別の行) も単独なら図と題になり、集約が止まる
    (re.compile(r" {0,3}!\[[^\]\n]+\](?:\[[^\]\n]*\])?(?:\{[^}\n]*\})?[ \t]*$").match, "画像", "single"),
    (re.compile(r"#+(?:[ \t]|$)").match, "見出し", "start"),
    (re.compile(r" {0,3}\|?[ \t]*:?-+:?[ \t]*(?:[|+][ \t]*:?-+:?[ \t]*)+\|?[ \t]*$").match, "表", "setext"),
    (re.compile(r" {0,3}\|?[ \t]*:?-+:?[ \t]*\|[ \t]*$").match, "表", "setext"),
    (re.compile(r" {0,3}(?=[^\n]*-{2})-+(?:[ \t]+-+)+[ \t]*$").match, "表", "setext"),
    # 1 字の下線でも、列の間が空白 2 個以上なら simple table になる (`a  b` の次の行が `-  -`。空白 1 個の `- -` は拾わない)
    (re.compile(r" {0,3}-+(?:[ \t]{2,}-+)+[ \t]*$").match, "表", "setext"),
    (re.compile(r"(?:=+|-+)[ \t]*$").match, "見出し", "setext"),
    (re.compile(r" {0,3}>").match, "引用ブロック", "start"),
    (re.compile(r" {0,2}[:~][ \t]").match, "定義リスト", "deflist"),
]


def legend_non_para_kinds(inner):
    """凡例 Div の中身 (`_strip_noise` 済みの行) から、段落にならない構造の種類を出現順に返す。"""
    lines = [ln.expandtabs(4) for ln in inner.splitlines()]
    blank = [not ln.strip() for ln in lines]
    start = [i == 0 or blank[i - 1] for i in range(len(lines))]
    kinds = []
    for i, line in enumerate(lines):
        if blank[i]:
            continue
        prev = next((j for j in range(i - 1, -1, -1) if not blank[j]), None)
        where_ok = {
            "any": True,
            "start": start[i],
            "single": start[i] and (i + 1 >= len(lines) or blank[i + 1]),
            "setext": not start[i] and i > 0 and start[i - 1],
            # 用語は 1 行に限られる (2 行の段落の後の `: x` は段落の続き)。空行は 1 行まで
            "deflist": prev is not None and i - prev <= 2 and start[prev],
        }
        for match, label, where in _LEGEND_RULES:
            if where_ok[where] and match(line):
                if label not in kinds:
                    kinds.append(label)
                break
    return kinds


def lint_legend_placement(blocks, floats, profile):
    """`Legend` Div の配置規則と中身を検査する。

    この記法は「凡例 Div を対象の直後に置く」という**位置だけ**で対応関係を表しており、
    規則を破ってもビルドは正常終了し警告も出ない (実測 4 パターン)。最終パッケージの集約先の
    振り分けも下の語数検査も、この配置規則が守られている前提に立つ。
    """
    if not (profile.get("lint") or {}).get("legend_placement"):
        return []
    origin = _origin_note(profile, "legend_placement")
    out = []
    idents = {f["ident"] for f in floats["figures"] + floats["tables"] if f["ident"]}
    for leg in floats["legends"]:
        loc = _loc(leg["line"])
        # (0) 配置: 直前が図表でない凡例は最終パッケージの集約から漏れ、本文に取り残される
        if leg["target"] is None:
            out.append(must(f"凡例 Div ({loc}) の直前に図・表がありません。凡例は対象の図 "
                            "(画像段落) / 表 (題 + 表) の直後に置いてください "
                            "— この位置だと最終パッケージの集約から漏れて本文に残ります", origin))
        else:
            ref = leg["for"]
            if ref is None:
                # 対象に識別子が無ければ `for` は書きようがないので指摘しない
                if leg["target"]["ident"]:
                    out.append(info(f"凡例 Div ({loc}) に for 属性がありません "
                                    f"(for=\"{leg['target']['ident']}\" を書くと検算できます)",
                                    origin))
            elif ref not in idents:
                out.append(must(f"凡例 Div ({loc}) の for=\"{ref}\" は原稿に存在しない識別子です",
                                origin))
            elif ref != leg["target"]["ident"]:
                out.append(must(f"凡例 Div ({loc}) の for=\"{ref}\" と直前の図表 "
                                f"({leg['target']['ident'] or '識別子なし'}) が食い違っています",
                                origin))
        # (1) 中身: 段落以外を含むと最終パッケージの集約がそこで止まる
        kinds = legend_non_para_kinds(leg["inner"])
        if kinds:
            out.append(must(f"凡例 Div ({loc}) に段落以外の要素があります ({'/'.join(kinds)})。"
                            "pandoc が `Legend` 以外の段落スタイルを付けるため、最終パッケージの"
                            "集約がそこで止まり、以降が本文に取り残されます (段落だけで書いてください)",
                            origin))
    return out


def count_textbox_floats(floats):
    """`.textbox` の中の図・表を (図の list, 表の list) で返す。

    概算行の内訳表示と `lint_textbox_floats()` で共用する。数え方は本文フローの図表と同じで、
    違うのは `in_textbox` の真偽だけである。
    """
    return ([f for f in floats["figures"] if f["in_textbox"]],
            [t for t in floats["tables"] if t["in_textbox"]])


def lint_textbox_floats(floats, profile):
    """`.textbox` の中に図表があることを知らせる。

    図表の点数は本文フローのものしか数えない (`lint_float_counts` の説明)。その設計は
    最終パッケージの移設対象と揃えるためのものだが、**数えなかったことを黙っていてはいけない**
    — 全図表を箱に置いた原稿は「図 0 点・表 0 点」と報告され、上限の検査が
    無警告で空振りする。しかも箱の中の図表は提出構成の組み替え (末尾移設・図凡例の集約) の
    対象外なので、**最終提出 docx では本文に埋め込まれたまま残る**。BHI は
    "Figures must NOT be embedded within the manuscript file." を課しているので、
    これは規定違反に直結する。

    発火条件を `limits.figures_tables` の有無に掛けるのは、上限を定めている誌でこそ
    「数えなかった点数」が意味を持つためである (同キーを持たない誌では発火しない)。
    箱の中の図表を「本文に埋め込んではならない」と決めているのも、現状では同じ BHI だけである。

    **発火条件は意味的には「図の本文埋め込みを禁じているか」に紐づくべきで、いまは上限キーで
    代用している**。この指摘文が伝える 2 点 —— 「最終提出 docx では
    本文に埋め込まれたまま残る」「題・凡例の語数検査も掛からない」—— は、点数の上限を
    定めているかどうかと**関係がない**。いま両者が一致しているのは BHI が偶然どちらも
    持っているためで、「埋め込みは禁じるが点数の上限は定めない」誌を足した瞬間に
    この検査は空振りする。そうした雑誌プロファイルを足すときは
    `figures.embed_in_manuscript_allowed` のような専用キーを新設し、発火条件を
    「上限キーがある **または** 埋め込みが禁じられている」に広げること
    (既定を「未指定なら発火しない」にすれば、いまある誌の挙動は変わらない)。
    """
    limit = (profile.get("limits") or {}).get("figures_tables")
    if not limit:
        return []
    box_figs, box_tbls = count_textbox_floats(floats)
    if not (box_figs or box_tbls):
        return []
    n_body = len([f for f in floats["figures"] if not f["in_textbox"]]) \
        + len([t for t in floats["tables"] if not t["in_textbox"]])
    locs = ", ".join(_loc(it["line"]) for it in sorted(box_figs + box_tbls,
                                                       key=lambda it: it["line"]))
    return [must(
        f".textbox の中に図 {len(box_figs)} 点・表 {len(box_tbls)} 点があります ({locs})。"
        f"これらは上の合計点数 {n_body} 点 (上限 {limit} 点) に数えていないため、"
        "上限の検査はこれらを見落としています。"
        "textbox 内の図表は提出構成の組み替え (末尾移設・図凡例の集約) の対象外なので、"
        "最終提出 docx では本文に埋め込まれたまま残ります "
        "(規定は図を原稿ファイルに埋め込むことを禁じています)。"
        "題・凡例の語数検査も掛かりません。本文の流れの上に置き直してください")]


def lint_float_counts(floats, profile):
    """図表の合計点数と、図表の題 / 凡例の語数。

    点数の数え方:
      - **図** = 本文の流れの上にある画像記法の数。`{#fig:x}` の無い装飾画像も数える
        (最終モードでは同じように図ファイルとして書き出されるため)。
      - **表** = 本文の流れの上にあるパイプ表の数。**`.grid` Div の中の表は数える**
        (罫線の指定が違うだけで本文の表と同じ)。
      - **`.textbox` の中の図表は数えない** — 本文の流れの外にあり、最終パッケージの移設対象からも
        外れている (`docs/architecture.md` §2.5)。

    ただし数えなかったことは黙らない。全図表を `.textbox` に置いた原稿は
    「図 0 点・表 0 点」と報告され、**上限の検査が無警告で空振りする**
    (図表 9 点を箱に置いた原稿では、上限 8 点を超えていても指摘が 1 件も出ない)。
    数え方そのものを変えないのは最終パッケージの移設対象 (= 本文フローの図表) と
    定義を揃えるためなので、代わりに `limits.figures_tables` を持つ誌では
    **箱の中に図表があること自体を要修正として指摘する** (`lint_textbox_floats`)。
    """
    out = []
    figs = [f for f in floats["figures"] if not f["in_textbox"]]
    tbls = [t for t in floats["tables"] if not t["in_textbox"]]
    limit = (profile.get("limits") or {}).get("figures_tables")
    if limit and len(figs) + len(tbls) > int(limit):
        out.append(must(f"図表の合計点数 {len(figs) + len(tbls)} 点 (図 {len(figs)} / 表 {len(tbls)}) が"
                        f"上限 {limit} 点を超過しています"))
    out.extend(lint_textbox_floats(floats, profile))

    for kind, items, cfg_key in (("図", figs, "figures"), ("表", tbls, "tables")):
        cfg = (profile.get(cfg_key) or {})
        tw, lw = cfg.get("title_words"), cfg.get("legend_words")
        for it in items:
            label = it["ident"] or f"{_loc(it['line'])} の{kind}"
            if tw and it["title"]:
                # 語数は執筆者が書いたキャプション本文だけを数える
                # (pandoc-crossref が入れる "Figure 1: " は原稿に存在しない)
                n = len(_word_tokens(it["title"]))
                if n > int(tw):
                    out.append(must(f"{kind}の題 ({label}) が {n} 語で上限 {tw} 語を超過しています"))
            if lw:
                n = sum(len(_word_tokens(g["inner"])) for g in it["legends"])
                if n > int(lw):
                    out.append(must(f"{kind}の凡例 ({label}) が {n} 語で上限 {lw} 語を超過しています"))
    return out


def lint_references_last(blocks, profile):
    """References が本文の最終節か。

    最終パッケージの集約先は「References の後」ではなく **「本文の末尾 (`w:sectPr` の直前)」**であり、
    「References が最終節である以上それで規定を満たす」という前提に立っている
    (`relocate.py` の `_appender()` / `docs/architecture.md` §2.5)。前提そのものは妥当だが、検査しないと
    References の後ろに付録の節を書いたときに `References → Appendix → [改ページ] Figure Legends`
    になり、警告も出ない (実測)。**移設が働く誌でだけ**検査する。
    """
    relocating = bool((profile.get("figures") or {}).get("legends_section")) \
        or (profile.get("tables") or {}).get("placement") == "end"
    if not relocating:
        return []
    tops = [b for b in blocks if b["kind"] == "heading" and b["level"] == 1 and not b["in_textbox"]]
    idx = next((i for i, h in enumerate(tops) if _norm(h["text"]) == "references"), None)
    if idx is None or idx == len(tops) - 1:
        return []
    after = [h["text"] for h in tops[idx + 1:]]
    # 何を末尾へ移すかは誌の設定で決まる (`separate` の誌で「表を末尾へ移す」と書かないため)
    moved = []
    if (profile.get("figures") or {}).get("legends_section"):
        moved.append("図の題と凡例")
    if (profile.get("tables") or {}).get("placement") == "end":
        moved.append("表")
    return [must("References の後ろに節があります (" + " / ".join(after) + ")。"
                 f"最終パッケージは{'・'.join(moved)}を本文の末尾へ移すため、これらの節より後ろに"
                 "置かれます (規定の並びは References の後に Figure Legends。表は本文の末尾か別ファイル)")]


_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RE_TEL_LABEL = re.compile(r"\b(?:tel|phone|telephone)\b\s*[:：]?\s*(.*)", re.IGNORECASE)


def _tel_line(line):
    """電話番号の行か (ラベル + 数字 6 桁以上、または記入欄が残っている行)。

    記入欄を許すのは、`Tel: <<+81-00-0000-0000>>` のような未記入の行に対して
    「電話番号が無い」と「記入欄が残っている」の 2 つを重ねて出さないため
    (直すべき箇所は 1 つなので、指摘も 1 つにする)。
    """
    m = _RE_TEL_LABEL.search(line)
    if not m:
        return False
    rest = m.group(1)
    return len(re.findall(r"\d", rest)) >= 6 or bool(_RE_PLACEHOLDER.search(rest))


def lint_corresponding(blocks, profile):
    """連絡著者ブロックが 1 名分で、住所・電話・E-mail を備えているか。

    検出対象は `custom-style="Corresponding"` Div (reference.docx に段落スタイルを注入してあり、
    BHI の骨格では必須ブロック)。規定は corresponding author を **1 名のみ**とし、
    氏名・住所全文・電話・E-mail を Title page に書くよう求めている。
    """
    if not (profile.get("lint") or {}).get("corresponding_author"):
        return []
    inners = _div_inner(blocks, "corresponding")
    if not inners:
        return [must("連絡著者ブロック (custom-style=\"Corresponding\" Div) がありません。"
                     "規定は氏名・住所全文・電話・E-mail を Title page に求めています")]
    out = []
    if len(inners) > 1:
        out.append(must(f"連絡著者ブロックが {len(inners)} 個あります。"
                        "規定は corresponding author を 1 名のみと定めています"))
    inner = inners[0]
    labels = re.findall(r"corresponding\s+author", inner, re.IGNORECASE)
    if len(labels) > 1:
        out.append(must(f"1 つの連絡著者ブロックに 'Corresponding author' が {len(labels)} 回"
                        "現れます (1 名のみ)"))
    emails = _RE_EMAIL.findall(inner)
    if not emails:
        out.append(must("連絡著者ブロックに E-mail がありません"))
    elif len(emails) > 1:
        out.append(must(f"連絡著者ブロックに E-mail が {len(emails)} 件あります ({', '.join(emails)})"))
    if not any(_tel_line(ln) for ln in inner.splitlines()):
        out.append(must("連絡著者ブロックに電話番号 (Tel: …) がありません"))
    # 住所は形式が国ごとに違うので機械判定できない。氏名行・Tel 行・E-mail 行を除いた
    # 段落が 1 つも無ければ「住所が無い」と見なす (参考情報)。
    rest = [ln for ln in inner.splitlines()
            if ln.strip()
            and not re.search(r"corresponding\s+author", ln, re.IGNORECASE)
            and not _tel_line(ln) and not _RE_EMAIL.search(ln)]
    if not rest:
        out.append(info("連絡著者ブロックに住所らしき行がありません "
                        "(規定は住所全文 = 部門・機関・番地・市・州・郵便番号・国 を求めています)"))
    return out


# 非 SI 単位の狭い検出器。臨床慣用単位 (mmHg 等) は規定が明示的に認めているので拾わない。
# 語形は**大文字小文字を区別して**照合する — "Miles" のような固有名詞を拾わないため。
_NON_SI = [
    (re.compile(r"℉|°\s?F\b"), "°F", "°C"),
    (re.compile(r"\b[Ff]ahrenheit\b"), "Fahrenheit", "°C (摂氏)"),
    (re.compile(r"\binch(?:es)?\b"), "inch", "mm / cm"),
    (re.compile(r"\blbs?\b"), "lb", "kg"),
    (re.compile(r"\bpounds?\b"), "pound", "kg"),
    (re.compile(r"\bounces?\b|\boz\b"), "ounce", "g"),
    (re.compile(r"\bmiles?\b"), "mile", "km"),
    (re.compile(r"\bgallons?\b"), "gallon", "L"),
]


def lint_units(text, profile):
    """lint.units: SI のとき、SI でない単位らしき語を拾う (参考情報)。

    **これは「SI に準拠している」ことの証明にはならない** — 検出できるのは英米慣用単位の
    代表的な綴りだけである。臨床慣用単位 (mmHg 等) は規定が認めているので対象にしない。
    誤検出を避けるため語形は大文字小文字を区別する。
    """
    if str((profile.get("lint") or {}).get("units") or "").upper() != "SI":
        return []
    body = re.split(r"^#+\s*References\b.*$", text, maxsplit=1,
                    flags=re.MULTILINE | re.IGNORECASE)[0]
    hits = []
    for i, line in enumerate(body.splitlines()):
        for pat, label, hint in _NON_SI:
            if pat.search(line):
                hits.append(f"{label} ({_loc(i)} → {hint})")
    if not hits:
        return []
    return [info("SI でない単位らしき表記があります: " + ", ".join(sorted(set(hits))[:8])
                 + " — 規定は SI または SI 派生単位を求めています "
                 "(mmHg 等の臨床慣用単位は可)", _origin_note(profile, "units"))]


# 統計ソフトは「型番 + 製造元 + 所在地」に加えて**バージョン**も要る (規定 "Method of stating
# the names of devices")。綴りが一意なパッケージ名だけを対象にする。
_STAT_SOFTWARE = ["SPSS", "SAS", "Stata", "STATA", "MATLAB", "GraphPad", "Prism",
                  "JMP", "EZR", "S-PLUS", "R version"]
_RE_VERSION = re.compile(r"\bversion\b|\bv?\d+\.\d+", re.IGNORECASE)
_RE_VENDOR = re.compile(r"\([^)]*,[^)]*\)")


def lint_device_notation(text, profile):
    """統計ソフトにバージョンと製造元 (括弧内) が添えられているか (参考情報)。

    機器一般の「型番 + 製造元 + 所在地」は文面から機械判定できないので、規定が特に
    「バージョンも」と念を押している**統計ソフト**に絞った狭い検査にしてある。
    **この検査は不備を見逃す側に倒してある** (誤検出を避けるため) — 括弧内にカンマがあれば
    製造元の記載とみなすので、文献の括弧 `(Smith, 2020)` でも合格になる。

    (1) 同じソフト名は**出現ごとに**判定する (1 件目だけを見ると、Methods と Results の 2 箇所に
    書いて片方だけ不備がある原稿を取り逃す)。同じ文面の指摘は重複を除いてまとめる。
    (2) 窓は**段落単位**で切る (全文を空白 1 個に畳んだ 1 行で切ると、段落をまたいで隣の文の
    括弧を拾ってしまう)。
    行単位にはしない — 原稿は行を折り返して書くので、ソフト名と製造元の括弧が別の行に
    分かれているだけで不備と判定してしまう。
    """
    if not (profile.get("lint") or {}).get("device_notation"):
        return []
    body = re.split(r"^#+\s*References\b.*$", text, maxsplit=1,
                    flags=re.MULTILINE | re.IGNORECASE)[0]
    seen, out = set(), []
    for para in re.split(r"\n[ \t]*\n", body):
        flat = re.sub(r"\s+", " ", para)
        for name in _STAT_SOFTWARE:
            for m in re.finditer(rf"\b{re.escape(name)}\b", flat):
                window = flat[m.start():m.start() + 140]
                lacks = []
                if not _RE_VERSION.search(window):
                    lacks.append("バージョン")
                if not _RE_VENDOR.search(window):
                    lacks.append("製造元と所在地 (括弧内)")
                if not lacks:
                    continue
                key = (name, tuple(lacks))
                if key in seen:
                    continue
                seen.add(key)
                out.append(info(f"統計ソフト '{name}' の記載に不足があります "
                                f"({' / '.join(lacks)})。規定は「型番 + 製造元 + 所在地 "
                                "(市・州・国)」を、統計ソフトにはバージョンも求めています"))
    return out


# =====================================================================
# 表題ページ・節・定型の記述の lint
#
# どれも profile のキーで発火し (DEFAULTS の既定は無効)、誌の ID では分岐しない。
# 節の名前は sections.aliases の言い換えも同じ節とみなす — 規定の中でも Conflicts of interest / interests、
# Acknowledgments / Acknowledgements が揺れ、Materials and methods を Methods と書く原稿も多い (docs/journal-abe.md §9 の 6)。
# 区分の考え方はほかの lint と同じ: 規定が "must" で書き機械で確かに判定できるものは要修正、規定が "avoid" /
# "should" のもの・判断が要るもの・語の有無から推し量るだけのものは参考情報。
# =====================================================================

def _lint_flag(profile, key):
    """lint.<key> を真偽値として読む (誤記は警告して無効)。"""
    return journal_profile.as_flag((profile.get("lint") or {}).get(key), f"lint.{key}")


def _lint_name(profile, key):
    """lint.<key> の文字列 (節の名前・定型文)。未指定なら None。"""
    v = (profile.get("lint") or {}).get(key)
    if v is None or isinstance(v, bool) or not str(v).strip():
        return None
    return str(v).strip()


def _strip_footnotes(md, repl=""):
    """行内の脚注 `^[…]` と脚注の参照 `[^n]` を repl に置き換える。

    脚注の中の角括弧 (リンク `[…](…)`・Span) の入れ子を数え、`\\[` のようなエスケープは飛ばす。正規表現
    `\\^\\[[^\\]]*\\]` では最初の `]` までしか外せず、新住所の脚注にリンクがあると脚注の残り (`, Gutsby, Fictionia.]`) を
    著者名と読んでしまう。閉じの無い `^[` は行末までを脚注とみなす。
    """
    out, i, n = [], 0, len(md)
    while i < n:
        if md.startswith("^[", i):
            depth, j = 0, i + 1
            while j < n:
                c = md[j]
                if c == "\\":
                    j += 2
                    continue
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(repl)
            i = j + 1
            continue
        if md.startswith("[^", i):
            j = md.find("]", i)
            if j >= 0:
                out.append(repl)
                i = j + 1
                continue
        out.append(md[i])
        i += 1
    return "".join(out)


# 数式の書体の命令 (中身を残す) と、1 字に描かれる命令 (\alpha / \times など)
_RE_MATH_FONT = re.compile(r"\\(?:mathrm|mathit|mathbf|mathsf|mathtt|mathcal|mathbb|boldsymbol|text|textrm|textit|"
                           r"textbf|textsf|mbox|operatorname)\s*\{([^{}]*)\}")


def _math_plain(tex):
    """TeX の数式を、描画したときの文字に近い文字列にする。

    `\\mathrm{CO}_2` → `CO2`、`\\alpha` → 1 字、`{}` `_` `^` と数式の中の空白は字に数えない。running title の字数の判定で、
    生の文字列のまま数えると `$\\mathrm{CO}_2$` が 15 字になり、描画は 3 字の題を 50 字超として要修正にしてしまう。近似なので、
    分数などは描画と 1〜2 字ずれうる。
    """
    s = tex
    for _ in range(3):                       # 入れ子の書体命令 (\mathbf{\mathrm{x}}) を外側から外す
        s = _RE_MATH_FONT.sub(r"\1", s)
    s = re.sub(r"\\(?:[,;:! ]|quad|qquad|left|right|displaystyle)", "", s)
    s = re.sub(r"\\[A-Za-z]+", "x", s)
    s = re.sub(r"\\(.)", r"\1", s)
    return re.sub(r"[{}_^\s]", "", s)


def _plain(md):
    """Markdown の行内の記法を落とした文字列 (空白は 1 個に畳む)。題・running title・著者名・定型文の照合に使う。"""
    # 脚注は括弧の入れ子を数えて外す (正規表現 `\^\[[^\]]*\]|\[\^[^\]]*\]` では脚注の中のリンクで止まる)
    s = _strip_footnotes(md)                                       # 行内の脚注 ^[…] / 脚注の参照 [^n]
    # 数式は描画に近い文字にする ($\mathrm{CO}_2$ → CO2)。`$5 and $10` のような金額は数式と読まない
    # (pandoc の tex_math_dollars と同じく、開きの $ の直後と閉じの $ の直前が空白でなく、閉じの $ の直後が数字でないものだけ)
    s = re.sub(r"\$\$(.+?)\$\$", lambda m: _math_plain(m.group(1)), s, flags=re.DOTALL)
    s = re.sub(r"(?<![\\$])\$(?![\s$])((?:[^$\n\\]|\\.)*?[^\s\\$])\$(?!\d)", lambda m: _math_plain(m.group(1)), s)
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)              # 画像・リンク
    s = re.sub(r"\[([^\]]*)\]\{[^}]*\}", r"\1", s)                # Span [x]{…}
    s = re.sub(r"\\(.)", r"\1", s)                                # エスケープ
    s = re.sub(r"\*+|(?<!\w)_+|_+(?!\w)", "", s)                  # 強調の記号 (語の中の _ は残す)
    s = s.replace("^", "").replace("~", "")                       # 上付き・下付きの記号 (中身は残す)
    return re.sub(r"\s+", " ", s).strip()


# --- 節の名前 ---

_RE_HEADING_ATTR = re.compile(r"\s*\{[^{}]*\}\s*$")


def _heading_title(text):
    """見出しの文字列から末尾の属性 ({.unnumbered} / {#sec:x}) を外す。"""
    return _RE_HEADING_ATTR.sub("", text).strip()


def _section_key(name):
    """節の名前の照合用の形 (属性を外し、& を and にし、_norm_item で大文字小文字・アポストロフィ・語末の s を畳む)。"""
    return _norm_item(_heading_title(str(name)).replace("&", " and "))


def section_names(profile, name):
    """name と同じ節とみなす名前の list (name を先頭に、sections.aliases で同じ組にある名前を続ける)。"""
    key = _section_key(name)
    out = [str(name)]
    for group in (profile.get("sections") or {}).get("aliases") or []:
        names = [str(x) for x in (group if isinstance(group, (list, tuple)) else [group])]
        if any(_section_key(x) == key for x in names):
            out += [x for x in names if x not in out]
    return out


def _top_headings(blocks):
    """最上位の見出し (テキストボックスの外で、原稿のいちばん浅い段のもの)。"""
    heads = [b for b in blocks if b["kind"] == "heading" and not b["in_textbox"]]
    top = min((h["level"] for h in heads), default=None)
    return [h for h in heads if h["level"] == top]


def _matches_section(heading_text, names):
    """見出しの文字列が names のどれかの節か (lint_declarations と同じ双方向の前方一致)。"""
    present = _section_key(heading_text)
    return bool(present) and any(_item_matches(present, _section_key(n)) for n in names)


def find_section(blocks, profile, name):
    """最上位の見出しのうち name (と言い換え) に当たる最初のもの。無ければ None。"""
    names = section_names(profile, name)
    return next((h for h in _top_headings(blocks) if _matches_section(h["text"], names)), None)


def _section_end(blocks, head, n_lines):
    """節の終わり (次の同じ段以上の見出しの行。無ければ文書の終わり)。節の中身は head の次の行からこの行の前まで。"""
    return next((b["line"] for b in blocks if b["kind"] == "heading" and not b["in_textbox"]
                 and b["line"] > head["line"] and b["level"] <= head["level"]), n_lines)


def _references_line(blocks):
    """文献の節の始まりの行 (References の見出しか {#refs} の Div の早いほう)。無ければ None。"""
    lines = [b["line"] for b in blocks
             if (b["kind"] == "heading" and not b["in_textbox"] and _section_key(b["text"]) == "reference")
             or (b["kind"] == "div" and b["ident"] == "refs")]
    return min(lines) if lines else None


# 表題ページの Div (本文の語を探す lint はここを見ない。凡例は図表の一部として本文の側で見る)
_FRONT_STYLES = META_STYLES - {LEGEND_STYLE}


def _body_lines(text, blocks):
    """本文の行の list (表題ページの Div と文献の節から後ろを空にする。行の数と位置は原文と同じ)。"""
    lines = text.splitlines()
    for b in blocks:
        if b["kind"] == "div" and (b["style"] or "").lower() in _FRONT_STYLES:
            for i in range(b["line"], min(b["close"] + 1, len(lines))):
                lines[i] = ""
    ref = _references_line(blocks)
    if ref is not None:
        lines[ref:] = [""] * (len(lines) - ref)
    return lines


def _first_hits(lines, rx, rng=None, limit=5):
    """rx に当たる語を、語ごとに最初の位置だけ「語 (L行)」で返す (rng を渡せばその行だけを見る。単複は同じ語とみなす)。"""
    seen, out = set(), []
    for i in (rng if rng is not None else range(len(lines))):
        for m in rx.finditer(lines[i]):
            word = _fold_word(re.sub(r"\s+", " ", m.group(0)))
            if word not in seen:
                seen.add(word)
                out.append(f"{m.group(0)} ({_loc(i)})")
    return out[:limit] + (["…"] if len(out) > limit else [])


def _section_body(lines, blocks, head):
    """節の中身 (見出しの次の行から節の終わりまで) を空白 1 個でつないだ文字列と、その行の範囲。"""
    rng = range(head["line"] + 1, _section_end(blocks, head, len(lines)))
    return re.sub(r"\s+", " ", " ".join(lines[i] for i in rng)).strip(), rng


# 文献の見出しを pandoc が足すときの題 (main/00_setup/defaults.yaml の metadata の reference-section-title)
_DEFAULTS_YAML = Path(__file__).resolve().parents[1] / "00_setup" / "defaults.yaml"


def _reference_section_title():
    try:
        import yaml
        with open(_DEFAULTS_YAML, encoding="utf-8") as f:
            meta = (yaml.safe_load(f) or {}).get("metadata") or {}
        title = meta.get("reference-section-title")
        return str(title) if title else None
    except (OSError, ImportError, AttributeError, ValueError):
        return None


def lint_required_sections(text, blocks, profile):
    """sections.required の節が最上位の見出しにあるか (要修正)。

    ABE の規定は "All manuscripts must contain the essential elements … introduction, materials & methods, results, discussion …"
    と、Conflicts of interest の節と文献を求める。言い換え (Methods / Results and discussion など) は sections.aliases で許す。
    **{#refs} の Div の無い原稿**は、pandoc が文献の後ろに defaults.yaml の reference-section-title (References) の見出しを
    足すので、引用が 1 件でもあればその見出しがあるものとして数える (pandoc 3.6.4 の出力を見て確かめた。
    {#refs} の Div を置いた原稿には足さないので、見出しを書き忘れると文献が見出し無しで並ぶ)。
    """
    required = (profile.get("sections") or {}).get("required")
    if not required:
        return []
    titles = [h["text"] for h in _top_headings(blocks)]
    has_refs_div = any(b["kind"] == "div" and b["ident"] == "refs" for b in blocks)
    auto = _reference_section_title()
    if auto and not has_refs_div and _citation_keys(text):
        titles.append(auto)
    missing = [str(r) for r in required
               if not any(_matches_section(t, section_names(profile, r)) for t in titles)]
    if not missing:
        return []
    alts = [f"{r} は {' / '.join(section_names(profile, r)[1:])} も可" for r in missing
            if len(section_names(profile, r)) > 1]
    return [must("必須の節が見当たりません: " + " / ".join(missing)
                 + " (原稿の最上位の見出しで探しました" + ("。" + "、".join(alts) if alts else "") + ")。"
                 "規定はこれらの節を原稿に欠かせない要素としています")]


# 構造化抄録の見出し (ラベル) の検出。既定のラベル名 (構造化抄録を求める誌の Objective / Methods / Results /
# Conclusion、よくある Background / Conclusions など) は 1 つでも、ほかの語のラベルは 2 つ以上で構造化抄録の形とみなす
_ABS_KNOWN_LABELS = {
    "background", "introduction", "context", "objective", "objectives", "aim", "aims", "purpose", "purposes", "goal", "goals",
    "method", "methods", "materials and methods", "methods and materials", "design", "study design", "setting", "settings",
    "participants", "patients", "subjects", "intervention", "interventions", "measurement", "measurements",
    "main outcome measures", "outcome measures", "outcomes", "result", "results", "main results", "findings",
    "conclusion", "conclusions", "significance", "limitations", "implications", "interpretation", "discussion",
    "trial registration",
}
_ABS_LABEL_WORDS = r"[A-Z][A-Za-z-]*(?:[ \t]+(?:and|&|of|the|[A-Za-z-]+)){0,3}?"
# 強調したラベル: **Background:** / **Background**: / *Background.* / **Background** (コロンも点も無いのは既定のラベル名だけ数える)
_RE_ABS_LABEL_EM = re.compile(rf"(?P<em>\*\*|__|\*|_)[ \t]*(?P<label>{_ABS_LABEL_WORDS})[ \t]*"
                              r"(?:(?P<c1>[:：.])[ \t]*(?P=em)|(?P=em)[ \t]*(?P<c2>[:：])?)")
# 素のラベル: 段落か文の頭の「語: 」(Background: …)
_RE_ABS_LABEL_PLAIN = re.compile(rf"(?:^|(?<=[.!?])[ \t]+)(?P<label>{_ABS_LABEL_WORDS})[ \t]*[:：]")


def abstract_labels(inner):
    """抄録の中の構造化抄録の見出しらしいラベルを出現順に返す (構造化の形でなければ空の list)。"""
    found = []                                   # (位置, ラベル, 既定の名前か, コロンか点があるか)
    for m in _RE_ABS_LABEL_EM.finditer(inner):
        label = re.sub(r"\s+", " ", m.group("label")).strip()
        found.append((m.start(), label, label.lower() in _ABS_KNOWN_LABELS, bool(m.group("c1") or m.group("c2"))))
    for para in re.split(r"\n[ \t]*\n", inner):
        flat = re.sub(r"\s+", " ", para).strip()
        for m in _RE_ABS_LABEL_PLAIN.finditer(flat):
            label = m.group("label").strip()
            found.append((len(found) + 10 ** 6, label, label.lower() in _ABS_KNOWN_LABELS, True))
    labels = [(pos, lb) for pos, lb, known, mark in found if mark or known]
    if not (any(known for _p, _l, known, _m in found) or len(labels) >= 2):
        return []
    out = []
    for _pos, lb in sorted(labels):
        if lb not in out:
            out.append(lb)
    return out


def lint_abstract_shape(blocks, profile):
    """抄録が 1 段落か (要修正)・構造化抄録でないか (要修正)・図表に触れていないか (参考)。

    規定は抄録を "in a single paragraph" で書き、"Avoid … citing figures or tables" とする (1 段落は must に準じる書き方なので
    要修正にする)。段落は Abstract の Div の中の空行で区切って見る。

    lint.unstructured_abstract の誌 (abstract.structured が偽のとき) では、見出しつきの構造化抄録の形 (abstract_labels()) も
    要修正にする。規定 (ABE p.8) は "Structured abstracts cannot be accommodated." 段落の数だけを見て「段落の間の空行を
    消してください」と助言すると、4 段落の構造化抄録が、助言どおり空行を消すと見出しつきの 1 段落のまま要修正 0 で通ってしまう。
    そこで段落の数の助言も「見出しを外して 1 段落の文章にする」の趣旨にしてある。
    """
    cfg = profile.get("abstract") or {}
    single = journal_profile.as_flag(cfg.get("single_paragraph"), "abstract.single_paragraph")
    floats_ok = journal_profile.as_flag(cfg.get("floats_allowed"), "abstract.floats_allowed", default=True)
    unstructured = _lint_flag(profile, "unstructured_abstract") and not cfg.get("structured")
    if not single and floats_ok and not unstructured:
        return []
    inner = _abstract_inner(blocks)
    if inner is None:
        return []
    out = []
    labels = abstract_labels(inner)
    if unstructured and labels:
        out.append(must(f"抄録が見出しつきの構造化抄録の形です (見出し: {' / '.join(labels)})。この雑誌は構造化抄録を"
                        "受け付けません。見出しを外して 1 段落の文章にしてください"))
    paras = [p for p in re.split(r"\n[ \t]*\n", inner) if p.strip()]
    if single and len(paras) > 1:
        # (構造化抄録では、段落の間の空行を消すだけでは見出しつきの形が残るので、そう助言する)
        out.append(must(f"抄録が {len(paras)} 段落あります。この雑誌は抄録を 1 段落で書くよう求めています "
                        + ("(見出しを外して 1 段落の文章にしてください。段落の間の空行を消すだけでは見出しつきの形が残ります)"
                           if labels else "(見出しを付けずに 1 段落の文章にまとめてください)")))
    if not floats_ok:
        # 番号が数字で始まるものに加えて、補足資料の図表 (Supplementary Fig. S1 / Table S2) も拾う
        hits = sorted({re.sub(r"\s+", " ", m.group(0)) for m in re.finditer(
            r"@(?:fig|tbl):[\w:.-]*\w|\b(?:Supplementary\s+)?(?:Fig(?:ure)?s?\.?|Tables?)\s*S?\d+", inner, re.IGNORECASE)})
        if hits:
            out.append(info(f"抄録が図表に触れています ({', '.join(hits)})。この雑誌は抄録で図表を引用しないよう求めています"))
    return out


# 題とキーワードの照合で語に数えない語 (冠詞・前置詞・接続詞など)
_TITLE_STOPWORDS = {
    "a", "an", "the", "and", "or", "nor", "but", "of", "in", "on", "at", "to", "for", "from", "by", "with",
    "without", "into", "onto", "over", "under", "between", "among", "through", "via", "as", "per", "vs",
    "versus", "its", "their", "is", "are", "be", "using", "based", "toward", "towards", "within", "after", "before",
}


def _fold_word(w):
    """照合用の語の形 (小文字・複数形の語尾を落とす)。

    -ies → -y (studies)、-ches / -shes / -xes / -zes / -sses → es を落とす (hunches)、ほかの -s は s を落とす。
    -ss / -us / -is で終わる語 (class / apparatus / analysis) は複数形ではないので落とさない。4 字以上の語だけ。
    """
    w = w.lower().replace("’", "'")
    if len(w) <= 3 or not w.endswith("s") or w.endswith(("ss", "us", "is")):
        return w
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("ches", "shes", "xes", "zes", "sses")):
        return w[:-2]
    return w[:-1]


def _fold_forms(w):
    """照合用の語の形の集合 (小文字の元の形と、複数形とみたときの単数形の候補)。

    _fold_word は 1 つの形しか返さないので、不規則な複数形が単数形と合わない (`analyses` → analyse で題の `Analysis`
    と合わない・`apparatuses` → apparatuse で `Apparatus` と合わない)。候補を集合で持ち、2 語の集合が交われば同じ語とみなす:
    -s を落とす (scales) / -es を落とす (hunches・apparatuses) / -ies → -y (studies) / -ses → -sis (analyses・hypotheses) /
    -ices → -ex・-ix (indices・matrices)。-ss / -us / -is で終わる語と 3 字以下の語は複数形とみなさない (class・apparatus・analysis)。
    存在しない形 (cases → cas) も候補に入るが、照合の相手が実在の語なので害は無い。
    """
    w = w.lower().replace("’", "'")
    forms = {w}
    if len(w) <= 3 or not w.endswith("s") or w.endswith(("ss", "us", "is")):
        return forms
    forms.add(w[:-1])
    if w.endswith(("ches", "shes", "xes", "zes", "sses")) or (w.endswith("es") and len(w) >= 6):
        forms.add(w[:-2])                    # 短い -es (uses / goes) は落とさない (us / go と取り違えないため)
    if w.endswith("ies"):
        forms.add(w[:-3] + "y")
    if w.endswith("ses"):
        forms.add(w[:-2] + "is")
    if w.endswith("ices"):
        forms.update({w[:-4] + "ex", w[:-4] + "ix"})
    return forms


# ハイフンでつないだ語の前の部分にあるとき、語として題と照合しない接頭辞
# (`Non-Invasive` と `non-contact` の non、`Real-Time` と `real-world` の real、`Self-Powered` と `self-report` の self)。
# つないだ形そのもの (non-contact) と、接頭辞でない部分 (contact) は照合する
_HYPHEN_PREFIXES = {
    "non", "self", "real", "multi", "co", "pre", "post", "anti", "semi", "inter", "intra", "re", "un", "sub", "super",
    "over", "under", "cross", "counter", "extra", "ultra", "micro", "macro", "mid", "bi", "tri", "mono", "poly", "quasi",
    "pseudo", "auto", "de", "dis", "mis", "out", "well", "ill", "half", "all",
}


def _content_words(text):
    """語 (英字と数字の並び。ハイフンでつないだ語はつないだ形と各部分の両方) を {原文の形の小文字: (原文の形, 照合用の形の集合)}
    で返す。冠詞などは除く。

    ハイフンでつないだ語の前の部分にある接頭辞 (_HYPHEN_PREFIXES) は部分として数えない。
    照合用の形は 1 つではなく集合で持つ (_fold_forms。不規則な複数形を単数形と合わせるため)。
    """
    out = {}
    for tok in re.findall(r"[^\W_]+(?:[-'’][^\W_]+)*", _plain(text)):
        parts = re.split(r"[-'’]", tok) if re.search(r"[-'’]", tok) else []
        parts = [p for k, p in enumerate(parts) if not (k < len(parts) - 1 and p.lower() in _HYPHEN_PREFIXES)]
        for part in [tok] + parts:
            if part.lower() not in _TITLE_STOPWORDS:
                out.setdefault(part.lower(), (part, _fold_forms(part)))
    return out


def lint_keywords_not_in_title(blocks, profile):
    """キーワードが題の語を繰り返していないか (要修正)。

    規定は "Do not repeat words from the manuscript title." と語の単位で書いているので、キーワード (複数語でもよい) の
    語のどれかが題の語と同じなら指摘する。大文字小文字・語末の s (単複) は区別せず、冠詞・前置詞・接続詞は除く
    (_TITLE_STOPWORDS)。
    """
    if not _lint_flag(profile, "keywords_not_in_title"):
        return []
    titles = _div_inner(blocks, "title")
    parsed = _keyword_items(blocks)
    if not titles or parsed is None:
        return []
    title_forms = set().union(*(forms for _w, forms in _content_words(titles[0]).values()))
    hits = []
    for kw in parsed[1]:
        words = _content_words(kw)
        common = [w for w, forms in words.values() if forms & title_forms]
        if common:
            # 1 語のキーワードは語そのものを、複数語のキーワードは繰り返した語を括弧で示す
            hits.append(_plain(kw) + (f" ({', '.join(common)})" if len(words) > 1 else ""))
    if not hits:
        return []
    return [must("キーワードが題の語を繰り返しています: " + " / ".join(hits)
                 + "。この雑誌はキーワードで題の語を繰り返さないよう求めています")]


def lint_running_title(blocks, profile):
    """running title の要否と字数 (要修正)。

    規定は "If the title exceeds 50 characters (including spaces), add a running title following the affiliations.
    The running title should not exceed 50 characters, including spaces." 字数は行内の記法を落とした文字列の長さ
    (空白込み)。running title は header.running_title_from の custom-style (柱に入れる段落と同じ。未指定なら Subtitle) の
    最初の Div。
    """
    limit = (profile.get("limits") or {}).get("running_title_chars")
    if not limit:
        return []
    limit = int(limit)
    titles = _div_inner(blocks, "title")
    if not titles:
        return []
    src = (profile.get("header") or {}).get("running_title_from")
    style = str(src).strip() if isinstance(src, str) and src.strip() else "Subtitle"
    title = _plain(titles[0])
    runs = [r for r in _div_inner(blocks, style.lower()) if _plain(r)]
    if not runs:
        if len(title) > limit:
            return [must(f"題が {len(title)} 字 (空白込み) で {limit} 字を超えるのに、running title "
                         f"(custom-style=\"{style}\" の Div) がありません。この雑誌は所属の後に {limit} 字以内の "
                         "running title を置くよう求めています")]
        return []
    run = _plain(runs[0])
    if len(run) > limit:
        return [must(f"running title が {len(run)} 字 (空白込み) で上限 {limit} 字を超えています "
                     f"(\"{run[:60]}{'…' if len(run) > 60 else ''}\")")]
    return []


# 著者名の一部として扱う語 (Jr. / Sr. / II / III / IV)、学位と敬称 (規定は著者を名と姓で書くよう求め、
# 学位・肩書は書かない)。
# 照合は点を外して小文字で (`Ph.D.` → phd)。学位のうち姓と紛れうるもの (MA = 姓の Ma など) は、カンマで区切った部分が
# 学位だけのとき (`Taro YOKAN, MA`) にだけ学位と読む
_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}
_DEGREES = {"phd", "md", "msc", "bsc", "dds", "dmd", "dvm", "pharmd", "mph", "drph", "mba", "mbbs", "rn", "dsc", "scd",
            "meng", "beng", "dphil", "dmsc", "frcp", "frcs", "facs", "dr", "prof", "professor"}
_DEGREES_AMBIGUOUS = {"ma", "ms", "ba", "bs", "mpharm", "mmsc"}
_RE_AUTHOR_SEP = re.compile(r",|;|&|\band\b|\x01")


def _name_key(tok):
    return tok.replace(".", "").lower()


def _name_tokens(text):
    """名前らしい語 (英字の並び。所属の番号の退避 \\x00n\\x00 は除く) の list。"""
    return re.findall(r"[^\W\d_]+(?:['’.-][^\W\d_]+)*\.?", re.sub(r"\x00\d+\x00", " ", text))


def _author_entries(inner):
    """Author の Div を著者ごとの dict の list に割る (_split_authors もこれを使う)。

    dict は name (学位・敬称・Jr. などを除いた名前。姓の大文字の検査に使う)・display (表示用。Jr. などを付けた名前)・
    labels (上付きの文字列の list)・extras (名前から外した学位・敬称)。

    割り方:
      - 上付きの中のカンマ (^1,2^) で割らないよう先に退避する。段落 (空行)・カンマ・セミコロン・& ・and で割る。括弧の中
        (`(ORCID: …)` など) は名前から外す。メールアドレス・URL を含む部分 (`Correspondence: …@…`) は名前ではない
      - 脚注 ^[…] は括弧の入れ子を数えて外す (中にリンクがあっても。_strip_footnotes)
      - 強制改行 (行末の `\\` か空白 2 個) では必ず割る。普通の改行は、前の行が所属の番号で終わるか、改行の前後がどちらも
        2 語以上の名前のときに割る (`Taro\\nYOKAN^1^` のように名前の途中で折り返した行は割らない)
      - `Jr.` / `Sr.` / `II` / `III` / `IV` は前の名前の一部 (`John SMITH, Jr.` を 2 人と読まない。II を大文字の姓と見なさない)
      - 学位・敬称 (`PhD` / `MD` / `Dr.` など) は名前から外して extras に入れる (`Taro Yokan MD` の MD を大文字の姓と見なさない)
    """
    sups = []

    def keep(m):
        sups.append(m.group(1))
        return f"\x00{len(sups) - 1}\x00"

    s = _strip_footnotes(inner, " ")
    s = re.sub(r"\^([^^\s]+)\^", keep, s)
    s = re.sub(r"\[\^[^\]]*\]", " ", s)
    s = re.sub(r"\\\n|[ \t]{2,}\n", "\x01", s)            # 強制改行
    entries = []
    for para in re.split(r"\n[ \t]*\n", s):
        lines = para.split("\n")
        joined = lines[0]
        for prev, nxt in zip(lines, lines[1:]):
            tail = _RE_AUTHOR_SEP.split(prev)[-1]
            head = _RE_AUTHOR_SEP.split(nxt)[0]
            split = tail.strip() and head.strip() and (
                re.search(r"\x00\d+\x00\s*$", tail)
                or (len(_name_tokens(tail)) >= 2 and len(_name_tokens(head)) >= 2))
            joined += ("\x01" if split else " ") + nxt
        for part in _RE_AUTHOR_SEP.split(re.sub(r"[ \t]+", " ", joined)):
            if "@" in part or "://" in part:
                continue
            labels = [sups[int(i)] for i in re.findall(r"\x00(\d+)\x00", part)]
            name = _plain(re.sub(r"\([^)]*\)", " ", re.sub(r"\x00\d+\x00", " ", part)))
            if not name:
                continue
            toks = name.split()
            keys = [_name_key(t) for t in toks]
            if entries and all(k in _NAME_SUFFIXES for k in keys):
                entries[-1]["display"] += ", " + name           # John SMITH, Jr.
                entries[-1]["labels"] += labels
                continue
            if entries and all(k in _DEGREES | _DEGREES_AMBIGUOUS for k in keys):
                entries[-1]["extras"] += toks                   # Taro YOKAN, PhD
                entries[-1]["labels"] += labels
                continue
            extras = []
            while len(toks) > 1 and _name_key(toks[0]) in _DEGREES:          # Dr. Taro YOKAN
                extras.append(toks.pop(0))
            suffix = []
            while len(toks) > 1 and _name_key(toks[-1]) in _DEGREES | _NAME_SUFFIXES:
                (suffix if _name_key(toks[-1]) in _NAME_SUFFIXES else extras).insert(0, toks.pop())
            entries.append({"name": " ".join(toks), "display": " ".join(toks + suffix),
                            "labels": labels, "extras": extras})
    return entries


def _split_authors(inner):
    """Author の Div を [(名前, [上付きの文字列])] に割る (名前は表示用。割り方は _author_entries)。"""
    return [(e["display"], e["labels"]) for e in _author_entries(inner)]


def lint_author_surnames(blocks, profile):
    """著者の姓がすべて大文字か (要修正)。

    規定は "All surnames must be fully capitalized." (例 Taro YAMADA)。姓が名の前か後かは原稿によるので、**名前の中に
    2 字以上の語がすべて大文字のものが 1 つも無い**著者を指摘する (テンプレートの見本 `Taroh Seitai` はこの形)。
    頭文字 (`K.`) は語に数えない。
    """
    if not _lint_flag(profile, "author_surname_caps"):
        return []
    bad, extras = [], []
    for inner in _div_inner(blocks, "author"):
        # 名前は学位・敬称・Jr. などを除いた形で見る (_author_entries)。そのまま見ると `Taro Yokan MD` の MD・
        # `John Smith II` の II を大文字の姓と見なして通し、`John SMITH, Jr.` の Jr. を 1 人の著者として要修正にしてしまう
        for e in _author_entries(inner):
            toks = [t for t in re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", e["name"])
                    if len(re.sub(r"['’-]", "", t)) >= 2]
            if toks and not any(t == t.upper() and t != t.lower() for t in toks):
                bad.append(e["display"])
            extras += [x for x in e["extras"] if x not in extras]
    out = []
    if bad:
        out.append(must("姓がすべて大文字になっていない著者があります: " + ", ".join(bad)
                        + "。この雑誌は著者の姓をすべて大文字で書くよう求めています (例 Taro YAMADA)"))
    if extras:
        # 規定 (ABE) は著者を名と姓 (ミドルネームは頭文字) で書くよう求め、学位・肩書は名前に含めない。
        # 語の形から推し量るだけなので参考情報
        out.append(info("著者名に学位・敬称らしい語があります (" + ", ".join(extras) + ")。"
                        "この雑誌は著者を名と姓 (ミドルネームは頭文字) で書くよう求めています。学位や肩書は書かないでください "
                        "(姓の大文字の検査はこれらを除いて行いました)"))
    return out


_RE_SUP_LABEL = re.compile(r"^\s*\^([^^\s]+)\^")
# 異動後の新住所の脚注 (規定は記号 * ** で示す)。機関の数に数えない
_RE_NEW_ADDRESS = re.compile(r"\b(?:present|current|new|permanent)\s+address|\bnow\s+(?:at|with)\b", re.IGNORECASE)


def lint_affiliation_labels(blocks, profile):
    """機関が 2 つ以上なら所属と著者が上付きの数字で対応づけられているか (参考)。

    規定は "When authors belong to different institutions, their respective addresses should be indicated by superscript
    numbers"、記号 (* **) は新住所の脚注用。所属は Affiliation の Div の段落 (または上付きで始まる行) を 1 機関と数え、
    新住所の脚注らしいもの (present address など) は数えない。テンプレートの見本は記号で対応づけている (docs/journal-abe.md §9 の 2)。
    """
    if not _lint_flag(profile, "affiliation_superscript"):
        return []
    items = []
    for inner in _div_inner(blocks, "affiliation"):
        for para in re.split(r"\n[ \t]*\n", inner):
            cur = []
            for ln in para.splitlines():
                if _RE_SUP_LABEL.match(ln) and cur:
                    items.append(" ".join(cur))
                    cur = []
                if ln.strip():
                    cur.append(ln.strip())
            if cur:
                items.append(" ".join(cur))
    insts = [it for it in items if not _RE_NEW_ADDRESS.search(it)]
    if len(insts) < 2:
        return []
    out = []
    unlabeled = [it for it in insts if not re.match(r"\s*\^\d+\^", it)]
    if unlabeled:
        out.append(info(f"所属が {len(insts)} 機関ありますが、上付きの数字 (^1^ など) で始まらない所属があります: "
                        + " / ".join(_plain(it)[:40] + ("…" if len(_plain(it)) > 40 else "") for it in unlabeled)
                        + "。この雑誌は、著者が異なる機関に属するとき所属を上付きの数字で対応づけるよう求めています"
                        " (記号 * ** は異動後の新住所の脚注に使う)"))
    names = [n for inner in _div_inner(blocks, "author") for n, labels in _split_authors(inner)
             if not any(re.search(r"\d", lb) for lb in labels)]
    if names:
        out.append(info(f"所属が {len(insts)} 機関あるのに、上付きの数字で所属を示していない著者があります: "
                        + ", ".join(names)))
    return out


def lint_float_titles(blocks, profile):
    """題 (キャプション) の無い図表 (要修正)。

    規定は "figures and tables with captions" を原稿に欠かせない要素とする。図は段落が画像 1 つだけで alt が空のもの
    (pandoc は題の無い画像として出す)、表は前後の行に `: 題` の無いパイプ表。テキストボックスの中も見る (題は箱の中でも要る)。
    文中に置いた画像 (段落に文字もある) は図ではないので見ない。
    """
    if not _lint_flag(profile, "float_titles"):
        return []
    bad = []
    for b in blocks:
        if b["kind"] == "image" and len(b["images"]) == 1 and _RE_IMAGE.fullmatch(b["text"].strip()) \
                and not b["images"][0]["alt"].strip():
            bad.append(f"図 ({_loc(b['line'])})")
        elif b["kind"] == "table" and not (b["title"] or "").strip():
            bad.append(f"表 ({_loc(b['line'])})")
    if not bad:
        return []
    return [must("題 (キャプション) の無い図表があります: " + ", ".join(bad)
                 + "。この雑誌は図表に題を付けるよう求めています (図は ![題](…)、表は表の前か後の行に `: 題 {#tbl:x}`)")]


def lint_table_caption_attrs(blocks, profile):
    """表の題の属性に {#tbl:x} 以外のもの (`.wide` など) があるか (要修正)。

    pandoc-crossref は表の題の末尾の `{#tbl:x}` しか読めず、`{#tbl:x .wide}` のようにクラスや key=value があると番号を付けず、
    題に属性の文字列がそのまま残り、本文の参照は ¿tbl:x? になる (pandoc-crossref 0.3.19 で確かめた)。build は警告するが
    (wide-blocks.lua。段組の誌だけ)、原稿の段階で知らせる。段抜きは表を題ごと `::: wide` の Div で囲んで書く。
    """
    if not _lint_flag(profile, "table_caption_attrs"):
        return []
    bad = []
    for b in blocks:
        attr = b.get("title_attr") if b["kind"] == "table" else b.get("attr") if b["kind"] == "table_caption" else None
        if attr and re.search(r"(?:^|\s)\.[A-Za-z]|=", attr):
            line = b.get("title_line") if b["kind"] == "table" else b["line"]
            bad.append(f"{{{attr.strip()}}} ({_loc(line if line is not None else b['line'])})")
    if not bad:
        return []
    wide = any(re.search(r"(?:^|\s)\.wide\b", x) for x in bad)
    return [must("表の題の属性に {#tbl:x} 以外のものがあります: " + ", ".join(bad)
                 + "。pandoc-crossref は表の題の {#tbl:x} しか読めないので、番号が付かず、題に属性の文字列が残り、参照が ¿tbl:x? に"
                 "なります。題の属性は {#tbl:x} だけにしてください"
                 + (" (段抜きにするなら、表を題ごと ::: wide の Div で囲む)" if wide else ""))]


# 表題ページの Div と、それを読む検査 (Div が無いと黙って空振りする)
_FRONT_DIV_CHECKS = {
    "title": "題の字数と running title・題の略語・キーワードと題の語の照合",
    "author": "姓の大文字・所属との対応",
    "abstract": "抄録の語数・段落・引用・図表・構造化抄録",
    "keywords": "キーワード数・題の語の繰り返し",
}


def lint_front_matter_divs(blocks, profile):
    """lint.front_matter_divs の custom-style の Div がちょうど 1 つずつあるか (要修正)。

    表題ページの検査 (抄録・キーワード・running title・姓など) は custom-style の Div を読むので、題や著者を YAML の
    title / author や見出しで書いた原稿・抄録を `# Abstract` の下の地の段落で書いた原稿では、どの検査も黙って空振りする
    (Keywords の Div が無いときだけは lint_keywords が要修正を出す)。Div が 2 つ以上あると最初の 1 つしか見ない。
    Keywords の Div が無いことは、limits.keywords を持つ誌では lint_keywords が言うのでここでは重ねない。
    """
    styles = (profile.get("lint") or {}).get("front_matter_divs")
    if not styles:
        return []
    if isinstance(styles, str):
        styles = [styles]
    out = []
    for style in styles:
        name = str(style).strip()
        if not name:
            continue
        key = name.lower()
        divs = [b for b in blocks if b["kind"] == "div" and (b["style"] or "").lower() == key]
        checks = _FRONT_DIV_CHECKS.get(key, "この Div を読む検査")
        if not divs:
            if key == "keywords" and (profile.get("limits") or {}).get("keywords"):
                continue
            out.append(must(f"{name} の Div (custom-style=\"{name}\") が見当たりません。表題ページの要素は custom-style の Div で"
                            f"書いてください (YAML の title / author や見出し・地の段落で書くと、{checks}の検査が黙って空振りし、"
                            "差分にも出ません)"))
        elif len(divs) > 1:
            out.append(must(f"{name} の Div が {len(divs)} 個あります ({', '.join(_loc(b['line']) for b in divs)})。"
                            f"{checks}の検査は最初の Div だけを見ています。1 つにまとめてください"))
    return out


def lint_caption_case(floats, profile):
    """図表の題が Title Case らしい (参考)。

    規定は "All titles and captions should use minimal capitalization." 先頭の語を除く 4 字以上の語 (全部大文字の略語は除く)
    のうち 6 割以上・2 語以上が大文字で始まる題を拾う。固有名詞が続く題も拾うので参考情報に留める。
    """
    if not _lint_flag(profile, "caption_minimal_caps"):
        return []
    hits = []
    for kind, items in (("図", floats["figures"]), ("表", floats["tables"])):
        for it in items:
            words = re.findall(r"[A-Za-z][A-Za-z'’-]*", _plain(it["title"] or ""))
            content = [w for w in words[1:] if len(w) >= 4 and not w.isupper()]
            caps = [w for w in content if w[0].isupper()]
            if len(caps) >= 2 and len(caps) >= 0.6 * len(content):
                hits.append(f"{it['ident'] or _loc(it['line']) + ' の' + kind} ({' '.join(caps)})")
    if not hits:
        return []
    return [info("図表の題が Title Case のようです: " + ", ".join(hits)
                 + "。この雑誌は題とキャプションを最小限の大文字 (文頭と固有名詞だけ) で書くよう求めています"
                 " (固有名詞なら直さなくてよい)")]


# 略語 (2 字以上の大文字の並び。複数形の s を許す)。ハイフンでつながった型番・番号 (HB-0000) と数字を含むもの (CO2) は見ない
_RE_ABBR = re.compile(r"(?<![\w-])([A-Z]{2,})(s?)(?![\w-])")
_RE_ROMAN = re.compile(r"(?:" + r"M*(?:CM)?D?(?:CD)?C*(?:XC)?L?(?:XL)?X*(?:IX)?V?(?:IV)?I*" + r")")
# ローマ数字を番号として使う前の語 (Phase II / Type III など。略語に数えない)
_RE_ROMAN_CONTEXT = re.compile(r"\b(?:phase|type|class|grade|stage|part|step|level|study|experiment|group|series|"
                               r"chapter|section|appendix|category|trial|cohort|arm)\s+$", re.IGNORECASE)


def lint_abbreviation_definitions(blocks, profile):
    """略語を本文の初出で括弧で定義しているか (参考)。

    規定は "Each abbreviation should be defined in parentheses together with its non-abbreviated term when it first appears
    in the text (except in the Title and Abstract)." 表題ページ・凡例・図表の題・表のセル・見出し・文献以外の本文の段落を
    文書の順に読み、略語の最初の出現が括弧の中 (`… device (TJD)`) か、直後に括弧が続く (`TJD (… device)`) なら定義とみなす。
    数式・引用キー・URL は見ない。定義の中身 (正式名か) は見ないので参考情報に留める。
    """
    if not _lint_flag(profile, "abbreviation_definitions"):
        return []
    ref = _references_line(blocks)
    seen, undefined = set(), []
    for b in blocks:
        if b["kind"] != "para" or (ref is not None and b["line"] >= ref):
            continue
        para = re.sub(r"\$\$.*?\$\$|\$[^$\n]+\$|-?@[\w:.#$%&+?<>~/-]+|\]\([^)]*\)",
                      lambda m: " " * len(m.group(0)), b["text"], flags=re.DOTALL)
        for m in _RE_ABBR.finditer(para):
            ab = m.group(1)
            if ab in seen:
                continue
            if _RE_ROMAN.fullmatch(ab) and _RE_ROMAN_CONTEXT.search(para[:m.start()]):
                continue
            seen.add(ab)
            if para.rfind("(", 0, m.start()) > para.rfind(")", 0, m.start()) or re.match(r"\s*\(", para[m.end():]):
                continue
            undefined.append(f"{ab} ({_loc(b['line'] + para.count(chr(10), 0, m.start()))})")
    if not undefined:
        return []
    return [info("本文の初出で括弧の定義が見当たらない略語があります: " + ", ".join(undefined[:10])
                 + ("…" if len(undefined) > 10 else "")
                 + "。この雑誌は略語を本文での初出のときに正式名とともに括弧で定義するよう求めています (題と抄録は初出に数えない)")]


_RE_COI_CONCRETE = re.compile(
    r"\b(?:receiv\w*|grants?|fees?|honorari\w*|employ\w*|stocks?|shares?|equity|consult\w*|patents?|royalt\w*|"
    r"advis\w*|speakers?|lectur\w*|board|owns?|founders?|salar\w*|paid|payments?|funded|funding|sponsor\w*|support\w*)\b",
    re.IGNORECASE)


# 否定の語。COI の節の「No funding was received」「no conflict … regarding the support」の
# funding / received / support は申告ではないので、同じ節 (文・セミコロン・「, and」などで区切った範囲) の中で否定の語より
# 後ろにある申告の語は数えない
_RE_NEGATION = re.compile(r"\b(?:no|not|none|neither|nor|never|without)\b|n['’]t\b", re.IGNORECASE)
_RE_CLAUSE_SEP = re.compile(r"[.;!?]|,\s*(?:and|but|except|whereas|while)\b", re.IGNORECASE)


def _coi_concrete(body):
    """COI の節に、否定されていない申告の語 (_RE_COI_CONCRETE) があるか。"""
    for clause in _RE_CLAUSE_SEP.split(body):
        neg = _RE_NEGATION.search(clause)
        for m in _RE_COI_CONCRETE.finditer(clause):
            if neg is None or m.start() < neg.start():
                return True
    return False


def _norm_sentence(s):
    s = _plain(s).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower().rstrip(".")


def lint_coi(text, blocks, profile):
    """利益相反の節に定型文も具体的な申告も無さそうか (参考)。

    ABE の規定は全著者の利益相反の申告を求め、無い場合の定型文を示す (lint.coi_standard_sentence に写す)。節の中に定型文
    (大文字小文字・引用符の形・空白は区別しない) があるか、具体的な申告らしい語 (received / grant / fees / employee / stock /
    consultant / patent など) があれば黙る。どちらも無ければ (`The authors declare no conflicts of interest.` だけの節など)
    定型文を案内する。節そのものの有無は sections.required が見る。
    """
    name = _lint_name(profile, "coi_section")
    if not name:
        return []
    head = find_section(blocks, profile, name)
    if head is None:
        return []
    body, _ = _section_body(text.splitlines(), blocks, head)
    std = _lint_name(profile, "coi_standard_sentence")
    if std and _norm_sentence(std) in _norm_sentence(body):
        return []
    # 否定された語 (No funding was received) は申告に数えない (節の中を _RE_COI_CONCRETE で探すだけだと、
    # 定型文でない「no conflicts」に資金の語を添えただけの節が黙って通る)
    if _coi_concrete(body):
        return []
    return [info(f"{_heading_title(head['text'])} の節 ({_loc(head['line'])}) に、"
                 + ("利益相反が無い場合の定型文も具体的な申告も見当たりません。無い場合は規定の定型文をそのまま書いてください: "
                    f"\"{std}\"" if std else "具体的な申告が見当たりません")
                 + " (申告がある場合は、関係する会社・団体と内容を書く)")]


_RE_HUMAN_ANIMAL = re.compile(
    r"\b(?:patients?|participants?|volunteers?|informed consent|human subjects?|"
    r"subjects?(?!\s+(?:to|of|matter|areas?)\b)|animals?|mice|mouse|rats?|rabbits?|dogs?|pigs?|swine|sheep|"
    r"monkeys?|primates?|cadavers?|in vivo)\b", re.IGNORECASE)


def lint_ethics(text, blocks, profile):
    """人・動物を扱うらしい語があるのに倫理の節が無いか (参考)。

    規定は "If the research … was conducted on animal or human subjects, the authors must include statements concerning
    their ethical treatment and conduct." 対象かどうかは語の有無から推し量るだけなので参考情報。表題ページと文献は見ない。
    """
    name = _lint_name(profile, "ethics_section")
    if not name or find_section(blocks, profile, name) is not None:
        return []
    hits = _first_hits(_body_lines(text, blocks), _RE_HUMAN_ANIMAL)
    if not hits:
        return []
    return [info(f"人や動物を扱うらしい語がありますが ({', '.join(hits)})、{name} の節が見当たりません。"
                 "この雑誌は、人や動物を対象にした研究では倫理的な扱いの記述を求め、倫理委員会の承認などの証拠書類を"
                 "原稿とともに出すよう求めています")]


# AI ツールらしき語 (略語 AI と製品名は大文字小文字を区別する)
_RE_AI_TOOL = re.compile(r"(?i:\bartificial intelligence\b|\blarge language models?\b)|\bAI\b|\bLLMs?\b|"
                         r"\bChatGPT\b|\bGPT-?\d[\w.]*|\bClaude\b|\bGemini\b|\bCopilot\b|\bGrammarly\b|\bDeepL\b")


def lint_ai_disclosure(text, blocks, profile):
    """AI ツールの使用の開示の置き場所 (参考)。

    ABE の規定は生成・非生成を問わず AI ツール (LLM を含む) の使用を "in the Methods section" で開示し、どのツールを
    どう使ったかを書くよう求める (誌によっては Acknowledgments)。AI ツールらしき語が lint.ai_disclosure_section の節 (小節を含む)
    にあれば黙り、節の外にだけあれば置き場所を、どこにも無ければ「使ったなら開示する」を参考情報で出す
    (AI を研究の対象にした原稿でも語は現れるので、語の有無は開示の有無を確かめない)。
    """
    name = _lint_name(profile, "ai_disclosure_section")
    if not name:
        return []
    lines = _body_lines(text, blocks)
    head = find_section(blocks, profile, name)
    if head is not None:
        if _first_hits(lines, _RE_AI_TOOL, range(head["line"], _section_end(blocks, head, len(lines)))):
            return []
    hits = _first_hits(lines, _RE_AI_TOOL)
    if hits:
        return [info(f"AI ツールらしき語が {name} の節の外にだけあります ({', '.join(hits)})。この雑誌は AI ツール "
                     f"(生成・非生成とも。LLM を含む) を使ったなら、{name} の節で、どのツールをどう使ったかを開示するよう求めています")]
    return [info(f"AI ツールの使用の開示が見当たりません。AI ツール (生成・非生成とも。綴り・文法の確認ツールや LLM を含む) を"
                 f"使ったなら、{name} の節で、どのツールをどう使ったかを開示してください (使っていなければ不要)")]


# "supported by …" / "financed by …" も資金の記述とみなす (fund / grant / KAKENHI / sponsor の語だけを見ると、それらの語の無い
# "This work was supported by the … Foundation." を資金の記述と見なさず、助成番号の無いことも知らせない)。
# 本文の "supported by the data" / "supported by Smith et al." を拾わないよう、同じ文の 100 字以内に資金提供者らしい語
# (Foundation / Grant / Agency / Ministry / JSPS など。大文字で始まるもの) があるときだけ数える
_FUNDER_WORDS = (r"Foundations?|Funds?|Grants?|Agency|Society|Council|Ministry|Programs?|Programmes?|Trust|Endowment|"
                 r"Commission|Corporation|Company|Inc|Ltd|JSPS|JST|AMED|NEDO|NIH|NSF|KAKENHI|Institutes?|Association|"
                 r"Organi[sz]ation|University|Hospital|Office|Department|Bureau|Cent(?:er|re)")
_RE_FUNDING = re.compile(r"\b(?:fund(?:s|ed|ing)?|grants?|KAKENHI|sponsor(?:s|ed|ship)?|"
                         r"financial(?:ly)?\s+support(?:ed)?|"
                         r"(?:supported|financed)\s+(?:in\s+part\s+|partly\s+|partially\s+)?by"
                         rf"(?=[^.;]{{0,100}}?\b(?-i:{_FUNDER_WORDS})\b))\b", re.IGNORECASE)
# 助成番号らしき語: 英字と数字の混ざった 5 字以上の語 (JP21K12345 / THPF-0000)・No. / number / # の後の数字・5 桁以上の数字
_RE_GRANT_NO = re.compile(r"(?<![\w-])(?=[\w-]{5,})(?=[\w-]*[A-Za-z])(?=[\w-]*\d)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?![\w-])"
                          r"|\b(?:No\.|numbers?|#)\s*:?\s*\d|\b\d{5,}\b", re.IGNORECASE)


def lint_funding(text, blocks, profile):
    """資金の書き方 (参考)。

    ABE の規定は "list all funding sources for their work in the Acknowledgements section. For each funding source, both the
    research funder and the grant number should be provided." 資金らしき語 (fund / grant / KAKENHI / sponsor など) が
    lint.funding_section の節に無く節の外にある、節そのものが無い、節にあるのに助成番号らしき語が無い、のどれかなら参考情報。
    """
    name = _lint_name(profile, "funding_section")
    if not name:
        return []
    lines = _body_lines(text, blocks)
    head = find_section(blocks, profile, name)
    hits = _first_hits(lines, _RE_FUNDING)
    advice = f"この雑誌は資金源をすべて {name} の節に、資金提供者と助成番号の両方で書くよう求めています"
    if head is None:
        return [info(f"資金らしき語がありますが ({', '.join(hits)})、{name} の節が見当たりません。{advice}")] if hits else []
    body, rng = _section_body(lines, blocks, head)
    if not _RE_FUNDING.search(body):
        return [info(f"資金らしき語が {name} の節の外にだけあります ({', '.join(hits)})。{advice}")] if hits else []
    if not _RE_GRANT_NO.search(_RE_FUNDING.sub(" ", body)):
        return [info(f"{name} の節 ({_loc(head['line'])}) に資金の記述がありますが、助成番号らしき語が見当たりません。{advice}")]
    return []


# --- 文献・補足資料 ---

_UNCITABLE_TYPES = {"unpublished": "未発表原稿", "thesis": "学位論文", "phdthesis": "学位論文", "mastersthesis": "学位論文"}
_RE_UNCITABLE_NOTE = re.compile(r"personal communication|private communication|private letter|unpublished|"
                                r"in preparation|submitted|company data|internal (?:report|document|data)|catalog(?:ue)?",
                                re.IGNORECASE)


def lint_uncitable_references(input_root, profile):
    """引けない文献の可能性 (参考)。

    ABE の規定は "company data, unpublished manuscripts, unpublished theses, private letters, catalogues, and personal
    communications" を文献にできないとする。abe.csl は @thesis を本の形で出すので、出力からは見分けられない。
    そこで ref.bib の型 (@unpublished / @thesis など) と note・howpublished・pubstate・type の語を見る。本文で引用した文献だけ。
    学位論文は刊行・公開されていれば引けるので参考情報に留める。
    """
    if not _lint_flag(profile, "uncitable_references"):
        return []
    hits = []
    for etype, key, fields in _cited_bib_entries(input_root):
        reasons = [f"@{etype} = {_UNCITABLE_TYPES[etype]}"] if etype in _UNCITABLE_TYPES else []
        for f in ("note", "howpublished", "pubstate", "type"):
            m = _RE_UNCITABLE_NOTE.search(fields.get(f, ""))
            if m:
                reasons.append(f"{f} に \"{m.group(0)}\"")
        if reasons:
            hits.append(f"{key} ({', '.join(reasons)})")
    if not hits:
        return []
    return [info("引けない文献の可能性があります: " + ", ".join(hits)
                 + "。この雑誌は社内資料・未発表原稿・未発表の学位論文・私信・カタログ・個人的な通信を文献にできないとしています"
                 " (学位論文は刊行・公開されていれば引ける)")]


SUPP_DIRNAME = "supplementary"
# OS が勝手に作る管理用ファイル。補足資料として複製せず (package.py)、容量にも数えない。雑誌に依存しない規則なので
# profile のキーにはしない。ドット始まりのファイルも同じ理由で落とす (`.gitkeep` 等)。
# 容量の検査 (ここ) と複製 (package.py) で同じ規則を使うため、ここに置く
SUPP_JUNK_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}
SUPP_JUNK_DIRS = {"__macosx"}


def supplementary_is_junk(rel):
    """補足資料として複製しない管理用ファイルか (rel は supplementary/ からの相対パス)。"""
    if rel.name.lower() in SUPP_JUNK_NAMES or rel.name.startswith("."):
        return True
    return any(part.lower() in SUPP_JUNK_DIRS for part in rel.parts[:-1])


def walk_supplementary(src_root):
    """補足資料のディレクトリの中のファイルを ([実パス], [行き先の読めないリンクの相対パス]) で返す (管理用ファイルも含む)。

    中のディレクトリのリンクもたどる (rglob はたどらない)。自分の祖先と同じ実体のディレクトリ (ループ) には入らない。
    リンクなのに中身が見えないもの (コンテナから見えない場所を指すリンク・行き先の無いリンク) は 2 つ目の list に入れる
    (package.py は止まる。補足資料が黙って提出物から抜けないように)。
    package.copy_supplementary と容量の検査が共用する。
    """
    files, unseen, chain = [], [], {}
    for dirpath, dirs, names in os.walk(src_root, followlinks=True):
        ancestors = chain.get(dirpath, frozenset()) | {os.path.realpath(dirpath)}
        keep = []
        for d in dirs:
            sub = os.path.join(dirpath, d)
            if os.path.realpath(sub) in ancestors:
                continue
            chain[sub] = ancestors
            keep.append(d)
        dirs[:] = keep
        for n in names:
            p = Path(dirpath) / n
            if p.is_file():
                files.append(p)
            elif p.is_symlink() and not p.exists():
                unseen.append(p.relative_to(src_root).as_posix())
    return files, unseen


# アーカイブ (圧縮) と実行形式のファイル (ABE の Submission Form は補足資料にこれらを含まないことを確かめさせる)
_ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz", ".tbz2", ".xz", ".txz", ".7z", ".rar", ".lzh",
                     ".lha", ".cab", ".zst"}
_BINARY_SUFFIXES = {".exe", ".dll", ".so", ".dylib", ".bin", ".msi", ".dmg", ".jar", ".class", ".o", ".obj", ".pyc"}


def lint_supplementary(input_root, profile):
    """補足資料の容量 (要修正) とアーカイブ・実行形式 (参考)。

    ABE の規定は "The maximum file size of each file is 50 Mbytes and the total file size of all Supplementary Material must not
    exceed 50 Mbytes." 容量は 10 進 (1 MB = 1 000 000 バイト) のバイトで比べる (package.py の動画の上限と同じ)。
    管理用ファイル (.DS_Store など) は複製しないので数えない。リンクの先が読めないものは package.py が止まるのでここでは数えない。
    """
    limits = profile.get("limits") or {}
    per, total = limits.get("supplementary_file_mb"), limits.get("supplementary_total_mb")
    archives = _lint_flag(profile, "supplementary_archives")
    root = Path(input_root) / SUPP_DIRNAME
    if not (per or total or archives) or not root.is_dir():
        return []
    files = []
    for p in sorted(walk_supplementary(root)[0]):
        rel = p.relative_to(root)
        if not supplementary_is_junk(rel):
            files.append((rel.as_posix(), p.stat().st_size))
    out = []
    if per:
        cap = int(float(per) * 1000 * 1000)
        big = [f"{rel} ({size:,} バイト)" for rel, size in files if size > cap]
        if big:
            out.append(must(f"補足資料に 1 ファイルの上限 {per} MB (= {cap:,} バイト) を超えるファイルがあります: "
                            + ", ".join(big)))
    if total:
        cap = int(float(total) * 1000 * 1000)
        n = sum(size for _rel, size in files)
        if n > cap:
            out.append(must(f"補足資料の合計 {n:,} バイト ({len(files)} ファイル) が上限 {total} MB (= {cap:,} バイト) を"
                            "超えています"))
    if archives:
        bad = [rel for rel, _size in files if Path(rel).suffix.lower() in _ARCHIVE_SUFFIXES | _BINARY_SUFFIXES]
        if bad:
            out.append(info("補足資料にアーカイブ (圧縮) か実行形式らしいファイルがあります: " + ", ".join(bad)
                            + "。この雑誌の Submission Form は、補足資料にバイナリのファイルとアーカイブのファイルを"
                            "含まないことを確かめさせます (中身を展開して置く)"))
    return out


# =====================================================================
# reference.docx との突合
# =====================================================================

def check_reference_layout(journal_id, profile):
    """雑誌固有 reference.docx の実体裁が profile.yaml とずれていたら警告文を返す。

    体裁は reference.docx に焼き込む設計なので、profile.yaml を編集して
    make-reference.sh の再実行を忘れると古い体裁のまま投稿まで進む。build 時にも同じ検査を
    出しているが (build_docx._warn_stale_reference)、提出物を組み立てる直前にもう一度掛ける。
    """
    ref = profile.get("reference_doc")
    if not ref:
        return []      # _default 継承の告知は build 側が受け持つ
    path = journal_profile.JOURNALS_DIR / journal_id / ref
    if not path.is_file():
        return []      # 不在の告知も build 側が受け持つ
    hint = journal_profile.layout_fix_hint(journal_id, profile)
    return [must(f"{path} の体裁が profile.yaml と食い違っています "
                 f"({key}: profile={want!r} != reference.docx={got!r})。{hint}")
            for key, want, got in journal_profile.layout_mismatches(profile, path)]


_RE_SPAN_STYLE = re.compile(r"\]\{[^}]*custom-style\s*=\s*\"([^\"]+)\"[^}]*\}")


def check_custom_styles(journal_id, profile, text, blocks):
    """原稿の custom-style が reference.docx に無く、pandoc が作るスタイルの基が無いか (参考)。

    pandoc は reference.docx に無い custom-style を、段落なら ID `BodyText`、文字なら ID `BodyTextChar` を基に作る
    (pandoc 3.6.4 の出力で確かめた)。pandoc が作る reference.docx にはこの 2 つがあるが、雑誌のテンプレートから作った
    reference.docx (ABE は和文の Word の自動 ID で Body Text が `a0`) には無いので、作られたスタイルは基を失い、Word では
    文書の既定の書式 (本文より小さい字など) で描かれる。キーは要らない — 基のある
    reference.docx (pandoc の既定を雛形にした誌) では必ず黙る。reference.docx が無い (まだ作っていない) ときも黙る。
    """
    ref = profile.get("reference_doc")
    if not (journal_id and ref):
        return []
    path = journal_profile.JOURNALS_DIR / journal_id / ref
    if not path.is_file():
        return []
    import docx_styles
    from lxml import etree
    try:
        root = etree.fromstring(zipfile.ZipFile(path).read("word/styles.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, etree.XMLSyntaxError):
        return []
    wanted = [("paragraph", "BodyText", sorted({b["style"] for b in blocks if b["kind"] == "div" and b["style"]})),
              ("character", "BodyTextChar", sorted(set(_RE_SPAN_STYLE.findall(text))))]
    out = []
    for stype, base, names in wanted:
        if docx_styles.style_by_id(root, base) is not None:
            continue
        missing = []
        for n in names:
            try:
                if docx_styles.style_by_name(root, n, stype) is None:
                    missing.append(n)
            except RuntimeError:        # 同じ名前のスタイルが 2 つ (pandoc はどちらかを使う。無いわけではない)
                pass
        if missing:
            out.append(info(f"custom-style の {', '.join(missing)} は {path} に無い"
                            f"{'段落' if stype == 'paragraph' else '文字'}スタイルです。pandoc はこれを ID {base} の"
                            f"スタイルを基にして作りますが、この reference.docx には ID {base} のスタイルが無いので、"
                            "Word では文書の既定の書式で描かれます (本文と字の大きさが変わるなど)。reference.docx にある"
                            "スタイルの名前を使ってください"))
    return out


# =====================================================================
# 本体
# =====================================================================

_BIB_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
# すべてのフィールドを順に読む (langid / hyphenation / note の名前だけを探すと、
# abstract={… note = …} のように別のフィールドの値の中の「note =」をフィールドと取り違える)
_BIB_FIELD_RE = re.compile(r"([A-Za-z][\w:.-]*)\s*=\s*")
# 本文の引用キー (pandoc の書き方。[@key] / @key / -@key)
_CITE_KEY_RE = re.compile(r"(?<![\w.])-?@([A-Za-z0-9_][\w:.#$%&+?<>~/-]*)")
_BIB_STRING_RE = re.compile(r"@string\s*\{\s*(\w+)\s*=\s*", re.IGNORECASE)
# 和文とみなす値 (check_csl.py の lint と同じ集合)
_LANG_JAPANESE = {"japanese", "ja", "ja-jp"}
# 英語とみなす値 (BibLaTeX / babel の言語名と BCP 47 の短い形)
_LANG_ENGLISH = {"english", "american", "british", "canadian", "australian", "newzealand",
                 "usenglish", "ukenglish", "en", "en-us", "en-gb", "en-ca", "en-au", "en-nz"}


def _bib_value(src, pos):
    """`=` の直後 (pos) から BibTeX の値を 1 つ読み、(値, 終わりの位置, 裸の語か) を返す。

    波括弧は入れ子を数えて外側を外し、内側の波括弧も取り除く (`{{japanese}}` → `japanese`)。
    引用符の値はそのまま、裸の語 (`english` / @string のマクロ名) はそのまま返す。
    """
    while pos < len(src) and src[pos] in " \t\r\n":
        pos += 1
    if pos >= len(src):
        return "", pos, False
    if src[pos] == "{":
        depth, i = 0, pos
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        return src[pos + 1:i].replace("{", "").replace("}", "").strip(), i + 1, False
    if src[pos] == '"':
        j = src.find('"', pos + 1)
        j = len(src) if j < 0 else j
        return src[pos + 1:j].strip(), j + 1, False
    m = re.match(r"[\w-]+", src[pos:])
    return (m.group(0), pos + m.end(), True) if m else ("", pos, False)


def _cited_bib_entries(input_root):
    """`ref.bib` の文献のうち本文で引用しているものを [(型, キー, {フィールド名: 値})] で返す (lint_langid の読み方)。

    `%` で始まる行 (pandoc が読まない) は除いて読む。`@string` のマクロは値に置き換え、`"a" # "b"` の連結も 1 つの値にする。
    `@comment` / `@string` / `@preamble` は文献ではないので返さない。**本文 (`main.md`) で引用している文献だけを返す**
    (pandoc は引用した文献しか文献リストに出さない。メタデータの `nocite` に `@*` があれば全件)。型とフィールド名は小文字。
    ref.bib が無ければ空の list。lint_langid と引けない文献の検査が共用する。
    """
    bib = Path(input_root) / "ref.bib"
    if not bib.is_file():
        return []
    main_md = Path(input_root) / "main.md"
    cited = None                       # None = 全件を見る
    if main_md.is_file():
        mtext = main_md.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"nocite[\s\S]{0,200}?@\*", mtext):
            cited = {k.rstrip(".:;,") for k in _CITE_KEY_RE.findall(mtext)}
    raw = bib.read_text(encoding="utf-8", errors="replace")
    src = "\n".join("" if ln.lstrip().startswith("%") else ln for ln in raw.splitlines())
    macros = {}
    for m in _BIB_STRING_RE.finditer(src):
        val, _, _ = _bib_value(src, m.end())
        macros[m.group(1).lower()] = val
    starts = list(_BIB_ENTRY_RE.finditer(src))
    entries = []
    for i, m in enumerate(starts):
        if m.group(1).lower() in ("comment", "string", "preamble"):
            continue
        if cited is not None and m.group(2) not in cited:
            continue
        end = starts[i + 1].start() if i + 1 < len(starts) else len(src)
        fields = {}
        pos = m.end()
        while True:
            fm = _BIB_FIELD_RE.search(src, pos, end)
            if not fm:
                break
            parts, pos = [], fm.end()
            while True:                     # `"eng" # "lish"` の連結も 1 つの値として読む
                val, pos, bare = _bib_value(src, pos)
                parts.append(macros.get(val.lower(), val) if bare else val)
                nxt = re.match(r"\s*#", src[pos:end])
                if not nxt:
                    break
                pos += nxt.end()
            fields.setdefault(fm.group(1).lower(), "".join(parts))
        entries.append((m.group(1).lower(), m.group(2), fields))
    return entries


def lint_langid(input_root, profile):
    """`ref.bib` に、`note` が無いまま日本語以外の言語を指定した文献が無いか (誌ごと。既定は無効)。

    pandoc は BibTeX の `langid` (と古い別名の `hyphenation`) を CSL の変数 `language` に写す。
    言語を注記する引用様式 (BHI 向けのもの) は `note` があればそれを括弧に入れて出し、無いときは `language` が**あるだけで**
    (値は比べられない) "(in Japanese)" を付ける。したがって誤った出力になるのは、ちょうど
    「`note` が無く、日本語以外の `langid` がある」文献である。書誌管理ソフト (Zotero /
    Better BibTeX など) は英語の文献にも `langid = {english}` を付けて書き出すことが多い。

    直し方は言語で分かれる。英語の文献は `langid` を消す。和文以外の非英語の文献は
    **`langid` を残して** `note = {in German}` のように言語を書く — `langid` を消すと pandoc が
    題を英語とみなしてセンテンスケースに直し、ドイツ語の名詞の大文字などが崩れるため。

    `%` で始まる行 (pandoc が読まない) は除いて読む。`@string` のマクロは値に置き換える。
    `@comment` / `@string` / `@preamble` は文献ではないので数えない。
    **本文 (`main.md`) で引用している文献だけを見る** (pandoc は引用した文献しか文献リストに出さない。
    メタデータの `nocite` に `@*` があれば全件を見る。書誌管理ソフトから書誌全体を書き出すと、
    引用していない文献の指摘が積み上がって本当の指摘が埋もれるため)。値は波括弧を外し、大文字小文字を区別せずに比べる。
    """
    if not (profile.get("lint") or {}).get("langid_japanese_only"):
        return []
    english, other = [], []
    for _etype, key, fields in _cited_bib_entries(input_root):
        # 引用符の値は _bib_value が波括弧を残すので外す ("{E}nglish" → English)
        lang = (fields.get("langid") or fields.get("hyphenation") or "").replace("{", "").replace("}", "").strip()
        if not lang or lang.lower() in _LANG_JAPANESE or fields.get("note"):
            continue
        field = "langid" if fields.get("langid") else "hyphenation"
        (english if lang.lower() in _LANG_ENGLISH else other).append(
            f"{key} ({field} = {{{lang}}})")
    findings = []
    if english:
        findings.append(must(
            f"ref.bib に langid (または hyphenation) が英語の文献が {len(english)} 件あります: {', '.join(english)}。"
            "この誌の引用様式は note の無い文献では langid があるだけで言語によらず \"(in Japanese)\" を付けます。"
            "英語の文献からは langid を消してください"))
    if other:
        findings.append(must(
            f"ref.bib に、note の無いまま和文以外の言語を指定した文献が {len(other)} 件あります: {', '.join(other)}。"
            "この誌の引用様式は note が無いと \"(in Japanese)\" を付けます。"
            "langid は残したまま (消すと題がセンテンスケースに直されます) note = {in German} のように言語を書いてください"))
    return findings


def validate(input_root, profile, article_type=None, journal_id=None, estimate=None):
    """limits / lint と照合し、指摘 (list[Finding]) を返す。

    estimate に list を渡すと、画面に出す概算の行 (語数・文献数・図表点数・除外した語数の内訳) を前後の空白を
    除いて足していく (package.py が SUBMISSION.md の「規定チェック」節に転記する)。

    profile は生 dict / journal_profile.resolve() 済みのどちらでもよい (ここで解決する。
    解決済みなら冪等ガードで素通り)。article_type を渡すと記事種別で limits / abstract を
    上書きして検証する。journal_id を渡すと reference.docx の
    実体裁との突合も行う (省略時は体裁を見ない)。

    戻り値は list[Finding] (要修正 / 参考の区分表示のため)。
    表示は print_findings() を使う。
    """
    profile = journal_profile.resolve(profile or {}, article_type)
    findings = []
    if journal_id:
        findings.extend(check_reference_layout(journal_id, profile))
    text = _read_main(input_root)
    if text is None:
        return findings + [must(f"{Path(input_root) / 'main.md'} が無く検証できません")]
    text = _strip_noise(text)
    blocks = scan_blocks(text)
    floats = analyze_floats(blocks)

    limits = (profile.get("limits") or {})
    abstract_cfg = (profile.get("abstract") or {})

    # --- 概算 (語数・文献数・図表点数) ---
    # 略語一覧を本文語数から除くかは誌のプロファイル次第
    # (declarations.abbreviations_section を持つ誌だけ除く。BHI のプロファイルは持つ)
    drop_abbr = bool((profile.get("declarations") or {}).get("abbreviations_section"))
    # 対応不明の凡例 (直前に図表が無い = 配置規則違反) は最終パッケージの
    # 集約から漏れて提出物の本文に残るので、本文語数にも算入する
    orphan_legends = [leg["inner"] for leg in floats["legends"] if leg["target"] is None]
    body = count_body_words(text, blocks, drop_abbreviations=drop_abbr, keep_legends=orphan_legends)
    # 除いた Abbreviations 節の語数 (除外は見積もりを甘くする側なので、凡例と同じく足し戻せるように出す)
    abbr_words = (count_body_words(text, blocks, drop_abbreviations=False, keep_legends=orphan_legends) - body
                  if drop_abbr else 0)
    abs_words = count_abstract_words(blocks)
    # 空白区切りの語数も出し、食い違えば両方を表示して上限は大きいほうで判定する
    abs_words_ws = count_abstract_words_ws(blocks)
    abs_judge = max(abs_words, abs_words_ws) if abs_words is not None else None
    refs = count_references(text)
    leg_fig, leg_tbl, leg_other = count_legend_words(floats)
    n_fig = len([f for f in floats["figures"] if not f["in_textbox"]])
    n_tbl = len([t for t in floats["tables"] if not t["in_textbox"]])

    def _say(line):
        print(line)
        if estimate is not None:
            estimate.append(line.strip())

    abs_shown = "—" if abs_words is None else (
        f"{abs_words}" if abs_words == abs_words_ws else f"{abs_words} (空白区切りでは {abs_words_ws})")
    _say(f"  概算: 本文 {body} 語 / 抄録 {abs_shown} 語"
         f" / 文献 {refs} 件 / 図 {n_fig} 点・表 {n_tbl} 点")
    if abbr_words > 0:
        _say(f"        本文語数から除外した Abbreviations 節: {abbr_words} 語"
             " (抄録と合わせて、編集室の数え方が違えば足して見積もる)")
    # 箱の中の図表は上の点数に入っていない。**入れなかったことを必ず言う**。
    # 上限の検査が空振りしていることに気づけるのはこの 1 行だけである (誌が上限を定めて
    # いなければ lint も出ないため)。
    box_figs, box_tbls = count_textbox_floats(floats)
    if box_figs or box_tbls:
        _say(f"        うち .textbox 内 図 {len(box_figs)} 点・表 {len(box_tbls)} 点は"
             "上限の対象外 (本文の流れの外にあり、末尾移設の対象からも外れる)")
    # 除外した凡例の内訳を必ず出す (除外は費用の見積もりを甘くする側に効くため、
    # 編集室の数え方が違ったときに足し戻せるようにする)
    if leg_fig or leg_tbl:
        parts = [f"図の凡例 {leg_fig}"] if leg_fig else []
        if leg_tbl:
            parts.append(f"表の凡例 {leg_tbl}")
        _say(f"        本文語数から除外した凡例: {' / '.join(parts)} 語 "
             f"(合計 {leg_fig + leg_tbl} 語)")
    if leg_other:
        _say(f"        対応不明の凡例 {leg_other} 語は提出物の本文に残るため本文語数に"
             "算入した (配置規則違反として別途指摘する)")

    # --- 上限との照合 ---
    wc = limits.get("word_count")
    if wc and body > int(wc):
        findings.append(must(f"本文語数 {body} が上限 {wc} を超過 (概算)"))

    aw = limits.get("abstract_words")
    if aw and abs_judge is not None and abs_judge > int(aw):
        # 2 つの数え方の大きいほうで判定する (英数字を含むトークンの数だけだと統計の文で少なく出る)
        how = "" if abs_words == abs_words_ws else (
            f" (英数字を含む語 {abs_words} / 空白区切り {abs_words_ws} の大きいほう)")
        findings.append(must(f"抄録語数 {abs_judge} が上限 {aw} を超過 (概算){how}"))

    rl = limits.get("references")
    if rl and refs > int(rl):
        findings.append(must(f"文献数 {refs} が上限 {rl} を超過"))

    # --- 構造化抄録の要求と原稿の体裁の食い違い ---
    if abstract_cfg.get("structured") and abs_words is not None:
        # 全文ではなく抄録 Div の中身だけでラベルを判定する
        # (本文の太字 '**Methods**' に釣られて見逃さないため)。
        # 誌が abstract.labels を定義していればそれを使う (BHI は Objective/Methods/
        # Results/Conclusion)。未定義なら既定ラベル。
        # 候補ラベルを縦棒でつないだ 1 本の正規表現を search する
        # だけでは、**4 つのうち 1 つ当たれば合格**になる。BHI (Objective/Methods/Results/
        # Conclusion) は既定ラベル (Background/Methods/Results/Conclusions) と Methods・Results
        # を共有し、大文字小文字を無視するため '**Conclusions:**' が 'Conclusion' にも当たる。
        # 結果として「他誌の癖のまま Background で書いた抄録」が BHI として無警告で通ってしまう
        # (data/dummy で実測)。誌が abstract.labels を明示している場合は全ラベルの存在を個別に
        # 確かめ、欠けたものを名指しで警告する。labels 未定義の誌は既定ラベルのいずれか 1 つで合格。
        abs_inner = _abstract_inner(blocks) or ""
        labels_cfg = abstract_cfg.get("labels")
        if labels_cfg:
            # 誌指定のラベルは語として一致させる (末尾に (?![A-Za-z]) を付ける)。前方一致のままだと
            # BHI の 'Conclusion' に既定ラベルの '**Conclusions:**' が当たってしまい、単複の取り違えを
            # 見逃す。既定ラベル側 (else 節) は前方一致のまま (labels 未定義の誌は単複を区別しない)。
            missing_labels = [str(lb) for lb in labels_cfg
                              if not re.search(rf"\*\*\s*{re.escape(str(lb))}(?![A-Za-z])",
                                               abs_inner, re.IGNORECASE)]
            if missing_labels:
                findings.append(must(
                    f"この雑誌は構造化抄録 ({'/'.join(str(lb) for lb in labels_cfg)}) を要求しますが、"
                    f"抄録に見出しラベル {'/'.join(missing_labels)} が見当たりません"
                    " (誌指定のラベルは全て必要です)"))
        else:
            # labels 未定義: 既定ラベルのいずれか 1 つでも見つかれば合格
            default_labels = ["Background", "Methods", "Results", "Conclusions"]
            pat = "|".join(re.escape(lb) for lb in default_labels)
            if not re.search(rf"\*\*\s*({pat})", abs_inner, re.IGNORECASE):
                findings.append(must(f"この雑誌は構造化抄録 ({'/'.join(default_labels)}) を"
                                     "要求しますが、抄録に見出しラベルが見当たりません"))

    # --- lint 群 (すべて profile 駆動。キーが無い雑誌では発火しない) ---
    # 走査済みの blocks / floats を渡す (走査は 1 回だけ)。各 lint が scan_blocks を呼び直すと、
    # 性能もさることながら、この層に状態 (採番など) を持たせたときに静かに壊れる。
    findings.extend(lint_title(blocks, profile))
    findings.extend(lint_keywords(blocks, profile))
    findings.extend(lint_abstract_citations(blocks, profile))
    findings.extend(lint_declarations(blocks, profile))
    findings.extend(lint_abbreviations(text, blocks, profile))
    findings.extend(lint_forbidden_chars(text, profile))
    findings.extend(lint_thousands_separator(text, profile))
    findings.extend(lint_placeholders(text, profile, input_root))
    findings.extend(lint_legend_placement(blocks, floats, profile))
    findings.extend(lint_float_counts(floats, profile))
    findings.extend(lint_references_last(blocks, profile))
    findings.extend(lint_corresponding(blocks, profile))
    findings.extend(lint_units(text, profile))
    findings.extend(lint_device_notation(text, profile))
    findings.extend(lint_langid(input_root, profile))
    # 表題ページ・節・定型の記述の検査 (どれもキーの無い誌では発火しない。上の検査の出力の順を変えないよう後ろに並べる)
    findings.extend(lint_front_matter_divs(blocks, profile))
    findings.extend(lint_abstract_shape(blocks, profile))
    findings.extend(lint_keywords_not_in_title(blocks, profile))
    findings.extend(lint_running_title(blocks, profile))
    findings.extend(lint_author_surnames(blocks, profile))
    findings.extend(lint_affiliation_labels(blocks, profile))
    findings.extend(lint_required_sections(text, blocks, profile))
    findings.extend(lint_float_titles(blocks, profile))
    findings.extend(lint_table_caption_attrs(blocks, profile))
    findings.extend(lint_caption_case(floats, profile))
    findings.extend(lint_abbreviation_definitions(blocks, profile))
    findings.extend(lint_coi(text, blocks, profile))
    findings.extend(lint_ethics(text, blocks, profile))
    findings.extend(lint_ai_disclosure(text, blocks, profile))
    findings.extend(lint_funding(text, blocks, profile))
    findings.extend(lint_uncitable_references(input_root, profile))
    findings.extend(lint_supplementary(input_root, profile))
    if journal_id:
        findings.extend(check_custom_styles(journal_id, profile, text, blocks))
    return findings


def print_findings(findings, indent="  "):
    """指摘を「規定違反の可能性 (要修正)」と「参考情報」に分けて表示する。"""
    if not findings:
        print(f"{indent}限度内 (または limits 未設定)")
        return
    for level, title in ((LEVEL_MUST, "規定違反の可能性 (要修正)"), (LEVEL_INFO, "参考情報")):
        rows = [f for f in findings if f.level == level]
        if not rows:
            continue
        print(f"{indent}-- {title} ({len(rows)} 件) --")
        for f in rows:
            print(f"{indent}  [{f.level}] {finding_text(f)}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input-root", required=True)
    p.add_argument("--journal", default="_default")
    p.add_argument("--article-type", default=None,
                   help="記事種別 (article_types を持つ誌のみ。limits/abstract を種別値で解決)")
    args = p.parse_args(argv)
    profile = journal_profile.load(args.journal)
    print(f"== validate: {args.input_root} vs journal={args.journal}"
          + (f" article_type={args.article_type}" if args.article_type else "") + " ==")
    findings = validate(args.input_root, profile, args.article_type, journal_id=args.journal)
    print_findings(findings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
