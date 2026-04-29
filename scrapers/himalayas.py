from __future__ import annotations

import logging
from datetime import date
from typing import Any

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

API_URL = "https://himalayas.app/api/jobs"


class HimalayadScraper(BaseScraper):
    name = "Himalayas"

    def get_jobs(self, cutoff: date) -> list[Job]:
        params = {"limit": 100, "isRemote": "true"}
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
        if not isinstance(raw_jobs, list):
            raw_jobs = []

        jobs: list[Job] = []
        for item in raw_jobs:
            if not isinstance(item, dict):
                continue

            pub_raw = item.get("publishedAt") or item.get("createdAt") or item.get("datePosted") or ""
            posted = self._parse_date(str(pub_raw)) if pub_raw else None
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url = item.get("url") or item.get("applicationUrl") or ""
            if not url:
                continue

            company_info = item.get("company") or {}
            company_name = (
                company_info.get("name", "") if isinstance(company_info, dict)
                else str(company_info)
            )

            tags_raw = item.get("tags") or []
            if isinstance(tags_raw, str):
                tags_raw = [t.strip() for t in tags_raw.split(",")]

            salary_min = item.get("salaryMin") or item.get("minSalary") or ""
            salary_max = item.get("salaryMax") or item.get("maxSalary") or ""
            salary_parts = [str(s) for s in [salary_min, salary_max] if s]
            salary = " – ".join(salary_parts) if salary_parts else ""

            jobs.append(Job(
                title=item.get("title", "").strip(),
                company=company_name.strip(),
                url=url.strip(),
                source=self.name,
                date_posted=posted,
                location=item.get("location") or "Remote",
                job_type=item.get("jobType") or item.get("employmentType") or "",
                category=item.get("category") or item.get("department") or "",
                tags=tags_raw if isinstance(tags_raw, list) else [],
                salary=salary,
                apply_url=url.strip(),
                description_snippet="",
            ))

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
