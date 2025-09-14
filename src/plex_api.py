import os
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()


class PlexAPI:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        if base_url is None:
            base_url = os.environ.get("PLEX_BASE_URL")
        if token is None:
            token = os.environ.get("PLEX_TOKEN")
        self.base_url = (base_url or "").rstrip("/")
        self.token = token or ""

    def _get_headers(self) -> Dict[str, str]:
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
        """Fetch items from a library section with pagination.

        Returns (items, total_size).
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

        response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
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
        # default first page only to avoid massive payloads
        items, _total = self.fetch_items("1", "1", start=0, size=100)
        return items

    def fetch_seasons(self, section_id: str):
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
        url = f"{self.base_url}/library/sections/{section_id}/all"
        params = {
            "type": str(type_id),
            "id": str(item_id),
            "addedAt.value": str(new_date_unix),
        }
        if lock:
            params["addedAt.locked"] = "1"
        response = requests.put(url, params=params, headers=self._get_headers(), timeout=30)
        response.raise_for_status()
        return True

    # --- Utilities ---
    def thumb_url(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        # Some thumbs are already absolute; if so, return as-is
        if path.startswith("http://") or path.startswith("https://"):
            # Ensure token
            joiner = "&" if "?" in path else "?"
            return f"{path}{joiner}X-Plex-Token={self.token}"
        return f"{self.base_url}{path}?X-Plex-Token={self.token}"
