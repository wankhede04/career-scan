"""
Resume tailor — uses the Anthropic API (Claude) to rewrite the base resume
and produce a cover letter that highlights the most relevant skills/experience
for a given JD.

Requires env var ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import logging
import os
import textwrap
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("APPLIER_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 4096


@dataclass
class TailoredArtifacts:
    resume_md: str
    cover_letter_md: str
    match_summary: str  # short notes: which skills matched, gaps, suggested talking points


SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert technical recruiter and resume editor.

    You will receive a candidate's BASE RESUME (markdown) and a JOB DESCRIPTION.
    Produce three artifacts as JSON:

    1. resume_md  — the candidate's resume rewritten to maximise relevance to the
       JD. Keep every claim truthful — only re-emphasise, re-order, and re-word
       what is already there. Do NOT invent experience, employers, dates, or
       certifications. Mirror the JD's vocabulary where the candidate genuinely
       has the underlying skill. Keep it to one page (~600 words). Markdown only.

    2. cover_letter_md — a concise (180-280 words) cover letter that opens with a
       hook tying the candidate's strongest 1-2 wins to the role's top 1-2 needs.
       No filler. No "I am writing to apply...". Markdown.

    3. match_summary — 4-8 short bullets covering: (a) the strongest matches
       between candidate and JD, (b) any obvious gaps the candidate should be
       prepared to address, (c) recommended talking points for a screen call.
       Markdown bullets.

    Return ONLY a JSON object with keys resume_md, cover_letter_md, match_summary.
    No prose around the JSON.
    """
).strip()


def _build_user_prompt(base_resume: str, jd_markdown: str, profile_yaml: str = "") -> str:
    return textwrap.dedent(
        f"""
        ## CANDIDATE PROFILE (yaml)
        ```yaml
        {profile_yaml or "(none)"}
        ```

        ## BASE RESUME (markdown)
        ```markdown
        {base_resume}
        ```

        ## JOB DESCRIPTION
        {jd_markdown}
        """
    ).strip()


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    # tolerate fenced code blocks
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
        # also strip leading ```json
        text = text.split("\n", 1)[1] if text.lower().startswith("json") else text
    return json.loads(text)


def tailor_resume(
    base_resume: str,
    jd_markdown: str,
    profile_yaml: str = "",
    model: str = DEFAULT_MODEL,
) -> TailoredArtifacts:
    """Call Claude to produce tailored resume + cover letter + match notes."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Configure it as a GitHub Actions secret "
            "or export it in your local env."
        )

    # Import lazily so the rest of the pipeline still works when the SDK is
    # missing (e.g. in environments that only run the scraper).
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    user_prompt = _build_user_prompt(base_resume, jd_markdown, profile_yaml)

    logger.info("calling Claude (%s) ...", model)
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")

    try:
        data = _parse_json_response(text)
    except json.JSONDecodeError as exc:
        logger.error("failed to parse model output as JSON: %s\n---\n%s\n---", exc, text[:500])
        raise

    return TailoredArtifacts(
        resume_md=data["resume_md"].strip(),
        cover_letter_md=data["cover_letter_md"].strip(),
        match_summary=data["match_summary"].strip(),
    )


def load_base_resume(path: Path = Path("resume/base_resume.md")) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"base resume not found at {path}. Replace the placeholder before running."
        )
    return path.read_text()


def load_profile(path: Path = Path("resume/profile.yml")) -> str:
    if not path.exists():
        return ""
    return path.read_text()
