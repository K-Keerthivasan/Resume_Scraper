"""
Indeed job collector
====================

Run the local collector for the Tampermonkey userscript and dashboard UI.
Saved jobs are written into `job_data/jobs_YYYY-MM-DD.csv`.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


BASE_DIR = Path(__file__).resolve().parent
JOB_DATA_DIR = BASE_DIR / "job_data"
INDEX_FILE = JOB_DATA_DIR / "job_index.json"
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)

CSV_FIELDS = [
    "job_title",
    "company",
    "location",
    "job_type",
    "salary",
    "posted_date",
    "description_summary",
    "key_skills",
    "contact_emails",
    "email_apply_required",
    "application_channel",
    "apply_url",
    "source_url",
    "scraped_at",
    "status",
]

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resume Scraper Dashboard</title>
  <style>
    :root {
      --bg: #08111f;
      --bg-deep: #040913;
      --panel: rgba(13, 21, 36, 0.82);
      --panel-strong: rgba(18, 28, 47, 0.96);
      --panel-soft: rgba(9, 16, 30, 0.7);
      --ink: #eef4ff;
      --muted: #8fa3c7;
      --line: rgba(141, 175, 230, 0.14);
      --accent: #45d0ff;
      --accent-strong: #20b8f0;
      --accent-soft: rgba(69, 208, 255, 0.12);
      --warm: #ff8b5e;
      --success: #3fe0ae;
      --duplicate: #ff6f8d;
      --shadow: 0 28px 80px rgba(0, 0, 0, 0.38);
      --radius: 24px;
      --font-ui: "Avenir Next", "Segoe UI", sans-serif;
      --font-display: "Iowan Old Style", "Georgia", serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: var(--font-ui);
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 12%, rgba(69, 208, 255, 0.14), transparent 22%),
        radial-gradient(circle at 88% 10%, rgba(255, 111, 141, 0.12), transparent 20%),
        radial-gradient(circle at 50% 100%, rgba(32, 184, 240, 0.09), transparent 26%),
        linear-gradient(180deg, #0b1425 0%, var(--bg) 46%, var(--bg-deep) 100%);
      min-height: 100vh;
      position: relative;
      overflow-x: hidden;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
      background-size: 34px 34px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.7), transparent 88%);
      pointer-events: none;
    }

    .shell {
      max-width: 1500px;
      margin: 0 auto;
      padding: 28px;
      position: relative;
      z-index: 1;
    }

    .hero {
      display: grid;
      grid-template-columns: 1.25fr 0.75fr;
      gap: 18px;
      margin-bottom: 18px;
    }

    .card {
      background: var(--panel);
      backdrop-filter: blur(12px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
    }

    .card:hover {
      border-color: rgba(69, 208, 255, 0.22);
    }

    .hero-main {
      padding: 30px;
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(69, 208, 255, 0.08), transparent 42%),
        linear-gradient(180deg, rgba(255,255,255,0.02), transparent 65%);
    }

    .hero-main::after {
      content: "";
      position: absolute;
      inset: auto -30px -30px auto;
      width: 260px;
      height: 260px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(69, 208, 255, 0.22), transparent 65%);
      pointer-events: none;
      filter: blur(8px);
    }

    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 11px;
      color: var(--warm);
      margin-bottom: 10px;
      font-weight: 700;
    }

    h1 {
      font-family: var(--font-display);
      font-size: clamp(34px, 5vw, 58px);
      line-height: 0.95;
      margin: 0 0 12px;
      font-weight: 700;
      text-shadow: 0 0 28px rgba(69, 208, 255, 0.08);
    }

    .hero-copy {
      max-width: 56ch;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.5;
      margin: 0;
    }

    .hero-side {
      padding: 18px;
      display: grid;
      gap: 12px;
      align-content: start;
    }

    .stat {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.03), transparent),
        var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      position: relative;
      overflow: hidden;
      transform: translateY(0);
      transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    }

    .stat::after {
      content: "";
      position: absolute;
      inset: auto -26px -26px auto;
      width: 96px;
      height: 96px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(69, 208, 255, 0.16), transparent 68%);
    }

    .stat:hover {
      transform: translateY(-3px);
      border-color: rgba(69, 208, 255, 0.22);
      box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
    }

    .stat-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.10em;
      margin-bottom: 6px;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 700;
      position: relative;
      z-index: 1;
    }

    .toolbar {
      display: grid;
      grid-template-columns: 1.3fr 0.8fr 0.8fr 0.8fr auto auto;
      gap: 12px;
      padding: 18px;
      margin-bottom: 18px;
      align-items: center;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.02), transparent),
        var(--panel-soft);
    }

    .field, .button, select {
      font: inherit;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(7, 15, 28, 0.88);
      color: var(--ink);
      padding: 12px 14px;
      transition: border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease, background 150ms ease;
    }

    .field:focus, select:focus {
      outline: 2px solid rgba(69, 208, 255, 0.12);
      border-color: var(--accent-strong);
      box-shadow: 0 0 0 5px rgba(69, 208, 255, 0.08);
    }

    .button {
      cursor: pointer;
      background: linear-gradient(135deg, var(--accent-strong), var(--accent));
      color: #03111b;
      font-weight: 600;
      box-shadow: 0 10px 24px rgba(32, 184, 240, 0.22);
    }

    .button.secondary {
      background: rgba(14, 23, 39, 0.92);
      color: var(--ink);
      box-shadow: none;
    }

    .button:hover {
      transform: translateY(-2px);
      border-color: rgba(69, 208, 255, 0.24);
    }

    .button:active {
      transform: translateY(0);
    }

    .layout {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 18px;
      min-height: 62vh;
    }

    .table-wrap {
      overflow: hidden;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.02), transparent),
        var(--panel-soft);
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th, td {
      padding: 14px 16px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid var(--line);
    }

    th {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      background: rgba(5, 10, 20, 0.96);
      position: sticky;
      top: 0;
      z-index: 1;
    }

    tbody tr {
      cursor: pointer;
      transition: background 140ms ease, transform 140ms ease, box-shadow 140ms ease;
    }

    tbody tr:hover,
    tbody tr.active {
      background: var(--accent-soft);
      transform: translateX(4px);
      box-shadow: inset 3px 0 0 var(--accent);
    }

    .role {
      font-weight: 700;
      margin-bottom: 4px;
    }

    .company {
      color: var(--muted);
      font-size: 13px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--line);
      white-space: nowrap;
    }

    .pill.duplicate {
      color: var(--duplicate);
      border-color: rgba(255, 111, 141, 0.22);
      background: rgba(255, 111, 141, 0.12);
    }

    .details {
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 18px;
      background:
        linear-gradient(180deg, rgba(69, 208, 255, 0.06), transparent 20%),
        var(--panel-soft);
    }

    .details h2 {
      margin: 0;
      font-size: 28px;
      line-height: 1.05;
      font-family: var(--font-display);
    }

    .details-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }

    .meta {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.03), transparent),
        var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      transition: transform 140ms ease, border-color 140ms ease;
    }

    .meta:hover {
      transform: translateY(-2px);
      border-color: rgba(69, 208, 255, 0.2);
    }

    .meta-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 8px;
    }

    .meta-value {
      font-size: 14px;
      line-height: 1.45;
      word-break: break-word;
    }

    .summary-box {
      background: rgba(9, 17, 31, 0.92);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      line-height: 1.6;
      white-space: pre-wrap;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .empty {
      padding: 38px 18px;
      text-align: center;
      color: var(--muted);
    }

    .footer-note {
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }

    @media (max-width: 1080px) {
      .hero, .layout { grid-template-columns: 1fr; }
      .toolbar { grid-template-columns: 1fr 1fr 1fr; }
    }

    @media (max-width: 720px) {
      .shell { padding: 16px; }
      .toolbar { grid-template-columns: 1fr; }
      .details-grid { grid-template-columns: 1fr; }
      th:nth-child(3), td:nth-child(3),
      th:nth-child(4), td:nth-child(4) { display: none; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="card hero-main">
        <div class="eyebrow">Local Collector</div>
        <h1>Resume Scraper Dashboard</h1>
        <p class="hero-copy">
          Browse saved Indeed jobs, spot duplicates, and inspect every field
          collected by the userscript without leaving the local app.
        </p>
      </div>
      <div class="card hero-side">
        <div class="stat">
          <div class="stat-label">Total jobs</div>
          <div class="stat-value" id="stat-total">0</div>
        </div>
        <div class="stat">
          <div class="stat-label">Saved today</div>
          <div class="stat-value" id="stat-today">0</div>
        </div>
        <div class="stat">
          <div class="stat-label">Duplicate entries</div>
          <div class="stat-value" id="stat-duplicates">0</div>
        </div>
        <div class="stat">
          <div class="stat-label">Email apply jobs</div>
          <div class="stat-value" id="stat-email">0</div>
        </div>
      </div>
    </section>

    <section class="card toolbar">
      <input id="search" class="field" type="search" placeholder="Search title, company, location, skills">
      <select id="statusFilter">
        <option value="">All statuses</option>
      </select>
      <select id="channelFilter">
        <option value="">All channels</option>
        <option value="platform">Platform apply</option>
        <option value="email">Email apply</option>
      </select>
      <select id="duplicateFilter">
        <option value="">All entries</option>
        <option value="unique">Unique only</option>
        <option value="duplicate">Duplicates only</option>
      </select>
      <button id="refreshBtn" class="button secondary" type="button">Refresh</button>
      <button id="exportBtn" class="button" type="button">Export JSON</button>
    </section>

    <section class="layout">
      <div class="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Role</th>
              <th>Status</th>
              <th>Saved</th>
              <th>Signals</th>
            </tr>
          </thead>
          <tbody id="jobsBody">
            <tr><td colspan="4" class="empty">Loading jobs...</td></tr>
          </tbody>
        </table>
      </div>

      <aside class="card details" id="detailsPane">
        <div class="empty">Select a job to inspect the full entry.</div>
      </aside>
    </section>

    <div class="footer-note" id="footerNote"></div>
  </div>

  <script>
    const state = {
      jobs: [],
      filtered: [],
      selectedId: null,
      showSkills: true,
    };

    function esc(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function fmt(value) {
      return value && String(value).trim() ? String(value) : "N/A";
    }

    function badge(text, cls = "") {
      return `<span class="pill ${cls}">${esc(text)}</span>`;
    }

    function filterJobs() {
      const query = document.getElementById("search").value.trim().toLowerCase();
      const status = document.getElementById("statusFilter").value;
      const channel = document.getElementById("channelFilter").value;
      const duplicateFilter = document.getElementById("duplicateFilter").value;

      state.filtered = state.jobs.filter((job) => {
        if (status && job.status !== status) return false;
        if (channel && job.application_channel !== channel) return false;
        if (duplicateFilter === "unique" && job.is_duplicate) return false;
        if (duplicateFilter === "duplicate" && !job.is_duplicate) return false;

        if (!query) return true;
        return [
          job.job_title,
          job.company,
          job.location,
          job.key_skills,
          job.contact_emails,
          job.application_channel,
          job.description_summary,
          job.salary,
          job.job_type,
        ].join(" ").toLowerCase().includes(query);
      });

      renderTable();
      syncSelectedRow();
      renderFooter();
    }

    function renderSummary(summary) {
      document.getElementById("stat-total").textContent = summary.total_jobs;
      document.getElementById("stat-today").textContent = summary.saved_today;
      document.getElementById("stat-duplicates").textContent = summary.duplicate_entries;
      document.getElementById("stat-email").textContent = summary.email_apply_jobs;
    }

    function renderStatusFilter(jobs) {
      const select = document.getElementById("statusFilter");
      const current = select.value;
      const statuses = [...new Set(jobs.map((job) => job.status).filter(Boolean))].sort();
      select.innerHTML = '<option value="">All statuses</option>' +
        statuses.map((status) => `<option value="${esc(status)}">${esc(status)}</option>`).join("");
      select.value = statuses.includes(current) ? current : "";
    }

    function renderTable() {
      const tbody = document.getElementById("jobsBody");
      if (!state.filtered.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty">No jobs match the current filters.</td></tr>';
        return;
      }

      tbody.innerHTML = state.filtered.map((job) => `
        <tr data-id="${esc(job.row_id)}" class="${job.row_id === state.selectedId ? "active" : ""}">
          <td>
            <div class="role">${esc(job.job_title)}</div>
            <div class="company">${esc(job.company)} • ${esc(job.location)}</div>
          </td>
          <td>${badge(job.status || "saved")}</td>
          <td>${esc(job.scraped_at)}</td>
          <td>
            ${job.is_duplicate ? badge("Duplicate", "duplicate") : badge("Unique")}
            ${job.application_channel === "email" ? badge("Email apply") : badge("Platform")}
            ${job.contact_emails && job.contact_emails !== "N/A" ? badge("Has email") : ""}
            ${job.salary && job.salary !== "N/A" ? badge(job.salary) : ""}
            ${job.job_type && job.job_type !== "N/A" ? badge(job.job_type) : ""}
          </td>
        </tr>
      `).join("");

      tbody.querySelectorAll("tr[data-id]").forEach((row) => {
        row.addEventListener("click", () => {
          state.selectedId = row.dataset.id;
          syncSelectedRow();
          renderDetails();
        });
      });
    }

    function syncSelectedRow() {
      const currentVisible = state.filtered.some((job) => job.row_id === state.selectedId);
      if (!currentVisible) {
        state.selectedId = state.filtered[0]?.row_id || null;
      }
      tbodyState();
      renderDetails();
    }

    function tbodyState() {
      document.querySelectorAll("#jobsBody tr[data-id]").forEach((row) => {
        row.classList.toggle("active", row.dataset.id === state.selectedId);
      });
    }

    function renderDetails() {
      const pane = document.getElementById("detailsPane");
      const job = state.filtered.find((item) => item.row_id === state.selectedId);
      if (!job) {
        pane.innerHTML = '<div class="empty">Select a job to inspect the full entry.</div>';
        return;
      }

      const duplicateText = job.is_duplicate
        ? `Yes • ${job.duplicate_count} entries share this job key`
        : "No";
      const signalBadges = [
        job.is_duplicate ? badge("Duplicate", "duplicate") : badge("Unique"),
        badge(job.application_channel === "email" ? "Email apply" : "Platform apply"),
        job.contact_emails && job.contact_emails !== "N/A" ? badge("Has contact email") : "",
        job.salary && job.salary !== "N/A" ? badge(job.salary) : "",
        job.job_type && job.job_type !== "N/A" ? badge(job.job_type) : "",
      ].filter(Boolean).join("");

      pane.innerHTML = `
        <div>
          <div class="eyebrow">Job Details</div>
          <h2>${esc(job.job_title)}</h2>
          <p class="hero-copy">${esc(job.company)} • ${esc(job.location)}</p>
          <div class="actions" style="margin-top:14px;">${signalBadges}</div>
        </div>

        <div class="actions">
          ${job.apply_url ? `<a class="button" href="${esc(job.apply_url)}" target="_blank" rel="noreferrer">Open Apply URL</a>` : ""}
          ${job.source_url ? `<a class="button secondary" href="${esc(job.source_url)}" target="_blank" rel="noreferrer">Open Source URL</a>` : ""}
        </div>

        <div class="details-grid">
          <div class="meta"><div class="meta-label">Status</div><div class="meta-value">${esc(fmt(job.status))}</div></div>
          <div class="meta"><div class="meta-label">Saved Date</div><div class="meta-value">${esc(fmt(job.scraped_at))}</div></div>
          <div class="meta"><div class="meta-label">Job Type</div><div class="meta-value">${esc(fmt(job.job_type))}</div></div>
          <div class="meta"><div class="meta-label">Salary</div><div class="meta-value">${esc(fmt(job.salary))}</div></div>
          <div class="meta"><div class="meta-label">Posted Date</div><div class="meta-value">${esc(fmt(job.posted_date))}</div></div>
          <div class="meta"><div class="meta-label">Duplicate</div><div class="meta-value">${esc(duplicateText)}</div></div>
          <div class="meta"><div class="meta-label">Apply Channel</div><div class="meta-value">${esc(fmt(job.application_channel))}</div></div>
          <div class="meta"><div class="meta-label">Contact Emails</div><div class="meta-value">${esc(fmt(job.contact_emails))}</div></div>
          <div class="meta"><div class="meta-label">Source File</div><div class="meta-value">${esc(fmt(job.file))}</div></div>
          <div class="meta"><div class="meta-label">Job Key</div><div class="meta-value">${esc(fmt(job.job_key))}</div></div>
        </div>

        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
            <div class="meta-label">Key Skills</div>
            <button id="toggleSkillsBtn" class="button secondary" type="button">${state.showSkills ? "Hide skills" : "Show skills"}</button>
          </div>
          <div class="summary-box" style="display:${state.showSkills ? "block" : "none"};">${esc(fmt(job.key_skills))}</div>
        </div>

        <div>
          <div class="meta-label">Description Summary</div>
          <div class="summary-box">${esc(fmt(job.description_summary))}</div>
        </div>
      `;

      document.getElementById("toggleSkillsBtn")?.addEventListener("click", () => {
        state.showSkills = !state.showSkills;
        renderDetails();
      });
    }

    function renderFooter() {
      const note = document.getElementById("footerNote");
      const total = state.jobs.length;
      const shown = state.filtered.length;
      const selected = state.filtered.find((job) => job.row_id === state.selectedId);
      note.textContent = selected
        ? `${shown} of ${total} jobs visible • focused on ${selected.company} / ${selected.job_title}`
        : `${shown} of ${total} jobs visible`;
    }

    async function loadJobs() {
      const response = await fetch("/api/jobs");
      const payload = await response.json();
      state.jobs = payload.jobs || [];
      renderSummary(payload.summary || { total_jobs: 0, saved_today: 0, duplicate_entries: 0 });
      renderStatusFilter(state.jobs);
      filterJobs();
    }

    function exportJson() {
      const blob = new Blob([JSON.stringify(state.filtered, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "resume_scraper_jobs.json";
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 300);
    }

    document.getElementById("search").addEventListener("input", filterJobs);
    document.getElementById("statusFilter").addEventListener("change", filterJobs);
    document.getElementById("channelFilter").addEventListener("change", filterJobs);
    document.getElementById("duplicateFilter").addEventListener("change", filterJobs);
    document.getElementById("refreshBtn").addEventListener("click", loadJobs);
    document.getElementById("exportBtn").addEventListener("click", exportJson);

    loadJobs().catch((error) => {
      document.getElementById("jobsBody").innerHTML =
        `<tr><td colspan="4" class="empty">Failed to load jobs: ${esc(error.message)}</td></tr>`;
    });
  </script>
</body>
</html>
"""


def ensure_storage() -> None:
    JOB_DATA_DIR.mkdir(parents=True, exist_ok=True)


def today_iso() -> str:
    return date.today().isoformat()


def daily_csv_path(day: str | None = None) -> Path:
    stamp = day or today_iso()
    return JOB_DATA_DIR / f"jobs_{stamp}.csv"


def normalize_text(value: str) -> str:
    lowered = (value or "").strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def clean_indeed_url(url: str) -> str:
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query)

    keep_keys = {"jk", "vjs", "from"}
    filtered = {key: value for key, value in query.items() if key in keep_keys}

    cleaned = parsed._replace(
        params="",
        fragment="",
        query=urlencode(filtered, doseq=True),
    )
    return urlunparse(cleaned)


def extract_emails_from_text(text: str) -> list[str]:
    seen: list[str] = []
    for match in EMAIL_PATTERN.findall(text or ""):
        email = match.strip().lower().rstrip(".,;:")
        if email and email not in seen:
            seen.append(email)
    return seen


def normalize_email_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = re.split(r"[|,\n\r;]+", str(value or ""))

    emails: list[str] = []
    for item in raw_values:
        for email in extract_emails_from_text(str(item)):
            if email not in emails:
                emails.append(email)
    return emails


def infer_application_channel(job: dict[str, Any], emails: list[str]) -> tuple[str, str]:
    apply_url = str(job.get("apply_url", "")).strip().lower()
    description = str(job.get("description_summary", "")).strip().lower()
    source_url = str(job.get("source_url", "")).strip().lower()
    combined = " ".join([apply_url, source_url, description])

    email_apply_required = bool(emails)
    if not email_apply_required:
        email_apply_required = any(
            phrase in combined
            for phrase in (
                "send your resume",
                "send resume",
                "send cv",
                "email your resume",
                "apply by email",
                "submit your resume to",
                "forward your resume to",
            )
        )

    channel = "email" if (email_apply_required or apply_url.startswith("mailto:")) else "platform"
    return ("yes" if email_apply_required else "no", channel)


def extract_indeed_job_id(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    query = parse_qs(parsed.query)
    for key in ("jk", "vjk"):
        values = query.get(key)
        if values and values[0].strip():
            return values[0].strip()
    return ""


def is_meaningful_job_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    path = parsed.path.strip("/")
    if not path:
        return False
    return any(token in path.lower() for token in ("viewjob", "job", "clk", "pagead"))


def compute_job_key(job: dict[str, Any]) -> str:
    source_url = str(job.get("source_url", "")).strip()
    apply_url = str(job.get("apply_url", "")).strip()

    for candidate in (source_url, apply_url):
        indeed_id = extract_indeed_job_id(candidate)
        if indeed_id:
            return f"jk:{indeed_id}"

    if source_url and is_meaningful_job_url(source_url):
        return f"url:{clean_indeed_url(source_url)}"

    if apply_url and not apply_url.lower().startswith("mailto:") and is_meaningful_job_url(apply_url):
        return f"url:{clean_indeed_url(apply_url)}"

    title = normalize_text(str(job.get("job_title", "")))
    company = normalize_text(str(job.get("company", "")))
    location = normalize_text(str(job.get("location", "")))
    return f"fingerprint:{title}|{company}|{location}"


def normalize_job_payload(job: dict[str, Any]) -> dict[str, str]:
    emails = normalize_email_list(job.get("contact_emails", ""))
    apply_url = str(job.get("apply_url", "")).strip()
    source_url = str(job.get("source_url", "")).strip()
    if apply_url.lower().startswith("mailto:"):
        emails_from_url = extract_emails_from_text(apply_url)
        for email in emails_from_url:
            if email not in emails:
                emails.append(email)

    email_apply_required, application_channel = infer_application_channel(job, emails)
    normalized = {field: "" for field in CSV_FIELDS}
    normalized.update(
        {
            "job_title": str(job.get("job_title", "Unknown Title")).strip(),
            "company": str(job.get("company", "Unknown Company")).strip(),
            "location": str(job.get("location", "Unknown Location")).strip(),
            "job_type": str(job.get("job_type", "N/A")).strip(),
            "salary": str(job.get("salary", "N/A")).strip(),
            "posted_date": str(job.get("posted_date", "N/A")).strip(),
            "description_summary": str(job.get("description_summary", "N/A")).strip(),
            "key_skills": str(job.get("key_skills", "N/A")).strip(),
            "contact_emails": " | ".join(emails) if emails else "N/A",
            "email_apply_required": str(
                job.get("email_apply_required", email_apply_required)
            ).strip().lower()
            or email_apply_required,
            "application_channel": str(
                job.get("application_channel", application_channel)
            ).strip().lower()
            or application_channel,
            "apply_url": apply_url,
            "source_url": clean_indeed_url(source_url) if source_url else "",
            "scraped_at": str(job.get("scraped_at", today_iso())).strip() or today_iso(),
            "status": str(job.get("status", "saved")).strip() or "saved",
        }
    )
    return normalized


def save_job_index(index: dict[str, dict[str, str]]) -> None:
    ensure_storage()
    INDEX_FILE.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")


def rebuild_job_index() -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for path in list_csv_files():
        ensure_csv_schema(path)
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = normalize_job_payload(row)
                key = compute_job_key(normalized)
                if key in index:
                    continue
                index[key] = {
                    "file": str(path.relative_to(BASE_DIR)),
                    "job_title": normalized["job_title"],
                    "company": normalized["company"],
                    "location": normalized["location"],
                    "source_url": normalized["source_url"],
                    "scraped_at": normalized["scraped_at"],
                }
    save_job_index(index)
    return index


def load_job_index() -> dict[str, dict[str, str]]:
    ensure_storage()
    return rebuild_job_index()


def ensure_csv_schema(path: Path) -> None:
    if not path.exists():
        return

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        existing_fields = reader.fieldnames or []
        rows = list(reader)

    if existing_fields == CSV_FIELDS:
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(normalize_job_payload(row))


def append_job_to_csv(job: dict[str, str], path: Path) -> None:
    ensure_storage()
    ensure_csv_schema(path)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({field: job.get(field, "") for field in CSV_FIELDS})


def store_job(job: dict[str, Any], allow_duplicate: bool = False) -> dict[str, Any]:
    normalized = normalize_job_payload(job)
    key = compute_job_key(normalized)
    index = load_job_index()
    existing = index.get(key)

    if existing and not allow_duplicate:
        return {
            "stored": False,
            "duplicate": True,
            "job_key": key,
            "existing_file": existing["file"],
            "existing": existing,
            "message": "Duplicate job detected",
        }

    target_file = daily_csv_path(normalized["scraped_at"])
    append_job_to_csv(normalized, target_file)

    if not existing:
        index[key] = {
            "file": str(target_file.relative_to(BASE_DIR)),
            "job_title": normalized["job_title"],
            "company": normalized["company"],
            "location": normalized["location"],
            "source_url": normalized["source_url"],
            "scraped_at": normalized["scraped_at"],
        }
        save_job_index(index)

    return {
        "stored": True,
        "duplicate": bool(existing),
        "job_key": key,
        "file": str(target_file.relative_to(BASE_DIR)),
        "message": "Duplicate job saved as a second entry" if existing else "Job saved",
    }


def get_today_summary() -> dict[str, Any]:
    ensure_storage()
    path = daily_csv_path()
    if not path.exists():
        return {"file": str(path.relative_to(BASE_DIR)), "saved_today": 0}

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        count = sum(1 for _ in reader)

    return {"file": str(path.relative_to(BASE_DIR)), "saved_today": count}


def list_csv_files() -> list[Path]:
    ensure_storage()
    return sorted(JOB_DATA_DIR.glob("jobs_*.csv"))


def load_all_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    key_counts: dict[str, int] = {}

    for path in list_csv_files():
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                normalized = normalize_job_payload(row)
                job_key = compute_job_key(normalized)
                key_counts[job_key] = key_counts.get(job_key, 0) + 1
                jobs.append(
                    {
                        **normalized,
                        "job_key": job_key,
                        "row_id": f"{path.name}:{row_number}",
                        "file": str(path.relative_to(BASE_DIR)),
                    }
                )

    for job in jobs:
        duplicate_count = key_counts.get(job["job_key"], 0)
        job["duplicate_count"] = duplicate_count
        job["is_duplicate"] = duplicate_count > 1

    jobs.sort(key=lambda item: (item.get("scraped_at", ""), item.get("row_id", "")), reverse=True)
    return jobs


def build_dashboard_payload() -> dict[str, Any]:
    jobs = load_all_jobs()
    summary = get_today_summary()
    return {
        "jobs": jobs,
        "summary": {
            "file": summary["file"],
            "saved_today": summary["saved_today"],
            "total_jobs": len(jobs),
            "duplicate_entries": sum(1 for job in jobs if job["is_duplicate"]),
            "email_apply_jobs": sum(1 for job in jobs if job["application_channel"] == "email"),
        },
    }


class JobRequestHandler(BaseHTTPRequestHandler):
    server_version = "IndeedJobCollector/1.0"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_html(200, DASHBOARD_HTML)
            return

        if parsed.path == "/health":
            self._send_json(200, {"ok": True, "summary": get_today_summary()})
            return

        if parsed.path == "/api/jobs":
            self._send_json(200, {"ok": True, **build_dashboard_payload()})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/api/jobs":
            self._send_json(404, {"ok": False, "error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "Invalid JSON payload"})
            return

        jobs = payload if isinstance(payload, list) else [payload]
        results = []
        stored = 0
        duplicates = 0

        for job in jobs:
            if not isinstance(job, dict):
                continue
            allow_duplicate = bool(job.pop("allow_duplicate", False))
            result = store_job(job, allow_duplicate=allow_duplicate)
            results.append(result)
            if result["stored"]:
                stored += 1
            if result["duplicate"]:
                duplicates += 1

        self._send_json(
            200,
            {
                "ok": True,
                "stored": stored,
                "duplicates": duplicates,
                "results": results,
                "summary": build_dashboard_payload()["summary"],
            },
        )


def serve_mode(host: str = "127.0.0.1", port: int = 8765) -> int:
    ensure_storage()
    server = ThreadingHTTPServer((host, port), JobRequestHandler)
    print("=" * 60)
    print("Indeed Job Collector")
    print(f"Listening on http://{host}:{port}")
    print(f"Dashboard: http://{host}:{port}/")
    print(f"Writing files to {JOB_DATA_DIR}")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    if args and args[0] == "serve":
        host = "127.0.0.1"
        port = 8765
        if len(args) >= 2:
            host = args[1]
        if len(args) >= 3:
            try:
                port = int(args[2])
            except ValueError:
                print(f"Invalid port: {args[2]}")
                return 1
        return serve_mode(host=host, port=port)

    print("Usage: python3 Scraper.py serve [host] [port]")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
