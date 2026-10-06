"""Sphinx configuration for the repository documentation."""

project = "rxp-task-reordering"
copyright = "2026"

extensions = ["myst_parser"]
source_suffix = {".md": "markdown"}
exclude_patterns = ["_build"]
myst_heading_anchors = 3
html_theme = "alabaster"
