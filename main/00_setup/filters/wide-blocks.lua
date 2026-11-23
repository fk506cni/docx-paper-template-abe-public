-- wide-blocks.lua: 段抜き (本文の段組をまたいで本文幅に置く) の図表に目印を付ける (build / diff 共用)
--
-- 本文を 2 段組にする誌 (誌の profile の layout.columns。ABE の学会テンプレート) で、段の幅に収まらない図表を
-- 本文幅で置くための記法の読み手。原稿の書き方は雑誌に依存しない:
--   図:   ![題](figs/x.svg){#fig:x .wide}
--   表など: ::: wide で囲む (表の題の {#tbl:x} に .wide を足すと pandoc-crossref が番号を付けられなくなるため、表は Div で書く)
-- 段組の無い誌 (1 段組) ではこのフィルタ自体を掛けない (build_docx.post_citeproc_args。pandoc の引数も出力も変わらない) ので、
-- `.wide` は何もしない。
-- 表の題に {#tbl:x .wide} と書いた表は (crossref が読めずに題に文字が残るので) 警告だけを出す (docx は変えない。
-- validate.py の lint.table_caption_attrs も同じことを原稿の段階で要修正にする)。
--
-- 段抜きにする範囲は「.wide の図 (または ::: wide の Div) + 直後に続く凡例 (custom-style="Legend" の Div) すべて」。
-- 凡例も本文幅に置くため (CLAUDE.md「図表の題と凡例の書き分け」の配置規則で凡例は対象の直後にある)。
-- 範囲の前後に隠しの目印の段落 (TextBoxMarker スタイル。.textbox / .grid と同じ形) WIDE_START / WIDE_END を置き、
-- 後処理 (main/step02_build/layout.py) が節の区切り (連続の節区切りで 1 段組の節を挟む。docs/journal-abe.md §11.3) に置き換えて目印を消す。
--
-- 目印を置く位置は本文の流れの上 (最上位と、custom-style も .textbox も持たない Div の中) だけ。テキストボックス・表・リストの中の
-- .wide は節で区切れないので、数えて警告するだけにする。テキストボックスは generic-style.lua が先に「目印 TEXTBOX_START + 中身 +
-- TEXTBOX_END」に展開しているので、その 2 つの目印の間も箱の中として扱う (Div の形では残っていない)。.grid の目印 (GRID_TABLE) は直後の表と隣り合っていないと効かないので、
-- 範囲の直前が GRID_TABLE なら WIDE_START をその前に置く。
--
-- 掛ける順: crossref → generic-style → citeproc → (unnumbered-style) → 本フィルタ (→ 差分では color-diff)。
-- docx 出力時のみ有効。

if FORMAT ~= "docx" then
  return {}
end

local CLASS = "wide"

local function marker(text)
  return pandoc.RawBlock("openxml",
    '<w:p><w:pPr><w:pStyle w:val="TextBoxMarker"/></w:pPr>' ..
    '<w:r><w:rPr><w:vanish/></w:rPr>' ..
    '<w:t xml:space="preserve">' .. text .. '</w:t></w:r></w:p>')
end

local function has_wide_image(block)
  local found = false
  pandoc.walk_block(block, {
    Image = function(img)
      if img.classes:includes(CLASS) then found = true end
    end
  })
  return found
end

--- 段抜きの範囲を始めるブロックか (.wide の図・.wide の画像だけの段落・::: wide の Div)
local function is_wide(block)
  if block.t == "Figure" then
    return block.classes:includes(CLASS) or has_wide_image(block)
  elseif block.t == "Para" or block.t == "Plain" then
    local imgs, other = 0, 0
    for _, il in ipairs(block.content) do
      if il.t == "Image" then
        if il.classes:includes(CLASS) then imgs = imgs + 1 else other = other + 1 end
      elseif il.t ~= "Space" and il.t ~= "SoftBreak" and il.t ~= "LineBreak" then
        other = other + 1
      end
    end
    return imgs > 0 and other == 0
  elseif block.t == "Div" then
    return block.classes:includes(CLASS)
  end
  return false
end

local function is_legend(block)
  return block.t == "Div" and block.attributes["custom-style"] == "Legend"
end

local function raw_marker(block, text)
  return block.t == "RawBlock" and block.format == "openxml" and block.text:find(text, 1, true) ~= nil
end

local function is_grid_marker(block)
  return raw_marker(block, "GRID_TABLE")
end

local function count_wide(blocks)
  local n = 0
  local doc = pandoc.Pandoc(blocks)
  doc:walk({
    Image = function(img) if img.classes:includes(CLASS) then n = n + 1 end end,
    Div = function(d) if d.classes:includes(CLASS) then n = n + 1 end end,
  })
  return n
end

--- 表の題に属性の文字列が残った表 ({#tbl:x .wide} など) の属性の list。
--- pandoc-crossref は表の題の末尾の {#tbl:x} しか読めず、クラスや key=value があると番号を付けずに題の文字のまま残す
--- (本フィルタは crossref の後に掛かるので、残った文字で見分けられる)。docx は変えず、警告だけを出す
local function stray_caption_attrs(doc)
  local hits = pandoc.List()
  doc:walk({
    Table = function(t)
      local cap = pandoc.utils.stringify(t.caption.long or {})
      local attr = cap:match("{#tbl:[^}]*}")
      if attr then hits:insert(attr) end
    end
  })
  return hits
end

local handled = 0

local function process(blocks)
  local out = pandoc.List()
  local i = 1
  local in_textbox = false
  while i <= #blocks do
    local b = blocks[i]
    if raw_marker(b, "TEXTBOX_START:") then
      in_textbox = true
      out:insert(b)
      i = i + 1
    elseif raw_marker(b, "TEXTBOX_END") then
      in_textbox = false
      out:insert(b)
      i = i + 1
    elseif in_textbox then
      out:insert(b)
      i = i + 1
    elseif is_wide(b) then
      local at = #out + 1
      if #out > 0 and is_grid_marker(out[#out]) then
        at = #out
      end
      out:insert(at, marker("WIDE_START"))
      out:insert(b)
      handled = handled + count_wide({ b })
      i = i + 1
      while i <= #blocks and is_legend(blocks[i]) do
        out:insert(blocks[i])
        i = i + 1
      end
      out:insert(marker("WIDE_END"))
    elseif b.t == "Div" and b.attributes["custom-style"] == nil and not b.classes:includes("textbox") then
      b.content = process(b.content)
      out:insert(b)
      i = i + 1
    else
      out:insert(b)
      i = i + 1
    end
  end
  return out
end

return {
  { Pandoc = function(doc)
      -- 表の題の .wide は段抜きにならず番号も付かないので、::: wide の Div で囲むよう警告する
      local stray = stray_caption_attrs(doc)
      if #stray > 0 then
        io.stderr:write(string.format(
          "  警告: 表の題に属性が文字のまま残っています (%s)。pandoc-crossref は表の題の {#tbl:x} しか読めないので、" ..
          "この表には番号が付かず、参照は ¿tbl:x? になります。段抜きにするなら表を題ごと ::: wide の Div で囲み、" ..
          "題の属性は {#tbl:x} だけにしてください\n", table.concat(stray, ", ")))
      end
      local total = count_wide(doc.blocks)
      if total == 0 then
        return nil
      end
      doc.blocks = process(doc.blocks)
      if handled < total then
        io.stderr:write(string.format(
          "  警告: .wide が %d 個ありますが、本文の流れの上に無いもの %d 個は段抜きにしません " ..
          "(テキストボックス・表・リスト・custom-style の Div の中など)\n", total, total - handled))
      end
      return doc
    end
  },
}
