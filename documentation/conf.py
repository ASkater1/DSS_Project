# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Food Security Dashboard'
copyright = '2026, Marc Avila Pedemonte (9780637), Tobias Buiten (9881174), Tim Kläring (7998805), Matthijs van Oord (9557296), Jari van Polen, Floris Smit (6947638)'
author = 'Marc Avila Pedemonte (9780637), Tobias Buiten (9881174), Tim Kläring (7998805), Matthijs van Oord (9557296), Jari van Polen, Floris Smit (6947638)'
release = '0.0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_autodoc_typehints",
    "myst_parser"
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
