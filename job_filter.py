from __future__ import annotations

import logging
import re

from scrapers.base import Job

logger = logging.getLogger(__name__)

# -- 1. Experience level exclusions (title only) -------------------------------

_JUNIOR_RE = re.compile(
    r"\b("
    r"junior|jr\.?|entry[\s\-]level|entry\s+level|"
    r"intern(ship)?|new\s+grad|graduate\s+(engineer|developer|position|role)|"
    r"apprentice|trainee|associate\s+(engineer|developer)|"
    r"[il][\s\-]?(engineer|developer)|level[\s\-]?[i1][\b\s]"
    r")\b",
    re.I,
)

_OVER_SENIOR_RE = re.compile(
    r"\b("
    r"staff\s+(software|engineer|developer)|"
    r"principal\s+(software|engineer|developer)|"
    r"distinguished\s+(engineer|developer)|"
    r"director(\s+of)?|vice\s+president|\bvp\b|"
    r"head\s+of\s+(engineering|technology|product)|"
    r"chief\s+(technical|technology|engineer|architect)|"
    r"c[\s\-]?[tl]o\b"
    r")\b",
    re.I,
)

# -- 2. Target designations ---------------------------------------------------
# Checked against title + tags + category + description

_DESIGNATION_RES: list[re.Pattern] = [
    # Backend
    re.compile(r"\bback[\s\-]?end\b", re.I),
    re.compile(r"\bserver[\s\-]side\b", re.I),
    re.compile(r"\bapi\s+(engineer|developer)\b", re.I),
    # Frontend
    re.compile(r"\bfront[\s\-]?end\b", re.I),
    re.compile(r"\bui\s+(engineer|developer)\b", re.I),
    # Fullstack
    re.compile(r"\bfull[\s\-]?stack\b", re.I),
    # Protocol
    re.compile(r"\bprotocol[\s\-]?(engineer|developer|layer|dev)?\b", re.I),
    # Blockchain / Web3
    re.compile(r"\bblockchain\b", re.I),
    re.compile(r"\bweb\s*3\b", re.I),
    re.compile(r"\bsmart[\s\-]?contract\b", re.I),
    re.compile(r"\bdefi\b", re.I),
    re.compile(r"\bsolidity\b", re.I),
    re.compile(r"\bcrypto(currency|graphic)?\b", re.I),
    re.compile(r"\bdecentrali[sz]ed\b", re.I),
    re.compile(r"\bweb3\b", re.I),
    # AI / ML
    re.compile(r"\bai\s+(engineer|developer|researcher|scientist)\b", re.I),
    re.compile(r"\bartificial\s+intelligence\b", re.I),
    re.compile(r"\bmachine\s+learning\b", re.I),
    re.compile(r"\bml\s+(engineer|developer|researcher)\b", re.I),
    re.compile(r"\bdeep\s+learning\b", re.I),
    re.compile(r"\b(large\s+language\s+model|llm)\b", re.I),
    re.compile(r"\bnlp\b|\bnatural\s+language\s+processing\b", re.I),
    re.compile(r"\bdata\s+scientist\b", re.I),
    re.compile(r"\bgenerative\s+ai\b|\bgenai\b", re.I),
    re.compile(r"\bml[\s\-]?ops\b|\bmlops\b", re.I),
    re.compile(r"\b(ai|ml|llm)\s*(infrastructure|platform|infra)\b", re.I),
]

# -- 3. Language filtering ----------------------------------------------------
# If ANY language keyword appears in the posting, at least one must be accepted.

_ANY_LANG_RE = re.compile(
    r"\b("
    r"golang|rustlang|javascript|typescript|python|"
    r"\bjava\b|ruby|php|scala|kotlin|swift|elixir|haskell|"
    r"perl|clojure|erlang|ocaml|cobol|fortran|"
    r"c\+\+|c#|\.net|objective[\s\-]c"
    r")\b",
    re.I,
)

_ACCEPTED_LANG_RE = re.compile(
    r"\b("
    r"golang|"
    r"rust|"
    r"javascript|node\.?js|react(\.?js)?|vue(\.?js)?|angular|next\.?js|nuxt|svelte|"
    r"typescript|"
    r"python|django|fastapi|flask|pandas|numpy|pytorch|tensorflow"
    r")\b",
    re.I,
)

# For tag-level matching (exact, case-insensitive)
_ACCEPTED_LANG_TAGS: frozenset[str] = frozenset({
    "go", "golang",
    "rust",
    "javascript", "js", "node", "nodejs", "node.js",
    "react", "reactjs", "react.js",
    "vue", "vuejs", "vue.js",
    "angular",
    "next.js", "nextjs", "nuxt", "svelte",
    "typescript", "ts",
    "python", "django", "fastapi", "flask",
})

# -- Public API ----------------------------------------------------------------

def filter_jobs(jobs: list[Job]) -> tuple[list[Job], dict[str, int]]:
    """
    Filter jobs against experience, designation, and language criteria.
    Returns (accepted_jobs, stats_dict).
    """
    accepted: list[Job] = []
    stats = {"junior": 0, "over_senior": 0, "wrong_designation": 0, "wrong_language": 0}

    for job in jobs:
        reason = _reject_reason(job)
        if reason:
            stats[reason] += 1
        else:
            accepted.append(job)

    logger.info(
        "Filter: %d/%d jobs kept  (junior=%d, over_senior=%d, wrong_designation=%d, wrong_language=%d)",
        len(accepted), len(jobs),
        stats["junior"], stats["over_senior"],
        stats["wrong_designation"], stats["wrong_language"],
    )
    return accepted, stats


def _reject_reason(job: Job) -> str | None:
    title_lower = job.title.lower()

    # 1. Skip clearly junior / intern roles
    if _JUNIOR_RE.search(title_lower):
        return "junior"

    # 2. Skip executive / over-senior roles
    if _OVER_SENIOR_RE.search(title_lower):
        return "over_senior"

    # Build combined text for designation + language checks
    combined = " ".join(filter(None, [
        job.title,
        job.category,
        job.tags_str(),
        job.description_snippet,
    ])).lower()

    # 3. Designation: must match at least one target role.
    #    Special fallback: "engineer/developer" + accepted language counts as a role match.
    designation_match = any(p.search(combined) for p in _DESIGNATION_RES)
    if not designation_match:
        is_eng_or_dev = bool(re.search(r"\b(engineer|developer|programmer)\b", title_lower))
        has_accepted_lang = _has_accepted_language(combined, job.tags)
        if not (is_eng_or_dev and has_accepted_lang):
            return "wrong_designation"

    # 4. Language: if any language is mentioned anywhere, at least one must be accepted.
    if _ANY_LANG_RE.search(combined):
        if not _has_accepted_language(combined, job.tags):
            return "wrong_language"

    return None


def _has_accepted_language(text: str, tags: list[str]) -> bool:
    if _ACCEPTED_LANG_RE.search(text):
        return True
    return any(t.strip().lower() in _ACCEPTED_LANG_TAGS for t in tags)
