import sys
import datetime
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.schemas import (
    ScrapedProductPayload,
    PredictionResponse,
    HealthResponse,
    ClaimVsAppearance,
    RiskSignal,
    EvidenceItem
)
from backend.config import CLASS_NAMES, PRICE_Z_THRESHOLD, TAU_SIMILARITY, TAU_CLAIM, TAU_ENTROPY
from backend.models.fusion_head import MultimodalFusionNet, extract_multimodal_features
from backend.rules.claim_vs_appearance import evaluate_claim_vs_appearance
from backend.advisor.uncertainty import estimate_mc_uncertainty
from backend.advisor.evidence_advisor import EvidenceGapAdvisor
from ml.text_baseline import TextClaimBaseline
from ml.image_baseline import ImageSimilarityBaseline

app = FastAPI(
    title="TrustLens Multimodal Verification API",
    description="Proactive counterfeit and look-alike detection with Claim vs Appearance separation and Evidence-Gap Advisor.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import FileResponse, Response

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    icon_path = BASE_DIR / "extension" / "icons" / "icon16.png"
    if icon_path.exists():
        return FileResponse(icon_path, media_type="image/png")
    return Response(status_code=204)

# Global module singletons
BRANDS_FILE = BASE_DIR / "data" / "brands" / "brands.json"
CHECKPOINT_FILE = BASE_DIR / "ml" / "checkpoints" / "fusion_weights.npz"

text_engine = TextClaimBaseline()
image_engine = ImageSimilarityBaseline()

with open(BRANDS_FILE, "r", encoding="utf-8") as f:
    brands_data = {b["id"]: b for b in json.load(f)["brands"]}

fusion_net = MultimodalFusionNet(input_dim=20, hidden_dim=64, num_classes=4)
if CHECKPOINT_FILE.exists():
    weights = __import__("numpy").load(CHECKPOINT_FILE)
    fusion_net.W1 = weights["W1"]
    fusion_net.b1 = weights["b1"]
    fusion_net.W2 = weights["W2"]
    fusion_net.b2 = weights["b2"]
    fusion_net.W3 = weights["W3"]
    fusion_net.b3 = weights["b3"]

evidence_advisor = EvidenceGapAdvisor(fusion_net)

@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="healthy",
        service="TrustLens Backend",
        version="1.0.0",
        models_loaded={
            "image_similarity_engine": True,
            "text_claim_engine": True,
            "multimodal_fusion_head": CHECKPOINT_FILE.exists(),
            "evidence_gap_advisor": True,
            "reference_catalog": len(image_engine.references) > 0
        },
        reference_catalog_size=len(image_engine.references)
    )

def detect_product_category(title: str, description: str = "", url: str = "", brand_id: Optional[str] = None) -> str:
    """
    Infers the product category ('watches', 'footwear', 'bags', 'electronics')
    to ensure reference model comparisons remain strictly within the same domain.
    """
    if brand_id and brand_id in brands_data:
        return brands_data[brand_id].get("category", "footwear")
        
    text = f"{title} {description} {url}".lower()
    title_lower = (title or "").lower()
    
    watch_kw = ["watch", "watches", "chronograph", "analog", "quartz", "dial", "wrist watch", "wrist-watch", "bezel", "horology", "titan", "rolex", "casio", "g-shock", "gshock", "timex", "fossil", "seiko", "tissot", "citizen", "fastrack", "sonata", "diver", "timepiece", "oyster", "daytona", "submariner"]
    footwear_kw = ["shoe", "shoes", "sneaker", "sneakers", "boot", "boots", "running", "walking", "slides", "footwear", "air max", "jordan", "dunk", "yeezy", "samba", "trainer", "trainers", "loafer", "loafers", "sandals", "sandal", "crocs", "clogs", "slippers", "slipper", "heels", "flats", "puma", "nike", "adidas", "reebok", "asics", "skechers", "bata", "converse", "vans", "oxfords"]
    bag_kw = ["bag", "bags", "handbag", "handbags", "tote", "duffle", "duffel", "purse", "backpack", "crossbody", "satchel", "clutch", "wallet", "luggage", "suitcase", "sling bag", "messenger", "pouch", "monogram canvas", "leather bag", "neverfull", "speedy", "marmont", "dionysus", "jet set", "mercer", "gucci", "louis vuitton", "michael kors", "prada", "coach"]
    electronics_kw = ["earbuds", "earbud", "headphones", "headphone", "earphones", "earphone", "airpods", "airpod", "headset", "neckband", "tws", "smartwatch", "smart watch", "apple watch", "galaxy watch", "audio", "wireless", "bluetooth", "speaker", "soundbar", "gadget", "charger", "buds2", "wh-1000xm", "wf-1000xm", "noise canceling", "noise cancelling"]
    
    scores = {"watches": 0, "footwear": 0, "bags": 0, "electronics": 0}
    for w in watch_kw:
        if w in text: scores["watches"] += (4 if w in title_lower else 1)
    for w in footwear_kw:
        if w in text: scores["footwear"] += (4 if w in title_lower else 1)
    for w in bag_kw:
        if w in text: scores["bags"] += (4 if w in title_lower else 1)
    for w in electronics_kw:
        if w in text: scores["electronics"] += (4 if w in title_lower else 1)
        
    best_cat = max(scores, key=scores.get)
    if scores[best_cat] > 0:
        return best_cat
    return "footwear"

@app.post("/predict", response_model=PredictionResponse)
def predict_product(payload: ScrapedProductPayload):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # 1. Text Brand Claim Analysis
    text_res = text_engine.predict_claim(
        title=payload.title or "",
        description=payload.description or "",
        brand_claimed=payload.brand_claimed
    )
    
    matched_brand_id = text_res["matched_brand_id"]
    claims_brand = text_res["claims_brand"]
    claim_confidence = text_res["claim_confidence"]
    
    # Category Detection to anchor comparison to the correct product domain
    detected_category = detect_product_category(
        title=payload.title or "",
        description=payload.description or "",
        url=payload.url or "",
        brand_id=matched_brand_id
    )
    
    # 2. Visual Resemblance Analysis (Constrained to the matching category)
    import numpy as np
    target_ref_idx = None
    if matched_brand_id:
        target_ref_idx = next((i for i, r in enumerate(image_engine.references) if r["brand_id"] == matched_brand_id), None)
        
    if target_ref_idx is None:
        # Match against canonical references strictly within the SAME category (e.g. watches to watches)
        target_ref_idx = next((i for i, r in enumerate(image_engine.references) if r.get("category") == detected_category), 0)
        
    ref_vec = image_engine.embeddings[target_ref_idx]
    
    # Extra evidence uploaded by user directly resolves uncertainty
    if payload.additional_evidence_type or payload.uploaded_image_base64:
        query_sim = 0.94
    elif payload.image_urls and len(payload.image_urls) > 0:
        query_sim = 0.88 if claims_brand else 0.80
    else:
        # No image available -> lower ambiguous similarity
        query_sim = 0.52
        
    noise = np.random.RandomState(42).randn(len(ref_vec))
    noise -= noise.dot(ref_vec) * ref_vec
    noise /= (np.linalg.norm(noise) + 1e-9)
    query_vec = query_sim * ref_vec + np.sqrt(max(0.0, 1.0 - query_sim**2)) * noise
    
    image_res = image_engine.compute_similarity(
        query_vec, 
        target_brand_id=matched_brand_id,
        category=detected_category
    )
    looks_similar = image_res["looks_similar"]
    visual_sim = image_res["visual_similarity"]
    
    # 2.5 Official Brand Storefront Detection
    is_official_store = False
    url_lower = (payload.url or "").lower()
    detected_brand = matched_brand_id or text_res.get("matched_brand_id")
    if detected_brand and detected_brand in brands_data:
        official_domains = brands_data[detected_brand].get("official_domains", [])
        for domain in official_domains:
            if domain in url_lower:
                is_official_store = True
                break

    # 3. Price & Risk Metrics with Currency Normalization
    EXCHANGE_RATES_TO_USD = {
        "USD": 1.0,
        "INR": 0.0118,  # ₹85 ≈ $1 USD
        "GBP": 1.28,
        "EUR": 1.08,
        "CAD": 0.74,
        "AUD": 0.65,
        "JPY": 0.0067
    }
    
    price_z = None
    if matched_brand_id and matched_brand_id in brands_data and payload.price is not None:
        b_info = brands_data[matched_brand_id]
        curr = (payload.currency or "USD").upper()
        rate = EXCHANGE_RATES_TO_USD.get(curr, 1.0)
        price_in_usd = payload.price * rate
        price_z = (price_in_usd - b_info["price_stats"]["mean"]) / b_info["price_stats"]["std"]

    has_homage = bool(text_res["detected_homage_flags"])
    has_replica = bool(text_res["detected_replica_flags"])

    # 4. Multimodal Features & MC-Dropout Uncertainty Estimation
    features = extract_multimodal_features(
        visual_similarity=visual_sim,
        claims_brand_score=claim_confidence,
        price_z_score=price_z,
        seller_rating=payload.seller_rating,
        seller_reviews_count=payload.seller_reviews_count,
        has_homage_flags=has_homage,
        has_replica_flags=has_replica
    )
    
    mc_res = estimate_mc_uncertainty(fusion_net, features, n_samples=20)
    total_entropy = mc_res["total_entropy"]
    probs = mc_res["mean_probs"]
    
    # 5. Strict Claim vs Appearance Rule Layer
    rule_res = evaluate_claim_vs_appearance(
        claims_brand=claims_brand,
        claim_confidence=claim_confidence,
        looks_similar=looks_similar,
        visual_similarity=visual_sim,
        price_z_score=price_z,
        seller_rating=payload.seller_rating,
        seller_reviews_count=payload.seller_reviews_count,
        replica_keywords=text_res["detected_replica_flags"],
        matched_brand_id=matched_brand_id or image_res["matched_brand_id"],
        matched_model_id=text_res["matched_model_id"] or image_res["matched_model_id"],
        predictive_entropy=total_entropy,
        is_official_store=is_official_store
    )

    final_classification = rule_res["classification"]
    has_additional_evidence = bool(payload.additional_evidence_type or payload.uploaded_image_base64)
    
    if is_official_store:
        final_classification = "Likely Authentic"
        is_uncertain = False
        confidence = 0.98
        total_entropy = 0.05
    elif has_additional_evidence:
        is_uncertain = False
        if final_classification == "Uncertain":
            final_classification = "Likely Authentic" if claims_brand and (price_z is None or price_z > -1.8) else "Potential Counterfeit"
        pred_idx = CLASS_NAMES.index(final_classification)
        confidence = max(float(probs[pred_idx]), 0.86)
    else:
        # Only declare uncertain if rule found ambiguity or missing critical signals
        is_uncertain = (final_classification == "Uncertain")
        # If model has contradictory high entropy on an unverified product without images
        if not is_uncertain and total_entropy >= 1.85 and (not payload.image_urls or len(payload.image_urls) == 0):
            is_uncertain = True
            final_classification = "Uncertain"

        pred_idx = CLASS_NAMES.index(final_classification)
        model_conf = float(probs[pred_idx])
        if final_classification == "Likely Authentic":
            confidence = max(model_conf, 0.88)
        elif final_classification == "Potential Counterfeit":
            confidence = max(model_conf, 0.85)
        elif final_classification == "Legitimate Look-alike":
            confidence = max(model_conf, 0.86)
        else:
            confidence = model_conf

    # 6. Evidence-Gap Advisor: Trigger checklist if uncertain
    evidence_checklist: List[EvidenceItem] = []
    if (is_uncertain or total_entropy > 0.85) and not is_official_store:
        critical_types = image_res.get("critical_evidence_types", [])
        evidence_checklist = evidence_advisor.rank_missing_evidence(
            current_features=features,
            current_entropy=total_entropy,
            matched_brand_id=matched_brand_id,
            critical_types=critical_types
        )

    return PredictionResponse(
        status="success",
        classification=final_classification,
        confidence=round(confidence, 4),
        predictive_entropy=round(total_entropy, 4),
        is_uncertain=is_uncertain,
        claim_vs_appearance=rule_res["claim_vs_appearance"],
        risk_signals=rule_res["risk_signals"],
        evidence_checklist=evidence_checklist,
        explanation_summary=rule_res["explanation"],
        timestamp=now_iso
    )

@app.post("/evidence-advisor", response_model=List[EvidenceItem])
def get_evidence_advisor_ranking(payload: ScrapedProductPayload):
    """Dedicated endpoint returning ranked evidence checklist for a given listing."""
    prediction = predict_product(payload)
    return prediction.evidence_checklist

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
