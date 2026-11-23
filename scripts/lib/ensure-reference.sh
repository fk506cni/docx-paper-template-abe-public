# ensure-reference.sh — 使う直前に reference.docx が無ければ make-reference.sh で生成する
#
# ⚠ これは実行スクリプトではなく、source されるライブラリである。
#   利用側: scripts/build.sh, scripts/diff.sh
#   (scripts/package.sh は reference.docx を使わない。--build のときは build.sh を経由する)
#
# なぜ要るか: reference.docx は pandoc の既定 reference.docx に profile.yaml の体裁を焼き込んだ
#   生成物で、data/journals/make-reference.sh が何度回しても同じものを作る (zip の時刻を固定して
#   いるのでバイト単位で同じ)。生成物を置いていない作業ツリー (clone した直後など) でも build と
#   diff がそのまま通るよう、ここで作る。
#
# 生成するのは次の 3 つだけ:
#   - data/journals/_default/reference.docx (どの誌でも、継承するときの受け皿になる)
#   - 対象誌の profile.yaml の reference_doc が "reference.docx" (make-reference.sh が書く名前) で、
#     そのファイルが無いときの data/journals/<id>/reference.docx
#   - 対象誌が雑誌の配るテンプレートを雛形にする (profile の reference_base) とき、生成の元
#     (テンプレート・profile・生成処理) か生成物が、前に作ったときの記録 (data/journals/<id>/.reference.source) と
#     違えば作り直す。有無だけを見ると、追跡をやめても手元に残る古い生成物や、生成処理を直す前の生成物を使い続けるため。
#     テンプレートが無ければ make-reference.sh が取得の案内を標準エラーに出して止まり、build / diff も止まる。
#     テンプレートの SHA-256 が profile の reference_base_sha256 と違うとき (改版) も止まる (新しい版を使うなら profile の値を
#     書き換える)。作ったときの警告 (.reference.warnings) は、作り直さずに使うときも build・diff のたびに標準エラーへ出し直す
#   reference_doc が別の名前 (雑誌が配るテンプレートなど) を指していて、そのファイルが無いときは
#   生成しない。人が置くファイルを作り物で黙って置き換えないためで、build の警告に任せる。
#
# 前提: PROJECT_ROOT に cd してから source すること。呼び出し側は `set -euo pipefail` を前提とする
#   (生成に失敗したらその場で止まる)。

# make-reference.sh を回す。標準出力は捨てる (最後の「reference_doc を切り替えると…」の案内は
# 手で新しい誌を足すときのもので、ここでは当てはまらない)。エラーは標準エラーに出る。
# 2 つ目の引数は作る理由と動作 (表示用。既定は「が無いので生成します」)
_ensure_reference_make() {
    echo "-- data/journals/$1/reference.docx ${2:-が無いので生成します} (bash data/journals/make-reference.sh $1)"
    bash data/journals/make-reference.sh "$1" >/dev/null
}

# ensure_reference_docx <journal-id>
ensure_reference_docx() {
    local journal="$1" dir="data/journals/$1" info want base reason=""
    if [ ! -f "data/journals/_default/reference.docx" ]; then
        _ensure_reference_make _default
    fi
    if [ "$journal" = "_default" ]; then
        return 0
    fi
    # テンプレートから作った reference.docx: 生成の記録どおりなら (生成の元と生成物の SHA-256 が全部一致すれば) そのまま使う。
    # 照合はホストの sha256sum だけで済むので、コンテナは起こさない
    if [ -f "$dir/.reference.source" ]; then
        if sha256sum --check --status --strict "$dir/.reference.source" >/dev/null 2>&1; then
            # 作ったときの警告 (テンプレートの改版の兆し) を build・diff のたびに出し直す (作り直すときの 1 回だけ出すと、
            # 2 回目以降の build は見出しの番号が崩れても黙る)
            if [ -s "$dir/.reference.warnings" ]; then
                echo "-- data/journals/$journal/reference.docx を作ったときの警告 (テンプレートの改版の可能性。出力を確かめてください):" >&2
                sed 's/^/  /' "$dir/.reference.warnings" >&2
            fi
            return 0
        fi
        reason="の生成の元 (テンプレート・profile・生成処理) か生成物が前に作ったときと違うので作り直します"
    elif [ -f "$dir/reference.docx" ] && ! grep -Eq '^[^#]*reference_base' "$dir/profile.yaml" 2>/dev/null; then
        # 自前の reference.docx を持ち、テンプレートを雛形にしない誌 (そのまま使う。コンテナを起こさない)。
        # grep は「起こさなくてよい」ことの粗い判定で、当たったときは下で journal_profile に読ませて確かめる
        return 0
    fi
    # 対象誌が自前の reference.docx を使う設定か・テンプレートを雛形にするかは profile.yaml を読まないと分からない。
    # 読み方は build と同じ journal_profile に任せる (YAML を sed で読むと引用符やコメントで外れる)。
    info="$(docker compose -f docker/docker-compose.yml run --rm -T -u "$(id -u):$(id -g)" pandoc \
        python3 -c 'import sys
sys.path.insert(0, "main/00_setup/lib")
import journal_profile
p = journal_profile.load(sys.argv[1])
print(p.get("reference_doc") or "")
print(p.get("reference_base") or "")' "$journal")"
    { IFS= read -r want || true; IFS= read -r base || true; } <<< "$info"
    if [ "$want" != "reference.docx" ]; then
        return 0
    fi
    if [ -n "$base" ]; then
        if [ -z "$reason" ]; then
            if [ -f "$dir/reference.docx" ]; then
                reason="に生成の記録が無い (テンプレートから作ったものと確かめられない) ので作り直します"
            else
                reason="が無いので生成します"
            fi
        fi
        _ensure_reference_make "$journal" "$reason"
    elif [ ! -f "$dir/reference.docx" ]; then
        _ensure_reference_make "$journal"
    else
        # テンプレートを雛形にしなくなった誌に生成の記録だけが残っている。照合が毎回外れないように消す
        rm -f "$dir/.reference.source"
    fi
}
