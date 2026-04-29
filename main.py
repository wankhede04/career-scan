#!/usr/bin/env python3
"""
career-scan -- daily remote jobs scraper
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
from job_filter import filter_jobs
from scrapers import (
    # Public feed / API portals
    RemoteOKScraper,
    JobicyScraper,
    ArbeitnowScraper,
    RemotiveScraper,
    WWRScraper,
    WorkingNomadsScraper,
    EURemoteJobsScraper,
    AIJobsScraper,
    HimalayadScraper,
    YCombinatorScraper,
    # ATS platform scrapers
    GreenhouseScraper,
    AshbyScraper,
    WorkableScraper,
)
from scrapers.base import BaseScraper, Job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("career-scan")

EXCEL_FILE = Path("remote_jobs.xlsx")
MAX_WORKERS = 8


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
        # ── Public portals ────────────────────────────────────────────────────
        RemoteOKScraper(),
        JobicyScraper(),
        ArbeitnowScraper(),
        RemotiveScraper(),
        WWRScraper(),
        WorkingNomadsScraper(),
        EURemoteJobsScraper(),
        AIJobsScraper(),
        HimalayadScraper(),
        YCombinatorScraper(),
        # ── ATS platforms (per-company lists from companies.yml) ───────────────
        GreenhouseScraper(),
        AshbyScraper(),
        WorkableScraper(),
    ]

    all_jobs: list[Job] = []
    portal_stats: dict[str, int] = {}

    logger.info("Scraping %d portals in parallel (max %d workers)...", len(scrapers), MAX_WORKERS)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch, s, cutoff): s.name for s in scrapers}
        for future in as_completed(futures):
            name, jobs, error = future.result()
            if error:
                logger.warning("%-22s FAILED: %s", name, error)
                portal_stats[name] = 0
            else:
                logger.info("%-22s → %d jobs", name, len(jobs))
                portal_stats[name] = len(jobs)
                all_jobs.extend(jobs)

    logger.info("Total fetched: %d jobs across all portals", len(all_jobs))

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered_jobs, filter_stats = filter_jobs(all_jobs)
    logger.info("After filter: %d jobs remain", len(filtered_jobs))

    manager = ExcelManager(EXCEL_FILE)
    new_count = manager.add_jobs(filtered_jobs)
    manager.save()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  career-scan  |  {today}")
    print("=" * 60)
    print(f"  Cutoff date : {cutoff}")
    print(f"  Portals     : {len(scrapers)}")
    print()
    for portal, count in sorted(portal_stats.items()):
        status = f"{count:>4} jobs" if count else "  -- failed"
        print(f"  {portal:<26} {status}")
    print()
    print(f"  Total fetched  : {len(all_jobs)}")
    print()
    print("  Filter criteria:")
    print("    Experience   : 4–7 yrs  (mid / senior)")
    print("    Languages    : Go, Rust, JS, TS, Python")
    print("    Roles        : backend, fullstack, frontend,")
    print("                   protocol, blockchain, AI/ML")
    print()
    print(f"  Filtered out   : {len(all_jobs) - len(filtered_jobs)}")
    print(f"    Too junior   : {filter_stats['junior']}")
    print(f"    Too senior   : {filter_stats['over_senior']}")
    print(f"    Wrong role   : {filter_stats['wrong_designation']}")
    print(f"    Wrong lang   : {filter_stats['wrong_language']}")
    print()
    print(f"  After filter   : {len(filtered_jobs)}")
    print(f"  New added      : {new_count}")
    print(f"  Duplicates     : {len(filtered_jobs) - new_count}")
    print(f"  Excel total    : {manager.total_rows} rows")
    print(f"  Saved to       : {EXCEL_FILE}")
    print("=" * 60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
