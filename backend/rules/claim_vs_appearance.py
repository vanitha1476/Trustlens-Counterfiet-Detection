"""
TrustLens Novelty Feature A: Strict Claim vs. Appearance Separation Engine
Implements the hard separation between legitimate look-alikes and counterfeits.
Includes official storefront verification and realistic retail price variance tolerance.
"""

from typing import Dict, Any, List, Optional
from backend.schemas import ClaimVsAppearance, RiskSignal

def evaluate_claim_vs_appearance(
    claims_brand: bool,
    claim_confidence: float,
    looks_similar: bool,
    visual_similarity: float,
    price_z_score: Optional[float],
    seller_rating: Optional[float],
    seller_reviews_count: Optional[int],
    replica_keywords: List[str],
    matched_brand_id: Optional[str] = None,
    matched_model_id: Optional[str] = None,
    predictive_entropy: float = 0.0,
    is_official_store: bool = False
) -> Dict[str, Any]:
    """
    Applies the transparent Claim vs. Appearance rule hierarchy.
    """
    risk_signals: List[RiskSignal] = []
    
    # CASE 1: DIRECT OFFICIAL BRAND STOREFRONT (e.g. nike.com, nike.in, apple.com)
    # The gold standard in e-commerce verification: direct manufacturer sales are guaranteed authentic.
    if is_official_store:
        cva = ClaimVsAppearance(
            claims_brand=True,
            claim_confidence=1.0,
            looks_similar=True,
            visual_similarity=max(visual_similarity, 0.95),
            matched_brand_id=matched_brand_id,
            matched_model_id=matched_model_id,
            rule_applied="Official Verified Brand Storefront -> Guaranteed Authentic"
        )
        return {
            "classification": "Likely Authentic",
            "claim_vs_appearance": cva,
            "risk_signals": [],
            "explanation": f"Item is hosted directly on the verified official {matched_brand_id or 'brand'} storefront. 100% Genuine authorized product."
        }

    # Normalize seller rating to percentage if on 5-star scale
    seller_risk = False
    norm_rating = seller_rating
    if seller_rating is not None and seller_rating > 0:
        if seller_rating <= 5.0:
            norm_rating = seller_rating * 20.0
            
        if norm_rating < 70.0:
            seller_risk = True
            risk_signals.append(RiskSignal(
                signal_name="Low Seller Feedback",
                severity="high",
                description=f"Seller satisfaction score is abnormally low ({seller_rating} / 5 stars or {norm_rating:.0f}%).",
                value=round(norm_rating, 1)
            ))
        elif norm_rating < 78.0:
            risk_signals.append(RiskSignal(
                signal_name="Marginal Seller Rating",
                severity="medium",
                description=f"Seller rating ({seller_rating} stars or {norm_rating:.0f}%) warrants moderate caution.",
                value=round(norm_rating, 1)
            ))

    # Analyze Price Discrepancy realistically
    # Seasonal sales (30-50% off) are common. Counterfeiters typically discount 75-95%.
    price_risk = False
    if price_z_score is not None:
        if price_z_score <= -2.4:
            price_risk = True
            risk_signals.append(RiskSignal(
                signal_name="Severe Price Discrepancy",
                severity="high",
                description=f"Listing price is {abs(price_z_score):.1f} std deviations below brand average (>75% markdown).",
                value=round(price_z_score, 2)
            ))
        elif price_z_score <= -1.8 and seller_risk:
            # Only consider moderate discount a risk if seller rating is ALSO questionable
            price_risk = True
            risk_signals.append(RiskSignal(
                signal_name="Suspicious Discount",
                severity="medium",
                description="Discounted price combined with low seller feedback warrants caution.",
                value=round(price_z_score, 2)
            ))
        elif price_z_score <= -1.5:
            # Informational notice only; not a counterfeit flag
            risk_signals.append(RiskSignal(
                signal_name="Promotional / Clearance Pricing",
                severity="info",
                description="Price reflects standard seasonal discount / clearance sale.",
                value=round(price_z_score, 2)
            ))

    if replica_keywords:
        risk_signals.append(RiskSignal(
            signal_name="Counterfeit Keyword Association",
            severity="high",
            description=f"Listing text matches known clone/replica markers: {', '.join(replica_keywords)}",
            value=replica_keywords
        ))

    # Evaluate Rule Hierarchy
    if not looks_similar:
        if 0.45 <= visual_similarity < 0.65:
            classification = "Uncertain"
            rule_applied = "Borderline visual resemblance [0.45 - 0.65] creates high ambiguity."
            explanation = "The product has partial design resemblance to brand references, but visual signals are insufficient for definitive classification."
        else:
            if not claims_brand:
                classification = "Likely Authentic"
                rule_applied = "Original design / Independent brand -> Likely Authentic"
                explanation = "The item exhibits an independent original design with no trademark infringement or counterfeit markers."
            else:
                classification = "Uncertain"
                rule_applied = "Brand claimed but low visual similarity with catalog models."
                explanation = "Listing asserts trademark ownership, but visual design diverges from canonical catalog models."
    else:
        # Visual similarity is HIGH (looks_similar is True)
        if not claims_brand:
            # STRICT NOVELTY BRANCH: High visual similarity WITHOUT trademark assertion
            classification = "Legitimate Look-alike"
            rule_applied = "looks_similar AND NOT claims_brand -> Legitimate Look-alike"
            explanation = "Item exhibits strong visual resemblance to the reference design, but makes NO trademark infringement or brand claim. Classified as lawful homage or dupe."
        else:
            # High visual similarity AND claims the trademark
            has_major_risk = price_risk or seller_risk or bool(replica_keywords)
            
            if has_major_risk:
                classification = "Potential Counterfeit"
                rule_applied = "claims_brand AND looks_similar WITH high risk anomalies -> Potential Counterfeit"
                reasons = []
                if price_risk: reasons.append("abnormal price markdown")
                if seller_risk: reasons.append("weak seller history")
                if replica_keywords: reasons.append("replica keyword indicators")
                explanation = f"Listing asserts {matched_brand_id or 'brand'} ownership and visually matches catalog, but flags critical risks: {', '.join(reasons)}."
            else:
                classification = "Likely Authentic"
                rule_applied = "claims_brand AND looks_similar WITH consistent market signals -> Likely Authentic"
                explanation = f"Listing claims verified {matched_brand_id or 'brand'} branding, matches canonical reference images, and displays consistent market pricing and seller metrics."

    cva = ClaimVsAppearance(
        claims_brand=claims_brand,
        claim_confidence=claim_confidence,
        looks_similar=looks_similar,
        visual_similarity=visual_similarity,
        matched_brand_id=matched_brand_id,
        matched_model_id=matched_model_id,
        rule_applied=rule_applied
    )

    return {
        "classification": classification,
        "claim_vs_appearance": cva,
        "risk_signals": risk_signals,
        "explanation": explanation
    }
