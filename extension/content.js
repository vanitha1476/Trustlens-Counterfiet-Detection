/**
 * TrustLens DOM Extraction Engine (Content Script)
 * Scrapes product metadata using a 4-tier cascade:
 * Tier 1: Schema.org JSON-LD
 * Tier 2: OpenGraph & Twitter Meta Tags
 * Tier 3: Platform Adapters (Amazon, Flipkart) - supports both Product & Search Results
 * Tier 4: Heuristic DOM scanning
 */

(function () {
  "use strict";

  function detectCurrency() {
    const host = window.location.hostname.toLowerCase();
    if (host.includes(".in") || host.includes("flipkart") || host.includes("myntra")) return "INR";
    if (host.includes(".co.uk")) return "GBP";
    if (host.includes(".de") || host.includes(".fr") || host.includes(".it") || host.includes(".es")) return "EUR";
    if (host.includes(".ca")) return "CAD";
    return "USD";
  }

  // Tier 1: Schema.org JSON-LD
  function extractJsonLd() {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of scripts) {
      try {
        const parsed = JSON.parse(script.textContent);
        const items = Array.isArray(parsed) ? parsed : (parsed["@graph"] || [parsed]);
        for (const item of items) {
          if (item["@type"] === "Product" || item["@type"]?.includes?.("Product")) {
            const offers = Array.isArray(item.offers) ? item.offers[0] : item.offers;
            let price = null;
            let currency = detectCurrency();
            if (offers) {
              const pVal = offers.price || offers.lowPrice || offers.highPrice;
              if (pVal) price = parseFloat(String(pVal).replace(/[^0-9.]/g, "")) || null;
              if (offers.priceCurrency) currency = offers.priceCurrency;
            }

            let images = [];
            if (typeof item.image === "string") images.push(item.image);
            else if (Array.isArray(item.image)) images = item.image.map(img => typeof img === "string" ? img : img.url).filter(Boolean);
            else if (item.image?.url) images.push(item.image.url);

            let brandName = null;
            if (typeof item.brand === "string") brandName = item.brand;
            else if (item.brand?.name) brandName = item.brand.name;

            return {
              title: item.name || null,
              price: price,
              currency: currency,
              brand_claimed: brandName,
              seller_name: offers?.seller?.name || null,
              seller_rating: item.aggregateRating?.ratingValue ? parseFloat(item.aggregateRating.ratingValue) : null,
              seller_reviews_count: item.aggregateRating?.reviewCount ? parseInt(item.aggregateRating.reviewCount) : null,
              description: item.description || "",
              image_urls: images
            };
          }
        }
      } catch (e) {
        // Continue
      }
    }
    return null;
  }

  // Tier 2: OpenGraph & Twitter Meta Tags
  function extractOpenGraph() {
    const getMeta = (propNames) => {
      for (const name of propNames) {
        const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
        if (el && el.content) return el.content.trim();
      }
      return null;
    };

    const title = getMeta(["og:title", "twitter:title"]);
    const rawPrice = getMeta(["product:price:amount", "og:price:amount"]);
    const currency = getMeta(["product:price:currency", "og:price:currency"]) || detectCurrency();
    const brand = getMeta(["product:brand", "og:brand"]);
    const image = getMeta(["og:image", "twitter:image"]);
    const desc = getMeta(["og:description", "description"]);

    let price = rawPrice ? parseFloat(rawPrice.replace(/[^0-9.]/g, "")) : null;

    if (title || image || price) {
      return {
        title: title,
        price: isNaN(price) ? null : price,
        currency: currency,
        brand_claimed: brand,
        seller_name: null,
        seller_rating: null,
        seller_reviews_count: null,
        description: desc || "",
        image_urls: image ? [image] : []
      };
    }
    return null;
  }

  // Tier 3: Specialized Platform Adapters
  function extractAmazon() {
    const isAmazon = window.location.hostname.includes("amazon.");
    if (!isAmazon) return null;

    const currency = detectCurrency();

    // Check if on a product detail page first
    const titleEl = document.querySelector("#productTitle, #title, h1#title");
    if (titleEl && titleEl.innerText.trim()) {
      const title = titleEl.innerText.trim();

      let price = null;
      const priceEl = document.querySelector(".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice, #corePriceDisplay_desktop_feature_div .a-price .a-offscreen, #corePrice_desktop .a-price .a-offscreen, .apexPriceToPay .a-offscreen");
      if (priceEl) {
        const match = priceEl.innerText.match(/[0-9,.]+/);
        if (match) price = parseFloat(match[0].replace(/,/g, ""));
      }

      let brand = null;
      const brandEl = document.querySelector("#bylineInfo, #brand, .po-brand .a-span9, tr.po-brand td.a-span9");
      if (brandEl) {
        brand = brandEl.innerText.replace(/Brand:|Visit the | Store/gi, "").trim();
      }

      let seller = null;
      const sellerEl = document.querySelector("#merchant-info, #sellerProfileTriggerId");
      if (sellerEl) {
        seller = sellerEl.innerText.trim();
      }

      let rating = null;
      const ratingEl = document.querySelector("#acrPopover .a-icon-alt, #averageCustomerReviews .a-icon-alt");
      if (ratingEl) {
        const rMatch = ratingEl.innerText.match(/([0-9.]+)\s+out of/i);
        if (rMatch) rating = parseFloat(rMatch[1]);
      }

      let images = [];
      const mainImg = document.querySelector("#landingImage, #imgBlkFront, #main-image-container img");
      if (mainImg && mainImg.src && !mainImg.src.startsWith("data:")) {
        images.push(mainImg.src);
      }

      return {
        title,
        price,
        currency,
        brand_claimed: brand,
        seller_name: seller,
        seller_rating: rating,
        description: document.querySelector("#feature-bullets")?.innerText?.trim() || "",
        image_urls: images,
        is_search_page: false
      };
    }

    // Otherwise, check if user is on Amazon Search Results Page
    const searchItems = document.querySelectorAll('div[data-component-type="s-search-result"], div.s-result-item[data-asin]:not([data-asin=""])');
    if (searchItems.length > 0) {
      // Grab first prominent item from search results
      for (const item of searchItems) {
        const itemTitleEl = item.querySelector("h2 a span, h2 span, a.a-link-normal span.a-text-normal");
        const itemPriceEl = item.querySelector(".a-price .a-offscreen, .a-color-price");
        const itemImgEl = item.querySelector("img.s-image");
        const itemRatingEl = item.querySelector("i.a-icon-star-small span.a-icon-alt, span[aria-label*='stars']");

        if (itemTitleEl && itemTitleEl.innerText.trim()) {
          const itemTitle = itemTitleEl.innerText.trim();
          let itemPrice = null;
          if (itemPriceEl) {
            const pMatch = itemPriceEl.innerText.match(/[0-9,.]+/);
            if (pMatch) itemPrice = parseFloat(pMatch[0].replace(/,/g, ""));
          }

          let images = [];
          if (itemImgEl && itemImgEl.src) images.push(itemImgEl.src);

          let rating = null;
          if (itemRatingEl) {
            const rMatch = itemRatingEl.innerText.match(/([0-9.]+)\s+out of/i);
            if (rMatch) rating = parseFloat(rMatch[1]);
          }

          // Try extracting brand from title prefix or brand tag
          let brand = null;
          const brandHeader = item.querySelector(".s-line-clamp-1, h5 span");
          if (brandHeader) brand = brandHeader.innerText.trim();

          return {
            title: itemTitle,
            price: itemPrice,
            currency,
            brand_claimed: brand,
            seller_name: "Amazon Marketplace",
            seller_rating: rating,
            description: "Product extracted from Amazon search results.",
            image_urls: images,
            is_search_page: true
          };
        }
      }
    }

    return null;
  }

  function extractFlipkart() {
    const isFlipkart = window.location.hostname.includes("flipkart.");
    if (!isFlipkart) return null;

    const currency = "INR";

    // Detail page
    const titleEl = document.querySelector(".B_NuCI, span.VU-ZEz, h1._6EBuvT, h1.VU-ZEz");
    if (titleEl && titleEl.innerText.trim()) {
      const title = titleEl.innerText.trim();

      let price = null;
      const priceEl = document.querySelector("._30jeq3._16Jk6d, div.Nx9bqj.CxhGGd, div._30jeq3");
      if (priceEl) {
        const match = priceEl.innerText.match(/[0-9,.]+/);
        if (match) price = parseFloat(match[0].replace(/,/g, ""));
      }

      const brandEl = document.querySelector("span.mEh187, span.G6XhRU, span.by-line");
      const brand = brandEl ? brandEl.innerText.trim() : null;

      const sellerEl = document.querySelector("#sellerName, div._1RLviY");
      const seller = sellerEl ? sellerEl.innerText.replace(/Seller:\s*/i, "").trim() : null;

      let rating = null;
      const ratingEl = document.querySelector("div._3LWZlK, div.XQDdHH");
      if (ratingEl) {
        try { rating = parseFloat(ratingEl.innerText.trim()); } catch (e) {}
      }

      let images = [];
      const imgEl = document.querySelector("img._396cs4._3exPp9, img.DByuf4, img._2r_T1I");
      if (imgEl && imgEl.src && !imgEl.src.startsWith("data:")) {
        images.push(imgEl.src);
      }

      return {
        title,
        price,
        currency,
        brand_claimed: brand,
        seller_name: seller,
        seller_rating: rating,
        description: document.querySelector("div._1mXcCf")?.innerText?.trim() || "",
        image_urls: images,
        is_search_page: false
      };
    }

    // Flipkart Search Results page
    const searchCards = document.querySelectorAll("div._1AtVbE, div._2kHMtA, div._4ddWXP, div[data-id]");
    if (searchCards.length > 0) {
      for (const card of searchCards) {
        const brandEl = card.querySelector("div._2WkVRV");
        const titleLink = card.querySelector("a.IRpwTa, div._4rR01T, a.s1Q9rs");
        const priceEl = card.querySelector("div._30jeq3, div.Nx9bqj");
        const imgEl = card.querySelector("img._396cs4, img.DByuf4");
        const ratingEl = card.querySelector("div._3LWZlK, div.XQDdHH");

        if (titleLink && titleLink.innerText.trim()) {
          const brand = brandEl ? brandEl.innerText.trim() : null;
          const title = brand ? `${brand} ${titleLink.innerText.trim()}` : titleLink.innerText.trim();

          let price = null;
          if (priceEl) {
            const match = priceEl.innerText.match(/[0-9,.]+/);
            if (match) price = parseFloat(match[0].replace(/,/g, ""));
          }

          let images = [];
          if (imgEl && imgEl.src) images.push(imgEl.src);

          let rating = null;
          if (ratingEl) {
            try { rating = parseFloat(ratingEl.innerText.trim()); } catch (e) {}
          }

          return {
            title,
            price,
            currency,
            brand_claimed: brand,
            seller_name: "Flipkart Seller",
            seller_rating: rating,
            description: "Product extracted from Flipkart search results.",
            image_urls: images,
            is_search_page: true
          };
        }
      }
    }

    return null;
  }

  // Tier 4: Generic Fallback Scanner
  function extractGenericFallback() {
    const h1 = document.querySelector("h1");
    let title = h1 ? h1.innerText.trim() : document.title;
    // Clean up generic search title if present
    if (title.toLowerCase().includes("amazon.com") || title.toLowerCase().includes("search results")) {
      const firstH2 = document.querySelector("h2 a span, h2 span");
      if (firstH2 && firstH2.innerText.trim()) {
        title = firstH2.innerText.trim();
      }
    }

    let price = null;
    const textNodes = document.body.innerText;
    const priceRegex = /(?:\$|£|€|₹)\s?([0-9,]+(?:\.[0-9]{2})?)/g;
    const match = priceRegex.exec(textNodes);
    if (match) {
      price = parseFloat(match[1].replace(/,/g, ""));
    }

    const images = [];
    const imgElements = Array.from(document.querySelectorAll("img"));
    for (const img of imgElements) {
      if (img.src && !img.src.startsWith("data:") && (img.width > 150 || img.naturalWidth > 150)) {
        images.push(img.src);
        if (images.length >= 3) break;
      }
    }

    return {
      title: title,
      price: price,
      currency: detectCurrency(),
      brand_claimed: null,
      seller_name: null,
      seller_rating: null,
      seller_reviews_count: null,
      description: "",
      image_urls: images,
      is_search_page: false
    };
  }

  // Master Extraction Cascade
  function extractPageProduct() {
    const amazon = extractAmazon();
    const flipkart = extractFlipkart();
    const jsonLd = extractJsonLd();
    const og = extractOpenGraph();
    const generic = extractGenericFallback();

    const candidate = amazon || flipkart || jsonLd || og || generic;
    const backup = og || generic;

    return {
      url: window.location.href,
      title: candidate.title || backup.title || document.title,
      price: candidate.price !== null ? candidate.price : backup.price,
      currency: candidate.currency || backup.currency || detectCurrency(),
      brand_claimed: candidate.brand_claimed || backup.brand_claimed || null,
      seller_name: candidate.seller_name || backup.seller_name || null,
      seller_rating: candidate.seller_rating !== null ? candidate.seller_rating : backup.seller_rating,
      seller_reviews_count: candidate.seller_reviews_count || backup.seller_reviews_count || null,
      description: candidate.description || backup.description || "",
      image_urls: (candidate.image_urls && candidate.image_urls.length > 0) ? candidate.image_urls : (backup.image_urls || []),
      is_search_page: candidate.is_search_page || false
    };
  }

  // ─────────────────────────────────────────────────────────────
  // MESSAGE HANDLERS
  // ─────────────────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    // Popup requests a live extraction (manual rescan button)
    if (request.action === "EXTRACT_PAGE_DATA") {
      try {
        const data = extractPageProduct();
        sendResponse({ success: true, data: data });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    }

    // Background requests whatever product data this page has (fallback for unscanned sites)
    if (request.action === "GET_CACHED_DATA") {
      try {
        const data = extractPageProduct();
        sendResponse({ success: true, data: data });
      } catch (err) {
        sendResponse({ success: false, data: null });
      }
    }

    return true;
  });

  // ─────────────────────────────────────────────────────────────
  // PASSIVE AUTO-SCAN (Zero-Click Feature)
  // ─────────────────────────────────────────────────────────────
  // Fires automatically when the page finishes loading.
  // Sends scraped product data to background.js without any user interaction.
  // Delay allows SPAs (Amazon, Flipkart) to finish rendering dynamic content.

  function sendPassiveScan() {
    // Skip internal browser pages and extension pages
    const url = window.location.href;
    if (!url || url.startsWith("chrome") || url.startsWith("about") || url.startsWith("edge")) return;

    let payload;
    try {
      payload = extractPageProduct();
    } catch (e) {
      return; // Extraction failed silently — don't crash the page
    }

    // Send fire-and-forget to background service worker
    // Must check lastError to prevent uncaught error in console
    chrome.runtime.sendMessage({ action: "PAGE_LOADED", payload }, () => {
      if (chrome.runtime.lastError) {
        // Background SW may be sleeping — this is normal. Ignore.
      }
    });
  }

  // 2500ms delay: lets React/Vue/Angular SPAs finish rendering product data
  setTimeout(sendPassiveScan, 2500);

  // ─────────────────────────────────────────────────────────────
  // BUY NOW / CHECKOUT INTERCEPTION  (Aggressive Dual-Mode)
  // ─────────────────────────────────────────────────────────────
  //
  // Mode A — CSS selector matching  (platform-specific, high precision)
  // Mode B — Text / attribute heuristics  (catches anything Mode A misses)
  //
  // Why dual-mode?
  //   Scam sites and indie shops rarely use <button id="buy-now-button">.
  //   They use <div onclick> or <a class="btn">Pay ₹499</a>.
  //   Text matching catches every real-world checkout trigger regardless
  //   of markup, class names, or platform.
  // ─────────────────────────────────────────────────────────────

  // ── Mode A: CSS selectors ──────────────────────────────────────
  // These are high-precision matches for known platforms.
  // Safe to add more — no other code changes required.
  const CHECKOUT_SELECTORS = [
    // ── Amazon ──────────────────────────────────────────────────
    "#buy-now-button",
    "#buyNow",
    "input[name='submit.buy-now']",
    "#pt-buy-box-atc button[name='submit.buy-now']",
    // ── Flipkart ────────────────────────────────────────────────
    "._2KpZ6l._3tsQPE._1SodSK",
    "._2KpZ6l._1ph1Gg._3tsQPE",
    "button[class*='_2KpZ6l']",
    // ── Meesho / generic Indian e-com ───────────────────────────
    "[data-testid='buy-now']",
    "[data-testid='checkout-btn']",
    "[data-testid='proceed-to-pay']",
    "[data-action='buy-now']",
    "[data-action='checkout']",
    // ── Generic class / id patterns ─────────────────────────────
    "#buy-now", "#buyNow", "#buy_now",
    "#checkout-btn", "#checkoutBtn", "#proceed-checkout",
    "#pay-now", "#payNow",
    ".buy-now", ".buy_now", ".buyNow",
    ".checkout-btn", ".checkoutBtn",
    ".proceed-to-checkout", ".proceed-checkout",
    ".pay-now", ".payNow",
    // ── Attribute / name patterns ───────────────────────────────
    "button[name='buy-now']",
    "button[name='checkout']",
    "button[type='submit'][class*='buy']",
    "button[type='submit'][class*='pay']",
    "button[type='submit'][class*='checkout']",
    // ── Href-based (anchor tags leading to checkout) ─────────────
    "a[href*='checkout']",
    "a[href*='buy-now']",
    "a[href*='buy_now']",
    "a[href*='payment']",
    "a[href*='pay-now']",
    // ── Razorpay / PhonePe embedded checkout buttons ─────────────
    ".razorpay-payment-button",
    "button[class*='razorpay']",
    "button[class*='phonepe']",
    "button[class*='paytm']",
  ];

  // ── Mode B: Text / attribute keyword heuristics ───────────────
  // Normalised to lower-case. Matched against:
  //   element.textContent (trimmed, collapsed whitespace)
  //   element.id
  //   element.name
  //   element.value          (input[type=submit])
  //   aria-label
  //   title attribute
  //   href (for anchor tags)
  const CHECKOUT_KEYWORDS = [
    "buy now", "buy it now", "buynow",
    "pay now", "pay \u20b9", "pay $", "pay \u00a3", "pay \u20ac",  // ₹ $ £ €
    "proceed to pay", "proceed to checkout", "proceed to payment",
    "place order", "placeorder",
    "checkout", "check out",
    "complete purchase", "confirm order", "confirm payment",
    "continue to payment", "continue to pay",
    "make payment", "go to checkout",
    "order now", "shop now",
    "add to cart & buy",
  ];

  // Elements that are NEVER checkout triggers — avoids false positives
  // on navigation menus, search bars, and filter buttons.
  const IGNORE_SELECTORS = [
    "input[type='search']", "input[type='text']", "input[type='email']",
    "input[type='password']", "textarea", "select",
    "[role='menuitem']", "[role='tab']", "[role='option']",
    ".cart-quantity", ".qty", "#quantity",
    "nav a", "header a", "footer a",
  ];

  /**
   * Returns true if `el` (or any ancestor up to 4 levels) matches
   * one of the CSS selectors in CHECKOUT_SELECTORS.
   */
  function matchesCssSelectors(el) {
    for (const sel of CHECKOUT_SELECTORS) {
      try {
        if (el.matches(sel) || el.closest(sel)) return true;
      } catch (_) { /* invalid selector — skip */ }
    }
    return false;
  }

  /**
   * Returns true if the element's visible text or key attributes
   * contain one of the CHECKOUT_KEYWORDS.
   */
  function matchesTextHeuristic(el) {
    // Walk up to the nearest interactive ancestor (button / a / [role])
    // so clicking a <span> inside a <button> still works.
    const interactive = el.closest(
      "button, a, [role='button'], input[type='submit'], input[type='button'], [onclick]"
    ) || el;

    // Build a single normalised string from all text-like attributes
    const parts = [
      interactive.textContent,
      interactive.id,
      interactive.getAttribute("name") || "",
      interactive.getAttribute("value") || "",
      interactive.getAttribute("aria-label") || "",
      interactive.getAttribute("title") || "",
      interactive.getAttribute("placeholder") || "",
      interactive.getAttribute("href") || "",
      interactive.getAttribute("data-label") || "",
      interactive.getAttribute("data-text") || "",
    ];

    const haystack = parts
      .join(" ")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();

    return CHECKOUT_KEYWORDS.some((kw) => haystack.includes(kw));
  }

  /**
   * Returns true if `el` should be ignored (search fields, nav links, etc.)
   */
  function shouldIgnore(el) {
    for (const sel of IGNORE_SELECTORS) {
      try {
        if (el.matches(sel) || el.closest(sel)) return true;
      } catch (_) {}
    }
    return false;
  }

  // ── Debounce guard ─────────────────────────────────────────────
  // Unlike a one-shot boolean, this resets after 2 s so a transient
  // Service Worker sleep failure can recover on the next click.
  let _intentCooldown = false;

  function _resetCooldown() {
    _intentCooldown = false;
  }

  /**
   * Master click handler — attached at document level with capture so
   * it fires before the page's own click handlers.
   *
   * NOT passive — we need the option to call event.preventDefault()
   * in future if we want to hard-block the navigation.
   */
  function handleCheckoutClick(event) {
    // Only intercept primary (left) clicks
    if (event.button !== 0) return;

    // Respect the 2-second cooldown
    if (_intentCooldown) return;

    const target = event.target;
    if (!target || typeof target.matches !== "function") return;

    // Fast-reject: ignore form fields, nav menus, etc.
    if (shouldIgnore(target)) return;

    // Check Mode A first (precise), then Mode B (text heuristic)
    const triggered = matchesCssSelectors(target) || matchesTextHeuristic(target);
    if (!triggered) return;

    // ── Triggered — arm the cooldown ─────────────────────────────
    _intentCooldown = true;
    setTimeout(_resetCooldown, 2000);

    // ── Scrape current product data ───────────────────────────────
    let payload = null;
    try { payload = extractPageProduct(); } catch (_) {}

    // ── Send to background Service Worker ────────────────────────
    // sendMessage is fire-and-forget; background.js checks session cache
    // and injects the overlay if the verdict is YELLOW or RED.
    try {
      chrome.runtime.sendMessage(
        { action: "CHECKOUT_INTENT", payload },
        () => {
          // chrome.runtime.lastError must be read to suppress the uncaught
          // console error when the SW is temporarily sleeping.
          void chrome.runtime.lastError;
        }
      );
    } catch (sendErr) {
      // Extension context can be invalidated after a reload — fail silently.
      console.debug("[TrustLens] sendMessage failed:", sendErr.message);
    }
  }

  // ── Attach listener ────────────────────────────────────────────
  // capture: true  — fires BEFORE the page's own onclick handlers
  // passive: false — allows future use of event.preventDefault()
  document.addEventListener("click", handleCheckoutClick, {
    capture: true,
    passive: false,
  });

  // ─────────────────────────────────────────────────────────────
  // MUTATION OBSERVER — SPA route-change & late-render detection
  // ─────────────────────────────────────────────────────────────
  // When a SPA (React / Vue / Angular) swaps in a new product page
  // without a full navigation, the passive scan needs to re-run AND
  // the cooldown guard should reset so the new page's buttons work.

  let rescanScheduled = false;
  const domObserver = new MutationObserver(() => {
    if (rescanScheduled) return;
    rescanScheduled = true;
    setTimeout(() => {
      rescanScheduled = false;
      // Re-run passive scan with new page content
      sendPassiveScan();
      // Reset intent cooldown — the user is now on a new product page
      _intentCooldown = false;
      // Disconnect after first successful rescan to avoid infinite loops
      domObserver.disconnect();
    }, 3000);
  });

  // Observe major structural changes only (childList on body, not subtree attribute noise)
  domObserver.observe(document.body, { childList: true, subtree: false });

  // Hard disconnect ceiling — 12 s is enough for any SPA to settle
  setTimeout(() => domObserver.disconnect(), 12000);

  // ─────────────────────────────────────────────────────────────
  // MODULE EXPORTS (for unit testing)
  // ─────────────────────────────────────────────────────────────
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      extractJsonLd,
      extractOpenGraph,
      extractAmazon,
      extractFlipkart,
      extractGenericFallback,
      extractPageProduct,
      sendPassiveScan
    };
  }
})();

