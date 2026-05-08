// ==UserScript==
// @name         Indeed Job Saver + Local Collector
// @namespace    https://k2digitalmedia.ca
// @version      3.0
// @description  Saves Indeed jobs into the local Resume_Scraper app and auto-fills common apply fields.
// @author       Keerthi (K2 Digital Media)
// @match        https://*.indeed.com/*
// @match        https://*.indeedapply.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_notification
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  const COLLECTOR_BASE = "http://127.0.0.1:8765";
  const COLLECTOR_URL = `${COLLECTOR_BASE}/api/jobs`;
  const DASHBOARD_URL = `${COLLECTOR_BASE}/`;

  const MY_INFO = {
    firstName: "Keerthi",
    lastName: "K",
    email: "your@email.com",
    phone: "519-000-0000",
    city: "London, Ontario",
    province: "Ontario",
    country: "Canada",
    linkedin: "https://linkedin.com/in/kkvasan",
    website: "https://k2digitalmedia.ca",
    workAuth: "Yes",
  };

  const state = {
    collectorOnline: false,
    saving: false,
    jobPreview: null,
    currentUrl: window.location.href,
    showSkills: true,
  };

  function todayISO() {
    return new Date().toISOString().split("T")[0];
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fillField(selector, value) {
    const el = document.querySelector(selector);
    if (!el || !value) return false;
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function showToast(message, duration = 3200) {
    const existing = document.getElementById("tm-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.id = "tm-toast";
    toast.textContent = message;
    Object.assign(toast.style, {
      position: "fixed",
      bottom: "24px",
      right: "24px",
      maxWidth: "340px",
      background: "linear-gradient(135deg, rgba(10,18,32,0.98), rgba(18,30,52,0.96))",
      color: "#eef6ff",
      padding: "12px 16px",
      borderRadius: "14px",
      fontSize: "13px",
      lineHeight: "1.45",
      fontFamily: "\"Segoe UI\", sans-serif",
      zIndex: "999999",
      boxShadow: "0 24px 48px rgba(0,0,0,0.36)",
      border: "1px solid rgba(106,194,255,0.18)",
      transition: "opacity 0.25s ease, transform 0.25s ease",
    });
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      setTimeout(() => toast.remove(), 260);
    }, duration);
  }

  function isJobPage() {
    return /viewjob|jk=/i.test(window.location.href);
  }

  const TITLE_SKIP_PATTERN = /^(welcome|hi|hello|home|search|sign in|log in|account|menu|browse jobs?)\b/i;

  function readText(selectors, fallback = "") {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      const value = el?.innerText?.trim();
      if (value) return value;
    }
    return fallback;
  }

  function pickAttributeText(pattern) {
    return [...document.querySelectorAll("[class*='attribute_snippet'], [data-testid*='attribute']")]
      .map((el) => el.innerText?.trim())
      .find((text) => text && pattern.test(text)) || "N/A";
  }

  function findPostedDate() {
    const direct = readText([
      "[data-testid='myJobsStateDate']",
      "[data-testid='inlineHeader-companyLocation'] + *",
      ".jobsearch-JobMetadataFooter",
      "span.date",
      "[class*='posted' i]",
    ]);
    if (direct && /(today|just posted|posted|days ago|hours ago|yesterday)/i.test(direct)) {
      return direct;
    }
    const jobContainer =
      document.querySelector("#viewJobSSRRoot") ||
      document.querySelector(".jobsearch-JobComponent") ||
      document.querySelector("main") ||
      document.body;

    const blocked = (el) => {
      if (!el) return true;
      if (el.closest && (el.closest("#tm-toast") || el.closest("#tm-panel") || el.closest("#tm-duplicate-modal"))) {
        return true;
      }
      return false;
    };

    const hit = [...jobContainer.querySelectorAll("span, div, p")]
      .filter((el) => !blocked(el))
      .map((el) => el.textContent?.trim() || "")
      .find(
        (text) =>
          text &&
          text.length < 80 &&
          /\b(today|just posted|posted (today|yesterday)|\d+\+? (?:days?|hours?) ago|yesterday)\b/i.test(text)
      );
    return hit || "N/A";
  }

  function extractEmails(text) {
    const matches = String(text || "").match(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi) || [];
    return [...new Set(matches.map((email) => email.toLowerCase().replace(/[.,;:]+$/, "")))];
  }

  function extractJobId(url) {
    try {
      const parsed = new URL(url, window.location.origin);
      return parsed.searchParams.get("jk") || parsed.searchParams.get("vjk") || "";
    } catch (error) {
      return "";
    }
  }

  function buildCanonicalSourceUrl(applyUrl) {
    const jobId =
      extractJobId(window.location.href) ||
      extractJobId(applyUrl) ||
      extractJobId(document.querySelector("a[href*='jk='], a[href*='vjk=']")?.href || "");

    if (jobId) {
      return `${window.location.origin}/viewjob?jk=${jobId}`;
    }
    return window.location.href;
  }

  function inferApplicationChannel(description, emails, applyUrl) {
    const combined = `${description} ${applyUrl}`.toLowerCase();
    const emailRequired =
      emails.length > 0 ||
      applyUrl.toLowerCase().startsWith("mailto:") ||
      /(send your resume|send resume|send cv|apply by email|email your resume|submit your resume to|forward your resume to)/i.test(combined);

    return {
      email_apply_required: emailRequired ? "yes" : "no",
      application_channel: emailRequired ? "email" : "platform",
    };
  }

  function findJobTitle() {
    const candidates = [
      "h1.jobsearch-JobInfoHeader-title",
      "[data-testid='jobsearch-JobInfoHeader-title']",
      "[data-testid='simpler-jobTitle']",
      "h2.jobsearch-JobInfoHeader-title",
      "h1[class*='JobInfoHeader' i]",
      "h1[class*='jobtitle' i]",
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      const text = el?.innerText?.trim();
      if (text && !TITLE_SKIP_PATTERN.test(text)) return text;
    }
    const heads = [...document.querySelectorAll("main h1, [role='main'] h1, h1")];
    for (const el of heads) {
      const text = el.innerText?.trim();
      if (text && !TITLE_SKIP_PATTERN.test(text) && text.length < 200) return text;
    }
    const docTitle = document.title.split(/[–|-]/)[0].trim();
    if (docTitle && !TITLE_SKIP_PATTERN.test(docTitle)) return docTitle;
    return "Unknown Title";
  }

  function findLocation() {
    const candidates = [
      "[data-testid='inlineHeader-companyLocation']",
      "[data-testid='job-location']",
      "[data-testid='jobsearch-JobInfoHeader-companyLocation']",
      "div[data-testid*='Location' i]",
      ".companyLocation",
      ".jobsearch-JobInfoHeader-subtitle div:nth-child(2)",
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      const text = el?.innerText?.trim();
      if (text && text.length < 160) return text;
    }
    const subtitle = document.querySelector("[class*='JobInfoHeader-subtitle' i]");
    if (subtitle) {
      const lines = subtitle.innerText.split(/\n+/).map((line) => line.trim()).filter(Boolean);
      const locLine = lines.find((line) => /(remote|hybrid|on[-\s]?site|, [A-Z]{2}\b|ontario|quebec|alberta|british columbia|manitoba|saskatchewan|nova scotia|new brunswick|newfoundland)/i.test(line));
      if (locLine) return locLine;
    }
    return "Unknown Location";
  }

  function scrapeCurrentJob() {
    const title = findJobTitle();

    const company = readText(
      ["[data-company-name]", "[data-testid='inlineHeader-companyName']", "[data-testid='jobsearch-JobInfoHeader-companyName'] a", ".companyName"],
      "Unknown Company"
    );

    const location = findLocation();

    const postedDate = findPostedDate();

    const salary = pickAttributeText(/\$|salary|hour|year|wage/i);
    const jobType = pickAttributeText(/full.time|part.time|contract|permanent|casual|temporary|intern/i);

    const descEl = document.querySelector("#jobDescriptionText, [class*='jobDescription']");
    const description = descEl ? descEl.innerText.slice(0, 800).replace(/\n/g, " ") : "N/A";

    const skills = descEl
      ? [...descEl.querySelectorAll("li")]
          .map((li) => li.innerText.trim())
          .filter((text) => text.length > 5 && text.length < 120)
          .slice(0, 8)
          .join(" | ")
      : "N/A";

    const applyBtn = document.querySelector(
      "button[id*='apply'], a[href*='applystart'], a[href*='applyUrl'], a[href*='indeedapply']"
    );
    const applyUrl = applyBtn?.href || window.location.href;
    const emails = extractEmails(`${document.body.innerText} ${applyUrl}`);
    const channel = inferApplicationChannel(description, emails, applyUrl);

    return {
      job_title: title,
      company,
      location,
      job_type: jobType,
      salary,
      posted_date: postedDate,
      description_summary: description,
      key_skills: skills,
      contact_emails: emails,
      email_apply_required: channel.email_apply_required,
      application_channel: channel.application_channel,
      apply_url: applyUrl,
      source_url: buildCanonicalSourceUrl(applyUrl),
      scraped_at: todayISO(),
      status: "saved",
    };
  }

  function renderPanel() {
    const titleNode = document.getElementById("tm-job-title");
    const metaNode = document.getElementById("tm-job-meta");
    const routeNode = document.getElementById("tm-job-route");
    const emailNode = document.getElementById("tm-job-email");
    const skillsNode = document.getElementById("tm-job-skills");
    const skillsWrap = document.getElementById("tm-job-skills-wrap");
    const toggleSkillsBtn = document.getElementById("tm-toggle-skills-btn");
    const statusNode = document.getElementById("tm-collector-status");
    const saveBtn = document.getElementById("tm-save-btn");

    if (!titleNode || !metaNode || !routeNode || !emailNode || !skillsNode || !skillsWrap || !toggleSkillsBtn || !statusNode || !saveBtn) return;

    state.jobPreview = isJobPage() ? scrapeCurrentJob() : null;
    const preview = state.jobPreview;

    if (preview) {
      titleNode.textContent = preview.job_title;
      metaNode.textContent = `${preview.company} • ${preview.location}`;
      routeNode.textContent = `Apply route: ${preview.application_channel}`;
      emailNode.textContent = preview.contact_emails.length
        ? `Detected email: ${preview.contact_emails.join(", ")}`
        : "No application email detected on this page.";
      skillsNode.textContent = preview.key_skills === "N/A" ? "No bullet skills detected yet." : preview.key_skills;
      skillsWrap.style.display = state.showSkills ? "block" : "none";
      toggleSkillsBtn.textContent = state.showSkills ? "Hide Skills" : "Show Skills";
      saveBtn.disabled = state.saving;
      saveBtn.style.opacity = state.saving ? "0.65" : "1";
      saveBtn.textContent = state.saving ? "Saving..." : "Save Job";
    } else {
      titleNode.textContent = "Open an Indeed job posting";
      metaNode.textContent = "The saver becomes active on actual job pages.";
      routeNode.textContent = "Apply route details show up on a job page.";
      emailNode.textContent = "Detected email addresses will show here.";
      skillsNode.textContent = "Detected skills and summary will appear here.";
      skillsWrap.style.display = state.showSkills ? "block" : "none";
      toggleSkillsBtn.textContent = state.showSkills ? "Hide Skills" : "Show Skills";
      saveBtn.disabled = true;
      saveBtn.style.opacity = "0.5";
      saveBtn.textContent = "Save Job";
    }

    statusNode.textContent = state.collectorOnline ? "Collector online" : "Collector offline";
    statusNode.style.background = state.collectorOnline ? "rgba(15,118,110,0.14)" : "rgba(185,28,28,0.12)";
    statusNode.style.color = state.collectorOnline ? "#0f766e" : "#b91c1c";
  }

  function request(method, url, payload) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method,
        url,
        headers: payload ? { "Content-Type": "application/json" } : {},
        data: payload ? JSON.stringify(payload) : undefined,
        onload: (response) => {
          try {
            resolve(JSON.parse(response.responseText));
          } catch (error) {
            reject(new Error("Invalid collector response"));
          }
        },
        onerror: () => reject(new Error("Collector request failed")),
      });
    });
  }

  async function pingCollector() {
    try {
      await request("GET", `${COLLECTOR_BASE}/health`);
      state.collectorOnline = true;
    } catch (error) {
      state.collectorOnline = false;
    }
    renderPanel();
  }

  function hideDuplicateModal() {
    document.getElementById("tm-duplicate-modal")?.remove();
  }

  function showDuplicateModal(job, duplicateInfo) {
    hideDuplicateModal();

    const overlay = document.createElement("div");
    overlay.id = "tm-duplicate-modal";
    Object.assign(overlay.style, {
      position: "fixed",
      inset: "0",
      background: "rgba(3, 8, 18, 0.62)",
      backdropFilter: "blur(10px)",
      zIndex: "999999",
      display: "grid",
      placeItems: "center",
      padding: "18px",
    });

    const existing = duplicateInfo?.existing || {};
    overlay.innerHTML = `
      <div style="
        width:min(520px, 100%);
        background:linear-gradient(180deg, rgba(12,20,35,0.98), rgba(7,13,24,0.98));
        color:#eef6ff;
        border-radius:22px;
        box-shadow:0 28px 70px rgba(0,0,0,0.42);
        border:1px solid rgba(106,194,255,0.16);
        overflow:hidden;
        font-family:'Segoe UI',sans-serif;
      ">
        <div style="padding:20px 22px;background:linear-gradient(135deg,#ff6f8d 0%,#ff8b5e 100%);color:#08111f;">
          <div style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;font-weight:700;opacity:0.88;">Duplicate Detected</div>
          <div style="font-size:24px;font-weight:700;margin-top:8px;">Save a second entry anyway?</div>
        </div>
        <div style="padding:20px 22px;display:grid;gap:14px;">
          <div style="font-size:14px;line-height:1.55;color:#9eb2d1;">
            This job already exists in <strong>${escapeHtml(existing.file || duplicateInfo.existing_file || "your job archive")}</strong>.
            You can keep the current archive clean or intentionally save a second row for the same job.
          </div>
          <div style="padding:14px;border-radius:16px;background:rgba(255,255,255,0.03);border:1px solid rgba(106,194,255,0.14);">
            <div style="font-size:16px;font-weight:700;">${escapeHtml(job.job_title)}</div>
            <div style="font-size:13px;color:#9eb2d1;margin-top:6px;">${escapeHtml(job.company)} • ${escapeHtml(job.location)}</div>
            <div style="font-size:12px;color:#7f96bb;margin-top:10px;">Original saved: ${escapeHtml(existing.scraped_at || "Unknown date")}</div>
          </div>
          <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;">
            <button id="tm-dup-cancel" type="button" style="padding:11px 14px;border-radius:12px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.03);color:#eef6ff;cursor:pointer;font:inherit;">Cancel</button>
            <button id="tm-dup-save" type="button" style="padding:11px 14px;border-radius:12px;border:0;background:linear-gradient(135deg,#20b8f0,#45d0ff);color:#04111a;cursor:pointer;font:inherit;font-weight:700;">Save second entry</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) hideDuplicateModal();
    });

    document.getElementById("tm-dup-cancel")?.addEventListener("click", hideDuplicateModal);
    document.getElementById("tm-dup-save")?.addEventListener("click", async () => {
      hideDuplicateModal();
      await saveJobToLocalApp(true);
    });
  }

  async function saveJobToLocalApp(allowDuplicate = false) {
    if (!isJobPage()) {
      showToast("Open a real job posting before saving.");
      return;
    }

    if (state.saving) return;
    state.saving = true;
    renderPanel();

    const job = scrapeCurrentJob();
    const payload = allowDuplicate ? { ...job, allow_duplicate: true } : job;

    try {
      const response = await request("POST", COLLECTOR_URL, payload);
      const result = response.results?.[0];
      const summary = response.summary || {};
      state.collectorOnline = true;

      if (result?.stored && result?.duplicate) {
        showToast(`Saved second entry to ${summary.file || "today's file"} (${summary.saved_today || 0} today)`);
      } else if (result?.stored) {
        showToast(`Saved to ${summary.file || "today's file"} (${summary.saved_today || 0} today)`);
      } else if (result?.duplicate) {
        showDuplicateModal(job, result);
      } else {
        showToast("Collector responded, but the save result was unclear.");
      }
    } catch (error) {
      state.collectorOnline = false;
      showToast("Local collector is offline. Run: python3 Scraper.py serve");
    } finally {
      state.saving = false;
      renderPanel();
    }
  }

  function isTypingTarget(target) {
    const tagName = target?.tagName?.toLowerCase();
    return tagName === "input" || tagName === "textarea" || tagName === "select" || target?.isContentEditable;
  }

  function isSaveShortcut(event) {
    return event.altKey && event.shiftKey && !event.ctrlKey && !event.metaKey && event.key?.toLowerCase() === "s";
  }

  function handleShortcut(event) {
    if (!isSaveShortcut(event) || isTypingTarget(event.target)) return;
    event.preventDefault();
    saveJobToLocalApp(false);
  }

  function autoFillForm() {
    let filled = 0;

    filled += fillField("input[name*='firstName' i], input[id*='firstName' i], input[placeholder*='first name' i]", MY_INFO.firstName) ? 1 : 0;
    filled += fillField("input[name*='lastName' i], input[id*='lastName' i], input[placeholder*='last name' i]", MY_INFO.lastName) ? 1 : 0;
    filled += fillField("input[type='email'], input[name*='email' i], input[id*='email' i]", MY_INFO.email) ? 1 : 0;
    filled += fillField("input[type='tel'], input[name*='phone' i], input[id*='phone' i], input[name*='mobile' i]", MY_INFO.phone) ? 1 : 0;
    filled += fillField("input[name*='city' i], input[id*='city' i]", MY_INFO.city) ? 1 : 0;

    const authEl = document.querySelector(
      "select[name*='auth' i], select[id*='auth' i], input[name*='authorized' i]"
    );
    if (authEl && authEl.tagName === "SELECT") {
      [...authEl.options].forEach((opt) => {
        if (/yes|authorized|eligible/i.test(opt.text)) {
          authEl.value = opt.value;
          authEl.dispatchEvent(new Event("change", { bubbles: true }));
          filled += 1;
        }
      });
    }

    filled += fillField("input[name*='linkedin' i], input[id*='linkedin' i], input[placeholder*='linkedin' i]", MY_INFO.linkedin) ? 1 : 0;
    filled += fillField("input[name*='website' i], input[name*='portfolio' i], input[id*='website' i]", MY_INFO.website) ? 1 : 0;

    if (filled > 0) {
      showToast(`Auto-filled ${filled} field(s)`);
    } else {
      showToast("No fillable fields found on this page.");
    }
  }

  function createPanel() {
    if (document.getElementById("tm-panel")) return;

    const panel = document.createElement("div");
    panel.id = "tm-panel";
    Object.assign(panel.style, {
      position: "fixed",
      right: "22px",
      bottom: "22px",
      width: "340px",
      maxWidth: "calc(100vw - 24px)",
      zIndex: "999998",
      background: "linear-gradient(180deg, rgba(8,14,27,0.98), rgba(5,10,18,0.98))",
      color: "#eef6ff",
      border: "1px solid rgba(106,194,255,0.16)",
      borderRadius: "22px",
      boxShadow: "0 28px 60px rgba(0, 0, 0, 0.42)",
      fontFamily: "\"Segoe UI\", sans-serif",
      overflow: "hidden",
    });

    panel.innerHTML = `
      <div style="padding:18px 18px 14px;background:linear-gradient(135deg,#071221 0%,#102746 100%);color:#eef6ff;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
          <div>
            <div style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;font-weight:700;color:#ff8b5e;">Indeed Saver</div>
            <div style="font-size:22px;font-weight:700;margin-top:8px;line-height:1.05;">Local Job Capture</div>
          </div>
          <button id="tm-min-btn" type="button" style="border:1px solid rgba(106,194,255,0.16);background:rgba(255,255,255,0.06);color:#eef6ff;width:32px;height:32px;border-radius:999px;cursor:pointer;font-size:18px;line-height:1;">−</button>
        </div>
        <div id="tm-collector-status" style="margin-top:14px;display:inline-flex;padding:7px 10px;border-radius:999px;font-size:12px;font-weight:700;">Collector offline</div>
      </div>

      <div id="tm-panel-body" style="padding:16px;display:grid;gap:14px;">
        <div style="padding:14px;border-radius:18px;background:linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));border:1px solid rgba(106, 194, 255, 0.12);box-shadow:inset 0 1px 0 rgba(255,255,255,0.03);">
          <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#ff8b5e;font-weight:700;">Detected Job</div>
          <div id="tm-job-title" style="margin-top:8px;font-size:18px;line-height:1.18;font-weight:700;">Loading...</div>
          <div id="tm-job-meta" style="margin-top:6px;font-size:13px;color:#9eb2d1;line-height:1.45;"></div>
          <div id="tm-job-route" style="margin-top:8px;font-size:12px;color:#45d0ff;font-weight:700;"></div>
          <div id="tm-job-email" style="margin-top:6px;font-size:12px;line-height:1.5;color:#9eb2d1;"></div>
          <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;">
            <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#ff8b5e;font-weight:700;">Key Skills</div>
            <button id="tm-toggle-skills-btn" type="button" style="padding:6px 10px;border-radius:999px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;font-size:11px;">Hide Skills</button>
          </div>
          <div id="tm-job-skills-wrap" style="display:block;">
            <div id="tm-job-skills" style="margin-top:8px;font-size:12px;line-height:1.55;color:#c8d7f0;"></div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <button id="tm-save-btn" type="button" title="Save Job (Alt+Shift+S)" style="padding:12px 14px;border-radius:14px;border:0;background:linear-gradient(135deg,#20b8f0,#45d0ff);color:#04111a;cursor:pointer;font:inherit;font-weight:700;box-shadow:0 12px 28px rgba(32,184,240,0.22);">Save Job</button>
          <button id="tm-fill-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;font-weight:700;">Auto Fill</button>
          <button id="tm-refresh-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;">Refresh</button>
          <button id="tm-dashboard-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;">Dashboard</button>
        </div>

        <div style="font-size:12px;line-height:1.5;color:#8ea2c6;">
          Shortcut: Alt+Shift+S saves the detected job. The saver highlights email-route jobs and pauses on duplicates.
        </div>
      </div>
    `;

    document.body.appendChild(panel);

    const body = panel.querySelector("#tm-panel-body");
    const minBtn = panel.querySelector("#tm-min-btn");
    let collapsed = false;

    minBtn?.addEventListener("click", () => {
      collapsed = !collapsed;
      if (body) body.style.display = collapsed ? "none" : "grid";
      minBtn.textContent = collapsed ? "+" : "−";
    });

    panel.querySelector("#tm-save-btn")?.addEventListener("click", () => saveJobToLocalApp(false));
    panel.querySelector("#tm-fill-btn")?.addEventListener("click", autoFillForm);
    panel.querySelector("#tm-toggle-skills-btn")?.addEventListener("click", () => {
      state.showSkills = !state.showSkills;
      renderPanel();
    });
    panel.querySelector("#tm-refresh-btn")?.addEventListener("click", async () => {
      renderPanel();
      await pingCollector();
      showToast("Panel refreshed.");
    });
    panel.querySelector("#tm-dashboard-btn")?.addEventListener("click", () => {
      window.open(DASHBOARD_URL, "_blank", "noopener,noreferrer");
    });

    renderPanel();
  }

  window.addEventListener("load", async () => {
    setTimeout(createPanel, 1200);
    setTimeout(renderPanel, 1800);
    setTimeout(pingCollector, 2200);
    setInterval(pingCollector, 20000);
    setInterval(() => {
      if (window.location.href !== state.currentUrl) {
        state.currentUrl = window.location.href;
        renderPanel();
      }
    }, 1500);

    if (/indeedapply\.com|indeed\.com\/apply/i.test(window.location.href)) {
      setTimeout(autoFillForm, 2000);
    }
  });
  window.addEventListener("keydown", handleShortcut);
})();
