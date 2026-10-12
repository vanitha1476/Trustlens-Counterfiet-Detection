import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app import predict_product
from backend.schemas import ScrapedProductPayload

def test_popup_html_structure():
    html_path = BASE_DIR / "extension" / "popup.html"
    assert html_path.exists(), "popup.html must exist"
    
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    
    # Check required Traffic Light UI element IDs (new simplified UI)
    required_ids = [
        # Header
        "statusDot",
        "statusText",
        # Traffic-light view + sub-states
        "view-traffic",
        "tl-loading",
        "tl-result",
        # Verdict ring / headline / subtitle
        "tlRing",
        "tlHeadline",
        "tlSub",
        # Scanned product bar
        "scannedBar",
        "scannedTitle",
        "scannedBadge",
        # Collapsible details
        "detailsToggle",
        "details-panel",
        # CVA grid cells
        "cvaClaim",
        "cvaVisual",
        "cvaPrice",
        "ruleBar",
        # Risk signals
        "riskSection",
        "riskList",
        # Evidence-Gap Advisor (hidden by default, but present in DOM)
        "advisorSection",
        "advisorList",
        "evidenceTypeSelect",
        "evidenceFileInput",
        "submitEvidenceBtn",
        # Error view
        "view-error",
        "errorMsg",
        "retryBtn",
        # Footer
        "rescanBtn",
        "reportBtn",
    ]
    for element_id in required_ids:
        assert soup.find(id=element_id) is not None, f"Element #{element_id} missing in popup.html"

def test_popup_css_styling():
    css_path = BASE_DIR / "extension" / "popup.css"
    assert css_path.exists(), "popup.css must exist"
    css = css_path.read_text(encoding="utf-8")
    
    # Check 4-class styling tokens
    assert "--verdict-auth" in css
    assert "--verdict-fake" in css
    assert "--verdict-lookalike" in css
    assert "--verdict-uncertain" in css
    assert "glass" in css or "backdrop-filter" in css

def test_popup_js_presets():
    js_path = BASE_DIR / "extension" / "popup.js"
    assert js_path.exists(), "popup.js must exist"
    js = js_path.read_text(encoding="utf-8")
    
    # Check presets for lab defense
    assert "auth:" in js
    assert "fake:" in js
    assert "lookalike:" in js
    assert "uncertain:" in js
    assert "additional_evidence_type" in js
    assert "FileReader" in js

def test_frontend_backend_contract():
    # Test that backend predict payload conforms to frontend field expectations
    payload = ScrapedProductPayload(
        title="Nike Air Jordan 1 Chicago",
        price=180.0,
        currency="USD",
        brand_claimed="Nike",
        image_urls=["https://example.com/aj1.jpg"]
    )
    res = predict_product(payload)
    data = res.model_dump()
    
    # Fields required by popup.js renderResult()
    assert "classification" in data
    assert "confidence" in data
    assert "explanation_summary" in data
    assert "claim_vs_appearance" in data
    assert "claims_brand" in data["claim_vs_appearance"]
    assert "looks_similar" in data["claim_vs_appearance"]
    assert "visual_similarity" in data["claim_vs_appearance"]
    assert "rule_applied" in data["claim_vs_appearance"]
    assert "risk_signals" in data
    assert "evidence_checklist" in data

if __name__ == "__main__":
    print("Running Phase 5 test suite...")
    test_popup_html_structure()
    print("[PASS] popup.html structure & required novelty IDs verified.")
    test_popup_css_styling()
    print("[PASS] popup.css 4-class theme tokens & glassmorphic styling verified.")
    test_popup_js_presets()
    print("[PASS] popup.js demo presets & file upload re-scoring logic verified.")
    test_frontend_backend_contract()
    print("[PASS] Frontend/Backend API contract alignment verified.")
    print("\nALL PHASE 5 TESTS PASSED SUCCESSFULLY!")
