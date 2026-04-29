from __future__ import annotations

import logging
from datetime import date
from typing import Any

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowScraper(BaseScraper):
    name = "Arbeitnow"

    def get_jobs(self, cutoff: date) -> list[Job]:
        jobs: list[Job] = []
        page = 1

        while True:
            try:
                resp = self._get(API_URL, params={"page": page})
            except Exception as e:
                logger.warning("%s: fetch failed (page %d) - %s", self.name, page, e)
                break

            try:
                payload: dict[str, Any] = resp.json()
            except Exception as e:
                logger.warning("%s: JSON parse failed - %s", self.name, e)
                break

            items = payload.get("data", [])
            if not items:
                break

            any_recent = False
            for item in items:
                if not isinstance(item, dict):
                    continue

                if not item.get("remote", False):
                    continue

                created_raw = item.get("created_at", "")
                posted = self._parse_date(str(created_raw)) if created_raw else None
                if posted is None:
                    posted = self._today()

                if not self._is_recent(posted, cutoff):
                    continue

                any_recent = True
                url = item.get("url", "").strip()
                if not url:
                    continue

                tags = item.get("tags") or []
                job_types = item.get("job_types") or []

                jobs.append(Job(
                    title=item.get("title", "").strip(),
                    company=item.get("company_name", "").strip(),
                    url=url,
                    source=self.name,
                    date_posted=posted,
                    location=item.get("location") or "Remote",
                    job_type=", ".join(job_types) if isinstance(job_types, list) else job_types,
                    category="",
                    tags=tags if isinstance(tags, list) else [tags],
                    salary="",
                    apply_url=url,
                    description_snippet=(item.get("description") or "")[:500].strip(),
                ))

            if not any_recent and items:
                break

            links = payload.get("links", {})
            if not links.get("next"):
                break
            page += 1

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
