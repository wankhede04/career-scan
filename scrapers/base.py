from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
}


@dataclass
class Job:
    title: str
    company: str
    url: str
    source: str
    date_posted: date
    location: str = "Remote"
    job_type: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    salary: str = ""
    apply_url: str = ""
    description_snippet: str = ""

    @property
    def uid(self) -> str:
        key = self.url.strip().rstrip("/").lower()
        return hashlib.md5(key.encode()).hexdigest()

    def tags_str(self) -> str:
        return ", ".join(self.tags)


class BaseScraper(ABC):
    name: str = "base"
    timeout: int = 15

    def _get(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("headers", HEADERS)
        resp = requests.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def _today(self) -> date:
        return datetime.now(timezone.utc).date()

    def _is_recent(self, d: date, cutoff: date) -> bool:
        return d >= cutoff

    def _parse_date(self, raw: str) -> Optional[date]:
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(raw.strip(), fmt)
                return dt.date()
            except ValueError:
                continue
        logger.debug("Cannot parse date: %r", raw)
        return None

    @abstractmethod
    def get_jobs(self, cutoff: date) -> list[Job]:
        """Fetch jobs posted on or after cutoff date."""
