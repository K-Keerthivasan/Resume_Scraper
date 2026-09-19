# Resume_Scraper

## Local collector flow

### Windows PowerShell

1. Set up the Windows virtual environment:
```powershell
.\setup_windows.ps1
```

If `python` is not on PATH but the Python launcher is installed:
```powershell
.\setup_windows.ps1 -PythonCommand py
```

2. Start the collector:
```powershell
.\start_windows.ps1
```

Optional custom host/port:
```powershell
.\start_windows.ps1 -HostName 127.0.0.1 -Port 8766
```

If PowerShell blocks local scripts, run this once from the project folder:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Ubuntu/Linux/macOS

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

On Windows, the direct command is:
```powershell
python Scraper.py serve
```

4. In Tampermonkey, use the script for the job board you are saving from:
   - [`tamper_monkey/indeed_job_saver.user.js`](tamper_monkey/indeed_job_saver.user.js) for Indeed.
   - [`tamper_monkey/linkedin_careerbeacon_job_saver.user.js`](tamper_monkey/linkedin_careerbeacon_job_saver.user.js) for LinkedIn and CareerBeacon.
   - [`tamper_monkey/londontechjobs_job_saver.user.js`](tamper_monkey/londontechjobs_job_saver.user.js) for London Tech Jobs.
   - [`tamper_monkey/universal_canada_job_saver.user.js`](tamper_monkey/universal_canada_job_saver.user.js) for everything else: Job Bank, federal/provincial portals, major Canadian cities, ATS platforms (Workday, Greenhouse, Lever, iCIMS, Taleo, SuccessFactors, BambooHR, Workable, SmartRecruiters, Recruitee, Bullhorn, Avature, Zoho Recruit, Dayforce, UltiPro, ADP), and Canadian aggregators (Jobillico, Eluta, Talent.com / Neuvoo, Monster.ca, Jobboom, SimplyHired). Reads schema.org JobPosting JSON-LD first, then microdata, then DOM heuristics. Indeed/LinkedIn/CareerBeacon/LondonTechJobs are excluded so their dedicated scrapers handle them.
5. Open the local dashboard at `http://127.0.0.1:8765/` to browse all saved jobs.

Saved jobs are written to:

- `job_data/`
- Daily file format: `job_data/jobs_YYYY-MM-DD.csv`
- If a duplicate is detected, the userscript now asks whether you want to save a second entry.
- The dashboard shows all saved jobs, duplicate entries, email-apply jobs, search filters, and full job details.
- API responses from `/api/jobs` now include `contact_emails`, `email_apply_required`, and `application_channel` so `n8n` can branch email-based applications automatically.
