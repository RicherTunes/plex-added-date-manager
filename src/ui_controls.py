"""UI controls and session-state helpers for the Streamlit app."""

from typing import Dict, List

import streamlit as st


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


def _apply_density() -> None:
    density = st.session_state.get("ui_density", "Comfortable")
    if density == "Compact":
        st.markdown(
            """
            <style>
            /* Text sizes */
            .title-row h3 { font-size: 1.0rem; }
            .meta { font-size: 0.82rem; }
            .chip { font-size: 0.70rem; padding: 1px 6px; }
            /* Widget sizes */
            .stButton button { padding: 4px 8px; font-size: 0.85rem; }
            div[data-baseweb="select"] > div { min-height: 32px; }
            .stSelectbox label, .stTextInput label, .stDateInput label, .stNumberInput label { font-size: 0.85rem; margin-bottom: 0.15rem; }
            .stTextInput input, .stNumberInput input, .stDateInput input { height: 32px; font-size: 0.9rem; }
            .stCheckbox label { font-size: 0.9rem; }
            /* Images */
            div[data-testid="stImage"] img { width: 80px !important; }
            /* Slightly tighter container */
            .block-container { padding-top: 2.6rem; }
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

