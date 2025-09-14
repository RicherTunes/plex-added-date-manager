import datetime
from typing import Dict, List

import streamlit as st

from plex_api import PlexAPI

st.set_page_config(page_title="Plex Added Date Manager", layout="wide")


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


def _controls(prefix: str) -> Dict:
    section_key = f"{prefix}_section"
    page_key = f"{prefix}_page"
    page_size_key = f"{prefix}_page_size"
    sort_key = f"{prefix}_sort"
    year_key = f"{prefix}_year_filter"
    title_key = f"{prefix}_title_filter"
    images_key = f"{prefix}_show_images"
    item_edit_key = f"{prefix}_show_item_edit"
    lock_key = f"{prefix}_lock_added"

    c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1.2, 1, 1.5, 1])
    with c1:
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
        if st.button("Reset Filters"):
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
    show_images: bool,
    show_item_edit: bool,
    lock_added: bool,
    section_id: str,
):
    selected: Dict[str, bool] = st.session_state.setdefault(select_key, {})

    # Batch controls
    left, mid, right = st.columns([2, 3, 2])
    with left:
        page_select_all = st.checkbox("Select all on page")
    with mid:
        batch_date = st.date_input("Batch date", value=datetime.date.today())
    with right:
        if st.button("Apply to selected"):
            keys = [k for k, v in selected.items() if v]
            if not keys:
                st.warning("No items selected.")
            else:
                new_unix = int(datetime.datetime.combine(batch_date, datetime.time.min).timestamp())
                total = len(keys)
                progress = st.progress(0)
                successes = 0
                for idx, rating_key in enumerate(keys, start=1):
                    try:
                        plex.update_added_date(section_id, rating_key, type_id, new_unix, lock=lock_added)
                        successes += 1
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Failed updating id={rating_key}: {e}")
                    finally:
                        progress.progress(int(idx * 100 / total))
                st.success(f"Updated {successes}/{total} items.")

    # Render list
    for item in items:
        rating_key = str(item.get("ratingKey"))
        cols = st.columns([0.2, 0.8])
        with cols[0]:
            checked = page_select_all or selected.get(rating_key, False)
            sel = st.checkbox("Select", key=f"sel_{rating_key}", value=checked)
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
                    key=f"date_{rating_key}",
                )
                new_unix = int(datetime.datetime.combine(new_date, datetime.time.min).timestamp())
                if st.button("Update Date", key=f"update_{rating_key}"):
                    plex.update_added_date(section_id, rating_key, type_id, new_unix, lock=lock_added)
                    st.success(f"Updated added date for {title} to {new_date}")


def main():
    st.markdown("<h2 style='text-align: center;'>Plex Added Date Manager</h2>", unsafe_allow_html=True)
    _init_state()

    plex = PlexAPI()
    if not plex.base_url or not plex.token:
        st.error("Missing PLEX_BASE_URL or PLEX_TOKEN in environment (.env).")
        st.stop()

    tab1, tab2 = st.tabs(["Movies", "TV Series"])  # TV Series == shows (type=2)

    # --- Movies Tab ---
    with tab1:
        cfg = _controls("movie")
        section_id = cfg["section_id"] or "1"
        type_id = "1"

        filters = {}
        if cfg["year"]:
            filters["year"] = cfg["year"]

        start = (cfg["page"] - 1) * int(cfg["page_size"])
        items, total = plex.fetch_items(
            section_id,
            type_id,
            start=start,
            size=int(cfg["page_size"]),
            sort=cfg["sort"],
            filters=filters,
        )

        # Optional client-side title filter (applies to current page only)
        title_filter = (cfg["title"] or "").strip().lower()
        if title_filter:
            items = [i for i in items if title_filter in (i.get("title", "").lower())]

        total_pages = max(1, (total + int(cfg["page_size"]) - 1) // int(cfg["page_size"]))

        nav_l, nav_c, nav_r = st.columns([1, 2, 1])
        with nav_l:
            if st.button("◀ Prev", disabled=cfg["page"] <= 1):
                st.session_state["movie_page"] = max(1, cfg["page"] - 1)
                st.experimental_rerun()
        with nav_c:
            st.write(f"Page {cfg['page']} of {total_pages} • Total {total}")
        with nav_r:
            if st.button("Next ▶", disabled=cfg["page"] >= total_pages):
                st.session_state["movie_page"] = min(total_pages, cfg["page"] + 1)
                st.experimental_rerun()

        if items:
            _render_items(
                plex,
                items,
                type_id=type_id,
                select_key="movie_selected",
                show_images=cfg["show_images"],
                show_item_edit=cfg["show_item_edit"],
                lock_added=cfg["lock"],
                section_id=section_id,
            )
        else:
            st.info("No movies found for current filters.")

    # --- TV Series (Shows) Tab ---
    with tab2:
        cfg = _controls("show")
        section_id = cfg["section_id"] or "2"
        type_id = "2"  # show

        filters = {}
        if cfg["year"]:
            filters["year"] = cfg["year"]

        start = (cfg["page"] - 1) * int(cfg["page_size"])
        items, total = plex.fetch_items(
            section_id,
            type_id,
            start=start,
            size=int(cfg["page_size"]),
            sort=cfg["sort"],
            filters=filters,
        )

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
                show_images=cfg["show_images"],
                show_item_edit=cfg["show_item_edit"],
                lock_added=cfg["lock"],
                section_id=section_id,
            )
        else:
            st.info("No shows found for current filters.")


if __name__ == "__main__":
    main()
