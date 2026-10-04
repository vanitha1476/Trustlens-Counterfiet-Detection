"""
TrustLens Multimodal Fusion Head with Modality Dropout
Combines Image representations, Text Claim representations, and Listing Metadata.
Features Modality Dropout during training to ensure resilience against missing inputs.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

# Try importing torch; if not present yet, use native numpy neural execution
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

CLASS_NAMES = [
    "Likely Authentic",
    "Potential Counterfeit",
    "Legitimate Look-alike",
    "Uncertain"
]

class MultimodalFusionNet:
    """
    Multimodal Fusion Network with Modality Dropout.
    Supports both PyTorch and vector-optimized NumPy execution.
    Input dimensions:
      - Image features: 8
      - Text features: 8
      - Metadata/Seller features: 4
      Total input dimension: 20
    Outputs: 4 classes logits.
    """
    def __init__(self, input_dim: int = 20, hidden_dim: int = 64, num_classes: int = 4, modality_dropout_p: float = 0.25):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_classes = num_classes
        self.modality_dropout_p = modality_dropout_p
        
        # Initialize deterministic weights
        rng = np.random.RandomState(42)
        # He / Kaiming normal initialization
        self.W1 = rng.randn(input_dim, hidden_dim) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros(hidden_dim)
        self.W2 = rng.randn(hidden_dim, 32) * np.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros(32)
        self.W3 = rng.randn(32, num_classes) * np.sqrt(2.0 / 32)
        self.b3 = np.zeros(num_classes)
        
        self.training = False

    def forward(
        self,
        features: np.ndarray,
        modality_mask: Optional[Dict[str, bool]] = None,
        apply_dropout: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Forward pass with optional modality dropout.
        features: shape (N, 20) or (20,)
        modality_mask: {'image': True/False, 'text': True/False, 'meta': True/False}
        Returns: (logits, probabilities)
        """
        x = np.array(features, dtype=np.float32)
        single_sample = (x.ndim == 1)
        if single_sample:
            x = x.reshape(1, -1)
            
        N = x.shape[0]
        x_masked = x.copy()
        
        # Modality masking
        # Image modality: indices 0:8
        # Text modality: indices 8:16
        # Metadata modality: indices 16:20
        if modality_mask:
            if not modality_mask.get("image", True):
                x_masked[:, 0:8] = 0.0
            if not modality_mask.get("text", True):
                x_masked[:, 8:16] = 0.0
            if not modality_mask.get("meta", True):
                x_masked[:, 16:20] = 0.0
        elif (self.training or apply_dropout) and self.modality_dropout_p > 0:
            # Apply stochastic modality dropout
            if np.random.rand() < self.modality_dropout_p:
                x_masked[:, 0:8] = 0.0
            if np.random.rand() < self.modality_dropout_p:
                x_masked[:, 8:16] = 0.0
            if np.random.rand() < self.modality_dropout_p:
                x_masked[:, 16:20] = 0.0

        # Layer 1
        h1 = np.maximum(0.0, np.dot(x_masked, self.W1) + self.b1)
        if (self.training or apply_dropout):
            drop_mask = (np.random.rand(*h1.shape) >= 0.2).astype(np.float32) / 0.8
            h1 *= drop_mask
            
        # Layer 2
        h2 = np.maximum(0.0, np.dot(h1, self.W2) + self.b2)
        
        # Logits
        logits = np.dot(h2, self.W3) + self.b3
        
        # Stable Softmax
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        
        if single_sample:
            return logits[0], probs[0]
        return logits, probs

    def compute_entropy(self, probs: np.ndarray) -> float:
        """Computes Shannon entropy: H(p) = -sum p_k * log2(p_k)"""
        eps = 1e-9
        return float(-np.sum(probs * np.log2(probs + eps)))

def extract_multimodal_features(
    visual_similarity: float,
    claims_brand_score: float,
    price_z_score: Optional[float],
    seller_rating: Optional[float],
    seller_reviews_count: Optional[int],
    has_homage_flags: bool,
    has_replica_flags: bool
) -> np.ndarray:
    """
    Constructs a standardized 20-dimensional multimodal feature vector.
    Indices:
      [0..7]: Image features (similarity, non-linear power activations)
      [8..15]: Text features (claim score, replica indicator, homage indicator)
      [16..19]: Listing metadata (price z-score, normalized seller rating, log reviews)
    """
    feat = np.zeros(20, dtype=np.float32)
    
    # 1. Image Modality (8 dims)
    sim = max(0.0, min(1.0, visual_similarity))
    feat[0] = sim
    feat[1] = sim ** 2
    feat[2] = np.sqrt(sim)
    feat[3] = 1.0 if sim >= 0.68 else 0.0 # Strict threshold flag
    feat[4] = 1.0 if sim >= 0.85 else 0.0 # High match flag
    feat[5] = 1.0 if sim < 0.50 else 0.0  # Low match flag
    feat[6] = max(0.0, sim - 0.68)        # Margin above threshold
    feat[7] = max(0.0, 0.68 - sim)        # Margin below threshold
    
    # 2. Text Modality (8 dims)
    claim = max(0.0, min(1.0, claims_brand_score))
    feat[8] = claim
    feat[9] = claim ** 2
    feat[10] = 1.0 if claim >= 0.45 else 0.0
    feat[11] = 1.0 if has_replica_flags else 0.0
    feat[12] = 1.0 if has_homage_flags else 0.0
    feat[13] = claim * (1.0 - (1.0 if has_homage_flags else 0.0))
    feat[14] = feat[3] * feat[10] # Intersection: looks_similar AND claims_brand
    feat[15] = feat[3] * (1.0 - feat[10]) # Intersection: looks_similar AND NOT claims_brand (Look-alike signature)

    # 3. Metadata Modality (4 dims)
    # Price z-score
    pz = price_z_score if price_z_score is not None else 0.0
    feat[16] = np.clip(pz, -3.0, 3.0) / 3.0
    
    # Seller rating (0 to 1)
    sr = (seller_rating / 100.0) if (seller_rating is not None and seller_rating > 0) else 0.85
    feat[17] = sr
    
    # Seller reviews count (log scale)
    rc = np.log1p(float(seller_reviews_count)) / 10.0 if (seller_reviews_count is not None and seller_reviews_count > 0) else 0.5
    feat[18] = min(1.0, rc)
    
    # Combined risk composite
    risk_comp = 0.0
    if pz < -1.8: risk_comp += 0.5
    if sr < 0.75: risk_comp += 0.3
    if has_replica_flags: risk_comp += 0.4
    feat[19] = min(1.0, risk_comp)
    
    return feat
