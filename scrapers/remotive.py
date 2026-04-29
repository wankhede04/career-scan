from __future__ import annotations

import logging
from datetime import date
from typing import Any

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveScraper(BaseScraper):
    name = "Remotive"

    def get_jobs(self, cutoff: date) -> list[Job]:
        try:
            resp = self._get(API_URL, params={"limit": 100})
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

            pub_raw = item.get("publication_date", "")
            posted = self._parse_date(pub_raw) if pub_raw else None
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url = item.get("url", "").strip()
            if not url:
                continue

            tags = item.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]

            jobs.append(Job(
                title=item.get("title", "").strip(),
                company=item.get("company_name", "").strip(),
                url=url,
                source=self.name,
                date_posted=posted,
                location=item.get("candidate_required_location") or "Remote",
                job_type=item.get("job_type", "").strip(),
                category=item.get("category", "").strip(),
                tags=tags if isinstance(tags, list) else [],
                salary=item.get("salary", "").strip(),
                apply_url=url,
                description_snippet="",
            ))

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
