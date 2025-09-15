"""Streamlit UI for browsing and batch-editing Plex 'addedAt' dates.

Highlights
- Server-side pagination (container start/size)
- Lightweight per-page title filter
- Selection persists with batch updates and rate limiting
- URL query params for pager navigation
"""

import streamlit as st

import ui_controls as controls
import ui_nav as nav
from data_cache import _cached_fetch as cached_fetch
from plex_api import PlexAPI
from ui_render import _render_items as render_items


st.set_page_config(page_title="Plex Added Date Manager", layout="wide")


def main() -> None:
    # Hydrate density from query param and localStorage bridge
    controls._maybe_apply_density_from_query()
    controls._inject_density_bootstrap()
    # Header row with density selector
    hdr_l, hdr_c, hdr_r = st.columns([3, 1, 1])
    with hdr_l:
        st.markdown("<h3 style='margin-bottom:0.25rem'>Plex Added Date Manager</h3>", unsafe_allow_html=True)
    with hdr_c:
        st.selectbox("Density", ["Comfortable", "Compact", "Ultra Compact", "Spacious"], key="ui_density")
    with hdr_r:
        if st.button("Reset All"):
            controls._reset_all()
            try:
                nav.clear_nav_params(["movie", "show"])
            except Exception:
                pass
            st.rerun()

    # App-wide density + initial state
    controls._apply_density()
    controls._init_state()

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
        cfg = controls._controls("movie", sections=sections, required_type="1")
        nav._inject_sticky_filters("Movies")
        section_id = cfg["section_id"] or "1"
        type_id = "1"

        start = (int(cfg["page"]) - 1) * int(cfg["page_size"])
        try:
            items, total = cached_fetch(
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
        nav._inject_fixed_pager("movie", "Movies", int(cfg["page"]), int(total_pages))
        nav._handle_query_nav("movie", "movie_page", int(total_pages))
        nav._nav("movie", "top", cfg, total_pages, total, "movie_page")

        if items:
            render_items(
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

        nav._nav("movie", "bottom", cfg, total_pages, total, "movie_page")

    # Shows
    with tab2:
        cfg = controls._controls("show", sections=sections, required_type="2")
        nav._inject_sticky_filters("TV Series")
        section_id = cfg["section_id"] or "2"
        type_id = "2"

        start = (int(cfg["page"]) - 1) * int(cfg["page_size"])
        try:
            items, total = cached_fetch(
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
        nav._inject_fixed_pager("show", "TV Series", int(cfg["page"]), int(total_pages))
        nav._handle_query_nav("show", "show_page", int(total_pages))
        nav._nav("show", "top", cfg, total_pages, total, "show_page")

        if items:
            render_items(
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

        nav._nav("show", "bottom", cfg, total_pages, total, "show_page")


if __name__ == "__main__":
    main()
