from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Literal
from datetime import datetime, timezone
import uuid

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

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str
