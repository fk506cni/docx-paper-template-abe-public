#!/bin/bash
# check-csl.sh — 雑誌 CSL の出力を規定の公式例と突き合わせる受入テスト (driver)
#
# 引用様式は投稿可否に直結するため、投稿規定に載っている出力例そのものを期待値として持ち、
# citeproc の実出力と 1 文字ずつ照合する。本文の引用の形などの誌ごとの違いはフィクスチャの check.yaml に書く。
# 本体は main/step02_build/check_csl.py (docx-paper-template-pandoc コンテナ内で実行)。
#
# 使い方:
#   scripts/check-csl.sh                                  # 既定の誌 abe を data/dummy/abe-csl で検証
#   scripts/check-csl.sh --journal <id>                   # 誌 <id> を data/dummy/<id>-csl で検証 (フィクスチャの既定)
#   scripts/check-csl.sh --journal abe --fixture data/dummy/abe-csl
#   scripts/check-csl.sh --docx data/step02_build/main.docx   # OOXML の書式も実測する (フィクスチャをビルドした後で)
#
# --docx を付けると docx を直接見て、本文の引用の形 (check.yaml の citation_form。abe = 角括弧で上付きでないか /
# superscript の誌 = 番号が上付きか) と、文献リストの文字と太字・斜体 (abe の巻の太字) を検査する。
# check.yaml に bibliography_label があれば、文献の番号の形 (abe = [1] / 番号 + ピリオドの誌 = 1.) と、docx では「番号 + 区切り + 本文」
# (区切りは profile の bibliography.label_separator: tab なら TAB、既定なら空白 + TAB) も照合する。
# 先に対象のフィクスチャを docx 化しておくこと:
#   bash scripts/build.sh --input data/dummy/abe-csl --journal abe
#
# 終了コード: 0 = 全件一致 / 1 = 不一致あり (差異は行内 diff と相違文字のコードポイントで出る)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_FILE="docker/docker-compose.yml"
JOURNAL="abe"
FIXTURE=""          # 既定は data/dummy/<journal>-csl (引数を読んだ後に決める)
DOCX=""

usage() {
    cat <<'EOF'
使い方: scripts/check-csl.sh [オプション]

オプション:
  --journal <id>    雑誌プロファイル (data/journals/<id>)。既定: abe
  --fixture <dir>   main.md / ref.bib / expected.txt (+ 任意で check.yaml) を置いたフィクスチャ。
                    既定: data/dummy/<journal>-csl
  --docx <path>     フィクスチャからビルドした docx の OOXML も実測する
                    (本文の引用の形 = check.yaml の citation_form と、文献リストの文字と太字・斜体。
                     check.yaml に bibliography_label があれば文献の「番号 + 区切り + 本文」の形も)
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --journal) JOURNAL="${2:?--journal に id を指定してください}"; shift 2 ;;
        --fixture) FIXTURE="${2:?--fixture にディレクトリを指定してください}"; shift 2 ;;
        --docx)    DOCX="${2:?--docx に docx のパスを指定してください}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *)         echo "エラー: 不明な引数 '$1'" >&2; usage; exit 1 ;;
    esac
done

FIXTURE="${FIXTURE:-data/dummy/${JOURNAL}-csl}"

if [ ! -d "data/journals/$JOURNAL" ]; then
    echo "エラー: 雑誌プロファイル 'data/journals/$JOURNAL' がありません。" >&2
    exit 1
fi
if [ ! -f "$FIXTURE/expected.txt" ]; then
    echo "エラー: フィクスチャ '$FIXTURE/expected.txt' がありません。" >&2
    exit 1
fi

if [ -n "$DOCX" ] && [ ! -f "$DOCX" ]; then
    echo "エラー: docx '$DOCX' がありません。" >&2
    echo "  先に 'bash scripts/build.sh --input $FIXTURE --journal $JOURNAL' を実行してください。" >&2
    exit 1
fi

docker compose -f "$COMPOSE_FILE" run --rm -u "$(id -u):$(id -g)" pandoc \
    python3 main/step02_build/check_csl.py --journal "$JOURNAL" --fixture "$FIXTURE" \
    ${DOCX:+--docx "$DOCX"}
