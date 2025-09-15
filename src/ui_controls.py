"""UI controls and session-state helpers for the Streamlit app."""

from typing import Dict, List, Optional

import streamlit as st
from streamlit import components


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


def _reset_all() -> None:
    """Reset all UI state to defaults, including density and selections."""
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
        st.session_state[k] = v


def _apply_density() -> None:
    """Apply global, density-aware CSS tokens for the whole UI.

    Scales spacing, control sizes, typography, and chrome consistently.
    Keeps legacy values working for "Ultra Compact".
    """
    density = st.session_state.get("ui_density", "Comfortable")

    # Map density -> scale/tokens
    # Ultra Compact kept as smallest scale for backward-compat
    if density not in {"Ultra Compact", "Compact", "Comfortable", "Spacious"}:
        density = "Comfortable"

    tokens = {
        "Ultra Compact": {"scale": 0.8, "control_h": 28, "nav_h": 40, "icon": 14, "radius": 6},
        "Compact": {"scale": 0.9, "control_h": 32, "nav_h": 44, "icon": 16, "radius": 7},
        "Comfortable": {"scale": 1.0, "control_h": 36, "nav_h": 48, "icon": 16, "radius": 8},
        "Spacious": {"scale": 1.15, "control_h": 44, "nav_h": 56, "icon": 18, "radius": 10},
    }[density]

    scale = tokens["scale"]
    control_h = tokens["control_h"]
    nav_h = tokens["nav_h"]
    icon = tokens["icon"]
    radius = tokens["radius"]

    # Derived spacing steps (4px baseline)
    s1 = int(round(4 * scale))
    s2 = int(round(8 * scale))
    s3 = int(round(12 * scale))
    s4 = int(round(16 * scale))

    # Typography
    t100 = max(12, int(round(12 * scale)))
    t200 = max(13, int(round(14 * scale)))

    css = f"""
    <style>
      :root {{
        --density: '{density}';
        --scale: {scale};
        --space-1: {s1}px;
        --space-2: {s2}px;
        --space-3: {s3}px;
        --space-4: {s4}px;
        --radius: {radius}px;
        --control-h: {control_h}px;
        --icon: {icon}px;
        --nav-h: {nav_h}px;
        --type-100: {t100}px;
        --type-200: {t200}px;
      }}

      /* App chrome */
      .block-container {{ padding-top: calc(var(--nav-h) + var(--space-2)); }}
      [data-testid="stHeader"] {{ height: var(--nav-h) !important; }}

      /* Titles & chips */
      .title-row h3 {{ margin-bottom: 2px; font-size: calc(var(--type-200)); }}
      .meta {{ color:#6b7280; font-size: calc(var(--type-100) * 0.95); margin: 4px 0 0; }}
      .chip {{ display:inline-block; background:#eef2ff; color:#3730a3; padding:2px var(--space-2); border-radius:12px; font-size: calc(var(--type-100) * 0.9); margin-right: var(--space-2); }}

      /* Controls */
      .stButton button {{ height: var(--control-h); padding: 0 var(--space-3); font-size: calc(var(--type-200)); border-radius: var(--radius); }}
      div[data-baseweb="select"] > div {{ min-height: var(--control-h); }}
      .stSelectbox label, .stTextInput label, .stDateInput label, .stNumberInput label {{ font-size: calc(var(--type-100)); margin-bottom: 0.2rem; }}
      .stTextInput input, .stNumberInput input, .stDateInput input {{ height: var(--control-h); font-size: calc(var(--type-200)); }}
      .stCheckbox label {{ font-size: calc(var(--type-200)); }}

      /* Layout spacing nudges */
      div[data-testid="stHorizontalBlock"] > div {{ padding-right: var(--space-2); }}
      div[data-testid="stVerticalBlock"] > div {{ margin-bottom: var(--space-3); }}

      /* Images within Streamlit image blocks will be sized by renderer */
    </style>
    <script>
      // Expose density on the parent document for custom components
      try {{ parent.document.documentElement.dataset.density = '{density}'.toLowerCase().replace(' ', '-'); }} catch(e) {{}}
      try {{ localStorage.setItem('ui_density', '{density}'); }} catch(e) {{}}
    </script>
    """

    st.markdown(css, unsafe_allow_html=True)


def _maybe_apply_density_from_query() -> None:
    """If ?ui_density=X is present, apply to session and remove the param.

    Keeps other query params intact. Supports both modern st.query_params and
    legacy experimental_* APIs.
    """
    valid = {"Ultra Compact", "Compact", "Comfortable", "Spacious"}
    # Read
    qp: Dict[str, List[str]]
    try:
        qp = dict(st.query_params)
    except Exception:
        try:
            qp = st.experimental_get_query_params()  # type: ignore[attr-defined]
        except Exception:
            qp = {}
    if not qp:
        return
    raw = qp.get("ui_density")
    val: Optional[str] = None
    if raw:
        val = raw[0] if isinstance(raw, list) else str(raw)
    if val and val in valid:
        if st.session_state.get("ui_density") != val:
            st.session_state["ui_density"] = val
        # Remove the param but keep others
        if "ui_density" in qp:
            del qp["ui_density"]
        try:
            st.query_params.clear()
            for k, v in qp.items():
                st.query_params[k] = v
        except Exception:
            try:
                # experimental_set_query_params expects kwargs
                qp_simple = {k: (v[0] if isinstance(v, list) else v) for k, v in qp.items()}
                st.experimental_set_query_params(**qp_simple)  # type: ignore[attr-defined]
            except Exception:
                pass


def _inject_density_bootstrap() -> None:
    """One-time bootstrap from localStorage -> query param to hydrate SSR.

    Avoids infinite loops by using sessionStorage flag.
    """
    cur = st.session_state.get("ui_density", "Comfortable")
    html = f"""
    <script>
      (function(){{
        try {{
          const serverDensity = {cur!r};
          const bootKey = 'ui_density_boot';
          const ls = localStorage.getItem('ui_density');
          const booted = sessionStorage.getItem(bootKey);
          if (ls && !booted && ls !== serverDensity) {{
            const url = new URL(parent.location);
            url.searchParams.set('ui_density', ls);
            sessionStorage.setItem(bootKey, '1');
            parent.location.replace(url.toString());
          }}
        }} catch(e){{}}
      }})();
    </script>
    """
    try:
        components.v1.html(html, height=0)  # type: ignore[attr-defined]
    except Exception:
        pass


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
            chosen = st.selectbox(
                "Section", options=labels, index=idx, key=f"{prefix}_section_label"
            )
            st.session_state[section_key] = label_to_key[chosen]
        else:
            st.text_input("Section ID", key=section_key)
    with r1c2:
        st.selectbox("Page Size", [50, 100, 200], key=page_size_key)
    with r1c3:
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
