// ==UserScript==
// @name         Universal Canada Job Saver + Local Collector
// @namespace    https://k2digitalmedia.ca
// @version      1.0
// @description  Saves any Canadian job posting (federal/provincial/city, university, ATS platforms, aggregators) into the local Resume_Scraper app. Reads schema.org JobPosting JSON-LD first, then microdata, then DOM heuristics.
// @author       Keerthi (K2 Digital Media)
//
// === Federal & provincial ===
// @match        *://*.jobbank.gc.ca/*
// @match        *://jobbank.gc.ca/*
// @match        *://*.jobs.gc.ca/*
// @match        *://jobs.gc.ca/*
// @match        *://emploisfp-psjobs.cfp-psc.gc.ca/*
// @match        *://*.canada.ca/*
// @match        *://*.gov.bc.ca/*
// @match        *://*.alberta.ca/*
// @match        *://*.ontario.ca/*
// @match        *://*.gov.mb.ca/*
// @match        *://*.gov.sk.ca/*
// @match        *://*.gnb.ca/*
// @match        *://*.novascotia.ca/*
// @match        *://*.gov.nl.ca/*
// @match        *://*.gov.pe.ca/*
//
// === Major Canadian cities ===
// @match        *://*.toronto.ca/*
// @match        *://*.london.ca/*
// @match        *://*.ottawa.ca/*
// @match        *://*.mississauga.ca/*
// @match        *://*.brampton.ca/*
// @match        *://*.hamilton.ca/*
// @match        *://*.vaughan.ca/*
// @match        *://*.kitchener.ca/*
// @match        *://*.waterloo.ca/*
// @match        *://*.windsor.ca/*
// @match        *://*.vancouver.ca/*
// @match        *://*.calgary.ca/*
// @match        *://*.edmonton.ca/*
// @match        *://*.winnipeg.ca/*
// @match        *://*.halifax.ca/*
// @match        *://*.regina.ca/*
// @match        *://*.saskatoon.ca/*
// @match        *://*.victoria.ca/*
// @match        *://*.montreal.ca/*
// @match        *://*.ville.montreal.qc.ca/*
//
// === ATS platforms (used by most Canadian employers) ===
// @match        *://*.myworkdayjobs.com/*
// @match        *://*.workday.com/*
// @match        *://boards.greenhouse.io/*
// @match        *://job-boards.greenhouse.io/*
// @match        *://jobs.lever.co/*
// @match        *://*.icims.com/*
// @match        *://*.taleo.net/*
// @match        *://*.successfactors.com/*
// @match        *://*.bamboohr.com/*
// @match        *://apply.workable.com/*
// @match        *://*.workable.com/*
// @match        *://*.recruitee.com/*
// @match        *://*.smartrecruiters.com/*
// @match        *://*.bullhornstaffing.com/*
// @match        *://*.avature.net/*
// @match        *://*.zohorecruit.com/*
// @match        *://*.dayforcehcm.com/*
// @match        *://*.ultipro.com/*
// @match        *://*.adp.com/*
//
// === Canadian aggregators ===
// @match        *://*.jobillico.com/*
// @match        *://*.eluta.ca/*
// @match        *://*.neuvoo.ca/*
// @match        *://*.monster.ca/*
// @match        *://*.talent.com/*
// @match        *://*.jobboom.com/*
// @match        *://*.simplyhired.ca/*
//
// === Avoid duplicating dedicated scrapers ===
// @exclude      *://*.indeed.com/*
// @exclude      *://*.linkedin.com/*
// @exclude      *://*.careerbeacon.com/*
// @exclude      *://*.londontechjobs.ca/*
//
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
  };

  const SKILL_KEYWORDS = [
    "JavaScript", "TypeScript", "Python", "Java", "C#", "C++", "Go", "Rust", "Ruby", "PHP", "Kotlin", "Swift",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Snowflake", "BigQuery",
    "React", "Vue", "Angular", "Svelte", "Next.js", "Node", "Django", "Flask", "FastAPI", "Spring", "Rails", ".NET",
    "HTML", "CSS", "SASS", "Tailwind", "Bootstrap",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "GitLab", "GitHub Actions",
    "Linux", "Bash", "PowerShell",
    "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator", "InDesign",
    "Excel", "Power BI", "Tableau", "Looker", "Salesforce", "HubSpot", "WordPress", "Shopify",
    "SEO", "SEM", "Google Analytics", "GA4", "GTM",
    "AI", "ML", "TensorFlow", "PyTorch", "LLM", "RAG", "Cybersecurity", "DevOps", "CI/CD", "Agile", "Scrum",
    "Bilingual", "French", "English",
  ];

  const NAV_HEADING_PATTERN = /^(home|about|contact|login|sign in|register|search|menu|jobs|careers|browse|filters?)$/i;

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

  function cleanText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function readText(selectors, fallback = "") {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      const value = cleanText(el?.innerText || el?.textContent || "");
      if (value) return value;
    }
    return fallback;
  }

  function getMeta(name) {
    const el = document.querySelector(`meta[property='${name}'], meta[name='${name}']`);
    return cleanText(el?.content || "");
  }

  function getJsonLdJobPosting() {
    const scripts = [...document.querySelectorAll("script[type='application/ld+json']")];
    for (const script of scripts) {
      let parsed;
      try {
        parsed = JSON.parse(script.textContent || "{}");
      } catch (error) {
        continue;
      }
      const candidates = [];
      const visit = (node) => {
        if (!node || typeof node !== "object") return;
        if (Array.isArray(node)) {
          node.forEach(visit);
          return;
        }
        if (Array.isArray(node["@graph"])) node["@graph"].forEach(visit);
        const type = node["@type"];
        if (type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"))) {
          candidates.push(node);
        }
      };
      visit(parsed);
      if (candidates.length) return candidates[0];
    }
    return null;
  }

  function getMicrodataJob() {
    const root = document.querySelector("[itemtype$='/JobPosting'], [itemtype$='/JobPosting/']");
    if (!root) return null;
    const read = (prop) => {
      const el = root.querySelector(`[itemprop='${prop}']`);
      if (!el) return "";
      return cleanText(el.getAttribute("content") || el.getAttribute("datetime") || el.innerText || el.textContent || "");
    };
    return {
      title: read("title"),
      hiringOrganization: { name: read("hiringOrganization") },
      jobLocation: { address: { addressLocality: read("jobLocation") } },
      datePosted: read("datePosted"),
      employmentType: read("employmentType"),
      description: read("description"),
    };
  }

  function getJsonLdLocation(job) {
    const location = Array.isArray(job.jobLocation) ? job.jobLocation[0] : job.jobLocation;
    if (!location) return "";
    if (typeof location === "string") return cleanText(location);
    const address = location.address || {};
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
    const minMax = value.minValue && value.maxValue ? `${value.minValue}-${value.maxValue}` : "";
    const single = value.value || value.minValue || value.maxValue || "";
    const amount = minMax || single;
    const currency = salary.currency || "";
    const unit = value.unitText ? `/${String(value.unitText).toLowerCase()}` : "";
    return cleanText([currency, amount].filter(Boolean).join(" ") + unit);
  }

  function extractEmails(text) {
    const matches = String(text || "").match(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi) || [];
    return [...new Set(matches.map((email) => email.toLowerCase().replace(/[.,;:]+$/, "")))];
  }

  function getApplyUrl(jsonLd) {
    if (jsonLd?.url && /^https?:/i.test(jsonLd.url)) return jsonLd.url;
    if (jsonLd?.applicationContact?.email) return `mailto:${jsonLd.applicationContact.email}`;

    const applyButton = [...document.querySelectorAll("a[href]")].find((link) => {
      const text = cleanText(link.innerText || link.textContent || "").toLowerCase();
      const href = link.getAttribute("href") || "";
      if (!href) return false;
      if (/^mailto:/i.test(href)) return true;
      if (/^javascript:/i.test(href)) return false;
      return /\bapply\b|postuler|appliquer/i.test(text) || /apply|career|application/i.test(href);
    });
    if (applyButton) {
      try {
        return new URL(applyButton.getAttribute("href"), window.location.href).toString();
      } catch (_) {
        return applyButton.getAttribute("href");
      }
    }
    return window.location.href;
  }

  function inferApplicationChannel(description, emails, applyUrl) {
    const combined = `${description} ${applyUrl}`.toLowerCase();
    const emailRequired =
      emails.length > 0 ||
      (applyUrl || "").toLowerCase().startsWith("mailto:") ||
      /(send your resume|send resume|send cv|apply by email|email your resume|submit your resume to|forward your resume to|envoyez votre cv)/i.test(combined);

    return {
      email_apply_required: emailRequired ? "yes" : "no",
      application_channel: emailRequired ? "email" : "platform",
    };
  }

  function getDescription(jsonLd) {
    if (jsonLd?.description) {
      const tmp = document.createElement("div");
      tmp.innerHTML = jsonLd.description;
      const text = cleanText(tmp.innerText || tmp.textContent || "");
      if (text) return text.slice(0, 1200);
    }
    const text =
      readText([
        "[itemprop='description']",
        "[class*='job-description' i]",
        "[class*='posting-description' i]",
        "[class*='jobdescription' i]",
        "[id*='job-description' i]",
        "[id*='jobdescription' i]",
        "[id*='description' i]",
        "section[class*='description' i]",
        "div[class*='description' i]",
        "article",
        "main",
      ]) || getMeta("og:description") || getMeta("description") || document.body.innerText;
    return cleanText(text).slice(0, 1200) || "N/A";
  }

  function getKeySkills(description) {
    const lists = [...document.querySelectorAll("main ul li, article ul li, section ul li, [class*='requirements' i] li, [class*='qualifications' i] li, [class*='responsibilities' i] li")]
      .map((li) => cleanText(li.innerText || li.textContent || ""))
      .filter((text) => text.length > 5 && text.length < 220 && !NAV_HEADING_PATTERN.test(text))
      .slice(0, 10);

    if (lists.length) return lists.join(" | ");

    const text = description || "";
    const matches = SKILL_KEYWORDS.filter((skill) =>
      new RegExp(`\\b${skill.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(text)
    );
    return matches.length ? matches.join(" | ") : "N/A";
  }

  function getHeadingTexts() {
    return [...document.querySelectorAll("h1, h2, h3")]
      .map((el) => cleanText(el.innerText || el.textContent || ""))
      .filter((text) => text && !NAV_HEADING_PATTERN.test(text));
  }

  function getCompanyHeuristic() {
    const og = getMeta("og:site_name");
    if (og && !/jobs?|careers?|hiring/i.test(og)) return og;

    const candidates = [
      "[class*='company' i]",
      "[class*='employer' i]",
      "[itemprop='hiringOrganization']",
      "[data-company]",
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      const text = cleanText(el?.innerText || el?.textContent || el?.getAttribute("content") || "");
      if (text && text.length < 120) return text;
    }
    const host = window.location.hostname.replace(/^www\./, "");
    return host || "Unknown Company";
  }

  function getLocationHeuristic() {
    const candidates = [
      "[class*='location' i]",
      "[itemprop='jobLocation']",
      "[data-location]",
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      const text = cleanText(el?.innerText || el?.textContent || "");
      if (text && text.length < 160) return text;
    }
    const lines = (document.body.innerText || "").split(/\n+/).map(cleanText).filter(Boolean);
    const provinceLine = lines.find((line) =>
      /\b(Ontario|ON|Quebec|QC|Que\.|British Columbia|BC|Alberta|AB|Manitoba|MB|Saskatchewan|SK|Nova Scotia|NS|New Brunswick|NB|Newfoundland|NL|PEI|Prince Edward Island|Yukon|YT|Northwest Territories|NT|Nunavut|NU|Canada|Remote)\b/i.test(line)
    );
    return provinceLine || "Unknown Location";
  }

  function isJobPage() {
    if (getJsonLdJobPosting()) return true;
    if (getMicrodataJob()) return true;
    const path = window.location.pathname.toLowerCase();
    if (/(^|\/)(job|jobs|career|careers|posting|postings|opportunity|vacancy|vacancies|emploi|emplois)(\/|$)/.test(path)) {
      const headings = getHeadingTexts();
      if (headings.length && cleanText(document.body.innerText).length > 400) return true;
    }
    return false;
  }

  function scrapeCurrentJob() {
    const jsonLd = getJsonLdJobPosting() || getMicrodataJob() || {};
    const description = getDescription(jsonLd);
    const applyUrl = getApplyUrl(jsonLd);
    const emails = extractEmails(`${description} ${document.body.innerText} ${applyUrl}`);
    const channel = inferApplicationChannel(description, emails, applyUrl);

    const headings = getHeadingTexts();
    const title =
      cleanText(jsonLd.title) ||
      getMeta("og:title") ||
      headings[0] ||
      cleanText(document.title) ||
      "Unknown Title";

    const company =
      cleanText(jsonLd.hiringOrganization?.name) ||
      getCompanyHeuristic();

    const location =
      getJsonLdLocation(jsonLd) ||
      getLocationHeuristic();

    return {
      job_title: title,
      company,
      location,
      job_type: cleanText(jsonLd.employmentType) || "N/A",
      salary: getJsonLdSalary(jsonLd) || "N/A",
      posted_date: cleanText(jsonLd.datePosted) || "N/A",
      description_summary: description,
      key_skills: getKeySkills(description),
      contact_emails: emails,
      email_apply_required: channel.email_apply_required,
      application_channel: channel.application_channel,
      apply_url: applyUrl,
      source_url: window.location.href.split("#")[0],
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
    const existing = document.getElementById("tm-uca-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.id = "tm-uca-toast";
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
    document.getElementById("tm-uca-duplicate-modal")?.remove();
  }

  function showDuplicateModal(job, duplicateInfo) {
    hideDuplicateModal();

    const overlay = document.createElement("div");
    overlay.id = "tm-uca-duplicate-modal";
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
      <div style="width:min(520px, 100%);background:linear-gradient(180deg, rgba(12,20,35,0.98), rgba(7,13,24,0.98));color:#eef6ff;border-radius:22px;box-shadow:0 28px 70px rgba(0,0,0,0.42);border:1px solid rgba(106,194,255,0.16);overflow:hidden;font-family:'Segoe UI',sans-serif;">
        <div style="padding:20px 22px;background:linear-gradient(135deg,#ff6f8d 0%,#ff8b5e 100%);color:#08111f;">
          <div style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;font-weight:700;opacity:0.88;">Duplicate Detected</div>
          <div style="font-size:24px;font-weight:700;margin-top:8px;">Save a second entry anyway?</div>
        </div>
        <div style="padding:20px 22px;display:grid;gap:14px;">
          <div style="font-size:14px;line-height:1.55;color:#9eb2d1;">
            This job already exists in <strong>${escapeHtml(existing.file || duplicateInfo.existing_file || "your job archive")}</strong>.
          </div>
          <div style="padding:14px;border-radius:16px;background:rgba(255,255,255,0.03);border:1px solid rgba(106,194,255,0.14);">
            <div style="font-size:16px;font-weight:700;">${escapeHtml(job.job_title)}</div>
            <div style="font-size:13px;color:#9eb2d1;margin-top:6px;">${escapeHtml(job.company)} • ${escapeHtml(job.location)}</div>
            <div style="font-size:12px;color:#7f96bb;margin-top:10px;">Original saved: ${escapeHtml(existing.scraped_at || "Unknown date")}</div>
          </div>
          <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;">
            <button id="tm-uca-dup-cancel" type="button" style="padding:11px 14px;border-radius:12px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.03);color:#eef6ff;cursor:pointer;font:inherit;">Cancel</button>
            <button id="tm-uca-dup-save" type="button" style="padding:11px 14px;border-radius:12px;border:0;background:linear-gradient(135deg,#20b8f0,#45d0ff);color:#04111a;cursor:pointer;font:inherit;font-weight:700;">Save second entry</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) hideDuplicateModal();
    });
    document.getElementById("tm-uca-dup-cancel")?.addEventListener("click", hideDuplicateModal);
    document.getElementById("tm-uca-dup-save")?.addEventListener("click", async () => {
      hideDuplicateModal();
      await saveJobToLocalApp(true);
    });
  }

  async function saveJobToLocalApp(allowDuplicate = false) {
    if (!isJobPage()) {
      showToast("Open a job posting page before saving.");
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
    filled += fillField("input[name*='province' i], input[name*='state' i], input[id*='province' i], input[autocomplete='address-level1']", MY_INFO.province) ? 1 : 0;
    filled += fillField("input[name*='country' i], input[id*='country' i], input[autocomplete='country-name']", MY_INFO.country) ? 1 : 0;
    filled += fillField("input[name*='linkedin' i], input[id*='linkedin' i], input[placeholder*='linkedin' i]", MY_INFO.linkedin) ? 1 : 0;
    filled += fillField("input[name*='website' i], input[name*='portfolio' i], input[id*='website' i], input[placeholder*='portfolio' i]", MY_INFO.website) ? 1 : 0;
    showToast(filled > 0 ? `Auto-filled ${filled} field(s)` : "No fillable fields found on this page.");
  }

  function renderPanel() {
    const titleNode = document.getElementById("tm-uca-job-title");
    const metaNode = document.getElementById("tm-uca-job-meta");
    const routeNode = document.getElementById("tm-uca-job-route");
    const emailNode = document.getElementById("tm-uca-job-email");
    const skillsNode = document.getElementById("tm-uca-job-skills");
    const skillsWrap = document.getElementById("tm-uca-job-skills-wrap");
    const toggleSkillsBtn = document.getElementById("tm-uca-toggle-skills-btn");
    const statusNode = document.getElementById("tm-uca-collector-status");
    const sourceNode = document.getElementById("tm-uca-source");
    const saveBtn = document.getElementById("tm-uca-save-btn");

    if (!titleNode || !metaNode || !routeNode || !emailNode || !skillsNode || !skillsWrap || !toggleSkillsBtn || !statusNode || !sourceNode || !saveBtn) return;

    state.jobPreview = isJobPage() ? scrapeCurrentJob() : null;
    const preview = state.jobPreview;
    const host = window.location.hostname.replace(/^www\./, "");

    sourceNode.textContent = `Source: ${host}`;

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
      metaNode.textContent = "The saver waits until it sees JobPosting structured data or a /job /career URL.";
      routeNode.textContent = "Navigate to the actual posting, then save.";
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
    if (document.getElementById("tm-uca-panel")) return;

    const panel = document.createElement("div");
    panel.id = "tm-uca-panel";
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
            <div style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;font-weight:700;color:#ff8b5e;">Universal Canada Saver</div>
            <div style="font-size:22px;font-weight:700;margin-top:8px;line-height:1.05;">Local Job Capture</div>
            <div id="tm-uca-source" style="margin-top:6px;font-size:11px;color:#9eb2d1;letter-spacing:0.04em;"></div>
          </div>
          <button id="tm-uca-min-btn" type="button" style="border:1px solid rgba(106,194,255,0.16);background:rgba(255,255,255,0.06);color:#eef6ff;width:32px;height:32px;border-radius:999px;cursor:pointer;font-size:18px;line-height:1;">-</button>
        </div>
        <div id="tm-uca-collector-status" style="margin-top:14px;display:inline-flex;padding:7px 10px;border-radius:999px;font-size:12px;font-weight:700;">Collector offline</div>
      </div>

      <div id="tm-uca-panel-body" style="padding:16px;display:grid;gap:14px;">
        <div style="padding:14px;border-radius:18px;background:linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));border:1px solid rgba(106, 194, 255, 0.12);box-shadow:inset 0 1px 0 rgba(255,255,255,0.03);">
          <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#ff8b5e;font-weight:700;">Detected Job</div>
          <div id="tm-uca-job-title" style="margin-top:8px;font-size:18px;line-height:1.18;font-weight:700;">Loading...</div>
          <div id="tm-uca-job-meta" style="margin-top:6px;font-size:13px;color:#9eb2d1;line-height:1.45;"></div>
          <div id="tm-uca-job-route" style="margin-top:8px;font-size:12px;color:#45d0ff;font-weight:700;"></div>
          <div id="tm-uca-job-email" style="margin-top:6px;font-size:12px;line-height:1.5;color:#9eb2d1;"></div>
          <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;">
            <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#ff8b5e;font-weight:700;">Key Skills</div>
            <button id="tm-uca-toggle-skills-btn" type="button" style="padding:6px 10px;border-radius:999px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;font-size:11px;">Hide Skills</button>
          </div>
          <div id="tm-uca-job-skills-wrap" style="display:block;">
            <div id="tm-uca-job-skills" style="margin-top:8px;font-size:12px;line-height:1.55;color:#c8d7f0;"></div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <button id="tm-uca-save-btn" type="button" title="Save Job (Alt+Shift+S)" style="padding:12px 14px;border-radius:14px;border:0;background:linear-gradient(135deg,#20b8f0,#45d0ff);color:#04111a;cursor:pointer;font:inherit;font-weight:700;box-shadow:0 12px 28px rgba(32,184,240,0.22);">Save Job</button>
          <button id="tm-uca-fill-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;font-weight:700;">Auto Fill</button>
          <button id="tm-uca-refresh-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;">Refresh</button>
          <button id="tm-uca-dashboard-btn" type="button" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(106,194,255,0.14);background:rgba(255,255,255,0.04);color:#eef6ff;cursor:pointer;font:inherit;">Dashboard</button>
        </div>

        <div style="font-size:12px;line-height:1.5;color:#8ea2c6;">
          Shortcut: Alt+Shift+S saves the detected job. Works on any page with JobPosting structured data, or /job /career style URLs.
        </div>
      </div>
    `;

    document.body.appendChild(panel);

    const body = panel.querySelector("#tm-uca-panel-body");
    const minBtn = panel.querySelector("#tm-uca-min-btn");
    let collapsed = false;

    minBtn?.addEventListener("click", () => {
      collapsed = !collapsed;
      if (body) body.style.display = collapsed ? "none" : "grid";
      minBtn.textContent = collapsed ? "+" : "-";
    });

    panel.querySelector("#tm-uca-save-btn")?.addEventListener("click", () => saveJobToLocalApp(false));
    panel.querySelector("#tm-uca-fill-btn")?.addEventListener("click", autoFillForm);
    panel.querySelector("#tm-uca-toggle-skills-btn")?.addEventListener("click", () => {
      state.showSkills = !state.showSkills;
      renderPanel();
    });
    panel.querySelector("#tm-uca-refresh-btn")?.addEventListener("click", async () => {
      renderPanel();
      await pingCollector();
      showToast("Panel refreshed.");
    });
    panel.querySelector("#tm-uca-dashboard-btn")?.addEventListener("click", () => {
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
  });
  window.addEventListener("keydown", handleShortcut);
})();
