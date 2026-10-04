// TrustLens Popup Interface Controller
document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const loadingState = document.getElementById("loadingState");
  const resultCard = document.getElementById("resultCard");
  const errorState = document.getElementById("errorState");
  const errorMessage = document.getElementById("errorMessage");
  const rescanBtn = document.getElementById("rescanBtn");
  const retryBtn = document.getElementById("retryBtn");
  const backendStatusText = document.getElementById("backendStatusText");
  const backendStatusPill = document.getElementById("backendStatusPill");

  // Verdict Elements
  const verdictBanner = document.getElementById("verdictBanner");
  const verdictTitle = document.getElementById("verdictTitle");
  const confidenceBadge = document.getElementById("confidenceBadge");
  const verdictSummary = document.getElementById("verdictSummary");

  // Claim vs Appearance Elements
  const cvaClaimValue = document.getElementById("cvaClaimValue");
  const cvaClaimConfidence = document.getElementById("cvaClaimConfidence");
  const cvaVisualValue = document.getElementById("cvaVisualValue");
  const cvaModelMatch = document.getElementById("cvaModelMatch");
  const cvaPriceValue = document.getElementById("cvaPriceValue");
  const cvaPriceSub = document.getElementById("cvaPriceSub");
  const ruleText = document.getElementById("ruleText");

  // Risk & Advisor Elements
  const riskSection = document.getElementById("riskSection");
  const riskTags = document.getElementById("riskTags");
  const advisorSection = document.getElementById("advisorSection");
  const evidenceList = document.getElementById("evidenceList");
  const evidenceTypeSelect = document.getElementById("evidenceTypeSelect");
  const evidenceFileInput = document.getElementById("evidenceFileInput");
  const submitEvidenceBtn = document.getElementById("submitEvidenceBtn");

  // Current active payload cache for re-scoring
  let activeListingPayload = null;

  // Viva Demo Presets
  const DEMO_PRESETS = {
    auth: {
      url: "https://www.nike.com/t/air-jordan-1-retro-high-og-chicago",
      title: "Nike Air Jordan 1 Retro High OG 'Chicago' 2022 Men's Basketball Shoe",
      price: 180.0,
      currency: "USD",
      brand_claimed: "Nike",
      seller_name: "Nike Official Store",
      seller_rating: 99.4,
      seller_reviews_count: 8900,
      image_urls: ["https://example.com/aj1-chicago.jpg"]
    },
    fake: {
      url: "https://discountshoes-surplus.com/item/jordan1-chicago-deal",
      title: "HOT AIR JORDAN 1 RETRO HIGH CHICAGO TOP GRADE 1:1 REPLICA",
      price: 38.0,
      currency: "USD",
      brand_claimed: "Nike",
      seller_name: "WholesaleSurplus_Direct",
      seller_rating: 64.0,
      seller_reviews_count: 12,
      image_urls: ["https://example.com/aj1-fake.jpg"]
    },
    lookalike: {
      url: "https://www.amazon.com/dp/B0006A74X8",
      title: "Invicta Men's Pro Diver Automatic 40mm Stainless Steel Black Dial Watch",
      price: 85.0,
      currency: "USD",
      brand_claimed: "Invicta", // Homage without claiming Rolex
      seller_name: "Invicta Official Direct",
      seller_rating: 96.8,
      seller_reviews_count: 14200,
      image_urls: ["https://example.com/invicta-diver.jpg"]
    },
    uncertain: {
      url: "https://estate-liquidators.com/item/vintage-court-shoe-9",
      title: "Vintage White Court Low Sneaker Men's Size 9.5 As-Is",
      price: 65.0,
      currency: "USD",
      brand_claimed: null,
      seller_name: "EstateSeller42",
      seller_rating: 79.0,
      image_urls: [] // Missing image creates ambiguity
    }
  };

  // Wire preset buttons
  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pKey = btn.getAttribute("data-preset");
      if (DEMO_PRESETS[pKey]) {
        analyzeListing(DEMO_PRESETS[pKey]);
      }
    });
  });

  // Health check
  function checkBackendHealth() {
    fetch("http://localhost:8000/health")
      .then((res) => res.json())
      .then((data) => {
        backendStatusText.textContent = "Online";
        backendStatusPill.style.color = "#34d399";
      })
      .catch(() => {
        backendStatusText.textContent = "Offline";
        backendStatusPill.style.color = "#f43f5e";
        backendStatusPill.style.borderColor = "rgba(244, 63, 94, 0.4)";
      });
  }

  // Trigger DOM extraction from active tab with programmatic injection fallback
  function triggerPageScan() {
    showLoading();

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || tabs.length === 0) {
        analyzeListing(DEMO_PRESETS.auth);
        return;
      }

      const activeTab = tabs[0];
      // If browsing an internal chrome:// page, load default demo
      if (!activeTab.url || activeTab.url.startsWith("chrome://") || activeTab.url.startsWith("edge://")) {
        analyzeListing(DEMO_PRESETS.auth);
        return;
      }

      function attemptExtraction(retryOnFail = true) {
        chrome.tabs.sendMessage(activeTab.id, { action: "EXTRACT_PAGE_DATA" }, (response) => {
          if (chrome.runtime.lastError || !response || !response.success) {
            if (retryOnFail) {
              // Programmatically inject content.js if the tab was loaded before the extension
              chrome.scripting.executeScript(
                {
                  target: { tabId: activeTab.id },
                  files: ["content.js"]
                },
                () => {
                  if (chrome.runtime.lastError) {
                    fallbackToMetadata();
                  } else {
                    setTimeout(() => attemptExtraction(false), 150);
                  }
                }
              );
            } else {
              fallbackToMetadata();
            }
            return;
          }

          analyzeListing(response.data);
        });
      }

      function fallbackToMetadata() {
        analyzeListing({
          url: activeTab.url,
          title: activeTab.title || "Product Listing",
          price: null,
          currency: "USD",
          brand_claimed: null,
          image_urls: []
        });
      }

      attemptExtraction(true);
    });
  }

  // Send payload to backend
  function analyzeListing(payload) {
    showLoading();
    activeListingPayload = payload;

    fetch("http://localhost:8000/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Backend error: HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        renderResult(data);
      })
      .catch((err) => {
        showError(err.message);
      });
  }

  // Render classification & novelty features
  function renderResult(data) {
    loadingState.classList.add("hidden");
    errorState.classList.add("hidden");
    resultCard.classList.remove("hidden");

    // Scanned info header
    const scannedTitle = document.getElementById("scannedTitle");
    const scannedSourceBadge = document.getElementById("scannedSourceBadge");
    if (scannedTitle && activeListingPayload) {
      scannedTitle.textContent = activeListingPayload.title || "Product Listing";
      if (activeListingPayload.is_search_page) {
        scannedSourceBadge.textContent = "Search Grid (Top Item)";
        scannedSourceBadge.style.color = "#f59e0b";
      } else {
        scannedSourceBadge.textContent = "Product Detail Page";
        scannedSourceBadge.style.color = "#38bdf8";
      }
    }

    verdictTitle.textContent = data.classification;
    confidenceBadge.textContent = `${Math.round(data.confidence * 100)}% Confidence`;
    verdictSummary.textContent = data.explanation_summary;

    // Styling based on 4 target classes
    if (data.classification === "Likely Authentic") {
      verdictBanner.style.background = "linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.02))";
      verdictBanner.style.borderColor = "rgba(16, 185, 129, 0.4)";
      verdictTitle.style.color = "var(--verdict-auth)";
    } else if (data.classification === "Potential Counterfeit") {
      verdictBanner.style.background = "linear-gradient(135deg, rgba(244, 63, 94, 0.15), rgba(244, 63, 94, 0.02))";
      verdictBanner.style.borderColor = "rgba(244, 63, 94, 0.4)";
      verdictTitle.style.color = "var(--verdict-fake)";
    } else if (data.classification === "Legitimate Look-alike") {
      verdictBanner.style.background = "linear-gradient(135deg, rgba(6, 182, 212, 0.15), rgba(6, 182, 212, 0.02))";
      verdictBanner.style.borderColor = "rgba(6, 182, 212, 0.4)";
      verdictTitle.style.color = "var(--accent-cyan)";
    } else {
      verdictBanner.style.background = "linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(245, 158, 11, 0.02))";
      verdictBanner.style.borderColor = "rgba(245, 158, 11, 0.4)";
      verdictTitle.style.color = "var(--verdict-uncertain)";
    }

    // Novelty A: Claim vs Appearance
    const cva = data.claim_vs_appearance;
    cvaClaimValue.textContent = cva.claims_brand ? "Claimed" : "Unclaimed";
    cvaClaimValue.style.color = cva.claims_brand ? "var(--verdict-auth)" : "var(--accent-blue)";
    cvaClaimConfidence.textContent = `${Math.round(cva.claim_confidence * 100)}% claim score`;

    cvaVisualValue.textContent = `${Math.round(cva.visual_similarity * 100)}%`;
    cvaVisualValue.style.color = cva.looks_similar ? "var(--verdict-auth)" : "var(--verdict-uncertain)";
    cvaModelMatch.textContent = cva.matched_model_id ? `Ref: ${cva.matched_model_id.replace(/_/g, " ")}` : "No direct match";

    const priceSignal = data.risk_signals.find((s) => s.signal_name.toLowerCase().includes("price"));
    if (priceSignal && priceSignal.value !== undefined) {
      cvaPriceValue.textContent = `${priceSignal.value}`;
      cvaPriceValue.style.color = priceSignal.severity === "high" ? "var(--verdict-fake)" : "var(--text-primary)";
      cvaPriceSub.textContent = priceSignal.severity === "high" ? "Severe discount" : "Within range";
    } else {
      cvaPriceValue.textContent = "Normal";
      cvaPriceSub.textContent = "Market range";
    }

    ruleText.textContent = cva.rule_applied;

    // Risk Flags
    if (data.risk_signals && data.risk_signals.length > 0) {
      riskSection.classList.remove("hidden");
      riskTags.innerHTML = data.risk_signals
        .map(
          (sig) => `
        <div class="risk-pill">
          <span class="risk-pill-title">&#x26A0;&#xFE0F; ${sig.signal_name}</span>
          <span class="risk-pill-desc">${sig.description}</span>
        </div>
      `
        )
        .join("");
    } else {
      riskSection.classList.add("hidden");
    }

    // Novelty B: Evidence-Gap Advisor
    if (data.is_uncertain && data.evidence_checklist && data.evidence_checklist.length > 0) {
      advisorSection.classList.remove("hidden");
      evidenceList.innerHTML = data.evidence_checklist
        .map(
          (item, idx) => `
        <div class="evidence-card">
          <div class="evidence-card-header">
            <span class="evidence-title">#${idx + 1} ${item.label}</span>
            <span class="evidence-drop">+${Math.round(item.expected_uncertainty_reduction * 100)}% Certainty</span>
          </div>
          <p class="evidence-desc">${item.rationale}</p>
        </div>
      `
        )
        .join("");
    } else {
      advisorSection.classList.add("hidden");
    }
  }

  // Handle Missing Evidence Upload & Re-Score
  submitEvidenceBtn.addEventListener("click", () => {
    if (!activeListingPayload) return;

    const evidenceType = evidenceTypeSelect.value;
    const file = evidenceFileInput.files[0];

    const reScorePayload = {
      ...activeListingPayload,
      additional_evidence_type: evidenceType
    };

    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        reScorePayload.uploaded_image_base64 = e.target.result;
        analyzeListing(reScorePayload);
      };
      reader.readAsDataURL(file);
    } else {
      // Re-score based on evidence type declaration
      reScorePayload.uploaded_image_base64 = "simulated_evidence_data";
      analyzeListing(reScorePayload);
    }
  });

  function showLoading() {
    loadingState.classList.remove("hidden");
    resultCard.classList.add("hidden");
    errorState.classList.add("hidden");
  }

  function showError(msg) {
    loadingState.classList.add("hidden");
    resultCard.classList.add("hidden");
    errorState.classList.remove("hidden");
    errorMessage.textContent = msg;
  }

  rescanBtn.addEventListener("click", triggerPageScan);
  retryBtn.addEventListener("click", triggerPageScan);

  // Initialize
  checkBackendHealth();
  triggerPageScan();
});
