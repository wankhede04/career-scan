from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

STATE_FILE = Path("applications/_state.json")

# State machine:
#   queued       -> seen, no JD yet
#   jd_fetched   -> JD downloaded
#   tailored     -> resume + cover letter generated and committed
#   submitted    -> application submitted via auto-applier or manual
#   responded    -> recruiter responded (manually marked)
#   rejected     -> manually marked
#   skipped      -> manually skipped (e.g. duplicate, not a fit)
VALID_STATES = {
    "queued",
    "jd_fetched",
    "tailored",
    "submitted",
    "responded",
    "rejected",
    "skipped",
    "error",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ApplicationRecord:
    uid: str
    slug: str
    company: str
    title: str
    url: str
    source: str
    state: str = "queued"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    history: list[dict] = field(default_factory=list)
    error: str = ""
    issue_number: Optional[int] = None

    def transition(self, new_state: str, note: str = "") -> None:
        if new_state not in VALID_STATES:
            raise ValueError(f"invalid state: {new_state}")
        self.history.append({"at": _now(), "from": self.state, "to": new_state, "note": note})
        self.state = new_state
        self.updated_at = _now()


class ApplicationState:
    """JSON-backed registry of all applications keyed by job uid."""

    def __init__(self, path: Path = STATE_FILE):
        self.path = Path(path)
        self.records: dict[str, ApplicationRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            logger.warning("state file %s is corrupt; starting fresh", self.path)
            return
        for uid, data in raw.items():
            self.records[uid] = ApplicationRecord(**data)

    def get(self, uid: str) -> Optional[ApplicationRecord]:
        return self.records.get(uid)

    def upsert(self, record: ApplicationRecord) -> ApplicationRecord:
        existing = self.records.get(record.uid)
        if existing:
            return existing
        self.records[record.uid] = record
        return record

    def by_state(self, *states: str) -> list[ApplicationRecord]:
        wanted = set(states)
        return [r for r in self.records.values() if r.state in wanted]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {uid: asdict(r) for uid, r in self.records.items()}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        logger.info("state saved -> %s (%d records)", self.path, len(self.records))

    def __iter__(self) -> Iterable[ApplicationRecord]:
        return iter(self.records.values())

    def __len__(self) -> int:
        return len(self.records)
