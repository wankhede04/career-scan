# career-scan

Automated daily scraper that pulls **remote jobs posted within the last 24 hours** from multiple job portals, deduplicates them against the running Excel log, and pushes the updated file to GitHub every morning.

## Portals Covered

| Portal | Method | Auth |
|---|---|---|
| [RemoteOK](https://remoteok.com) | Public JSON API | None |
| [Jobicy](https://jobicy.com) | Public JSON API | None |
| [Arbeitnow](https://www.arbeitnow.com) | Public JSON API | None |
| [Remotive](https://remotive.com) | Public JSON API | None |
| [We Work Remotely](https://weworkremotely.com) | RSS feed | None |
| [Working Nomads](https://www.workingnomads.com) | Public JSON API | None |
| [EU Remote Jobs](https://euremotejobs.com) | RSS feed | None |
| [AI Jobs](https://aijobs.net) | Public JSON API | None |
| [Himalayas](https://himalayas.app) | Public JSON API | None |
| [Y Combinator](https://www.workatastartup.com) | Public JSON API | None |
| Per-company Greenhouse / Ashby / Workable boards | Per-board APIs | None |

## Output

`remote_jobs.xlsx` — single sheet **"Remote Jobs"** with columns:

| Column | Description |
|---|---|
| Date Posted | Date the job was published (UTC) |
| Title | Job title |
| Company | Hiring company |
| Location | Remote scope / timezone requirement |
| Job Type | full-time, part-time, contract... |
| Category | Industry / function |
| Tags | Skill tags |
| Salary | Salary range if disclosed |
| Source | Portal name |
| URL | Link to the job listing |
| Date Added | Date this row was written to the file |

## Deduplication

Each run loads the existing Excel, hashes every URL already present, and only appends rows whose URL is new. Jobs are inserted at the top (newest first).

## Automation

GitHub Actions workflow (`.github/workflows/daily_scrape.yml`) runs at **07:00 UTC** every day:

1. Checks out the repo
2. Installs Python dependencies
3. Runs `python main.py`
4. Commits and pushes `remote_jobs.xlsx` if any new rows were added

You can also trigger it manually from the **Actions** tab -> **Daily Remote Jobs Scrape** -> **Run workflow**.

## Local Usage

```bash
pip install -r requirements.txt
python main.py
```

The script exits with code `0` on success. Check `remote_jobs.xlsx` for results.

---

## Auto-Applier Pipeline

The `applier/` package extends the daily scrape with an end-to-end application
pipeline:

1. Read newly-scraped jobs from `remote_jobs.xlsx`.
2. Fetch each job's full description (portal-aware: Greenhouse, Lever, Ashby,
   Workable, RemoteOK + a generic fallback).
3. Use Claude (`anthropic` SDK) to tailor `resume/base_resume.md` to the JD and
   draft a cover letter + match-summary.
4. Save artifacts under `applications/<slug>/` where the slug is
   `<date>-<company>-<title>-<hash>` — committed back to GitHub.
5. For supported portals (currently Greenhouse public Job Board API), submit
   the application when `APPLIER_AUTO_SUBMIT=1`. Otherwise opens a tracking
   GitHub Issue with the artifacts and apply URL for manual submission.
6. Track per-job state in `applications/_state.json` so re-runs are idempotent.

### Setup

- Replace `resume/base_resume.md` and `resume/profile.yml` with your real
  data. The base resume is used **verbatim** as ground truth — Claude is
  instructed never to invent experience.
- Create the following GitHub Actions secrets/vars:

  | Name | Type | Required | Purpose |
  |---|---|---|---|
  | `ANTHROPIC_API_KEY` | secret | yes | Claude API key |
  | `APPLIER_AUTO_SUBMIT` | var | no | `"1"` to actually submit (default dry-run) |
  | `APPLIER_MODEL` | var | no | override Claude model |
  | `APPLIER_FIRST_NAME`, `APPLIER_LAST_NAME`, `APPLIER_EMAIL`, `APPLIER_PHONE`, `APPLIER_LINKEDIN`, `APPLIER_GITHUB_URL`, `APPLIER_PORTFOLIO` | secrets | only when auto-submitting | candidate contact fields |

### Cron

`.github/workflows/daily_apply.yml` runs at **07:30 UTC** (30 minutes after
the scraper). It tailors any new jobs, renders `resume.md` to PDF via pandoc,
opens tracking issues for tailored applications, and commits the
`applications/` directory.

### Local Usage

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python -m applier.main --max 10
```

Use `--retry-errors` to re-process records currently in `error` state.
