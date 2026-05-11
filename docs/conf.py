"""Sphinx configuration for AgenticFlict documentation."""
import os
import sys

# Make the src/ modules importable by autodoc
sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -------------------------------------------------------
project = "AgenticFlict"
author = "Daniel Ogenrwot, John Businge"
copyright = "2026, Daniel Ogenrwot, John Businge"
release = "1.0.0"
version = "1.0"

# -- General configuration -----------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",       # Generate docs from docstrings
    "sphinx.ext.napoleon",      # Parse Google-style docstrings
    "sphinx.ext.viewcode",      # Add links to highlighted source
    "sphinx.ext.intersphinx",   # Link to external docs
]

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "member-order": "bysource",
}

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_use_rtype = True
napoleon_use_param = True
napoleon_use_ivar = True   # Prevents duplicate attribute entries for dataclasses

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
}

# Suppress duplicate-object warnings from dataclass field auto-documentation
suppress_warnings = ["ref.duplicate"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output ---------------------------------------------------
html_theme = "furo"

html_theme_options = {
    "source_repository": "https://github.com/unlv-evol/AgenticFlict",
    "source_branch": "main",
    "source_directory": "docs/",
}

html_title = "AgenticFlict"
html_static_path = []
