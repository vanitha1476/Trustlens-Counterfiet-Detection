"""
TrustLens Novelty Feature A: Strict Claim vs. Appearance Separation Engine
Implements the hard separation between legitimate look-alikes and counterfeits.
"""

from typing import Dict, Any, List, Optional
from backend.config import TAU_SIMILARITY, TAU_CLAIM, PRICE_Z_THRESHOLD
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
    predictive_entropy: float = 0.0
) -> Dict[str, Any]:
    """
    Applies the transparent Claim vs. Appearance rule hierarchy.
    Returns:
        - classification: 'Likely Authentic' | 'Potential Counterfeit' | 'Legitimate Look-alike' | 'Uncertain'
        - claim_vs_appearance: ClaimVsAppearance schema
        - risk_signals: List[RiskSignal]
        - explanation: str
    """
    risk_signals: List[RiskSignal] = []
    
    # Analyze Risk Signals
    price_risk = False
    if price_z_score is not None:
        if price_z_score <= PRICE_Z_THRESHOLD:
            price_risk = True
            risk_signals.append(RiskSignal(
                signal_name="Severe Price Discrepancy",
                severity="high",
                description=f"Listing price is {abs(price_z_score):.1f} std deviations below brand average.",
                value=round(price_z_score, 2)
            ))
        elif price_z_score <= -1.2:
            risk_signals.append(RiskSignal(
                signal_name="Moderate Price Discount",
                severity="medium",
                description="Price is noticeably below typical retail channel levels.",
                value=round(price_z_score, 2)
            ))

    seller_risk = False
    if seller_rating is not None and seller_rating > 0:
        if seller_rating < 75.0:
            seller_risk = True
            risk_signals.append(RiskSignal(
                signal_name="Low Seller Feedback",
                severity="high",
                description=f"Seller satisfaction score is abnormally low ({seller_rating}%).",
                value=seller_rating
            ))
        elif seller_rating < 85.0:
            risk_signals.append(RiskSignal(
                signal_name="Marginal Seller Rating",
                severity="medium",
                description=f"Seller rating ({seller_rating}%) warrants caution.",
                value=seller_rating
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
        if 0.45 <= visual_similarity < TAU_SIMILARITY:
            # Ambiguous visual match -> triggers Evidence Gap
            classification = "Uncertain"
            rule_applied = "Borderline visual resemblance [0.45 - 0.65] creates high ambiguity."
            explanation = "The product has partial design resemblance to brand references, but visual signals are insufficient for definitive classification."
        else:
            classification = "Legitimate Look-alike" if not claims_brand else "Uncertain"
            rule_applied = "Low visual similarity with monitored brand catalog."
            explanation = "The item does not match monitored brand silhouettes."
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
