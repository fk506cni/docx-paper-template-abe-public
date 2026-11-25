#!/bin/bash
# make-samples.sh — samples/ の出力のサンプル (同梱のサンプル論文から作った docx と、Word で作った PDF) を作り直す
#
# samples/ は、何も入れずに出力の見た目を確かめられるように置いている見本 (samples/README.md)。
# 原稿・誌のプロファイル・後処理を変えて出力が変わったら、このスクリプトで作り直して commit する。
#
#   --journal _default  汎用のサンプル (data/dummy/main.md) を _default で build し、クイックスタートと同じ書き換え
#                       (Twenty trials → Twenty-four trials) との差分を作る。docx と PDF を samples/_default/ に置く
#   --journal abe       src/ のサンプル論文を abe で build し (学会テンプレートが要る)、決まった 4 か所の書き換え
#                       (題の語・抄録の数・序論の語・表のセル) をした旧版との差分を作る。samples/abe/ には PDF だけを置く —
#                       abe の docx は学会テンプレートのスタイル・テーマ・番号の定義を持つので、このリポジトリでは再配布しない
#
# PDF は roundtrip.sh --skip-build --no-package (Google Drive と Windows の Word。任意の機能で、外向きの操作) で作り、
# data/products/main.pdf・main_diff.pdf を samples/<誌>/manuscript.pdf・manuscript-diff.pdf に写す。
#
# 見本は公開物に出るので、commit 済みの同梱のサンプルと処理からだけ作る。abe は src/ が指紋の一覧
# (scripts/lib/sample-files.sha256) と一致すること、両誌とも入力と処理 (src・data/dummy・data/journals・main・scripts・docker・samples) に
# commit していない変更が無いことを確かめてから組む。PDF まで作り終えたら samples/<誌>/SOURCE.txt に出所 (commit・入力と出力の
# SHA-256) を書く。公開物を作る側の検査がこの記録を原本と照らす (SOURCE.txt は公開物に出さない)。
#
# 使い方:
#   bash scripts/make-samples.sh --journal _default
#   bash scripts/make-samples.sh --journal abe
#   bash scripts/make-samples.sh --journal abe --no-pdf    # roundtrip を回さない (build と差分まで。PDF は作らない)
#
# 終了コード: 0 = 作り直した / 1 = 失敗 (build・差分・roundtrip が止まった、書き換えが当たらない、PDF ができない)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

JOURNAL=""
PDF=1

usage() {
    # 2 行目から、最初のコメントでない行の手前までの頭書き
    awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --journal) JOURNAL="${2:?--journal に _default か abe を指定してください}"; shift 2 ;;
        --no-pdf)  PDF=0; shift ;;
        -h|--help) usage; exit 0 ;;
        *)         echo "エラー: 不明な引数 '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

WORK="jank/samples"
mkdir -p "$WORK"

# 文字列の書き換え (固定文字列。ちょうど 1 回当たらなければ止める = 原稿が変わって書き換えが外れたことに気づくため)
replace_once() {
    local file="$1" from="$2" to="$3" n
    n="$(grep -c -F -- "$from" "$file" || true)"
    if [ "$n" != "1" ]; then
        # src/ がサンプルのままかは先に確かめるので、ここに来るのはサンプル自体を直したときだけ
        echo "エラー: $file に「$from」が ${n} 回あります (1 回のはず)。同梱のサンプルの本文を直したなら、このスクリプトの書き換えの語句も合わせてください" >&2
        exit 1
    fi
    # ホストの道具 (awk) だけで書き換える (README の要件は Docker・bash・git。正規表現ではなく固定文字列で探す)
    awk -v from="$from" -v to="$to" '
        !done && (i = index($0, from)) { $0 = substr($0, 1, i - 1) to substr($0, i + length(from)); done = 1 }
        { print }' "$file" > "$file.tmp"
    mv "$file.tmp" "$file"
}

case "$JOURNAL" in
    _default|abe) ;;
    "") echo "エラー: --journal を指定してください (_default か abe)" >&2; usage >&2; exit 1 ;;
    *)  echo "エラー: --journal は _default か abe です (指定: $JOURNAL)" >&2; exit 1 ;;
esac

# ---- 見本は commit 済みの同梱のサンプルと処理からだけ作る
# (見本は公開物に出る。私的な変更を含む作業ツリーや自分の原稿から作ると、Word の PDF に描かれた私的な文面が見本に入るおそれがある。
#  作り終えたら samples/<誌>/SOURCE.txt に出所 (commit・入力と出力の SHA-256) を書く)
if command -v sha256sum >/dev/null 2>&1; then
    hash_of() { sha256sum < "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
    hash_of() { shasum -a 256 < "$1" | cut -d' ' -f1; }
else
    echo "エラー: sha256sum も shasum もありません (見本の出所を記録できません)" >&2; exit 1
fi
sample_inputs() {   # 見本の入力 (出所の記録に載せ、書き出しで照らすファイル)
    case "$JOURNAL" in
        abe)      git ls-files -- src | grep -v -E '(^|/)(README\.md|\.gitkeep)$' | grep -v -x 'src/cover-letter.md' ;;
        _default) git ls-files -- data/dummy/main.md data/dummy/ref.bib data/dummy/figs ;;
    esac
}
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "エラー: git の作業ツリーではありません (見本は commit 済みの原稿と処理からだけ作ります)" >&2; exit 1
fi
if [ "$JOURNAL" = "abe" ] && ! bash scripts/remove-sample.sh --check >/dev/null 2>&1; then
    echo "エラー: src/ が同梱のサンプル論文と一致しません (scripts/lib/sample-files.sha256 で確かめた)。" >&2
    echo "  見本は同梱のサンプルからだけ作ります。自分の原稿の src/ では回さないでください。" >&2
    echo "  サンプルを直したのなら、直したファイルの行を一覧に足して commit してから回してください" >&2
    echo "  (bash scripts/remove-sample.sh --check で、合わないファイルが分かります)" >&2
    exit 1
fi
dirty="$(git status --porcelain --untracked-files=all -- src data/dummy data/journals main scripts docker samples 2>/dev/null || true)"
if [ -n "$dirty" ]; then
    echo "エラー: 見本の入力か処理に commit していない変更があります (見本は commit 済みのものからだけ作ります):" >&2
    printf '%s\n' "$dirty" | sed 's/^/   /' >&2
    echo "  commit してから回してください (見本を試すだけなら、このスクリプトではなく build.sh と diff.sh を直接回す)" >&2
    exit 1
fi
HEAD_COMMIT="$(git rev-parse HEAD)"

case "$JOURNAL" in
    _default)
        ROOT="data/dummy"
        OUT="samples/_default"
        OLD="$ROOT/main.md"
        NEW="$WORK/main-new.md"
        cp "$ROOT/main.md" "$NEW"
        replace_once "$NEW" "Twenty trials" "Twenty-four trials"
        BUILD_ARGS=(--journal _default)
        ;;
    abe)
        ROOT="src"
        OUT="samples/abe"
        OLD="$WORK/abe-old.md"
        NEW="$ROOT/main.md"
        if [ ! -f "$NEW" ]; then
            echo "エラー: $NEW がありません (同梱のサンプル論文を消した作業ツリーでは abe のサンプルは作れません)" >&2
            exit 1
        fi
        cp "$NEW" "$OLD"
        # 旧版 = サンプルから 4 か所を戻した形 (差分は「旧版 → サンプル」の書き換えとして色が付く)
        replace_once "$OLD" "a New Dimensional Scale" "a Dimensional Scale"
        replace_once "$OLD" "at 2.6 units" "at 2.5 units"
        replace_once "$OLD" "phenomenon, yet it has never been" "phenomenon, yet it has rarely been"
        replace_once "$OLD" "| Gentle touch  |      5 |            1.2 |" "| Gentle touch  |      5 |            1.1 |"
        BUILD_ARGS=(--journal abe --article-type original)
        ;;
    "")
        echo "エラー: --journal を指定してください (_default か abe)" >&2; usage >&2; exit 1 ;;
    *)
        echo "エラー: --journal は _default か abe です (指定: $JOURNAL)" >&2; exit 1 ;;
esac

echo "== サンプルの出力を作り直します: journal=$JOURNAL 入力ルート=$ROOT → $OUT/ =="
bash scripts/build.sh "${BUILD_ARGS[@]}" --input "$ROOT"
bash scripts/diff.sh "$OLD" "$NEW" "${BUILD_ARGS[@]}" --input "$ROOT"

mkdir -p "$OUT"
if [ "$JOURNAL" = "_default" ]; then
    cp data/step02_build/main.docx "$OUT/manuscript.docx"
    cp data/step03_diff/main_diff.docx "$OUT/manuscript-diff.docx"
    # 見本の docx からは、pandoc が原稿のメタデータを書き込むユーザー定義の文書のプロパティ (docProps/custom.xml。
    # 相互参照の設定と、文献ファイル・引用様式などの相対パス) を外す。Word の表示には関係しない作業用の値で、
    # 公開物の書き出しの検査 (バイナリのメタデータ) が 1 項目ずつ当てるため
    docker compose -f docker/docker-compose.yml run --rm -T -u "$(id -u):$(id -g)" pandoc \
        python3 - "$OUT/manuscript.docx" "$OUT/manuscript-diff.docx" <<'PY'
import os, re, sys, zipfile
for path in sys.argv[1:]:
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "docProps/custom.xml":
                continue
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = re.sub(rb'<Override[^>]*PartName="/docProps/custom\.xml"[^>]*/>', b"", data)
            elif item.filename == "_rels/.rels":
                data = re.sub(rb'<Relationship[^>]*Target="/?docProps/custom\.xml"[^>]*/>', b"", data)
            zout.writestr(item, data)
    os.replace(tmp, path)
PY
    echo "  写した: $OUT/manuscript.docx・$OUT/manuscript-diff.docx (ユーザー定義の文書のプロパティを外した)"
fi

if [ "$PDF" = 0 ]; then
    echo "-- --no-pdf: PDF は作りません ($OUT/ の PDF は前のまま)"
    echo "   出所の記録 ($OUT/SOURCE.txt) も書き換えません。docx だけを作り直した見本は記録と合わないので、書き出しの検査 (9) が止めます"
    echo "   (公開物に出すなら PDF まで作り直す)"
    exit 0
fi

# roundtrip が今回作った PDF だけを写す (前の PDF が残っていても、変換に失敗したときに古いものを写さない)
STAMP="$WORK/.roundtrip-start"
touch "$STAMP"
INPUT_ROOT="$ROOT" bash scripts/roundtrip.sh --skip-build --no-package
for pair in "main.pdf:manuscript.pdf" "main_diff.pdf:manuscript-diff.pdf"; do
    src="data/products/${pair%%:*}"
    dst="$OUT/${pair##*:}"
    if [ ! -f "$src" ] || [ ! "$src" -nt "$STAMP" ]; then
        echo "エラー: $src が今回の roundtrip で作られていません (Word の変換を確かめてください)" >&2
        exit 1
    fi
    cp "$src" "$dst"
    echo "  写した: $dst"
done

# 出所の記録 (公開物には出さない)。書きかけのファイルは $OUT の外 ($WORK) に置く ($OUT の中に置くと、出力の一覧に自分が入る)
REC="$OUT/SOURCE.txt"
REC_TMP="$WORK/SOURCE-$JOURNAL.txt.tmp"
{
    echo "# $OUT/ の出所 (scripts/make-samples.sh が書く。公開物を作る側の検査が原本と照らす。"
    echo "# 公開物には出さない。手で書き換えない。入力が変わったら make-samples.sh で作り直す)"
    printf 'journal\t%s\n' "$JOURNAL"
    printf 'commit\t%s\n' "$HEAD_COMMIT"
    printf 'clean\tyes\n'
    sample_inputs | while IFS= read -r f; do printf 'input\t%s\t%s\n' "$(hash_of "$f")" "$f"; done
    find "$OUT" -type f ! -name SOURCE.txt | LC_ALL=C sort | while IFS= read -r f; do
        printf 'output\t%s\t%s\n' "$(hash_of "$f")" "$f"
    done
} > "$REC_TMP"
mv "$REC_TMP" "$REC"
echo "  書いた: $REC (出所の記録)"
echo "== 完了: $OUT/ (samples/README.md の表と合っているかを確かめて commit する) =="
