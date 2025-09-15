import streamlit as st
from streamlit import components


def maybe_apply_density_from_query() -> None:
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


def inject_density_bootstrap() -> None:
    """Bootstrap density from localStorage once per tab.

    If no saved density exists, prefer Spacious on touch devices (pointer: coarse),
    otherwise Comfortable.
    """
    cur = st.session_state.get("ui_density", "Comfortable")
    html = f"""
    <script>
      (function(){{
        try {{
          const serverDensity = {cur!r};
          const bootKey = 'ui_density_boot';
          let ls = localStorage.getItem('ui_density');
          if (!ls) {{
            // pointer-aware default when nothing saved; can be disabled via ui_ptr_default=0
            const pref = localStorage.getItem('ui_ptr_default');
            const preferSpacious = (pref === null || pref === '1');
            const isTouch = (window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
            ls = (preferSpacious && isTouch) ? 'Spacious' : 'Comfortable';
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


def apply_density() -> None:
    """Apply global, density-aware CSS tokens for the whole UI."""
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

    ptr_default = '1' if bool(st.session_state.get('ui_ptr_default', True)) else '0'
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
      try {{ localStorage.setItem('ui_ptr_default', '{ptr_default}'); }} catch(e) {{}}
    </script>
    """

    st.markdown(css, unsafe_allow_html=True)

