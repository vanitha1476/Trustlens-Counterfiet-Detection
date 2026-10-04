import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import pytest
except ImportError:
    pytest = None

from backend.app import app, health_check, predict_product
from backend.schemas import HealthResponse, PredictionResponse, ScrapedProductPayload

def test_manifest_structure():
    manifest_path = BASE_DIR / "extension" / "manifest.json"
    assert manifest_path.exists(), "extension/manifest.json must exist"
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data.get("manifest_version") == 3, "Must be Manifest V3"
    assert "host_permissions" in data, "Must define host_permissions"
    assert any("localhost:8000" in hp for hp in data["host_permissions"]), "Must allow localhost:8000"
    assert "background" in data and "service_worker" in data["background"]
    assert "content_scripts" in data and len(data["content_scripts"]) > 0
    assert "action" in data and "default_popup" in data["action"]
    
    # Check icons exist
    for size, icon_rel in data.get("icons", {}).items():
        icon_path = BASE_DIR / "extension" / icon_rel
        assert icon_path.exists(), f"Icon {icon_path} does not exist"

def test_labeling_rules_doc():
    doc_path = BASE_DIR / "docs" / "labeling_rules.md"
    assert doc_path.exists(), "docs/labeling_rules.md must exist"
    content = doc_path.read_text(encoding="utf-8")
    
    # Check all four classes are defined
    assert "Likely Authentic" in content
    assert "Potential Counterfeit" in content
    assert "Legitimate Look-alike" in content
    assert "Uncertain" in content
    assert "claims_brand" in content
    assert "looks_similar" in content

def test_assumptions_doc():
    doc_path = BASE_DIR / "docs" / "assumptions.md"
    assert doc_path.exists(), "docs/assumptions.md must exist"

def test_brands_catalog():
    brands_path = BASE_DIR / "data" / "brands" / "brands.json"
    assert brands_path.exists(), "data/brands/brands.json must exist"
    
    with open(brands_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
        
    assert "brands" in catalog
    brands = catalog["brands"]
    assert len(brands) >= 5, f"Expected at least 5 brands, got {len(brands)}"
    
    for b in brands:
        assert "id" in b and "name" in b and "price_stats" in b and "canonical_models" in b
        assert "mean" in b["price_stats"]
        assert len(b["canonical_models"]) > 0
        for m in b["canonical_models"]:
            assert "critical_evidence_types" in m
            assert len(m["critical_evidence_types"]) > 0

def test_backend_health_endpoint():
    res = health_check()
    assert isinstance(res, HealthResponse)
    assert res.status == "healthy"
    assert res.reference_catalog_size > 0

def test_backend_predict_schema():
    payload = ScrapedProductPayload(
        title="Nike Air Jordan 1 Retro High OG Chicago - Size 10",
        price=180.0,
        currency="USD",
        brand_claimed="Nike",
        seller_name="Nike Official Store",
        seller_rating=99.4,
        seller_reviews_count=1420,
        image_urls=["https://example.com/aj1.jpg"]
    )
    res = predict_product(payload)
    assert isinstance(res, PredictionResponse)
    assert res.classification in [
        "Likely Authentic",
        "Potential Counterfeit",
        "Legitimate Look-alike",
        "Uncertain"
    ]
    assert hasattr(res.claim_vs_appearance, "claims_brand")
    assert hasattr(res.claim_vs_appearance, "looks_similar")

if __name__ == "__main__":
    print("Running Phase 1 validation tests...")
    test_manifest_structure()
    print("[PASS] Manifest V3 structure and icons verified.")
    test_labeling_rules_doc()
    print("[PASS] docs/labeling_rules.md verified.")
    test_assumptions_doc()
    print("[PASS] docs/assumptions.md verified.")
    test_brands_catalog()
    print("[PASS] data/brands/brands.json verified.")
    test_backend_health_endpoint()
    print("[PASS] /health endpoint verified.")
    test_backend_predict_schema()
    print("[PASS] /predict endpoint schema verified.")
    print("\nALL PHASE 1 TESTS PASSED SUCCESSFULLY!")

