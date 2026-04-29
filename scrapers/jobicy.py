from __future__ import annotations

import logging
from datetime import date
from typing import Any

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

API_URL = "https://jobicy.com/api/v2/remote-jobs"


class JobicyScraper(BaseScraper):
    name = "Jobicy"

    def get_jobs(self, cutoff: date) -> list[Job]:
        params = {"count": 50, "geo": "worldwide"}
        try:
            resp = self._get(API_URL, params=params)
        except Exception as e:
            logger.warning("%s: fetch failed – %s", self.name, e)
            return []

        try:
            payload: dict[str, Any] = resp.json()
        except Exception as e:
            logger.warning("%s: JSON parse failed – %s", self.name, e)
            return []

        raw_jobs = payload.get("jobs", [])
        jobs: list[Job] = []

        for item in raw_jobs:
            if not isinstance(item, dict):
                continue

            pub_date_raw = item.get("pubDate", "")
            posted = self._parse_date(pub_date_raw)
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url = item.get("url") or item.get("jobSlug") or ""
            if not url:
                continue

            industries = item.get("jobIndustry") or []
            if isinstance(industries, str):
                industries = [industries]

            jobs.append(Job(
                title=item.get("jobTitle", "").strip(),
                company=item.get("companyName", "").strip(),
                url=url.strip(),
                source=self.name,
                date_posted=posted,
                location=item.get("jobGeo") or "Remote",
                job_type=item.get("jobType", "").strip(),
                category=", ".join(industries),
                tags=[],
                salary=item.get("annualSalaryMin", "") or "",
                apply_url=url.strip(),
                description_snippet=(item.get("jobExcerpt") or "")[:500].strip(),
            ))

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
