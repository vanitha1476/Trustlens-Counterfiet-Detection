/**
 * TrustLens Popup Controller v2.0
 *
 * Architecture:
 *   1. On open → send GET_SCAN_RESULT to background to load CACHED result.
 *   2. If cached  → render traffic light immediately (instant, zero extra fetch).
 *   3. If no cache → trigger a fresh EXTRACT_PAGE_DATA + ANALYZE_PRODUCT scan.
 *   4. Demo presets bypass the cache and call the backend directly (for judges).
 *
 * NO jargon is shown in the default traffic light view.
 * ML detail (Claim vs Appearance, Risk Signals, Evidence Advisor) is in the
 * collapsible "View AI Analysis Details" section below.
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {

  // ─── Element refs ────────────────────────────────────
  const statusDot      = document.getElementById("statusDot");
  const statusText     = document.getElementById("statusText");

  const tlLoading      = document.getElementById("tl-loading");
  const tlResult       = document.getElementById("tl-result");
  const tlRing         = document.getElementById("tlRing");
  const tlHeadline     = document.getElementById("tlHeadline");
  const tlSub          = document.getElementById("tlSub");

  const scannedBar     = document.getElementById("scannedBar");
  const scannedTitle   = document.getElementById("scannedTitle");
  const scannedBadge   = document.getElementById("scannedBadge");

  const detailsToggle  = document.getElementById("detailsToggle");
  const detailsPanel   = document.getElementById("details-panel");

  const cvaClaim       = document.getElementById("cvaClaim");
  const cvaClaimConf   = document.getElementById("cvaClaimConf");
  const cvaVisual      = document.getElementById("cvaVisual");
  const cvaModel       = document.getElementById("cvaModel");
  const cvaPrice       = document.getElementById("cvaPrice");
  const cvaPriceSub    = document.getElementById("cvaPriceSub");
  const ruleBar        = document.getElementById("ruleBar");

  const riskSection    = document.getElementById("riskSection");
  const riskList       = document.getElementById("riskList");
  const advisorSection = document.getElementById("advisorSection");
  const advisorList    = document.getElementById("advisorList");

  const viewError      = document.getElementById("view-error");
  const errorMsg       = document.getElementById("errorMsg");
  const retryBtn       = document.getElementById("retryBtn");
  const rescanBtn      = document.getElementById("rescanBtn");
  const reportBtn      = document.getElementById("reportBtn");

  const evidenceTypeSelect = document.getElementById("evidenceTypeSelect");
  const evidenceFileInput  = document.getElementById("evidenceFileInput");
  const submitEvidenceBtn  = document.getElementById("submitEvidenceBtn");

  // ─── State ───────────────────────────────────────────
  let activePayload = null; // Raw scraped data for re-scoring

  // ─── Demo Presets (for live hackathon demo) ───────────
  const DEMO_PRESETS = {
    auth: {
      url: "https://www.nike.com/t/air-jordan-1-retro-high-og-chicago",
      title: "Nike Air Jordan 1 Retro High OG 'Chicago' Men's Basketball Shoe",
      price: 180.0, currency: "USD",
      brand_claimed: "Nike",
      seller_name: "Nike Official Store", seller_rating: 99.4, seller_reviews_count: 8900,
      image_urls: ["https://example.com/aj1-chicago.jpg"]
    },
    fake: {
      url: "https://discountshoes-surplus.com/item/jordan1-chicago-deal",
      title: "HOT AIR JORDAN 1 RETRO HIGH CHICAGO TOP GRADE 1:1 REPLICA",
      price: 38.0, currency: "USD",
      brand_claimed: "Nike",
      seller_name: "WholesaleSurplus_Direct", seller_rating: 64.0, seller_reviews_count: 12,
      image_urls: ["https://example.com/aj1-fake.jpg"]
    },
    lookalike: {
      url: "https://www.amazon.com/dp/B0006A74X8",
      title: "Invicta Men's Pro Diver Automatic 40mm Stainless Steel Black Dial Watch",
      price: 85.0, currency: "USD",
      brand_claimed: "Invicta",
      seller_name: "Invicta Official Direct", seller_rating: 96.8, seller_reviews_count: 14200,
      image_urls: ["https://example.com/invicta-diver.jpg"]
    },
    uncertain: {
      url: "https://estate-liquidators.com/item/vintage-court-shoe-9",
      title: "Vintage White Court Low Sneaker Men's Size 9.5 As-Is",
      price: 65.0, currency: "USD",
      brand_claimed: null,
      seller_name: "EstateSeller42", seller_rating: 79.0,
      image_urls: []
    }
  };

  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.getAttribute("data-preset");
      if (DEMO_PRESETS[key]) {
        showLoadingState();
        analyzePayload(DEMO_PRESETS[key]);
      }
    });
  });

  // ─── Backend health check ─────────────────────────────
  function checkHealth() {
    fetch("http://localhost:8000/health")
      .then((r) => r.json())
      .then(() => {
        statusDot.className = "status-dot online";
        statusText.textContent = "AI Online";
      })
      .catch(() => {
        statusDot.className = "status-dot offline";
        statusText.textContent = "Offline";
      });
  }

  // ─── UI State Management ──────────────────────────────
  function showLoadingState() {
    tlLoading.style.display = "flex";
    tlResult.classList.add("hidden");
    viewError.classList.add("hidden");
  }

  function showErrorState(msg) {
    tlLoading.style.display = "none";
    tlResult.classList.add("hidden");
    viewError.classList.remove("hidden");
    errorMsg.textContent = msg || "Unable to connect to the TrustLens AI engine at http://localhost:8000.";
  }

  // ─── Traffic Light Renderer ───────────────────────────
  const TL_CONFIG = {
    GREEN:  { cls: "green",  icon: "✅" },
    YELLOW: { cls: "yellow", icon: "⚠️" },
    RED:    { cls: "red",    icon: "🛑" },
  };

  function renderTrafficLight(verdict, productTitle, isSearchPage) {
    const cfg = TL_CONFIG[verdict.traffic_light] || TL_CONFIG.YELLOW;

    tlLoading.style.display = "none";
    tlResult.classList.remove("hidden");
    viewError.classList.add("hidden");

    // Ring
    tlRing.className = `tl-ring ${cfg.cls}`;
    tlRing.textContent = cfg.icon;

    // Headline + sub (plain English from backend — zero jargon)
    tlHeadline.className = `tl-headline ${cfg.cls}`;
    tlHeadline.textContent = verdict.headline;
    tlSub.textContent = verdict.sub_message;

    // Scanned item bar
    if (productTitle) {
      scannedTitle.textContent = productTitle;
      scannedBadge.textContent = isSearchPage ? "Top result from search page" : "Product detail page";
    } else {
      scannedBar.style.display = "none";
    }
  }

  // ─── Full ML Details Renderer ─────────────────────────
  // Called when we have the full PredictionResponse (not just TrafficLightVerdict)
  function renderDetails(data) {
    const cva = data.claim_vs_appearance;

    // Claim vs Appearance
    cvaClaim.textContent = cva.claims_brand ? "Claimed" : "Unclaimed";
    cvaClaim.style.color = cva.claims_brand ? "var(--green)" : "var(--muted)";
    cvaClaimConf.textContent = `${Math.round(cva.claim_confidence * 100)}% match`;

    cvaVisual.textContent = `${Math.round(cva.visual_similarity * 100)}%`;
    cvaVisual.style.color = cva.looks_similar ? "var(--green)" : "var(--yellow)";
    cvaModel.textContent = cva.matched_model_id
      ? cva.matched_model_id.replace(/_/g, " ")
      : "No direct match";

    const priceSignal = (data.risk_signals || []).find((s) =>
      s.signal_name.toLowerCase().includes("price")
    );
    if (priceSignal && priceSignal.value !== undefined) {
      cvaPrice.textContent = typeof priceSignal.value === "number"
        ? priceSignal.value.toFixed(2)
        : priceSignal.value;
      cvaPrice.style.color = priceSignal.severity === "high" ? "var(--red)" : "var(--text)";
      cvaPriceSub.textContent = priceSignal.severity === "high" ? "Severe discount" : "Within range";
    } else {
      cvaPrice.textContent = "Normal";
      cvaPriceSub.textContent = "Market range";
    }

    ruleBar.textContent = `⚖️ Rule applied: ${cva.rule_applied}`;

    // Risk signals
    if (data.risk_signals && data.risk_signals.length > 0) {
      riskSection.classList.remove("hidden");
      riskList.innerHTML = data.risk_signals.map((s) => `
        <div class="risk-pill ${s.severity}">
          <span class="risk-pill-title">⚠️ ${s.signal_name}</span>
          <span class="risk-pill-desc">${s.description}</span>
        </div>
      `).join("");
    } else {
      riskSection.classList.add("hidden");
    }

    // Evidence-Gap Advisor
    if (data.is_uncertain && data.evidence_checklist && data.evidence_checklist.length > 0) {
      advisorSection.classList.remove("hidden");
      advisorList.innerHTML = data.evidence_checklist.map((item, i) => `
        <div class="evidence-card">
          <div class="evidence-header">
            <span class="evidence-title">#${i + 1} ${item.label}</span>
            <span class="evidence-drop">+${Math.round(item.expected_uncertainty_reduction * 100)}% certainty</span>
          </div>
          <p class="evidence-desc">${item.rationale}</p>
        </div>
      `).join("");
    } else {
      advisorSection.classList.add("hidden");
    }
  }

  // ─── Main Analysis Flow ───────────────────────────────
  function analyzePayload(payload) {
    activePayload = payload;
    chrome.runtime.sendMessage({ action: "ANALYZE_PRODUCT", payload }, (response) => {
      if (chrome.runtime.lastError || !response || !response.success) {
        showErrorState("Could not reach the AI engine. Is the backend running?");
        return;
      }
      const data = response.data;
      if (!data || !data.traffic_light) {
        showErrorState("Backend returned an unexpected response.");
        return;
      }
      renderTrafficLight(data.traffic_light, payload.title, payload.is_search_page);
      renderDetails(data);
    });
  }

  // ─── Primary Startup: Load from cache or trigger scan ─
  function initialize() {
    showLoadingState();

    // Step 1: Get active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || tabs.length === 0) {
        analyzePayload(DEMO_PRESETS.auth);
        return;
      }

      const tab = tabs[0];

      // Internal pages (chrome://, edge://) — show demo
      if (!tab.url || tab.url.startsWith("chrome") || tab.url.startsWith("edge") || tab.url.startsWith("about")) {
        analyzePayload(DEMO_PRESETS.auth);
        return;
      }

      // Step 2: Ask background for cached scan result
      chrome.runtime.sendMessage({ action: "GET_SCAN_RESULT" }, (response) => {
        if (chrome.runtime.lastError) {
          // Background SW is sleeping — fall back to fresh scan
          triggerFreshScan(tab);
          return;
        }

        if (response && response.success && response.result) {
          const cached = response.result;
          // We have a cached result — render it immediately (zero extra latency)
          renderTrafficLight(
            cached.verdict,
            cached.payload?.title || tab.title,
            cached.payload?.is_search_page || false
          );
          // If we also have the full ML details, render those too
          if (cached.full_response) {
            renderDetails(cached.full_response);
          }
        } else {
          // No cache — trigger a fresh extraction + analysis
          triggerFreshScan(tab);
        }
      });
    });
  }

  function triggerFreshScan(tab) {
    // Ask content.js to extract the page
    chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_PAGE_DATA" }, (response) => {
      if (chrome.runtime.lastError || !response || !response.success) {
        // Content script not running yet — inject it programmatically
        chrome.scripting.executeScript(
          { target: { tabId: tab.id }, files: ["content.js"] },
          () => {
            if (chrome.runtime.lastError) {
              // Cannot inject (restricted page) — use tab metadata as fallback
              analyzePayload({ url: tab.url, title: tab.title || "Product", image_urls: [] });
            } else {
              setTimeout(() => {
                chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_PAGE_DATA" }, (r) => {
                  if (r && r.success) {
                    analyzePayload(r.data);
                  } else {
                    analyzePayload({ url: tab.url, title: tab.title || "Product", image_urls: [] });
                  }
                });
              }, 200);
            }
          }
        );
        return;
      }
      analyzePayload(response.data);
    });
  }

  // ─── Evidence Upload & Re-Score ───────────────────────
  submitEvidenceBtn.addEventListener("click", () => {
    if (!activePayload) return;
    const reScorePayload = {
      ...activePayload,
      additional_evidence_type: evidenceTypeSelect.value,
    };
    const file = evidenceFileInput.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        reScorePayload.uploaded_image_base64 = e.target.result;
        showLoadingState();
        analyzePayload(reScorePayload);
      };
      reader.readAsDataURL(file);
    } else {
      reScorePayload.uploaded_image_base64 = "simulated_evidence_data";
      showLoadingState();
      analyzePayload(reScorePayload);
    }
  });

  // ─── Details Collapse Toggle ──────────────────────────
  detailsToggle.addEventListener("click", () => {
    const isOpen = detailsPanel.classList.contains("open");
    detailsPanel.classList.toggle("open", !isOpen);
    detailsToggle.classList.toggle("open", !isOpen);
  });

  // ─── Footer Buttons ───────────────────────────────────
  rescanBtn.addEventListener("click", initialize);
  retryBtn.addEventListener("click", initialize);

  reportBtn.addEventListener("click", () => {
    // Toggle details panel open as a "full report" shortcut
    if (!detailsPanel.classList.contains("open")) {
      detailsPanel.classList.add("open");
      detailsToggle.classList.add("open");
      detailsPanel.scrollIntoView({ behavior: "smooth" });
    }
  });

  // ─── Boot ─────────────────────────────────────────────
  checkHealth();
  initialize();
});
