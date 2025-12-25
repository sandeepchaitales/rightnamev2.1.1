from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Literal, Union, Any
from datetime import datetime, timezone
import uuid

class DimensionScore(BaseModel):
    name: str
    score: float
    reasoning: str

class TrademarkRiskRow(BaseModel):
    likelihood: int = Field(default=1)
    severity: int = Field(default=1)
    zone: str = Field(default="Green")
    commentary: str = Field(default="No specific risk identified")

class TrademarkRiskMatrix(BaseModel):
    genericness: Optional[TrademarkRiskRow] = Field(default_factory=lambda: TrademarkRiskRow())
    existing_conflicts: Optional[TrademarkRiskRow] = Field(default_factory=lambda: TrademarkRiskRow())
    phonetic_similarity: Optional[TrademarkRiskRow] = Field(default_factory=lambda: TrademarkRiskRow())
    relevant_classes: Optional[TrademarkRiskRow] = Field(default_factory=lambda: TrademarkRiskRow())
    rebranding_probability: Optional[TrademarkRiskRow] = Field(default_factory=lambda: TrademarkRiskRow())
    overall_assessment: str = Field(default="Risk assessment pending")

class DomainAnalysis(BaseModel):
    exact_match_status: str
    risk_level: Optional[str] = Field(default="LOW", description="LOW/MEDIUM/HIGH - .com alone = LOW risk")
    has_active_business: Optional[str] = Field(default="UNKNOWN", description="Is there an operating business?")
    has_trademark: Optional[str] = Field(default="UNKNOWN", description="Is there a registered TM?")
    alternatives: List[Union[Dict[str, str], str]] = Field(default=[])
    strategy_note: str = Field(default="")
    score_impact: Optional[str] = Field(default="-1 point max for taken .com", description="Score impact explanation")
    
    @field_validator('alternatives', mode='before')
    @classmethod
    def normalize_alternatives(cls, v):
        """Handle both string and dict formats for domain alternatives"""
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                # Convert string to dict format
                result.append({"domain": item, "status": "suggested"})
            elif isinstance(item, dict):
                result.append(item)
        return result

class DomainCheckResult(BaseModel):
    domain: str
    status: str
    available: Optional[bool] = None
    
    @field_validator('available', mode='before')
    @classmethod
    def parse_available(cls, v):
        if v is None or v == 'unknown' or v == 'Unknown' or v == '':
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', 'yes', '1', 'available')
        return None

class MultiDomainAvailability(BaseModel):
    category_domains: List[DomainCheckResult] = Field(default=[], description="Category-specific TLDs like .shop, .tech")
    country_domains: List[DomainCheckResult] = Field(default=[], description="Country-specific TLDs like .in, .co.uk")
    recommended_domain: Optional[str] = None
    acquisition_strategy: Optional[str] = None

class SocialHandleResult(BaseModel):
    platform: str
    handle: str
    status: str
    available: Optional[bool] = None
    
    @field_validator('available', mode='before')
    @classmethod
    def parse_available(cls, v):
        if v is None or v == 'unknown' or v == 'Unknown' or v == '':
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', 'yes', '1', 'available')
        return None

class SocialAvailability(BaseModel):
    handle: str
    platforms: List[SocialHandleResult] = Field(default=[], description="Social platform availability")
    available_platforms: List[str] = Field(default=[], description="List of available platforms")
    taken_platforms: List[str] = Field(default=[], description="List of taken platforms")
    recommendation: Optional[str] = None

class ConflictItem(BaseModel):
    name: str
    category: str
    their_product_intent: Optional[str] = Field(default=None, description="What does this product DO?")
    their_customer_avatar: Optional[str] = Field(default=None, description="Who uses this competitor/app")
    intent_match: Optional[str] = Field(default=None, description="SAME/DIFFERENT - Does it solve the same problem?")
    customer_overlap: Optional[str] = Field(default=None, description="HIGH/NONE - overlap with user's customers")
    risk_level: str = Field(default="LOW", description="HIGH only if SAME intent + SAME customers")
    reason: Optional[str] = None

class PhoneticConflict(BaseModel):
    input_name: Optional[str] = None
    phonetic_variants: List[str] = Field(default=[])
    ipa_pronunciation: Optional[str] = None
    found_conflict: Optional[Dict[str, Any]] = None
    conflict_type: Optional[str] = Field(default="NONE")
    legal_risk: Optional[str] = None
    verdict_impact: Optional[str] = None

class VisibilityAnalysis(BaseModel):
    user_product_intent: Optional[str] = Field(default=None, description="What does the user's product DO?")
    user_customer_avatar: Optional[str] = Field(default=None, description="Who buys the user's product")
    phonetic_conflicts: List[PhoneticConflict] = Field(default=[], description="Phonetically similar names in same category - CRITICAL")
    direct_competitors: List[ConflictItem] = Field(default=[], description="Same intent + same customers - HIGH risk")
    name_twins: List[ConflictItem] = Field(default=[], description="Keyword matches with different intent/customers - LOW risk, NOT rejection factors")
    google_presence: List[Any] = Field(default=[])
    app_store_presence: List[Any] = Field(default=[])
    warning_triggered: bool = Field(default=False)
    warning_reason: Optional[str] = None
    conflict_summary: Optional[str] = Field(default=None, description="Summary distinguishing real conflicts from false positives")

class CountryAnalysis(BaseModel):
    country: str
    cultural_resonance_score: float
    cultural_notes: str
    linguistic_check: str

class Competitor(BaseModel):
    name: str
    x_coordinate: Optional[float] = Field(default=50, description="X-axis position 0-100")
    y_coordinate: Optional[float] = Field(default=50, description="Y-axis position 0-100")
    price_position: Optional[str] = Field(default=None, description="Price positioning description")
    category_position: Optional[str] = Field(default=None, description="Category-specific positioning")
    quadrant: Optional[str] = Field(default="Center", description="Quadrant Name")
    # Legacy fields for backward compatibility
    price_axis: Optional[str] = Field(default=None, description="Legacy: X-Axis description")
    modernity_axis: Optional[str] = Field(default=None, description="Legacy: Y-Axis description")
    
    @field_validator('x_coordinate', 'y_coordinate', mode='before')
    @classmethod
    def parse_coordinate(cls, v):
        if v is None or v == 'N/A' or v == 'n/a' or v == '':
            return 50.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 50.0
        return 50.0

class UserBrandPosition(BaseModel):
    x_coordinate: Optional[float] = Field(default=50, description="X-axis position 0-100")
    y_coordinate: Optional[float] = Field(default=50, description="Y-axis position 0-100")
    quadrant: Optional[str] = Field(default="Center")
    rationale: Optional[str] = None
    
    @field_validator('x_coordinate', 'y_coordinate', mode='before')
    @classmethod
    def parse_coordinate(cls, v):
        if v is None or v == 'N/A' or v == 'n/a' or v == '':
            return 50.0  # Default to center
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 50.0
        return 50.0

class CompetitorAnalysis(BaseModel):
    x_axis_label: Optional[str] = Field(default="Price: Low → High", description="X-axis label")
    y_axis_label: Optional[str] = Field(default="Quality: Basic → Premium", description="Y-axis label")
    competitors: List[Competitor] = Field(default=[])
    user_brand_position: Optional[UserBrandPosition] = None
    white_space_analysis: Optional[str] = Field(default="Analysis pending")
    strategic_advantage: Optional[str] = Field(default="Analysis pending")
    suggested_pricing: Optional[str] = Field(default="N/A")

class Recommendation(BaseModel):
    title: str
    content: str

class FinalAssessment(BaseModel):
    verdict_statement: str
    suitability_score: float
    dimension_breakdown: List[Dict[str, float]]
    recommendations: List[Recommendation]
    alternative_path: str

class AlternativeNameSuggestion(BaseModel):
    name: str
    rationale: str

class AlternativeNames(BaseModel):
    poison_words: Optional[List[str]] = Field(default=[], description="Words from original name that caused conflict")
    reasoning: Optional[str] = Field(default="Alternative names suggested based on analysis")
    suggestions: List[AlternativeNameSuggestion] = Field(default=[])

class BrandScore(BaseModel):
    brand_name: str
    namescore: float
    verdict: str 
    summary: str
    strategic_classification: Optional[str] = Field(default="Classification pending")
    pros: List[str] = Field(default=[])
    cons: List[str] = Field(default=[])
    alternative_names: Optional[AlternativeNames] = None
    dimensions: List[DimensionScore] = Field(default=[])
    trademark_risk: Optional[dict] = Field(default={})
    trademark_matrix: Optional[TrademarkRiskMatrix] = None
    trademark_classes: List[str] = Field(default=[], description="List of Nice Classes")
    domain_analysis: Optional[DomainAnalysis] = None
    multi_domain_availability: Optional[MultiDomainAvailability] = None
    social_availability: Optional[SocialAvailability] = None
    visibility_analysis: Optional[VisibilityAnalysis] = None
    cultural_analysis: List[CountryAnalysis] = Field(default=[])
    competitor_analysis: Optional[CompetitorAnalysis] = None
    final_assessment: Optional[FinalAssessment] = None
    positioning_fit: Optional[str] = Field(default="Positioning analysis pending")

class BrandEvaluationRequest(BaseModel):
    brand_names: List[str]
    industry: Optional[str] = Field(default=None, description="Industry sector")
    category: str
    product_type: Optional[str] = Field(default="Digital", description="Physical, Digital, Service, Hybrid")
    usp: Optional[str] = Field(default=None, description="Unique Selling Proposition")
    brand_vibe: Optional[str] = Field(default=None, description="Brand personality/vibe")
    positioning: Literal["Budget", "Mid-Range", "Premium", "Luxury", "Mass", "Ultra-Premium"]
    market_scope: Literal["Single Country", "Multi-Country", "Global"]
    countries: List[str]

class BrandEvaluationResponse(BaseModel):
    executive_summary: str
    brand_scores: List[BrandScore]
    # Made optional to prevent validation errors when LLM omits it (e.g. single brand or fatal flaw)
    comparison_verdict: Optional[str] = None
    report_id: Optional[str] = None 

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str
