"""
Publisher — writes tailored artifacts to applications/<slug>/ on disk.

The GitHub Actions workflow takes care of committing & pushing the directory
after the orchestrator finishes.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from applier.jd_fetcher import JobDescription
from applier.resume_tailor import TailoredArtifacts
from applier.state import ApplicationRecord

logger = logging.getLogger(__name__)

APPLICATIONS_DIR = Path("applications")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def publish_application(
    record: ApplicationRecord,
    jd: JobDescription,
    artifacts: TailoredArtifacts,
    base_dir: Path = APPLICATIONS_DIR,
) -> Path:
    """Write jd.md, resume.md, cover_letter.md, match_summary.md, metadata.json
    into applications/<slug>/. Returns the directory path.
    """
    folder = base_dir / record.slug
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "jd.md").write_text(jd.to_markdown())
    (folder / "resume.md").write_text(artifacts.resume_md + "\n")
    (folder / "cover_letter.md").write_text(artifacts.cover_letter_md + "\n")
    (folder / "match_summary.md").write_text(artifacts.match_summary + "\n")

    metadata = {
        "uid": record.uid,
        "slug": record.slug,
        "company": record.company,
        "title": record.title,
        "url": record.url,
        "apply_url": jd.apply_url or record.url,
        "source": record.source,
        "state": record.state,
        "generated_at": _now_iso(),
    }
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True))

    logger.info("published artifacts -> %s", folder)
    return folder
