# TrustLens Labeling Guide: 4-Class Counterfeit & Look-alike Classification

## 1. Objective and Scope
TrustLens categorizes e-commerce product listings into four mutually exclusive, rigorous classes based on visual resemblance to authentic brand references, textual claims, and listing risk signals (price discrepancy, seller history, rating volatility).

This document serves as the ground-truth standard for labeling all real, curated, and synthetically augmented listings in `data/listings/`.

---

## 2. Core Operational Variables

Every listing is evaluated against reference catalog data $\mathcal{R}_B$ for brand $B$:

1. **`claims_brand` ($\in \{0, 1\}$ or continuous score $c \in [0, 1]$)**:
   - Does the title, seller brand field, or product description explicitly assert that the product is made by brand $B$ (e.g., *"Nike Air Jordan 1"*, *"Rolex Submariner Date"*, *"Authentic Apple AirPods Pro"*), or use protected trademark names?
   - If generic/homage branding is used (e.g., *"Fashion Classic Running Shoe"*, *"Pagani Design Diver Watch"*), then $\text{claims\_brand} = 0$.

2. **`looks_similar` ($\in \{0, 1\}$ or continuous score $s \in [0, 1]$)**:
   - Does the product image exhibit visual feature similarity (colorway, silhouette, bezel/dial layout, iconic hardware) matching canonical brand reference images at or above similarity threshold $\tau_{\text{sim}}$ ($s \ge 0.70$)?

3. **`risk_flags`**:
   - **Price Anomaly**: Normalized price deviation $z_{\text{price}} < -1.8$ (e.g., listing price is $>65\%$ below median authorized retail price).
   - **Seller Anomaly**: New seller account ($<90$ days), low feedback rating ($<80\%$), missing business address, or high cancellation rate.
   - **Text Anomaly**: Vague terms ("1:1 replica", "mirror quality", "OEM duplicate", "overrun stock", "grade AAA+").

---

## 3. Four-Class Definitions & Decision Matrix

| Class ID | Class Label | `claims_brand` | `looks_similar` | Risk Signals | Typical Real-World Examples |
|---|---|---|---|---|---|
| **0** | **Likely Authentic** | **YES** ($c \ge 0.75$) | **YES** ($s \ge 0.70$) | **LOW / NORMAL** | Official flagship store, verified authorized dealer, realistic market price, high seller rating. |
| **1** | **Potential Counterfeit** | **YES** ($c \ge 0.75$) | **YES** ($s \ge 0.70$) | **HIGH** | Listing titled *"Rolex Submariner"* sold for $85 by an unverified storefront; *"Nike Dunk Low"* at 75% discount with blurry tag. |
| **2** | **Legitimate Look-alike** | **NO** ($c < 0.40$) | **YES** ($s \ge 0.70$) | **N/A** (independent) | Fast-fashion or homage brand (e.g., *"Zara Canvas High-top"* resembling Converse, *"Invicta Pro Diver"* resembling Rolex) without infringing brand name. |
| **3** | **Uncertain** | Indeterminate or Low Signal | Ambiguous visual / low quality | Inconclusive | Low-resolution image, incomplete listing metadata, contradictory claims, model predictive entropy above threshold $H(p) \ge \tau_{\text{entropy}}$. |

---

## 4. Strict Claim vs. Appearance Rule (Separation Layer)

The strict rule layer enforces legal and commercial logic to avoid a critical failure mode of naive ML classifiers: misclassifying legitimate budget alternatives/homages as counterfeits.

```text
IF looks_similar >= tau_sim:
    IF claims_brand < tau_claim:
        LABEL = Legitimate Look-alike  (High visual similarity WITHOUT trademark infringement)
    ELSE (claims_brand >= tau_claim):
        IF high_risk_signals_present():
            LABEL = Potential Counterfeit
        ELSE:
            LABEL = Likely Authentic
ELSE:
    IF predictive_entropy >= tau_entropy OR missing_critical_evidence:
        LABEL = Uncertain (Triggers Evidence-Gap Advisor)
    ELSE:
        LABEL = Non-Target / Neutral Product
```

---

## 5. Dataset Provenance & Split Integrity

1. **Source Column**:
   - Every entry in `data/listings/listings_*.json` or `.csv` contains an explicit `source` column:
     - `real`: Scraped or manually curated from actual e-commerce platforms.
     - `synthetic`: Systematically generated perturbations (perturbed prices, perturbed titles, augmented images, injected adversarial claims).
2. **Brand-Disjoint Splitting**:
   - Train, Validation, and Test splits are strictly stratified or brand-isolated where appropriate to evaluate zero-shot brand generalization and prevent data leakage.
3. **No Synthetic Evaluation Deception**:
   - Test metrics must be computed and reported separately for `real` listings and `synthetic` listings in evaluation reports.
