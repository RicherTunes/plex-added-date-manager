"""Plex Added Date Manager — Full features, clean UI, music support."""
import datetime
import time
from typing import Dict, List, Tuple

import streamlit as st

from plex_api import PlexAPI
from utils import brief_summary, human_duration, human_size, human_ts, list_join, media_info

st.set_page_config(page_title="Plex Added Date Manager", layout="wide")

st.markdown(
    """
    <style>
    .meta { color:#6b7280; font-size:0.9rem; margin:4px 0 0; }
    .title-row h3 { margin-bottom:2px; }
    .chip { display:inline-block; background:#eef2ff; color:#3730a3; padding:2px 8px;
            border-radius:12px; font-size:0.75rem; margin-right:6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass


# ── Controls bar ──

def _controls(prefix: str, *, sections: List[dict], required_type: str) -> Dict:
    type_map = {"1": "movie", "2": "show", "8": "artist"}
    typed = [s for s in sections if s.get("type") == type_map.get(required_type)]
    labels = [f"{s['title']} (#{s['key']})" for s in typed]
    label_to_key = {f"{s['title']} (#{s['key']})": s["key"] for s in typed}

    r1c1, r1c2, r1c3, r1c4, r1c5, r1c6 = st.columns([2.4, 1, 1.2, 1, 1.4, 1])
    with r1c1:
        if labels:
            curr = st.session_state.get(f"{prefix}_section")
            try:
                idx = labels.index(next(lbl for lbl in labels if label_to_key[lbl] == curr))
            except Exception:
                idx = 0
            chosen = st.selectbox("Section", options=labels, index=idx, key=f"{prefix}_section_lbl")
            st.session_state[f"{prefix}_section"] = label_to_key[chosen]
        else:
            st.text_input("Section ID", key=f"{prefix}_section")
    with r1c2:
        st.selectbox("Page Size", [50, 100, 200], key=f"{prefix}_page_size")
    with r1c3:
        st.selectbox(
            "Sort",
            ["addedAt:desc", "addedAt:asc", "titleSort:asc", "titleSort:desc", "year:desc", "year:asc"],
            key=f"{prefix}_sort",
        )
    with r1c4:
        st.text_input("Year", key=f"{prefix}_year", placeholder="e.g. 2021")
    with r1c5:
        st.text_input("Title contains", key=f"{prefix}_title_filter")
    with r1c6:
        st.checkbox("Show images", key=f"{prefix}_show_images", value=True)

    r2c1, r2c2, r2c3, r2c4 = st.columns([1, 1, 3, 1.2])
    with r2c1:
        st.checkbox("Lock added date", key=f"{prefix}_lock", value=True)
    with r2c2:
        if st.button("Reset Filters", key=f"{prefix}_reset"):
            st.session_state[f"{prefix}_year"] = ""
            st.session_state[f"{prefix}_title_filter"] = ""
            st.session_state[f"{prefix}_sort"] = "addedAt:desc"
            st.session_state[f"{prefix}_page"] = 1
            _safe_rerun()
    with r2c3:
        st.caption("Tip: Use the pager to jump to any page.")
    with r2c4:
        st.checkbox("Show details", key=f"{prefix}_show_details")

    return {
        "section_id": st.session_state[f"{prefix}_section"],
        "page": st.session_state.get(f"{prefix}_page", 1),
        "page_size": st.session_state.get(f"{prefix}_page_size", 100),
        "sort": st.session_state.get(f"{prefix}_sort", "addedAt:desc"),
        "year": st.session_state.get(f"{prefix}_year", ""),
        "title": st.session_state.get(f"{prefix}_title_filter", ""),
        "show_images": st.session_state.get(f"{prefix}_show_images", True),
        "show_details": st.session_state.get(f"{prefix}_show_details", False),
        "lock": st.session_state.get(f"{prefix}_lock", True),
    }


# ── Item list with batch operations ──

def _render_items(
    plex: PlexAPI,
    items: List[dict],
    *,
    section_id: str,
    type_id: str,
    prefix: str,
    total: int,
):
    cfg_page = st.session_state.get(f"{prefix}_page", 1)
    page_size = st.session_state.get(f"{prefix}_page_size", 100)
    total_pages = max(1, (total + page_size - 1) // page_size)
    show_images = st.session_state.get(f"{prefix}_show_images", True)
    show_details = st.session_state.get(f"{prefix}_show_details", False)
    lock_added = st.session_state.get(f"{prefix}_lock", True)
    sort = st.session_state.get(f"{prefix}_sort", "addedAt:desc")
    year = st.session_state.get(f"{prefix}_year", "")
    title_filter = (st.session_state.get(f"{prefix}_title_filter", "") or "").strip().lower()
    selected: Dict[str, bool] = st.session_state.setdefault(f"{prefix}_selected", {})

    # ═══ Modify dates ═══
    st.markdown("#### Modify dates")

    sel1, sel2, sel3 = st.columns([2, 3, 2])
    with sel1:
        page_select_all = st.checkbox("Select all on page", key=f"{prefix}_sel_all_page")
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Select all results", key=f"{prefix}_sel_all"):
                progress = st.progress(0)
                count = 0
                start = 0
                while True:
                    batch, tot = plex.fetch_items(
                        section_id, type_id, start=start, size=page_size, sort=sort,
                        filters=({"year": year} if year else None),
                    )
                    if title_filter:
                        batch = [i for i in batch if title_filter in (i.get("title", "").lower())]
                    for it in batch:
                        rk = str(it.get("ratingKey"))
                        if rk:
                            selected[rk] = True
                            count += 1
                    start += page_size
                    if start >= tot:
                        break
                    progress.progress(min(100, int(start * 100 / max(1, tot))))
                progress.progress(100)
                st.success(f"Selected {count} items.")
        with b2:
            if st.button("Clear all", key=f"{prefix}_clear"):
                selected.clear()
                st.success("Cleared.")
        with b3:
            if st.button("Clear page", key=f"{prefix}_clear_page"):
                for it in items:
                    rk = str(it.get("ratingKey"))
                    if rk in selected:
                        selected[rk] = False
                st.success("Cleared page.")

    with sel2:
        batch_date = st.date_input("Batch date", value=datetime.date.today(), key=f"{prefix}_batch_date")
        max_per_min = st.number_input("Max/min (0=unlimited)", min_value=0, value=0, step=30, key=f"{prefix}_rate")

    with sel3:
        total_sel = sum(1 for v in selected.values() if v)
        st.caption(f"**{total_sel}** selected")
        if st.button("Apply to selected", key=f"{prefix}_apply", disabled=total_sel == 0):
            keys = [k for k, v in selected.items() if v]
            new_unix = int(datetime.datetime.combine(batch_date, datetime.time.min).timestamp())
            per_item_sleep = (60.0 / max_per_min) if max_per_min > 0 else 0.0
            progress = st.progress(0)
            ok = 0
            for idx, rk in enumerate(keys, 1):
                last_err = None
                attempts = 0
                while attempts < 4:
                    try:
                        plex.update_added_date(section_id, rk, type_id, new_unix, lock=lock_added)
                        ok += 1
                        last_err = None
                        break
                    except Exception as e:
                        attempts += 1
                        last_err = e
                        time.sleep(min(8, 0.5 * (2 ** (attempts - 1))))
                if last_err is not None:
                    st.error(f"Failed id={rk}: {last_err}")
                progress.progress(int(idx * 100 / max(1, len(keys))))
                if per_item_sleep:
                    time.sleep(per_item_sleep)
            st.success(f"Updated {ok}/{len(keys)} items.")

    # ── Date range selection ──
    with st.expander("Select by Added date range", expanded=False):
        presets = st.columns([1, 1, 1, 1, 1, 1, 1])
        today = datetime.date.today()
        preset_actions = {
            "Last 7": (today - datetime.timedelta(days=7), today),
            "Last 30": (today - datetime.timedelta(days=30), today),
            "Last 90": (today - datetime.timedelta(days=90), today),
            "Last 365": (today - datetime.timedelta(days=365), today),
            "This Year": (datetime.date(today.year, 1, 1), today),
        }
        pkeys = list(preset_actions.keys())
        for i, name in enumerate(pkeys):
            with presets[i]:
                if st.button(name, key=f"{prefix}_preset_{name}"):
                    s, e = preset_actions[name]
                    st.session_state[f"{prefix}_range_from"] = s
                    st.session_state[f"{prefix}_range_to"] = e
        with presets[-2]:
            if st.button("Older >1y", key=f"{prefix}_preset_older"):
                st.session_state[f"{prefix}_range_from"] = today - datetime.timedelta(days=365 * 50)
                st.session_state[f"{prefix}_range_to"] = today - datetime.timedelta(days=365)
        with presets[-1]:
            if st.button("Clear", key=f"{prefix}_preset_clear"):
                st.session_state.pop(f"{prefix}_range_from", None)
                st.session_state.pop(f"{prefix}_range_to", None)

        rc1, rc2 = st.columns(2)
        with rc1:
            range_from = st.date_input("From", key=f"{prefix}_range_from",
                                       value=st.session_state.get(f"{prefix}_range_from", today - datetime.timedelta(days=365)))
        with rc2:
            range_to = st.date_input("To", key=f"{prefix}_range_to",
                                     value=st.session_state.get(f"{prefix}_range_to", today))

        def _select_range(select: bool):
            start_ts = int(datetime.datetime.combine(range_from, datetime.time.min).timestamp())
            end_ts = int(datetime.datetime.combine(range_to, datetime.time.max).timestamp())
            progress = st.progress(0)
            touched = 0
            start = 0
            while True:
                batch_items, tot = plex.fetch_items(
                    section_id, type_id, start=start, size=page_size, sort=sort,
                    filters=({"year": year} if year else None),
                )
                if title_filter:
                    batch_items = [i for i in batch_items if title_filter in (i.get("title", "").lower())]
                for it in batch_items:
                    at = int(it.get("addedAt", 0) or 0)
                    if start_ts <= at <= end_ts:
                        rk = str(it.get("ratingKey"))
                        if rk:
                            selected[rk] = select
                            touched += 1
                start += page_size
                if start >= tot:
                    break
                progress.progress(min(100, int(start * 100 / max(1, tot))))
            progress.progress(100)
            st.success(("Selected" if select else "Deselected") + f" {touched} items in range.")

        act1, act2 = st.columns(2)
        with act1:
            if st.button("Select range", key=f"{prefix}_select_range"):
                _select_range(True)
        with act2:
            if st.button("Deselect range", key=f"{prefix}_deselect_range"):
                _select_range(False)

    st.divider()

    # ═══ List ═══
    # ── Pagination ──
    col_prev, col_info, col_goto, col_next = st.columns([1, 2, 1, 1])
    with col_prev:
        if st.button("< Prev", key=f"{prefix}_prev", disabled=cfg_page <= 1):
            st.session_state[f"{prefix}_page"] = max(1, cfg_page - 1)
            _safe_rerun()
    with col_info:
        st.write(f"Page {cfg_page} of {total_pages} — {total} items")
    with col_goto:
        goto = st.number_input("Go to", min_value=1, max_value=max(1, total_pages),
                               value=min(cfg_page, total_pages), step=1, key=f"{prefix}_goto")
        if st.button("Go", key=f"{prefix}_goto_btn"):
            st.session_state[f"{prefix}_page"] = int(goto)
            _safe_rerun()
    with col_next:
        if st.button("Next >", key=f"{prefix}_next", disabled=cfg_page >= total_pages):
            st.session_state[f"{prefix}_page"] = min(total_pages, cfg_page + 1)
            _safe_rerun()

    if not items:
        st.info("No items found.")
        return

    # ── Render list ──
    for item in items:
        rating_key = str(item.get("ratingKey"))
        if title_filter and title_filter not in (item.get("title", "").lower()):
            continue

        cols = st.columns([0.15, 0.85])
        with cols[0]:
            checked = page_select_all or selected.get(rating_key, False)
            sel = st.checkbox("Select", key=f"{prefix}_sel_{rating_key}", value=checked)
            selected[rating_key] = sel
            if show_images:
                thumb = item.get("thumb")
                url = plex.thumb_url(thumb)
                if url:
                    st.image(url, width=110)
        with cols[1]:
            title = item.get("title", "Unknown")
            year_val = item.get("year")
            rel = item.get("originallyAvailableAt") or "-"
            display = f"{title} ({year_val})" if year_val else title
            st.markdown(f"<div class='title-row'><h3>{display}</h3></div>", unsafe_allow_html=True)

            added_at = item.get("addedAt")
            added_dt = datetime.datetime.fromtimestamp(int(added_at)) if added_at else datetime.datetime.now()
            date_key = f"{prefix}_date_{rating_key}"

            def _on_change(rk=rating_key, title=title, sid=section_id, tid=type_id):
                try:
                    d = st.session_state[date_key]
                    new_unix = int(datetime.datetime.combine(d, datetime.time.min).timestamp())
                    plex.update_added_date(sid, rk, tid, new_unix, lock=lock_added)
                    if hasattr(st, "toast"):
                        st.toast(f"Saved {title}")
                    else:
                        st.success(f"Saved {title}")
                except Exception as e:
                    st.error(f"Failed to save {title}: {e}")

            date_kwargs = {}
            if date_key not in st.session_state:
                date_kwargs["value"] = added_dt.date()
            st.date_input("Added", key=date_key, on_change=_on_change, **date_kwargs)

            # Chips
            chips = [f"Release {rel}", f"ID {rating_key}"]
            info = media_info(item)
            if info.get("resolution"):
                chips.append(f"{info['resolution']}p")
            if info.get("size"):
                chips.append(info["size"])
            if item.get("duration"):
                dur = human_duration(int(item.get("duration") or 0))
                if dur:
                    chips.append(dur)
            st.markdown(" ".join(f"<span class='chip'>{c}</span>" for c in chips), unsafe_allow_html=True)

            if show_details:
                meta_l, meta_r = st.columns([2, 3])
                with meta_l:
                    summary = brief_summary(item.get("summary"))
                    if summary:
                        st.write(summary)
                    genres = list_join(
                        [g.get("tag") for g in (item.get("Genre") or []) if isinstance(g, dict)],
                        limit=6,
                    ) if isinstance(item.get("Genre"), list) else None
                    if genres:
                        st.caption(f"Genres: {genres}")
                    studio = item.get("studio")
                    cr = item.get("contentRating")
                    if studio or cr:
                        st.caption(" ".join(p for p in [f"Studio: {studio}" if studio else None, f"Rated: {cr}" if cr else None] if p))
                with meta_r:
                    last = human_ts(item.get("lastViewedAt"))
                    plays = item.get("viewCount")
                    guid = item.get("guid")
                    partsz = human_size(
                        ((item.get("Media") or [{}])[0].get("Part") or [{}])[0].get("size")
                    ) if item.get("Media") else None
                    lines = []
                    if last:
                        lines.append(f"Last viewed: {last}")
                    if plays:
                        lines.append(f"Plays: {plays}")
                    if guid:
                        lines.append(f"GUID: {guid}")
                    if partsz:
                        lines.append(f"File: {partsz}")
                    if lines:
                        st.caption(" | ".join(lines))


# ── Music controls (reusable for artists/albums) ──

def _music_controls(prefix: str) -> Dict:
    """Render filter/sort controls for music views — same layout as Movies/TV."""

    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns([2.4, 1, 1.2, 1.4, 1])
    with r1c1:
        st.text_input("Title contains", key=f"{prefix}_title_filter")
    with r1c2:
        st.selectbox("Page Size", [50, 100, 200], key=f"{prefix}_page_size")
    with r1c3:
        st.selectbox(
            "Sort",
            ["addedAt:desc", "addedAt:asc", "titleSort:asc", "titleSort:desc"],
            key=f"{prefix}_sort",
        )
    with r1c4:
        st.checkbox("Lock added date", key=f"{prefix}_lock", value=True)
    with r1c5:
        st.checkbox("Show images", key=f"{prefix}_show_images", value=True)

    r2c1, r2c2, r2c3 = st.columns([1, 1, 4])
    with r2c1:
        if st.button("Reset Filters", key=f"{prefix}_reset"):
            st.session_state[f"{prefix}_title_filter"] = ""
            st.session_state[f"{prefix}_sort"] = "addedAt:desc"
            st.session_state[f"{prefix}_page"] = 1
            _safe_rerun()
    with r2c2:
        st.checkbox("Show details", key=f"{prefix}_show_details")
    with r2c3:
        st.caption("")

    return {
        "page": st.session_state.get(f"{prefix}_page", 1),
        "page_size": st.session_state.get(f"{prefix}_page_size", 100),
        "sort": st.session_state.get(f"{prefix}_sort", "addedAt:desc"),
        "title": st.session_state.get(f"{prefix}_title_filter", ""),
        "lock": st.session_state.get(f"{prefix}_lock", True),
        "show_images": st.session_state.get(f"{prefix}_show_images", True),
        "show_details": st.session_state.get(f"{prefix}_show_details", False),
    }


# ── Music: Artists ──

def _render_music_artists(plex: PlexAPI, section_id: str):
    cfg = _music_controls("music_artist")
    page = cfg["page"]
    page_size = cfg["page_size"]
    sort = cfg["sort"]
    title_filter = (cfg["title"] or "").strip().lower()
    lock = cfg["lock"]
    show_images = cfg["show_images"]
    show_details = cfg["show_details"]

    start = (page - 1) * page_size
    try:
        items, total = plex.fetch_artists(section_id, start=start, size=page_size, sort=sort)
    except Exception as e:
        st.error(f"Failed to fetch artists: {e}")
        items, total = [], 0

    total_pages = max(1, (total + page_size - 1) // page_size)
    selected: Dict[str, bool] = st.session_state.setdefault("music_artist_selected", {})

    # ═══ Modify dates ═══
    st.markdown("#### Modify dates")

    sel1, sel2, sel3 = st.columns([2, 3, 2])
    with sel1:
        page_select_all = st.checkbox("Select all on page", key="music_artist_sel_all_page")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Select all results", key="music_artist_sel_all"):
                progress = st.progress(0)
                count = 0
                s = 0
                while True:
                    batch, tot = plex.fetch_artists(section_id, start=s, size=page_size, sort=sort)
                    for it in batch:
                        rk = str(it.get("ratingKey"))
                        if rk:
                            selected[rk] = True
                            count += 1
                    s += page_size
                    if s >= tot:
                        break
                    progress.progress(min(100, int(s * 100 / max(1, tot))))
                progress.progress(100)
                st.success(f"Selected {count} artists.")
        with b2:
            if st.button("Clear all", key="music_artist_clear"):
                selected.clear()
                st.success("Cleared.")
    with sel2:
        batch_date = st.date_input("Batch date", value=datetime.date.today(), key="music_artist_batch_date")
        max_per_min = st.number_input("Max/min (0=unlimited)", min_value=0, value=0, step=30, key="music_artist_rate")
    with sel3:
        total_sel = sum(1 for v in selected.values() if v)
        st.caption(f"**{total_sel}** selected")
        if st.button("Apply to selected", key="music_artist_apply", disabled=total_sel == 0):
            keys = [k for k, v in selected.items() if v]
            new_unix = int(datetime.datetime.combine(batch_date, datetime.time.min).timestamp())
            per_item_sleep = (60.0 / max_per_min) if max_per_min > 0 else 0.0
            progress = st.progress(0)
            ok = 0
            for idx, rk in enumerate(keys, 1):
                try:
                    plex.update_added_date(section_id, rk, "8", new_unix, lock=lock)
                    ok += 1
                except Exception as e:
                    st.error(f"Failed id={rk}: {e}")
                progress.progress(int(idx * 100 / max(1, len(keys))))
                if per_item_sleep:
                    time.sleep(per_item_sleep)
            st.success(f"Updated {ok}/{len(keys)} artists.")

    # ── Date range selection ──
    with st.expander("Select by Added date range", expanded=False):
        presets = st.columns([1, 1, 1, 1, 1, 1, 1])
        today = datetime.date.today()
        preset_actions = {
            "Last 7": (today - datetime.timedelta(days=7), today),
            "Last 30": (today - datetime.timedelta(days=30), today),
            "Last 90": (today - datetime.timedelta(days=90), today),
            "Last 365": (today - datetime.timedelta(days=365), today),
            "This Year": (datetime.date(today.year, 1, 1), today),
        }
        pkeys = list(preset_actions.keys())
        for i, name in enumerate(pkeys):
            with presets[i]:
                if st.button(name, key=f"music_artist_preset_{name}"):
                    s, e = preset_actions[name]
                    st.session_state["music_artist_range_from"] = s
                    st.session_state["music_artist_range_to"] = e
        with presets[-2]:
            if st.button("Older >1y", key="music_artist_preset_older"):
                st.session_state["music_artist_range_from"] = today - datetime.timedelta(days=365 * 50)
                st.session_state["music_artist_range_to"] = today - datetime.timedelta(days=365)
        with presets[-1]:
            if st.button("Clear", key="music_artist_preset_clear"):
                st.session_state.pop("music_artist_range_from", None)
                st.session_state.pop("music_artist_range_to", None)

        rc1, rc2 = st.columns(2)
        with rc1:
            range_from = st.date_input("From", key="music_artist_range_from",
                                       value=st.session_state.get("music_artist_range_from", today - datetime.timedelta(days=365)))
        with rc2:
            range_to = st.date_input("To", key="music_artist_range_to",
                                     value=st.session_state.get("music_artist_range_to", today))

        def _select_range_artists(select: bool):
            start_ts = int(datetime.datetime.combine(range_from, datetime.time.min).timestamp())
            end_ts = int(datetime.datetime.combine(range_to, datetime.time.max).timestamp())
            progress = st.progress(0)
            touched = 0
            s = 0
            while True:
                batch_items, tot = plex.fetch_artists(section_id, start=s, size=page_size, sort=sort)
                for it in batch_items:
                    at = int(it.get("addedAt", 0) or 0)
                    if start_ts <= at <= end_ts:
                        rk = str(it.get("ratingKey"))
                        if rk:
                            selected[rk] = select
                            touched += 1
                s += page_size
                if s >= tot:
                    break
                progress.progress(min(100, int(s * 100 / max(1, tot))))
            progress.progress(100)
            st.success(("Selected" if select else "Deselected") + f" {touched} artists in range.")

        act1, act2 = st.columns(2)
        with act1:
            if st.button("Select range", key="music_artist_select_range"):
                _select_range_artists(True)
        with act2:
            if st.button("Deselect range", key="music_artist_deselect_range"):
                _select_range_artists(False)

    st.divider()

    # ═══ List ═══
    # ── Pagination ──
    col_prev, col_info, col_goto, col_next = st.columns([1, 2, 1, 1])
    with col_prev:
        if st.button("< Prev", key="music_prev", disabled=page <= 1):
            st.session_state["music_artist_page"] = max(1, page - 1)
            _safe_rerun()
    with col_info:
        st.write(f"Page {page} of {total_pages} — {total} artists")
    with col_goto:
        goto = st.number_input("Go to", min_value=1, max_value=max(1, total_pages),
                               value=min(page, total_pages), step=1, key="music_artist_goto")
        if st.button("Go", key="music_artist_goto_btn"):
            st.session_state["music_artist_page"] = int(goto)
            _safe_rerun()
    with col_next:
        if st.button("Next >", key="music_next", disabled=page >= total_pages):
            st.session_state["music_artist_page"] = min(total_pages, page + 1)
            _safe_rerun()

    if not items:
        st.info("No artists found.")
        return

    # ── Render list ──
    for artist in items:
        rk = str(artist.get("ratingKey", ""))
        if title_filter and title_filter not in (artist.get("title", "").lower()):
            continue

        if show_images:
            cols = st.columns([0.15, 0.65, 0.2])
        else:
            cols = st.columns([0.05, 0.75, 0.2])
        with cols[0]:
            checked = page_select_all or selected.get(rk, False)
            sel = st.checkbox("Select", key=f"music_artist_sel_{rk}", value=checked)
            selected[rk] = sel
            if show_images:
                thumb = artist.get("thumb")
                url = plex.thumb_url(thumb)
                if url:
                    st.image(url, width=110)
        with cols[1]:
            title = artist.get("title", "Unknown Artist")
            st.markdown(f"**{title}**")
            added_at = artist.get("addedAt")
            added_dt = datetime.datetime.fromtimestamp(int(added_at)) if added_at else datetime.datetime.now()
            date_key = f"music_artist_date_{rk}"

            def _on_change_artist(rk=rk, title=title, sid=section_id):
                try:
                    d = st.session_state[date_key]
                    new_unix = int(datetime.datetime.combine(d, datetime.time.min).timestamp())
                    plex.update_added_date(sid, rk, "8", new_unix, lock=lock)
                    if hasattr(st, "toast"):
                        st.toast(f"Saved {title}")
                    else:
                        st.success(f"Saved {title}")
                except Exception as e:
                    st.error(f"Failed to save {title}: {e}")

            date_kwargs = {}
            if date_key not in st.session_state:
                date_kwargs["value"] = added_dt.date()
            st.date_input("Added", key=date_key, on_change=_on_change_artist, **date_kwargs)
            st.markdown(f"<span class='chip'>ID {rk}</span>", unsafe_allow_html=True)
        with cols[2]:
            if st.button("View Albums ▸", key=f"go_albums_{rk}"):
                st.session_state["music_view"] = "albums"
                st.session_state["music_artist_id"] = rk
                st.session_state["music_artist_name"] = title
                st.session_state["music_artist_page"] = 1
                _safe_rerun()


# ── Music: Albums ──

def _render_music_albums(plex: PlexAPI, section_id: str, artist_id: str, artist_name: str):
    cfg = _music_controls("music_album")
    page = cfg["page"]
    page_size = cfg["page_size"]
    sort = cfg["sort"]
    title_filter = (cfg["title"] or "").strip().lower()
    lock = cfg["lock"]
    show_images = cfg["show_images"]
    show_details = cfg["show_details"]

    start = (page - 1) * page_size
    try:
        items, total = plex.fetch_albums_for_artist(section_id, artist_id, start=start, size=page_size, sort=sort)
    except Exception as e:
        st.error(f"Failed to fetch albums: {e}")
        items, total = [], 0

    total_pages = max(1, (total + page_size - 1) // page_size)
    selected: Dict[str, bool] = st.session_state.setdefault("music_album_selected", {})

    # ═══ Modify dates ═══
    st.markdown("#### Modify dates")

    sel1, sel2, sel3 = st.columns([2, 3, 2])
    with sel1:
        page_select_all = st.checkbox("Select all on page", key="music_album_sel_all_page")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Select all results", key="music_album_sel_all"):
                progress = st.progress(0)
                count = 0
                s = 0
                while True:
                    batch, tot = plex.fetch_albums_for_artist(section_id, artist_id, start=s, size=page_size, sort=sort)
                    for it in batch:
                        rk = str(it.get("ratingKey"))
                        if rk:
                            selected[rk] = True
                            count += 1
                    s += page_size
                    if s >= tot:
                        break
                    progress.progress(min(100, int(s * 100 / max(1, tot))))
                progress.progress(100)
                st.success(f"Selected {count} albums.")
        with b2:
            if st.button("Clear all", key="music_album_clear"):
                selected.clear()
                st.success("Cleared.")
    with sel2:
        batch_date = st.date_input("Batch date", value=datetime.date.today(), key="music_album_batch_date")
        max_per_min = st.number_input("Max/min (0=unlimited)", min_value=0, value=0, step=30, key="music_album_rate")
    with sel3:
        total_sel = sum(1 for v in selected.values() if v)
        st.caption(f"**{total_sel}** selected")
        if st.button("Apply to selected", key="music_album_apply", disabled=total_sel == 0):
            keys = [k for k, v in selected.items() if v]
            new_unix = int(datetime.datetime.combine(batch_date, datetime.time.min).timestamp())
            per_item_sleep = (60.0 / max_per_min) if max_per_min > 0 else 0.0
            progress = st.progress(0)
            ok = 0
            for idx, rk in enumerate(keys, 1):
                try:
                    plex.update_added_date(section_id, rk, "9", new_unix, lock=lock)
                    ok += 1
                except Exception as e:
                    st.error(f"Failed id={rk}: {e}")
                progress.progress(int(idx * 100 / max(1, len(keys))))
                if per_item_sleep:
                    time.sleep(per_item_sleep)
            st.success(f"Updated {ok}/{len(keys)} albums.")

    st.divider()

    # ═══ List ═══
    # ── Pagination ──
    col_prev, col_info, col_goto, col_next = st.columns([1, 2, 1, 1])
    with col_prev:
        if st.button("< Prev", key="music_album_prev", disabled=page <= 1):
            st.session_state["music_album_page"] = max(1, page - 1)
            _safe_rerun()
    with col_info:
        st.write(f"Page {page} of {total_pages} — {total} albums")
    with col_goto:
        goto = st.number_input("Go to", min_value=1, max_value=max(1, total_pages),
                               value=min(page, total_pages), step=1, key="music_album_goto")
        if st.button("Go", key="music_album_goto_btn"):
            st.session_state["music_album_page"] = int(goto)
            _safe_rerun()
    with col_next:
        if st.button("Next >", key="music_album_next", disabled=page >= total_pages):
            st.session_state["music_album_page"] = min(total_pages, page + 1)
            _safe_rerun()

    if not items:
        st.info("No albums found.")
        return

    # ── Render list ──
    for album in items:
        rk = str(album.get("ratingKey", ""))
        if title_filter and title_filter not in (album.get("title", "").lower()):
            continue

        if show_images:
            cols = st.columns([0.15, 0.65, 0.2])
        else:
            cols = st.columns([0.05, 0.75, 0.2])
        with cols[0]:
            checked = page_select_all or selected.get(rk, False)
            sel = st.checkbox("Select", key=f"music_album_sel_{rk}", value=checked)
            selected[rk] = sel
            if show_images:
                thumb = album.get("thumb") or album.get("parentThumb")
                url = plex.thumb_url(thumb)
                if url:
                    st.image(url, width=110)
        with cols[1]:
            title = album.get("title", "Unknown Album")
            year = album.get("year")
            display = f"{title} ({year})" if year else title
            st.markdown(f"**{display}**")
            added_at = album.get("addedAt")
            added_dt = datetime.datetime.fromtimestamp(int(added_at)) if added_at else datetime.datetime.now()
            date_key = f"music_album_date_{rk}"

            def _on_change_album(rk=rk, title=title, sid=section_id):
                try:
                    d = st.session_state[date_key]
                    new_unix = int(datetime.datetime.combine(d, datetime.time.min).timestamp())
                    plex.update_added_date(sid, rk, "9", new_unix, lock=lock)
                    if hasattr(st, "toast"):
                        st.toast(f"Saved {title}")
                    else:
                        st.success(f"Saved {title}")
                except Exception as e:
                    st.error(f"Failed to save {title}: {e}")

            date_kwargs = {}
            if date_key not in st.session_state:
                date_kwargs["value"] = added_dt.date()
            st.date_input("Added", key=date_key, on_change=_on_change_album, **date_kwargs)
            st.markdown(f"<span class='chip'>ID {rk}</span>", unsafe_allow_html=True)
        with cols[2]:
            if st.button("View Tracks ▸", key=f"go_tracks_{rk}"):
                st.session_state["music_view"] = "tracks"
                st.session_state["music_album_id"] = rk
                st.session_state["music_album_name"] = title
                st.session_state["music_album_page"] = 1
                _safe_rerun()


# ── Music: Tracks ──

def _render_music_tracks(plex: PlexAPI, section_id: str, album_id: str, album_name: str):
    cfg = _music_controls("music_track")
    page = cfg["page"]
    page_size = cfg["page_size"]
    sort = cfg["sort"]
    title_filter = (cfg["title"] or "").strip().lower()
    lock = cfg["lock"]

    start = (page - 1) * page_size
    try:
        items, total = plex.fetch_tracks_for_album(section_id, album_id, start=start, size=page_size, sort=sort)
    except Exception as e:
        st.error(f"Failed to fetch tracks: {e}")
        items, total = [], 0

    total_pages = max(1, (total + page_size - 1) // page_size)
    selected: Dict[str, bool] = st.session_state.setdefault("music_track_selected", {})

    # ═══ Modify dates ═══
    st.markdown("#### Modify dates")

    sel1, sel2, sel3 = st.columns([2, 3, 2])
    with sel1:
        page_select_all = st.checkbox("Select all on page", key="music_track_sel_all_page")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Select all results", key="music_track_sel_all"):
                progress = st.progress(0)
                count = 0
                s = 0
                while True:
                    batch, tot = plex.fetch_tracks_for_album(section_id, album_id, start=s, size=page_size, sort=sort)
                    for it in batch:
                        rk = str(it.get("ratingKey"))
                        if rk:
                            selected[rk] = True
                            count += 1
                    s += page_size
                    if s >= tot:
                        break
                    progress.progress(min(100, int(s * 100 / max(1, tot))))
                progress.progress(100)
                st.success(f"Selected {count} tracks.")
        with b2:
            if st.button("Clear all", key="music_track_clear"):
                selected.clear()
                st.success("Cleared.")
    with sel2:
        batch_date = st.date_input("Batch date", value=datetime.date.today(), key="music_track_batch_date")
        max_per_min = st.number_input("Max/min (0=unlimited)", min_value=0, value=0, step=30, key="music_track_rate")
    with sel3:
        total_sel = sum(1 for v in selected.values() if v)
        st.caption(f"**{total_sel}** selected")
        if st.button("Apply to selected", key="music_track_apply", disabled=total_sel == 0):
            keys = [k for k, v in selected.items() if v]
            new_unix = int(datetime.datetime.combine(batch_date, datetime.time.min).timestamp())
            per_item_sleep = (60.0 / max_per_min) if max_per_min > 0 else 0.0
            progress = st.progress(0)
            ok = 0
            for idx, rk in enumerate(keys, 1):
                try:
                    plex.update_added_date(section_id, rk, "10", new_unix, lock=lock)
                    ok += 1
                except Exception as e:
                    st.error(f"Failed id={rk}: {e}")
                progress.progress(int(idx * 100 / max(1, len(keys))))
                if per_item_sleep:
                    time.sleep(per_item_sleep)
            st.success(f"Updated {ok}/{len(keys)} tracks.")

    st.divider()

    # ═══ List ═══
    # ── Pagination ──
    col_prev, col_info, col_goto, col_next = st.columns([1, 2, 1, 1])
    with col_prev:
        if st.button("< Prev", key="music_track_prev", disabled=page <= 1):
            st.session_state["music_track_page"] = max(1, page - 1)
            _safe_rerun()
    with col_info:
        st.write(f"Page {page} of {total_pages} — {total} tracks")
    with col_goto:
        goto = st.number_input("Go to", min_value=1, max_value=max(1, total_pages),
                               value=min(page, total_pages), step=1, key="music_track_goto")
        if st.button("Go", key="music_track_goto_btn"):
            st.session_state["music_track_page"] = int(goto)
            _safe_rerun()
    with col_next:
        if st.button("Next >", key="music_track_next", disabled=page >= total_pages):
            st.session_state["music_track_page"] = min(total_pages, page + 1)
            _safe_rerun()

    if not items:
        st.info("No tracks found.")
        return

    # ── Render list ──
    for idx, track in enumerate(items, 1):
        rk = str(track.get("ratingKey", ""))
        title = track.get("title", f"Track {idx}")
        if title_filter and title_filter not in title.lower():
            continue

        track_num = track.get("index", idx)
        added_at = track.get("addedAt")
        added_dt = datetime.datetime.fromtimestamp(int(added_at)) if added_at else datetime.datetime.now()

        cols = st.columns([0.05, 0.15, 0.35, 0.25, 0.2])
        with cols[0]:
            checked = page_select_all or selected.get(rk, False)
            sel = st.checkbox("Select", key=f"music_track_sel_{rk}", value=checked)
            selected[rk] = sel
        with cols[1]:
            st.write(f"**{track_num}**")
        with cols[2]:
            st.write(title)
        with cols[3]:
            date_key = f"music_track_date_{rk}"

            def _on_change_track(rk=rk, title=title, sid=section_id):
                try:
                    d = st.session_state[date_key]
                    new_unix = int(datetime.datetime.combine(d, datetime.time.min).timestamp())
                    plex.update_added_date(sid, rk, "10", new_unix, lock=lock)
                    if hasattr(st, "toast"):
                        st.toast(f"Saved {title}")
                    else:
                        st.success(f"Saved {title}")
                except Exception as e:
                    st.error(f"Failed to save {title}: {e}")

            date_kwargs = {}
            if date_key not in st.session_state:
                date_kwargs["value"] = added_dt.date()
            st.date_input("Added", key=date_key, on_change=_on_change_track, **date_kwargs)
        with cols[4]:
            st.caption(f"ID: {rk}")


# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════

def main():
    st.markdown("<h2 style='text-align: center;'>Plex Added Date Manager</h2>", unsafe_allow_html=True)

    plex = PlexAPI()
    if not plex.base_url or not plex.token:
        st.error("Missing PLEX_BASE_URL or PLEX_TOKEN in environment (.env).")
        st.stop()

    try:
        sections = plex.get_sections()
    except Exception as e:
        sections = []
        st.warning(f"Could not list library sections: {e}")

    movie_sections = [s for s in sections if s.get("type") == "movie"]
    show_sections = [s for s in sections if s.get("type") == "show"]
    music_sections = [s for s in sections if s.get("type") == "artist"]

    tab1, tab2, tab3 = st.tabs(["Movies", "TV Series", "Music"])

    def render_tab(prefix: str, type_id: str, tab_sections: list):
        if not tab_sections:
            st.info(f"No {'movie' if type_id == '1' else 'show'} libraries found.")
            return
        cfg = _controls(prefix, sections=tab_sections, required_type=type_id)
        section_id = cfg["section_id"] or ("1" if type_id == "1" else "2")
        start = (int(cfg["page"]) - 1) * int(cfg["page_size"])
        filters = {"year": cfg["year"]} if cfg["year"] else None
        try:
            items, total = plex.fetch_items(
                section_id, type_id, start=start, size=int(cfg["page_size"]),
                sort=cfg["sort"], filters=filters,
            )
        except Exception as e:
            st.error(f"Failed to fetch items: {e}")
            items, total = [], 0
        # Client-side title filter
        title_filter = (cfg["title"] or "").strip().lower()
        if title_filter:
            items = [i for i in items if title_filter in (i.get("title", "").lower())]
        _render_items(plex, items, section_id=section_id, type_id=type_id, prefix=prefix, total=total)

    with tab1:
        render_tab("movie", "1", movie_sections)
    with tab2:
        render_tab("show", "2", show_sections)

    with tab3:
        if not music_sections:
            st.info("No music libraries found.")
        else:
            labels = [f"{s['title']} (#{s['key']})" for s in music_sections]
            label_to_key = {f"{s['title']} (#{s['key']})": s["key"] for s in music_sections}
            chosen = st.selectbox("Music Library", options=labels, key="music_section_label")
            section_id = label_to_key[chosen]

            view = st.session_state.get("music_view", "artists")
            artist_name = st.session_state.get("music_artist_name", "")
            album_name = st.session_state.get("music_album_name", "")

            # Breadcrumb
            if view in ("albums", "tracks") and artist_name:
                if st.button(f"← {artist_name}", key="bc_artist"):
                    st.session_state["music_view"] = "artists"
                    st.session_state["music_artist_id"] = None
                    st.session_state["music_artist_name"] = ""
                    st.session_state["music_album_id"] = None
                    st.session_state["music_album_name"] = ""
                    st.session_state["music_artist_page"] = 1
                    _safe_rerun()
            if view == "tracks" and album_name:
                if st.button(f"← {album_name}", key="bc_album"):
                    st.session_state["music_view"] = "albums"
                    st.session_state["music_album_id"] = None
                    st.session_state["music_album_name"] = ""
                    st.session_state["music_album_page"] = 1
                    _safe_rerun()

            if view == "artists":
                _render_music_artists(plex, section_id)
            elif view == "albums":
                _render_music_albums(plex, section_id, st.session_state["music_artist_id"], artist_name)
            elif view == "tracks":
                _render_music_tracks(plex, section_id, st.session_state["music_album_id"], album_name)


if __name__ == "__main__":
    main()
