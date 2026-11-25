#!/usr/bin/env python3
"""package.py — 投稿パッケージ組立 (コンテナ内本体)。

docs/architecture.md §2.5 / §3。雑誌プロファイル (data/journals/<id>/profile.yaml) に従い、ビルド済みの
docx (step02) と差分 docx (step03)・図 (step01) を整形・命名・集約して
data/output/<journal>/ に提出一式を作る。docx-paper-template-pandoc コンテナ内で実行する
(scripts/package.sh が driver)。

【モード (図の扱い)】profile.figures.embed と --mode で決まる:
  - draft (草稿, embed=true)  : 図を埋め込んだ manuscript.docx をそのまま提出 (data/step02_build/main.docx)。
  - final (最終, embed=false) : manuscript から図を取り除き [Figure N about here] のプレースホルダに置換し
                                (図キャプション=凡例は残す)、図を雑誌指定の形式/解像度/命名で figures/ に分離出力。
  --mode で profile を上書きできる (ダミーで両モードを検証するため)。
  **profile.figures.separate: false の誌** (図表を本文に埋め込んで提出する誌) では、final でも
  図を外さず提出構成の組み替えも行わない (manuscript.docx = main.docx)。提出用であること (出所の照合を止める側・
  SUBMISSION.md・roundtrip の配送) は図を分離する誌の final と同じ。図の形式 (figures.formats) は使わない。
  `submission.collect_forms` の誌は <INPUT_ROOT>/forms/ の記入済みの書式を forms/ に複製し、Word で PDF にして上げる docx の
  一覧 (.upload-as-pdf) を書く (roundtrip.sh が PDF にして Drive の submission-<journal>/ に置く)。
  書式の拡張子は小文字にそろえて写す (`X.DOCX` → `X.docx`。roundtrip.sh と判定をそろえる)。
  書式と補足資料の止まる検査は、直前に組んだパッケージを消す前に行う。

【図形式の対応状況 (docs/profile-schema.md)】図の生成経路は svg→pdf (svg-conversion) / svg→png (rsvg) /
  svg→pptx (svg_pptx) の 3 つ。profile.figures.formats の先頭を「主形式」とし、
  pdf→PDF / png→PNG / pptx→PPTX。tiff は PNG、eps は PDF へフォールバックし警告する
  (経路追加は将来。docs/profile-schema.md)。ただし代替先が profile.submission.figure_formats
  (定義時) に無い場合は警告でなくエラーで停止する。
  **生成経路が無い形式 (未知の綴り) は pdf へ代替せずエラーで停止する**
  (既定の代替先を pdf にすると、PDF 図を禁じる誌でも注意 1 行だけで PDF 図が出てしまうため)。
  png は svg_raster が物理サイズから画素数を計算して 300dpi 等を保証する (届かなければエラー)。
  pptx は 1 図 = 1 pptx = 1 スライドで SVG をベクターのまま埋め込み、同じ svg_raster で作った PNG
  フォールバックを同梱する。**元がラスタの図は pptx に包まず画像ファイルのまま出す**
  (規定は PowerPoint を受け付ける形式に挙げるだけで、画像を包むことは求めていない)。一次ソースの pptx が図の隣に在れば**無変換でコピー**する (案 A)。
  Inkscape が要る変換 (pdf 化 / text_to_path のアウトライン化) は svg-conversion コンテナで行うため
  figure-plan サブコマンドが必要な変換を列挙し、package.sh (ホスト) が駆動する。

サブコマンド:
  package.py figure-plan --input-root <dir> --journal <id> [--mode m] [--format f] [--font-handling h]
      [--slide-fit f] [--keep-figures]
      → 最終モードで svg-conversion が要る変換を TSV (src<TAB>out<TAB>embed<TAB>kind) で stdout に列挙。
        kind=pdf         : svg→pdf (「非 mermaid svg」のみ。mermaid は mmdc 正本 pdf を保持)
        kind=outline-svg : svg→アウトライン化 svg (pptx 経路で figures.pptx.text_to_path=true のとき)
        embed=1 なら convert.sh --embed-fonts。診断は stderr。
  package.py assemble --input-root <dir> --journal <id> [--mode m] [--format f] [--dpi n]
      [--font-handling h] [--slide-fit f] [--keep-figures] [--no-validate]
      → data/output/<journal>/ に manuscript / figures / revise-report / cover-letter (+ diff) を集約。

【提出構成の組み替え】最終モードでは profile に応じて manuscript.docx の構成も変える
  (実装は relocate.py):
    tables.placement: end          → 本文中の表を末尾へ移し `[Table N about here]` を残す
    tables.placement: separate     → 本文中の表を外し `[Table N about here]` を残して、
                                     `tables/TableN.docx` に 1 表 1 ファイルで出す
                                     (題 + 表 + 凡例。write_table_files)
    figures.legends_section: <題>  → 図の題+凡例を References の後の新ページへ集約
    tables.allow_color: false      → 表の網掛け・文字色・セル色を検出して警告 (docx 層の lint。
                                     数値の桁区切りカンマは Markdown 層 = validate.py の担当)
  あわせて `<INPUT_ROOT>/supplementary/` を無変換で複製し (動画は limits.video_mb を検査)、
  `submission` ブロックを持つ誌には提出マニフェスト `SUBMISSION.md` を書く。
  **これらのキーを持たない誌では何も起きない**。
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate as validate_mod  # noqa: E402
# 提出構成の組み替え (表末尾移設 / Figure Legends 集約) と表の体裁 lint は relocate.py に分けてある
import relocate as relocate_mod  # noqa: E402

# profile の読み込み・既定値・記事種別解決は共通モジュールに集約 (docs/profile-schema.md)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "00_setup" / "lib"))
import journal_profile  # noqa: E402
# 300dpi を保証する svg→png は step01 と共通モジュールを使う
import svg_raster  # noqa: E402
# ベクター提出 (1 図 = 1 pptx = 1 スライド) は共通モジュールへ
import svg_pptx  # noqa: E402
# pptx に埋め込む SVG を CSS に頼らない形へ書き換える
import svg_safe  # noqa: E402

# profile.yaml の探索は journal_profile.JOURNALS_DIR が持つ (本モジュールには JOURNALS_DIR を置かない)。
DEFAULT_ID = "_default"
FIG_ROOT = Path("data/step01_figures")          # 正規化済み図ツリー (figs/<rel>)
BUILD_DIR = Path("data/step02_build")
DIFF_DIR = Path("data/step03_diff")
# step05 が作る中間派生物 (`<stem>.outline.svg` など) の置き場。これは step01 の生成物ではないので
# 図ツリー (FIG_ROOT) には書かない — 「コードとデータを分離し、ステップごとに data/stepNN_*/ へ出す」
# という本テンプレの規約 (CLAUDE.md 「Step-by-Step Pipeline」) に従うため。図ツリーに置くと、
# 原稿の図の隣に提出用の派生物が混ざり、図ツリーを走査する受入テスト (check_dpi) が派生物を
# 名前で除外しなければならなくなる。
PKG_DIR = Path("data/step05_package")
OUTPUT_ROOT = Path("data/output")

# OOXML 名前空間 (図除去で使う最小限)
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"


def W(tag):
    return f"{{{W_NS}}}{tag}"


def WP(tag):
    return f"{{{WP_NS}}}{tag}"


# =====================================================================
# プロファイル解決
# =====================================================================

def load_profile(journal_id, article_type=None):
    """profile.yaml を読み、既定値と記事種別を解決した dict を返す (journal_profile へ委譲)。"""
    return journal_profile.load_resolved(journal_id, article_type)


def _figures_cfg(profile):
    fig = profile.get("figures") or {}
    return fig if isinstance(fig, dict) else {}


def resolve_mode(profile, mode_override):
    """draft / final を解決する。--mode 優先、無ければ profile.figures.embed (true→draft)。"""
    if mode_override in ("draft", "final"):
        return mode_override
    embed = _figures_cfg(profile).get("embed", True)
    return "draft" if embed else "final"


def resolve_format(profile, fmt_override):
    """図の主形式 (profile.figures.formats[0] か --format)。小文字化して返す。"""
    if fmt_override:
        fmt = fmt_override.lower()
        # --format の受入値を検証する。受入値を絞らないと、綴り違い ('pnj' 等) が
        # 既定の代替に落ちて**黙って別の形式に化ける**。指定できる値は「生成経路がある形式 +
        # 生成非対応と分かっている形式」に限り、それ以外は打鍵ミスとして即座に止める。
        if fmt not in KNOWN_FORMATS:
            # 第 1 文で列挙するのは「いま使える値」だけにする。KNOWN_FORMATS を全部並べると、
            # 指定すると別の理由で必ず停止する値 (jpeg/jpg) まで候補に見え、打鍵ミスを直そうとして
            # いる利用者が使えない値へ打ち直して 2 度目のエラーを踏む。
            unusable = sorted(KNOWN_FORMATS - GENERATABLE_FORMATS)
            sys.exit(
                f"エラー: --format '{fmt_override}' は認識できません。\n"
                f"  いま使えるのは {'/'.join(sorted(GENERATABLE_FORMATS))} です。\n"
                f"  ({'/'.join(unusable)} は綴りとしては認識しますが、指定すると停止します — "
                "線画に不向きなため生成非対応)。"
            )
    else:
        formats = _figures_cfg(profile).get("formats") or ["pdf"]
        if isinstance(formats, str):
            formats = [formats]
        fmt = str(formats[0]).lower() if formats else "pdf"
    # jpeg/jpg は「代替」として黙って png に落とさず、明示エラーにする。
    # 本テンプレが作る図は SVG のベクター線画で、JPEG は非可逆圧縮のため
    # 線・文字の輪郭が劣化する = 線画に最も不向きな形式である。BHI は PNG / TIF も受け付けるので
    # 「jpeg 指定で png が出る」という紛らわしい選択肢は置かない
    # (submission.figure_formats に jpeg を残すのは「投稿系が受け付ける形式」の記録であって
    # 生成できるという意味ではない)。
    if fmt in ("jpeg", "jpg"):
        sys.exit(
            "エラー: 図形式 'jpeg' は生成できません。本テンプレが線画 (SVG) から"
            "作れるラスタは PNG のみで、JPEG は非可逆圧縮のため線・文字の輪郭が劣化します。\n"
            "  PNG を受け付ける誌では --format png を使ってください。"
        )
    return fmt


# 主形式 -> (実際に生成する形式, フォールバックか否か)。
# 生成経路は pdf (svg→pdf。svg-conversion) / png (svg_raster。rsvg) / pptx (svg_pptx) の 3 つ。
_EXPORT_ROUTES = {
    "pdf":  ("pdf", False),
    "png":  ("png", False),
    "pptx": ("pptx", False),    # 1 図 = 1 pptx = 1 スライド (SVG 埋込 + PNG フォールバック)
    "eps":  ("pdf", True),      # ベクター: pdf を代替 (EPS ネイティブ経路は未実装)
    "tiff": ("png", True),      # ラスタ: png を代替 (TIFF ネイティブ経路は意図的に用意していない。docs/profile-schema.md)
    "tif":  ("png", True),
}
GENERATABLE_FORMATS = frozenset(_EXPORT_ROUTES)          # --format で生成まで行ける値
KNOWN_FORMATS = GENERATABLE_FORMATS | {"jpeg", "jpg"}    # 綴りとして認識する値


def resolved_export(fmt):
    """主形式 -> 実際に生成する形式 (pdf / png) と、フォールバックか否か。

    **未知の形式を pdf に代替しない**。既定の代替先を pdf にすると、PDF を明確に禁止する誌 (BHI) で
    プロファイルを置いた直後に `--mode final` を回したときに**規定違反の PDF 図**が
    `figures/Figure1.pdf` として生成される (停止を check_export_allowed の受入形式照合だけに
    頼ると、`submission.figure_formats` を持たない誌では素通りする)。

    生成経路が無い形式に対しては **(None, True)** を返す。実際に図を出す直前で
    `require_export_route()` がエラー停止させる。ここで即座に sys.exit しないのは、
    草稿モード (--mode draft) や --keep-figures では図を生成しないため — 主形式に生成経路が
    無くても草稿ビルドは通す必要がある。
    """
    fmt = (fmt or "pdf").lower()
    return _EXPORT_ROUTES.get(fmt, (None, True))


def require_export_route(fmt, export):
    """図を実際に生成する直前に、生成経路の無い形式で停止する。

    「落ちずに規定違反物を出す」ことを防ぐのが目的なので、既定代替 (pdf) は用意しない。
    """
    if export is not None:
        return
    # ここに来るのは「未知の綴り」だけ (pdf / png / pptx はすべて生成経路を持つ)。
    sys.exit(
        f"エラー: 図形式 '{fmt}' の生成経路がありません。\n"
        f"  生成できるのは {'/'.join(sorted(GENERATABLE_FORMATS))} です。"
        "'--format' で明示指定してください (未知の形式を pdf などへ黙って代替することはしません)。"
    )


# 図形式の表記ゆれ (submission.figure_formats との照合用)
_FMT_ALIASES = {"tif": "tiff", "jpg": "jpeg"}


def check_export_allowed(profile, fmt, export, fallback, allow_disallowed=False):
    """実際に生成する図形式を誌の受入形式 (submission.figure_formats) と照合する。

    代替 (tiff→png / eps→pdf) の先を受け付けない誌 (BHI は PDF を受け付けない) では、「規定が
    禁止する形式の図が注意 1 行だけで生成される」事故が起きる。禁止形式へは黙って代替せず停止する。
    submission.figure_formats 未定義の誌は警告つきフォールバックのまま。

    照合は**代替が起きたときに限らず**、「実際に生成する形式」に対して常に行う。代替のときだけ
    照合すると、BHI で `--format pdf` のように「規定が禁止しているが本テンプレが生成できる形式」を
    明示指定したときに代替に当たらず、受入形式外の図が警告 1 行も無く生成される (実測)。
    外れたときの扱いは経路で分ける:
      - fallback=True  (作れないので代用した) → エラーで停止
      - fallback=False (利用者が明示指定し、その形式を生成できる) → **確認の一段を要求する**
        `--allow-disallowed-format` があれば停止せず警告を返す。

    fallback=False のときに警告どまりで生成すると、BHI で `--format pdf` だけが終了コード 0 で
    `Figure1.pdf` / `Figure2.pdf` を出す (実測)。`png` と `pdf` は 2 文字違いで、警告は出るものの
    最後は「パッケージ完了」で終わるため、**打ち間違いで規定違反の図一式が揃う**。
    「利用者の明示指定を尊重する」は維持しつつ (専用オプションを付ければ通る)、
    *打ち間違い* と *意図した指定* を区別できるようにする。
    `submission.figure_formats` を持たない誌は冒頭で None を返すため無影響。
    返り値: 警告メッセージ (str) または None。停止する場合は返らない。
    """
    allowed = (profile.get("submission") or {}).get("figure_formats")
    if not allowed:
        return None
    norm = {_FMT_ALIASES.get(str(a).lower(), str(a).lower()) for a in allowed}
    if _FMT_ALIASES.get(export, export) in norm:
        return None
    if fallback:
        sys.exit(
            f"エラー: 図形式 '{fmt}' の生成経路は未実装で、代替の '{export}' はこの誌の"
            f"受入形式 {allowed} に含まれません (禁止形式へ黙って代替しません)。\n"
            f"  受入形式内で生成できる形式 (例: --format png) を指定してください。"
        )
    if not allow_disallowed:
        sys.exit(
            f"エラー: 図形式 '{export}' はこの誌の受入形式 {allowed} に含まれません"
            f"。このまま出しても投稿系で受け付けられません。\n"
            f"  提出用には受入形式内の形式を指定してください (例: --format png)。\n"
            f"  受入形式外と承知のうえで生成する場合だけ '--allow-disallowed-format' を付けてください。"
        )
    return (
        f"★要注意: 生成する図形式 '{export}' はこの誌の受入形式 {allowed} に含まれません "
        f"(--allow-disallowed-format による明示同意あり)。"
        f"このまま提出しても投稿系で受け付けられません。"
        f"提出用には受入形式内 (例: --format png) を指定してください。"
    )


def resolve_dpi(profile, dpi_override):
    # dpi は画素数計算に直結するので、非数値・非正値を
    # トレースバックでなくエラーメッセージで止める。
    #
    # プロファイル側も --dpi と同じ基準で検証する。
    # `(_figures_cfg(profile).get("dpi") or 300)` のように書くと (a) `dpi: 0` が or 演算で 300 に化けて
    # 「正の整数で指定してください」に到達せず、(b) `dpi: 300.5` を int() が黙って 300 に
    # 切り捨てる (同じ値を --dpi で渡すとエラーになるので挙動が非対称になる)。
    # 解像度は画素数に直結するので、黙って別の値になることは避ける。
    if dpi_override is not None:
        src, raw = "--dpi", dpi_override
    else:
        cfg = _figures_cfg(profile)
        if "dpi" in cfg and cfg["dpi"] is not None:
            src, raw = "profile.figures.dpi", cfg["dpi"]
        else:
            return 300
    # 小数表記 (300.5 / 300.0) は --dpi と同じ基準で弾く。int(float) の黙った切り捨てを防ぐ。
    if not re.fullmatch(r"\s*[+-]?\d+\s*", str(raw)):
        sys.exit(f"エラー: {src} の値 '{raw}' が整数ではありません。")
    dpi = int(str(raw).strip())
    if dpi <= 0:
        sys.exit(f"エラー: {src} の値 '{raw}' は正の整数で指定してください。")
    return dpi


def resolve_font_handling(profile, fh_override):
    if fh_override in ("outline", "embed"):
        return fh_override
    return str(_figures_cfg(profile).get("font_handling") or "outline").lower()


# --- pptx 経路の設定 (profile.figures.pptx。既定は journal_profile.DEFAULTS) ---
PPTX_MODES = ("svg-blob", "passthrough", "native-shapes")
PPTX_SLIDE_FITS = ("figure", "fixed")


def resolve_pptx_cfg(profile, dpi, slide_fit_override=None):
    """profile.figures.pptx を解決して dict(mode, slide_fit, png_fallback_dpi, text_to_path) を返す。

    値の検証はここで一括して行い、綴り違いを黙って既定へ倒さない
    (図形式の解決と同じ方針。`--format pnj` が黙って別の形式に化けるのを防ぐのと同じ理由)。
    `png_fallback_dpi` の null → `figures.dpi` 継承は journal_profile.resolve() が済ませている
    (値を 2 か所で定義しないため)。ここでは resolve を通していない生 profile でも
    落ちないよう `dpi` を最終の落とし先にする。
    """
    cfg = _figures_cfg(profile).get("pptx")
    cfg = cfg if isinstance(cfg, dict) else {}

    mode = str(cfg.get("mode") or "svg-blob").lower()
    if mode not in PPTX_MODES:
        sys.exit(f"エラー: profile.figures.pptx.mode の値 '{cfg.get('mode')}' は不正です "
                 f"(有効: {'/'.join(PPTX_MODES)})。")
    if mode == "native-shapes":
        sys.exit(
            "エラー: profile.figures.pptx.mode: native-shapes (案 B′ = PowerPoint ネイティブ"
            "シェイプへの変換) は未実装です。\n"
            "  黙って案 B (SVG 埋込) へ落とすと『編集可能なシェイプ』という要求に応えたことに"
            "ならないため停止します。\n"
            "  mode: svg-blob (SVG をベクターのまま埋め込む) か mode: passthrough "
            "(利用者が PowerPoint で仕上げた図をそのまま出す) を選んでください。"
        )

    slide_fit = (slide_fit_override or cfg.get("slide_fit") or "figure")
    slide_fit = str(slide_fit).lower()
    if slide_fit not in PPTX_SLIDE_FITS:
        src = "--slide-fit" if slide_fit_override else "profile.figures.pptx.slide_fit"
        sys.exit(f"エラー: {src} の値 '{slide_fit}' は不正です "
                 f"(有効: {'/'.join(PPTX_SLIDE_FITS)})。")

    raw_dpi = cfg.get("png_fallback_dpi")
    if raw_dpi is None:
        png_dpi = dpi
    elif not re.fullmatch(r"\s*[+-]?\d+\s*", str(raw_dpi)):
        sys.exit(f"エラー: profile.figures.pptx.png_fallback_dpi の値 '{raw_dpi}' が整数ではありません。")
    else:
        png_dpi = int(str(raw_dpi).strip())
        if png_dpi <= 0:
            sys.exit("エラー: profile.figures.pptx.png_fallback_dpi は正の整数で指定してください "
                     f"(受け取った値: {raw_dpi})。")

    return {
        "mode": mode,
        "slide_fit": slide_fit,
        "png_fallback_dpi": png_dpi,
        "text_to_path": journal_profile.as_flag(
            cfg.get("text_to_path"), "figures.pptx.text_to_path", default=False),
        # 埋め込む SVG を CSS に頼らない形へ書き換える (svg_safe.py)。
        # SVG の CSS を適用しない描画系 (例: Aspose.Slides) で、svglite の塗りなしの枠が黒く塗られないように。
        "inline_css": journal_profile.as_flag(
            cfg.get("inline_css"), "figures.pptx.inline_css", default=False),
    }


def figure_label(profile, n):
    """numbering.figure (例 'Figure %d.' / 'Fig. %d') に番号を当てたラベル。"""
    numbering = profile.get("numbering") or {}
    pat = numbering.get("figure") or "Figure %d."
    try:
        return pat % n if "%d" in pat else f"{pat} {n}"
    except (TypeError, ValueError):
        return f"Figure {n}"


def figure_basename(profile, n):
    """ラベルからファイル名 (拡張子なし) を作る。'Figure 1.'→'Figure1', 'Fig. 1'→'Fig1'。"""
    base = re.sub(r"[^0-9A-Za-z]+", "", figure_label(profile, n))
    # ラテン文字を含まない書式 (例 '図%d'→'1') はファイル名が数字のみ ('1.pdf') に
    # 縮退し図と分かりにくいため 'Figure{n}' に倒す (空のときだけでなく、ラテン文字が無いときも)。
    if not re.search(r"[A-Za-z]", base):
        return f"Figure{n}"
    return base


# =====================================================================
# 原稿の図参照を出現順に取得
# =====================================================================

def _strip_yaml_and_code(md_text):
    md_text = re.sub(r"^---\n.*?\n---\n", "", md_text, count=1, flags=re.DOTALL)
    md_text = re.sub(r"<!--.*?-->", "", md_text, flags=re.DOTALL)   # HTML コメント
    md_text = re.sub(r"```.*?```", "", md_text, flags=re.DOTALL)    # コードフェンス
    return md_text


MANIFEST = BUILD_DIR / "main.docx.images.tsv"   # build_docx.py が保持する画像マニフェスト


def manuscript_figures(input_root, body_only=False):
    """原稿の図参照を出現順に [rel_path] で返す。

    body_only=True のとき、テキストボックス (.textbox) 内の図を除いた**本文の図だけ**を返す。
    これは strip_inline_figures が `_in_textbox` で温存する図集合と一致し、
    `[Figure N about here]` のプレースホルダ番号と `figures/FigureN` の対応を揃えるために使う。
    判定にはマニフェスト第 3 列 (in_textbox = 1|0) を用いる。第 3 列が無いマニフェスト
    (古いビルドの残り) では全図を本文図とみなす。

    build (postprocess) と図の数え方を一致させるため、build_docx.py が保持する
    image-manifest (data/step02_build/main.docx.images.tsv = src<TAB>caption) を**優先**して読む。これで
    素の正規表現がキャプション内の角括弧・参照形式画像で取りこぼす不一致を package でも回避し、
    strip / export / build が同一の図集合・順序を共有する。マニフェストが無いときだけ正規表現に
    フォールバックする (postprocess.py 単独実行・古いビルドとの互換)。
    """
    if MANIFEST.is_file():
        figs = []
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cols = line.split("\t")
            # 第 3 列 (in_textbox) が無い古いマニフェストは "0" 扱い。
            in_textbox = len(cols) > 2 and cols[2].strip() == "1"
            if body_only and in_textbox:
                continue
            figs.append(cols[0])
        return figs
    md = Path(input_root) / "main.md"
    if not md.is_file():
        return []
    text = _strip_yaml_and_code(md.read_text(encoding="utf-8"))
    return [m.group(1) for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", text)]


def _resolve_fig_sources(rel, input_root=None):
    """原稿の図参照 rel (例 figs/fig-overview.svg) を step01 の実体に解決する。

    返り値 dict: svg / pdf / png / outline_svg / src_pptx のフルパス (存在は呼び出し側で確認)。
    mermaid (figs/mermaid/<n>.svg) も同規則。pdf は <stem>.pdf (mermaid は mmdc 正本)。

    pptx 経路のための派生物:
      outline_svg : `<stem>.outline.svg` = svg-conversion で文字をパス化した提出用 SVG
                    (figures.pptx.text_to_path=true のときだけ作る。figure-plan が計画する)
                    **置き場は `data/step05_package/`** (図ツリーには置かない)。
                    step05 の生成物を図ツリーに置くと、原稿の図と提出用の派生物が同じ場所に
                    混ざり、図ツリーを走査する受入テストが名前で除外せざるを得なくなる。
      src_pptx    : 執筆者が置いた一次ソースの pptx (案 A の無変換コピー元)。step01 は pptx を
                    図ツリーへ写さないので、図ツリー → 入力ルートの順に探す (非 svg 図の
                    実体探索と同じ規則)。原稿は `.svg` プレビューを参照し、隣に同名の
                    `.pptx` を置く運用 (CLAUDE.md の執筆規約)。
      src_macro   : 同じ場所に置かれた**マクロ有効の PowerPoint ファイル** (`.pptm` / `.ppsm` /
                    `.potm`)。`.pptx` しか探さないと、執筆者が `.pptm` を置いても
                    一次ソースとして見つからず、`svg_pptx.inspect_pptx` が持っている拒否メッセージ
                    にも到達せず、**黙って案 B (SVG からの生成) に落ちる**。置いた本人は
                    自分の PowerPoint 作業が提出物に反映されたと思い込む。
    """
    rel_path = Path(rel)
    svg = FIG_ROOT / rel_path
    pdf = FIG_ROOT / rel_path.with_suffix(".pdf")
    png = FIG_ROOT / (str(rel_path) + ".png")    # generic-style.lua の *.svg.png 規約
    # 提出用の派生物は step05 の領域へ (図ツリーには置かない)
    outline_svg = PKG_DIR / (str(rel_path.with_suffix("")) + ".outline.svg")
    # CSS に頼らない形へ書き換えた SVG (figures.pptx.inline_css。svg_safe.py)
    safe_svg = PKG_DIR / (str(rel_path.with_suffix("")) + ".safe.svg")

    def _sibling(suffix):
        """図と同じ場所の <stem><suffix> を図ツリー → 入力ルートの順に探す。"""
        cand_rel = rel_path.with_suffix(suffix)
        found = FIG_ROOT / cand_rel
        if not found.is_file() and input_root:
            alt = Path(input_root) / cand_rel
            if alt.is_file():
                return alt
        return found

    src_pptx = _sibling(".pptx")
    src_macro = next((p for p in (_sibling(s) for s in svg_pptx.MACRO_SUFFIXES) if p.is_file()),
                     None)
    is_mermaid = len(rel_path.parts) >= 2 and "mermaid" in rel_path.parts
    return {"svg": svg, "pdf": pdf, "png": png, "outline_svg": outline_svg,
            "safe_svg": safe_svg,
            "src_pptx": src_pptx, "src_macro": src_macro,
            "is_mermaid": is_mermaid, "rel": rel}


def write_safe_svg(src):
    """src["svg"] を CSS に頼らない形へ書き換えて src["safe_svg"] に書く。

    SVG の CSS を適用しない描画系 (例: Aspose.Slides) は svglite の CSS (`.svglite rect { fill: none; … }`) を
    読まず、塗りの指定が無い枠を黒で塗ってパネルを隠す。投稿系がどの描画系で図を描くかは公開されていないので、
    どれで描かれても崩れないよう書き換える。書き換えの中身と根拠は svg_safe.py。
    CSS に対応しない書き方が SVG にあれば svg_safe が ValueError を出すので、ここで止める
    (黙って一部だけ書き換えると、見た目が変わったことに気づけないため)。
    返り値: (書いたパス, 報告 dict)
    """
    data = Path(src["svg"]).read_bytes()
    try:
        out, report = svg_safe.make_self_contained(data)
    except ValueError as exc:
        sys.exit(f"エラー: {src['rel']}: CSS を要素へ書き出せません ({exc})。\n"
                 "  扱える CSS の範囲は main/00_setup/lib/svg_safe.py の説明にあります。次のどれかで避けてください:\n"
                 "    - この図だけ避けるなら、図の隣に PowerPoint で仕上げた同じ名前の .pptx を置く (無変換で提出される)\n"
                 "    - 作図の側で CSS を使わない SVG に書き出す (Mermaid の図では選べない)\n"
                 "    - --format png で全部の図を PNG にする\n"
                 "  (figures.pptx.inline_css を外すと、CSS を読まない描画系で塗りの無い図形が黒く塗られえます)。")
    dest = Path(src["safe_svg"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out)
    return dest, report


# =====================================================================
# figure-plan: 最終モードで svg-conversion (Inkscape) が要る変換を列挙 (host が駆動)
#
# TSV: src_svg <TAB> out <TAB> embed(0/1) <TAB> kind(pdf|outline-svg)
#   4 列目 kind があるのは、pptx 提出で figures.pptx.text_to_path=true のとき
#   pdf ではなく **アウトライン化した SVG** (convert.sh --outline-svg) が要るため。
#   package.sh が kind を見て convert.sh の呼び分けをする。
# =====================================================================

def cmd_figure_plan(args):
    profile = load_profile(args.journal, args.article_type)
    mode = resolve_mode(profile, args.mode)
    # tables.legend_position: above と tables.placement: end / separate の併用はここでも止める (build の検査だけだと、
    # build の後に profile を変えて package したときに題と凡例が本文に取り残される)。
    # figure-plan は assemble より先に走るので、図の変換を始める前に止まる
    journal_profile.table_legend_position(profile)
    # figures.separate: false の誌は図を分離しないので、図の形式も Inkscape の変換も使わない。
    # 図の形式の解決 (resolve_format) も通さない (formats を持たない誌で無関係な判定をしないため)。併用できないキーならここで止まる
    if not journal_profile.figures_separate(profile):
        print(f"  figure-plan: mode={mode} figures.separate=false (図を本文に埋め込んだまま) → svg-conversion は不要",
              file=sys.stderr)
        return 0
    fmt = resolve_format(profile, args.format)
    export, fallback = resolved_export(fmt)
    if mode == "final" and not args.keep_figures:
        # 生成経路が無い形式はここで停止する (pdf などへの既定代替はしない)
        require_export_route(fmt, export)
        # 代替なら停止、明示指定は明示同意を要求
        w = check_export_allowed(profile, fmt, export, fallback, args.allow_disallowed_format)
        if w:
            print(f"  figure-plan: {w}", file=sys.stderr)
    embed = "1" if resolve_font_handling(profile, args.font_handling) == "embed" else "0"

    # pptx 経路で text_to_path=true (BHI の既定) のときだけ svg→svg (アウトライン化) を計画する。
    # false では pptx 経路で Inkscape を一切呼ばない (駆動対象は pdf 経路だけ)。
    kind = None
    inline_css = False
    if mode == "final" and not args.keep_figures:
        if export == "pdf":
            kind = "pdf"
        elif export == "pptx":
            pptx_cfg = resolve_pptx_cfg(profile, resolve_dpi(profile, None), args.slide_fit)
            if pptx_cfg["text_to_path"] and pptx_cfg["mode"] == "svg-blob":
                kind = "outline-svg"
                # CSS の書き出しを輪郭化より【先に】行う。輪郭化すると <text> が
                # <path> になり、svglite の `.svglite path { fill: none }` が当たって文字が透明になる
                # (Inkscape は CSS を残したまま書き出す。実測)。書き換え済みの SVG を Inkscape に渡す。
                inline_css = pptx_cfg["inline_css"]

    if kind is None:
        # png 経路 / text_to_path=false の pptx 経路 / 草稿モード・--keep-figures では
        # svg-conversion (Inkscape) は不要
        print(f"  figure-plan: mode={mode} export={export} → svg-conversion は不要",
              file=sys.stderr)
        return 0

    # 図の一覧は直前の build の画像の一覧 (data/step02_build/main.docx.images.tsv) から読むので、
    # 図を変換する前に出所を照合する。別の原稿の build が残っていると、無関係な図を変換して止まり、
    # 本当の理由 (build の取り違え) が出ないため。注意の文は assemble が出すので、ここでは捨てる
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        _check_build_provenance(args, profile, mode, args.input_root)
    # 変換する図 (step01) の出所も照合する
    _require_figures_source(args, args.input_root)

    # export_figures と同じ図集合 (テキストボックス内図を除く) を対象にする。
    # 分離出力しない図の変換を走らせても無駄なため。
    for rel in manuscript_figures(args.input_root, body_only=True):
        if not rel.endswith(".svg"):
            continue
        src = _resolve_fig_sources(rel, args.input_root)
        if kind == "pdf" and src["is_mermaid"]:
            # mermaid は mmdc 正本 pdf を保持 (inkscape で上書きしない。step01 と同方針)。
            # ※ outline-svg は「正本」が別に無い派生物なので mermaid も対象にする。
            print(f"  figure-plan: skip mermaid (正本 pdf 保持): {rel}", file=sys.stderr)
            continue
        if kind == "outline-svg" and src["src_pptx"].is_file():
            # 案 A で無変換コピーする図はアウトライン化しない (中身に触らないのが目的のため)
            print(f"  figure-plan: skip 一次 pptx あり (案 A で無変換コピー): {rel}", file=sys.stderr)
            continue
        if not src["svg"].is_file():
            # 図の前処理の結果が無い図を飛ばすと、図の欠けた提出物が終了コード 0 でできる
            _missing_figure(f"{rel}: 図の前処理の結果 {src['svg']} がありません")
        out = src["pdf"] if kind == "pdf" else src["outline_svg"]
        conv_src = src["svg"]
        if kind == "outline-svg" and inline_css:
            conv_src, rep = write_safe_svg(src)
            print(f"  figure-plan: CSS を要素へ書き出し → {conv_src} "
                  f"(宣言 {rep['declarations_written']} 件 / 文字色の明示 {rep['text_fill_added']} 件)",
                  file=sys.stderr)
        print(f"{conv_src}\t{out}\t{embed}\t{kind}")
    return 0


# =====================================================================
# 最終モード: manuscript から inline 図を除去しプレースホルダ化
# =====================================================================

TXBX_CONTENT = "{%s}txbxContent" % W_NS


def _in_textbox(elem):
    """elem の祖先に w:txbxContent (テキストボックス内) が在るか。"""
    p = elem.getparent()
    while p is not None:
        if p.tag == TXBX_CONTENT:
            return True
        p = p.getparent()
    return False


def lint_manuscript_tables(docx_path, profile):
    """docx を**読むだけ**で表の体裁 lint を掛ける (草稿 / --keep-figures 経路)。

    草稿の manuscript.docx は `shutil.copyfile` でそのまま複製する (書き換えると
    草稿出力が build の docx とバイト単位で一致しなくなる)。lint は読み取り専用
    なので複製後の docx をもう一度開いて掛ける。色・網掛けの禁止は草稿でも直しておく価値がある
    (最終だけで警告すると、投稿直前に表を作り直すことになる)。
    """
    from lxml import etree
    with zipfile.ZipFile(docx_path, "r") as z:
        root = etree.fromstring(z.read("word/document.xml"))
    return relocate_mod.lint_tables(root, profile)


def _drop_orphan_media(parts, doc_xml_bytes):
    """document から参照されなくなった image 型 rels と word/media/* を削除する。

    図除去後、本文 (document.xml) のどこにも rId が現れない image 関係だけを孤立とみなし、関係定義と
    メディア実体を消す。残る図 (テキストボックス内図など) の rId は文字列照合で保護する。header/footer の
    画像は別 rels ファイルにあるため対象外。
    """
    from lxml import etree
    rels_path = "word/_rels/document.xml.rels"
    if rels_path not in parts:
        return 0
    doc_text = doc_xml_bytes.decode("utf-8", "ignore")
    rels_root = etree.fromstring(parts[rels_path])
    removed = 0
    for rel in list(rels_root):
        if not rel.get("Type", "").endswith("/image"):
            continue
        rid = rel.get("Id", "")
        # rId が document.xml の属性値として現れれば使用中 (閉じ引用符まで含め誤一致を防ぐ)
        if rid and (f'"{rid}"' in doc_text):
            continue
        target = rel.get("Target", "")
        media_part = target.lstrip("/") if target.startswith("/") else "word/" + target
        parts.pop(media_part, None)
        rels_root.remove(rel)
        removed += 1
    if removed:
        parts[rels_path] = etree.tostring(
            rels_root, xml_declaration=True, encoding="UTF-8", standalone=True
        )
    return removed


def table_file_name(group, index):
    """別ファイルへ出す表のファイル名 (`Table1.docx`)。題の無い表は通し番号で区別する。"""
    if group.get("number") is not None:
        return f"Table{group['number']}.docx"
    return f"Table-untitled{index}.docx"


def write_table_files(parts, root, groups, tables_dir, profile, log=print):
    """本文から外した表を 1 表 1 ファイルの docx に書き出す (tables.placement: separate)。

    本文の docx に表を含めず、表を 1 表 1 ファイルで出す。
    BHI のプロファイルは、規定 Tables 節の "or can be submitted as a separate file" に従って別ファイルを既定にする
    (規定の Manuscript Submission 節と Figures 節は本文の末尾に置く書き方なので、それに合わせるなら `end`)。

    作り方: **組み替え後の manuscript.docx の書庫をそのまま複製し、`w:body` の中身だけを
    その表の組 (題 + `w:tbl` + 凡例) と元の `w:sectPr` に置き換える**。styles / numbering /
    rels / フッタを本文と共有するので、題・凡例・表の体裁が本文と同じになる
    (別の reference.docx から組み立て直すと、本文と表で体裁がずれうる)。
      - 題は表の上・凡例は表の下 (pandoc の出力順そのまま。BHI 規定の並び)。
      - 行番号は `line_numbers_scope: manuscript` なら外す (表ファイルは本文 main.md ではない。
        カバーレターから行番号を外すのと同じ扱い)。`all` なら本文と同じく残す。
      - ページ番号 (フッタ) は残す。
      - 本文の相互参照 ("Table 1") のブックマークは本文側に残る (relocate の説明を参照)。
      - 最後が `w:tbl` で終わるなら空段落を足す (Word 自身も表の後に必ず段落を置く)。

    返り値: (written=[(ファイル名, パス)], lint=[警告文])
    """
    import copy
    from lxml import etree

    tables_dir = Path(tables_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)
    scope = str(profile.get("line_numbers_scope") or "all").lower()
    written, lint = [], []
    # 名前が重なると後の表が前の表を黙って上書きし、提出物から表が消える。書く前に止める
    names = [table_file_name(g, index) for index, g in enumerate(groups, start=1)]
    dups = sorted({n for n in names if names.count(n) > 1})
    if dups:
        sys.exit(f"エラー: 表ファイルの名前が重なります ({', '.join(dups)})。表の番号が重複しています — "
                 "表の題と相互参照のラベル ({#tbl:x}) を確かめてください (表が上書きされて消えるのを防ぐため中止します)。")
    for index, g in enumerate(groups, start=1):
        name = names[index - 1]
        doc = copy.deepcopy(root)
        body = doc.find(W("body"))
        sect = body.find(W("sectPr"))
        for el in list(body):
            if el is not sect:
                body.remove(el)
        add = (lambda el, s=sect: s.addprevious(el)) if sect is not None else body.append
        for el in g["elements"]:
            add(copy.deepcopy(el))
        if g["elements"] and g["elements"][-1].tag == W("tbl"):
            add(relocate_mod._make_paragraph(etree, "", style=relocate_mod.STYLE_PLACEHOLDER))
        if scope == "manuscript" and sect is not None:
            for ln in sect.findall(W("lnNumType")):
                sect.remove(ln)
        doc_bytes = etree.tostring(doc, xml_declaration=True, encoding="UTF-8", standalone=True)
        tparts = dict(parts)
        tparts["word/document.xml"] = doc_bytes
        _drop_orphan_media(tparts, doc_bytes)
        dest = tables_dir / name
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
            for part_name, data in tparts.items():
                zout.writestr(part_name, data)
        lint.extend(relocate_mod.lint_tables(doc, profile, label=f"tables/{name} の表"))
        written.append((name, dest))
    if written:
        log(f"  tables: {len(written)} 件を {tables_dir}/ に 1 表 1 ファイルで出力 "
            f"({', '.join(n for n, _ in written)})")
    return written, lint


def strip_inline_figures(docx_in, docx_out, profile=None, log=print, tables_dir=None):
    """inline 図 (wp:inline を含む w:drawing) を除去し [Figure N about here] に置換する。

    図キャプション (ImageCaption 段落=凡例) は残す。テキストボックス (wp:anchor) 自体は図ではないので
    対象外。(a) 1 段落に複数図があっても先頭で打ち切らず**全件**処理する、
    (b) テキストボックス内 (w:txbxContent 配下) の inline 図は
    フロート図表として温存し除去しない。除去後に参照されなくなった media/rels は
    掃除する (残すと最終 docx が肥大し、匿名版にも図データが残る)。
    番号 N は本文中 inline 図の出現順 (= postprocess が manifest 順に埋め込んだ図順) と一致する。

    **同じ 1 回の書庫の開閉で提出構成の組み替えと表の lint も済ませる** (relocate.py)。
    docx を 2 度開き直さないため、および「図をプレースホルダ化してから題と凡例を集約する」という
    順序の前提を関数の中に閉じ込めるため (relocate は図が本文に残ったままでは呼べない)。
    profile を渡さなければ図の除去だけを行う。

    `tables.placement: separate` では本文から外した表を `tables_dir` へ
    1 表 1 ファイルで書き出す (write_table_files)。表ファイルは本文と同じ書庫から作るので、
    この関数の中で (= 本文の書庫を閉じる前に) 行う。

    返り値: dict(stripped=図の件数, figures=集約した図の組数, tables=移設した表の組数,
                 legends_section=集約先の見出し名 or None, warnings=[...], lint=[...],
                 tables_files=[(ファイル名, パス)]  ← separate のときだけ非空)
    """
    from lxml import etree
    with zipfile.ZipFile(docx_in, "r") as zin:
        parts = {i.filename: zin.read(i.filename) for i in zin.infolist()}

    root = etree.fromstring(parts["word/document.xml"])
    body = root.find(W("body"))
    n = 0
    if body is not None:
        # 先に対象 drawing を確定してから変更する (走査中の木の変更を避ける)。
        targets = [dr for dr in body.iter(W("drawing"))
                   if dr.find(WP("inline")) is not None and not _in_textbox(dr)]
        for drawing in targets:
            n += 1
            run = drawing.getparent()                   # 図を載せた w:r
            # run 内の drawing を消し、同 run にプレースホルダ text を入れる (rPr は温存)
            run.remove(drawing)
            t = etree.SubElement(run, W("t"))
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            t.text = f"[Figure {n} about here]"

    result = {"stripped": n, "figures": 0, "tables": 0,
              "legends_section": None, "warnings": [], "lint": [], "tables_files": []}
    separated = []
    if profile is not None:
        # 表末尾移設 / Figure Legends 集約 (profile 駆動。未指定の誌では何もしない)
        rel = relocate_mod.relocate(root, profile, log=log)
        result.update({k: rel[k] for k in ("figures", "tables", "legends_section")})
        result["warnings"] = rel["warnings"]
        result["lint"] = relocate_mod.lint_tables(root, profile)
        separated = rel.get("tables_separated") or []

    doc_bytes = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    parts["word/document.xml"] = doc_bytes
    _drop_orphan_media(parts, doc_bytes)

    Path(docx_out).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(docx_out, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            zout.writestr(name, data)

    if separated:
        if tables_dir is None:
            sys.exit("エラー: tables.placement: separate で外した表の出力先 (tables_dir) が "
                     "渡されていません (package.py の呼び出し側の不具合)。")
        written, lint = write_table_files(parts, root, separated, tables_dir, profile, log=log)
        result["tables_files"] = written
        result["lint"].extend(lint)
    return result


# =====================================================================
# 図の分離出力 (final mode)
# =====================================================================

def _png_at_dpi(svg_path, out_png, dpi, label=None):
    """svg→png を「指定 dpi を保証して」生成する (pandoc コンテナ内)。

    `rsvg-convert -d/-p` に dpi を渡すだけでは、この指定が画素数に
    効くのは物理単位 (pt/mm/in/cm) を持つ SVG のときだけである。
    px/無単位 SVG (手書き・pdf2svg・mermaid 出力の多く) は 1:1 描画のままになり、BHI の
    "minimum of 300 dpi" を**満たさない図が警告 1 行で出てしまう**。
    そこで svg_raster が物理サイズから必要画素数を計算して -w/-h で明示し、生成後に実画素数を
    検算して pHYs を書き込む。**目標 dpi に届かない場合は警告ではなくエラーで停止**する
    (規定違反物を出さないため)。

    返り値: svg_raster.render_png_at_dpi の結果 dict。失敗時は sys.exit で停止する。
    """
    try:
        return svg_raster.render_png_at_dpi(svg_path, out_png, dpi, log=print, label=label)
    except svg_raster.SvgRasterError as exc:
        sys.exit(
            f"エラー: 図の png 生成に失敗しました ({label or svg_path})。\n  {exc}\n"
            "  解像度要件を満たさない図を提出しないため停止します "
            "(dpi を下げるか SVG の寸法指定を見直してください)。"
        )


def _raster_resolution_note(path, dpi):
    """原寸複製した生ラスタ図の解像度の状態を 1 行にする。

    pHYs を読めるのは PNG だけなので、それ以外は「機械判定できない」と正直に書く。
    """
    if Path(path).suffix.lower() != ".png":
        return (f"{Path(path).suffix.lstrip('.').upper()} は解像度を機械判定できない形式です "
                f"({dpi}dpi 以上で書き出したか確認してください)")
    try:
        w, h = svg_raster.png_pixel_size(path)
        state, value = svg_raster.read_png_phys(path)
    except svg_raster.SvgRasterError as exc:
        return f"解像度を読めませんでした ({exc})"
    if state == "dpi":
        judge = "要件を満たします" if value[0] >= dpi - 0.001 else f"**{dpi}dpi を下回ります**"
        return f"実測 {w}x{h} px / pHYs {value[0]:.2f}dpi — {judge}"
    if state == "unitless":
        return (f"実測 {w}x{h} px / pHYs はありますが単位が『なし』(縦横比のみ) で解像度を"
                f"表していません ({dpi}dpi と認識されません)")
    return (f"実測 {w}x{h} px / pHYs (物理解像度) が無いため何 dpi の画像か機械判定できません "
            f"(配置幅で割った値が {dpi}dpi 以上か確認してください)")


def _pptx_source_svg(src, pptx_cfg, index):
    """pptx へ埋め込む SVG を決める (text_to_path=true ならアウトライン化済みのもの)。

    `text_to_path: true` を指定したのに素の SVG を黙って埋め込むと、
    「フォント依存を消したつもりが消えていない」状態を検知できないので停止する
    (図形式を「黙って別形式に代替しない」のと同じ理由)。

    `inline_css: true` なら CSS に頼らない SVG を埋め込む。
      - text_to_path=false: ここで書き換えて `<stem>.safe.svg` を埋め込む。
      - text_to_path=true : figure-plan が書き換え済みの SVG を輪郭化しているはずなので、
        輪郭化した SVG に `<style>` が残っていれば (古い手順で作った残りもの) 停止する。
    """
    if not pptx_cfg["text_to_path"]:
        if pptx_cfg.get("inline_css"):
            path, _ = write_safe_svg(src)
            return path
        return src["svg"]
    if src["outline_svg"].is_file():
        if pptx_cfg.get("inline_css") and b"<style" in src["outline_svg"].read_bytes():
            sys.exit(
                f"エラー: Figure {index}: 輪郭化済み SVG {src['outline_svg']} に CSS (<style>) が残っています "
                "(figures.pptx.inline_css=true)。\n"
                "  CSS を書き出す前の SVG から作った古いファイルです。CSS を読まない描画系では塗りなしの枠が"
                "黒く塗られうるので停止します。\n"
                "  'bash scripts/package.sh' で作り直してください (figure-plan が書き出し → 輪郭化の順に行います)。")
        return src["outline_svg"]
    sys.exit(
        f"エラー: Figure {index}: text-to-path 済み SVG {src['outline_svg']} がありません "
        "(figures.pptx.text_to_path=true)。\n"
        "  素の SVG を黙って埋め込むとフォント依存が残ったまま提出されるため停止します。\n"
        "  'bash scripts/package.sh' 経由で実行してください (figure-plan が svg-conversion に"
        "アウトライン化を依頼します)。package.py を直に呼ぶ場合は\n"
        f"    bash docker/svg-conversion/convert.sh {src['svg']} {src['outline_svg']} --outline-svg\n"
        "  を先に実行してください。"
    )


def _export_one_pptx(src, dest, pptx_cfg, index, rel, warnings, profile):
    """図 1 枚を pptx として出す (案 A の無変換コピー or 案 B の SVG 埋込生成)。

    返り値: True なら 1 件生成した。
    """
    has_src_pptx = src["src_pptx"].is_file()

    # マクロ有効のファイル (.pptm 等) を置かれたときは黙って案 B に落とさない
    # (`.pptx` しか探さないと、拒否メッセージにすら到達しない)。
    if not has_src_pptx and src.get("src_macro"):
        sys.exit(
            f"エラー: Figure {index}: マクロ有効の PowerPoint ファイルは提出できません "
            f"({src['src_macro']})。\n"
            "  投稿系はマクロ / ActiveX を含む文書の変換に失敗すると明記しています。\n"
            "  マクロを外して同じ場所に <name>.pptx として保存し直してください "
            "(そのまま置いても案 A の無変換コピーには使われません)。\n"
            "  SVG から生成してよい場合は、そのファイルを図の隣から移動してください。"
        )

    # --- 案 A: 一次ソースが pptx なら無変換でコピーする (劣化ゼロ) ---
    if has_src_pptx or pptx_cfg["mode"] == "passthrough":
        if not has_src_pptx:
            sys.exit(
                f"エラー: Figure {index}: figures.pptx.mode: passthrough は一次ソースの pptx を"
                f"求めますが {src['src_pptx']} がありません。\n"
                "  原稿が参照する図と同じ場所・同じ名前で <name>.pptx を置いてください "
                "(原稿側は .svg のプレビューを参照したままにします)。\n"
                "  SVG から pptx を生成する場合は figures.pptx.mode: svg-blob にしてください。"
            )
        try:
            svg_pptx.copy_pptx_passthrough(src["src_pptx"], dest, log=print)
        except svg_pptx.SvgPptxError as exc:
            sys.exit(f"エラー: Figure {index} ({rel}) の pptx を提出できません。\n  {exc}")
        note = ("一次ソースの pptx をそのまま提出します (案 A。変換していないので劣化ゼロ)"
                if pptx_cfg["mode"] == "passthrough" else
                "一次ソースの pptx があったため SVG からの生成 (案 B) ではなく**無変換コピー**"
                "しました (案 A。変換を挟まないほうが劣化しないため)")
        # 案 A の pptx には figures.pptx.inline_css / text_to_path も掛からない (中身に触らない)
        extra = ""
        if pptx_cfg.get("inline_css") or pptx_cfg["text_to_path"]:
            extra = ("この誌の設定の CSS の書き出しと文字の輪郭化も掛かりません — 図の中の SVG が CSS で塗りを"
                     "決めていると、CSS を読まない描画系で黒く塗られえます。")
        warnings.append(
            f"Figure {index}: {note}。中身はテンプレートの検査対象外です — "
            "フォントの環境依存・余白・凡例キーは執筆者が PowerPoint 上で確認してください。" + extra)
        return True

    # --- 案 B: SVG から 1 スライドの pptx を生成する ---
    if not src["svg"].is_file():
        _missing_figure(f"Figure {index} ({rel}): 図の前処理の結果 {src['svg']} がありません")   # 図の欠けで止める
    embed_svg = _pptx_source_svg(src, pptx_cfg, index)
    with tempfile.TemporaryDirectory() as tmp:
        # PNG フォールバックは pptx の中身なので figures/ には置かない (提出物に混ぜない)
        try:
            # descr に `rel` (= `figs/fig-workflow.svg` という
            # **リポジトリ内の相対パス**) を渡すと、提出する pptx の代替テキストに内部の
            # ディレクトリ構成がそのまま載る。docProps から pandoc 開発者の氏名と作成日時を
            # 消した判断 (svg_pptx の骨格加工) と揃えて、図番号だけの中立な代替テキストにする。
            # (原稿のキャプションを代替テキストにするのが理想だが、この関数はキャプションを
            #  受け取っていないため、今後の課題とする)
            r = svg_pptx.build_figure_pptx(
                embed_svg, dest, png_path=Path(tmp) / "fallback.png",
                dpi=pptx_cfg["png_fallback_dpi"], slide_fit=pptx_cfg["slide_fit"],
                title=dest.stem, descr=figure_label(profile, index).rstrip("."), log=print)
        except svg_pptx.SvgPptxError as exc:
            sys.exit(f"エラー: Figure {index} ({rel}) の pptx 生成に失敗しました。\n  {exc}")
        except svg_raster.SvgRasterError as exc:
            sys.exit(
                f"エラー: Figure {index} ({rel}) の PNG フォールバック生成に失敗しました。\n  {exc}\n"
                "  pptx の PNG フォールバックは『多数の受け手が実際に見る本体』なので "
                "(Microsoft 365 / Office 2019 未満では PNG 側が描画され、投稿系の査読用 PDF 変換でも描画されうる)、"
                "解像度を保証できないまま出さずに停止します。")
    print(f"  figures: Figure {index} ({rel}) -> {dest}  "
          f"[pptx {r['slide_w_in']:.2f}x{r['slide_h_in']:.2f} in / PNG "
          f"{r['png_width']}x{r['png_height']} px @ {r['effective_dpi']:.0f}dpi]")
    if r["fit"] == "fixed":
        warnings.append(
            f"Figure {index}: slide_fit=fixed のため、スライドは既定サイズ "
            f"({r['slide_w_in']:.2f}x{r['slide_h_in']:.2f} in) で図を中央に置きました "
            f"(図の占める寸法 {r['placed_w_in']:.2f}x{r['placed_h_in']:.2f} in)。"
            "スライドに余白が残るので、余白を嫌う誌では SVG 側の寸法を見直してください。")
    elif r["pad_w_in"] > 0 or r["pad_h_in"] > 0:
        # 規格下限 (1 インチ) に合わせてスライドを広げた = 図の周りに余白ができた。
        # 量は小さいが「余白を最小化せよ」という規定があるので黙らせない。
        warnings.append(
            f"Figure {index}: 図が {r['placed_w_in']:.3f}x{r['placed_h_in']:.3f} in と小さく、"
            "PowerPoint のスライド寸法の下限 (1 インチ) を割るため、スライドを "
            f"{r['slide_w_in']:.3f}x{r['slide_h_in']:.3f} in へ広げて図を中央に置きました "
            f"(足した余白は幅 {r['pad_w_in']:.3f} in / 高さ {r['pad_h_in']:.3f} in)。"
            "余白を無くしたい場合は SVG ルートの width/height を 1 インチ以上にしてください。")
    return True


def export_figures(input_root, profile, out_fig_dir, fmt, export, fallback, dpi,
                   pptx_cfg=None):
    """原稿の図を雑誌指定の形式/解像度/命名で out_fig_dir に分離出力する。

    返り値: (生成数, 警告リスト, **書き出した順のリスト** [(表示名, パス), ...])。

    3 要素目は `SUBMISSION.md` の図の表の順序に使う。ディレクトリを
    `sorted(fig_dir.iterdir())` で**読み直して**はいけない。
    ファイル名は `figure_basename()` が作る `Figure1` / `Figure2` … で 0 埋めが無いため、
    `sorted()` は文字列として比較する。図が 10 枚を超えると
    `Figure1 → Figure10 → Figure11 → Figure12 → Figure2 → …` の順になり、
    マニフェストが「**本文の初出順にアップロードする (下表の順)**」と書いている表が
    初出順でなくなる (図 12 枚で実測)。投稿系は上げた順に図番号を割り当てるため、
    指示どおりに上げると全図が凡例と食い違う。本リストは `figs` (= 本文の初出順) を
    そのまま辿って積むので、命名規則 (`numbering.figure`) を変えても順序が壊れない。
    """
    warnings = []
    # 全図 (svg に限らない) を出現順 (manifest 順) に番号付け、
    # strip のプレースホルダ番号と一致させる。
    # body_only=True でテキストボックス内図を除外する。manifest の
    # 全件を分離対象にすると、strip_inline_figures が温存する textbox 内図まで FigureN として
    # 書き出し、プレースホルダ番号と figures/ の番号が (textbox 図の位置以降) 全部ずれる。
    figs = manuscript_figures(input_root, body_only=True)
    if not figs:
        # 空の figures/ も作る (「0 件を figures/ に分離出力」と出すのにフォルダが無いと、check-figures.sh が
        # 「package を先に回せ」と案内して止まるため)
        Path(out_fig_dir).mkdir(parents=True, exist_ok=True)
        warnings.append("原稿に図参照がありません (figures/ は空)")
        return 0, warnings, []
    if fallback:
        # TIFF ネイティブ経路は用意していない (理由と再検討する条件は下の警告文)。
        # 代替であることを黙らせず毎回明示する。
        extra = ""
        if fmt in ("tiff", "tif"):
            extra = ("。TIFF ネイティブ経路は**意図的に用意していない** — コンテナに画像"
                     "ライブラリが無く (Pillow/ImageMagick/exiftool いずれも不在)、追加すると"
                     "全ビルドが重くなる一方、多くの誌は PNG も受け付けるため。TIFF しか受け付けない"
                     "誌に投稿するときに再検討する")
        warnings.append(
            f"図形式 '{fmt}' は未対応の生成経路です。代替として '{export}' で出力します "
            f"(docs/profile-schema.md の figures.formats。EPS 経路は将来追加){extra}"
        )
    if export == "png":
        # dpi は物理単位の無い SVG にも効く (svg_raster が物理サイズから画素数を計算し、
        # 届かなければエラー停止する)。残る注意は
        # 「無単位 SVG の物理サイズをどう決めたか」という前提の明示だけ。
        warnings.append(
            f"png 図は {dpi}dpi を保証して生成しました (実画素数を検算済)。ただし物理単位 "
            "(mm/pt/in) を持たない SVG は width/height (無ければ viewBox) を CSS px = 96dpi と"
            "みなして物理サイズを決めています。**図を意図した印刷幅より小さい公称サイズで作っている場合、"
            "その印刷幅での実効解像度は 300dpi を下回りえます** — 各図のログ行 (元サイズ→inch→画素数) を"
            "確認し、必要なら SVG ルートに物理単位の width/height を持たせてください。"
            "ベクター図を png にラスタ化している点にも注意 (線画はベクター提出が望ましい場合あり)。"
        )
    if export == "pptx":
        # ベクター提出。dpi は「pptx に同梱する PNG フォールバック」の解像度として効く。
        # 「pptx 図は SVG をベクターのまま埋め込み…同梱しました」と
        # 全 pptx 図について断言しない。案 A (一次 pptx の無変換コピー) の図はテンプレートが
        # 中身に触っていないので、埋込も 300dpi の代替表示 PNG も**保証していない**。
        # 主語を「SVG から生成した図」に限り、案 A の図は個別の注意で扱う旨を書く。
        warnings.append(
            f"**SVG から生成した** pptx 図は SVG をベクターのまま埋め込み、"
            f"{pptx_cfg['png_fallback_dpi']}dpi の PNG "
            "フォールバックを同梱しました (**一次 pptx を無変換コピーした図 = 案 A は"
            "この保証の対象外で、個別に注意を出しています**)。**PNG フォールバックは保険ではなく多数の"
            "受け手が実際に見る本体です** — SVG のネイティブ表示に対応するのは Microsoft 365 / "
            "Office 2019 以降で、買い切り版 Office 2016 では PNG 側が描画されます。投稿系が査読用の PDF を作るときに"
            "どちらを描くか (SVG を描き直すか) は公開されていません。"
            "なお **スライド寸法を図に合わせても『余白の最小化 (closely cropped)』要件は満たせません** "
            "— SVG の viewBox が描画内容より広ければ白余白はそのままスライドに載るため、"
            "余白のトリミングは執筆者が SVG 側で行ってください。"
        )
    out_fig_dir = Path(out_fig_dir)
    out_fig_dir.mkdir(parents=True, exist_ok=True)
    ext = {"pdf": "pdf", "pptx": "pptx"}.get(export, "png")

    count = 0
    written = []            # 書き出した順 (= 本文の初出順) を保つ
    for i, rel in enumerate(figs, start=1):
        src = _resolve_fig_sources(rel, input_root)
        if not rel.endswith(".svg"):
            # 非 svg 図 (png/jpg 等): 原寸のまま複製 (svg 経路のみ形式変換に対応)。番号は必ず進める。
            orig_ext = Path(rel).suffix.lstrip(".") or "img"
            dest = out_fig_dir / f"{figure_basename(profile, i)}.{orig_ext}"
            cand = FIG_ROOT / rel
            if not cand.is_file():
                cand = Path(input_root) / rel
            if cand.is_file():
                shutil.copyfile(cand, dest)
                count += 1
                written.append((dest.name, dest))
                # 実画素数と pHYs をその場で読み、解像度の状態を必ず出す。
                # 300dpi 保証 (svg_raster) はこの経路に届かないので、そのことを利用者に必ず伝える
                # (実投稿で dpi 要件に引っかかりやすいのは線画ではなく写真であり、それがこの経路を通る)。
                res_note = _raster_resolution_note(dest, dpi)
                print(f"  figures: Figure {i} ({rel}) -> {dest}  [非svg 原寸複製。{res_note}]")
                if export == "pptx":
                    # 元がラスタの図は **意図的に** pptx へ包まない (規定は PowerPoint を受け付ける形式に挙げるだけで、
                    # 画像を包むことは求めていない)。ラスタを pptx に包んでも拡大耐性は上がらないため。
                    warnings.append(
                        f"Figure {i}: 元がラスタの図 ({rel}) は **pptx に包まず画像ファイルのまま**"
                        "出しました (画像の図は画像ファイルのまま提出する。"
                        "ラスタを pptx に包んでも拡大耐性は"
                        f"上がりません)。{res_note} "
                        f"**この図は {dpi}dpi 保証 (SVG からの生成経路) の対象外です** — 雑誌が dpi 要件を課す"
                        "場合は、元画像を要求解像度で書き出し直してください (ツール側では作り直せません)。"
                    )
                else:
                    warnings.append(
                        f"Figure {i}: 非 svg 図 ({rel}) は形式 '{fmt}' へ変換せず原寸複製しました "
                        f"(svg 経路のみ形式変換に対応)。{res_note} "
                        f"**この図は {dpi}dpi 保証 (SVG からの生成経路) の対象外です** — 雑誌が dpi 要件を課す場合は、"
                        "元画像を要求解像度で書き出し直してください (ツール側では作り直せません)。"
                    )
                # 原寸複製は形式変換を経ないため check_export_allowed の検査を
                # 通らない。元の拡張子を誌の受入形式と照合し、外れていれば注意を出す。
                allowed_ff = (profile.get("submission") or {}).get("figure_formats")
                if allowed_ff:
                    norm_ff = {_FMT_ALIASES.get(str(a).lower(), str(a).lower()) for a in allowed_ff}
                    oe = orig_ext.lower()
                    if _FMT_ALIASES.get(oe, oe) not in norm_ff:
                        warnings.append(
                            f"Figure {i}: 原寸複製した '{orig_ext}' はこの誌の受入形式 {allowed_ff} に"
                            "含まれません。受入形式内に変換してから提出してください。"
                        )
            else:
                _missing_figure(f"Figure {i}: 非 svg 図 {rel} の実体が見つかりません")   # 図の欠けで止める
            continue
        dest = out_fig_dir / f"{figure_basename(profile, i)}.{ext}"
        # pptx 以外の形式で出すときは、執筆者が置いた一次 pptx が
        # **使われない**。これを黙って行わない。原稿が参照する `.svg` は執筆規約上
        # 「pptx のプレビュー」でしかないので (CLAUDE.md)、下書きの図がそのまま提出物になりうる。
        if export != "pptx" and (src["src_pptx"].is_file() or src.get("src_macro")):
            found = src["src_pptx"] if src["src_pptx"].is_file() else src["src_macro"]
            warnings.append(
                f"Figure {i}: 図の隣に PowerPoint ファイル ({found}) が置かれていますが、"
                f"形式 '{export}' で出すため**使っていません**。"
                f"提出物になるのは同名の SVG ({src['svg']}) から作った画像です。"
                "その SVG が PowerPoint 側の内容と合っているかを確認してください "
                "(執筆規約では .svg は .pptx のプレビュー扱いです)。"
                "PowerPoint の中身をそのまま出すには --format pptx で実行してください。"
            )
        if export == "pdf":
            master = src["pdf"]
            if not master.is_file():
                _missing_figure(f"Figure {i} ({rel}): pdf 図 {master} がありません "
                                "(package.sh が svg-conversion で生成し、mermaid は step01 で生成する)")   # 図の欠けで止める
            shutil.copyfile(master, dest)
            count += 1
            written.append((dest.name, dest))
            print(f"  figures: Figure {i} ({rel}) -> {dest}  [pdf。ベクターは dpi 非依存]")
        elif export == "pptx":
            if _export_one_pptx(src, dest, pptx_cfg, i, rel, warnings, profile):
                count += 1
                written.append((dest.name, dest))
        else:  # png
            if not src["svg"].is_file():
                _missing_figure(f"Figure {i} ({rel}): 図の前処理の結果 {src['svg']} がありません")   # 図の欠けで止める
            r = _png_at_dpi(src["svg"], dest, dpi, label=f"Figure {i} ({rel})")
            count += 1
            written.append((dest.name, dest))
            print(f"  figures: Figure {i} ({rel}) -> {dest}  "
                  f"[png {r['width_px']}x{r['height_px']} px @ {dpi}dpi 検算済]")
    return count, warnings, written


# =====================================================================
# assemble: 提出一式を data/output/<journal>/ に集約
# =====================================================================

def _copy_if_exists(src, dst, label, collected, missing):
    src = Path(src)
    if src.is_file():
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        collected.append((label, str(dst)))
        return True
    missing.append((label, str(src)))
    return False


def _safe_journal_out_dir(journal):
    """data/output/<journal> を返す。journal id を検証し OUTPUT_ROOT の外を指さないことを保証する。

    shutil.rmtree(out_dir) が data/output や data/ 全体を消さないよう、空・'.'・'..'・
    パス区切り (/・\\) を拒否し、解決後パスが OUTPUT_ROOT の真の子孫であることを確認する。直接 package.py を
    呼ぶ運用でも効く load-bearing なガード。
    """
    if not journal or journal in (".", "..") or "/" in journal or "\\" in journal:
        sys.exit(f"エラー: 不正な --journal '{journal}' (空・'.'・'..'・パス区切りは使えません)")
    out = (OUTPUT_ROOT / journal).resolve()
    root = OUTPUT_ROOT.resolve()
    if out == root or root not in out.parents:
        sys.exit(f"エラー: --journal '{journal}' が {OUTPUT_ROOT}/ の外を指します (削除を中止します)")
    return OUTPUT_ROOT / journal


# =====================================================================
# supplementary / video のパススルー
# =====================================================================

SUPP_DIRNAME = validate_mod.SUPP_DIRNAME
# 動画かどうかは拡張子で決める。profile.submission.video_formats は「投稿系が受け付ける形式」の
# 記録なので、これで判定すると **受け付けられない形式の動画** (mov 等) が動画として扱われず、
# サイズ上限の検査からも漏れる。分類は拡張子、可否は profile、という切り分けにする。
VIDEO_SUFFIXES = (".mp4", ".mov", ".avi", ".wmv", ".mkv", ".m4v", ".webm", ".mpg", ".mpeg")

# OS が勝手に作る管理用ファイル。BHI の補足資料は「受け取ったまま、一切変換せず
# 公開され、受理後は変更できない」ため、これらが混ざるとそのまま誌面に載る (実測: `.DS_Store` が
# 複製され、SUBMISSION.md に「形式: (拡張子なし) / 1 B」として提出物の行が立った)。
# **雑誌に依存しない規則なので profile のキーにはせずコード側の定数に置く**。
# ドット始まりのファイルも同じ理由で落とす (`.gitkeep` 等)。除外したことは黙らせない。
# 規則と、補足資料のディレクトリのたどり方は validate.py に置く (規定チェックの容量の検査と同じ規則で数えるため)
_is_junk = validate_mod.supplementary_is_junk
# copy_supplementary / copy_forms の scan を省略した印 (None は「置き場所が無い」の意味で使う)
_NOT_SCANNED = object()


def scan_supplementary(input_root):
    """`<INPUT_ROOT>/supplementary/` の中のファイルの一覧を返す (複製はしない。ディレクトリが無ければ None)。止まる条件はここで調べる。

    直前に組んだパッケージ data/output/<journal>/ を消す前に呼ぶ (消した後で検査すると、読めないリンクで止まったときに
    確かめ済みのパッケージまで失われる)。
    """
    src_root = Path(input_root) / SUPP_DIRNAME
    if not src_root.is_dir():
        # リンクなのに読めない (コンテナから見えない場所を指す) なら止める。黙って「補足資料なし」にすると、
        # 査読の対象で受理後は差し替えられない資料が提出物から抜ける
        if src_root.is_symlink() or (src_root.exists() and not src_root.is_dir()):
            sys.exit(f"エラー: {src_root} はディレクトリとして読めません (コンテナから見えない場所を指すリンクか、"
                     "ファイル)。補足資料を提出物に入れられないので止めます。実体をリポジトリの中に置くか、"
                     "リポジトリの中を指す相対リンクにしてください。")
        return None
    # 中のディレクトリのリンクもたどって数える (rglob はたどらない)。リンクなのに中身が見えないもの (コンテナから見えない
    # 場所を指すリンク・行き先の無いリンク) があれば止める (補足資料が黙って提出物から抜けないように)。
    # 自分の祖先と同じ実体のディレクトリ (ループ) には入らない (_inputs_sha256 と同じ扱い)
    files, unseen = validate_mod.walk_supplementary(src_root)
    if unseen:
        sys.exit(f"エラー: {src_root} の中の次のリンクの先が読めません (コンテナから見えない場所を指すリンクか、"
                 f"行き先の無いリンク): {', '.join(sorted(unseen))}。補足資料を提出物に入れられないので止めます。"
                 "実体をリポジトリの中に置くか、リポジトリの中を指す相対リンクにしてください。")
    return files


def copy_supplementary(input_root, profile, out_dir, warnings, flags=None, scan=_NOT_SCANNED):
    """`<INPUT_ROOT>/supplementary/` を**無変換で**複製する。

    BHI の規定は "published as received ... without any conversion" (査読対象・受理後は変更不可)
    なので、テンプレート側は**ファイルの中身に**一切手を加えず複製する。動画は
    `profile.limits.video_mb` 超過と受入形式外を警告する。

    入力ルートを `src/` 直書きにしないのは、`.development` の有無で `data/dummy` / `src` に
    切り替わる規約 (docs/architecture.md §4) があり、`src/` 固定では検証データで確認できないため。

    あわせて次の 3 点を守る:
      - OS が作る管理用ファイル (`.DS_Store` 等) は複製しない (`_is_junk`)。除外は報告する。
      - 動画のサイズ判定は **10 進 (1MB = 1,000,000 バイト)** のバイト比較にする。
        1024 進で割った値を「MB」と比較すると上限が実質 52.4MB になり
        (規定より 4.9% 甘い)、境界では「50.0 MB で … 上限 50 MB を超えています」という
        自己矛盾した文面が出る。実バイト数を併記して丸めの誤解も断つ。
      - 複製が 0 件のときに、作られてもいない複製先を名指しする行を出さない。

    引数 `flags` に dict を渡すと、SUBMISSION.md の表へ出す印 (表示名 → 注意文) を書き込む。
    引数 `scan` には scan_supplementary の結果を渡す (直前に組んだパッケージを消す前に読んだもの)。省略すればここで読む。

    返り値: (supplementary エントリ, video エントリ)。各エントリは (表示名, 実パス)。
    """
    src_root = Path(input_root) / SUPP_DIRNAME
    # 止まる検査 (読めないディレクトリ・読めないリンク) は scan_supplementary で行う
    files = scan_supplementary(input_root) if scan is _NOT_SCANNED else scan
    if files is None:
        return [], []
    dest_root = Path(out_dir) / SUPP_DIRNAME
    limits = profile.get("limits") if isinstance(profile.get("limits"), dict) else {}
    video_mb = limits.get("video_mb")
    allowed_video = (profile.get("submission") or {}).get("video_formats")
    norm_video = ({_FMT_ALIASES.get(str(a).lower(), str(a).lower()) for a in allowed_video}
                  if allowed_video else None)
    if flags is None:
        flags = {}

    supp, video, skipped = [], [], []
    for src in sorted(files):
        rel = src.relative_to(src_root)
        if _is_junk(rel):
            skipped.append(rel.as_posix())
            continue
        dst = dest_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)                 # 無変換 (中身に手を加えない)
        name = f"{SUPP_DIRNAME}/{rel.as_posix()}"
        entry = (name, dst)
        if src.suffix.lower() in VIDEO_SUFFIXES:
            video.append(entry)
            n_bytes = dst.stat().st_size
            # 10 進 (1MB = 1,000,000 バイト) のバイト比較。
            if video_mb is not None and n_bytes > float(video_mb) * 1000 * 1000:
                warnings.append(
                    f"動画 '{rel.as_posix()}' は {n_bytes:,} バイト ({_human_size(n_bytes)}) で、"
                    f"この誌の上限 {video_mb} MB (= {int(float(video_mb) * 1000 * 1000):,} バイト) を"
                    "超えています。分割するか再エンコードしてください。")
                flags[name] = "⚠ 上限超過"
            ext = src.suffix.lstrip(".").lower()
            if norm_video is not None and _FMT_ALIASES.get(ext, ext) not in norm_video:
                warnings.append(
                    f"動画 '{rel.as_posix()}' の形式 '{ext}' はこの誌の受入形式 "
                    f"{allowed_video} に含まれません。")
                flags[name] = (flags.get(name, "") + " ⚠ 受入形式外").strip()
        else:
            supp.append(entry)
    n_copied = len(supp) + len(video)
    if n_copied:
        print(f"  supplementary: {n_copied} 件を {dest_root}/ に無変換で複製 "
              f"(うち動画 {len(video)} 件)")
    else:
        # 0 件のときは複製先が作られないので、その場所を名指ししない。
        print(f"  supplementary: {src_root}/ に複製する対象がありませんでした")
    if skipped:
        # 除外は黙らせない (執筆者が意図して置いたものかもしれない)。
        print(f"  supplementary: 管理用ファイル {len(skipped)} 件を除外しました "
              f"({', '.join(skipped)})")
    if n_copied and (profile.get("submission") or {}).get("supplementary") == "as-is":
        warnings.append(
            "補足資料は**無変換で公開され、査読対象で、受理後は変更できません**。"
            "投稿時点で最終形になっているか確認してください "
            "(本文中では図表と同様に引用のかたちで言及すること)。")
    return supp, video


def supplementary_limit_notes(profile, entries, flags):
    """補足資料の容量の上限 (limits.supplementary_file_mb / supplementary_total_mb) を SUBMISSION.md 用の文にする。

    上限を持たない誌は None (SUBMISSION.md に何も足さない)。1 ファイルの上限を超えた行には flags に印を付ける。
    数え方は規定チェック (validate.py の容量の検査) と同じ 10 進のバイト (管理用ファイルは複製しないので数えない)。動画も補足資料に数える。
    """
    limits = profile.get("limits") if isinstance(profile.get("limits"), dict) else {}
    file_mb, total_mb = limits.get("supplementary_file_mb"), limits.get("supplementary_total_mb")
    if file_mb is None and total_mb is None:
        return None
    total = 0
    for name, path in entries:
        n = Path(path).stat().st_size if Path(path).is_file() else 0
        total += n
        if file_mb is not None and n > float(file_mb) * 1000 * 1000:
            flags[name] = (flags.get(name, "") + " ⚠ 1 ファイルの上限超過").strip()
    rule = " / ".join(x for x in (
        f"1 ファイル {file_mb} MB 以内" if file_mb is not None else "",
        f"合計 {total_mb} MB 以内" if total_mb is not None else "") if x)
    line = f"容量: {rule} (動画を含む。今回の合計 {_human_size(total)})"
    if total_mb is not None and total > float(total_mb) * 1000 * 1000:
        line += f"。**⚠ 合計が上限 {total_mb} MB を超えている**"
    return line


# =====================================================================
# 記入済みの書式 <INPUT_ROOT>/forms/
# =====================================================================
# 投稿の書式 (投稿の申告書・利益相反の書式など) は誌の配布物に著者が記入し、署名して出す。署名・個人情報を含むので
# git で追跡しない場所 (<INPUT_ROOT>/forms/。.gitignore は src/forms/ を外す) に置き、提出パッケージの forms/ に
# 無変換で複製する。docx の書式は roundtrip.sh が Word で PDF にして Drive の submission-<journal>/forms/ に置く
# (同じ名前の PDF があれば、そちら = 署名を入れて PDF にしたもの をそのまま使い、docx は Word に回さない)。
# 書式の名前と通数は誌によって違うので、ここでは中身を判定しない (何を出すかは profile の submission.forms の一覧)。

FORMS_DIRNAME = "forms"
UPLOAD_PDF_LIST = ".upload-as-pdf"   # roundtrip.sh が読む (名前を変えるときは両方を直すこと)


def forms_dest_name(name):
    """書式をパッケージに写すときの名前。拡張子だけを小文字にそろえる (`X.DOCX` → `X.docx`)。

    roundtrip.sh は .upload-as-pdf の行を `*.docx` (小文字) でしか受け付けず、Word が作る PDF も `<名前>.pdf` で探す。
    拡張子の大文字小文字を問わず docx を PDF にする一覧に載せると、`X.DOCX` があるだけで roundtrip が「行が不正」で止まり、
    package を回し直しても直らない。両者の判定をそろえるため、パッケージの中では拡張子を小文字にする (中身は無変換のまま)。
    """
    p = Path(name)
    return p.stem + p.suffix.lower() if p.suffix else name


def scan_forms(input_root):
    """`<INPUT_ROOT>/forms/` を読み、複製する書式を決める (複製はしない)。止まる条件はここで調べる。

    直前に組んだパッケージ data/output/<journal>/ を消す前に呼ぶ (消した後で検査すると、読めないリンクなどで止まったときに
    確かめ済みのパッケージまで失われる)。
    返り値: None (forms/ が無い) か dict(files=[(原本, パッケージでの名前)], skipped=[管理用ファイル], subdirs=[ディレクトリ],
    renamed=[(元の名前, パッケージでの名前)])。
    """
    src_root = Path(input_root) / FORMS_DIRNAME
    if not src_root.is_dir():
        if src_root.is_symlink() or src_root.exists():
            sys.exit(f"エラー: {src_root} はディレクトリとして読めません (コンテナから見えない場所を指すリンクか、ファイル)。"
                     "書式を提出物に入れられないので止めます。実体をリポジトリの中に置いてください。")
        return None
    files, skipped, subdirs, renamed = [], [], [], []
    seen = {}                                     # パッケージでの名前 → 元の名前 (拡張子をそろえて重なる名前を止める)
    for p in sorted(src_root.iterdir()):
        if p.is_dir():
            subdirs.append(p.name)
        elif _is_junk(Path(p.name)):
            skipped.append(p.name)
        elif not p.is_file():
            sys.exit(f"エラー: {p} の先が読めません (コンテナから見えない場所を指すリンクか、行き先の無いリンク)。"
                     "書式を提出物に入れられないので止めます。実体をリポジトリの中に置いてください。")
        elif "\t" in p.name or "\n" in p.name:
            sys.exit(f"エラー: 書式のファイル名にタブか改行が入っています: {p.name!r}。名前を変えてください。")
        else:
            dest = forms_dest_name(p.name)
            if dest in seen:
                sys.exit(f"エラー: 書式 {seen[dest]!r} と {p.name!r} は、拡張子の大文字小文字をそろえると同じ名前 {dest!r} に"
                         "なります (提出パッケージでは拡張子を小文字にする)。どちらかの名前を変えるか、要らない方を消してください。")
            seen[dest] = p.name
            if dest != p.name:
                renamed.append((p.name, dest))
            files.append((p, dest))
    return {"files": files, "skipped": skipped, "subdirs": subdirs, "renamed": renamed}


def forms_git_note(input_root):
    """`<INPUT_ROOT>/forms/` が git で無視されていなければ、その旨の注意の文を返す (問題が無ければ None)。

    記入済みの書式は署名と個人情報を含むので git で追跡しない (.gitignore は src/forms/ だけを外す)。
    `--input mypaper` のように入力ルートを変えると mypaper/forms/ は無視されず、git add -A で入りうる。
    data/dummy/ の下 (動作例の架空の書式。追跡するのが正しい) は見ない。git が無い・リポジトリの外 (コンテナから .git が
    見えない worktree など) では黙って飛ばす。読むだけで、何も変えない。
    """
    src_root = Path(input_root) / FORMS_DIRNAME
    if not src_root.is_dir():
        return None
    dummy = Path("data/dummy").resolve()
    here = src_root.resolve()
    if here == dummy or dummy in here.parents:
        return None
    try:
        ign = subprocess.run(["git", "check-ignore", "-q", "--", f"{src_root}/"], capture_output=True, timeout=30)
        if ign.returncode not in (0, 1):          # 128 = リポジトリでない・git が使えない
            return None
        tracked = subprocess.run(["git", "ls-files", "--", f"{src_root}/"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    n_tracked = len(tracked.stdout.splitlines()) if tracked.returncode == 0 else 0
    if n_tracked:
        # 追跡しているファイルがあると、.gitignore に書いてあっても check-ignore はディレクトリを「無視されていない」と答える
        return (f"記入済みの書式の置き場所 {src_root}/ の {n_tracked} 件が git で追跡されています。署名と個人情報を含むので、"
                f"git rm --cached で追跡から外し、.gitignore に {src_root.as_posix()}/ が無ければ足してください (書式の中身は変えていません)。")
    if ign.returncode == 1:
        return (f"記入済みの書式の置き場所 {src_root}/ は git で無視されていません (git add -A などで署名入りの書式がリポジトリに入りうる)。"
                f"署名と個人情報を含むので、.gitignore に {src_root.as_posix()}/ を足してください (書式の中身は変えていません)。")
    return None


def copy_forms(input_root, out_dir, warnings=None, scan=_NOT_SCANNED):
    """`<INPUT_ROOT>/forms/` の直下のファイルを `out_dir/forms/` に無変換で複製する。

    warnings に list を渡すと (提出用のパッケージ)、書式が 1 つも無いことを注意に足す。
    scan には scan_forms の結果を渡す (直前に組んだパッケージを消す前に読んだもの)。省略すればここで読む。
    返り値: dict(entries=[(表示名, 実パス)], notes={表示名: 上げる形}, to_pdf=[パッケージからの相対パス], src=原本の場所)。
    """
    src_root = Path(input_root) / FORMS_DIRNAME
    ctx = {"entries": [], "notes": {}, "to_pdf": [], "src": f"{input_root}/{FORMS_DIRNAME}/"}
    if scan is _NOT_SCANNED:
        scan = scan_forms(input_root)
    if scan is None:
        print(f"  forms: {src_root}/ がありません (記入済みの書式を置くと提出パッケージの forms/ に複製されます)")
        if warnings is not None:
            warnings.append(f"記入済みの書式の置き場所 {src_root}/ がありません。SUBMISSION.md の「提出フォーム」の一覧の書式を"
                            "記入して置いてください (git で追跡しない場所。docx は roundtrip が Word で PDF にする)。")
        return ctx
    files, skipped, subdirs = scan["files"], scan["skipped"], scan["subdirs"]
    # docx と PDF の対は拡張子をそろえた名前で見る
    pdf_stems = {Path(dest).stem.lower() for _p, dest in files if Path(dest).suffix == ".pdf"}
    dest_root = Path(out_dir) / FORMS_DIRNAME
    for p, dest in files:
        dst = dest_root / dest
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)                    # 無変換 (中身に手を加えない。名前は拡張子だけ小文字にそろえる)
        name = f"{FORMS_DIRNAME}/{dest}"
        ctx["entries"].append((name, dst))
        stem, suffix = Path(dest).stem, Path(dest).suffix
        if suffix == ".pdf":
            ctx["notes"][name] = "PDF のまま上げる"
        elif suffix == ".docx" and stem.lower() in pdf_stems:
            ctx["notes"][name] = "同じ名前の PDF を上げる (この docx は Word に回さない)"
        elif suffix == ".docx":
            ctx["notes"][name] = f"Word で PDF にして上げる (`{FORMS_DIRNAME}/{stem}.pdf`)"
            ctx["to_pdf"].append(name)
        else:
            ctx["notes"][name] = "そのまま (投稿系が受け付ける形式か確かめる。Word で PDF にするのは docx だけ)"
    if scan["renamed"]:
        print("  forms: 拡張子を小文字にそろえて複製しました ("
              + ", ".join(f"{a} → {b}" for a, b in scan["renamed"]) + ")")
    if files:
        print(f"  forms: {len(files)} 件を {dest_root}/ に無変換で複製 (Word で PDF にする docx {len(ctx['to_pdf'])} 件)")
    else:
        print(f"  forms: {src_root}/ に複製する書式がありませんでした")
        if warnings is not None:
            warnings.append(f"{src_root}/ に書式がありません。SUBMISSION.md の「提出フォーム」の一覧の書式を記入して置いてください。")
    if skipped:
        print(f"  forms: 管理用ファイル {len(skipped)} 件を除外しました ({', '.join(skipped)})")
    if subdirs:
        msg = (f"{src_root}/ の中のディレクトリ ({', '.join(subdirs)}) は扱いません (書式は forms/ の直下に置く)。")
        print(f"  forms: {msg}")
        if warnings is not None:
            warnings.append(msg)
    return ctx


def write_upload_pdf_list(out_dir, profile, forms_ctx):
    """Word で PDF にして投稿系に上げる docx の一覧を `out_dir/.upload-as-pdf` に書く (提出用のパッケージだけ)。

    roundtrip.sh は一覧の docx を PDF 化に回し、できた PDF を提出パッケージの配送で submission-<journal>/ の同じ場所に
    `<名前>.pdf` で置く。原稿本体の受入形式 (submission.text_formats) が PDF なら manuscript.docx を、書式を集める誌なら
    docx の書式を載せる。一覧が空なら書かない。返り値: 一覧 (パッケージからの相対パス)。
    """
    text_formats = [str(x).lower() for x in (_submission_cfg(profile).get("text_formats") or [])]
    items = []
    if "pdf" in text_formats:
        items.append("manuscript.docx")
    if forms_ctx:
        items.extend(forms_ctx["to_pdf"])
    if items:
        (Path(out_dir) / UPLOAD_PDF_LIST).write_text(
            "# roundtrip.sh が Word で PDF にして submission-<journal>/ の同じ場所に <名前>.pdf で置く docx (package.py が書く)\n"
            + "".join(f"{x}\n" for x in items), encoding="utf-8")
    return items


def embedded_structure(profile):
    """図表を本文に埋め込んで提出する誌 (figures.separate: false) の SUBMISSION.md の「構成」の文を profile から組む。"""
    sections = (profile.get("sections") or {}).get("required") or []
    placement = relocate_mod.table_placement(profile)
    text = "図と表は本文中に埋め込んだまま提出する (`figures.separate: false` / `tables.placement: " + placement + "`)。"
    if sections:
        text = "表題ページ → 本文 (必須の節: " + " → ".join(str(s) for s in sections) + ")。" + text
    return text


# =====================================================================
# 提出マニフェスト SUBMISSION.md
# =====================================================================

def _human_size(n_bytes):
    """人が読むサイズ表記。**10 進 (1KB = 1,000 バイト)** で数える。

    1024 進で割った値に「KB」「MB」の単位を付けると、動画の上限判定を同じ流儀で行ったときに
    規定の「1 ファイル 50MB 以内」が実質 52.4MB になり (4.9% 甘い)、
    境界では「50.0 MB で … 上限 50 MB を超えています」という自己矛盾した文面が出る。
    投稿系の表示に合わせるなら 10 進のほうが素直なので、判定と表示の両方を 10 進に揃える。
    """
    if n_bytes < 1000:
        return f"{n_bytes} B"
    if n_bytes < 1000 * 1000:
        return f"{n_bytes / 1000:.1f} KB"
    return f"{n_bytes / (1000 * 1000):.2f} MB"


def _fmt_of(path):
    return Path(path).suffix.lstrip(".").lower() or "(拡張子なし)"


def _file_table(entries, flags=None, notes=None):
    """[(表示名, パス)] を Markdown 表にする。返り値: (行リスト, 合計バイト)。

    任意の `flags` (表示名 → 注意文) と `notes` (表示名 → 用途) を
    受ける。**該当が 1 つでもあるときだけ列を増やす**ので、印も用途も無い表は 4 列のままになる。
    上限超過や受入形式外はここで `⚠ 上限超過` として行に出す — 画面のログは流れるが
    マニフェストは残るため、規定に反するファイルを一覧に無印で載せてはならない。
    """
    flags = flags or {}
    notes = notes or {}
    has_flag = any(flags.get(name) for name, _ in entries)
    has_note = any(notes.get(name) for name, _ in entries)
    head = "| # | ファイル | 形式 | サイズ |"
    sep = "|---|----------|------|--------|"
    if has_flag:
        head += " 注意 |"
        sep += "------|"
    if has_note:
        head += " 用途 |"
        sep += "------|"
    rows = [head, sep]
    total = 0
    for i, (name, path) in enumerate(entries, start=1):
        size = Path(path).stat().st_size if Path(path).is_file() else 0
        total += size
        row = f"| {i} | `{name}` | {_fmt_of(path)} | {_human_size(size)} |"
        if has_flag:
            row += f" {flags.get(name, '')} |"
        if has_note:
            row += f" {notes.get(name, '')} |"
        rows.append(row)
    return rows, total


def _submission_cfg(profile):
    cfg = profile.get("submission")
    return cfg if isinstance(cfg, dict) else {}


def has_submission_spec(profile):
    """profile が提出マニフェストを出すに足る情報を持つか。

    `submission` の**いずれか 1 つ**が非 null なら真、とはしない。
    `submission.figure_formats` は図の生成でも読む `submission` キーで
    (受入形式外の図への代替を止める検査に使う)、新しい誌を足すとき**最初に
    書きたくなる**キーである。それだけを書いた段階でマニフェストを出すと、他の項目が未調査のまま
    「この誌はフォームの提出を求めていない」のような**未調査を断定に化けさせる**文面が並ぶ。
    原稿本体の受入形式 (`text_formats`) が分からない誌ではマニフェストの第 1 節が成立しないので、
    これを必須にする。`submission` ブロックを持たない誌ではマニフェストを出力しない。
    """
    return _submission_cfg(profile).get("text_formats") is not None


# =====================================================================
# Caption / Legend の貼り付け用ファイル CAPTIONS.md
# =====================================================================
# ScholarOne の投稿画面には、一般に上げたファイルごとの Caption / Legend 欄がある (BHI の実画面とは照合していない)
# 図表の題と凡例を手で写すと本文と食い違うので、**提出するファイルそのもの**
# (manuscript.docx の Figure Legends 節と tables/*.docx) から抜き出して、貼るだけの形で出す。
# 欄は書式なしのテキストとみなし、上付き・下付きは Unicode の文字に置き換え、斜体・太字・数式・脚注・リンクは注記する。

_M_OMATH = "{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath"
_M_T = "{http://schemas.openxmlformats.org/officeDocument/2006/math}t"

_SUPERSCRIPT = str.maketrans({
    **dict(zip("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")),
    "+": "⁺", "-": "⁻", "−": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    **dict(zip("abcdefghijklmnoprstuvwxyz", "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ")),
})
_SUBSCRIPT = str.maketrans({
    **dict(zip("0123456789", "₀₁₂₃₄₅₆₇₈₉")),
    "+": "₊", "-": "₋", "−": "₋", "=": "₌", "(": "₍", ")": "₎",
    **dict(zip("aehijklmnoprstuvx", "ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")),
})


def _toggle_on(rpr, tag):
    """rPr の太字・斜体などのトグルが**明示的に**オンか (w:val が 0 / false でない)。"""
    el = rpr.find(W(tag)) if rpr is not None else None
    return el is not None and (el.get(W("val")) or "true").lower() not in ("0", "false", "off")


def caption_plain_text(paragraph):
    """段落を書式なしのテキスト欄へ貼れる文字列にする。返り値: (文字列, 注記のリスト)。

    - 上付き・下付きは Unicode の上付き・下付き文字に置き換える (10⁴ / log₂)。置き換えられない
      文字を含むときは ^(…) / _(…) と書き、注記に出す (人が投稿画面で直す)。
    - 斜体・太字は貼ると消えるので、該当する文字列を注記に出す (段落スタイル由来の斜体 =
      TableCaption の全体斜体などは書式であって中身ではないので数えない)。
    - タブは空白、改行 (w:br) は改行にする。フィールドの命令文 (w:instrText) は拾わない。
    - 数式 (OMML の m:oMath) は文字だけを拾って ⚠ の注記を出す。脚注の記号と、リンクの URL は欄に入らないので
      ⚠ の注記を出す (黙って落とすと、欠けた文面を本文と同じと信じて貼ることになる)。
    """
    out, notes = [], []
    rel_id = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for h in paragraph.iter(W("hyperlink")):
        if h.get(rel_id):
            label = "".join(t.text or "" for t in h.iter(W("t"))).strip()
            notes.append(f"⚠ リンク `{label}` の URL は欄に入らない — 必要なら URL を文で書き足すこと")
    for r in paragraph.iter(W("r"), _M_OMATH):
        if r.tag == _M_OMATH:
            if any(a.tag == _M_OMATH for a in r.iterancestors()):
                continue                  # 入れ子の数式は外側でまとめて拾う
            s = "".join(t.text or "" for t in r.iter(_M_T))
            if s:
                notes.append(f"⚠ 数式 `{s}` は文字だけにした (上付き・分数などの組みは欄に入らない)"
                             " — 本文と見比べて直すこと")
                out.append(s)
            continue
        if any(a.tag == W("del") for a in r.iterancestors()):
            continue                      # 変更履歴の削除側は本文ではない
        if r.find(W("footnoteReference")) is not None or r.find(W("endnoteReference")) is not None:
            notes.append("⚠ 脚注の記号は欄に入らないので落とした — 脚注の中身が要るなら凡例に書き足すこと")
        buf = []
        for child in r:
            if child.tag == W("t"):
                buf.append(child.text or "")
            elif child.tag == W("tab"):
                buf.append(" ")
            elif child.tag in (W("br"), W("cr")):
                buf.append("\n")
            elif child.tag == W("noBreakHyphen"):
                buf.append("-")
        s = "".join(buf)
        if not s:
            continue
        rpr = r.find(W("rPr"))
        va = rpr.find(W("vertAlign")) if rpr is not None else None
        va = va.get(W("val")) if va is not None else None
        if va in ("superscript", "subscript"):
            table, mark, word = ((_SUPERSCRIPT, "^", "上付き") if va == "superscript"
                                 else (_SUBSCRIPT, "_", "下付き"))
            conv = s.translate(table)
            if all(c != o or c.isspace() for c, o in zip(conv, s)):
                notes.append(f"{word} `{s}` を Unicode の `{conv}` にした")
                s = conv
            else:
                notes.append(f"⚠ {word} `{s}` は Unicode にできないので `{mark}({s})` と書いた"
                             " — 投稿画面で直すこと")
                s = f"{mark}({s})"
        if _toggle_on(rpr, "i"):
            notes.append(f"斜体 `{s.strip()}` (貼ると斜体は消える)")
        if _toggle_on(rpr, "b"):
            notes.append(f"太字 `{s.strip()}` (貼ると太字は消える)")
        out.append(s)
    text = re.sub(r"[ \t]+", " ", "".join(out)).strip()
    return text, notes


def collect_caption_entries(manuscript_docx, tables_files, figures_written):
    """提出するファイルから図表の題と凡例を集める。投稿画面の順 (Table → Figure) で返す。

    返り値: [{"kind": "Table"|"Figure", "number": int|None, "file": 表示名|None,
              "text": 貼る文字列, "notes": [...]}]
    - 表: tables.placement: separate なら各 tables/TableN.docx、そうでなければ本文 (末尾) から。
    - 図: 本文の Figure Legends 節 (relocate が集約した ImageCaption + Legend)。図ファイル名は
      題の番号で figures_written (書き出した順 = 本文の初出順) と対応づける。
    """
    from lxml import etree

    def body_of(path):
        with zipfile.ZipFile(path) as z:
            return etree.fromstring(z.read("word/document.xml")).find(W("body"))

    def entry(kind, number, file_name, paragraphs):
        texts, notes = [], []
        for p in paragraphs:
            t, n = caption_plain_text(p)
            if t:
                texts.append(t)
            notes.extend(n)
        return {"kind": kind, "number": number, "file": file_name,
                "text": "\n".join(texts), "notes": notes}

    entries = []
    if tables_files:
        for name, path in tables_files:
            # 表ファイルにはブックマークが付いてこないので、番号は組み替えの前に決めたファイル名 (TableN.docx) から取る
            m = re.match(r"Table(\d+)\.docx$", name)
            for g in relocate_mod.collect_table_groups(body_of(path), require_bookmark=False):
                paras = ([g["caption"]] if g["caption"] is not None else []) + g["legends"]
                entries.append(entry("Table", int(m.group(1)) if m else None, name, paras))
    else:
        for g in relocate_mod.collect_table_groups(body_of(manuscript_docx), require_bookmark=False):
            paras = ([g["caption"]] if g["caption"] is not None else []) + g["legends"]
            entries.append(entry("Table", g["number"], None, paras))
    fig_names = [name for name, _ in (figures_written or [])]
    mbody = body_of(manuscript_docx)
    # 図ファイル (FigureN) はプレースホルダの順 = 題の無い図も含む本文の図の順で、図の番号は crossref のラベルの付いた図だけの
    # 順なので、番号では引けない (番号で引くと、題の無い図や題はあるがラベルの無い図が先にあるとき、
    # Figure 1 の題を中身の違う Figure1.pptx に結びつける)。題のあるプレースホルダの並びと Figure Legends の題の並びは
    # どちらも題のある図の文書順なので、同じ位置どうしを対応づける (数が合わなければ対応づけない)。
    # プレースホルダが無ければ (図を分離しない) 番号で引く
    groups = relocate_mod.collect_figure_groups(mbody)
    seq = relocate_mod.body_placeholders(mbody, relocated=True)
    captioned = [fig_names[p - 1] for p, titled in seq if titled and 0 < p <= len(fig_names)]
    for idx, g in enumerate(groups):
        n = g["number"]
        if seq:
            name = captioned[idx] if len(captioned) == len(groups) else None
        else:
            name = fig_names[n - 1] if n is not None and 0 < n <= len(fig_names) else None
        entries.append(entry("Figure", n, name, [g["caption"]] + g["legends"]))
    return entries


def write_captions_manifest(out_dir, profile, journal_id, entries):
    """data/output/<journal>/CAPTIONS.md を書く (Caption / Legend 欄に貼る文面)。"""
    name = profile.get("name", journal_id)
    lines = [
        f"# Caption / Legend (貼り付け用) — {name}",
        "",
        "投稿系 (ScholarOne) のファイルを上げる画面で、上げたファイルごとの Caption / Legend の欄に、"
        "下の枠の中身を貼る (欄の名前と並びは投稿画面で確かめること)。**このファイル自体はアップロードしない。**",
        "",
        f"- 生成元: `data/output/{journal_id}/` の `manuscript.docx` (図の題と凡例の節) と表ファイル。"
        "**提出するファイルそのものから、書式を除いて同じ文字を抜き出した**。⚠ の付いた項目 (数式・脚注・リンク・"
        "Unicode にできない上付き) は欄に入らない部分があるので、本文と見比べて直すこと。"
        "原稿を直したら `package.sh --mode final` で作り直すこと (このファイルも作り直される)。",
        "- 並びは表 → 図の順 (投稿画面の並びとは照合していない)。",
        "- 各枠の 1 行目が題 (`Table 1: …` / `Figure 1: …`)、2 行目以降が凡例。",
        "- 欄は書式なしのテキストなので、**上付き・下付きは Unicode の文字に置き換えてある** (例: 10⁴)。"
        "斜体・太字は貼ると消える — 該当があれば各項の下に書いてある。",
        "- Manuscript・カバーレター・フォームの欄に入れる文面は、ここには無い。",
        "",
    ]
    if not entries:
        lines += ["図表の題と凡例は見つからなかった (本文に図表が無い)。", ""]
    for e in entries:
        label = f"{e['kind']} {e['number']}" if e["number"] is not None else f"{e['kind']} (番号なし)"
        file_note = f" — `{e['file']}`" if e["file"] else (
            " — (本文の末尾にある表)" if e["kind"] == "Table" else " — (図ファイルと対応づけられない)")
        fence = "~~~~" if "```" in e["text"] else "```"
        lines += [f"## {label}{file_note}", "", f"{fence}text", e["text"] or "(題も凡例も無い)", fence, ""]
        for n in e["notes"]:
            lines.append(f"- {n}")
        if e["notes"]:
            lines.append("")
    path = Path(out_dir) / "CAPTIONS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_submission_manifest(out_dir, profile, journal_id, mode, ctx):
    """data/output/<journal>/SUBMISSION.md を書く。

    ScholarOne は原稿を**アップロード種別ごとに分けて**登録させるため、どのファイルをどの種別で
    出すのかを機械生成のチェックリストにしておく。形式・サイズ・順序と、COI Disclosure Form /
    License to Publish の提出要否まで 1 枚に収める (案 B の pptx は SVG と
    300dpi PNG を両方同梱するため肥大するが、profile がサイズ予算を持っているのは動画だけなので、
    サイズは「上限判定」ではなく「一覧」として出す)。

    **実行時の状態と検出結果を受け取る。** profile と出力
    ディレクトリの中身だけからマニフェストを組み立てると、その実行が実際に何をしたか、
    何を検出したかが分からない。そのため (a) 草稿モード / `--keep-figures` でも出力され、
    図が本文に埋め込まれたままなのに「生成モード: final (図: 分離)」と書き、
    (b) 表があるのに「本文に表が無いため移設していない」と断定し、
    (c) 上限超過の動画・受入形式外のファイル・表の色・図と凡例の食い違いといった
    **検出済みの問題を 1 つも載せない** (すべて実測)。
    マニフェストは画面のログが流れたあとに残る唯一のチェックリストであり、投稿は生成の当日に
    行うとは限らない。**信じるほど誤りやすい**状態は機能の目的と正反対である。

    ctx が受け取る鍵:
      relocated     : 提出構成の組み替えを行ったか (= 提出用のパッケージか)
      keep_figures  : --keep-figures 指定だったか (表示の出し分けに使う)
      warnings      : この実行で出た注意の全文 (末尾の節に転記する)
      flags         : 表の行に出す印 (表示名 → "⚠ 上限超過" 等)
      findings      : 規定チェック (validate) の指摘 list[Finding]。**None は「省略した」**
                      (--no-validate)。空リスト = 検査したが指摘なし

    **規定チェックの指摘も載せる。** validate の「規定違反の可能性 (要修正)」を載せず、
    冒頭の断定文が注意の件数だけを数えると、画面に要修正が何件出ていても「この実行で 1 件の注意が
    出ている」と書くことになる。投稿は生成の当日に行うとは限らず、後日このファイルだけを見て
    投稿する運用では上限超過や必須節の欠落が完全に見えなくなる。
    """
    sub = _submission_cfg(profile)
    tables_cfg = profile.get("tables") if isinstance(profile.get("tables"), dict) else {}
    limits = profile.get("limits") if isinstance(profile.get("limits"), dict) else {}
    at = profile.get("article_type")
    at_name = ((profile.get("article_types") or {}).get(at) or {}).get("name", "") if at else ""
    relocated = bool(ctx.get("relocated"))
    # 提出用か。図を分離する誌では relocated と同じ。図を本文に埋め込んだまま提出する誌
    # (figures.separate: false) では、提出用でも relocated (図の分離と組み替え) は偽になる
    for_submission = bool(ctx.get("for_submission", relocated))
    embedded = for_submission and not relocated
    warn_list = list(ctx.get("warnings") or [])
    flags = ctx.get("flags") or {}
    # 規定チェックの指摘 (None = --no-validate で省略した)
    findings = ctx.get("findings")
    must_list = [f for f in (findings or []) if f.level == validate_mod.LEVEL_MUST]
    info_list = [f for f in (findings or []) if f.level == validate_mod.LEVEL_INFO]

    # 値が無いのは「規定に無い」ではなく「プロファイルに記録が無い」である。
    # 断定に化けさせると、出し忘れると受理が止まる書類 (利益相反の申告書等) について
    # 「求められていない」と読める文面が機械生成されてしまう。
    def fmt_list(key, fallback="(プロファイルに記録なし。規定を確認すること)"):
        v = sub.get(key)
        return " / ".join(str(x).upper() for x in v) if v else fallback

    lines = [
        f"# 提出物マニフェスト — {profile.get('name', journal_id)}",
        "",
    ]
    # --- 提出用でないパッケージはいちばん先に宣言する ---
    if not for_submission:
        why = "--keep-figures (図を本文に残す指定)" if ctx.get("keep_figures") else "草稿モード"
        lines += [
            f"> ⛔ **このパッケージは提出用ではない** ({why} で生成した)。",
            "> **図が本文に埋め込まれたまま**であり、提出構成の組み替え (表の末尾移設か別ファイル化 / "
            "図の題と凡例の集約) も行っていない。",
            "> 提出物を作るには `--mode final` を `--keep-figures` なしで実行すること。",
            "> 以下の一覧はこの状態のまま機械生成したものである。",
            "",
        ]
    # 注意と規定チェックの要修正を合算して断定する。注意だけを
    # 数えると、要修正が何件出ていても「1 件の注意が出ている」のように書けてしまう。
    if warn_list or must_list:
        parts = []
        if must_list:
            parts.append(f"規定チェックの要修正 {len(must_list)} 件")
        if warn_list:
            parts.append(f"注意 {len(warn_list)} 件")
        lines += [
            f"> ⚠ **この実行で {' / '.join(parts)} が出ている。"
            "末尾の該当する節を必ず読むこと。**",
            "",
        ]
    if findings is None:
        # 沈黙を「問題なし」と読ませない (未調査を断定に化けさせないのと同じ考え方)
        lines += [
            "> ℹ **規定チェック (語数・上限・執筆 lint) は `--no-validate` で省略した。**"
            "本ファイルに規定チェックの節は無い。",
            "",
        ]
    lines.append(f"- 雑誌プロファイル: `{journal_id}`"
                 + (f" ({profile['name']})" if profile.get("name") else ""))
    if at:
        lines.append(f"- 記事種別: `{at}`" + (f" ({at_name})" if at_name else ""))
    if profile.get("submission_system"):
        lines.append(f"- 投稿系: <{profile['submission_system']}>")
    # 図の扱いは mode ではなく**実際に分離したか**で書く。
    # `mode == 'draft'` だけを見ると、`--mode final --keep-figures` で
    # 図が埋め込まれたままなのに「図: 分離」と書いてしまう。
    fig_state = "分離" if relocated else (
        "本文に埋め込み = figures.separate: false" if embedded else
        "埋込 (--keep-figures)" if ctx.get("keep_figures") else "埋込")
    lines += [
        f"- 生成モード: `{mode}` (図: {fig_state})",
        f"- 生成元: `data/output/{journal_id}/`",
    ]
    # どの原稿から作ったパッケージかを残す。roundtrip.sh が提出パッケージを
    # Drive の submission-<journal>/ へ届ける前に、今の入力ルートと一致するかを照合する
    # (別の入力ルート (動作例など) で作ったパッケージが data/output/<journal>/ に残っていても、日付だけでは
    #  見分けられない。**この行の書式は roundtrip.sh が読むので変えるときは両方を直すこと**)。
    if ctx.get("input_root"):
        lines.append(f"- 原稿の入力ルート: `{ctx['input_root']}`")
    # 原稿の SHA-256 も残す。roundtrip.sh が今の main.md と照合し、パッケージを作った後に
    # 原稿を直したまま届けるのを止める (時刻の比較だけだと、ファイルの時刻が保たれた写しや戻しで見落とす)。
    if ctx.get("main_sha256"):
        lines.append(f"- 原稿の SHA-256: `{ctx['main_sha256']}`")
    # 誌のプロファイルと reference.docx の SHA-256 とパスも残す。package は build したときの値と照合済み
    # (提出用)。roundtrip.sh が届ける前に今のファイルと照合し、パッケージを作った後に profile やテンプレートを変えたまま
    # 届けるのを止める。**この 2 行の書式も roundtrip.sh が読むので変えるときは両方を直すこと**
    assets = ctx.get("assets")
    if assets:
        lines.append(f"- 誌プロファイルの SHA-256: `{assets['profile_sha256']}` (`{Path(assets['profile_path']).as_posix()}`)")
        lines.append(f"- reference.docx の SHA-256: `{assets['reference_sha256']}` "
                     f"(`{Path(assets['reference_path']).as_posix()}`)")
    lines += [
        "",
        "> `profile.yaml` の `submission` ブロックから機械生成したチェックリストである。",
        "> **投稿系の画面表示が優先する** — 規定が改訂されたらプロファイル側を直すこと。",
        "",
    ]

    total_bytes = 0
    n_section = 0

    def section(title, note_lines, entries, empty_note, notes=None):
        nonlocal total_bytes, n_section
        n_section += 1
        lines.append(f"## {n_section}. {title}")
        lines.append("")
        lines.extend(note_lines)
        lines.append("")
        if entries:
            rows, size = _file_table(entries, flags=flags, notes=notes)
            total_bytes += size
            lines.extend(rows)
        elif empty_note:
            lines.append(empty_note)
        lines.append("")

    # Word で PDF にして上げる docx (roundtrip.sh が Drive の submission-<journal>/ に PDF を置く)
    upload_pdf = list(ctx.get("upload_pdf") or [])

    # --- 1. Text ---
    text_notes = [f"受入形式: {fmt_list('text_formats')}"]
    if ctx.get("structure"):
        text_notes.append("")
        text_notes.append(f"構成: {ctx['structure']}")
    if "manuscript.docx" in upload_pdf:
        text_notes.append("")
        text_notes.append("**上げるのは Word で PDF にした `manuscript.pdf`** (下表の docx から作る)。"
                          f"`bash scripts/roundtrip.sh` が Word で PDF にし、Google Drive の `submission-{journal_id}/` に "
                          "`manuscript.pdf` として置く (`INPUT_ROOT=<原稿> bash scripts/roundtrip.sh --skip-build`)。")
    section("Text (原稿本体)", text_notes, ctx["text"],
            "**原稿本体がありません** (先に `bash scripts/build.sh` を実行してください)。")

    # --- 2. Tables ---
    tbl_notes = [f"受入形式: {fmt_list('table_formats')}"
                 + ("。**画像化は不可** (Word の表オブジェクトのまま出す)"
                    if str(tables_cfg.get("object") or "").lower() == "word" else "")]
    if embedded and not sub.get("table_formats"):
        # 表を本文中に置いたまま提出する誌 (figures.separate: false では tables.placement は inline だけ)
        tbl_notes = [f"表は本文中に置いたまま提出する (`tables.placement: {relocate_mod.table_placement(profile)}`。"
                     "別ファイルの表は無い)。"]
    if ctx.get("tables_moved"):
        tbl_notes.append("")
        tbl_notes.append(
            f"本文ファイルの末尾へ **{ctx['tables_moved']} 件**を移設済み "
            f"(題は表の上・凡例は表の下。元位置には `[Table N about here]` を残した)。"
            + ("別ファイルでの提出も認められている。"
               if tables_cfg.get("separate_file_allowed") else ""))
    elif ctx.get("tables_files"):
        # tables.placement: separate (1 表 1 ファイル)
        tbl_notes.append("")
        tbl_notes.append(
            f"**1 表 1 ファイル**で `tables/` に出した ({len(ctx['tables_files'])} 件。"
            "各ファイルは題 (表の上)・表・凡例 (表の下))。"
            "本文の元位置には `[Table N about here]` を残し、**本文の流れに表は残していない** "
            "(テキストボックスの中の表は動かさない)。")
        tbl_notes.append("")
        tbl_notes.append("**表番号の順にアップロードする** (下表の順。相互参照のラベル `{#tbl:x}` の付いた表 "
                         "(`TableN.docx`) を番号の順に並べ、ラベルの無い表 (`Table-untitledN.docx`) は最後に回した。"
                         "ラベルの無い表は本文で番号が振られないので、本文の表番号と食い違わないようにラベルを付けるのが確実)。"
                         "投稿画面の Caption / Legend 欄には `CAPTIONS.md` の文面を貼る。")   # ラベルの無い表の扱いを書く
        # 一覧の順 (文書の順のままだと、ラベルの無い表が先にあるとき「表番号の順」の案内どおりに上げると
        # Table1.docx が 2 番目の表として番号付けされるため)
    elif relocate_mod.table_placement(profile) in ("end", "separate"):
        tbl_notes.append("")
        # 条件を `tables.placement == "end"` だけにしてモードを見ないと、
        # **表がある原稿を草稿モードで回したときに「本文に表が無い」と断定**してしまう
        # (実測)。移設したかどうかは relocated でしか分からない。
        if relocated:
            tbl_notes.append("本文に表が無いため移設していない。"
                             if relocate_mod.table_placement(profile) == "end"
                             else "本文に表が無いため表ファイルは無い。")
        else:
            tbl_notes.append(
                "**このモードでは表を移設していない** (本文に表があるかどうかは判定していない)。"
                "提出物を作るときは `--mode final` を `--keep-figures` なしで実行すること。")
    # 末尾移設をした場合は上の注記で説明が済んでいるので、空表の注記は出さない (重複を避ける)
    def _table_order(item):
        m = re.search(r"Table(\d+)\.docx$", str(item[0]))
        return (0, int(m.group(1)), "") if m else (1, 0, str(item[0]))
    section("Tables (表)", tbl_notes, sorted(ctx.get("tables_files") or [], key=_table_order),
            "" if ctx.get("tables_moved") or (embedded and not sub.get("table_formats"))
            else "別ファイルとしての表はない。")

    # --- 3. Figures ---
    if embedded:
        # 図を本文に埋め込んだまま提出する誌 (figures.separate: false): 図の形式・解像度・アップロードの順は無い
        section("Figures (図)", ["図は本文に埋め込んで提出する (`figures.separate: false`。分離した図ファイルは無い)。"],
                [], "")
    else:
        fig_notes = [f"受入形式: {fmt_list('figure_formats')}"]
        dpi = (_figures_cfg(profile) or {}).get("dpi")
        if dpi:
            fig_notes[0] += f"、最低 {dpi} dpi"
        fig_notes.append("")
        # 下表は export_figures が書き出した順 (= 本文の初出順) をそのまま並べる。
        # 投稿系は**上げた順に図番号を割り当てる**ので、この順序が狂うと全図が凡例と食い違う。
        # 表の # と本文の図番号が一致すると書けるのは、図がすべて番号つきで 1 から順に並ぶと確かめたときだけ
        if ctx.get("figure_numbers_match") is True:
            fig_notes.append("**本文の初出順にアップロードする** (下表の順。表の # が本文の図番号と一致する)。")
        elif ctx.get("figure_numbers_match") is False:
            # 理由と直し方は assemble が出し分ける (ラベルの無い図 / テキストボックスの中の図)
            why, fix = ctx.get("figure_numbers_reason") or ("番号の無い図か、図ファイルにならない図があるため", "")
            fig_notes.append("**本文の初出順にアップロードする** (下表の順)。"
                             f"★要注意: {why.replace('{#fig:x}', '`{#fig:x}`')}、表の # (図ファイルの番号) は"
                             "本文の図番号と一致しない。`CAPTIONS.md` の図番号とファイルの対応を見てから上げる"
                             + (f"({fix})。" if fix else "。"))
        else:
            fig_notes.append("**本文の初出順にアップロードする** (下表の順)。表の # が本文の図番号と一致するのは、"
                             "図がすべて相互参照のラベル (`{#fig:x}`) つきのときだけ。")
        if ctx.get("legends_section"):
            fig_notes.append(
                "投稿画面の Caption / Legend 欄には `CAPTIONS.md` の文面を貼る。"
                f"図の題と凡例は原稿本体の `{ctx['legends_section']}` 節にまとめてあり、"
                "画像ファイル側には書かない。")
        section("Figures (図)", fig_notes, ctx.get("figures") or [],
                "分離出力した図はない "
                + ("(`--mode final` を `--keep-figures` なしで実行すると生成される)。"
                   if not relocated else "(原稿に図参照がない)。"))

    # --- 4. Video ---
    video_notes = [f"受入形式: {fmt_list('video_formats', '(動画の規定なし)')}"
                   + (f"、1 ファイル {limits['video_mb']} MB 以内"
                      if limits.get("video_mb") else "")]
    section("Video (動画)", video_notes, ctx.get("video") or [],
            f"動画なし (`<INPUT_ROOT>/{SUPP_DIRNAME}/` に置けば複製される)。")

    # --- 5. Supplementary ---
    supp_notes = []
    supp_rule = sub.get("supplementary")
    if supp_rule == "as-is":
        supp_notes.append("**無変換で公開される**。査読対象であり、受理後は変更できないので"
                          "投稿時に最終形で出すこと。本文中では図表と同様に引用のかたちで言及する。")
    elif isinstance(supp_rule, str) and supp_rule.strip():
        # 誌の規定の要点を profile に文で書いた誌。決まった文 (as-is) は特定の誌の規定の言い回しなので使い回さない
        supp_notes.append(supp_rule.strip())
    else:
        supp_notes.append("補足資料。")
    if ctx.get("supplementary_limits"):
        # 容量の上限 (limits.supplementary_file_mb / supplementary_total_mb)
        supp_notes.append("")
        supp_notes.append(ctx["supplementary_limits"])
    section("Supplementary (補足資料)", supp_notes, ctx.get("supplementary") or [],
            f"補足資料なし (`<INPUT_ROOT>/{SUPP_DIRNAME}/` に置けば無変換で複製される)。")

    # --- 6. 提出フォーム ---
    n_section += 1
    forms_ctx = ctx.get("forms")     # None = 書式を集めない誌 (submission.collect_forms が偽)
    if forms_ctx is None:
        lines.append(f"## {n_section}. 提出フォーム (アップロード種別ではない)")
    else:
        # 記入済みの書式を投稿系にファイルとして上げる誌
        lines.append(f"## {n_section}. 提出フォーム (記入済みの書式)")
    lines.append("")
    forms = sub.get("forms")
    if forms:
        # 通数と記入者は誌によって違う (著者ごとに 1 通の誌も、連絡著者が全著者を代表して
        # 1 通の誌もある) ので、ここでは断定せず profile の各項目の注記に任せる。
        lines.append("**誰が何通出すかは各項目の注記と誌の規定に従う。**")
        lines.append("")
        for f in forms:
            lines.append(f"- [ ] {f}")
    else:
        # 未調査を「求められていない」と断定しない。
        lines.append("**フォームの記録がプロファイルに無い** (規定を確認すること)。"
                     "出し忘れると受理が止まる書類 (利益相反の申告書など) が"
                     "この誌にも要る可能性がある。")
    lines.append("")
    if forms_ctx is not None:
        # <INPUT_ROOT>/forms/ から複製した書式の一覧と、上げる形
        lines.append(f"記入済みの書式を `{forms_ctx['src']}` からパッケージの `{FORMS_DIRNAME}/` に無変換で複製した "
                     "(**記入済みの書式は署名・個人情報を含むので git で追跡しない場所に置く**)。"
                     f"docx の書式は `bash scripts/roundtrip.sh` が Word で PDF にし、"
                     f"Google Drive の `submission-{journal_id}/{FORMS_DIRNAME}/` に同じ名前の `.pdf` で置く "
                     "(署名を入れて PDF にしたものは、docx と同じ名前の `.pdf` で置けばそちらをそのまま使う)。")
        lines.append("")
        if forms_ctx["entries"]:
            rows, size = _file_table(forms_ctx["entries"], flags=flags, notes=forms_ctx["notes"])
            total_bytes += size
            lines.extend(rows)
        else:
            lines.append(f"**書式がありません** (`{forms_ctx['src']}` に置けば複製される)。")
        lines.append("")

    # --- 7. アップロード種別ではないもの (用途を注記する) ---
    if ctx.get("other"):
        n_section += 1
        lines.append(f"## {n_section}. 同じパッケージに入っているが、アップロード種別ではないもの")
        lines.append("")
        lines.append("**投稿画面のどの欄に出すか (あるいは出さないか) はファイルごとに違う。**")
        lines.append("")
        # 用途は名前で引く (差分 docx は初回投稿では上げない)。
        other_notes = {
            "cover-letter.docx": "投稿画面のテキスト欄または添付",
            "revise-report.docx": "**査読対応の再投稿でのみ使う**",
            "manuscript-diff.docx": "**査読対応の再投稿でのみ使う。初回投稿では上げない**",
            "CAPTIONS.md": "**アップロードしない**。投稿画面の各ファイルの Caption / Legend 欄に貼る文面",
        }
        rows, size = _file_table(ctx["other"], flags=flags, notes=other_notes)
        total_bytes += size
        lines.extend(rows)
        lines.append("")
        # 差分 docx の扱いは誌によって違うので、注記は profile の submission.diff_note から書く
        # (決まった注記を誌によらず書くと、別の誌の扱いを書いてしまう)
        diff_note = sub.get("diff_note")
        if diff_note and any(Path(p).name == "manuscript-diff.docx" for _, p in ctx["other"]):
            lines.append(f"> {str(diff_note).strip()}")
            lines.append("")

    # --- 合計 ---
    n_files = sum(len(ctx.get(k) or []) for k in
                  ("text", "tables_files", "figures", "video", "supplementary", "other"))
    if forms_ctx is not None:
        n_files += len(forms_ctx["entries"])
    lines.append("---")
    lines.append("")
    lines.append(f"**合計: {n_files} ファイル / {_human_size(total_bytes)}**")
    lines.append("")
    if ctx.get("supplementary_limits"):
        # 補足資料の容量の上限を持つ誌。上限を持たない誌の文は「サイズ予算は動画だけ」と書くので出し分ける
        lines.append("(サイズは 10 進 (1MB = 1,000,000 バイト) で数えている。"
                     "**上限と照らしたのは補足資料 (動画を含む) だけで、ほかは一覧である** — "
                     "ほかのファイルの上限は投稿系の画面表示で確認すること。)")
    else:
        lines.append("(サイズは 10 進 (1MB = 1,000,000 バイト) で数えている。"
                     "**動画以外は投稿系の上限判定ではなく一覧である** — "
                     "profile がサイズ予算を持つのは動画だけなので、"
                     "他は投稿系の画面表示で確認すること。)")
    lines.append("")

    # --- 規定チェック (validate の指摘をマニフェストに残す) ---
    # 注意の節より前に置く — 上限超過や必須節の欠落は、図変換の注意より投稿に直結する。
    if findings is not None:
        lines.append("---")
        lines.append("")
        lines.append(f"## 規定チェック (要修正 {len(must_list)} 件 / 参考 {len(info_list)} 件)")
        lines.append("")
        # 概算の行も載せる (投稿当日に SUBMISSION.md だけを見る人が、本文語数と、足し戻すための
        # 除外した語数を見られるように)
        estimate = ctx.get("estimate") or []
        if estimate:
            lines.append("概算 (Markdown 段階。除外した語数は、編集室の数え方が違えば足して見積もる):")
            lines.append("")
            for e in estimate:
                lines.append(f"- {e}")
            lines.append("")
        if not findings:
            lines.append("限度内 (または `limits` 未設定)。")
            lines.append("")
        else:
            lines.append("**要修正は投稿前に直すこと。** Markdown 段階の機械判定なので"
                         "最終判断は実物で行う (検査はエラーにしない)。"
                         "単独で回し直すには "
                         "`python3 main/step05_package/validate.py --input-root <原稿> "
                         "--journal <id> --article-type <種別>`。")
            lines.append("")
            for title, rows in (("規定違反の可能性 (要修正)", must_list),
                                ("参考情報", info_list)):
                if not rows:
                    continue
                lines.append(f"### {title} — {len(rows)} 件")
                lines.append("")
                for f in rows:
                    lines.append(f"- {validate_mod.finding_text(f)}")
                lines.append("")

    # --- 注意 (この実行で検出したものをマニフェストに残す) ---
    # 画面のログは流れるがマニフェストは残る。投稿は生成の当日に行うとは限らず、
    # 共著者の確認を待って別の人が上げることもある。その人が読むのはこのファイルだけである。
    if warn_list:
        lines.append("---")
        lines.append("")
        lines.append(f"## 注意 (この実行で検出したもの — {len(warn_list)} 件)")
        lines.append("")
        lines.append("**投稿する前にすべて目を通すこと。**"
                     "パッケージを作り直しても、注意の原因 (原稿・差分 docx・図・プロファイルなど) を"
                     "直さない限り同じ注意が出る。")   # 差分の注意は原稿ではなく差分 docx を直す
        lines.append("")
        for w in warn_list:
            lines.append(f"- {w}")
        lines.append("")

    path = Path(out_dir) / "SUBMISSION.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _file_sha256(path):
    """ファイルの SHA-256。読めなければ印の文字列 (_inputs_sha256 が止めずに数える)。"""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return "unreadable"


def build_assets(journal_id):
    """build が使う誌のプロファイルと reference.docx の (パス, SHA-256) を返す。

    reference.docx の解決は build_docx.py の _resolve_asset と同じ規則 (profile の reference_doc が指すファイルがあれば
    それ、無ければ _default の reference.docx)。build.sh が build の前後に `package.py build-assets` で呼んで
    data/step02_build/.build.source に記録し (profile_sha256 / reference_sha256)、package の出所の照合と SUBMISSION.md の
    記録 (roundtrip.sh が照合する) が同じ関数で今の値を出す (計算を 1 か所に置く)。ファイルが無ければ SHA-256 は空。
    """
    jdir = journal_profile.JOURNALS_DIR / journal_id
    prof_path = jdir / "profile.yaml"
    ref_value = (journal_profile.load(journal_id) or {}).get("reference_doc") if prof_path.is_file() else None
    ref_path = jdir / str(ref_value) if ref_value else None
    if ref_path is None or not ref_path.is_file():
        ref_path = journal_profile.JOURNALS_DIR / DEFAULT_ID / "reference.docx"
    return {"profile_path": prof_path, "profile_sha256": _file_sha256(prof_path) if prof_path.is_file() else "",
            "reference_path": ref_path, "reference_sha256": _file_sha256(ref_path) if ref_path.is_file() else ""}


def reference_source_changes(reference_path):
    """テンプレートから作る reference.docx の生成の記録 (<誌>/.reference.source) と今のファイルの食い違いを返す。

    記録は scripts/lib/ensure-reference.sh と make-reference.sh が書く sha256sum の形 (「SHA-256  パス」)。build のときは
    ensure-reference が食い違いを見て作り直すが、package は reference.docx を作り直さないので、build の後にテンプレートを
    差し替えたり戻したりすると、reference.docx の SHA-256 は記録どおりのまま古い体裁の本文が提出物になる。
    記録が無い誌 (テンプレートを雛形にしない誌) は空。読むだけで何も変えない。返り値: 食い違うパスの list。
    """
    rec = Path(reference_path).parent / ".reference.source"
    if not rec.is_file():
        return []
    changed = []
    for ln in rec.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^([0-9a-f]{64}) [ *](.+)$", ln)
        if not m:
            continue
        path = Path(m.group(2))
        if not path.is_file() or _file_sha256(path) != m.group(1):
            changed.append(m.group(2))
    return changed


def cmd_build_assets(args):
    """build.sh が出所の記録 (.build.source) に書く 2 行を出す。"""
    a = build_assets(args.journal)
    print(f"profile_sha256\t{a['profile_sha256']}")
    print(f"reference_sha256\t{a['reference_sha256']}")
    return 0


def cmd_inputs_sha256(args):
    """scripts/build.sh が .build.source の inputs_sha256 に書く値を出す (計算を 1 か所にする)。"""
    print(_inputs_sha256(args.input_root))
    return 0


def cmd_inputs_visible(args):
    """ホストで見える原稿の入力が、コンテナの中からも見えるかを確かめる (scripts/build.sh が呼ぶ)。

    見えないものがあれば「inputs-visible: 名前 …」の 1 行を出して終了コード 1。リポジトリの中を指す絶対パスのリンクを
    途中に挟む形のように、ホストのパスの判定では外に出ないのにコンテナからは読めない形をまとめて見つけるため。
    """
    root = Path(args.input_root)
    unseen = [n for n in args.names if not (root / n).exists()]
    if unseen:
        print("inputs-visible: " + " ".join(unseen))
        return 1
    return 0


def _inputs_sha256(root, names=("ref.bib", "cover-letter.md", "revise-report.md")):
    """原稿のほかの入力 (ref.bib / cover-letter.md / revise-report.md / figs/) の中身のハッシュ。

    「相対パス<TAB>SHA-256」の行を C ロケールの順に並べた全体の SHA-256。figs/mermaid/ 直下の .svg / .pdf と
    *.svg.png は除く。scripts/build.sh も出所の記録に書くときに、この関数をコンテナの中で呼ぶ (サブコマンド
    inputs-sha256)。計算を 1 か所にするのは、ホストとコンテナで別々に計算すると、コンテナから見えない
    リンクの先 (絶対パスのリンク・リポジトリの外を指すリンク) で値が食い違い、final が必ず止まるため。
    シンボリックリンクはリンクの先の中身を数え、figs の中のディレクトリのリンクもたどる。自分の祖先と同じ実体を
    指すディレクトリ (ループ) には入らない (find -L と同じ扱い)。
    コンテナから見えないリンクの先は数えない (build もそのファイルを読めないので、原稿の入力にならない)。
    figs の中のディレクトリのリンクは、ここではたどるが図の前処理 (process_figures.py) はたどらないので、
    そこに図を置くと build が止まる (広めに数えるのは安全側)。
    読めないファイルは中身の代わりに印を数える (止めずに、読めるようになれば値が変わる)。
    names=() で figs/ だけのハッシュになる (図の前処理の出所の記録に使う。_figs_sha256)。
    """
    root = Path(root)
    rows = []
    for name in names:
        f = root / name
        if f.is_file():
            rows.append((name, _file_sha256(f)))
    figs = root / "figs"
    if figs.is_dir():
        rels = []
        # 走査中のディレクトリの祖先 (自分を含む) の実体。find -L はこれと同じ実体のディレクトリだけをループとして避け、
        # 別の場所から同じ実体を 2 度たどるのは避けない
        chain = {}
        for dirpath, dirs, files in os.walk(figs, followlinks=True):
            here = os.path.realpath(dirpath)
            ancestors = chain.get(dirpath, frozenset()) | {here}
            keep = []
            for d in dirs:
                sub = os.path.join(dirpath, d)
                if os.path.realpath(sub) in ancestors:
                    continue
                chain[sub] = ancestors
                keep.append(d)
            dirs[:] = keep
            for fn in files:
                f = Path(dirpath) / fn
                if not f.is_file():
                    continue
                rel = f.relative_to(root).as_posix()
                # 除くのは生成物の残り: *.svg.png と、同じ名前の .mmd がある figs/mermaid/ の .svg / .pdf
                # (process_figures.py の _mermaid_leftover と同じ条件。.mmd の無い PDF は図として変換されるので数える)
                if rel.endswith(".svg.png") or (
                        rel.startswith("figs/mermaid/") and f.suffix in (".svg", ".pdf")
                        and (Path(dirpath) / (f.stem + ".mmd")).is_file()):
                    continue
                rels.append(rel)
        for rel in sorted(rels, key=lambda r: r.encode("utf-8")):
            rows.append((rel, _file_sha256(root / rel)))
    text = "".join(f"{a}\t{b}\n" for a, b in rows)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---- 図の前処理 (data/step01_figures/) の出所 ----
# 最終モードの提出物の図は step01 から作る。出所の照合 (_check_build_provenance) は main.docx と入力ルートを見るので、
# step01 を別に照合しないと、build の後に別の入力ルートで diff.sh (図の前処理を作り直す) を回したとき、同じ名前の図は
# 別の原稿のものが注意も無く提出物に入り、名前の違う図は欠ける。figures.sh が前処理の最後に入力ルートと figs/ の
# ハッシュを記録し、最終モードの package と --skip-figures の build / diff が照合する
FIGURES_SOURCE = Path("data/step01_figures/.figures.source")


def _figs_sha256(root):
    """figs/ の中身だけのハッシュ (数え方は _inputs_sha256 と同じ)。"""
    return _inputs_sha256(root, names=())


def _figure_outputs():
    """図の前処理が作った図 (data/step01_figures/figs/ の中。PDF は package.sh が後から書き足すので除く) の
    [(相対パス, SHA-256)]。"""
    figs = FIG_ROOT / "figs"
    if not figs.is_dir():
        return []
    rels = sorted((p.relative_to(FIG_ROOT).as_posix() for p in figs.rglob("*")
                   if p.is_file() and p.suffix.lower() != ".pdf"), key=lambda r: r.encode("utf-8"))
    return [(rel, _file_sha256(FIG_ROOT / rel)) for rel in rels]


def write_figures_source(input_root, expect=None):
    """図の前処理の出所の記録を書く (figures.sh が前処理の最後にコンテナの中で呼ぶ)。

    expect は前処理の前に取った figs/ のハッシュ。今のハッシュと違えば、前処理の最中に図が変わったので書かずに
    SystemExit (古い図を「今の図から作った」と記録しないため)。作った図の各ファイルの SHA-256 も書き、
    照合で記録の後の上書き (中断した build のコンテナが後から書くなど) を見つける。
    """
    now = _figs_sha256(input_root)
    if expect is not None and expect != now:
        sys.exit(f"エラー: 図の前処理の最中に {input_root}/figs/ が変わりました。図の前処理からやり直してください。")
    outputs = _figure_outputs()
    FIGURES_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    # 一時名に乱数を入れる (コンテナの中の PID は毎回同じになるため)
    tmp = FIGURES_SOURCE.with_name(f"{FIGURES_SOURCE.name}.{os.getpid()}.{os.urandom(4).hex()}")
    tmp.write_text(f"input_root\t{input_root}\nfigs_sha256\t{now}\noutputs\t{len(outputs)}\n"
                   + "".join(f"output\t{sha}\t{rel}\n" for rel, sha in outputs), encoding="utf-8")
    os.replace(tmp, FIGURES_SOURCE)


def figures_source_problem(input_root):
    """data/step01_figures/ の図が、今の入力ルートの今の figs/ から作ったものかを照合する。問題が無ければ None。"""
    if not FIGURES_SOURCE.is_file():
        return ("図の前処理の結果 (data/step01_figures/) をどの原稿から作ったかの記録 "
                "(data/step01_figures/.figures.source) がありません")
    lines = FIGURES_SOURCE.read_text(encoding="utf-8", errors="replace").splitlines()
    rec = dict(ln.split("\t", 1) for ln in lines if "\t" in ln and not ln.startswith("output\t"))
    rec_root = rec.get("input_root", "").strip()
    if not rec_root or Path(rec_root).resolve() != Path(input_root).resolve():
        return (f"data/step01_figures/ の図は {rec_root or '(不明)'} の原稿から作られています "
                f"(今回の入力ルートは {input_root})")
    if rec.get("figs_sha256", "").strip() != _figs_sha256(input_root):
        return f"data/step01_figures/ の図を作った後に {input_root}/figs/ が変わっています"
    # 作った図が記録の後に変わっていないか
    outs = [ln.split("\t", 2) for ln in lines if ln.startswith("output\t")]
    if "outputs" not in rec or str(len(outs)) != rec["outputs"].strip():
        return "図の前処理の出所の記録が古い形か壊れています (作った図の一覧がありません)"
    for _tag, sha, rel in outs:
        f = FIG_ROOT / rel
        if not f.is_file() or _file_sha256(f) != sha:
            return (f"data/step01_figures/{rel} が図の前処理の後に変わっています "
                    "(止めた build のコンテナが後から書いた場合などに起きる)")
    return None


def _require_figures_source(args, input_root):
    """最終モードで図を分離して出すときだけ、図の前処理の出所を照合して、食い違えば止める。"""
    problem = figures_source_problem(input_root)
    if problem:
        sys.exit(f"エラー: {problem}。\n"
                 "  提出物の図が別の原稿のものになったり欠けたりするのを防ぐため中止します。\n"
                 f"  'bash scripts/build.sh --journal {args.journal} --input {input_root}' で図の前処理から build し直すか、"
                 "'bash scripts/package.sh … --build' を使ってください。")


def _missing_figure(msg):
    """最終モードで提出する図が見つからないときに止める (注意だけで飛ばすと、図の欠けた提出物が終了コード 0 でできるため)。"""
    sys.exit(f"エラー: {msg}。\n"
             "  提出物から図が欠けるのを防ぐため中止します。原稿と同じ入力ルートで build から回し直してください。")


def cmd_figures_source(args):
    """サブコマンド figures-source: hash = figs/ のハッシュを出す / write = 記録を書く /
    check = 照合して、食い違えば理由を出して終了コード 1。"""
    if args.action == "hash":
        print(_figs_sha256(args.input_root))
        return
    if args.action == "write":
        write_figures_source(args.input_root, args.expect)
        return
    problem = figures_source_problem(args.input_root)
    if problem:
        print(problem, file=sys.stderr)
        sys.exit(1)


# ---- 同梱のサンプル (src/ のサンプル論文と data/dummy/ の動作例) の消し忘れ ----
# clone した直後の src/ には ABE の体裁のサンプル論文 (架空) がある。README の案内で汎用のサンプル (data/dummy/) を src/ に写すこともある。
# 自分の main.md に書き換えてもサンプルのカバーレター・回答書・文献・図・書式が残っていると、それが自分の論文の提出物に入る。
# 判定の規則は sample_files.py にまとめた (scripts/remove-sample.sh と同じ規則。指紋の一覧 scripts/lib/sample-files.sha256 の
# ABE のサンプルに加えて、src/ に写した汎用のサンプルと動作例の書式も数える)
import sample_files  # noqa: E402

SAMPLE_LIST = sample_files.SAMPLE_LIST


def sample_leftovers(input_root):
    """(main.md が同梱のサンプルそのものか, 中身がサンプルと同じまま残っている main.md 以外のファイル) を返す。

    中身 (SHA-256) で比べるので、書き換えたファイルや同じ名前の自分のファイルは数えない。一覧に同じパスの行が 2 つ以上あれば
    (公開した版ごとのサンプル)、どれかと一致すればサンプルとみなす。動作例 (data/dummy/ と data/dummy/abe/) はその場の中身と比べる。
    入力ルートが data/dummy/ の下なら (False, [])。規則は sample_files.py の冒頭。
    """
    return sample_files.leftovers(input_root)


def _sample_check(input_root, mode):
    """サンプルの消し忘れを確かめる。最終モードで消し忘れがあれば止め、それ以外は注意の文のリストを返す。"""
    is_sample, left = sample_leftovers(input_root)
    if Path(input_root).resolve() == Path("src").resolve():
        cmd = "bash scripts/remove-sample.sh"
    else:
        cmd = f"bash scripts/remove-sample.sh --input {input_root}"
    if is_sample:
        return [f"入力ルート {input_root} の原稿は、同梱のサンプル (src/ のサンプル論文か data/dummy/ の動作例。架空の論文) そのものです。"
                f"自分の論文を組むときは、先に '{cmd}' でサンプルのファイルを消してください"]
    if not left:
        return []
    msg = (f"入力ルート {input_root} の main.md は同梱のサンプルではないのに、サンプル (src/ のサンプル論文か data/dummy/ の動作例) の"
           f"ファイルが中身もそのまま残っています: {', '.join(left)}。このまま組むと、サンプルのカバーレター・回答書・文献・図・書式が"
           f"自分の論文の提出物に入ります。'{cmd}' でサンプルのファイルを消すか (中身がサンプルと同じファイルだけを消し、書き換えたファイルは"
           "残します)、自分の内容に書き換えてから、build からやり直してください")
    if mode == "final":
        sys.exit(f"エラー: {msg}。")
    return [msg]


def _check_build_provenance(args, profile, mode, input_root):
    """main.docx の有無と、どの雑誌・どの原稿から build したかを照合する。

    前回のパッケージを消す前に呼ぶ (消してから照合すると、--input を付け忘れて止まったときに
    確かめ済みのパッケージまで消えるため)。最終モードで食い違えば SystemExit。
    """
    main_build = BUILD_DIR / "main.docx"
    if not main_build.is_file():
        sys.exit(f"エラー: {main_build} がありません。先に 'bash scripts/build.sh' を実行してください。")

    # main.docx がどの雑誌で build されたかを照合し、--journal と異なれば警告
    # (package は事前 build の docx をそのまま使うため、雑誌固有体裁の取り違えを検知する)。
    # 提出用 (--mode final で --keep-figures なし) では止める。図表を本文に埋め込んだまま出す誌 (figures.separate: false) では
    # main.docx がそのまま提出物の本文になり、注意にとどめると、別の誌で build した 1 段組の docx が画面の注意 1 行だけで
    # 提出用のパッケージに入るため。草稿 (draft・--keep-figures) は注意だけ。食い違いは下の asset_problems に集め、最後にまとめて扱う
    asset_problems = []       # 誌・誌のプロファイル・reference.docx の食い違い
    built_for = ""
    prov = BUILD_DIR / ".journal"
    if prov.is_file():
        # 1 行目 = journal id (2 行目は記事種別の provenance。ここでの照合は
        # journal のみ — 記事種別は build の出力を変えないため不一致でも docx は正しい)
        prov_lines = prov.read_text(encoding="utf-8").splitlines()
        built_for = prov_lines[0].strip() if prov_lines else ""
        if built_for and built_for != args.journal:
            asset_problems.append(f"data/step02_build/main.docx は journal={built_for} で build されています "
                                  f"(今回の --journal {args.journal} と不一致)")
        # 2 行目 (記事種別) も照合する。
        # build を letter、package を既定 (original) で回すと 1200 語ではなく 4000 語で検証されるのに、
        # 照合しなければ何の注意も出ない。build の出力は種別で
        # 変わらないので docx 自体は正しく、警告に留める。
        built_type = prov_lines[1].strip() if len(prov_lines) > 1 else ""
        this_type = profile.get("article_type") or ""
        if built_type and this_type and built_type != this_type:
            print(f"  [注意] data/step02_build/main.docx は article_type={built_type} で "
                  f"build されています (今回の検証は {this_type})。語数・抄録の上限は {this_type} の値で照合します。"
                  f"意図が違う場合は '--article-type {built_type}' を付け直してください。")

    # main.docx を作った原稿が、今回 package する原稿と同じかを照合する。
    # 照合しないと、「--input で build して --input なしで package する」「原稿を直して build し直さずに
    # package する」で、提出物の本文 (main.docx 由来) と規定チェック・SUBMISSION.md (今回の原稿) が
    # 別の原稿を指すパッケージが黙ってできる。記録は build.sh が書く「キー<TAB>値」の行。
    cur_sha = build_source_problem = None
    rec = None
    cur_md = Path(input_root) / "main.md"
    if cur_md.is_file():
        cur_sha = hashlib.sha256(cur_md.read_bytes()).hexdigest()
    build_src = BUILD_DIR / ".build.source"
    if not build_src.is_file():
        build_source_problem = ("data/step02_build/main.docx をどの原稿から build したかの記録 "
                                "(data/step02_build/.build.source) がありません")
    else:
        # errors="replace": 壊れた記録でも traceback で落とさず、下の照合の食い違いとして止める
        rec = dict(ln.split("\t", 1) for ln in
                   build_src.read_text(encoding="utf-8", errors="replace").splitlines() if "\t" in ln)
        b_root, b_sha = rec.get("input_root", "").strip(), rec.get("main_sha256", "").strip()
        b_inputs = rec.get("inputs_sha256", "").strip()
        if not b_root or Path(b_root).resolve() != Path(input_root).resolve():
            build_source_problem = (f"data/step02_build/main.docx は {b_root or '(不明)'} の原稿から build されています "
                                    f"(今回の入力ルートは {input_root})")
        elif cur_sha and b_sha != cur_sha:
            build_source_problem = f"data/step02_build/main.docx を build した後に {cur_md} が変わっています"
        elif not b_inputs:
            # 原稿のほかの入力のハッシュの行が無い記録 (手で作った記録・壊れた記録)。
            build_source_problem = ("data/step02_build/.build.source に原稿のほかの入力 "
                                    "(ref.bib / cover-letter.md / revise-report.md / figs/) のハッシュがありません")
        elif b_inputs != _inputs_sha256(input_root):
            # main.md だけを見ると、文献・カバーレター・図を直して build し直さないパッケージが通り、
            # 提出物の本文とカバーレターが古い版のまま入る
            build_source_problem = (f"data/step02_build/main.docx を build した後に {input_root} の ref.bib / "
                                    "cover-letter.md / revise-report.md / figs/ のどれかが変わっています")
        elif rec.get("main_docx_sha256", "").strip() != hashlib.sha256(main_build.read_bytes()).hexdigest():
            # 記録を書いた build と main.docx を書いた build が違う (同じ作業ツリーで 2 つの build を
            # 同時に回した、または main.docx を手で差し替えた)。行の無い記録もここで止まる
            build_source_problem = ("data/step02_build/main.docx が、出所の記録 (data/step02_build/.build.source) を書いた "
                                    "build のものではありません")
    if build_source_problem:
        fix = (f"'bash scripts/build.sh --journal {args.journal} --input {input_root}' で build し直すか、"
               f"'bash scripts/package.sh … --build' を使ってください")
        if mode == "final" and not args.keep_figures:
            sys.exit(f"エラー: {build_source_problem}。\n"
                     f"  提出物の本文と規定チェックが別の原稿を指すのを防ぐため中止します。\n  {fix}")
        print(f"  [注意] {build_source_problem}。{fix}")

    # build したときの誌のプロファイルと reference.docx が今のものと同じかを照合する。build の後に
    # profile.yaml・reference.docx (・テンプレートなどその生成の元) を変えて build し直さずに package すると、提出物の本文は
    # 古い体裁のまま、規定チェックと SUBMISSION.md は新しい profile で作られる。記録は build.sh が .build.source に書く
    # profile_sha256 / reference_sha256 (今の値は build_assets。build.sh が記録に使うのと同じ関数)。
    # 誌が食い違うときは比べない (別の誌のファイルどうしを比べても意味がない。上の誌の食い違いだけを出す)
    if rec is not None:
        b_journal = rec.get("journal", "").strip()
        if b_journal and b_journal != args.journal and not (built_for and built_for != args.journal):
            asset_problems.append(f"data/step02_build/main.docx は journal={b_journal} で build されています "
                                  f"(今回の --journal {args.journal} と不一致)")
        if not asset_problems:
            now = build_assets(args.journal)
            b_prof, b_ref = rec.get("profile_sha256", "").strip(), rec.get("reference_sha256", "").strip()
            if not b_prof or not b_ref:
                asset_problems.append("data/step02_build/.build.source に誌のプロファイルと reference.docx の SHA-256 の行が"
                                      "ありません (記録が欠けている)")
            else:
                if b_prof != now["profile_sha256"]:
                    asset_problems.append(f"data/step02_build/main.docx を build した後に {now['profile_path']} が変わっています")
                if b_ref != now["reference_sha256"]:
                    asset_problems.append(f"data/step02_build/main.docx を build したときの reference.docx と、今の "
                                          f"{now['reference_path']} が違います (build の後に作り直したか差し替えた)")
            changed = reference_source_changes(now["reference_path"])
            if changed:
                asset_problems.append(f"{now['reference_path']} の生成の元 ({', '.join(changed)}) が、reference.docx を作った"
                                      "ときと違います (build の後にテンプレートなどを変えた。build し直すと作り直される)")
    if asset_problems:
        at = f" --article-type {args.article_type}" if args.article_type else ""
        fix = (f"'bash scripts/build.sh --journal {args.journal}{at} --input {input_root}' で build し直すか、"
               f"'bash scripts/package.sh --journal {args.journal}{at} --input {input_root} … --build' を使ってください")
        if mode == "final" and not args.keep_figures:
            sys.exit("エラー: " + "。\n  ".join(asset_problems) + "。\n"
                     "  提出用のパッケージ (--mode final) に、別の誌の体裁や build の後に変えた体裁と食い違う本文を入れないため"
                     f"中止します。\n  {fix}")
        for problem in asset_problems:
            print(f"  [注意] {problem}。{fix}")
    return cur_sha


def cmd_assemble(args):
    input_root = args.input_root
    # rmtree の前に journal id を検証する (不正値での破壊的削除を防ぐ)。
    out_dir = _safe_journal_out_dir(args.journal)
    profile = load_profile(args.journal, args.article_type)
    mode = resolve_mode(profile, args.mode)
    # 提出用か (for_submission) と、図を本文から外すか (separate) を分ける (docs/journal-abe.md §14.1)。
    #   for_submission = 出所の照合を止める側にする・SUBMISSION.md に「提出用ではない」を書かない・roundtrip が配送する
    #   separate       = 図を外して figures/ へ分離し、提出構成の組み替え (表の移設・図凡例の集約) を行い、CAPTIONS.md を書く
    # figures.separate を持たない誌 (既定 true) では 2 つが常に一致する (1 つの条件で分けるのと同じに動く)
    fig_separate = journal_profile.figures_separate(profile)   # 併用できないキーならここで止まる
    # 表の凡例を表の上へ移す誌 (tables.legend_position: above) と、表を本文から移す組み替え (tables.placement: end / separate) の
    # 併用も止める。build だけでなく package でも呼ぶ (直前に組んだパッケージを消す前)
    journal_profile.table_legend_position(profile)
    for_submission = (mode == "final" and not args.keep_figures)
    separate = for_submission and fig_separate
    if fig_separate:
        fmt = resolve_format(profile, args.format)
        export, fallback = resolved_export(fmt)
    else:
        # 図を分離しない誌では図の形式を使わない (resolve_format も通さない。jpeg などの形式の判定で止めないため)
        fmt, export, fallback = None, None, False
        if args.format:
            print(f"  [注意] この誌は figures.separate: false (図を本文に埋め込んだまま提出する) なので、"
                  f"--format {args.format} は使いません (図のファイルを別に作らないため)。")
        if mode == "final" and args.keep_figures:
            print("  [注意] figures.separate: false の誌では --keep-figures を付けても図の扱いは同じ (本文に埋め込んだまま) で、"
                  "パッケージが提出用でなくなるだけです (出所の照合は注意止まり・SUBMISSION.md は「提出用ではない」・roundtrip は配送しない)。")
    export_warning = None
    if separate:
        # --keep-figures は図を分離出力しない (禁止形式の図が生成されない) ため対象外。
        # 生成経路が無い形式はここで停止する (pdf などへの既定代替はしない)
        require_export_route(fmt, export)
        # 代替なら停止。明示指定は明示同意 (--allow-disallowed-format) を要求する
        export_warning = check_export_allowed(profile, fmt, export, fallback,
                                              args.allow_disallowed_format)
    dpi = resolve_dpi(profile, args.dpi)
    # pptx 経路の設定は「実際に pptx を出すとき」だけ解決する (綴り違いの検証を含むため、
    # pptx を使わない誌に無関係なエラーを出さない)。
    pptx_cfg = (resolve_pptx_cfg(profile, dpi, args.slide_fit)
                if export == "pptx" and separate else None)

    # main.docx の有無と出所の照合は、直前に作ったパッケージを消す前に行う。
    # 返り値は今回の main.md の SHA-256 (SUBMISSION.md の「原稿の SHA-256」に書く)
    cur_sha = _check_build_provenance(args, profile, mode, input_root)
    if for_submission:
        # 提出物の図 (step01) の出所。図を埋め込んだまま提出する誌 (figures.separate: false) でも照合する —
        # 埋め込んだ図は build が data/step01_figures/ から入れたもので、そのまま提出物の本文に入るため
        _require_figures_source(args, input_root)
    # 補足資料と記入済みの書式の止まる検査 (読めないリンク・拡張子をそろえると重なる書式の名前など) も、直前に組んだ
    # パッケージを消す前に行う (消した後で検査すると、止まったときに確かめ済みのパッケージまで失われる)
    supp_scan = scan_supplementary(input_root)
    collect_forms = journal_profile.as_flag(_submission_cfg(profile).get("collect_forms"),
                                            "submission.collect_forms", default=False)
    forms_scan = scan_forms(input_root) if collect_forms else None
    # 同梱のサンプル論文の消し忘れ (最終モードで消し残しがあれば止める)。これも前回のパッケージを消す前に確かめる
    sample_notes = _sample_check(input_root, mode)

    # 提出パッケージは生成物なので毎回作り直す (data/output/<journal>/ 全体を再生成)。
    # flat な data/output/*.docx (roundtrip 集約) は別物なので触らない。
    if out_dir.exists():
        print(f"  注意: 既存の {out_dir}/ を再生成します (手置きファイルがあれば事前に退避してください)")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"== Step 05 投稿パッケージ組立 ==")
    print(f"  INPUT_ROOT = {input_root}")
    print(f"  JOURNAL    = {args.journal}  ({profile.get('name', '(名称未設定)')})")
    if profile.get("article_types") and profile.get("article_type"):
        at = profile["article_type"]
        at_name = (profile["article_types"].get(at) or {}).get("name", "")
        print(f"  TYPE       = {at}  ({at_name})")
    if mode == "final" and not fig_separate:
        print(f"  MODE       = {mode}  (図: 埋込 = figures.separate: false)")
    else:
        print(f"  MODE       = {mode}  (図: {'埋込' if mode == 'draft' else '分離'})")
    if mode == "final" and not fig_separate:
        print("  FIGURES    = 本文に埋め込んだまま提出する (figures.separate: false。図の形式・dpi は使わない)")
    elif mode == "final":
        # export is None = 生成経路なし。--keep-figures のときだけここに来る (分離しないので害はない)
        if export is None:
            note = " [生成経路なし。--keep-figures のため図は分離しません]"
        else:
            note = f" [{fmt}→{export} 代替]" if fallback else ""
        print(f"  FIGURES    = 形式={fmt}{note} / dpi={dpi}")
        if pptx_cfg:
            print(f"  PPTX       = mode={pptx_cfg['mode']} / slide_fit={pptx_cfg['slide_fit']} / "
                  f"png_fallback_dpi={pptx_cfg['png_fallback_dpi']} / "
                  f"text_to_path={str(pptx_cfg['text_to_path']).lower()}")
        if export_warning:   # 受入形式外の図を作ろうとしている
            print(f"  {export_warning}")
    print(f"  OUT_DIR    = {out_dir}/")

    collected = []
    missing = []
    main_build = BUILD_DIR / "main.docx"

    # --- manuscript ---
    manuscript_out = out_dir / "manuscript.docx"
    # 受入形式外の警告は末尾の「図変換の注意」にも残す (冒頭表示だけだと流れる)
    fig_warnings = [export_warning] if export_warning else []
    struct_warnings = []                 # 提出構成の組み替え・表 lint の注意
    struct_warnings.extend(sample_notes)  # 同梱のサンプル論文の消し忘れ
    # 組み替えの結果 (SUBMISSION.md が読む)。草稿 / --keep-figures では何もしないので 0 のまま。
    r = {"stripped": 0, "figures": 0, "tables": 0, "legends_section": None, "tables_files": []}
    # 実行が実際に何をしたかを SUBMISSION.md へ渡す。
    #   separate    = 図の分離と提出構成の組み替えを行ったか (SUBMISSION.md へは relocated の名前で渡す)。提出用かどうかは for_submission
    #   fig_written = 分離出力した図を **書き出した順** で保つ (ディレクトリは読み直さない)
    fig_written = []
    manifest_flags = {}     # SUBMISSION.md の表に出す印 (表示名 → "⚠ 上限超過" 等)
    if separate:
        # 図のプレースホルダ化 → 提出構成の組み替え (表末尾移設 / Figure Legends 集約)
        # → 表の体裁 lint を 1 回の書庫の開閉で行う。
        r.update(strip_inline_figures(main_build, manuscript_out, profile=profile,
                                      tables_dir=out_dir / "tables"))
        n = r["stripped"]
        struct_warnings.extend(r["warnings"])
        struct_warnings.extend(r["lint"])
        label_extra = ""
        if r["figures"]:
            label_extra += f" / 図の題+凡例 {r['figures']} 組を '{r['legends_section']}' へ集約"
        if r["tables"]:
            label_extra += f" / 表 {r['tables']} 組を末尾へ移設"
        if r["tables_files"]:
            label_extra += f" / 表 {len(r['tables_files'])} 組を tables/ へ分離"
        collected.append((f"manuscript (図 {n} 件をプレースホルダ化{label_extra})",
                          str(manuscript_out)))
        for name, path in r["tables_files"]:
            collected.append((f"table (別ファイル) {name}", str(path)))
        # 除去した本文図数と原稿の図参照数を照合し、ずれれば警告 (番号ずれを黙認しない)。
        # 照合相手を body_only (テキストボックス内図を除く) にする。
        # (manifest 全件と比べると、textbox 内図があるだけで必ず不一致警告が出る)。
        n_refs = len(manuscript_figures(input_root, body_only=True))
        if n != n_refs:
            fig_warnings.append(
                f"本文から除去した図 {n} 件と原稿の本文図参照 {n_refs} 件が一致しません。"
                "本文中の非図 inline 画像がある場合、'[Figure N about here]' の番号と "
                "figures/ の番号がずれる可能性があります (要確認)。"
            )
        # 図を分離出力。書き出した順 (= 本文の初出順) をそのまま受け取り、
        # SUBMISSION.md へ渡す (ディレクトリを読み直すと文字列順になり初出順でなくなる)。
        n_fig, fw, fig_written = export_figures(
            input_root, profile, out_dir / "figures", fmt, export, fallback, dpi,
            pptx_cfg=pptx_cfg
        )
        fig_warnings.extend(fw)
        print(f"  figures: {n_fig} 件を {out_dir}/figures/ に分離出力")
        # figures/ の件数と Figure Legends の項目数が食い違うなら、
        # 図番号の 3 系統 (プレースホルダ / 集約した題 / 分離出力ファイル) が割れている。
        if r["legends_section"] and n_fig != r["figures"]:
            struct_warnings.append(
                f"★要注意: 分離出力した図 {n_fig} 件と '{r['legends_section']}' に集約した"
                f"題 {r['figures']} 件が一致しません。題の無い図があるか、図以外の inline 画像が"
                "本文に混ざっています (提出物で図と凡例の対応が崩れます)。")
    elif for_submission:
        # figures.separate: false (図表を本文に埋め込んで提出する誌): main.docx をそのまま提出用の本文にする。
        # 図を外さず、提出構成の組み替え (relocate.py) も通さない (併用できないキーは figures_separate() が止めた)。
        # 表の体裁 lint は草稿と同じく読むだけで掛ける。外した図の数と原稿の図の数の照合は行わない (外さないため)
        shutil.copyfile(main_build, manuscript_out)
        collected.append(("manuscript (図埋込・figures.separate: false)", str(manuscript_out)))
        struct_warnings.extend(lint_manuscript_tables(manuscript_out, profile))
    else:
        shutil.copyfile(main_build, manuscript_out)
        label = "manuscript (図埋込)" if mode == "draft" else "manuscript (図埋込・--keep-figures)"
        collected.append((label, str(manuscript_out)))
        # この経路では構成の組み替えをしない。profile が要求しているなら黙らせない。
        skipped = []
        if (_figures_cfg(profile).get("legends_section")):
            skipped.append(f"図凡例の '{_figures_cfg(profile)['legends_section']}' への集約")
        placement = relocate_mod.table_placement(profile)
        if placement == "end":
            skipped.append("表の末尾移設")
        elif placement == "separate":
            skipped.append("表の別ファイル化")
        if skipped:
            why = ("草稿モード" if mode == "draft" else "--keep-figures (図を本文に残す指定)")
            struct_warnings.append(
                f"{' と '.join(skipped)} は {why} のため行いませんでした。"
                "提出物を作るときは '--mode final' を --keep-figures なしで実行してください。")
        struct_warnings.extend(lint_manuscript_tables(manuscript_out, profile))

    # --- 差分 docx (任意。査読対応の提出に有用) ---
    # main.docx より古い差分なら陳腐化警告 (初回投稿への古い差分混入を防ぐ。
    # roundtrip.sh の phase_collect と同方式。同梱自体は維持し非破壊)。
    diff_src = DIFF_DIR / "main_diff.docx"
    skip_diff = False
    if diff_src.is_file():
        # 別の原稿・別の誌から作った差分や古い差分が、提出物に黙って混ざらないようにする。
        # diff.sh は誌と新版の原稿のパスを .main_diff.source に記録する。食い違えば SUBMISSION.md の注意にも載せる
        # (画面の 1 行だけだと、SUBMISSION.md を投稿前の確認の一覧として読む人が見落とす)。
        diff_notes = []
        rec = DIFF_DIR / ".main_diff.source"
        rec_lines = rec.read_text(encoding="utf-8").splitlines() if rec.is_file() else []
        d_journal = rec_lines[0].strip() if rec_lines else ""
        d_new = rec_lines[1].strip() if len(rec_lines) > 1 else ""
        d_sha = rec_lines[2].strip() if len(rec_lines) > 2 else ""
        d_type = rec_lines[3].strip() if len(rec_lines) > 3 else ""
        cur_md = Path(input_root) / "main.md"
        same_md = bool(d_new) and Path(d_new).resolve() == cur_md.resolve()
        if d_sha:
            # 新版の原稿の中身のハッシュで比べる (package.sh --build が main.docx を作り直しても誤って「古い」としない)。
            # 新版が別のファイルなら下の「新版が … である」で知らせるので、ここでは比べない
            if same_md and cur_md.is_file() and hashlib.sha256(cur_md.read_bytes()).hexdigest() != d_sha:
                diff_notes.append(f"差分を作った後に {input_root}/main.md が変わっている")
        elif main_build.is_file() and diff_src.stat().st_mtime < main_build.stat().st_mtime:
            # ハッシュの行が無い記録 (手で作ったものなど): 更新時刻で比べる
            diff_notes.append("data/step02_build/main.docx より古い")
        if rec.is_file():
            if d_journal and d_journal != args.journal:
                diff_notes.append(f"journal={d_journal} で作られている (今回は {args.journal})")
            if d_new and not same_md:
                diff_notes.append(f"新版が {d_new} である (今回の原稿は {input_root}/main.md)")
            if d_type and args.article_type and d_type != args.article_type:
                diff_notes.append(f"記事種別 {d_type} で作られている (今回は {args.article_type})")
        else:
            diff_notes.append("どの原稿から作ったかの記録が無い")
        if diff_notes and mode == "final":
            # 最終モードでは、出所の食い違う差分を提出物に入れない (入れると roundtrip.sh がパッケージごと Drive の
            # submission-<誌>/ に置く)。止めるとクイックスタートの 8. が通らないので、入れずに注意する
            skip_diff = True
            msg = ("data/step03_diff/main_diff.docx は " + " / ".join(diff_notes) + "。別の原稿や古い版の差分かもしれないので、"
                   "最終モードの提出物には入れなかった (manuscript-diff.docx は無い)。再投稿で使うなら 'bash scripts/diff.sh' で"
                   "作り直してから package し直してください")
            print(f"  [注意] {msg}")
            struct_warnings.append(msg)
        elif diff_notes:
            msg = ("manuscript-diff.docx (元は data/step03_diff/main_diff.docx) は "
                   + " / ".join(diff_notes) + "。別の原稿や古い版の差分かもしれないので、"
                   "再投稿で使うなら 'bash scripts/diff.sh' で作り直し、使わないなら "
                   "data/step03_diff/main_diff.docx を消してから package し直してください")
            print(f"  [注意] {msg}")
            struct_warnings.append(msg)
    if not skip_diff:
        _copy_if_exists(diff_src, out_dir / "manuscript-diff.docx",
                        "manuscript-diff (任意)", collected, missing)

    # --- revise-report / cover-letter (任意) ---
    # 前段 (build) の出力は入力ルートを切り替えても残るため、別原稿の
    # revise-report.docx が [OK] で提出物に並ぶことがある。build.sh 側でも掃除するが、
    # 「package だけ回した」「INPUT_ROOT を変えて package だけ回した」経路も残るので、
    # 一次ソース (<INPUT_ROOT>/<name>.md) の有無を照合して黙らせない。
    for opt in ("revise-report", "cover-letter"):
        docx = BUILD_DIR / f"{opt}.docx"
        if docx.is_file() and not (Path(input_root) / f"{opt}.md").is_file():
            print(f"  [注意] {docx} を集めましたが、今回の入力ルートに {input_root}/{opt}.md が"
                  f"ありません。**別の原稿でビルドした古い docx が混ざっている可能性**があります "
                  f"(不要なら {docx} を消してから再実行してください)。")
    _copy_if_exists(BUILD_DIR / "revise-report.docx", out_dir / "revise-report.docx",
                    "revise-report (任意)", collected, missing)
    _copy_if_exists(BUILD_DIR / "cover-letter.docx", out_dir / "cover-letter.docx",
                    "cover-letter (任意)", collected, missing)

    # --- supplementary / video の無変換パススルー ---
    supp_entries, video_entries = copy_supplementary(
        input_root, profile, out_dir, struct_warnings, flags=manifest_flags, scan=supp_scan)
    for label, entries in (("supplementary (無変換)", supp_entries),
                           ("supplementary (動画)", video_entries)):
        for name, path in entries:
            collected.append((f"{label} {name}", str(path)))
    # 補足資料の容量 (limits.supplementary_file_mb / supplementary_total_mb。規定チェックは validate が要修正で出す)。
    # 表の行にも印を付ける (画面のログは流れるが SUBMISSION.md は残る)
    supp_limits = supplementary_limit_notes(profile, supp_entries + video_entries, manifest_flags)

    # --- 記入済みの書式 (submission.collect_forms の誌だけ) ---
    forms_ctx = None
    if collect_forms:
        forms_ctx = copy_forms(input_root, out_dir, struct_warnings if for_submission else None,
                               scan=forms_scan)   # 読んだのは直前に組んだパッケージを消す前
        for name, path in forms_ctx["entries"]:
            collected.append((f"form (無変換) {name}", str(path)))
        # 書式の置き場所が git で無視されているか (入力ルートを src/ から変えたとき)。草稿でも出す
        git_note = forms_git_note(input_root)
        if git_note:
            print(f"  [注意] {git_note}")
            struct_warnings.append(git_note)
    # Word で PDF にして上げる docx の一覧 (roundtrip.sh が読む。提出用のパッケージだけ)
    upload_pdf = write_upload_pdf_list(out_dir, profile, forms_ctx) if for_submission else []

    # --- 検証 (語数・上限・執筆 lint) ---
    # **マニフェストを書く前に走らせる**。マニフェストを書いた
    # あとで validate を回すと、「規定違反の可能性 (要修正)」が
    # SUBMISSION.md に 1 件も載らない。しかもマニフェストは検出件数を断定的に書くので、
    # 画面に要修正が何件出ていても「この実行で 1 件の注意が出ている」と書いてしまう
    # (マニフェストは画面のログが流れたあとに残る唯一のチェックリストである)。
    # **validate はファイルに一切触れない**
    # (原稿と profile を読んで指摘を返すだけ。check_reference_layout も読み取りのみ) ため、
    # 先に回しても成果物は変わらない。指摘の一覧は下 (集約結果の後) で印字する。
    #
    # profile は解決済み (load_profile が article_type まで解決)。validate 側の再解決は
    # journal_profile.resolve の冪等ガード (_resolved) で素通りする。
    # journal_id を渡すと reference.docx の実体裁との突合も掛かる
    v_findings = None            # None = --no-validate で省略した (空リスト = 指摘なし と区別する)
    v_estimate = []              # 概算の行 (SUBMISSION.md の規定チェック節に転記する)
    if not args.no_validate:
        v_findings = validate_mod.validate(input_root, profile, args.article_type,
                                           journal_id=args.journal, estimate=v_estimate)

    # --- Caption / Legend の貼り付け用 CAPTIONS.md (提出用パッケージで、
    #     提出マニフェストを書く誌のみ = `submission` ブロックを持たない誌には出ない)。マニフェストより前に書き、
    #     マニフェストの「アップロード種別ではないもの」に載せる ---
    # 図表を分離しない誌 (figures.separate: false) では書かない — 本文の題と凡例がそのまま提出物になる
    if separate and has_submission_spec(profile):
        cap_entries = collect_caption_entries(manuscript_out, r["tables_files"], fig_written)
        captions = write_captions_manifest(out_dir, profile, args.journal, cap_entries)
        collected.append((f"CAPTIONS (Caption / Legend の貼り付け用。{len(cap_entries)} 件)",
                          str(captions)))
        for e in cap_entries:
            for n in e["notes"]:
                if n.startswith("⚠"):
                    struct_warnings.append(f"CAPTIONS.md の {e['kind']} {e['number']}: {n}")
        # 図ファイルの並び (Figure1, Figure2, …) が本文の図番号と一致するのは、図がすべて番号つきで 1 から順に並ぶとき
        # だけ (ラベルの無い図は本文で番号が振られないが、図ファイルは書き出した順に番号が付く)
        fig_numbers = [e["number"] for e in cap_entries if e["kind"] == "Figure"]
        figure_numbers_match = fig_numbers == list(range(1, len(fig_written) + 1))
        # 一致しない理由を出し分ける。ラベルの無い図は番号を持たず、テキストボックスの中の図は
        # 本文の図番号を取るが図ファイルにならない (番号が 1 から始まらないか、途中が飛ぶ)
        # テキストボックスの理由は、テキストボックスの図が本当にあるときだけ出し、書き出せなかった図があるときは
        # それを理由にする。図の前処理の結果が無い図は最終モードで止めるので、ここは念のための分岐
        n_textbox = len(manuscript_figures(args.input_root)) - len(manuscript_figures(args.input_root, body_only=True))
        n_skipped = len(manuscript_figures(args.input_root, body_only=True)) - len(fig_written)
        # 題の無い図は CAPTIONS の項目にならない (本文では番号が振られないが、図ファイルにはなる)。番号つきの図の番号が
        # 1 から順に並ばないときだけ、番号を取っているのに図ファイルにならない図 (テキストボックスの中の図) を理由にする
        n_untitled = len(fig_written) - len(fig_numbers)
        numbered = [n for n in fig_numbers if n is not None]
        if figure_numbers_match:
            figure_numbers_reason = None
        elif any(n is None for n in fig_numbers):
            figure_numbers_reason = ("番号の無い図 (相互参照のラベル {#fig:x} の無い図) があるため",
                                     "ラベルを付ければ一致する")
        elif n_skipped > 0:
            figure_numbers_reason = (f"本文の図のうち {n_skipped} 枚を図ファイルに書き出せなかったため (上の注意を見る)",
                                     "原稿と同じ入力ルートで build から回し直す")
        elif n_untitled > 0 and numbered == list(range(1, len(numbered) + 1)):
            figure_numbers_reason = (f"題 (キャプション) の無い図 {n_untitled} 枚も図ファイルとして書き出され、"
                                     "本文では番号が振られないため",
                                     "題の無い図が本文の末尾にまとまっていれば、それより前の図ファイルの番号は一致する。"
                                     "図なら題と {#fig:x} を付け、飾りの画像なら本文から外す")
        elif n_textbox > 0 and numbered != list(range(1, len(numbered) + 1)):
            figure_numbers_reason = ("図ファイルにならない図 (テキストボックスの中の図) が本文の図番号を取っているため",
                                     "図をテキストボックスの外に出せば一致する")
        else:
            figure_numbers_reason = ("図ファイルと本文の図番号の対応が取れないため",
                                     "CAPTIONS.md の図番号と図ファイルの対応を確かめる")
        if not figure_numbers_match:
            struct_warnings.append(
                f"★要注意: {figure_numbers_reason[0]}、図ファイルの番号 (FigureN) が"
                f"本文の図番号と一致しない ({figure_numbers_reason[1]})。CAPTIONS.md の図番号とファイルの対応を見てから上げること")
    else:
        figure_numbers_match = None
        figure_numbers_reason = None

    # --- 提出マニフェスト SUBMISSION.md (submission.text_formats を持つ誌のみ) ---
    if has_submission_spec(profile):
        structure = None
        if for_submission and not separate:
            structure = embedded_structure(profile)
        elif separate:
            parts_desc = ["Title page → Abstract → 本文 → Declarations → References"]
            if r["figures"]:
                parts_desc.append(f"**{r['legends_section']}** ({r['figures']} 組)")
            if r["tables"]:
                parts_desc.append(f"**表** ({r['tables']} 組)")
            structure = " → ".join(parts_desc) + "。" + \
                ("図は本文から分離し `[Figure N about here]` を残した。" if r["figures"] else "図は無い。")
            if r["tables_files"]:
                structure += ("表も本文から分離し `[Table N about here]` を残した "
                              "(表は `tables/` の 1 表 1 ファイル。本文の末尾には置いていない)。")
        manifest = write_submission_manifest(
            out_dir, profile, args.journal, mode,
            {
                "text": [(manuscript_out.name, manuscript_out)],
                # tables.placement: separate のときだけ非空 (end では本文末尾に含める)
                "tables_files": [(nm, p) for nm, p in r["tables_files"]] if separate else [],
                # export_figures が書き出した順 (= 本文の初出順) をそのまま使う
                "figures": list(fig_written),
                "figure_numbers_match": figure_numbers_match,
                "figure_numbers_reason": figure_numbers_reason,
                "video": [(n, p) for n, p in video_entries],
                "supplementary": [(n, p) for n, p in supp_entries],
                "other": [(Path(p).name, p) for label, p in collected
                          if Path(p).name in ("cover-letter.docx", "revise-report.docx",
                                              "manuscript-diff.docx", "CAPTIONS.md")],
                "structure": structure,
                "tables_moved": r["tables"] if separate else 0,
                "legends_section": r["legends_section"] if separate else None,
                # 実行時の状態と検出結果を渡す (profile と出力ディレクトリの中身だけでは
                # 「この実行が何をしたか / 何を見つけたか」が分からない)。
                "relocated": separate,
                "for_submission": for_submission,   # 提出用か (図を分離するかとは別。figures.separate: false の誌では違う)
                "supplementary_limits": supp_limits,
                "forms": forms_ctx,
                "upload_pdf": upload_pdf,
                # roundtrip.sh の配送前の照合に使う
                "input_root": str(input_root),
                "main_sha256": cur_sha or "",
                "assets": build_assets(args.journal),   # 誌のプロファイルと reference.docx
                "keep_figures": bool(args.keep_figures),
                "warnings": list(struct_warnings) + list(fig_warnings),
                "flags": manifest_flags,
                # 規定チェックの指摘 (None = --no-validate で省略)
                "findings": v_findings,
                "estimate": v_estimate,
            })
        collected.append(("SUBMISSION (提出マニフェスト)", str(manifest)))

    # --- 集約結果 ---
    print("\n-- 集約した提出物 --")
    for label, path in collected:
        print(f"  [OK]   {label}: {path}")
    for label, path in missing:
        print(f"  [skip] {label}: {path} は無し")

    # --- 検証結果の表示 (実行そのものはマニフェストより前で済ませてある) ---
    # 戻り値は Finding の list (level = 要修正 / 参考)。表示は validate 側に任せ、
    # 「規定違反の可能性 (要修正)」と「参考情報」に区分して出す。
    # 印字は集約結果の後に置く (実行そのものはマニフェストより前)。
    if v_findings is not None:
        print("\n-- 規定チェック (validate) --")
        validate_mod.print_findings(v_findings)

    # --- 匿名版の要求を黙殺しない (blinded はスキーマ拡張。自動伏字は未実装。docs/profile-schema.md) ---
    if profile.get("blinded"):
        print("\n  [注意] この雑誌は匿名版 (blinded: true / double-anonymous) を要求します。"
              "著者・所属の伏字は未自動化です — 提出前に手動で匿名化してください。")

    # --- 図変換の警告 ---
    if fig_warnings:
        print("\n-- 図変換の注意 --")
        for w in fig_warnings:
            print(f"  [注意] {w}")

    # --- 提出構成 (移設・集約・表の体裁・補足資料) の警告 ---
    if struct_warnings:
        print("\n-- 提出構成の注意 --")
        for w in struct_warnings:
            print(f"  [注意] {w}")

    print(f"\n== 完了: {out_dir}/ ==")
    return 0


# =====================================================================
# エントリ
# =====================================================================

def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--input-root", required=True, help="原稿ルート (data/dummy または src)")
    common.add_argument("--journal", default=DEFAULT_ID, help="雑誌プロファイル id (既定 _default)")
    common.add_argument("--article-type", default=None,
                        help="記事種別 (article_types を持つ誌のみ。limits/abstract を種別値で解決)")
    common.add_argument("--mode", choices=["draft", "final"], default=None,
                        help="図の扱い (既定: profile.figures.embed)")
    # 綴り違いが黙って別の形式に化けないよう受入値を明示する (検証は resolve_format)。
    # pptx はベクター提出。jpeg は生成非対応。
    common.add_argument("--format", default=None,
                        help="図形式の上書き (pdf/png/pptx/tiff/eps。jpeg は生成非対応)")
    # スライド寸法が規格 (1〜56 インチ) を外れる図の退避経路を CLI からも選べるようにする
    # (profile を書き換えずに済ませるため)。
    common.add_argument("--slide-fit", choices=list(PPTX_SLIDE_FITS), default=None,
                        help="pptx のスライド寸法 (figure=図の実寸 / fixed=既定サイズに中央配置)。"
                             "既定: profile.figures.pptx.slide_fit")
    common.add_argument("--font-handling", choices=["outline", "embed"], default=None,
                        help="最終図 svg→pdf のフォント処理上書き")
    # figure-plan も --keep-figures を解する。assemble 専用にすると、
    # 「図を分離しないので形式検査は対象外」という assemble 側の判断が figure-plan に伝わらず、
    # --keep-figures 付きでも figure-plan が受入形式照合で停止する (BHI の pptx 主形式で実測)。
    common.add_argument("--keep-figures", action="store_true",
                        help="最終モードでも図を manuscript に残す (分離しない)")
    # 受入形式外の形式を明示指定したときの明示同意。警告どまりで生成すると、
    # BHI で --format png と --format pdf を打ち間違えたときに規定違反の図一式が終了コード 0 で揃う。
    common.add_argument("--allow-disallowed-format", action="store_true",
                        help="誌の受入形式 (submission.figure_formats) 外の図を承知のうえで生成する")

    pp = sub.add_parser("figure-plan", parents=[common],
                        help="最終モードで pdf 化が要る非 mermaid svg を TSV 列挙")
    pp.set_defaults(func=cmd_figure_plan)

    pi = sub.add_parser("inputs-sha256",
                        help="原稿のほかの入力のハッシュを出す (build.sh が出所の記録に使う)")
    pi.add_argument("--input-root", required=True, help="原稿ルート")
    pi.set_defaults(func=cmd_inputs_sha256)

    pb = sub.add_parser("build-assets",
                        help="誌のプロファイルと build が使う reference.docx の SHA-256 を出す "
                             "(build.sh が出所の記録に使う)")
    pb.add_argument("--journal", required=True, help="雑誌プロファイル id")
    pb.set_defaults(func=cmd_build_assets)

    pv = sub.add_parser("inputs-visible",
                        help="ホストで見える原稿の入力がコンテナからも見えるかを確かめる (build.sh が使う)")
    pv.add_argument("--input-root", required=True, help="原稿ルート")
    pv.add_argument("names", nargs="*", help="確かめる入力の名前 (main.md・ref.bib・figs など)")
    pv.set_defaults(func=cmd_inputs_visible)

    pf = sub.add_parser("figures-source",
                        help="図の前処理の figs/ のハッシュを出す (hash) / 出所の記録を書く (write。figures.sh) / "
                             "照合する (check。--skip-figures の build と diff)")
    pf.add_argument("action", choices=("hash", "write", "check"))
    pf.add_argument("--input-root", required=True, help="原稿ルート")
    pf.add_argument("--expect", default=None,
                    help="write のとき、前処理の前に取った figs/ のハッシュ (違えば書かずに終了コード 1)")
    pf.set_defaults(func=cmd_figures_source)

    pa = sub.add_parser("assemble", parents=[common], help="提出一式を集約")
    pa.add_argument("--dpi", default=None, help="ラスタ図の dpi 上書き")
    pa.add_argument("--no-validate", action="store_true", help="語数等の検証をしない")
    pa.set_defaults(func=cmd_assemble)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
