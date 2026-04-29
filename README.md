# Resume_Scraper

## Local collector flow

1. Start the collector with the helper script:
```bash
./start.sh
```

Optional custom host/port:
```bash
./start.sh 127.0.0.1 8766
```

2. Or activate the virtualenv manually:
```bash
source .venv/bin/activate
```

3. Start the local collector directly:
```bash
python3 Scraper.py serve
```

4. In Tampermonkey, use [`indeed_job_saver.user.js`](/home/keerthi/Dev/scripts/Resume_Scraper/indeed_job_saver.user.js).
5. Open the local dashboard at `http://127.0.0.1:8765/` to browse all saved jobs.

Saved jobs are written to:

- [`job_data/`](/home/keerthi/Dev/scripts/Resume_Scraper/job_data)
- Daily file format: `job_data/jobs_YYYY-MM-DD.csv`
- If a duplicate is detected, the userscript now asks whether you want to save a second entry.
- The dashboard shows all saved jobs, duplicate entries, email-apply jobs, search filters, and full job details.
- API responses from `/api/jobs` now include `contact_emails`, `email_apply_required`, and `application_channel` so `n8n` can branch email-based applications automatically.
