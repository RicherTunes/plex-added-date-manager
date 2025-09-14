CLI Reference

Run without the UI to update many items efficiently.

Examples
```
# Dry run: update all movies (section 1) from 2023 to have addedAt 2024-01-15
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --dry-run

# Apply with throttle 0.1s per item
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

# Discover libraries
python src/cli.py --list-sections
# Filter discovery by type
python src/cli.py --list-sections --sections-type show
```

Flags
- `--section-id` (required for updates): Your Plex library section id (Movies often `1`, Shows often `2`).
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

Exit codes
- `0`: Success.
- `1`: Runtime error (e.g., listing sections failed).
- `2`: Invalid arguments or missing required values.

Tips
- Start with `--dry-run` on a small `--year` slice to confirm matches.
- Use `--max-per-minute` for long-running batches to stay friendly to Plex.
- Prefer explicit `--ids` when re-running to avoid re-fetching.

