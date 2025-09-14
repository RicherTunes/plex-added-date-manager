"""Item rendering and batch update UI for the Streamlit app."""

import datetime
import time
from typing import Dict, List

import streamlit as st

from plex_api import PlexAPI


def _render_items(
    plex: PlexAPI,
    items: List[dict],
    *,
    type_id: str,
    select_key: str,
    key_prefix: str,
    show_images: bool,
    lock_added: bool,
    section_id: str,
    sort: str,
    year: str,
    title_filter: str,
    page_size: int,
) -> None:
    density = st.session_state.get("ui_density", "Comfortable")
    cols_widths = [0.16, 0.84] if density == "Compact" else [0.2, 0.8]
    poster_w = 80 if density == "Compact" else 110
    selected: Dict[str, bool] = st.session_state.setdefault(select_key, {})

    # Batch controls
    left, mid, right = st.columns([2, 3, 2])
    with left:
        page_select_all = st.checkbox("Select all on page", key=f"{key_prefix}_select_all")
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Select all results", key=f"{key_prefix}_select_all_results"):
                progress = st.progress(0)
                selected_count = 0
                try:
                    start = 0
                    total_known = None
                    while True:
                        batch_items, total = plex.fetch_items(
                            section_id,
                            type_id,
                            start=start,
                            size=page_size,
                            sort=sort,
                            filters=({"year": year} if year else None),
                        )
                        total_known = total
                        if title_filter:
                            batch_items = [i for i in batch_items if title_filter in (i.get("title", "").lower())]
                        for it in batch_items:
                            rk = str(it.get("ratingKey"))
                            if rk:
                                selected[rk] = True
                                selected_count += 1
                        start += page_size
                        if start >= total:
                            break
                        progress.progress(min(100, int(start * 100 / max(1, total))))
                finally:
                    progress.progress(100)
                st.success(f"Selected {selected_count} items across results (total ~{total_known}).")
        with b2:
            if st.button("Clear all", key=f"{key_prefix}_clear_all"):
                selected.clear()
                st.success("Cleared all selections.")
        with b3:
            if st.button("Clear page", key=f"{key_prefix}_clear_page"):
                for it in items:
                    rk = str(it.get("ratingKey"))
                    if rk in selected:
                        selected[rk] = False
                st.success("Cleared selections on this page.")
    with mid:
        batch_date = st.date_input("Batch date", value=datetime.date.today(), key=f"{key_prefix}_batch_date")
        max_per_min = st.number_input("Max/min (0=unlimited)", min_value=0, value=0, step=30, key=f"{key_prefix}_max_per_min")
    with right:
        if st.button("Apply to selected", key=f"{key_prefix}_apply_batch"):
            keys = [k for k, v in selected.items() if v]
            if not keys:
                st.warning("No items selected.")
            else:
                new_unix = int(datetime.datetime.combine(batch_date, datetime.time.min).timestamp())
                total_sel = len(keys)
                progress = st.progress(0)
                successes = 0
                per_item_sleep = (60.0 / max_per_min) if max_per_min and max_per_min > 0 else 0.0
                for idx, rating_key in enumerate(keys, start=1):
                    last_err = None
                    attempts = 0
                    while attempts < 4:
                        try:
                            plex.update_added_date(section_id, rating_key, type_id, new_unix, lock=lock_added)
                            successes += 1
                            last_err = None
                            break
                        except Exception as e:  # noqa: BLE001
                            attempts += 1
                            last_err = e
                            time.sleep(min(8, 0.5 * (2 ** (attempts - 1))))
                    if last_err is not None:
                        st.error(f"Failed updating id={rating_key}: {last_err}")
                    progress.progress(int(idx * 100 / total_sel))
                    if per_item_sleep:
                        time.sleep(per_item_sleep)
                st.success(f"Updated {successes}/{total_sel} items.")

    # Selection summary
    total_selected = sum(1 for v in selected.values() if v)
    st.caption(f"Selected: {total_selected}")

    # Date range selection (advanced)
    with st.expander("Select by Added date range", expanded=False):
        presets = st.columns([1,1,1,1,1,1,1])
        today = datetime.date.today()
        # Preset handlers
        preset_actions = {
            "Last 7": (today - datetime.timedelta(days=7), today),
            "Last 30": (today - datetime.timedelta(days=30), today),
            "Last 90": (today - datetime.timedelta(days=90), today),
            "Last 365": (today - datetime.timedelta(days=365), today),
            "This Year": (datetime.date(today.year, 1, 1), today),
        }
        keys = list(preset_actions.keys())
        for i, name in enumerate(keys):
            with presets[i]:
                if st.button(name, key=f"{key_prefix}_preset_{name}"):
                    start, end = preset_actions[name]
                    st.session_state[f"{key_prefix}_range_from"] = start
                    st.session_state[f"{key_prefix}_range_to"] = end
        with presets[-2]:
            if st.button("Older >1y", key=f"{key_prefix}_preset_older"):
                st.session_state[f"{key_prefix}_range_from"] = today - datetime.timedelta(days=365*50)
                st.session_state[f"{key_prefix}_range_to"] = today - datetime.timedelta(days=365)
        with presets[-1]:
            if st.button("Clear", key=f"{key_prefix}_preset_clear"):
                st.session_state.pop(f"{key_prefix}_range_from", None)
                st.session_state.pop(f"{key_prefix}_range_to", None)

        rc1, rc2 = st.columns(2)
        with rc1:
            range_from = st.date_input("From", key=f"{key_prefix}_range_from", value=st.session_state.get(f"{key_prefix}_range_from", today - datetime.timedelta(days=365)))
        with rc2:
            range_to = st.date_input("To", key=f"{key_prefix}_range_to", value=st.session_state.get(f"{key_prefix}_range_to", today))
        act1, act2 = st.columns(2)

        def _select_range(select: bool):
            start_ts = int(datetime.datetime.combine(range_from, datetime.time.min).timestamp())
            end_ts = int(datetime.datetime.combine(range_to, datetime.time.max).timestamp())
            progress = st.progress(0)
            touched = 0
            try:
                start = 0
                while True:
                    batch_items, total = plex.fetch_items(
                        section_id,
                        type_id,
                        start=start,
                        size=page_size,
                        sort=sort,
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
                    if start >= total:
                        break
                    progress.progress(min(100, int(start * 100 / max(1, total))))
            finally:
                progress.progress(100)
            st.success(("Selected" if select else "Deselected") + f" {touched} items in range.")
        with act1:
            if st.button("Select range", key=f"{key_prefix}_select_range"):
                _select_range(True)
        with act2:
            if st.button("Deselect range", key=f"{key_prefix}_deselect_range"):
                _select_range(False)

    # Render list
    for item in items:
        rating_key = str(item.get("ratingKey"))
        cols = st.columns(cols_widths)
        with cols[0]:
            checked = page_select_all or selected.get(rating_key, False)
            sel = st.checkbox("Select", key=f"{key_prefix}_sel_{rating_key}", value=checked)
            selected[rating_key] = sel
            if show_images:
                thumb = item.get("thumb")
                url = plex.thumb_url(thumb)
                if url:
                    st.image(url, width=poster_w)
        with cols[1]:
            title = item.get("title", "Unknown")
            year = item.get("year")
            rel = item.get("originallyAvailableAt") or "-"
            display = f"{title} ({year})" if year else title
            st.markdown(f"<div class='title-row'><h3>{display}</h3></div>", unsafe_allow_html=True)

            # Added (inline editable)
            added_at = item.get("addedAt")
            if added_at:
                added_dt = datetime.datetime.fromtimestamp(int(added_at))
            else:
                added_dt = datetime.datetime.now()

            date_key = f"{key_prefix}_date_{rating_key}"

            def _on_change_inline(rk=rating_key):
                try:
                    d = st.session_state[date_key]
                    new_unix = int(datetime.datetime.combine(d, datetime.time.min).timestamp())
                    plex.update_added_date(section_id, rk, type_id, new_unix, lock=lock_added)
                    st.toast(f"Saved {title}") if hasattr(st, "toast") else st.success(f"Saved {title}")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Failed to save {title}: {e}")

            date_kwargs = {}
            if date_key not in st.session_state:
                date_kwargs["value"] = added_dt.date()
            st.date_input("Added", key=date_key, on_change=_on_change_inline, **date_kwargs)

            # Secondary info chips
            st.markdown(f"<span class='chip'>Release {rel}</span> <span class='chip'>ID {rating_key}</span>", unsafe_allow_html=True)

