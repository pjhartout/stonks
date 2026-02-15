"""Sphinx configuration for stonks documentation."""

import sys
from pathlib import Path

# -- Path setup --------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# -- Project information -----------------------------------------------------
project = "stonks"
copyright = "2025, stonks contributors"
author = "stonks contributors"
version = "0.1.0"
release = version

# -- General configuration ---------------------------------------------------
extensions = [
    "autodoc2",
    "myst_parser",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
]

# -- MyST parser configuration -----------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
    "deflist",
    "tasklist",
]

# -- sphinx-autodoc2 configuration -------------------------------------------
autodoc2_packages = [
    {
        "path": "../stonks",
        "exclude_dirs": ["__pycache__", "server"],
    },
]
autodoc2_output_dir = "apidocs"
autodoc2_render_plugin = "myst"

# -- Napoleon configuration (Google-style docstrings) -------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True

# -- Intersphinx configuration ------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- HTML output configuration ------------------------------------------------
html_theme = "pydata_sphinx_theme"

html_theme_options = {
    "github_url": "https://github.com/pjhartout/stonks",
    "navbar_align": "left",
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "navigation_depth": 3,
    "show_nav_level": 1,
    "show_toc_level": 2,
    "collapse_navigation": True,
    "pygments_light_style": "default",
    "pygments_dark_style": "monokai",
    "secondary_sidebar_items": ["page-toc", "edit-this-page"],
    "show_prev_next": True,
    "back_to_top_button": True,
    "logo": {
        "text": "stonks",
    },
}

html_context = {
    "github_user": "pjhartout",
    "github_repo": "stonks",
    "github_version": "main",
    "doc_path": "docs",
}

html_static_path = ["_static"]
html_title = "stonks"

# -- Source configuration -----------------------------------------------------
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "myst",
}

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
suppress_warnings = ["myst.header"]
