"""Navigation and query-parameter helpers for the Streamlit UI.

Contains:
- `_safe_rerun`: resilient rerun helper across Streamlit versions
- `_qp_get`/`_qp_set`: query param accessors
- `_handle_query_nav`: consumes `?{prefix}_nav=prev|next` and `?{prefix}_goto=N`
- `_nav`: in-page pager controls
- `_inject_fixed_pager`: top mini-pager bar
- `_inject_sticky_filters`: keeps filter row sticky below the header
"""

from string import Template
from typing import Dict, List, Optional

import streamlit as st
from streamlit import components


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


def _nav(
    prefix: str, position: str, cfg: Dict, total_pages: int, total: int, page_state_key: str
) -> None:
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
        if st.button(
            "Next >", key=f"{prefix}_{position}_next", disabled=int(cfg["page"]) >= int(total_pages)
        ):
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
    # Read density to size the fixed bar consistently with the app header
    try:
        density = st.session_state.get("ui_density", "Comfortable")
    except Exception:
        density = "Comfortable"
    nav_h = {"Ultra Compact": 40, "Compact": 44, "Comfortable": 48, "Spacious": 56}.get(density, 48)
    font_px = {"Ultra Compact": 12, "Compact": 12, "Comfortable": 13, "Spacious": 14}.get(
        density, 13
    )
    muted_px = max(font_px - 1, 11)
    font_small_px = max(font_px - 1, 11)
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
          @media (max-width: 640px) { #fixed-pager-$prefix { font-size: ${font_small}px; } }
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
    html = tpl.safe_substitute(
        prefix=str(prefix),
        tab=str(tab_label),
        page=str(page),
        total=str(total_pages),
        max=str(max(1, int(total_pages))),
        nav_h=str(nav_h),
        pad_v=str(pad_v),
        font_px=str(font_px),
        muted_px=str(muted_px),
        font_small=str(font_small_px),
    )
    try:
        components.v1.html(html, height=nav_h)  # type: ignore[attr-defined]
    except Exception:
        pass


def _inject_sticky_filters(tab_label: str, top_offset_px: Optional[int] = None) -> None:
    # Compute top offset from current density if not provided
    if top_offset_px is None:
        try:
            density = st.session_state.get("ui_density", "Comfortable")
        except Exception:
            density = "Comfortable"
        top_offset_px = {"Ultra Compact": 40, "Compact": 44, "Comfortable": 48, "Spacious": 56}.get(
            density, 48
        )
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
