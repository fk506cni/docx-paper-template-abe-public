#!/usr/bin/env python3
"""compare-snapshots.py — `jank/baseline/` の 2 スナップショットを【内容】で比較する。

回帰判定の受入テスト。`scripts/baseline.sh` / `scripts/baseline-abe.sh` が撮った
スナップショットの対を比べ、成果物の中身が変わっていないかを見る。

    python3 scripts/compare-snapshots.py <比較元の接尾辞> <比較先の接尾辞> [--expect-missing <誌>[,<誌>…]]
    例: python3 scripts/compare-snapshots.py before after
        python3 scripts/compare-snapshots.py before after --expect-missing abe   # 学会テンプレートが無く abe を撮れないとき

**前後の片方にしか無い誌は「比較できず」として不合格に数える** (終了コード 1)。撮影が途中の誌で止まって後ろの誌が
欠けても「差分 0 件」に見えないようにするため。撮る対象を意図して変えた比較 (誌を足した・外した前後や、学会テンプレートが
無くて abe を撮れない環境など) だけ、`--expect-missing` に誌を明示して数から外す。
明示した誌が両方にあれば普通に比べる。
**前後の両方に無い誌も不合格に数える**。比べるべき誌の一覧は作業ツリーの `data/journals/*/profile.yaml`
から組み、そこにある誌が前後のどちらか (両方を含む) に無ければ、`--expect-missing` に挙げた誌を除いて「比較できず」にする
(スナップショットのディレクトリからだけ誌を拾うと、ある誌を前後とも撮り忘れても「差分 0 件」・終了コード 0 になる)。

docx は zip で、pandoc がエントリのタイムスタンプと docProps/core.xml の作成/更新日時を
毎回入れるためバイト比較では必ず差が出る。回帰判定は「zip 内の各パートの中身が同じか」で行う。
比較対象から外すもの:
  - docProps/core.xml (作成/更新日時)
  - ログ中の一時ファイル名 (jank/diff_old_<pid>.md) と Inkscape の時刻つき警告
  - ログ中のリポジトリの絶対パス (別のディレクトリで撮ったスナップショット同士・ホストとコンテナのパスの違い)。
    **伏せるのはログ (*.log) だけ**で、成果物の文面 (SUBMISSION.md など) はそのまま比べる
    (成果物に私的なパスが入る退行を隠さないため)

【置き場所】道具は git で追跡する `scripts/` に置き、**スナップショットの実体 (数百 MB) は
`jank/baseline/` に置く** (git 管理外)。
"""
import argparse
import glob
import re
import sys
import zipfile
from pathlib import Path

IGNORE_PARTS = {"docProps/core.xml"}
# 比べるべき誌の一覧の出どころ (リポジトリの根から)
JOURNALS_DIR = Path("data/journals")
# 成果物ではないファイル (build.sh が同時 build を止めるためのロック。中身は空)
IGNORE_FILES = {".build.lock"}
# PDF は Ghostscript/Inkscape が生成時刻と文書 ID を毎回書くため、そこだけ潰して比較する
PDF_NOISE = re.compile(rb"(/CreationDate|/ModDate)\s*\([^)]*\)|<[0-9A-Fa-f]{32}>")
NOISE = [
    (re.compile(r"jank/diff_old_\d+\.md"), "jank/diff_old_<pid>.md"),
    # build の一時名 (build_docx.py が乱数を入れる。同時に回した build が一時ファイルを取り合わないため)
    (re.compile(r"\.building(?:\.[0-9a-f]+)?\.docx"), ".building.<id>.docx"),
    (re.compile(r"\(inkscape:\d+\): WARNING \*\*: \d+:\d+:\d+\.\d+"), "(inkscape): WARNING <t>"),
    # reference.docx を持たない作業ツリー (clone した直後) で撮った回だけに出る行。成果物は変わらない
    (re.compile(r"^-- data/journals/[^/\n]+/reference\.docx が無いので生成します[^\n]*\n?", re.M), ""),
    # リポジトリの絶対パス (別のディレクトリで撮ったスナップショット同士・ホストとコンテナのパスの違い)。
    # パスの中の**最後の**既知のフォルダ名の手前までを根とみなす (リポジトリを ~/src/ や …/jank/…/repo の下に
    # 置いても、根の途中の src や jank で止まらない)
    (re.compile(r"(?<![\w.~:/-])/(?:[^\s/'\"]+/)+(?=(?:data|jank|docker|main|scripts|src|publish)/)"), "<ROOT>/"),
]


def norm_log(text):
    for pat, rep in NOISE:
        text = pat.sub(rep, text)
    return text


def docx_parts(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in sorted(z.namelist()) if n not in IGNORE_PARTS}


def compare(a, b):
    diffs = []
    files_a = {p.relative_to(a) for p in a.rglob("*") if p.is_file() and p.name not in IGNORE_FILES}
    files_b = {p.relative_to(b) for p in b.rglob("*") if p.is_file() and p.name not in IGNORE_FILES}
    for only, side in ((files_a - files_b, a), (files_b - files_a, b)):
        for f in sorted(only):
            diffs.append(f"片側のみ ({side.name}): {f}")
    for f in sorted(files_a & files_b):
        pa, pb = a / f, b / f
        if pa.suffix.lower() in (".docx", ".pptx", ".xlsx"):
            if docx_parts(pa) != docx_parts(pb):
                pda, pdb = docx_parts(pa), docx_parts(pb)
                changed = [k for k in set(pda) | set(pdb) if pda.get(k) != pdb.get(k)]
                diffs.append(f"docx 内容差: {f} -> {sorted(changed)}")
        elif pa.suffix.lower() in (".log", ".txt", ".md", ".tsv", ".yaml", ".csl"):
            ta = pa.read_text(encoding="utf-8", errors="replace")
            tb = pb.read_text(encoding="utf-8", errors="replace")
            if pa.suffix.lower() == ".log":     # 伏せるのはログだけ (成果物の文面はそのまま比べる)
                ta, tb = norm_log(ta), norm_log(tb)
            if ta != tb:
                import difflib
                d = list(difflib.unified_diff(ta.splitlines(), tb.splitlines(),
                                              str(f) + " (pre)", str(f) + " (post)", lineterm="", n=0))
                diffs.append("テキスト差: " + "\n    ".join(d))
        elif pa.suffix.lower() == ".pdf":
            if PDF_NOISE.sub(b"X", pa.read_bytes()) != PDF_NOISE.sub(b"X", pb.read_bytes()):
                diffs.append(f"PDF 内容差: {f}")
        elif pa.name == ".build.source":
            # build の出所の記録。main_docx_sha256 (build が書いた docx そのもののハッシュ) は、docx に入る作成時刻のため
            # build のたびに変わるので比べない。ほかの行 (入力ルート・原稿と入力のハッシュ・誌) はそのまま比べる
            def _rec(p):
                return [ln for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
                        if not ln.startswith("main_docx_sha256\t")]
            if _rec(pa) != _rec(pb):
                diffs.append(f"テキスト差: {f} (main_docx_sha256 の行を除いて)")
        else:
            if pa.read_bytes() != pb.read_bytes():
                diffs.append(f"バイナリ差: {f}")
    return diffs


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="jank/baseline/ の 2 スナップショットを内容で比較する (回帰判定)。")
    p.add_argument("pre", help="比較元の接尾辞 (jank/baseline/<誌>__<pre>)")
    p.add_argument("post", help="比較先の接尾辞 (jank/baseline/<誌>__<post>)")
    p.add_argument("--expect-missing", action="append", default=[], metavar="誌[,誌…]",
                   help="前後の片方 (か両方) に無くてもよい誌 (撮る対象を意図して変えた比較だけで使う。"
                        "繰り返しかカンマ区切りで複数)。指定の無い誌が片方にしか無いか、data/journals/*/profile.yaml にある誌が"
                        "前後の両方に無ければ不合格")
    args = p.parse_args(argv)
    args.expect_missing = {j.strip() for v in args.expect_missing for j in v.split(",") if j.strip()}
    return args


def main(argv=None):
    args = parse_args(argv)
    base = Path("jank/baseline")
    pre_suffix, post_suffix = args.pre, args.post
    total = 0
    compared, missing_bad, missing_ok = [], [], []
    # 対象誌は名前を固定で持たず、jank/baseline/<誌>__<suffix> のディレクトリから拾う。
    # abe は入力ルートが違うので別のスクリプト (scripts/baseline-abe.sh) で撮るが、比較は同じ物差しで行う
    # (誌の名前を固定で持つと、誌を足しても黙って比較の対象外になる)。
    # どちらか片方にしか無い誌は「比較できず」として不合格に数える (--expect-missing で明示した誌だけ外す)。
    journals: set[str] = set()
    for suffix in (pre_suffix, post_suffix):
        tail = f"__{suffix}"
        for d in base.glob(f"*{glob.escape(tail)}"):
            if d.is_dir():
                journals.add(d.name[: -len(tail)])
    if not journals:
        print(f"スナップショットがありません: {base}/*__{pre_suffix} / {base}/*__{post_suffix}")
        print("\n== 差分 1 件 ==")
        return 1
    # 比べるべき誌 = 作業ツリーにある誌 (data/journals/*/profile.yaml)。前後の両方に無い誌もここで拾う
    # (誌の名前は固定で持たない。誌を足せばその誌も比べる)
    required = {p.parent.name for p in JOURNALS_DIR.glob("*/profile.yaml")}
    if not required:
        print(f"誌の一覧を作れません ({JOURNALS_DIR}/*/profile.yaml が無い)。リポジトリの根で実行してください")
        print("\n== 差分 1 件 ==")
        return 1
    journals |= required
    # 表示順は _default を先頭に、残りは名前順 (baseline.sh → baseline-abe.sh の撮影順とは限らない)
    for j in sorted(journals, key=lambda x: (x != "_default", x)):
        a, b = base / f"{j}__{pre_suffix}", base / f"{j}__{post_suffix}"
        print(f"===== {j} =====")
        if not a.is_dir() and not b.is_dir():
            # 前後の両方に無い (data/journals にある誌だけがここに来る)
            if j in args.expect_missing:
                print(f"  比較できず (想定どおり。--expect-missing {j}): {a} も {b} もありません")
                missing_ok.append(j)
            else:
                print(f"  比較できず: {a} も {b} もありません (data/journals/{j}/profile.yaml はある)。"
                      "この誌を撮るスクリプト (baseline.sh / baseline-abe.sh) を前後とも回していません")
                missing_bad.append(j)
                total += 1
            continue
        if not a.is_dir() or not b.is_dir():
            have = a if a.is_dir() else b
            lack = b if a.is_dir() else a
            if j in args.expect_missing:
                print(f"  比較できず (想定どおり。--expect-missing {j}): {lack} がありません ({have} だけがある)")
                missing_ok.append(j)
            else:
                print(f"  比較できず: {lack} がありません ({have} だけがある)。"
                      "撮影が途中で止まったか、撮る対象が変わっています")
                missing_bad.append(j)
                total += 1
            continue
        compared.append(j)
        if j in args.expect_missing:
            print(f"  (--expect-missing {j} を指定したが、前後の両方にあるので比べる)")
        diffs = compare(a, b)
        if not diffs:
            print("  差分なし (内容一致)")
        for d in diffs:
            print(f"  {d}")
            total += 1
    # どの誌を比べ、どの誌を比べられなかったかを必ず出す (前後の両方に無い誌も data/journals から拾って数える)
    print("\n-- 比べた誌: " + (", ".join(compared) or "(なし)"))
    if missing_bad:
        print("-- 比較できず (不合格に数えた): " + ", ".join(missing_bad))
    if missing_ok:
        print("-- 比較できず (--expect-missing で想定どおり): " + ", ".join(missing_ok))
    print(f"\n== 差分 {total} 件 ==")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
