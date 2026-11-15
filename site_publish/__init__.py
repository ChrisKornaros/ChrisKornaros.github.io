"""vault -> Quarto site publishing pipeline.

Deterministic conversion of Obsidian Markdown from the vault (posts drafted in
``~/vault/writing``, recipe pages in ``~/vault/library/food/recipes``) into
Quarto ``.qmd`` under this site's ``source/``. Git/PR orchestration
lives in the ``/publish`` Claude skill, not here -- this package never shells
out to git.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
