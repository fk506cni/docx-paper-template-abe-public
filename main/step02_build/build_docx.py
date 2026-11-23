#!/usr/bin/env python3
"""build_docx.py — 1 つの Markdown 原稿を投稿用 docx へ変換する (コンテナ内本体)。

docs/architecture.md §2.2。pandoc (crossref → generic-style.lua → citeproc) で docx 化し、postprocess.py で
OOXML 後処理 (表罫線・ネイティブ SVG 埋込・テキストボックス) を適用する。
docx-paper-template-pandoc コンテナ内で実行する (scripts/build.sh が driver)。

雑誌プロファイル (data/journals/<id>/profile.yaml) から reference.docx と CSL を解決する。
profile の csl / reference_doc が null・不在なら _default のものを継承する (docs/profile-schema.md)。

使い方:
    python3 build_docx.py --input-root data/dummy --journal _default \
        --doc main.md --out data/step02_build/main.docx [--no-embed-svg] [--no-relocate]
"""

import argparse
import hashlib
import os
import secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import postprocess  # noqa: E402

# profile の読み込み・既定値・記事種別解決は共通モジュールに集約 (docs/profile-schema.md)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
import journal_profile  # noqa: E402

JOURNALS_DIR = Path("data/journals")
DEFAULT_ID = "_default"
DEFAULTS_YAML = "main/00_setup/defaults.yaml"
GENERIC_FILTER = "main/00_setup/filters/generic-style.lua"
UNNUMBERED_FILTER = "main/00_setup/filters/unnumbered-style.lua"
WIDE_FILTER = "main/00_setup/filters/wide-blocks.lua"


def _inherited_layout_mismatches(journal_id):
    """journal_id の体裁キーが _default と食い違う箇所を [(キー, 誌の値, _default の値)] で返す。

    reference.docx を _default から継承すると、profile.yaml に書いた体裁は
    一切効かない。どのキーが効いていないのかを名前で示さないと利用者が気づけない。
    体裁キーの一覧と値の解釈は journal_profile 側が正 (docs/profile-schema.md)。
    """
    own = journal_profile.load(journal_id)
    default = journal_profile.load(DEFAULT_ID)
    out = []
    for key in journal_profile.LAYOUT_KEYS:
        mine, theirs = own.get(key), default.get(key)
        if mine is not None and str(mine).strip().lower() != str(theirs).strip().lower():
            out.append((key, mine, theirs))
    return out


def _warn_stale_reference(journal_id, reference_doc):
    """雑誌固有 reference.docx の実体裁が profile.yaml とずれていたら警告する。

    体裁は reference.docx に焼き込む設計なので、profile.yaml を編集して
    make-reference.sh の再実行を忘れると古い体裁のまま投稿まで進む。_inherited_layout_mismatches の
    警告は「_default を継承した」場合しか捕まえられないため、「自誌の reference.docx はあるが古い」
    場合をここで捕まえる (BHI は行間・行番号・ページ番号がいずれも規定必須)。
    """
    profile = journal_profile.load(journal_id)
    hint = journal_profile.layout_fix_hint(journal_id, profile)
    for key, want, got in journal_profile.layout_mismatches(profile, reference_doc):
        print(f"  警告: {reference_doc} の体裁が profile.yaml と食い違っています "
              f"({key}: profile={want!r} != reference.docx={got!r})。{hint}")


def post_citeproc_args(profile, reference_doc):
    """citeproc の後に掛けるフィルタの pandoc の引数を返す (build と diff が共用する)。

    headings.unnumbered_style があれば、{.unnumbered} の見出しをその段落スタイルにするフィルタ
    (filters/unnumbered-style.lua) を掛ける。citeproc が足す文献の見出しも {.unnumbered} なので citeproc の後に置く。
    layout.columns (段組) があれば、段抜き (`.wide` の図と `::: wide` の Div) に目印を付けるフィルタ
    (filters/wide-blocks.lua) を掛ける (後処理 layout.py が節の区切りにする)。段組の無い誌では `.wide` は何もしない。
    キーの無い誌には何も足さない (pandoc の引数も出力も変わらない)。
    reference.docx にそのスタイルが無いと、pandoc は本文と同じ書式の段落スタイルを自動で作り、見出しに見えなくなるので警告する。
    """
    args = []
    style = journal_profile.unnumbered_style(profile)
    if style:
        _warn_missing_style(reference_doc, style, "headings.unnumbered_style")
        args += ["-M", f"unnumbered-style={style}", "--lua-filter", UNNUMBERED_FILTER]
    if journal_profile.layout(profile):
        args += ["--lua-filter", WIDE_FILTER]
    return args


def crossref_defaults(profile, path):
    """crossref (pandoc-crossref の設定の誌ごとの上書き) を path に「metadata だけを書いた defaults」として書き、
    (pandoc の引数 ["--defaults", path], ログに出す 1 行) を返す (build と diff が共用する)。crossref の無い誌は何も書かずに ([], None)。

    defaults.yaml の後に渡すと同じ名前の値を上書きする。--metadata-file は defaults.yaml の metadata (-M と同じ強さ) に負けて
    黙って効かず、-M figureTitle=… は defaults の同じキーと一覧になって pandoc-crossref が止まる。
    呼び出し側は pandoc の後に path を消す。
    """
    import yaml

    cfg = journal_profile.crossref(profile)
    if not cfg:
        return [], None
    Path(path).write_text(
        "# crossref (誌の profile.yaml) から作った pandoc の defaults。build / diff が書いて使い終わったら消す\n"
        + yaml.safe_dump({"metadata": cfg}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    note = "  crossref (誌の上書き): " + ", ".join(f"{k}={v!r}" for k, v in cfg.items())
    return ["--defaults", str(path)], note


def caption_options(profile, reference_doc=None):
    """図表の題と凡例・式番号・文献の番号の区切り の postprocess.process_docx の引数を返す
    (build と diff が共用する)。

    式番号の右タブを合わせる「本文の節の段の幅」は reference.docx の本文の節から取る (equation_column_twip。
    段組の節を組み立てない回答書・カバーレターでも本文と同じ基準で右タブをずらすため)。equations.style の無い誌では読まない。
    """
    equation_style = journal_profile.equation_style(profile)
    equation_column_twip = None
    if equation_style and reference_doc is not None:
        import layout
        equation_column_twip = layout.reference_body_column_twip(profile, reference_doc)
    return {
        "table_legend_position": journal_profile.table_legend_position(profile),
        "figure_keep_together": journal_profile.figures_keep_together(profile),
        "equation_style": equation_style,
        "equation_column_twip": equation_column_twip,
        "bibliography_label_separator": journal_profile.bibliography_label_separator(profile),
    }


def layout_for(profile, reference_doc, is_manuscript):
    """この文書に段組の節を組み立てるなら layout.prepare() の値を、組み立てないなら None を返す (build と diff が共用)。

    layout.scope が manuscript (既定) なら本文 (main.md と差分) だけ。all ならカバーレターと回答書も。
    """
    cfg = journal_profile.layout(profile)
    if cfg is None or (cfg["scope"] == "manuscript" and not is_manuscript):
        return None
    import layout
    return layout.prepare(profile, reference_doc)


def _warn_missing_style(reference_doc, name, key):
    """reference.docx に段落スタイル name が無ければ警告する (名前で引く。ID はテンプレートごとに違う)。"""
    import zipfile

    import docx_styles
    from lxml import etree

    try:
        with zipfile.ZipFile(reference_doc) as z:
            styles = etree.fromstring(z.read("word/styles.xml"))
        found = docx_styles.style_by_name(styles, name, "paragraph") is not None
    except Exception as exc:                                        # noqa: BLE001
        print(f"  警告: {reference_doc} のスタイルを読めませんでした ({exc})。{key} の確認を省きます")
        return
    if not found:
        print(f"  警告: {key} の段落スタイル '{name}' が {reference_doc} にありません。"
              "pandoc が本文と同じ書式で自動定義するので、番号なしの見出しが見出しに見えなくなります")


def _resolve_asset(journal_id, profile_value, default_rel, kind):
    """雑誌アセット (reference.docx / CSL) を解決する。

    profile_value が指す雑誌固有ファイルがあればそれを、無ければ _default のものを返す。
    """
    if profile_value:
        cand = JOURNALS_DIR / journal_id / profile_value
        if cand.is_file():
            if kind == "reference_doc":
                # 焼き込み済みの体裁が profile.yaml とずれていないか検算する
                _warn_stale_reference(journal_id, cand)
            return cand
        print(f"  警告: {kind}='{cand}' が無いため _default を使用します")
    elif kind == "csl":
        # csl: null は _default (AMA 11th) を継承する。誌の規定が別の引用様式 (角括弧の
        # Vancouver など) のとき、黙って継承すると規定と異なる引用表記が警告なしに出るので、
        # 継承したことを必ず知らせる。重要度は上のフォールバックと揃えて「警告:」とする。
        print("  警告: csl 未指定。_default (AMA 11th) を継承します。"
              "雑誌規定と一致するか確認してください")
    elif kind == "reference_doc":
        # reference_doc: null は _default の体裁を継承する (csl と対称に扱う)。
        # 体裁は reference.docx に焼き込む設計なので、継承した時点で profile.yaml の体裁値は
        # 効いていない。たとえば profile.yaml に single / 行番号なし / 10.5pt / 15mm と書いても、
        # 出力は _default の double / 連続行番号 / 12pt / 25mm になる。継承したことと、
        # 効いていないキー名を必ず知らせる。
        print("  警告: reference_doc 未指定。_default の体裁 "
              "(double / 連続行番号 / Times New Roman 12pt / 余白 25mm / A4) を継承します。"
              "雑誌規定と一致するか確認してください")
        mismatches = _inherited_layout_mismatches(journal_id)
        if mismatches:
            detail = ", ".join(f"{k}: profile={v!r} != _default={d!r}" for k, v, d in mismatches)
            print(f"  警告: profile.yaml の体裁が _default と食い違っています ({detail})。"
                  f"これらは出力に反映されません — "
                  f"'bash data/journals/make-reference.sh {journal_id}' で "
                  f"reference.docx を生成し reference_doc を切り替えてください")
    default_path = JOURNALS_DIR / DEFAULT_ID / default_rel
    if not default_path.is_file():
        sys.exit(f"エラー: 既定 {kind} {default_path} がありません "
                 f"(_default の reference.docx は make-reference.sh で生成してください)")
    return default_path


def build(input_root, journal_id, doc, out, embed_svg=True, no_relocate=False,
          article_type=None, sha256_out=None):
    input_root = Path(input_root)
    out = Path(out)
    src_md = input_root / doc
    if not src_md.is_file():
        sys.exit(f"エラー: 原稿が見つかりません: {src_md}")

    # 記事種別を解決する (build は種別で出力を変えないが、未知の種別を早くエラーにするためここで解決)
    profile = journal_profile.load_resolved(journal_id, article_type)
    reference_doc = _resolve_asset(journal_id, profile.get("reference_doc"),
                                   "reference.docx", "reference_doc")
    csl = _resolve_asset(journal_id, profile.get("csl"), "_default.csl", "csl")
    # 題と凡例・式番号の後処理の指定は pandoc の前に解釈する (併用できない指定で止めるなら、変換する前に止める)
    caption_opts = caption_options(profile, reference_doc)

    resource_path = ["data/step01_figures", str(input_root / "figs"), "."]
    bib = input_root / "ref.bib"

    out.parent.mkdir(parents=True, exist_ok=True)

    # 一時名に書き、後処理まで成功したら out を置き換える。
    # 直接 out に書くと、後処理で失敗したときに失敗した版の docx が out に残り、前回の build の記録
    # (data/step02_build/.build.source) と組みになって package の照合を通りうる。失敗したら前回の out が残る。
    # 一時名には乱数を入れる。同じ作業ツリーで 2 つの build を同時に回したときに一時ファイルを
    # 取り合うと、片方が相手の書いた中身のハッシュを記録しうるため (コンテナの中ではプロセス番号がいつも同じなので使えない)
    final_out, out = out, out.with_name(f".{out.stem}.building.{secrets.token_hex(4)}{out.suffix}")

    # 画像マニフェスト: generic-style.lua が pandoc AST から出現順に画像を書き出し、
    # postprocess.py が件数照合・埋込対象 SVG 解決に使う。
    # パスは最終の docx の名前のまま (pandoc はこのメタデータを docProps/custom.xml に書くので、一時名にすると
    # 提出する docx に一時ファイルの名前が入る)。失敗したら消す (前回の docx と食い違う一覧を残さない。
    # 無ければ package は画像の一覧を使わない数え方で照合する)
    manifest = str(final_out) + ".images.tsv"
    # 誌ごとの crossref の上書き。名前は出力ごとに決まった名前にする (乱数を入れるとログが毎回変わる。
    # build は同時に 1 つしか回らない = build-lock.sh)。pandoc の後に消す
    crossref_yaml = final_out.with_name(f".{final_out.stem}.crossref.yaml")
    crossref_args, crossref_note = crossref_defaults(profile, crossref_yaml)

    cmd = [
        "pandoc", str(src_md),
        "--defaults", DEFAULTS_YAML,
        *crossref_args,
        "-M", f"image-manifest={manifest}",
        "--to", "docx",
        f"--reference-doc={reference_doc}",
        f"--resource-path={':'.join(resource_path)}",
        "--filter", "pandoc-crossref",
        "--lua-filter", GENERIC_FILTER,
        "--citeproc",
        f"--csl={csl}",
        *post_citeproc_args(profile, reference_doc),
        f"--output={out}",
    ]
    if bib.is_file():
        cmd.append(f"--bibliography={bib}")
    else:
        print(f"  注意: {bib} が無いため文献解決なし (引用があるなら ref.bib を用意してください)")

    print(f"== ビルド: {src_md} -> {final_out} ==")
    print(f"  journal={journal_id}  reference={reference_doc}  csl={csl}")
    if crossref_note:
        print(crossref_note)
    print("  pandoc " + " ".join(cmd[1:]))
    try:
        _build_into(cmd, out, src_md, profile, doc, resource_path, embed_svg, no_relocate, manifest,
                    reference_doc, caption_opts)
    except BaseException:
        # 失敗した版は残さない (前回の成功の out はそのまま)
        for p in (out, Path(manifest)):
            p.unlink(missing_ok=True)
        raise
    finally:
        crossref_yaml.unlink(missing_ok=True)
    if sha256_out:
        # 置き換える直前に、この build が書いた docx そのもののハッシュを残す (build.sh が .build.source に記録し、
        # package.py が main.docx と照合する。置き換えた後に読むと、同時に回った別の build の docx を読みうる)
        Path(sha256_out).write_text(hashlib.sha256(out.read_bytes()).hexdigest() + "\n", encoding="utf-8")
    os.replace(out, final_out)
    # manifest は削除せず保持する。step05 (package.py) が図の数え方を build と一致させるため
    # main.docx.images.tsv を読む (原稿を素の正規表現で数えると取りこぼす図があるため)。
    # data/step02_build/* は gitignored。
    print(f"  画像マニフェスト保持: {manifest} (step05 が参照)")
    print(f"== 完了: {final_out} ==")


def _build_into(cmd, out, src_md, profile, doc, resource_path, embed_svg, no_relocate, manifest, reference_doc,
                caption_opts):
    """pandoc で out (一時名) に書き、OOXML の後処理まで掛ける。失敗したら例外か SystemExit で抜ける。"""
    res = subprocess.run(cmd)
    if res.returncode != 0:
        sys.exit(f"エラー: pandoc が失敗しました (exit {res.returncode})")

    # --- 行番号の適用範囲 ---
    # line_numbers_scope: all (既定) / manuscript (本文 main.md だけに行番号を付ける)。
    # 行番号は査読者が**本文**の位置を指し示すための体裁なので、カバーレターや査読対応レポートに
    # まで付くのは筋が悪い (build は 3 文書を同じ reference.docx で変換するため実際に付く)。
    # 未指定なら全文書に付く。
    # 既定値は journal_profile.DEFAULTS が敷く ("all")。`or "all"` は明示 null への保険。
    scope = str(profile.get("line_numbers_scope") or "all").lower()
    if scope not in ("all", "manuscript"):
        print(f"  警告: line_numbers_scope の値 '{profile.get('line_numbers_scope')}' は不正です "
              "(有効: all / manuscript)。'all' (既定) として扱います")
        scope = "all"
    no_line_numbers = (scope == "manuscript" and doc != "main.md")

    # --- OOXML 後処理 (表罫線 / SVG 埋込 / textbox / 前付け (柱・所属のタブ・著者の脚注の記号) / 題と凡例 / 段組の節 / 式番号 / 行番号の除去) ---
    # 柱 (header.*) は main.md 以外 (カバーレター・回答書) でも同じ reference.docx の柱が付くので、
    # どの文書にも掛ける。running title の段落が無いと中央を空にするが、それを知らせるのは本文 (main.md) だけ。
    # 段組の節 (layout.*) は layout.scope の文書だけ (既定は本文 main.md だけ。カバーレターと回答書は 1 段組のまま)。
    # 題と凡例・式番号 (tables.legend_position / figures.keep_together / equations.style) と文献の番号の区切り
    # (bibliography.label_separator) はどの文書にも掛ける
    # (crossref の題の上書きもどの文書にも効くのと同じ)
    postprocess.process_docx(
        str(out),
        source_md=str(src_md),
        resource_path=resource_path,
        embed_svg=embed_svg,
        no_relocate=no_relocate,
        image_manifest=manifest,
        no_line_numbers=no_line_numbers,
        running_header=journal_profile.running_header(profile),
        affiliation_label_tab=journal_profile.affiliation_label_tab(profile),
        # 著者の脚注の記号 (title_page.author_footnote_marks)。著者の段落の無い文書では何もしない
        author_footnote_marks=journal_profile.author_footnote_marks(profile),
        # 出力の見出しのスタイルが自動番号を持つかを毎回確かめる (テンプレートの自動番号で見出しに番号を付ける誌 = headings.unnumbered_style のある誌の、
        # 番号を残す文書だけ)
        expect_numbered_headings=(journal_profile.unnumbered_style(profile) is not None
                                  and journal_profile.heading_numbers_kept(profile, is_manuscript=(doc == "main.md"))),
        is_manuscript=(doc == "main.md"),
        layout_cfg=layout_for(profile, reference_doc, is_manuscript=(doc == "main.md")),
        # 見出しの自動番号は headings.numbered_scope の文書だけに残す (既定 all = 全文書)
        suppress_heading_numbers=not journal_profile.heading_numbers_kept(profile, is_manuscript=(doc == "main.md")),
        **caption_opts,
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input-root", required=True, help="原稿ルート (data/dummy または src)")
    p.add_argument("--journal", default=DEFAULT_ID, help="雑誌プロファイル id (既定 _default)")
    p.add_argument("--doc", default="main.md", help="原稿ファイル (input-root 相対。既定 main.md)")
    p.add_argument("--out", required=True, help="出力 docx パス")
    p.add_argument("--no-embed-svg", action="store_true", help="ネイティブ SVG 埋込をしない")
    p.add_argument("--no-relocate", action="store_true", help="textbox の page 配置移動をしない")
    # 注意: build が profile から読むのは reference_doc / csl の 2 キーだけで、記事種別は出力を
    # 変えない。--article-type は (1) 未知種別の早期エラー (2) build.sh の provenance 記録
    # (data/step02_build/.journal の 2 行目) のために受ける。
    p.add_argument("--article-type", default=None,
                   help="記事種別 (article_types を持つ誌のみ。build の出力は変えない)")
    p.add_argument("--sha256-out", default=None,
                   help="書いた docx の SHA-256 をこのファイルに書く (build.sh が出所の記録に使う)")
    args = p.parse_args(argv)
    build(
        args.input_root, args.journal, args.doc, args.out,
        embed_svg=not args.no_embed_svg, no_relocate=args.no_relocate,
        article_type=args.article_type, sha256_out=args.sha256_out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
