"""
TrustLens Uncertainty Estimation Module (Monte Carlo Dropout)
Estimates epistemic and aleatoric predictive uncertainty using MC-Dropout forward passes.
Explicitly computes predictive entropy, predictive variance, and mutual information.
"""

import numpy as np
from typing import Dict, Any, Tuple
from backend.models.fusion_head import MultimodalFusionNet

def estimate_mc_uncertainty(
    model: MultimodalFusionNet,
    features: np.ndarray,
    n_samples: int = 20
) -> Dict[str, Any]:
    """
    Performs Monte Carlo Dropout inference by executing T forward passes with active dropout.
    
    Mathematical Formulation:
      - Mean probability: \bar{p} = (1/T) * sum_{t=1}^T p^{(t)}
      - Total predictive uncertainty (Shannon Entropy): H(\bar{p}) = -sum_k \bar{p}_k log2(\bar{p}_k)
      - Aleatoric uncertainty: (1/T) * sum_{t=1}^T H(p^{(t)})
      - Epistemic uncertainty (Mutual Information): I(y, w | x) = H(\bar{p}) - Aleatoric
      - Predictive variance: Var(p) = (1/T) * sum_{t=1}^T (p^{(t)} - \bar{p})^2
    
    Honesty in implementation:
      - Epistemic uncertainty measures the model's lack of knowledge (dropout disagreement).
      - Aleatoric uncertainty measures inherent data noise.
      - Total predictive entropy combines both.
    """
    eps = 1e-9
    samples = []
    sample_entropies = []
    
    for _ in range(n_samples):
        # Forward pass with active dropout
        _, probs = model.forward(features, apply_dropout=True)
        samples.append(probs)
        h_t = -np.sum(probs * np.log2(probs + eps))
        sample_entropies.append(h_t)
        
    samples = np.array(samples) # Shape: (T, num_classes)
    
    mean_probs = np.mean(samples, axis=0)
    predictive_variance = np.var(samples, axis=0)
    mean_variance = float(np.mean(predictive_variance))
    
    total_entropy = float(-np.sum(mean_probs * np.log2(mean_probs + eps)))
    aleatoric_entropy = float(np.mean(sample_entropies))
    epistemic_mutual_info = float(max(0.0, total_entropy - aleatoric_entropy))
    
    # Confidence is max mean probability
    confidence = float(np.max(mean_probs))
    predicted_class_idx = int(np.argmax(mean_probs))
    
    return {
        "mean_probs": mean_probs,
        "predicted_class_idx": predicted_class_idx,
        "confidence": confidence,
        "total_entropy": total_entropy,
        "aleatoric_uncertainty": aleatoric_entropy,
        "epistemic_uncertainty": epistemic_mutual_info,
        "predictive_variance": mean_variance
    }
