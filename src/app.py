"""Streamlit UI for browsing and batch-editing Plex 'addedAt' dates.

Highlights
- Server-side pagination (container start/size)
- Lightweight per-page title filter
- Selection persists with batch updates and rate limiting
- URL query params for pager navigation
"""
import datetime
import time
from typing import Dict, List, Tuple

import streamlit as st

from plex_api import PlexAPI
from streamlit import components
from string import Template


st.set_page_config(page_title="Plex Added Date Manager", layout="wide")

def _maybe_apply_density_from_query() -> None:
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
    valid = {"Ultra Compact", "Compact", "Comfortable", "Spacious"}
    val = raw[0] if isinstance(raw, list) else raw
    if val and val in valid:
        st.session_state["ui_density"] = val
        try:
            st.query_params.clear()
            for k, v in qp.items():
                if k == "ui_density":
                    continue
                st.query_params[k] = v
        except Exception:
            try:
                qp2 = {k: (v[0] if isinstance(v, list) else v) for k, v in qp.items() if k != "ui_density"}
                st.experimental_set_query_params(**qp2)  # type: ignore[attr-defined]
            except Exception:
                pass


def _inject_density_bootstrap() -> None:
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

# Lightweight styling
st.markdown(
    """
    <style>
    .meta { color:#6b7280; font-size:0.9rem; margin:4px 0 0; }
    .title-row h3 { margin-bottom: 2px; }
    .subtle { color:#6b7280; }
    .chip { display:inline-block; background:#eef2ff; color:#3730a3; padding:2px 8px; border-radius:12px; font-size:0.75rem; margin-right:6px; }
    /* Leave room for fixed mini-pager at top */
    .block-container { padding-top: 3.0rem; }
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


def _qp_get() -> Dict[str, List[str]]:
    try:
        return dict(st.query_params)
    except Exception:
        try:
            return st.experimental_get_query_params()  # type: ignore[attr-defined]
        except Exception:
            return {}


def _qp_set(params: Dict[str, str]) -> None:
    try:
        st.query_params.clear()
        for k, v in params.items():
            st.query_params[k] = v
    except Exception:
        try:
            st.experimental_set_query_params(**params)  # type: ignore[attr-defined]
        except Exception:
            pass


def _handle_query_nav(prefix: str, page_state_key: str, total_pages: int) -> None:
    q = _qp_get()
    nav_key = f"{prefix}_nav"
    goto_key = f"{prefix}_goto"
    changed = False
    if nav_key in q:
        val = (q.get(nav_key) or [""])[0]
        page = int(st.session_state[page_state_key])
        if val == "prev" and page > 1:
            st.session_state[page_state_key] = page - 1
            changed = True
        elif val == "next" and page < int(total_pages):
            st.session_state[page_state_key] = page + 1
            changed = True
    if goto_key in q:
        try:
            page = int((q.get(goto_key) or [""])[0])
            page = max(1, min(int(total_pages), page))
            st.session_state[page_state_key] = page
            changed = True
        except Exception:
            pass
    if changed:
        for k in [nav_key, goto_key]:
            if k in q:
                del q[k]
        _qp_set({k: (v[0] if isinstance(v, list) else v) for k, v in q.items()})
        _safe_rerun()


def _inject_fixed_pager(prefix: str, tab_label: str, page: int, total_pages: int) -> None:
    # Size bar using current density
    density = st.session_state.get("ui_density", "Comfortable")
    nav_h = {"Ultra Compact": 40, "Compact": 44, "Comfortable": 48, "Spacious": 56}.get(density, 48)
    font_px = {"Ultra Compact": 12, "Compact": 12, "Comfortable": 13, "Spacious": 14}.get(density, 13)
    muted_px = max(font_px - 1, 11)
    pad_v = {"Ultra Compact": 4, "Compact": 6, "Comfortable": 6, "Spacious": 8}.get(density, 6)
    tpl = Template(
        """
        <style>
          #fixed-pager-$prefix {
            position: fixed; top: 0; left: 0; right: 0; height: ${nav_h}px;
            background: rgba(255,255,255,0.9); backdrop-filter: blur(4px);
            border-bottom: 1px solid #e5e7eb; z-index: 1000;
            display: flex; align-items: center; gap: 8px; padding: ${pad_v}px 12px; font-family: ui-sans-serif, system-ui; font-size: ${font_px}px;
          }
          #fixed-pager-$prefix input { width: 70px; }
          #fixed-pager-$prefix .spacer { flex: 1; }
          #fixed-pager-$prefix .muted { color:#6b7280; font-size: ${muted_px}px; }
          @media (max-width: 640px) { #fixed-pager-$prefix { font-size: ${muted_px}px; } }
        </style>
        <div id="fixed-pager-$prefix" style="display:none">
          <button class="prev" title="Prev">&lt; Prev</button>
          <span class="muted">$tab</span>
          <span>Page $page / $total</span>
          <span class="spacer"></span>
          <label>Go to</label>
          <input class="goto" type="number" min="1" max="$max" value="$page"/>
          <button class="go">Go</button>
          <button class="next" title="Next">Next &gt;</button>
        </div>
        <script>
          (function(){
            const tabLabel = "$tab";
            const prefix = "$prefix";
            const root = document.getElementById('fixed-pager-'+prefix);
            function activeTab(){
              const t = parent.document.querySelector('button[role="tab"][aria-selected="true"]');
              return t ? t.innerText.trim() : '';
            }
            function showIfActive(){ root.style.display = (activeTab()===tabLabel)?'flex':'none'; }
            function setParam(k,v){
              try {
                const url = new URL(parent.location);
                url.searchParams.set(k,v);
                parent.location.replace(url.toString());
              } catch(e){}
            }
            root.querySelector('.prev').addEventListener('click', ()=> setParam(prefix+'_nav','prev'));
            root.querySelector('.next').addEventListener('click', ()=> setParam(prefix+'_nav','next'));
            root.querySelector('.go').addEventListener('click', ()=> { const v = root.querySelector('.goto').value; if(v) setParam(prefix+'_goto', v); });
            window.addEventListener('keydown', (e)=>{
              if (activeTab()!==tabLabel) return;
              if (e.key==='ArrowLeft') setParam(prefix+'_nav','prev');
              if (e.key==='ArrowRight') setParam(prefix+'_nav','next');
              if (e.key==='Enter') {
                const el = root.querySelector('.goto');
                if (document.activeElement === el) { const v = el.value; if(v) setParam(prefix+'_goto', v); }
              }
            });
            setInterval(showIfActive, 400);
            showIfActive();
          })();
        </script>
        """
    )
    html = tpl.safe_substitute(prefix=str(prefix), tab=str(tab_label), page=str(page), total=str(total_pages), max=str(max(1, int(total_pages))), nav_h=str(nav_h), font_px=str(font_px), muted_px=str(muted_px), pad_v=str(pad_v))
    try:
        components.v1.html(html, height=nav_h)  # type: ignore[attr-defined]
    except Exception:
        pass


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


def _apply_density() -> None:
    """Apply global, density-aware CSS tokens for the whole UI.

    Scales spacing, control sizes, typography, and chrome consistently.
    Keeps legacy values working for "Ultra Compact".
    """
    density = st.session_state.get("ui_density", "Comfortable")

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

    s1 = int(round(4 * scale))
    s2 = int(round(8 * scale))
    s3 = int(round(12 * scale))
    s4 = int(round(16 * scale))

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

      .block-container {{ padding-top: calc(var(--nav-h) + var(--space-2)); }}
      [data-testid="stHeader"] {{ height: var(--nav-h) !important; }}

      .title-row h3 {{ margin-bottom: 2px; font-size: calc(var(--type-200)); }}
      .meta {{ color:#6b7280; font-size: calc(var(--type-100) * 0.95); margin: 4px 0 0; }}
      .chip {{ display:inline-block; background:#eef2ff; color:#3730a3; padding:2px var(--space-2); border-radius:12px; font-size: calc(var(--type-100) * 0.9); margin-right: var(--space-2); }}

      .stButton button {{ height: var(--control-h); padding: 0 var(--space-3); font-size: calc(var(--type-200)); border-radius: var(--radius); }}
      div[data-baseweb="select"] > div {{ min-height: var(--control-h); }}
      .stSelectbox label, .stTextInput label, .stDateInput label, .stNumberInput label {{ font-size: calc(var(--type-100)); margin-bottom: 0.2rem; }}
      .stTextInput input, .stNumberInput input, .stDateInput input {{ height: var(--control-h); font-size: calc(var(--type-200)); }}
      .stCheckbox label {{ font-size: calc(var(--type-200)); }}

      div[data-testid="stHorizontalBlock"] > div {{ padding-right: var(--space-2); }}
      div[data-testid="stVerticalBlock"] > div {{ margin-bottom: var(--space-3); }}
    </style>
    <script>
      try {{ parent.document.documentElement.dataset.density = '{density}'.toLowerCase().replace(' ', '-'); }} catch(e) {{}}
      try {{ localStorage.setItem('ui_density', '{density}'); }} catch(e) {{}}
    </script>
    """

    st.markdown(css, unsafe_allow_html=True)


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


def main() -> None:
    # Density persistence (localStorage → query) and initial hydrate
    _maybe_apply_density_from_query()
    _inject_density_bootstrap()
    # Header row with density selector
    hdr_l, hdr_c, hdr_r = st.columns([3, 1, 1])
    with hdr_l:
        st.markdown("<h3 style='margin-bottom:0.25rem'>Plex Added Date Manager</h3>", unsafe_allow_html=True)
    with hdr_c:
        st.selectbox("Density", ["Comfortable", "Compact", "Ultra Compact", "Spacious"], key="ui_density")
    with hdr_r:
        if st.button("Reset All"):
            # Reset common keys
            for k in list(st.session_state.keys()):
                if k.startswith('movie_') or k.startswith('show_') or k in {'ui_density'}:
                    st.session_state.pop(k, None)
            st.session_state['ui_density'] = 'Comfortable'
            # Clear nav query params
            try:
                st.query_params.clear()
            except Exception:
                try:
                    st.experimental_set_query_params()  # type: ignore[attr-defined]
                except Exception:
                    pass
            st.rerun()
    # Settings expander
    with st.expander("Settings"):
        st.checkbox(
            "Prefer Spacious on touch",
            key="ui_ptr_default",
            help="When enabled (default), new sessions on touch devices start in Spacious if no saved density exists.",
        )
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
        _inject_sticky_filters(
            "Movies",
            top_offset_px=56 if st.session_state.get("ui_density") == "Spacious" else (44 if st.session_state.get("ui_density") == "Compact" else 48),
        )
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
        _inject_fixed_pager("movie", "Movies", int(cfg["page"]), int(total_pages))
        _handle_query_nav("movie", "movie_page", int(total_pages))
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
        _inject_sticky_filters(
            "TV Series",
            top_offset_px=56 if st.session_state.get("ui_density") == "Spacious" else (44 if st.session_state.get("ui_density") == "Compact" else 48),
        )
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
        _inject_fixed_pager("show", "TV Series", int(cfg["page"]), int(total_pages))
        _handle_query_nav("show", "show_page", int(total_pages))
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


def _inject_sticky_filters(tab_label: str, top_offset_px: int = 48) -> None:
    tpl = Template(
        """
        <script>
          (function(){
            const tabLabel = "$tab";
            function activeTab(){
              const t = parent.document.querySelector('button[role="tab"][aria-selected="true"]');
              return t ? t.innerText.trim() : '';
            }
            function getActivePanel(){
              const tabs = parent.document.querySelectorAll('button[role="tab"]');
              let idx = -1;
              tabs.forEach((t,i)=>{ if(t.getAttribute('aria-selected')==='true') idx=i; });
              const panels = parent.document.querySelectorAll('div[role="tabpanel"]');
              return (idx>=0 && panels[idx])? panels[idx] : null;
            }
            function makeSticky(){
              if(activeTab()!==tabLabel) return;
              const panel = getActivePanel();
              if(!panel) return;
              const btns = panel.querySelectorAll('button');
              let resetBtn = null;
              btns.forEach(b=>{ if((b.innerText||'').trim()==='Reset Filters') resetBtn=b; });
              if(!resetBtn) return;
              let node = resetBtn.parentElement;
              for(let i=0; i<8 && node; i++){
                if(node.getAttribute && (node.getAttribute('data-testid')==='stHorizontalBlock' || node.getAttribute('data-testid')==='stVerticalBlock')) break;
                node = node.parentElement;
              }
              if(!node) return;
              node.style.position = 'sticky';
              node.style.top = '$toppx';
              node.style.zIndex = '900';
              node.style.background = 'rgba(255,255,255,0.96)';
              node.style.backdropFilter = 'blur(2px)';
              node.style.borderBottom = '1px solid #e5e7eb';
              node.style.paddingTop = '6px';
              node.style.paddingBottom = '6px';
            }
            setTimeout(makeSticky, 50);
            setInterval(makeSticky, 500);
          })();
        </script>
        """
    )
    html = tpl.safe_substitute(tab=str(tab_label), toppx=f"{int(top_offset_px)}px")
    try:
        components.v1.html(html, height=0)  # type: ignore[attr-defined]
    except Exception:
        pass


if __name__ == "__main__":
    main()

























