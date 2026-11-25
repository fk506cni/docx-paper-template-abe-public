#!/usr/bin/env python3
"""test_sample_gate.py — 同梱のサンプルの消し残しの判定の試験。

package.py の判定 (main/step05_package/sample_files.py) と scripts/remove-sample.sh が、同じファイルを「同梱のサンプルのまま」と
みなすか、リンクの先を消さないか、data/dummy/ の下では何もしないかを、一時ディレクトリに作った小さな作業ツリーで照らす。

  docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \\
      python3 main/step05_package/test_sample_gate.py

素の assert ではなく件数を数え、最後に「OK n / NG m」を出す。NG が 1 件でもあれば終了コード 1。
src/ にサンプルが無いとき (サンプルを消して自分の原稿を書いた作業ツリー) は、サンプルを使う場合を飛ばしたと出す。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import sample_files  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(desc: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((desc, bool(ok), detail))


def make_project(tmp: Path) -> Path:
    """一時ディレクトリに、remove-sample.sh・指紋の一覧・data/dummy の動作例・src/ のサンプルだけを持つ作業ツリーを作る。"""
    proj = tmp / "proj"
    (proj / "scripts" / "lib").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "remove-sample.sh", proj / "scripts" / "remove-sample.sh")
    shutil.copy2(ROOT / "scripts" / "lib" / "sample-files.sha256", proj / "scripts" / "lib" / "sample-files.sha256")
    dd = ROOT / "data" / "dummy"
    for p in list(dd.glob("*.md")) + [dd / "ref.bib"]:
        if p.is_file() and not p.name.startswith("."):
            (proj / "data" / "dummy").mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, proj / "data" / "dummy" / p.name)
    if (dd / "figs").is_dir():
        shutil.copytree(dd / "figs", proj / "data" / "dummy" / "figs", symlinks=True)
    da = dd / "abe"
    (proj / "data" / "dummy" / "abe").mkdir(parents=True, exist_ok=True)
    for p in list(da.glob("*.md")) + [da / "ref.bib"]:
        if p.is_file() and not p.name.startswith("."):
            shutil.copy2(p, proj / "data" / "dummy" / "abe" / p.name)
    for sub in ("figs", "forms", "supplementary"):
        if (da / sub).is_dir():
            shutil.copytree(da / sub, proj / "data" / "dummy" / "abe" / sub, symlinks=True)
    return proj


def fresh_src(proj: Path) -> Path:
    src = proj / "src"
    if src.is_symlink() or src.is_file():
        src.unlink()
    elif src.exists():
        shutil.rmtree(src)
    src.mkdir()
    for rel, _ in sample_files.read_list(proj / "scripts" / "lib" / "sample-files.sha256"):
        s = ROOT / "src" / rel
        if s.is_file():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, src / rel)
    return src


def py_set(proj: Path, root: str = "src") -> set[str]:
    cwd = os.getcwd()
    os.chdir(proj)
    try:
        is_sample, left = sample_files.leftovers(root, Path("."))
    finally:
        os.chdir(cwd)
    return set(left) | ({"main.md"} if is_sample else set())


def sh_run(proj: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(proj / "scripts" / "remove-sample.sh"), *args],
                          capture_output=True, text=True, cwd=proj)


def sh_set(proj: Path, root: str = "src") -> set[str]:
    r = sh_run(proj, "--dry-run", "--input", root)
    out = set()
    for ln in r.stdout.splitlines():
        if ln.startswith("  消す:"):
            out.add(ln.split(":", 1)[1].strip()[len(root) + 1:])
    return out


def agree(desc: str, proj: Path, expect: set[str] | None = None, root: str = "src") -> None:
    p, s = py_set(proj, root), sh_set(proj, root)
    check(f"{desc}: package.py と remove-sample.sh が同じファイルを消し残しとみなす", p == s,
          f"package.py={sorted(p)} remove-sample.sh={sorted(s)}")
    if expect is not None:
        check(f"{desc}: 期待どおり", p == expect, f"実際={sorted(p)} 期待={sorted(expect)}")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    have_sample = all((ROOT / "src" / rel).is_file() for rel, _ in sample_files.read_list(ROOT / "scripts/lib/sample-files.sha256"))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = make_project(tmp)
        lst = proj / "scripts" / "lib" / "sample-files.sha256"
        all_list = {rel for rel, _ in sample_files.read_list(lst)}
        if have_sample:
            # 1. サンプルのまま / main.md だけ書き換えた
            src = fresh_src(proj)
            agree("サンプルのまま", proj, all_list)
            (src / "main.md").write_text((src / "main.md").read_text(encoding="utf-8") + "\nmy edit\n", encoding="utf-8")
            agree("main.md だけ書き換えた", proj, all_list - {"main.md"})
            # 2. 一覧の書き方 (CRLF・* の付いたパス・大文字の 16 進・空白を含む名前)
            orig = lst.read_bytes()
            (src / "figs" / "my fig.svg").write_bytes((src / "figs" / "fig-ths.svg").read_bytes())
            extra = f"{sha(src / 'figs' / 'my fig.svg')}  figs/my fig.svg\n".encode()
            for name, data in (("CRLF", orig.replace(b"\n", b"\r\n")),
                               ("* の付いたパス", orig.replace(b"  ", b" *")),
                               ("大文字の 16 進", b"\n".join(ln[:64].upper() + ln[64:] for ln in orig.split(b"\n"))),
                               ("空白を含むパス", orig + extra)):
                lst.write_bytes(data)
                want = all_list - {"main.md"} | ({"figs/my fig.svg"} if name == "空白を含むパス" else set())
                agree(f"一覧の書き方 ({name})", proj, want)
            lst.write_bytes(orig)
            (src / "figs" / "my fig.svg").unlink()
            # 3. ファイルのリンク・ディレクトリのリンク (どちらも数えず、リンクの先を消さない)
            src = fresh_src(proj)
            (src / "main.md").write_text("# my paper\n", encoding="utf-8")
            outside = tmp / "outside"
            outside.mkdir()
            shutil.copy2(src / "figs" / "fig-tjd.jpg", outside / "fig-tjd.jpg")
            (src / "figs" / "fig-tjd.jpg").unlink()
            (src / "figs" / "fig-tjd.jpg").symlink_to(outside / "fig-tjd.jpg")
            agree("ファイルのリンク", proj, all_list - {"main.md", "figs/fig-tjd.jpg"})
            figs_out = tmp / "figs-outside"
            shutil.move(str(src / "figs"), str(figs_out))
            (figs_out / "fig-tjd.jpg").unlink()
            shutil.copy2(outside / "fig-tjd.jpg", figs_out / "fig-tjd.jpg")
            (src / "figs").symlink_to(figs_out, target_is_directory=True)
            agree("ディレクトリのリンク", proj, {r for r in all_list if not r.startswith("figs/")} - {"main.md"})
            r = sh_run(proj)
            check("ディレクトリのリンク: remove-sample.sh がリンクの先を消さない",
                  all((figs_out / n).is_file() for n in ("fig-tjd.jpg", "fig-ths.svg", "fig-apparatus.svg")), r.stdout[-300:])
            check("ディレクトリのリンク: remove-sample.sh がほかのサンプルを消す",
                  not (src / "ref.bib").exists() and not (src / "cover-letter.md").exists(), r.stdout[-300:])
            (src / "figs").unlink()
            # 4. 実際に消す (main.md を書き換えた形): 消したものと案内
            src = fresh_src(proj)
            (src / "main.md").write_text((src / "main.md").read_text(encoding="utf-8") + "\nedit\n", encoding="utf-8")
            r = sh_run(proj)
            gone = {rel for rel in all_list if not (src / rel).exists()}
            check("実際に消す: main.md 以外のサンプルを消す", gone == all_list - {"main.md"}, f"消えた={sorted(gone)}")
            check("実際に消す: 書き換えた main.md は残す", (src / "main.md").is_file())
            check("実際に消す: 消えたファイルだけを戻す案内を出す", "git ls-files --deleted" in r.stdout, r.stdout[-300:])
        else:
            check("src/ にサンプルが無い (サンプルを使う場合は飛ばした)", True)
        # 5. 汎用のサンプルを README の案内どおり写して main.md だけ書き換えた
        src = proj / "src"
        if src.exists() or src.is_symlink():
            shutil.rmtree(src) if src.is_dir() and not src.is_symlink() else src.unlink()
        src.mkdir()
        dd = proj / "data" / "dummy"
        for p in list(dd.glob("*.md")) + [dd / "ref.bib"]:
            shutil.copy2(p, src / p.name)
        shutil.copytree(dd / "figs", src / "figs", dirs_exist_ok=True)
        (src / "main.md").write_text("# my own paper\n", encoding="utf-8")
        want = {p.name for p in dd.glob("*.md")} - {"main.md"} | {"ref.bib"} | \
            {p.relative_to(dd).as_posix() for p in (dd / "figs").rglob("*") if p.is_file()}
        agree("汎用のサンプルを写して main.md だけ書き換えた", proj, want)
        check("汎用のサンプル: カバーレターと回答書を消し残しとみなす",
              {"cover-letter.md", "revise-report.md"} <= py_set(proj), str(sorted(py_set(proj))))
        # 6. ABE の動作例の書式 (ダミー) を src/forms/ に写した
        forms = proj / "data" / "dummy" / "abe" / "forms"
        if forms.is_dir():
            shutil.copytree(forms, src / "forms")
            fset = {f"forms/{p.relative_to(forms).as_posix()}" for p in forms.rglob("*") if p.is_file()}
            check("動作例の書式を src/forms/ に写した: 消し残しとみなす", fset <= py_set(proj) and fset <= sh_set(proj),
                  f"package.py={sorted(py_set(proj) & fset)} remove-sample.sh={sorted(sh_set(proj) & fset)}")
        # 7. 入力ルートが data/dummy/ の下 (動作例そのもの) なら何もしない
        check("data/dummy/abe そのもの: package.py は判定しない", py_set(proj, "data/dummy/abe") == set())
        r = sh_run(proj, "--input", "data/dummy/abe")
        check("data/dummy/abe そのもの: remove-sample.sh は何も消さない",
              (proj / "data/dummy/abe/main.md").is_file() and "何も消しません" in r.stdout, r.stdout[-200:])
        # 8. 一覧が入力ルートの外を指す行を持てば remove-sample.sh は何もせずに止まる
        lst.write_bytes(lst.read_bytes() + b"0" * 64 + b"  ../outside.txt\n")
        r = sh_run(proj, "--dry-run")
        check("一覧が入力ルートの外を指す: remove-sample.sh は止まる", r.returncode == 1 and "外を指して" in r.stderr, r.stderr[-200:])
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    for desc, ok, detail in RESULTS:
        print(f"{'OK' if ok else 'NG'}: {desc}" + ("" if ok or not detail else f"\n      {detail}"))
    print(f"\n== サンプルの判定の試験: OK {n_ok} / NG {len(RESULTS) - n_ok}")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
