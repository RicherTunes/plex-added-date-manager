import os
import time
from typing import Callable, Dict, List, Optional, Tuple

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
        self.session = self._build_session()

    def _build_session(self) -> Session:
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
            params.update(
                {k: str(v) for k, v in filters.items() if v not in (None, "")}
            )

        response = self.session.get(
            url, headers=self._get_headers(), params=params, timeout=30
        )
        response.raise_for_status()
        container = response.json().get("MediaContainer", {})
        items = container.get("Metadata", []) or []
        total = container.get("totalSize")
        if total is None:
            # Fallbacks used by Plex in some builds
            total = container.get("size", len(items))
        return items, int(total)

    # (removed unused legacy helpers get_all_movies/fetch_seasons)

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
        response = self.session.put(
            url, params=params, headers=self._get_headers(), timeout=30
        )
        response.raise_for_status()
        return True

    # --- Music ---
    def fetch_artists(
        self,
        section_id: str,
        *,
        start: int = 0,
        size: int = 100,
        sort: str = "addedAt:desc",
    ) -> Tuple[List[dict], int]:
        """Fetch artists (type=8) from a music library section."""
        return self.fetch_items(section_id, "8", start=start, size=size, sort=sort)

    def fetch_albums_for_artist(
        self,
        section_id: str,
        artist_id: str,
        *,
        start: int = 0,
        size: int = 100,
        sort: str = "addedAt:desc",
    ) -> Tuple[List[dict], int]:
        """Fetch albums (type=9) for a specific artist."""
        url = f"{self.base_url}/library/sections/{section_id}/all"
        params: Dict[str, str] = {
            "type": "9",
            "artist.id": artist_id,
            "sort": sort,
            "X-Plex-Container-Start": str(start),
            "X-Plex-Container-Size": str(size),
        }
        response = self.session.get(url, headers=self._get_headers(), params=params, timeout=30)
        response.raise_for_status()
        container = response.json().get("MediaContainer", {})
        items = container.get("Metadata", []) or []
        total = container.get("totalSize")
        if total is None:
            total = container.get("size", len(items))
        return items, int(total)

    def fetch_tracks_for_album(
        self,
        section_id: str,
        album_id: str,
        *,
        start: int = 0,
        size: int = 100,
        sort: str = "addedAt:desc",
    ) -> Tuple[List[dict], int]:
        """Fetch tracks (type=10) for a specific album."""
        url = f"{self.base_url}/library/sections/{section_id}/all"
        params: Dict[str, str] = {
            "type": "10",
            "album.id": album_id,
            "sort": sort,
            "X-Plex-Container-Start": str(start),
            "X-Plex-Container-Size": str(size),
        }
        response = self.session.get(url, headers=self._get_headers(), params=params, timeout=30)
        response.raise_for_status()
        container = response.json().get("MediaContainer", {})
        items = container.get("Metadata", []) or []
        total = container.get("totalSize")
        if total is None:
            total = container.get("size", len(items))
        return items, int(total)

    # --- File date sync ---

    @staticmethod
    def get_file_date(path: str) -> Optional[int]:
        """Return birthtime (unix ts) of file, fallback to mtime. None if file doesn't exist."""
        try:
            st = os.stat(path)
            try:
                return int(st.st_birthtime)
            except (AttributeError, OSError):
                pass
            return int(st.st_mtime)
        except (OSError, TypeError):
            return None

    @staticmethod
    def _has_birthtime(path: str) -> bool:
        try:
            st = os.stat(path)
            try:
                st.st_birthtime
                return True
            except (AttributeError, OSError):
                return False
        except OSError:
            return False

    def sync_dates_from_files(
        self,
        section_id: str,
        *,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict:
        """Build a sync plan from file dates. Read-only — does NOT apply changes."""
        plan: Dict = {"tracks": [], "albums": {}, "artists": {}, "stats": {}}
        all_tracks: List[dict] = []
        start = 0
        page_size = 200
        while True:
            batch, total = self.fetch_items(section_id, "10", start=start, size=page_size, sort="addedAt:asc")
            all_tracks.extend(batch)
            if progress_callback:
                progress_callback("fetching_tracks", len(all_tracks), total)
            start += page_size
            if start >= total:
                break
        tracks_updated = 0
        tracks_skipped = 0
        tracks_no_file = 0
        for idx, track in enumerate(all_tracks):
            rk = str(track.get("ratingKey", ""))
            title = track.get("title", "Unknown")
            old_added = int(track.get("addedAt", 0) or 0)
            album_id = str(track.get("parentRatingKey", "") or "")
            artist_id = str(track.get("grandparentRatingKey", "") or "")
            media = track.get("Media") or []
            part = (media[0].get("Part") or [{}])[0] if media else {}
            file_path = part.get("file", "")
            if not file_path:
                tracks_no_file += 1
                continue
            new_date = self.get_file_date(file_path)
            if new_date is None:
                tracks_no_file += 1
                continue
            if new_date == old_added:
                tracks_skipped += 1
                continue
            source = "mtime"
            try:
                st = os.stat(file_path)
                try:
                    st.st_birthtime
                    source = "birthtime"
                except (AttributeError, OSError):
                    pass
            except OSError:
                pass
            tracks_updated += 1
            plan["tracks"].append({
                "id": rk, "title": title, "old_date": old_added, "new_date": new_date,
                "source": source, "path": file_path, "album_id": album_id, "artist_id": artist_id,
            })
            if album_id:
                if album_id not in plan["albums"] or new_date > plan["albums"][album_id]["new_date"]:
                    plan["albums"][album_id] = {"id": album_id, "new_date": new_date, "old_date": 0, "title": track.get("parentTitle", "Unknown Album")}
            if artist_id:
                if artist_id not in plan["artists"] or new_date > plan["artists"][artist_id]["new_date"]:
                    plan["artists"][artist_id] = {"id": artist_id, "new_date": new_date, "old_date": 0, "title": track.get("grandparentTitle", "Unknown Artist")}
            if progress_callback and (idx + 1) % 500 == 0:
                progress_callback("reading_files", idx + 1, len(all_tracks))
        album_old_dates: Dict[str, int] = {}
        artist_old_dates: Dict[str, int] = {}
        if plan["albums"]:
            s = 0
            while True:
                batch, tot = self.fetch_items(section_id, "9", start=s, size=200, sort="addedAt:asc")
                for a in batch:
                    aid = str(a.get("ratingKey", ""))
                    if aid in plan["albums"]:
                        album_old_dates[aid] = int(a.get("addedAt", 0) or 0)
                        plan["albums"][aid]["title"] = a.get("title", plan["albums"][aid]["title"])
                s += 200
                if s >= tot or not batch:
                    break
        if plan["artists"]:
            s = 0
            while True:
                batch, tot = self.fetch_items(section_id, "8", start=s, size=200, sort="addedAt:asc")
                for a in batch:
                    arid = str(a.get("ratingKey", ""))
                    if arid in plan["artists"]:
                        artist_old_dates[arid] = int(a.get("addedAt", 0) or 0)
                        plan["artists"][arid]["title"] = a.get("title", plan["artists"][arid]["title"])
                s += 200
                if s >= tot or not batch:
                    break
        for album_id, album_plan in plan["albums"].items():
            album_plan["old_date"] = album_old_dates.get(album_id, 0)
        for artist_id, artist_plan in plan["artists"].items():
            artist_plan["old_date"] = artist_old_dates.get(artist_id, 0)
        plan["albums"] = {k: v for k, v in plan["albums"].items() if v["old_date"] != v["new_date"] and v["old_date"] > 0}
        plan["artists"] = {k: v for k, v in plan["artists"].items() if v["old_date"] != v["new_date"] and v["old_date"] > 0}
        plan["stats"] = {"total_tracks": len(all_tracks), "tracks_updated": tracks_updated, "tracks_skipped": tracks_skipped, "tracks_no_file": tracks_no_file, "albums_updated": len(plan["albums"]), "artists_updated": len(plan["artists"])}
        return plan

    def apply_sync_plan(
        self,
        section_id: str,
        plan: Dict,
        *,
        lock: bool = True,
        rate_limit: int = 0,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict:
        ok = 0
        errors = 0
        per_item_sleep = (60.0 / rate_limit) if rate_limit > 0 else 0.0
        total_items = len(plan["tracks"]) + len(plan["albums"]) + len(plan["artists"])
        processed = 0
        for track in plan["tracks"]:
            try:
                self.update_added_date(section_id, track["id"], "10", track["new_date"], lock=lock)
                ok += 1
            except Exception:
                errors += 1
            processed += 1
            if progress_callback:
                progress_callback("tracks", processed, total_items)
            if per_item_sleep:
                time.sleep(per_item_sleep)
        for album_id, album_plan in plan["albums"].items():
            try:
                self.update_added_date(section_id, album_id, "9", album_plan["new_date"], lock=lock)
                ok += 1
            except Exception:
                errors += 1
            processed += 1
            if progress_callback:
                progress_callback("albums", processed, total_items)
            if per_item_sleep:
                time.sleep(per_item_sleep)
        for artist_id, artist_plan in plan["artists"].items():
            try:
                self.update_added_date(section_id, artist_id, "8", artist_plan["new_date"], lock=lock)
                ok += 1
            except Exception:
                errors += 1
            processed += 1
            if progress_callback:
                progress_callback("artists", processed, total_items)
            if per_item_sleep:
                time.sleep(per_item_sleep)
        return {"updated": ok, "errors": errors, "total": total_items}

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
            out.append(
                {
                    "key": str(d.get("key")),
                    "title": d.get("title") or d.get("title1") or "Section",
                    "type": d.get("type"),  # e.g., 'movie', 'show', 'artist', etc.
                }
            )
        return out
