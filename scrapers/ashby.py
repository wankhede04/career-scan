from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

BOARDS_API = "https://api.ashbyhq.com/posting-api/job-board/{token}/published"
COMPANIES_FILE = Path(__file__).parent.parent / "companies.yml"

DEFAULT_COMPANIES: list[dict] = [
    {"board_token": "elevenlabs",    "name": "ElevenLabs"},
    {"board_token": "linear",        "name": "Linear"},
    {"board_token": "resend",        "name": "Resend"},
    {"board_token": "supabase",      "name": "Supabase"},
    {"board_token": "clerk",         "name": "Clerk"},
    {"board_token": "perplexityai",  "name": "Perplexity AI"},
    {"board_token": "modal",         "name": "Modal"},
    {"board_token": "fly",           "name": "Fly.io"},
    {"board_token": "turso",         "name": "Turso"},
    {"board_token": "neon",          "name": "Neon"},
    {"board_token": "trigger",       "name": "Trigger.dev"},
    {"board_token": "cal",           "name": "Cal.com"},
    {"board_token": "dub",           "name": "Dub.co"},
    {"board_token": "liveblocks",    "name": "Liveblocks"},
    {"board_token": "inngest",       "name": "Inngest"},
    {"board_token": "highlight",     "name": "Highlight"},
    {"board_token": "qdrant",        "name": "Qdrant"},
    {"board_token": "weaviate",      "name": "Weaviate"},
    {"board_token": "chroma",        "name": "Chroma"},
    {"board_token": "langchain",     "name": "LangChain"},
]


class AshbyScraper(BaseScraper):
    name = "Ashby"

    def _load_companies(self) -> list[dict]:
        if COMPANIES_FILE.exists():
            try:
                config = yaml.safe_load(COMPANIES_FILE.read_text()) or {}
                custom = config.get("ashby", [])
                if custom:
                    return custom
            except Exception as e:
                logger.debug("Could not load companies.yml: %s", e)
        return DEFAULT_COMPANIES

    def _fetch_company(self, token: str, name: str, cutoff: date) -> list[Job]:
        url = BOARDS_API.format(token=token)
        try:
            resp = self._get(url, params={"includeCompensation": "true"})
        except Exception as e:
            logger.debug("Ashby %s (%s): %s", name, token, e)
            return []

        try:
            payload: dict[str, Any] = resp.json()
        except Exception:
            return []

        jobs: list[Job] = []
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue

            if not item.get("isRemote", False):
                continue

            pub_raw = item.get("publishedDate") or item.get("updatedAt") or ""
            posted = self._parse_date(pub_raw) if pub_raw else None
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url_job = item.get("jobUrl") or item.get("url") or ""
            if not url_job:
                continue

            compensation = item.get("compensationTierSummary") or ""

            jobs.append(Job(
                title=item.get("title", "").strip(),
                company=name,
                url=url_job.strip(),
                source=self.name,
                date_posted=posted,
                location=item.get("locationName") or "Remote",
                job_type=item.get("employmentType") or "",
                category=item.get("teamName") or item.get("department") or "",
                tags=[],
                salary=compensation,
                apply_url=url_job.strip(),
                description_snippet="",
            ))
        return jobs

    def get_jobs(self, cutoff: date) -> list[Job]:
        companies = self._load_companies()
        all_jobs: list[Job] = []

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(self._fetch_company, c["board_token"], c["name"], cutoff): c["name"]
                for c in companies
            }
            for future in as_completed(futures):
                try:
                    all_jobs.extend(future.result())
                except Exception as e:
                    logger.debug("Ashby company error: %s", e)

        logger.info("%s: %d jobs found after %s", self.name, len(all_jobs), cutoff)
        return all_jobs
