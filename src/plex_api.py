"""Thin wrapper around the Plex HTTP API used by the UI and CLI.

Responsibilities
- Build a retrying `requests.Session` tuned for Plex endpoints
- Fetch items with pagination and basic filters
- Update the `addedAt` field with optional locking
- Provide helpers for section discovery and thumbnail URLs
"""

import os
from typing import Dict, List, Optional, Tuple

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()


class PlexAPI:
    """Simple client for interacting with a Plex server.

    Parameters
    - base_url: Base server URL (e.g., http://host:32400). Falls back to env var `PLEX_BASE_URL`.
    - token: Plex token. Falls back to env var `PLEX_TOKEN`.
    """
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        if base_url is None:
            base_url = os.environ.get("PLEX_BASE_URL")
        if token is None:
            token = os.environ.get("PLEX_TOKEN")
        self.base_url = (base_url or "").rstrip("/")
        self.token = token or ""
        self.session = self._build_session()

    def _build_session(self) -> Session:
        """Return a `requests.Session` with sensible retries for Plex.

        Retries on 429/5xx with exponential backoff for GET/PUT.
        """
        s = requests.Session()
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            status=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET", "PUT"},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        return s

    def _get_headers(self) -> Dict[str, str]:
        """Headers attached to every request."""
        return {
            "X-Plex-Token": self.token,
            "Accept": "application/json",
        }

    # --- Fetching ---
    def fetch_items(
        self,
        section_id: str,
        type_id: str,
        *,
        start: int = 0,
        size: int = 100,
        sort: str = "addedAt:desc",
        filters: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[dict], int]:
        """Fetch items from a section with pagination.

        Returns
        - (items, total_size)
        """
        url = f"{self.base_url}/library/sections/{section_id}/all"
        params: Dict[str, str] = {
            "type": str(type_id),
            "sort": sort,
            "X-Plex-Container-Start": str(start),
            "X-Plex-Container-Size": str(size),
        }
        if filters:
            params.update({k: str(v) for k, v in filters.items() if v not in (None, "")})

        response = self.session.get(url, headers=self._get_headers(), params=params, timeout=30)
        response.raise_for_status()
        container = response.json().get("MediaContainer", {})
        items = container.get("Metadata", []) or []
        total = container.get("totalSize")
        if total is None:
            # Fallbacks used by Plex in some builds
            total = container.get("size", len(items))
        return items, int(total)

    # Backwards compatibility helpers
    def get_all_movies(self):
        """Back-compat helper that returns the first page of movies."""
        # default first page only to avoid massive payloads
        items, _total = self.fetch_items("1", "1", start=0, size=100)
        return items

    def fetch_seasons(self, section_id: str):
        """Back-compat helper to fetch first page of shows for a section."""
        # In Plex, type=2 is "show" (series). Keep prior behavior.
        items, _total = self.fetch_items(section_id, "2", start=0, size=100)
        return items

    # --- Update ---
    def update_added_date(
        self,
        section_id: str,
        item_id: str,
        type_id: str,
        new_date_unix: int,
        *,
        lock: bool = True,
    ) -> bool:
        """Update the `addedAt` timestamp for a specific item.

        Parameters
        - section_id: Library section id
        - item_id: The item's ratingKey
        - type_id: Plex type id ("1" movie, "2" show)
        - new_date_unix: Unix timestamp (seconds)
        - lock: When True, locks the field to prevent future auto changes
        """
        url = f"{self.base_url}/library/sections/{section_id}/all"
        params = {
            "type": str(type_id),
            "id": str(item_id),
            "addedAt.value": str(new_date_unix),
        }
        if lock:
            params["addedAt.locked"] = "1"
        response = self.session.put(url, params=params, headers=self._get_headers(), timeout=30)
        response.raise_for_status()
        return True

    # --- Utilities ---
    def thumb_url(self, path: Optional[str]) -> Optional[str]:
        """Return an absolute, tokenized image URL given a Plex thumb path."""
        if not path:
            return None
        # Some thumbs are already absolute; if so, return as-is
        if path.startswith("http://") or path.startswith("https://"):
            # Ensure token
            joiner = "&" if "?" in path else "?"
            return f"{path}{joiner}X-Plex-Token={self.token}"
        return f"{self.base_url}{path}?X-Plex-Token={self.token}"

    # --- Sections ---
    def get_sections(self) -> List[dict]:
        """Return available library sections (key, title, type)."""
        url = f"{self.base_url}/library/sections"
        resp = self.session.get(url, headers=self._get_headers(), timeout=30)
        resp.raise_for_status()
        container = resp.json().get("MediaContainer", {})
        dirs = container.get("Directory", []) or []
        # Normalize fields
        out: List[dict] = []
        for d in dirs:
            out.append({
                "key": str(d.get("key")),
                "title": d.get("title") or d.get("title1") or "Section",
                "type": d.get("type"),  # e.g., 'movie', 'show', 'artist', etc.
            })
        return out
