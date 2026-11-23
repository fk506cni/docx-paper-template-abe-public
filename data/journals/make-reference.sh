#!/bin/bash
# make-reference.sh — 任意の雑誌プロファイルの reference.docx を profile.yaml から生成する (汎用版)。
#
# docs/architecture.md §3。pandoc 既定 reference.docx をベースに、<id>/profile.yaml の体裁値 (line_spacing /
# line_numbers / page_numbers / font / font_size / margins / paper_size) と差分スタイル
# DiffAdd/DiffDel を焼き込む。
# すべて docx-paper-template-pandoc コンテナ内で実行する (ホスト Python は汚さない)。
#
# 新規雑誌の追加手順 (docs/usage-guide.md §4):
#   1. mkdir data/journals/<id> && cp data/journals/_default/profile.yaml data/journals/<id>/
#      (profile.yaml だけを写す。ディレクトリごと写すと _default 専用の make-reference.sh と
#       _default.csl まで付いてくる)
#   2. data/journals/<id>/profile.yaml を実規定に合わせて編集
#   3. bash data/journals/make-reference.sh <id>      ← 本スクリプト
#      (雛形の reference_doc: reference.docx のままなら省いてよい。無ければ build / diff が生成する)
#   (引用様式が違う場合は <id>.csl を置き csl: <id>.csl に。null なら _default の AMA を継承し、そのことを警告する)
#
# 使い方:  bash data/journals/make-reference.sh <id>     (id 既定: _default)
# 出力:    data/journals/<id>/reference.docx
#
# 注: profile.margins は四辺一律の代表値として解釈する (非対称余白の誌は patch 側の拡張が要る)。
#
# 【雑誌が配るテンプレートから作る誌】(profile の reference_base)
#   reference_base があれば、pandoc の既定ではなくそのテンプレート (data/journals/<id>/<reference_base>) を雛形にし、
#   体裁は焼き込まない (テンプレートが正。patch_reference_docx.py --base)。テンプレートは学会の配布物なので git で追跡せず、
#   人が取得元 (profile の reference_base_url) から取って置く。無い・壊れているときは取得の案内を標準エラーに出して止まる
#   (build / diff から呼ばれるときは標準出力が捨てられるため)。
#   作ったら隣に生成の記録 .reference.source (テンプレート・profile・生成処理・生成物の SHA-256。sha256sum の形式) を書く。
#   scripts/lib/ensure-reference.sh はこれを sha256sum --check で照合し、違えば作り直す (古い生成物を使い続けないため)。
#   テンプレートの SHA-256 が profile の reference_base_sha256 と違えば止まる (改版に気づかないまま作り続けないため)。
#   新しい版を使うときは profile のその値を書き換える。生成の警告 (見出しの番号定義・受け皿のスタイル・想定外のパート・git の追跡) は
#   標準エラーに出すとともに .reference.warnings に記録し、ensure-reference.sh が build・diff のたびに出し直す。
#   作った後にテンプレートと reference.docx が git で無視されているか (git check-ignore) を確かめ、
#   追跡されている・無視されていなければ標準エラーに警告する (git の無い環境では黙って飛ばす)。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

ID="${1:-_default}"
PROFILE="data/journals/$ID/profile.yaml"
PATCH="main/00_setup/lib/patch_reference_docx.py"
SOURCE_RECORD="data/journals/$ID/.reference.source"
# 生成の警告の記録 (テンプレートの経路だけ。ensure-reference.sh が build・diff のたびに出し直す)
WARN_RECORD="data/journals/$ID/.reference.warnings"

if [ ! -f "$PROFILE" ]; then
    echo "エラー: $PROFILE がありません (data/journals/$ID/ を作りましたか)" >&2
    exit 1
fi

RUN="docker compose -f docker/docker-compose.yml run --rm -u $(id -u):$(id -g) -T pandoc"

# --- 雛形の種類を profile から読む (reference_base があればテンプレートから作る) ---
# 値の読み方は build と同じ journal_profile に任せる (YAML を sed で読むと引用符やコメントで外れる)。1 行に 1 つずつ出す
base_info="$($RUN python3 -c 'import sys
sys.path.insert(0, "main/00_setup/lib")
import journal_profile
p = journal_profile.load(sys.argv[1])
for k in ("reference_base", "reference_base_sha256", "reference_base_url", "reference_doc"):
    v = p.get(k)
    print("" if v is None else str(v).strip())' "$ID")"
{ IFS= read -r BASE || true; IFS= read -r BASE_SHA || true; IFS= read -r BASE_URL || true; IFS= read -r REF_DOC || true; } <<< "$base_info"

if [ -n "$BASE" ]; then
    TEMPLATE="data/journals/$ID/$BASE"
    OUT="data/journals/$ID/reference.docx"
    how_to_get() {
        echo "  取得元: ${BASE_URL:-(profile.yaml に reference_base_url がありません。誌の投稿規定のページを見てください)}" >&2
        echo "  そこから $BASE を取得して $TEMPLATE に置き、もう一度実行してください (テンプレートは git で追跡しません)" >&2
    }
    echo "[1/2] 雑誌が配るテンプレートを確かめる ($TEMPLATE)"
    if [ ! -f "$TEMPLATE" ]; then
        echo "エラー: テンプレート $TEMPLATE がありません (profile.yaml の reference_base: $BASE)。" >&2
        how_to_get
        exit 1
    fi
    sha="$(sha256sum "$TEMPLATE" | cut -d' ' -f1)"
    # 指紋が違えば止める。警告して作り続けると、警告は作り直す 1 回目の build にしか出ず、
    # 2 回目以降は生成の記録の照合が通って黙るので、改版で見出しの番号などが崩れても気づけない。
    # profile の reference_base_sha256 を新しい値に書き換えることが「新しい版を確かめる」という印になる。profile に sha が無ければ照合せずに作る
    if [ -n "$BASE_SHA" ] && [ "$sha" != "$(printf '%s' "$BASE_SHA" | tr 'A-F' 'a-f')" ]; then
        echo "エラー: テンプレートの SHA-256 が profile.yaml の reference_base_sha256 と違います (改版された可能性)。" >&2
        echo "  置いたもの: $sha" >&2
        echo "  profile   : $BASE_SHA" >&2
        echo "  学会テンプレートが改版されると、スタイル名や節の構造が変わって後処理が外れることがあります。" >&2
        echo "  新しい版を使うなら、$PROFILE の reference_base_sha256 を上の「置いたもの」の値に書き換えてから、もう一度実行してください。" >&2
        echo "  そのあと出てくる警告と、roundtrip の PDF の体裁 (2 段組・柱・見出しの番号・図表の題) を確かめてください。" >&2
        echo "  元の版に戻すなら、取得し直して置き直してください:" >&2
        how_to_get
        exit 1
    fi
    echo "[2/2] テンプレートから reference.docx を作る (体裁は焼き込まない。足りないスタイルの別名・見出しの番号定義・識別子の除去)"
    rm -f "$SOURCE_RECORD" "$WARN_RECORD"
    # 生成の警告 (見出しの番号定義・受け皿のスタイル・想定外のパートなど。どれもテンプレートの改版の兆し) は標準エラーに出しつつ記録し、
    # ensure-reference.sh が build・diff のたびに出し直す (作り直すときの 1 回だけでは、2 回目以降の build で気づけない)
    patch_err="$(mktemp "data/journals/$ID/.reference.stderr.XXXXXX")"
    if ! $RUN python3 "$PATCH" --base "$TEMPLATE" -o "$OUT" 2>"$patch_err"; then
        cat "$patch_err" >&2
        rm -f "$patch_err"
        echo "エラー: テンプレート $TEMPLATE から reference.docx を作れませんでした (上のエラー)。" >&2
        echo "  テンプレートが壊れているか、想定と違う版の可能性があります。取得し直すときは:" >&2
        how_to_get
        exit 1
    fi
    cat "$patch_err" >&2
    if grep -q "警告" "$patch_err"; then
        grep "警告" "$patch_err" > "$WARN_RECORD"
    fi
    rm -f "$patch_err"
    # 生成の記録 (sha256sum の形式)。ensure-reference.sh が sha256sum --check で照合する。
    # 生成処理の一覧を変えるときは、本スクリプトの SHA-256 も変わるので古い記録は自動で外れる
    tmp="$(mktemp "data/journals/$ID/.reference.source.XXXXXX")"
    sha256sum "$TEMPLATE" "$PROFILE" "data/journals/make-reference.sh" "$PATCH" \
        "main/00_setup/lib/docx_styles.py" "$OUT" > "$tmp"
    mv -f "$tmp" "$SOURCE_RECORD"
    # テンプレートと生成物が git で無視されているかを確かめ、追跡されている・無視されていないなら標準エラーに警告する
    # (学会の配布物とその加工物を git に載せない。.gitignore は誌のディレクトリの docx をまとめて外すが、名前や置き場所を
    #  変えた・.gitignore を書き換えたときに、git add -A で黙って追跡に入らないように)。git の無い環境・作業ツリーの外では黙って飛ばす
    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        for f in "$TEMPLATE" "$OUT"; do
            if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
                echo "警告: $f が git で追跡されています (学会の配布物とその生成物は追跡しない)。" \
                     "git rm --cached -- '$f' で追跡から外し、.gitignore で外れることを確かめてください" | tee -a "$WARN_RECORD" >&2
                continue
            fi
            rc=0
            git check-ignore -q -- "$f" || rc=$?
            if [ "$rc" -eq 1 ]; then
                echo "警告: $f が git で無視されていません (git add -A で追跡に入ります)。.gitignore に足してください" \
                     "(学会の配布物とその生成物は追跡しない)" | tee -a "$WARN_RECORD" >&2
            fi
        done
    fi
    echo "done: $OUT (生成の記録: $SOURCE_RECORD)"
    if [ "$REF_DOC" != "reference.docx" ]; then
        echo "  → data/journals/$ID/profile.yaml の reference_doc を 'reference.docx' に変更すると build/diff で使われます"
        echo "    (いまの値: '${REF_DOC:-(未指定)}')"
    fi
    exit 0
fi
# reference_base の無い誌に古い生成の記録が残っていれば消す (照合が毎回外れて作り直しを繰り返さないように)。警告の記録も
rm -f "$SOURCE_RECORD" "$WARN_RECORD"

echo "[1/3] pandoc 既定 reference.docx を取り出す ($ID)"
$RUN sh -c "pandoc -o /workspace/data/journals/$ID/.base-reference.docx --print-default-data-file reference.docx"

echo "[2/3] profile.yaml の体裁 + 差分スタイルを焼き込む"
# profile.yaml を読んで patch_reference_docx.py の引数へ変換し実行する (コンテナ内 python)。
# JID はコンテナへ -e で明示的に渡す (docker compose run はホスト環境変数を自動転送しない)。
docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" -T \
    -e JID="$ID" pandoc python3 - <<'PY'
import os, subprocess, sys

# 値の解釈 (真偽値 / 列挙 / 単位つき数値) は main/00_setup/lib/journal_profile.py に 1 つだけ置き、
# 焼き込み側 (本スクリプト) と検査側 (build / validate) で共有する。ここに写しを置くと
# 既定値が二重に定義され、片方だけ直したときに焼き込みと検査が食い違う。
sys.path.insert(0, "main/00_setup/lib")
import journal_profile as jp

jid = os.environ["JID"]
prof = jp.load(jid)

ls = jp.as_choice(prof.get("line_spacing"), {"single", "1.5", "double"}, "double", "line_spacing")
ln = jp.as_choice(prof.get("line_numbers"), {"none", "continuous", "per-page"}, "continuous", "line_numbers")
pn = jp.as_flag(prof.get("page_numbers"), "page_numbers")
font = str(prof.get("font") or "Times New Roman")
fs = jp.as_number(prof.get("font_size"), "12")
# 辺ごとの余白 (辞書形) は、テンプレートから作る誌 (reference_base) の照合にだけ書ける。焼き込みは四辺一律なので、
# 辞書を数に読むと最初の辺の値で黙って四辺をそろえてしまう。止める
if isinstance(prof.get("margins"), dict):
    sys.exit("エラー: profile の margins が辺ごとの辞書です。焼き込みは四辺一律の値だけなので、"
             "margins: 25mm のように 1 つの値で書いてください (辺ごとの余白はテンプレートを雛形にする誌 = reference_base でだけ書けます)")
mg = jp.as_number(prof.get("margins"), "25")
paper = jp.as_choice(prof.get("paper_size"), {"a4", "letter"}, "a4", "paper_size")

base = f"data/journals/{jid}/.base-reference.docx"
out = f"data/journals/{jid}/reference.docx"
cmd = ["python3", "main/00_setup/lib/patch_reference_docx.py", base, "-o", out,
       "--line-spacing", ls, "--line-numbers", ln, "--font", font,
       "--font-size", str(fs), "--margin", str(mg), "--paper", paper]
if pn:
    cmd.append("--page-numbers")
# 題・見出し・抄録の級数と色。text_styles が無い誌は引数を足さない (級数と色に手を加えない)
ts = prof.get("text_styles") or {}
# 辞書でない値は traceback ではなくキー名つきで止め、知らないキーは警告する
if not isinstance(ts, dict):
    sys.exit(f"エラー: profile の text_styles は辞書で書いてください (例: text_styles: {{uniform_size: true}})。いまの値: {ts!r}")
for k in sorted(set(ts) - {"uniform_size", "heading_color", "uniform_line_spacing"}):
    print(f"[警告] profile の text_styles.{k} は知らないキーなので読みません "
          "(uniform_size / heading_color / uniform_line_spacing のどれか。綴りを確かめてください)", file=sys.stderr)
if jp.as_flag(ts.get("uniform_size"), "text_styles.uniform_size"):
    cmd.append("--uniform-style-size")
hc = jp.as_choice(ts.get("heading_color"), {"keep", "black"}, "keep", "text_styles.heading_color")
if hc != "keep":
    cmd += ["--heading-color", hc]
# 段落スタイルが個別に持つ行送りを外し、文書全体の行送りにそろえる
if jp.as_flag(ts.get("uniform_line_spacing"), "text_styles.uniform_line_spacing"):
    cmd.append("--uniform-line-spacing")
print("  " + " ".join(cmd))
subprocess.run(cmd, check=True)
PY

echo "[3/3] 中間物を片付ける"
rm -f "data/journals/$ID/.base-reference.docx"

echo "done: data/journals/$ID/reference.docx"
# reference_doc が既に reference.docx を指していれば案内は要らない (build / diff が自動で生成するときも同じ)
ref_doc=$(sed -n 's/^reference_doc:[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$PROFILE" | head -n 1)
if [ "$ref_doc" != "reference.docx" ]; then
    echo "  → data/journals/$ID/profile.yaml の reference_doc を 'reference.docx' に変更すると build/diff で使われます"
    echo "    (いまの値: '${ref_doc:-(未指定)}')"
fi
