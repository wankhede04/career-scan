"""
Applicator — submits an application to the source portal.

Reality check: most career portals (LinkedIn, Indeed, big-co careers sites)
require a logged-in browser session, frequently with MFA + captcha. They are
not safely automatable from CI without per-user creds. This module therefore:

  * implements lightweight adapters for portals that expose a public submission
    API (Greenhouse public Job Board API, Workable public apply endpoint),
  * for everything else, falls back to opening a tracking GitHub Issue with
    the tailored artifacts and the apply URL so the user can submit manually.

Submission via API is gated behind APPLIER_AUTO_SUBMIT=1 to avoid sending real
applications during dry-runs / CI tests.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from applier.jd_fetcher import JobDescription
from applier.state import ApplicationRecord

logger = logging.getLogger(__name__)

AUTO_SUBMIT = os.environ.get("APPLIER_AUTO_SUBMIT") == "1"
APPLY_TIMEOUT = 30


@dataclass
class SubmitResult:
    submitted: bool
    portal: str
    note: str
    confirmation_id: str = ""


def _portal_for(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "greenhouse.io" in host:
        return "greenhouse"
    if "workable.com" in host:
        return "workable"
    if "ashbyhq.com" in host or "ashby.io" in host:
        return "ashby"
    if "lever.co" in host:
        return "lever"
    return "manual"


def _resume_pdf_path(slug: str) -> Path | None:
    """Resolve a PDF rendering of the tailored resume, if available.

    The default workflow renders resume.md -> resume.pdf via pandoc; if the
    PDF is missing we fall back to attaching the markdown as plain text.
    """
    pdf = Path("applications") / slug / "resume.pdf"
    return pdf if pdf.exists() else None


def _candidate_payload() -> dict:
    """Read candidate contact info from env vars (set in GH Actions secrets)."""
    keys = ["FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE", "LINKEDIN", "GITHUB_URL", "PORTFOLIO"]
    return {k.lower(): os.environ.get(f"APPLIER_{k}", "") for k in keys}


def _greenhouse_submit(record: ApplicationRecord, jd: JobDescription) -> SubmitResult:
    # Greenhouse Job Boards have a per-job application endpoint:
    #   POST https://boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>
    # https://developers.greenhouse.io/job-board.html#apply-to-job
    m = re.match(r"^/(?P<board>[^/]+)/jobs/(?P<id>\d+)", urlparse(jd.apply_url or record.url).path)
    if not m:
        return SubmitResult(False, "greenhouse", "could not parse board/job from URL")

    candidate = _candidate_payload()
    if not all([candidate["first_name"], candidate["last_name"], candidate["email"]]):
        return SubmitResult(False, "greenhouse", "missing candidate env vars (first_name, last_name, email)")

    pdf_path = _resume_pdf_path(record.slug)
    files = {}
    data = {
        "first_name": candidate["first_name"],
        "last_name": candidate["last_name"],
        "email": candidate["email"],
        "phone": candidate["phone"],
    }
    if pdf_path:
        files["resume"] = (pdf_path.name, pdf_path.read_bytes(), "application/pdf")
    else:
        md_path = Path("applications") / record.slug / "resume.md"
        files["resume_text"] = (None, md_path.read_text())

    cover_path = Path("applications") / record.slug / "cover_letter.md"
    if cover_path.exists():
        files["cover_letter_text"] = (None, cover_path.read_text())

    endpoint = f"https://boards-api.greenhouse.io/v1/boards/{m.group('board')}/jobs/{m.group('id')}"
    try:
        resp = requests.post(endpoint, data=data, files=files, timeout=APPLY_TIMEOUT)
    except requests.RequestException as exc:
        return SubmitResult(False, "greenhouse", f"network error: {exc}")

    if resp.status_code in (200, 201):
        confirmation = ""
        try:
            confirmation = str(resp.json().get("id", ""))
        except ValueError:
            pass
        return SubmitResult(True, "greenhouse", "submitted", confirmation)
    return SubmitResult(False, "greenhouse", f"http {resp.status_code}: {resp.text[:200]}")


def _manual_fallback(record: ApplicationRecord, jd: JobDescription) -> SubmitResult:
    return SubmitResult(
        submitted=False,
        portal="manual",
        note=(
            "auto-submit not supported for this portal; tailored resume + cover "
            "letter committed under applications/" + record.slug + ". Apply via "
            + (jd.apply_url or record.url)
        ),
    )


def submit_application(record: ApplicationRecord, jd: JobDescription) -> SubmitResult:
    portal = _portal_for(jd.apply_url or record.url)

    if not AUTO_SUBMIT:
        return SubmitResult(
            submitted=False,
            portal=portal,
            note="dry-run (set APPLIER_AUTO_SUBMIT=1 to enable submission)",
        )

    if portal == "greenhouse":
        return _greenhouse_submit(record, jd)
    # Workable/Ashby/Lever submission requires per-employer auth or per-job
    # tokens that are not in the public API. Treat them as manual for now.
    return _manual_fallback(record, jd)
