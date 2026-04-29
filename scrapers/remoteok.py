from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"


class RemoteOKScraper(BaseScraper):
    name = "RemoteOK"

    def get_jobs(self, cutoff: date) -> list[Job]:
        import requests as _req
        try:
            resp = _req.get(
                API_URL,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; career-scan-bot/1.0)",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning("%s: fetch failed - %s", self.name, e)
            return []

        try:
            data: list[Any] = resp.json()
        except Exception as e:
            logger.warning("%s: JSON parse failed - %s", self.name, e)
            return []

        jobs: list[Job] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            epoch = item.get("epoch")
            if epoch is None:
                continue
            try:
                posted = datetime.fromtimestamp(int(epoch), tz=timezone.utc).date()
            except (ValueError, OSError):
                continue

            if not self._is_recent(posted, cutoff):
                continue

            url = item.get("url") or item.get("apply_url") or ""
            if not url:
                continue

            salary_parts = []
            if item.get("salary_min"):
                salary_parts.append(f"${item['salary_min']}")
            if item.get("salary_max"):
                salary_parts.append(f"${item['salary_max']}")
            salary = " - ".join(salary_parts)

            tags = item.get("tags") or []

            jobs.append(Job(
                title=item.get("position", "").strip(),
                company=item.get("company", "").strip(),
                url=url.strip(),
                source=self.name,
                date_posted=posted,
                location=item.get("location") or "Remote",
                job_type="",
                category="",
                tags=tags if isinstance(tags, list) else [tags],
                salary=salary,
                apply_url=item.get("apply_url", "").strip(),
                description_snippet=(item.get("description") or "")[:500].strip(),
            ))

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
