"""vault -> Quarto site publishing pipeline.

Deterministic conversion of Obsidian Markdown drafts (in ``~/vault/writing``)
into Quarto ``.qmd`` under this site's ``source/pages``. Git/PR orchestration
lives in the ``/publish`` Claude skill, not here -- this package never shells
out to git.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
