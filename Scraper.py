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
      grid-template-columns: 1.1fr 0.7fr 0.7fr 0.7fr 0.7fr 0.7fr auto auto auto;
      gap: 12px;
      padding: 18px;
      margin-bottom: 18px;
      align-items: center;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.02), transparent),
        var(--panel-soft);
    }

    .button.copied {
      background: linear-gradient(135deg, var(--success), #2bb389);
      color: #04221a;
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
      display: block;
      min-height: 62vh;
    }

    .table-wrap {
      overflow: hidden;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.02), transparent),
        var(--panel-soft);
    }

    .drawer-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(3, 8, 18, 0.55);
      backdrop-filter: blur(6px);
      z-index: 40;
      opacity: 0;
      pointer-events: none;
      transition: opacity 200ms ease;
    }

    .drawer-backdrop.open {
      opacity: 1;
      pointer-events: auto;
    }

    .drawer {
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: min(560px, 100vw);
      background:
        linear-gradient(180deg, rgba(69, 208, 255, 0.06), transparent 18%),
        linear-gradient(180deg, rgba(13, 21, 36, 0.98), rgba(8, 13, 23, 0.99));
      border-left: 1px solid var(--line);
      box-shadow: -32px 0 60px rgba(0, 0, 0, 0.45);
      transform: translateX(100%);
      transition: transform 220ms ease;
      z-index: 41;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .drawer.open {
      transform: translateX(0);
    }

    .drawer-header {
      padding: 18px 22px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid var(--line);
      background: rgba(7, 13, 24, 0.6);
    }

    .drawer-header .eyebrow {
      margin: 0;
    }

    .drawer-close {
      width: 36px;
      height: 36px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.04);
      color: var(--ink);
      cursor: pointer;
      font-size: 20px;
      line-height: 1;
      transition: background 140ms ease, border-color 140ms ease, transform 140ms ease;
    }

    .drawer-close:hover {
      background: rgba(255, 255, 255, 0.08);
      border-color: rgba(69, 208, 255, 0.32);
      transform: scale(1.04);
    }

    .drawer-body {
      padding: 22px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 18px;
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

    th.sortable {
      cursor: pointer;
      user-select: none;
    }

    th.sortable:hover {
      color: var(--ink);
    }

    .sort-indicator {
      margin-left: 6px;
      opacity: 0.6;
      font-size: 11px;
    }

    th.sortable.active .sort-indicator {
      opacity: 1;
      color: var(--accent);
    }

    th.col-check, td.col-check {
      width: 36px;
      padding-right: 0;
    }

    .row-check {
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
      cursor: pointer;
    }

    .status-select {
      font: inherit;
      font-size: 12px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.04);
      color: var(--ink);
      cursor: pointer;
    }

    .status-select:focus {
      outline: 2px solid rgba(69, 208, 255, 0.18);
      border-color: var(--accent-strong);
    }

    .status-select.is-applied { color: var(--accent); border-color: rgba(69, 208, 255, 0.32); }
    .status-select.is-interview { color: #f5c46a; border-color: rgba(245, 196, 106, 0.34); }
    .status-select.is-offer { color: var(--success); border-color: rgba(63, 224, 174, 0.4); }
    .status-select.is-rejected { color: var(--duplicate); border-color: rgba(255, 111, 141, 0.32); }
    .status-select.is-withdrawn { color: var(--muted); border-color: var(--line); }

    .button.danger {
      background: linear-gradient(135deg, #ff5577, #ff8b5e);
      color: #1c0712;
      box-shadow: 0 10px 24px rgba(255, 85, 119, 0.22);
    }

    .button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
      transform: none;
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
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .role-open,
    .role-copy {
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 8px;
      background: rgba(69, 208, 255, 0.08);
      transition: background 140ms ease, border-color 140ms ease, transform 140ms ease, color 140ms ease;
      cursor: pointer;
      font-family: inherit;
    }

    .role-open:hover,
    .role-copy:hover {
      background: rgba(69, 208, 255, 0.18);
      border-color: rgba(69, 208, 255, 0.4);
      transform: translateY(-1px);
    }

    .role-copy.copied {
      background: rgba(63, 224, 174, 0.18);
      border-color: rgba(63, 224, 174, 0.45);
      color: var(--success);
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
      .hero { grid-template-columns: 1fr; }
      .toolbar { grid-template-columns: 1fr 1fr 1fr; }
    }

    @media (max-width: 720px) {
      .shell { padding: 16px; }
      .toolbar { grid-template-columns: 1fr; }
      .details-grid { grid-template-columns: 1fr; }
      .drawer { width: 100vw; }
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
      <select id="sourceFilter">
        <option value="">All sources</option>
      </select>
      <select id="daysFilter">
        <option value="">Any time</option>
        <option value="0">Today</option>
        <option value="1">Last 24h</option>
        <option value="3">Last 3 days</option>
        <option value="7">Last 7 days</option>
        <option value="14">Last 14 days</option>
        <option value="30">Last 30 days</option>
      </select>
      <button id="deleteBtn" class="button danger" type="button" disabled>Delete (0)</button>
      <button id="refreshBtn" class="button secondary" type="button">Refresh</button>
      <button id="exportBtn" class="button" type="button">Export JSON</button>
    </section>

    <section class="layout">
      <div class="card table-wrap">
        <table>
          <thead>
            <tr>
              <th class="col-check"><input type="checkbox" class="row-check" id="checkAll" aria-label="Select all"></th>
              <th class="sortable" data-sort-key="job_title">Role<span class="sort-indicator"></span></th>
              <th class="sortable" data-sort-key="status">Status<span class="sort-indicator"></span></th>
              <th class="sortable active" data-sort-key="scraped_at">Saved<span class="sort-indicator">↓</span></th>
              <th>Signals</th>
            </tr>
          </thead>
          <tbody id="jobsBody">
            <tr><td colspan="5" class="empty">Loading jobs...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="footer-note" id="footerNote"></div>
  </div>

  <div class="drawer-backdrop" id="drawerBackdrop"></div>
  <aside class="drawer" id="drawerPane" role="dialog" aria-hidden="true">
    <div class="drawer-header">
      <div class="eyebrow">Job Details</div>
      <button class="drawer-close" id="drawerCloseBtn" type="button" aria-label="Close details">×</button>
    </div>
    <div class="drawer-body" id="detailsPane">
      <div class="empty">Select a job to inspect the full entry.</div>
    </div>
  </aside>

  <script>
    const state = {
      jobs: [],
      filtered: [],
      selectedId: null,
      showSkills: true,
      selected: new Set(),
      sort: { key: "scraped_at", dir: "desc" },
    };

    const STATUS_OPTIONS = ["saved", "applied", "interview", "offer", "rejected", "withdrawn"];

    function statusClass(value) {
      const v = String(value || "").toLowerCase();
      if (STATUS_OPTIONS.includes(v) && v !== "saved") return `is-${v}`;
      return "";
    }

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

    function daysSince(dateStr) {
      if (!dateStr) return Infinity;
      const parsed = Date.parse(dateStr);
      if (Number.isNaN(parsed)) return Infinity;
      const now = new Date();
      const startOfToday = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
      const diffMs = startOfToday - parsed;
      return Math.floor(diffMs / 86400000);
    }

    function filterJobs() {
      const query = document.getElementById("search").value.trim().toLowerCase();
      const status = document.getElementById("statusFilter").value;
      const channel = document.getElementById("channelFilter").value;
      const duplicateFilter = document.getElementById("duplicateFilter").value;
      const source = document.getElementById("sourceFilter").value;
      const daysRaw = document.getElementById("daysFilter").value;
      const maxDays = daysRaw === "" ? null : Number(daysRaw);

      state.filtered = state.jobs.filter((job) => {
        if (status && job.status !== status) return false;
        if (channel && job.application_channel !== channel) return false;
        if (source && job.source_site !== source) return false;
        if (duplicateFilter === "unique" && job.is_duplicate) return false;
        if (duplicateFilter === "duplicate" && !job.is_duplicate) return false;
        if (maxDays !== null && daysSince(job.scraped_at) > maxDays) return false;

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
          job.source_site,
        ].join(" ").toLowerCase().includes(query);
      });

      sortFiltered();
      pruneSelection();
      renderTable();
      syncSelectedRow();
      renderFooter();
      renderSortIndicators();
      renderDeleteButton();
      syncCheckAll();
    }

    function sortFiltered() {
      const { key, dir } = state.sort;
      const factor = dir === "asc" ? 1 : -1;
      state.filtered.sort((a, b) => {
        const av = String(a[key] ?? "").toLowerCase();
        const bv = String(b[key] ?? "").toLowerCase();
        if (av < bv) return -1 * factor;
        if (av > bv) return 1 * factor;
        const ar = String(a.row_id || "");
        const br = String(b.row_id || "");
        return ar < br ? -1 : ar > br ? 1 : 0;
      });
    }

    function pruneSelection() {
      const visibleIds = new Set(state.filtered.map((job) => job.row_id));
      for (const id of Array.from(state.selected)) {
        if (!visibleIds.has(id)) state.selected.delete(id);
      }
    }

    function renderSortIndicators() {
      document.querySelectorAll("th.sortable").forEach((th) => {
        const key = th.dataset.sortKey;
        const indicator = th.querySelector(".sort-indicator");
        if (key === state.sort.key) {
          th.classList.add("active");
          if (indicator) indicator.textContent = state.sort.dir === "asc" ? "↑" : "↓";
        } else {
          th.classList.remove("active");
          if (indicator) indicator.textContent = "";
        }
      });
    }

    function renderDeleteButton() {
      const btn = document.getElementById("deleteBtn");
      if (!btn) return;
      const count = state.selected.size;
      btn.textContent = `Delete (${count})`;
      btn.disabled = count === 0;
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

    function renderSourceFilter(jobs) {
      const select = document.getElementById("sourceFilter");
      const current = select.value;
      const sources = [...new Set(jobs.map((job) => job.source_site).filter(Boolean))].sort();
      select.innerHTML = '<option value="">All sources</option>' +
        sources.map((source) => `<option value="${esc(source)}">${esc(source)}</option>`).join("");
      select.value = sources.includes(current) ? current : "";
    }

    function renderTable() {
      const tbody = document.getElementById("jobsBody");
      if (!state.filtered.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No jobs match the current filters.</td></tr>';
        return;
      }

      tbody.innerHTML = state.filtered.map((job) => {
        const openUrl = job.source_url || job.apply_url || "";
        const openLink = openUrl
          ? `<a class="role-open" href="${esc(openUrl)}" target="_blank" rel="noreferrer" title="Open job listing">Open ↗</a>`
          : "";
        const copyBtn = openUrl
          ? `<button class="role-copy" type="button" data-copy-url="${esc(openUrl)}" title="Copy job link">Copy</button>`
          : "";
        const currentStatus = (job.status || "saved").toLowerCase();
        const optionList = STATUS_OPTIONS.includes(currentStatus)
          ? STATUS_OPTIONS
          : [currentStatus, ...STATUS_OPTIONS];
        const options = optionList
          .map((opt) => `<option value="${esc(opt)}" ${opt === currentStatus ? "selected" : ""}>${esc(opt)}</option>`)
          .join("");
        const checked = state.selected.has(job.row_id) ? "checked" : "";
        return `
        <tr data-id="${esc(job.row_id)}" class="${job.row_id === state.selectedId ? "active" : ""}">
          <td class="col-check"><input type="checkbox" class="row-check" data-check-id="${esc(job.row_id)}" ${checked} aria-label="Select row"></td>
          <td>
            <div class="role"><span>${esc(job.job_title)}</span>${openLink}${copyBtn}</div>
            <div class="company">${esc(job.company)} • ${esc(job.location)}</div>
          </td>
          <td>
            <select class="status-select ${statusClass(currentStatus)}" data-status-id="${esc(job.row_id)}" aria-label="Status">
              ${options}
            </select>
          </td>
          <td>${esc(job.scraped_at)}</td>
          <td>
            ${job.source_site ? badge(job.source_site) : ""}
            ${job.is_duplicate ? badge("Duplicate", "duplicate") : badge("Unique")}
            ${job.application_channel === "email" ? badge("Email apply") : badge("Platform")}
            ${job.contact_emails && job.contact_emails !== "N/A" ? badge("Has email") : ""}
            ${job.salary && job.salary !== "N/A" ? badge(job.salary) : ""}
            ${job.job_type && job.job_type !== "N/A" ? badge(job.job_type) : ""}
          </td>
        </tr>
      `;
      }).join("");

      tbody.querySelectorAll("input.row-check").forEach((cb) => {
        cb.addEventListener("click", (event) => event.stopPropagation());
        cb.addEventListener("change", () => {
          const id = cb.dataset.checkId;
          if (cb.checked) state.selected.add(id);
          else state.selected.delete(id);
          renderDeleteButton();
          syncCheckAll();
        });
      });

      tbody.querySelectorAll("select.status-select").forEach((sel) => {
        sel.addEventListener("click", (event) => event.stopPropagation());
        sel.addEventListener("change", async () => {
          const id = sel.dataset.statusId;
          const newStatus = sel.value;
          sel.disabled = true;
          try {
            const response = await fetch("/api/jobs/update", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ row_id: id, updates: { status: newStatus } }),
            });
            const data = await response.json();
            if (!data.ok) throw new Error(data.error || "Update failed");
            const job = state.jobs.find((j) => j.row_id === id);
            if (job) job.status = newStatus;
            sel.className = `status-select ${statusClass(newStatus)}`;
          } catch (err) {
            sel.value = (state.jobs.find((j) => j.row_id === id) || {}).status || "saved";
            console.error("Status update failed:", err);
          } finally {
            sel.disabled = false;
          }
        });
      });

      tbody.querySelectorAll("tr[data-id]").forEach((row) => {
        row.addEventListener("click", () => {
          state.selectedId = row.dataset.id;
          tbodyState();
          renderDetails();
          openDrawer();
        });
      });

      tbody.querySelectorAll("a.role-open").forEach((link) => {
        link.addEventListener("click", (event) => event.stopPropagation());
      });

      tbody.querySelectorAll("button.role-copy").forEach((btn) => {
        btn.addEventListener("click", async (event) => {
          event.stopPropagation();
          const url = btn.getAttribute("data-copy-url") || "";
          if (!url) return;
          try {
            if (navigator.clipboard?.writeText) {
              await navigator.clipboard.writeText(url);
            } else {
              const ta = document.createElement("textarea");
              ta.value = url;
              ta.style.position = "fixed";
              ta.style.opacity = "0";
              document.body.appendChild(ta);
              ta.select();
              document.execCommand("copy");
              document.body.removeChild(ta);
            }
            btn.classList.add("copied");
            btn.textContent = "Copied!";
          } catch {
            btn.textContent = "Failed";
          }
          setTimeout(() => {
            btn.classList.remove("copied");
            btn.textContent = "Copy";
          }, 1400);
        });
      });
    }

    function syncSelectedRow() {
      const currentVisible = state.filtered.some((job) => job.row_id === state.selectedId);
      if (!currentVisible) {
        state.selectedId = null;
        closeDrawer();
      }
      tbodyState();
      renderDetails();
    }

    function openDrawer() {
      document.getElementById("drawerPane")?.classList.add("open");
      document.getElementById("drawerBackdrop")?.classList.add("open");
      document.getElementById("drawerPane")?.setAttribute("aria-hidden", "false");
    }

    function closeDrawer() {
      document.getElementById("drawerPane")?.classList.remove("open");
      document.getElementById("drawerBackdrop")?.classList.remove("open");
      document.getElementById("drawerPane")?.setAttribute("aria-hidden", "true");
    }

    function tbodyState() {
      document.querySelectorAll("#jobsBody tr[data-id]").forEach((row) => {
        row.classList.toggle("active", row.dataset.id === state.selectedId);
      });
    }

    function syncCheckAll() {
      const checkAll = document.getElementById("checkAll");
      if (!checkAll) return;
      const total = state.filtered.length;
      const selected = state.filtered.filter((job) => state.selected.has(job.row_id)).length;
      checkAll.checked = total > 0 && selected === total;
      checkAll.indeterminate = selected > 0 && selected < total;
    }

    async function bulkDelete() {
      const ids = Array.from(state.selected);
      if (!ids.length) return;
      const confirmed = window.confirm(`Delete ${ids.length} job${ids.length === 1 ? "" : "s"}? This rewrites the CSV files and cannot be undone.`);
      if (!confirmed) return;
      const btn = document.getElementById("deleteBtn");
      if (btn) {
        btn.disabled = true;
        btn.textContent = "Deleting...";
      }
      try {
        const response = await fetch("/api/jobs/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ row_ids: ids }),
        });
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || "Delete failed");
        state.selected.clear();
        if (state.selectedId && ids.includes(state.selectedId)) {
          state.selectedId = null;
          closeDrawer();
        }
        await loadJobs();
      } catch (err) {
        console.error("Bulk delete failed:", err);
        if (btn) btn.textContent = "Delete failed";
        setTimeout(renderDeleteButton, 1400);
      }
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
          <h2>${esc(job.job_title)}</h2>
          <p class="hero-copy">${esc(job.company)} • ${esc(job.location)}</p>
          <div class="actions" style="margin-top:14px;">${signalBadges}</div>
        </div>

        <div class="actions">
          ${job.apply_url ? `<a class="button" href="${esc(job.apply_url)}" target="_blank" rel="noreferrer">Open Apply URL</a>` : ""}
          ${job.source_url ? `<a class="button secondary" href="${esc(job.source_url)}" target="_blank" rel="noreferrer">Open Indeed Link</a>` : ""}
          ${job.source_url ? `<button class="button secondary" type="button" data-copy="${esc(job.source_url)}" data-label="Copy Indeed Link">Copy Indeed Link</button>` : ""}
          ${job.apply_url ? `<button class="button secondary" type="button" data-copy="${esc(job.apply_url)}" data-label="Copy Apply URL">Copy Apply URL</button>` : ""}
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
          <div class="meta"><div class="meta-label">Source Site</div><div class="meta-value">${esc(fmt(job.source_site))}</div></div>
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

      pane.querySelectorAll("button[data-copy]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const text = btn.getAttribute("data-copy") || "";
          const label = btn.getAttribute("data-label") || btn.textContent;
          if (!text) return;
          try {
            if (navigator.clipboard?.writeText) {
              await navigator.clipboard.writeText(text);
            } else {
              const ta = document.createElement("textarea");
              ta.value = text;
              ta.style.position = "fixed";
              ta.style.opacity = "0";
              document.body.appendChild(ta);
              ta.select();
              document.execCommand("copy");
              document.body.removeChild(ta);
            }
            btn.classList.add("copied");
            btn.textContent = "Copied!";
            setTimeout(() => {
              btn.classList.remove("copied");
              btn.textContent = label;
            }, 1400);
          } catch (err) {
            btn.textContent = "Copy failed";
            setTimeout(() => { btn.textContent = label; }, 1400);
          }
        });
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
      renderSourceFilter(state.jobs);
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
    document.getElementById("sourceFilter").addEventListener("change", filterJobs);
    document.getElementById("daysFilter").addEventListener("change", filterJobs);
    document.getElementById("refreshBtn").addEventListener("click", loadJobs);
    document.getElementById("exportBtn").addEventListener("click", exportJson);
    document.getElementById("deleteBtn").addEventListener("click", bulkDelete);
    document.getElementById("drawerCloseBtn").addEventListener("click", closeDrawer);
    document.getElementById("drawerBackdrop").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeDrawer();
    });

    document.getElementById("checkAll").addEventListener("change", (event) => {
      if (event.target.checked) {
        state.filtered.forEach((job) => state.selected.add(job.row_id));
      } else {
        state.filtered.forEach((job) => state.selected.delete(job.row_id));
      }
      renderTable();
      syncSelectedRow();
      renderDeleteButton();
      syncCheckAll();
    });

    document.querySelectorAll("th.sortable").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.sortKey;
        if (state.sort.key === key) {
          state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
        } else {
          state.sort.key = key;
          state.sort.dir = "asc";
        }
        filterJobs();
      });
    });

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


TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "msclkid", "yclid", "mc_cid", "mc_eid",
    "ref", "referer", "referrer", "src", "source",
    "trk", "trk_info", "tracking_id", "tk", "tid",
    "_ga", "_gl", "hsa_acc", "hsa_cam", "hsa_grp",
}

INDEED_KEEP_KEYS = {"jk", "vjs", "from"}


def clean_job_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower()
    query = parse_qs(parsed.query)

    if "indeed" in host:
        filtered = {k: v for k, v in query.items() if k in INDEED_KEEP_KEYS}
    else:
        filtered = {k: v for k, v in query.items() if k.lower() not in TRACKING_QUERY_PARAMS}

    cleaned = parsed._replace(
        params="",
        fragment="",
        query=urlencode(filtered, doseq=True),
    )
    return urlunparse(cleaned)


def derive_source_site(url: str) -> str:
    try:
        host = (urlparse(url or "").hostname or "").lower()
    except Exception:
        host = ""
    return host[4:] if host.startswith("www.") else host


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
        return f"url:{clean_job_url(source_url)}"

    if apply_url and not apply_url.lower().startswith("mailto:") and is_meaningful_job_url(apply_url):
        return f"url:{clean_job_url(apply_url)}"

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
            "source_url": clean_job_url(source_url) if source_url else "",
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


UPDATABLE_FIELDS = {"status"}


def parse_row_id(row_id: str) -> tuple[Path, int] | None:
    if not isinstance(row_id, str) or ":" not in row_id:
        return None
    file_part, _, row_part = row_id.rpartition(":")
    try:
        row_number = int(row_part)
    except ValueError:
        return None
    candidate = (JOB_DATA_DIR / file_part).resolve()
    try:
        candidate.relative_to(JOB_DATA_DIR.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate, row_number


def update_job_row(row_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_row_id(row_id)
    if parsed is None:
        return {"ok": False, "error": "Invalid row_id"}
    path, target_row = parsed
    if not isinstance(updates, dict) or not updates:
        return {"ok": False, "error": "No updates provided"}

    cleaned: dict[str, str] = {}
    for key, value in updates.items():
        if key in UPDATABLE_FIELDS:
            cleaned[key] = str(value).strip()
    if not cleaned:
        return {"ok": False, "error": "No updatable fields supplied"}

    ensure_csv_schema(path)
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    target_index = target_row - 2
    if target_index < 0 or target_index >= len(rows):
        return {"ok": False, "error": "Row out of range"}

    rows[target_index].update(cleaned)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(normalize_job_payload(row))

    return {"ok": True, "updated": cleaned}


def delete_job_rows(row_ids: list[str]) -> dict[str, Any]:
    if not isinstance(row_ids, list) or not row_ids:
        return {"ok": False, "error": "No row_ids provided"}

    grouped: dict[Path, set[int]] = {}
    invalid: list[str] = []
    for row_id in row_ids:
        parsed = parse_row_id(row_id)
        if parsed is None:
            invalid.append(row_id)
            continue
        path, row_number = parsed
        grouped.setdefault(path, set()).add(row_number)

    deleted = 0
    for path, target_rows in grouped.items():
        ensure_csv_schema(path)
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        kept = [row for idx, row in enumerate(rows, start=2) if idx not in target_rows]
        deleted += len(rows) - len(kept)
        if not kept:
            path.unlink()
            continue
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in kept:
                writer.writerow(normalize_job_payload(row))

    rebuild_job_index()
    return {"ok": True, "deleted": deleted, "invalid": invalid}


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
                        "source_site": derive_source_site(
                            normalized.get("source_url") or normalized.get("apply_url") or ""
                        ),
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
        if self.path not in {"/api/jobs", "/api/jobs/update", "/api/jobs/delete"}:
            self._send_json(404, {"ok": False, "error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "Invalid JSON payload"})
            return

        if self.path == "/api/jobs/update":
            if not isinstance(payload, dict):
                self._send_json(400, {"ok": False, "error": "Expected object payload"})
                return
            result = update_job_row(payload.get("row_id", ""), payload.get("updates", {}))
            status_code = 200 if result.get("ok") else 400
            self._send_json(status_code, {**result, "summary": build_dashboard_payload()["summary"]})
            return

        if self.path == "/api/jobs/delete":
            if not isinstance(payload, dict):
                self._send_json(400, {"ok": False, "error": "Expected object payload"})
                return
            result = delete_job_rows(payload.get("row_ids", []))
            status_code = 200 if result.get("ok") else 400
            self._send_json(status_code, {**result, "summary": build_dashboard_payload()["summary"]})
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
