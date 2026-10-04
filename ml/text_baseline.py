"""
TrustLens Text-Only Baseline: Brand Claim Classifier
Evaluates brand claim assertion using semantic keyword & token matching,
homage/dupe penalty rules, and contextual confidence scoring.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
BRANDS_FILE = BASE_DIR / "data" / "brands" / "brands.json"

class TextClaimBaseline:
    def __init__(self, brands_file: Path = BRANDS_FILE):
        with open(brands_file, "r", encoding="utf-8") as f:
            self.brand_data = json.load(f)["brands"]
        
        # Build brand lookup
        self.brand_map = {}
        for b in self.brand_data:
            b_id = b["id"]
            aliases = [a.lower() for a in b.get("aliases", [b["name"]])]
            self.brand_map[b_id] = {
                "name": b["name"].lower(),
                "aliases": set(aliases),
                "canonical_models": b.get("canonical_models", [])
            }
            
        self.homage_keywords = {
            "homage", "dupe", "inspired", "inspired by", "tribute",
            "alternative to", "lookalike", "look-alike", "style of", "similar to"
        }
        
        self.replica_keywords = {
            "1:1", "replica", "clone", "superclone", "aaa+", "mirror quality",
            "first copy", "master copy", "surplus stock", "overrun", "unauthorized"
        }

    def predict_claim(self, title: str, description: str = "", brand_claimed: str = None) -> Dict[str, Any]:
        """
        Calculates brand claim score and detects matching brand.
        Returns:
            - claims_brand: bool
            - claim_confidence: float [0.0, 1.0]
            - matched_brand_id: Optional[str]
            - matched_model_id: Optional[str]
            - risk_keywords: List[str]
        """
        combined_text = f"{title} {description} {brand_claimed or ''}".lower()
        
        # Check replica flags
        detected_replica_flags = [kw for kw in self.replica_keywords if re.search(r"\b" + re.escape(kw) + r"\b", combined_text)]
        detected_homage_flags = [kw for kw in self.homage_keywords if re.search(r"\b" + re.escape(kw) + r"\b", combined_text)]
        
        best_brand_id = None
        best_model_id = None
        max_claim_score = 0.0
        
        for b_id, b_info in self.brand_map.items():
            score = 0.0
            # 1. Explicit brand field match
            if brand_claimed and (brand_claimed.lower() == b_info["name"] or brand_claimed.lower() in b_info["aliases"]):
                score += 0.70
                
            # 2. Alias keyword matches in title/desc
            title_lower = title.lower().strip()
            # Check if title starts with brand name (e.g. "Nike Mens Air Max...")
            for alias in b_info["aliases"]:
                if title_lower.startswith(alias + " ") or title_lower == alias:
                    score += 0.85
                    break
                elif re.search(r"\b" + re.escape(alias) + r"\b", title_lower):
                    score += 0.75
                    break
                elif re.search(r"\b" + re.escape(alias) + r"\b", combined_text):
                    score += 0.35
                    break
                    
            cur_model_id = None
            # 3. Model keyword matches
            for model in b_info["canonical_models"]:
                m_keywords = [kw.lower() for kw in model.get("keywords", [])]
                for kw in m_keywords:
                    if re.search(r"\b" + re.escape(kw) + r"\b", combined_text):
                        score += 0.20
                        cur_model_id = model["model_id"]
                        break
                        
            # Homage / Dupe penalty only if actual homage keywords are detected
            if detected_homage_flags:
                score *= 0.15  # Heavily dampen claim score if explicit homage keywords present
                
            if score > max_claim_score:
                max_claim_score = min(score, 1.0)
                best_brand_id = b_id
                if cur_model_id:
                    best_model_id = cur_model_id
                elif b_info["canonical_models"]:
                    best_model_id = b_info["canonical_models"][0]["model_id"]
                
        # Lower minimal threshold: if title clearly has brand name, it claims brand
        claims_brand = (max_claim_score >= 0.40)
        
        return {
            "claims_brand": claims_brand,
            "claim_confidence": round(max_claim_score, 4),
            "matched_brand_id": best_brand_id if claims_brand or max_claim_score > 0.2 else None,
            "matched_model_id": best_model_id,
            "detected_replica_flags": detected_replica_flags,
            "detected_homage_flags": detected_homage_flags
        }

def evaluate_text_baseline(dataset_path: Path):
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)["listings"]
        
    model = TextClaimBaseline()
    correct_claims = 0
    total = len(data)
    
    # We check if text claims brand matches ground truth (Authentic/Counterfeit claim brand, Look-alike does NOT)
    for row in data:
        pred = model.predict_claim(
            title=row["title"],
            description=row.get("description", ""),
            brand_claimed=row.get("brand_claimed")
        )
        gt_claims = row["label"] in ["Likely Authentic", "Potential Counterfeit"]
        if pred["claims_brand"] == gt_claims:
            correct_claims += 1
            
    acc = correct_claims / total
    print(f"Text Claim Accuracy: {acc:.4f} ({correct_claims}/{total})")
    return acc

if __name__ == "__main__":
    dataset_file = BASE_DIR / "data" / "listings" / "dataset.json"
    evaluate_text_baseline(dataset_file)
