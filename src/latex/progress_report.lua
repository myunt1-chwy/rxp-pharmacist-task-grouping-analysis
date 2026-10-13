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
