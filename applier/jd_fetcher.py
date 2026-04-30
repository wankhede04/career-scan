"""
JD fetcher — pull the full job description from a posting URL.

Strategy: try portal-specific extractors first (Greenhouse, Lever, Ashby,
Workable, RemoteOK), then fall back to a generic readability-style extractor.
Returns plain text suitable for an LLM context window.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json,*/*",
}

TIMEOUT = 20
MAX_LEN = 18_000  # truncate JDs that are absurdly long before sending to LLM


@dataclass
class JobDescription:
    url: str
    apply_url: str
    title: str
    company: str
    location: str
    raw_text: str

    def to_markdown(self) -> str:
        return (
            f"# {self.title}\n\n"
            f"**Company**: {self.company}\n"
            f"**Location**: {self.location}\n"
            f"**Source**: {self.url}\n"
            f"**Apply**: {self.apply_url or self.url}\n\n"
            f"---\n\n{self.raw_text}\n"
        )


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_LEN]


def _greenhouse(url: str, soup: BeautifulSoup, json_data: dict | None) -> JobDescription | None:
    # https://boards.greenhouse.io/<company>/jobs/<id> ; or boards-api JSON
    if json_data:
        return JobDescription(
            url=url,
            apply_url=json_data.get("absolute_url") or url,
            title=json_data.get("title", ""),
            company=(json_data.get("company") or {}).get("name", "") or json_data.get("departments", [{}])[0].get("name", ""),
            location=(json_data.get("location") or {}).get("name", ""),
            raw_text=_clean(BeautifulSoup(json_data.get("content", ""), "html.parser").get_text("\n")),
        )
    title = soup.select_one("h1.app-title, h1") or soup.find("h1")
    body = soup.select_one("#content, .content, .job__description") or soup.find("article") or soup
    return JobDescription(
        url=url,
        apply_url=url,
        title=(title.get_text(strip=True) if title else ""),
        company="",
        location="",
        raw_text=_clean(body.get_text("\n")),
    )


def _ashby(url: str, soup: BeautifulSoup) -> JobDescription | None:
    title = soup.find("h1")
    body = soup.select_one('[class*="JobDescription"], [class*="jobDescription"], main')
    if not body:
        body = soup
    return JobDescription(
        url=url,
        apply_url=url,
        title=title.get_text(strip=True) if title else "",
        company="",
        location="",
        raw_text=_clean(body.get_text("\n")),
    )


def _workable(url: str, soup: BeautifulSoup, json_data: dict | None) -> JobDescription | None:
    if json_data:
        title = json_data.get("title", "")
        location = json_data.get("location", {}) or {}
        loc = ", ".join(filter(None, [location.get("city"), location.get("country")]))
        body = (
            (json_data.get("description") or "")
            + "\n\n"
            + (json_data.get("requirements") or "")
            + "\n\n"
            + (json_data.get("benefits") or "")
        )
        text = BeautifulSoup(body, "html.parser").get_text("\n")
        return JobDescription(
            url=url,
            apply_url=json_data.get("application_url") or url,
            title=title,
            company=json_data.get("company", {}).get("name", "") if isinstance(json_data.get("company"), dict) else "",
            location=loc,
            raw_text=_clean(text),
        )
    title = soup.find("h1")
    body = soup.select_one("[data-ui='job-description']") or soup.find("article") or soup
    return JobDescription(
        url=url,
        apply_url=url,
        title=title.get_text(strip=True) if title else "",
        company="",
        location="",
        raw_text=_clean(body.get_text("\n")),
    )


def _lever(url: str, soup: BeautifulSoup) -> JobDescription | None:
    title = soup.select_one(".posting-headline h2") or soup.find("h2") or soup.find("h1")
    body = soup.select_one(".posting-page, .content-wrapper") or soup
    return JobDescription(
        url=url,
        apply_url=url,
        title=title.get_text(strip=True) if title else "",
        company="",
        location="",
        raw_text=_clean(body.get_text("\n")),
    )


def _remoteok(url: str, soup: BeautifulSoup) -> JobDescription | None:
    title = soup.find("h1") or soup.find("h2")
    body = soup.select_one(".description, #job-description, .markdown") or soup
    return JobDescription(
        url=url,
        apply_url=url,
        title=title.get_text(strip=True) if title else "",
        company="",
        location="",
        raw_text=_clean(body.get_text("\n")),
    )


def _generic(url: str, soup: BeautifulSoup) -> JobDescription:
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()
    title = soup.find("h1") or soup.find("title")
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return JobDescription(
        url=url,
        apply_url=url,
        title=title.get_text(strip=True) if title else "",
        company="",
        location="",
        raw_text=_clean(main.get_text("\n")),
    )


def _try_json_endpoint(url: str) -> dict | None:
    """For known portals, try a JSON variant of the URL."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path

    candidates: list[str] = []
    if "greenhouse.io" in host or "boards.greenhouse.io" in host:
        # boards.greenhouse.io/<co>/jobs/<id> -> boards-api.greenhouse.io/v1/boards/<co>/jobs/<id>
        m = re.match(r"^/(?P<co>[^/]+)/jobs/(?P<id>\d+)", path)
        if m:
            candidates.append(f"https://boards-api.greenhouse.io/v1/boards/{m.group('co')}/jobs/{m.group('id')}")
    elif "workable.com" in host:
        m = re.match(r"^/(?:j/)?(?P<token>[A-Z0-9]+)/?$", path)
        if m:
            # apply.workable.com public API for a given shortcode
            candidates.append(f"https://apply.workable.com/api/v3/accounts/jobs/{m.group('token')}")

    for c in candidates:
        try:
            resp = requests.get(c, timeout=TIMEOUT, headers={**HEADERS, "Accept": "application/json"})
            if resp.ok and resp.headers.get("content-type", "").startswith("application/json"):
                return resp.json()
        except (requests.RequestException, ValueError):
            continue
    return None


def fetch_jd(url: str) -> JobDescription:
    """Fetch and parse a JD from a job posting URL.

    Raises requests.RequestException if the URL can't be fetched.
    """
    json_data = _try_json_endpoint(url)
    resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    host = urlparse(url).netloc.lower()

    if "greenhouse.io" in host:
        jd = _greenhouse(url, soup, json_data)
    elif "ashbyhq.com" in host or "ashby.io" in host or "jobs.ashbyhq.com" in host:
        jd = _ashby(url, soup)
    elif "workable.com" in host:
        jd = _workable(url, soup, json_data)
    elif "lever.co" in host or "jobs.lever.co" in host:
        jd = _lever(url, soup)
    elif "remoteok.com" in host or "remoteok.io" in host:
        jd = _remoteok(url, soup)
    else:
        jd = _generic(url, soup)

    if jd is None:
        jd = _generic(url, soup)

    if not jd.raw_text:
        raise ValueError(f"empty JD extracted from {url}")
    return jd
