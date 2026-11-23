#!/usr/bin/env python3
"""ast_diff.py — 構造保持型 二層 AST 差分エンジン (Step 03 diff の中核)。

docs/architecture.md §2.3 / docs/design-fullarea-diff.md。pandiff は使わない。旧版・新版の pandoc AST
(panflute Doc) を突き合わせ、構造 (custom-style Div / native Table / .textbox Div /
raw openxml / Figure) を一切壊さず、変更語句だけを Span (.diff-add / .diff-del) で包んだ
1 つのマージ Doc を返す。色付けは色実体ではなく Span のクラスのみ付与し、後段の
color-diff.lua が custom-style="DiffAdd"/"DiffDel" 文字スタイルへ写像する。

二層アルゴリズム:
  レベル1   : ブロック列を difflib (= LCS 系) で整列。`equal` は新版を温存。整列は小文字で取るので、`equal` の対は大文字小文字を
              区別してもう一度比べ、違えば対の差分に回す (そうしないと大文字小文字だけの変更が差分に出ない)。
              表の行・リストの項目の整列も同じ。語の差分 (レベル2) と式の比較は大文字小文字を区別する
  レベル1.5 : `replace` 区間で旧/新ブロックを類似度 (しきい値 0.5) ・同種別で対応付ける
              (層1→層2 の橋渡し。これが無いと 1 語修正の段落が段落まるごと赤青になる)。
  レベル2   : 対応した葉ブロック内のインラインを語単位で差分し変更語を Span で包む。
              Cite / 相互参照 / 数式 / Image は不透明トークンとして要素のまま温存する。
  コンテナ  : Div / Table / リスト / Figure / Caption は型のついた木をたどって再帰する。

図表と式の番号 (pandoc-crossref のラベル) を差分で壊さないための扱い:
  - 表の題の末尾のラベル `{#tbl:x}` は差分の Span の外に置く (Span の中にあると pandoc-crossref が読めず、
    足した表の題が `{#tbl:x}` の文字のまま出て参照が `¿tbl:x?` になる)。消した表のラベルは外す (番号を使わない)
  - 番号つきの式 `$$ … $$ {#eq:x}` は差分の前に `[$$ … $$]{#eq:x}` (Span。pandoc-crossref は同じに扱い docx も同一) にし、
    式とラベルを 1 つの不透明トークンにする。式だけの段落を書き換えたら、旧の式 (ラベルなし・削除の色) と新の式 (ラベルつき・追加の色) の
    2 段落にする (1 段落に式が 2 つ並ぶと番号も式番号の右寄せも掛からない)
  - 旧版と新版で同じ図表・式のラベルが書き換わっていたら、旧版のラベルと参照を新版の名前に直してから差分を取る (ラベルの付け替えは
    番号に現れないので、色を付けない)。同じとみなすのは、表は題が似て中身 (セル) も似ているもの、図は画像が同じか題が同じもの、
    式は式が同じもの (題の語の類似度だけで判定すると、題の似た別の図表を同一視する) と、ブロックの整列で
    対になった表 (中身が似ている)・図 (画像が同じか題が同じ)・式 (式の記号が似ている) (これを付け替えとみなさないと、
    題も書き換えた図表で、変えていない文の参照まで `¿tbl:old?` になる)
  - 画像が同じ図は、題を書き換えても整列で対にする (題の差分になる)
  - 段抜きの `::: wide` の Div は、旧版の Div の付け方を新版に合わせてから差分を取る (合わせないと、既存の表を囲んだだけで
    表がまるごと削除 + 追加になる)
  - 消したブロックの式のラベルは、脚注などの中のものも外す (外さないと、番号つきの式を含む脚注を書き換えたとき
    pandoc-crossref が Duplicate label で止まる)
  - 足した図の画像は Span で包まない (包むと pandoc が図を表の形で組む)
  - 表のセルと題 (キャプション) は、旧と新が 1 段落ずつなら 1 つの段落の中で差分を出す (似ていれば語の差分、似ていなければ
    旧の全体 (削除) + 新の全体 (追加))。段落の差分に任せると、セルの 1.1 → 1.2 が「追加の段落 → 削除の段落」の 2 段落に割れる
  - 式とリンク (図表・式の参照) の色は pandoc が付けないので、color-diff.lua が式かリンクを含む差分 Span に目印 (ブックマーク) を付け、
    diff_docx.py が範囲の中の式の文字とリンクの文字に差分の書式を付ける

このモジュールは I/O を持たず純粋に Doc → Doc を行う (テスト容易性のため)。CLI は
2 つの pandoc JSON を読み、マージ JSON を stdout に書く。実運用は diff_docx.py が
diff_documents() を直接呼ぶ。
"""

import bisect
import copy
import difflib
import re
import sys

import panflute as pf

# レベル1.5 で「同一ブロックの改稿」とみなす類似度しきい値 (docs/architecture.md §2.3 / docs/design-fullarea-diff.md §3 の「レベル1.5」)
SIMILARITY_THRESHOLD = 0.5

# 差分 span のクラス名 (color-diff.lua がこれを custom-style 文字スタイルへ写像する)
ADD = "diff-add"
DEL = "diff-del"

# 語差分でインラインをまたぐ「空白」とみなすトークン
_WS_TAGS = {"Space", "SoftBreak", "LineBreak"}

# pandoc-crossref のラベルの属性 (表の題の末尾・式の後ろの `{#tbl:x}` / `{#eq:x}`)。pandoc は 1 つの Str にする
_LABEL_STR = re.compile(r"^\{#([^\s{}]+)\}$")
# 式とラベルの間に置ける空白 (pandoc-crossref は空白なし・Space・SoftBreak のどれでも式のラベルとして読む。コンテナで確かめた)
_EQ_GAP_TAGS = {"Space", "SoftBreak"}


def _copy(el):
    """el とその下だけを深く複製する (複製の親は None。置いた先のコンテナが親を付け直す)。

    panflute の要素は親 (.parent) を持つので、素の copy.deepcopy は親をたどって文書全体まで複製する。
    語の差分は 1 語ごとに複製するので、それでは文書の大きさ × 語数の手間になり、動作例の 1 語の書き換えでも
    1 分を超える。親への参照を memo で None に差し替えて、上へたどらないようにする。差分のコードは複製の親を読まない。"""
    parent = getattr(el, "parent", None)
    return copy.deepcopy(el) if parent is None else copy.deepcopy(el, {id(parent): None})


# =====================================================================
# 正規化・署名・類似度
# =====================================================================

def _normalize(text):
    """署名・類似度比較用にテキストを正規化する (小文字化・空白畳み込み)。

    小文字にするのは整列 (どのブロックとどのブロックを対にするか) と類似度のためだけで、「同じか」の最終判定には使わない
    (整列で同じと判定した対をそのまま新版で出すと、大文字小文字だけの変更 (題・姓の大文字化・
    式の記号 T → t・単位の mS → ms) が差分 docx に出ない)。同じかどうかは _exact で比べる。"""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _exact(text):
    """「同じか」の判定に使う正規化 (空白の畳み込みだけ。大文字小文字は区別する)。"""
    return re.sub(r"\s+", " ", (text or "").strip())


def _type_key(block):
    """ブロックの「種別キー」。同種別判定 (レベル1.5 の対応付け制約) に使う。

    Div は custom-style とクラスを、Header はレベルを種別に含める。これにより
    Title Div と Author Div、見出しレベル違いが誤って対応付けられない。
    """
    t = block.tag
    if t == "Div":
        cs = (block.attributes or {}).get("custom-style")
        return f"Div:{cs}:{','.join(block.classes)}"
    if t == "Header":
        return f"Header:{block.level}"
    return t


def _full_sig(block):
    """レベル1 の LCS 整列に使う署名 (種別キー + 正規化テキスト)。"""
    return _type_key(block) + "\x00" + _normalize(pf.stringify(block))


def _exact_sig(block):
    """整列で「同じ」と判定した対を、大文字小文字を区別してもう一度比べるための署名。"""
    return _type_key(block) + "\x00" + _exact(pf.stringify(block))


def _word_tokens(el):
    """要素から比較用の語トークンを集める。`Str` を語に割って集めるので、表のセルや
    リスト項目が「区切り無しの 1 トークン」に潰れない。

    `pf.stringify` はセルを区切り無しで連結する (例: `| A | B |/| 1 | 2 |` → `'AB12'`)。
    これを `.split()` すると 1 トークンになり、`_similarity` が単語・数値セルの表で常に 0 を返す。
    その結果、変更された表がペアにならず表全体が「旧=全赤/新=全青」に二重化する。"""
    words = []

    def _collect(e, doc=None):
        if isinstance(e, pf.Str):
            words.extend(_normalize(e.text).split())
        return e

    el.walk(_collect)
    return words


def _similarity(a, b):
    """2 ブロックのテキスト類似度 (語列の difflib 比)。0..1。

    語列は `_word_tokens` で集める (stringify 連結ではセル境界が消えるため)。"""
    ta = _word_tokens(a)
    tb = _word_tokens(b)
    if not ta and not tb:
        return 1.0
    return difflib.SequenceMatcher(None, ta, tb, autojunk=False).ratio()


# =====================================================================
# 図表と式のラベル (pandoc-crossref)
# =====================================================================

def _is_display_math(el):
    return el.tag == "Math" and el.format == "DisplayMath"


def _is_eq_span(el):
    """`[$$ … $$]{#eq:x}` の形 (識別子が eq: の Span で、中身が別行立ての式 1 つだけ)。"""
    return (el.tag == "Span" and (el.identifier or "").startswith("eq:")
            and len(el.content) == 1 and _is_display_math(el.content[0]))


def _wrap_equation_labels(doc):
    """`$$ … $$ {#eq:x}` (Math + 空白 + Str "{#eq:x}") を `[$$ … $$]{#eq:x}` (Span) に書き換える (doc を直接変える)。

    pandoc-crossref は 2 つの書き方を同じに扱い、docx の出力も同一になる (コンテナで確かめた)。差分では式とラベルが
    1 つの不透明トークンになり、式を書き換えてもラベルが式から離れない (離れると番号が付かず参照が `¿eq:x?` になる)。
    """
    def action(el, _doc):
        if el.tag not in ("Para", "Plain"):
            return None
        inl = list(el.content)
        out, i, changed = [], 0, False
        while i < len(inl):
            e = inl[i]
            if _is_display_math(e):
                j = i + 1
                while j < len(inl) and inl[j].tag in _EQ_GAP_TAGS:
                    j += 1
                if j < len(inl) and inl[j].tag == "Str":
                    m = _LABEL_STR.match(inl[j].text)
                    if m and m.group(1).startswith("eq:"):
                        out.append(pf.Span(e, identifier=m.group(1)))
                        i, changed = j + 1, True
                        continue
            out.append(e)
            i += 1
        if changed:
            el.content = out
        return None

    doc.walk(action)


def _unlabel(inlines):
    """消した側のインライン列から式のラベルを外す (`[$$ … $$]{#eq:x}` → `$$ … $$`)。消した式に番号を使わせない。

    最上位の式は Span を外して式だけにし、脚注 (Note)・強調 (Emph) などの中の式は Span の識別子を外す (識別子の無い Span は
    pandoc-crossref が読まず、docx にも何も出ない)。中まで見るのは、最上位だけを見ると、番号つきの式を含む脚注を
    書き換えたとき、消した脚注と足した脚注に同じラベルが残り、pandoc-crossref が Duplicate label で止まるため。
    インラインは書き換える (呼び出し側は写しを渡す)。
    """
    def _clear(el, _doc=None):
        if _is_eq_span(el):
            el.identifier = ""
        return None

    out = []
    for e in inlines:
        if _is_eq_span(e):
            out.extend(e.content)
        else:
            e.walk(_clear)
            out.append(e)
    return out


def _split_caption_label(caption):
    """表の題 (Caption) の末尾のラベル `{#tbl:x}` を切り離す。

    戻り値: (ラベルを除いた題の写し, ラベルの id か None, ラベルのインライン列 (前の空白を含む))。
    caption は変えない。題の最後の段落の末尾 (空白を除く) が 1 つの Str の `{#…}` のときだけ切り離す。
    """
    if caption is None:
        return None, None, []
    cap = _copy(caption)
    if not cap.content or cap.content[-1].tag not in ("Plain", "Para"):
        return cap, None, []
    last = cap.content[-1]
    inl = list(last.content)
    k = len(inl) - 1
    while k >= 0 and _is_ws(inl[k]):
        k -= 1
    if k < 0 or inl[k].tag != "Str":
        return cap, None, []
    m = _LABEL_STR.match(inl[k].text)
    if not m:
        return cap, None, []
    j = k
    while j > 0 and _is_ws(inl[j - 1]):
        j -= 1
    label_inlines = inl[j:k + 1]
    last.content = inl[:j]
    return cap, m.group(1), label_inlines


def _attach_label(caption, label_inlines):
    """_split_caption_label で切り離したラベルを、差分を取った題の最後の段落の末尾へ (差分の Span の外に) 戻す。"""
    if not label_inlines:
        return caption
    label_inlines = [_copy(e) for e in label_inlines]
    if caption.content and caption.content[-1].tag in ("Plain", "Para"):
        last = caption.content[-1]
        if not last.content:
            label_inlines = [e for e in label_inlines if not _is_ws(e)]
        last.content.extend(label_inlines)
    else:
        caption.content.append(pf.Plain(*[e for e in label_inlines if not _is_ws(e)]))
    return caption


def _caption_text(caption):
    return _normalize(" ".join(pf.stringify(b) for b in caption.content)) if caption is not None else ""


def _float_label(el):
    """図表と式の要素のラベル (("tbl" / "fig" / "eq", ラベル)) か None。表は題の末尾の {#tbl:x}、図は識別子、式は `[$$ … $$]{#eq:x}`。"""
    if el.tag == "Table" and el.caption is not None:
        _cap, lbl, _ = _split_caption_label(el.caption)
        if lbl and lbl.startswith("tbl:"):
            return "tbl", lbl
    elif el.tag == "Figure" and (el.identifier or "").startswith("fig:"):
        return "fig", el.identifier
    elif _is_eq_span(el):
        return "eq", el.identifier
    return None


def _float_labels(doc):
    """{"tbl" / "fig" / "eq": {ラベル: 要素}} (最初に出てきたもの)。"""
    out = {"tbl": {}, "fig": {}, "eq": {}}

    def action(el, _doc):
        kl = _float_label(el)
        if kl is not None:
            out[kl[0]].setdefault(kl[1], el)
        return None

    doc.walk(action)
    return out


def _ratio(a, b):
    """2 つの語列の difflib 比 (両方空なら 1.0)。"""
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _float_caption_words(el):
    """表 (ラベルを除く) と図の題の語 (小文字。付け替えの判定用)。"""
    cap = _split_caption_label(el.caption)[0] if el.tag == "Table" else el.caption
    return _caption_text(cap).split()


def _table_cell_words(tbl):
    """表の見出し・本体・脚のセルの語 (題を除く)。"""
    words = []
    for sec in [tbl.head, *tbl.content, tbl.foot]:
        if sec is not None:
            words.extend(_word_tokens(sec))
    return words


def _image_targets(el):
    found = []

    def _collect(e, _doc=None):
        if e.tag == "Image":
            found.append(e.url)
        return None

    el.walk(_collect)
    return found


_TEX_TOKEN = re.compile(r"\\[A-Za-z]+|\\.|\S")


def _same_float(kind, o, n, cap_sim):
    """旧版の図表・式 o と新版の n を「同じ図表・式を書き換えたもの」とみなせるか (ラベルの付け替えの判定)。

    - 表: セル (題を除く) の語の類似度がしきい値以上。題が似ていても中身の違う表は別の表とみなす
    - 図: 画像 (のパス) が同じか、題が同じ (大文字小文字と空白を除いて)。題が似ていても画像の違う図は別の図とみなす
    - 式: 式の TeX が同じ (大文字小文字を区別する)
    題の語の類似度 0.5 以上だけで判定すると、"Mean score for each condition." と "Number of trials for each condition."、
    "Overview of the apparatus." と "Overview of the results." のような別の図表を同じとみなし、参照の行き先が別の表に変わっても
    「変更なし」の黒で出してしまう。cap_sim は題の語の類似度 (表と図)。
    """
    if kind == "tbl":
        return _ratio(_table_cell_words(o), _table_cell_words(n)) >= SIMILARITY_THRESHOLD
    if kind == "fig":
        imgs = _image_targets(o)
        return (bool(imgs) and imgs == _image_targets(n)) or (cap_sim >= 1.0 and bool(_float_caption_words(o)))
    return _exact(o.content[0].text) == _exact(n.content[0].text)


def _label_renames(old_doc, new_doc):
    """旧版にだけあるラベル → 新版にだけあるラベル の対応 (付け替えとみなすもの)。

    表は題の語の類似度がしきい値以上で中身 (セル) も似ているもの、図は画像が同じか題が同じもの、式は式の TeX が同じものを
    (_same_float。題が似ていても中身と画像が違えば対応づけない)、類似度の高い順に 1 対 1 で対応づける。
    式を書き換えてラベルも変えた場合はここでは対応づけない (ブロックの整列で対になったときだけ _paired_renames が対応づける)。
    """
    old_l, new_l = _float_labels(old_doc), _float_labels(new_doc)
    renames = {}
    for kind in ("tbl", "fig", "eq"):
        o_only = {k: v for k, v in old_l[kind].items() if k not in new_l[kind]}
        n_only = {k: v for k, v in new_l[kind].items() if k not in old_l[kind]}
        cands = []
        for ok_, ov in o_only.items():
            for nk, nv in n_only.items():
                if kind == "eq":
                    s = 1.0
                else:
                    s = _ratio(_float_caption_words(ov), _float_caption_words(nv))
                    if kind == "tbl" and s < SIMILARITY_THRESHOLD:
                        continue
                if _same_float(kind, ov, nv, s):
                    if kind == "tbl":
                        s += _ratio(_table_cell_words(ov), _table_cell_words(nv))   # 題が同じなら中身の近いほうを先に
                    cands.append((s, ok_, nk))
        cands.sort(key=lambda x: (-x[0], x[1], x[2]))
        used_o, used_n = set(), set()
        for _s, ok_, nk in cands:
            if ok_ in used_o or nk in used_n:
                continue
            renames[ok_] = nk
            used_o.add(ok_)
            used_n.add(nk)
    return renames


def _label_conflict(ob, nb):
    """ラベルの違う表どうし・図どうしで、同じ図表を書き換えたものとはみなせない (_same_float が偽) か。

    整列でこの 2 つを対にしない (削除 + 追加にする)。対にすると、題の差分で同じ図表を書き換えたように見せながら付け替えは
    しない (参照は旧のラベルのまま) ことになり、題の似た別の図表 (画像の違う図など) が「題だけを直した図」に見えてしまう。
    ラベルが同じか、どちらかにラベルが無ければ類似度だけで対にする。
    """
    ko, kn = _float_label(ob), _float_label(nb)
    if ko is None or kn is None or ko[0] != kn[0] or ko[1] == kn[1]:
        return False
    return not _same_float(ko[0], ob, nb, _ratio(_float_caption_words(ob), _float_caption_words(nb)))


# ブロックの整列で対になった図表と式の (旧, 新) を集める入れ物 (_paired_renames の 1 回目の差分の間だけリスト)
_PAIR_LOG = None


def _log_pair(old, new):
    if _PAIR_LOG is not None:
        _PAIR_LOG.append((old, new))


def _paired_renames(old_doc, new_doc):
    """ブロックの整列で対になった図表と式の、旧版にだけあるラベル → 新版にだけあるラベル の対応。

    題も書き換えた図表 (題の類似度では _label_renames が対応づけない) でも、整列で対になれば同じ図表を書き換えたものなので、
    旧版のラベルと参照を新版の名前に直す (直さないと、変えていない文の参照まで `~~Table ¿tbl:old?~~ Table 1` になる)。
    1 回差分を取って対を集める (_PAIR_LOG)。対になっても別の図表・式とみなすもの (_same_float の表と図。式は TeX の記号の類似度が
    しきい値未満) は対応づけない。old_doc と new_doc は変えない。
    """
    global _PAIR_LOG
    _PAIR_LOG = []
    try:
        _diff_blocks(list(old_doc.content), list(new_doc.content))
        pairs = _PAIR_LOG
    finally:
        _PAIR_LOG = None
    old_l, new_l = _float_labels(old_doc), _float_labels(new_doc)
    renames, used_n = {}, set()
    for o, n in pairs:
        if o.tag in ("Para", "Plain"):
            o = next(e for e in o.content if _is_eq_span(e) or _is_display_math(e))
            n = next(e for e in n.content if _is_eq_span(e) or _is_display_math(e))
        ko, kn = _float_label(o), _float_label(n)
        if ko is None or kn is None or ko[0] != kn[0]:
            continue
        kind, ol, nl = ko[0], ko[1], kn[1]
        if ol == nl or ol in new_l[kind] or nl in old_l[kind] or ol in renames or nl in used_n:
            continue
        if kind == "eq":
            same = _ratio(_TEX_TOKEN.findall(o.content[0].text),
                          _TEX_TOKEN.findall(n.content[0].text)) >= SIMILARITY_THRESHOLD
        else:
            same = _same_float(kind, o, n, _ratio(_float_caption_words(o), _float_caption_words(n)))
        if same:
            renames[ol] = nl
            used_n.add(nl)
    return renames


def _apply_label_renames(doc, renames):
    """doc (旧版) のラベルの定義と参照 (Cite) を renames で書き換える (doc を直接変える)。"""
    if not renames:
        return
    key_chars = r"[\w:.#$%&+?<>~/-]"
    pats = [(re.compile("@" + re.escape(o) + f"(?!{key_chars})"), "@" + n) for o, n in renames.items()]

    def action(el, _doc):
        if el.tag == "Cite":
            hit = False
            for c in el.citations:
                if c.id in renames:
                    c.id = renames[c.id]
                    hit = True
            if hit:
                for s in _iter_str(el):
                    for pat, rep in pats:
                        s.text = pat.sub(rep, s.text)
        elif el.tag == "Table" and el.caption is not None:
            _cap, lbl, _inl = _split_caption_label(el.caption)
            if lbl in renames:
                last = el.caption.content[-1]
                for e in last.content:
                    if e.tag == "Str" and e.text == "{#" + lbl + "}":
                        e.text = "{#" + renames[lbl] + "}"
        elif el.tag == "Figure" and el.identifier in renames:
            el.identifier = renames[el.identifier]
        elif _is_eq_span(el) and el.identifier in renames:
            el.identifier = renames[el.identifier]
        return None

    doc.walk(action)


def _iter_str(el):
    found = []

    def _collect(e, _doc=None):
        if isinstance(e, pf.Str):
            found.append(e)
        return None

    el.walk(_collect)
    return found


def _equation_only(block):
    """段落 (Para / Plain) の中身が、前後の空白を除いて別行立ての式 1 つ (ラベルつきでも) だけか。"""
    if block.tag not in ("Para", "Plain"):
        return False
    core = [e for e in block.content if not _is_ws(e)]
    return len(core) == 1 and (_is_display_math(core[0]) or _is_eq_span(core[0]))


def _image_only(block):
    """段落 (Para / Plain) の中身が画像 (と空白) だけか。足した図の画像を Span で包まないために使う。"""
    return (block.tag in ("Para", "Plain") and bool(block.content)
            and all(e.tag == "Image" or _is_ws(e) for e in block.content))


# =====================================================================
# レベル2: インライン語差分
# =====================================================================

def _tokenize_inlines(inlines):
    """インライン列を (key, element) トークン列へ展開する。

    pandoc は地の文を Str (語) と Space に既に分割しているので、要素単位のトークン化で
    語単位差分になる。Emph/Strong/Cite/Math/Link/Image/Code 等の複合・不透明インラインは
    1 つの不透明トークンとして扱う (要素内部だけの変更は要素まるごとの置換になる。docs/design-fullarea-diff.md §6)。
    """
    tokens = []
    for el in inlines:
        if el.tag == "Str":
            tokens.append((el.text, el))
        elif el.tag in _WS_TAGS:
            tokens.append((" ", el))  # 改行も空白扱いで一致させる (描画は元要素を温存)
        else:
            # 不透明トークン: 種別 + 文字列化で同一物だけが一致する
            tokens.append(("\x00" + el.tag + "\x00" + pf.stringify(el), el))
    return tokens


def _is_ws(el):
    return el.tag in _WS_TAGS


def _emit_group(elements, cls, out):
    """変更されたインライン群を Span(cls) で包んで out へ追加する。

    両端の空白トークンは Span の外へ出し、色付き run が無意味な空白で広がるのを防ぐ。
    語が 1 つも無い (空白のみ) 群は包まずそのまま出す。
    """
    lead, core, trail = [], list(elements), []
    if cls == DEL:
        core = _unlabel(core)   # 消した式に番号を使わせない
    while core and _is_ws(core[0]):
        lead.append(core.pop(0))
    while core and _is_ws(core[-1]):
        trail.insert(0, core.pop())
    out.extend(lead)
    if core:
        out.append(pf.Span(*core, classes=[cls]))
    out.extend(trail)


def _inline_diff(old_inlines, new_inlines):
    """対応した葉ブロックのインラインを語単位差分し、変更語を Span で包んだ列を返す。"""
    old_t = _tokenize_inlines(old_inlines)
    new_t = _tokenize_inlines(new_inlines)
    sm = difflib.SequenceMatcher(None, [k for k, _ in old_t], [k for k, _ in new_t],
                                 autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.extend(_copy(e) for _, e in new_t[j1:j2])
        elif op == "insert":
            _emit_group([_copy(e) for _, e in new_t[j1:j2]], ADD, out)
        elif op == "delete":
            _emit_group([_copy(e) for _, e in old_t[i1:i2]], DEL, out)
        elif op == "replace":
            # latexdiff 流に「削除(旧)→追加(新)」の順で並べる
            _emit_group([_copy(e) for _, e in old_t[i1:i2]], DEL, out)
            _emit_group([_copy(e) for _, e in new_t[j1:j2]], ADD, out)
    return out


# =====================================================================
# 全体着色 (ブロック丸ごとの追加 / 削除)
# =====================================================================

def _wrap_all(inlines, cls):
    """葉ブロックのインライン全体を 1 つの Span(cls) で包む (空なら空リスト)。"""
    inlines = list(inlines)
    if cls == DEL:
        inlines = _unlabel(inlines)   # 消した式に番号を使わせない
    if not inlines:
        return []
    return [pf.Span(*inlines, classes=[cls])]


def _colorize(block, cls):
    """ブロック (とその子) のテキストを丸ごと cls で着色する。block は破壊的に変更される。

    追加ブロック (diff-add) / 削除ブロック (diff-del) の全文を一色にするために使う。
    画像・数式・引用などの不透明インラインは Span 内に温存される (要素は壊さない)。
    CodeBlock / RawBlock / HorizontalRule など run スタイルを乗せられない要素は素通し。
    """
    t = block.tag
    if t in ("Para", "Plain", "Header"):
        block.content = _wrap_all(block.content, cls)
        return block
    if t == "Figure":
        # キャプションを着色する。削除図 (DEL) は画像本体を残さず Div へ畳む:
        # 削除図のファイルは作業ツリーに無いことがあり (図前処理は新版基準)、画像を温存すると
        # pandoc が図を落とし、件数照合 (原稿画像数 != docx 図数) が差分生成を中止させる。
        # 追加図 (ADD) はファイルが作業ツリーに在るので画像を温存する。
        cap_blocks = ([_colorize(b, cls) for b in block.caption.content]
                      if block.caption is not None else [])
        if cls == DEL:
            return pf.Div(*cap_blocks, classes=["deleted-figure"])
        block.caption = pf.Caption(*cap_blocks)
        # 画像だけの段落は Span で包まない。包むと pandoc が「画像 1 つの図」と認めず、図を表の形 (FigureTable) で組み、
        # 段組の後処理と題の後処理が図として扱えなくなる。画像に文字スタイルを掛けても色は付かないので、包まなくても失うものは無い
        block.content = [b if _image_only(b) else _colorize(b, cls) for b in block.content]
        return block
    if t in ("Div", "BlockQuote", "Note"):
        block.content = [_colorize(b, cls) for b in block.content]
        return block
    if t == "Table":
        return _colorize_table(block, cls)
    if t in ("BulletList", "OrderedList"):
        # panflute は項目を ListItem オブジェクト (反復不可、中身は .content) で持つ。
        # 項目を [Block] とみなして `for b in item` と書くと TypeError で止まる
        items = [pf.ListItem(*[_colorize(b, cls) for b in item.content])
                 for item in block.content]
        if t == "OrderedList":
            return pf.OrderedList(*items, start=block.start, style=block.style,
                                  delimiter=block.delimiter)
        return pf.BulletList(*items)
    # 不透明 (CodeBlock / RawBlock / HorizontalRule / LineBlock 等) は素通し
    return block


def _colorize_table(tbl, cls):
    if tbl.caption is not None:
        # 題の末尾のラベル {#tbl:x} は色の Span の外に置く (中にあると pandoc-crossref が読めない)。
        # 消した表はラベルを外す (番号を使わない。消した図と同じ扱い)
        cap, _lbl, label_inlines = _split_caption_label(tbl.caption)
        cap = pf.Caption(*[_colorize(b, cls) for b in cap.content])
        if cls == ADD:
            _attach_label(cap, label_inlines)
        tbl.caption = cap
    for sec in (tbl.head, tbl.foot):
        if sec is None:
            continue
        for row in sec.content:
            for cell in row.content:
                cell.content = [_colorize(b, cls) for b in cell.content]
    for body in tbl.content:
        for row in body.content:
            for cell in row.content:
                cell.content = [_colorize(b, cls) for b in cell.content]
    return tbl


def _color_block(block, cls):
    """deepcopy してから丸ごと着色する (元 AST を汚さない)。"""
    return _colorize(_copy(block), cls)


# =====================================================================
# コンテナ要素の再帰差分
# =====================================================================

def _diff_short_blocks(old_blocks, new_blocks):
    """表のセルと題 (キャプション) の中身の差分。旧と新が同じ種類の段落 1 つずつなら、1 つの段落の中で差分を出す。

    似ていれば語の差分、似ていなければ「旧の全体 (削除) + 空白 + 新の全体 (追加)」(語の差分にすると空白だけが一致して
    削除と追加の語が交互に並ぶ)。_diff_blocks に任せると、似ていない 1 段落ずつ (セルの 1.1 → 1.2 など) は「追加の段落 →
    削除の段落」の 2 段落になり、セルの高さが倍になって新が旧の上に出る。本文の段落は _diff_blocks に任せる。
    """
    if (len(old_blocks) == 1 and len(new_blocks) == 1
            and old_blocks[0].tag == new_blocks[0].tag and new_blocks[0].tag in ("Plain", "Para")):
        o, n = old_blocks[0], new_blocks[0]
        if (_equation_only(o) and _equation_only(n)) or _similarity(o, n) >= SIMILARITY_THRESHOLD:
            return _diff_pair(o, n)
        dele = _wrap_all([_copy(e) for e in o.content], DEL)
        add = _wrap_all([_copy(e) for e in n.content], ADD)
        ctor = pf.Para if n.tag == "Para" else pf.Plain
        return [ctor(*(dele + ([pf.Space()] if dele and add else []) + add))]
    return _diff_blocks(old_blocks, new_blocks)


def _diff_caption(old_cap, new_cap):
    old_blocks = list(old_cap.content) if old_cap is not None else []
    new_blocks = list(new_cap.content) if new_cap is not None else []
    return pf.Caption(*_diff_short_blocks(old_blocks, new_blocks))


def _diff_figure(old, new):
    """Figure: 画像本体 (新版) は温存し、キャプションだけを差分化する。"""
    fig = _copy(new)
    fig.caption = _diff_caption(old.caption, new.caption)
    return fig


def _row_sig(row, norm=_normalize):
    return norm("\x1f".join(pf.stringify(c) for c in row.content))


def _diff_row_cells(old_row, new_row):
    """対応した行: セルを位置で対応付け、各セル内ブロックを再帰差分する。"""
    nr = _copy(new_row)
    old_cells = list(old_row.content)
    new_cells = list(new_row.content)
    out_cells = []
    for ci, nc in enumerate(new_cells):
        if ci < len(old_cells):
            merged = _diff_short_blocks(list(old_cells[ci].content), list(nc.content))
            cell = _copy(nc)
            cell.content = merged
            out_cells.append(cell)
        else:
            cell = _copy(nc)
            cell.content = [_colorize(b, ADD) for b in cell.content]
            out_cells.append(cell)
    nr.content = out_cells
    return nr


def _colorize_row(row, cls):
    nr = _copy(row)
    for cell in nr.content:
        cell.content = [_colorize(b, cls) for b in cell.content]
    return nr


def _diff_rows(old_rows, new_rows):
    """行列を整列して差分行列を返す。

    対応行はセル差分、追加行は全 add 着色、削除行は全 del 着色して新表の中に残す。
    """
    o_sig = [_row_sig(r) for r in old_rows]
    n_sig = [_row_sig(r) for r in new_rows]
    sm = difflib.SequenceMatcher(None, o_sig, n_sig, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            # 大文字小文字だけ違う行はセルの差分に回す
            for orow, nrow in zip(old_rows[i1:i2], new_rows[j1:j2]):
                if _row_sig(orow, _exact) == _row_sig(nrow, _exact):
                    out.append(_copy(nrow))
                else:
                    out.append(_diff_row_cells(orow, nrow))
        elif op == "insert":
            out.extend(_colorize_row(r, ADD) for r in new_rows[j1:j2])
        elif op == "delete":
            out.extend(_colorize_row(r, DEL) for r in old_rows[i1:i2])
        elif op == "replace":
            o = old_rows[i1:i2]
            n = new_rows[j1:j2]
            for k in range(max(len(o), len(n))):
                if k < len(o) and k < len(n):
                    out.append(_diff_row_cells(o[k], n[k]))
                elif k < len(n):
                    out.append(_colorize_row(n[k], ADD))
                else:
                    out.append(_colorize_row(o[k], DEL))
    return out


def _diff_table_section(old_sec, new_sec, _ctor):
    sec = _copy(new_sec)
    old_rows = list(old_sec.content) if old_sec is not None else []
    sec.content = _diff_rows(old_rows, list(new_sec.content))
    return sec


def _diff_table_body(old_body, new_body):
    nb = _copy(new_body)
    old_rows = list(old_body.content) if old_body is not None else []
    nb.content = _diff_rows(old_rows, list(new_body.content))
    return nb


def _diff_table(old, new):
    """Table: 新版の骨格 (colspec/identifier) を保ち、キャプション・各セルを差分化する。

    行は署名で整列し、セルは位置で対応付ける (colspan/rowspan を含む複雑表は曖昧。既知制限)。
    """
    tbl = _copy(new)
    # 題の末尾のラベル {#tbl:x} を外して差分を取り、新版のラベルを Span の外に戻す。
    # ラベルが差分の Span の中に入ると pandoc-crossref が読めず、番号が付かない
    old_cap, _o, _ = _split_caption_label(old.caption)
    new_cap, _n, new_label = _split_caption_label(new.caption)
    tbl.caption = _attach_label(_diff_caption(old_cap, new_cap), new_label)
    tbl.head = _diff_table_section(old.head, new.head, pf.TableHead)
    old_bodies = list(old.content)
    new_bodies = []
    for bi, nb in enumerate(new.content):
        ob = old_bodies[bi] if bi < len(old_bodies) else None
        new_bodies.append(_diff_table_body(ob, nb))
    tbl.content = new_bodies
    tbl.foot = _diff_table_section(old.foot, new.foot, pf.TableFoot)
    return tbl


def _item_sig(item, norm=_normalize):
    # item は panflute の ListItem (中身は .content)。反復できないので
    # `for b in item` ではなく `item.content` をたどる。
    return norm("\x1f".join(pf.stringify(b) for b in item.content))


def _diff_list(old, new):
    """BulletList / OrderedList: 項目を署名で整列し、対応項目を再帰差分する。

    panflute は項目を ListItem オブジェクトで持つ (中身は .content)。項目を [Block] とみなして
    `for b in item` / `list(item)` / `pf.BulletList(*[[Block]])` と書くと TypeError で止まる
    (リストの追加・削除・編集のすべてで)。各分岐は ListItem を作る。"""
    old_items = list(old.content)   # ListItem の並び
    new_items = list(new.content)
    sm = difflib.SequenceMatcher(None, [_item_sig(x) for x in old_items],
                                 [_item_sig(x) for x in new_items], autojunk=False)
    out_items = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            # 大文字小文字だけ違う項目は中身の差分に回す
            for oit, nit in zip(old_items[i1:i2], new_items[j1:j2]):
                if _item_sig(oit, _exact) == _item_sig(nit, _exact):
                    out_items.append(_copy(nit))
                else:
                    out_items.append(pf.ListItem(*_diff_blocks(list(oit.content), list(nit.content))))
        elif op == "insert":
            out_items.extend(pf.ListItem(*[_colorize(_copy(b), ADD) for b in it.content])
                             for it in new_items[j1:j2])
        elif op == "delete":
            out_items.extend(pf.ListItem(*[_colorize(_copy(b), DEL) for b in it.content])
                             for it in old_items[i1:i2])
        elif op == "replace":
            o = old_items[i1:i2]
            n = new_items[j1:j2]
            for k in range(max(len(o), len(n))):
                if k < len(o) and k < len(n):
                    out_items.append(pf.ListItem(*_diff_blocks(list(o[k].content), list(n[k].content))))
                elif k < len(n):
                    out_items.append(pf.ListItem(*[_colorize(_copy(b), ADD) for b in n[k].content]))
                else:
                    out_items.append(pf.ListItem(*[_colorize(_copy(b), DEL) for b in o[k].content]))
    if new.tag == "OrderedList":
        return pf.OrderedList(*out_items, start=new.start, style=new.style,
                              delimiter=new.delimiter)
    return pf.BulletList(*out_items)


# =====================================================================
# 対応ブロックの差分 (種別ごとに分岐)
# =====================================================================

def _diff_pair(old, new):
    """同種別で対応した 1 ブロックを差分化し、ブロックのリストを返す。"""
    t = new.tag
    if t in ("Para", "Plain") and _equation_only(old) and _equation_only(new):
        # 式だけの段落: 式が同じなら新版 (ラベルの付け替えは番号に現れない)。違えば旧の式 (ラベルなし・削除の色) と
        # 新の式 (ラベルつき・追加の色) を別の段落にする (1 段落に式が 2 つ並ぶと番号も式番号の右寄せも掛からない)。
        # 式は大文字小文字を区別して比べる (小文字にして比べると T → t・\Delta → \delta を同じとみなす)
        _log_pair(old, new)
        if _exact(pf.stringify(old)) == _exact(pf.stringify(new)):
            return [_copy(new)]
        return [_color_block(old, DEL), _color_block(new, ADD)]
    if t in ("Table", "Figure"):
        _log_pair(old, new)       # ラベルの付け替えの判定に使う
    if t in ("Para", "Plain"):
        ctor = pf.Para if t == "Para" else pf.Plain
        return [ctor(*_inline_diff(list(old.content), list(new.content)))]
    if t == "Header":
        inl = _inline_diff(list(old.content), list(new.content))
        return [pf.Header(*inl, level=new.level, identifier=new.identifier,
                          classes=list(new.classes), attributes=dict(new.attributes))]
    if t == "Div":
        merged = _diff_blocks(list(old.content), list(new.content))
        return [pf.Div(*merged, identifier=new.identifier, classes=list(new.classes),
                       attributes=dict(new.attributes))]
    if t == "BlockQuote":
        return [pf.BlockQuote(*_diff_blocks(list(old.content), list(new.content)))]
    if t == "Figure":
        return [_diff_figure(old, new)]
    if t == "Table":
        return [_diff_table(old, new)]
    if t in ("BulletList", "OrderedList"):
        return [_diff_list(old, new)]
    # その他 (CodeBlock / RawBlock / 数式 Para 等の不透明): 変化なしなら温存、変化ありなら del+add
    # (大文字小文字を区別して比べる。_normalize (小文字) で比べると大文字小文字だけの変更を見落とす)
    if _exact(pf.stringify(old)) == _exact(pf.stringify(new)):
        return [_copy(new)]
    return [_color_block(old, DEL), _color_block(new, ADD)]


# =====================================================================
# レベル1 + レベル1.5: ブロック列の整列と replace 橋渡し
# =====================================================================

def _greedy_pairs(old_chunk, new_chunk):
    """replace 区間で同種別・類似度しきい値以上の旧/新ブロックを対応付ける。

    貪欲 (類似度降順) に 1 対 1 で割当て、最後に新順で旧インデックス単調増加を満たす対のみ
    残す (交差対は外し add/del へ倒す)。これで後段のマージ走査が順序破綻しない。
    """
    cands = []
    for nj, nb in enumerate(new_chunk):
        nk = _type_key(nb)
        for oi, ob in enumerate(old_chunk):
            if _type_key(ob) != nk:
                continue
            if nk in ("Table", "Figure") and _label_conflict(ob, nb):
                continue
            s = _similarity(ob, nb)
            if nk == "Figure" and s < SIMILARITY_THRESHOLD and _image_targets(ob) and \
                    _image_targets(ob) == _image_targets(nb):
                # 画像が同じ図は、題を書き換えても同じ図として対にする (題の差分になる。題の類似度だけで決めると、
                # 題が似ていなければ図の削除 + 追加になる。付け替えの判定 (_same_float) と同じく画像の一致を同じ図の証拠にする)
                s = SIMILARITY_THRESHOLD
            if s >= SIMILARITY_THRESHOLD:
                cands.append((s, nj, oi))
    cands.sort(key=lambda x: (-x[0], x[1], x[2]))
    pair, used_o, used_n = {}, set(), set()
    for _s, nj, oi in cands:
        if nj in used_n or oi in used_o:
            continue
        pair[nj] = oi
        used_n.add(nj)
        used_o.add(oi)
    mono, last = {}, -1
    for nj in sorted(pair):
        if pair[nj] > last:
            mono[nj] = pair[nj]
            last = pair[nj]
    return mono


def _match_replace(old_chunk, new_chunk):
    """replace 区間: 対応付け (レベル1.5) → 対応対は差分、非対応は add/del 着色。

    対応対 (旧インデックス単調増加) をアンカーに旧/新を二ポインタでマージし、
    順序を保ったまま削除ブロック (赤) を新版の流れの中へ差し込む。
    """
    pairing = _greedy_pairs(old_chunk, new_chunk)
    matched_old = set(pairing.values())
    out = []
    oi = 0
    for nj in range(len(new_chunk)):
        if nj in pairing:
            anchor = pairing[nj]
            while oi < anchor:  # アンカー手前の未対応旧 = 削除
                if oi not in matched_old:
                    out.append(_color_block(old_chunk[oi], DEL))
                oi += 1
            out.extend(_diff_pair(old_chunk[anchor], new_chunk[nj]))
            oi = anchor + 1
        else:
            out.append(_color_block(new_chunk[nj], ADD))  # 対応なしの新 = 追加
    while oi < len(old_chunk):  # 末尾に残った未対応旧 = 削除
        if oi not in matched_old:
            out.append(_color_block(old_chunk[oi], DEL))
        oi += 1
    return out


def _diff_blocks(old_blocks, new_blocks):
    """ブロック列を整列し、マージしたブロック列 (構造温存 + 差分 span) を返す。"""
    o_keys = [_full_sig(b) for b in old_blocks]
    n_keys = [_full_sig(b) for b in new_blocks]
    sm = difflib.SequenceMatcher(None, o_keys, n_keys, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            # 整列は小文字で取るので、大文字小文字を区別してもう一度比べ、違えば語の差分に回す
            for ob, nb in zip(old_blocks[i1:i2], new_blocks[j1:j2]):
                if _exact_sig(ob) == _exact_sig(nb):
                    out.append(_copy(nb))
                else:
                    out.extend(_diff_pair(ob, nb))
        elif op == "insert":
            out.extend(_color_block(b, ADD) for b in new_blocks[j1:j2])
        elif op == "delete":
            out.extend(_color_block(b, DEL) for b in old_blocks[i1:i2])
        elif op == "replace":
            out.extend(_match_replace(old_blocks[i1:i2], new_blocks[j1:j2]))
    return out


# =====================================================================
# 段抜き (`::: wide`) の Div の透過
# =====================================================================

def _is_wide_div(b):
    """`::: wide` の Div (クラスが wide だけ・識別子と属性なし・中身あり)。段抜きの目印 (wide-blocks.lua) で、差分では透過する。"""
    return (b.tag == "Div" and list(b.classes) == ["wide"] and not b.identifier
            and not dict(b.attributes) and len(b.content) > 0)


def _flatten_wide(blocks):
    """ブロック列から wide の Div を外した列と、各ブロックが属していた Div の位置 (属さなければ None) の列を返す。"""
    flat, groups = [], []
    for gi, b in enumerate(blocks):
        if _is_wide_div(b):
            flat.extend(b.content)
            groups.extend([gi] * len(b.content))
        else:
            flat.append(b)
            groups.append(None)
    return flat, groups


def _harmonize_wide(old_blocks, new_blocks):
    """旧版の最上位のブロック列の wide の Div の付け方を新版に合わせた列を返す。

    改訂で既存の表を `::: wide` で囲む (または外す) と、Div と表は種別が違うので整列で対にならず、表がまるごと削除 + 追加になり、
    変えていない凡例が削除した表の上へ移る。そこで wide の Div を外した列どうしを差分と同じ規則 (整列 + 類似度の対応付け) で
    対にし、旧版のブロックを対になった新版のブロックの Div に入れ直す (旧版の中身はそのまま。Div の付け方だけを変える)。
    対にならない旧版のブロック (消したブロック) は、前後の対になったブロックが同じ Div にあればその Div に、そうでなければ
    旧版で同じ Div にあった隣のブロックの Div に、どちらでもなければ Div の外に置く。付け方が変わらなければ old_blocks をそのまま返す。
    段抜きは本文の流れの上にしか効かないので、最上位だけを見る。
    """
    if not any(_is_wide_div(b) for b in old_blocks) and not any(_is_wide_div(b) for b in new_blocks):
        return old_blocks
    o_flat, o_grp = _flatten_wide(old_blocks)
    n_flat, n_grp = _flatten_wide(new_blocks)
    match = {}
    sm = difflib.SequenceMatcher(None, [_full_sig(b) for b in o_flat], [_full_sig(b) for b in n_flat],
                                 autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                match[i1 + k] = j1 + k
        elif op == "replace":
            for nj, oi in _greedy_pairs(o_flat[i1:i2], n_flat[j1:j2]).items():
                match[i1 + oi] = j1 + nj
    matched = sorted(match)
    target = []
    for i in range(len(o_flat)):
        if i in match:
            target.append(n_grp[match[i]])
            continue
        k = bisect.bisect_left(matched, i)
        prev = matched[k - 1] if k > 0 else None
        nxt = matched[k] if k < len(matched) else None
        pg = n_grp[match[prev]] if prev is not None else None
        ng = n_grp[match[nxt]] if nxt is not None else None
        if pg == ng:
            target.append(pg)
        elif o_grp[i] is not None and pg is not None and o_grp[prev] == o_grp[i]:
            target.append(pg)
        elif o_grp[i] is not None and ng is not None and o_grp[nxt] == o_grp[i]:
            target.append(ng)
        else:
            target.append(None)
    out, i = [], 0
    while i < len(o_flat):
        g = target[i]
        if g is None:
            out.append(o_flat[i])
            i += 1
            continue
        j = i
        while j < len(o_flat) and target[j] == g:
            j += 1
        out.append(pf.Div(*[_copy(b) for b in o_flat[i:j]], classes=list(new_blocks[g].classes)))
        i = j

    def shape(blocks):
        return [("wide", len(b.content)) if _is_wide_div(b) else id(b) for b in blocks]

    return old_blocks if shape(out) == shape(old_blocks) else out


# =====================================================================
# 公開 API
# =====================================================================

def diff_documents(old_doc, new_doc):
    """旧/新 panflute Doc を突き合わせ、マージ Doc を返す。

    マージ後 Doc は新版の Meta (crossref 接頭辞 / citeproc / lang 等) を採る。
    構造は温存され、変更語句のみ Span(.diff-add/.diff-del) で包まれる。
    差分の前に、両版の番号つきの式を Span の形にし、旧版の図表と式のラベルの付け替えを新版の名前に直す。
    旧版の段抜きの Div の付け方も新版に合わせる。付け替えは題の類似度 (と中身・画像) で
    決めたものに加えて、ブロックの整列で対になった図表と式のものも直す (1 回目の差分で対を集める)。
    引数の Doc は変えない。
    """
    old_doc = _copy(old_doc)
    new_doc = _copy(new_doc)
    _wrap_equation_labels(old_doc)
    _wrap_equation_labels(new_doc)
    old_blocks = list(old_doc.content)
    harmonized = _harmonize_wide(old_blocks, list(new_doc.content))
    if harmonized is not old_blocks:
        old_doc.content = [_copy(b) for b in harmonized]
    _apply_label_renames(old_doc, _label_renames(old_doc, new_doc))
    _apply_label_renames(old_doc, _paired_renames(old_doc, new_doc))
    merged = _copy(new_doc)
    merged.content = _diff_blocks(list(old_doc.content), list(new_doc.content))
    return merged


def main(argv=None):
    """CLI: 2 つの pandoc JSON (旧 新) を読み、マージ JSON を stdout へ。"""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        sys.exit("usage: ast_diff.py OLD.json NEW.json  (マージ JSON を stdout へ出力)")
    with open(argv[0], encoding="utf-8") as f:
        old_doc = pf.load(f)
    with open(argv[1], encoding="utf-8") as f:
        new_doc = pf.load(f)
    merged = diff_documents(old_doc, new_doc)
    pf.dump(merged, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
