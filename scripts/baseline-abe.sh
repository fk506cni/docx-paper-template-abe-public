#!/bin/bash
# baseline-abe.sh — ABE プロファイルの回帰スナップショット
#
# abe を scripts/baseline.sh に含めず専用にした理由は 2 つ:
#   - baseline.sh は誌を順に撮り、失敗すると止まる。abe は学会テンプレート (git で追跡しない) が無いと
#     build できないので、baseline.sh に含めるとテンプレートの無い環境で abe で止まり、後ろの誌が撮られない
#   - abe の動作例は入力ルートが data/dummy/abe で --article-type も要る
#
# 使い方: ABE_DIFF_REV=<commit> bash scripts/baseline-abe.sh [suffix]
# 比較 :  python3 scripts/compare-snapshots.py <pre の suffix> <post の suffix>
# 出力先: jank/baseline/abe__<suffix>/  (git 管理外)
#
# 【diff の旧版は ABE_DIFF_REV】動作例 data/dummy/abe/ は、ほかの誌の動作例 (data/dummy/) と履歴に入った時期が
# 違いうるので、旧版は別の変数で受け取る (ほかの誌の DIFF_REV を使い回して、旧版に原稿が無くて止まるのを避けるため)。
# data/dummy/abe/main.md があるコミットを ABE_DIFF_REV に渡す (無ければ下の案内が、最初に入れたコミットを示す)。
# 既定値は置かない (HEAD~1 などを既定にすると、コミットのたびに比較元が動く)。
set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
    cat <<'EOF'
使い方: ABE_DIFF_REV=<commit> bash scripts/baseline-abe.sh [suffix]

ABE プロファイルの回帰スナップショットを撮る。動作例 data/dummy/abe で build / diff / package (final) を回し
(--article-type original)、出力を jank/baseline/ に退避する。

  suffix 無し    jank/baseline/abe/ に退避 (着手前のベースライン)
  suffix 有り    jank/baseline/abe__<suffix>/ に退避 (変更後の比較用)
  -h, --help     この説明を出して終わる

diff の旧版は環境変数 ABE_DIFF_REV で決まる (既定値は無い。DIFF_REV は見ない)。data/dummy/abe/main.md を最初に入れた
コミットを渡す (clone した直後なら ABE_DIFF_REV=HEAD。差分は空になるが diff の経路は通る)。比較する 2 つは同じ ABE_DIFF_REV で撮ること。
段が失敗したら、その段の名前とログの末尾を出して止まる (ログ全体は退避先の *.log)。
abe 以外の誌は scripts/baseline.sh で撮る。
比較: docker compose -f docker/docker-compose.yml run --rm -u "$(id -u):$(id -g)" pandoc \
          python3 scripts/compare-snapshots.py <前の suffix> <後の suffix>
EOF
}

# --help を suffix として受け取って撮り始めないように、- で始まる引数は suffix にしない
case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    -*)        echo "エラー: 不明なオプション '$1' (suffix は - で始められません)" >&2; usage >&2; exit 1 ;;
esac
if [ $# -gt 1 ]; then
    echo "エラー: 引数は suffix の 1 つだけです (受け取った数: $#)" >&2; usage >&2; exit 1
fi

SUFFIX="${1:-}"
BASE="jank/baseline"
INPUT="data/dummy/abe"

# 段の出力はログに書き、失敗したら段の名前とログの末尾を画面に出して止める
# (set -e で止めるだけだと、何が失敗したかはログを開くまで分からない)
run_logged() {   # $1 = 段の名前 / $2 = ログ / $3 以降 = コマンド
    local name="$1" log="$2"; shift 2
    local rc=0
    "$@" >"$log" 2>&1 || rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "エラー: $name が失敗しました (終了コード $rc)。ログ: $log" >&2
        echo "---- ログの末尾 ----" >&2
        tail -n 15 "$log" >&2
        exit "$rc"
    fi
}

# diff の旧版を、撮り始める前に確かめる。未設定・旧版に原稿が無いなら、何を設定すればよいかを出して止まる
abe_rev_hint() {
    # data/dummy/abe/main.md を最初に入れたコミット (履歴にあれば)。案内に使うだけで、黙って既定値にはしない
    local first
    first="$(git log --diff-filter=A --format=%h -- "$INPUT/main.md" 2>/dev/null | tail -n 1)"
    if [ -n "$first" ]; then
        echo "  この作業ツリーの履歴で $INPUT/main.md を最初に入れたコミットは $first です" >&2
        echo "  (例: ABE_DIFF_REV=$first bash scripts/baseline-abe.sh <suffix>)。" >&2
    else
        echo "  この作業ツリーの履歴には $INPUT/main.md を入れたコミットがまだありません。" >&2
        echo "  動作例をコミットしてから、そのハッシュを ABE_DIFF_REV に渡してください。" >&2
    fi
    echo "  比較する 2 つは同じ ABE_DIFF_REV で撮ること。" >&2
}
if [ -z "${ABE_DIFF_REV:-}" ]; then
    echo "エラー: 環境変数 ABE_DIFF_REV (diff の旧版にするコミット) が設定されていません。" >&2
    echo "  動作例 $INPUT/ はほかの誌の DIFF_REV のコミットに無いことがあるので、ABE だけ別の変数で旧版を受け取ります。" >&2
    abe_rev_hint
    exit 1
fi
if ! git cat-file -e "$ABE_DIFF_REV:$INPUT/main.md" 2>/dev/null; then
    echo "エラー: diff の旧版 ABE_DIFF_REV=$ABE_DIFF_REV に $INPUT/main.md がありません。" >&2
    abe_rev_hint
    exit 1
fi

out="$BASE/abe${SUFFIX:+__$SUFFIX}"
rm -rf "$out" "data/output/abe"
mkdir -p "$out"

echo "===== baseline: abe -> $out (diff の旧版 ABE_DIFF_REV=$ABE_DIFF_REV) ====="
run_logged "build (abe)" "$out/build.log" \
    bash scripts/build.sh --journal abe --article-type original --input "$INPUT"
cp -a data/step01_figures "$out/step01_figures"
cp -a data/step02_build "$out/step02_build"
# diff も撮る。撮らないと package が data/step03_diff に残っている**別原稿の**差分 docx を
# manuscript-diff.docx として拾い、スナップショット間で本物でない差が出る。
run_logged "diff (abe)" "$out/diff.log" \
    bash scripts/diff.sh --journal abe --article-type original --skip-figures --input "$INPUT" "$ABE_DIFF_REV"
cp -a data/step03_diff "$out/step03_diff"
run_logged "package final (abe)" "$out/package-final.log" \
    bash scripts/package.sh --journal abe --article-type original --mode final --input "$INPUT"
cp -a "data/output/abe" "$out/output-final"
echo "===== baseline 完了: $out ====="
