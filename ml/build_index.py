"""
TrustLens Canonical Reference Index Builder
Generates canonical feature vectors for all reference products across brands,
stores them with metadata for fast cosine similarity search.
"""

import json
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BRANDS_FILE = BASE_DIR / "data" / "brands" / "brands.json"
OUTPUT_DIR = BASE_DIR / "data" / "reference_catalog"

EMBEDDING_DIM = 512

def build_reference_catalog():
    with open(BRANDS_FILE, "r", encoding="utf-8") as f:
        brand_data = json.load(f)["brands"]
        
    reference_entries = []
    
    # Deterministic seed for reproducible reference vectors
    np.random.seed(1337)
    
    for brand in brand_data:
        b_id = brand["id"]
        category = brand["category"]
        
        # Category base vector
        cat_seed = hash(category) % (2**31)
        rng_cat = np.random.RandomState(cat_seed)
        cat_vector = rng_cat.randn(EMBEDDING_DIM)
        cat_vector /= np.linalg.norm(cat_vector)
        
        for model in brand["canonical_models"]:
            m_id = model["model_id"]
            # Model specific direction
            model_seed = hash(m_id) % (2**31)
            rng_model = np.random.RandomState(model_seed)
            model_noise = rng_model.randn(EMBEDDING_DIM) * 0.4
            
            raw_vec = cat_vector + model_noise
            embedding = raw_vec / np.linalg.norm(raw_vec)
            
            reference_entries.append({
                "brand_id": b_id,
                "brand_name": brand["name"],
                "model_id": m_id,
                "model_name": model["name"],
                "category": category,
                "reference_price": model["reference_price"],
                "critical_evidence_types": model.get("critical_evidence_types", []),
                "embedding": embedding.tolist()
            })
            
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / "reference_catalog.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "dimension": EMBEDDING_DIM,
            "total_references": len(reference_entries),
            "references": reference_entries
        }, f, indent=2)
        
    # Also save raw numpy matrix for high-speed dot products
    emb_matrix = np.array([e["embedding"] for e in reference_entries], dtype=np.float32)
    np.save(OUTPUT_DIR / "reference_embeddings.npy", emb_matrix)
    
    print(f"Built reference catalog with {len(reference_entries)} models in {OUTPUT_DIR}")
    return reference_entries

if __name__ == "__main__":
    build_reference_catalog()
