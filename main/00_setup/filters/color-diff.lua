-- color-diff.lua: 差分 span を文字スタイルへマップする (差分経路 step03 専用)
--
-- 構造保持 AST 差分 (main/step03_diff/) が付けた以下の Span を、docx の文字スタイル参照へ変換する:
--   [..]{.diff-add} → custom-style="DiffAdd" (青 #2E74B5)
--   [..]{.diff-del} → custom-style="DiffDel" (赤 #C00000 + 取消線)
--
-- 【重要】生 OOXML run は生成しない (docs/architecture.md §2.0 / §2.3、
-- docs/design-fullarea-diff.md §4)。理由:
--   - custom-style="DiffAdd" は pandoc docx ライタが <w:rStyle w:val="DiffAdd"/> を出すだけで、色そのものは
--     持たない。色の実体 (DiffAdd 青 / DiffDel 赤+取消線) は差分後処理 (lxml) が生成 docx の word/styles.xml へ
--     **冪等注入**する。これにより雑誌提供テンプレ (2 スタイルを持たない) でも差分色が出る。
--   - 色は run プロパティ (w:rStyle) として乗るため、postprocess.py の wrap_textboxes() が run を textbox へコピーする際にも
--     そのまま運ばれる → テキストボックス内セルの差分も色付きになる。
--   - 生インライン OOXML (`...`{=openxml}) は文脈により docx を壊す既知問題 (jgm/pandoc #5094/#6933) があり使わない。
--
-- Cite / 相互参照 / 数式は差分エンジン側で要素のまま温存されており、本フィルタは触らない。
-- docx 出力時のみ有効。フィルタ適用順は crossref → generic-style → citeproc → color-diff (最後)。
--
-- 【式とリンクの色】pandoc の docx ライタは、式 (OMML) には文字スタイルを掛けず、リンク (pandoc-crossref の図表・式の参照
-- Fig. 1 / Table 2 / Eq. 1 など) の文字には Hyperlink の文字スタイルを掛けるので、custom-style だけでは書き換えた式と参照に
-- 差分の色が付かない (旧と新の式が黒のまま並び、消した参照も取消線なしのリンクの色で並ぶ)。
-- 式・リンク・脚注を含む差分 Span には識別子 DiffAddMark<N> / DiffDelMark<N> を付け、pandoc が書くブックマークを目印に、
-- 差分の後処理 (main/step03_diff/diff_docx.py の _color_diff_marks) が範囲の中の式の文字 (m:r) とリンクの文字に差分の書式を付けて
-- ブックマークを消す。識別子を持つ Span (pandoc-crossref の式のラベルなど) には付けない (差分 Span はその外側にある)
--
-- 【脚注の色】差分 Span の中の脚注 (Note) は、Span の文字スタイルが脚注の本文に及ばず、参照の番号も
-- 脚注の参照の文字スタイルで書かれるので、書き換えた脚注は旧と新が無色で 2 つ並ぶ。差分 Span の中の脚注の本文の段落を
-- 同じ差分の文字スタイルの Span で包み (本文に式かリンクがあればその Span にも識別子を付ける。目印は脚注のパートに出る)、
-- 脚注を含む差分 Span にも識別子を付ける。diff_docx.py の _color_diff_marks が、範囲の中の脚注の参照の run と、その脚注の番号の run に
-- 差分の書式 (色・削除は取消線) を直に付ける (文字スタイルは脚注の参照 = 上付きのまま)

if FORMAT ~= "docx" then
  return {}
end

local marked = 0

local function has_marked_content(el)
  local found = false
  el:walk({
    Math = function() found = true end,
    Link = function() found = true end,
    Note = function() found = true end,
  })
  return found
end

local function set_mark_id(el, style)
  if el.identifier == "" and has_marked_content(el) then
    marked = marked + 1
    el.identifier = style .. "Mark" .. marked
  end
end

-- 脚注の本文の段落の中身を、差分の文字スタイルの Span で包む
local function wrap_para(p, style)
  if #p.content == 0 then
    return nil
  end
  local span = pandoc.Span(p.content)
  span.attributes["custom-style"] = style
  set_mark_id(span, style)
  p.content = { span }
  return p
end

local function color_notes(el, style)
  return el:walk({
    Note = function(n)
      n.content = n.content:walk({
        Para = function(p) return wrap_para(p, style) end,
        Plain = function(p) return wrap_para(p, style) end,
      })
      return n
    end,
  })
end

local function mark(el, cls, style)
  el.attributes["custom-style"] = style
  el.classes = el.classes:filter(function(c) return c ~= cls end)
  set_mark_id(el, style)
  return color_notes(el, style)
end

return {
  Span = function(el)
    if el.classes:includes("diff-add") then
      return mark(el, "diff-add", "DiffAdd")
    elseif el.classes:includes("diff-del") then
      return mark(el, "diff-del", "DiffDel")
    end
  end,
}
