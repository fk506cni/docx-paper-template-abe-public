#!/bin/bash
# remove-sample.sh — src/ に同梱したサンプル論文のファイルを消す (自分の論文を書き始める前に 1 回)
#
# サンプル論文は ABE の Original Paper の体裁の架空の論文 (TJD/THS のパロディ)。動作例 data/dummy/abe/ はそこから TJD の挿絵を除いた同じ論文
# (そちらは試験に使うので消さない)。
#
# 消すのは、中身 (SHA-256) が同梱のサンプルと一致するファイルだけ。サンプルとは
#   - サンプルの一覧 (scripts/lib/sample-files.sha256) に載っている src/ のサンプル論文のファイル
#   - 動作例 data/dummy/ (汎用のサンプル: 直下の *.md・ref.bib・figs/ の下) と data/dummy/abe/ (*.md・ref.bib・figs/・forms/・
#     supplementary/ の下) のいまのファイル (README の案内で汎用のサンプルを src/ に写したときの消し残しも消す)
# 書き換えたファイルや、同じ名前で置いた自分のファイルは消さずに「残した」と出す。何度回しても自分のファイルは消えない。
# 入力ルートからのパスのどこかがリンクなら、そのファイルは消さない (リンクの先は自分のファイルかもしれない。src/figs のような
# ディレクトリのリンクも含む)。
# 入力ルートが data/dummy/ の下 (動作例と試験用のファイルそのもの) なら何も消さない。
# このスクリプトで中身を消して空になった supplementary/ は消す (figs/ は残す)。
# コンテナは使わない (sha256sum、無ければ shasum -a 256)。
#
# 判定の規則は main/step05_package/sample_files.py (package.py と試験が使う) と同じ。片方を直したらもう片方も直し、
# main/step05_package/test_sample_gate.py で両方が同じファイルを消し残しとみなすことを確かめる。
#
# package.sh は、入力ルートの main.md がサンプルではないのにサンプルのほかのファイル (カバーレター・回答書・補足資料・
# 文献・図・書式) が残っていると、最終モードで止まってこのスクリプトを案内する (草稿モードでは注意だけ)。
#
# 使い方:
#   bash scripts/remove-sample.sh               # src/ のサンプルのファイルを消す
#   bash scripts/remove-sample.sh --dry-run     # 消すもの・残すものの一覧だけを出す (何も消さない)
#   bash scripts/remove-sample.sh --input <dir> # src/ ではなく <dir> を見る (サンプルを別の場所に写したとき。リポジトリの最上位からのパス)
#   bash scripts/remove-sample.sh --check       # (保守用) 一覧が今の src/ のサンプルと合っているかを確かめる (一覧だけを見る)。
#                                               #   合わなければ終了コード 1 (サンプルを直したら一覧に行を足す)
#
# 一覧の書式: 「SHA-256<空白>入力ルートからの相対パス」の行 (sha256sum の出力と同じ。sha256sum -b の「*パス」も読む)。
#   行末の CR は除き、16 進の大文字は小文字とみなし、パスは 1 つ目の空白の並びの後の残り全部 (空白を含む名前も読む)。
#   # で始まる行は読まない。形の合わない行は読まない (注意を出す)。入力ルートの外を指す行 (絶対パス・..) があれば何もせずに止まる。
#   同じパスの行が 2 つ以上あれば、どれかと一致すればサンプルとみなす (公開した版ごとのサンプルを見分けるため)。
#   src/ のサンプルはコメントを data/dummy/abe/ と書き分けてあるので中身が違う。サンプルを直したら、直したファイルの行を足す
#   (公開した版の行は消さない)。src/ で:
#     sha256sum <直したファイル> >> ../scripts/lib/sample-files.sha256   (足したら --check で確かめる)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

LIST="scripts/lib/sample-files.sha256"
ROOT="src"
MODE="remove"

usage() {
    cat <<'EOF'
使い方: bash scripts/remove-sample.sh [--dry-run | --check] [--input <dir>]

src/ に同梱したサンプル論文のファイル (と、src/ に写した data/dummy/ の動作例のファイル) のうち、
中身がサンプルと同じものだけを消す。書き換えたファイル・同じ名前の自分のファイル・リンクは消さない
(何度回しても自分のファイルは消えない)。

オプション:
  --dry-run       消すもの・残すものの一覧だけを出す (何も消さない)
  --input <dir>   src/ ではなく <dir> を見る (サンプルを別の場所に写したとき。リポジトリの最上位からのパス)
  --check         (保守用) サンプルの一覧 (scripts/lib/sample-files.sha256) が今の入力ルートの中身と
                  合っているかを確かめる (一覧だけを見る)。合わなければ終了コード 1
  -h, --help      この説明を出す
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) MODE="dry-run"; shift ;;
        --check)   MODE="check"; shift ;;
        --input)   ROOT="${2:?--input にディレクトリを指定してください}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *)         echo "エラー: 不明な引数 '$1'" >&2; usage >&2; exit 1 ;;
    esac
done
ROOT="${ROOT%/}"

if [ ! -f "$LIST" ]; then
    echo "エラー: サンプルの一覧 $LIST がありません。" >&2
    exit 1
fi
if [ ! -d "$ROOT" ]; then
    echo "エラー: $ROOT/ がありません (--input はリポジトリの最上位からのパス)。" >&2
    exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
    hash_of() { sha256sum < "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
    hash_of() { shasum -a 256 < "$1" | cut -d' ' -f1; }
else
    echo "エラー: sha256sum も shasum もありません (ファイルの中身を確かめられないので、何も消しません)。" >&2
    exit 1
fi

# ---- 候補 (相対パスと SHA-256 の組)。bash 3.2 でも動くよう連想配列は使わない
cand_rel=()
cand_sha=()
list_rel=()     # 一覧のパス (--check が見る)
LINE_RE='^([0-9A-Fa-f]{64})[[:space:]]+\*?(.+)$'
n_entries=0
while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in ''|'#'*) continue ;; esac
    if [[ $line =~ $LINE_RE ]]; then
        sha="$(printf '%s' "${BASH_REMATCH[1]}" | tr 'A-F' 'a-f')"
        rel="${BASH_REMATCH[2]}"
        rel="${rel%"${rel##*[![:space:]]}"}"     # 行末の空白を除く
    else
        echo "[注意] $LIST の形の合わない行を読み飛ばしました: '$line'" >&2
        continue
    fi
    # 一覧の行は「入力ルートからの相対パス」だけを受け付ける (外を指す行で入力ルートの外を消さないため)
    case "$rel" in
        /*|..|../*|*/../*|*/..|[A-Za-z]:[\\/]*)
            echo "エラー: $LIST の行のパスが入力ルートの外を指しています: '$rel' (何も消しません)" >&2
            exit 1 ;;
    esac
    n_entries=$((n_entries + 1))
    cand_rel+=("$rel"); cand_sha+=("$sha"); list_rel+=("$rel")
done < "$LIST"
if [ "$n_entries" -eq 0 ]; then
    echo "エラー: サンプルの一覧 $LIST に行がありません。" >&2
    exit 1
fi

# 入力ルートが data/dummy/ の下か (動作例と試験用のファイルそのものは消さない)
under_dummy=0
root_abs="$(cd "$ROOT" && pwd -P)"
if [ -d data/dummy ]; then
    dummy_abs="$(cd data/dummy && pwd -P)"
    case "$root_abs/" in "$dummy_abs/"*) under_dummy=1 ;; esac
fi

# 動作例のファイルを候補に足す (--check は一覧だけを見るので足さない)
add_dummy() {   # $1 = 動作例のディレクトリ、残り = 「*.md」などの直下の glob か「figs/」(その下のすべて)
    local base="$1" pat f
    shift
    [ -d "$base" ] || return 0
    for pat in "$@"; do
        case "$pat" in
            */)
                [ -d "$base/${pat%/}" ] && [ ! -L "$base/${pat%/}" ] || continue
                while IFS= read -r f; do
                    cand_rel+=("${f#"$base"/}"); cand_sha+=("$(hash_of "$f")")
                done < <(find "$base/${pat%/}" -type f | LC_ALL=C sort)
                ;;
            *)
                for f in "$base"/$pat; do
                    [ -f "$f" ] && [ ! -L "$f" ] || continue
                    cand_rel+=("${f#"$base"/}"); cand_sha+=("$(hash_of "$f")")
                done
                ;;
        esac
    done
}
if [ "$MODE" != "check" ] && [ "$under_dummy" -eq 0 ]; then
    add_dummy data/dummy '*.md' ref.bib figs/
    add_dummy data/dummy/abe '*.md' ref.bib figs/ forms/ supplementary/
fi

has_link() {   # 入力ルートからのパス $1 のどこかの部分がリンクか (入力ルートそのものは見ない)
    local cur="$ROOT" rest="$1" part
    while :; do
        part="${rest%%/*}"
        cur="$cur/$part"
        [ -L "$cur" ] && return 0
        [ "$part" = "$rest" ] && return 1
        rest="${rest#*/}"
    done
}
is_candidate() {   # $1 = 相対パス, $2 = SHA-256
    local k
    for k in "${!cand_rel[@]}"; do
        [ "${cand_rel[$k]}" = "$1" ] && [ "${cand_sha[$k]}" = "$2" ] && return 0
    done
    return 1
}

# 見るパス (重複を除いて候補の順。--check は一覧のパスだけ)
paths=()
if [ "$MODE" = "check" ]; then
    src_list=("${list_rel[@]}")
else
    src_list=("${cand_rel[@]}")
fi
for rel in "${src_list[@]}"; do
    seen=0
    for q in ${paths[@]+"${paths[@]}"}; do
        [ "$q" = "$rel" ] && { seen=1; break; }
    done
    [ "$seen" -eq 1 ] || paths+=("$rel")
done

matched=()     # 中身がサンプルと一致するファイル (消す対象)
kept=()        # 同じパスにあるが中身が違う・リンクのファイル (残す)
absent=()      # 一覧にあるが無いファイル (--check が見る)
for rel in "${paths[@]}"; do
    f="$ROOT/$rel"
    if has_link "$rel"; then
        kept+=("$rel")
    elif [ -f "$f" ]; then
        if is_candidate "$rel" "$(hash_of "$f")"; then
            matched+=("$rel")
        else
            kept+=("$rel")
        fi
    elif [ -e "$f" ]; then
        kept+=("$rel")
    else
        absent+=("$rel")
    fi
done

if [ "$MODE" = "check" ]; then
    if [ "${#kept[@]}" -eq 0 ] && [ "${#absent[@]}" -eq 0 ]; then
        echo "一覧 ($LIST) は $ROOT/ のサンプル ${#paths[@]} ファイルと一致します。"
        exit 0
    fi
    echo "一覧 ($LIST) が $ROOT/ と合っていません (サンプルを直したら、直したファイルの行を一覧に足してください):" >&2
    for rel in ${kept[@]+"${kept[@]}"}; do echo "  中身が違う: $ROOT/$rel" >&2; done
    for rel in ${absent[@]+"${absent[@]}"}; do echo "  無い:       $ROOT/$rel" >&2; done
    exit 1
fi

if [ "$under_dummy" -eq 1 ]; then
    echo "== $ROOT/ は data/dummy/ の下 (動作例と試験用のファイル) なので、何も消しません =="
    exit 0
fi

if [ "$MODE" = "dry-run" ]; then
    echo "== サンプルのファイルの一覧 ($ROOT/。--dry-run なので何も消しません) =="
else
    echo "== サンプルのファイルを消します ($ROOT/) =="
fi
removed_supp=0
for rel in ${matched[@]+"${matched[@]}"}; do
    if [ "$MODE" = "dry-run" ]; then
        echo "  消す:   $ROOT/$rel"
    else
        rm -f -- "$ROOT/$rel"
        echo "  消した: $ROOT/$rel"
        case "$rel" in supplementary/*) removed_supp=1 ;; esac
    fi
done
for rel in ${kept[@]+"${kept[@]}"}; do
    why="中身がサンプルと違うので、あなたのファイルとみなし"
    has_link "$rel" && why="パスにリンクを含むので (リンクの先はあなたのファイルかもしれない)、触らずに"
    if [ "$MODE" = "dry-run" ]; then
        echo "  残す:   $ROOT/$rel (${why}ます)"
    else
        echo "  残した: $ROOT/$rel (${why}ました)"
    fi
done
if [ "${#matched[@]}" -eq 0 ]; then
    echo "  消すファイルはありません (サンプルのファイルは残っていません)。"
fi

# このスクリプトで中身を消して空になった supplementary/ は消す (補足資料が無い論文で、空のフォルダを残さないため)
supp="$ROOT/supplementary"
if [ "$removed_supp" -eq 1 ] && [ -d "$supp" ] && [ ! -L "$supp" ] && [ -z "$(ls -A "$supp")" ]; then
    rmdir "$supp"
    echo "  消した: $supp/ (空になったため)"
fi

if [ "$MODE" = "remove" ] && [ "${#matched[@]}" -gt 0 ]; then
    # サンプルの main.md を書き換えて使っている人が回すと、main.md は残るが、その main.md が引く文献・図は消える
    if [ -f "$ROOT/main.md" ]; then
        echo ""
        echo "[注意] $ROOT/main.md は残しましたが (中身がサンプルと違うため)、サンプルのほかのファイルは消しました。"
        echo "       サンプルを書き換えて使っているなら、消えたファイルだけを戻せます (書き換えは戻りません):"
        echo "         git ls-files --deleted $ROOT | xargs git checkout --"
    fi
    echo ""
    echo "サンプルから作った生成物 (data/step01_figures/・data/step02_build/・data/step03_diff/・data/output/<誌>/) は残っています。"
    echo "自分の原稿で build・diff・package を回すと作り直されます (要らなければ消してかまいません)。"
fi
