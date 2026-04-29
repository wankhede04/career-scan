from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

RSS_URL = "https://euremotejobs.com/feed/"


class EURemoteJobsScraper(BaseScraper):
    name = "EURemoteJobs"

    def get_jobs(self, cutoff: date) -> list[Job]:
        try:
            resp = self._get(RSS_URL, headers={
                "User-Agent": "Mozilla/5.0 (compatible; career-scan-bot/1.0)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            })
        except Exception as e:
            logger.warning("%s: fetch failed – %s", self.name, e)
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.warning("%s: XML parse failed – %s", self.name, e)
            return []

        items = root.findall(".//item")
        jobs: list[Job] = []

        for item in items:
            def _text(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""

            pub_raw = _text("pubDate")
            posted = self._parse_date(pub_raw) if pub_raw else None
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url = _text("link")
            if not url:
                link_el = item.find("link")
                if link_el is not None and link_el.tail:
                    url = link_el.tail.strip()
            if not url:
                continue

            # Extract company from <creator> or <author> if present
            company = (
                _text("{http://purl.org/dc/elements/1.1/}creator")
                or _text("author")
                or ""
            )

            # Try to extract job type and location from categories
            categories = [
                (c.text or "").strip()
                for c in item.findall("category")
                if c.text
            ]

            jobs.append(Job(
                title=_text("title"),
                company=company,
                url=url,
                source=self.name,
                date_posted=posted,
                location="EU / Remote",
                job_type="",
                category=", ".join(categories[:2]),
                tags=categories,
                salary="",
                apply_url=url,
                description_snippet=_text("description")[:500].strip(),
            ))

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
