/**
 * JurisLens AI — Client Application Logic
 * Implements side-by-side clause verification, anti-hallucination Q&A,
 * redline comparison, and accessible keyboard navigation.
 */

// Global Application State
const state = {
  currentDocumentId: null,
  currentAnalysis: null,
  currentClauses: [],
  samples: [],
  activeTab: "tab-findings",
};

// DOM Element Selectors
const elements = {
  themeToggleBtn: document.getElementById("theme-toggle-btn"),
  sampleSelect: document.getElementById("sample-select"),
  loadSampleBtn: document.getElementById("load-sample-btn"),
  analyzeBtn: document.getElementById("analyze-btn"),
  rawTextInput: document.getElementById("raw-text-input"),
  fileUploadInput: document.getElementById("file-upload"),
  clausesContainer: document.getElementById("clauses-container"),
  analysisContainer: document.getElementById("analysis-container"),
  docTitleHeader: document.getElementById("doc-title-header"),
  docMetaInfo: document.getElementById("doc-meta-info"),
  qaInput: document.getElementById("qa-input"),
  qaSubmitBtn: document.getElementById("qa-submit-btn"),
  qaResultsContainer: document.getElementById("qa-results-container"),
  qaQuickPrompts: document.getElementById("qa-quick-prompts"),
  lawyerBriefModal: document.getElementById("lawyer-brief-modal"),
  openBriefBtn: document.getElementById("open-brief-btn"),
  closeBriefBtn: document.getElementById("close-brief-btn"),
  briefContent: document.getElementById("brief-content"),
  copyBriefBtn: document.getElementById("copy-brief-btn"),
  compareDoc1Text: document.getElementById("compare-doc1-text"),
  compareDoc2Text: document.getElementById("compare-doc2-text"),
  runCompareBtn: document.getElementById("run-compare-btn"),
  compareResultsContainer: document.getElementById("compare-results-container"),
  loadCompareSamplesBtn: document.getElementById("load-compare-samples-btn"),
  ariaAnnouncer: document.getElementById("aria-announcer"),
};

// Utility: Screen Reader Announcement
function announce(message) {
  if (elements.ariaAnnouncer) {
    elements.ariaAnnouncer.textContent = message;
  }
}

// Theme Toggle
elements.themeToggleBtn?.addEventListener("click", () => {
  const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
  const nextTheme = currentTheme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", nextTheme);
  elements.themeToggleBtn.textContent = nextTheme === "dark" ? "☀️ Light Mode" : "🌙 Dark Mode";
  announce(`Switched to ${nextTheme} theme`);
});

// Load Pre-packaged Samples
async function fetchSamples() {
  try {
    const res = await fetch("/api/samples");
    if (!res.ok) return;
    const data = await res.json();
    state.samples = data.samples || [];

    if (elements.sampleSelect) {
      elements.sampleSelect.innerHTML = state.samples
        .map((s, idx) => `<option value="${s.id}">${s.name}</option>`)
        .join("");
    }
  } catch (err) {
    console.error("Failed to fetch sample documents", err);
  }
}

// Handle Sample Selection
elements.loadSampleBtn?.addEventListener("click", () => {
  const selectedId = elements.sampleSelect.value;
  const sample = state.samples.find((s) => s.id === selectedId);
  if (sample && elements.rawTextInput) {
    elements.rawTextInput.value = sample.content;
    announce(`Loaded sample: ${sample.name}`);
    // Auto-analyze for ultra-fast < 40 click experience
    triggerAnalysis(sample.content, sample.name);
  }
});

// File Upload Handler
elements.fileUploadInput?.addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  setLoadingState(true, `Uploading and analyzing ${file.name}...`);
  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to upload document");
    }
    const data = await res.json();
    renderAnalysisResults(data);
  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    setLoadingState(false);
  }
});

// Manual Analyze Button
elements.analyzeBtn?.addEventListener("click", () => {
  const text = elements.rawTextInput.value.trim();
  if (!text) {
    alert("Please paste contract text or select a sample document.");
    return;
  }
  triggerAnalysis(text, "Contract Document");
});

async function triggerAnalysis(text, title) {
  setLoadingState(true, "Analyzing clauses and verifying grounding with Gemini 2.5...");
  try {
    const res = await fetch("/api/analyze-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, title }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Analysis failed");
    }

    const data = await res.json();
    renderAnalysisResults(data);
  } catch (err) {
    alert(`Analysis error: ${err.message}`);
  } finally {
    setLoadingState(false);
  }
}

function setLoadingState(isLoading, message = "") {
  if (elements.analyzeBtn) elements.analyzeBtn.disabled = isLoading;
  if (elements.loadSampleBtn) elements.loadSampleBtn.disabled = isLoading;
  if (isLoading) {
    announce(message);
    if (elements.analysisContainer) {
      elements.analysisContainer.innerHTML = `
        <div style="text-align: center; padding: 3rem 1rem;">
          <div style="font-size: 2rem; margin-bottom: 1rem;">⚡</div>
          <p style="font-size: 1.1rem; font-weight: 600; color: var(--accent-blue);">${message}</p>
          <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: 0.5rem;">Segmenting clauses & scoring risk with Google Gemini 2.5 Flash...</p>
        </div>
      `;
    }
  }
}

// Render Ingested Clauses in Left Pane
function renderClauses(clauses, docTitle, totalPages) {
  state.currentClauses = clauses;
  if (elements.docTitleHeader) {
    elements.docTitleHeader.textContent = docTitle;
  }
  if (elements.docMetaInfo) {
    elements.docMetaInfo.textContent = `${clauses.length} Segmented Clauses • ~${totalPages} Pages`;
  }

  if (!elements.clausesContainer) return;

  elements.clausesContainer.innerHTML = clauses
    .map(
      (c) => `
      <article 
        class="clause-block" 
        id="${c.clause_id}" 
        data-number="${c.number}"
        tabindex="0"
        aria-label="Clause ${c.number}: ${c.title}"
      >
        <div class="clause-meta">
          <span class="clause-number">Clause ${c.number} (Page ${c.page_number})</span>
          <span class="clause-category">${c.category}</span>
        </div>
        <h4 class="clause-title">${escapeHtml(c.title)}</h4>
        <div class="clause-text">${escapeHtml(c.text)}</div>
      </article>
    `
    )
    .join("");
}

// Grounding & Verification: Synchronous Scroll and Highlight
window.jumpToClause = function (clauseId) {
  const target = document.getElementById(clauseId);
  if (!target) {
    console.warn(`Clause element ${clauseId} not found`);
    return;
  }

  // Remove highlight from any other clause
  document.querySelectorAll(".clause-block.highlighted").forEach((el) => {
    el.classList.remove("highlighted");
  });

  // Highlight and focus target
  target.classList.add("highlighted");
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.focus({ preventScroll: true });

  announce(`Jumped to and highlighted ${target.getAttribute("aria-label")}`);
};

// Render Full Analysis into Right Pane
function renderAnalysisResults(analysis) {
  state.currentDocumentId = analysis.document_id;
  state.currentAnalysis = analysis;

  // Render left-pane clauses
  renderClauses(analysis.clauses, analysis.title, Math.max(1, Math.ceil(analysis.clauses.length / 5)));

  if (elements.openBriefBtn) {
    elements.openBriefBtn.disabled = false;
  }

  const scoreClass =
    analysis.overall_risk_score >= 75
      ? "score-critical"
      : analysis.overall_risk_score >= 50
      ? "score-high"
      : analysis.overall_risk_score >= 30
      ? "score-medium"
      : "score-low";

  // Build Tabbed Interface
  if (elements.analysisContainer) {
    elements.analysisContainer.innerHTML = `
      <!-- Overall Risk Score Card -->
      <section class="risk-meter-container" aria-label="Risk Assessment Overview">
        <div class="score-circle ${scoreClass}">
          <span>${analysis.overall_risk_score}</span>
          <span style="font-size: 0.6rem; text-transform: uppercase;">Risk Score</span>
        </div>
        <div>
          <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
            <h3 style="font-size: 1.1rem; font-weight: 700;">${analysis.document_type}</h3>
            <span class="severity-tag tag-${analysis.risk_level}">${analysis.risk_level} RISK</span>
          </div>
          <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.35rem;">
            ${escapeHtml(analysis.executive_summary)}
          </p>
          <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; gap: 1rem;">
            <span>🛡️ Grounding Confidence: <strong>${analysis.grounding_confidence}%</strong></span>
            <span>⚡ Engine: <strong>${analysis.processed_by}</strong></span>
          </div>
        </div>
      </section>

      <!-- Navigation Tabs -->
      <nav class="tabs-nav" role="tablist" aria-label="Analysis Sections">
        <button class="tab-btn" role="tab" id="btn-tab-findings" aria-selected="true" onclick="switchTab('tab-findings')">
          🔍 Risk Findings (${analysis.key_findings.length})
        </button>
        <button class="tab-btn" role="tab" id="btn-tab-obligations" aria-selected="false" onclick="switchTab('tab-obligations')">
          📋 Obligations & Deadlines (${analysis.obligations_checklist.length})
        </button>
        <button class="tab-btn" role="tab" id="btn-tab-missing" aria-selected="false" onclick="switchTab('tab-missing')">
          ⚠️ Missing Protections (${analysis.missing_protections.length})
        </button>
        <button class="tab-btn" role="tab" id="btn-tab-questions" aria-selected="false" onclick="switchTab('tab-questions')">
          ⚖️ Lawyer Prep (${analysis.suggested_lawyer_questions.length})
        </button>
      </nav>

      <!-- Tab 1: Key Risk Findings -->
      <div id="tab-findings" class="tab-pane active" style="padding-top: 1rem;" role="tabpanel" aria-labelledby="btn-tab-findings">
        ${analysis.key_findings
          .map(
            (f) => `
          <div class="finding-card">
            <div class="finding-header">
              <span class="severity-tag tag-${f.risk_level}">${f.risk_level}</span>
              <button class="citation-chip" onclick="jumpToClause('${f.clause_id}')" title="Click to highlight in original contract">
                📍 Verify Clause ${f.clause_number}
              </button>
            </div>
            <h4 style="font-size: 0.95rem; margin-bottom: 0.25rem;">${escapeHtml(f.clause_title)}</h4>
            <p style="font-size: 0.85rem; color: var(--text-primary); margin-bottom: 0.4rem;">
              <strong>Plain English:</strong> ${escapeHtml(f.plain_summary)}
            </p>
            <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.4rem;">
              <strong>Legal Exposure:</strong> ${escapeHtml(f.potential_risk)}
            </p>
            <div style="background: rgba(56, 189, 248, 0.08); border-left: 3px solid var(--accent-blue); padding: 0.5rem; font-size: 0.8rem; border-radius: 4px;">
              <strong>Recommended Action:</strong> ${escapeHtml(f.action_item)}
            </div>
          </div>
        `
          )
          .join("")}
      </div>

      <!-- Tab 2: Obligations Checklist -->
      <div id="tab-obligations" class="tab-pane" style="display: none; padding-top: 1rem;" role="tabpanel" aria-labelledby="btn-tab-obligations">
        <table class="data-table" aria-label="Contractual Obligations Checklist">
          <thead>
            <tr>
              <th>Clause</th>
              <th>Responsible Party</th>
              <th>Action Required</th>
              <th>Deadline / Trigger</th>
              <th>Breach Consequence</th>
            </tr>
          </thead>
          <tbody>
            ${analysis.obligations_checklist
              .map(
                (o) => `
              <tr>
                <td>
                  <button class="citation-chip" onclick="jumpToClause('${o.clause_id}')">
                    ${o.clause_number}
                  </button>
                </td>
                <td><strong>${escapeHtml(o.party)}</strong></td>
                <td>${escapeHtml(o.obligation)}</td>
                <td><span style="color: var(--risk-medium); font-weight: 600;">${escapeHtml(o.deadline_or_trigger)}</span></td>
                <td style="color: var(--text-muted);">${escapeHtml(o.consequence)}</td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        </table>
      </div>

      <!-- Tab 3: Missing Protections -->
      <div id="tab-missing" class="tab-pane" style="display: none; padding-top: 1rem;" role="tabpanel" aria-labelledby="btn-tab-missing">
        <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid var(--risk-medium); padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; font-size: 0.85rem;">
          💡 <strong>What's Missing is Often More Dangerous Than What's Present:</strong><br/>
          Standard protective clauses typically found in contracts of this type that are notably absent.
        </div>
        ${analysis.missing_protections
          .map(
            (m) => `
          <div class="finding-card" style="border-left: 4px solid var(--risk-medium);">
            <h4 style="color: var(--risk-medium); font-size: 0.95rem; margin-bottom: 0.35rem;">⚠️ Missing: ${escapeHtml(m.topic)}</h4>
            <p style="font-size: 0.85rem; margin-bottom: 0.35rem;">${escapeHtml(m.description)}</p>
            <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.35rem;">
              <strong>Risk Implication:</strong> ${escapeHtml(m.significance)}
            </p>
            <div style="background: var(--bg-surface); padding: 0.5rem; border-radius: 4px; font-size: 0.8rem;">
              <strong>Clarification to Request:</strong> ${escapeHtml(m.suggested_inquiry)}
            </div>
          </div>
        `
          )
          .join("")}
      </div>

      <!-- Tab 4: Lawyer Questions -->
      <div id="tab-questions" class="tab-pane" style="display: none; padding-top: 1rem;" role="tabpanel" aria-labelledby="btn-tab-questions">
        <div style="background: var(--bg-card); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 1rem;">
          <h4 style="margin-bottom: 0.5rem;">Prioritized Questions to Ask Licensed Counsel</h4>
          <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
            Take these questions to your legal consultation to maximize your consultation value and clarify legal risks.
          </p>
          <ol style="padding-left: 1.25rem; font-size: 0.85rem; line-height: 1.8;">
            ${analysis.suggested_lawyer_questions.map((q) => `<li><strong>${escapeHtml(q)}</strong></li>`).join("")}
          </ol>
        </div>
      </div>
    `;
  }

  announce(`Analysis complete. Risk score: ${analysis.overall_risk_score} out of 100.`);
}

// Tab Switching
window.switchTab = function (tabId) {
  state.activeTab = tabId;
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.style.display = pane.id === tabId ? "block" : "none";
  });
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const isTarget = btn.id === `btn-${tabId}`;
    btn.setAttribute("aria-selected", isTarget ? "true" : "false");
  });
};

// Grounded Q&A Submission
elements.qaSubmitBtn?.addEventListener("click", () => submitQuestion());
elements.qaInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") submitQuestion();
});

// Quick Prompt Clickers
window.setQAPrompt = function (promptText) {
  if (elements.qaInput) {
    elements.qaInput.value = promptText;
    submitQuestion();
  }
};

async function submitQuestion() {
  const question = elements.qaInput.value.trim();
  if (!question) return;

  if (!state.currentDocumentId) {
    alert("Please analyze a document first before asking questions.");
    return;
  }

  if (elements.qaResultsContainer) {
    elements.qaResultsContainer.innerHTML = `
      <div style="padding: 1.5rem; text-align: center; color: var(--accent-blue);">
        ⚡ Grounding answer against document clauses with Gemini 2.5...
      </div>
    `;
  }

  try {
    const res = await fetch("/api/qa", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_id: state.currentDocumentId,
        question: question,
        user_role: "general",
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "QA request failed");
    }

    const data = await res.json();
    renderQAResult(data);
  } catch (err) {
    if (elements.qaResultsContainer) {
      elements.qaResultsContainer.innerHTML = `
        <div style="padding: 1rem; color: var(--risk-critical);">Error: ${err.message}</div>
      `;
    }
  }
}

function renderQAResult(data) {
  if (!elements.qaResultsContainer) return;

  const foundBadge = data.is_found_in_document
    ? `<span class="severity-tag tag-LOW">✓ Grounded in Document</span>`
    : `<span class="severity-tag tag-HIGH">⚠️ Information Not Found in Document (Zero Hallucination)</span>`;

  elements.qaResultsContainer.innerHTML = `
    <div class="finding-card" style="margin-top: 1rem; border-color: ${data.is_found_in_document ? "var(--accent-blue)" : "var(--risk-medium)"};">
      <div class="finding-header">
        ${foundBadge}
        <span style="font-size: 0.75rem; color: var(--text-muted);">Confidence: ${data.confidence}%</span>
      </div>
      
      <p style="font-size: 0.95rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-primary);">
        "${escapeHtml(data.question)}"
      </p>

      <div style="font-size: 0.9rem; line-height: 1.6; margin-bottom: 0.75rem; color: var(--text-secondary);">
        ${escapeHtml(data.answer)}
      </div>

      ${
        data.citations && data.citations.length > 0
          ? `
        <div style="margin-bottom: 0.75rem;">
          <strong style="font-size: 0.8rem; color: var(--text-muted); display: block; margin-bottom: 0.25rem;">VERIFIED SOURCE CLAUSES:</strong>
          <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
            ${data.citations
              .map(
                (c) => `
              <button class="citation-chip" onclick="jumpToClause('${c.clause_id}')">
                📍 Jump to Clause ${c.clause_number} (Page ${c.page_number})
              </button>
            `
              )
              .join("")}
          </div>
        </div>
      `
          : ""
      }

      <div style="font-size: 0.8rem; color: var(--text-muted); background: var(--bg-surface); padding: 0.5rem; border-radius: 4px; margin-bottom: 0.5rem;">
        <strong>Verification Guidance:</strong> ${escapeHtml(data.verification_guidance)}
      </div>

      ${
        data.lawyer_follow_up
          ? `
        <div style="font-size: 0.8rem; color: var(--accent-blue); background: rgba(56, 189, 248, 0.08); padding: 0.5rem; border-radius: 4px;">
          ⚖️ <strong>Suggested Attorney Follow-up:</strong> ${escapeHtml(data.lawyer_follow_up)}
        </div>
      `
          : ""
      }
    </div>
  `;

  announce(`Answer generated: ${data.answer.substring(0, 80)}...`);
}

// Side-by-Side Comparison Engine Handler
elements.loadCompareSamplesBtn?.addEventListener("click", () => {
  const std = state.samples.find((s) => s.id === "sample_nda_standard");
  const agg = state.samples.find((s) => s.id === "sample_nda_aggressive");
  if (std && agg) {
    if (elements.compareDoc1Text) elements.compareDoc1Text.value = std.content;
    if (elements.compareDoc2Text) elements.compareDoc2Text.value = agg.content;
    announce("Loaded Standard NDA vs Aggressive Vendor NDA for comparison.");
    runComparison();
  }
});

elements.runCompareBtn?.addEventListener("click", () => runComparison());

async function runComparison() {
  const text1 = elements.compareDoc1Text?.value.trim();
  const text2 = elements.compareDoc2Text?.value.trim();

  if (!text1 || !text2) {
    alert("Please provide both documents to compare.");
    return;
  }

  if (elements.compareResultsContainer) {
    elements.compareResultsContainer.innerHTML = `
      <div style="padding: 2rem; text-align: center; color: var(--accent-blue);">
        ⚡ Generating clause-by-clause redline diff and risk shift analysis...
      </div>
    `;
  }

  try {
    const res = await fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doc1_text: text1,
        doc2_text: text2,
        doc1_name: "Standard Mutual NDA",
        doc2_name: "Aggressive Vendor NDA",
      }),
    });

    if (!res.ok) throw new Error("Comparison failed");
    const data = await res.json();
    renderComparisonResult(data);
  } catch (err) {
    if (elements.compareResultsContainer) {
      elements.compareResultsContainer.innerHTML = `
        <div style="padding: 1rem; color: var(--risk-critical);">Error: ${err.message}</div>
      `;
    }
  }
}

function renderComparisonResult(data) {
  if (!elements.compareResultsContainer) return;

  elements.compareResultsContainer.innerHTML = `
    <div style="background: var(--bg-card); padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid var(--risk-critical);">
      <h4 style="font-size: 1rem; margin-bottom: 0.35rem;">VERDICT & SUMMARY</h4>
      <p style="font-size: 0.85rem; color: var(--text-primary); margin-bottom: 0.5rem;">${escapeHtml(data.verdict)}</p>
      <ul style="padding-left: 1.25rem; font-size: 0.8rem; color: var(--text-secondary);">
        ${data.key_takeaways.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}
      </ul>
    </div>

    <table class="data-table" aria-label="Contract Side-by-Side Comparison Diff">
      <thead>
        <tr>
          <th>Category</th>
          <th>${escapeHtml(data.doc1_name)}</th>
          <th>${escapeHtml(data.doc2_name)}</th>
          <th>Risk Shift</th>
          <th>Analysis</th>
        </tr>
      </thead>
      <tbody>
        ${data.differences
          .map(
            (d) => `
          <tr>
            <td><strong>${escapeHtml(d.category)}</strong></td>
            <td style="font-size: 0.8rem;">${escapeHtml(d.doc1_snippet)}</td>
            <td style="font-size: 0.8rem;">${escapeHtml(d.doc2_snippet)}</td>
            <td>
              <span class="severity-tag ${
                d.risk_shift === "CRITICAL_RISK_ADDED"
                  ? "tag-CRITICAL"
                  : d.risk_shift === "MORE_FAVORABLE_DOC1"
                  ? "tag-MEDIUM"
                  : "tag-LOW"
              }">
                ${d.risk_shift.replace(/_/g, " ")}
              </span>
            </td>
            <td style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(d.explanation)}</td>
          </tr>
        `
          )
          .join("")}
      </tbody>
    </table>
  `;

  announce("Comparison analysis complete.");
}

// Lawyer Consultation Brief Modal
elements.openBriefBtn?.addEventListener("click", async () => {
  if (!state.currentDocumentId) return;

  if (elements.briefContent) {
    elements.briefContent.innerHTML = "Generating 1-Page Attorney Consultation Packet...";
  }
  if (elements.lawyerBriefModal) {
    elements.lawyerBriefModal.style.display = "flex";
  }

  try {
    const res = await fetch("/api/lawyer-brief", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_id: state.currentDocumentId,
        user_notes: "Pre-signature review focusing on notice period, post-termination non-compete, and intellectual property ownership.",
      }),
    });

    if (!res.ok) throw new Error("Failed to generate brief");
    const data = await res.json();

    if (elements.briefContent) {
      elements.briefContent.innerHTML = `
        <div style="display: flex; justify-content: space-between; border-bottom: 2px solid var(--border-color); padding-bottom: 0.75rem; margin-bottom: 1rem;">
          <div>
            <h2 style="font-size: 1.25rem;">LEGAL CONSULTATION BRIEFING PACKET</h2>
            <div style="font-size: 0.8rem; color: var(--text-muted);">${data.document_title} • ${data.document_type}</div>
          </div>
          <div style="text-align: right; font-size: 0.8rem; color: var(--text-muted);">
            <div>${data.generated_date}</div>
            <div style="color: var(--accent-blue);">JurisLens AI (Gemini 2.5)</div>
          </div>
        </div>

        <section style="margin-bottom: 1.25rem;">
          <h4 style="color: var(--accent-blue); font-size: 0.95rem; margin-bottom: 0.35rem;">1. HIGH-PRIORITY RISK CLAUSES FOR ATTORNEY REVIEW</h4>
          <table class="data-table" style="font-size: 0.8rem;">
            <thead>
              <tr>
                <th>Clause</th>
                <th>Risk</th>
                <th>Client Vulnerability</th>
                <th>Recommended Stance</th>
              </tr>
            </thead>
            <tbody>
              ${data.top_risks_for_review
                .map(
                  (r) => `
                <tr>
                  <td><strong>${escapeHtml(r.clause)}</strong></td>
                  <td><span class="severity-tag tag-${r.severity}">${r.severity}</span></td>
                  <td>${escapeHtml(r.risk)}</td>
                  <td>${escapeHtml(r.action)}</td>
                </tr>
              `
                )
                .join("")}
            </tbody>
          </table>
        </section>

        <section style="margin-bottom: 1.25rem;">
          <h4 style="color: var(--risk-medium); font-size: 0.95rem; margin-bottom: 0.35rem;">2. CRITICAL CONTRACTUAL OMISSIONS & SILENCES</h4>
          <ul style="padding-left: 1.25rem; font-size: 0.85rem; line-height: 1.6;">
            ${data.critical_omissions.map((o) => `<li>${escapeHtml(o)}</li>`).join("")}
          </ul>
        </section>

        <section style="margin-bottom: 1.25rem;">
          <h4 style="color: var(--accent-blue); font-size: 0.95rem; margin-bottom: 0.35rem;">3. DIRECT QUESTIONS FOR COUNSEL</h4>
          <ol style="padding-left: 1.25rem; font-size: 0.85rem; line-height: 1.8;">
            ${data.prepared_questions_for_counsel.map((q) => `<li><strong>${escapeHtml(q)}</strong></li>`).join("")}
          </ol>
        </section>

        <div style="font-size: 0.75rem; color: var(--text-muted); border-top: 1px solid var(--border-color); padding-top: 0.75rem; margin-top: 1rem;">
          ${escapeHtml(data.disclaimer)}
        </div>
      `;
    }
  } catch (err) {
    if (elements.briefContent) {
      elements.briefContent.innerHTML = `<p style="color: var(--risk-critical);">Error: ${err.message}</p>`;
    }
  }
});

elements.closeBriefBtn?.addEventListener("click", () => {
  if (elements.lawyerBriefModal) elements.lawyerBriefModal.style.display = "none";
});

// Close modal on Escape key
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && elements.lawyerBriefModal?.style.display === "flex") {
    elements.lawyerBriefModal.style.display = "none";
  }
});

// Copy Brief to Clipboard
elements.copyBriefBtn?.addEventListener("click", () => {
  if (elements.briefContent) {
    navigator.clipboard.writeText(elements.briefContent.innerText);
    announce("Attorney briefing packet copied to clipboard!");
    alert("Attorney briefing packet copied to clipboard!");
  }
});

// Helper: HTML Escaping
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Switch main feature (e.g. show comparison section)
window.switchMainFeature = function (feature) {
  const compareSection = document.getElementById("compare-section");
  if (feature === "compare" && compareSection) {
    compareSection.style.display = "block";
    compareSection.scrollIntoView({ behavior: "smooth" });
    if (elements.loadCompareSamplesBtn) {
      elements.loadCompareSamplesBtn.click();
    }
  }
};

// Global initialization
document.addEventListener("DOMContentLoaded", () => {
  fetchSamples();
});
