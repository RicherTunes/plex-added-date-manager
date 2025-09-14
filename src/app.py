import datetime
import time
from typing import Dict, List, Tuple

import streamlit as st

from plex_api import PlexAPI
from streamlit import components


st.set_page_config(page_title="Plex Added Date Manager", layout="wide")

# Lightweight styling
st.markdown(
    """
    <style>
    .meta { color:#6b7280; font-size:0.9rem; margin:4px 0 0; }
    .title-row h3 { margin-bottom: 2px; }
    .subtle { color:#6b7280; }
    .chip { display:inline-block; background:#eef2ff; color:#3730a3; padding:2px 8px; border-radius:12px; font-size:0.75rem; margin-right:6px; }
    .block-container { padding-top: .25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _safe_rerun() -> None:
    try:
        if hasattr(st, "rerun"):
            st.rerun()
            return
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
            return
    except Exception:
        pass


def _nav(prefix: str, position: str, cfg: Dict, total_pages: int, total: int, page_state_key: str) -> None:
    nav_l, nav_c, nav_r = st.columns([1, 2, 2])
    with nav_l:
        if st.button("< Prev", key=f"{prefix}_{position}_prev", disabled=cfg["page"] <= 1):
            st.session_state[page_state_key] = max(1, int(cfg["page"]) - 1)
            _safe_rerun()
    with nav_c:
        st.write(f"Page {cfg['page']} of {total_pages} - Total {total}")
    with nav_r:
        goto = st.number_input(
            "Go to page",
            min_value=1,
            max_value=max(1, int(total_pages)),
            value=int(min(max(1, int(cfg["page"])), max(1, int(total_pages)))),
            step=1,
            key=f"{prefix}_{position}_goto",
        )
        if st.button("Go", key=f"{prefix}_{position}_go"):
            st.session_state[page_state_key] = int(goto)
            _safe_rerun()
        if st.button("Next >", key=f"{prefix}_{position}_next", disabled=int(cfg["page"]) >= int(total_pages)):
            st.session_state[page_state_key] = min(int(total_pages), int(cfg["page"]) + 1)
            _safe_rerun()


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


def _init_state() -> None:
    defaults = {
        "movie_page": 1,
        "movie_page_size": 100,
        "movie_selected": {},
        "movie_show_images": True,
        "movie_sort": "addedAt:desc",
        "movie_year_filter": "",
        "movie_title_filter": "",
        "movie_section": "1",
        "movie_lock_added": True,
        "show_page": 1,
        "show_page_size": 100,
        "show_selected": {},
        "show_show_images": True,
        "show_sort": "addedAt:desc",
        "show_year_filter": "",
        "show_title_filter": "",
        "show_section": "2",
        "show_lock_added": True,
        "ui_density": "Comfortable",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def _apply_density():
    density = st.session_state.get("ui_density", "Comfortable")
    if density == "Compact":
        st.markdown(
            """
            <style>
            .title-row h3 { font-size: 1.0rem; }
            .meta { font-size: 0.8rem; }
            .chip { font-size: 0.7rem; padding: 1px 6px; }
            div[data-testid="stImage"] img { width: 96px !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )


def _controls(prefix: str, *, sections: List[dict], required_type: str) -> Dict:
    section_key = f"{prefix}_section"
    page_key = f"{prefix}_page"
    page_size_key = f"{prefix}_page_size"
    sort_key = f"{prefix}_sort"
    year_key = f"{prefix}_year_filter"
    title_key = f"{prefix}_title_filter"
    images_key = f"{prefix}_show_images"
    lock_key = f"{prefix}_lock_added"

    # Section dropdown (filtered by type)
    typed = [s for s in sections if s.get("type") == ("movie" if required_type == "1" else "show")]
    labels = [f"{s['title']} (#{s['key']})" for s in typed]
    label_to_key = {f"{s['title']} (#{s['key']})": s["key"] for s in typed}

    r1c1, r1c2, r1c3, r1c4, r1c5, r1c6 = st.columns([2.4, 1, 1.2, 1, 1.4, 1])
    with r1c1:
        if labels:
            # preserve current selection if possible
            curr = st.session_state.get(section_key)
            try:
                idx = labels.index(next(l for l in labels if label_to_key[l] == curr))
            except Exception:
                idx = 0
            chosen = st.selectbox("Section", options=labels, index=idx, key=f"{prefix}_section_label")
            st.session_state[section_key] = label_to_key[chosen]
        else:
            st.text_input("Section ID", key=section_key)
    with r1c2:
        st.selectbox("Page Size", [50, 100, 200], key=page_size_key)
    with r1c3:
        st.selectbox(
            "Sort",
            ["addedAt:desc", "addedAt:asc", "titleSort:asc", "titleSort:desc", "year:desc", "year:asc"],
            key=sort_key,
        )
    with r1c4:
        st.text_input("Year", key=year_key, placeholder="e.g. 2021")
    with r1c5:
        st.text_input("Title contains", key=title_key)
    with r1c6:
        st.checkbox("Show images", key=images_key)

    r2c1, r2c2, r2c3 = st.columns([1, 1, 3])
    with r2c1:
        st.checkbox("Lock added date", key=lock_key)
    with r2c2:
        if st.button("Reset Filters", key=f"{prefix}_reset"):
            st.session_state[year_key] = ""
            st.session_state[title_key] = ""
            st.session_state[sort_key] = "addedAt:desc"
            st.session_state[page_key] = 1
    with r2c3:
        st.caption("Tip: Use the pager to jump to any page.")

    return {
        "section_id": st.session_state[section_key],
        "page": st.session_state[page_key],
        "page_size": st.session_state[page_size_key],
        "sort": st.session_state[sort_key],
        "year": st.session_state[year_key],
        "title": st.session_state[title_key],
        "show_images": st.session_state[images_key],
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
    lock_added: bool,
    section_id: str,
    sort: str,
    year: str,
    title_filter: str,
    page_size: int,
) -> None:
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


def main() -> None:
    # Header row with density selector
    hdr_l, hdr_r = st.columns([3, 1])
    with hdr_l:
        st.markdown("<h3 style='margin-bottom:0.25rem'>Plex Added Date Manager</h3>", unsafe_allow_html=True)
    with hdr_r:
        st.selectbox("Density", ["Comfortable", "Compact"], key="ui_density")
    _apply_density()
    _init_state()

    plex = PlexAPI()
    if not plex.base_url or not plex.token:
        st.error("Missing PLEX_BASE_URL or PLEX_TOKEN in environment (.env).")
        st.stop()

    try:
        sections = plex.get_sections()
    except Exception as e:
        sections = []
        st.warning(f"Could not list library sections: {e}")

    tab1, tab2 = st.tabs(["Movies", "TV Series"])  # TV Series == shows (type=2)

    # Movies
    with tab1:
        cfg = _controls("movie", sections=sections, required_type="1")
        section_id = cfg["section_id"] or "1"
        type_id = "1"

        start = (int(cfg["page"]) - 1) * int(cfg["page_size"])
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

        # Filter title (current page)
        title_filter = (cfg["title"] or "").strip().lower()
        if title_filter:
            items = [i for i in items if title_filter in (i.get("title", "").lower())]

        total_pages = max(1, (total + int(cfg["page_size"]) - 1) // int(cfg["page_size"]))
        _nav("movie", "top", cfg, total_pages, total, "movie_page")

        if items:
            _render_items(
                plex,
                items,
                type_id=type_id,
                select_key="movie_selected",
                key_prefix="movie",
                show_images=cfg["show_images"],
                lock_added=cfg["lock"],
                section_id=section_id,
                sort=cfg["sort"],
                year=cfg["year"] or "",
                title_filter=title_filter,
                page_size=int(cfg["page_size"]),
            )
        else:
            st.info("No movies found for current filters.")

        _nav("movie", "bottom", cfg, total_pages, total, "movie_page")

    # Shows
    with tab2:
        cfg = _controls("show", sections=sections, required_type="2")
        section_id = cfg["section_id"] or "2"
        type_id = "2"

        start = (int(cfg["page"]) - 1) * int(cfg["page_size"])
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
        _nav("show", "top", cfg, total_pages, total, "show_page")

        if items:
            _render_items(
                plex,
                items,
                type_id=type_id,
                select_key="show_selected",
                key_prefix="show",
                show_images=cfg["show_images"],
                lock_added=cfg["lock"],
                section_id=section_id,
                sort=cfg["sort"],
                year=cfg["year"] or "",
                title_filter=title_filter,
                page_size=int(cfg["page_size"]),
            )
        else:
            st.info("No shows found for current filters.")

        _nav("show", "bottom", cfg, total_pages, total, "show_page")


if __name__ == "__main__":
    main()

