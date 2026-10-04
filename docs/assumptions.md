# TrustLens: Technical & Operational Assumptions

This document records the foundational assumptions adopted during development.

---

## 1. Zero-Cost & Local Execution
- **Hardware Profile**: The backend runs purely locally on `localhost:8000`. Models are optimized for CPU inference (float32 or quantized int8) while automatically taking advantage of a CUDA GPU if present (`torch.cuda.is_available()`).
- **No Paid APIs**: No external paid APIs (OpenAI, Google Vision, AWS Rekognition) are required. Pretrained lightweight foundation models (e.g. CLIP `openai/clip-vit-base-patch32` or distilled equivalents, and DistilBERT `distilbert-base-uncased`) provide visual and textual representations.

---

## 2. Scraping & Privacy Boundaries
- **Shopper-Side Only**: The Chrome Extension executes content extraction exclusively on the browser tab already opened by the user. No headless crawling or automated scraping scripts target third-party sites outside the user's active session.
- **Graceful Degradation**: E-commerce DOMs vary drastically. Extraction relies on a tiered cascade:
  1. Tier 1: Schema.org JSON-LD structured data (`<script type="application/ld+json">`).
  2. Tier 2: OpenGraph & Twitter Card metadata tags (`og:title`, `og:image`, `og:price:amount`, etc.).
  3. Tier 3: Specialized platform selectors (Amazon, Flipkart).
  4. Tier 4: Heuristic DOM scanning (first `h1`, prominent `img`, currency symbols).
- If one or more fields are absent, the payload passes `null` values; the backend handles missing modalities via modality dropout resilience.

---

## 3. Currency and Price Normalization
- All prices are normalized to a base currency (USD or local INR) using fixed baseline exchange rates for standard z-score computation:
  $$z_{\text{price}} = \frac{P_{\text{listing}} - \mu_{\text{brand}}}{\sigma_{\text{brand}}}$$
- If a listing currency is omitted, it defaults to USD unless the domain is a regional TLD (e.g., `.in` -> INR).

---

## 4. Evidence-Gap Estimation
- When confidence is below threshold, uncertainty is estimated using Monte Carlo Dropout (variance of predictive distributions across $T$ passes with dropout enabled) or ensemble variance.
- The expected entropy reduction $\Delta H(e)$ for missing evidence $e$ is estimated by masking/unmasking modality representations in the fusion layer, simulating the information gain expected when that modality is supplied.
