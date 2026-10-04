import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BRANDS_FILE = DATA_DIR / "brands" / "brands.json"
REFERENCE_CATALOG_DIR = DATA_DIR / "reference_catalog"
MODELS_DIR = BASE_DIR / "ml" / "checkpoints"
REPORTS_DIR = BASE_DIR / "reports"

# Thresholds
TAU_SIMILARITY = 0.65       # Cosine similarity threshold for visual resemblance
TAU_CLAIM = 0.50            # Threshold for textual brand claim score
TAU_ENTROPY = 1.65          # Shannon entropy threshold for classifying as 'Uncertain' (max is 2.0 for 4 classes)
PRICE_Z_THRESHOLD = -1.8    # Standard deviations below brand mean price triggering high risk

# Model configurations
CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
TEXT_MODEL_NAME = "distilbert-base-uncased"
EMBEDDING_DIM = 512
NUM_CLASSES = 4
CLASS_NAMES = [
    "Likely Authentic",
    "Potential Counterfeit",
    "Legitimate Look-alike",
    "Uncertain"
]

# MC-Dropout settings
MC_DROPOUT_SAMPLES = 20
DROPOUT_RATE = 0.3
MODALITY_DROPOUT_P = 0.25
