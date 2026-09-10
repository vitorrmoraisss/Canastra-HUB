# matching/service.py
from __future__ import annotations

from django.conf import settings

from .matcher import JobMatcher

_matcher: JobMatcher | None = None


def get_matcher() -> JobMatcher:
    global _matcher
    if _matcher is None:
        _matcher = JobMatcher(persist_directory=str(settings.CHROMADB_PATH))
    return _matcher
