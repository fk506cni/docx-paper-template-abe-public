-- unnumbered-style.lua: 番号なしの見出し ({.unnumbered}) を、誌の「番号なし見出し」の段落スタイルにする (build / diff 共用)
--
-- 雑誌が配るテンプレートには、見出しのスタイル (heading 1 など) に自動番号 (numPr) を持たせ、番号の無い節
-- (Abstract / Conflicts of interest / References など) のために別の段落スタイルを用意しているものがある
-- (ABE の学会テンプレートの NoNumberSectionHeader。docs/journal-abe.md §8.2)。pandoc の docx の書き出しは
-- {.unnumbered} を見ず、番号なしの見出しも heading 1 にするので、テンプレートの自動番号が付いてしまう
-- (「6. Conflicts of interest」「8. References」。Word 実機で確かめた)。そこで {.unnumbered} の見出しを、
-- そのスタイルの段落 (custom-style の Div の中の段落) に置き換える。
--
-- スタイルの名前は誌の profile の headings.unnumbered_style で、build_docx.py / diff_docx.py がメタデータ
-- `unnumbered-style` で渡す。キーの無い誌ではこのフィルタ自体を掛けない (出力も pandoc の引数も変わらない)。
-- メタデータは読んだら消す (pandoc はメタデータを docx の docProps/custom.xml に書くので、提出物に残さないため)。
--
-- 【citeproc の後に掛ける】citeproc が足す文献の見出し (reference-section-title) も {.unnumbered} なので、
-- その後で掛けないと文献の見出しだけ番号つきのまま残る。build の順は
-- crossref → generic-style → citeproc → 本フィルタ、差分は … → citeproc → 本フィルタ → color-diff。
--
-- 見出しの識別子は Div に移す (pandoc は識別子のある Div をブックマークで囲むので、節への相互参照やリンクの
-- 行き先が残る)。見出しの段 (#, ##, …) によらず 1 つのスタイルにする — テンプレートの番号なしのスタイルは 1 つで、
-- heading 2 以下も自動番号を持つので、段を残すと番号が付く。
-- 見出しの中の差分の span (diff-add / diff-del) は段落の中にそのまま運ぶ (色は後の color-diff.lua が付ける)。
--
-- docx 出力時のみ有効。

if FORMAT ~= "docx" then
  return {}
end

return {
  { Pandoc = function(doc)
      local raw = doc.meta["unnumbered-style"]
      if raw == nil then
        return nil
      end
      doc.meta["unnumbered-style"] = nil
      local style = pandoc.utils.stringify(raw)
      if style == "" then
        return doc
      end
      local n = 0
      doc.blocks = doc.blocks:walk({
        Header = function(h)
          if h.classes:includes("unnumbered") then
            n = n + 1
            return pandoc.Div({ pandoc.Para(h.content) },
              pandoc.Attr(h.identifier, {}, { { "custom-style", style } }))
          end
        end
      })
      if n > 0 then
        io.stderr:write(string.format("  番号なしの見出し %d 個を段落スタイル '%s' にしました\n", n, style))
      end
      return doc
    end
  },
}
