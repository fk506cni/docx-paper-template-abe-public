#!/bin/bash
# check-diff.sh — 差分エンジンの受入テスト (driver)
#
# 回帰スナップショット (scripts/baseline*.sh) の差分の段は旧版と新版が同じ原稿なので、差分エンジンが壊れても検出できない。
# ここでは旧版と新版の対 (data/dummy/regression/diff/<名前>/old.md・new.md。文の書き換え・大文字小文字だけの変更・表のセル・
# 表の追加と削除・番号つきの式の書き換えとラベルの付け替え・図の追加・脚注の書き換え・脚注の中の番号つきの式・ラベルと題の書き換え・
# 段抜きの Div) を実際の経路で差分 docx にし、性質 (削除・追加の色の位置と文字・番号と参照に ¿ が無い・目印のブックマークが
# 残らない・脚注の色) を照合する。本体は main/step03_diff/test_diff_engine.py (docx-paper-template-pandoc コンテナ内で実行)。
#
# 誌は _default。学会テンプレート data/journals/abe/ABETemplate.docx があれば abe でも回す (無ければ飛ばす。
# テンプレートは git で追跡しない)。どの誌も、使う直前に reference.docx を確かめる (build.sh / diff.sh と同じ)。
#
# 使い方:
#   scripts/check-diff.sh                   # 全フィクスチャ
#   scripts/check-diff.sh --only footnote   # このフィクスチャだけ (複数可)
#   scripts/check-diff.sh --keep jank/check-diff   # 差分 docx とログを残す
#   scripts/check-diff.sh --no-abe          # テンプレートがあっても abe を飛ばす
#   scripts/check-diff.sh --require-journal <誌>   # その誌のプロファイルが無ければ不合格にする (既定は黙って飛ばす。複数可)
#
# 終了コード: 0 = 全件合格 / 1 = 外れあり
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_FILE="docker/docker-compose.yml"
ABE=1
ARGS=()

usage() {
    # 2 行目から、最初のコメントでない行の手前までの頭書き (頭書きの行数が変わっても崩れない)
    awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --only) ARGS+=(--only "${2:?--only にフィクスチャの名前を指定してください}"); shift 2 ;;
        --keep) ARGS+=(--keep "${2:?--keep にディレクトリを指定してください}"); shift 2 ;;
        --no-abe) ABE=0; shift ;;
        --require-journal) ARGS+=(--require-journal "${2:?--require-journal に誌の id を指定してください}"); shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "エラー: 不明な引数 '$1'" >&2; usage; exit 1 ;;
    esac
done

# shellcheck source=lib/ensure-reference.sh
source scripts/lib/ensure-reference.sh
# reference.docx を profile から生成する誌で回す (bhi は BHI 版のテンプレートにある誌)。誌のプロファイルが無ければ黙って飛ばす
# (test_diff_engine.py も同じ条件で誌を選ぶ)
for j in _default bhi; do
    if [ -f "data/journals/$j/profile.yaml" ]; then
        ensure_reference_docx "$j"
    fi
done
if [ "$ABE" = 1 ] && [ -f data/journals/abe/ABETemplate.docx ]; then
    ensure_reference_docx abe
    ARGS+=(--abe)
else
    echo "-- abe は飛ばします (data/journals/abe/ABETemplate.docx が無いか --no-abe)"
fi

docker compose -f "$COMPOSE_FILE" run --rm -T -u "$(id -u):$(id -g)" pandoc \
    python3 main/step03_diff/test_diff_engine.py "${ARGS[@]}"
