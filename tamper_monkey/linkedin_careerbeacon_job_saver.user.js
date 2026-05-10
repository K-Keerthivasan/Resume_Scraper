// ==UserScript==
// @name         LinkedIn + CareerBeacon Job Saver
// @namespace    https://k2digitalmedia.ca
// @version      1.0
// @description  Saves LinkedIn and CareerBeacon jobs into the local Resume_Scraper app and auto-fills common apply fields.
// @author       Keerthi (K2 Digital Media)
// @match        https://*.linkedin.com/jobs/*
// @match        https://*.linkedin.com/jobs/view/*
// @match        https://*.linkedin.com/jobs/search/*
// @match        https://*.careerbeacon.com/*
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
    fullName: "Keerthi K",
    email: "your@email.com",
    phone: "519-000-0000",
    city: "London",
    province: "Ontario",
    country: "Canada",
    linkedin: "https://linkedin.com/in/kkvasan",
    website: "https://k2digitalmedia.ca",
    workAuth: "Yes",
  };

  const SITE_CONFIG = {
    linkedin: {
      label: "LinkedIn",
      hostPattern: /(^|\.)linkedin\.com$/i,
      jobPathPattern: /\/jobs\/(view|collections|search|recommended|details)|currentJobId=/i,
      titleSelectors: [
        ".jobs-unified-top-card__job-title h1",
        ".job-details-jobs-unified-top-card__job-title h1",
        ".jobs-details__main-content h1",
        ".top-card-layout__title",
        "h1",
      ],
      companySelectors: [
        ".jobs-unified-top-card__company-name a",
        ".job-details-jobs-unified-top-card__company-name a",
        ".jobs-unified-top-card__primary-description-container a",
        ".topcard__org-name-link",
        "[data-tracking-control-name='public_jobs_topcard-org-name']",
      ],
      locationSelectors: [
        ".jobs-unified-top-card__bullet",
        ".job-details-jobs-unified-top-card__primary-description-container .tvm__text",
        ".topcard__flavor--bullet",
        ".jobs-unified-top-card__primary-description-container span",
      ],
      postedSelectors: [
        ".jobs-unified-top-card__posted-date",
        ".job-details-jobs-unified-top-card__primary-description-container .tvm__text--positive",
        ".posted-time-ago__text",
        "time",
      ],
      descriptionSelectors: [
        "#job-details",
        ".jobs-description-content__text",
        ".jobs-box__html-content",
        ".description__text",
      ],
      applySelectors: [
        ".jobs-apply-button",
        "button.jobs-apply-button",
        "button[aria-label*='Apply' i]",
        "a[data-control-name*='apply' i]",
      ],
    },
    careerbeacon: {
      label: "CareerBeacon",
      hostPattern: /(^|\.)careerbeacon\.com$/i,
      jobPathPattern: /\/(en\/)?(job|jobs|apply)\b|jobid=|posting/i,
      titleSelectors: [
        "[data-testid='job-title']",
        ".job-title",
        ".posting-title",
        "h1",
      ],
      companySelectors: [
        "[data-testid='company-name']",
        ".company-name",
        ".posting-company",
        "a[href*='/company/']",
      ],
      locationSelectors: [
        "[data-testid='job-location']",
        ".job-location",
        ".posting-location",
        "[class*='location' i]",
      ],
      postedSelectors: [
        "[data-testid='posted-date']",
        ".posted-date",
        ".posting-date",
        "time",
      ],
      descriptionSelectors: [
        "[data-testid='job-description']",
        ".job-description",
        ".posting-description",
        "[class*='description' i]",
        "main",
      ],
      applySelectors: [
        "a[href*='apply' i]",
        "button[class*='apply' i]",
        "button[aria-label*='Apply' i]",
      ],
    },
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

  function cleanText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function readText(selectors, fallback = "") {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      const value = cleanText(el?.innerText || el?.textContent || "");
      if (value) return value;
    }
    return fallback;
  }

  function detectSite() {
    const host = window.location.hostname;
    return Object.values(SITE_CONFIG).find((site) => site.hostPattern.test(host)) || null;
  }

  function getJsonLdJobPosting() {
    const scripts = [...document.querySelectorAll("script[type='application/ld+json']")];
    for (const script of scripts) {
      try {
        const parsed = JSON.parse(script.textContent || "{}");
        const graph = parsed?.["@graph"] ? (Array.isArray(parsed["@graph"]) ? parsed["@graph"] : [parsed["@graph"]]) : [];
        const items = Array.isArray(parsed) ? parsed : [parsed, ...graph];
        const job = items.find((item) => {
          const type = item?.["@type"];
          return type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"));
        });
        if (job) return job;
      } catch (error) {
        // Ignore malformed page metadata and continue with DOM scraping.
      }
    }
    return {};
  }

  function getJsonLdLocation(job) {
    const location = Array.isArray(job.jobLocation) ? job.jobLocation[0] : job.jobLocation;
    const address = location?.address || {};
    return cleanText(
      [
        address.addressLocality,
        address.addressRegion,
        address.addressCountry?.name || address.addressCountry,
      ]
        .filter(Boolean)
        .join(", ")
    );
  }

  function getJsonLdSalary(job) {
    const salary = job.baseSalary;
    if (!salary) return "";
    const value = salary.value || {};
    const amount = value.minValue && value.maxValue ? `${value.minValue}-${value.maxValue}` : value.value || value.minValue || value.maxValue || "";
    const currency = salary.currency || "";
    const unit = value.unitText ? `/${String(value.unitText).toLowerCase()}` : "";
    return cleanText([currency, amount].filter(Boolean).join(" ") + unit);
  }

  function extractEmails(text) {
    const matches = String(text || "").match(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi) || [];
    return [...new Set(matches.map((email) => email.toLowerCase().replace(/[.,;:]+$/, "")))];
  }

  function extractLinkedInJobId(url) {
    try {
      const parsed = new URL(url, window.location.origin);
      const pathMatch = parsed.pathname.match(/\/jobs\/view\/(\d+)/i);
      return pathMatch?.[1] || parsed.searchParams.get("currentJobId") || parsed.searchParams.get("jobId") || "";
    } catch (error) {
      return "";
    }
  }

  function canonicalSourceUrl(site) {
    if (site?.label === "LinkedIn") {
      const id =
        extractLinkedInJobId(window.location.href) ||
        extractLinkedInJobId(document.querySelector("a[href*='/jobs/view/']")?.href || "");
      if (id) return `https://www.linkedin.com/jobs/view/${id}/`;
    }
    return window.location.href.split("#")[0];
  }

  function isJobPage() {
    const site = detectSite();
    if (!site) return false;
    const hasJobMetadata = Boolean(getJsonLdJobPosting()?.title);
    return hasJobMetadata || site.jobPathPattern.test(`${window.location.pathname}${window.location.search}`);
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

  function pickShortTextByPattern(pattern) {
    return [...document.querySelectorAll("span, div, li, p")]
      .map((el) => cleanText(el.innerText || el.textContent || ""))
      .find((text) => text && text.length < 90 && pattern.test(text)) || "";
  }

  function getApplyUrl(site) {
    for (const selector of site.applySelectors) {
      const el = document.querySelector(selector);
      const href = el?.href || el?.closest("a")?.href;
      if (href) return href;
    }
    const mailto = document.querySelector("a[href^='mailto:']")?.href;
    return mailto || window.location.href;
  }

  function getKeySkills(descEl, description) {
    const listItems = descEl
      ? [...descEl.querySelectorAll("li")]
          .map((li) => cleanText(li.innerText || li.textContent || ""))
          .filter((text) => text.length > 5 && text.length < 140)
          .slice(0, 8)
      : [];

    if (listItems.length) return listItems.join(" | ");

    const keywordMatches = [
      "JavaScript",
      "Python",
      "SQL",
      "React",
      "Node",
      "HTML",
      "CSS",
      "Figma",
      "Excel",
      "Power BI",
      "AWS",
      "Azure",
      "Salesforce",
      "SEO",
      "WordPress",
    ].filter((skill) => new RegExp(`\\b${skill.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(description));

    return keywordMatches.length ? keywordMatches.join(" | ") : "N/A";
  }

  function scrapeCurrentJob() {
    const site = detectSite();
    const jsonLd = getJsonLdJobPosting();
    const descEl = site ? document.querySelector(site.descriptionSelectors.join(", ")) : null;
    const rawDescription = cleanText(descEl?.innerText || descEl?.textContent || jsonLd.description || "");
    const description = rawDescription ? rawDescription.slice(0, 800) : "N/A";
    const applyUrl = site ? getApplyUrl(site) : window.location.href;
    const emails = extractEmails(`${rawDescription} ${document.body.innerText} ${applyUrl}`);
    const channel = inferApplicationChannel(description, emails, applyUrl);

    const title = cleanText(jsonLd.title) || readText(site?.titleSelectors || ["h1"], "Unknown Title");
    const company =
      cleanText(jsonLd.hiringOrganization?.name) ||
      readText(site?.companySelectors || [], "Unknown Company");
    const location = getJsonLdLocation(jsonLd) || readText(site?.locationSelectors || [], "Unknown Location");
    const postedDate =
      cleanText(jsonLd.datePosted) ||
      readText(site?.postedSelectors || [], "") ||
      pickShortTextByPattern(/today|just posted|posted|days ago|hours ago|reposted|promoted/i) ||
      "N/A";
    const salary = getJsonLdSalary(jsonLd) || pickShortTextByPattern(/\$|salary|hour|year|wage/i) || "N/A";
    const jobType = cleanText(jsonLd.employmentType) || pickShortTextByPattern(/full.time|part.time|contract|permanent|casual|temporary|intern/i) || "N/A";

    return {
      job_title: title,
      company,
      location,
      job_type: jobType,
      salary,
      posted_date: postedDate,
      description_summary: description,
      key_skills: getKeySkills(descEl, rawDescription),
      contact_emails: emails,
      email_apply_required: channel.email_apply_required,
      application_channel: channel.application_channel,
      apply_url: applyUrl,
      source_url: canonicalSourceUrl(site),
      scraped_at: todayISO(),
      status: "saved",
    };
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

  function showToast(message, duration = 3200) {
    const existing = document.getElementById("tm-lcb-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.id = "tm-lcb-toast";
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
    document.getElementById("tm-lcb-duplicate-modal")?.remove();
  }

  function showDuplicateModal(job, duplicateInfo) {
    hideDuplicateModal();

    const overlay = document.createElement("div");
    overlay.id = "tm-lcb-duplicate-modal";
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
          </div>
          ${existing.flagged === "yes" ? `
          <div style="padding:14px;border-radius:14px;background:rgba(245,196,106,0.14);border:1px solid rgba(245,196,106,0.55);color:#f5c46a;font-size:14px;font-weight:600;line-height:1.45;">
            ⚑ You flagged this job as useless previously. Reconsider before saving again.
          </div>` : ""}
          <div style="padding:14px;border-radius:16px;background:rgba(255,255,255,0.03);border:1px solid rgba(106,194,255,0.14);">
            <div style="font-size:16px;font-weight:700;">${escapeHtml(job.job_title)}</div>
            <div style="font-size:13px;color:#9eb2d1;margin-top:6px;">${escapeHtml(job.company)} • ${escapeHtml(job.location)}</div>
            <div style="font-size:12px;color:#7f96bb;margin-top:10px;">Original saved: ${escapeHtml(existing.scraped_at || "Unknown date")}</div>
          </div>
          <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;">
            <button id="tm-lcb-dup-cancel" type="button" style="padding:11px 14px;border-radius:12px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.03);color:#eef6ff;cursor:pointer;font:inherit;">Cancel</button>
            <button id="tm-lcb-dup-save" type="button" style="padding:11px 14px;border-radius:12px;border:0;background:linear-gradient(135deg,#20b8f0,#45d0ff);color:#04111a;cursor:pointer;font:inherit;font-weight:700;">Save second entry</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) hideDuplicateModal();
    });
    document.getElementById("tm-lcb-dup-cancel")?.addEventListener("click", hideDuplicateModal);
    document.getElementById("tm-lcb-dup-save")?.addEventListener("click", async () => {
      hideDuplicateModal();
      await saveJobToLocalApp(true);
    });
  }

  async function saveJobToLocalApp(allowDuplicate = false) {
    if (!isJobPage()) {
      showToast("Open a job posting before saving.");
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

  function fillField(selector, value) {
    const el = document.querySelector(selector);
    if (!el || !value) return false;
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function autoFillForm() {
    let filled = 0;

    filled += fillField("input[name*='firstName' i], input[id*='firstName' i], input[autocomplete='given-name'], input[placeholder*='first name' i]", MY_INFO.firstName) ? 1 : 0;
    filled += fillField("input[name*='lastName' i], input[id*='lastName' i], input[autocomplete='family-name'], input[placeholder*='last name' i]", MY_INFO.lastName) ? 1 : 0;
    filled += fillField("input[name*='fullName' i], input[id*='fullName' i], input[autocomplete='name'], input[placeholder*='full name' i]", MY_INFO.fullName) ? 1 : 0;
    filled += fillField("input[type='email'], input[name*='email' i], input[id*='email' i]", MY_INFO.email) ? 1 : 0;
    filled += fillField("input[type='tel'], input[name*='phone' i], input[id*='phone' i], input[name*='mobile' i]", MY_INFO.phone) ? 1 : 0;
    filled += fillField("input[name*='city' i], input[id*='city' i], input[autocomplete='address-level2']", MY_INFO.city) ? 1 : 0;
    filled += fillField("input[name*='province' i], input[id*='province' i], input[autocomplete='address-level1']", MY_INFO.province) ? 1 : 0;
    filled += fillField("input[name*='country' i], input[id*='country' i], input[autocomplete='country-name']", MY_INFO.country) ? 1 : 0;
    filled += fillField("input[name*='linkedin' i], input[id*='linkedin' i], input[placeholder*='linkedin' i]", MY_INFO.linkedin) ? 1 : 0;
    filled += fillField("input[name*='website' i], input[name*='portfolio' i], input[id*='website' i], input[placeholder*='portfolio' i]", MY_INFO.website) ? 1 : 0;

    const authEl = document.querySelector("select[name*='auth' i], select[id*='auth' i], select[name*='work' i], input[name*='authorized' i]");
    if (authEl && authEl.tagName === "SELECT") {
      [...authEl.options].forEach((opt) => {
        if (/yes|authorized|eligible|canada/i.test(opt.text)) {
          authEl.value = opt.value;
          authEl.dispatchEvent(new Event("change", { bubbles: true }));
          filled += 1;
        }
      });
    }

    showToast(filled > 0 ? `Auto-filled ${filled} field(s)` : "No fillable fields found on this page.");
  }

  function renderPanel() {
    const site = detectSite();
    const titleNode = document.getElementById("tm-lcb-job-title");
    const metaNode = document.getElementById("tm-lcb-job-meta");
    const routeNode = document.getElementById("tm-lcb-job-route");
    const emailNode = document.getElementById("tm-lcb-job-email");
    const skillsNode = document.getElementById("tm-lcb-job-skills");
    const skillsWrap = document.getElementById("tm-lcb-job-skills-wrap");
    const toggleSkillsBtn = document.getElementById("tm-lcb-toggle-skills-btn");
    const statusNode = document.getElementById("tm-lcb-collector-status");
    const saveBtn = document.getElementById("tm-lcb-save-btn");
    const sourceNode = document.getElementById("tm-lcb-source-label");

    if (!titleNode || !metaNode || !routeNode || !emailNode || !skillsNode || !skillsWrap || !toggleSkillsBtn || !statusNode || !saveBtn || !sourceNode) return;

    state.jobPreview = isJobPage() ? scrapeCurrentJob() : null;
    const preview = state.jobPreview;
    sourceNode.textContent = `${site?.label || "Job"} Saver`;

    if (preview) {
      titleNode.textContent = preview.job_title;
      metaNode.textContent = `${preview.company} • ${preview.location}`;
      routeNode.textContent = `Apply route: ${preview.application_channel}`;
      emailNode.textContent = preview.contact_emails.length
        ? `Detected email: ${preview.contact_emails.join(", ")}`
        : "No application email detected on this page.";
      skillsNode.textContent = preview.key_skills === "N/A" ? "No skills detected yet." : preview.key_skills;
      skillsWrap.style.display = state.showSkills ? "block" : "none";
      toggleSkillsBtn.textContent = state.showSkills ? "Hide Skills" : "Show Skills";
      saveBtn.disabled = state.saving;
      saveBtn.style.opacity = state.saving ? "0.65" : "1";
      saveBtn.textContent = state.saving ? "Saving..." : "Save Job";
    } else {
      titleNode.textContent = "Open a job posting";
      metaNode.textContent = "The saver becomes active on LinkedIn or CareerBeacon job pages.";
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

  function createPanel() {
    if (document.getElementById("tm-lcb-panel")) return;

    const panel = document.createElement("div");
    panel.id = "tm-lcb-panel";
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
            <div id="tm-lcb-source-label" style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;font-weight:700;color:#ff8b5e;">Job Saver</div>
            <div style="font-size:22px;font-weight:700;margin-top:8px;line-height:1.05;">Local Job Capture</div>
          </div>
          <button id="tm-lcb-min-btn" type="button" style="border:1px solid rgba(106,194,255,0.16);background:rgba(255,255,255,0.06);color:#eef6ff;width:32px;height:32px;border-radius:999px;cursor:pointer;font-size:18px;line-height:1;">-</button>
        </div>
        <div id="tm-lcb-collector-status" style="margin-top:14px;display:inline-flex;padding:7px 10px;border-radius:999px;font-size:12px;font-weight:700;">Collector offline</div>
      </div>

      <div id="tm-lcb-panel-body" style="padding:16px;display:grid;gap:14px;">
        <div style="padding:14px;border-radius:18px;background:linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));border:1px solid rgba(106, 194, 255, 0.12);box-shadow:inset 0 1px 0 rgba(255,255,255,0.03);">
          <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#ff8b5e;font-weight:700;">Detected Job</div>
          <div id="tm-lcb-job-title" style="margin-top:8px;font-size:18px;line-height:1.18;font-weight:700;">Loading...</div>
          <div id="tm-lcb-job-meta" style="margin-top:6px;font-size:13px;color:#9eb2d1;line-height:1.45;"></div>
          <div id="tm-lcb-job-route" style="margin-top:8px;font-size:12px;color:#45d0ff;font-weight:700;"></div>
          <div id="tm-lcb-job-email" style="margin-top:6px;font-size:12px;line-height:1.5;color:#9eb2d1;"></div>
          <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;">
            <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#ff8b5e;font-weight:700;">Key Skills</div>
            <button id="tm-lcb-toggle-skills-btn" type="button" style="padding:6px 10px;border-radius:999px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;font-size:11px;">Hide Skills</button>
          </div>
          <div id="tm-lcb-job-skills-wrap" style="display:block;">
            <div id="tm-lcb-job-skills" style="margin-top:8px;font-size:12px;line-height:1.55;color:#c8d7f0;"></div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <button id="tm-lcb-save-btn" type="button" title="Save Job (Alt+Shift+S)" style="padding:12px 14px;border-radius:14px;border:0;background:linear-gradient(135deg,#20b8f0,#45d0ff);color:#04111a;cursor:pointer;font:inherit;font-weight:700;box-shadow:0 12px 28px rgba(32,184,240,0.22);">Save Job</button>
          <button id="tm-lcb-fill-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;font-weight:700;">Auto Fill</button>
          <button id="tm-lcb-refresh-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;">Refresh</button>
          <button id="tm-lcb-dashboard-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;">Dashboard</button>
        </div>
      </div>
      <div style="padding:0 16px 16px;font-size:12px;line-height:1.5;color:#8ea2c6;">
        Shortcut: Alt+Shift+S saves the detected job.
      </div>
    `;

    document.body.appendChild(panel);

    const body = panel.querySelector("#tm-lcb-panel-body");
    const minBtn = panel.querySelector("#tm-lcb-min-btn");
    let collapsed = false;

    minBtn?.addEventListener("click", () => {
      collapsed = !collapsed;
      if (body) body.style.display = collapsed ? "none" : "grid";
      minBtn.textContent = collapsed ? "+" : "-";
    });

    panel.querySelector("#tm-lcb-save-btn")?.addEventListener("click", () => saveJobToLocalApp(false));
    panel.querySelector("#tm-lcb-fill-btn")?.addEventListener("click", autoFillForm);
    panel.querySelector("#tm-lcb-toggle-skills-btn")?.addEventListener("click", () => {
      state.showSkills = !state.showSkills;
      renderPanel();
    });
    panel.querySelector("#tm-lcb-refresh-btn")?.addEventListener("click", async () => {
      renderPanel();
      await pingCollector();
      showToast("Panel refreshed.");
    });
    panel.querySelector("#tm-lcb-dashboard-btn")?.addEventListener("click", () => {
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
        setTimeout(renderPanel, 700);
      }
    }, 1500);

    if (/\/apply|easy-apply|jobs-apply|careerbeacon\.com/i.test(window.location.href)) {
      setTimeout(autoFillForm, 2200);
    }
  });
  window.addEventListener("keydown", handleShortcut);
})();
