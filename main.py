#!/usr/bin/env python3
"""
career-scan — daily remote jobs scraper
Scrapes multiple job portals for remote positions posted today,
deduplicates against the existing Excel, and saves an updated file.
"""
from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from excel_manager import ExcelManager
from scrapers import (
    ArbeitnowScraper,
    JobicyScraper,
    RemoteOKScraper,
    RemotiveScraper,
    WWRScraper,
)
from scrapers.base import BaseScraper, Job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("career-scan")

EXCEL_FILE = Path("remote_jobs.xlsx")
MAX_WORKERS = 5


def _cutoff_date():
    """Return yesterday's UTC date so we capture all of today and yesterday."""
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


def _fetch(scraper: BaseScraper, cutoff) -> tuple[str, list[Job], str | None]:
    try:
        jobs = scraper.get_jobs(cutoff)
        return scraper.name, jobs, None
    except Exception as exc:
        return scraper.name, [], str(exc)


def main() -> int:
    cutoff = _cutoff_date()
    today = datetime.now(timezone.utc).date()
    logger.info("Run date: %s  |  Cutoff: %s", today, cutoff)

    scrapers: list[BaseScraper] = [
        RemoteOKScraper(),
        JobicyScraper(),
        ArbeitnowScraper(),
        RemotiveScraper(),
        WWRScraper(),
    ]

    all_jobs: list[Job] = []
    portal_stats: dict[str, int] = {}

    logger.info("Scraping %d portals in parallel (max %d workers)…", len(scrapers), MAX_WORKERS)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch, s, cutoff): s.name for s in scrapers}
        for future in as_completed(futures):
            name, jobs, error = future.result()
            if error:
                logger.warning("%-20s FAILED: %s", name, error)
                portal_stats[name] = 0
            else:
                logger.info("%-20s → %d jobs", name, len(jobs))
                portal_stats[name] = len(jobs)
                all_jobs.extend(jobs)

    logger.info("Total fetched: %d jobs across all portals", len(all_jobs))

    manager = ExcelManager(EXCEL_FILE)
    new_count = manager.add_jobs(all_jobs)
    manager.save()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print(f"  career-scan  |  {today}")
    print("=" * 55)
    print(f"  Cutoff date : {cutoff}")
    print(f"  Portals     : {len(scrapers)}")
    print()
    for portal, count in sorted(portal_stats.items()):
        print(f"  {portal:<22} {count:>4} jobs fetched")
    print()
    print(f"  Total fetched : {len(all_jobs)}")
    print(f"  New added     : {new_count}")
    print(f"  Duplicates    : {len(all_jobs) - new_count}")
    print(f"  Excel total   : {manager.total_rows} rows")
    print(f"  Saved to      : {EXCEL_FILE}")
    print("=" * 55 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
