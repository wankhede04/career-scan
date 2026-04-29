from __future__ import annotations

import logging
from datetime import date
from typing import Any

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

API_URL = "https://www.workingnomads.com/api/exposed_jobs/"


class WorkingNomadsScraper(BaseScraper):
    name = "WorkingNomads"

    def get_jobs(self, cutoff: date) -> list[Job]:
        params = {"limit": 200, "pub_date_from": cutoff.isoformat()}
        try:
            resp = self._get(API_URL, params=params)
        except Exception as e:
            logger.warning("%s: fetch failed – %s", self.name, e)
            return []

        try:
            data: list[Any] = resp.json()
        except Exception as e:
            logger.warning("%s: JSON parse failed – %s", self.name, e)
            return []

        if isinstance(data, dict):
            data = data.get("results", data.get("jobs", []))

        jobs: list[Job] = []
        for item in data:
            if not isinstance(item, dict):
                continue

            pub_raw = item.get("pub_date", "") or item.get("pubDate", "")
            posted = self._parse_date(pub_raw) if pub_raw else None
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url = item.get("url", "").strip()
            if not url:
                continue

            tags_raw = item.get("tags", [])
            if isinstance(tags_raw, str):
                tags_raw = [t.strip() for t in tags_raw.split(",")]

            jobs.append(Job(
                title=item.get("title", "").strip(),
                company=item.get("company", "").strip(),
                url=url,
                source=self.name,
                date_posted=posted,
                location=item.get("region", "Remote").strip() or "Remote",
                job_type="",
                category=item.get("category", "").strip(),
                tags=tags_raw if isinstance(tags_raw, list) else [],
                salary=item.get("salary", "").strip() if item.get("salary") else "",
                apply_url=url,
                description_snippet="",
            ))

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
