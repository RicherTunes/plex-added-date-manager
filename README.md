# Plex Added Date Manager

Streamlit (Python) app that interacts with the Plex API to fetch and manage movie data (Specifically Added Date).

<img width="1231" alt="screen" src="https://github.com/user-attachments/assets/3fae4793-9799-48d8-9715-62fc80f95601" />

## Setup Instructions

1. **Clone the repository**
2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. **Install the required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure your Plex credentials:** Create a `.env` file at project root
   ```ini
     PLEX_TOKEN=your_plex_token_here
     PLEX_BASE_URL=http://your-plex-ip:32400
   ```

## Usage

1. **Run the Streamlit application:**
   ```bash
   streamlit run src/app.py
   ```

2. **Access the application:**
   Open your web browser and go to `http://localhost:8501`.

### CLI Batch Mode

Run without the UI to update many items efficiently.

Examples:

```bash
# Dry run: update all movies (section 1) from 2023 to have addedAt 2024-01-15
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --dry-run

# Apply with lock and throttle 0.1s per item
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --sleep 0.1

# Rate limit to at most 120 updates/minute (auto sleep)
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --max-per-minute 120

# Only items whose title contains "Batman" (client-side filter)
python src/cli.py --section-id 1 --type movie --title-contains batman --date 2022-10-01

# Explicit ids (skips fetch)
python src/cli.py --section-id 1 --type movie --ids 12345 67890 --date 2021-06-01

# Override env variables if needed
python src/cli.py --section-id 1 --type movie --date 2024-01-15 \
  --base-url http://your-plex-ip:32400 --token YOUR_PLEX_TOKEN

# List sections
python src/cli.py --list-sections

# List only TV sections
python src/cli.py --list-sections --sections-type show
```

Flags:
- `--section-id` (required): Your Plex library section id (Movies often `1`, Shows often `2`).
- `--type`: `movie`/`1` or `show`/`2`.
- `--date` (required): New date in `YYYY-MM-DD`.
- `--year`: Server-side filter.
- `--title-contains`: Client-side filter per page.
- `--ids`: Update only these ratingKeys.
- `--page-size`: Fetch page size (default 200).
- `--max-items`: Stop after N updates.
- `--sleep`: Seconds between updates.
- `--max-per-minute`: Ceiling on updates per minute; auto-calculates sleep.
- `--no-lock`: Do not lock the `addedAt` field after update.
- `--dry-run`: Show planned changes only.
- `--base-url`, `--token`: Override `.env`.
 
CLI utilities:
- `--list-sections`: Prints `key`, `type`, and `title` for all libraries.
- `--sections-type`: Filter list by type (e.g., `show`, `movie`).

### New Features

- Pagination: Control page size (50/100/200) and navigate pages. Avoids crashes on large libraries.
- Server-side sorting and year filter: Sort by added date, title, or year; filter by year.
- Title contains: Client-side filter on the current page to quickly narrow items.
- Batch updates: Select multiple items (persist selections across pages), pick a date, and update all at once with progress feedback and optional metadata lock.
- Section discovery: Section selector is auto-populated from your Plex server (Movies vs Shows).
- Select all results: With current filters applied, select items across all pages; also includes "Clear all".
- QoL toggles: Show/hide images and enable/disable per-item edit controls to keep the UI light.

Notes:
- Movies use section id default `1`, shows use default `2`. Adjust in the UI if yours differ.
- Batch updates send one request per item. For very large batches, consider running in smaller chunks.

## Known Limitations

- Large libraries (thousands of items): The app currently renders your entire library on a single page. For each item it creates an image, a date input, and an update button. Streamlit must serialize all of those widgets (and any media) and send them to the browser over a WebSocket. With several thousand items, that payload becomes very large and can exceed Streamlit’s message-size/memory limits or your browser’s memory, which is why it tends to crash around ~3k items.

### Workarounds (legacy builds)

- Use the new pagination + filters to keep render sizes small.
- Reduce UI load by toggling images off when working with large pages.
- Advanced: You can raise Streamlit’s server message size via `.streamlit/config.toml` (e.g., `maxMessageSize = 500`), but the new pagination generally makes this unnecessary.

### Planned Fix

- Add server-side pagination + filtering so only a small subset of items is rendered at a time.
- Optionally add a lightweight CLI/batch mode for bulk updates without the UI.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.
