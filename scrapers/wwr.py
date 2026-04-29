from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

RSS_URL = "https://weworkremotely.com/remote-jobs.rss"


class WWRScraper(BaseScraper):
    name = "WeWorkRemotely"

    def get_jobs(self, cutoff: date) -> list[Job]:
        try:
            resp = self._get(RSS_URL, headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; career-scan-bot/1.0)"
                ),
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

        ns = {"": ""}
        items = root.findall(".//item")
        jobs: list[Job] = []

        for item in items:
            def _text(tag: str) -> str:
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""

            pub_date_raw = _text("pubDate")
            posted = self._parse_date(pub_date_raw) if pub_date_raw else None
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url = _text("link")
            if not url:
                # WWR uses <link> which may be a CDATA or next sibling trick
                link_el = item.find("link")
                if link_el is not None and link_el.tail:
                    url = link_el.tail.strip()
            if not url:
                continue

            title_raw = _text("title")
            # WWR title format: "Company: Job Title at Company"
            parts = title_raw.split(" at ", 1)
            job_title = parts[0].strip() if parts else title_raw

            # Extract region from <region> tag if present
            region_el = item.find("{https://weworkremotely.com}region")
            location = (region_el.text or "Remote").strip() if region_el is not None else "Remote"

            category_el = item.find("{https://weworkremotely.com}category")
            category = (category_el.text or "").strip() if category_el is not None else ""

            jobs.append(Job(
                title=job_title,
                company="",
                url=url,
                source=self.name,
                date_posted=posted,
                location=location,
                job_type="",
                category=category,
                tags=[],
                salary="",
                apply_url=url,
                description_snippet=_text("description")[:500].strip(),
            ))

        logger.info("%s: %d jobs found after %s", self.name, len(jobs), cutoff)
        return jobs
