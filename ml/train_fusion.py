"""
TrustLens Fusion Head Training Script with Modality Dropout
Trains the multimodal classification head on stratified dataset listings.
Saves checkpoint weights and evaluates train/val/test performance.
"""

import sys
import json
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.models.fusion_head import (
    MultimodalFusionNet,
    extract_multimodal_features,
    CLASS_NAMES
)
DATASET_FILE = BASE_DIR / "data" / "listings" / "dataset.json"
BRANDS_FILE = BASE_DIR / "data" / "brands" / "brands.json"
CHECKPOINTS_DIR = BASE_DIR / "ml" / "checkpoints"

CLASS_MAP = {name: i for i, name in enumerate(CLASS_NAMES)}

def load_data():
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        listings = json.load(f)["listings"]
        
    with open(BRANDS_FILE, "r", encoding="utf-8") as f:
        brands = {b["id"]: b for b in json.load(f)["brands"]}

    def process_split(split_name):
        X, y = [], []
        for row in listings:
            if row["split"] != split_name:
                continue
            
            # Compute price z-score
            b_info = brands.get(row["brand_id"])
            price_z = 0.0
            if b_info and row.get("price"):
                p_mean = b_info["price_stats"]["mean"]
                p_std = b_info["price_stats"]["std"]
                price_z = (row["price"] - p_mean) / p_std
                
            has_replica = any(kw in row["title"].lower() or kw in row.get("description", "").lower() 
                              for kw in ["replica", "1:1", "mirror", "clone"])
            has_homage = any(kw in row["title"].lower() or kw in row.get("description", "").lower() 
                             for kw in ["homage", "inspired", "tribute"])
            
            feat = extract_multimodal_features(
                visual_similarity=row.get("visual_similarity", 0.5),
                claims_brand_score=row.get("claims_brand_score", 0.5),
                price_z_score=price_z,
                seller_rating=row.get("seller_rating"),
                seller_reviews_count=row.get("seller_reviews_count"),
                has_homage_flags=has_homage,
                has_replica_flags=has_replica
            )
            X.append(feat)
            y.append(CLASS_MAP[row["label"]])
            
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)

    X_train, y_train = process_split("train")
    X_val, y_val = process_split("val")
    X_test, y_test = process_split("test")
    
    return (X_train, y_train), (X_val, y_val), (X_test, y_test)

def train_fusion_model(epochs: int = 150, lr: float = 0.02, modality_dropout_p: float = 0.25):
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = load_data()
    print(f"Data splits loaded: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
    
    model = MultimodalFusionNet(input_dim=20, hidden_dim=64, num_classes=4, modality_dropout_p=modality_dropout_p)
    model.training = True
    
    N = len(X_train)
    reg = 1e-4
    
    for epoch in range(epochs):
        # Forward pass with stochastic modality dropout
        # We manually compute gradients for the MLP layers
        x = X_train.copy()
        
        # Modality dropout mask on training batch
        if modality_dropout_p > 0 and np.random.rand() < 0.5:
            mod_choice = np.random.choice(["image", "text", "meta"])
            if mod_choice == "image": x[:, 0:8] = 0.0
            elif mod_choice == "text": x[:, 8:16] = 0.0
            elif mod_choice == "meta": x[:, 16:20] = 0.0
            
        # Layer 1
        z1 = np.dot(x, model.W1) + model.b1
        h1 = np.maximum(0.0, z1)
        
        # Layer 2
        z2 = np.dot(h1, model.W2) + model.b2
        h2 = np.maximum(0.0, z2)
        
        # Output layer
        logits = np.dot(h2, model.W3) + model.b3
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        
        # Cross-entropy loss
        log_probs = -np.log(probs[np.arange(N), y_train] + 1e-9)
        loss = np.mean(log_probs) + 0.5 * reg * (np.sum(model.W1**2) + np.sum(model.W2**2) + np.sum(model.W3**2))
        
        # Backward pass
        dlogits = probs.copy()
        dlogits[np.arange(N), y_train] -= 1.0
        dlogits /= N
        
        dW3 = np.dot(h2.T, dlogits) + reg * model.W3
        db3 = np.sum(dlogits, axis=0)
        
        dh2 = np.dot(dlogits, model.W3.T)
        dz2 = dh2 * (z2 > 0)
        
        dW2 = np.dot(h1.T, dz2) + reg * model.W2
        db2 = np.sum(dz2, axis=0)
        
        dh1 = np.dot(dz2, model.W2.T)
        dz1 = dh1 * (z1 > 0)
        
        dW1 = np.dot(x.T, dz1) + reg * model.W1
        db1 = np.sum(dz1, axis=0)
        
        # SGD update
        model.W3 -= lr * dW3
        model.b3 -= lr * db3
        model.W2 -= lr * dW2
        model.b2 -= lr * db2
        model.W1 -= lr * dW1
        model.b1 -= lr * db1
        
        if (epoch + 1) % 25 == 0:
            model.training = False
            _, val_probs = model.forward(X_val)
            val_preds = np.argmax(val_probs, axis=1)
            val_acc = np.mean(val_preds == y_val)
            print(f"Epoch [{epoch+1}/{epochs}] - Loss: {loss:.4f} - Val Accuracy: {val_acc:.4f}")
            model.training = True

    model.training = False
    
    # Evaluate on Test Set
    _, test_probs = model.forward(X_test)
    test_preds = np.argmax(test_probs, axis=1)
    test_acc = np.mean(test_preds == y_test)
    print(f"\nFinal Test Accuracy: {test_acc:.4f} ({np.sum(test_preds == y_test)}/{len(y_test)})")
    
    # Save checkpoint
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    chk_path = CHECKPOINTS_DIR / "fusion_weights.npz"
    np.savez(
        chk_path,
        W1=model.W1, b1=model.b1,
        W2=model.W2, b2=model.b2,
        W3=model.W3, b3=model.b3
    )
    print(f"Model checkpoint successfully saved to {chk_path}")
    return model, test_acc

if __name__ == "__main__":
    train_fusion_model()
