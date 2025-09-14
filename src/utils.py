"""Small utilities used by the UI.

Note: Some functions may be legacy and not wired into the current UI. Kept for
backwards compatibility but candidates for cleanup.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from typing import Any, Dict, Optional


def format_date(date_string: str) -> Optional[Date]:
    """Parse a YYYY-MM-DD string into a `datetime.date`.

    Returns None when the input is invalid.
    """
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        return None

def validate_date(value: Any) -> bool:
    """Return True when the value is a `datetime` instance.

    This is primarily used for older code paths; new code prefers explicit
    types and validation at parse-time.
    """
    return isinstance(value, datetime)

def format_movie_data(movie: Any) -> Dict[str, Any]:
    """Serialize a movie-like object into a simple dict for display.

    Expected attributes: `title`, `addedAt` (datetime), `rating`, `summary`.
    """
    return {
        "title": getattr(movie, "title", None),
        "added_date": getattr(getattr(movie, "addedAt", None), "strftime", lambda _fmt: None)("%Y-%m-%d"),
        "rating": getattr(movie, "rating", None),
        "summary": getattr(movie, "summary", None),
    }
