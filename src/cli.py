import argparse
import datetime
import os
import sys
import time
from typing import Dict, Iterable, List, Optional

from dotenv import load_dotenv

from plex_api import PlexAPI


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="plex-added-date-cli",
        description="Batch update Plex addedAt dates using filters or explicit ids.",
    )

    p.add_argument("--section-id", required=True, help="Plex library section id (e.g., 1 for Movies, 2 for Shows)")
    p.add_argument(
        "--type",
        choices=["movie", "show", "1", "2"],
        default="movie",
        help="Item type: movie (1) or show (2)",
    )
    p.add_argument("--date", required=True, help="New date in YYYY-MM-DD format")
    p.add_argument("--year", help="Filter by year (server-side)")
    p.add_argument("--title-contains", help="Filter current page by title substring (client-side)")
    p.add_argument("--ids", nargs="*", help="Explicit ratingKey ids to update (skip fetching)")
    p.add_argument("--page-size", type=int, default=200, help="Fetch page size (default 200)")
    p.add_argument("--max-items", type=int, help="Stop after updating N matched items")
    p.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between updates (throttle)")
    p.add_argument("--max-per-minute", type=float, help="Max updates per minute (rate limit)")
    p.add_argument("--no-lock", action="store_true", help="Do not lock the addedAt field after update")
    p.add_argument("--base-url", help="Override PLEX_BASE_URL")
    p.add_argument("--token", help="Override PLEX_TOKEN")
    p.add_argument("--dry-run", action="store_true", help="Print planned changes without applying")

    return p.parse_args(argv)


def to_unix(date_str: str) -> int:
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise SystemExit(f"Invalid --date value: {e}")
    return int(datetime.datetime.combine(dt.date(), datetime.time.min).timestamp())


def iter_ids_from_fetch(
    plex: PlexAPI,
    section_id: str,
    type_id: str,
    page_size: int,
    year: Optional[str],
    title_contains: Optional[str],
) -> Iterable[str]:
    filters: Dict[str, str] = {}
    if year:
        filters["year"] = str(year)

    page = 0
    while True:
        start = page * page_size
        items, total = plex.fetch_items(
            section_id,
            type_id,
            start=start,
            size=page_size,
            sort="addedAt:desc",
            filters=filters,
        )
        if not items:
            break
        if title_contains:
            needle = title_contains.lower()
            items = [i for i in items if needle in (i.get("title", "").lower())]
        for it in items:
            rk = it.get("ratingKey")
            if rk is not None:
                yield str(rk)
        page += 1
        if start + page_size >= total:
            break


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    base_url = args.base_url or os.environ.get("PLEX_BASE_URL", "").rstrip("/")
    token = args.token or os.environ.get("PLEX_TOKEN", "")
    if not base_url or not token:
        print("Missing PLEX_BASE_URL or PLEX_TOKEN (env or flags)", file=sys.stderr)
        return 2

    type_id = "1" if args.type in {"movie", "1"} else "2"
    new_unix = to_unix(args.date)
    lock = not args.no_lock

    plex = PlexAPI(base_url=base_url, token=token)

    if args.ids:
        ids = [str(i) for i in args.ids]
    else:
        ids = list(
            iter_ids_from_fetch(
                plex,
                section_id=args.section_id,
                type_id=type_id,
                page_size=args.page_size,
                year=args.year,
                title_contains=args.title_contains,
            )
        )

    if not ids:
        print("No matching items found.")
        return 0

    print(f"Matched {len(ids)} items. {'DRY RUN' if args.dry_run else ''}")
    updated = 0
    # Derived throttle from max-per-minute
    rate_sleep = 0.0
    if args.max_per_minute and args.max_per_minute > 0:
        rate_sleep = max(0.0, 60.0 / float(args.max_per_minute))
    per_item_sleep = max(float(args.sleep), rate_sleep)
    for idx, rk in enumerate(ids, start=1):
        if args.max_items and updated >= args.max_items:
            break
        if args.dry_run:
            print(f"Would update id={rk} to {args.date} (unix={new_unix})")
        else:
            # Simple retry with backoff in addition to HTTPAdapter retries
            attempts = 0
            last_err = None
            while attempts < 4:
                try:
                    plex.update_added_date(args.section_id, rk, type_id, new_unix, lock=lock)
                    print(f"[{idx}/{len(ids)}] Updated id={rk}")
                    updated += 1
                    last_err = None
                    break
                except Exception as e:  # noqa: BLE001
                    attempts += 1
                    last_err = e
                    sleep_for = min(8, 0.5 * (2 ** (attempts - 1)))
                    print(f"[{idx}/{len(ids)}] Retry {attempts}/3 after error: {e}")
                    time.sleep(sleep_for)
            if last_err is not None:
                print(f"[{idx}/{len(ids)}] Failed id={rk}: {last_err}", file=sys.stderr)
        if per_item_sleep:
            time.sleep(per_item_sleep)

    print(f"Done. Updated {updated} item(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
