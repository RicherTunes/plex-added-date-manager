"""Cached data fetcher for Plex items used by the UI."""

from typing import List, Tuple

import streamlit as st

from plex_api import PlexAPI


@st.cache_data(show_spinner=False, ttl=30)
def _cached_fetch(
    base_url: str,
    token: str,
    section_id: str,
    type_id: str,
    start: int,
    size: int,
    sort: str,
    year: str,
) -> Tuple[List[dict], int]:
    p = PlexAPI(base_url=base_url, token=token)
    filters = {"year": year} if year else None
    return p.fetch_items(section_id, type_id, start=start, size=size, sort=sort, filters=filters)

