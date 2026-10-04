# TrustLens: Proactive Multimodal Fake & Look-alike Detection

TrustLens is a shopper-side Chrome Extension (Manifest V3) backed by a local deep learning inference engine (FastAPI) that verifies product authenticity directly on e-commerce product pages without requiring manual image uploads.

---

## Key Novelties
1. **Claim vs Appearance Check**: A strict rule layer separating legitimate look-alikes / homage products (visually similar without brand claims) from potential counterfeits (claiming the trademark while displaying anomalies).
2. **Evidence-Gap Advisor**: When classification is uncertain, the model calculates which specific missing piece of evidence (e.g., inner label, batch code, packaging box) would reduce predictive entropy the most and presents a ranked checklist.

---

## Directory Structure
```text
├── backend/
│   ├── app.py             # FastAPI backend with /health and /predict
│   ├── config.py          # Thresholds, model configs, and path constants
│   └── schemas.py         # Pydantic data schemas
├── extension/             # Chrome Extension (Manifest V3)
│   ├── manifest.json      # Extension manifest
│   ├── popup.html         # Inspection popup UI
│   ├── popup.css          # Styling & dark-mode theme
│   ├── popup.js           # Client-side UI logic
│   ├── content.js         # DOM scraper
│   ├── background.js      # Service worker API bridge
│   └── icons/             # 16px, 48px, 128px assets
├── data/
│   ├── brands/            # Canonical brand catalog (brands.json)
│   └── reference_catalog/ # Reference image embeddings
├── docs/
│   ├── labeling_rules.md  # 4-class definitions and claim vs appearance rules
│   └── assumptions.md     # Documented engineering and ML assumptions
├── reports/               # Evaluation tables and ablation outputs
├── tests/
│   └── test_phase1.py     # Phase 1 test suite
├── run_backend.bat        # Windows one-click backend launcher
└── requirements.txt       # Python dependencies
```

---

## Quickstart Guide (Windows)

### 1. Install Dependencies
In PowerShell or Command Prompt:
```powershell
pip install -r requirements.txt
```

### 2. Run the Backend
Double-click `run_backend.bat` or run:
```powershell
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
Verify the server is running by opening: `http://localhost:8000/health`

### 3. Load the Chrome Extension
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Toggle **Developer mode** (top-right corner) to **ON**.
3. Click **Load unpacked** (top-left button).
4. Select the `extension/` folder inside this project directory.
5. The **TrustLens** icon will appear in your Chrome toolbar.

## Running All Tests
To run the full unit and integration test suite (28 tests across all phases):
```powershell
python -m pytest tests/ -v
```

---

## Evaluation & Ablation Results
To reproduce the evaluation benchmarks, ablations, and calibration statistics:
```powershell
python ml/evaluate.py
```
Detailed results are saved in [`reports/results_summary.md`](file:///c:/Users/vanit/DL%20PROJECT/reports/results_summary.md).

---

## Lab Defense & Oral Viva Notes
For technical interview preparation, viva questions, and a 5-minute live demo script, see:
[`docs/viva_notes.md`](file:///c:/Users/vanit/DL%20PROJECT/docs/viva_notes.md).

For data labeling criteria and class boundaries, see:
[`docs/labeling_rules.md`](file:///c:/Users/vanit/DL%20PROJECT/docs/labeling_rules.md).

