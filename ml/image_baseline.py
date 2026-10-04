"""
TrustLens Image-Only Baseline: Visual Similarity Engine
Evaluates visual resemblance against the brand reference catalog.
Computes cosine similarity, nearest reference model matching, and looks_similar scoring.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
REFERENCE_CATALOG_FILE = BASE_DIR / "data" / "reference_catalog" / "reference_catalog.json"
EMBEDDINGS_FILE = BASE_DIR / "data" / "reference_catalog" / "reference_embeddings.npy"

class ImageSimilarityBaseline:
    def __init__(self, catalog_path: Path = REFERENCE_CATALOG_FILE, emb_path: Path = EMBEDDINGS_FILE):
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog_data = json.load(f)
        self.references = catalog_data["references"]
        self.embeddings = np.load(emb_path) # Shape (N, D), already L2-normalized
        self.tau_sim = 0.68

    def compute_similarity(self, query_vector: np.ndarray, target_brand_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Computes cosine similarity against reference embeddings.
        If target_brand_id is provided, filters or ranks matches for that brand.
        """
        # Ensure query vector is normalized
        norm = np.linalg.norm(query_vector)
        if norm > 0:
            q_norm = query_vector / norm
        else:
            q_norm = query_vector

        # Dot product with normalized reference vectors = cosine similarity
        similarities = np.dot(self.embeddings, q_norm)
        
        if target_brand_id:
            brand_indices = [i for i, r in enumerate(self.references) if r["brand_id"] == target_brand_id]
            if brand_indices:
                sub_sims = similarities[brand_indices]
                best_sub_idx = brand_indices[np.argmax(sub_sims)]
                best_sim = float(similarities[best_sub_idx])
                best_match = self.references[best_sub_idx]
            else:
                best_idx = int(np.argmax(similarities))
                best_sim = float(similarities[best_idx])
                best_match = self.references[best_idx]
        else:
            best_idx = int(np.argmax(similarities))
            best_sim = float(similarities[best_idx])
            best_match = self.references[best_idx]

        looks_similar = best_sim >= self.tau_sim
        
        return {
            "looks_similar": looks_similar,
            "visual_similarity": round(best_sim, 4),
            "matched_brand_id": best_match["brand_id"],
            "matched_brand_name": best_match["brand_name"],
            "matched_model_id": best_match["model_id"],
            "matched_model_name": best_match["model_name"],
            "critical_evidence_types": best_match.get("critical_evidence_types", [])
        }

def evaluate_image_baseline(dataset_path: Path):
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)["listings"]
        
    engine = ImageSimilarityBaseline()
    correct_look_alike_detection = 0
    total_look_alikes = 0
    
    # Ground truth: Legitimate Look-alikes, Counterfeits, and Authentics should look similar
    for row in data:
        sim = row.get("visual_similarity", 0.5)
        # Construct a synthetic query vector with cosine similarity close to row["visual_similarity"]
        model_id = row.get("model_id")
        ref_idx = next((i for i, r in enumerate(engine.references) if r["model_id"] == model_id), 0)
        ref_vec = engine.embeddings[ref_idx]
        
        # Perturb ref_vec to match the exact visual_similarity
        noise = np.random.randn(len(ref_vec))
        noise -= noise.dot(ref_vec) * ref_vec # Orthogonal component
        noise /= np.linalg.norm(noise)
        
        target_sim = sim
        query_vec = target_sim * ref_vec + np.sqrt(max(0.0, 1.0 - target_sim**2)) * noise
        
        res = engine.compute_similarity(query_vec, target_brand_id=row.get("brand_id"))
        
        expected_looks_similar = row["label"] in ["Likely Authentic", "Potential Counterfeit", "Legitimate Look-alike"]
        if row["label"] == "Legitimate Look-alike":
            total_look_alikes += 1
            if res["looks_similar"]:
                correct_look_alike_detection += 1
                
    recall_lookalike = correct_look_alike_detection / total_look_alikes if total_look_alikes > 0 else 0
    print(f"Image Baseline: Look-alike Recall = {recall_lookalike:.4f} ({correct_look_alike_detection}/{total_look_alikes})")
    return recall_lookalike

if __name__ == "__main__":
    dataset_file = BASE_DIR / "data" / "listings" / "dataset.json"
    evaluate_image_baseline(dataset_file)
