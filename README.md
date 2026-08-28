# Plex Added Date Manager

[![CI](https://github.com/RicherTunes/plex-added-date-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/RicherTunes/plex-added-date-manager/actions/workflows/ci.yml)

Streamlit (Python) app that interacts with the Plex API to manage added dates for Movies, TV Shows, and Music (Artists, Albums, Tracks).

## Setup

1. **Clone the repository**
2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure Plex credentials:** Create a `.env` file at project root
   ```ini
   PLEX_TOKEN=your_plex_token_here
   PLEX_BASE_URL=http://your-plex-ip:32400
   ```

## Usage

```bash
streamlit run src/app.py
```

Open `http://localhost:8501` in your browser.

### What you can do

- **Movies & TV Shows**: Browse your libraries, filter by year/title, sort by added date or title, edit dates individually or in batch.
- **Music**: Browse Artists → Albums → Tracks with the same controls. Navigate with breadcrumbs (`← Artist Name` to go back).
- **Batch updates**: Select multiple items (across pages), pick a date, and update all at once with progress feedback.
- **Date range selection** (Movies/TV): Filter by preset ranges (Last 7/30/90/365 days, This Year, Older >1y) or set a custom date range.
- **Per-item auto-save**: Change a date and it saves immediately — no need to click a save button.

### UI controls

| Control | What it does |
|---------|-------------|
| **Page Size** | 50, 100, or 200 items per page |
| **Sort** | By added date or title (ascending/descending) |
| **Title contains** | Filter items by name (client-side) |
| **Year** | Filter by year (server-side, Movies/TV only) |
| **Lock added date** | Prevent Plex from overwriting the date on next scan |
| **Show images** | Toggle thumbnail visibility |
| **Show details** | Show resolution, file size, duration, genres, etc. |
| **Reset Filters** | Clear all filters and return to defaults |
| **Go to page** | Jump directly to any page |

### Batch operations

1. Check individual items or use **Select all on page** / **Select all results**
2. Pick a date in the **Batch date** picker
3. Optionally set a rate limit (**Max/min**) to avoid overwhelming Plex
4. Click **Apply to selected**

## CLI Batch Mode

Run without the UI to update many items efficiently.

```bash
# Dry run: update all movies (section 1) from 2023 to have addedAt 2024-01-15
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --dry-run

# Apply with lock and throttle 0.1s per item
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --sleep 0.1

# Rate limit to at most 120 updates/minute
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --max-per-minute 120

# Filter by title
python src/cli.py --section-id 1 --type movie --title-contains batman --date 2022-10-01

# Update specific items by ID
python src/cli.py --section-id 1 --type movie --ids 12345 67890 --date 2021-06-01

# Music: update all tracks in an album
python src/cli.py --section-id 11 --type track --date 2024-01-15

# List all library sections
python src/cli.py --list-sections

# List only music sections
python src/cli.py --list-sections --sections-type artist
```

### CLI flags

| Flag | Description |
|------|-------------|
| `--section-id` | Plex library section ID (required). Movies often `1`, Shows `2`, Music `11`. |
| `--type` | `movie`/`1`, `show`/`2`, `artist`/`8`, `album`/`9`, `track`/`10` |
| `--date` | New date in `YYYY-MM-DD` format (required) |
| `--year` | Filter by year (server-side) |
| `--title-contains` | Filter by title (client-side) |
| `--ids` | Update only these ratingKeys |
| `--page-size` | Fetch page size (default 200) |
| `--max-items` | Stop after N updates |
| `--sleep` | Seconds between updates |
| `--max-per-minute` | Rate limit; auto-calculates sleep |
| `--no-lock` | Do not lock `addedAt` after update |
| `--dry-run` | Show planned changes only |
| `--base-url` | Override `PLEX_BASE_URL` |
| `--token` | Override `PLEX_TOKEN` |
| `--list-sections` | Print key, type, and title for all libraries |
| `--sections-type` | Filter list by type: `movie`, `show`, `artist`, `photo`, `mixed` |

The CLI retries failed updates up to 3 times with exponential backoff.

## Known Limitations

- Rendering hundreds of widgets with images on a single page can feel heavy. Use page sizes of 50–200 and disable images for large libraries.
- Lists are not virtualized; pagination is the workaround.
- Music: Year filter is not available for Artists (no year field). Album year is displayed but not filterable server-side.
- Batch updates send one request per item. For very large batches, consider smaller chunks or CLI mode.

## License

MIT
