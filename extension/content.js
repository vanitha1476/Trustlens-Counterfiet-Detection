/**
 * TrustLens DOM Extraction Engine (Content Script)
 * Scrapes product metadata using a 4-tier cascade:
 * Tier 1: Schema.org JSON-LD
 * Tier 2: OpenGraph & Twitter Meta Tags
 * Tier 3: Platform Adapters (Amazon, Flipkart)
 * Tier 4: Heuristic DOM scanning
 */

(function () {
  "use strict";

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
            let currency = "USD";
            if (offers) {
              price = parseFloat(offers.price || offers.lowPrice || offers.highPrice) || null;
              currency = offers.priceCurrency || "USD";
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
        // Continue to next script
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
    const currency = getMeta(["product:price:currency", "og:price:currency"]) || "USD";
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

    const titleEl = document.querySelector("#productTitle, #title");
    const title = titleEl ? titleEl.innerText.trim() : null;

    let price = null;
    const priceEl = document.querySelector(".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice, #corePrice_desktop .a-price .a-offscreen");
    if (priceEl) {
      const match = priceEl.innerText.match(/[0-9,.]+/);
      if (match) price = parseFloat(match[0].replace(/,/g, ""));
    }

    let brand = null;
    const brandEl = document.querySelector("#bylineInfo, #brand, .po-brand .a-span9");
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
      currency: "USD",
      brand_claimed: brand,
      seller_name: seller,
      seller_rating: rating,
      description: document.querySelector("#feature-bullets")?.innerText?.trim() || "",
      image_urls: images
    };
  }

  function extractFlipkart() {
    const isFlipkart = window.location.hostname.includes("flipkart.");
    if (!isFlipkart) return null;

    const titleEl = document.querySelector(".B_NuCI, span.VU-ZEz, h1._6EBuvT");
    const title = titleEl ? titleEl.innerText.trim() : null;

    let price = null;
    const priceEl = document.querySelector("._30jeq3._16Jk6d, div.Nx9bqj.CxhGGd");
    if (priceEl) {
      const match = priceEl.innerText.match(/[0-9,.]+/);
      if (match) price = parseFloat(match[0].replace(/,/g, ""));
    }

    const brandEl = document.querySelector("span.mEh187, span.G6XhRU");
    const brand = brandEl ? brandEl.innerText.trim() : null;

    const sellerEl = document.querySelector("#sellerName, div._1RLviY");
    const seller = sellerEl ? sellerEl.innerText.replace(/Seller:\s*/i, "").trim() : null;

    let rating = null;
    const ratingEl = document.querySelector("div._3LWZlK, div.XQDdHH");
    if (ratingEl) {
      rating = parseFloat(ratingEl.innerText.trim());
    }

    let images = [];
    const imgEl = document.querySelector("img._396cs4._3exPp9, img.DByuf4");
    if (imgEl && imgEl.src && !imgEl.src.startsWith("data:")) {
      images.push(imgEl.src);
    }

    return {
      title,
      price,
      currency: "INR",
      brand_claimed: brand,
      seller_name: seller,
      seller_rating: rating,
      description: document.querySelector("div._1mXcCf")?.innerText?.trim() || "",
      image_urls: images
    };
  }

  // Tier 4: Generic Fallback Scanner
  function extractGenericFallback() {
    const h1 = document.querySelector("h1");
    const title = h1 ? h1.innerText.trim() : document.title;

    let price = null;
    // Look for price patterns in text
    const textNodes = document.body.innerText;
    const priceRegex = /(?:\$|£|€|₹)\s?([0-9,]+(?:\.[0-9]{2})?)/g;
    const match = priceRegex.exec(textNodes);
    if (match) {
      price = parseFloat(match[1].replace(/,/g, ""));
    }

    // Prominent images
    const images = [];
    const imgElements = Array.from(document.querySelectorAll("img"));
    for (const img of imgElements) {
      if (img.src && !img.src.startsWith("data:") && (img.width > 200 || img.naturalWidth > 200)) {
        images.push(img.src);
        if (images.length >= 3) break;
      }
    }

    return {
      title: title,
      price: price,
      currency: "USD",
      brand_claimed: null,
      seller_name: null,
      seller_rating: null,
      seller_reviews_count: null,
      description: "",
      image_urls: images
    };
  }

  // Master Extraction Cascade
  function extractPageProduct() {
    const jsonLd = extractJsonLd();
    const amazon = extractAmazon();
    const flipkart = extractFlipkart();
    const og = extractOpenGraph();
    const generic = extractGenericFallback();

    // Prefer high-fidelity structured data, merge fallbacks
    const candidate = amazon || flipkart || jsonLd || og || generic;
    const backup = og || generic;

    return {
      url: window.location.href,
      title: candidate.title || backup.title || document.title,
      price: candidate.price !== null ? candidate.price : backup.price,
      currency: candidate.currency || backup.currency || "USD",
      brand_claimed: candidate.brand_claimed || backup.brand_claimed || null,
      seller_name: candidate.seller_name || backup.seller_name || null,
      seller_rating: candidate.seller_rating !== null ? candidate.seller_rating : backup.seller_rating,
      seller_reviews_count: candidate.seller_reviews_count || backup.seller_reviews_count || null,
      description: candidate.description || backup.description || "",
      image_urls: (candidate.image_urls && candidate.image_urls.length > 0) ? candidate.image_urls : (backup.image_urls || [])
    };
  }

  // Listen for message from popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "EXTRACT_PAGE_DATA") {
      try {
        const data = extractPageProduct();
        sendResponse({ success: true, data: data });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    }
    return true;
  });

  // Expose for testing if running in node/jest
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      extractJsonLd,
      extractOpenGraph,
      extractAmazon,
      extractFlipkart,
      extractGenericFallback,
      extractPageProduct
    };
  }
})();
