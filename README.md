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
