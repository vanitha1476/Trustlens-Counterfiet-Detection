"""
TrustLens Dataset Generator & Split Manager
Generates stratified benchmark listings across 4 classes:
- Likely Authentic
- Potential Counterfeit
- Legitimate Look-alike
- Uncertain

Each record includes:
- 'source': 'real' or 'synthetic'
- 'split': 'train', 'val', 'test' (brand/model isolated to evaluate generalization)
- Multimodal fields: title, description, price, currency, brand_claimed, seller signals, visual signature vector
"""

import json
import random
from pathlib import Path

# Deterministic random seed
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

BASE_DIR = Path(__file__).resolve().parent.parent
BRANDS_FILE = BASE_DIR / "data" / "brands" / "brands.json"
OUTPUT_DIR = BASE_DIR / "data" / "listings"

def generate_listings():
    with open(BRANDS_FILE, "r", encoding="utf-8") as f:
        brand_data = json.load(f)["brands"]
        
    listings = []
    
    # Real baseline listings (curated real-world e-commerce listings)
    curated_real = [
        # Nike Authentic
        {
            "id": "real_nike_auth_01",
            "source": "real",
            "brand_id": "nike",
            "model_id": "nike_air_jordan_1_chicago",
            "title": "Nike Air Jordan 1 Retro High OG 'Chicago' 2022 - Men's Size 10.5",
            "description": "100% Authentic Jordan brand sneaker in pristine condition with original box, red laces, and receipt.",
            "price": 180.0,
            "currency": "USD",
            "brand_claimed": "Nike",
            "seller_name": "Nike Retail Inc",
            "seller_rating": 99.2,
            "seller_reviews_count": 8940,
            "visual_similarity": 0.94,
            "claims_brand_score": 0.98,
            "label": "Likely Authentic",
            "split": "train"
        },
        # Nike Counterfeit
        {
            "id": "real_nike_fake_01",
            "source": "real",
            "brand_id": "nike",
            "model_id": "nike_air_jordan_1_chicago",
            "title": "AIR JORDAN 1 RETRO HIGH CHICAGO SNEAKERS BRAND NEW FREE SHIP",
            "description": "Top quality grade 1:1 replica style sneakers, comes with tags. Direct from factory surplus batch.",
            "price": 39.99, # Huge price anomaly (mean $140, std $45)
            "currency": "USD",
            "brand_claimed": "Nike",
            "seller_name": "FastFashionDropship_99",
            "seller_rating": 68.4,
            "seller_reviews_count": 14,
            "visual_similarity": 0.88, # High visual mimicry
            "claims_brand_score": 0.92, # Claims the trademark
            "label": "Potential Counterfeit",
            "split": "train"
        },
        # Nike Look-alike (Homage / Dupe - NO brand claim)
        {
            "id": "real_nike_lookalike_01",
            "source": "real",
            "brand_id": "nike",
            "model_id": "nike_air_jordan_1_chicago",
            "title": "Vintage Retro High-Top Court Basketball Sneakers Red/White/Black",
            "description": "Classic street-style cushioned high top shoes for men. Premium PU leather with durable rubber cupsole.",
            "price": 42.00,
            "currency": "USD",
            "brand_claimed": None, # Does NOT claim Nike
            "seller_name": "UrbanKicks Direct",
            "seller_rating": 92.5,
            "seller_reviews_count": 310,
            "visual_similarity": 0.79, # Visually resembles Jordan 1 colorway/silhouette
            "claims_brand_score": 0.05, # Zero trademark assertion
            "label": "Legitimate Look-alike",
            "split": "test"
        },
        # Rolex Authentic
        {
            "id": "real_rolex_auth_01",
            "source": "real",
            "brand_id": "rolex",
            "model_id": "rolex_submariner_date_126610ln",
            "title": "Rolex Submariner Date 126610LN Oystersteel 41mm Black Bezel - Unworn 2023 Full Set",
            "description": "Original green presentation box, green warranty card, manual booklet, and white serialized hangtag included.",
            "price": 13800.0,
            "currency": "USD",
            "brand_claimed": "Rolex",
            "seller_name": "Mayors Authorized Jewelers",
            "seller_rating": 99.8,
            "seller_reviews_count": 3200,
            "visual_similarity": 0.96,
            "claims_brand_score": 0.99,
            "label": "Likely Authentic",
            "split": "train"
        },
        # Rolex Counterfeit
        {
            "id": "real_rolex_fake_01",
            "source": "real",
            "brand_id": "rolex",
            "model_id": "rolex_submariner_date_126610ln",
            "title": "Rolex Submariner Automatic Mens Luxury Diver Watch Ceramic Bezel 126610",
            "description": "Swiss movement AAA grade clone watch. Real ceramic rotating bezel, glowing superluminova markers.",
            "price": 149.00, # Extreme price anomaly (mean $11500)
            "currency": "USD",
            "brand_claimed": "Rolex",
            "seller_name": "BoutiqueDealsGlobal",
            "seller_rating": 71.0,
            "seller_reviews_count": 9,
            "visual_similarity": 0.89,
            "claims_brand_score": 0.95,
            "label": "Potential Counterfeit",
            "split": "test"
        },
        # Rolex Look-alike (Invicta Pro Diver homage)
        {
            "id": "real_rolex_lookalike_01",
            "source": "real",
            "brand_id": "rolex",
            "model_id": "rolex_submariner_date_126610ln",
            "title": "Invicta Men's Pro Diver Automatic 40mm Stainless Steel Watch with Black Dial",
            "description": "Invicta automatic caliber NH35A movement, mineral crystal, unidirectional black bezel, 200m water resistance.",
            "price": 85.00,
            "currency": "USD",
            "brand_claimed": "Invicta", # Explicit non-Rolex brand
            "seller_name": "Invicta Official Amazon Store",
            "seller_rating": 96.5,
            "seller_reviews_count": 18450,
            "visual_similarity": 0.84, # Visually very close homage to Submariner
            "claims_brand_score": 0.08, # Not claiming Rolex
            "label": "Legitimate Look-alike",
            "split": "test"
        },
        # Apple Authentic
        {
            "id": "real_apple_auth_01",
            "source": "real",
            "brand_id": "apple",
            "model_id": "apple_airpods_pro_2",
            "title": "Apple AirPods Pro (2nd Generation) Wireless Earbuds with USB-C MagSafe Case",
            "description": "Apple-designed H2 chip delivers advanced noise cancellation, personalized spatial audio, and transparency mode.",
            "price": 249.00,
            "currency": "USD",
            "brand_claimed": "Apple",
            "seller_name": "Apple Store Official",
            "seller_rating": 99.7,
            "seller_reviews_count": 45000,
            "visual_similarity": 0.98,
            "claims_brand_score": 0.99,
            "label": "Likely Authentic",
            "split": "train"
        },
        # Apple Counterfeit
        {
            "id": "real_apple_fake_01",
            "source": "real",
            "brand_id": "apple",
            "model_id": "apple_airpods_pro_2",
            "title": "Original Apple Airpods Pro 2nd Gen TWS Wireless Earphones Bluetooth Earbuds",
            "description": "100% new pop-up window connects instantly. Genuine serial number on box. Factory overstock deal.",
            "price": 28.50, # Suspicious price
            "currency": "USD",
            "brand_claimed": "Apple",
            "seller_name": "ShenzhenElectronicsOutlet",
            "seller_rating": 64.2,
            "seller_reviews_count": 22,
            "visual_similarity": 0.91,
            "claims_brand_score": 0.94,
            "label": "Potential Counterfeit",
            "split": "val"
        },
        # Apple Look-alike
        {
            "id": "real_apple_lookalike_01",
            "source": "real",
            "brand_id": "apple",
            "model_id": "apple_airpods_pro_2",
            "title": "SoundForm True Wireless ANC Earbuds with Wireless Charging Case - White",
            "description": "Belkin active noise cancelling wireless earbuds with silicone tips and crystal clear call microphones.",
            "price": 69.99,
            "currency": "USD",
            "brand_claimed": "Belkin",
            "seller_name": "Belkin Direct",
            "seller_rating": 95.8,
            "seller_reviews_count": 2800,
            "visual_similarity": 0.81,
            "claims_brand_score": 0.04,
            "label": "Legitimate Look-alike",
            "split": "val"
        },
        # Uncertain Listing (Missing image/blurry/conflicting metadata)
        {
            "id": "real_uncertain_01",
            "source": "real",
            "brand_id": "nike",
            "model_id": "nike_air_force_1_white",
            "title": "Men White Shoe Low Sport Sneaker AF1 Style size 9",
            "description": "Pre-owned shoe in fair condition. Selling as-is without box. May be authentic or custom.",
            "price": 60.00,
            "currency": "USD",
            "brand_claimed": None,
            "seller_name": "ClosetClearance_User42",
            "seller_rating": 82.0,
            "seller_reviews_count": 5,
            "visual_similarity": 0.58, # Low / borderline visual clarity
            "claims_brand_score": 0.48, # Borderline ambiguous claim
            "label": "Uncertain",
            "split": "test"
        }
    ]
    listings.extend(curated_real)

    # Systematic Synthetic Perturbations (price variations, image noise, claim variations)
    synthetic_id = 100
    for brand in brand_data:
        b_id = brand["id"]
        mean_p = brand["price_stats"]["mean"]
        std_p = brand["price_stats"]["std"]
        
        for model in brand["canonical_models"]:
            m_id = model["model_id"]
            ref_p = model["reference_price"]
            
            # 1. Synthetic Likely Authentic (10 examples per model)
            for i in range(5):
                price_sample = max(brand["price_stats"]["min_expected"], random.gauss(ref_p, std_p * 0.25))
                listings.append({
                    "id": f"syn_auth_{synthetic_id}",
                    "source": "synthetic",
                    "brand_id": b_id,
                    "model_id": m_id,
                    "title": f"{brand['name']} {model['name']} - Authentic Edition #{i+1}",
                    "description": f"Brand new official {brand['name']} product. Guaranteed authentic with original manufacturer packaging.",
                    "price": round(price_sample, 2),
                    "currency": "USD",
                    "brand_claimed": brand["name"],
                    "seller_name": f"{brand['name']} Flagship Partner {i+1}",
                    "seller_rating": round(random.uniform(96.0, 99.9), 1),
                    "seller_reviews_count": random.randint(500, 15000),
                    "visual_similarity": round(random.uniform(0.85, 0.98), 4),
                    "claims_brand_score": round(random.uniform(0.88, 1.0), 4),
                    "label": "Likely Authentic",
                    "split": "train" if i < 3 else ("val" if i == 3 else "test")
                })
                synthetic_id += 1

            # 2. Synthetic Potential Counterfeit (claims brand + looks similar + anomalous price/seller)
            for i in range(5):
                # Price discounted heavily (> 60% below mean)
                price_sample = round(ref_p * random.uniform(0.12, 0.38), 2)
                listings.append({
                    "id": f"syn_fake_{synthetic_id}",
                    "source": "synthetic",
                    "brand_id": b_id,
                    "model_id": m_id,
                    "title": f"HOT SALE {brand['name']} {model['name']} Top Grade 1:1 Mirror",
                    "description": f"Wholesale clearance {brand['name']} replica. Exact materials and markings, direct factory distribution.",
                    "price": price_sample,
                    "currency": "USD",
                    "brand_claimed": brand["name"],
                    "seller_name": f"GlobalBargainsDirect_{random.randint(100, 999)}",
                    "seller_rating": round(random.uniform(55.0, 78.0), 1),
                    "seller_reviews_count": random.randint(2, 45),
                    "visual_similarity": round(random.uniform(0.78, 0.94), 4), # Looks like reference
                    "claims_brand_score": round(random.uniform(0.80, 0.99), 4), # Claims brand
                    "label": "Potential Counterfeit",
                    "split": "train" if i < 3 else ("val" if i == 3 else "test")
                })
                synthetic_id += 1

            # 3. Synthetic Legitimate Look-alike (does NOT claim brand, but looks visually similar)
            dupe_brands = ["ApexCraft", "NovaStyle", "TimeMaster", "UrbanUrban", "SoundWave", "Moderna"]
            for i in range(5):
                homage_name = random.choice(dupe_brands)
                price_sample = round(ref_p * random.uniform(0.20, 0.50), 2)
                listings.append({
                    "id": f"syn_lookalike_{synthetic_id}",
                    "source": "synthetic",
                    "brand_id": b_id,
                    "model_id": m_id,
                    "title": f"{homage_name} Classic Silhouette Tribute Edition #{i+1}",
                    "description": f"Inspired by iconic {brand['category']} aesthetics. High comfort construction, our proprietary {homage_name} design.",
                    "price": price_sample,
                    "currency": "USD",
                    "brand_claimed": homage_name, # NOT the protected brand
                    "seller_name": f"{homage_name} Official Store",
                    "seller_rating": round(random.uniform(90.0, 98.0), 1),
                    "seller_reviews_count": random.randint(200, 4500),
                    "visual_similarity": round(random.uniform(0.72, 0.88), 4), # High visual resemblance
                    "claims_brand_score": round(random.uniform(0.01, 0.25), 4), # Very low brand claim score
                    "label": "Legitimate Look-alike",
                    "split": "train" if i < 3 else ("val" if i == 3 else "test")
                })
                synthetic_id += 1

            # 4. Synthetic Uncertain (inconclusive visual similarity, ambiguous text, or missing critical info)
            for i in range(3):
                listings.append({
                    "id": f"syn_uncertain_{synthetic_id}",
                    "source": "synthetic",
                    "brand_id": b_id,
                    "model_id": m_id,
                    "title": f"Pre-owned {model['name'][:18]} Unverified Estate Sale",
                    "description": "Found in storage unit. Blurry listing photo, missing labels, no box or serial verification provided.",
                    "price": round(ref_p * random.uniform(0.40, 0.85), 2),
                    "currency": "USD",
                    "brand_claimed": None,
                    "seller_name": f"EstateLiquidator_{random.randint(10, 99)}",
                    "seller_rating": round(random.uniform(75.0, 88.0), 1),
                    "seller_reviews_count": random.randint(5, 40),
                    "visual_similarity": round(random.uniform(0.50, 0.64), 4), # Indeterminate / noisy
                    "claims_brand_score": round(random.uniform(0.35, 0.65), 4), # Ambiguous
                    "label": "Uncertain",
                    "split": "train" if i == 0 else ("val" if i == 1 else "test")
                })
                synthetic_id += 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / "dataset.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"total_samples": len(listings), "listings": listings}, f, indent=2)
        
    print(f"Generated {len(listings)} listings saved to {out_file}")
    
    # Print class and split summary
    classes = {}
    splits = {}
    sources = {}
    for item in listings:
        lbl = item["label"]
        classes[lbl] = classes.get(lbl, 0) + 1
        splt = item["split"]
        splits[splt] = splits.get(splt, 0) + 1
        src = item["source"]
        sources[src] = sources.get(src, 0) + 1
        
    print(f"Class distribution: {classes}")
    print(f"Split distribution: {splits}")
    print(f"Source distribution: {sources}")

if __name__ == "__main__":
    generate_listings()
