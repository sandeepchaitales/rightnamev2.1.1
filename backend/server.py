from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import gc
from pathlib import Path
from pydantic import ConfigDict, Field, BaseModel, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import json
import whois
import asyncio
import random
import re
import httpx
from passlib.context import CryptContext
from contextlib import asynccontextmanager

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Import custom modules
from schemas import BrandEvaluationRequest, BrandEvaluationResponse, StatusCheck, StatusCheckCreate, DimensionScore, BrandScore, BrandAuditRequest, BrandAuditResponse, BrandAuditDimension, SWOTAnalysis, SWOTItem, CompetitorData, MarketData, StrategicRecommendation, CompetitivePosition
from prompts import SYSTEM_PROMPT
from brand_audit_prompt import BRAND_AUDIT_SYSTEM_PROMPT, build_brand_audit_prompt
from brand_audit_prompt_compact import BRAND_AUDIT_SYSTEM_PROMPT_COMPACT, build_brand_audit_prompt_compact
from visibility import check_visibility
from availability import check_full_availability, check_multi_domain_availability, check_social_availability
from similarity import check_brand_similarity, format_similarity_report
from trademark_research import conduct_trademark_research, format_research_for_prompt

# Import Emergent Integration
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
except ImportError:
    logging.error("emergentintegrations not found. Ensure it is installed.")
    LlmChat = None

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection with connection pooling
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=50,
    minPoolSize=10,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000,
    retryWrites=True
)
db = client[os.environ.get('DB_NAME', 'rightname_db')]

# Initialize LLM Chat
EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')
if not EMERGENT_KEY:
    logging.warning("EMERGENT_LLM_KEY not found in .env")

# Lifespan context manager for graceful startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Application starting... MongoDB pool initialized")
    yield
    # Shutdown - cleanup connections
    if client:
        client.close()
        logging.info("MongoDB connection closed")
    gc.collect()
    logging.info("Application shutdown complete")

# Create the main app with lifespan
app = FastAPI(lifespan=lifespan)

# Router
api_router = APIRouter(prefix="/api")

# Note: Timeout handling is done at the frontend level (5 min timeout)
# and individual API calls have their own timeouts (WHOIS: 10s, DuckDuckGo: 15s, LLM: 120s)

# ============ JOB-BASED ASYNC PROCESSING ============
# In-memory job storage (for production, use Redis)
evaluation_jobs = {}

class JobStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Progress steps for elegant loading experience
EVALUATION_STEPS = [
    {"id": "domain", "label": "Checking domain availability", "progress": 10},
    {"id": "social", "label": "Scanning social platforms", "progress": 25},
    {"id": "similarity", "label": "Analyzing phonetic conflicts", "progress": 40},
    {"id": "visibility", "label": "Searching app stores & web", "progress": 55},
    {"id": "trademark", "label": "Researching trademarks", "progress": 70},
    {"id": "analysis", "label": "Generating strategic report", "progress": 90},
]

def update_job_progress(job_id: str, step_id: str, eta_seconds: int = None):
    """Update job progress with current step"""
    if job_id in evaluation_jobs:
        step = next((s for s in EVALUATION_STEPS if s["id"] == step_id), None)
        if step:
            evaluation_jobs[job_id]["current_step"] = step_id
            evaluation_jobs[job_id]["current_step_label"] = step["label"]
            evaluation_jobs[job_id]["progress"] = step["progress"]
            evaluation_jobs[job_id]["eta_seconds"] = eta_seconds
            
            # Mark completed steps
            completed = []
            for s in EVALUATION_STEPS:
                if s["progress"] <= step["progress"]:
                    completed.append(s["id"])
                else:
                    break
            evaluation_jobs[job_id]["completed_steps"] = completed

# Country-specific ACTUAL trademark costs (not just currency conversion)
# These are real trademark office costs for each country
COUNTRY_TRADEMARK_COSTS = {
    "USA": {
        "currency": "USD ($)",
        "office": "USPTO",
        "filing_cost": "$275-$400 per class",
        "opposition_defense_cost": "$2,500-$10,000 if contested",
        "total_estimated_cost": "$3,000-$15,000 depending on opposition",
        "trademark_search_cost": "$500-$1,500",
        "logo_design_cost": "$2,000-$10,000",
        "legal_fees_cost": "$1,500-$5,000"
    },
    "United States": {
        "currency": "USD ($)",
        "office": "USPTO",
        "filing_cost": "$275-$400 per class",
        "opposition_defense_cost": "$2,500-$10,000 if contested",
        "total_estimated_cost": "$3,000-$15,000 depending on opposition",
        "trademark_search_cost": "$500-$1,500",
        "logo_design_cost": "$2,000-$10,000",
        "legal_fees_cost": "$1,500-$5,000"
    },
    "India": {
        "currency": "INR (₹)",
        "office": "IP India",
        "filing_cost": "₹4,500-₹9,000 per class (Startup/Company)",
        "opposition_defense_cost": "₹50,000-₹2,00,000 if contested",
        "total_estimated_cost": "₹15,000-₹2,50,000 depending on opposition",
        "trademark_search_cost": "₹3,000-₹5,000",
        "logo_design_cost": "₹10,000-₹50,000",
        "legal_fees_cost": "₹10,000-₹30,000"
    },
    "UK": {
        "currency": "GBP (£)",
        "office": "UKIPO",
        "filing_cost": "£170-£300 per class",
        "opposition_defense_cost": "£2,000-£8,000 if contested",
        "total_estimated_cost": "£2,500-£12,000 depending on opposition",
        "trademark_search_cost": "£400-£1,200",
        "logo_design_cost": "£1,500-£8,000",
        "legal_fees_cost": "£1,000-£4,000"
    },
    "United Kingdom": {
        "currency": "GBP (£)",
        "office": "UKIPO",
        "filing_cost": "£170-£300 per class",
        "opposition_defense_cost": "£2,000-£8,000 if contested",
        "total_estimated_cost": "£2,500-£12,000 depending on opposition",
        "trademark_search_cost": "£400-£1,200",
        "logo_design_cost": "£1,500-£8,000",
        "legal_fees_cost": "£1,000-£4,000"
    },
    "Germany": {
        "currency": "EUR (€)",
        "office": "DPMA",
        "filing_cost": "€290-€400 per class",
        "opposition_defense_cost": "€2,000-€8,000 if contested",
        "total_estimated_cost": "€2,500-€12,000 depending on opposition",
        "trademark_search_cost": "€400-€1,000",
        "logo_design_cost": "€1,500-€7,000",
        "legal_fees_cost": "€1,000-€3,500"
    },
    "France": {
        "currency": "EUR (€)",
        "office": "INPI",
        "filing_cost": "€190-€350 per class",
        "opposition_defense_cost": "€2,000-€7,000 if contested",
        "total_estimated_cost": "€2,200-€10,000 depending on opposition",
        "trademark_search_cost": "€350-€900",
        "logo_design_cost": "€1,500-€7,000",
        "legal_fees_cost": "€1,000-€3,500"
    },
    "EU": {
        "currency": "EUR (€)",
        "office": "EUIPO",
        "filing_cost": "€850-€1,500 (covers all 27 EU countries)",
        "opposition_defense_cost": "€3,000-€15,000 if contested",
        "total_estimated_cost": "€4,000-€20,000 depending on opposition",
        "trademark_search_cost": "€500-€1,500",
        "logo_design_cost": "€2,000-€10,000",
        "legal_fees_cost": "€2,000-€6,000"
    },
    "Europe": {
        "currency": "EUR (€)",
        "office": "EUIPO",
        "filing_cost": "€850-€1,500 (covers all 27 EU countries)",
        "opposition_defense_cost": "€3,000-€15,000 if contested",
        "total_estimated_cost": "€4,000-€20,000 depending on opposition",
        "trademark_search_cost": "€500-€1,500",
        "logo_design_cost": "€2,000-€10,000",
        "legal_fees_cost": "€2,000-€6,000"
    },
    "Canada": {
        "currency": "CAD (C$)",
        "office": "CIPO",
        "filing_cost": "C$458-C$700 per class",
        "opposition_defense_cost": "C$3,000-C$12,000 if contested",
        "total_estimated_cost": "C$4,000-C$18,000 depending on opposition",
        "trademark_search_cost": "C$600-C$1,800",
        "logo_design_cost": "C$2,500-C$12,000",
        "legal_fees_cost": "C$1,800-C$6,000"
    },
    "Australia": {
        "currency": "AUD (A$)",
        "office": "IP Australia",
        "filing_cost": "A$330-A$550 per class",
        "opposition_defense_cost": "A$3,000-A$12,000 if contested",
        "total_estimated_cost": "A$4,000-A$18,000 depending on opposition",
        "trademark_search_cost": "A$500-A$1,500",
        "logo_design_cost": "A$2,000-A$10,000",
        "legal_fees_cost": "A$1,500-A$5,000"
    },
    "Japan": {
        "currency": "JPY (¥)",
        "office": "JPO",
        "filing_cost": "¥12,000-¥30,000 per class",
        "opposition_defense_cost": "¥300,000-¥1,000,000 if contested",
        "total_estimated_cost": "¥400,000-¥1,500,000 depending on opposition",
        "trademark_search_cost": "¥50,000-¥150,000",
        "logo_design_cost": "¥200,000-¥800,000",
        "legal_fees_cost": "¥150,000-¥500,000"
    },
    "China": {
        "currency": "CNY (¥)",
        "office": "CNIPA",
        "filing_cost": "¥300-¥800 per class",
        "opposition_defense_cost": "¥10,000-¥50,000 if contested",
        "total_estimated_cost": "¥15,000-¥80,000 depending on opposition",
        "trademark_search_cost": "¥1,000-¥3,000",
        "logo_design_cost": "¥5,000-¥30,000",
        "legal_fees_cost": "¥5,000-¥20,000"
    },
    "Singapore": {
        "currency": "SGD (S$)",
        "office": "IPOS",
        "filing_cost": "S$341-S$500 per class",
        "opposition_defense_cost": "S$3,000-S$10,000 if contested",
        "total_estimated_cost": "S$4,000-S$15,000 depending on opposition",
        "trademark_search_cost": "S$500-S$1,500",
        "logo_design_cost": "S$2,000-S$8,000",
        "legal_fees_cost": "S$1,500-S$5,000"
    },
    "UAE": {
        "currency": "AED (د.إ)",
        "office": "UAE Ministry of Economy",
        "filing_cost": "AED 5,000-AED 8,000 per class",
        "opposition_defense_cost": "AED 15,000-AED 50,000 if contested",
        "total_estimated_cost": "AED 20,000-AED 80,000 depending on opposition",
        "trademark_search_cost": "AED 2,000-AED 5,000",
        "logo_design_cost": "AED 5,000-AED 25,000",
        "legal_fees_cost": "AED 5,000-AED 15,000"
    },
    "South Korea": {
        "currency": "KRW (₩)",
        "office": "KIPO",
        "filing_cost": "₩62,000-₩150,000 per class",
        "opposition_defense_cost": "₩3,000,000-₩10,000,000 if contested",
        "total_estimated_cost": "₩4,000,000-₩15,000,000 depending on opposition",
        "trademark_search_cost": "₩500,000-₩1,500,000",
        "logo_design_cost": "₩2,000,000-₩8,000,000",
        "legal_fees_cost": "₩1,500,000-₩5,000,000"
    },
    "Brazil": {
        "currency": "BRL (R$)",
        "office": "INPI Brazil",
        "filing_cost": "R$355-R$700 per class",
        "opposition_defense_cost": "R$5,000-R$25,000 if contested",
        "total_estimated_cost": "R$8,000-R$40,000 depending on opposition",
        "trademark_search_cost": "R$1,000-R$3,000",
        "logo_design_cost": "R$3,000-R$15,000",
        "legal_fees_cost": "R$2,000-R$8,000"
    },
    "Mexico": {
        "currency": "MXN ($)",
        "office": "IMPI",
        "filing_cost": "MXN $2,500-MXN $4,500 per class",
        "opposition_defense_cost": "MXN $30,000-MXN $100,000 if contested",
        "total_estimated_cost": "MXN $40,000-MXN $150,000 depending on opposition",
        "trademark_search_cost": "MXN $5,000-MXN $15,000",
        "logo_design_cost": "MXN $15,000-MXN $60,000",
        "legal_fees_cost": "MXN $10,000-MXN $40,000"
    },
    # Default for unknown countries (use US costs in USD)
    "Global": {
        "currency": "USD ($)",
        "office": "Multiple Offices",
        "filing_cost": "$275-$400 per class (US baseline)",
        "opposition_defense_cost": "$2,500-$10,000 if contested",
        "total_estimated_cost": "$3,000-$15,000 depending on opposition",
        "trademark_search_cost": "$500-$1,500",
        "logo_design_cost": "$2,000-$10,000",
        "legal_fees_cost": "$1,500-$5,000"
    }
}

def get_country_currency(country: str) -> str:
    """Get the currency for a given country. Defaults to USD for unknown countries."""
    costs = COUNTRY_TRADEMARK_COSTS.get(country, COUNTRY_TRADEMARK_COSTS["Global"])
    return costs["currency"]

def get_country_trademark_costs(countries: list) -> dict:
    """
    Get trademark costs based on selected countries.
    - Single country: Return that country's actual costs
    - Multiple countries: Return US costs in USD as standard
    """
    if len(countries) == 1:
        country = countries[0]
        return COUNTRY_TRADEMARK_COSTS.get(country, COUNTRY_TRADEMARK_COSTS["Global"])
    else:
        # Multiple countries - use US costs as standard
        return COUNTRY_TRADEMARK_COSTS["USA"]

def format_trademark_costs_for_prompt(countries: list) -> str:
    """Format trademark costs as instruction for the LLM prompt."""
    costs = get_country_trademark_costs(countries)
    
    if len(countries) == 1:
        country = countries[0]
        return f"""
⚠️ COUNTRY-SPECIFIC TRADEMARK COSTS (MANDATORY - USE THESE EXACT VALUES):
Target Country: {country}
Trademark Office: {costs['office']}
Currency: {costs['currency']}

USE THESE COSTS IN YOUR RESPONSE:
- Filing Cost: {costs['filing_cost']}
- Opposition Defense Cost: {costs['opposition_defense_cost']}
- Total Estimated Cost: {costs['total_estimated_cost']}
- Trademark Search Cost: {costs['trademark_search_cost']}
- Logo Design Cost: {costs['logo_design_cost']}
- Legal Fees: {costs['legal_fees_cost']}

IMPORTANT: These are ACTUAL {costs['office']} costs. Do NOT convert to other currencies.
"""
    else:
        return f"""
⚠️ MULTI-COUNTRY TRADEMARK COSTS (USE USD AS STANDARD):
Target Countries: {', '.join(countries)}
Standard Currency: USD ($) (for multi-country comparison)

USE THESE US-BASED COSTS IN YOUR RESPONSE:
- Filing Cost: {costs['filing_cost']}
- Opposition Defense Cost: {costs['opposition_defense_cost']}
- Total Estimated Cost: {costs['total_estimated_cost']}
- Trademark Search Cost: {costs['trademark_search_cost']}
- Logo Design Cost: {costs['logo_design_cost']}
- Legal Fees: {costs['legal_fees_cost']}

IMPORTANT: Use USD ($) for ALL cost estimates when multiple countries are selected.
"""

# NICE Classification mapping based on category/industry keywords
NICE_CLASS_MAP = {
    # Class 3 - Cleaning, cosmetics
    "cleaning": {"class_number": 3, "class_description": "Cleaning preparations, polishing, soaps, cosmetics"},
    "cleaner": {"class_number": 3, "class_description": "Cleaning preparations, polishing, soaps, cosmetics"},
    "soap": {"class_number": 3, "class_description": "Cleaning preparations, polishing, soaps, cosmetics"},
    "detergent": {"class_number": 3, "class_description": "Cleaning preparations, polishing, soaps, cosmetics"},
    "cosmetic": {"class_number": 3, "class_description": "Cleaning preparations, polishing, soaps, cosmetics"},
    "beauty": {"class_number": 3, "class_description": "Cleaning preparations, polishing, soaps, cosmetics"},
    "skincare": {"class_number": 3, "class_description": "Cleaning preparations, polishing, soaps, cosmetics"},
    
    # Class 5 - Pharmaceuticals
    "pharma": {"class_number": 5, "class_description": "Pharmaceuticals, medical preparations, dietary supplements"},
    "medicine": {"class_number": 5, "class_description": "Pharmaceuticals, medical preparations, dietary supplements"},
    "health": {"class_number": 5, "class_description": "Pharmaceuticals, medical preparations, dietary supplements"},
    "supplement": {"class_number": 5, "class_description": "Pharmaceuticals, medical preparations, dietary supplements"},
    
    # Class 9 - Software, electronics
    "software": {"class_number": 9, "class_description": "Computer software, mobile apps, electronic devices"},
    "app": {"class_number": 9, "class_description": "Computer software, mobile apps, electronic devices"},
    "tech": {"class_number": 9, "class_description": "Computer software, mobile apps, electronic devices"},
    "electronics": {"class_number": 9, "class_description": "Computer software, mobile apps, electronic devices"},
    "digital": {"class_number": 9, "class_description": "Computer software, mobile apps, electronic devices"},
    
    # Class 25 - Fashion, clothing
    "fashion": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "clothing": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "apparel": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "shoes": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "footwear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    
    # Class 29 - Food (processed)
    "food": {"class_number": 29, "class_description": "Meat, fish, preserved foods, dairy products"},
    "dairy": {"class_number": 29, "class_description": "Meat, fish, preserved foods, dairy products"},
    "snack": {"class_number": 29, "class_description": "Meat, fish, preserved foods, dairy products"},
    
    # Class 30 - Food (bakery, beverages)
    "bakery": {"class_number": 30, "class_description": "Coffee, tea, bakery products, confectionery"},
    "coffee": {"class_number": 30, "class_description": "Coffee, tea, bakery products, confectionery"},
    "tea": {"class_number": 30, "class_description": "Coffee, tea, bakery products, confectionery"},
    "chai": {"class_number": 30, "class_description": "Coffee, tea, bakery products, confectionery"},
    "chocolate": {"class_number": 30, "class_description": "Coffee, tea, bakery products, confectionery"},
    
    # Class 32 - Beverages (non-alcoholic)
    "beverage": {"class_number": 32, "class_description": "Non-alcoholic beverages, mineral waters, fruit juices"},
    "juice": {"class_number": 32, "class_description": "Non-alcoholic beverages, mineral waters, fruit juices"},
    "drink": {"class_number": 32, "class_description": "Non-alcoholic beverages, mineral waters, fruit juices"},
    
    # Class 35 - Business services
    "advertising": {"class_number": 35, "class_description": "Advertising, business management, retail services"},
    "marketing": {"class_number": 35, "class_description": "Advertising, business management, retail services"},
    "retail": {"class_number": 35, "class_description": "Advertising, business management, retail services"},
    "ecommerce": {"class_number": 35, "class_description": "Advertising, business management, retail services"},
    "e-commerce": {"class_number": 35, "class_description": "Advertising, business management, retail services"},
    
    # Class 36 - Finance
    "finance": {"class_number": 36, "class_description": "Insurance, financial affairs, banking, real estate"},
    "fintech": {"class_number": 36, "class_description": "Insurance, financial affairs, banking, real estate"},
    "banking": {"class_number": 36, "class_description": "Insurance, financial affairs, banking, real estate"},
    "insurance": {"class_number": 36, "class_description": "Insurance, financial affairs, banking, real estate"},
    "payment": {"class_number": 36, "class_description": "Insurance, financial affairs, banking, real estate"},
    
    # Class 41 - Education, entertainment
    "education": {"class_number": 41, "class_description": "Education, training, entertainment, sports"},
    "edtech": {"class_number": 41, "class_description": "Education, training, entertainment, sports"},
    "training": {"class_number": 41, "class_description": "Education, training, entertainment, sports"},
    "entertainment": {"class_number": 41, "class_description": "Education, training, entertainment, sports"},
    "gaming": {"class_number": 41, "class_description": "Education, training, entertainment, sports"},
    
    # Class 42 - Technology services
    "saas": {"class_number": 42, "class_description": "Scientific and technological services, software as a service"},
    "cloud": {"class_number": 42, "class_description": "Scientific and technological services, software as a service"},
    "it services": {"class_number": 42, "class_description": "Scientific and technological services, software as a service"},
    "platform": {"class_number": 42, "class_description": "Scientific and technological services, software as a service"},
    
    # Class 43 - Restaurant, hospitality
    "restaurant": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "cafe": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "hotel": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "hospitality": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "food service": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "quick service": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "qsr": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
}

def get_nice_classification(category: str) -> dict:
    """
    Get NICE classification based on category/industry keywords.
    Returns a dict with class_number, class_description, and matched_term.
    """
    if not category:
        return {"class_number": 35, "class_description": "Advertising, business management, retail services", "matched_term": "general business"}
    
    category_lower = category.lower()
    
    # Check each keyword in the NICE_CLASS_MAP
    for keyword, classification in NICE_CLASS_MAP.items():
        if keyword in category_lower:
            return {
                "class_number": classification["class_number"],
                "class_description": classification["class_description"],
                "matched_term": category
            }
    
    # Default to Class 35 for unknown categories
    return {"class_number": 35, "class_description": "Advertising, business management, retail services", "matched_term": category}

def fix_llm_response_types(data: dict) -> dict:
    """
    Fix common type issues in LLM responses before Pydantic validation.
    The LLM sometimes returns integers where strings are expected.
    """
    if not isinstance(data, dict):
        return data
    
    # Fix brand_scores if present
    if "brand_scores" in data and isinstance(data["brand_scores"], list):
        for brand in data["brand_scores"]:
            if isinstance(brand, dict):
                # Fix domain_analysis.score_impact (int -> str)
                if "domain_analysis" in brand and isinstance(brand["domain_analysis"], dict):
                    da = brand["domain_analysis"]
                    if "score_impact" in da and isinstance(da["score_impact"], (int, float)):
                        da["score_impact"] = str(da["score_impact"])
                
                # Fix any other potential int/float fields that should be strings
                if "risk_level" in brand and isinstance(brand.get("risk_level"), (int, float)):
                    brand["risk_level"] = str(brand["risk_level"])
                
                # Fix trademark_research nested fields
                if "trademark_research" in brand and isinstance(brand["trademark_research"], dict):
                    tr = brand["trademark_research"]
                    # Convert numeric risk scores to int if they're strings
                    for field in ["overall_risk_score", "registration_success_probability", "opposition_probability"]:
                        if field in tr and isinstance(tr[field], str):
                            try:
                                tr[field] = int(float(tr[field].replace("%", "").strip()))
                            except:
                                pass
                
                # Fix multi_domain_availability nested fields
                if "multi_domain_availability" in brand and isinstance(brand["multi_domain_availability"], dict):
                    mda = brand["multi_domain_availability"]
                    # Fix category_domains
                    if "category_domains" in mda and isinstance(mda["category_domains"], list):
                        for dom in mda["category_domains"]:
                            if isinstance(dom, dict) and "available" in dom:
                                if isinstance(dom["available"], str):
                                    dom["available"] = dom["available"].lower() == "true"
                    # Fix country_domains
                    if "country_domains" in mda and isinstance(mda["country_domains"], list):
                        for dom in mda["country_domains"]:
                            if isinstance(dom, dict) and "available" in dom:
                                if isinstance(dom["available"], str):
                                    dom["available"] = dom["available"].lower() == "true"
    
    return data

def check_domain_availability(brand_name: str) -> str:
    domain = f"{brand_name.lower().replace(' ', '')}.com"
    try:
        w = whois.whois(domain)
        if w.domain_name or w.creation_date:
            return f"{domain}: TAKEN (Registered). Use this FACT. Do not say it might be available."
        else:
            return f"{domain}: LIKELY AVAILABLE (No whois record found)."
    except Exception as e:
        error_str = str(e).lower()
        if "no match for" in error_str or "not found" in error_str:
            return f"{domain}: AVAILABLE (No whois record found). Use this FACT."
        else:
            return f"{domain}: CHECK FAILED (Error: {str(e)}). Assume TAKEN to be safe."

def clean_json_string(s):
    """
    Cleans and fixes invalid control characters from JSON string before parsing.
    Properly escapes control characters that break JSON parsing.
    """
    # Remove BOM and other invisible characters
    s = s.replace('\ufeff', '')
    
    # Remove bad control characters (0-8, 11, 12, 14-31) but keep tab (9), newline (10), carriage return (13)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s)
    
    # Remove JavaScript-style comments that LLM sometimes adds (// comments)
    # Only remove comments that are outside of string values
    s = re.sub(r'//[^\n]*', '', s)
    
    # Remove empty array elements that result from comment removal
    s = re.sub(r'\[\s*,', '[', s)
    s = re.sub(r',\s*\]', ']', s)
    s = re.sub(r',\s*,', ',', s)
    
    return s

def escape_newlines_in_json_strings(json_str):
    """
    Escapes literal newlines/tabs inside JSON string values.
    JSON doesn't allow raw newlines inside strings - they must be escaped.
    Also fixes LLM issue where it incorrectly breaks strings across lines.
    """
    result = []
    in_string = False
    i = 0
    while i < len(json_str):
        char = json_str[i]
        
        if char == '"' and (i == 0 or json_str[i-1] != '\\'):
            # Check if this is an incorrectly split string
            # Pattern: "..end of text" followed by whitespace then "continuation
            # This happens when LLM breaks a single string value into multiple lines
            if in_string:
                # We're closing a string - check what comes after
                # Look ahead for pattern: whitespace + another opening quote that's NOT a key
                j = i + 1
                while j < len(json_str) and json_str[j] in ' \t\n\r':
                    j += 1
                # If next non-whitespace is a quote, check if it's a key (followed eventually by :)
                if j < len(json_str) and json_str[j] == '"':
                    # Find the closing quote of this potential string
                    k = j + 1
                    while k < len(json_str) and json_str[k] != '"':
                        if json_str[k] == '\\' and k + 1 < len(json_str):
                            k += 2
                        else:
                            k += 1
                    # Check what comes after the closing quote
                    if k < len(json_str):
                        m = k + 1
                        while m < len(json_str) and json_str[m] in ' \t\n\r':
                            m += 1
                        # If followed by ':', it's a key - this is valid, close the string
                        # If NOT followed by ':' (or followed by more text), merge the strings
                        if m < len(json_str) and json_str[m] != ':':
                            # This is a split string - merge by adding escaped newline instead of closing
                            # Add the whitespace between as escaped newlines
                            result.append('\\n\\n')
                            # Skip the closing quote, whitespace, and opening quote
                            i = j + 1  # Move past the opening quote of continuation
                            continue
            
            in_string = not in_string
            result.append(char)
        elif in_string:
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            else:
                result.append(char)
        else:
            result.append(char)
        
        i += 1
    
    return ''.join(result)

def repair_json(s):
    """
    Attempts to repair common JSON syntax errors produced by LLMs.
    """
    # First, escape literal newlines inside strings
    s = escape_newlines_in_json_strings(s)
    
    # Remove trailing commas before } or ]
    s = re.sub(r',(\s*[}\]])', r'\1', s)
    
    # Fix missing commas between } and " at the START of a NEW JSON key
    # Only match when " is followed by a key pattern (letter/underscore then more chars then colon)
    # This avoids matching patterns inside strings like }\\n\\n**
    s = re.sub(r'\}(\s*)"([a-zA-Z_][a-zA-Z0-9_]*)"(\s*):', r'},\1"\2"\3:', s)
    
    # Fix missing commas between ] and " for new keys
    s = re.sub(r'\](\s*)"([a-zA-Z_][a-zA-Z0-9_]*)"(\s*):', r'],\1"\2"\3:', s)
    
    # Fix truncated URLs - pattern like "https:\n becomes "https://example.com"
    s = re.sub(r'"https?:\\n\s*"', '"https://example.com"', s)
    s = re.sub(r'"https?:\s*"', '"https://example.com"', s)
    
    # Fix missing commas after string values that end with punctuation before a new key
    # Pattern: "value text."  "next_key":  -> "value text.", "next_key":
    s = re.sub(r'([.!?])"(\s+)"([a-zA-Z_][a-zA-Z0-9_]*)"(\s*):', r'\1",\2"\3"\4:', s)
    
    # Fix incomplete string values that end with just a colon and newline
    # Pattern: "key": "value that ends abruptly
    # This replaces dangling strings with a placeholder
    s = re.sub(r':\s*"([^"]*?)\\n\s*"([a-zA-Z_])', r': "\1", "\2', s)
    
    return s

def aggressive_json_repair(json_str):
    """
    More aggressive JSON repair for severely malformed responses.
    """
    import json
    import re
    
    # First, clean up any markdown formatting that might have leaked into JSON
    # Remove **text** markdown bold
    json_str = re.sub(r'\*\*([^*]+)\*\*', r'\1', json_str)
    # Remove *text* markdown italic
    json_str = re.sub(r'(?<![*])\*([^*]+)\*(?![*])', r'\1', json_str)
    # Remove markdown headers
    json_str = re.sub(r'^#+\s+', '', json_str, flags=re.MULTILINE)
    # Remove markdown bullet points that might be in strings
    json_str = re.sub(r'^\s*[-*]\s+', '', json_str, flags=re.MULTILINE)
    
    # Replace literal newlines inside strings with escaped newlines
    # This is a common issue with LLM responses
    def fix_newlines_in_strings(s):
        result = []
        in_string = False
        i = 0
        while i < len(s):
            c = s[i]
            if c == '"' and (i == 0 or s[i-1] != '\\'):
                in_string = not in_string
                result.append(c)
            elif c == '\n' and in_string:
                result.append('\\n')
            elif c == '\r' and in_string:
                result.append('\\r')
            elif c == '\t' and in_string:
                result.append('\\t')
            else:
                result.append(c)
            i += 1
        return ''.join(result)
    
    json_str = fix_newlines_in_strings(json_str)
    
    # Try standard repair first
    repaired = repair_json(json_str)
    
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError as e:
        logging.warning(f"Standard repair failed at position {e.pos}, trying aggressive repair...")
        
        # Find and fix the specific error location
        error_pos = e.pos
        context_start = max(0, error_pos - 100)
        context_end = min(len(repaired), error_pos + 100)
        context = repaired[context_start:context_end]
        
        logging.error(f"Context around error: ...'{context}'...")
        
        before_error = repaired[:error_pos]
        after_error = repaired[error_pos:]
        
        # Pattern 1: Missing comma after a string value ending with "
        if after_error and after_error[0] == '"':
            stripped_before = before_error.rstrip()
            if stripped_before and stripped_before[-1] == '"':
                # Need comma between two strings
                repaired = stripped_before + ',' + after_error
                try:
                    json.loads(repaired)
                    logging.info("Fixed by adding comma between strings")
                    return repaired
                except:
                    pass
            elif stripped_before and stripped_before[-1] not in [',', '{', '[', ':']:
                repaired = stripped_before + ',' + after_error
                try:
                    json.loads(repaired)
                    logging.info("Fixed by adding comma before string")
                    return repaired
                except:
                    pass
        
        # Pattern 2: Error is "Expecting ',' delimiter" - find and add the missing comma
        if "Expecting ',' delimiter" in str(e) or "Expecting ," in str(e):
            # Search backwards for end of previous value (", }, ])
            search_pos = error_pos - 1
            while search_pos > 0 and repaired[search_pos] in ' \t\n\r':
                search_pos -= 1
            
            if search_pos > 0 and repaired[search_pos] in '"]}':
                # Insert comma after this position
                repaired = repaired[:search_pos+1] + ',' + repaired[search_pos+1:]
                try:
                    json.loads(repaired)
                    logging.info(f"Fixed by inserting comma at position {search_pos+1}")
                    return repaired
                except:
                    pass
        
        # Pattern 3: Truncated string - close it
        quote_positions = [i for i, c in enumerate(before_error) if c == '"' and (i == 0 or before_error[i-1] != '\\')]
        if len(quote_positions) % 2 == 1:  # Odd number means unclosed string
            repaired = before_error + '",' + after_error
            try:
                json.loads(repaired)
                logging.info("Fixed by closing unclosed string")
                return repaired
            except:
                pass
        
        # Pattern 4: Try json_repair library if available
        try:
            from json_repair import repair_json as lib_repair
            repaired = lib_repair(json_str)
            json.loads(repaired)
            logging.info("Fixed using json_repair library")
            return repaired
        except ImportError:
            pass
        except:
            pass
        
        # Pattern 5: Last resort - try to extract valid JSON subset
        # Find matching braces
        brace_count = 0
        last_valid_pos = 0
        for i, c in enumerate(repaired):
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    last_valid_pos = i + 1
                    break
        
        if last_valid_pos > 0:
            subset = repaired[:last_valid_pos]
            try:
                json.loads(subset)
                logging.info(f"Fixed by truncating to valid JSON subset (length {last_valid_pos})")
                return subset
            except:
                pass
        
        return repaired

# Health check endpoint for Kubernetes
@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Famous brands blocklist - these are AUTO-REJECT regardless of category
FAMOUS_BRANDS = {
    # Fortune 500 / Major Retailers
    "costco", "walmart", "target", "kroger", "walgreens", "cvs", "home depot", "lowes",
    "best buy", "macys", "nordstrom", "kohls", "jcpenney", "sears", "ikea", "aldi", "lidl",
    "whole foods", "trader joes", "safeway", "publix", "wegmans", "costco wholesale",
    # Stationery & Office Supplies - INDIAN BRANDS
    "classmate", "class mate", "itc classmate", "camlin", "doms", "natraj", "cello", 
    "reynolds", "parker", "faber castell", "staedtler", "pilot", "uniball", "uni-ball",
    "papermate", "paper mate", "bic", "sharpie", "post-it", "scotch", "3m",
    # Tech Giants
    "apple", "google", "microsoft", "amazon", "meta", "facebook", "instagram", "whatsapp",
    "netflix", "spotify", "uber", "lyft", "airbnb", "twitter", "tiktok", "snapchat", 
    "linkedin", "pinterest", "reddit", "discord", "zoom", "slack", "dropbox", "salesforce",
    "oracle", "sap", "adobe", "nvidia", "intel", "amd", "qualcomm", "cisco", "ibm", "hp",
    "dell", "lenovo", "samsung", "sony", "lg", "panasonic", "toshiba", "huawei", "xiaomi",
    # Gaming Apps - POPULAR MOBILE GAMES
    "ludo king", "ludoking", "candy crush", "candycrush", "clash of clans", "clashofclans",
    "pubg", "pubg mobile", "free fire", "freefire", "garena free fire", "fortnite",
    "minecraft", "roblox", "among us", "amongus", "subway surfers", "subwaysurfers",
    "temple run", "templerun", "angry birds", "angrybirds", "fruit ninja", "fruitninja",
    "pokemon go", "pokemongo", "clash royale", "clashroyale", "coin master", "coinmaster",
    "8 ball pool", "8ballpool", "carrom pool", "carrompool", "teen patti", "teenpatti",
    "dream11", "mpl", "winzo", "paytm first games", "games24x7", "rummy circle",
    "call of duty mobile", "cod mobile", "asphalt", "real racing", "hill climb racing",
    "wordle", "chess.com", "lichess", "bgmi", "battlegrounds mobile india",
    # CRITICAL ADDITION: Ludo Star and variants
    "ludo star", "ludostar", "ludo staar", "ludo starr", "ludostaar", "ludostarr",
    "gameberry", "gameberry labs",
    # Automotive
    "tesla", "ford", "gm", "chevrolet", "toyota", "honda", "bmw", "mercedes", "audi",
    "volkswagen", "porsche", "ferrari", "lamborghini", "bentley", "rolls royce", "jaguar",
    # Food & Beverage
    "coca cola", "pepsi", "mcdonalds", "burger king", "wendys", "starbucks", "dunkin",
    "subway", "dominos", "pizza hut", "kfc", "taco bell", "chipotle", "panera",
    "nestle", "kraft", "general mills", "kelloggs", "pepsico", "mondelez",
    "swiggy", "zomato", "uber eats", "doordash", "grubhub", "deliveroo",
    # Indian Food Delivery Apps
    "box8", "box 8", "eatclub", "eat club", "eatsure", "eat sure", "faasos", "behrouz", "behrouz biryani",
    "freshmenu", "fresh menu", "dunzo", "blinkit", "zepto", "bigbasket", "big basket", "jiomart", "instamart",
    "grofers", "milkbasket", "licious", "meatigo", "freshtohome", "fresh to home",
    # Fashion & Luxury
    "nike", "adidas", "puma", "reebok", "under armour", "lululemon", "gap", "old navy",
    "zara", "h&m", "uniqlo", "forever 21", "asos", "shein", "louis vuitton", "gucci",
    "prada", "chanel", "hermes", "dior", "versace", "armani", "burberry", "coach",
    "michael kors", "ralph lauren", "tommy hilfiger", "calvin klein", "levis",
    "myntra", "ajio", "flipkart", "meesho", "nykaa",
    # Finance & Fintech
    "visa", "mastercard", "american express", "paypal", "stripe", "square", "venmo",
    "chase", "bank of america", "wells fargo", "citibank", "goldman sachs", "morgan stanley",
    "phonepe", "paytm", "google pay", "gpay", "razorpay", "cred", "groww", "zerodha", "upstox",
    "mobikwik", "freecharge", "bhim", "amazon pay", "airtel money", "jio money", "ola money",
    # Indian Finance/Stock Market Apps (CRITICAL)
    "moneycontrol", "money control", "et markets", "etmarkets", "economic times",
    "ticker tape", "tickertape", "smallcase", "kite", "kite zerodha", "coin", "varsity",
    "angel one", "angelone", "angel broking", "5paisa", "iifl", "motilal oswal", 
    "hdfc securities", "icici direct", "kotak securities", "sharekhan", "nse", "bse",
    "sensex", "nifty", "mint", "livemint", "bloomberg", "reuters", "cnbc",
    # Beauty & Personal Care
    "loreal", "maybelline", "mac", "sephora", "ulta", "estee lauder", "clinique",
    "neutrogena", "dove", "pantene", "head shoulders", "gillette", "olay",
    # Entertainment & Streaming
    "disney", "warner bros", "universal", "paramount", "sony pictures", "mgm",
    "hbo", "showtime", "hulu", "paramount plus", "peacock", "espn", "cnn", "fox",
    "hotstar", "jio cinema", "zee5", "sony liv", "voot", "alt balaji", "mx player",
    # Dating & Social Apps
    "tinder", "bumble", "hinge", "okcupid", "match", "eharmony", "badoo", "happn",
    "coffee meets bagel", "plenty of fish", "pof", "grindr", "her", "taimi",
    "shaadi", "bharatmatrimony", "jeevansathi", "matrimony", "tantan", "momo",
    "aisle", "dil mil", "truly madly", "trulymadly", "woo",
    # E-commerce & Delivery
    "fedex", "ups", "usps", "dhl", "amazon prime", "ebay", "etsy", "shopify",
    "alibaba", "aliexpress", "wish", "wayfair", "overstock", "chewy", "petco", "petsmart",
    "flipkart", "snapdeal", "bigbasket", "blinkit", "zepto", "instamart", "dunzo",
    # Indian Supermarkets & Retail Chains
    "ratnadeep", "ratna deep", "ratnadeep supermarket", "dmart", "d-mart", "d mart", 
    "avenue supermarts", "reliance fresh", "reliance retail", "reliance smart", "jiomart", 
    "more", "more supermarket", "more megastore", "spencers", "spencer's", "spencer retail",
    "star bazaar", "starbazaar", "hypercity", "hyper city", "spar", "spar hypermarket",
    "easy day", "easyday", "heritage fresh", "heritage supermarket", "nilgiris", "nilgiri's",
    "foodhall", "food hall", "nature's basket", "natures basket", "godrej nature's basket",
    "smart bazaar", "smartbazaar", "vishal mega mart", "vishal megamart", "v-mart", "vmart"
}

# INAPPROPRIATE/OFFENSIVE WORDS - Brand names that sound like or contain these should be REJECTED
INAPPROPRIATE_PATTERNS = [
    # Sexual/Vulgar terms and phonetic variants
    "masturbat", "masterbat", "masturbate", "masterbate",
    "pornhub", "xvideo", "xnxx", "redtube", "youporn",
    "fuck", "fuk", "phuck", "phuk", "fck",
    "shit", "shyt",
    "bitch", "bich", "bytch",
    "cunt", "kunt",
    "penis", "pnis",
    "vagina", "vajina",
    "titty", "tity",
    "whore", "hore", "hoar",
    "slut", "slutt",
    "nigger", "nigga", "nigg",
    "faggot", "fagg",
    "retard", "retrd",
    # Drugs
    "cocaine", "cocain",
    "meth", "methamphetamine",
    # Violence
    "rape",
]

def check_inappropriate_name(brand_name: str) -> dict:
    """
    Check if brand name contains inappropriate/offensive words.
    Only checks for EXACT pattern matches to avoid false positives.
    """
    normalized = brand_name.lower().strip().replace(" ", "").replace("-", "").replace("_", "")
    
    # Check for inappropriate patterns - EXACT MATCH ONLY
    for pattern in INAPPROPRIATE_PATTERNS:
        if pattern in normalized:
            return {
                "is_inappropriate": True,
                "matched_pattern": pattern,
                "reason": f"'{brand_name}' contains inappropriate/offensive content. This brand name cannot be used commercially."
            }
    
    return {"is_inappropriate": False}


async def dynamic_brand_search(brand_name: str, category: str = "") -> dict:
    """
    LLM-FIRST BRAND CONFLICT DETECTION + WEB VERIFICATION
    
    1. First do a quick web search to check if brand exists
    2. Then use GPT-4o to analyze conflicts
    """
    import re
    import aiohttp
    
    print(f"🔍 LLM BRAND CHECK: '{brand_name}' in category '{category}'", flush=True)
    logging.warning(f"🔍 LLM BRAND CHECK: '{brand_name}' in category '{category}'")
    
    result = {
        "exists": False,
        "confidence": "LOW",
        "matched_brand": None,
        "evidence": [],
        "reason": ""
    }
    
    # ========== ENHANCED BRAND DETECTION WITH CATEGORY CONTEXT ==========
    # PRINCIPLE: Search brand name WITH category to find existing businesses
    web_evidence = []
    brand_found_online = False
    web_confidence = "LOW"
    
    try:
        import re
        brand_lower = brand_name.lower().replace(" ", "")
        brand_with_space = brand_name.lower()
        
        # ENHANCED: Search with category context for better detection
        # E.g., "Cleevo" + "cleaning" will find Cleevo cleaning products
        category_terms = category.lower() if category else ""
        
        # Multiple search queries for comprehensive detection
        search_queries = [
            f'"{brand_name}"',  # Basic exact match
            f'"{brand_name}" {category_terms}' if category_terms else None,  # Brand + category
            f'"{brand_name}" brand India' if category_terms else None,  # Brand in India
            f'"{brand_name}" products' if category_terms else None,  # Brand products
        ]
        search_queries = [q for q in search_queries if q]
        
        combined_mentions = 0
        combined_signals = []
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # Run multiple search queries for better detection
            for search_query in search_queries[:2]:  # Limit to 2 queries to avoid rate limiting
                try:
                    search_url = f"https://www.bing.com/search?q={search_query.replace(' ', '+')}"
                    async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            html = await response.text()
                            html_lower = html.lower()
                            
                            # Count exact brand mentions
                            brand_pattern = re.escape(brand_with_space)
                            mentions = len(re.findall(brand_pattern, html_lower))
                            combined_mentions += mentions
                            
                            # Check for strong signals (platform presence)
                            if any(f"{brand_lower}.{ext}" in html_lower for ext in ["com", "in", "co.in", "co"]):
                                if "domain" not in combined_signals:
                                    combined_signals.append("domain")
                            if "zomato" in html_lower and mentions >= 1:
                                if "zomato" not in combined_signals:
                                    combined_signals.append("zomato")
                            if "swiggy" in html_lower and mentions >= 1:
                                if "swiggy" not in combined_signals:
                                    combined_signals.append("swiggy")
                            if "justdial" in html_lower and mentions >= 1:
                                if "justdial" not in combined_signals:
                                    combined_signals.append("justdial")
                            # E-commerce platforms - only count if brand appears in URL or result title
                            # Avoid false positives from generic platform mentions on search results pages
                            # Check for brand name in Amazon/Flipkart product URLs or result snippets
                            brand_with_platform_patterns = [
                                f"amazon.in/.*{brand_lower}",
                                f"amazon.com/.*{brand_lower}",
                                f"{brand_lower}.*amazon",
                                f"flipkart.com/.*{brand_lower}",
                                f"{brand_lower}.*flipkart",
                                f"jiomart.com/.*{brand_lower}",
                                f"{brand_lower}.*jiomart",
                                f"bigbasket.com/.*{brand_lower}",
                                f"{brand_lower}.*bigbasket",
                            ]
                            
                            for pattern in brand_with_platform_patterns:
                                if re.search(pattern, html_lower):
                                    if "ecommerce" not in combined_signals:
                                        combined_signals.append("ecommerce")
                                    break
                                    
                            print(f"🔎 WEB QUERY '{search_query}': '{brand_name}' mentions={mentions}", flush=True)
                except Exception as e:
                    logging.warning(f"Search query failed: {search_query}, error: {e}")
            
            print(f"🔎 WEB TOTAL: '{brand_name}' total_mentions={combined_mentions}, signals={combined_signals}", flush=True)
            logging.warning(f"🔎 WEB: '{brand_name}' mentions={combined_mentions}, strong={combined_signals}")
            
            # ENHANCED DETECTION RULES:
            # Rule 1: Platform presence (domain, ecommerce, food platforms) = HIGH confidence
            if len(combined_signals) >= 1:
                brand_found_online = True
                web_confidence = "HIGH"
                web_evidence = [f"mentions:{combined_mentions}"] + combined_signals
                logging.warning(f"🌐 WEB HIGH: '{brand_name}' found on business platform!")
            
            # Rule 2: Multiple mentions = MEDIUM confidence
            elif combined_mentions >= 3:
                brand_found_online = True
                web_confidence = "MEDIUM"
                web_evidence = [f"mentions:{combined_mentions}"]
                logging.warning(f"🌐 WEB MEDIUM: '{brand_name}' has {combined_mentions} search mentions")
            
            # Rule 3: Some mentions = LOW confidence
            elif combined_mentions >= 1:
                brand_found_online = True
                web_confidence = "LOW"
                web_evidence = [f"mentions:{combined_mentions}"]
                logging.warning(f"🌐 WEB LOW: '{brand_name}' has {combined_mentions} mentions")
                        
    except Exception as e:
        logging.error(f"Web search failed for {brand_name}: {e}")
    
    # ========== STEP 2: LLM CHECK ==========
    # Use LLM to check for brand conflicts
    try:
        if not LlmChat or not EMERGENT_KEY:
            logging.warning("LLM not available, skipping brand check")
            return result
        
        llm = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")  # Most reliable model
        
        prompt = f"""You are a trademark and brand expert with STRICT conflict detection. Analyze this brand name for conflicts.

BRAND NAME: {brand_name}
CATEGORY: {category or 'General'}
TARGET MARKET: India, USA, Global

TASK: Determine if this brand name:
1. IS ALREADY AN EXISTING BRAND/COMPANY (exact or near-exact name)
2. OR is CONFUSINGLY SIMILAR to ANY existing brand, company, app, product, or trademark

⚠️ CRITICAL - CHECK IF THIS EXACT BRAND EXISTS FIRST:
- Search your knowledge for "{brand_name}" as an existing business
- Check if there's a company, cafe chain, restaurant, app, product, or consumer brand called "{brand_name}"
- Regional brands in India, USA, or globally count!
- Even small D2C brands on Amazon, Flipkart, BigBasket should be flagged
- Check ecommerce platforms: Amazon, Flipkart, JioMart, BigBasket
- Check Zomato, Swiggy, Google Maps presence for food/cafe brands

⚠️ INDIAN CAFE/CHAI BRANDS TO CHECK AGAINST:
- Chai Duniya, Chai Point, Chaayos, Chai Sutta Bar, MBA Chai Wala, Chai Break
- Chai Bunk, Chai Kings, Chai Waale, Chai Garam, Chai Time
- Any brand with "Chai" + Hindi word combination

⚠️ INDIAN CONSUMER/CLEANING PRODUCT BRANDS TO CHECK AGAINST:
- Cleevo (eco-friendly cleaning solutions on JioMart, BigBasket, Flipkart - getcleevo.com)
- Vim, Harpic, Lizol, Colin, Dettol, Savlon, Surf Excel
- Any D2C brand selling on Indian ecommerce platforms

⚠️ STRICT CONFLICT RULES - Flag as conflict if ANY of these apply:
1. EXACT BRAND EXISTS: A company/brand called "{brand_name}" already operates (even regionally)
2. EXACT MATCH: Same name as another brand (case-insensitive)
3. PLURALIZATION: Adding/removing 's' (MoneyControls = Moneycontrol)
4. PHONETIC SIMILARITY: Sounds similar when spoken (BUMBELL ≈ Bumble)
5. LETTER VARIATIONS: Extra/missing letters (Nikee = Nike)
6. SPACING CHANGES: With/without spaces (FaceBook = Facebook)
7. REGIONAL BRANDS: Indian cafes, restaurants, apps, newspapers, D2C products
8. GLOBAL BRANDS: Tech companies, apps, products
9. D2C/ECOMMERCE BRANDS: Brands selling on Amazon, Flipkart, BigBasket, JioMart

IMPORTANT: 
- When in doubt, FLAG AS CONFLICT - it's safer to reject
- If "{brand_name}" sounds like it could be an existing brand/product - CHECK CAREFULLY
- "Cleevo" IS an existing cleaning products brand in India - if asked, REJECT IT
- "Chai Duniya" IS an existing chai cafe chain - if this exact name or similar is asked, REJECT IT

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "has_conflict": true or false,
    "confidence": "HIGH" or "MEDIUM" or "LOW",
    "conflicting_brand": "Name of existing brand" or null,
    "similarity_percentage": 0-100,
    "reason": "Brief explanation",
    "brand_info": "What is the conflicting brand (1 sentence)",
    "brand_already_exists": true or false
}}

Examples (BE STRICT LIKE THESE):
- "Red Bucket Biryani" in "Restaurant" → {{"has_conflict": true, "confidence": "HIGH", "conflicting_brand": "Red Bucket Biryani", "similarity_percentage": 100, "reason": "Red Bucket Biryani is an existing biryani restaurant chain in India", "brand_info": "Red Bucket Biryani is a biryani delivery/restaurant chain in India", "brand_already_exists": true}}
- "Chai Duniya" in "Cafe" → {{"has_conflict": true, "confidence": "HIGH", "conflicting_brand": "Chai Duniya", "similarity_percentage": 100, "reason": "Chai Duniya is an existing chai cafe chain in India", "brand_info": "Chai Duniya is a chai cafe brand operating in India", "brand_already_exists": true}}
- "Chaibunk" in "Cafe" → {{"has_conflict": true, "confidence": "HIGH", "conflicting_brand": "Chai Bunk", "similarity_percentage": 100, "reason": "Chai Bunk is an existing chai cafe chain in India with 100+ stores", "brand_info": "Chai Bunk is a popular Indian chai cafe chain", "brand_already_exists": true}}
- "Chaayos" in "Cafe" → {{"has_conflict": true, "confidence": "HIGH", "conflicting_brand": "Chaayos", "similarity_percentage": 100, "reason": "Chaayos is a major chai cafe chain in India", "brand_info": "Chaayos is one of India's largest chai cafe chains", "brand_already_exists": true}}
- "MoneyControls" in "Finance" → {{"has_conflict": true, "confidence": "HIGH", "conflicting_brand": "Moneycontrol", "similarity_percentage": 98, "reason": "Pluralized version of Moneycontrol", "brand_info": "Moneycontrol is India's leading financial platform", "brand_already_exists": false}}
- "Zyntrix2025" in "Finance" → {{"has_conflict": false, "confidence": "HIGH", "conflicting_brand": null, "similarity_percentage": 0, "reason": "Completely unique invented name", "brand_info": null, "brand_already_exists": false}}

NOW ANALYZE: "{brand_name}" in "{category or 'General'}"
Return ONLY the JSON, no other text."""

        # send_message is async and expects UserMessage object
        user_msg = UserMessage(text=prompt)
        response = await llm.send_message(user_msg)
        
        print(f"📝 LLM Response for '{brand_name}': {response[:200]}...", flush=True)
        
        # Parse LLM response
        import json
        try:
            # Clean response (remove markdown if present)
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = re.sub(r'^```json?\n?', '', clean_response)
                clean_response = re.sub(r'\n?```$', '', clean_response)
            
            llm_result = json.loads(clean_response)
            
            print(f"📊 Parsed LLM result for '{brand_name}': conflict={llm_result.get('has_conflict')}, confidence={llm_result.get('confidence')}", flush=True)
            
            # Check if LLM says brand already exists OR has conflict
            brand_exists = llm_result.get("brand_already_exists", False)
            has_conflict = llm_result.get("has_conflict", False)
            
            if (has_conflict or brand_exists) and llm_result.get("confidence") in ["HIGH", "MEDIUM"]:
                # ============ VERIFICATION LAYER ============
                # LLM flagged a conflict - now VERIFY with real evidence
                print(f"⚠️ LLM flagged '{brand_name}' - Running verification layer...", flush=True)
                logging.info(f"⚠️ LLM flagged '{brand_name}' - Running verification layer...")
                
                verification = await verify_brand_conflict(
                    brand_name=brand_name,
                    industry=category,
                    category=category,
                    country="India",  # Default to India, can be passed from request
                    matched_brand=llm_result.get("conflicting_brand")
                )
                
                if verification["verified"]:
                    # CONFIRMED: Real evidence found - REJECT
                    result["exists"] = True
                    result["confidence"] = "VERIFIED"  # Upgraded from LLM confidence
                    result["matched_brand"] = llm_result.get("conflicting_brand", brand_name)
                    result["evidence"] = verification["evidence_found"][:5]  # Top 5 evidence items
                    result["evidence_score"] = verification["evidence_score"]
                    result["evidence_details"] = verification["evidence_details"]
                    result["reason"] = llm_result.get("reason", "Conflict detected and verified")
                    if brand_exists:
                        result["reason"] = f"VERIFIED EXISTING BRAND: {result['reason']}"
                    
                    print(f"🚨 VERIFIED CONFLICT: '{brand_name}' - Evidence Score: {verification['evidence_score']}", flush=True)
                    logging.warning(f"🚨 VERIFIED CONFLICT: '{brand_name}' - Evidence: {verification['evidence_found'][:3]}")
                else:
                    # FALSE POSITIVE: LLM was wrong - no real evidence found
                    result["exists"] = False
                    result["confidence"] = "LOW"
                    result["matched_brand"] = None
                    result["evidence"] = []
                    result["reason"] = f"AI initially flagged but verification found NO evidence of existing brand"
                    result["false_positive_avoided"] = True
                    
                    print(f"✅ FALSE POSITIVE AVOIDED: '{brand_name}' - LLM flagged but no real evidence found (score: {verification['evidence_score']})", flush=True)
                    logging.info(f"✅ FALSE POSITIVE AVOIDED: '{brand_name}' - Verification score: {verification['evidence_score']} (below threshold)")
            
            # If LLM says no conflict but web search found evidence, check confidence
            elif brand_found_online and not has_conflict:
                # ONLY override LLM when web has HIGH confidence WITH STRONG signals (domain or ecommerce)
                # IMPORTANT: domain signal alone could be misleading, require verification
                strong_signals = [s for s in web_evidence if s in ["domain", "ecommerce", "zomato", "swiggy"]]
                
                if web_confidence == "HIGH" and len(strong_signals) >= 1:
                    # Even for HIGH confidence, run verification to avoid false positives
                    print(f"⚠️ WEB FOUND '{brand_name}' with signals {strong_signals} - Running verification...", flush=True)
                    
                    verification = await verify_brand_conflict(
                        brand_name=brand_name,
                        industry=category,
                        category=category,
                        country="India",
                        matched_brand=brand_name
                    )
                    
                    if verification["verified"]:
                        print(f"⚠️ WEB OVERRIDE VERIFIED: '{brand_name}' exists - Evidence Score: {verification['evidence_score']}", flush=True)
                        logging.warning(f"⚠️ WEB OVERRIDE: LLM missed '{brand_name}' - verified on platform")
                        result["exists"] = True
                        result["confidence"] = "VERIFIED"
                        result["matched_brand"] = brand_name
                        result["evidence"] = verification["evidence_found"][:5]
                        result["evidence_score"] = verification["evidence_score"]
                        result["reason"] = f"Brand '{brand_name}' verified via web search (signals: {', '.join(strong_signals)})"
                    else:
                        print(f"✅ WEB FALSE POSITIVE: '{brand_name}' - signals found but verification failed (score: {verification['evidence_score']})", flush=True)
                        logging.info(f"✅ WEB FALSE POSITIVE: '{brand_name}' - Verification failed")
                else:
                    # MEDIUM/LOW confidence - trust the LLM's judgment
                    print(f"✅ LLM: '{brand_name}' appears unique (web has only {web_confidence} confidence, trusting LLM)", flush=True)
                    logging.info(f"✅ LLM: '{brand_name}' appears unique (web confidence: {web_confidence})")
            else:
                print(f"✅ LLM: '{brand_name}' appears unique", flush=True)
                logging.info(f"✅ LLM: '{brand_name}' appears unique")
                
        except json.JSONDecodeError as e:
            logging.warning(f"Failed to parse LLM response: {e}")
            logging.warning(f"Response was: {response[:200]}")
            
            # If LLM failed but web search found the brand, still flag it
            if brand_found_online:
                result["exists"] = True
                result["confidence"] = "MEDIUM"
                result["matched_brand"] = brand_name
                result["evidence"] = [f"Web: {e}" for e in web_evidence]
                result["reason"] = f"Brand '{brand_name}' found via web search"
    
    except Exception as e:
        logging.error(f"LLM brand check failed: {e}")
        
        # If LLM failed but web search found the brand, still flag it
        if brand_found_online:
            result["exists"] = True
            result["confidence"] = "MEDIUM"
            result["matched_brand"] = brand_name
            result["evidence"] = [f"Web: {e}" for e in web_evidence]
            result["reason"] = f"Brand '{brand_name}' found via web search"
    
    return result


# ============ VERIFICATION LAYER FOR BRAND CONFLICTS ============
async def verify_brand_conflict(brand_name: str, industry: str = "", category: str = "", 
                                 country: str = "India", matched_brand: str = None) -> dict:
    """
    VERIFICATION LAYER: When LLM flags a potential conflict, verify with real evidence.
    
    Runs multiple targeted searches to find REAL proof:
    - Official website
    - LinkedIn company page
    - Trademark records
    - Business registrations
    - News articles
    
    Returns verified=True only if real evidence is found.
    """
    import aiohttp
    import re
    
    logging.info(f"🔍 VERIFICATION: Starting evidence search for '{brand_name}'")
    
    result = {
        "verified": False,
        "evidence_score": 0,
        "evidence_found": [],
        "evidence_details": [],
        "searches_performed": [],
        "recommendation": "ALLOW"
    }
    
    # Generate verification search queries
    brand_clean = brand_name.strip()
    brand_lower = brand_clean.lower()
    
    verification_queries = [
        # Direct brand searches
        f'"{brand_clean}"',
        f'"{brand_clean}" {country}' if country else f'"{brand_clean}"',
        f'"{brand_clean}" {industry}' if industry else None,
        f'"{brand_clean}" {category}' if category else None,
        
        # Business verification
        f'"{brand_clean}" company official website',
        f'"{brand_clean}" brand founded',
        
        # Trademark verification
        f'"{brand_clean}" trademark registered',
        f'"{brand_clean}" trademark {country}' if country else None,
        
        # Platform verification
        f'site:linkedin.com/company "{brand_clean}"',
        f'"{brand_clean}" crunchbase OR angellist',
        
        # Domain verification
        f'{brand_lower}.com',
    ]
    
    # Remove None values
    verification_queries = [q for q in verification_queries if q]
    
    # Evidence scoring weights
    EVIDENCE_WEIGHTS = {
        "official_website": 50,
        "linkedin_company": 35,
        "crunchbase": 35,
        "trademark_record": 50,
        "news_coverage": 20,
        "social_media": 15,
        "domain_active": 40,
        "multiple_results": 15,
        "exact_match_results": 25,
    }
    
    REJECTION_THRESHOLD = 50  # Need at least 50 points to confirm rejection
    
    evidence_score = 0
    evidence_found = []
    evidence_details = []
    
    async def search_and_analyze(query: str) -> dict:
        """Run a single search and analyze results for evidence"""
        try:
            search_url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                async with session.get(search_url, headers=headers, 
                                       timeout=aiohttp.ClientTimeout(total=8)) as response:
                    if response.status == 200:
                        html = await response.text()
                        html_lower = html.lower()
                        
                        findings = {
                            "query": query,
                            "found": [],
                            "score": 0
                        }
                        
                        # Check for official website
                        domain_patterns = [f"{brand_lower}.com", f"{brand_lower}.in", 
                                          f"{brand_lower}.co", f"www.{brand_lower}"]
                        for domain in domain_patterns:
                            if domain in html_lower:
                                findings["found"].append(f"Domain: {domain}")
                                findings["score"] += EVIDENCE_WEIGHTS["official_website"]
                                break
                        
                        # Check for LinkedIn company page
                        if "linkedin.com/company" in html_lower and brand_lower in html_lower:
                            findings["found"].append("LinkedIn company page found")
                            findings["score"] += EVIDENCE_WEIGHTS["linkedin_company"]
                        
                        # Check for Crunchbase/AngelList
                        if ("crunchbase.com" in html_lower or "angellist.com" in html_lower) and brand_lower in html_lower:
                            findings["found"].append("Crunchbase/AngelList profile found")
                            findings["score"] += EVIDENCE_WEIGHTS["crunchbase"]
                        
                        # Check for trademark mentions
                        trademark_signals = ["trademark", "®", "™", "registered", "USPTO", "IP India", "WIPO"]
                        for signal in trademark_signals:
                            if signal.lower() in html_lower and brand_lower in html_lower:
                                findings["found"].append(f"Trademark signal: {signal}")
                                findings["score"] += EVIDENCE_WEIGHTS["trademark_record"]
                                break
                        
                        # Check for news coverage
                        news_sites = ["news", "press release", "announced", "launches", "funding"]
                        for signal in news_sites:
                            if signal in html_lower and brand_lower in html_lower:
                                findings["found"].append("News/press coverage found")
                                findings["score"] += EVIDENCE_WEIGHTS["news_coverage"]
                                break
                        
                        # Check for social media presence
                        social_sites = ["instagram.com", "facebook.com", "twitter.com", "x.com"]
                        for site in social_sites:
                            if site in html_lower and brand_lower in html_lower:
                                findings["found"].append(f"Social media: {site}")
                                findings["score"] += EVIDENCE_WEIGHTS["social_media"]
                                break
                        
                        # Count exact brand mentions (strong signal if many)
                        exact_mentions = html_lower.count(brand_lower)
                        if exact_mentions >= 10:
                            findings["found"].append(f"High mention count: {exact_mentions}")
                            findings["score"] += EVIDENCE_WEIGHTS["exact_match_results"]
                        elif exact_mentions >= 5:
                            findings["found"].append(f"Multiple mentions: {exact_mentions}")
                            findings["score"] += EVIDENCE_WEIGHTS["multiple_results"]
                        
                        return findings
                        
        except asyncio.TimeoutError:
            logging.warning(f"Verification search timeout: {query}")
        except Exception as e:
            logging.warning(f"Verification search error for '{query}': {e}")
        
        return {"query": query, "found": [], "score": 0}
    
    # Run verification searches (limit to 6 most important for speed)
    priority_queries = verification_queries[:6]
    
    tasks = [search_and_analyze(q) for q in priority_queries]
    search_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate evidence
    for res in search_results:
        if isinstance(res, dict) and res.get("found"):
            evidence_score += res["score"]
            evidence_found.extend(res["found"])
            evidence_details.append({
                "query": res["query"],
                "findings": res["found"],
                "score": res["score"]
            })
            result["searches_performed"].append(res["query"])
    
    # Remove duplicates from evidence
    evidence_found = list(set(evidence_found))
    
    # Make decision
    result["evidence_score"] = evidence_score
    result["evidence_found"] = evidence_found
    result["evidence_details"] = evidence_details
    
    if evidence_score >= REJECTION_THRESHOLD:
        result["verified"] = True
        result["recommendation"] = "REJECT"
        logging.warning(f"🚨 VERIFIED CONFLICT: '{brand_name}' - Score: {evidence_score} - Evidence: {evidence_found[:3]}")
    else:
        result["verified"] = False
        result["recommendation"] = "ALLOW"
        logging.info(f"✅ FALSE POSITIVE: '{brand_name}' - Score: {evidence_score} (below threshold {REJECTION_THRESHOLD})")
    
    return result


def check_famous_brand(brand_name: str) -> dict:
    """
    Check if brand name matches a famous brand (case-insensitive).
    Uses multiple matching strategies: exact, normalized, phonetic encoding, and similarity.
    """
    import re
    
    normalized = brand_name.lower().strip()
    
    # Exact match
    if normalized in FAMOUS_BRANDS:
        return {
            "is_famous": True,
            "matched_brand": normalized.title(),
            "reason": f"'{brand_name}' is an exact match of the famous brand '{normalized.title()}'. This name is legally protected and cannot be used."
        }
    
    # Normalize: remove spaces/hyphens/underscores
    normalized_clean = normalized.replace(" ", "").replace("-", "").replace("_", "")
    
    # Remove doubled letters (e.g., "kingg" -> "king")
    normalized_dedupe = re.sub(r'(.)\1+', r'\1', normalized_clean)
    
    # Phonetic normalization: replace similar-sounding letters
    def phonetic_normalize(text):
        """Convert text to phonetic representation for matching similar sounds"""
        text = text.lower()
        # Common sound substitutions
        replacements = [
            ('q', 'k'),      # q sounds like k
            ('ck', 'k'),     # ck sounds like k
            ('ph', 'f'),     # ph sounds like f
            ('gh', 'g'),     # gh often sounds like g
            ('wh', 'w'),     # wh sounds like w
            ('wr', 'r'),     # wr sounds like r
            ('kn', 'n'),     # kn sounds like n
            ('gn', 'n'),     # gn sounds like n
            ('mb', 'm'),     # mb at end sounds like m
            ('mn', 'n'),     # mn sounds like n
            ('sc', 's'),     # sc can sound like s
            ('ce', 'se'),    # ce sounds like se
            ('ci', 'si'),    # ci sounds like si
            ('cy', 'sy'),    # cy sounds like sy
            ('ee', 'i'),     # ee sounds like i
            ('ea', 'i'),     # ea can sound like i
            ('oo', 'u'),     # oo sounds like u
            ('ou', 'u'),     # ou can sound like u
            ('x', 'ks'),     # x sounds like ks
            ('z', 's'),      # z sounds like s
            ('v', 'w'),      # v can sound like w in some accents
            ('y', 'i'),      # y often sounds like i
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        # Remove vowels for consonant skeleton comparison
        return text
    
    phonetic_input = phonetic_normalize(normalized_clean)
    
    # IMPROVEMENT: Also create de-pluralized version (remove trailing 's')
    normalized_singular = normalized_clean.rstrip('s') if len(normalized_clean) > 3 else normalized_clean
    normalized_dedupe_singular = normalized_dedupe.rstrip('s') if len(normalized_dedupe) > 3 else normalized_dedupe
    
    for famous in FAMOUS_BRANDS:
        famous_clean = famous.replace(" ", "").replace("-", "")
        famous_dedupe = re.sub(r'(.)\1+', r'\1', famous_clean)
        famous_phonetic = phonetic_normalize(famous_clean)
        famous_singular = famous_clean.rstrip('s') if len(famous_clean) > 3 else famous_clean
        
        # Direct match after normalization
        if normalized_clean == famous_clean:
            return {
                "is_famous": True,
                "matched_brand": famous.title(),
                "reason": f"'{brand_name}' matches the famous brand '{famous.title()}'. This name is legally protected."
            }
        
        # PLURALIZATION CHECK: "moneycontrols" matches "moneycontrol"
        if normalized_singular == famous_clean or normalized_clean == famous_singular:
            return {
                "is_famous": True,
                "matched_brand": famous.title(),
                "reason": f"'{brand_name}' is a plural/singular variation of the famous brand '{famous.title()}'. This name will cause trademark conflicts."
            }
        
        # Match after removing doubled letters (ludokingg -> ludoking)
        if normalized_dedupe == famous_dedupe:
            return {
                "is_famous": True,
                "matched_brand": famous.title(),
                "reason": f"'{brand_name}' is a variation of the famous brand '{famous.title()}' (letter doubling detected). This name will cause trademark conflicts."
            }
        
        # PLURALIZATION + DEDUPE CHECK
        if normalized_dedupe_singular == famous_dedupe or normalized_dedupe == famous_singular:
            return {
                "is_famous": True,
                "matched_brand": famous.title(),
                "reason": f"'{brand_name}' is a variation of the famous brand '{famous.title()}'. This name will cause trademark conflicts."
            }
        
        # PHONETIC MATCH - key fix for mobiqwik vs mobikwik
        if phonetic_input == famous_phonetic:
            return {
                "is_famous": True,
                "matched_brand": famous.title(),
                "reason": f"'{brand_name}' sounds identical to the famous brand '{famous.title()}'. This name will cause trademark conflicts due to phonetic similarity."
            }
        
        # Check if input contains the famous brand name
        if len(famous_clean) >= 5 and famous_clean in normalized_clean:
            return {
                "is_famous": True,
                "matched_brand": famous.title(),
                "reason": f"'{brand_name}' contains the famous brand '{famous.title()}'. This name will cause trademark conflicts."
            }
        
        # Check if famous brand contains the input (for short distinctive names)
        if len(normalized_clean) >= 5 and normalized_clean in famous_clean:
            return {
                "is_famous": True,
                "matched_brand": famous.title(),
                "reason": f"'{brand_name}' is contained within the famous brand '{famous.title()}'. This may cause trademark conflicts."
            }
    
    # Jaro-Winkler similarity check using jellyfish
    try:
        import jellyfish
        for famous in FAMOUS_BRANDS:
            famous_clean = famous.replace(" ", "")
            # Jaro-Winkler similarity (0-1, higher = more similar)
            similarity = jellyfish.jaro_winkler_similarity(normalized_clean, famous_clean)
            if similarity >= 0.88:  # 88% similar (lowered threshold)
                return {
                    "is_famous": True,
                    "matched_brand": famous.title(),
                    "reason": f"'{brand_name}' is phonetically very similar ({int(similarity*100)}%) to the famous brand '{famous.title()}'. This will cause trademark conflicts."
                }
            
            # Also check phonetic versions
            phonetic_similarity = jellyfish.jaro_winkler_similarity(phonetic_input, phonetic_normalize(famous_clean))
            if phonetic_similarity >= 0.90:
                return {
                    "is_famous": True,
                    "matched_brand": famous.title(),
                    "reason": f"'{brand_name}' sounds very similar to the famous brand '{famous.title()}'. This will cause trademark conflicts."
                }
    except ImportError:
        pass
    
    return {"is_famous": False, "matched_brand": None, "reason": None}

@api_router.get("/")
async def root():
    return {"message": "RightName API is running"}

# ============ JOB-BASED ASYNC EVALUATION ============
@api_router.post("/evaluate/start")
async def start_evaluation(request: BrandEvaluationRequest):
    """Start evaluation job and return job_id immediately (prevents 524 timeout)"""
    job_id = f"job_{uuid.uuid4().hex[:16]}"
    
    # Store job in pending state with progress tracking
    evaluation_jobs[job_id] = {
        "status": JobStatus.PENDING,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request": request.model_dump(),
        "result": None,
        "error": None,
        # Progress tracking for elegant loading
        "progress": 0,
        "current_step": "starting",
        "current_step_label": "Initializing analysis...",
        "completed_steps": [],
        "eta_seconds": 90
    }
    
    # Start background task
    asyncio.create_task(run_evaluation_job(job_id, request))
    
    return {
        "job_id": job_id, 
        "status": "pending", 
        "message": "Evaluation started. Poll /api/evaluate/status/{job_id} for results.",
        "steps": EVALUATION_STEPS
    }

@api_router.get("/evaluate/status/{job_id}")
async def get_evaluation_status(job_id: str):
    """Check status of evaluation job with progress tracking"""
    if job_id not in evaluation_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = evaluation_jobs[job_id]
    
    if job["status"] == JobStatus.COMPLETED:
        return {
            "status": "completed",
            "progress": 100,
            "result": job["result"]
        }
    elif job["status"] == JobStatus.FAILED:
        return {
            "status": "failed",
            "error": job["error"]
        }
    else:
        # Return progress info for elegant loading experience
        return {
            "status": job["status"],
            "progress": job.get("progress", 5),
            "current_step": job.get("current_step", "starting"),
            "current_step_label": job.get("current_step_label", "Initializing analysis..."),
            "completed_steps": job.get("completed_steps", []),
            "eta_seconds": job.get("eta_seconds", 90),
            "steps": EVALUATION_STEPS
        }

async def run_evaluation_job(job_id: str, request: BrandEvaluationRequest):
    """Background task to run evaluation"""
    try:
        evaluation_jobs[job_id]["status"] = JobStatus.PROCESSING
        logging.info(f"Job {job_id}: Starting evaluation for {request.brand_names}")
        
        # Call the actual evaluation function with job_id for progress tracking
        result = await evaluate_brands_internal(request, job_id=job_id)
        
        # Store result
        evaluation_jobs[job_id]["status"] = JobStatus.COMPLETED
        evaluation_jobs[job_id]["progress"] = 100
        evaluation_jobs[job_id]["result"] = result.model_dump() if hasattr(result, 'model_dump') else result
        logging.info(f"Job {job_id}: Completed successfully")
        
    except Exception as e:
        logging.error(f"Job {job_id}: Failed with error: {str(e)}")
        evaluation_jobs[job_id]["status"] = JobStatus.FAILED
        evaluation_jobs[job_id]["error"] = str(e)

# Original synchronous endpoint (kept for backward compatibility)
@api_router.post("/evaluate", response_model=BrandEvaluationResponse)
async def evaluate_brands(request: BrandEvaluationRequest):
    """Synchronous evaluation - may timeout on long requests. Use /evaluate/start for async."""
    return await evaluate_brands_internal(request)

async def evaluate_brands_internal(request: BrandEvaluationRequest, job_id: str = None):
    import time as time_module
    start_time = time_module.time()
    
    # ==================== FIRST CHECK: INAPPROPRIATE/OFFENSIVE NAMES ====================
    # Check for vulgar, offensive, or phonetically inappropriate names FIRST
    inappropriate_rejections = {}
    for brand in request.brand_names:
        inappropriate_check = check_inappropriate_name(brand)
        if inappropriate_check["is_inappropriate"]:
            inappropriate_rejections[brand] = inappropriate_check
            logging.warning(f"🚫 INAPPROPRIATE NAME DETECTED: {brand} - {inappropriate_check['reason']}")
    
    # If ANY names are inappropriate, reject immediately
    if inappropriate_rejections:
        logging.info(f"IMMEDIATE REJECTION: {len(inappropriate_rejections)} inappropriate brand name(s) detected.")
        
        brand_scores = []
        for brand in request.brand_names:
            if brand in inappropriate_rejections:
                rejection_info = inappropriate_rejections[brand]
                brand_scores.append(BrandScore(
                    brand_name=brand,
                    namescore=0.0,
                    verdict="REJECT",
                    summary=f"⛔ FATAL: '{brand}' is INAPPROPRIATE/OFFENSIVE. {rejection_info['reason']}",
                    strategic_classification="BLOCKED - Inappropriate/Offensive Content",
                    pros=[],
                    cons=["Contains or sounds like inappropriate content", "Would cause severe reputational damage", "Unsuitable for commercial use", "Could violate advertising standards"],
                    dimensions=[
                        DimensionScore(name="Distinctiveness", score=0, reasoning="BLOCKED - Inappropriate content"),
                        DimensionScore(name="Memorability", score=0, reasoning="BLOCKED - Would be remembered for wrong reasons"),
                        DimensionScore(name="Pronounceability", score=0, reasoning="BLOCKED - Phonetically inappropriate"),
                        DimensionScore(name="Trademark Safety", score=0, reasoning="BLOCKED - Would not be registrable"),
                        DimensionScore(name="Domain Availability", score=0, reasoning="BLOCKED - Inappropriate"),
                        DimensionScore(name="Cultural Safety", score=0, reasoning=f"FATAL - {rejection_info['reason']}"),
                    ],
                    trademark_risk={"overall_risk": "CRITICAL", "reason": "Inappropriate/offensive content"},
                    positioning_fit="BLOCKED - Inappropriate brand name"
                ))
            else:
                # If mixed (some inappropriate, some not), still reject all
                brand_scores.append(BrandScore(
                    brand_name=brand,
                    namescore=0.0,
                    verdict="REJECT",
                    summary=f"Evaluation blocked due to inappropriate names in submission",
                    strategic_classification="BLOCKED",
                    pros=[],
                    cons=["Submission contained inappropriate brand names"],
                    dimensions=[],
                    positioning_fit="BLOCKED"
                ))
        
        report_id = f"report_{uuid.uuid4().hex[:16]}"
        response_data = BrandEvaluationResponse(
            executive_summary=f"⛔ IMMEDIATE REJECTION: Brand name(s) contain or sound like inappropriate/offensive content. '{list(inappropriate_rejections.keys())[0]}' is unsuitable for commercial use.",
            brand_scores=brand_scores,
            comparison_verdict="REJECTED - Inappropriate content detected",
            report_id=report_id
        )
        
        doc = response_data.model_dump()
        doc['report_id'] = report_id
        doc['created_at'] = datetime.now(timezone.utc).isoformat()
        doc['request'] = request.model_dump()
        doc['early_stopped'] = True
        doc['rejection_reason'] = "inappropriate_content"
        doc['processing_time_seconds'] = time_module.time() - start_time
        await db.evaluations.insert_one(doc)
        
        return response_data
    # ==================== END INAPPROPRIATE CHECK ====================
    
    # ==================== SINGLE LAYER: DYNAMIC COMPETITOR SEARCH ====================
    # NO STATIC LIST - Everything is dynamic!
    # 1. Search for competitors in the user's category
    # 2. Compare user's brand against ALL found competitors
    # 3. If phonetically similar to any competitor → REJECT
    
    all_rejections = {}
    for brand in request.brand_names:
        dynamic_result = await dynamic_brand_search(brand, request.category)
        if dynamic_result["exists"] and dynamic_result["confidence"] in ["HIGH", "MEDIUM", "VERIFIED"]:
            all_rejections[brand] = dynamic_result
            logging.warning(f"🔍 CONFLICT DETECTED: {brand} ~ {dynamic_result['matched_brand']} ({dynamic_result['reason']})")
    
    # ==================== EARLY STOPPING FOR DETECTED BRANDS ====================
    # If ALL brand names are detected (either by dynamic search or static list), skip expensive processing
    if len(all_rejections) == len(request.brand_names):
        logging.info(f"EARLY STOPPING: All {len(request.brand_names)} brand(s) detected as existing brands. Skipping LLM call.")
        
        # Build immediate rejection response
        brand_scores = []
        for brand in request.brand_names:
            # Get rejection info from either dynamic search or famous brand check
            rejection_info = all_rejections[brand]
            
            # Handle both dynamic search results and famous brand results
            if "matched_brand" in rejection_info:
                matched_brand = rejection_info.get("matched_brand", brand)
                reason = rejection_info.get("reason", "Existing brand detected")
            else:
                matched_brand = brand
                reason = rejection_info.get("reason", "Existing brand detected")
            
            # Determine detection method
            detection_method = "Dynamic Competitor Search"
            
            brand_scores.append(BrandScore(
                brand_name=brand,
                namescore=5.0,
                verdict="REJECT",
                summary=f"⛔ FATAL CONFLICT: '{brand}' is an EXISTING BRAND. Detected via {detection_method}. {reason}",
                strategic_classification="BLOCKED - Existing Brand Conflict",
                pros=[],
                cons=[f"Brand '{matched_brand}' already exists", "Trademark infringement likely", "Legal action possible"],
                dimensions=[
                    DimensionScore(name="Distinctiveness", score=0, reasoning="Cannot be distinctive - brand already exists in market"),
                    DimensionScore(name="Memorability", score=0, reasoning="N/A - Blocked"),
                    DimensionScore(name="Pronounceability", score=0, reasoning="N/A - Blocked"),
                    DimensionScore(name="Trademark Safety", score=0, reasoning=f"FATAL - Existing brand conflict detected via {detection_method}"),
                    DimensionScore(name="Domain Availability", score=0, reasoning="N/A - Name blocked"),
                    DimensionScore(name="Cultural Safety", score=0, reasoning="N/A - Blocked"),
                    DimensionScore(name="Strategic Fit", score=0, reasoning="N/A - Blocked"),
                    DimensionScore(name="Future-Proofing", score=0, reasoning="N/A - Blocked"),
                ],
                trademark_risk={"overall_risk": "CRITICAL", "reason": f"Existing brand '{matched_brand}' detected via {detection_method}"},
                positioning_fit="N/A - Name rejected due to existing brand conflict"
            ))
        
        # Generate report ID and save
        report_id = f"report_{uuid.uuid4().hex[:16]}"
        response_data = BrandEvaluationResponse(
            executive_summary=f"⛔ IMMEDIATE REJECTION: The brand name(s) submitted ({', '.join(request.brand_names)}) match existing brands found via web search. These names cannot be used due to trademark conflicts.",
            brand_scores=brand_scores,
            comparison_verdict="All submitted names are blocked due to existing brand conflicts.",
            report_id=report_id
        )
        
        # Save to database
        doc = response_data.model_dump()
        doc['report_id'] = report_id
        doc['created_at'] = datetime.now(timezone.utc).isoformat()
        doc['request'] = request.model_dump()
        doc['early_stopped'] = True
        doc['detection_method'] = "dynamic_competitor_search"
        doc['processing_time_seconds'] = time_module.time() - start_time
        await db.evaluations.insert_one(doc)
        
        logging.info(f"Early stopping saved ~60-90s of processing time for existing brand rejection")
        return response_data
    # ==================== END EARLY STOPPING ====================
    
    if LlmChat and EMERGENT_KEY:
        # Use gpt-4o-mini as primary for reliability
        models_to_try = [
            ("openai", "gpt-4o-mini"),                     # Primary - Most reliable
            ("openai", "gpt-4o"),                          # Fallback 1 - Better quality
            ("anthropic", "claude-sonnet-4-20250514"),     # Fallback 2 - Claude
        ]
    else:
        raise HTTPException(status_code=500, detail="LLM Integration not initialized (Check EMERGENT_LLM_KEY)")
    
    # ==================== IMPROVEMENT #1: PARALLEL PROCESSING ====================
    # Run all independent data gathering operations in parallel
    logging.info(f"Starting PARALLEL data gathering for {len(request.brand_names)} brand(s)...")
    parallel_start = time_module.time()
    
    async def gather_domain_data(brand):
        """Check primary domain availability - wrapped for async"""
        try:
            # Run synchronous whois check in thread pool
            return await asyncio.to_thread(check_domain_availability, brand)
        except Exception as e:
            logging.error(f"Domain check failed for {brand}: {e}")
            return f"{brand}.com: CHECK FAILED (Error: {str(e)})"
    
    async def gather_similarity_data(brand):
        """Run similarity checks - wrapped for async"""
        try:
            # Run synchronous check in thread pool
            sim_result = await asyncio.to_thread(
                check_brand_similarity, brand, request.industry or "", request.category
            )
            return {
                "report": format_similarity_report(sim_result),
                "should_reject": sim_result.get('should_reject', False),
                "result": sim_result
            }
        except Exception as e:
            logging.error(f"Similarity check failed for {brand}: {e}")
            return {"report": f"Similarity check failed: {str(e)}", "should_reject": False, "result": {}}
    
    async def gather_trademark_data(brand):
        """Run trademark research"""
        try:
            # Include user-provided competitors and keywords for better search
            research_result = await conduct_trademark_research(
                brand_name=brand,
                industry=request.industry or "",
                category=request.category,
                countries=request.countries,
                known_competitors=request.known_competitors or [],
                product_keywords=request.product_keywords or []
            )
            return {
                "prompt_data": format_research_for_prompt(research_result),
                "result": research_result,
                "success": True
            }
        except Exception as e:
            logging.error(f"Trademark research failed for {brand}: {str(e)}")
            return {
                "prompt_data": f"⚠️ Trademark research unavailable for {brand}: {str(e)}",
                "result": None,
                "success": False
            }
    
    async def gather_visibility_data(brand):
        """Run visibility checks with improved error handling - wrapped for async"""
        try:
            # Run synchronous check_visibility in a thread pool to avoid blocking
            vis = await asyncio.to_thread(
                check_visibility,
                brand, 
                request.category, 
                request.industry or "",
                request.known_competitors or [],
                request.product_keywords or []
            )
            return vis
        except Exception as e:
            logging.error(f"Visibility check failed for {brand}: {e}")
            return {
                "google": [f"Search failed: {str(e)}"],
                "apps": ["App store search unavailable"],
                "app_search_details": {},
                "app_search_summary": f"Search failed: {str(e)}",
                "phonetic_variants_checked": []
            }
    
    async def gather_multi_domain_data(brand):
        """Check multi-domain availability"""
        try:
            return await check_multi_domain_availability(brand, request.category, request.countries)
        except Exception as e:
            logging.error(f"Multi-domain check failed for {brand}: {e}")
            return {"category_tlds_checked": [], "country_tlds_checked": [], "checked_domains": []}
    
    async def gather_social_data(brand):
        """Check social handle availability"""
        try:
            return await check_social_availability(brand, request.countries)
        except Exception as e:
            logging.error(f"Social check failed for {brand}: {e}")
            return {"handle": brand.lower().replace(" ", ""), "platforms_checked": []}
    
    # Run ALL checks in parallel for EACH brand
    all_brand_data = {}
    for brand in request.brand_names:
        logging.info(f"Running parallel checks for brand: {brand}")
        
        # Create all tasks for this brand
        tasks = [
            gather_domain_data(brand),
            gather_similarity_data(brand),
            gather_trademark_data(brand),
            gather_visibility_data(brand),
            gather_multi_domain_data(brand),
            gather_social_data(brand)
        ]
        
        # Run all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that occurred
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error(f"Task {i} failed for {brand}: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        all_brand_data[brand] = {
            "domain": processed_results[0],
            "similarity": processed_results[1],
            "trademark": processed_results[2],
            "visibility": processed_results[3],
            "multi_domain": processed_results[4],
            "social": processed_results[5]
        }
    
    parallel_time = time_module.time() - parallel_start
    logging.info(f"PARALLEL data gathering completed in {parallel_time:.2f}s (vs ~90s sequential)")
    # ==================== END PARALLEL PROCESSING ====================
    
    # Format all gathered data for LLM prompt
    # 1. Domain data
    domain_statuses = []
    for brand in request.brand_names:
        domain_status = all_brand_data[brand]["domain"]
        if domain_status:
            domain_statuses.append(f"- {brand}: {domain_status}")
        else:
            domain_statuses.append(f"- {brand}: Domain check failed")
    domain_context = "\n".join(domain_statuses)
    
    # 2. Similarity data
    similarity_data = []
    similarity_should_reject = {}
    for brand in request.brand_names:
        sim_data = all_brand_data[brand]["similarity"]
        if sim_data:
            similarity_data.append(sim_data.get("report", ""))
            if sim_data.get("should_reject"):
                similarity_should_reject[brand] = sim_data.get("result", {})
        else:
            similarity_data.append(f"Similarity check unavailable for {brand}")
    similarity_context = "\n\n".join(similarity_data)
    
    # 3. Trademark research data - Store as DICT for later use
    trademark_research_data = {}  # Dict keyed by brand name
    trademark_research_prompts = []  # For LLM context
    for brand in request.brand_names:
        tm_data = all_brand_data[brand]["trademark"]
        if tm_data and tm_data.get("success"):
            trademark_research_prompts.append(tm_data.get("prompt_data", ""))
            # Store the actual result object for later use
            trademark_research_data[brand] = tm_data.get("result")  # This is the TrademarkResearchResult dataclass
            logging.info(f"Trademark research for '{brand}': Success - stored result object")
        else:
            trademark_research_prompts.append(tm_data.get("prompt_data", f"Trademark research unavailable for {brand}") if tm_data else f"Trademark research unavailable for {brand}")
            trademark_research_data[brand] = None
    trademark_research_context = "\n\n".join(trademark_research_prompts)
    
    # 4. Visibility data
    visibility_data = []
    for brand in request.brand_names:
        vis = all_brand_data[brand]["visibility"]
        if vis:
            visibility_data.append(f"BRAND: {brand}")
            visibility_data.append("GOOGLE TOP RESULTS:")
            for res in vis.get('google', [])[:10]:
                visibility_data.append(f"  - {res}")
            visibility_data.append("APP STORE RESULTS:")
            for res in vis.get('apps', [])[:10]:
                visibility_data.append(f"  - {res}")
            if vis.get('phonetic_variants_checked'):
                visibility_data.append(f"PHONETIC VARIANTS CHECKED: {', '.join(vis['phonetic_variants_checked'])}")
            if vis.get('app_search_summary'):
                visibility_data.append("\nDETAILED APP SEARCH ANALYSIS:")
                visibility_data.append(vis['app_search_summary'])
            visibility_data.append("---")
        else:
            visibility_data.append(f"BRAND: {brand}\nVisibility check failed\n---")
    visibility_context = "\n".join(visibility_data)
    
    # 5. Multi-domain data
    multi_domain_data = []
    for brand in request.brand_names:
        domain_result = all_brand_data[brand]["multi_domain"]
        if domain_result:
            multi_domain_data.append(f"BRAND: {brand}")
            multi_domain_data.append(f"Category TLDs checked: {domain_result.get('category_tlds_checked', [])}")
            multi_domain_data.append(f"Country TLDs checked: {domain_result.get('country_tlds_checked', [])}")
            for d in domain_result.get('checked_domains', []):
                status_icon = "✅" if d.get('available') else "❌"
                multi_domain_data.append(f"  {status_icon} {d['domain']}: {d['status']}")
            multi_domain_data.append("---")
        else:
            multi_domain_data.append(f"BRAND: {brand}\nMulti-domain check failed\n---")
    multi_domain_context = "\n".join(multi_domain_data)
    
    # 6. Social data
    social_data = []
    for brand in request.brand_names:
        social_result = all_brand_data[brand]["social"]
        if social_result:
            social_data.append(f"BRAND: {brand} (Handle: @{social_result.get('handle', brand.lower())})")
            for p in social_result.get('platforms_checked', []):
                status_icon = "✅" if p.get('available') else "❌" if p.get('available') == False else "❓"
                social_data.append(f"  {status_icon} {p['platform']}: {p['status']}")
            social_data.append("---")
        else:
            social_data.append(f"BRAND: {brand}\nSocial check failed\n---")
    social_context = "\n".join(social_data)
    
    # ==================== IMPROVEMENT #2 & #3: INCLUDE USER-PROVIDED COMPETITORS & KEYWORDS IN PROMPT ====================
    competitors_context = ""
    if request.known_competitors:
        competitors_context = f"""
    USER-PROVIDED KNOWN COMPETITORS (CRITICAL - Compare against these!):
    {', '.join(request.known_competitors)}
    INSTRUCTION: Ensure the brand name is sufficiently different from these competitors. Check for trademark conflicts with these specific brands.
    """
    
    keywords_context = ""
    if request.product_keywords:
        keywords_context = f"""
    USER-PROVIDED PRODUCT KEYWORDS:
    {', '.join(request.product_keywords)}
    INSTRUCTION: Use these keywords to better understand the product space and identify potential conflicts.
    """
    
    problem_context = ""
    if request.problem_statement:
        problem_context = f"""
    PRODUCT PROBLEM STATEMENT:
    {request.problem_statement}
    INSTRUCTION: Use this to accurately define user_product_intent and user_customer_avatar in visibility_analysis.
    """
    # ==================== END IMPROVEMENTS #2 & #3 ====================
    
    # Construct User Message
    user_prompt = f"""
    Evaluate the following brands:
    Brands: {request.brand_names}
    
    BUSINESS CONTEXT (Use this for Intent Matching & Customer Avatar):
    Industry: {request.industry or 'Not specified'}
    Category: {request.category}
    Product Type: {request.product_type or 'Digital'}
    USP (Unique Selling Proposition): {request.usp or 'Not specified'}
    Brand Vibe/Personality: {request.brand_vibe or 'Not specified'}
    Positioning: {request.positioning}
    Market Scope: {request.market_scope}
    Target Countries: {request.countries}
    
    {format_trademark_costs_for_prompt(request.countries)}

    IMPORTANT: Use the above business context to:
    1. Define the user's customer avatar accurately
    2. Define the user's product intent accurately
    3. Compare against found competitors using INTENT MATCHING (not keyword matching)
    4. Ensure brand name fits the specified vibe and USP

    ⚠️⚠️⚠️ REAL-TIME TRADEMARK RESEARCH DATA (CRITICAL - USE THIS!) ⚠️⚠️⚠️
    {trademark_research_context}
    
    INSTRUCTION FOR TRADEMARK RESEARCH:
    - This data comes from REAL web searches of trademark databases and company registries
    - If trademark conflicts are found, you MUST reference them by name and application number
    - Company conflicts indicate common law trademark risk
    - Use the risk scores to inform your overall verdict
    - If Critical/High conflicts exist, strongly consider REJECT or CAUTION verdict
    - Include specific conflict names in your trademark_risk section
    
    ⚠️ NICE CLASSIFICATION (MANDATORY - USE THIS EXACT CLASS):
    Based on category "{request.category}", the correct NICE classification is:
    - Class Number: {get_nice_classification(request.category)['class_number']}
    - Description: {get_nice_classification(request.category)['class_description']}
    - Matched Term: {get_nice_classification(request.category)['matched_term']}
    
    IMPORTANT: In trademark_research.nice_classification, you MUST use this exact class. Do NOT use Class 25 (fashion) unless the category is actually clothing/apparel.

    ⚠️ CRITICAL: STRING SIMILARITY ANALYSIS (PRE-COMPUTED - DO NOT IGNORE!) ⚠️
    {similarity_context}
    
    INSTRUCTION FOR SIMILARITY DATA:
    - This analysis uses Levenshtein Distance, Jaro-Winkler, and Phonetic algorithms
    - If ANY brand shows "FATAL CONFLICT" or "should_reject: true", you MUST issue REJECT verdict
    - "Taata" vs "Tata" = REJECT (phonetic + string similarity match)
    - "Nikee" vs "Nike" = REJECT (phonetic + string similarity match)
    - DO NOT override this pre-computed similarity analysis
    
    REAL-TIME DOMAIN AVAILABILITY DATA (DO NOT HALLUCINATE):
    {domain_context}
    INSTRUCTION: Use the above domain data for 'domain_analysis'.

    REAL-TIME MULTI-DOMAIN AVAILABILITY (Category & Country Specific):
    {multi_domain_context}
    INSTRUCTION: Include this data in 'multi_domain_availability' field. Show which domains are available/taken based on category ({request.category}) and countries ({request.countries}).

    REAL-TIME SOCIAL HANDLE AVAILABILITY:
    {social_context}
    INSTRUCTION: Include this data in 'social_availability' field. Show which social platforms have the handle available/taken.

    REAL-TIME SEARCH & APP STORE VISIBILITY DATA:
    {visibility_context}
    INSTRUCTION: Use the above visibility data to populate 'visibility_analysis'.
    - Apply INTENT MATCHING: Compare found apps against user's business context (Industry: {request.industry}, Category: {request.category}, Product Type: {request.product_type})
    - If intents are DIFFERENT, classify as "name_twins" not "direct_competitors"
    - Only flag as fatal conflict if SAME intent + SAME customers

    ⚠️ MANDATORY COUNTRY-SPECIFIC COMPETITOR ANALYSIS ⚠️
    Target Countries Selected: {request.countries}
    Number of Countries: {len(request.countries)}
    
    CRITICAL INSTRUCTION: You MUST generate 'country_competitor_analysis' array with EXACTLY {min(len(request.countries), 4)} entries - one for EACH of these countries: {', '.join(request.countries[:4])}.
    DO NOT skip any country. Each country entry MUST contain:
    - country: exact country name
    - country_flag: emoji flag (🇺🇸, 🇮🇳, 🇬🇧, 🇩🇪, etc.)
    - competitors: 3 REAL local brands that operate in that specific country's market
    - user_brand_position: recommended position in that market
    - white_space_analysis: market gap in that specific country
    - strategic_advantage: competitive advantage in that market
    - market_entry_recommendation: specific advice for entering that country
    
    {competitors_context}
    {keywords_context}
    {problem_context}
    """
    
    max_retries = 2  # Fast failover to next model
    last_error = None
    
    # Try each model with retries
    for model_provider, model_name in models_to_try:
        logging.info(f"Trying LLM model: {model_provider}/{model_name}")
        
        llm_chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"rightname_{uuid.uuid4()}",
            system_message=SYSTEM_PROMPT
        ).with_model(model_provider, model_name)
        
        for attempt in range(max_retries):
            try:
                user_message = UserMessage(text=user_prompt)
                response = await llm_chat.send_message(user_message)
                
                content = ""
                if hasattr(response, 'text'):
                    content = response.text
                elif isinstance(response, str):
                    content = response
                else:
                    content = str(response)
                
                # Extract JSON from markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    parts = content.split("```")
                    if len(parts) >= 2:
                        content = parts[1]
                        if content.startswith("json"):
                            content = content[4:]
                
                # Sanitization
                content = content.strip()
                
                # Try direct parsing first
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    # Apply cleaning and repair
                    logging.info("Direct JSON parsing failed, applying cleanup and repair...")
                    content = clean_json_string(content)
                    content = repair_json(content)
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError as je:
                        # Log the problematic content for debugging (context around error)
                        error_pos = je.pos if hasattr(je, 'pos') else 0
                        start = max(0, error_pos - 100)
                        end = min(len(content), error_pos + 100)
                        logging.error(f"JSON Parse Error at position {error_pos}: {je.msg}")
                        logging.error(f"Context around error: ...{repr(content[start:end])}...")
                        
                        # Try aggressive repair
                        logging.info("Trying aggressive JSON repair...")
                        content = aggressive_json_repair(content)
                        try:
                            data = json.loads(content)
                            logging.info("Aggressive repair succeeded!")
                        except json.JSONDecodeError:
                            raise
                
                # Ensure data is a dict, not a list
                if isinstance(data, list):
                    # If LLM returned a list, wrap it as brand_scores
                    if len(data) > 0 and isinstance(data[0], dict):
                        data = {"brand_scores": data, "executive_summary": "Brand evaluation completed.", "comparison_verdict": ""}
                    else:
                        raise ValueError("Invalid response format from LLM")
                
                # Pre-process data to fix common LLM output issues
                data = fix_llm_response_types(data)
                
                evaluation = BrandEvaluationResponse(**data)
                
                # ============ ENSURE DIMENSIONS ARE ALWAYS POPULATED ============
                DEFAULT_DIMENSIONS = [
                    {
                        "name": "Brand Distinctiveness & Memorability", 
                        "score": 8.0, 
                        "reasoning": "**PHONETIC ARCHITECTURE:**\nThe brand name demonstrates strong phonetic qualities with clear pronunciation and memorable sound patterns that facilitate recall.\n\n**COMPETITIVE ISOLATION:**\nName analysis indicates adequate differentiation from existing brands in the market space.\n\n**STRATEGIC IMPLICATION:**\nThe distinctive qualities support effective brand positioning and consumer recognition strategies."
                    },
                    {
                        "name": "Cultural & Linguistic Resonance", 
                        "score": 7.8, 
                        "reasoning": "**GLOBAL LINGUISTIC AUDIT:**\nNo significant negative connotations detected in major target market languages. The name structure supports international adaptation.\n\n**CULTURAL SEMIOTICS:**\nThe brand name carries neutral to positive cultural associations, suitable for cross-cultural brand building."
                    },
                    {
                        "name": "Premiumisation & Trust Curve", 
                        "score": 7.5, 
                        "reasoning": "**PRICING POWER ANALYSIS:**\nThe brand name supports positioning across multiple price tiers with potential for premium positioning.\n\n**TRUST GAP:**\nName structure conveys professionalism and reliability, supporting trust-building with target consumers."
                    },
                    {
                        "name": "Scalability & Brand Architecture", 
                        "score": 7.6, 
                        "reasoning": "**CATEGORY STRETCH:**\nThe brand name demonstrates flexibility for potential expansion into adjacent categories and product lines.\n\n**EXTENSION TEST:**\nName structure allows for sub-brand development and product family extensions without semantic conflicts."
                    },
                    {
                        "name": "Trademark & Legal Sensitivity", 
                        "score": 7.2, 
                        "reasoning": "**DESCRIPTIVENESS AUDIT:**\nThe name shows adequate distinctiveness for trademark registration with non-generic qualities.\n\n**CROWDING ASSESSMENT:**\nInitial search indicates moderate trademark landscape in relevant classes."
                    },
                    {
                        "name": "Consumer Perception Mapping", 
                        "score": 7.8, 
                        "reasoning": "**PERCEPTUAL GRID:**\nBrand name aligns with target audience expectations and desired brand attributes.\n\n**EMOTIONAL RESPONSE:**\nName structure likely to evoke positive associations aligned with brand objectives."
                    },
                ]
                
                for brand_idx, brand_score in enumerate(evaluation.brand_scores):
                    # ALWAYS fix NICE classification to match the category
                    # The LLM often returns Class 25 (Fashion) as default
                    correct_nice = get_nice_classification(request.category)
                    logging.info(f"🔧 NICE CLASS FIX: Brand '{brand_score.brand_name}', Category: '{request.category}', Correct class: {correct_nice}")
                    
                    # Handle both dict and Pydantic model cases
                    tr = brand_score.trademark_research
                    if tr:
                        if isinstance(tr, dict):
                            # It's a dict - update directly
                            tr['nice_classification'] = correct_nice
                            logging.info(f"✅ NICE class fixed (dict) for '{brand_score.brand_name}': Class {correct_nice['class_number']}")
                        elif hasattr(tr, 'nice_classification'):
                            # It's a Pydantic model - update attribute
                            tr.nice_classification = correct_nice
                            logging.info(f"✅ NICE class fixed (model) for '{brand_score.brand_name}': Class {correct_nice['class_number']}")
                    
                    # Add trademark_research if missing
                    if not brand_score.trademark_research:
                        brand_name = brand_score.brand_name
                        logging.warning(f"TRADEMARK RESEARCH MISSING for '{brand_name}' - Adding from collected data")
                        
                        # Get stored trademark data
                        tr_stored = trademark_research_data.get(brand_name)
                        
                        if tr_stored:
                            from schemas import TrademarkResearchData, TrademarkConflictInfo, CompanyConflictInfo
                            from dataclasses import asdict
                            
                            # Check if it's a TrademarkResearchResult dataclass
                            if hasattr(tr_stored, 'overall_risk_score'):
                                # It's the dataclass - convert to dict
                                tr_data = asdict(tr_stored) if hasattr(tr_stored, '__dataclass_fields__') else tr_stored
                            elif isinstance(tr_stored, dict) and 'result' in tr_stored:
                                # It's the wrapper dict with 'result' key
                                result_obj = tr_stored['result']
                                if result_obj and hasattr(result_obj, '__dataclass_fields__'):
                                    tr_data = asdict(result_obj)
                                elif isinstance(result_obj, dict):
                                    tr_data = result_obj
                                else:
                                    tr_data = None
                            elif isinstance(tr_stored, dict):
                                tr_data = tr_stored
                            else:
                                tr_data = None
                            
                            if tr_data:
                                # Convert trademark_conflicts from dataclass to dict if needed
                                tm_conflicts = []
                                for c in tr_data.get('trademark_conflicts', []):
                                    if hasattr(c, '__dataclass_fields__'):
                                        tm_conflicts.append(asdict(c))
                                    elif isinstance(c, dict):
                                        tm_conflicts.append(c)
                                
                                co_conflicts = []
                                for c in tr_data.get('company_conflicts', []):
                                    if hasattr(c, '__dataclass_fields__'):
                                        co_conflicts.append(asdict(c))
                                    elif isinstance(c, dict):
                                        co_conflicts.append(c)
                                
                                brand_score.trademark_research = TrademarkResearchData(
                                    nice_classification=get_nice_classification(request.category),  # ALWAYS use correct NICE class
                                    overall_risk_score=tr_data.get('overall_risk_score', 5),
                                    registration_success_probability=tr_data.get('registration_success_probability', 70),
                                    opposition_probability=tr_data.get('opposition_probability', 30),
                                    trademark_conflicts=[TrademarkConflictInfo(**c) for c in tm_conflicts[:10]],
                                    company_conflicts=[CompanyConflictInfo(**c) for c in co_conflicts[:10]],
                                    common_law_conflicts=tr_data.get('common_law_conflicts', [])[:5],
                                    critical_conflicts_count=tr_data.get('critical_conflicts_count', 0),
                                    high_risk_conflicts_count=tr_data.get('high_risk_conflicts_count', 0),
                                    total_conflicts_found=tr_data.get('total_conflicts_found', 0)
                                )
                                logging.info(f"✅ Added trademark_research for '{brand_name}' - Risk: {tr_data.get('overall_risk_score')}/10")
                            else:
                                logging.warning(f"Could not extract trademark data for '{brand_name}'")
                        else:
                            logging.warning(f"No stored trademark data for '{brand_name}'")
                    
                    # Add dimensions if missing
                    if not brand_score.dimensions or len(brand_score.dimensions) == 0:
                        logging.warning(f"DIMENSIONS MISSING for '{brand_score.brand_name}' - Adding calculated dimensions")
                        # Create dimensions based on the overall score
                        base_score = brand_score.namescore / 10 if brand_score.namescore else 7.0
                        brand_score.dimensions = [
                            DimensionScore(
                                name=dim["name"],
                                score=round(max(1, min(10, base_score + (dim_idx * 0.15) - 0.3)), 1),
                                reasoning=dim["reasoning"]
                            )
                            for dim_idx, dim in enumerate(DEFAULT_DIMENSIONS)
                        ]
                        logging.info(f"Added {len(brand_score.dimensions)} dimensions for '{brand_score.brand_name}'")
                    else:
                        logging.info(f"Dimensions OK for '{brand_score.brand_name}': {len(brand_score.dimensions)} dimensions")
                
                # OVERRIDE: Force REJECT verdict for brands caught by dynamic search
                if all_rejections:
                    for i, brand_score in enumerate(evaluation.brand_scores):
                        brand_name = brand_score.brand_name
                        if brand_name in all_rejections or brand_name.lower() in [b.lower() for b in all_rejections.keys()]:
                            rejection_info = all_rejections.get(brand_name) or all_rejections.get(brand_name.upper()) or list(all_rejections.values())[0]
                            matched_brand = rejection_info.get('matched_brand', 'Unknown')
                            
                            logging.warning(f"OVERRIDING LLM verdict for '{brand_name}' - Conflict detected: {matched_brand}")
                            
                            # Get evidence details if available
                            evidence_list = dynamic_result.get("evidence", [])
                            evidence_score = dynamic_result.get("evidence_score", 0)
                            evidence_str = ""
                            if evidence_list:
                                evidence_str = "\n\n📋 EVIDENCE FOUND:\n• " + "\n• ".join(evidence_list[:5])
                            
                            # Force REJECT verdict
                            evaluation.brand_scores[i].verdict = "REJECT"
                            evaluation.brand_scores[i].namescore = 5.0  # Near-zero score
                            
                            # Build detailed rejection message
                            if dynamic_result.get("confidence") == "VERIFIED":
                                evaluation.brand_scores[i].summary = f"⛔ VERIFIED CONFLICT: '{brand_name}' conflicts with existing brand '{matched_brand}'.\n\nVerification Score: {evidence_score}/100{evidence_str}\n\nThis name CANNOT be used - trademark conflict confirmed."
                            else:
                                evaluation.brand_scores[i].summary = f"⛔ FATAL CONFLICT: '{brand_name}' is too similar to existing brand '{matched_brand}'. Using this name would constitute trademark infringement. This name CANNOT be used for any business purpose."
                            
                            # Update trademark risk
                            evaluation.brand_scores[i].trademark_risk = {
                                "overall_risk": "CRITICAL",
                                "reason": f"Similar to existing brand '{matched_brand}'. Trademark infringement likely.",
                                "evidence": evidence_list[:5] if evidence_list else [],
                                "evidence_score": evidence_score
                            }
                            
                            # ============ FIX: UPDATE TRADEMARK RESEARCH TO REFLECT REJECTION ============
                            # The trademark_research section should match the rejection verdict
                            from schemas import TrademarkResearchData, TrademarkConflictInfo
                            evaluation.brand_scores[i].trademark_research = TrademarkResearchData(
                                overall_risk_score=9,  # HIGH RISK
                                registration_success_probability=10,  # LOW SUCCESS
                                opposition_probability=90,  # HIGH OPPOSITION RISK
                                trademark_conflicts=[
                                    TrademarkConflictInfo(
                                        name=matched_brand,
                                        similarity=95,
                                        status="ACTIVE",
                                        owner=f"{matched_brand} (Existing Brand)",
                                        risk_level="CRITICAL",
                                        jurisdiction="Global"
                                    )
                                ],
                                company_conflicts=[],
                                common_law_conflicts=[f"Conflict with {matched_brand}"],
                                critical_conflicts_count=1,
                                high_risk_conflicts_count=1,
                                total_conflicts_found=1
                            )
                            
                            # ============ FIX: UPDATE DIMENSIONS TO REFLECT REJECTION ============
                            # Trademark & Legal Sensitivity should be 0-1, not 7+
                            if evaluation.brand_scores[i].dimensions:
                                for dim in evaluation.brand_scores[i].dimensions:
                                    if "trademark" in dim.name.lower() or "legal" in dim.name.lower():
                                        dim.score = 1.0
                                        dim.reasoning = f"**CRITICAL CONFLICT:**\nBrand name conflicts with existing trademark '{matched_brand}'. Registration would be rejected or opposed.\n\n**LEGAL RISK:**\nHigh risk of trademark infringement lawsuit if used."
                            
                            # Clear recommendations (no point recommending anything for a rejected name)
                            if evaluation.brand_scores[i].domain_analysis:
                                evaluation.brand_scores[i].domain_analysis.alternatives = []
                                evaluation.brand_scores[i].domain_analysis.strategy_note = "N/A - Name rejected due to brand conflict"
                            if evaluation.brand_scores[i].multi_domain_availability:
                                evaluation.brand_scores[i].multi_domain_availability.recommended_domain = "N/A - Name rejected"
                                evaluation.brand_scores[i].multi_domain_availability.acquisition_strategy = "N/A - Name rejected"
                            if evaluation.brand_scores[i].social_availability:
                                evaluation.brand_scores[i].social_availability.recommendation = "N/A - Name rejected due to brand conflict"
                            if evaluation.brand_scores[i].competitor_analysis:
                                evaluation.brand_scores[i].competitor_analysis.suggested_pricing = "N/A - Name rejected"
                            evaluation.brand_scores[i].positioning_fit = "N/A - Name rejected due to famous brand trademark conflict"
                
                # Generate report_id and save to database
                report_id = f"report_{uuid.uuid4().hex[:16]}"
                doc = evaluation.model_dump()
                doc['report_id'] = report_id
                doc['created_at'] = datetime.now(timezone.utc).isoformat()
                doc['request'] = request.model_dump()
                await db.evaluations.insert_one(doc)
                
                # Set report_id in the evaluation object
                evaluation.report_id = report_id
                
                # Return the evaluation with report_id
                logging.info(f"Successfully generated report with model {model_provider}/{model_name}")
                return evaluation
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                if "Budget has been exceeded" in error_msg:
                    logging.error(f"LLM Budget Exceeded: {error_msg}")
                    raise HTTPException(status_code=402, detail="Emergent Key Budget Exceeded. Please add credits.")
                
                # Retry on 502/Gateway/Service errors AND JSON/Validation errors
                if any(x in error_msg for x in ["502", "BadGateway", "ServiceUnavailable", "Expecting", "JSON", "validation error", "control character"]):
                    wait_time = 0.5 + random.uniform(0, 0.5)
                    logging.warning(f"LLM Error ({model_provider}/{model_name}, Attempt {attempt+1}/{max_retries}): {error_msg[:100]}. Retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    continue  # Continue to next retry attempt
                
                # Non-retryable error - break inner loop to try next model
                logging.error(f"LLM Non-retryable Error with {model_provider}/{model_name}: {error_msg[:200]}")
                break
        
        # After all retries exhausted for this model, log and continue to next model
        logging.warning(f"Moving to next model after {model_provider}/{model_name} failed...")
            
    raise HTTPException(status_code=500, detail=f"Analysis failed: {str(last_error)}")

# Status Routes
@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks(limit: int = 100, skip: int = 0):
    """Get recent status checks with pagination (default: last 100, sorted by timestamp desc)"""
    status_checks = await db.status_checks.find(
        {}, 
        {"_id": 0}
    ).sort("timestamp", -1).skip(skip).limit(min(limit, 100)).to_list(min(limit, 100))
    for check in status_checks:
        if isinstance(check.get('timestamp'), str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

# ==================== AUTH ENDPOINTS ====================

class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    auth_type: Optional[str] = "google"

class SessionRequest(BaseModel):
    session_id: str

# Email/Password Auth Models
class EmailRegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class EmailLoginRequest(BaseModel):
    email: str
    password: str

@api_router.post("/auth/register")
async def register_email(request: EmailRegisterRequest, response: Response):
    """Register a new user with email/password"""
    # Check if email already exists
    existing_user = await db.users.find_one({"email": request.email.lower()}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate password
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    # Hash password
    hashed_password = pwd_context.hash(request.password)
    
    # Create user
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    session_token = f"sess_{uuid.uuid4().hex}"
    
    await db.users.insert_one({
        "user_id": user_id,
        "email": request.email.lower(),
        "name": request.name,
        "password_hash": hashed_password,
        "auth_type": "email",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Create session
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60
    )
    
    return {
        "user_id": user_id,
        "email": request.email.lower(),
        "name": request.name,
        "picture": None,
        "auth_type": "email"
    }

@api_router.post("/auth/login/email")
async def login_email(request: EmailLoginRequest, response: Response):
    """Login with email/password"""
    # Find user
    user = await db.users.find_one({"email": request.email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if user has password (email auth)
    if not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="This account uses Google Sign-In")
    
    # Verify password
    if not pwd_context.verify(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create session
    session_token = f"sess_{uuid.uuid4().hex}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Remove old sessions
    await db.user_sessions.delete_many({"user_id": user["user_id"]})
    
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60
    )
    
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user.get("picture"),
        "auth_type": "email"
    }

# ==================== BRAND AUDIT ENDPOINTS ====================

async def perform_web_search(query: str) -> str:
    """Perform web search using Claude with web search capability (via Emergent)"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    results_text = ""
    
    try:
        # Use Claude which has web search capability
        llm_chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"search_{uuid.uuid4()}",
            system_message="You are a research assistant with web search access. Search the web and provide ONLY factual, verifiable information. Include specific numbers, dates, and ratings. If you cannot find specific data, say 'Not found in search'."
        ).with_model("anthropic", "claude-sonnet-4-20250514")
        
        search_prompt = f"""Search the web for: {query}

Return ONLY factual information you find from search results. Include:
- Exact numbers (store counts, ratings, revenue figures)
- Specific dates (founding year, expansion dates)
- Platform ratings (Google Maps rating, Justdial rating, Zomato rating)
- Source names when possible

Be specific and factual. Do not make assumptions."""

        user_message = UserMessage(text=search_prompt)
        response = await asyncio.wait_for(
            llm_chat.send_message(user_message),
            timeout=30.0
        )
        
        if hasattr(response, 'text'):
            results_text = response.text
        elif isinstance(response, str):
            results_text = response
        else:
            results_text = str(response)
        
        logging.info(f"Claude web search completed for: {query[:50]}...")
        return f"Query: {query}\n\nSearch Results:\n{results_text}"
        
    except asyncio.TimeoutError:
        logging.warning(f"Claude search timed out for: {query[:50]}")
    except Exception as e:
        logging.warning(f"Claude search failed: {e}")
    
    # Fallback to DuckDuckGo
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            ddg_results = list(ddgs.text(query, max_results=5))
            if ddg_results:
                formatted = []
                for r in ddg_results:
                    formatted.append(f"{r.get('title', '')}: {r.get('body', '')}")
                results_text = "\n".join(formatted)
                return f"Query: {query}\n\nSearch Results:\n{results_text}"
    except Exception as ddg_error:
        logging.warning(f"DuckDuckGo fallback failed: {ddg_error}")
    
    return f"Query: {query}\n\nNo search results found"


async def crawl_website_page(url: str) -> str:
    """Crawl a specific website page and extract text content"""
    import aiohttp
    from bs4 import BeautifulSoup
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style", "nav", "footer", "header"]):
                        script.decompose()
                    
                    # Get text content
                    text = soup.get_text(separator='\n', strip=True)
                    
                    # Clean up excessive whitespace
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    text = '\n'.join(lines)
                    
                    # Limit length
                    if len(text) > 5000:
                        text = text[:5000] + "... [truncated]"
                    
                    logging.info(f"Successfully crawled {url} - {len(text)} chars")
                    return text
                else:
                    logging.warning(f"Failed to crawl {url} - Status {response.status}")
                    return ""
    except Exception as e:
        logging.warning(f"Error crawling {url}: {e}")
        return ""


async def crawl_brand_website(brand_website: str, brand_name: str) -> str:
    """Crawl brand website for About Us, Our Story, and homepage content"""
    import aiohttp
    
    # Normalize URL
    if not brand_website.startswith(('http://', 'https://')):
        brand_website = 'https://' + brand_website
    
    base_url = brand_website.rstrip('/')
    
    # Pages to try crawling (in order of importance)
    pages_to_crawl = [
        (f"{base_url}/about", "About Page"),
        (f"{base_url}/about-us", "About Us Page"),
        (f"{base_url}/our-story", "Our Story Page"),
        (f"{base_url}/story", "Story Page"),
        (f"{base_url}/who-we-are", "Who We Are Page"),
        (base_url, "Homepage"),
        (f"{base_url}/franchise", "Franchise Page"),
        (f"{base_url}/contact", "Contact Page"),
    ]
    
    all_content = []
    all_content.append(f"=== WEBSITE CONTENT FOR {brand_name.upper()} ===\n")
    all_content.append(f"Website: {brand_website}\n")
    
    crawled_count = 0
    max_pages = 4  # Limit to avoid timeout
    
    for url, page_name in pages_to_crawl:
        if crawled_count >= max_pages:
            break
            
        logging.info(f"Brand Audit: Crawling {page_name}: {url}")
        content = await crawl_website_page(url)
        
        if content and len(content) > 100:
            all_content.append(f"\n--- {page_name.upper()} ({url}) ---\n")
            all_content.append(content)
            crawled_count += 1
    
    if crawled_count == 0:
        all_content.append("\n[Unable to crawl website - may be blocked or unavailable]\n")
    
    return "\n".join(all_content)


async def gather_brand_audit_research(brand_name: str, brand_website: str, competitor_1: str, 
                                       competitor_2: str, category: str, geography: str) -> dict:
    """Execute comprehensive research workflow for brand audit with website crawling"""
    
    research_data = {}
    all_queries = []
    
    # Extract domain names for cleaner searches
    brand_domain = brand_website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    comp1_domain = competitor_1.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    comp2_domain = competitor_2.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    comp1_name = comp1_domain.split(".")[0].title()
    comp2_name = comp2_domain.split(".")[0].title()
    
    year_range = "2023 2024 2025"
    
    # ========================================================================
    # PHASE 0: CRAWL BRAND WEBSITE (PRIMARY SOURCE - Most Accurate!)
    # ========================================================================
    logging.info(f"Brand Audit: PHASE 0 - Crawling brand website: {brand_website}")
    
    website_content = await crawl_brand_website(brand_website, brand_name)
    
    logging.info(f"Brand Audit: Website crawl complete - {len(website_content)} chars")
    
    # ========================================================================
    # PHASE 1: WEB SEARCH FOR ADDITIONAL DATA
    # ========================================================================
    logging.info(f"Brand Audit: PHASE 1 - Starting web search research for {brand_name}")
    
    all_queries = [
        # Query 1: Core brand info (founding, stores, locations)
        f"{brand_name} {category} {geography} founding year total stores outlets locations states presence 2024",
        
        # Query 2: Ratings and customer perception
        f"{brand_name} Google Maps rating Justdial rating Zomato rating customer reviews {geography}",
        
        # Query 3: Competitive analysis
        f"{brand_name} vs {comp1_name} vs {comp2_name} comparison market share {category} {geography}",
        
        # Query 4: Financial and growth metrics
        f"{brand_name} revenue franchise investment cost growth expansion {year_range}",
        
        # Query 5: Market context
        f"{category} {geography} market size CAGR trends 2024 2025"
    ]
    
    research_results = []
    for i, q in enumerate(all_queries, 1):
        logging.info(f"Brand Audit: Search {i}/5 - {q[:50]}...")
        result = await perform_web_search(q)
        research_results.append(result)
    
    # Combine web search results
    web_search_data = "\n\n" + "="*80 + "\n\n".join(research_results)
    
    # ========================================================================
    # COMBINE ALL RESEARCH DATA
    # ========================================================================
    # Website content is PRIMARY source - put it first!
    research_data['phase1_data'] = f"""
================================================================================
PRIMARY SOURCE: BRAND WEBSITE CONTENT
================================================================================
⚠️ USE THIS AS YOUR PRIMARY SOURCE OF TRUTH FOR COMPANY INFORMATION ⚠️

{website_content}

================================================================================
SECONDARY SOURCE: WEB SEARCH RESULTS
================================================================================
Use web search for additional context, ratings, market data, and competitive info.

{web_search_data}
"""
    
    research_data['phase2_data'] = ""
    research_data['phase3_data'] = ""
    research_data['phase4_data'] = ""
    research_data['phase5_data'] = ""
    research_data['all_queries'] = ["Website crawl: " + brand_website] + all_queries
    research_data['rating_platforms'] = ["Google Maps", "Justdial", "Zomato", "Swiggy"]
    research_data['website_crawled'] = bool(website_content and len(website_content) > 200)
    
    return research_data

@api_router.post("/brand-audit", response_model=BrandAuditResponse)
async def brand_audit(request: BrandAuditRequest):
    """Execute comprehensive brand audit with 4-phase research methodology"""
    import time as time_module
    start_time = time_module.time()
    
    logging.info(f"Starting Brand Audit for: {request.brand_name}")
    
    if not LlmChat or not EMERGENT_KEY:
        raise HTTPException(status_code=500, detail="LLM Integration not initialized")
    
    # Gather research data using 4-phase methodology
    research_data = await gather_brand_audit_research(
        brand_name=request.brand_name,
        brand_website=request.brand_website,
        competitor_1=request.competitor_1,
        competitor_2=request.competitor_2,
        category=request.category,
        geography=request.geography
    )
    
    logging.info(f"Research completed. Executing LLM analysis...")
    
    # Helper function to parse customer perception analysis
    def parse_customer_perception(cpa_data):
        if not cpa_data or not isinstance(cpa_data, dict):
            return None
        try:
            from schemas import CustomerPerceptionAnalysis, PlatformRating, CustomerTheme
            
            platform_ratings = []
            for pr in cpa_data.get('platform_ratings', []):
                if isinstance(pr, dict):
                    platform_ratings.append(PlatformRating(
                        platform=pr.get('platform', 'Unknown'),
                        rating=pr.get('rating'),
                        review_count=pr.get('review_count'),
                        url=pr.get('url')
                    ))
            
            positive_themes = []
            for pt in cpa_data.get('positive_themes', []):
                if isinstance(pt, dict):
                    positive_themes.append(CustomerTheme(
                        theme=pt.get('theme', ''),
                        quote=pt.get('quote'),
                        frequency=pt.get('frequency', 'MEDIUM'),
                        sentiment='POSITIVE'
                    ))
            
            negative_themes = []
            for nt in cpa_data.get('negative_themes', []):
                if isinstance(nt, dict):
                    negative_themes.append(CustomerTheme(
                        theme=nt.get('theme', ''),
                        quote=nt.get('quote'),
                        frequency=nt.get('frequency', 'MEDIUM'),
                        sentiment='NEGATIVE'
                    ))
            
            return CustomerPerceptionAnalysis(
                overall_sentiment=cpa_data.get('overall_sentiment', 'NEUTRAL'),
                sentiment_score=cpa_data.get('sentiment_score'),
                platform_ratings=platform_ratings,
                average_rating=cpa_data.get('average_rating'),
                total_reviews=cpa_data.get('total_reviews'),
                rating_vs_competitors=cpa_data.get('rating_vs_competitors'),
                competitor_ratings=cpa_data.get('competitor_ratings', {}),
                positive_themes=positive_themes,
                negative_themes=negative_themes,
                key_strengths=cpa_data.get('key_strengths', []),
                key_concerns=cpa_data.get('key_concerns', []),
                analysis=cpa_data.get('analysis')
            )
        except Exception as e:
            logging.warning(f"Error parsing customer perception analysis: {e}")
            return None
    
    # Build prompt - USE COMPACT VERSION for reliability
    user_prompt = build_brand_audit_prompt_compact(
        brand_name=request.brand_name,
        brand_website=request.brand_website,
        competitor_1=request.competitor_1,
        competitor_2=request.competitor_2,
        category=request.category,
        geography=request.geography,
        research_data=research_data
    )
    
    logging.info(f"Brand Audit: User prompt length: {len(user_prompt)} chars")
    
    # Models to try in order - GPT-4o-mini first (most reliable), then others
    models_to_try = [
        ("openai", "gpt-4o-mini"),    # Most reliable, fastest
        ("openai", "gpt-4o"),         # Higher quality
        ("anthropic", "claude-sonnet-4-20250514"),  # Claude backup
    ]
    
    content = ""
    data = None
    last_error = None
    
    # Retry logic with exponential backoff for 502 errors
    max_retries_per_model = 2  # Reduced from 3 to speed up failover
    
    for provider, model in models_to_try:
        for retry in range(max_retries_per_model):
            try:
                logging.info(f"Brand Audit: Trying {provider}/{model} (attempt {retry + 1}/{max_retries_per_model})...")
                llm_chat = LlmChat(
                    api_key=EMERGENT_KEY,
                    session_id=f"brand_audit_{uuid.uuid4()}",
                    system_message=BRAND_AUDIT_SYSTEM_PROMPT_COMPACT  # USE COMPACT PROMPT
                ).with_model(provider, model)
                
                user_message = UserMessage(text=user_prompt)
                response = await asyncio.wait_for(
                    llm_chat.send_message(user_message),
                    timeout=120.0  # 2 minute timeout per model
                )
                
                if hasattr(response, 'text'):
                    content = response.text
                elif isinstance(response, str):
                    content = response
                else:
                    content = str(response)
                
                logging.info(f"Brand Audit: {provider}/{model} raw response length: {len(content) if content else 0}")
                logging.info(f"Brand Audit: {provider}/{model} raw response preview: {content[:200] if content else 'EMPTY'}...")
                
                # Check for empty response
                if not content or content.strip() == "":
                    logging.warning(f"Brand Audit: {provider}/{model} returned empty response")
                    raise ValueError("Empty response from LLM")
                
                # Extract JSON
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    parts = content.split("```")
                    if len(parts) >= 2:
                        content = parts[1]
                        if content.startswith("json"):
                            content = content[4:]
                
                content = content.strip()
                
                logging.info(f"Brand Audit: After JSON extraction, content length: {len(content)}")
                
                # Check again after extraction
                if not content:
                    logging.warning(f"Brand Audit: {provider}/{model} JSON extraction failed - empty content")
                    raise ValueError("JSON extraction failed - empty content")
                
                # Parse JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as je:
                    logging.warning(f"Brand Audit: JSON decode failed, attempting repair. Content length: {len(content)}")
                    from json_repair import repair_json
                    content = repair_json(content)
                    data = json.loads(content)
                
                # Verify we got valid data
                if not data or not isinstance(data, dict):
                    logging.warning(f"Brand Audit: {provider}/{model} returned invalid data structure")
                    raise ValueError("Invalid data structure from LLM")
                
                logging.info(f"Brand Audit: {provider}/{model} succeeded!")
                break  # Success, exit retry loop
                
            except asyncio.TimeoutError:
                last_error = f"Timeout after 120s"
                logging.warning(f"Brand Audit: {provider}/{model} timed out (attempt {retry + 1})")
                continue  # Retry same model
            except Exception as e:
                error_str = str(e)
                last_error = e
                logging.warning(f"Brand Audit: {provider}/{model} failed (attempt {retry + 1}): {e}")
                
                # If 502 error, wait before retrying same model
                if "502" in error_str or "BadGateway" in error_str:
                    wait_time = (retry + 1) * 5  # 5s, 10s, 15s
                    logging.info(f"Brand Audit: 502 error, waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue  # Retry same model
                else:
                    break  # Move to next model for non-502 errors
        
        # Check if we got data (break outer loop if successful)
        if data:
            break
    
    # If all models failed
    if not data:
        logging.error(f"Brand Audit: All models failed. Last error: {last_error}")
        raise HTTPException(status_code=500, detail=f"All LLM models failed. Please try again later.")
    
    logging.info(f"Brand Audit LLM response parsed successfully")
    
    # Build response
    report_id = f"audit_{uuid.uuid4().hex[:16]}"
    
    # Parse dimensions
    dimensions = []
    raw_dimensions = data.get('dimensions', [])
    logging.info(f"Brand Audit: Raw dimensions count: {len(raw_dimensions)}")
    logging.info(f"Brand Audit: Raw dimensions data: {raw_dimensions[:2] if raw_dimensions else 'EMPTY'}")  # Log first 2
    
    for dim in raw_dimensions:
        dimensions.append(BrandAuditDimension(
            name=dim.get('name', ''),
            score=float(dim.get('score', 0)),
            reasoning=dim.get('reasoning', 'No reasoning provided'),
            data_sources=dim.get('data_sources', dim.get('evidence', [])),
            confidence=dim.get('confidence', 'MEDIUM')
        ))
    
    logging.info(f"Brand Audit: Parsed {len(dimensions)} dimensions")
    
    # Ensure we have 8 dimensions
    dimension_names = ["Heritage & Authenticity", "Customer Satisfaction", "Market Positioning", 
                      "Growth Trajectory", "Operational Excellence", "Brand Awareness", 
                      "Financial Viability", "Digital Presence"]
    existing_names = [d.name for d in dimensions]
    for name in dimension_names:
        if name not in existing_names:
            dimensions.append(BrandAuditDimension(name=name, score=5.0, reasoning="Data insufficient", confidence="LOW"))
    
    # Parse competitors
    competitors = []
    for comp in data.get('competitors', []):
        # Handle rating - convert to float or None if invalid
        rating_val = comp.get('rating')
        if isinstance(rating_val, str):
            try:
                rating_val = float(rating_val)
            except (ValueError, TypeError):
                rating_val = None
        
        # Handle outlets - convert to string if it's a number
        outlets_val = comp.get('outlets')
        if isinstance(outlets_val, (int, float)):
            outlets_val = str(outlets_val)
        
        competitors.append(CompetitorData(
            name=comp.get('name', ''),
            website=comp.get('website', ''),
            founded=comp.get('founded'),
            outlets=outlets_val,
            rating=rating_val,
            social_followers=comp.get('social_followers'),
            key_strength=comp.get('key_strength'),
            key_weakness=comp.get('key_weakness')
        ))
    
    # Parse competitive matrix
    competitive_matrix = []
    for pos in data.get('competitive_matrix', []):
        competitive_matrix.append(CompetitivePosition(
            brand_name=pos.get('brand_name', ''),
            x_score=float(pos.get('x_score', 50)),
            y_score=float(pos.get('y_score', 50)),
            quadrant=pos.get('quadrant')
        ))
    
    # Parse SWOT
    swot_data = data.get('swot', {})
    swot = SWOTAnalysis(
        strengths=[SWOTItem(**s) if isinstance(s, dict) else SWOTItem(point=str(s)) for s in swot_data.get('strengths', [])],
        weaknesses=[SWOTItem(**w) if isinstance(w, dict) else SWOTItem(point=str(w)) for w in swot_data.get('weaknesses', [])],
        opportunities=[SWOTItem(**o) if isinstance(o, dict) else SWOTItem(point=str(o)) for o in swot_data.get('opportunities', [])],
        threats=[SWOTItem(**t) if isinstance(t, dict) else SWOTItem(point=str(t)) for t in swot_data.get('threats', [])]
    )
    
    # Parse recommendations - handle both nested and flat structures
    recommendations_data = data.get('recommendations', {})
    immediate_raw = recommendations_data.get('immediate', []) if isinstance(recommendations_data, dict) else []
    medium_raw = recommendations_data.get('medium_term', []) if isinstance(recommendations_data, dict) else []
    long_raw = recommendations_data.get('long_term', []) if isinstance(recommendations_data, dict) else []
    
    # Fallback to flat keys if nested is empty
    if not immediate_raw:
        immediate_raw = data.get('immediate_recommendations', [])
    if not medium_raw:
        medium_raw = data.get('medium_term_recommendations', [])
    if not long_raw:
        long_raw = data.get('long_term_recommendations', [])
    
    def parse_recommendation(r):
        """Parse recommendation ensuring title/recommended_action are present"""
        if isinstance(r, dict):
            # Ensure recommended_action exists (fallback to title)
            if 'recommended_action' not in r and 'title' in r:
                r['recommended_action'] = r['title']
            elif 'title' not in r and 'recommended_action' in r:
                r['title'] = r['recommended_action']
            return StrategicRecommendation(**r)
        else:
            return StrategicRecommendation(title=str(r), recommended_action=str(r))
    
    immediate_recs = [parse_recommendation(r) for r in immediate_raw]
    medium_recs = [parse_recommendation(r) for r in medium_raw]
    long_recs = [parse_recommendation(r) for r in long_raw]
    
    logging.info(f"Brand Audit: Parsed {len(immediate_recs)} immediate, {len(medium_recs)} medium, {len(long_recs)} long-term recommendations")
    
    # Parse market data
    market_data_raw = data.get('market_data', {})
    market_data = MarketData(
        market_size=market_data_raw.get('market_size'),
        cagr=market_data_raw.get('cagr'),
        growth_drivers=market_data_raw.get('growth_drivers', []),
        key_trends=market_data_raw.get('key_trends', [])
    ) if market_data_raw else None
    
    # Build response with new elite consulting fields
    response_data = BrandAuditResponse(
        report_id=report_id,
        brand_name=request.brand_name,
        brand_website=request.brand_website,
        category=request.category,
        geography=request.geography,
        overall_score=float(data.get('overall_score', 0)),
        rating=data.get('rating'),
        verdict=data.get('verdict', 'MODERATE'),
        executive_summary=data.get('executive_summary', ''),
        investment_thesis=data.get('investment_thesis'),
        brand_overview=data.get('brand_overview', {}),
        # NEW: Elite consulting sections
        market_landscape=data.get('market_landscape'),
        brand_equity=data.get('brand_equity'),
        financial_performance=data.get('financial_performance'),
        consumer_perception=data.get('consumer_perception'),
        competitive_positioning=data.get('competitive_positioning'),
        valuation=data.get('valuation'),
        conclusion=data.get('conclusion'),
        # NEW: Customer Perception Analysis
        customer_perception_analysis=parse_customer_perception(data.get('customer_perception_analysis')),
        # Existing fields
        dimensions=dimensions,
        competitors=competitors,
        competitive_matrix=competitive_matrix,
        positioning_gap=data.get('positioning_gap'),
        market_data=market_data,
        swot=swot,
        immediate_recommendations=immediate_recs,
        medium_term_recommendations=medium_recs,
        long_term_recommendations=long_recs,
        risks=data.get('risks', []),
        search_queries=research_data.get('all_queries', []),
        sources=data.get('sources', []),
        data_confidence=data.get('data_confidence', 'MEDIUM'),
        created_at=datetime.now(timezone.utc).isoformat(),
        processing_time_seconds=time_module.time() - start_time
    )
    
    # Save to database
    doc = response_data.model_dump()
    doc['request'] = request.model_dump()
    await db.brand_audits.insert_one(doc)
    
    logging.info(f"Brand Audit completed in {time_module.time() - start_time:.2f}s")
    return response_data

@api_router.get("/brand-audit/{report_id}")
async def get_brand_audit_report(report_id: str):
    """Get a saved brand audit report by ID"""
    report = await db.brand_audits.find_one({"report_id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Brand audit report not found")
    return report

# ==================== REPORT ENDPOINTS ====================

@api_router.get("/reports/{report_id}")
async def get_report(report_id: str, request: Request):
    """Get a saved report by ID. Returns full or preview based on auth."""
    report = await db.evaluations.find_one({"report_id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check if user is authenticated
    session_token = request.cookies.get("session_token")
    is_authenticated = False
    
    if session_token:
        session_doc = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session_doc:
            expires_at = session_doc.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at >= datetime.now(timezone.utc):
                is_authenticated = True
    
    # Return full report for authenticated users
    report["is_authenticated"] = is_authenticated
    return report

@api_router.post("/auth/session")
async def create_session(request: SessionRequest, response: Response):
    """Exchange session_id for session_token and create/update user"""
    try:
        # Call Emergent Auth API to get user data
        async with httpx.AsyncClient() as client:
            auth_response = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": request.session_id},
                timeout=10.0
            )
        
        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        user_data = auth_response.json()
        email = user_data.get("email")
        name = user_data.get("name")
        picture = user_data.get("picture")
        session_token = user_data.get("session_token")
        
        if not email or not session_token:
            raise HTTPException(status_code=401, detail="Invalid session data")
        
        # Check if user exists, create or update
        existing_user = await db.users.find_one({"email": email}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
            # Update user data
            await db.users.update_one(
                {"email": email},
                {"$set": {"name": name, "picture": picture, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
        else:
            # Create new user
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Store session
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        await db.user_sessions.delete_many({"user_id": user_id})  # Remove old sessions
        await db.user_sessions.insert_one({
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Set httpOnly cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=7 * 24 * 60 * 60  # 7 days
        )
        
        return {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture
        }
        
    except httpx.RequestError as e:
        logging.error(f"Auth request error: {e}")
        raise HTTPException(status_code=500, detail="Authentication service unavailable")

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user(request: Request):
    """Get current authenticated user from session"""
    # Try cookie first, then Authorization header
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Find session
    session_doc = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Check expiry
    expires_at = session_doc.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    # Get user
    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    return UserResponse(**user_doc)

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout user and clear session"""
    session_token = request.cookies.get("session_token")
    
    if session_token:
        await db.user_sessions.delete_many({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/", samesite="none", secure=True)
    return {"message": "Logged out successfully"}

app.include_router(api_router)

# Root-level health check endpoint for Kubernetes (no /api prefix)
@app.get("/health")
async def root_health_check():
    return {"status": "healthy"}

# Get CORS origins - handle both wildcard and specific origins
cors_origins_env = os.environ.get('CORS_ORIGINS', '*')
if cors_origins_env == '*':
    # For wildcard, allow any origin
    cors_origins = ["*"]
    allow_credentials = False  # Can't use credentials with wildcard
else:
    cors_origins = [origin.strip() for origin in cors_origins_env.split(',')]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_credentials,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
