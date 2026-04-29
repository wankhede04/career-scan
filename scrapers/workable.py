from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

# Workable public hosted-jobs API per company
BOARDS_API = "https://www.workable.com/api/accounts/{subdomain}/jobs"
COMPANIES_FILE = Path(__file__).parent.parent / "companies.yml"

DEFAULT_COMPANIES: list[dict] = [
    {"subdomain": "typeform",        "name": "Typeform"},
    {"subdomain": "hotjar",          "name": "Hotjar"},
    {"subdomain": "skroutz",         "name": "Skroutz"},
    {"subdomain": "learnworlds",     "name": "LearnWorlds"},
    {"subdomain": "beat",            "name": "Beat"},
    {"subdomain": "epignosis",       "name": "Epignosis"},
    {"subdomain": "workable",        "name": "Workable"},
    {"subdomain": "codefresh",       "name": "Codefresh"},
    {"subdomain": "personio",        "name": "Personio"},
    {"subdomain": "factorial",       "name": "Factorial"},
    {"subdomain": "travelperk",      "name": "TravelPerk"},
    {"subdomain": "intellias",       "name": "Intellias"},
    {"subdomain": "brightscout",     "name": "Brightscout"},
    {"subdomain": "kainos",          "name": "Kainos"},
    {"subdomain": "babbel",          "name": "Babbel"},
]


class WorkableScraper(BaseScraper):
    name = "Workable"

    def _load_companies(self) -> list[dict]:
        if COMPANIES_FILE.exists():
            try:
                config = yaml.safe_load(COMPANIES_FILE.read_text()) or {}
                custom = config.get("workable", [])
                if custom:
                    return custom
            except Exception as e:
                logger.debug("Could not load companies.yml: %s", e)
        return DEFAULT_COMPANIES

    def _fetch_company(self, subdomain: str, name: str, cutoff: date) -> list[Job]:
        url = BOARDS_API.format(subdomain=subdomain)
        try:
            resp = self._get(url, params={"remote": "true", "state": "published"})
        except Exception as e:
            logger.debug("Workable %s (%s): %s", name, subdomain, e)
            return []

        try:
            payload: dict[str, Any] = resp.json()
        except Exception:
            return []

        jobs: list[Job] = []
        raw_jobs = payload.get("jobs", [])

        for item in raw_jobs:
            if not isinstance(item, dict):
                continue

            location_info = item.get("location") or {}
            is_remote = (
                location_info.get("remote", False)
                if isinstance(location_info, dict)
                else False
            )
            location_str = (
                location_info.get("location_str", "")
                if isinstance(location_info, dict)
                else str(location_info)
            )
            if not is_remote and "remote" not in location_str.lower():
                continue

            created_raw = item.get("created_at") or item.get("createdAt") or ""
            posted = self._parse_date(created_raw) if created_raw else None
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url_job = item.get("url") or item.get("application_url") or ""
            if not url_job:
                continue

            jobs.append(Job(
                title=item.get("title") or item.get("full_title") or "",
                company=name,
                url=url_job.strip(),
                source=self.name,
                date_posted=posted,
                location=location_str or "Remote",
                job_type=item.get("type") or "",
                category=item.get("department") or "",
                tags=[],
                salary="",
                apply_url=item.get("application_url") or url_job,
                description_snippet="",
            ))
        return jobs

    def get_jobs(self, cutoff: date) -> list[Job]:
        companies = self._load_companies()
        all_jobs: list[Job] = []

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(self._fetch_company, c["subdomain"], c["name"], cutoff): c["name"]
                for c in companies
            }
            for future in as_completed(futures):
                try:
                    all_jobs.extend(future.result())
                except Exception as e:
                    logger.debug("Workable company error: %s", e)

        logger.info("%s: %d jobs found after %s", self.name, len(all_jobs), cutoff)
        return all_jobs
