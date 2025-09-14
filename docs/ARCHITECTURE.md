Architecture

High level
- Streamlit UI (`src/app.py`) renders two tabs (Movies, TV Series) with server-side pagination and light client-side filtering.
- API client (`src/plex_api.py`) wraps Plex HTTP endpoints with retrying `requests.Session`.
- CLI (`src/cli.py`) uses the same API client for batch operations and discovery, sharing pagination logic.

Data flow (UI)
- Controls build a config: section id, page, page size, sort, optional `year`, optional title filter.
- `_cached_fetch(...)` loads a single page via `PlexAPI.fetch_items` with `X-Plex-Container-Start/Size`.
- Title filter (when set) is applied client-side to current page only.
- Selection persists in `st.session_state[prefix_selected]` across pagination.
- Batch updates iterate selected items, compute Unix timestamp, and call `PlexAPI.update_added_date` with optional lock.

Pagination & navigation
- Server-side: page index → `start = (page-1) * page_size`.
- URL controls: tiny JS writes `?movie_nav=prev|next` or `?movie_goto=12` and the app consumes them via `_handle_query_nav`.
- A lightweight fixed mini-pager is injected at page top for quick navigation when the relevant tab is active.

Caching & retries
- `@st.cache_data(ttl=30)` wraps the fetcher to smooth repeated navigation and avoid bursty requests.
- HTTP retries: `PlexAPI` configures `urllib3.Retry` on GET/PUT for 429/5xx with exponential backoff.

Rate limiting
- UI batch panel: `max-per-minute` translates to a per-item sleep; requests also have internal retries.
- CLI: either `--sleep` or derived sleep from `--max-per-minute`.

Error handling
- Fetch errors display a user-visible message and render an empty list.
- Update errors show inline per-item errors in UI; CLI logs failures and continues.

Known limitations
- Client-side title filtering applies to the current page only; “select all results” across pages uses server-side scanning which may take time on large libraries.
- Some Streamlit DOM tweaks (sticky controls/mini-pager) are best-effort and may not work on all Streamlit versions.

