"""Progress reporting for document ingestion, so the UI can show the pipeline live.

A progress callback is called as  progress(stage, status, detail="", value=None)
  stage:  upload | extract | split | embed_sentences | chunk | embed_chunks | store | index
  status: running | done | skipped
  value:  optional fraction 0..1 for steps with a progress bar
"""
from collections.abc import Callable

Progress = Callable[..., None]


def no_progress(*_args, **_kwargs) -> None:
    """Default callback: ingestion without anyone watching."""
