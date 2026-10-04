from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ScrapedProductPayload(BaseModel):
    url: Optional[str] = Field(default="", description="URL of the product listing")
    title: Optional[str] = Field(default="", description="Listing title scraped from DOM")
    price: Optional[float] = Field(default=None, description="Scraped numeric price")
    currency: Optional[str] = Field(default="USD", description="Scraped or detected currency")
    brand_claimed: Optional[str] = Field(default=None, description="Brand name claimed in structured data or text")
    seller_name: Optional[str] = Field(default=None, description="Store or seller username")
    seller_rating: Optional[float] = Field(default=None, description="Seller feedback percentage or rating (0-5 or 0-100)")
    seller_reviews_count: Optional[int] = Field(default=None, description="Total number of seller ratings/reviews")
    description: Optional[str] = Field(default="", description="Product text description or bullet points")
    image_urls: List[str] = Field(default_factory=list, description="List of product image URLs scraped from page")
    additional_evidence_type: Optional[str] = Field(default=None, description="Optional evidence tag if user uploaded extra item")
    uploaded_image_base64: Optional[str] = Field(default=None, description="Base64 encoded extra photo if supplied by user")

class ClaimVsAppearance(BaseModel):
    claims_brand: bool = Field(description="Strict boolean whether listing claims the brand name/trademark")
    claim_confidence: float = Field(description="Confidence score [0.0, 1.0] from keyword + semantic text model")
    looks_similar: bool = Field(description="Boolean whether visual match exceeds appearance threshold")
    visual_similarity: float = Field(description="Cosine similarity [0.0, 1.0] against brand reference catalog")
    matched_brand_id: Optional[str] = Field(default=None, description="Matched canonical brand identifier")
    matched_model_id: Optional[str] = Field(default=None, description="Closest canonical product model")
    rule_applied: str = Field(description="Explicit human-readable rule branch explaining the decision")

class EvidenceItem(BaseModel):
    evidence_type: str = Field(description="Identifier of missing evidence (e.g. inner_label, serial_batch_code)")
    label: str = Field(description="Plain English title")
    expected_uncertainty_reduction: float = Field(description="Estimated reduction in predictive entropy [0.0, 1.0]")
    rationale: str = Field(description="Explanation of why this evidence resolves the uncertainty")
    verification_method: str = Field(description="What the user or verification model inspects")

class RiskSignal(BaseModel):
    signal_name: str
    severity: str  # "high", "medium", "low", "info"
    description: str
    value: Optional[Any] = None

class PredictionResponse(BaseModel):
    status: str = "success"
    classification: str = Field(
        description="One of: 'Likely Authentic', 'Potential Counterfeit', 'Legitimate Look-alike', 'Uncertain'"
    )
    confidence: float = Field(description="Model prediction confidence [0.0, 1.0]")
    predictive_entropy: float = Field(description="Predictive uncertainty / Shannon entropy")
    is_uncertain: bool = Field(description="True if uncertainty triggers the Evidence-Gap Advisor")
    claim_vs_appearance: ClaimVsAppearance
    risk_signals: List[RiskSignal] = Field(default_factory=list)
    evidence_checklist: List[EvidenceItem] = Field(default_factory=list, description="Ranked checklist if uncertain")
    explanation_summary: str = Field(description="Concise, plain-English summary of the verdict")
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    models_loaded: Dict[str, bool]
    reference_catalog_size: int
