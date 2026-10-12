// =============================================================
// TrustLens Background Service Worker v2.0 (Manifest V3)
// Orchestrates: Passive Scanning | Payment Interception | Badge | Overlay
// =============================================================
// STRICT MV3 RULES ENFORCED:
//   - No localStorage, sessionStorage, or any DOM API
//   - All state lives in chrome.storage.session (in-memory, tab-keyed)
//   - chrome.action used (NOT chrome.browserAction — that's MV2)
//   - Injected functions are fully self-contained (no closure references)
//   - return true from onMessage keeps ONE async channel open
// =============================================================

"use strict";

// ─────────────────────────────────────────────────────────────
// SECTION 1 — CONFIGURATION
// ─────────────────────────────────────────────────────────────

const BACKEND_URL = "http://localhost:8000";

/**
 * India-first payment gateway URL patterns.
 * ADD new gateways here only — no other code changes needed.
 */
const PAYMENT_GATEWAY_PATTERNS = [
  "phonepe.com",
  "razorpay.com",
  "paytm.com",
  "payu.in",
  "payumoney.com",
  "ccavenue.com",
  "cashfree.com",
  "billdesk.com",
  "juspay.net",
  "juspay.in",
  "easebuzz.in",
  "instamojo.com",
  "gpay.app",
  // International (extensible)
  "paypal.com/checkoutnow",
  "checkout.stripe.com",
];

const BADGE_CONFIG = {
  GREEN:   { text: "✓", color: "#10b981" },
  YELLOW:  { text: "!", color: "#f59e0b" },
  RED:     { text: "✕", color: "#f43f5e" },
  LOADING: { text: "…", color: "#6366f1" },
  DEFAULT: { text: "",  color: "#1e293b" },
};

// ─────────────────────────────────────────────────────────────
// SECTION 2 — UTILITY HELPERS
// ─────────────────────────────────────────────────────────────

/** Returns true if the URL belongs to a known payment gateway. */
function isPaymentGateway(url) {
  if (!url) return false;
  const lower = url.toLowerCase();
  return PAYMENT_GATEWAY_PATTERNS.some((pattern) => lower.includes(pattern));
}

/** Returns true if the URL is a browser internal page we cannot inject into. */
function isInternalUrl(url) {
  if (!url) return true;
  return (
    url.startsWith("chrome://") ||
    url.startsWith("chrome-extension://") ||
    url.startsWith("about:") ||
    url.startsWith("edge://") ||
    url.startsWith("moz-extension://")
  );
}

/** Storage key scoped to a specific tab. */
function storageKey(tabId) {
  return `trustlens_scan_${tabId}`;
}

/**
 * Persist the scan result for a tab.
 * Uses chrome.storage.session (MV3, in-memory, cleared on browser restart).
 * @param {number} tabId
 * @param {Object} result - { verdict: TrafficLightVerdict, payload, timestamp, scanned_url }
 */
async function storeResult(tabId, result) {
  await chrome.storage.session.set({ [storageKey(tabId)]: result });
}

/** Retrieve the stored scan result for a tab. Returns null if none. */
async function getResult(tabId) {
  const data = await chrome.storage.session.get(storageKey(tabId));
  return data[storageKey(tabId)] || null;
}

/** Remove the stored scan result for a tab (e.g., on new page navigation). */
async function clearResult(tabId) {
  await chrome.storage.session.remove(storageKey(tabId));
}

/** Set the extension badge for a specific tab. */
function setBadge(tabId, state) {
  const cfg = BADGE_CONFIG[state] || BADGE_CONFIG.DEFAULT;
  chrome.action.setBadgeText({ text: cfg.text, tabId });
  chrome.action.setBadgeBackgroundColor({ color: cfg.color, tabId });
}

// ─────────────────────────────────────────────────────────────
// SECTION 3 — BACKEND COMMUNICATION
// ─────────────────────────────────────────────────────────────

/**
 * POST to /predict (full ML pipeline with MC-Dropout).
 * Called by the passive scanner after page load.
 * Returns the traffic_light field from the PredictionResponse.
 */
async function callPredict(payload) {
  const res = await fetch(`${BACKEND_URL}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`/predict returned HTTP ${res.status}`);
  const data = await res.json();
  return data; // Full PredictionResponse including data.traffic_light
}

/**
 * POST to /quick-scan (fast path, skips MC-Dropout).
 * Called when user hits a payment page without a prior scan cached.
 * Returns a TrafficLightVerdict directly.
 */
async function callQuickScan(payload) {
  const res = await fetch(`${BACKEND_URL}/quick-scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`/quick-scan returned HTTP ${res.status}`);
  return await res.json(); // TrafficLightVerdict
}

// ─────────────────────────────────────────────────────────────
// SECTION 4 — PASSIVE SCANNER
// ─────────────────────────────────────────────────────────────

/**
 * Runs silently in the background after content.js sends PAGE_LOADED.
 * Calls /predict, stores the result, updates the badge.
 * User sees nothing — this is fully zero-click.
 */
async function runPassiveScan(tabId, payload) {
  setBadge(tabId, "LOADING");
  try {
    const data = await callPredict(payload);
    const verdict = data.traffic_light;

    if (!verdict) {
      console.warn("[TrustLens] /predict returned no traffic_light field.");
      setBadge(tabId, "DEFAULT");
      return;
    }

    await storeResult(tabId, {
      verdict,          // TrafficLightVerdict — drives badge, overlay, popup
      payload,          // Raw scraped data — available for popup's detail view
      full_response: data, // Full PredictionResponse — for popup's advanced view
      timestamp: Date.now(),
    });

    setBadge(tabId, verdict.traffic_light);
    console.log(`[TrustLens] Tab ${tabId} scanned → ${verdict.traffic_light}`);
  } catch (err) {
    console.error("[TrustLens] Passive scan failed:", err.message);
    setBadge(tabId, "DEFAULT");
  }
}

// ─────────────────────────────────────────────────────────────
// SECTION 5 — OVERLAY INJECTION ENGINE
// ─────────────────────────────────────────────────────────────

/**
 * Injects the warning overlay into a tab.
 * @param {number} tabId - Target tab
 * @param {Object|null} verdict - TrafficLightVerdict. Null = show loading state.
 * @param {boolean} isLoading - If true, renders spinner instead of verdict.
 */
async function injectOverlay(tabId, verdict, isLoading = false) {
  try {
    // Step 1: Inject host-page CSS (scroll-lock + stacking context anchor).
    // chrome.scripting.insertCSS deduplicates — safe to call multiple times.
    await chrome.scripting.insertCSS({
      target: { tabId, allFrames: false },
      files: ["overlay.css"],
    });

    // Step 2: Plant the verdict JSON into a data-carrier <div> so that
    // overlay.js (when injected as a file) can read it without needing
    // closure access to background.js scope.
    await chrome.scripting.executeScript({
      target: { tabId, allFrames: false },
      func: _plantVerdictData,
      args: [verdict, isLoading],
    });

    // Step 3: Inject overlay.js as a file — it reads the data carrier
    // and renders the full Shadow DOM warning UI.
    await chrome.scripting.executeScript({
      target: { tabId, allFrames: false },
      files: ["overlay.js"],
    });
  } catch (err) {
    // Tab is navigating, restricted, or already has the overlay. Safe to ignore.
    console.warn("[TrustLens] Overlay injection skipped:", err.message);
  }
}

/**
 * Planted into the page BEFORE overlay.js is injected.
 * Creates a hidden <div id="tl-overlay-root-data"> that carries the verdict
 * JSON as a data attribute. overlay.js reads and removes this element.
 *
 * MUST be 100% self-contained — no outer-scope references.
 * @param {Object|null} verdict
 * @param {boolean}     isLoading
 */
function _plantVerdictData(verdict, isLoading) {
  // Remove any stale carrier from a previous injection cycle
  const stale = document.getElementById("tl-overlay-root-data");
  if (stale) stale.remove();

  const carrier = document.createElement("div");
  carrier.id = "tl-overlay-root-data";
  try {
    carrier.dataset.tlVerdict = JSON.stringify(verdict);
  } catch (_) {
    carrier.dataset.tlVerdict = "null";
  }
  carrier.dataset.tlLoading = String(Boolean(isLoading));
  document.documentElement.appendChild(carrier);
}

/**
 * Removes the overlay from a tab (e.g., before re-injecting with a real result).
 */
async function removeOverlay(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId, allFrames: false },
      func: () => {
        const root = document.getElementById("tl-overlay-root");
        if (root) root.remove();
      },
      args: [],
    });
  } catch (_) { /* Tab may have navigated — ignore */ }
}

/**
 * ═══════════════════════════════════════════════════════════════
 * INJECTED FUNCTION — buildAndMountOverlay
 * ═══════════════════════════════════════════════════════════════
 * This function is SERIALISED by chrome.scripting.executeScript
 * and re-evaluated inside the page's JavaScript context.
 *
 * ABSOLUTE RULES for this function:
 *   1. NO references to any outer scope variables (BACKEND_URL, etc.)
 *   2. ALL data comes from the `verdict` and `isLoading` parameters
 *   3. Uses Shadow DOM (mode: "closed") — host page CSS cannot leak in
 *   4. Checks for existing overlay to prevent double-injection
 * ═══════════════════════════════════════════════════════════════
 *
 * @param {Object|null} verdict  - TrafficLightVerdict from backend
 * @param {boolean}     isLoading - True = show spinner, not verdict
 */
function buildAndMountOverlay(verdict, isLoading) {
  // ── Guard: prevent double injection ──────────────────────────
  if (document.getElementById("tl-overlay-root")) return;

  // ── Theme config based on traffic light state ─────────────────
  const THEMES = {
    GREEN:   { bg: "#022c1c", border: "#10b981", accent: "#10b981", glow: "#10b98130", icon: "✅", label: "SAFE" },
    YELLOW:  { bg: "#2c1a00", border: "#f59e0b", accent: "#f59e0b", glow: "#f59e0b30", icon: "⚠️", label: "CAUTION" },
    RED:     { bg: "#2c0010", border: "#f43f5e", accent: "#f43f5e", glow: "#f43f5e30", icon: "🛑", label: "HIGH RISK" },
    LOADING: { bg: "#0d0f1f", border: "#6366f1", accent: "#6366f1", glow: "#6366f130", icon: "🔍", label: "SCANNING" },
  };

  const state = isLoading ? "LOADING" : (verdict && verdict.traffic_light ? verdict.traffic_light : "YELLOW");
  const t = THEMES[state] || THEMES.YELLOW;

  const headline   = isLoading ? "TrustLens is checking this store…"         : (verdict && verdict.headline    || "Hold on — we're checking this.");
  const subMessage = isLoading ? "Don't enter your payment details just yet." : (verdict && verdict.sub_message || "");
  const shouldBlock = !isLoading && state !== "GREEN";

  // ── Build host element + closed Shadow DOM ───────────────────
  const host = document.createElement("div");
  host.id = "tl-overlay-root";
  document.body.appendChild(host);
  const shadow = host.attachShadow({ mode: "closed" });

  // ── Inline styles (scoped inside shadow) ─────────────────────
  const css = `
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :host { all: initial; }

    #tl-overlay {
      position: fixed;
      inset: 0;
      z-index: 2147483647;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(2, 4, 12, 0.88);
      backdrop-filter: blur(16px) saturate(0.6);
      -webkit-backdrop-filter: blur(16px) saturate(0.6);
      animation: tl-fadein 0.35s cubic-bezier(0.16,1,0.3,1);
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    }

    @keyframes tl-fadein {
      from { opacity: 0; transform: scale(0.97); }
      to   { opacity: 1; transform: scale(1); }
    }

    @keyframes tl-pulse {
      0%, 100% { box-shadow: 0 0 0 0 ${t.glow}, 0 32px 64px rgba(0,0,0,0.6); }
      50%       { box-shadow: 0 0 0 20px transparent, 0 32px 64px rgba(0,0,0,0.6); }
    }

    @keyframes tl-spin {
      to { transform: rotate(360deg); }
    }

    @keyframes tl-blink {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.4; }
    }

    #tl-card {
      background: ${t.bg};
      border: 1.5px solid ${t.border};
      border-radius: 24px;
      padding: 48px;
      max-width: 540px;
      width: calc(100vw - 40px);
      text-align: center;
      color: #f1f5f9;
      position: relative;
      animation: tl-pulse 2.4s ease-in-out infinite;
    }

    #tl-label {
      display: inline-block;
      background: ${t.glow};
      border: 1px solid ${t.border}80;
      border-radius: 100px;
      padding: 5px 14px;
      font-size: 10px;
      font-weight: 700;
      color: ${t.accent};
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 20px;
    }

    #tl-icon {
      font-size: 60px;
      line-height: 1;
      display: block;
      margin-bottom: 20px;
    }

    #tl-headline {
      font-size: 22px;
      font-weight: 800;
      color: ${t.accent};
      line-height: 1.35;
      margin-bottom: 12px;
    }

    #tl-sub {
      font-size: 14.5px;
      color: #94a3b8;
      line-height: 1.65;
      margin-bottom: 32px;
    }

    #tl-spinner {
      width: 44px;
      height: 44px;
      border: 3px solid ${t.border}30;
      border-top-color: ${t.accent};
      border-radius: 50%;
      animation: tl-spin 0.75s linear infinite;
      margin: 0 auto 32px;
    }

    #tl-scanning-text {
      font-size: 13px;
      color: ${t.accent};
      animation: tl-blink 1.2s ease-in-out infinite;
      margin-bottom: 8px;
    }

    .tl-btn-primary {
      display: block;
      width: 100%;
      background: ${t.accent};
      color: #020c0e;
      border: none;
      border-radius: 14px;
      padding: 15px 24px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      transition: opacity 0.2s, transform 0.1s;
      margin-bottom: 12px;
      letter-spacing: 0.01em;
    }
    .tl-btn-primary:hover  { opacity: 0.88; transform: translateY(-1px); }
    .tl-btn-primary:active { transform: translateY(0); }

    #tl-confirm-row {
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
    }

    #tl-confirm-input {
      flex: 1;
      min-width: 0;
      background: #0f172a;
      border: 1.5px solid #1e293b;
      border-radius: 10px;
      padding: 11px 14px;
      color: #f1f5f9;
      font-size: 13px;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s;
    }
    #tl-confirm-input::placeholder { color: #334155; }
    #tl-confirm-input:focus { border-color: ${t.accent}80; }

    #tl-btn-continue {
      background: #0f172a;
      color: #334155;
      border: 1.5px solid #1e293b;
      border-radius: 10px;
      padding: 11px 16px;
      font-size: 13px;
      font-family: inherit;
      cursor: not-allowed;
      transition: all 0.2s;
      white-space: nowrap;
    }
    #tl-btn-continue.unlocked {
      color: #cbd5e1;
      border-color: #334155;
      cursor: pointer;
    }
    #tl-btn-continue.unlocked:hover { background: #1e293b; }

    #tl-hint {
      font-size: 11.5px;
      color: #334155;
      text-align: center;
    }

    #tl-footer {
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #1e293b;
      font-size: 11px;
      color: #334155;
      letter-spacing: 0.03em;
    }
  `;

  // ── HTML structure ────────────────────────────────────────────
  const html = `
    <style>${css}</style>
    <div id="tl-overlay">
      <div id="tl-card">

        <div id="tl-label">TrustLens Safety Shield</div>
        <span id="tl-icon">${t.icon}</span>
        <h2 id="tl-headline">${headline}</h2>
        <p id="tl-sub">${subMessage}</p>

        ${isLoading ? `
          <div id="tl-spinner"></div>
          <p id="tl-scanning-text">Analysing seller…</p>
        ` : `
          <button class="tl-btn-primary" id="tl-btn-back">← Go Back to Safety</button>

          ${shouldBlock ? `
            <div id="tl-confirm-row">
              <input
                id="tl-confirm-input"
                type="text"
                placeholder='Type "I UNDERSTAND" to continue anyway'
                autocomplete="off"
                spellcheck="false"
              />
              <button id="tl-btn-continue" disabled>Continue</button>
            </div>
            <p id="tl-hint">We strongly advise you not to proceed with this payment.</p>
          ` : ``}
        `}

        <div id="tl-footer">TRUSTLENS v2.0 &nbsp;·&nbsp; Powered by AI &nbsp;·&nbsp; Your Shopping Bodyguard</div>

      </div>
    </div>
  `;

  shadow.innerHTML = html;

  // ── Event listeners (all within the serialised function scope) ─

  // Back button — dismiss overlay and go back in browser history
  const backBtn = shadow.getElementById("tl-btn-back");
  if (backBtn) {
    backBtn.addEventListener("click", () => {
      host.remove();
      window.history.back();
    });
  }

  // "I UNDERSTAND" typing unlock — enables the continue button
  const confirmInput  = shadow.getElementById("tl-confirm-input");
  const continueBtn   = shadow.getElementById("tl-btn-continue");
  if (confirmInput && continueBtn) {
    confirmInput.addEventListener("input", () => {
      const ready = confirmInput.value.trim().toUpperCase() === "I UNDERSTAND";
      continueBtn.disabled = !ready;
      continueBtn.classList.toggle("unlocked", ready);
    });
    continueBtn.addEventListener("click", () => {
      if (!continueBtn.disabled) host.remove();
    });
  }
}

// ─────────────────────────────────────────────────────────────
// SECTION 6 — PAYMENT INTERCEPTION LOGIC
// ─────────────────────────────────────────────────────────────

/**
 * Called when browser navigates to (and completes loading of) a payment URL.
 * Decision tree:
 *   CACHED GREEN  → do nothing (safe)
 *   CACHED YELLOW/RED → inject full warning overlay immediately
 *   NOT CACHED    → inject generic caution overlay (unscanned store)
 */
async function handlePaymentNavigation(tabId, url) {
  if (isInternalUrl(url)) return;

  const cached = await getResult(tabId);

  if (cached && cached.verdict) {
    const { verdict } = cached;

    if (verdict.traffic_light === "GREEN") {
      // Safe — do not intercept. Badge already shows ✓.
      console.log(`[TrustLens] Tab ${tabId}: Payment gateway reached, prior scan was GREEN — allowing.`);
      return;
    }

    // YELLOW or RED — inject the real verdict overlay
    console.log(`[TrustLens] Tab ${tabId}: Intercepting payment page — verdict is ${verdict.traffic_light}.`);
    await injectOverlay(tabId, verdict, false);

  } else {
    // No prior scan — show a generic caution overlay for unscanned stores
    console.log(`[TrustLens] Tab ${tabId}: Payment page reached with no prior scan — generic caution.`);

    const genericCaution = {
      traffic_light: "YELLOW",
      headline: "We haven't scanned the store you came from ⚠️",
      sub_message: "TrustLens didn't get a chance to check the seller's product listing. Be cautious — only pay on sites you fully trust.",
      should_intercept: true,
      risk_score: 0.5,
      scanned_url: url,
    };

    await injectOverlay(tabId, genericCaution, false);
  }
}

// ─────────────────────────────────────────────────────────────
// SECTION 7 — EVENT LISTENERS
// ─────────────────────────────────────────────────────────────

// ── 7.1 Extension lifecycle ───────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  console.log("[TrustLens] Service Worker v2.0 initialized.");
  // Clear any stale session data from a previous session
  chrome.storage.session.clear();
});

// ── 7.2 Message bus (from content.js and popup.js) ───────────
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  const tabId = sender.tab?.id;

  // ── PAGE_LOADED: content.js auto-scraped a product page ──────
  if (request.action === "PAGE_LOADED") {
    if (!tabId || !request.payload) {
      sendResponse({ success: false, reason: "Missing tabId or payload" });
      return false;
    }
    runPassiveScan(tabId, request.payload)
      .then(() => sendResponse({ success: true }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // async — keep channel open
  }

  // ── CHECKOUT_INTENT: content.js detected a Buy Now click ─────
  if (request.action === "CHECKOUT_INTENT") {
    if (!tabId) {
      sendResponse({ success: false });
      return false;
    }

    getResult(tabId).then(async (cached) => {
      if (cached && cached.verdict) {
        if (cached.verdict.should_intercept) {
          await injectOverlay(tabId, cached.verdict, false);
          sendResponse({ success: true, intercepted: true });
        } else {
          // GREEN — don't intercept, just acknowledge
          sendResponse({ success: true, intercepted: false });
        }
      } else {
        // No cached result — run quick scan then inject overlay
        setBadge(tabId, "LOADING");
        const fallbackPayload = request.payload || { url: sender.tab?.url || "", title: "", image_urls: [] };
        await injectOverlay(tabId, null, true); // Show loading overlay

        const verdict = await callQuickScan(fallbackPayload).catch(() => null);

        await removeOverlay(tabId); // Tear down loading overlay

        if (verdict) {
          await storeResult(tabId, { verdict, payload: fallbackPayload, timestamp: Date.now() });
          setBadge(tabId, verdict.traffic_light);
          if (verdict.should_intercept) {
            await injectOverlay(tabId, verdict, false);
          }
          sendResponse({ success: true, intercepted: verdict.should_intercept });
        } else {
          setBadge(tabId, "DEFAULT");
          sendResponse({ success: true, intercepted: false });
        }
      }
    });
    return true; // async
  }

  // ── GET_SCAN_RESULT: popup.js requests the cached scan ───────
  if (request.action === "GET_SCAN_RESULT") {
    if (!tabId) {
      sendResponse({ success: false, result: null });
      return false;
    }
    getResult(tabId)
      .then((result) => sendResponse({ success: true, result }))
      .catch(() => sendResponse({ success: false, result: null }));
    return true; // async
  }

  // ── ANALYZE_PRODUCT: legacy relay for popup direct analysis ──
  if (request.action === "ANALYZE_PRODUCT") {
    callPredict(request.payload)
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // async
  }
});

// ── 7.3 Payment gateway detection via webNavigation ──────────
// Uses onCompleted (not onBeforeNavigate) so the page has actually
// finished loading before we inject — avoids race conditions.
chrome.webNavigation.onCompleted.addListener(
  (details) => {
    // frameId 0 = main document frame only (ignore iframes on payment pages)
    if (details.frameId !== 0) return;
    if (isPaymentGateway(details.url)) {
      handlePaymentNavigation(details.tabId, details.url);
    }
  },
  { url: [{ schemes: ["https", "http"] }] }
);

// ── 7.4 Cache management on navigation ───────────────────────
// When a tab navigates to a NEW non-payment page, clear the old scan
// so the incoming content.js PAGE_LOADED starts a fresh scan.
// IMPORTANT: Do NOT clear if navigating TO a payment gateway —
// we need the cached product scan result for the interception check.
chrome.webNavigation.onBeforeNavigate.addListener(
  async (details) => {
    if (details.frameId !== 0) return;
    if (!isPaymentGateway(details.url)) {
      await clearResult(details.tabId);
      setBadge(details.tabId, "DEFAULT");
    }
  },
  { url: [{ schemes: ["https", "http"] }] }
);

// ── 7.5 Tab close — free up session storage ──────────────────
chrome.tabs.onRemoved.addListener((tabId) => {
  clearResult(tabId).catch(() => {});
});
