"""
applier — daily job-application pipeline.

Reads new jobs from remote_jobs.xlsx, fetches each job description,
uses Claude to tailor the base resume + cover letter for the JD,
saves artifacts to applications/<slug>/, and tracks application state.
"""
from applier.slug import make_slug
from applier.state import ApplicationState, ApplicationRecord
from applier.jd_fetcher import fetch_jd
from applier.resume_tailor import tailor_resume
from applier.publisher import publish_application
from applier.applicator import submit_application

__all__ = [
    "make_slug",
    "ApplicationState",
    "ApplicationRecord",
    "fetch_jd",
    "tailor_resume",
    "publish_application",
    "submit_application",
]
