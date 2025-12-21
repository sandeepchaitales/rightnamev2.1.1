from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal

class DimensionScore(BaseModel):
    name: str
    score: float
    reasoning: str

class TrademarkRisk(BaseModel):
    risk_level: Literal["Low", "Medium", "High", "Critical"]
    score: float
    summary: str
    details: List[Dict[str, str]]

class CountryAnalysis(BaseModel):
    country: str
    cultural_resonance_score: float
    cultural_notes: str
    linguistic_check: str

class BrandScore(BaseModel):
    brand_name: str
    namescore: float
    verdict: Literal["GO", "CONDITIONAL GO", "NO-GO", "REJECT"]
    summary: str
    dimensions: List[DimensionScore]
    trademark_risk: TrademarkRisk
    cultural_analysis: List[CountryAnalysis]
    positioning_fit: str

class BrandEvaluationRequest(BaseModel):
    brand_names: List[str]
    category: str
    positioning: Literal["Mass", "Premium", "Ultra-Premium"]
    market_scope: Literal["Single Country", "Multi-Country", "Global"]
    countries: List[str]

class BrandEvaluationResponse(BaseModel):
    executive_summary: str
    brand_scores: List[BrandScore]
    comparison_verdict: str
