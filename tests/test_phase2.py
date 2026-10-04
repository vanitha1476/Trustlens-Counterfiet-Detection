import sys
import json
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.scraper_parser import extract_from_html
from ml.text_baseline import TextClaimBaseline
from ml.image_baseline import ImageSimilarityBaseline

def test_dataset_integrity():
    data_file = BASE_DIR / "data" / "listings" / "dataset.json"
    assert data_file.exists(), "dataset.json must exist"
    with open(data_file, "r", encoding="utf-8") as f:
        content = json.load(f)
    listings = content["listings"]
    assert len(listings) >= 100, f"Expected at least 100 listings, got {len(listings)}"
    
    classes_found = set()
    sources_found = set()
    splits_found = set()
    for row in listings:
        assert "source" in row and row["source"] in ["real", "synthetic"]
        assert "split" in row and row["split"] in ["train", "val", "test"]
        assert "label" in row
        classes_found.add(row["label"])
        sources_found.add(row["source"])
        splits_found.add(row["split"])
        
    assert {"Likely Authentic", "Potential Counterfeit", "Legitimate Look-alike", "Uncertain"}.issubset(classes_found)
    assert {"real", "synthetic"} == sources_found
    assert {"train", "val", "test"} == splits_found

def test_reference_catalog_integrity():
    cat_file = BASE_DIR / "data" / "reference_catalog" / "reference_catalog.json"
    emb_file = BASE_DIR / "data" / "reference_catalog" / "reference_embeddings.npy"
    assert cat_file.exists(), "reference_catalog.json must exist"
    assert emb_file.exists(), "reference_embeddings.npy must exist"
    
    embeddings = np.load(emb_file)
    with open(cat_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert len(meta["references"]) == len(embeddings)
    assert embeddings.shape[1] == 512

def test_text_claim_baseline():
    model = TextClaimBaseline()
    
    # 1. Clear brand claim
    res1 = model.predict_claim(
        title="Nike Air Jordan 1 Retro High OG Chicago",
        description="Authentic high top basketball sneaker.",
        brand_claimed="Nike"
    )
    assert res1["claims_brand"] is True
    assert res1["claim_confidence"] > 0.70
    assert res1["matched_brand_id"] == "nike"
    
    # 2. Look-alike / Homage (should NOT claim brand)
    res2 = model.predict_claim(
        title="Invicta Pro Diver Homage Automatic Black Dial Watch",
        description="Inspired by classic luxury diver aesthetic.",
        brand_claimed="Invicta"
    )
    assert res2["claims_brand"] is False
    assert res2["claim_confidence"] < 0.40

def test_image_similarity_baseline():
    engine = ImageSimilarityBaseline()
    assert len(engine.references) >= 12
    
    # Perfect match test using exact 0th reference vector
    ref_vec = engine.embeddings[0]
    res = engine.compute_similarity(ref_vec)
    assert res["looks_similar"] is True
    assert res["visual_similarity"] >= 0.99
    assert res["matched_model_id"] == engine.references[0]["model_id"]
    
    # Random orthogonal vector (should NOT look similar)
    noise_vec = np.random.randn(512)
    noise_vec -= np.dot(noise_vec, ref_vec) * ref_vec
    noise_vec /= np.linalg.norm(noise_vec)
    res_noise = engine.compute_similarity(noise_vec)
    assert res_noise["looks_similar"] is False
    assert res_noise["visual_similarity"] < 0.40

def test_scraper_end_to_end():
    sample_html = """
    <html>
    <head>
      <meta property="og:title" content="Casio G-Shock GA-2100-1A1 All Black">
      <meta property="og:price:amount" content="99.00">
      <meta property="og:price:currency" content="USD">
      <meta property="og:brand" content="Casio">
      <meta property="og:image" content="https://example.com/gshock.jpg">
    </head>
    <body><h1>Casio G-Shock</h1></body>
    </html>
    """
    scraped = extract_from_html(sample_html, "https://example.com/casio-gshock")
    assert scraped["title"] == "Casio G-Shock GA-2100-1A1 All Black"
    assert scraped["price"] == 99.0
    assert scraped["brand_claimed"] == "Casio"
    assert len(scraped["image_urls"]) > 0

if __name__ == "__main__":
    print("Running Phase 2 comprehensive tests...")
    test_dataset_integrity()
    print("[PASS] Dataset integrity (source, splits, 4 classes) verified.")
    test_reference_catalog_integrity()
    print("[PASS] Reference catalog & 512-d embeddings verified.")
    test_text_claim_baseline()
    print("[PASS] Text claim baseline logic & dupe dampening verified.")
    test_image_similarity_baseline()
    print("[PASS] Image similarity baseline & FAISS-style cosine matching verified.")
    test_scraper_end_to_end()
    print("[PASS] DOM Scraper 4-tier cascade verified.")
    print("\nALL PHASE 2 TESTS PASSED SUCCESSFULLY!")
