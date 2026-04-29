from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .base import BaseScraper, Job

logger = logging.getLogger(__name__)

BOARDS_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
COMPANIES_FILE = Path(__file__).parent.parent / "companies.yml"

# Remote-indicating keywords checked against location name
_REMOTE_KEYWORDS = {"remote", "anywhere", "worldwide", "distributed", "work from home", "wfh"}


def _is_remote(location: str) -> bool:
    return any(k in location.lower() for k in _REMOTE_KEYWORDS)


DEFAULT_COMPANIES: list[dict] = [
    {"board_token": "anthropic",   "name": "Anthropic"},
    {"board_token": "cloudflare",  "name": "Cloudflare"},
    {"board_token": "stripe",      "name": "Stripe"},
    {"board_token": "hashicorp",   "name": "HashiCorp"},
    {"board_token": "datadog",     "name": "Datadog"},
    {"board_token": "elastic",     "name": "Elastic"},
    {"board_token": "mongodb",     "name": "MongoDB"},
    {"board_token": "gitlab",      "name": "GitLab"},
    {"board_token": "pagerduty",   "name": "PagerDuty"},
    {"board_token": "hubspot",     "name": "HubSpot"},
    {"board_token": "zendesk",     "name": "Zendesk"},
    {"board_token": "dbtlabs",     "name": "dbt Labs"},
    {"board_token": "scaleai",     "name": "Scale AI"},
    {"board_token": "mixpanel",    "name": "Mixpanel"},
    {"board_token": "brex",        "name": "Brex"},
    {"board_token": "figma",       "name": "Figma"},
    {"board_token": "notion",      "name": "Notion"},
    {"board_token": "rippling",    "name": "Rippling"},
    {"board_token": "gusto",       "name": "Gusto"},
    {"board_token": "reddit",      "name": "Reddit"},
]


class GreenhouseScraper(BaseScraper):
    name = "Greenhouse"

    def _load_companies(self) -> list[dict]:
        if COMPANIES_FILE.exists():
            try:
                config = yaml.safe_load(COMPANIES_FILE.read_text()) or {}
                custom = config.get("greenhouse", [])
                if custom:
                    return custom
            except Exception as e:
                logger.debug("Could not load companies.yml: %s", e)
        return DEFAULT_COMPANIES

    def _fetch_company(self, token: str, name: str, cutoff: date) -> list[Job]:
        url = BOARDS_API.format(token=token)
        try:
            resp = self._get(url)
        except Exception as e:
            logger.debug("Greenhouse %s (%s): %s", name, token, e)
            return []

        try:
            payload: dict[str, Any] = resp.json()
        except Exception:
            return []

        jobs: list[Job] = []
        for item in payload.get("jobs", []):
            if not isinstance(item, dict):
                continue

            location_name = (item.get("location") or {}).get("name", "") or ""
            if not _is_remote(location_name):
                continue

            updated_raw = item.get("updated_at") or item.get("created_at") or ""
            posted = self._parse_date(updated_raw) if updated_raw else None
            if posted is None:
                posted = self._today()

            if not self._is_recent(posted, cutoff):
                continue

            url_job = item.get("absolute_url") or item.get("url") or ""
            if not url_job:
                continue

            depts = [d.get("name", "") for d in (item.get("departments") or []) if isinstance(d, dict)]

            jobs.append(Job(
                title=item.get("title", "").strip(),
                company=name,
                url=url_job.strip(),
                source=self.name,
                date_posted=posted,
                location=location_name or "Remote",
                job_type="",
                category=", ".join(depts),
                tags=[],
                salary="",
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
                    logger.debug("Greenhouse company error: %s", e)

        logger.info("%s: %d jobs found after %s", self.name, len(all_jobs), cutoff)
        return all_jobs
