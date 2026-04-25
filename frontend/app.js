// ── State ──────────────────────────────────────────────────
let inputType = "url";
let systemReady = false;

// ── DOM refs ───────────────────────────────────────────────
const toggleBtns     = document.querySelectorAll(".toggle-btn");
const urlField       = document.getElementById("url-field");
const pasteField     = document.getElementById("paste-field");
const jobUrl         = document.getElementById("job-url");
const jobPaste       = document.getElementById("job-paste");
const processBtn     = document.getElementById("process-btn");
const recheckBtn     = document.getElementById("recheck-btn");
const statusMsg      = document.getElementById("status-msg");
const inputCard      = document.getElementById("input-card");
const duplicateCard  = document.getElementById("duplicate-card");
const dupMsg         = document.getElementById("duplicate-msg");
const dupCvLink      = document.getElementById("dup-cv-link");
const dupForceBtn    = document.getElementById("dup-force-btn");
const dupBackBtn     = document.getElementById("dup-back-btn");
const progressCard   = document.getElementById("progress-card");
const progressTimer  = document.getElementById("progress-timer");
const progressCurrent = document.getElementById("progress-current");
const stepsList      = document.getElementById("steps-list");
const resultsSection = document.getElementById("results-section");
const newBtn         = document.getElementById("new-btn");
const cvLink         = document.getElementById("cv-link");
const sheetLink      = document.getElementById("sheet-link");

// ── Pre-defined step order ─────────────────────────────────
const STEPS = [
  { id: "scraping",          label: "Extracting job description" },
  { id: "analyzing",         label: "Analyzing job requirements & ATS keywords" },
  { id: "company_scrape",    label: "Researching company website" },
  { id: "news",              label: "Searching recent news" },
  { id: "company_synthesis", label: "Synthesising company research" },
  { id: "matching",          label: "Scoring fit & identifying CV gaps" },
  { id: "tailoring",         label: "Tailoring CV content" },
  { id: "creating",          label: "Creating tailored Google Doc" },
  { id: "logging",           label: "Logging to application tracker" },
];

// ── Health check ───────────────────────────────────────────
const SERVICE_LABELS = {
  anthropic:     "Anthropic API",
  tavily:        "Tavily (News)",
  google:        "Google API",
  tahel_profile: "Tahel Profile",
};

async function runHealthCheck() {
  Object.keys(SERVICE_LABELS).forEach(key => {
    const el = document.getElementById(`sc-${key}`);
    if (el) { el.className = "status-item loading"; el.removeAttribute("title"); }
  });
  statusMsg.classList.add("hidden");
  processBtn.disabled = true;
  recheckBtn.disabled = true;
  recheckBtn.textContent = "Checking...";

  try {
    const res = await fetch("/api/health-check");
    const data = await res.json();

    Object.entries(data.checks).forEach(([key, check]) => {
      const el = document.getElementById(`sc-${key}`);
      if (!el) return;
      el.className = `status-item ${check.status}`;
      el.setAttribute("title", check.message);
    });

    systemReady = data.ready;
    processBtn.disabled = !systemReady;

    if (!systemReady) {
      const errors = Object.entries(data.checks)
        .filter(([, c]) => c.status === "error")
        .map(([k, c]) => `${SERVICE_LABELS[k]}: ${c.message}`)
        .join(" · ");
      statusMsg.textContent = errors;
      statusMsg.classList.remove("hidden");
    }
  } catch (e) {
    statusMsg.textContent = "Could not reach server. Is it running?";
    statusMsg.classList.remove("hidden");
  } finally {
    recheckBtn.disabled = false;
    recheckBtn.textContent = "Recheck";
  }
}

recheckBtn.addEventListener("click", runHealthCheck);
runHealthCheck();

// ── Toggle URL / Paste ─────────────────────────────────────
toggleBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    toggleBtns.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    inputType = btn.dataset.type;
    if (inputType === "url") {
      urlField.classList.remove("hidden");
      pasteField.classList.add("hidden");
    } else {
      urlField.classList.add("hidden");
      pasteField.classList.remove("hidden");
    }
  });
});

// ── Process ────────────────────────────────────────────────
processBtn.addEventListener("click", () => processRequest(false));
dupForceBtn.addEventListener("click", () => processRequest(true));

async function processRequest(force) {
  const content = inputType === "url" ? jobUrl.value.trim() : jobPaste.value.trim();
  if (!content) {
    alert(inputType === "url" ? "Please enter a job URL." : "Please paste a job description.");
    return;
  }

  // Switch to progress view and pre-render all steps as pending
  inputCard.classList.add("hidden");
  duplicateCard.classList.add("hidden");
  resultsSection.classList.add("hidden");
  progressCard.classList.remove("hidden");
  progressCurrent.textContent = "Starting...";

  stepsList.innerHTML = STEPS.map(s => `
    <li class="step-item pending" id="step-${s.id}">
      <div class="step-icon">○</div>
      <span>${s.label}</span>
    </li>
  `).join("");

  // Start elapsed timer
  let elapsed = 0;
  progressTimer.textContent = "0s";
  const timerInterval = setInterval(() => {
    elapsed++;
    progressTimer.textContent = `${elapsed}s`;
  }, 1000);

  function activateStep(id, message) {
    // Mark previous active step as done
    document.querySelectorAll(".step-item.active").forEach(el => {
      el.classList.remove("active");
      el.classList.add("done");
      el.querySelector(".step-icon").textContent = "✓";
    });
    const el = document.getElementById(`step-${id}`);
    if (el) {
      el.classList.remove("pending");
      el.classList.add("active");
      el.querySelector(".step-icon").textContent = "⟳";
    }
    progressCurrent.textContent = message;
  }

  function markAllDone() {
    document.querySelectorAll(".step-item.active, .step-item.pending").forEach(el => {
      el.classList.remove("active", "pending");
      el.classList.add("done");
      el.querySelector(".step-icon").textContent = "✓";
    });
  }

  function markStepError(id, message) {
    // Mark active step as error
    document.querySelectorAll(".step-item.active").forEach(el => {
      el.classList.remove("active");
      el.classList.add("error");
      el.querySelector(".step-icon").textContent = "✕";
    });
    progressCurrent.textContent = message;
    progressCurrent.style.color = "var(--red)";

    const retry = document.createElement("button");
    retry.className = "btn-ghost";
    retry.textContent = "Try Again";
    retry.style.marginTop = "16px";
    retry.onclick = () => resetToInput();
    progressCard.appendChild(retry);
  }

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_type: inputType, content, force }),
    });

    if (!response.ok) throw new Error(`Server error: ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let payload;
        try { payload = JSON.parse(line.slice(6)); } catch { continue; }

        const { step, message, data } = payload;

        if (step === "duplicate") {
          clearInterval(timerInterval);
          progressCard.classList.add("hidden");
          dupMsg.textContent = message;
          dupCvLink.href = (data && data.cv_url) ? data.cv_url : "#";
          if (!data || !data.cv_url) dupCvLink.classList.add("hidden");
          else dupCvLink.classList.remove("hidden");
          duplicateCard.classList.remove("hidden");
          return;
        }

        if (step === "linkedin_error") {
          clearInterval(timerInterval);
          progressCard.classList.add("hidden");
          inputCard.classList.remove("hidden");
          // Switch to paste mode and show the message
          toggleBtns.forEach(b => b.classList.remove("active"));
          document.querySelector('.toggle-btn[data-type="paste"]').classList.add("active");
          inputType = "paste";
          urlField.classList.add("hidden");
          pasteField.classList.remove("hidden");
          jobPaste.placeholder = "Paste the LinkedIn job description here...";
          jobPaste.focus();
          const banner = document.createElement("p");
          banner.className = "linkedin-banner";
          banner.textContent = "LinkedIn requires login — paste the job description below instead.";
          inputCard.insertBefore(banner, inputCard.querySelector(".toggle-row"));
          return;
        }

        if (step === "error") {
          clearInterval(timerInterval);
          markStepError(step, message);
          return;
        }

        if (step === "complete") {
          clearInterval(timerInterval);
          markAllDone();
          progressCurrent.textContent = `Done in ${elapsed}s`;
          setTimeout(() => renderResults(data), 600);
          return;
        }

        activateStep(step, message);
      }
    }
  } catch (err) {
    clearInterval(timerInterval);
    markStepError("", err.message || "Unexpected error. Check the server is running.");
  }
});

// ── Render results ─────────────────────────────────────────
function renderResults(data) {
  const { job_analysis, company_research, match_gaps, news, cv_url, sheet_url } = data;

  const ja = document.getElementById("job-analysis-content");
  ja.innerHTML = `
    <div class="kv-row"><span class="kv-key">Company</span><span class="kv-val">${esc(job_analysis.company_name)}</span></div>
    <div class="kv-row"><span class="kv-key">Title</span><span class="kv-val">${esc(job_analysis.job_title)}</span></div>
    <div class="kv-row"><span class="kv-key">Level</span><span class="kv-val">${esc(job_analysis.seniority)}</span></div>
    <p style="margin-top:10px;font-size:.8125rem;color:#64748B">${esc(job_analysis.ideal_candidate_summary)}</p>
    <div class="tags" style="margin-top:10px">
      ${(job_analysis.ats_keywords || []).slice(0, 8).map(k => `<span class="tag">${esc(k)}</span>`).join("")}
    </div>
  `;

  const cr = document.getElementById("company-content");
  cr.innerHTML = `
    <p style="font-size:.875rem">${esc(company_research.summary)}</p>
    <ul class="info-list" style="margin-top:10px">
      ${(company_research.key_talking_points || []).map(p => `<li>${esc(p)}</li>`).join("")}
    </ul>
    <div class="tags" style="margin-top:10px">
      <span class="tag green">${esc(company_research.growth_stage || "")}</span>
    </div>
  `;

  const score = match_gaps.match_score || 0;
  const scoreClass = score >= 70 ? "high" : score >= 50 ? "mid" : "low";
  const mc = document.getElementById("match-content");
  mc.innerHTML = `
    <div class="match-score-num ${scoreClass}">${score}</div>
    <div class="match-score-label">/ 100</div>
    <p class="match-rationale">${esc(match_gaps.match_rationale || "")}</p>
  `;

  const nc = document.getElementById("news-content");
  nc.innerHTML = (!news || news.length === 0)
    ? `<p class="news-empty">No recent news found for this company.</p>`
    : news.map(n => `
        <div class="news-item">
          <div class="news-title"><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></div>
          <div class="news-snippet">${esc(n.snippet)}</div>
        </div>
      `).join("");

  const gc = document.getElementById("gaps-content");
  const strategy = match_gaps.cv_strategy ? `<div class="strategy-box">${esc(match_gaps.cv_strategy)}</div>` : "";
  const gapsHtml = (match_gaps.gaps || []).map(g => `
    <div class="gap-item ${g.importance}">
      <div class="gap-title">
        <span class="tag ${g.importance === "high" ? "red" : g.importance === "medium" ? "amber" : "green"}">${esc(g.importance)}</span>
        &nbsp;${esc(g.gap)}
      </div>
      <div class="gap-suggestion">${esc(g.suggestion)}</div>
    </div>
  `).join("");
  gc.innerHTML = strategy + gapsHtml;

  cvLink.href = cv_url || "#";
  sheetLink.href = sheet_url || "#";

  progressCard.classList.add("hidden");
  resultsSection.classList.remove("hidden");
}

// ── Reset ──────────────────────────────────────────────────
newBtn.addEventListener("click", resetToInput);
dupBackBtn.addEventListener("click", resetToInput);

function resetToInput() {
  jobUrl.value = "";
  jobPaste.value = "";
  stepsList.innerHTML = "";
  progressCurrent.textContent = "";
  progressCurrent.style.color = "";
  progressTimer.textContent = "0s";
  progressCard.classList.add("hidden");
  duplicateCard.classList.add("hidden");
  resultsSection.classList.add("hidden");
  inputCard.classList.remove("hidden");
  progressCard.querySelectorAll("button.btn-ghost").forEach(el => el.remove());
  inputCard.querySelectorAll(".linkedin-banner").forEach(el => el.remove());
}

// ── Utility ────────────────────────────────────────────────
function esc(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
