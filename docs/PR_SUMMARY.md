Title: Pagination, Batch Updates, CLI, Section Discovery, and Resilience for Large Libraries

Summary
- Add server-side pagination to avoid UI crashes on large libraries.
- Add filters (year, title contains) and sorting options.
- Add selection + batch update with progress and optional lock.
- Add “Select all results” and “Clear all/Clear page” actions.
- Display per-item Added date and Release date for easy triage.
- Add section discovery and per-tab Section dropdown (Movies vs TV).
- Add CLI with rate limiting (--max-per-minute) and retries.
- Add PowerShell wrapper for Unraid/Windows convenience.
- Add HTTP retries/backoff for GET/PUT to handle 429/5xx.

UI/UX Notes
- Keep page size 100–200 for best responsiveness.
- Toggle images off and per-item edit off to reduce widget count.
- Use “Select all results” to operate across pages; selection persists.
- The batch panel supports a Max/min field to limit update rate.

CLI Quickstart
```bash
python src/cli.py --list-sections                 # discover libraries
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --dry-run
python src/cli.py --section-id 1 --type movie --year 2023 --date 2024-01-15 --max-per-minute 120
```

Screenshots/GIF
- Place screenshots in docs/assets/ and reference them here.
- Suggested shots: Filters/pagination controls; Batch panel; Selection summary and meta lines; “Select all results”.

Breaking Changes
- None. Defaults preserve previous behavior but with safer pagination.

Known Limitations
- Very large “Select all results” can take time as it scans pages; rate limiting helps avoid server throttling.

