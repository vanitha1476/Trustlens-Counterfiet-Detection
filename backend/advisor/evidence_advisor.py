"""
TrustLens Novelty Feature B: Evidence-Gap Advisor
When classification is Uncertain, this module identifies which missing evidence item
would maximize information gain (minimize predictive entropy), and returns a ranked checklist.

NOTE ON ESTIMATION VS MEASUREMENT (FOR LAB DEFENSE & HONESTY):
- Current predictive entropy H(p) is EMPIRICALLY MEASURED via Monte Carlo Dropout passes.
- Expected uncertainty drop Delta H(e) is SIMULATED by projecting the listing's feature
  vector into the hypothesized post-verification state and measuring the entropy reduction.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from backend.schemas import EvidenceItem
from backend.models.fusion_head import MultimodalFusionNet, extract_multimodal_features
from backend.advisor.uncertainty import estimate_mc_uncertainty

# Catalog of candidate evidence items
CANDIDATE_EVIDENCE_CATALOG = {
    "inner_label": {
        "label": "Inner Wash / Size / Manufacturer Label Photo",
        "rationale": "Authentic production tags use micro-aligned typography and serialized factory codes that counterfeiters routinely misprint or blur.",
        "verification_method": "Inspect font kerning, manufacturer SKU consistency, and heat-press border quality.",
        "modality_target": "image",
        "expected_sim_boost": 0.32,
        "base_weight": 0.45
    },
    "serial_batch_code": {
        "label": "Serial Number / Production Batch Code",
        "rationale": "Directly cross-checks the registered manufacturer production run, instantly resolving authenticity for watches, electronics, and luxury goods.",
        "verification_method": "Cryptographic check and database sequence lookup against authorized serial runs.",
        "modality_target": "meta",
        "expected_sim_boost": 0.28,
        "base_weight": 0.42
    },
    "packaging_box": {
        "label": "Official Retail Packaging & Barcode Label",
        "rationale": "Counterfeits frequently economize on outer packaging, displaying incorrect fonts, missing legal certifications, or mismatched UPC/EAN stickers.",
        "verification_method": "Barcode UPC/EAN validation and packaging structural rigidity inspection.",
        "modality_target": "image",
        "expected_sim_boost": 0.24,
        "base_weight": 0.35
    },
    "seller_invoice": {
        "label": "Original Purchase Receipt / Authorized Retail Invoice",
        "rationale": "Provides chain-of-custody documentation from an authorized brand dealer, resolving seller credibility questions.",
        "verification_method": "Proof-of-purchase validation and authorized distributor tax identification verification.",
        "modality_target": "meta",
        "expected_sim_boost": 0.22,
        "base_weight": 0.38
    },
    "stitching_closeup": {
        "label": "High-Resolution Macro Photo of Stitching or Hardware",
        "rationale": "Macro inspection of stitch tension, hardware engraving, and material grain reveals assembly craftsmanship not visible in standard photos.",
        "verification_method": "Computer vision edge-curvature and thread density micro-analysis.",
        "modality_target": "image",
        "expected_sim_boost": 0.20,
        "base_weight": 0.30
    }
}

class EvidenceGapAdvisor:
    def __init__(self, model: MultimodalFusionNet):
        self.model = model

    def rank_missing_evidence(
        self,
        current_features: np.ndarray,
        current_entropy: float,
        matched_brand_id: Optional[str] = None,
        critical_types: Optional[List[str]] = None
    ) -> List[EvidenceItem]:
        """
        Computes expected uncertainty reduction for each candidate evidence item
        and returns a sorted list of EvidenceItem objects.
        """
        checklist: List[EvidenceItem] = []
        
        # Consider all candidate items; boost items flagged as critical for the matched model
        evidence_keys = list(CANDIDATE_EVIDENCE_CATALOG.keys())
        
        for key in evidence_keys:
            meta = CANDIDATE_EVIDENCE_CATALOG[key]
            
            # Simulate features post-evidence acquisition
            simulated_feat = current_features.copy()
            
            if meta["modality_target"] == "image":
                # Evidence improves visual certainty (tightens similarity toward canonical reference)
                simulated_feat[0] = min(1.0, simulated_feat[0] + meta["expected_sim_boost"])
                simulated_feat[1] = simulated_feat[0] ** 2
                simulated_feat[2] = np.sqrt(simulated_feat[0])
                simulated_feat[3] = 1.0 if simulated_feat[0] >= 0.68 else 0.0
                simulated_feat[4] = 1.0 if simulated_feat[0] >= 0.85 else 0.0
                simulated_feat[5] = 0.0
            elif meta["modality_target"] == "meta":
                # Evidence resolves metadata ambiguity (price / seller uncertainty decreases)
                simulated_feat[17] = max(simulated_feat[17], 0.95) # High verified seller score
                simulated_feat[19] = max(0.0, simulated_feat[19] - 0.40) # Risk composite collapse
                
            # Measure new simulated uncertainty via MC-Dropout
            sim_res = estimate_mc_uncertainty(self.model, simulated_feat, n_samples=15)
            new_entropy = sim_res["total_entropy"]
            
            # Expected drop in entropy Delta H(e)
            raw_entropy_drop = max(0.02, current_entropy - new_entropy)
            
            # If item is explicitly in canonical model's critical list, apply domain relevance boost
            multiplier = 1.25 if (critical_types and key in critical_types) else 1.0
            expected_reduction = min(0.92, (raw_entropy_drop / max(0.1, current_entropy)) * multiplier)
            
            checklist.append(EvidenceItem(
                evidence_type=key,
                label=meta["label"],
                expected_uncertainty_reduction=round(float(expected_reduction), 3),
                rationale=meta["rationale"],
                verification_method=meta["verification_method"]
            ))
            
        # Sort descending by expected uncertainty reduction
        checklist.sort(key=lambda item: item.expected_uncertainty_reduction, reverse=True)
        return checklist
