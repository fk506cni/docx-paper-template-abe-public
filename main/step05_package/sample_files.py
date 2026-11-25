"""sample_files.py — 同梱のサンプルの消し残しの判定。

package.py (最終モードで止める)・test_validate_abe.py (指紋の一覧の古さ)・test_sample_gate.py (remove-sample.sh と同じ判定か) が使う。
scripts/remove-sample.sh は同じ規則を bash で持つ (コンテナを使わないため)。規則を変えたら両方を直し、test_sample_gate.py で照らす。

規則:
  - 指紋の一覧 scripts/lib/sample-files.sha256 (src/ の ABE のサンプル論文): 「SHA-256<空白>[*]パス」の行。行末の CR と
    パスの先頭の * を除き、16 進は小文字にそろえ、パスは 1 つ目の空白の並びの後の残り全部 (空白を含む名前も読む)。
    # で始まる行・形の合わない行・入力ルートの外を指す行 (絶対パス・.. を含む) は読まない
  - 動作例: data/dummy/ (汎用のサンプル: 直下の *.md・ref.bib・figs/ の下のすべて) と data/dummy/abe/ (*.md・ref.bib・figs/・
    forms/・supplementary/ の下のすべて) のいまのファイルの SHA-256。その場で計算する (書き出しで data/dummy/ のコメントが
    書き換わるので、原本と公開物で中身が違い、一覧に持てない)。README の案内どおり汎用のサンプルを src/ に写したときも数える
  - 入力ルートが data/dummy/ の下 (動作例・試験用のファイルそのもの) なら判定しない
  - 入力ルートからのパスのどの部分がリンクでも、そのファイルは数えない (remove-sample.sh も消さない。リンクの先は自分のファイルかもしれない)
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

SAMPLE_LIST = Path("scripts/lib/sample-files.sha256")
_LINE = re.compile(r"([0-9A-Fa-f]{64})[ \t]+\*?(.+)$")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def safe_rel(rel: str) -> bool:
    """入力ルートの中を指す相対パスか (絶対パス・.. を含むもの・空は不可)。"""
    if not rel or rel.startswith("/") or re.match(r"[A-Za-z]:[\\/]", rel):
        return False
    return ".." not in rel.replace("\\", "/").split("/")


def read_list(path: Path = SAMPLE_LIST) -> list[tuple[str, str]]:
    """指紋の一覧の (相対パス, SHA-256) の並び (上の規則で読む)。一覧が無ければ空。"""
    if not Path(path).is_file():
        return []
    out = []
    for ln in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.rstrip("\r")
        if ln.startswith("#"):
            continue
        m = _LINE.fullmatch(ln)
        if not m:
            continue
        rel = m.group(2).rstrip()
        if safe_rel(rel):
            out.append((rel, m.group(1).lower()))
    return out


def _files_under(base: Path, patterns: list[str]) -> list[Path]:
    """base の下の、patterns に当たる通常のファイル。「dir/」は dir の下のすべて (find -type f と同じ)、それ以外は base の直下の
    glob (bash と同じく . で始まる名前は含めない)。パスのどこかがリンクのものは含めない (remove-sample.sh と同じ)。"""
    out = []
    for pat in patterns:
        if pat.endswith("/"):
            d = base / pat.rstrip("/")
            if d.is_dir() and not d.is_symlink():
                out.extend(p for p in sorted(d.rglob("*"))
                           if p.is_file() and not has_link(base, p.relative_to(base).as_posix()))
        else:
            out.extend(p for p in sorted(base.glob(pat))
                       if p.is_file() and not p.is_symlink() and not p.name.startswith("."))
    return out


def dummy_candidates(repo_root: Path = Path(".")) -> dict[str, set[str]]:
    """動作例 (data/dummy/ と data/dummy/abe/) のファイルの「相対パス → SHA-256 の集合」。"""
    cands: dict[str, set[str]] = {}
    for sub, pats in (("data/dummy", ["*.md", "ref.bib", "figs/"]),
                      ("data/dummy/abe", ["*.md", "ref.bib", "figs/", "forms/", "supplementary/"])):
        base = Path(repo_root) / sub
        if not base.is_dir():
            continue
        for p in _files_under(base, pats):
            cands.setdefault(p.relative_to(base).as_posix(), set()).add(_sha256(p))
    return cands


def candidates(repo_root: Path = Path("."), list_path: Path | None = None) -> dict[str, set[str]]:
    """消し残しとみなす「相対パス → SHA-256 の集合」(指紋の一覧 + 動作例)。"""
    lp = Path(list_path) if list_path else Path(repo_root) / SAMPLE_LIST
    cands = dummy_candidates(repo_root)
    for rel, sha in read_list(lp):
        cands.setdefault(rel, set()).add(sha)
    return cands


def has_link(root: Path, rel: str) -> bool:
    """入力ルートからのパスのどこかの部分がリンクか (入力ルートそのものは見ない)。"""
    cur = Path(root)
    for part in rel.split("/"):
        cur = cur / part
        if cur.is_symlink():
            return True
    return False


def is_under_dummy(input_root: Path, repo_root: Path = Path(".")) -> bool:
    try:
        Path(input_root).resolve().relative_to((Path(repo_root) / "data" / "dummy").resolve())
        return True
    except ValueError:
        return False


def matches(root: Path, rel: str, shas: set[str]) -> bool:
    p = Path(root) / rel
    return not has_link(root, rel) and p.is_file() and _sha256(p) in shas


def leftovers(input_root, repo_root: Path = Path("."), list_path: Path | None = None) -> tuple[bool, list[str]]:
    """(main.md が同梱のサンプルそのものか, 中身がサンプルと同じまま残っている main.md 以外のファイル)。
    入力ルートが data/dummy/ の下なら (False, [])。"""
    if is_under_dummy(input_root, repo_root):
        return False, []
    cands = candidates(repo_root, list_path)
    root = Path(input_root)
    is_sample = "main.md" in cands and matches(root, "main.md", cands["main.md"])
    left = [rel for rel in sorted(cands) if rel != "main.md" and matches(root, rel, cands[rel])]
    return is_sample, left


def list_state(input_root, list_path: Path = SAMPLE_LIST) -> tuple[bool, list[str]]:
    """指紋の一覧だけで見た (main.md が一覧の main.md か, 一覧と一致する main.md 以外のファイル)。
    test_validate_abe.py が一覧の古さを見るのに使う (動作例は見ない)。"""
    root = Path(input_root)
    entries: dict[str, set[str]] = {}
    for rel, sha in read_list(list_path):
        entries.setdefault(rel, set()).add(sha)
    is_sample = "main.md" in entries and matches(root, "main.md", entries["main.md"])
    left = [rel for rel in sorted(entries) if rel != "main.md" and matches(root, rel, entries[rel])]
    return is_sample, left
