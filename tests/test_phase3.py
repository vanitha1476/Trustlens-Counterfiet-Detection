import sys
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.rules.claim_vs_appearance import evaluate_claim_vs_appearance
from backend.models.fusion_head import MultimodalFusionNet, extract_multimodal_features
from backend.app import predict_product, health_check
from backend.schemas import ScrapedProductPayload

def test_claim_vs_appearance_novelty_rule():
    # 1. Look-alike Branch: looks_similar AND NOT claims_brand
    res_lookalike = evaluate_claim_vs_appearance(
        claims_brand=False,
        claim_confidence=0.08,
        looks_similar=True,
        visual_similarity=0.82,
        price_z_score=-0.5,
        seller_rating=95.0,
        seller_reviews_count=1200,
        replica_keywords=[],
        matched_brand_id="rolex"
    )
    assert res_lookalike["classification"] == "Legitimate Look-alike"
    assert "NOT claims_brand" in res_lookalike["claim_vs_appearance"].rule_applied
    
    # 2. Counterfeit Branch: claims_brand AND looks_similar AND anomalous price
    res_counterfeit = evaluate_claim_vs_appearance(
        claims_brand=True,
        claim_confidence=0.96,
        looks_similar=True,
        visual_similarity=0.89,
        price_z_score=-2.8, # Extreme price discount
        seller_rating=62.0,
        seller_reviews_count=8,
        replica_keywords=["1:1", "replica"],
        matched_brand_id="rolex"
    )
    assert res_counterfeit["classification"] == "Potential Counterfeit"
    assert len(res_counterfeit["risk_signals"]) >= 2
    
    # 3. Authentic Branch: claims_brand AND looks_similar AND normal price & high seller
    res_auth = evaluate_claim_vs_appearance(
        claims_brand=True,
        claim_confidence=0.98,
        looks_similar=True,
        visual_similarity=0.92,
        price_z_score=0.2, # Regular price
        seller_rating=99.1,
        seller_reviews_count=4500,
        replica_keywords=[],
        matched_brand_id="nike"
    )
    assert res_auth["classification"] == "Likely Authentic"

    # 4. Uncertain Branch: borderline visual match
    res_uncertain = evaluate_claim_vs_appearance(
        claims_brand=False,
        claim_confidence=0.40,
        looks_similar=False,
        visual_similarity=0.55, # Ambiguous band
        price_z_score=0.0,
        seller_rating=85.0,
        seller_reviews_count=20,
        replica_keywords=[]
    )
    assert res_uncertain["classification"] == "Uncertain"

def test_modality_dropout_robustness():
    net = MultimodalFusionNet(input_dim=20, hidden_dim=64, num_classes=4)
    feat = np.random.randn(20).astype(np.float32)
    
    # Complete input
    _, p_full = net.forward(feat)
    assert np.isclose(np.sum(p_full), 1.0)
    
    # Dropout Image Modality (missing product photo)
    _, p_no_img = net.forward(feat, modality_mask={"image": False, "text": True, "meta": True})
    assert np.isclose(np.sum(p_no_img), 1.0)
    assert not np.isnan(p_no_img).any()
    
    # Dropout Text Modality (sparse title, no description)
    _, p_no_text = net.forward(feat, modality_mask={"image": True, "text": False, "meta": True})
    assert np.isclose(np.sum(p_no_text), 1.0)
    assert not np.isnan(p_no_text).any()
    
    # Dropout Metadata (no price or seller available)
    _, p_no_meta = net.forward(feat, modality_mask={"image": True, "text": True, "meta": False})
    assert np.isclose(np.sum(p_no_meta), 1.0)
    assert not np.isnan(p_no_meta).any()

def test_api_predict_lookalike_separation():
    # Test Invicta Pro Diver payload (Look-alike homage)
    lookalike_payload = ScrapedProductPayload(
        title="Invicta Men's Pro Diver Automatic 40mm Black Dial Homage Watch",
        price=85.0,
        currency="USD",
        brand_claimed="Invicta",
        seller_name="Invicta Store",
        seller_rating=97.0,
        seller_reviews_count=2400,
        image_urls=["https://images.invicta.com/diver.jpg"]
    )
    res = predict_product(lookalike_payload)
    assert res.classification == "Legitimate Look-alike"
    assert res.claim_vs_appearance.claims_brand is False
    assert res.claim_vs_appearance.looks_similar is True

def test_api_predict_counterfeit():
    # Test Rolex Counterfeit payload ($120 clone)
    fake_payload = ScrapedProductPayload(
        title="Rolex Submariner 126610LN Automatic Watch 1:1 Superclone Replica",
        price=120.0,
        currency="USD",
        brand_claimed="Rolex",
        seller_name="GlobalDealsExpress",
        seller_rating=62.0,
        seller_reviews_count=12,
        image_urls=["https://fake.com/submariner.jpg"]
    )
    res = predict_product(fake_payload)
    assert res.classification == "Potential Counterfeit"
    assert res.claim_vs_appearance.claims_brand is True
    assert len(res.risk_signals) > 0

if __name__ == "__main__":
    print("Running Phase 3 test suite...")
    test_claim_vs_appearance_novelty_rule()
    print("[PASS] Strict Claim vs Appearance novelty rule layer verified.")
    test_modality_dropout_robustness()
    print("[PASS] Modality dropout resilience (missing image/text/meta) verified.")
    test_api_predict_lookalike_separation()
    print("[PASS] API separates Legitimate Look-alikes from Counterfeits.")
    test_api_predict_counterfeit()
    print("[PASS] API detects Potential Counterfeits with risk flags.")
    print("\nALL PHASE 3 TESTS PASSED SUCCESSFULLY!")
