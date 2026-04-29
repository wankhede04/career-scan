from __future__ import annotations

import logging
from datetime import date
from typing import Any

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

# YC Work at a Startup public jobs search
API_URL = "https://www.workatastartup.com/api/companies"


class YCombinatorScraper(BaseScraper):
    name = "YCombinator"

    def get_jobs(self, cutoff: date) -> list[Job]:
        params = {
            "filter[remote]": "remote",
            "sort": "created_desc",
            "page": 1,
            "limit": 100,
        }
        try:
            resp = self._get(API_URL, params=params, headers={
                **{k: v for k, v in {
                    "User-Agent": "Mozilla/5.0 (compatible; career-scan-bot/1.0)",
                    "Accept": "application/json",
                    "Referer": "https://www.workatastartup.com/",
                }.items()},
            })
        except Exception as e:
            logger.warning("%s: fetch failed – %s", self.name, e)
            return []

        try:
            payload: dict[str, Any] = resp.json()
        except Exception as e:
            logger.warning("%s: JSON parse failed – %s", self.name, e)
            return []

        companies = payload.get("companies", [])
        if not isinstance(companies, list):
            companies = []

        jobs: list[Job] = []
        for company in companies:
            if not isinstance(company, dict):
                continue
            company_name = company.get("name", "").strip()
            raw_jobs = company.get("jobs", [])
            if not isinstance(raw_jobs, list):
                continue

            for item in raw_jobs:
                if not isinstance(item, dict):
                    continue

                remote_val = item.get("remote", "")
                if remote_val and remote_val not in ("remote", "yes", True, "true", "Remote"):
                    continue

                created_raw = item.get("created_at") or item.get("createdAt") or ""
                posted = self._parse_date(str(created_raw)) if created_raw else None
                if posted is None:
                    posted = self._today()

                if not self._is_recent(posted, cutoff):
                    continue

                job_id = item.get("id") or item.get("slug") or ""
                url = item.get("url") or (
                    f"https://www.workatastartup.com/jobs/{job_id}" if job_id else ""
                )
                if not url:
                    continue

                jobs.append(Job(
                    title=item.get("title", "").strip(),
                    company=company_name,
                    url=url.strip(),
                    source=self.name,
                    date_posted=posted,
                    location=item.get("location") or "Remote",
                    job_type=item.get("type") or item.get("employment_type") or "",
                    category=item.get("role_type") or "",
                    tags=[],
                    salary="",
                    apply_url=url.strip(),
                    description_snippet="",
                ))

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
