from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Literal, Union, Any
from datetime import datetime, timezone
import uuid

class DimensionScore(BaseModel):
    name: str
    score: float = Field(default=0.0)
    reasoning: str = Field(default="")
    
    @field_validator('score', mode='before')
    @classmethod
    def convert_score(cls, v):
        if v is None or v == 'N/A' or v == '':
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

class TrademarkRiskRow(BaseModel):
    likelihood: int = Field(default=1)
    severity: int = Field(default=1)
    zone: str = Field(default="Green")
    commentary: str = Field(default="No specific risk identified")
    
    @field_validator('likelihood', 'severity', mode='before')
    @classmethod
    def convert_int(cls, v):
        if v is None or v == 'N/A' or v == '':
            return 1
        try:
            return int(v)
        except (ValueError, TypeError):
            return 1

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
    alternatives: List[Union[Dict[str, Any], str]] = Field(default=[])
    strategy_note: str = Field(default="")
    score_impact: Optional[str] = Field(default="-1 point max for taken .com", description="Score impact explanation")
    
    @field_validator('alternatives', mode='before')
    @classmethod
    def normalize_alternatives(cls, v):
        """Handle both string and dict formats for domain alternatives, converting booleans to strings"""
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                # Convert string to dict format
                result.append({"domain": item, "status": "suggested"})
            elif isinstance(item, dict):
                # Convert all values to strings to avoid type mismatches
                normalized = {}
                for key, val in item.items():
                    if isinstance(val, bool):
                        normalized[key] = "true" if val else "false"
                    elif val is None:
                        normalized[key] = ""
                    else:
                        normalized[key] = str(val)
                result.append(normalized)
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

class CountryCompetitorAnalysis(BaseModel):
    country: str = Field(description="Country name (e.g., USA, India, UK)")
    country_flag: Optional[str] = Field(default=None, description="Country flag emoji")
    x_axis_label: Optional[str] = Field(default="Price: Low → High", description="X-axis label for this market")
    y_axis_label: Optional[str] = Field(default="Quality: Basic → Premium", description="Y-axis label for this market")
    competitors: List[Competitor] = Field(default=[], description="Top competitors in this country's market")
    user_brand_position: Optional[UserBrandPosition] = None
    white_space_analysis: Optional[str] = Field(default="Analysis pending", description="White space opportunity in this market")
    strategic_advantage: Optional[str] = Field(default="Analysis pending", description="Strategic advantage in this market")
    market_entry_recommendation: Optional[str] = Field(default=None, description="Recommendation for entering this market")

class Recommendation(BaseModel):
    title: str
    content: str

# Trademark Research Models (for enhanced trademark analysis)
class TrademarkConflictInfo(BaseModel):
    """Discovered trademark conflict"""
    name: str
    source: str = Field(default="Web Search", description="Source of the conflict (e.g., IP India, Tofler)")
    conflict_type: str = Field(default="trademark_application", description="Type: trademark_application, registered_company, common_law")
    application_number: Optional[str] = None
    status: Optional[str] = None  # REGISTERED, PENDING, OBJECTED, ABANDONED
    owner: Optional[str] = None
    class_number: Optional[str] = None
    filing_date: Optional[str] = None
    risk_level: str = Field(default="MEDIUM", description="CRITICAL, HIGH, MEDIUM, LOW")
    details: Optional[str] = None
    url: Optional[str] = None

class CompanyConflictInfo(BaseModel):
    """Discovered company with similar name"""
    name: str
    cin: Optional[str] = None  # Corporate Identification Number
    status: str = Field(default="ACTIVE")
    incorporation_date: Optional[str] = None
    industry: Optional[str] = None
    state: Optional[str] = None
    source: str = Field(default="Company Registry")
    risk_level: str = Field(default="MEDIUM")
    url: Optional[str] = None

class LegalPrecedentInfo(BaseModel):
    """Relevant legal case or precedent"""
    case_name: str
    court: Optional[str] = None
    year: Optional[str] = None
    relevance: Optional[str] = None
    key_principle: Optional[str] = None
    url: Optional[str] = None

class TrademarkResearchData(BaseModel):
    """Complete trademark research findings"""
    nice_classification: Optional[Dict[str, Any]] = Field(default=None, description="Nice Classification info")
    trademark_conflicts: List[TrademarkConflictInfo] = Field(default=[], description="Discovered trademark conflicts")
    company_conflicts: List[CompanyConflictInfo] = Field(default=[], description="Discovered company conflicts")
    common_law_conflicts: List[Dict[str, Any]] = Field(default=[], description="Unregistered but operating businesses")
    legal_precedents: List[LegalPrecedentInfo] = Field(default=[], description="Relevant legal cases")
    overall_risk_score: int = Field(default=5, description="Risk score 1-10")
    registration_success_probability: int = Field(default=50, description="Probability 0-100%")
    opposition_probability: int = Field(default=50, description="Probability 0-100%")
    critical_conflicts_count: int = Field(default=0)
    high_risk_conflicts_count: int = Field(default=0)
    total_conflicts_found: int = Field(default=0)
    
    @field_validator('overall_risk_score', 'registration_success_probability', 'opposition_probability', 
                     'critical_conflicts_count', 'high_risk_conflicts_count', 'total_conflicts_found', mode='before')
    @classmethod
    def convert_int_fields(cls, v):
        if v is None or v == 'N/A' or v == '':
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

class RegistrationTimeline(BaseModel):
    """Trademark registration timeline and costs"""
    estimated_duration: str = Field(default="12-18 months", description="Expected registration duration")
    stages: List[Dict[str, str]] = Field(default=[], description="Registration stages with duration")
    filing_cost: Optional[str] = None
    opposition_defense_cost: Optional[str] = None
    total_estimated_cost: Optional[str] = None

class MitigationStrategy(BaseModel):
    """Risk mitigation strategy"""
    priority: str = Field(default="MEDIUM", description="HIGH, MEDIUM, LOW")
    action: str
    rationale: str
    estimated_cost: Optional[str] = None

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
    # Enhanced trademark research data
    trademark_research: Optional[TrademarkResearchData] = Field(default=None, description="Real-time trademark research findings")
    registration_timeline: Optional[RegistrationTimeline] = Field(default=None, description="Expected registration timeline and costs")
    mitigation_strategies: List[MitigationStrategy] = Field(default=[], description="Risk mitigation strategies")
    domain_analysis: Optional[DomainAnalysis] = None
    multi_domain_availability: Optional[MultiDomainAvailability] = None
    social_availability: Optional[SocialAvailability] = None
    visibility_analysis: Optional[VisibilityAnalysis] = None
    cultural_analysis: List[CountryAnalysis] = Field(default=[])
    competitor_analysis: Optional[CompetitorAnalysis] = None
    country_competitor_analysis: List[CountryCompetitorAnalysis] = Field(default=[], description="Competitor analysis per country (max 4 countries)")
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
