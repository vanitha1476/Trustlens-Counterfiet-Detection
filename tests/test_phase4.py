import sys
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.advisor.uncertainty import estimate_mc_uncertainty
from backend.advisor.evidence_advisor import EvidenceGapAdvisor
from backend.models.fusion_head import MultimodalFusionNet, extract_multimodal_features
from backend.app import predict_product, get_evidence_advisor_ranking
from backend.schemas import ScrapedProductPayload

def test_mc_dropout_uncertainty_decomposition():
    model = MultimodalFusionNet(input_dim=20, hidden_dim=64, num_classes=4)
    feat = np.random.RandomState(42).randn(20).astype(np.float32)
    
    res = estimate_mc_uncertainty(model, feat, n_samples=25)
    
    assert "mean_probs" in res
    assert np.isclose(np.sum(res["mean_probs"]), 1.0)
    assert res["total_entropy"] >= 0.0
    assert res["aleatoric_uncertainty"] >= 0.0
    assert res["epistemic_uncertainty"] >= 0.0
    assert res["predictive_variance"] >= 0.0
    # Information-theoretic identity: Total Entropy >= Aleatoric
    assert res["total_entropy"] + 1e-6 >= res["aleatoric_uncertainty"]

def test_evidence_advisor_ranking_order():
    model = MultimodalFusionNet(input_dim=20, hidden_dim=64, num_classes=4)
    advisor = EvidenceGapAdvisor(model)
    
    # Ambiguous feature vector (high initial entropy)
    feat = extract_multimodal_features(
        visual_similarity=0.55,
        claims_brand_score=0.45,
        price_z_score=-0.5,
        seller_rating=80.0,
        seller_reviews_count=10,
        has_homage_flags=False,
        has_replica_flags=False
    )
    
    mc_init = estimate_mc_uncertainty(model, feat, n_samples=15)
    checklist = advisor.rank_missing_evidence(
        current_features=feat,
        current_entropy=mc_init["total_entropy"],
        matched_brand_id="nike",
        critical_types=["inner_label", "packaging_box"]
    )
    
    assert len(checklist) >= 4
    # Check descending order of expected uncertainty reduction
    for i in range(len(checklist) - 1):
        assert checklist[i].expected_uncertainty_reduction >= checklist[i+1].expected_uncertainty_reduction
        
    # Check top item has plain-English rationale and verification method
    top_item = checklist[0]
    assert len(top_item.rationale) > 20
    assert len(top_item.verification_method) > 10

def test_evidence_addition_reduces_entropy():
    # Initial ambiguous listing without images
    payload_init = ScrapedProductPayload(
        title="Air Jordan Retro Court Style High Top",
        price=95.0,
        currency="USD",
        brand_claimed="Nike",
        seller_name="QuickSalesOnline",
        seller_rating=78.0,
        image_urls=[] # Missing image
    )
    res_init = predict_product(payload_init)
    assert res_init.is_uncertain is True
    assert res_init.predictive_entropy > 0.70
    assert len(res_init.evidence_checklist) > 0
    
    # User provides additional evidence photo (inner label)
    payload_with_evidence = ScrapedProductPayload(
        title="Air Jordan Retro Court Style High Top",
        price=95.0,
        currency="USD",
        brand_claimed="Nike",
        seller_name="QuickSalesOnline",
        seller_rating=78.0,
        image_urls=[],
        additional_evidence_type="inner_label",
        uploaded_image_base64="data:image/jpeg;base64,samplelabeldata"
    )
    res_resolved = predict_product(payload_with_evidence)
    
    # Providing the top evidence resolves uncertainty
    assert res_resolved.is_uncertain is False
    assert res_resolved.classification in ["Likely Authentic", "Potential Counterfeit", "Legitimate Look-alike"]

def test_evidence_advisor_endpoint():
    payload = ScrapedProductPayload(
        title="Vintage Submariner Watch Unmarked",
        price=180.0,
        currency="USD",
        image_urls=[]
    )
    ranking = get_evidence_advisor_ranking(payload)
    assert isinstance(ranking, list)
    assert len(ranking) > 0
    assert hasattr(ranking[0], "expected_uncertainty_reduction")

if __name__ == "__main__":
    print("Running Phase 4 test suite...")
    test_mc_dropout_uncertainty_decomposition()
    print("[PASS] MC-Dropout uncertainty (Entropy, Variance, Epistemic/Aleatoric) verified.")
    test_evidence_advisor_ranking_order()
    print("[PASS] Evidence-Gap Advisor ranking logic & descending ordering verified.")
    test_evidence_addition_reduces_entropy()
    print("[PASS] Supplying missing evidence reduces entropy & resolves uncertainty.")
    test_evidence_advisor_endpoint()
    print("[PASS] /evidence-advisor endpoint verified.")
    print("\nALL PHASE 4 TESTS PASSED SUCCESSFULLY!")
