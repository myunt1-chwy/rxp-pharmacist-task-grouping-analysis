-- Resolve source-relative paths for the compiled PDF in outputs/reports/pdf.
function Image(image)
  image.src = image.src:gsub("^%.%./outputs/", "outputs/")
  return image
end

function Link(link)
  link.target = link.target:gsub("^%.%./outputs/", "../../")
  link.target = link.target:gsub("^%.%./generated/", "../../../generated/")
  return link
end

-- Article's sixth Markdown heading level otherwise becomes unstyled text.
function Header(header)
  if header.level > 5 then
    header.level = 5
  end
  return header
end

-- Rotate only tables that remain too wide for portrait pages.
function Pandoc(doc)
  local blocks = pandoc.List()
  local index = 1
  while index <= #doc.blocks do
    local block = doc.blocks[index]
    if block.t == "Header" and doc.blocks[index + 1]
        and doc.blocks[index + 1].t == "Table" then
      blocks:insert(pandoc.RawBlock("latex", "\\Needspace{8\\baselineskip}"))
      blocks:insert(block)
      index = index + 1
    elseif block.t == "Table" and #block.colspecs >= 8 then
      blocks:insert(pandoc.RawBlock("latex", "\\begin{landscape}"))
      blocks:insert(block)
      blocks:insert(pandoc.RawBlock("latex", "\\end{landscape}"))
      index = index + 1
    elseif block.t == "Table" and #block.colspecs == 7 then
      blocks:insert(pandoc.RawBlock("latex", "\\begingroup\\setlength{\\tabcolsep}{4pt}"))
      blocks:insert(block)
      blocks:insert(pandoc.RawBlock("latex", "\\endgroup"))
      index = index + 1
    elseif block.t == "Table" and #block.colspecs == 6 then
      local headings = {
        "Without same preceding", "With same preceding", "-1 residual SD",
        "+1 residual SD", "Difference", "Change (%)",
      }
      for column, heading in ipairs(headings) do
        block.head.rows[1].cells[column].contents = pandoc.read(heading, "markdown").blocks
      end
      blocks:insert(pandoc.RawBlock("latex", "\\begingroup\\setlength{\\tabcolsep}{5pt}"))
      blocks:insert(block)
      blocks:insert(pandoc.RawBlock("latex", "\\endgroup"))
      index = index + 1
    else
      blocks:insert(block)
      index = index + 1
    end
  end
  return pandoc.Pandoc(blocks, doc.meta)
end
