/**
 * TrustLens Warning Overlay — overlay.js
 * ════════════════════════════════════════════════════════════════
 * Injected into the HOST PAGE by background.js via:
 *   chrome.scripting.executeScript({ files: ["overlay.js"] })
 *
 * This file is the FILE-BASED counterpart to the inline
 * buildAndMountOverlay() function defined in background.js.
 *
 * Execution model:
 *   background.js sets  #tl-overlay-root[data-tl-verdict]  BEFORE
 *   injecting this file. overlay.js reads that attribute, parses
 *   the JSON verdict, and renders the full Shadow DOM UI.
 *
 *   If no data attribute is found (e.g. loaded during a loading
 *   state), it renders the spinner / scanning view instead.
 *
 * Shadow DOM: mode "closed" — host page JS/CSS cannot reach inside.
 * ════════════════════════════════════════════════════════════════
 */

(function tlOverlayInit() {
  "use strict";

  // ── Guard: never double-inject ─────────────────────────────────
  if (document.getElementById("tl-overlay-root")) return;

  // ── Read verdict from data attribute written by background.js ──
  // background.js sets the attribute right before calling
  // chrome.scripting.executeScript({ files: ["overlay.js"] }).
  // If the attribute is absent we default to a generic YELLOW caution.
  const hostEl   = document.getElementById("tl-overlay-root-data");
  let verdict    = null;
  let isLoading  = false;

  if (hostEl) {
    try {
      verdict   = JSON.parse(hostEl.dataset.tlVerdict || "null");
      isLoading = hostEl.dataset.tlLoading === "true";
    } catch (_) {
      verdict = null;
    }
    hostEl.remove(); // clean up the data carrier element
  }

  // ── Theme map ──────────────────────────────────────────────────
  const THEMES = {
    GREEN: {
      bg:     "#011a0f",
      border: "#10b981",
      accent: "#10b981",
      glow:   "#10b98122",
      ring:   "#10b98140",
      icon:   "✅",
      label:  "SAFE",
    },
    YELLOW: {
      bg:     "#1c1200",
      border: "#f59e0b",
      accent: "#f59e0b",
      glow:   "#f59e0b22",
      ring:   "#f59e0b40",
      icon:   "⚠️",
      label:  "CAUTION — Proceed Carefully",
    },
    RED: {
      bg:     "#1c0009",
      border: "#f43f5e",
      accent: "#f43f5e",
      glow:   "#f43f5e22",
      ring:   "#f43f5e40",
      icon:   "🛑",
      label:  "HIGH RISK — Likely Counterfeit",
    },
    LOADING: {
      bg:     "#0a0c1f",
      border: "#6366f1",
      accent: "#6366f1",
      glow:   "#6366f122",
      ring:   "#6366f140",
      icon:   "🔍",
      label:  "SCANNING",
    },
  };

  const state = isLoading
    ? "LOADING"
    : verdict?.traffic_light?.toUpperCase() in THEMES
      ? verdict.traffic_light.toUpperCase()
      : "YELLOW";

  const t = THEMES[state];

  // ── Text content ───────────────────────────────────────────────
  const headline = isLoading
    ? "TrustLens is checking this store…"
    : verdict?.headline || _defaultHeadline(state);

  const subMessage = isLoading
    ? "Please don't enter your payment details just yet. We'll let you know in a moment."
    : verdict?.sub_message || _defaultSub(state);

  // For GREEN we show a brief confirmation then auto-dismiss.
  // For YELLOW/RED we block with the "Go Back to Safety" primary action.
  const shouldBlock = !isLoading && state !== "GREEN";

  // ── Build host + closed Shadow DOM ─────────────────────────────
  const host = document.createElement("div");
  host.id = "tl-overlay-root";
  document.body.appendChild(host);

  /** @type {ShadowRoot} */
  const shadow = host.attachShadow({ mode: "closed" });

  // ── Scoped CSS (lives INSIDE the shadow — host CSS cannot touch it) ──
  const css = `
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    /* Reset any inherited host-page styles */
    :host {
      all: initial;
      font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Full-screen backdrop ─────────────────────────────────── */
    #tl-overlay {
      position: fixed;
      inset: 0;
      z-index: 2147483647;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(2, 4, 16, 0.92);
      backdrop-filter: blur(20px) saturate(0.5);
      -webkit-backdrop-filter: blur(20px) saturate(0.5);
      animation: tl-fadein 0.38s cubic-bezier(0.16, 1, 0.3, 1) both;
      font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      padding: 20px;
    }

    @keyframes tl-fadein {
      from { opacity: 0; transform: scale(0.96); }
      to   { opacity: 1; transform: scale(1);    }
    }

    /* ── Warning card ─────────────────────────────────────────── */
    #tl-card {
      background: ${t.bg};
      border: 1.5px solid ${t.border};
      border-radius: 28px;
      padding: 44px 40px 36px;
      max-width: 520px;
      width: 100%;
      text-align: center;
      color: #f1f5f9;
      position: relative;
      animation: tl-card-in 0.42s cubic-bezier(0.34, 1.56, 0.64, 1) both;
      box-shadow:
        0 0 0 1px ${t.ring},
        0 0 60px ${t.glow},
        0 32px 80px rgba(0, 0, 0, 0.7);
    }

    @keyframes tl-card-in {
      from { opacity: 0; transform: translateY(28px) scale(0.94); }
      to   { opacity: 1; transform: translateY(0)    scale(1);    }
    }

    /* Pulsing glow ring on RED/YELLOW cards */
    @keyframes tl-danger-pulse {
      0%, 100% { box-shadow: 0 0 0 1px ${t.ring}, 0 0 60px ${t.glow}, 0 32px 80px rgba(0,0,0,0.7); }
      50%       { box-shadow: 0 0 0 1px ${t.ring}, 0 0 90px ${t.ring}, 0 32px 80px rgba(0,0,0,0.7); }
    }

    #tl-card.pulsing {
      animation: tl-card-in 0.42s cubic-bezier(0.34, 1.56, 0.64, 1) both,
                 tl-danger-pulse 2.4s ease-in-out 0.5s infinite;
    }

    /* ── Pill label ───────────────────────────────────────────── */
    #tl-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: ${t.glow};
      border: 1px solid ${t.border}66;
      border-radius: 100px;
      padding: 5px 14px;
      font-size: 10px;
      font-weight: 700;
      color: ${t.accent};
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 22px;
    }

    /* ── Icon ─────────────────────────────────────────────────── */
    #tl-icon {
      font-size: 64px;
      line-height: 1;
      display: block;
      margin-bottom: 22px;
      filter: drop-shadow(0 0 18px ${t.ring});
      animation: tl-icon-bounce 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) 0.25s both;
    }

    @keyframes tl-icon-bounce {
      from { transform: scale(0.5); opacity: 0; }
      to   { transform: scale(1);   opacity: 1; }
    }

    /* ── Headline ─────────────────────────────────────────────── */
    #tl-headline {
      font-size: 22px;
      font-weight: 900;
      color: ${t.accent};
      line-height: 1.3;
      margin-bottom: 12px;
      letter-spacing: -0.3px;
    }

    /* ── Subtext ──────────────────────────────────────────────── */
    #tl-sub {
      font-size: 14px;
      color: #94a3b8;
      line-height: 1.7;
      margin-bottom: 32px;
      max-width: 400px;
      margin-left: auto;
      margin-right: auto;
    }

    /* ── Loading spinner ──────────────────────────────────────── */
    #tl-spinner-wrap {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 14px;
      margin-bottom: 10px;
    }

    #tl-spinner {
      width: 48px;
      height: 48px;
      border: 3px solid ${t.border}33;
      border-top-color: ${t.accent};
      border-radius: 50%;
      animation: tl-spin 0.75s linear infinite;
    }

    @keyframes tl-spin { to { transform: rotate(360deg); } }

    #tl-scanning-text {
      font-size: 13px;
      color: ${t.accent};
      font-weight: 600;
      animation: tl-blink 1.3s ease-in-out infinite;
    }

    @keyframes tl-blink {
      0%, 100% { opacity: 1;   }
      50%       { opacity: 0.3; }
    }

    /* ── Primary CTA — "Go Back to Safety" ───────────────────── */
    #tl-btn-back {
      display: block;
      width: 100%;
      background: ${t.accent};
      color: #020c0e;
      border: none;
      border-radius: 16px;
      padding: 16px 24px;
      font-size: 16px;
      font-weight: 800;
      cursor: pointer;
      transition: opacity 0.2s, transform 0.15s;
      margin-bottom: 16px;
      letter-spacing: 0.01em;
      font-family: inherit;
    }
    #tl-btn-back:hover  { opacity: 0.85; transform: translateY(-2px); }
    #tl-btn-back:active { transform: translateY(0);  opacity: 0.95; }

    /* ── "Continue anyway" escape hatch (requires typing) ────── */
    #tl-escape-section { margin-top: 4px; }

    #tl-confirm-row {
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
    }

    #tl-confirm-input {
      flex: 1;
      min-width: 0;
      background: #0a0f1e;
      border: 1.5px solid #1e293b;
      border-radius: 12px;
      padding: 11px 14px;
      color: #f1f5f9;
      font-size: 13px;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s;
    }
    #tl-confirm-input::placeholder { color: #2d3c52; }
    #tl-confirm-input:focus        { border-color: ${t.accent}66; }

    #tl-btn-continue {
      background: #0a0f1e;
      color: #2d3c52;
      border: 1.5px solid #1e293b;
      border-radius: 12px;
      padding: 11px 18px;
      font-size: 13px;
      font-family: inherit;
      cursor: not-allowed;
      transition: all 0.2s;
      white-space: nowrap;
      font-weight: 600;
    }
    #tl-btn-continue.unlocked {
      color: #94a3b8;
      border-color: #334155;
      cursor: pointer;
    }
    #tl-btn-continue.unlocked:hover { background: #1e293b; }

    #tl-escape-hint {
      font-size: 11.5px;
      color: #2d3c52;
      text-align: center;
      line-height: 1.5;
    }

    /* ── Footer ───────────────────────────────────────────────── */
    #tl-footer {
      margin-top: 28px;
      padding-top: 18px;
      border-top: 1px solid #1e293b;
      font-size: 11px;
      color: #2d3c52;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    #tl-footer span { color: ${t.accent}88; }
  `;

  // ── HTML structure ─────────────────────────────────────────────
  const blockControls = shouldBlock ? `
    <div id="tl-btn-area">
      <button id="tl-btn-back">← Go Back to Safety</button>
      <div id="tl-escape-section">
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
        <p id="tl-escape-hint">
          We strongly advise against proceeding with this payment.
        </p>
      </div>
    </div>
  ` : (state === "GREEN" ? `
    <button id="tl-btn-back">✓ Continue Shopping — You're Safe</button>
  ` : ``);

  const loadingSection = isLoading ? `
    <div id="tl-spinner-wrap">
      <div id="tl-spinner"></div>
      <p id="tl-scanning-text">Analysing seller credibility…</p>
    </div>
  ` : blockControls;

  shadow.innerHTML = `
    <style>${css}</style>
    <div id="tl-overlay" role="alertdialog" aria-modal="true" aria-labelledby="tl-headline">
      <div id="tl-card" class="${shouldBlock ? 'pulsing' : ''}">

        <div id="tl-label">
          <span>🛡️</span>
          TrustLens Safety Shield &nbsp;·&nbsp; ${t.label}
        </div>

        <span id="tl-icon">${t.icon}</span>
        <h2 id="tl-headline">${_escHtml(headline)}</h2>
        <p id="tl-sub">${_escHtml(subMessage)}</p>

        ${loadingSection}

        <div id="tl-footer">
          <span>TrustLens v2.0</span>
          &nbsp;·&nbsp; Powered by AI
          &nbsp;·&nbsp; Your Shopping Bodyguard
        </div>
      </div>
    </div>
  `;

  // ── Event wiring ───────────────────────────────────────────────

  // Primary: "Go Back to Safety" button
  const backBtn = shadow.getElementById("tl-btn-back");
  if (backBtn) {
    backBtn.addEventListener("click", () => {
      _dismissAndGoBack(host);
    });
  }

  // Secondary: "I UNDERSTAND" typed unlock for "Continue anyway"
  const confirmInput = shadow.getElementById("tl-confirm-input");
  const continueBtn  = shadow.getElementById("tl-btn-continue");
  if (confirmInput && continueBtn) {
    confirmInput.addEventListener("input", () => {
      const unlocked = confirmInput.value.trim().toUpperCase() === "I UNDERSTAND";
      continueBtn.disabled = !unlocked;
      continueBtn.classList.toggle("unlocked", unlocked);
    });
    continueBtn.addEventListener("click", () => {
      if (!continueBtn.disabled) {
        host.remove();
        // Re-enable body scroll
        document.body.style.overflow = "";
      }
    });
  }

  // Auto-dismiss GREEN overlay after 3 seconds
  if (state === "GREEN" && !isLoading) {
    setTimeout(() => {
      if (host.isConnected) host.remove();
    }, 3000);
  }

  // Keyboard accessibility: Escape = go back
  document.addEventListener("keydown", function escHandler(e) {
    if (e.key === "Escape" && host.isConnected) {
      document.removeEventListener("keydown", escHandler);
      _dismissAndGoBack(host);
    }
  });

  // ── Internal helpers ───────────────────────────────────────────

  /** Animate out, remove host element, navigate back. */
  function _dismissAndGoBack(hostNode) {
    const overlay = shadow.getElementById("tl-overlay");
    if (overlay) {
      overlay.style.animation = "tl-fadein 0.25s cubic-bezier(0.4, 0, 1, 1) reverse both";
    }
    setTimeout(() => {
      if (hostNode.isConnected) hostNode.remove();
      window.history.back();
    }, 220);
  }

  /** Minimal HTML entity escape — prevents XSS from verdict text. */
  function _escHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** Default headlines per state (fallback when verdict.headline is absent). */
  function _defaultHeadline(s) {
    return {
      GREEN:   "This store looks legitimate ✅",
      YELLOW:  "Heads up — this seller has risk signals ⚠️",
      RED:     "Stop! This page shows signs of counterfeiting 🛑",
      LOADING: "TrustLens is scanning this store…",
    }[s] || "Proceed with caution";
  }

  /** Default sub-messages per state. */
  function _defaultSub(s) {
    return {
      GREEN:   "Our AI found no significant red flags. You may continue to payment.",
      YELLOW:  "We detected some unusual signals on this seller. Double-check before paying.",
      RED:     "Our AI flagged this listing as high-risk. Do not enter payment details.",
      LOADING: "Please wait — we're running a quick safety check before you pay.",
    }[s] || "Be careful when entering your payment details.";
  }

})();
