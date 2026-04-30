from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date


_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_DASHES = re.compile(r"-+")


def _slugify(text: str, max_len: int = 40) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _NON_ALNUM.sub("-", text)
    text = _DASHES.sub("-", text).strip("-")
    return text[:max_len].rstrip("-")


def make_slug(company: str, title: str, url: str, posted: date | None = None) -> str:
    """Stable slug: <company>-<title>-<short-hash> e.g. acme-senior-backend-go-3f2a91.

    Hash on URL guarantees uniqueness across same-titled roles.
    """
    company_part = _slugify(company, 24) or "company"
    title_part = _slugify(title, 60) or "role"
    digest = hashlib.md5(url.strip().rstrip("/").lower().encode()).hexdigest()[:6]
    if posted:
        return f"{posted.isoformat()}-{company_part}-{title_part}-{digest}"
    return f"{company_part}-{title_part}-{digest}"
