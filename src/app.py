import datetime
import time
from typing import Dict, List, Tuple

import streamlit as st

from plex_api import PlexAPI

st.set_page_config(page_title="Plex Added Date Manager", layout="wide")


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


def _init_state():
    defaults = {
        "movie_page": 1,
        "movie_page_size": 100,
        "movie_selected": {},
        "movie_show_images": True,
        "movie_show_item_edit": False,
        "movie_sort": "addedAt:desc",
        "movie_year_filter": "",
        "movie_title_filter": "",
        "movie_section": "1",
        "movie_lock_added": True,
        "show_page": 1,
        "show_page_size": 100,
        "show_selected": {},
        "show_show_images": True,
        "show_show_item_edit": False,
        "show_sort": "addedAt:desc",
        "show_year_filter": "",
        "show_title_filter": "",
        "show_section": "2",
        "show_lock_added": True,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def _controls(prefix: str, *, sections: List[dict], required_type: str) -> Dict:
    section_key = f"{prefix}_section"
    page_key = f"{prefix}_page"
    page_size_key = f"{prefix}_page_size"
    sort_key = f"{prefix}_sort"
    year_key = f"{prefix}_year_filter"
    title_key = f"{prefix}_title_filter"
    images_key = f"{prefix}_show_images"
    item_edit_key = f"{prefix}_show_item_edit"
    lock_key = f"{prefix}_lock_added"

    # Build section options filtered by type
    typed_sections = [s for s in sections if s.get("type") == ("movie" if required_type == "1" else "show")]
    # Option labels
    options = [f"{s['title']} (#{s['key']})" for s in typed_sections] or []
    key_by_label = {f"{s['title']} (#{s['key']})": s["key"] for s in typed_sections}

    c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1, 1.2, 1, 1.5, 1])
    with c1:
        if options:
            default_label = None
            # pick current value if present
            for lbl, key in key_by_label.items():
                if key == st.session_state[section_key]:
                    default_label = lbl
                    break
            selection = st.selectbox("Section", options=options, index=(options.index(default_label) if default_label in options else 0))
            st.session_state[section_key] = key_by_label.get(selection, st.session_state[section_key])
        else:
            st.text_input("Section ID", key=section_key)
    with c2:
        st.selectbox("Page Size", [50, 100, 200], key=page_size_key)
    with c3:
        st.selectbox(
            "Sort",
            [
                "addedAt:desc",
                "addedAt:asc",
                "titleSort:asc",
                "titleSort:desc",
                "year:desc",
                "year:asc",
            ],
            key=sort_key,
        )
    with c4:
        st.text_input("Year", key=year_key, placeholder="e.g. 2021")
    with c5:
        st.text_input("Title contains", key=title_key)
    with c6:
        st.checkbox("Show images", key=images_key, value=st.session_state[images_key])

    c7, c8, c9 = st.columns([1, 1, 2])
    with c7:
        st.checkbox("Per-item edit", key=item_edit_key, value=st.session_state[item_edit_key])
    with c8:
        st.checkbox("Lock added date", key=lock_key, value=st.session_state[lock_key])
    with c9:
        if st.button("Reset Filters", key=f"{prefix}_reset"):
            st.session_state[year_key] = ""
            st.session_state[title_key] = ""
            st.session_state[sort_key] = "addedAt:desc"
            st.session_state[page_key] = 1

    return {
        "section_id": st.session_state[section_key],
        "page": st.session_state[page_key],
        "page_size": st.session_state[page_size_key],
        "sort": st.session_state[sort_key],
        "year": st.session_state[year_key],
        "title": st.session_state[title_key],
        "show_images": st.session_state[images_key],
        "show_item_edit": st.session_state[item_edit_key],
        "lock": st.session_state[lock_key],
    }


def _render_items(
    plex: PlexAPI,
    items: List[dict],
    *,
    type_id: str,
    select_key: str,
    key_prefix: str,
    show_images: bool,
    show_item_edit: bool,
    lock_added: bool,
    section_id: str,
    # for select-all across results
    sort: str,
    year: str,
    title_filter: str,
    page_size: int,
):
    selected: Dict[str, bool] = st.session_state.setdefault(select_key, {})

    # Batch controls
    left, mid, right = st.columns([2, 3, 2])
    with left:
        page_select_all = st.checkbox("Select all on page", key=f"{key_prefix}_select_all")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Select all results", key=f"{key_prefix}_select_all_results"):
                # Enumerate across all pages with current filters
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
                st.success(f"Selected {selected_count} items across all results (total ~{total_known}).")
        with b2:
            if st.button("Clear all", key=f"{key_prefix}_clear_all"):
                selected.clear()
                st.success("Cleared all selections.")
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
                total = len(keys)
                progress = st.progress(0)
                successes = 0
                per_item_sleep = (60.0 / max_per_min) if max_per_min and max_per_min > 0 else 0.0
                for idx, rating_key in enumerate(keys, start=1):
                    try:
                        attempts = 0
                        last_err = None
                        while attempts < 4:
                            try:
                                plex.update_added_date(section_id, rating_key, type_id, new_unix, lock=lock_added)
                                successes += 1
                                last_err = None
                                break
                            except Exception as e:  # noqa: BLE001
                                attempts += 1
                                last_err = e
                                backoff = min(8, 0.5 * (2 ** (attempts - 1)))
                                time.sleep(backoff)
                        if last_err is not None:
                            st.error(f"Failed updating id={rating_key}: {last_err}")
                    finally:
                        progress.progress(int(idx * 100 / total))
                        if per_item_sleep:
                            time.sleep(per_item_sleep)
                st.success(f"Updated {successes}/{total} items.")

    # Render list
    for item in items:
        rating_key = str(item.get("ratingKey"))
        cols = st.columns([0.2, 0.8])
        with cols[0]:
            checked = page_select_all or selected.get(rating_key, False)
            sel = st.checkbox("Select", key=f"{key_prefix}_sel_{rating_key}", value=checked)
            selected[rating_key] = sel
            if show_images:
                thumb = item.get("thumb")
                url = plex.thumb_url(thumb)
                if url:
                    st.image(url, width=110)
        with cols[1]:
            title = item.get("title", "Unknown")
            year = item.get("year")
            rel = item.get("originallyAvailableAt")
            display = f"{title} ({year})" if year else title
            if rel:
                st.markdown(
                    f"<h3 title='Release Date: {rel}' style='margin-bottom:0'>{display}</h3>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"<h3 style='margin-bottom:0'>{display}</h3>", unsafe_allow_html=True)

            added_at = item.get("addedAt")
            if added_at:
                added_dt = datetime.datetime.fromtimestamp(int(added_at))
            else:
                added_dt = datetime.datetime.now()

            if show_item_edit:
                new_date = st.date_input(
                    "Edit Added Date",
                    value=added_dt.date(),
                    key=f"{key_prefix}_date_{rating_key}",
                )
                new_unix = int(datetime.datetime.combine(new_date, datetime.time.min).timestamp())
                if st.button("Update Date", key=f"{key_prefix}_update_{rating_key}"):
                    plex.update_added_date(section_id, rating_key, type_id, new_unix, lock=lock_added)
                    st.success(f"Updated added date for {title} to {new_date}")


def main():
    st.markdown("<h2 style='text-align: center;'>Plex Added Date Manager</h2>", unsafe_allow_html=True)
    _init_state()

    plex = PlexAPI()
    if not plex.base_url or not plex.token:
        st.error("Missing PLEX_BASE_URL or PLEX_TOKEN in environment (.env).")
        st.stop()
    # Load sections once
    try:
        sections = plex.get_sections()
    except Exception as e:
        sections = []
        st.warning(f"Could not list library sections: {e}")

    tab1, tab2 = st.tabs(["Movies", "TV Series"])  # TV Series == shows (type=2)

    # --- Movies Tab ---
    with tab1:
        cfg = _controls("movie", sections=sections, required_type="1")
        section_id = cfg["section_id"] or "1"
        type_id = "1"

        start = (cfg["page"] - 1) * int(cfg["page_size"])
        try:
            items, total = _cached_fetch(
                plex.base_url,
                plex.token,
                section_id,
                type_id,
                start,
                int(cfg["page_size"]),
                cfg["sort"],
                cfg["year"] or "",
            )
        except Exception as e:
            st.error(f"Failed to fetch items for section {section_id}: {e}")
            items, total = [], 0

        # Optional client-side title filter (applies to current page only)
        title_filter = (cfg["title"] or "").strip().lower()
        if title_filter:
            items = [i for i in items if title_filter in (i.get("title", "").lower())]

        total_pages = max(1, (total + int(cfg["page_size"]) - 1) // int(cfg["page_size"]))

        nav_l, nav_c, nav_r = st.columns([1, 2, 1])
        with nav_l:
            if st.button("◀ Prev", key="movie_prev", disabled=cfg["page"] <= 1):
                st.session_state["movie_page"] = max(1, cfg["page"] - 1)
                st.experimental_rerun()
        with nav_c:
            st.write(f"Page {cfg['page']} of {total_pages} • Total {total}")
        with nav_r:
            if st.button("Next ▶", key="movie_next", disabled=cfg["page"] >= total_pages):
                st.session_state["movie_page"] = min(total_pages, cfg["page"] + 1)
                st.experimental_rerun()

        if items:
            _render_items(
                plex,
                items,
                type_id=type_id,
                select_key="movie_selected",
                key_prefix="movie",
                show_images=cfg["show_images"],
                show_item_edit=cfg["show_item_edit"],
                lock_added=cfg["lock"],
                section_id=section_id,
                sort=cfg["sort"],
                year=cfg["year"] or "",
                title_filter=title_filter,
                page_size=int(cfg["page_size"]),
            )
        else:
            st.info("No movies found for current filters.")

    # --- TV Series (Shows) Tab ---
    with tab2:
        cfg = _controls("show", sections=sections, required_type="2")
        section_id = cfg["section_id"] or "2"
        type_id = "2"  # show

        start = (cfg["page"] - 1) * int(cfg["page_size"])
        try:
            items, total = _cached_fetch(
                plex.base_url,
                plex.token,
                section_id,
                type_id,
                start,
                int(cfg["page_size"]),
                cfg["sort"],
                cfg["year"] or "",
            )
        except Exception as e:
            st.error(f"Failed to fetch items for section {section_id}: {e}")
            items, total = [], 0

        title_filter = (cfg["title"] or "").strip().lower()
        if title_filter:
            items = [i for i in items if title_filter in (i.get("title", "").lower())]

        total_pages = max(1, (total + int(cfg["page_size"]) - 1) // int(cfg["page_size"]))

        nav_l, nav_c, nav_r = st.columns([1, 2, 1])
        with nav_l:
            if st.button("◀ Prev", key="show_prev", disabled=cfg["page"] <= 1):
                st.session_state["show_page"] = max(1, cfg["page"] - 1)
                st.experimental_rerun()
        with nav_c:
            st.write(f"Page {cfg['page']} of {total_pages} • Total {total}")
        with nav_r:
            if st.button("Next ▶", key="show_next", disabled=cfg["page"] >= total_pages):
                st.session_state["show_page"] = min(total_pages, cfg["page"] + 1)
                st.experimental_rerun()

        if items:
            _render_items(
                plex,
                items,
                type_id=type_id,
                select_key="show_selected",
                key_prefix="show",
                show_images=cfg["show_images"],
                show_item_edit=cfg["show_item_edit"],
                lock_added=cfg["lock"],
                section_id=section_id,
                sort=cfg["sort"],
                year=cfg["year"] or "",
                title_filter=title_filter,
                page_size=int(cfg["page_size"]),
            )
        else:
            st.info("No shows found for current filters.")


if __name__ == "__main__":
    main()
