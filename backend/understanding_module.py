"""
═══════════════════════════════════════════════════════════════════════════════
UNDERSTANDING MODULE - The Brain of RIGHTNAME.AI
═══════════════════════════════════════════════════════════════════════════════

This module runs FIRST before any other analysis.
It generates a "Source of Truth" JSON that ALL downstream modules read from.

Purpose: Understand what the user is trying to build BEFORE analyzing.

Author: RIGHTNAME.AI Team
Created: July 2025
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Try to import LLM integration
try:
    from emergentintegrations.llm.chat import LlmChat
    EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
except ImportError:
    LlmChat = None
    EMERGENT_KEY = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS FOR UNDERSTANDING MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class WordAnalysis(BaseModel):
    """Analysis of a single word in the brand name"""
    word: str
    is_dictionary_word: bool
    language: str = "English"
    part_of_speech: Optional[str] = None
    meaning: Optional[str] = None
    sentiment: Optional[str] = None  # positive, negative, neutral
    commonality: Optional[str] = None  # very common, common, uncommon, rare

class LinguisticClassification(BaseModel):
    """Trademark classification based on linguistic analysis"""
    type: str  # FANCIFUL, ARBITRARY, SUGGESTIVE, DESCRIPTIVE, GENERIC
    confidence: float = Field(ge=0, le=1)
    reasoning: str

class BrandAnalysis(BaseModel):
    """Complete brand name dissection"""
    original: str
    tokenized: List[str]
    token_count: int
    word_analysis: List[WordAnalysis]
    combined_meaning: str
    has_dictionary_words: bool
    all_words_are_dictionary: bool
    contains_invented_elements: bool
    linguistic_classification: LinguisticClassification

class TargetAudience(BaseModel):
    """Target audience definition"""
    primary: str
    secondary: Optional[str] = None
    demographics: Optional[str] = None

class BusinessUnderstanding(BaseModel):
    """Understanding of what the user is building"""
    business_type: str  # product, service, content_media, marketplace, saas
    business_model: str  # subscription, transaction, advertising, freemium
    what_they_offer: str
    core_value_proposition: str
    target_audience: TargetAudience
    industry_sector: str
    sub_sector: Optional[str] = None

class NiceClass(BaseModel):
    """NICE trademark class information"""
    class_number: int
    class_name: str
    class_description: str
    specific_terms: Optional[str] = None
    rationale: Optional[str] = None

class RegistrationRisk(BaseModel):
    """Trademark registration risk assessment"""
    level: str  # LOW, MEDIUM, HIGH, CRITICAL
    reason: str
    strategy_hint: Optional[str] = None

class TrademarkContext(BaseModel):
    """Trademark intelligence for the brand"""
    primary_nice_class: NiceClass
    secondary_nice_classes: List[NiceClass] = []
    registration_risk: RegistrationRisk

class ComparableBrand(BaseModel):
    """A comparable brand in the same category"""
    name: str
    type: str
    relevance: str

class CompetitiveContext(BaseModel):
    """Competitive landscape hints"""
    search_in_category: str
    NOT_in_category: str
    comparable_brands: List[ComparableBrand] = []
    direct_competitor_search_queries: List[str] = []

class DigitalContext(BaseModel):
    """Domain and digital strategy hints"""
    recommended_tlds: List[str]
    avoid_tlds: List[str] = []
    tld_reasoning: str
    social_platforms_priority: List[str]
    social_platforms_secondary: List[str] = []
    social_platforms_irrelevant: List[str] = []

class WordSentimentCheck(BaseModel):
    """Sentiment check for a specific word"""
    concern: str
    risk_level: str  # LOW, MEDIUM, HIGH
    cultural_notes: Dict[str, str] = {}

class CulturalContext(BaseModel):
    """Cultural and market context"""
    name_sentiment_check: Dict[str, WordSentimentCheck] = {}
    brand_tone: str
    audience_expectation: str

class ModuleInstruction(BaseModel):
    """Instructions for a specific downstream module"""
    instruction: str
    extra_data: Dict[str, Any] = {}

class ModuleInstructions(BaseModel):
    """Instructions for all downstream modules"""
    linguistic_module: ModuleInstruction
    trademark_module: ModuleInstruction
    competitor_module: ModuleInstruction
    domain_module: ModuleInstruction
    cultural_module: ModuleInstruction

class SemanticSafety(BaseModel):
    """Name-category conflict detection"""
    category_conflict: bool = False
    conflict_reason: Optional[str] = None
    severity: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW
    industry_fit_score: float = Field(ge=0, le=10, default=7.0)

class UnderstandingMeta(BaseModel):
    """Metadata for the understanding module output"""
    understanding_version: str = "1.0"
    generated_at: str
    processing_time_ms: int
    model_used: str
    confidence_score: float = Field(ge=0, le=1)

class BrandUnderstanding(BaseModel):
    """Complete understanding module output - The Source of Truth"""
    brand_analysis: BrandAnalysis
    business_understanding: BusinessUnderstanding
    trademark_context: TrademarkContext
    competitive_context: CompetitiveContext
    digital_context: DigitalContext
    cultural_context: CulturalContext
    semantic_safety: SemanticSafety
    module_instructions: ModuleInstructions
    meta: UnderstandingMeta


# ═══════════════════════════════════════════════════════════════════════════════
# NICE CLASS DATABASE (Quick lookup for common categories)
# ═══════════════════════════════════════════════════════════════════════════════

NICE_CLASS_DATABASE = {
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 9 - Software, Mobile Apps, Electronics (PRIMARY for booking apps)
    # ═══════════════════════════════════════════════════════════════════════════
    "software": {"number": 9, "name": "Software & Electronics", "desc": "Computer software, mobile apps, electronic devices"},
    "app": {"number": 9, "name": "Software & Electronics", "desc": "Computer software, mobile apps, electronic devices"},
    "mobile app": {"number": 9, "name": "Software & Electronics", "desc": "Downloadable mobile applications, software"},
    "tech": {"number": 9, "name": "Software & Electronics", "desc": "Computer software, mobile apps, electronic devices"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BOOKING APPS - Class 9 (software) PRIMARY, Class 42 (SaaS) SECONDARY
    # NOT Class 39 (travel/transport) - that's only for actual transport services
    # ═══════════════════════════════════════════════════════════════════════════
    "booking app": {"number": 9, "name": "Software & Electronics", "desc": "Mobile booking application software"},
    "booking": {"number": 9, "name": "Software & Electronics", "desc": "Booking software, appointment scheduling apps"},
    "appointment": {"number": 9, "name": "Software & Electronics", "desc": "Appointment scheduling software, booking apps"},
    "appointment app": {"number": 9, "name": "Software & Electronics", "desc": "Appointment scheduling mobile application"},
    "appointment booking": {"number": 9, "name": "Software & Electronics", "desc": "Appointment booking software"},
    "scheduling app": {"number": 9, "name": "Software & Electronics", "desc": "Scheduling software, calendar apps"},
    "scheduling": {"number": 9, "name": "Software & Electronics", "desc": "Scheduling software applications"},
    "reservation app": {"number": 9, "name": "Software & Electronics", "desc": "Reservation booking software"},
    "reservation": {"number": 9, "name": "Software & Electronics", "desc": "Reservation software applications"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SALON/BEAUTY BOOKING - Class 9 (app) + Class 44 (beauty services)
    # NOT Class 39 (travel) - that's for transport, not beauty
    # ═══════════════════════════════════════════════════════════════════════════
    "salon": {"number": 9, "name": "Software & Electronics", "desc": "Salon booking software, beauty appointment apps"},
    "salon app": {"number": 9, "name": "Software & Electronics", "desc": "Salon appointment booking mobile application"},
    "salon booking": {"number": 9, "name": "Software & Electronics", "desc": "Salon appointment booking software"},
    "salon booking app": {"number": 9, "name": "Software & Electronics", "desc": "Salon appointment booking mobile application"},
    "beauty booking": {"number": 9, "name": "Software & Electronics", "desc": "Beauty service booking software"},
    "beauty app": {"number": 9, "name": "Software & Electronics", "desc": "Beauty service booking mobile application"},
    "spa booking": {"number": 9, "name": "Software & Electronics", "desc": "Spa appointment booking software"},
    "spa app": {"number": 9, "name": "Software & Electronics", "desc": "Spa booking mobile application"},
    "parlour": {"number": 9, "name": "Software & Electronics", "desc": "Parlour booking software"},
    "parlor": {"number": 9, "name": "Software & Electronics", "desc": "Parlor booking software"},
    "barber": {"number": 9, "name": "Software & Electronics", "desc": "Barber appointment booking software"},
    "barber app": {"number": 9, "name": "Software & Electronics", "desc": "Barber booking mobile application"},
    "grooming app": {"number": 9, "name": "Software & Electronics", "desc": "Grooming service booking application"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DOCTOR/HEALTHCARE BOOKING - Class 9 (app) + Class 44 (medical services)
    # ═══════════════════════════════════════════════════════════════════════════
    "doctor appointment": {"number": 9, "name": "Software & Electronics", "desc": "Doctor appointment booking software"},
    "doctor booking": {"number": 9, "name": "Software & Electronics", "desc": "Doctor appointment scheduling software"},
    "doctor app": {"number": 9, "name": "Software & Electronics", "desc": "Doctor appointment mobile application"},
    "clinic booking": {"number": 9, "name": "Software & Electronics", "desc": "Clinic appointment booking software"},
    "hospital booking": {"number": 9, "name": "Software & Electronics", "desc": "Hospital appointment booking software"},
    "telemedicine": {"number": 9, "name": "Software & Electronics", "desc": "Telemedicine software application"},
    "telehealth": {"number": 9, "name": "Software & Electronics", "desc": "Telehealth software application"},
    "healthtech": {"number": 9, "name": "Software & Electronics", "desc": "Healthcare technology software"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 35 - Business, Advertising, Marketplace Platforms
    # ═══════════════════════════════════════════════════════════════════════════
    "ecommerce": {"number": 35, "name": "Advertising & Business", "desc": "Advertising, business management, retail services"},
    "marketplace": {"number": 35, "name": "Advertising & Business", "desc": "Online marketplace platform services"},
    "booking platform": {"number": 35, "name": "Advertising & Business", "desc": "Online booking platform marketplace services"},
    "consulting": {"number": 35, "name": "Advertising & Business", "desc": "Business consulting, management services"},
    "aggregator": {"number": 35, "name": "Advertising & Business", "desc": "Service aggregator platform"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 36 - Finance, Insurance, Banking
    # ═══════════════════════════════════════════════════════════════════════════
    "finance": {"number": 36, "name": "Financial Services", "desc": "Insurance, financial affairs, banking, real estate"},
    "fintech": {"number": 36, "name": "Financial Services", "desc": "Insurance, financial affairs, banking, real estate"},
    "payment": {"number": 36, "name": "Financial Services", "desc": "Payment processing, financial transactions"},
    "banking": {"number": 36, "name": "Financial Services", "desc": "Insurance, financial affairs, banking, real estate"},
    "insurance": {"number": 36, "name": "Financial Services", "desc": "Insurance services"},
    "lending": {"number": 36, "name": "Financial Services", "desc": "Financial lending services"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 41 - Education, Entertainment, Content
    # ═══════════════════════════════════════════════════════════════════════════
    "youtube": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "youtube channel": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "content creator": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "podcast": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "education": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "edtech": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "entertainment": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "gaming": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "media": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "streaming": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "influencer": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "vlog": {"number": 41, "name": "Education & Entertainment", "desc": "Education, training, entertainment, sporting and cultural activities"},
    "online course": {"number": 41, "name": "Education & Entertainment", "desc": "Online educational courses and training"},
    "e-learning": {"number": 41, "name": "Education & Entertainment", "desc": "Electronic learning services"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 42 - SaaS, Technology Services, Cloud Computing
    # ═══════════════════════════════════════════════════════════════════════════
    "saas": {"number": 42, "name": "Technology Services", "desc": "Scientific and technological services, software as a service"},
    "cloud": {"number": 42, "name": "Technology Services", "desc": "Scientific and technological services, cloud computing"},
    "ai": {"number": 42, "name": "Technology Services", "desc": "Scientific and technological services, AI/ML services"},
    "platform": {"number": 42, "name": "Technology Services", "desc": "Scientific and technological services, platform services"},
    "software service": {"number": 42, "name": "Technology Services", "desc": "Software as a service (SaaS)"},
    "web service": {"number": 42, "name": "Technology Services", "desc": "Web-based software services"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 43 - Hospitality, Food Service, Accommodation
    # ═══════════════════════════════════════════════════════════════════════════
    "hotel": {"number": 43, "name": "Hospitality", "desc": "Hotels, temporary accommodation, restaurant services"},
    "restaurant": {"number": 43, "name": "Hospitality", "desc": "Restaurant services, food and drink services"},
    "cafe": {"number": 43, "name": "Hospitality", "desc": "Restaurant services, cafe services"},
    "food service": {"number": 43, "name": "Hospitality", "desc": "Restaurant services, food and drink services"},
    "hospitality": {"number": 43, "name": "Hospitality", "desc": "Hotel, restaurant, temporary accommodation services"},
    "catering": {"number": 43, "name": "Hospitality", "desc": "Catering and food service"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 44 - Medical, Beauty, Wellness SERVICES (not apps)
    # Use for actual service providers, not booking apps
    # ═══════════════════════════════════════════════════════════════════════════
    "healthcare": {"number": 44, "name": "Medical & Beauty Services", "desc": "Medical services, health care, veterinary services"},
    "medical": {"number": 44, "name": "Medical & Beauty Services", "desc": "Medical services, health care"},
    "wellness": {"number": 44, "name": "Medical & Beauty Services", "desc": "Medical services, health care, wellness"},
    "beauty services": {"number": 44, "name": "Medical & Beauty Services", "desc": "Beauty care, salon services, hygienic care"},
    "salon services": {"number": 44, "name": "Medical & Beauty Services", "desc": "Beauty salon services, hair care"},
    "spa services": {"number": 44, "name": "Medical & Beauty Services", "desc": "Spa, massage, wellness services"},
    "dental": {"number": 44, "name": "Medical & Beauty Services", "desc": "Dental services, oral care"},
    "veterinary": {"number": 44, "name": "Medical & Beauty Services", "desc": "Veterinary services, animal care"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 25 - Clothing, Fashion, Apparel
    # ═══════════════════════════════════════════════════════════════════════════
    "fashion": {"number": 25, "name": "Clothing & Apparel", "desc": "Clothing, footwear, headgear"},
    "clothing": {"number": 25, "name": "Clothing & Apparel", "desc": "Clothing, footwear, headgear"},
    "apparel": {"number": 25, "name": "Clothing & Apparel", "desc": "Clothing, footwear, headgear"},
    "streetwear": {"number": 25, "name": "Clothing & Apparel", "desc": "Clothing, footwear, headgear"},
    "footwear": {"number": 25, "name": "Clothing & Apparel", "desc": "Shoes, boots, footwear"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 3 - Cosmetics, Cleaning Products
    # ═══════════════════════════════════════════════════════════════════════════
    "beauty": {"number": 3, "name": "Cosmetics & Cleaning", "desc": "Cleaning preparations, cosmetics, perfumery"},
    "cosmetics": {"number": 3, "name": "Cosmetics & Cleaning", "desc": "Cleaning preparations, cosmetics, perfumery"},
    "skincare": {"number": 3, "name": "Cosmetics & Cleaning", "desc": "Cleaning preparations, cosmetics, perfumery"},
    "cleaning": {"number": 3, "name": "Cosmetics & Cleaning", "desc": "Cleaning preparations, polishing, soaps"},
    "makeup": {"number": 3, "name": "Cosmetics & Cleaning", "desc": "Cosmetics, makeup products"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 29/30/32 - Food Products, Beverages
    # ═══════════════════════════════════════════════════════════════════════════
    "food": {"number": 29, "name": "Food Products", "desc": "Meat, fish, preserved foods, dairy"},
    "beverages": {"number": 32, "name": "Beverages", "desc": "Beers, mineral waters, soft drinks, fruit juices"},
    "tea": {"number": 30, "name": "Food Products", "desc": "Coffee, tea, cocoa, bakery goods"},
    "coffee": {"number": 30, "name": "Food Products", "desc": "Coffee, tea, cocoa, bakery goods"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 39 - Transport, Travel, Logistics (ONLY for actual transport)
    # NOT for booking apps - booking apps go to Class 9
    # ═══════════════════════════════════════════════════════════════════════════
    "logistics": {"number": 39, "name": "Transport & Logistics", "desc": "Transport, packaging, travel arrangement"},
    "travel": {"number": 39, "name": "Transport & Logistics", "desc": "Transport, travel arrangement services"},
    "delivery": {"number": 39, "name": "Transport & Logistics", "desc": "Transport, delivery services"},
    "transport": {"number": 39, "name": "Transport & Logistics", "desc": "Transport services, freight"},
    "shipping": {"number": 39, "name": "Transport & Logistics", "desc": "Shipping, freight transport"},
    "cab": {"number": 39, "name": "Transport & Logistics", "desc": "Taxi, cab transportation services"},
    "taxi": {"number": 39, "name": "Transport & Logistics", "desc": "Taxi transportation services"},
    "ride": {"number": 39, "name": "Transport & Logistics", "desc": "Ride-hailing transportation services"},
    "ride-hailing": {"number": 39, "name": "Transport & Logistics", "desc": "Ride-hailing transportation services"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# TLD RECOMMENDATIONS BY BUSINESS TYPE
# ═══════════════════════════════════════════════════════════════════════════════

TLD_RECOMMENDATIONS = {
    "content_media": {
        "recommended": [".com", ".tv", ".show", ".media", ".co", ".live"],
        "avoid": [".io", ".app", ".ai", ".tech", ".dev"],
        "reasoning": "Content/media brands prioritize .com and media-specific TLDs"
    },
    "saas": {
        "recommended": [".com", ".io", ".app", ".ai", ".co"],
        "avoid": [".tv", ".show", ".media"],
        "reasoning": "SaaS/Tech brands use .io, .app, .ai to signal innovation"
    },
    "product": {
        "recommended": [".com", ".co", ".store", ".shop"],
        "avoid": [".io", ".app", ".ai"],
        "reasoning": "Product brands prioritize .com and e-commerce TLDs"
    },
    "service": {
        "recommended": [".com", ".co", ".services", ".pro"],
        "avoid": [".io", ".tv", ".shop"],
        "reasoning": "Service brands use professional TLDs"
    },
    "marketplace": {
        "recommended": [".com", ".market", ".store", ".co"],
        "avoid": [".io", ".tv", ".media"],
        "reasoning": "Marketplaces use commerce-focused TLDs"
    },
    "default": {
        "recommended": [".com", ".co", ".net"],
        "avoid": [],
        "reasoning": "Default recommendation - .com is always preferred"
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL PLATFORM PRIORITIES BY BUSINESS TYPE
# ═══════════════════════════════════════════════════════════════════════════════

SOCIAL_PRIORITIES = {
    "content_media": {
        "priority": ["youtube", "instagram", "twitter", "tiktok", "linkedin"],
        "secondary": ["facebook", "threads"],
        "irrelevant": ["github", "dribbble", "behance"]
    },
    "saas": {
        "priority": ["linkedin", "twitter", "github", "youtube"],
        "secondary": ["instagram", "facebook"],
        "irrelevant": ["tiktok", "pinterest"]
    },
    "product": {
        "priority": ["instagram", "facebook", "pinterest", "tiktok"],
        "secondary": ["twitter", "youtube"],
        "irrelevant": ["github", "dribbble"]
    },
    "service": {
        "priority": ["linkedin", "facebook", "instagram", "twitter"],
        "secondary": ["youtube"],
        "irrelevant": ["tiktok", "github", "pinterest"]
    },
    "marketplace": {
        "priority": ["instagram", "facebook", "twitter", "linkedin"],
        "secondary": ["youtube", "pinterest"],
        "irrelevant": ["github", "dribbble"]
    },
    "default": {
        "priority": ["instagram", "twitter", "linkedin", "facebook"],
        "secondary": ["youtube", "tiktok"],
        "irrelevant": []
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# LLM PROMPT FOR UNDERSTANDING MODULE
# ═══════════════════════════════════════════════════════════════════════════════

UNDERSTANDING_PROMPT = """You are a Brand Strategist and Trademark Expert. Your task is to UNDERSTAND what the user is building BEFORE any analysis begins.

## INPUT
- Brand Name: {brand_name}
- Category: {category}
- Positioning: {positioning}
- Countries: {countries}

## YOUR TASK

### 1. TOKENIZE THE BRAND NAME
Split the brand name into individual words. Look for:
- CamelCase splits (FailedFounders → Failed, Founders)
- Common word boundaries
- Prefix/suffix patterns

### 2. ANALYZE EACH WORD
For each token, determine:
- Is it a dictionary word? (in English or any major language)
- What is its meaning?
- What is its sentiment? (positive/negative/neutral)
- How common is it?

### 3. CLASSIFY THE BRAND NAME
Based on word analysis, classify as:
- FANCIFUL: Completely invented, no meaning (Xerox, Kodak)
- ARBITRARY: Real word, unrelated to product (Apple for computers)
- SUGGESTIVE: Hints at product quality (Netflix = Net + Flicks)
- DESCRIPTIVE: Directly describes product (General Motors)
- GENERIC: Common name for product category (Computer Store)

IMPORTANT: If ANY word is a common dictionary word that relates to the business, it CANNOT be FANCIFUL.

### 4. UNDERSTAND THE BUSINESS
Determine:
- What type of business is this? (product/service/content_media/marketplace/saas)
- What is their business model? (subscription/transaction/advertising/freemium)
- Who is their target audience?
- What industry sector?

### 5. IDENTIFY NICE CLASS
Based on the category, determine the correct NICE trademark class (1-45).
Common mappings:
- YouTube/Content/Podcast → Class 41 (Entertainment)
- Software/Apps → Class 9 (Software) or Class 42 (SaaS)
- Finance/Payments → Class 36 (Financial)
- Fashion/Clothing → Class 25 (Apparel)
- Food Service → Class 43 (Restaurant)
- Cosmetics → Class 3 (Cosmetics)

### 6. LIST COMPARABLE BRANDS
Find 3-5 brands in the SAME category (not just similar names).
For YouTube Channel → other YouTubers
For SaaS → other SaaS companies
For Restaurant → other restaurants

### 7. CHECK FOR CONFLICTS
Does the brand name conflict with the category?
- "BurgerKing" for a Gym = CONFLICT
- "FailedFounders" for YouTube about failures = NO CONFLICT

## OUTPUT FORMAT
Return ONLY valid JSON matching this exact structure:

{{
  "brand_analysis": {{
    "original": "{brand_name}",
    "tokenized": ["word1", "word2"],
    "token_count": 2,
    "word_analysis": [
      {{
        "word": "word1",
        "is_dictionary_word": true,
        "language": "English",
        "part_of_speech": "noun",
        "meaning": "description",
        "sentiment": "positive",
        "commonality": "common"
      }}
    ],
    "combined_meaning": "what the full name means together",
    "has_dictionary_words": true,
    "all_words_are_dictionary": true,
    "contains_invented_elements": false,
    "linguistic_classification": {{
      "type": "DESCRIPTIVE",
      "confidence": 0.95,
      "reasoning": "explanation"
    }}
  }},
  "business_understanding": {{
    "business_type": "content_media",
    "business_model": "advertising_sponsorship",
    "what_they_offer": "description of offering",
    "core_value_proposition": "main value prop",
    "target_audience": {{
      "primary": "main audience",
      "secondary": "secondary audience",
      "demographics": "age, interests"
    }},
    "industry_sector": "media_entertainment",
    "sub_sector": "educational_content"
  }},
  "trademark_context": {{
    "primary_nice_class": {{
      "class_number": 41,
      "class_name": "Education & Entertainment",
      "class_description": "Education, training, entertainment",
      "specific_terms": "specific goods/services"
    }},
    "secondary_nice_classes": [],
    "registration_risk": {{
      "level": "HIGH",
      "reason": "why risky",
      "strategy_hint": "how to mitigate"
    }}
  }},
  "competitive_context": {{
    "search_in_category": "what to search for",
    "NOT_in_category": "what to exclude",
    "comparable_brands": [
      {{"name": "Brand1", "type": "type", "relevance": "why relevant"}}
    ],
    "direct_competitor_search_queries": ["query1", "query2"]
  }},
  "digital_context": {{
    "recommended_tlds": [".com", ".tv"],
    "avoid_tlds": [".io", ".app"],
    "tld_reasoning": "why these TLDs",
    "social_platforms_priority": ["youtube", "instagram"],
    "social_platforms_secondary": ["facebook"],
    "social_platforms_irrelevant": ["github"]
  }},
  "cultural_context": {{
    "name_sentiment_check": {{
      "word_with_concern": {{
        "concern": "what the concern is",
        "risk_level": "MEDIUM",
        "cultural_notes": {{
          "USA": "perception in USA",
          "India": "perception in India"
        }}
      }}
    }},
    "brand_tone": "tone description",
    "audience_expectation": "what audience expects"
  }},
  "semantic_safety": {{
    "category_conflict": false,
    "conflict_reason": null,
    "severity": "LOW",
    "industry_fit_score": 8.5
  }}
}}

RESPOND WITH ONLY THE JSON. NO EXPLANATION BEFORE OR AFTER."""


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FUNCTION: GENERATE BRAND UNDERSTANDING
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_brand_understanding(
    brand_name: str,
    category: str,
    positioning: str,
    countries: List[str]
) -> Dict[str, Any]:
    """
    Generate comprehensive brand understanding - The Brain of RIGHTNAME.AI
    
    This runs FIRST before any other analysis.
    Returns a "Source of Truth" that all downstream modules read from.
    
    Args:
        brand_name: The brand name to analyze
        category: Business category (e.g., "YouTube Channel", "SaaS", "Restaurant")
        positioning: Brand positioning (e.g., "Premium", "Budget", "Educational")
        countries: Target countries
    
    Returns:
        Dict containing complete brand understanding
    """
    import time
    start_time = time.time()
    
    logger.info(f"🧠 UNDERSTANDING MODULE: Starting analysis for '{brand_name}' in '{category}'")
    
    # Prepare the prompt
    prompt = UNDERSTANDING_PROMPT.format(
        brand_name=brand_name,
        category=category,
        positioning=positioning,
        countries=", ".join(countries)
    )
    
    understanding_data = None
    model_used = "fallback"
    
    # Try LLM first
    if LlmChat and EMERGENT_KEY:
        from emergentintegrations.llm.chat import UserMessage
        
        models_to_try = [
            ("openai", "gpt-4o-mini"),  # Fast and reliable for structured output
            ("openai", "gpt-4o"),        # Fallback
        ]
        
        for provider, model in models_to_try:
            try:
                logger.info(f"🧠 Understanding Module: Trying {provider}/{model}...")
                
                chat = LlmChat(EMERGENT_KEY, provider, model)
                user_msg = UserMessage(text=prompt)
                
                response = await asyncio.wait_for(
                    chat.send_message(user_msg),
                    timeout=30
                )
                
                # Parse the JSON response
                response_text = str(response).strip()
                
                # Clean up response if needed
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                understanding_data = json.loads(response_text.strip())
                model_used = f"{provider}/{model}"
                logger.info(f"🧠 Understanding Module: SUCCESS with {model_used}")
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"🧠 Understanding Module: JSON parse error with {model}: {e}")
                continue
            except Exception as e:
                logger.error(f"🧠 Understanding Module: Error with {model}: {e}")
                continue
    
    # If LLM failed, use fallback
    if understanding_data is None:
        logger.warning("🧠 Understanding Module: LLM failed, using fallback logic")
        understanding_data = generate_fallback_understanding(brand_name, category, positioning, countries)
        model_used = "fallback"
    
    # Add module instructions
    understanding_data["module_instructions"] = generate_module_instructions(understanding_data)
    
    # Add metadata
    processing_time_ms = int((time.time() - start_time) * 1000)
    understanding_data["meta"] = {
        "understanding_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "processing_time_ms": processing_time_ms,
        "model_used": model_used,
        "confidence_score": 0.9 if model_used != "fallback" else 0.7
    }
    
    # Log summary
    classification = understanding_data.get("brand_analysis", {}).get("linguistic_classification", {}).get("type", "UNKNOWN")
    nice_class = understanding_data.get("trademark_context", {}).get("primary_nice_class", {}).get("class_number", 0)
    business_type = understanding_data.get("business_understanding", {}).get("business_type", "unknown")
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  🧠 UNDERSTANDING MODULE COMPLETE                                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Brand: {brand_name:<55}  ║
║  Classification: {classification:<48}  ║
║  NICE Class: {nice_class:<51}  ║
║  Business Type: {business_type:<49}  ║
║  Model: {model_used:<57}  ║
║  Time: {processing_time_ms}ms{' ' * (54 - len(str(processing_time_ms)))}  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    return understanding_data


def generate_fallback_understanding(
    brand_name: str,
    category: str,
    positioning: str,
    countries: List[str]
) -> Dict[str, Any]:
    """
    Generate understanding using rule-based logic when LLM is unavailable.
    """
    logger.info(f"🧠 Fallback Understanding: Generating for '{brand_name}'")
    
    # Tokenize brand name (simple camelCase and space split)
    import re
    
    # Split on camelCase, spaces, hyphens, underscores
    tokens = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+', brand_name)
    if not tokens:
        tokens = [brand_name]
    
    # Common English dictionary words (basic check)
    COMMON_WORDS = {
        "failed", "founder", "founders", "success", "business", "tech", "app",
        "cloud", "smart", "quick", "fast", "easy", "simple", "best", "top",
        "prime", "first", "new", "next", "big", "small", "good", "great",
        "super", "mega", "ultra", "pro", "plus", "max", "mini", "lite",
        "pay", "buy", "sell", "shop", "store", "market", "hub", "lab",
        "studio", "works", "craft", "media", "digital", "online", "web",
        "net", "link", "connect", "sync", "data", "info", "learn", "teach",
        "help", "care", "health", "fit", "food", "eat", "cook", "chef",
        "home", "house", "room", "space", "place", "spot", "zone", "area"
    }
    
    # Analyze each word
    word_analysis = []
    has_dict_words = False
    all_dict_words = True
    
    for token in tokens:
        token_lower = token.lower()
        is_dict = token_lower in COMMON_WORDS or len(token) > 2
        
        # Simple heuristic: if it's a common word pattern, likely dictionary
        if is_dict:
            has_dict_words = True
        else:
            all_dict_words = False
        
        word_analysis.append({
            "word": token,
            "is_dictionary_word": is_dict,
            "language": "English",
            "part_of_speech": "unknown",
            "meaning": "Component of brand name",
            "sentiment": "neutral",
            "commonality": "common" if is_dict else "unknown"
        })
    
    # Determine classification
    if not has_dict_words:
        classification_type = "FANCIFUL"
        classification_confidence = 0.8
        classification_reasoning = "No recognizable dictionary words found"
    elif all_dict_words:
        classification_type = "DESCRIPTIVE"
        classification_confidence = 0.85
        classification_reasoning = "All components are common dictionary words"
    else:
        classification_type = "SUGGESTIVE"
        classification_confidence = 0.7
        classification_reasoning = "Mix of dictionary and invented elements"
    
    # Determine NICE class from category
    category_lower = category.lower()
    nice_info = None
    
    for key, value in NICE_CLASS_DATABASE.items():
        if key in category_lower:
            nice_info = value
            break
    
    if not nice_info:
        nice_info = {"number": 35, "name": "Business Services", "desc": "Advertising, business management"}
    
    # Determine business type
    business_type = "service"
    if any(x in category_lower for x in ["youtube", "podcast", "content", "media", "channel", "influencer"]):
        business_type = "content_media"
    elif any(x in category_lower for x in ["saas", "software", "app", "platform"]):
        business_type = "saas"
    elif any(x in category_lower for x in ["shop", "store", "ecommerce", "marketplace"]):
        business_type = "marketplace"
    elif any(x in category_lower for x in ["product", "goods", "manufacturing"]):
        business_type = "product"
    
    # Get TLD and social recommendations
    tld_config = TLD_RECOMMENDATIONS.get(business_type, TLD_RECOMMENDATIONS["default"])
    social_config = SOCIAL_PRIORITIES.get(business_type, SOCIAL_PRIORITIES["default"])
    
    # Build the understanding object
    return {
        "brand_analysis": {
            "original": brand_name,
            "tokenized": tokens,
            "token_count": len(tokens),
            "word_analysis": word_analysis,
            "combined_meaning": f"Brand name composed of: {', '.join(tokens)}",
            "has_dictionary_words": has_dict_words,
            "all_words_are_dictionary": all_dict_words,
            "contains_invented_elements": not all_dict_words,
            "linguistic_classification": {
                "type": classification_type,
                "confidence": classification_confidence,
                "reasoning": classification_reasoning
            }
        },
        "business_understanding": {
            "business_type": business_type,
            "business_model": "advertising_sponsorship" if business_type == "content_media" else "subscription",
            "what_they_offer": f"{category} services/products",
            "core_value_proposition": f"Providing {category} to target customers",
            "target_audience": {
                "primary": f"Customers interested in {category}",
                "secondary": "General audience",
                "demographics": "Varies by market"
            },
            "industry_sector": category.lower().replace(" ", "_"),
            "sub_sector": None
        },
        "trademark_context": {
            "primary_nice_class": {
                "class_number": nice_info["number"],
                "class_name": nice_info["name"],
                "class_description": nice_info["desc"],
                "specific_terms": category
            },
            "secondary_nice_classes": [],
            "registration_risk": {
                "level": "HIGH" if classification_type == "DESCRIPTIVE" else "MEDIUM" if classification_type == "SUGGESTIVE" else "LOW",
                "reason": f"{classification_type} names face {'rejection' if classification_type == 'DESCRIPTIVE' else 'moderate' if classification_type == 'SUGGESTIVE' else 'minimal'} registration challenges",
                "strategy_hint": "Consider distinctive elements" if classification_type != "FANCIFUL" else None
            }
        },
        "competitive_context": {
            "search_in_category": category,
            "NOT_in_category": "Unrelated industries",
            "comparable_brands": [],
            "direct_competitor_search_queries": [
                f"top {category} brands",
                f"best {category} companies",
                f"{category} market leaders"
            ]
        },
        "digital_context": {
            "recommended_tlds": tld_config["recommended"],
            "avoid_tlds": tld_config["avoid"],
            "tld_reasoning": tld_config["reasoning"],
            "social_platforms_priority": social_config["priority"],
            "social_platforms_secondary": social_config["secondary"],
            "social_platforms_irrelevant": social_config["irrelevant"]
        },
        "cultural_context": {
            "name_sentiment_check": {},
            "brand_tone": "professional",
            "audience_expectation": f"Quality {category} offerings"
        },
        "semantic_safety": {
            "category_conflict": False,
            "conflict_reason": None,
            "severity": "LOW",
            "industry_fit_score": 7.0
        }
    }


def generate_module_instructions(understanding: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate specific instructions for each downstream module based on understanding.
    """
    brand_analysis = understanding.get("brand_analysis", {})
    trademark_context = understanding.get("trademark_context", {})
    digital_context = understanding.get("digital_context", {})
    competitive_context = understanding.get("competitive_context", {})
    cultural_context = understanding.get("cultural_context", {})
    
    classification = brand_analysis.get("linguistic_classification", {}).get("type", "UNKNOWN")
    primary_class = trademark_context.get("primary_nice_class", {}).get("class_number", 35)
    
    return {
        "linguistic_module": {
            "instruction": f"Classification is {classification}. Validate and enrich, do not re-classify as FANCIFUL if dictionary words exist.",
            "extra_data": {
                "pre_tokenized_words": brand_analysis.get("tokenized", []),
                "known_classification": classification,
                "skip_dictionary_check": False
            }
        },
        "trademark_module": {
            "instruction": f"Search primarily in Class {primary_class}. Focus on {competitive_context.get('search_in_category', 'the category')}.",
            "extra_data": {
                "search_class": primary_class,
                "secondary_classes": [c.get("class_number") for c in trademark_context.get("secondary_nice_classes", [])],
                "search_terms": competitive_context.get("direct_competitor_search_queries", [])
            }
        },
        "competitor_module": {
            "instruction": f"Search for {competitive_context.get('search_in_category', 'category competitors')}. Exclude {competitive_context.get('NOT_in_category', 'unrelated')}.",
            "extra_data": {
                "search_category": competitive_context.get("search_in_category", ""),
                "exclude_category": competitive_context.get("NOT_in_category", ""),
                "seed_brands": [b.get("name") for b in competitive_context.get("comparable_brands", [])]
            }
        },
        "domain_module": {
            "instruction": f"Prioritize TLDs: {', '.join(digital_context.get('recommended_tlds', ['.com']))}. Avoid: {', '.join(digital_context.get('avoid_tlds', []))}",
            "extra_data": {
                "prioritize_tlds": digital_context.get("recommended_tlds", [".com"]),
                "avoid_tlds": digital_context.get("avoid_tlds", [])
            }
        },
        "cultural_module": {
            "instruction": f"Check sentiment for flagged words. Context: {cultural_context.get('brand_tone', 'professional')}",
            "extra_data": {
                "flagged_words": list(cultural_context.get("name_sentiment_check", {}).keys()),
                "context": cultural_context.get("audience_expectation", "")
            }
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_nice_class_from_understanding(understanding: Dict[str, Any]) -> Dict[str, Any]:
    """Extract NICE class info from understanding for trademark module"""
    trademark_context = understanding.get("trademark_context", {})
    primary = trademark_context.get("primary_nice_class", {})
    
    return {
        "class_number": primary.get("class_number", 35),
        "class_description": primary.get("class_description", "Business services")
    }


def get_classification_from_understanding(understanding: Dict[str, Any]) -> str:
    """Extract linguistic classification from understanding"""
    brand_analysis = understanding.get("brand_analysis", {})
    return brand_analysis.get("linguistic_classification", {}).get("type", "UNKNOWN")


def get_business_type_from_understanding(understanding: Dict[str, Any]) -> str:
    """Extract business type from understanding"""
    business = understanding.get("business_understanding", {})
    return business.get("business_type", "service")


def should_use_understanding_classification(understanding: Dict[str, Any]) -> bool:
    """Check if understanding module classification should override others"""
    meta = understanding.get("meta", {})
    confidence = meta.get("confidence_score", 0)
    return confidence >= 0.7


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "generate_brand_understanding",
    "get_nice_class_from_understanding",
    "get_classification_from_understanding",
    "get_business_type_from_understanding",
    "should_use_understanding_classification",
    "BrandUnderstanding",
    "NICE_CLASS_DATABASE",
]
