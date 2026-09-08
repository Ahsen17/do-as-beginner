import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

project = "do-as-beginner"
author = "ahsen17"
release = "0.1.0"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxcontrib.mermaid",
    "sphinxext.opengraph",
    "sphinx_tippy",
]

html_theme = "shibuya"

myst_enable_extensions = ["colon_fence", "deflist", "tasklist"]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

exclude_patterns = ["_build"]

# Mermaid
mermaid_parallel = True
mermaid_parallel_processes = 2
