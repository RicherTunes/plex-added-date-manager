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
from ui_density import apply_density as __apply_density, inject_density_bootstrap as __inject_density_bootstrap, maybe_apply_density_from_query as __maybe_apply_density_from_query


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
          let ls = localStorage.getItem('ui_density');
          if (!ls) {{
            ls = (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) ? 'Spacious' : 'Comfortable';
            localStorage.setItem('ui_density', ls);
          }}
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
    __apply_density()
