# src/ — 原稿の正本 (一次ソース)

このディレクトリに**あなたの論文**を置く。`.development` マーカーが**無い**とき、`build.sh` / `diff.sh` /
`package.sh` はこの `src/` を入力ルート (`INPUT_ROOT`) にする。

## clone した直後: サンプル論文が入っている

clone した直後の `src/` には、ABE の Original Paper の体裁で書いたサンプル論文 (明らかなフィクション。TJD/THS のパロディで、
著者・所属・データは架空) が入っている。`data/dummy/abe/` の動作例に TJD の挿絵 (図 1。段抜きのラスタ図) を足したもので、そのまま組める:

```bash
bash scripts/build.sh   --journal abe --article-type original               # 先に学会テンプレートを data/journals/abe/ に置く
bash scripts/package.sh --journal abe --article-type original --mode final
```

書き換えて使ってもよい。別の原稿から始めるときは、先にサンプルを消す:

```bash
bash scripts/remove-sample.sh --dry-run   # 消すもの・残すものの一覧だけを出す
bash scripts/remove-sample.sh             # 中身がサンプルのままのファイルだけを消す (書き換えたファイルは残す)
```

自分の `main.md` の隣にサンプルのファイル (カバーレター・回答書・文献・図・ダミーの書式) が中身もそのまま残っていると、最終モードの
`package.sh` は止まる (サンプルのファイルが自分の提出物に入らないようにするため)。対象はこのサンプル論文と、`src/` に写した
`data/dummy/`・`data/dummy/abe/` の動作例 (中身で比べるので、書き換えたファイルは数えない)。サンプルから作った出力の見本は
`samples/` (`samples/README.md`) にある。

## 構成 (執筆時にここへ作る)

```
src/
├── main.md            # 本文 (必須)。タイトル/著者/抄録/キーワードは custom-style Div で書く
├── ref.bib            # 文献データベース (BibTeX)
├── revise-report.md   # リバイスレポート (査読対応。任意)
├── cover-letter.md    # カバーレター (任意)
├── forms/             # 記入済みの投稿書式 (git で追跡しない。ABE は package.sh が提出パッケージに複製する)
├── supplementary/     # 補足資料 (任意。無変換で提出パッケージに複製する)
└── figs/              # 図ソース (*.svg / *.pdf を手で配置)
    └── mermaid/       #   Mermaid 図ソース (*.mmd)
```

## 新規論文の始め方

ABE に出すなら、サンプルを消してから記入式の骨格を写す:

```bash
bash scripts/remove-sample.sh
[ -e src/main.md ] || cp data/journals/abe/skeleton/main.md src/main.md   # 記入欄は <<...>> (書き換えた main.md は上書きしない)
```

サンプル論文そのものを書き換えて使っているなら、このブロックも下の汎用のサンプルのブロックも回さない。`remove-sample.sh` は
書き換えた `main.md` が引いている (中身はサンプルのままの) `ref.bib` と図も消し、汎用のサンプルの `cp` は同じ名前のファイルを上書きする
(消えたファイルだけを戻すには `git ls-files --deleted src | xargs git checkout --`。`git checkout -- src/` は書き換えも元に戻す)。

ほかの誌に出すなら、汎用のサンプル (`data/dummy/`。タイトル/著者/抄録/本文/図 (SVG+PDF+mermaid)/引用/表/textbox を網羅) を写す:

```bash
bash scripts/remove-sample.sh
cp data/dummy/*.md data/dummy/ref.bib src/   # 汎用のサンプルの原稿・文献・カバーレター・回答書を src/ へ複製
cp -r data/dummy/figs/. src/figs/             # 図 (サブディレクトリの誌の動作例とフィクスチャは写さない)
rm -f .development             # 入力ルートを src に (.development があれば data/dummy になる)
$EDITOR src/main.md            # 自分の原稿に書き換える
```

ゼロから書く場合は `src/main.md` と `src/ref.bib` を新規作成する。**タイトル・著者・抄録・キーワードは
YAML メタではなく `custom-style` Div** で書くこと (構造保持 AST 差分で温存・差分化するため。CLAUDE.md の「原稿執筆の規約」)。

## 執筆 → 投稿の流れ

`docs/usage-guide.md` (操作ガイド: 図の追加 / 雑誌の追加 / 差分の出し方) と、リポジトリルートの
`README.md` (始め方の節) を参照。

> 注: `src/` 配下の原稿・図はあなたの著作物であり git 追跡される (`.gitignore` は中間/成果物と `src/forms/` を除外)。
> テンプレートを別リポジトリとして複製して使う想定。
