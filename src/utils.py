"""Utility helpers for formatting and safe metadata access.

These helpers are used by the Streamlit UI to present richer metadata,
and are intentionally stdlib‑only to avoid extra dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, List, Mapping, Optional


def human_size(num: Optional[int]) -> Optional[str]:
    if num is None:
        return None
    try:
        n = float(num)
    except (TypeError, ValueError):
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    return f"{n:.1f} {units[i]}"


def human_duration(value: Optional[int]) -> Optional[str]:
    """Return human string for duration milliseconds or seconds.

    Plex returns `duration` in ms; if the value looks like seconds (small),
    we still handle it gracefully.
    """
    if value is None:
        return None
    total_ms = int(value)
    # Heuristic: treat small numbers as seconds
    if total_ms < 10_000:
        total_ms *= 1000
    seconds = total_ms // 1000
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def human_ts(unix: Optional[int]) -> Optional[str]:
    if not unix:
        return None
    try:
        dt = datetime.fromtimestamp(int(unix), tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _tags_list(obj: Mapping[str, Any], key: str) -> List[str]:
    vals = obj.get(key)
    out: List[str] = []
    if isinstance(vals, list):
        for v in vals:
            if isinstance(v, Mapping) and "tag" in v:
                out.append(str(v.get("tag")))
            else:
                out.append(str(v))
    return out


def media_info(item: Mapping[str, Any]) -> Mapping[str, Optional[str]]:
    media = None
    try:
        medias = item.get("Media") or []
        if isinstance(medias, list) and medias:
            media = medias[0]
    except Exception:
        media = None
    if not isinstance(media, Mapping):
        media = {}

    part = None
    try:
        parts = media.get("Part") or []
        if isinstance(parts, list) and parts:
            part = parts[0]
    except Exception:
        part = None
    if not isinstance(part, Mapping):
        part = {}

    return {
        "resolution": (
            str(media.get("videoResolution")) if media.get("videoResolution") else None
        ),
        "videoCodec": str(media.get("videoCodec")) if media.get("videoCodec") else None,
        "audioCodec": str(media.get("audioCodec")) if media.get("audioCodec") else None,
        "audioChannels": (
            str(media.get("audioChannels")) if media.get("audioChannels") else None
        ),
        "container": str(media.get("container")) if media.get("container") else None,
        "size": human_size(part.get("size")) if part.get("size") else None,
    }


def brief_summary(text: Optional[str], max_len: int = 180) -> Optional[str]:
    if not text:
        return None
    t = str(text).strip()
    return t if len(t) <= max_len else t[: max_len - 1].rstrip() + "…"


def list_join(values: Iterable[str], *, limit: int = 6) -> Optional[str]:
    vals = [v for v in values if v]
    if not vals:
        return None
    head = vals[:limit]
    more = len(vals) - len(head)
    return ", ".join(head) + (f" +{more}" if more > 0 else "")
