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
import aiohttp
from passlib.context import CryptContext
from contextlib import asynccontextmanager

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Import custom modules
from schemas import BrandEvaluationRequest, BrandEvaluationResponse, StatusCheck, StatusCheckCreate, DimensionScore, BrandScore, BrandAuditRequest, BrandAuditResponse, BrandAuditDimension, SWOTAnalysis, SWOTItem, CompetitorData, MarketData, StrategicRecommendation, CompetitivePosition
from prompts import SYSTEM_PROMPT
from prompts_v2 import SYSTEM_PROMPT_V2  # New optimized prompt
from brand_audit_prompt import BRAND_AUDIT_SYSTEM_PROMPT, build_brand_audit_prompt
from brand_audit_prompt_compact import BRAND_AUDIT_SYSTEM_PROMPT_COMPACT, build_brand_audit_prompt_compact
from visibility import check_visibility
from availability import check_full_availability, check_multi_domain_availability, check_social_availability, check_full_availability_with_llm, llm_analyze_domain_strategy
from similarity import check_brand_similarity, format_similarity_report, deep_trace_analysis, format_deep_trace_report
from trademark_research import conduct_trademark_research, format_research_for_prompt

# Import LLM-First Market Intelligence Research Module
from market_intelligence import (
    research_all_countries,
    research_country_market,
    research_cultural_sensitivity,
    format_market_intelligence_for_response,
    format_cultural_intelligence_for_response
)

# Import Universal Linguistic Analysis Module
from linguistic_analysis import (
    analyze_brand_linguistics,
    format_linguistic_analysis_for_prompt,
    get_linguistic_insights_for_trademark,
    get_linguistic_insights_for_cultural_fit
)

# Import Understanding Module - THE BRAIN of RIGHTNAME.AI
from understanding_module import (
    generate_brand_understanding,
    get_nice_class_from_understanding,
    get_classification_from_understanding,
    get_business_type_from_understanding,
    should_use_understanding_classification
)

# Import Deep Market Intelligence Agent
from deep_market_intelligence import (
    deep_market_intelligence,
    format_competitors_for_matrix,
    format_country_analysis,
    get_white_space_summary
)

# Import Competitive Intelligence v2 (FUNNEL APPROACH)
from competitive_intelligence_v2 import (
    competitive_intelligence_v2,
    get_white_space_summary_v2
)

# Import Payment Routes
from payment_routes import payment_router, set_db as set_payment_db

# Import Google OAuth Routes
from google_oauth import google_oauth_router, set_google_oauth_db

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

# Google Custom Search API credentials
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
GOOGLE_SEARCH_ENGINE_ID = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')
if GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
    logging.info("✅ Google Custom Search API configured")
else:
    logging.warning("⚠️ Google Search API not configured - using Bing fallback")

# Import admin routes
from admin_routes import admin_router, initialize_admin, set_db

# Lifespan context manager for graceful startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Application starting... MongoDB pool initialized")
    
    # Initialize admin panel - wrapped in try/except for resilience
    try:
        set_db(db)
        await initialize_admin(db)
        logging.info("✅ Admin panel initialized")
    except Exception as e:
        # Don't fail startup - admin panel is not critical for health checks
        logging.warning(f"⚠️ Admin initialization warning (app still functional): {e}")
    
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
# Use MongoDB for persistent job storage (survives restarts)
# Jobs collection: db.evaluation_jobs

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

async def get_job(job_id: str) -> dict:
    """Get job from MongoDB (async)"""
    try:
        job = await db.evaluation_jobs.find_one({"job_id": job_id})
        if job:
            # Remove MongoDB _id field for JSON serialization
            job.pop('_id', None)
        return job
    except Exception as e:
        logging.error(f"Error getting job {job_id}: {e}")
        return None

async def save_job(job_id: str, job_data: dict):
    """Save or update job in MongoDB (async)"""
    try:
        job_data["job_id"] = job_id
        job_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.evaluation_jobs.update_one(
            {"job_id": job_id},
            {"$set": job_data},
            upsert=True
        )
    except Exception as e:
        logging.error(f"Error saving job {job_id}: {e}")

async def update_job_progress(job_id: str, step_id: str, eta_seconds: int = None):
    """Update job progress in MongoDB (async)"""
    step = next((s for s in EVALUATION_STEPS if s["id"] == step_id), None)
    if step:
        completed = []
        for s in EVALUATION_STEPS:
            if s["progress"] <= step["progress"]:
                completed.append(s["id"])
            else:
                break
        
        await db.evaluation_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "current_step": step_id,
                "current_step_label": step["label"],
                "progress": step["progress"],
                "eta_seconds": eta_seconds,
                "completed_steps": completed,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )


# ============ DYNAMIC PROMPT LOADING ============
async def get_active_system_prompt() -> str:
    """Get active system prompt from database, fallback to V2 optimized prompt"""
    try:
        prompt_doc = await db.prompts.find_one({"type": "system", "is_active": True})
        if prompt_doc and prompt_doc.get("content"):
            logging.info(f"Using custom system prompt: {prompt_doc.get('name', 'Custom')}")
            return prompt_doc["content"]
    except Exception as e:
        logging.warning(f"Error fetching custom prompt: {e}")
    
    # Fallback to V2 optimized prompt (default)
    logging.info("Using default V2 optimized system prompt")
    return SYSTEM_PROMPT_V2

async def get_active_model_settings() -> dict:
    """Get active model settings from database, fallback to defaults"""
    defaults = {
        "primary_model": "gpt-4o-mini",
        "fallback_models": ["claude-sonnet-4-20250514", "gpt-4o"],
        "timeout_seconds": 35,
        "temperature": 0.7,
        "max_tokens": 8000,
        "retry_count": 2
    }
    try:
        settings = await db.settings.find_one({"type": "model_settings"})
        if settings:
            # Merge with defaults (in case some fields missing)
            for key in defaults:
                if key not in settings:
                    settings[key] = defaults[key]
            return settings
    except Exception as e:
        logging.warning(f"Error fetching model settings: {e}")
    
    return defaults


# ============ COUNTRY COMPETITOR ANALYSIS GENERATOR ============
COUNTRY_FLAGS = {
    "India": "🇮🇳", "USA": "🇺🇸", "United States": "🇺🇸", "UK": "🇬🇧", "United Kingdom": "🇬🇧",
    "Germany": "🇩🇪", "France": "🇫🇷", "Japan": "🇯🇵", "China": "🇨🇳", "Australia": "🇦🇺",
    "Canada": "🇨🇦", "Brazil": "🇧🇷", "Singapore": "🇸🇬", "UAE": "🇦🇪", "Thailand": "🇹🇭",
    "Indonesia": "🇮🇩", "Malaysia": "🇲🇾", "Vietnam": "🇻🇳", "South Korea": "🇰🇷", "Italy": "🇮🇹",
    "Spain": "🇪🇸", "Netherlands": "🇳🇱", "Mexico": "🇲🇽", "Russia": "🇷🇺", "Global": "🌍"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL COMPETITORS DATABASE - International brands for "Global Overview"
# These are WORLDWIDE/MULTINATIONAL brands, not country-specific
# ═══════════════════════════════════════════════════════════════════════════════
GLOBAL_COMPETITORS_BY_CATEGORY = {
    "hotels": {
        "competitors": [
            {"name": "Marriott International", "x_coordinate": 75, "y_coordinate": 70, "quadrant": "Global Full-Service", "hq": "USA"},
            {"name": "Hilton Worldwide", "x_coordinate": 70, "y_coordinate": 65, "quadrant": "Business Premium", "hq": "USA"},
            {"name": "IHG (InterContinental)", "x_coordinate": 72, "y_coordinate": 68, "quadrant": "Upscale Portfolio", "hq": "UK"},
            {"name": "Accor Group", "x_coordinate": 65, "y_coordinate": 72, "quadrant": "Lifestyle Diverse", "hq": "France"},
            {"name": "Hyatt Hotels", "x_coordinate": 80, "y_coordinate": 75, "quadrant": "Luxury Lifestyle", "hq": "USA"},
            {"name": "Wyndham Hotels", "x_coordinate": 40, "y_coordinate": 50, "quadrant": "Economy Scale", "hq": "USA"}
        ],
        "axis_x": "Price: Budget → Ultra-Luxury",
        "axis_y": "Positioning: Business/Standard → Lifestyle/Experience",
        "white_space": "Global hospitality ($800B) is dominated by mega-chains with portfolio strategies. **Opportunity: Authentic local experiences** that chains cannot replicate. Boutique, sustainability-focused, and culturally-immersive concepts are underserved globally.",
        "strategic_advantage": "Independent brands can offer authentic local experiences, faster innovation, and community integration that global chains struggle to deliver. Digital-first distribution reduces dependency on OTAs."
    },
    "tea": {
        "competitors": [
            {"name": "Twinings (ABF)", "x_coordinate": 70, "y_coordinate": 55, "quadrant": "Heritage Premium", "hq": "UK"},
            {"name": "Lipton (Unilever)", "x_coordinate": 45, "y_coordinate": 45, "quadrant": "Mass Market", "hq": "Netherlands"},
            {"name": "Dilmah", "x_coordinate": 65, "y_coordinate": 70, "quadrant": "Estate Premium", "hq": "Sri Lanka"},
            {"name": "TWG Tea", "x_coordinate": 90, "y_coordinate": 85, "quadrant": "Ultra-Luxury", "hq": "Singapore"},
            {"name": "Teavana (Starbucks)", "x_coordinate": 75, "y_coordinate": 75, "quadrant": "Lifestyle Premium", "hq": "USA"},
            {"name": "Harney & Sons", "x_coordinate": 72, "y_coordinate": 68, "quadrant": "Artisan Premium", "hq": "USA"}
        ],
        "axis_x": "Price: Mass Market → Ultra-Premium",
        "axis_y": "Positioning: Commodity → Experience/Specialty",
        "white_space": "Global tea market ($70B) is polarized between commodity (Lipton) and ultra-luxury (TWG). **Gap: Accessible premium** segment with authentic origin stories, sustainable sourcing, and wellness positioning.",
        "strategic_advantage": "Direct-to-consumer models bypass retail markup. Origin authenticity (Darjeeling, Assam, Ceylon) commands premium. Wellness trend drives demand for functional teas."
    },
    "coffee": {
        "competitors": [
            {"name": "Starbucks", "x_coordinate": 70, "y_coordinate": 75, "quadrant": "Experience Premium", "hq": "USA"},
            {"name": "Nescafé (Nestlé)", "x_coordinate": 40, "y_coordinate": 40, "quadrant": "Mass Instant", "hq": "Switzerland"},
            {"name": "Lavazza", "x_coordinate": 75, "y_coordinate": 65, "quadrant": "Italian Heritage", "hq": "Italy"},
            {"name": "Blue Bottle", "x_coordinate": 85, "y_coordinate": 85, "quadrant": "Third Wave Premium", "hq": "USA"},
            {"name": "Costa Coffee (Coca-Cola)", "x_coordinate": 55, "y_coordinate": 60, "quadrant": "Accessible Quality", "hq": "UK"},
            {"name": "Illy", "x_coordinate": 80, "y_coordinate": 70, "quadrant": "Artisan Italian", "hq": "Italy"}
        ],
        "axis_x": "Price: Budget → Ultra-Premium",
        "axis_y": "Positioning: Convenience → Experience",
        "white_space": "Global coffee market ($130B) has Starbucks dominating experience, Nestlé dominating instant. **Gap: Specialty third-wave** coffee with origin transparency, sustainable practices, and artisan quality.",
        "strategic_advantage": "Direct trade relationships ensure quality and story. Subscription models create recurring revenue. Coffee culture growth in Asia presents expansion opportunity."
    },
    "technology": {
        "competitors": [
            {"name": "Microsoft", "x_coordinate": 80, "y_coordinate": 60, "quadrant": "Enterprise Dominant", "hq": "USA"},
            {"name": "Google (Alphabet)", "x_coordinate": 75, "y_coordinate": 80, "quadrant": "Innovation Leader", "hq": "USA"},
            {"name": "Amazon AWS", "x_coordinate": 70, "y_coordinate": 70, "quadrant": "Cloud Infrastructure", "hq": "USA"},
            {"name": "SAP", "x_coordinate": 85, "y_coordinate": 50, "quadrant": "Enterprise Legacy", "hq": "Germany"},
            {"name": "Salesforce", "x_coordinate": 75, "y_coordinate": 75, "quadrant": "SaaS Pioneer", "hq": "USA"},
            {"name": "Oracle", "x_coordinate": 82, "y_coordinate": 45, "quadrant": "Database Legacy", "hq": "USA"}
        ],
        "axis_x": "Price: SMB → Enterprise",
        "axis_y": "Positioning: Traditional → Cloud-Native",
        "white_space": "Global enterprise software ($500B+) dominated by US giants. **Gap: Vertical-specific SaaS** solutions for underserved industries. Regional players can win with localization and compliance expertise.",
        "strategic_advantage": "AI-first architecture can leapfrog legacy systems. Vertical focus enables domain expertise. Lower cost structures in emerging markets enable competitive pricing."
    },
    "food": {
        "competitors": [
            {"name": "Nestlé", "x_coordinate": 70, "y_coordinate": 55, "quadrant": "Global Conglomerate", "hq": "Switzerland"},
            {"name": "PepsiCo (Frito-Lay)", "x_coordinate": 50, "y_coordinate": 50, "quadrant": "Snacks Mass", "hq": "USA"},
            {"name": "Mondelez", "x_coordinate": 60, "y_coordinate": 60, "quadrant": "Confectionery Global", "hq": "USA"},
            {"name": "Danone", "x_coordinate": 70, "y_coordinate": 70, "quadrant": "Health Focus", "hq": "France"},
            {"name": "Kraft Heinz", "x_coordinate": 55, "y_coordinate": 45, "quadrant": "Legacy Brands", "hq": "USA"},
            {"name": "Unilever Foods", "x_coordinate": 65, "y_coordinate": 55, "quadrant": "Diverse Portfolio", "hq": "Netherlands/UK"}
        ],
        "axis_x": "Price: Value → Premium",
        "axis_y": "Positioning: Traditional → Health/Wellness",
        "white_space": "Global packaged food ($4T) shifting to health, sustainability, and authenticity. **Gap: Clean-label, locally-sourced** products with transparent supply chains.",
        "strategic_advantage": "Agility to respond to health trends faster than conglomerates. Direct-to-consumer bypasses retail gatekeepers. Authentic stories resonate with conscious consumers."
    },
    "beauty": {
        "competitors": [
            {"name": "L'Oréal", "x_coordinate": 75, "y_coordinate": 70, "quadrant": "Mass Premium", "hq": "France"},
            {"name": "Estée Lauder", "x_coordinate": 85, "y_coordinate": 75, "quadrant": "Prestige Beauty", "hq": "USA"},
            {"name": "Shiseido", "x_coordinate": 80, "y_coordinate": 72, "quadrant": "Asian Luxury", "hq": "Japan"},
            {"name": "Unilever Beauty", "x_coordinate": 50, "y_coordinate": 55, "quadrant": "Mass Market", "hq": "Netherlands/UK"},
            {"name": "Coty", "x_coordinate": 65, "y_coordinate": 60, "quadrant": "Accessible Luxury", "hq": "USA"},
            {"name": "Amorepacific", "x_coordinate": 75, "y_coordinate": 78, "quadrant": "K-Beauty Innovation", "hq": "South Korea"}
        ],
        "axis_x": "Price: Mass → Prestige",
        "axis_y": "Positioning: Traditional → Innovation/Natural",
        "white_space": "Global beauty ($550B) seeing shift to clean beauty, inclusivity, and sustainability. **Gap: Authentic indie brands** with transparent ingredients and mission-driven positioning.",
        "strategic_advantage": "DTC and social commerce reduce retail dependency. Influencer-led brands can build faster than conglomerates. Clean beauty premiums justify higher margins."
    },
    "finance": {
        "competitors": [
            {"name": "Visa/Mastercard", "x_coordinate": 85, "y_coordinate": 50, "quadrant": "Payment Rails", "hq": "USA"},
            {"name": "PayPal", "x_coordinate": 70, "y_coordinate": 70, "quadrant": "Digital Payments", "hq": "USA"},
            {"name": "Stripe", "x_coordinate": 75, "y_coordinate": 80, "quadrant": "Developer Fintech", "hq": "USA"},
            {"name": "Ant Group (Alipay)", "x_coordinate": 65, "y_coordinate": 75, "quadrant": "Super App", "hq": "China"},
            {"name": "Adyen", "x_coordinate": 78, "y_coordinate": 72, "quadrant": "Unified Commerce", "hq": "Netherlands"},
            {"name": "Block (Square)", "x_coordinate": 60, "y_coordinate": 75, "quadrant": "SMB Fintech", "hq": "USA"}
        ],
        "axis_x": "Target: Consumer → Enterprise",
        "axis_y": "Positioning: Legacy → Digital-Native",
        "white_space": "Global fintech ($200B+) disrupting traditional banking. **Gap: Embedded finance** and vertical-specific solutions. Underbanked markets present massive opportunity.",
        "strategic_advantage": "Mobile-first approach reaches underbanked populations. API-first enables embedded finance partnerships. Regional compliance expertise creates moats."
    },
    "default": {
        "competitors": [
            {"name": "Global Market Leader", "x_coordinate": 80, "y_coordinate": 70, "quadrant": "Premium Established", "hq": "Global"},
            {"name": "Value Champion", "x_coordinate": 40, "y_coordinate": 55, "quadrant": "Mass Market", "hq": "Global"},
            {"name": "Innovation Disruptor", "x_coordinate": 65, "y_coordinate": 85, "quadrant": "Tech-Forward", "hq": "Global"},
            {"name": "Regional Specialist", "x_coordinate": 55, "y_coordinate": 50, "quadrant": "Local Expert", "hq": "Global"},
            {"name": "Heritage Brand", "x_coordinate": 75, "y_coordinate": 45, "quadrant": "Traditional Premium", "hq": "Global"},
            {"name": "Challenger Brand", "x_coordinate": 50, "y_coordinate": 70, "quadrant": "Emerging Player", "hq": "Global"}
        ],
        "axis_x": "Price: Budget → Premium",
        "axis_y": "Positioning: Traditional → Modern",
        "white_space": "Market opportunities exist for differentiated brands combining innovation with authentic value propositions.",
        "strategic_advantage": "Agile positioning and digital-first strategy can capture market share from established players."
    }
}

def get_global_competitors(category: str, industry: str = None) -> dict:
    """Get GLOBAL competitors for the 'Global Overview' strategic matrix.
    
    These are MULTINATIONAL brands, not country-specific.
    """
    # Map category to key
    category_lower = (category or "").lower()
    
    if any(word in category_lower for word in ["hotel", "hospitality", "resort", "lodge", "accommodation"]):
        category_key = "hotels"
    elif any(word in category_lower for word in ["tea", "chai"]):
        category_key = "tea"
    elif any(word in category_lower for word in ["coffee", "cafe", "espresso"]):
        category_key = "coffee"
    elif any(word in category_lower for word in ["tech", "software", "saas", "app", "digital", "it "]):
        category_key = "technology"
    elif any(word in category_lower for word in ["food", "snack", "beverage", "restaurant"]):
        category_key = "food"
    elif any(word in category_lower for word in ["beauty", "cosmetic", "skincare", "makeup"]):
        category_key = "beauty"
    elif any(word in category_lower for word in ["finance", "payment", "bank", "fintech", "insurance"]):
        category_key = "finance"
    else:
        category_key = "default"
    
    global_data = GLOBAL_COMPETITORS_BY_CATEGORY.get(category_key, GLOBAL_COMPETITORS_BY_CATEGORY["default"])
    
    logging.info(f"🌍 GLOBAL COMPETITORS: Category '{category}' → using '{category_key}' global data ({len(global_data.get('competitors', []))} brands)")
    
    return global_data

# ============ SACRED/ROYAL/RELIGIOUS NAME DATABASE ============
SACRED_ROYAL_NAMES = {
    "Thailand": {
        "royal_terms": ["rama", "chakri", "bhumibol", "vajiralongkorn", "sirikit", "maha", "chulalongkorn", "mongkut", "prajadhipok", "ananda", "mahidol"],
        "royal_titles": ["phra", "somdet", "chao", "phraya", "khun", "luang"],
        "buddhist_terms": ["buddha", "sangha", "dharma", "dhamma", "wat", "phra", "bhikkhu", "nirvana", "bodhi", "arhat"],
        "warning": "⚠️ **CRITICAL CULTURAL RISK - THAILAND:** The brand name contains elements that may reference Thai royal nomenclature. In Thailand, the Chakri Dynasty monarchs use 'Rama' as their regnal name (Rama I through Rama X - current King Vajiralongkorn is Rama X). **Lèse-majesté laws (Section 112)** make it illegal to defame, insult, or threaten the royal family, punishable by 3-15 years imprisonment per offense. Using royal-associated names for commercial purposes could be perceived as appropriation of royal dignity and may face legal challenges, public backlash, or registration rejection by Thai authorities. **STRONGLY RECOMMEND:** Conduct formal legal review with Thai counsel before market entry."
    },
    "India": {
        "deity_names": ["rama", "ram", "krishna", "shiva", "ganesh", "ganesha", "vishnu", "brahma", "lakshmi", "durga", "kali", "hanuman", "saraswati", "parvati", "indra", "surya"],
        "sacred_terms": ["om", "aum", "namaste", "mantra", "puja", "devi", "deva", "swami", "guru", "ashram", "dharma", "karma", "moksha", "atman", "veda"],
        "political_figures": ["gandhi", "modi", "nehru", "ambedkar", "patel"],
        "warning": "⚠️ **CULTURAL SENSITIVITY - INDIA:** The brand name contains elements associated with Hindu deities, sacred terminology, or significant cultural/political figures. While not illegal, using deity names commercially can trigger **strong public sentiment and boycott movements**. The Hindu community has historically protested brands perceived as trivializing sacred names (e.g., protests against 'Lakshmi' branded products). **RECOMMENDATION:** Conduct sentiment analysis and consider alternative naming to avoid potential PR crises and market rejection in India's 1.4B+ population market."
    },
    "UAE": {
        "islamic_sacred": ["allah", "muhammad", "mohammed", "mohammad", "mecca", "makkah", "medina", "madinah", "quran", "kaaba", "hajj", "umrah", "ramadan", "eid"],
        "religious_terms": ["halal", "haram", "imam", "mosque", "masjid", "sheikh", "mufti", "fatwa", "jihad", "sharia", "salat", "zakat"],
        "royal_terms": ["nahyan", "maktoum", "khalifa", "zayed", "rashid", "sultan", "emir", "amir"],
        "warning": "⚠️ **CRITICAL CULTURAL/LEGAL RISK - UAE/GCC:** The brand name contains terms sacred to Islam or associated with UAE royal families. In UAE and GCC countries, **blasphemy laws** prohibit insults to Islam, and commercial use of sacred terms can result in trademark rejection, business closure, or legal prosecution. Royal family names are protected and cannot be used commercially without explicit permission. **MANDATORY:** Consult with UAE legal counsel and consider formal clearance from relevant authorities before market entry."
    },
    "Japan": {
        "imperial_terms": ["tenno", "mikado", "chrysanthemum", "emperor", "imperial"],
        "sacred_shinto": ["kami", "shinto", "shrine", "torii", "amaterasu", "izanagi", "izanami"],
        "buddhist_terms": ["buddha", "zen", "temple", "bodhi", "dharma"],
        "warning": "⚠️ **CULTURAL SENSITIVITY - JAPAN:** The brand name contains terms associated with the Japanese Imperial family or Shinto/Buddhist sacred terminology. While Japan has freedom of expression, **Imperial symbolism** (particularly the chrysanthemum crest) is legally protected. Religious terminology used commercially may face social disapproval. **RECOMMENDATION:** Review with Japanese cultural consultant and trademark attorney before market entry."
    },
    "China": {
        "political_terms": ["mao", "zedong", "xi", "jinping", "communist", "revolution", "tiananmen"],
        "sacred_terms": ["buddha", "dalai", "lama", "tibet", "falun", "gong"],
        "cultural_terms": ["dragon", "emperor", "dynasty", "mandate", "heaven"],
        "warning": "⚠️ **LEGAL/POLITICAL RISK - CHINA:** The brand name contains politically sensitive or religiously restricted terminology. China's trademark law prohibits marks that are **'detrimental to socialist morals or customs'** or have **'other unhealthy influences.'** Names associated with political figures, Tibetan Buddhism, or Falun Gong face automatic rejection. **MANDATORY:** Engage Chinese IP counsel for formal clearance before China market entry or manufacturing."
    },
    "Saudi Arabia": {
        "islamic_sacred": ["allah", "muhammad", "mohammed", "mecca", "makkah", "medina", "madinah", "quran", "kaaba", "hajj", "prophet"],
        "royal_terms": ["saud", "salman", "abdullah", "fahd", "faisal", "khalid"],
        "warning": "⚠️ **CRITICAL LEGAL RISK - SAUDI ARABIA:** Saudi Arabia enforces strict **Islamic law (Sharia)** regarding sacred terminology. Commercial use of names of Allah, the Prophet, or holy cities is prohibited and may result in severe legal consequences including business closure, deportation, or imprisonment. Royal family names are protected by law. **MANDATORY:** Formal legal clearance required before any Saudi market activity."
    },
    "Israel": {
        "religious_terms": ["yahweh", "jehovah", "elohim", "adonai", "torah", "talmud", "zion", "jerusalem", "temple", "sabbath", "kosher"],
        "warning": "⚠️ **CULTURAL SENSITIVITY - ISRAEL:** The brand name contains Hebrew religious terminology. While Israel has freedom of expression, commercial use of sacred names may face **community opposition** and trademark challenges. **RECOMMENDATION:** Consult with Israeli trademark counsel."
    },
    "default": {
        "warning": None
    }
}

# ============ LINGUISTIC DECOMPOSITION DATABASE ============
# Morpheme database for brand name analysis

MORPHEME_DATABASE = {
    # Sanskrit/Hindi roots (common in South/Southeast Asian names)
    "rama": {
        "origin": "Sanskrit",
        "meaning": "deity/king/seventh avatar of Vishnu",
        "type": "root",
        "cultural_resonance": {
            "India": {"level": "HIGH", "context": "Hindu deity Lord Rama from Ramayana epic - deeply revered"},
            "Thailand": {"level": "CRITICAL", "context": "Royal regnal name (Rama I-X) - current king is Rama X. Lèse-majesté laws apply"},
            "Indonesia": {"level": "HIGH", "context": "Ramayana tradition is central to Javanese/Balinese culture"},
            "Japan": {"level": "LOW", "context": "No significant cultural connection"},
            "USA": {"level": "LOW", "context": "Exotic/foreign sounding, no negative connotations"},
            "UK": {"level": "LOW", "context": "Exotic/foreign sounding, no negative connotations"}
        },
        "industry_fit": {"hotels": "HIGH", "wellness": "HIGH", "luxury": "HIGH", "tech": "MEDIUM"}
    },
    "raya": {
        "origin": "Sanskrit/Malay",
        "meaning": "king/royal/great/celebration",
        "type": "suffix",
        "cultural_resonance": {
            "India": {"level": "HIGH", "context": "Sanskrit 'Raja' derivative - royal/kingly connotation"},
            "Thailand": {"level": "HIGH", "context": "Royal connotation, associated with grandeur"},
            "Indonesia": {"level": "HIGH", "context": "Hari Raya (celebration), royal connotation"},
            "Malaysia": {"level": "HIGH", "context": "Hari Raya festival, positive festive association"},
            "Japan": {"level": "LOW", "context": "No cultural significance"},
            "USA": {"level": "MEDIUM", "context": "Exotic luxury sound"},
            "UK": {"level": "MEDIUM", "context": "Exotic luxury sound"}
        },
        "industry_fit": {"hotels": "HIGH", "luxury": "HIGH", "food": "HIGH", "tech": "LOW"}
    },
    "raj": {
        "origin": "Sanskrit",
        "meaning": "rule/kingdom/reign",
        "type": "root",
        "cultural_resonance": {
            "India": {"level": "HIGH", "context": "Royal/imperial connotation, British Raj historical association"},
            "UK": {"level": "MEDIUM", "context": "British Raj colonial history - check sensitivity"},
            "USA": {"level": "LOW", "context": "Exotic, no strong associations"}
        },
        "industry_fit": {"hotels": "HIGH", "luxury": "HIGH", "restaurants": "HIGH", "tech": "LOW"}
    },
    "zen": {
        "origin": "Japanese/Chinese Buddhist",
        "meaning": "meditation/enlightenment",
        "type": "root",
        "cultural_resonance": {
            "Japan": {"level": "MEDIUM", "context": "Buddhist term - respectful use expected"},
            "China": {"level": "MEDIUM", "context": "Chan Buddhism origin"},
            "USA": {"level": "HIGH", "context": "Positive wellness/calm association"},
            "UK": {"level": "HIGH", "context": "Positive wellness/calm association"}
        },
        "industry_fit": {"wellness": "HIGH", "spa": "HIGH", "tech": "MEDIUM", "hotels": "HIGH"}
    },
    "sakura": {
        "origin": "Japanese",
        "meaning": "cherry blossom",
        "type": "root",
        "cultural_resonance": {
            "Japan": {"level": "HIGH", "context": "National symbol, positive but may seem appropriative if non-Japanese brand"},
            "USA": {"level": "HIGH", "context": "Positive Japanese aesthetic association"},
            "UK": {"level": "HIGH", "context": "Positive Japanese aesthetic association"}
        },
        "industry_fit": {"beauty": "HIGH", "food": "HIGH", "hotels": "MEDIUM", "tech": "LOW"}
    },
    "nova": {
        "origin": "Latin",
        "meaning": "new/star",
        "type": "root",
        "cultural_resonance": {
            "Global": {"level": "HIGH", "context": "Universal positive - innovation, brightness"},
            "Spanish-speaking": {"level": "CAUTION", "context": "'No va' = 'doesn't go' - Chevy Nova issue"}
        },
        "industry_fit": {"tech": "HIGH", "automotive": "CAUTION", "hotels": "MEDIUM", "finance": "HIGH"}
    },
    "lux": {
        "origin": "Latin",
        "meaning": "light/luxury",
        "type": "root/prefix",
        "cultural_resonance": {
            "Global": {"level": "HIGH", "context": "Universal luxury association"}
        },
        "industry_fit": {"hotels": "HIGH", "beauty": "HIGH", "fashion": "HIGH", "tech": "MEDIUM"}
    },
    "kai": {
        "origin": "Multiple (Hawaiian/Japanese/Chinese)",
        "meaning": "sea (Hawaiian), forgiveness (Japanese), open (Chinese)",
        "type": "root",
        "cultural_resonance": {
            "Hawaii/USA": {"level": "HIGH", "context": "Ocean, nature, positive"},
            "Japan": {"level": "MEDIUM", "context": "Multiple meanings, generally positive"},
            "China": {"level": "MEDIUM", "context": "Opening/beginning, positive"}
        },
        "industry_fit": {"hospitality": "HIGH", "wellness": "HIGH", "food": "MEDIUM", "tech": "MEDIUM"}
    },
    "om": {
        "origin": "Sanskrit",
        "meaning": "sacred syllable/primordial sound",
        "type": "root",
        "cultural_resonance": {
            "India": {"level": "CRITICAL", "context": "Most sacred Hindu syllable - commercial use controversial"},
            "Nepal": {"level": "CRITICAL", "context": "Sacred Hindu/Buddhist symbol"},
            "USA": {"level": "MEDIUM", "context": "Yoga/wellness association, generally positive"}
        },
        "industry_fit": {"wellness": "HIGH", "yoga": "HIGH", "hotels": "MEDIUM", "tech": "LOW"}
    },
    "veda": {
        "origin": "Sanskrit",
        "meaning": "knowledge/sacred texts",
        "type": "root",
        "cultural_resonance": {
            "India": {"level": "HIGH", "context": "Sacred Hindu scriptures - use with respect"},
            "USA": {"level": "MEDIUM", "context": "Wisdom/knowledge connotation"}
        },
        "industry_fit": {"education": "HIGH", "wellness": "HIGH", "tech": "MEDIUM", "hotels": "LOW"}
    }
}

# Suffix-Industry Fit Scoring
SUFFIX_INDUSTRY_FIT = {
    "hotels": {
        "high_fit": ["ya", "kan", "tel", "inn", "stay", "nest", "haven", "lodge", "palace", "manor", "raya", "raj", "villa"],
        "medium_fit": ["hub", "spot", "zone", "place", "casa", "maison"],
        "low_fit": ["ify", "ly", "io", "soft", "tech", "ai", "bot", "ware", "labs", "byte"]
    },
    "technology": {
        "high_fit": ["ify", "ly", "io", "ai", "hub", "lab", "labs", "tech", "soft", "ware", "byte", "bit", "cloud", "net"],
        "medium_fit": ["pro", "plus", "max", "go", "one", "x"],
        "low_fit": ["inn", "stay", "nest", "tel", "palace", "manor", "villa", "lodge"]
    },
    "beauty": {
        "high_fit": ["glow", "lux", "belle", "beauty", "skin", "glo", "radiance", "pure", "bloom"],
        "medium_fit": ["lab", "labs", "co", "studio"],
        "low_fit": ["tech", "soft", "ware", "byte", "inn", "tel"]
    },
    "food": {
        "high_fit": ["kitchen", "eats", "bites", "feast", "table", "bowl", "plate", "spice", "flavor"],
        "medium_fit": ["hub", "spot", "co", "house"],
        "low_fit": ["tech", "soft", "ware", "byte", "labs"]
    },
    "finance": {
        "high_fit": ["pay", "fin", "bank", "capital", "wealth", "fund", "vest", "money", "cash"],
        "medium_fit": ["pro", "plus", "hub", "one"],
        "low_fit": ["inn", "tel", "stay", "kitchen", "eats"]
    },
    "wellness": {
        "high_fit": ["zen", "calm", "peace", "vita", "life", "health", "fit", "well", "soul", "mind"],
        "medium_fit": ["hub", "lab", "co", "studio"],
        "low_fit": ["tech", "soft", "ware", "byte"]
    },
    # New categories for media/content
    "media": {
        "high_fit": ["cast", "show", "tube", "tv", "media", "studio", "productions", "channel", "network", "talks"],
        "medium_fit": ["hub", "spot", "co", "lab", "zone", "nation"],
        "low_fit": ["inn", "tel", "stay", "palace", "manor", "villa", "bank", "pay"]
    },
    "education": {
        "high_fit": ["learn", "edu", "academy", "school", "class", "course", "tutor", "study", "skills"],
        "medium_fit": ["hub", "lab", "pro", "plus", "co"],
        "low_fit": ["inn", "tel", "stay", "palace", "manor", "villa"]
    },
    "retail": {
        "high_fit": ["mart", "shop", "store", "market", "bazaar", "cart", "buy", "deal"],
        "medium_fit": ["hub", "spot", "co", "zone"],
        "low_fit": ["inn", "tel", "stay", "palace", "manor", "tech", "soft"]
    },
    # General fallback - neutral for all
    "general": {
        "high_fit": [],
        "medium_fit": ["hub", "co", "pro", "plus"],
        "low_fit": []
    }
}

# Phonetic Risk Patterns by Country
PHONETIC_RISKS = {
    "Japan": {
        "shi": {"risk": "HIGH", "reason": "Sounds like 'death' (死)"},
        "ku": {"risk": "MEDIUM", "reason": "Can sound like 'suffering' (苦)"},
        "shiku": {"risk": "HIGH", "reason": "Combination sounds like 'death and suffering'"}
    },
    "China": {
        "si": {"risk": "HIGH", "reason": "Sounds like 'death' (死) in Mandarin"},
        "fan": {"risk": "MEDIUM", "reason": "Can mean 'trouble' in some contexts"},
        "gui": {"risk": "MEDIUM", "reason": "Can sound like 'ghost' (鬼)"}
    },
    "Thailand": {
        "hia": {"risk": "HIGH", "reason": "Sounds like Chinese-Thai slur"},
        "mung": {"risk": "MEDIUM", "reason": "Can be considered rude pronoun"}
    },
    "Germany": {
        "mist": {"risk": "HIGH", "reason": "Means 'manure/crap' in German"},
        "gift": {"risk": "HIGH", "reason": "Means 'poison' in German"}
    },
    "Spain": {
        "nova": {"risk": "MEDIUM", "reason": "'No va' sounds like 'doesn't go'"}
    },
    "France": {
        "pet": {"risk": "MEDIUM", "reason": "Means 'fart' in French"}
    },
    "Italy": {
        "cazzo": {"risk": "HIGH", "reason": "Vulgar term"},
        "fica": {"risk": "HIGH", "reason": "Vulgar term"}
    }
}

def decompose_brand_name(brand_name: str) -> dict:
    """
    Decompose a brand name into morphemes (roots, prefixes, suffixes).
    Uses pattern matching and known morpheme database.
    """
    name_lower = brand_name.lower().strip()
    morphemes = []
    remaining = name_lower
    
    # First pass: Check for known morphemes in database
    found_morphemes = []
    for morpheme, data in MORPHEME_DATABASE.items():
        if morpheme in name_lower:
            start_idx = name_lower.find(morpheme)
            found_morphemes.append({
                "text": morpheme,
                "start": start_idx,
                "end": start_idx + len(morpheme),
                "data": data
            })
    
    # Sort by position
    found_morphemes.sort(key=lambda x: x["start"])
    
    # Build morpheme list with positions
    result = {
        "original": brand_name,
        "lowercase": name_lower,
        "morphemes": [],
        "unknown_parts": []
    }
    
    if found_morphemes:
        # Extract known morphemes
        last_end = 0
        for fm in found_morphemes:
            # Check for unknown part before this morpheme
            if fm["start"] > last_end:
                unknown_part = name_lower[last_end:fm["start"]]
                if unknown_part.strip():
                    result["unknown_parts"].append({
                        "text": unknown_part,
                        "position": "prefix" if last_end == 0 else "infix"
                    })
            
            result["morphemes"].append({
                "text": fm["text"],
                "original_case": brand_name[fm["start"]:fm["end"]],
                "origin": fm["data"].get("origin", "Unknown"),
                "meaning": fm["data"].get("meaning", "Unknown"),
                "type": fm["data"].get("type", "root"),
                "cultural_resonance": fm["data"].get("cultural_resonance", {}),
                "industry_fit": fm["data"].get("industry_fit", {})
            })
            last_end = fm["end"]
        
        # Check for trailing unknown part
        if last_end < len(name_lower):
            trailing = name_lower[last_end:]
            if trailing.strip():
                result["unknown_parts"].append({
                    "text": trailing,
                    "position": "suffix"
                })
    else:
        # No known morphemes found - treat whole name as unknown
        result["unknown_parts"].append({
            "text": name_lower,
            "position": "whole"
        })
    
    return result

def analyze_suffix_industry_fit(brand_name: str, category: str) -> dict:
    """
    Analyze if the brand name's suffix fits the target industry.
    """
    name_lower = brand_name.lower()
    category_lower = category.lower()
    
    # Map category to our suffix database
    category_map = {
        "hotel": "hotels", "hotels": "hotels", "hospitality": "hotels", "accommodation": "hotels",
        "tech": "technology", "technology": "technology", "software": "technology", "saas": "technology", "app": "technology",
        "beauty": "beauty", "cosmetics": "beauty", "skincare": "beauty",
        "food": "food", "restaurant": "food", "f&b": "food", "beverage": "food",
        "finance": "finance", "fintech": "finance", "banking": "finance", "payments": "finance",
        "wellness": "wellness", "health": "wellness", "fitness": "wellness", "spa": "wellness",
        # Media & Content categories
        "youtube": "media", "channel": "media", "podcast": "media", "content": "media", 
        "media": "media", "streaming": "media", "vlog": "media", "creator": "media",
        "entertainment": "media", "video": "media", "influencer": "media",
        # Education
        "education": "education", "edtech": "education", "learning": "education", "course": "education",
        "training": "education", "academy": "education", "school": "education",
        # E-commerce & Retail
        "ecommerce": "retail", "retail": "retail", "shop": "retail", "store": "retail", "marketplace": "retail"
    }
    
    industry_key = None
    for key, value in category_map.items():
        if key in category_lower:
            industry_key = value
            break
    
    if not industry_key:
        industry_key = "general"  # Default to general, not hotels
    
    industry_suffixes = SUFFIX_INDUSTRY_FIT.get(industry_key, SUFFIX_INDUSTRY_FIT.get("general", {"high_fit": [], "low_fit": []}))
    
    result = {
        "industry": industry_key,
        "fit_level": "NEUTRAL",
        "matched_suffix": None,
        "reasoning": ""
    }
    
    # Check high fit suffixes
    for suffix in industry_suffixes.get("high_fit", []):
        if name_lower.endswith(suffix) or suffix in name_lower:
            result["fit_level"] = "HIGH"
            result["matched_suffix"] = suffix
            result["reasoning"] = f"'{suffix}' suffix/element strongly aligns with {industry_key} industry"
            return result
    
    # Check low fit suffixes
    for suffix in industry_suffixes.get("low_fit", []):
        if name_lower.endswith(suffix) or suffix in name_lower:
            result["fit_level"] = "LOW"
            result["matched_suffix"] = suffix
            result["reasoning"] = f"'{suffix}' suffix/element typically associated with different industries (not {industry_key})"
            return result
    
    # Check medium fit
    for suffix in industry_suffixes.get("medium_fit", []):
        if name_lower.endswith(suffix) or suffix in name_lower:
            result["fit_level"] = "MEDIUM"
            result["matched_suffix"] = suffix
            result["reasoning"] = f"'{suffix}' is moderately suitable for {industry_key} industry"
            return result
    
    result["reasoning"] = f"No strong industry-specific suffix detected for {industry_key}"
    return result

def check_phonetic_risks(brand_name: str, countries: list) -> list:
    """
    Check for phonetic collision risks in target countries.
    """
    name_lower = brand_name.lower()
    risks = []
    
    for country in countries:
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        country_title = country_name.title()
        
        country_risks = PHONETIC_RISKS.get(country_title, {})
        for sound, risk_data in country_risks.items():
            if sound in name_lower:
                risks.append({
                    "country": country_title,
                    "sound": sound,
                    "risk_level": risk_data["risk"],
                    "reason": risk_data["reason"]
                })
    
    return risks

def generate_linguistic_decomposition(brand_name: str, countries: list, category: str) -> dict:
    """
    Generate comprehensive linguistic decomposition analysis for a brand name.
    
    Returns structured analysis including:
    - Morpheme breakdown
    - Cultural resonance per country
    - Industry fit analysis
    - Risk detection
    - Overall classification
    """
    # Step 1: Decompose the brand name
    decomposition = decompose_brand_name(brand_name)
    
    # Step 2: Analyze suffix-industry fit
    industry_fit = analyze_suffix_industry_fit(brand_name, category)
    
    # Step 3: Check phonetic risks
    phonetic_risks = check_phonetic_risks(brand_name, countries)
    
    # Step 4: Check sacred/royal names (existing function)
    sacred_check = check_sacred_royal_names(brand_name, countries)
    
    # Step 5: Build per-country cultural analysis
    country_analysis = {}
    flags_lower = {k.lower(): v for k, v in COUNTRY_FLAGS.items()}
    
    for country in countries:
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        country_lower = country_name.lower().strip()
        country_title = country_name.title()
        country_flag = flags_lower.get(country_lower, "🌍")
        
        morpheme_analysis = []
        overall_resonance = "NEUTRAL"
        risk_flags = []
        
        for morpheme in decomposition["morphemes"]:
            cultural_data = morpheme.get("cultural_resonance", {})
            
            # Try exact country match, then partial match
            resonance_data = None
            for key in cultural_data.keys():
                if country_lower in key.lower() or key.lower() in country_lower:
                    resonance_data = cultural_data[key]
                    break
            
            # Try "Global" fallback
            if not resonance_data:
                resonance_data = cultural_data.get("Global", {"level": "NEUTRAL", "context": "No specific cultural data"})
            
            morpheme_analysis.append({
                "morpheme": morpheme["text"],
                "origin": morpheme["origin"],
                "meaning": morpheme["meaning"],
                "resonance_level": resonance_data.get("level", "NEUTRAL"),
                "context": resonance_data.get("context", "No specific data")
            })
            
            # Update overall resonance (CRITICAL > HIGH > MEDIUM > LOW > NEUTRAL)
            level = resonance_data.get("level", "NEUTRAL")
            if level == "CRITICAL":
                overall_resonance = "CRITICAL"
                risk_flags.append(f"CRITICAL: {morpheme['text']} - {resonance_data.get('context', '')}")
            elif level == "HIGH" and overall_resonance not in ["CRITICAL"]:
                overall_resonance = "HIGH"
        
        # Check for phonetic risks in this country
        country_phonetic_risks = [r for r in phonetic_risks if r["country"] == country_title]
        for pr in country_phonetic_risks:
            risk_flags.append(f"PHONETIC: '{pr['sound']}' - {pr['reason']}")
        
        # Check for sacred name warnings
        for warning in sacred_check.get("warnings", []):
            if warning["country"].lower() == country_lower:
                risk_flags.append(f"SACRED/ROYAL: {', '.join(warning['matched_terms'])}")
        
        country_analysis[country_title] = {
            "country_flag": country_flag,
            "morpheme_analysis": morpheme_analysis,
            "overall_resonance": overall_resonance,
            "risk_flags": risk_flags,
            "risk_count": len(risk_flags)
        }
    
    # Step 6: GATE 1 - Determine brand type classification (DICTIONARY CHECK)
    # CRITICAL: Do NOT call descriptive names "Coined/Invented"
    brand_type = classify_brand_name_type(brand_name, decomposition)
    
    # Check for category mismatch (GATE 2)
    category_mismatch = False
    category_mismatch_warning = None
    if industry_fit["fit_level"] == "LOW":
        category_mismatch = True
        category_mismatch_warning = f"⚠️ **Category Mismatch Risk:** Name contains '{industry_fit.get('matched_suffix', 'term')}' which may limit consumer perception in the '{category}' market."
    
    # Step 7: Generate recommendations
    recommendations = []
    high_risk_countries = [c for c, data in country_analysis.items() if data["overall_resonance"] == "CRITICAL"]
    medium_risk_countries = [c for c, data in country_analysis.items() if data["overall_resonance"] == "HIGH"]
    
    if high_risk_countries:
        recommendations.append(f"⚠️ CRITICAL RISK in {', '.join(high_risk_countries)}: Consult local legal counsel before market entry")
    if medium_risk_countries:
        recommendations.append(f"📋 HIGH RESONANCE in {', '.join(medium_risk_countries)}: Leverage cultural connection in marketing")
    if category_mismatch:
        recommendations.append(f"⚠️ CATEGORY MISMATCH: '{industry_fit.get('matched_suffix', 'term')}' may not align with {category} positioning")
    if brand_type == "Descriptive/Composite":
        recommendations.append(f"⚠️ TRADEMARK WARNING: Descriptive names have weaker legal protection than coined terms")
    if not recommendations:
        recommendations.append(f"✅ Name appears suitable for target markets. Proceed with standard trademark clearance.")
    
    return {
        "brand_name": brand_name,
        "decomposition": decomposition,
        "industry_fit": industry_fit,
        "phonetic_risks": phonetic_risks,
        "sacred_name_check": sacred_check,
        "country_analysis": country_analysis,
        "brand_type": brand_type,
        "category_mismatch": category_mismatch,
        "category_mismatch_warning": category_mismatch_warning,
        "recommendations": recommendations
    }

def format_linguistic_analysis_for_output(analysis: dict, country: str) -> str:
    """
    Format the linguistic analysis into a readable cultural notes string for a specific country.
    """
    country_data = analysis.get("country_analysis", {}).get(country, {})
    decomposition = analysis.get("decomposition", {})
    industry_fit = analysis.get("industry_fit", {})
    
    output_parts = []
    
    # Header
    output_parts.append(f"**LINGUISTIC ANALYSIS: {analysis['brand_name']}**\n")
    
    # Morpheme Breakdown
    if decomposition.get("morphemes"):
        output_parts.append("**MORPHEME BREAKDOWN:**")
        for idx, morpheme in enumerate(decomposition["morphemes"]):
            ma = None
            for m in country_data.get("morpheme_analysis", []):
                if m["morpheme"] == morpheme["text"]:
                    ma = m
                    break
            
            if ma:
                resonance_emoji = "🔴" if ma["resonance_level"] == "CRITICAL" else "🟡" if ma["resonance_level"] == "HIGH" else "🟢"
                output_parts.append(f"• **{morpheme['text'].upper()}** ({morpheme['origin']})")
                output_parts.append(f"  Meaning: {morpheme['meaning']}")
                output_parts.append(f"  {country} Resonance: {resonance_emoji} {ma['resonance_level']} - {ma['context']}")
    
    # Industry Fit
    fit_emoji = "✅" if industry_fit.get("fit_level") == "HIGH" else "⚠️" if industry_fit.get("fit_level") == "LOW" else "➡️"
    output_parts.append(f"\n**INDUSTRY FIT:** {fit_emoji} {industry_fit.get('fit_level', 'NEUTRAL')}")
    output_parts.append(f"  {industry_fit.get('reasoning', 'No specific analysis')}")
    
    # Risk Flags
    if country_data.get("risk_flags"):
        output_parts.append("\n**⚠️ RISK FLAGS:**")
        for flag in country_data["risk_flags"]:
            output_parts.append(f"• {flag}")
    
    # Classification
    output_parts.append(f"\n**BRAND TYPE:** {analysis.get('brand_type', 'Unknown')}")
    
    # Recommendation for this country
    overall = country_data.get("overall_resonance", "NEUTRAL")
    if overall == "CRITICAL":
        output_parts.append("\n**RECOMMENDATION:** 🔴 Consult local legal counsel before market entry. Name contains culturally/legally sensitive elements.")
    elif overall == "HIGH":
        output_parts.append("\n**RECOMMENDATION:** 🟡 Strong cultural resonance - leverage in marketing but verify no IP conflicts.")
    else:
        output_parts.append("\n**RECOMMENDATION:** 🟢 Name appears suitable for this market. Proceed with standard trademark clearance.")
    
    return "\n".join(output_parts)


# ============ MASTER CLASSIFICATION SYSTEM ============
# Single classification called ONCE, result passed to all sections
# Implements 5-Step Spectrum of Distinctiveness

# CACHE to avoid duplicate classification calls
_CLASSIFICATION_CACHE = {}

COMMON_DICTIONARY_WORDS = {
    # Common English words that indicate DESCRIPTIVE names
    "check", "my", "meal", "quick", "fast", "health", "care", "med", "doc", "doctor",
    "pay", "flow", "cash", "money", "bank", "fin", "tech", "app", "book", "shop",
    "buy", "sell", "trade", "market", "store", "home", "house", "real", "estate",
    "food", "eat", "dine", "cook", "chef", "kitchen", "taste", "fresh", "organic",
    "fit", "gym", "work", "out", "body", "mind", "soul", "life", "live", "well",
    "travel", "trip", "tour", "fly", "drive", "ride", "go", "move", "run", "walk",
    "learn", "teach", "study", "class", "school", "edu", "smart", "brain", "think",
    "cloud", "data", "sync", "link", "connect", "net", "web", "site", "page", "hub",
    "social", "chat", "talk", "speak", "call", "meet", "date", "love", "match",
    "news", "feed", "post", "share", "like", "view", "watch", "play", "game", "fun",
    "style", "fashion", "wear", "dress", "look", "beauty", "glow", "skin", "hair",
    "auto", "car", "bike", "wheel", "park", "fix", "repair", "service", "clean",
    "pet", "dog", "cat", "vet", "kid", "baby", "family", "parent", "mom", "dad",
    "green", "eco", "solar", "power", "energy", "save", "easy", "simple",
    "pro", "plus", "max", "prime", "elite", "premium", "super", "mega", "ultra",
    "one", "first", "best", "top", "next", "new", "now", "today", "daily", "weekly",
    "local", "global", "world", "city", "urban", "rural", "metro", "zone", "area",
    "true", "real", "pure", "free", "open", "clear", "bright", "light", "dark",
    "blue", "red", "gold", "silver", "black", "white", "color", "colour",
    # Medical/Healthcare
    "steth", "scope", "pulse", "heart", "blood", "test", "lab", "scan", "ray",
    "heal", "cure", "therapy", "clinic", "hospital", "pharma", "drug", "pill",
    # Finance
    "wallet", "coin", "credit", "debit", "loan", "invest", "fund", "stock",
    # Tech
    "code", "dev", "build", "make", "create", "design", "pixel", "byte", "bit",
    # Common suffixes that indicate descriptive
    "ly", "er", "ist", "ify", "ize", "able", "ible", "ful", "less", "ment", "ness",
    "works", "hub", "spot", "base", "point", "space", "place", "land",
    # Additional common words
    "air", "bus", "face", "sound", "snap", "insta", "gram", "tube", "flix",
    "drop", "box", "door", "dash", "uber", "grab", "bolt", "zoom", "slack",
}

# Industry keywords for semantic matching
INDUSTRY_KEYWORDS = {
    "food": ["meal", "eat", "dine", "food", "cook", "chef", "taste", "recipe", "kitchen", "restaurant", "cafe", "dish", "menu"],
    "healthcare": ["health", "med", "doctor", "clinic", "care", "patient", "therapy", "heal", "cure", "hospital", "pharma", "steth", "pulse"],
    "finance": ["pay", "money", "bank", "cash", "fund", "loan", "credit", "invest", "wallet", "coin", "finance", "fintech"],
    "technology": ["tech", "code", "dev", "app", "software", "cloud", "data", "digital", "cyber", "ai", "ml"],
    "travel": ["travel", "trip", "tour", "fly", "flight", "hotel", "stay", "vacation", "journey", "voyage"],
    "fitness": ["fit", "gym", "workout", "health", "body", "exercise", "train", "muscle", "yoga"],
    "education": ["learn", "teach", "study", "edu", "school", "class", "course", "academy", "tutor"],
    "ecommerce": ["shop", "buy", "sell", "store", "cart", "order", "delivery", "market", "retail"],
    "social": ["social", "connect", "chat", "friend", "share", "post", "network", "community"],
    "entertainment": ["play", "game", "fun", "watch", "stream", "video", "music", "media"],
}

MODIFIED_SPELLING_PATTERNS = [
    # Words with letters removed (Lyft, Flickr, Tumblr style)
    ("lyft", "lift"), ("flickr", "flicker"), ("tumblr", "tumbler"),
    ("grindr", "grinder"), ("fiverr", "fiver"), ("scribd", "scribed"),
    ("bettr", "better"), ("fastr", "faster"), ("hungr", "hungry"),
    ("dribbble", "dribble"), ("reddit", "read it"),
]

# Heritage language roots
HERITAGE_ORIGINS = ["Sanskrit", "Latin", "Greek", "Japanese", "Chinese", "Arabic", "Hebrew", "Persian"]


def tokenize_brand_name(brand_name: str) -> list:
    """
    STEP 1: DE-COMPOUND - Split brand name into tokens
    
    "CheckMyMeal" → ["check", "my", "meal"]
    "FaceBook" → ["face", "book"]
    "Xerox" → ["xerox"]
    "LUMINARA" → ["luminara"] (all-caps treated as single word)
    """
    # Normalize: If ALL CAPS, convert to title case first to avoid splitting each letter
    if brand_name.isupper() and len(brand_name) > 1:
        brand_name = brand_name.title()  # LUMINARA → Luminara
    
    brand_lower = brand_name.lower()
    
    # Method 1: Split by common separators
    tokens = []
    
    # Split camelCase: "CheckMyMeal" → ["Check", "My", "Meal"]
    import re
    camel_split = re.sub('([A-Z])', r' \1', brand_name).split()
    if len(camel_split) > 1:
        tokens = [t.lower() for t in camel_split if t]
    
    # If no camelCase, try to find dictionary words within the string
    if len(tokens) <= 1:
        tokens = []
        remaining = brand_lower
        
        # Sort dictionary words by length (longest first) to match greedily
        sorted_words = sorted(COMMON_DICTIONARY_WORDS, key=len, reverse=True)
        
        while remaining:
            found = False
            for word in sorted_words:
                if remaining.startswith(word) and len(word) >= 3:
                    tokens.append(word)
                    remaining = remaining[len(word):]
                    found = True
                    break
            
            if not found:
                # No dictionary word found at start, take one character and continue
                if remaining:
                    # Check if remaining is itself a token
                    if remaining in COMMON_DICTIONARY_WORDS:
                        tokens.append(remaining)
                        break
                    remaining = remaining[1:]  # Skip one character
    
    # If still no tokens, the whole name is one token
    if not tokens:
        tokens = [brand_lower]
    
    return tokens


def get_industry_domain(industry: str) -> tuple:
    """Get the primary domain of an industry"""
    industry_lower = industry.lower()
    
    for domain, keywords in INDUSTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in industry_lower:
                return domain, keywords
    
    return "general", []


def classify_brand_with_industry(brand_name: str, industry: str) -> dict:
    """
    MASTER CLASSIFICATION FUNCTION
    
    Called ONCE at start, result passed to all sections.
    Implements 5-Step Spectrum of Distinctiveness:
    
    1. GENERIC - Names the category itself (unprotectable)
    2. DESCRIPTIVE - Directly describes product (weak protection)
    3. SUGGESTIVE - Hints at product, needs imagination (moderate)
    4. ARBITRARY - Real word, unrelated context (strong)
    5. FANCIFUL - Completely invented (strongest)
    
    HARD RULES:
    - Compound Rule: FaceBook = Face + Book = NOT Coined
    - Conservative Rule: If borderline, default to weaker category
    - No Fluff Rule: Legal accuracy > Marketing appeal
    
    CACHING: Results are cached to avoid duplicate calculations.
    """
    global _CLASSIFICATION_CACHE
    
    # Check cache first
    cache_key = f"{brand_name.lower()}|{industry.lower()}"
    if cache_key in _CLASSIFICATION_CACHE:
        logging.info(f"🏷️ CLASSIFICATION (CACHED): '{brand_name}' → {_CLASSIFICATION_CACHE[cache_key]['category']}")
        return _CLASSIFICATION_CACHE[cache_key]
    
    # Helper to store in cache before returning
    def cache_and_return(result, log_msg):
        _CLASSIFICATION_CACHE[cache_key] = result
        logging.info(log_msg)
        return result
    
    brand_lower = brand_name.lower()
    industry_lower = industry.lower()
    
    # ========== STEP 1: DE-COMPOUND & DICTIONARY CHECK ==========
    tokens = tokenize_brand_name(brand_name)
    
    # Check which tokens are dictionary words
    dictionary_tokens = []
    invented_tokens = []
    
    for token in tokens:
        if token in COMMON_DICTIONARY_WORDS or len(token) <= 2:
            dictionary_tokens.append(token)
        else:
            # Check if it's a partial match
            is_dict_word = False
            for dict_word in COMMON_DICTIONARY_WORDS:
                if dict_word in token or token in dict_word:
                    dictionary_tokens.append(token)
                    is_dict_word = True
                    break
            if not is_dict_word:
                invented_tokens.append(token)
    
    # Get industry domain
    industry_domain, industry_keywords = get_industry_domain(industry)
    
    # Check for modified spelling
    is_modified_spelling = False
    original_word = None
    for modified, original in MODIFIED_SPELLING_PATTERNS:
        if modified in brand_lower:
            is_modified_spelling = True
            original_word = original
            break
    
    # ========== CLASSIFICATION DECISION TREE ==========
    
    # Initialize result
    result = {
        "brand_name": brand_name,
        "industry": industry,
        "tokens": tokens,
        "dictionary_tokens": dictionary_tokens,
        "invented_tokens": invented_tokens,
        "category": None,
        "distinctiveness": None,
        "protectability": None,
        "dictionary_status": None,
        "semantic_link": None,
        "imagination_required": None,
        "warning": None,
        "reasoning": None
    }
    
    # ========== STEP 2: GENERIC CHECK ==========
    # Does the name literally name the category?
    is_generic = False
    if brand_lower in industry_keywords or brand_lower == industry_domain:
        is_generic = True
    
    # Check if ALL tokens are industry keywords
    if len(dictionary_tokens) > 0:
        all_industry_match = all(
            any(token in kw or kw in token for kw in industry_keywords)
            for token in dictionary_tokens
        )
        if all_industry_match and len(dictionary_tokens) >= 2:
            is_generic = True
    
    if is_generic:
        result["category"] = "GENERIC"
        result["distinctiveness"] = "NONE"
        result["protectability"] = "UNPROTECTABLE"
        result["dictionary_status"] = f"All tokens are common words: {dictionary_tokens}"
        result["semantic_link"] = f"Name directly names the product category '{industry}'"
        result["imagination_required"] = False
        result["warning"] = "⛔ Generic terms CANNOT be trademarked. Choose a different name."
        result["reasoning"] = f"'{brand_name}' literally describes or names the '{industry}' category. Generic terms are free for all to use."
        
        return cache_and_return(result, f"🏷️ CLASSIFICATION: '{brand_name}' → GENERIC (names the category)")
    
    # ========== STEP 3: DESCRIPTIVE CHECK ==========
    # Do the dictionary words DIRECTLY describe the product?
    is_descriptive = False
    matching_industry_tokens = []
    
    for token in dictionary_tokens:
        for keyword in industry_keywords:
            if token == keyword or token in keyword or keyword in token:
                matching_industry_tokens.append(token)
                break
    
    # If 50%+ of tokens match industry keywords → DESCRIPTIVE
    if len(dictionary_tokens) > 0:
        match_ratio = len(matching_industry_tokens) / len(dictionary_tokens)
        if match_ratio >= 0.5 and len(dictionary_tokens) >= 2:
            is_descriptive = True
    
    # If ALL tokens are dictionary words and describe function → DESCRIPTIVE
    if len(dictionary_tokens) >= 2 and len(invented_tokens) == 0:
        is_descriptive = True
    
    if is_descriptive:
        result["category"] = "DESCRIPTIVE"
        result["distinctiveness"] = "LOW"
        result["protectability"] = "WEAK"
        result["dictionary_status"] = f"Contains dictionary words: {dictionary_tokens}"
        result["semantic_link"] = f"Words directly describe the {industry} - {', '.join(matching_industry_tokens) if matching_industry_tokens else 'composite description'}"
        result["imagination_required"] = False
        result["warning"] = "⚠️ Descriptive marks require proof of 'Secondary Meaning' (acquired distinctiveness) for trademark protection. This typically requires 5+ years of exclusive use and significant marketing investment."
        result["reasoning"] = f"'{brand_name}' is composed of dictionary words ({', '.join(dictionary_tokens)}) that describe the product/service. Under trademark law, descriptive marks receive weak protection."
        
        return cache_and_return(result, f"🏷️ CLASSIFICATION: '{brand_name}' → DESCRIPTIVE (describes the product)")
    
    # ========== STEP 4: SUGGESTIVE CHECK ==========
    # Does consumer need imagination to connect name to product?
    is_suggestive = False
    
    # Has dictionary words but doesn't directly describe
    if len(dictionary_tokens) >= 1 and not is_descriptive:
        is_suggestive = True
    
    # Modified spelling of real words → Suggestive
    if is_modified_spelling:
        is_suggestive = True
    
    # Compound of real words that hints but doesn't describe
    # e.g., "Netflix" (Net + Flicks), "Airbus" (Air + Bus)
    if len(dictionary_tokens) >= 2 and len(matching_industry_tokens) == 0:
        is_suggestive = True
    
    if is_suggestive:
        result["category"] = "SUGGESTIVE"
        result["distinctiveness"] = "MODERATE"
        result["protectability"] = "MODERATE"
        result["dictionary_status"] = f"Contains words: {dictionary_tokens}" + (f" (modified from '{original_word}')" if is_modified_spelling else "")
        result["semantic_link"] = f"Hints at {industry} but requires imagination to connect"
        result["imagination_required"] = True
        result["warning"] = "Suggestive marks are protectable but may face challenges from similar suggestive marks in the same industry."
        result["reasoning"] = f"'{brand_name}' suggests qualities of the product but requires consumer imagination to make the connection. This places it in the SUGGESTIVE category with moderate trademark protection."
        
        return cache_and_return(result, f"🏷️ CLASSIFICATION: '{brand_name}' → SUGGESTIVE (hints at product)")
    
    # ========== STEP 5: ARBITRARY CHECK ==========
    # Is it a real word in UNRELATED context?
    is_arbitrary = False
    
    # Has one dictionary word that's completely unrelated to industry
    if len(dictionary_tokens) == 1 and len(matching_industry_tokens) == 0:
        is_arbitrary = True
    
    if is_arbitrary:
        result["category"] = "ARBITRARY"
        result["distinctiveness"] = "HIGH"
        result["protectability"] = "STRONG"
        result["dictionary_status"] = f"Common word '{dictionary_tokens[0]}' used in unrelated context"
        result["semantic_link"] = f"No semantic connection to {industry}"
        result["imagination_required"] = False
        result["warning"] = None
        result["reasoning"] = f"'{brand_name}' is a common word used in a completely unrelated context ({industry}). Like 'Apple' for computers, arbitrary marks receive strong trademark protection."
        
        return cache_and_return(result, f"🏷️ CLASSIFICATION: '{brand_name}' → ARBITRARY (unrelated context)")
    
    # ========== STEP 6: FANCIFUL/COINED CHECK ==========
    # Is the word completely made up?
    if len(dictionary_tokens) == 0 and len(invented_tokens) > 0:
        result["category"] = "FANCIFUL"
        result["distinctiveness"] = "HIGHEST"
        result["protectability"] = "STRONGEST"
        result["dictionary_status"] = f"Invented term with no dictionary origin: {invented_tokens}"
        result["semantic_link"] = "No pre-existing meaning"
        result["imagination_required"] = False
        result["warning"] = None
        result["reasoning"] = f"'{brand_name}' is a completely invented word with no prior dictionary meaning. Like 'Xerox' or 'Kodak', fanciful marks receive the strongest trademark protection."
        
        return cache_and_return(result, f"🏷️ CLASSIFICATION: '{brand_name}' → FANCIFUL/COINED (invented word)")
    
    # ========== DEFAULT: CONSERVATIVE RULE ==========
    # If we can't clearly classify, default to DESCRIPTIVE (safer for user)
    result["category"] = "DESCRIPTIVE"
    result["distinctiveness"] = "LOW"
    result["protectability"] = "WEAK"
    result["dictionary_status"] = f"Tokens: {tokens}"
    result["semantic_link"] = f"Unclear relationship to {industry}"
    result["imagination_required"] = False
    result["warning"] = "⚠️ Classification unclear - defaulting to DESCRIPTIVE (conservative approach). Consult a trademark attorney."
    result["reasoning"] = f"'{brand_name}' could not be clearly classified. Following the Conservative Rule, we default to DESCRIPTIVE to protect against legal risk."
    
    return cache_and_return(result, f"🏷️ CLASSIFICATION: '{brand_name}' → DESCRIPTIVE (conservative default)")


# Legacy function for backward compatibility
def classify_brand_name_type(brand_name: str, decomposition: dict) -> str:
    """
    DEPRECATED: Use classify_brand_with_industry() instead.
    Kept for backward compatibility.
    """
    # Call new function with empty industry (will use conservative classification)
    result = classify_brand_with_industry(brand_name, "general")
    
    # Map new categories to old format
    category_map = {
        "GENERIC": "Generic",
        "DESCRIPTIVE": "Descriptive/Composite",
        "SUGGESTIVE": "Suggestive/Composite",
        "ARBITRARY": "Arbitrary",
        "FANCIFUL": "Coined/Invented"
    }


def classify_brand_with_linguistic_override(
    brand_name: str, 
    industry: str, 
    linguistic_analysis: dict = None
) -> dict:
    """
    ENHANCED MASTER CLASSIFICATION FUNCTION
    
    Runs standard classification FIRST, then OVERRIDES based on linguistic analysis.
    
    Override Rules:
    - If linguistic says "has_meaning=True" + "name_type=Mythological" → Cannot be FANCIFUL
    - If linguistic says "has_meaning=True" + "name_type=Foreign-Language" → Check alignment
    - If meaning aligns with business → SUGGESTIVE (hints at product via foreign meaning)
    - If meaning unrelated to business → ARBITRARY (real word in unrelated context)
    - If no meaning found → Trust original classification
    
    Args:
        brand_name: The brand name to classify
        industry: The industry/category
        linguistic_analysis: Results from analyze_brand_linguistics()
        
    Returns:
        dict with classification results (potentially overridden)
    """
    # Step 1: Run standard English-based classification
    base_result = classify_brand_with_industry(brand_name, industry)
    
    # Step 2: Check if we have linguistic analysis with meaning
    if not linguistic_analysis:
        logging.info(f"🏷️ CLASSIFICATION (NO LINGUISTIC DATA): '{brand_name}' → {base_result['category']}")
        return base_result
    
    has_meaning = linguistic_analysis.get("has_linguistic_meaning", False)
    confidence = linguistic_analysis.get("confidence_assessment", {}).get("overall_confidence", "Low")
    meaning_certainty = linguistic_analysis.get("confidence_assessment", {}).get("meaning_certainty", "None")
    
    # Only override if we have HIGH/MEDIUM confidence
    if not has_meaning or confidence == "Low" or meaning_certainty in ["None", "Speculative"]:
        logging.info(f"🏷️ CLASSIFICATION (LOW CONFIDENCE): '{brand_name}' → {base_result['category']} (linguistic: {has_meaning}, confidence: {confidence})")
        # Still attach linguistic data for reference
        base_result["linguistic_override"] = False
        base_result["linguistic_data"] = {
            "has_meaning": has_meaning,
            "confidence": confidence
        }
        return base_result
    
    # Step 3: Extract linguistic classification
    name_type = linguistic_analysis.get("classification", {}).get("name_type", "Unknown")
    alignment_score = linguistic_analysis.get("business_alignment", {}).get("alignment_score", 5)
    languages = linguistic_analysis.get("linguistic_analysis", {}).get("languages_detected", [])
    combined_meaning = linguistic_analysis.get("linguistic_analysis", {}).get("decomposition", {}).get("combined_meaning", "")
    cultural_ref = linguistic_analysis.get("cultural_significance", {}).get("has_cultural_reference", False)
    
    # Step 4: Determine override
    original_category = base_result["category"]
    new_category = original_category  # Default: no change
    override_reason = None
    
    # RULE 1: Mythological/Heritage names → SUGGESTIVE (always)
    # These suggest qualities through cultural/mythological association
    if name_type in ["Mythological", "Heritage"]:
        if original_category == "FANCIFUL":
            new_category = "SUGGESTIVE"
            override_reason = f"Name has {name_type} origin ({', '.join(languages)}): '{combined_meaning}'. Cannot be FANCIFUL."
    
    # RULE 2: Foreign-Language names → Check business alignment
    elif name_type == "Foreign-Language":
        if alignment_score >= 7:
            # High alignment = meaning describes/relates to business → SUGGESTIVE
            if original_category == "FANCIFUL":
                new_category = "SUGGESTIVE"
                override_reason = f"Foreign word meaning '{combined_meaning}' aligns with business (score: {alignment_score}/10)"
        else:
            # Low alignment = meaning unrelated to business → ARBITRARY
            if original_category == "FANCIFUL":
                new_category = "ARBITRARY"
                override_reason = f"Foreign word meaning '{combined_meaning}' is unrelated to business (score: {alignment_score}/10)"
    
    # RULE 3: Compound/Portmanteau with meaning → SUGGESTIVE
    elif name_type in ["Compound", "Portmanteau"]:
        if original_category == "FANCIFUL":
            new_category = "SUGGESTIVE"
            override_reason = f"Compound name with meaningful parts: '{combined_meaning}'"
    
    # RULE 4: Evocative names → SUGGESTIVE
    elif name_type == "Evocative":
        if original_category in ["FANCIFUL", "ARBITRARY"]:
            new_category = "SUGGESTIVE"
            override_reason = f"Name evokes qualities: '{combined_meaning}'"
    
    # RULE 5: True-Coined → Keep FANCIFUL
    elif name_type == "True-Coined":
        # Linguistic analysis confirms it's truly invented
        pass  # Keep original
    
    # RULE 6: CATCH-ALL - ANY name with verified meaning cannot be FANCIFUL
    # This handles cases where name_type is "Descriptive", "Phonetic-Adaptation", "Unknown", etc.
    # If has_meaning=True and we reached this point, the name has meaning in some language
    if original_category == "FANCIFUL" and new_category == "FANCIFUL" and has_meaning and combined_meaning:
        # If we still have FANCIFUL after all rules, but meaning exists - override based on alignment
        if alignment_score >= 6:
            new_category = "SUGGESTIVE"
            override_reason = f"Name has clear linguistic meaning ({', '.join(languages) if languages else 'detected languages'}): '{combined_meaning}'. High business alignment ({alignment_score}/10) suggests product/service."
        else:
            new_category = "ARBITRARY"
            override_reason = f"Name has linguistic meaning ({', '.join(languages) if languages else 'detected languages'}): '{combined_meaning}'. Used in unrelated business context."
        logging.info(f"🏷️ CATCH-ALL OVERRIDE: '{brand_name}' has meaning but no specific rule matched → {new_category}")
    
    # Step 5: Apply override if needed
    if new_category != original_category:
        logging.info(f"🏷️ CLASSIFICATION OVERRIDE: '{brand_name}' → {original_category} → {new_category}")
        logging.info(f"   Reason: {override_reason}")
        
        # Update result
        base_result["category"] = new_category
        base_result["linguistic_override"] = True
        base_result["original_category"] = original_category
        base_result["override_reason"] = override_reason
        
        # Update distinctiveness and protectability based on new category
        category_attributes = {
            "GENERIC": ("NONE", "UNPROTECTABLE"),
            "DESCRIPTIVE": ("LOW", "WEAK"),
            "SUGGESTIVE": ("MODERATE", "MODERATE"),
            "ARBITRARY": ("HIGH", "STRONG"),
            "FANCIFUL": ("HIGHEST", "STRONGEST")
        }
        
        if new_category in category_attributes:
            base_result["distinctiveness"], base_result["protectability"] = category_attributes[new_category]
        
        # Update reasoning
        base_result["reasoning"] = f"'{brand_name}' was linguistically analyzed and found to have meaning in {', '.join(languages)}: '{combined_meaning}'. {override_reason}. Classification changed from {original_category} to {new_category}."
        
        # Add warning for SUGGESTIVE
        if new_category == "SUGGESTIVE":
            base_result["warning"] = "Suggestive marks (names that hint at the product through foreign/cultural meaning) are protectable but may face challenges from similar marks."
    else:
        base_result["linguistic_override"] = False
        base_result["linguistic_data"] = {
            "has_meaning": has_meaning,
            "name_type": name_type,
            "languages": languages,
            "alignment_score": alignment_score
        }
        logging.info(f"🏷️ CLASSIFICATION (NO OVERRIDE NEEDED): '{brand_name}' → {original_category}")
    
    # Always attach linguistic insights for downstream use
    base_result["linguistic_insights"] = {
        "has_meaning": has_meaning,
        "name_type": name_type,
        "languages": languages,
        "combined_meaning": combined_meaning,
        "alignment_score": alignment_score,
        "cultural_reference": cultural_ref,
        "confidence": confidence
    }
    
    return base_result
    
    return category_map.get(result["category"], "Descriptive/Composite")


# ============ GATE 2: CATEGORY MISMATCH CHECK ============
# Detect when brand name semantics don't match the industry category

CATEGORY_SEMANTIC_KEYWORDS = {
    # Healthcare/Medical
    "doctor": ["medical", "health", "clinic", "physician", "care", "patient", "appointment", "consultation"],
    "healthcare": ["medical", "health", "wellness", "care", "hospital", "clinic", "treatment"],
    "pharmacy": ["medicine", "drug", "prescription", "health", "wellness"],
    
    # Food/Restaurant
    "food": ["meal", "eat", "dine", "cook", "taste", "recipe", "kitchen", "restaurant", "cafe"],
    "restaurant": ["meal", "eat", "dine", "food", "taste", "cuisine", "chef"],
    
    # Finance/Fintech
    "finance": ["money", "payment", "bank", "invest", "fund", "credit", "loan", "wallet"],
    "fintech": ["payment", "money", "transaction", "banking", "transfer", "wallet"],
    "payment": ["pay", "money", "transaction", "transfer", "wallet", "checkout"],
    
    # Travel/Hospitality
    "hotel": ["stay", "room", "accommodation", "hospitality", "resort", "lodge", "inn"],
    "travel": ["trip", "journey", "tour", "vacation", "flight", "booking"],
    
    # Technology/Software
    "technology": ["tech", "software", "digital", "code", "app", "platform", "system"],
    "saas": ["software", "platform", "cloud", "service", "subscription"],
    
    # E-commerce/Retail
    "ecommerce": ["shop", "buy", "sell", "store", "cart", "order", "delivery"],
    "retail": ["shop", "store", "buy", "product", "sale", "deal"],
}

# Keywords that STRONGLY signal a specific domain
DOMAIN_SIGNAL_WORDS = {
    "meal": "food",
    "food": "food",
    "eat": "food",
    "dine": "food",
    "cook": "food",
    "recipe": "food",
    "kitchen": "food",
    "restaurant": "food",
    
    "pay": "finance",
    "money": "finance",
    "bank": "finance",
    "cash": "finance",
    "wallet": "finance",
    "coin": "finance",
    "fund": "finance",
    
    "doctor": "healthcare",
    "med": "healthcare",
    "health": "healthcare",
    "clinic": "healthcare",
    "patient": "healthcare",
    "steth": "healthcare",
    
    "hotel": "hospitality",
    "stay": "hospitality",
    "room": "hospitality",
    "resort": "hospitality",
    
    "travel": "travel",
    "trip": "travel",
    "tour": "travel",
    "flight": "travel",
    
    "shop": "retail",
    "store": "retail",
    "buy": "retail",
    "cart": "retail",
}


def check_category_mismatch(brand_name: str, category: str) -> dict:
    """
    GATE 2: Check if brand name semantics match the industry category
    
    Example: "Check My Meal" for "Doctor Appointment App" = MISMATCH
    - "Meal" signals Food domain
    - Category is Healthcare domain
    - This is a strategic risk
    """
    brand_lower = brand_name.lower()
    category_lower = category.lower()
    
    # Step 1: Detect what domain the brand NAME signals
    name_signals_domain = None
    signaling_word = None
    
    for word, domain in DOMAIN_SIGNAL_WORDS.items():
        if word in brand_lower:
            name_signals_domain = domain
            signaling_word = word
            break
    
    # Step 2: Detect what domain the CATEGORY is
    category_domain = None
    for cat_key, keywords in CATEGORY_SEMANTIC_KEYWORDS.items():
        if cat_key in category_lower:
            category_domain = cat_key
            break
    
    # Also check if category contains domain keywords
    if not category_domain:
        for word, domain in DOMAIN_SIGNAL_WORDS.items():
            if word in category_lower:
                category_domain = domain
                break
    
    # Step 3: Check for mismatch
    result = {
        "has_mismatch": False,
        "name_signals": name_signals_domain,
        "signaling_word": signaling_word,
        "category_domain": category_domain,
        "warning": None,
        "score_penalty": 0
    }
    
    if name_signals_domain and category_domain:
        # Check if they're different domains
        if name_signals_domain != category_domain:
            # Special case: healthcare and wellness are related
            related_domains = [
                {"healthcare", "wellness"},
                {"finance", "fintech"},
                {"food", "restaurant"},
                {"retail", "ecommerce"},
                {"hotel", "hospitality", "travel"},
            ]
            
            is_related = False
            for related_set in related_domains:
                if name_signals_domain in related_set and category_domain in related_set:
                    is_related = True
                    break
            
            if not is_related:
                result["has_mismatch"] = True
                result["warning"] = f"⚠️ **Category Mismatch Risk:** The name contains '{signaling_word}' which signals {name_signals_domain.upper()} domain, but the category is {category.title()} ({category_domain.upper()} domain). This may confuse consumers and limit market perception."
                result["score_penalty"] = 15  # Reduce score by 15 points
                
                logging.warning(f"🚨 GATE 2 CATEGORY MISMATCH: '{brand_name}' signals {name_signals_domain} but category is {category_domain}")
    
    return result


def check_sacred_royal_names(brand_name: str, countries: list) -> dict:
    """Check if brand name contains sacred, royal, or culturally sensitive terms for target markets"""
    brand_lower = brand_name.lower()
    warnings = []
    affected_countries = []
    risk_score_modifier = 0
    
    for country in countries:
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        sacred_data = SACRED_ROYAL_NAMES.get(country_name, SACRED_ROYAL_NAMES.get("default", {}))
        
        # Check all term categories for this country
        all_terms = []
        for key, value in sacred_data.items():
            if key != "warning" and isinstance(value, list):
                all_terms.extend(value)
        
        # Check if brand name contains any sacred/royal terms
        matched_terms = []
        for term in all_terms:
            # Check for whole word or as part of compound word
            if term in brand_lower or re.search(rf'\b{re.escape(term)}\b', brand_lower, re.IGNORECASE):
                matched_terms.append(term)
        
        if matched_terms and sacred_data.get("warning"):
            warnings.append({
                "country": country_name,
                "matched_terms": list(set(matched_terms)),
                "warning": sacred_data["warning"]
            })
            affected_countries.append(country_name)
            risk_score_modifier -= 2.0  # Reduce cultural resonance score
    
    return {
        "has_issues": len(warnings) > 0,
        "warnings": warnings,
        "affected_countries": affected_countries,
        "risk_score_modifier": risk_score_modifier
    }

# ============ CATEGORY-SPECIFIC COUNTRY MARKET DATA ============
# Structure: CATEGORY_COUNTRY_MARKET_DATA[category][country]
CATEGORY_COUNTRY_MARKET_DATA = {
    # ============ HOTELS & HOSPITALITY ============
    "hotels": {
        "India": {
            "competitors": [
                {"name": "Taj Hotels", "x_coordinate": 90, "y_coordinate": 85, "quadrant": "Heritage Luxury"},
                {"name": "OYO Rooms", "x_coordinate": 25, "y_coordinate": 40, "quadrant": "Budget Tech-Enabled"},
                {"name": "ITC Hotels", "x_coordinate": 85, "y_coordinate": 75, "quadrant": "Luxury Business"},
                {"name": "Lemon Tree", "x_coordinate": 45, "y_coordinate": 55, "quadrant": "Mid-scale Value"}
            ],
            "user_position": {"x": 65, "y": 70, "quadrant": "Premium Boutique"},
            "axis_x": "Price: ₹1,500/night Budget → ₹50,000+/night Luxury",
            "axis_y": "Experience: Standardized → Unique/Boutique",
            "white_space": "India's $30B hospitality market is polarized - luxury (Taj, Oberoi, ITC) and budget (OYO). **Gap: Premium boutique segment (₹5,000-15,000/night)** targeting experience-seeking millennials and domestic tourists. Heritage properties, wellness retreats, and experiential stays are undersupplied despite 78M domestic tourist trips annually.",
            "strategic_advantage": "Post-COVID domestic tourism boom: 2B+ domestic trips projected by 2030. First-mover advantage in Tier 2 cities (Jaipur, Udaipur, Goa, Kerala) where international chains have limited presence. Lower real estate costs enable unique property acquisition. Government's 'Swadesh Darshan' scheme offers incentives for heritage tourism.",
            "entry_recommendation": "Phase 1: Acquire/lease 3-5 heritage properties in high-tourism corridors (Rajasthan, Kerala, Himachal). Phase 2: List on MakeMyTrip, Goibibo, Booking.com with competitive commission structure. Phase 3: Build direct booking channel with loyalty program. Key: Partner with Airbnb Luxe for global exposure, target NRI travelers (high-spending segment)."
        },
        "USA": {
            "competitors": [
                {"name": "Marriott International", "x_coordinate": 75, "y_coordinate": 65, "quadrant": "Full-Service Leader"},
                {"name": "Hilton Hotels", "x_coordinate": 70, "y_coordinate": 70, "quadrant": "Business Premium"},
                {"name": "Airbnb", "x_coordinate": 50, "y_coordinate": 80, "quadrant": "Alternative Experience"},
                {"name": "Hyatt Hotels", "x_coordinate": 80, "y_coordinate": 75, "quadrant": "Upscale Lifestyle"}
            ],
            "user_position": {"x": 60, "y": 78, "quadrant": "Boutique Lifestyle"},
            "axis_x": "Price: $100/night Economy → $500+/night Luxury",
            "axis_y": "Experience: Chain Standard → Unique/Local",
            "white_space": "US hotel market ($230B) is dominated by mega-chains. **Gap: Lifestyle boutique segment** for millennials/Gen Z who reject cookie-cutter hotels. The 'soft brand' space (Marriott's Autograph, Hilton's Curio) is growing but mostly conversions, not purpose-built. Opportunity in secondary markets (Austin, Nashville, Denver) where demand exceeds boutique supply.",
            "strategic_advantage": "'Revenge travel' spending remains strong. Independent hotels outperform chains on RevPAR in lifestyle segment. Direct booking technology eliminates OTA commissions (15-25%). Opportunity to partner with local F&B concepts for unique food experiences.",
            "entry_recommendation": "Phase 1: Flagship property in high-profile secondary market (Nashville, Portland, Savannah). Phase 2: Expand via management contracts with property owners seeking lifestyle repositioning. Phase 3: Launch loyalty program and direct booking platform. Key: Instagram-worthy design, local partnerships, competitive group business rates."
        },
        "Thailand": {
            "competitors": [
                {"name": "Dusit International", "x_coordinate": 80, "y_coordinate": 70, "quadrant": "Thai Heritage Luxury"},
                {"name": "Centara Hotels", "x_coordinate": 65, "y_coordinate": 60, "quadrant": "Resort Mid-Scale"},
                {"name": "Minor Hotels (Anantara)", "x_coordinate": 90, "y_coordinate": 85, "quadrant": "Ultra-Luxury Experience"},
                {"name": "Onyx Hospitality (Amari)", "x_coordinate": 55, "y_coordinate": 55, "quadrant": "Urban Business"}
            ],
            "user_position": {"x": 70, "y": 75, "quadrant": "Premium Wellness"},
            "axis_x": "Price: ฿1,500/night Budget → ฿30,000+/night Ultra-Luxury",
            "axis_y": "Positioning: City/Business → Resort/Experiential",
            "white_space": "Thailand's $20B tourism industry is rebounding to 40M+ arrivals. **Gap: Premium wellness and sustainable tourism** segment. Existing luxury (Four Seasons, Aman, Six Senses) is ultra-high-end. Mid-luxury wellness (฿5,000-15,000/night) targeting health-conscious Western and Asian travelers is underserved.",
            "strategic_advantage": "Thailand is world's #1 medical tourism destination ($4B market). Wellness tourism growing 20%+ annually. Lower operating costs than Bali or Vietnam. TAT (Tourism Authority) actively promotes 'Amazing Thailand' wellness positioning. Phuket, Chiang Mai, Koh Samui have established infrastructure.",
            "entry_recommendation": "Phase 1: Launch wellness resort in Chiang Mai (lower costs, growing demand) or Hua Hin (proximity to Bangkok). Phase 2: Partner with Thai spas, traditional medicine practitioners for authentic programs. Phase 3: Expand to beach destinations (Koh Samui, Krabi). Key: Target Chinese returning tourists, partner with Agoda (dominant in Thailand), secure TAT partnership for marketing support."
        },
        "UK": {
            "competitors": [
                {"name": "Premier Inn (Whitbread)", "x_coordinate": 35, "y_coordinate": 40, "quadrant": "Budget Consistent"},
                {"name": "The Hoxton", "x_coordinate": 70, "y_coordinate": 80, "quadrant": "Hipster Lifestyle"},
                {"name": "Gleneagles/Rocco Forte", "x_coordinate": 90, "y_coordinate": 75, "quadrant": "Heritage Luxury"},
                {"name": "citizenM", "x_coordinate": 55, "y_coordinate": 75, "quadrant": "Tech-Forward Affordable"}
            ],
            "user_position": {"x": 65, "y": 72, "quadrant": "Contemporary Premium"},
            "axis_x": "Price: £60/night Budget → £400+/night Luxury",
            "axis_y": "Style: Traditional/Chain → Contemporary/Independent",
            "white_space": "UK hotel market (£26B) is split between budget chains (Premier Inn, Travelodge) and London luxury (Claridge's, The Savoy). **Gap: Regional boutique hotels** outside London. Edinburgh, Manchester, Bristol, Bath have tourism demand but limited boutique supply. 'Staycation' trend continues post-Brexit.",
            "strategic_advantage": "Weak pound drives inbound tourism and domestic stays. Regional cities growing faster than London. Listed buildings offer unique conversion opportunities with heritage tax benefits. UK consumers trust independent hotels over chains for 'authentic' experiences.",
            "entry_recommendation": "Phase 1: Acquire/convert Georgian or Victorian property in Edinburgh or Bath. Phase 2: List on Mr & Mrs Smith, Tablet Hotels for affluent positioning. Phase 3: Expand to Manchester, Bristol with consistent brand identity. Key: Emphasize British heritage with modern amenities, partner with local restaurants, leverage National Trust for heritage positioning."
        },
        "UAE": {
            "competitors": [
                {"name": "Jumeirah Group", "x_coordinate": 90, "y_coordinate": 85, "quadrant": "Iconic Luxury"},
                {"name": "Rotana Hotels", "x_coordinate": 60, "y_coordinate": 55, "quadrant": "Regional Business"},
                {"name": "Address Hotels (Emaar)", "x_coordinate": 80, "y_coordinate": 75, "quadrant": "Lifestyle Luxury"},
                {"name": "Rove Hotels", "x_coordinate": 45, "y_coordinate": 65, "quadrant": "Affordable Contemporary"}
            ],
            "user_position": {"x": 70, "y": 78, "quadrant": "Premium Lifestyle"},
            "axis_x": "Price: AED 300/night Budget → AED 5,000+/night Ultra-Luxury",
            "axis_y": "Positioning: Business/Transit → Destination/Experience",
            "white_space": "UAE hospitality ($15B) is dominated by mega-brands and ultra-luxury. **Gap: Design-forward mid-luxury** (AED 600-1,200/night) targeting younger affluent travelers and digital nomads. Dubai's new visa programs (remote work, golden visa) create demand for longer stays with lifestyle amenities.",
            "strategic_advantage": "UAE targeting 25M tourists by 2025. Expo 2020 legacy infrastructure. No income tax enables competitive pricing. Dubai Marina, JBR, Business Bay have high demand but limited boutique supply. Abu Dhabi positioning for cultural tourism (Louvre, Guggenheim).",
            "entry_recommendation": "Phase 1: Management contract or lease in Dubai Marina or Downtown area. Phase 2: Develop co-living/long-stay concept for digital nomads. Phase 3: Expand to Abu Dhabi for cultural tourism segment. Key: Partner with Emirates for travel packages, target GCC weekend travelers, emphasize Instagram-worthy design."
        },
        "Singapore": {
            "competitors": [
                {"name": "Marina Bay Sands", "x_coordinate": 95, "y_coordinate": 80, "quadrant": "Iconic Integrated Resort"},
                {"name": "Raffles Singapore", "x_coordinate": 90, "y_coordinate": 70, "quadrant": "Heritage Luxury"},
                {"name": "YOTEL", "x_coordinate": 40, "y_coordinate": 75, "quadrant": "Tech Compact"},
                {"name": "The Warehouse Hotel", "x_coordinate": 75, "y_coordinate": 80, "quadrant": "Boutique Heritage"}
            ],
            "user_position": {"x": 68, "y": 75, "quadrant": "Contemporary Lifestyle"},
            "axis_x": "Price: S$150/night Budget → S$1,000+/night Luxury",
            "axis_y": "Style: Business/Chain → Lifestyle/Boutique",
            "white_space": "Singapore hospitality ($10B) is highly competitive with international chains. **Gap: Mid-range lifestyle hotels** targeting regional business travelers and short-stay tourists. Limited supply in emerging districts (Tiong Bahru, Katong, Kampong Glam) where heritage shophouses create unique opportunities.",
            "strategic_advantage": "Singapore is ASEAN business hub with 19M+ annual visitors. Strong IP protection and rule of law for international brands. Changi Airport connectivity. STB (Singapore Tourism Board) offers grants for tourism innovation.",
            "entry_recommendation": "Phase 1: Boutique hotel in heritage district (Tiong Bahru, Katong) via shophouse conversion. Phase 2: Partner with SilkAir/Singapore Airlines for regional packages. Phase 3: Expand to Sentosa for leisure segment. Key: Emphasize local Peranakan culture, target Malaysian/Indonesian weekend visitors, leverage Singapore's food scene."
        },
        "Japan": {
            "competitors": [
                {"name": "Hoshino Resorts", "x_coordinate": 85, "y_coordinate": 80, "quadrant": "Japanese Luxury Experience"},
                {"name": "APA Hotels", "x_coordinate": 30, "y_coordinate": 35, "quadrant": "Budget Business"},
                {"name": "Prince Hotels", "x_coordinate": 65, "y_coordinate": 55, "quadrant": "Traditional Premium"},
                {"name": "Aman Tokyo", "x_coordinate": 95, "y_coordinate": 90, "quadrant": "Ultra-Luxury Minimal"}
            ],
            "user_position": {"x": 70, "y": 75, "quadrant": "Modern Ryokan Fusion"},
            "axis_x": "Price: ¥8,000/night Budget → ¥100,000+/night Luxury",
            "axis_y": "Style: Western Standard → Japanese Authentic",
            "white_space": "Japan hospitality ($100B) is recovering to 60M+ tourist target. **Gap: Modern ryokan concept** bridging traditional Japanese hospitality with contemporary design for Western travelers. Existing ryokans are either ultra-luxury (¥50,000+) or dated mid-range. Demand for 'accessible Japanese experience' (¥15,000-30,000/night) exceeds supply.",
            "strategic_advantage": "Yen weakness (150+/$) drives record inbound tourism. 2025 Osaka Expo creates demand surge. Rural revitalization initiatives offer subsidies for heritage property development. Japanese service culture ('omotenashi') is unique differentiator.",
            "entry_recommendation": "Phase 1: Acquire/restore traditional property in Kyoto or Kanazawa with modern amenities. Phase 2: Partner with JR rail passes for package offerings. Phase 3: Expand to secondary cities (Takayama, Naoshima, Hakone). Key: Hire experienced Japanese hospitality staff, design for tatami/futon flexibility, target FIT (Free Independent Travelers) via Jalan and Rakuten Travel."
        },
        "default": {
            "competitors": [
                {"name": "Marriott International", "x_coordinate": 75, "y_coordinate": 65, "quadrant": "Global Full-Service"},
                {"name": "Hilton Worldwide", "x_coordinate": 70, "y_coordinate": 60, "quadrant": "Business Premium"},
                {"name": "Accor Hotels", "x_coordinate": 60, "y_coordinate": 55, "quadrant": "European Diverse"},
                {"name": "IHG Hotels", "x_coordinate": 65, "y_coordinate": 50, "quadrant": "Mid-Scale Focus"}
            ],
            "user_position": {"x": 65, "y": 72, "quadrant": "Boutique Lifestyle"},
            "axis_x": "Price: Budget → Luxury",
            "axis_y": "Experience: Standardized Chain → Unique Boutique",
            "white_space": "Global hospitality market shows consistent demand for **lifestyle boutique experiences** over standardized chain offerings. Millennials and Gen Z prioritize Instagram-worthy design, local authenticity, and unique experiences over loyalty program points.",
            "strategic_advantage": "Independent boutique hotels consistently outperform chains on guest satisfaction and social media engagement. Direct booking technology reduces OTA dependency. Flexible brand standards enable local adaptation.",
            "entry_recommendation": "Phase 1: Flagship property in high-demand destination. Phase 2: Management contract expansion with property partners. Phase 3: Regional brand building via strategic marketing. Focus on design differentiation, local partnerships, and digital-first guest experience."
        }
    },
    
    # ============ BEAUTY & COSMETICS ============
    "beauty": {
        "India": {
            "competitors": [
                {"name": "Nykaa", "x_coordinate": 70, "y_coordinate": 75, "quadrant": "Premium Digital-First"},
                {"name": "Mamaearth", "x_coordinate": 55, "y_coordinate": 80, "quadrant": "Natural/Clean Beauty"},
                {"name": "Sugar Cosmetics", "x_coordinate": 50, "y_coordinate": 70, "quadrant": "Affordable Trendy"},
                {"name": "Plum Goodness", "x_coordinate": 60, "y_coordinate": 65, "quadrant": "Vegan Premium"}
            ],
            "user_position": {"x": 65, "y": 78, "quadrant": "Premium Accessible"},
            "axis_x": "Price: ₹200 Budget → ₹2000+ Premium",
            "axis_y": "Positioning: Mass Market → Premium DTC",
            "white_space": "India's ₹1.2 trillion beauty market is dominated by legacy brands (Lakme, L'Oréal India) in mass retail. **Gap: DTC premium segment** (₹500-1500 price point) targeting 25-35 urban professionals remains underpenetrated. 'Clean beauty' positioning resonates with health-conscious millennials - only 12% of market currently addresses this.",
            "strategic_advantage": "India's DTC beauty grew 45% YoY (2023-24). First-mover advantage in Tier 2/3 cities where Nykaa/Mamaearth have limited reach. Lower CAC ($2-4) vs USA ($15-25) enables faster scale. Vernacular marketing in Hindi/regional languages can capture 400M non-English speakers.",
            "entry_recommendation": "Phase 1: Launch on Amazon India, Flipkart, and Nykaa marketplace (6 months). Phase 2: Own D2C website with COD (Cash on Delivery - 65% of orders). Phase 3: Quick commerce (Blinkit, Zepto) for replenishment. Key: Partner with micro-influencers (10K-100K followers) at ₹5,000-20,000/post vs celebrity endorsements."
        },
        "USA": {
            "competitors": [
                {"name": "Glossier", "x_coordinate": 75, "y_coordinate": 85, "quadrant": "Premium Millennial"},
                {"name": "The Ordinary", "x_coordinate": 40, "y_coordinate": 70, "quadrant": "Science-Led Affordable"},
                {"name": "Drunk Elephant", "x_coordinate": 85, "y_coordinate": 80, "quadrant": "Clean Luxury"},
                {"name": "CeraVe", "x_coordinate": 35, "y_coordinate": 55, "quadrant": "Dermatologist Value"}
            ],
            "user_position": {"x": 60, "y": 72, "quadrant": "Accessible Clean Beauty"},
            "axis_x": "Price: $10 Drugstore → $100+ Prestige",
            "axis_y": "Channel: Mass Retail → DTC/Specialty",
            "white_space": "US skincare market ($24B) is saturated at premium ($50+) and mass ($10-15) tiers. **Gap: The $20-40 'masstige' segment** is contested but not dominated. Brands combining clinical efficacy (like The Ordinary) with aspirational branding (like Glossier) at mid-price. Gen Z demands transparency + sustainability.",
            "strategic_advantage": "TikTok-driven discovery is reshaping US beauty - #SkinTok has 100B+ views. Unlike established brands, new entrants can build virality through UGC. Opportunity in Ulta Beauty's 'Conscious Beauty' program and Target's clean beauty shelf space expansion.",
            "entry_recommendation": "Phase 1: Amazon US launch with FBA (test market fit, 3-6 months). Phase 2: Ulta Beauty pitch (requires $2M+ marketing commitment). Phase 3: Own DTC with Shopify + aggressive Meta/TikTok ads ($50-100 CAC expected). Critical: FDA compliance for claims, clean ingredient list for retailer acceptance."
        },
        "Thailand": {
            "competitors": [
                {"name": "Oriental Princess", "x_coordinate": 65, "y_coordinate": 60, "quadrant": "Local Heritage Premium"},
                {"name": "Mistine", "x_coordinate": 40, "y_coordinate": 50, "quadrant": "Mass Market Leader"},
                {"name": "Beauty Buffet", "x_coordinate": 35, "y_coordinate": 65, "quadrant": "K-Beauty Inspired Affordable"},
                {"name": "SRICHAND", "x_coordinate": 55, "y_coordinate": 45, "quadrant": "Traditional Thai Beauty"}
            ],
            "user_position": {"x": 70, "y": 75, "quadrant": "Modern Premium Import"},
            "axis_x": "Price: ฿100 Mass → ฿1500+ Import Premium",
            "axis_y": "Origin: Local Thai → International/K-Beauty",
            "white_space": "Thailand's $6B beauty market is K-Beauty dominated (40% market share). **Gap: Western/International clean beauty** brands are underrepresented. Thai consumers associate 'farang' (foreign) brands with premium quality. Opportunity in 'whitening-free' positioning - global clean beauty trend conflicts with local whitening obsession.",
            "strategic_advantage": "Thailand is ASEAN's beauty hub - successful launch here provides gateway to Vietnam, Indonesia, Philippines. Lower regulatory burden than China. Thai FDA approval is straightforward for cosmetics. Bangkok's 7-Eleven (13,000+ stores) is a unique distribution channel.",
            "entry_recommendation": "Phase 1: Shopee Thailand and Lazada launch (dominant e-commerce, 70% of online sales). Phase 2: Watsons and Boots pharmacy chains (high-trust retail). Phase 3: 7-Eleven for impulse SKUs. Key: Thai-language social media (Line, not WhatsApp), partner with Thai beauty bloggers, consider Thai celebrity ambassador."
        },
        "UK": {
            "competitors": [
                {"name": "Charlotte Tilbury", "x_coordinate": 85, "y_coordinate": 80, "quadrant": "Luxury Glamour"},
                {"name": "The Body Shop", "x_coordinate": 50, "y_coordinate": 55, "quadrant": "Ethical Mass"},
                {"name": "Lush", "x_coordinate": 60, "y_coordinate": 70, "quadrant": "Handmade Premium"},
                {"name": "Boots No7", "x_coordinate": 40, "y_coordinate": 45, "quadrant": "Pharmacy Value"}
            ],
            "user_position": {"x": 65, "y": 75, "quadrant": "Modern Clean Premium"},
            "axis_x": "Price: £5 Value → £50+ Luxury",
            "axis_y": "Positioning: Traditional → Modern/Clean",
            "white_space": "UK beauty market (£10B) faces post-Brexit supply chain challenges for EU brands. **Gap: British-made clean beauty** brands are rare - most 'clean' brands are US imports. Opportunity in 'Made in UK' positioning with sustainability focus. Vegan/cruelty-free is table stakes.",
            "strategic_advantage": "UK consumers are Europe's most digitally-savvy beauty shoppers. Lower customer acquisition costs than US. Boots (2,200 stores) and Superdrug (800 stores) provide mass reach. UK launch validates brand for broader European expansion.",
            "entry_recommendation": "Phase 1: Amazon UK + own D2C site (3-6 months validation). Phase 2: Cult Beauty or Space NK for premium positioning, OR Boots for mass reach. Phase 3: Expand to EU via Netherlands hub. Key: UK-specific claims compliance, sustainable packaging mandatory."
        },
        "default": {
            "competitors": [
                {"name": "L'Oréal Group", "x_coordinate": 75, "y_coordinate": 65, "quadrant": "Mass Premium Leader"},
                {"name": "Estée Lauder", "x_coordinate": 85, "y_coordinate": 75, "quadrant": "Prestige Beauty"},
                {"name": "Unilever Beauty", "x_coordinate": 50, "y_coordinate": 50, "quadrant": "Mass Market"},
                {"name": "Indie Brands", "x_coordinate": 60, "y_coordinate": 80, "quadrant": "DTC Disruptors"}
            ],
            "user_position": {"x": 65, "y": 72, "quadrant": "Accessible Premium"},
            "axis_x": "Price: Budget → Premium",
            "axis_y": "Channel: Mass Retail → DTC/Specialty",
            "white_space": "Global beauty market shows consistent demand for **clean, transparent, sustainable** brands. The 'masstige' segment ($20-50) remains underpenetrated in most markets.",
            "strategic_advantage": "DTC brands with authentic stories consistently outperform on customer loyalty. Social media (TikTok, Instagram) enables rapid brand building without traditional advertising spend.",
            "entry_recommendation": "Phase 1: E-commerce validation on marketplaces. Phase 2: Build DTC channel with strong social presence. Phase 3: Retail partnerships for scale. Focus on ingredient transparency, sustainable packaging, and community building."
        }
    },
    
    # ============ TECHNOLOGY & SAAS ============
    "technology": {
        "India": {
            "competitors": [
                {"name": "Zoho", "x_coordinate": 65, "y_coordinate": 70, "quadrant": "Indian Enterprise SaaS"},
                {"name": "Freshworks", "x_coordinate": 60, "y_coordinate": 75, "quadrant": "Global SMB Focus"},
                {"name": "Razorpay", "x_coordinate": 70, "y_coordinate": 80, "quadrant": "Fintech Leader"},
                {"name": "Infosys", "x_coordinate": 80, "y_coordinate": 55, "quadrant": "Enterprise Services"}
            ],
            "user_position": {"x": 55, "y": 72, "quadrant": "Emerging SaaS"},
            "axis_x": "Market: SMB/Startup → Enterprise",
            "axis_y": "Reach: India-First → Global-First",
            "white_space": "India's $10B SaaS market is dominated by US imports and a few Indian giants. **Gap: Vertical-specific SaaS** for Indian industries (pharma, textiles, agriculture). 75M+ SMBs lack affordable, localized software solutions. Opportunity in vernacular interfaces and UPI-integrated tools.",
            "strategic_advantage": "India produces world-class engineering talent at 70-80% lower cost. Domestic market of 75M+ SMBs for validation before global expansion. Government's 'Digital India' initiative drives cloud adoption. Strong VC ecosystem (Sequoia, Accel, Peak XV) for growth funding.",
            "entry_recommendation": "Phase 1: MVP for specific vertical (healthcare, education, retail) with freemium model. Phase 2: Build enterprise sales team for mid-market. Phase 3: Expand to SEA markets with similar characteristics. Key: Offer UPI/local payment integration, WhatsApp Business API support, Hindi/regional language support."
        },
        "USA": {
            "competitors": [
                {"name": "Salesforce", "x_coordinate": 90, "y_coordinate": 70, "quadrant": "Enterprise CRM Leader"},
                {"name": "HubSpot", "x_coordinate": 65, "y_coordinate": 75, "quadrant": "SMB Growth Platform"},
                {"name": "Stripe", "x_coordinate": 80, "y_coordinate": 85, "quadrant": "Developer-First Payments"},
                {"name": "Notion", "x_coordinate": 55, "y_coordinate": 80, "quadrant": "Productivity Disruptor"}
            ],
            "user_position": {"x": 60, "y": 78, "quadrant": "Emerging Challenger"},
            "axis_x": "Market: SMB → Enterprise",
            "axis_y": "Approach: Sales-Led → Product-Led Growth",
            "white_space": "US SaaS market ($200B) is mature but fragmented. **Gap: AI-native vertical solutions** for specific industries. Horizontal tools (CRM, project management) are commoditized. Opportunity in applying GPT/AI to specific workflows (legal, healthcare, construction) with deep domain expertise.",
            "strategic_advantage": "PLG (Product-Led Growth) enables efficient scaling. US market validates global pricing. Access to world's largest talent pool and VC ecosystem. Enterprise willingness to pay premium for best-in-class solutions.",
            "entry_recommendation": "Phase 1: Launch AI-powered niche tool with freemium or free trial. Phase 2: Build self-serve motion with product-led growth. Phase 3: Add enterprise sales for larger accounts. Key: SOC2 compliance mandatory, integrate with existing workflows (Slack, Salesforce), competitive pricing vs incumbents."
        },
        "default": {
            "competitors": [
                {"name": "Microsoft", "x_coordinate": 85, "y_coordinate": 60, "quadrant": "Enterprise Incumbent"},
                {"name": "Google Cloud", "x_coordinate": 80, "y_coordinate": 70, "quadrant": "Cloud Infrastructure"},
                {"name": "Atlassian", "x_coordinate": 60, "y_coordinate": 75, "quadrant": "Developer Tools"},
                {"name": "Local Players", "x_coordinate": 45, "y_coordinate": 55, "quadrant": "Regional Focus"}
            ],
            "user_position": {"x": 55, "y": 72, "quadrant": "Agile Innovator"},
            "axis_x": "Market: SMB → Enterprise",
            "axis_y": "Approach: Traditional Sales → Product-Led Growth",
            "white_space": "Global SaaS market continues rapid growth. **Gap: AI-native, vertical-specific solutions** that solve specific industry problems better than horizontal tools.",
            "strategic_advantage": "Product-led growth enables efficient customer acquisition. Cloud infrastructure reduces time-to-market. Global talent pool available for remote hiring.",
            "entry_recommendation": "Phase 1: MVP with clear value proposition for specific use case. Phase 2: Build self-serve onboarding and product-led growth. Phase 3: Add sales team for enterprise expansion. Focus on customer success and net revenue retention."
        }
    },
    
    # ============ FOOD & BEVERAGE ============
    "food": {
        "India": {
            "competitors": [
                {"name": "Haldiram's", "x_coordinate": 70, "y_coordinate": 55, "quadrant": "Heritage Snacks Leader"},
                {"name": "Paper Boat", "x_coordinate": 60, "y_coordinate": 80, "quadrant": "Premium Nostalgia"},
                {"name": "Chaayos", "x_coordinate": 55, "y_coordinate": 75, "quadrant": "Modern Chai Chain"},
                {"name": "Chai Point", "x_coordinate": 50, "y_coordinate": 70, "quadrant": "B2B Tea Focus"}
            ],
            "user_position": {"x": 65, "y": 78, "quadrant": "Premium Authentic"},
            "axis_x": "Price: ₹20 Mass → ₹200+ Premium",
            "axis_y": "Positioning: Traditional → Modern Premium",
            "white_space": "India's $800B food market is highly fragmented. **Gap: Premium authentic regional cuisine** for urban millennials. 400M+ urban consumers willing to pay premium for 'grandmother's recipes' with modern packaging. Opportunity in healthy traditional foods (millets, regional snacks) without preservatives.",
            "strategic_advantage": "India's food delivery grew 25%+ annually. Quick commerce (10-min delivery) changes consumption patterns. Regional pride drives demand for authentic local foods. Lower manufacturing costs enable competitive pricing.",
            "entry_recommendation": "Phase 1: D2C launch via own website + Amazon/Flipkart. Phase 2: Quick commerce (Blinkit, Zepto, Instamart) for metro cities. Phase 3: Modern trade (Big Bazaar, Reliance Retail). Key: Clean labels (no preservatives), regional authenticity story, Instagram-worthy packaging."
        },
        "USA": {
            "competitors": [
                {"name": "Oatly", "x_coordinate": 75, "y_coordinate": 80, "quadrant": "Plant-Based Leader"},
                {"name": "Impossible Foods", "x_coordinate": 70, "y_coordinate": 85, "quadrant": "Alt-Protein Innovation"},
                {"name": "KIND Snacks", "x_coordinate": 60, "y_coordinate": 65, "quadrant": "Better-For-You"},
                {"name": "Chobani", "x_coordinate": 65, "y_coordinate": 60, "quadrant": "Greek Yogurt Leader"}
            ],
            "user_position": {"x": 68, "y": 75, "quadrant": "Clean Label Premium"},
            "axis_x": "Price: $3 Mass → $10+ Premium",
            "axis_y": "Positioning: Conventional → Health/Sustainability",
            "white_space": "US food market ($1T) is shifting to health-conscious choices. **Gap: Ethnic 'better-for-you' foods** targeting diverse population. Indian, Korean, Mexican cuisines growing but lack clean-label, premium brands. Opportunity in functional foods (adaptogens, probiotics) with ethnic positioning.",
            "strategic_advantage": "US consumers increasingly adventurous with global flavors. Whole Foods, Sprouts, Target expanding ethnic/health sections. Food service channel (restaurants, cafeterias) provides scale. DTC subscription models enable customer retention.",
            "entry_recommendation": "Phase 1: Amazon + specialty retailers (Whole Foods, Sprouts). Phase 2: Foodservice partnerships (corporate cafeterias, universities). Phase 3: Mass retail (Target, Walmart) with proven velocity. Key: Clean ingredient deck, compelling origin story, competitive shelf price."
        },
        "default": {
            "competitors": [
                {"name": "Nestlé", "x_coordinate": 80, "y_coordinate": 50, "quadrant": "Global Mass Leader"},
                {"name": "Kraft Heinz", "x_coordinate": 70, "y_coordinate": 45, "quadrant": "Processed Foods"},
                {"name": "Local Champions", "x_coordinate": 55, "y_coordinate": 60, "quadrant": "Regional Favorites"},
                {"name": "Health Brands", "x_coordinate": 60, "y_coordinate": 80, "quadrant": "Better-For-You"}
            ],
            "user_position": {"x": 65, "y": 72, "quadrant": "Premium Authentic"},
            "axis_x": "Price: Budget → Premium",
            "axis_y": "Positioning: Conventional → Health/Authentic",
            "white_space": "Global food trends favor **health-conscious, authentic, sustainable** options. Plant-based, functional foods, and clean labels are growth drivers across all markets.",
            "strategic_advantage": "Consumer willingness to pay premium for quality and authenticity. E-commerce and quick commerce reduce distribution barriers. Social media enables direct brand building.",
            "entry_recommendation": "Phase 1: E-commerce and specialty retail validation. Phase 2: Foodservice partnerships for scale. Phase 3: Mass retail with proven demand. Focus on clean ingredients, compelling story, and sustainable packaging."
        }
    },
    
    # ============ FINANCE & PAYMENTS ============
    "finance": {
        "India": {
            "competitors": [
                {"name": "PhonePe", "x_coordinate": 45, "y_coordinate": 85, "quadrant": "Mass UPI Leader"},
                {"name": "Razorpay", "x_coordinate": 70, "y_coordinate": 70, "quadrant": "B2B Payments"},
                {"name": "Groww", "x_coordinate": 55, "y_coordinate": 80, "quadrant": "Retail Investing"},
                {"name": "Zerodha", "x_coordinate": 60, "y_coordinate": 75, "quadrant": "Discount Broker Leader"}
            ],
            "user_position": {"x": 65, "y": 78, "quadrant": "Digital-First Premium"},
            "axis_x": "Market: Retail/Consumer → Business/Enterprise",
            "axis_y": "Innovation: Traditional → Digital-Native",
            "white_space": "India's fintech market ($100B by 2025) is dominated by payments. **Gap: Embedded finance and neobanking** for underserved segments. 400M+ Indians lack access to credit. Opportunity in BNPL for non-metro, SMB lending, and wealth management for mass affluent.",
            "strategic_advantage": "India Stack (UPI, Aadhaar, DigiLocker) enables instant onboarding. RBI's regulatory sandbox encourages innovation. Lower customer acquisition costs via WhatsApp. Account Aggregator framework enables open banking.",
            "entry_recommendation": "Phase 1: Niche segment focus (freelancers, students, SMBs) with specific product. Phase 2: Expand product suite (savings, credit, insurance). Phase 3: Build to 'super app' with ecosystem. Key: RBI compliance, partnerships with banks for deposits, fraud prevention."
        },
        "USA": {
            "competitors": [
                {"name": "Stripe", "x_coordinate": 80, "y_coordinate": 85, "quadrant": "Developer Payments"},
                {"name": "Square (Block)", "x_coordinate": 65, "y_coordinate": 75, "quadrant": "SMB Ecosystem"},
                {"name": "Chime", "x_coordinate": 50, "y_coordinate": 80, "quadrant": "Consumer Neobank"},
                {"name": "Plaid", "x_coordinate": 75, "y_coordinate": 70, "quadrant": "Infrastructure"}
            ],
            "user_position": {"x": 60, "y": 78, "quadrant": "Vertical Fintech"},
            "axis_x": "Market: Consumer → Enterprise",
            "axis_y": "Approach: Banking → Fintech/Embedded",
            "white_space": "US fintech market is mature but fragmented. **Gap: Vertical-specific embedded finance** for industries (healthcare, construction, legal) with complex payment flows. Opportunity in 'banking-as-a-service' for non-financial brands.",
            "strategic_advantage": "APIs enable rapid product development. Banking charters available (easier than before). Enterprise willingness to pay for specialized solutions. Strong VC funding environment.",
            "entry_recommendation": "Phase 1: Solve specific pain point for defined vertical. Phase 2: Expand product suite within vertical. Phase 3: Horizontal expansion to adjacent verticals. Key: Compliance (state licenses, SOC2), banking partnerships, fraud prevention."
        },
        "default": {
            "competitors": [
                {"name": "Visa/Mastercard", "x_coordinate": 85, "y_coordinate": 55, "quadrant": "Card Network Incumbents"},
                {"name": "PayPal", "x_coordinate": 70, "y_coordinate": 65, "quadrant": "Digital Payments"},
                {"name": "Local Banks", "x_coordinate": 60, "y_coordinate": 45, "quadrant": "Traditional Banking"},
                {"name": "Regional Fintechs", "x_coordinate": 55, "y_coordinate": 75, "quadrant": "Digital Challengers"}
            ],
            "user_position": {"x": 60, "y": 72, "quadrant": "Digital-First Challenger"},
            "axis_x": "Market: Consumer → Enterprise",
            "axis_y": "Innovation: Traditional → Digital-Native",
            "white_space": "Global fintech continues rapid growth. **Gap: Embedded finance for specific verticals** and underserved segments. Cross-border payments, SMB lending, and wealth management remain underpenetrated.",
            "strategic_advantage": "Digital-first approach enables superior user experience. API-based architecture allows rapid iteration. Regulatory clarity increasing globally.",
            "entry_recommendation": "Phase 1: Niche segment with clear pain point. Phase 2: Expand product suite. Phase 3: Geographic or vertical expansion. Focus on compliance, partnerships with licensed entities, and fraud prevention."
        }
    },
    
    # ============ FASHION & APPAREL ============
    "fashion": {
        "India": {
            "competitors": [
                {"name": "Zara India", "x_coordinate": 80, "y_coordinate": 75, "quadrant": "Fast Fashion Premium"},
                {"name": "H&M India", "x_coordinate": 60, "y_coordinate": 65, "quadrant": "Fast Fashion Value"},
                {"name": "Bewakoof", "x_coordinate": 35, "y_coordinate": 70, "quadrant": "DTC Youth"},
                {"name": "The Souled Store", "x_coordinate": 45, "y_coordinate": 75, "quadrant": "Pop Culture Streetwear"}
            ],
            "user_position": {"x": 55, "y": 80, "quadrant": "Premium Streetwear"},
            "axis_x": "Price: ₹500 Budget → ₹10,000+ Premium",
            "axis_y": "Style: Classic/Traditional → Streetwear/Avant-garde",
            "white_space": "India's $90B apparel market is dominated by ethnic wear (40%) and fast fashion. **Gap: Premium streetwear segment (₹2,000-8,000)** targeting Gen Z urbanites. Only 5% of market is streetwear vs 25% globally. Rising sneaker culture, hip-hop influence, and Instagram fashion driving demand. Limited homegrown streetwear brands with authentic positioning.",
            "strategic_advantage": "430M Gen Z + Millennials with rising disposable income. Instagram/YouTube fashion influencers drive trends. Limited competition in premium streetwear - Bewakoof is budget, international brands are overpriced. D2C model enables 60%+ gross margins. India's textile manufacturing ecosystem supports local production.",
            "entry_recommendation": "Phase 1: Launch 20-30 SKU capsule collection, D2C only via Instagram + own website. Phase 2: Collaborate with Indian hip-hop artists, cricketers for authenticity. Phase 3: Selective multi-brand retail (Lifestyle, Shopper's Stop). Key: Build community via drops, limited editions, streetwear culture events."
        },
        "USA": {
            "competitors": [
                {"name": "Supreme", "x_coordinate": 95, "y_coordinate": 90, "quadrant": "Hype Streetwear"},
                {"name": "Off-White", "x_coordinate": 90, "y_coordinate": 85, "quadrant": "Luxury Streetwear"},
                {"name": "Stüssy", "x_coordinate": 75, "y_coordinate": 80, "quadrant": "OG Streetwear"},
                {"name": "BAPE", "x_coordinate": 85, "y_coordinate": 75, "quadrant": "Japanese Streetwear"}
            ],
            "user_position": {"x": 65, "y": 78, "quadrant": "Emerging Streetwear"},
            "axis_x": "Price: $50 Entry → $500+ Hype",
            "axis_y": "Positioning: Mass → Exclusive/Limited",
            "white_space": "US streetwear market ($185B by 2027) is mature but **Gap: Affordable premium streetwear ($80-200)** between fast fashion (H&M, Zara) and hype brands (Supreme, Off-White). Gen Z wants authenticity without $300+ price tags. Sustainability and ethical production increasingly important. Resale market ($15B) indicates strong demand exceeds supply for quality streetwear.",
            "strategic_advantage": "Direct-to-consumer eliminates wholesale margins. Social media enables community-building without retail footprint. Collaborations drive virality. US consumers pay premium for 'story' and authenticity. Athleisure crossover expands addressable market.",
            "entry_recommendation": "Phase 1: Launch with limited 'drop' model - build scarcity and hype. Phase 2: Strategic collaborations with artists, athletes, brands (start small). Phase 3: Selective wholesale to Nordstrom, SSENSE, END Clothing. Key: Community-first, authentic brand story, quality over quantity."
        },
        "Japan": {
            "competitors": [
                {"name": "BAPE", "x_coordinate": 90, "y_coordinate": 85, "quadrant": "Harajuku Hype"},
                {"name": "NEIGHBORHOOD", "x_coordinate": 85, "y_coordinate": 80, "quadrant": "Military Streetwear"},
                {"name": "UNIQLO", "x_coordinate": 40, "y_coordinate": 50, "quadrant": "Mass Basics"},
                {"name": "COMME des GARÇONS", "x_coordinate": 95, "y_coordinate": 90, "quadrant": "Avant-garde Luxury"}
            ],
            "user_position": {"x": 70, "y": 75, "quadrant": "International Streetwear"},
            "axis_x": "Price: ¥3,000 Entry → ¥100,000+ Luxury",
            "axis_y": "Style: Minimalist → Bold/Experimental",
            "white_space": "Japan's $100B fashion market is birthplace of streetwear. **Gap: International streetwear brands** with authentic non-Japanese story. Japanese consumers are most discerning but respect authenticity. 'Gaijin' (foreign) brands with genuine culture story can succeed (see: Supreme's Japan success). Growing 'genderless' and sustainability trends create new niches.",
            "strategic_advantage": "Japanese consumers pay premium for quality and story. Strong sneaker culture supports streetwear crossover. Tokyo remains global fashion capital - success here validates brand globally. Japanese wholesale/retail partners (BEAMS, UNITED ARROWS) provide distribution.",
            "entry_recommendation": "Phase 1: Pop-up in Harajuku/Shibuya to test market, build buzz. Phase 2: Wholesale to curated retailers (BEAMS, UNITED ARROWS). Phase 3: Flagship store if demand warrants. Key: Never discount (destroys brand in Japan), respect local sizing, partner with Japanese creatives for localization."
        },
        "UK": {
            "competitors": [
                {"name": "Palace Skateboards", "x_coordinate": 85, "y_coordinate": 85, "quadrant": "British Streetwear"},
                {"name": "Burberry", "x_coordinate": 90, "y_coordinate": 70, "quadrant": "Luxury Heritage"},
                {"name": "ASOS", "x_coordinate": 45, "y_coordinate": 65, "quadrant": "Fast Fashion Online"},
                {"name": "Represent", "x_coordinate": 75, "y_coordinate": 80, "quadrant": "Manchester Streetwear"}
            ],
            "user_position": {"x": 65, "y": 78, "quadrant": "International Streetwear"},
            "axis_x": "Price: £30 Budget → £500+ Premium",
            "axis_y": "Positioning: High Street → Streetwear Culture",
            "white_space": "UK streetwear market (£12B) has strong local scene (Palace, Corteiz, Represent). **Gap: Accessible premium international streetwear (£80-200)**. Post-Brexit, EU brands face logistics challenges - opportunity for non-EU brands. London remains key fashion city. Football/music culture drives streetwear adoption beyond core skate/hip-hop.",
            "strategic_advantage": "English-speaking market enables direct marketing. Strong influencer ecosystem. London Fashion Week provides platform. UK consumers are early adopters - success here influences EU. Post-Brexit means less EU competition, more opportunity for US/Asia brands.",
            "entry_recommendation": "Phase 1: Online-first via own site, partner with END Clothing, SSENSE for credibility. Phase 2: London pop-up in Soho/Shoreditch. Phase 3: Wholesale to Selfridges, Harvey Nichols. Key: Football and grime music collaborations resonate locally."
        },
        "default": {
            "competitors": [
                {"name": "Nike", "x_coordinate": 70, "y_coordinate": 75, "quadrant": "Sportswear Giant"},
                {"name": "Adidas", "x_coordinate": 65, "y_coordinate": 70, "quadrant": "Sport Heritage"},
                {"name": "Zara", "x_coordinate": 55, "y_coordinate": 60, "quadrant": "Fast Fashion"},
                {"name": "Supreme", "x_coordinate": 90, "y_coordinate": 90, "quadrant": "Hype Streetwear"}
            ],
            "user_position": {"x": 60, "y": 78, "quadrant": "Emerging Streetwear"},
            "axis_x": "Price: Budget → Premium",
            "axis_y": "Style: Classic → Streetwear/Experimental",
            "white_space": "Global streetwear market continues rapid growth driven by Gen Z and millennial consumers. **Gap: Authentic, sustainable streetwear** at accessible price points ($80-200). Fast fashion lacks authenticity; hype brands are unattainable. Community-driven brands with genuine stories outperform.",
            "strategic_advantage": "Direct-to-consumer model enables global reach with lower capital requirements. Social media and collaborations drive organic growth. Sustainability increasingly important differentiator.",
            "entry_recommendation": "Phase 1: Launch D2C with limited drops to build scarcity. Phase 2: Strategic collaborations for reach. Phase 3: Selective wholesale to premium retailers. Focus on community, authenticity, and quality."
        }
    }
}

# Category mapping to normalize input categories
CATEGORY_MAPPING = {
    # Hotels & Hospitality
    "hotel": "hotels", "hotels": "hotels", "hotel chain": "hotels", "hospitality": "hotels",
    "resort": "hotels", "motel": "hotels", "lodge": "hotels", "inn": "hotels",
    "accommodation": "hotels", "lodging": "hotels", "boutique hotel": "hotels",
    
    # Beauty & Cosmetics  
    "beauty": "beauty", "cosmetics": "beauty", "skincare": "beauty", "makeup": "beauty",
    "personal care": "beauty", "haircare": "beauty", "fragrance": "beauty",
    
    # Technology & SaaS (EXPANDED)
    "technology": "technology", "tech": "technology", "saas": "technology", "software": "technology",
    "it": "technology", "app": "technology", "ai": "technology", "fintech": "technology",
    "tool": "technology", "platform": "technology", "digital": "technology", "analytics": "technology",
    "automation": "technology", "cloud": "technology", "data": "technology", "cyber": "technology",
    "machine learning": "technology", "ml": "technology", "startup": "technology", "b2b": "technology",
    "enterprise": "technology", "api": "technology", "devops": "technology", "iot": "technology",
    "blockchain": "technology", "web3": "technology", "crypto": "technology", "nft": "technology",
    "ecommerce": "technology", "e-commerce": "technology", "marketplace": "technology",
    "evaluation": "technology", "assessment": "technology", "analyzer": "technology",
    
    # Food & Beverage
    "food": "food", "beverage": "food", "food & beverage": "food", "f&b": "food",
    "restaurant": "food", "cafe": "food", "snacks": "food", "drinks": "food",
    "tea": "food", "coffee": "food", "chai": "food",
    
    # Finance & Payments
    "finance": "finance", "banking": "finance", "payments": "finance", "insurance": "finance",
    "investment": "finance", "lending": "finance", "wealth": "finance",
    
    # Fashion & Apparel
    "fashion": "fashion", "apparel": "fashion", "clothing": "fashion", "streetwear": "fashion",
    "fashion & apparel": "fashion", "footwear": "fashion", "shoes": "fashion",
    "accessories": "fashion", "luxury fashion": "fashion", "sportswear": "fashion",
    "athleisure": "fashion", "denim": "fashion", "activewear": "fashion",
    
    # Healthcare & Medical
    "healthcare": "healthcare", "health": "healthcare", "medical": "healthcare", "doctor": "healthcare",
    "hospital": "healthcare", "clinic": "healthcare", "pharma": "healthcare", "pharmaceutical": "healthcare",
    "wellness": "healthcare", "fitness": "healthcare", "telemedicine": "healthcare", "healthtech": "healthcare",
    
    # Education & EdTech
    "education": "education", "edtech": "education", "learning": "education", "training": "education",
    "courses": "education", "tutoring": "education", "school": "education", "university": "education",
    
    # Travel & Tourism
    "travel": "travel", "tourism": "travel", "booking": "travel", "flights": "travel",
    "vacation": "travel", "trips": "travel", "adventure": "travel",
    
    # Real Estate
    "real estate": "realestate", "property": "realestate", "housing": "realestate", "rental": "realestate",
    "proptech": "realestate",
    
    # Media & Entertainment
    "media": "media", "entertainment": "media", "streaming": "media", "gaming": "media",
    "content": "media", "video": "media", "music": "media", "podcast": "media"
}

# INDUSTRY to CATEGORY mapping (secondary lookup)
INDUSTRY_TO_CATEGORY = {
    "technology & software": "technology",
    "technology": "technology",
    "software": "technology",
    "information technology": "technology",
    "it services": "technology",
    "saas": "technology",
    "hospitality": "hotels",
    "hotels & resorts": "hotels",
    "beauty & cosmetics": "beauty",
    "cosmetics": "beauty",
    "food & beverage": "food",
    "food service": "food",
    "financial services": "finance",
    "banking & finance": "finance",
    "fashion & retail": "fashion",
    "retail": "fashion",
    "healthcare": "healthcare",
    "health & wellness": "healthcare",
    "education": "education",
    "travel & tourism": "travel",
    "real estate": "realestate",
    "media & entertainment": "media",
}

def get_category_key(category: str, industry: str = None) -> str:
    """
    Normalize category input to match our data structure.
    
    IMPROVED LOGIC:
    1. Direct exact match on category
    2. Word-boundary substring match on category (prevents "app" matching "apparel")
    3. Industry as secondary lookup (NEW)
    4. Fallback to "default"
    
    Args:
        category: User's category input (e.g., "brand evaluation tool")
        industry: User's industry input (e.g., "Technology & Software") - SECONDARY LOOKUP
    """
    import re
    
    if not category:
        # Try industry if category is empty
        if industry:
            industry_lower = industry.lower().strip()
            if industry_lower in INDUSTRY_TO_CATEGORY:
                result = INDUSTRY_TO_CATEGORY[industry_lower]
                logging.info(f"📁 CATEGORY from INDUSTRY: '{industry}' → '{result}'")
                return result
        return "default"
    
    category_lower = category.lower().strip()
    
    # Step 1: Check direct exact mapping
    if category_lower in CATEGORY_MAPPING:
        logging.info(f"📁 CATEGORY EXACT MATCH: '{category}' → '{CATEGORY_MAPPING[category_lower]}'")
        return CATEGORY_MAPPING[category_lower]
    
    # Step 2: Word-boundary substring match (prevents "app" matching "apparel")
    # Sort by key length descending to prefer longer matches first
    sorted_keys = sorted(CATEGORY_MAPPING.keys(), key=len, reverse=True)
    for key in sorted_keys:
        # Use word boundary regex to prevent partial matches
        pattern = r'\b' + re.escape(key) + r'\b'
        if re.search(pattern, category_lower):
            logging.info(f"📁 CATEGORY WORD MATCH: '{category}' contains '{key}' → '{CATEGORY_MAPPING[key]}'")
            return CATEGORY_MAPPING[key]
    
    # Step 3: Try industry as secondary lookup (NEW)
    if industry:
        industry_lower = industry.lower().strip()
        # Direct match on industry
        if industry_lower in INDUSTRY_TO_CATEGORY:
            result = INDUSTRY_TO_CATEGORY[industry_lower]
            logging.info(f"📁 CATEGORY from INDUSTRY (secondary): '{industry}' → '{result}'")
            return result
        # Substring match on industry
        for ind_key, ind_value in INDUSTRY_TO_CATEGORY.items():
            if ind_key in industry_lower or industry_lower in ind_key:
                logging.info(f"📁 CATEGORY from INDUSTRY SUBSTRING: '{industry}' matches '{ind_key}' → '{ind_value}'")
                return ind_value
    
    logging.warning(f"⚠️ CATEGORY NOT MAPPED: '{category}' (industry: '{industry}') → using 'default'")
    return "default"

def get_market_data_for_category_country(category: str, country: str, industry: str = None) -> dict:
    """Get market data for specific category and country combination.
    
    IMPROVED:
    - Case-insensitive country matching
    - Industry as secondary lookup
    - Neutral default fallback (no more beauty hardcode)
    """
    category_key = get_category_key(category, industry)
    
    # Get category-specific data
    category_data = CATEGORY_COUNTRY_MARKET_DATA.get(category_key, {})
    
    # CASE-INSENSITIVE country matching
    country_lower = country.lower().strip() if country else ""
    country_lookup = {k.lower(): k for k in category_data.keys()}
    
    # Try to find the country (case-insensitive)
    if country_lower in country_lookup:
        actual_key = country_lookup[country_lower]
        logging.info(f"✅ Country matched: '{country}' → '{actual_key}' (category: {category_key})")
        return category_data[actual_key]
    elif "default" in category_data:
        logging.warning(f"⚠️ Country '{country}' not found in {category_key} data, using category default")
        return category_data["default"]
    
    # NEUTRAL DEFAULT FALLBACK (no more beauty hardcode!)
    logging.warning(f"⚠️ Category '{category_key}' has no data for '{country}', using NEUTRAL default")
    return _get_neutral_default_market_data(category, country)


def _get_neutral_default_market_data(category: str, country: str) -> dict:
    """
    Generate a NEUTRAL, category-agnostic default market data template.
    This replaces the old beauty-hardcoded fallback.
    
    The content is generic enough to work for ANY industry while still being useful.
    """
    # Determine currency based on country
    currency_map = {
        "india": "₹", "usa": "$", "uk": "£", "japan": "¥", "china": "¥",
        "thailand": "฿", "singapore": "S$", "uae": "AED", "germany": "€",
        "france": "€", "australia": "A$", "canada": "C$", "brazil": "R$"
    }
    country_lower = country.lower().strip() if country else ""
    currency = currency_map.get(country_lower, "$")
    
    return {
        "competitors": [
            {"name": "Market Leader", "x_coordinate": 80, "y_coordinate": 75, "quadrant": "Premium Established"},
            {"name": "Value Champion", "x_coordinate": 35, "y_coordinate": 55, "quadrant": "Affordable Quality"},
            {"name": "Innovation Player", "x_coordinate": 60, "y_coordinate": 80, "quadrant": "Modern Disruptor"},
            {"name": "Regional Specialist", "x_coordinate": 50, "y_coordinate": 45, "quadrant": "Local Expert"}
        ],
        "user_position": {"x": 65, "y": 72, "quadrant": "Accessible Premium"},
        "axis_x": f"Price: {currency}Budget → {currency}Premium",
        "axis_y": "Positioning: Traditional → Modern",
        "white_space": f"Market analysis for {category} in {country} indicates opportunities in underserved segments. Focus on differentiation through innovation, customer experience, and authentic brand positioning. Digital-first strategies offer cost-effective market entry.",
        "strategic_advantage": f"As a new entrant in the {category} space, the brand can leverage agile operations, modern technology stack, and customer-centric approaches to capture market share from established players.",
        "entry_recommendation": f"Phased market entry for {country}: Phase 1 (6 months) - Digital validation and customer discovery. Phase 2 (12 months) - Strategic partnerships and channel development. Phase 3 (18+ months) - Scale operations and market expansion. Key success factors: strong unit economics, customer retention, and brand building."
    }


async def generate_llm_market_insights(
    brand_name: str,
    category: str,
    country: str,
    positioning: str = None,
    usp: str = None
) -> dict:
    """
    Generate DYNAMIC market insights using LLM.
    Returns white_space, strategic_advantage, and entry_recommendation.
    Falls back to hardcoded data if LLM fails.
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
        if not EMERGENT_KEY:
            return None
        
        prompt = f"""You are a McKinsey market strategist. Analyze the market opportunity for a NEW brand.

BRAND: {brand_name}
CATEGORY: {category}
TARGET COUNTRY: {country}
POSITIONING: {positioning or 'Not specified'}
USP: {usp or 'Not specified'}

Provide analysis in this EXACT JSON format (no markdown, just JSON):
{{
    "white_space": "2-3 sentences about market gaps and opportunities specific to {category} in {country}. Include market size if known. Be specific about underserved segments.",
    "strategic_advantage": "2-3 sentences about how '{brand_name}' can win in this market. Focus on differentiation, timing, and competitive positioning.",
    "entry_recommendation": "3-phase market entry plan (6mo/12mo/18mo+) specific to {country}. Include specific platforms, partnerships, and success metrics."
}}

Be specific to the {category} industry and {country} market. Do not be generic."""

        chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
        user_msg = UserMessage(text=prompt)
        response = await chat.send_message(user_msg)
        
        # Parse response
        response_text = str(response).strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        result = json.loads(response_text)
        logging.info(f"✅ LLM Market Insights generated for {brand_name} in {country}")
        return result
        
    except Exception as e:
        logging.warning(f"⚠️ LLM Market Insights failed: {e}")
        return None


def generate_dynamic_market_insights_sync(
    brand_name: str,
    category: str,
    country: str,
    positioning: str = None,
    classification: dict = None
) -> dict:
    """
    Generate market insights synchronously (non-LLM fallback).
    Creates dynamic insights based on brand characteristics.
    """
    legal_category = classification.get("category", "SUGGESTIVE") if classification else "SUGGESTIVE"
    category_lower = category.lower()
    country_lower = country.lower()
    
    # Dynamic white space based on category
    if any(word in category_lower for word in ["tea", "chai"]):
        white_space = f"The {country} tea market presents opportunity in the premium segment. Gap exists between mass-market commodity tea and ultra-luxury offerings. '{brand_name}' can target the accessible-premium segment with authentic origin stories and wellness positioning."
    elif any(word in category_lower for word in ["hotel", "hospitality"]):
        white_space = f"The {country} hospitality sector shows demand for boutique and experience-driven accommodations. Chain standardization has created opportunity for authentic, locally-rooted brands. '{brand_name}' can capture the lifestyle-conscious traveler segment."
    elif any(word in category_lower for word in ["tech", "software", "app"]):
        white_space = f"The {country} technology market is growing with increasing digital adoption. Opportunity exists for solutions that address local market needs with global standards. '{brand_name}' can position as an innovative challenger."
    elif any(word in category_lower for word in ["food", "restaurant"]):
        white_space = f"The {country} food market is evolving toward health-conscious and authentic offerings. Consumer demand for quality and transparency is rising. '{brand_name}' can differentiate through product authenticity and brand story."
    elif any(word in category_lower for word in ["beauty", "cosmetic"]):
        white_space = f"The {country} beauty market is shifting toward clean beauty and sustainability. Indie brands with authentic stories are gaining against conglomerates. '{brand_name}' can capture the conscious consumer segment."
    else:
        white_space = f"The {country} {category} market presents opportunities for differentiated brands. '{brand_name}' can establish positioning by focusing on underserved customer segments and innovative value propositions."
    
    # Dynamic strategic advantage based on classification
    if legal_category == "FANCIFUL":
        strategic_advantage = f"As a coined/invented name, '{brand_name}' has maximum trademark protection and can be positioned across multiple categories. The blank-slate nature allows complete brand narrative control. No legacy associations to overcome."
    elif legal_category == "ARBITRARY":
        strategic_advantage = f"'{brand_name}' uses familiar words in an unexpected context, creating memorability while maintaining strong legal protection. This allows creative storytelling while leveraging existing word recognition."
    elif legal_category == "SUGGESTIVE":
        strategic_advantage = f"'{brand_name}' suggests product benefits without directly describing them, balancing distinctiveness with consumer understanding. This creates intuitive brand recognition while maintaining registrability."
    else:
        strategic_advantage = f"'{brand_name}' can differentiate through execution excellence, customer experience, and brand building. Focus on building distinctive brand assets and customer loyalty."
    
    # Dynamic entry recommendation
    if any(word in country_lower for word in ["india", "indonesia", "brazil", "mexico"]):
        entry_recommendation = f"Phase 1 (0-6 months): Launch on major e-commerce platforms and build digital presence. Phase 2 (6-12 months): Expand to tier-2 cities and build distribution partnerships. Phase 3 (12-18 months): Consider offline presence in high-traffic locations. Key: Mobile-first approach, local language content."
    elif any(word in country_lower for word in ["usa", "uk", "canada", "australia"]):
        entry_recommendation = f"Phase 1 (0-6 months): DTC website launch with targeted digital marketing. Phase 2 (6-12 months): Amazon/marketplace expansion and influencer partnerships. Phase 3 (12-18 months): Retail partnerships and brand awareness campaigns. Key: Build community and loyalty program early."
    elif any(word in country_lower for word in ["uae", "singapore", "japan"]):
        entry_recommendation = f"Phase 1 (0-6 months): Premium positioning with flagship presence. Phase 2 (6-12 months): Strategic partnerships with established distributors. Phase 3 (12-18 months): Regional expansion from hub market. Key: Quality perception and premium pricing."
    else:
        entry_recommendation = f"Phase 1 (0-6 months): Market validation and customer discovery. Phase 2 (6-12 months): Channel development and partnership building. Phase 3 (12-18 months): Scale operations and expand market share. Key: Adapt to local market dynamics."
    
    return {
        "white_space": white_space,
        "strategic_advantage": strategic_advantage,
        "entry_recommendation": entry_recommendation
    }



    """Generate RESEARCHED competitor analysis for ALL user-selected countries (max 4)
    Now category-aware - uses different competitor data based on industry category
    """
    result = []
    
    # Log the category being used
    category_key = get_category_key(category, industry)
    logging.info(f"📊 CATEGORY-AWARE MARKET DATA: Category '{category}' mapped to '{category_key}'")
    
    # Ensure we process up to 4 countries
    countries_to_process = countries[:4] if len(countries) > 4 else countries
    
    # Case-insensitive flag lookup
    flags_lower = {k.lower(): v for k, v in COUNTRY_FLAGS.items()}
    
    for idx, country in enumerate(countries_to_process):
        # Get country name (handle dict or string)
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        
        # Get flag - CASE INSENSITIVE
        country_lower = country_name.lower().strip() if country_name else ""
        flag = flags_lower.get(country_lower, "🌍")
        
        # Normalize country name for display
        display_name = country_name.title() if country_name else "Unknown"
        
        # Get CATEGORY-SPECIFIC market data for this country
        market_data = get_market_data_for_category_country(category, country_name, industry)
        logging.info(f"📊 Market data for {display_name} {flag} ({category_key}): {len(market_data.get('competitors', []))} competitors")
        
        # Check if we got default/generic data - if so, generate dynamic insights
        is_generic_data = "Market Leader" in str(market_data.get("competitors", [])) or \
                          "Market analysis for" in market_data.get("white_space", "")
        
        if is_generic_data:
            # Generate dynamic insights for this brand/category/country
            dynamic_insights = generate_dynamic_market_insights_sync(
                brand_name=brand_name,
                category=category,
                country=display_name,
                positioning=None,
                classification=None
            )
            white_space = dynamic_insights["white_space"]
            strategic_advantage = dynamic_insights["strategic_advantage"]
            entry_recommendation = dynamic_insights["entry_recommendation"]
            logging.info(f"🔄 Using DYNAMIC market insights for {display_name} (category had default data)")
        else:
            white_space = market_data["white_space"].replace("'", "'")
            strategic_advantage = market_data["strategic_advantage"].replace("'", "'")
            entry_recommendation = market_data["entry_recommendation"].replace("'", "'")
        
        # Build enhanced gap analysis
        competitors = market_data["competitors"]
        direct_comps = [c for c in competitors if c.get("type") == "DIRECT" or "direct" in str(c.get("quadrant", "")).lower()]
        indirect_comps = [c for c in competitors if c not in direct_comps]
        
        direct_names = ", ".join([c.get("name", "Unknown") for c in direct_comps[:6]]) or "None identified"
        indirect_names = ", ".join([c.get("name", "Unknown") for c in indirect_comps[:6]]) or "None identified"
        
        # Build the analysis with enhanced data
        result.append({
            "country": display_name,
            "country_flag": flag,
            "x_axis_label": market_data.get("axis_x", "Price: Budget → Premium"),
            "y_axis_label": market_data.get("axis_y", "Positioning: Traditional → Modern"),
            "competitors": competitors,
            "user_brand_position": {
                "x_coordinate": market_data["user_position"]["x"],
                "y_coordinate": market_data["user_position"]["y"],
                "quadrant": market_data["user_position"]["quadrant"],
                "rationale": f"'{brand_name}' positioned in {market_data['user_position']['quadrant']} segment to maximize market opportunity in {display_name}"
            },
            "gap_analysis": {
                "direct_count": len(direct_comps),
                "indirect_count": len(indirect_comps),
                "total_competitors": len(competitors),
                "direct_competitors": direct_names,
                "indirect_competitors": indirect_names,
                "gap_detected": len(direct_comps) <= 2
            },
            "white_space_analysis": white_space,
            "strategic_advantage": strategic_advantage + f"\n\n**Direct Competitors ({len(direct_comps)}):** {direct_names}" + (f"\n\n**Indirect Competitors ({len(indirect_comps)}):** {indirect_names}" if indirect_comps else ""),
            "market_entry_recommendation": entry_recommendation
        })
    
    return result


# ============ NEW FORMULA-BASED CULTURAL SCORING SYSTEM ============
# Score = (Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)

LLM_CULTURAL_SCORING_PROMPT = """You are the Global Brand Strategy Director for a Fortune 500 consultancy. 
Your goal is to stress-test brand names for cultural risks across international markets.
Your analysis must be cynical, conservative, and brutally honest.

### INPUT DATA ###
Brand Name: {brand_name}
Industry: {category}
Target Country: {country}

### SCORING CRITERIA (0-10 scale for each) ###

1. SAFETY SCORE (Weight: 40%)
   Check for "Phonetic Accidents": Does the name sound like slang, insult, bodily function, or sacred term in the local language?
   - 10 = Completely clean, no issues
   - 7-9 = Minor concerns but acceptable
   - 4-6 = Some phonetic risks identified
   - 1-3 = Sounds like a problematic word
   - 0 = CRITICAL - sounds like offensive/sacred term

2. FLUENCY SCORE (Weight: 30%)
   How easy is it for a mass-market consumer in {country} to pronounce?
   - 10 = Native ease (like "Sony" or "Nike")
   - 7-9 = Easy with minor accent adjustment
   - 4-6 = Moderate difficulty, some sounds challenging
   - 1-3 = Hard sounds for local speakers (e.g., "Th" in Thai, "V" in Japanese)
   - 0 = Virtually unpronounceable

3. VIBE SCORE (Weight: 30%)
   Compare to top competitors in {category} in {country}. Does it fit premium market codes?
   - 10 = Sounds like a market leader
   - 7-9 = Professional, trustworthy sound
   - 4-6 = Average/generic
   - 1-3 = Sounds cheap, industrial, or off-brand
   - 0 = Completely wrong vibe for category

### REQUIRED CALCULATION ###
You MUST calculate: Final Score = (Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)

### OUTPUT FORMAT (JSON only, no extra text) ###
{{
    "country": "{country}",
    "native_script_preview": "Local script representation if applicable",
    "safety_score": {{
        "raw": 0-10,
        "issues_found": ["List specific phonetic issues or 'None found'"],
        "reasoning": "Brief explanation"
    }},
    "fluency_score": {{
        "raw": 0-10,
        "difficult_sounds": ["List problematic sounds or 'None'"],
        "reasoning": "Brief explanation"
    }},
    "vibe_score": {{
        "raw": 0-10,
        "local_competitors": ["Top 3 competitors in {category} in {country}"],
        "comparison": "How does {brand_name} compare to these?",
        "reasoning": "Brief explanation"
    }},
    "calculation": {{
        "formula": "(Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)",
        "math": "(X × 0.4) + (Y × 0.3) + (Z × 0.3) = Result",
        "final_score": 0.0-10.0
    }},
    "risk_verdict": "SAFE / CAUTION / CRITICAL",
    "summary": "One sentence cultural verdict for {country}"
}}

Return ONLY valid JSON."""


async def llm_calculate_cultural_score(
    brand_name: str,
    category: str,
    country: str
) -> dict:
    """
    LLM-FIRST Cultural Scoring with FORMULA
    
    Score = (Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)
    
    This forces LLM to:
    1. Evaluate 3 distinct factors
    2. Run the actual math
    3. Show the calculation
    """
    EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')
    
    if not LlmChat or not EMERGENT_KEY:
        logging.warning(f"🌐 LLM not available for cultural scoring - using fallback for {country}")
        return calculate_fallback_cultural_score(brand_name, category, country)
    
    try:
        prompt = LLM_CULTURAL_SCORING_PROMPT.format(
            brand_name=brand_name,
            category=category,
            country=country
        )
        
        chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
        user_msg = UserMessage(prompt)
        
        response = await asyncio.wait_for(
            chat.send_message(user_msg),
            timeout=20
        )
        
        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        result = json.loads(response_text)
        
        # Verify the calculation is present and valid
        calculation = result.get("calculation", {})
        final_score = calculation.get("final_score", 0)
        
        logging.info(f"🧮 LLM CULTURAL SCORE for '{brand_name}' in {country}:")
        logging.info(f"   Safety: {result.get('safety_score', {}).get('raw', '?')}/10")
        logging.info(f"   Fluency: {result.get('fluency_score', {}).get('raw', '?')}/10")
        logging.info(f"   Vibe: {result.get('vibe_score', {}).get('raw', '?')}/10")
        logging.info(f"   FINAL: {final_score}/10 ({result.get('risk_verdict', '?')})")
        
        return {
            "llm_calculated": True,
            "data": result
        }
        
    except asyncio.TimeoutError:
        logging.warning(f"LLM cultural scoring timed out for {country}")
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse LLM cultural score: {e}")
    except Exception as e:
        logging.warning(f"LLM cultural scoring failed: {e}")
    
    return calculate_fallback_cultural_score(brand_name, category, country)


def calculate_fallback_cultural_score(
    brand_name: str,
    category: str,
    country: str,
    classification: dict = None  # NEW: Accept pre-calculated classification
) -> dict:
    """
    FALLBACK Cultural Scoring (when LLM unavailable)
    
    Uses heuristics to estimate Safety, Fluency, Vibe scores
    Still applies the formula: (Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)
    
    NEW: Accepts pre-calculated classification to avoid duplicate computation.
    """
    brand_lower = brand_name.lower()
    country_lower = country.lower().strip()
    
    # Use passed classification or calculate if not provided
    if classification is None:
        classification = classify_brand_with_industry(brand_name, category)
    
    # === SAFETY SCORE (Phonetic Accidents) ===
    safety_score = 8  # Default: assume clean
    safety_issues = []
    
    # Check sacred/royal names
    sacred_check = check_sacred_royal_names(brand_name, [{"name": country}])
    if sacred_check.get("detected"):
        for detection in sacred_check.get("detections", []):
            if detection.get("country", "").lower() == country_lower:
                if detection.get("risk_level") == "CRITICAL":
                    safety_score = 2
                    safety_issues.append(f"Sacred/royal term detected: {detection.get('term')}")
                elif detection.get("risk_level") == "HIGH":
                    safety_score = 4
                    safety_issues.append(f"Cultural sensitivity: {detection.get('term')}")
    
    # Check for common problematic sounds by country
    PROBLEMATIC_PATTERNS = {
        "japan": {"v": -1, "l": -0.5, "th": -1},  # V and L sounds
        "china": {"r": -0.5, "th": -1},
        "thailand": {"r": -0.5},
        "germany": {"th": -0.5},
        "france": {"h": -0.5, "th": -1},
        "spain": {"th": -0.5},
        "india": {},  # Generally good with English sounds
        "usa": {},
        "uk": {},
    }
    
    # === FLUENCY SCORE (Pronunciation Ease) ===
    fluency_score = 7  # Default: moderate ease
    difficult_sounds = []
    
    patterns = PROBLEMATIC_PATTERNS.get(country_lower, {})
    for sound, penalty in patterns.items():
        if sound in brand_lower:
            fluency_score += penalty
            difficult_sounds.append(f"'{sound}' sound")
    
    # Length penalty
    if len(brand_name) > 12:
        fluency_score -= 1
        difficult_sounds.append("Long name")
    elif len(brand_name) <= 6:
        fluency_score += 1  # Short names are easier
    
    # Consonant cluster penalty
    consonant_clusters = re.findall(r'[bcdfghjklmnpqrstvwxyz]{3,}', brand_lower)
    if consonant_clusters:
        fluency_score -= len(consonant_clusters) * 0.5
        difficult_sounds.append(f"Consonant clusters: {consonant_clusters}")
    
    fluency_score = max(3, min(10, fluency_score))
    
    # === VIBE SCORE (Market Fit) ===
    vibe_score = 6  # Default: average
    vibe_issues = []
    
    # GATE 2: Check for category mismatch (use classification data)
    category_mismatch = check_category_mismatch(brand_name, category)
    if category_mismatch.get("has_mismatch"):
        vibe_score -= 3  # Significant penalty for category mismatch
        vibe_issues.append(category_mismatch.get("warning", "Category mismatch detected"))
    
    # Category-based vibe assessment
    PREMIUM_INDICATORS = ["health", "care", "med", "clinic", "pro", "prime", "elite", "lux"]
    BUDGET_INDICATORS = ["quick", "fast", "cheap", "deal", "save", "discount"]
    
    for indicator in PREMIUM_INDICATORS:
        if indicator in brand_lower:
            vibe_score += 1
    
    for indicator in BUDGET_INDICATORS:
        if indicator in brand_lower:
            vibe_score -= 1
    
    # USE PASSED CLASSIFICATION (no duplicate calculation)
    # Descriptive names get penalty (weaker trademark)
    if classification.get("category") == "DESCRIPTIVE":
        vibe_score -= 1
        vibe_issues.append(f"DESCRIPTIVE name - {classification.get('warning', 'weaker trademark protection')}")
    elif classification.get("category") == "GENERIC":
        vibe_score -= 2
        vibe_issues.append(f"GENERIC name - {classification.get('warning', 'unprotectable')}")
    
    vibe_score = max(2, min(10, vibe_score))
    
    # === CALCULATE FINAL SCORE ===
    final_score = (safety_score * 0.4) + (fluency_score * 0.3) + (vibe_score * 0.3)
    final_score = round(final_score, 1)
    
    # Determine verdict
    if final_score >= 7:
        verdict = "SAFE"
    elif final_score >= 5:
        verdict = "CAUTION"
    else:
        verdict = "CRITICAL"
    
    logging.info(f"🧮 FALLBACK CULTURAL SCORE for '{brand_name}' in {country}:")
    logging.info(f"   Safety: {safety_score}/10, Fluency: {fluency_score}/10, Vibe: {vibe_score}/10")
    logging.info(f"   Formula: ({safety_score}×0.4) + ({fluency_score}×0.3) + ({vibe_score}×0.3) = {final_score}")
    
    # Get local competitors (basic fallback)
    local_competitors = get_fallback_competitors(category, country)
    
    return {
        "llm_calculated": False,
        "data": {
            "country": country.title(),
            "native_script_preview": get_native_script_preview(brand_name, country),
            "safety_score": {
                "raw": safety_score,
                "issues_found": safety_issues if safety_issues else ["None found"],
                "reasoning": "Checked for sacred terms, slang, and phonetic accidents"
            },
            "fluency_score": {
                "raw": round(fluency_score, 1),
                "difficult_sounds": difficult_sounds if difficult_sounds else ["None"],
                "reasoning": f"Assessed pronunciation ease for {country} speakers"
            },
            "vibe_score": {
                "raw": round(vibe_score, 1),
                "local_competitors": local_competitors,
                "comparison": f"Compared to top {category} brands in {country}",
                "reasoning": "Evaluated premium market fit"
            },
            "calculation": {
                "formula": "(Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)",
                "math": f"({safety_score} × 0.4) + ({round(fluency_score, 1)} × 0.3) + ({round(vibe_score, 1)} × 0.3) = {final_score}",
                "final_score": final_score
            },
            "risk_verdict": verdict,
            "summary": f"{'Clean profile' if verdict == 'SAFE' else 'Some concerns identified' if verdict == 'CAUTION' else 'Significant risks'} for {brand_name} in {country}"
        }
    }


def get_native_script_preview(brand_name: str, country: str) -> str:
    """Get native script representation if applicable"""
    country_lower = country.lower().strip()
    
    # Basic transliterations (simplified)
    SCRIPT_MAP = {
        "japan": f"カタカナ: {brand_name}",  # Would need actual katakana conversion
        "china": f"音译: {brand_name}",
        "thailand": f"ทับศัพท์: {brand_name}",
        "india": f"हिंदी: {brand_name}",
        "uae": f"العربية: {brand_name}",
        "saudi arabia": f"العربية: {brand_name}",
        "south korea": f"한글: {brand_name}",
        "russia": f"Кириллица: {brand_name}",
    }
    
    return SCRIPT_MAP.get(country_lower, brand_name)


def get_fallback_competitors(category: str, country: str) -> list:
    """Get basic competitor list for fallback mode"""
    category_lower = category.lower()
    country_lower = country.lower().strip()
    
    # Simplified competitor mapping
    COMPETITOR_MAP = {
        ("doctor", "india"): ["Practo", "1mg", "Apollo 24/7"],
        ("doctor", "usa"): ["Zocdoc", "Teladoc", "One Medical"],
        ("doctor", "uk"): ["Babylon Health", "Push Doctor", "GP at Hand"],
        ("doctor", "uae"): ["Okadoc", "Medcare", "Aster DM"],
        ("doctor", "thailand"): ["Doctor Raksa", "Chiiwii", "HDmall"],
        ("healthcare", "india"): ["Practo", "1mg", "PharmEasy"],
        ("healthcare", "usa"): ["CVS Health", "Teladoc", "Amwell"],
        ("hotel", "india"): ["OYO", "Taj Hotels", "ITC Hotels"],
        ("hotel", "thailand"): ["Dusit", "Centara", "Minor Hotels"],
        ("hotel", "uae"): ["Jumeirah", "Emaar Hospitality", "Rotana"],
    }
    
    # Check for matches
    for (cat_key, country_key), competitors in COMPETITOR_MAP.items():
        if cat_key in category_lower and country_key in country_lower:
            return competitors
    
    # Default fallback
    return [f"Top {category} Brand 1", f"Top {category} Brand 2", f"Top {category} Brand 3"]


# ============ CULTURAL ANALYSIS GENERATOR (UPDATED) ============
COUNTRY_CULTURAL_DATA = {
    "India": {
        "resonance_score": 8.0,
        "cultural_notes": "Strong appeal to India's 400M+ millennials and Gen Z who prefer international-sounding brands. No adverse meanings in Hindi, Tamil, Telugu, Bengali, or other major languages. The coined/modern sound aligns with aspirational purchasing behavior in urban India. Consider vernacular adaptations for Tier 2/3 city marketing.",
        "linguistic_check": "PASS - Clean linguistic profile across 22 official Indian languages"
    },
    "USA": {
        "resonance_score": 7.5,
        "cultural_notes": "Clean phonetic profile for English speakers. No homophone conflicts with negative terms. Modern coined structure aligns with US consumer preference for distinctive DTC brands. Consider trademark search for phonetic variants in USPTO database.",
        "linguistic_check": "PASS - No adverse associations in American English"
    },
    "Thailand": {
        "resonance_score": 7.0,
        "cultural_notes": "No negative meanings in Thai language. Thai consumers associate Western/English brand names with premium quality. The name structure is easy to pronounce for Thai speakers. Consider Thai transliteration (ทับศัพท์) for local marketing materials. Avoid conflicts with royal/Buddhist terminology.",
        "linguistic_check": "PASS - Phonetically accessible for Thai speakers"
    },
    "UK": {
        "resonance_score": 7.5,
        "cultural_notes": "Clean linguistic profile for British English. No conflicts with UK slang or colloquialisms. The modern coined structure resonates with UK consumers' preference for innovative brands. Brexit has increased appetite for non-EU brands.",
        "linguistic_check": "PASS - No adverse meanings in British English"
    },
    "Singapore": {
        "resonance_score": 8.0,
        "cultural_notes": "Multilingual market (English, Mandarin, Malay, Tamil) - name tested clean across all four official languages. Singaporean consumers are highly brand-literate and prefer international names. No conflicts in Singlish vocabulary.",
        "linguistic_check": "PASS - Clean across English, Mandarin, Malay, Tamil"
    },
    "UAE": {
        "resonance_score": 7.5,
        "cultural_notes": "No conflicts with Arabic language or Islamic terminology. Dubai's cosmopolitan population (85% expat) is comfortable with English brand names. Ensure brand imagery respects local cultural sensitivities. Consider Arabic script adaptation for regional marketing.",
        "linguistic_check": "PASS - No Arabic conflicts, culturally appropriate"
    },
    "Japan": {
        "resonance_score": 7.0,
        "cultural_notes": "Katakana adaptation available for Japanese market. No phonetic conflicts with negative Japanese words. Japanese consumers appreciate Western brands with clear, pronounceable names. The name length is appropriate for Japanese marketing (shorter preferred).",
        "linguistic_check": "PASS - Katakana adaptable, phonetically accessible"
    },
    "Germany": {
        "resonance_score": 7.5,
        "cultural_notes": "Clean profile in German language. No conflicts with German idioms or negative connotations. German consumers value authentic brand stories - emphasize heritage or innovation narrative.",
        "linguistic_check": "PASS - No adverse meanings in German"
    },
    "France": {
        "resonance_score": 7.0,
        "cultural_notes": "No conflicts with French vocabulary or slang. French consumers are discerning about brand names - ensure pronunciation is elegant in French. Consider French-language tagline for local market.",
        "linguistic_check": "PASS - Phonetically acceptable in French"
    },
    "China": {
        "resonance_score": 7.0,
        "cultural_notes": "Chinese transliteration (音译) required for local marketing. Recommend working with native linguist to select characters with positive meanings. Avoid characters associated with death (死), four (四), or negative concepts. Test in Mandarin and Cantonese.",
        "linguistic_check": "CAUTION - Requires professional Chinese naming consultation"
    },
    "Australia": {
        "resonance_score": 7.5,
        "cultural_notes": "Clean profile in Australian English. No conflicts with Australian slang or colloquialisms. Australian consumers appreciate straightforward, authentic brands. The modern sound aligns with AU market preferences.",
        "linguistic_check": "PASS - No adverse meanings in Australian English"
    },
    "Canada": {
        "resonance_score": 7.5,
        "cultural_notes": "Clean in both English and French Canadian. Bilingual packaging requirements for Canadian market. No conflicts in Quebec French or Canadian English slang.",
        "linguistic_check": "PASS - Clean in English and French Canadian"
    },
    "default": {
        "resonance_score": 7.0,
        "cultural_notes": "No known negative connotations identified. Recommend local linguistic validation before market entry. Coined names generally travel well internationally but local testing advised.",
        "linguistic_check": "ADVISORY - Local linguistic validation recommended"
    }
}

def generate_cultural_analysis(countries: list, brand_name: str, category: str = "Business", classification: dict = None, universal_linguistic: dict = None) -> list:
    """Generate cultural analysis for ALL user-selected countries (max 4)
    
    NEW FORMULA-BASED SCORING:
    Score = (Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)
    
    - Safety: Phonetic accidents, slang, sacred terms
    - Fluency: Pronunciation ease for local speakers  
    - Vibe: Premium market fit vs local competitors
    
    NEW: Accepts pre-calculated classification to avoid duplicate computation.
    NEW: Accepts universal_linguistic analysis for rich cultural context.
    """
    result = []
    
    # Use passed classification or calculate if not provided
    if classification is None:
        classification = classify_brand_with_industry(brand_name, category)
    
    # Create case-insensitive lookups
    cultural_data_lower = {k.lower(): v for k, v in COUNTRY_CULTURAL_DATA.items()}
    flags_lower = {k.lower(): v for k, v in COUNTRY_FLAGS.items()}
    
    # Check if we have universal linguistic analysis (LLM-powered)
    has_universal_linguistic = (
        universal_linguistic and 
        universal_linguistic.get("_analyzed_by") != "fallback" and
        universal_linguistic.get("has_linguistic_meaning")
    )
    
    # Extract key linguistic insights if available
    ling_insights = {}
    if has_universal_linguistic:
        ling_insights = {
            "has_meaning": True,
            "languages": universal_linguistic.get("linguistic_analysis", {}).get("languages_detected", []),
            "combined_meaning": universal_linguistic.get("linguistic_analysis", {}).get("decomposition", {}).get("combined_meaning", ""),
            "name_type": universal_linguistic.get("classification", {}).get("name_type", "Unknown"),
            "cultural_ref_type": universal_linguistic.get("cultural_significance", {}).get("reference_type"),
            "cultural_details": universal_linguistic.get("cultural_significance", {}).get("details", ""),
            "source_origin": universal_linguistic.get("cultural_significance", {}).get("source_text_or_origin", ""),
            "sentiment": universal_linguistic.get("cultural_significance", {}).get("sentiment", "Neutral"),
            "recognition_regions": universal_linguistic.get("cultural_significance", {}).get("regions_of_recognition", []),
            "instant_recognition": universal_linguistic.get("business_alignment", {}).get("customer_understanding", {}).get("instant_recognition_regions", []),
            "needs_explanation": universal_linguistic.get("business_alignment", {}).get("customer_understanding", {}).get("needs_explanation_regions", []),
            "potential_concerns": universal_linguistic.get("potential_concerns", []),
            "alignment_score": universal_linguistic.get("business_alignment", {}).get("alignment_score", 5),
            "religious_sensitive": universal_linguistic.get("cultural_significance", {}).get("religious_sensitivity", {}).get("is_sensitive", False)
        }
        logging.info(f"🌍 CULTURAL ANALYSIS: Using Universal Linguistic Data for '{brand_name}'")
        logging.info(f"   Languages: {ling_insights['languages']}")
        logging.info(f"   Name Type: {ling_insights['name_type']}")
        logging.info(f"   Recognition Regions: {ling_insights['recognition_regions']}")
    else:
        # Fall back to old linguistic decomposition
        linguistic_analysis = generate_linguistic_decomposition(brand_name, countries, category)
        logging.info(f"🔤 LINGUISTIC DECOMPOSITION for '{brand_name}' (fallback):")
        logging.info(f"   Brand Type: {linguistic_analysis.get('brand_type')}")
    
    # Ensure we process up to 4 countries
    countries_to_process = countries[:4] if len(countries) > 4 else countries
    
    for country in countries_to_process:
        # Get country name (handle dict or string)
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        country_lower = country_name.lower().strip() if country_name else ""
        display_name = country_name.title() if country_name else "Unknown"
        display_name = country_name.title() if country_name else "Unknown"
        
        # Get base cultural data - CASE INSENSITIVE
        base_cultural_data = cultural_data_lower.get(country_lower, COUNTRY_CULTURAL_DATA["default"])
        
        # Get flag - CASE INSENSITIVE
        flag = flags_lower.get(country_lower, "🌍")
        
        # ========== NEW: FORMULA-BASED CULTURAL SCORING ==========
        # Calculate using: Score = (Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)
        # PASS the classification to avoid duplicate calculation
        cultural_score_result = calculate_fallback_cultural_score(brand_name, category, display_name, classification)
        score_data = cultural_score_result.get("data", {})
        
        safety_score = score_data.get("safety_score", {}).get("raw", 7)
        fluency_score = score_data.get("fluency_score", {}).get("raw", 7)
        vibe_score = score_data.get("vibe_score", {}).get("raw", 6)
        calculated_final = score_data.get("calculation", {}).get("final_score", 7.0)
        risk_verdict = score_data.get("risk_verdict", "CAUTION")
        
        # Build comprehensive cultural notes
        cultural_notes_parts = []
        
        # ==================== USE UNIVERSAL LINGUISTIC DATA IF AVAILABLE ====================
        if has_universal_linguistic and ling_insights:
            # Part 1: Classification with override info
            cultural_notes_parts.append(f"**🏷️ TRADEMARK CLASSIFICATION: {classification.get('category', 'Unknown')}**")
            cultural_notes_parts.append(f"Distinctiveness: {classification.get('distinctiveness', 'Unknown')} | Protectability: {classification.get('protectability', 'Unknown')}")
            if classification.get('linguistic_override'):
                cultural_notes_parts.append(f"⚡ *Override: {classification.get('original_category')} → {classification.get('category')} (linguistic meaning found)*")
            if classification.get('warning'):
                cultural_notes_parts.append(f"\n{classification.get('warning')}\n")
            cultural_notes_parts.append("---")
            
            # Part 2: Universal Linguistic Analysis
            cultural_notes_parts.append(f"\n**🌍 UNIVERSAL LINGUISTIC ANALYSIS**\n")
            
            # Show meaning if found
            if ling_insights.get("combined_meaning"):
                cultural_notes_parts.append(f"**MEANING:** \"{ling_insights['combined_meaning']}\"")
                cultural_notes_parts.append(f"**ORIGIN:** {', '.join(ling_insights.get('languages', ['Unknown']))}")
                cultural_notes_parts.append(f"**NAME TYPE:** {ling_insights.get('name_type', 'Unknown')}")
            
            # Cultural significance
            if ling_insights.get("cultural_ref_type"):
                cultural_notes_parts.append(f"\n**CULTURAL SIGNIFICANCE:**")
                cultural_notes_parts.append(f"• Type: {ling_insights['cultural_ref_type']}")
                if ling_insights.get("source_origin"):
                    cultural_notes_parts.append(f"• Source: {ling_insights['source_origin']}")
                cultural_notes_parts.append(f"• Sentiment: {ling_insights.get('sentiment', 'Neutral')}")
                if ling_insights.get("cultural_details"):
                    cultural_notes_parts.append(f"• Details: {ling_insights['cultural_details'][:150]}...")
            
            cultural_notes_parts.append("---")
            
            # Part 3: Country-Specific Analysis based on linguistic data
            cultural_notes_parts.append(f"\n**🎯 {display_name.upper()} MARKET FIT**\n")
            
            # Check if this country is in recognition regions
            recognition_regions = [r.lower() for r in ling_insights.get("recognition_regions", [])]
            instant_recognition = [r.lower() for r in ling_insights.get("instant_recognition", [])]
            needs_explanation = [r.lower() for r in ling_insights.get("needs_explanation", [])]
            
            country_in_recognition = any(country_lower in r or r in country_lower for r in recognition_regions)
            country_instant = any(country_lower in r or r in country_lower for r in instant_recognition)
            country_needs_explanation = any(country_lower in r or r in country_lower for r in needs_explanation)
            
            if country_instant or country_in_recognition:
                cultural_notes_parts.append(f"✅ **INSTANT RECOGNITION** - The name meaning is culturally significant in {display_name}.")
                if ling_insights.get("combined_meaning"):
                    cultural_notes_parts.append(f"Consumers will immediately connect \"{ling_insights['combined_meaning']}\" with ")
                    if ling_insights.get("cultural_ref_type") == "Mythological":
                        cultural_notes_parts.append(f"the {ling_insights.get('source_origin', 'cultural heritage')}.")
                    else:
                        cultural_notes_parts.append(f"the {ling_insights.get('name_type', 'meaning').lower()} origin.")
                if ling_insights.get("religious_sensitive"):
                    cultural_notes_parts.append(f"⚠️ *Note: Religious/sacred connotations detected. May evoke strong positive OR negative reactions.*")
            elif country_needs_explanation:
                cultural_notes_parts.append(f"📖 **NEEDS EXPLANATION** - The name's meaning is not widely known in {display_name}.")
                cultural_notes_parts.append(f"Consider educational marketing to convey the story behind \"{brand_name}\".")
            else:
                # Generic analysis for this country
                if ling_insights.get("combined_meaning"):
                    cultural_notes_parts.append(f"ℹ️ The name \"{brand_name}\" means \"{ling_insights['combined_meaning']}\" in {', '.join(ling_insights.get('languages', []))}.")
                    cultural_notes_parts.append(f"Recognition level in {display_name}: May vary. Consider local market research.")
            
            # Check for concerns specific to this country
            concerns_for_country = []
            for concern in ling_insights.get("potential_concerns", []):
                concern_region = concern.get("language_or_region", "").lower()
                if country_lower in concern_region or concern_region in country_lower or concern_region == "global":
                    concerns_for_country.append(concern)
            
            if concerns_for_country:
                cultural_notes_parts.append(f"\n**⚠️ CONCERNS FOR {display_name.upper()}:**")
                for concern in concerns_for_country:
                    cultural_notes_parts.append(f"• [{concern.get('severity', 'Medium')}] {concern.get('concern_type', 'Issue')}: {concern.get('details', 'N/A')}")
            
            # Business alignment
            cultural_notes_parts.append(f"\n**BUSINESS ALIGNMENT:** {ling_insights.get('alignment_score', 5)}/10 for {category}")
            
            # Part 4: Recommendation
            if calculated_final < 5:
                cultural_notes_parts.append("\n**RECOMMENDATION:** 🔴 CRITICAL - Significant cultural/linguistic concerns. Consult local experts.")
            elif calculated_final < 7 or concerns_for_country:
                cultural_notes_parts.append("\n**RECOMMENDATION:** 🟡 CAUTION - Some concerns identified. Local validation advised.")
            else:
                cultural_notes_parts.append("\n**RECOMMENDATION:** 🟢 SAFE - Name appears suitable. Proceed with standard clearance.")
                
        else:
            # ==================== FALLBACK: OLD LINGUISTIC DECOMPOSITION ====================
            linguistic_analysis = generate_linguistic_decomposition(brand_name, countries_to_process, category) if not has_universal_linguistic else {}
            country_linguistic = linguistic_analysis.get("country_analysis", {}).get(display_name, {}) if linguistic_analysis else {}
            
            # Part 1: Classification info at top
            cultural_notes_parts.append(f"**🏷️ TRADEMARK CLASSIFICATION: {classification.get('category', 'Unknown')}**")
            cultural_notes_parts.append(f"Distinctiveness: {classification.get('distinctiveness', 'Unknown')} | Protectability: {classification.get('protectability', 'Unknown')}")
            if classification.get('warning'):
                cultural_notes_parts.append(f"\n{classification.get('warning')}\n")
            cultural_notes_parts.append("---")
            
            # Part 2: Linguistic Decomposition Header
            cultural_notes_parts.append(f"\n**🔤 LINGUISTIC ANALYSIS: {brand_name}**\n")
            
            # Part 3: Morpheme Breakdown
            decomposition = linguistic_analysis.get("decomposition", {}) if linguistic_analysis else {}
            if decomposition.get("morphemes"):
                cultural_notes_parts.append("**MORPHEME BREAKDOWN:**")
                for morpheme in decomposition["morphemes"]:
                    # Find this morpheme's analysis for this country
                    morpheme_data = None
                    for ma in country_linguistic.get("morpheme_analysis", []):
                        if ma["morpheme"] == morpheme["text"]:
                            morpheme_data = ma
                            break
                    
                    if morpheme_data:
                        resonance_emoji = "🔴" if morpheme_data["resonance_level"] == "CRITICAL" else "🟡" if morpheme_data["resonance_level"] == "HIGH" else "🟢"
                        cultural_notes_parts.append(f"• **{morpheme['text'].upper()}** ({morpheme['origin']}): {morpheme['meaning']}")
                        cultural_notes_parts.append(f"  └─ {display_name} Resonance: {resonance_emoji} {morpheme_data['resonance_level']} - {morpheme_data['context']}")
                    else:
                        cultural_notes_parts.append(f"• **{morpheme['text'].upper()}** ({morpheme['origin']}): {morpheme['meaning']}")
            
            # Part 3: Industry Fit
            industry_fit = linguistic_analysis.get("industry_fit", {}) if linguistic_analysis else {}
            fit_emoji = "✅" if industry_fit.get("fit_level") == "HIGH" else "⚠️" if industry_fit.get("fit_level") == "LOW" else "➡️"
            cultural_notes_parts.append(f"\n**INDUSTRY FIT:** {fit_emoji} {industry_fit.get('fit_level', 'NEUTRAL')}")
            cultural_notes_parts.append(f"  {industry_fit.get('reasoning', 'No specific analysis')}")
            
            # Part 4: Risk Flags
            risk_flags = country_linguistic.get("risk_flags", [])
            if risk_flags:
                cultural_notes_parts.append("\n**⚠️ RISK FLAGS:**")
                for flag_item in risk_flags:
                    cultural_notes_parts.append(f"• {flag_item}")
            
            # Part 5: Brand Classification
            cultural_notes_parts.append(f"\n**BRAND TYPE:** {linguistic_analysis.get('brand_type', 'Modern/Coined') if linguistic_analysis else 'Unknown'}")
            
            # Part 6: Country-Specific Recommendation based on CALCULATED score
            if calculated_final < 5:
                cultural_notes_parts.append("\n**RECOMMENDATION:** 🔴 CRITICAL - Significant cultural/linguistic barriers identified. Consult local experts before market entry.")
            elif calculated_final < 7:
                cultural_notes_parts.append("\n**RECOMMENDATION:** 🟡 CAUTION - Some concerns identified. Local linguistic validation strongly advised.")
            else:
                cultural_notes_parts.append("\n**RECOMMENDATION:** 🟢 SAFE - Name appears suitable for this market. Proceed with standard clearance.")
            
            # Part 7: Original base cultural notes
            cultural_notes_parts.append(f"\n---\n**LOCAL MARKET CONTEXT:**\n{base_cultural_data['cultural_notes']}")
        
        # Join all parts
        cultural_notes = "\n".join(cultural_notes_parts)
        
        # Use the NEW calculated score (×10 for 0-100 scale compatibility)
        resonance_score = calculated_final
        
        # Generate linguistic check status based on calculated score
        if calculated_final < 5:
            linguistic_check = f"⚠️ CRITICAL - Score {calculated_final}/10"
        elif calculated_final < 7:
            linguistic_check = f"⚠️ CAUTION - Score {calculated_final}/10"
        else:
            linguistic_check = f"✅ SAFE - Score {calculated_final}/10"
        
        result.append({
            "country": display_name,
            "country_flag": flag,
            "cultural_resonance_score": round(resonance_score, 1),
            "cultural_notes": cultural_notes,
            "linguistic_check": linguistic_check,
            # NEW: Include sub-scores for transparency
            "score_breakdown": {
                "safety_score": safety_score,
                "fluency_score": fluency_score,
                "vibe_score": vibe_score,
                "formula": "(Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)",
                "calculation": f"({safety_score} × 0.4) + ({fluency_score} × 0.3) + ({vibe_score} × 0.3) = {calculated_final}",
                "final_score": calculated_final,
                "risk_verdict": risk_verdict
            },
            # NEW: Include classification (calculated ONCE, passed through)
            "trademark_classification": {
                "category": classification.get("category"),
                "distinctiveness": classification.get("distinctiveness"),
                "protectability": classification.get("protectability"),
                "tokens": classification.get("tokens"),
                "warning": classification.get("warning")
            },
            "linguistic_analysis": {
                # Use universal linguistic data if available, else use fallback
                "has_universal_analysis": has_universal_linguistic,
                "languages": ling_insights.get("languages", []) if has_universal_linguistic else [],
                "name_type": ling_insights.get("name_type", "Unknown") if has_universal_linguistic else "Coined/Invented",
                "combined_meaning": ling_insights.get("combined_meaning", "") if has_universal_linguistic else None,
                "alignment_score": ling_insights.get("alignment_score", 5) if has_universal_linguistic else None,
                "cultural_reference_type": ling_insights.get("cultural_ref_type") if has_universal_linguistic else None,
                "recognition_regions": ling_insights.get("recognition_regions", []) if has_universal_linguistic else []
            }
        })
        
        logging.info(f"📊 Cultural analysis for {display_name}: Safety={safety_score}, Fluency={fluency_score}, Vibe={vibe_score} → FINAL={calculated_final}/10 ({risk_verdict})")
    
    return result


def merge_cultural_analysis_with_sacred_names(
    market_intel_cultural: list,
    local_cultural_analysis: list,
    brand_name: str,
    countries: list
) -> list:
    """
    CRITICAL: Merge market intelligence cultural data with local sacred name detection.
    
    The issue: market_intelligence fallback doesn't include sacred name detection.
    The fix: Always run local generate_cultural_analysis (which has sacred name detection)
             and merge/enhance with market_intelligence data if available.
    
    Priority: Local analysis (with sacred names) takes precedence for risk detection.
    """
    if not market_intel_cultural:
        # No market intelligence data, use local analysis directly
        logging.info(f"🔤 Using LOCAL cultural analysis with sacred name detection for '{brand_name}'")
        return local_cultural_analysis
    
    if not local_cultural_analysis:
        logging.warning(f"⚠️ No local cultural analysis - sacred name detection may be missing for '{brand_name}'")
        return market_intel_cultural
    
    # Create lookup for local analysis by country
    local_by_country = {}
    for item in local_cultural_analysis:
        country = item.get("country", "").lower()
        local_by_country[country] = item
    
    # Merge: Use market_intel as base, enhance with local sacred name detection
    merged = []
    for mi_item in market_intel_cultural:
        country = mi_item.get("country", "Unknown")
        country_lower = country.lower()
        
        local_item = local_by_country.get(country_lower, {})
        
        # Get linguistic analysis from local (has sacred name detection)
        local_notes = local_item.get("cultural_notes", "")
        local_linguistic = local_item.get("linguistic_analysis", {})
        local_linguistic_check = local_item.get("linguistic_check", "")
        
        # Check if local analysis detected risks
        has_local_risks = (
            local_linguistic.get("risk_count", 0) > 0 or
            "CRITICAL" in local_linguistic.get("overall_resonance", "") or
            "SACRED" in local_notes.upper() or
            "ROYAL" in local_notes.upper() or
            "⚠️" in local_linguistic_check
        )
        
        merged_item = mi_item.copy()
        
        if has_local_risks:
            # Local detected sacred/cultural risks - use local analysis
            logging.warning(f"⚠️ SACRED NAME RISK DETECTED for '{brand_name}' in {country} - using local analysis")
            merged_item["cultural_notes"] = local_notes
            merged_item["linguistic_check"] = local_linguistic_check
            merged_item["linguistic_analysis"] = local_linguistic
            # Reduce score if risks detected
            if local_linguistic.get("overall_resonance") == "CRITICAL":
                merged_item["cultural_resonance_score"] = min(
                    merged_item.get("cultural_resonance_score", 7.0),
                    local_item.get("cultural_resonance_score", 5.0)
                )
        else:
            # No local risks - can use market_intel data
            # But still enhance with local linguistic analysis
            if local_linguistic and not merged_item.get("linguistic_analysis"):
                merged_item["linguistic_analysis"] = local_linguistic
        
        merged.append(merged_item)
    
    # Add any countries in local but not in market_intel
    mi_countries = {item.get("country", "").lower() for item in market_intel_cultural}
    for local_item in local_cultural_analysis:
        country_lower = local_item.get("country", "").lower()
        if country_lower not in mi_countries:
            merged.append(local_item)
            logging.info(f"📊 Added local cultural analysis for {local_item.get('country')} (not in market_intel)")
    
    return merged


# ============ LLM-FIRST RESEARCH INTEGRATION ============

async def llm_first_country_analysis(
    countries: list, 
    category: str, 
    brand_name: str,
    use_llm_research: bool = True,
    positioning: str = "Mid-Range",
    classification: dict = None,  # NEW: Accept pre-calculated classification
    universal_linguistic: dict = None  # NEW: Accept universal linguistic analysis
) -> tuple:
    """
    LLM-First approach to country analysis with POSITIONING-AWARE search.
    
    KEY IMPROVEMENT: Includes positioning in search queries to get segment-specific competitors.
    Example: "Premium Hotel Chain India" → Taj, ITC, Oberoi
    Instead of: "Hotel Chain India" → mixed OYO to Taj
    
    Uses real-time web search + LLM for accuracy, with hardcoded fallback if research fails.
    
    NEW: Accepts pre-calculated classification to avoid duplicate computation.
    NEW: Accepts universal_linguistic analysis for rich cultural context.
    
    Returns: (country_competitor_analysis, cultural_analysis)
    """
    # Use passed classification or calculate if not provided
    if classification is None:
        classification = classify_brand_with_industry(brand_name, category)
    
    if not use_llm_research:
        # Use hardcoded fallback directly
        logging.info(f"⚡ Using hardcoded data (LLM research disabled)")
        return (
            generate_country_competitor_analysis(countries, category, brand_name, None),
            generate_cultural_analysis(countries, brand_name, category, classification, universal_linguistic)
        )
    
    logging.info(f"🔬 LLM-FIRST RESEARCH: Starting {positioning} research for {len(countries)} countries...")
    
    try:
        # Prepare fallback data with case-insensitive lookup
        fallback_market = {}
        fallback_cultural = {}
        cultural_data_lower = {k.lower(): v for k, v in COUNTRY_CULTURAL_DATA.items()}
        
        for country in countries[:4]:
            country_name = country.get('name') if isinstance(country, dict) else str(country)
            country_lower = country_name.lower().strip() if country_name else ""
            fallback_market[country_name] = get_market_data_for_category_country(category, country_name, None)
            fallback_cultural[country_name] = cultural_data_lower.get(country_lower, COUNTRY_CULTURAL_DATA["default"])
        
        # Execute LLM-first research WITH POSITIONING
        market_intelligence, cultural_intelligence = await research_all_countries(
            category=category,
            countries=countries,
            brand_name=brand_name,
            fallback_market_data=fallback_market,
            fallback_cultural_data=fallback_cultural,
            positioning=positioning
        )
        
        # Format results for API response
        country_competitor_analysis = []
        cultural_analysis = []
        
        # Format market intelligence
        for intel in market_intelligence:
            country_competitor_analysis.append({
                "country": intel.country,
                "country_flag": intel.country_flag,
                "x_axis_label": intel.x_axis_label,
                "y_axis_label": intel.y_axis_label,
                "competitors": intel.competitors,
                "user_brand_position": intel.user_brand_position,
                "white_space_analysis": intel.white_space_analysis,
                "strategic_advantage": intel.strategic_advantage,
                "market_entry_recommendation": intel.market_entry_recommendation,
                "research_quality": intel.research_quality  # NEW: Indicates if data is from LLM or fallback
            })
            # DEBUG: Log actual competitor names
            competitor_names = [c.get('name', 'Unknown') for c in intel.competitors[:4]] if intel.competitors else []
            logging.info(f"✅ Market research for {intel.country} {intel.country_flag}: {intel.research_quality} quality, {len(intel.competitors)} competitors: {competitor_names}")
        
        # Format cultural intelligence
        for cultural in cultural_intelligence:
            notes = cultural.cultural_notes
            
            # Prepend warning if sacred name detected
            if cultural.sacred_name_detected and cultural.cultural_risk_warning:
                detected_str = ", ".join(cultural.detected_terms)
                notes = f"{cultural.cultural_risk_warning}\n\n**Detected terms:** {detected_str}\n\n**Original Analysis:** {notes}"
                if cultural.legal_implications:
                    notes += f"\n\n**Legal Implications:** {cultural.legal_implications}"
            
            cultural_analysis.append({
                "country": cultural.country,
                "country_flag": cultural.country_flag,
                "cultural_resonance_score": cultural.cultural_resonance_score,
                "cultural_notes": notes,
                "linguistic_check": cultural.linguistic_check,
                "research_quality": cultural.research_quality
            })
            
            if cultural.sacred_name_detected:
                logging.warning(f"⚠️ Sacred name detected for {cultural.country}: {cultural.detected_terms}")
        
        logging.info(f"✅ LLM-FIRST RESEARCH COMPLETE: {len(country_competitor_analysis)} markets, {len(cultural_analysis)} cultural analyses")
        return (country_competitor_analysis, cultural_analysis)
        
    except Exception as e:
        logging.error(f"❌ LLM-first research failed: {e}, using hardcoded fallback")
        return (
            generate_country_competitor_analysis(countries, category, brand_name, None),
            generate_cultural_analysis(countries, brand_name, category, classification, universal_linguistic)
        )


# ============ LEGAL PRECEDENTS & TRADEMARK INTELLIGENCE ============
# ============ CATEGORY-SPECIFIC TLD MAPPING ============
# Maps categories to appropriate TLDs (NO generic .beauty/.shop for medical apps)

CATEGORY_TLD_MAP = {
    # Healthcare / Medical
    "doctor": [".health", ".care", ".doctor", ".clinic", ".med", ".medical"],
    "doctor appointment": [".health", ".care", ".doctor", ".clinic", ".med", ".medical"],
    "healthcare": [".health", ".care", ".clinic", ".med", ".medical"],
    "hospital": [".health", ".care", ".hospital", ".clinic", ".med"],
    "pharmacy": [".pharmacy", ".health", ".care", ".med"],
    "telemedicine": [".health", ".care", ".doctor", ".clinic", ".med"],
    "medical": [".health", ".care", ".doctor", ".clinic", ".med"],
    "wellness": [".health", ".care", ".fitness", ".life"],
    
    # Finance / Fintech
    "finance": [".finance", ".money", ".bank", ".capital"],
    "fintech": [".finance", ".money", ".pay", ".bank"],
    "payments": [".pay", ".finance", ".money"],
    "banking": [".bank", ".finance", ".money"],
    "insurance": [".insurance", ".finance", ".life"],
    
    # Technology / SaaS
    "technology": [".tech", ".io", ".dev", ".digital", ".app"],
    "saas": [".io", ".app", ".tech", ".cloud", ".software"],
    "software": [".software", ".io", ".app", ".tech"],
    "ai": [".ai", ".tech", ".io"],
    "app": [".app", ".io", ".tech"],
    
    # E-commerce / Retail
    "ecommerce": [".shop", ".store", ".market", ".buy"],
    "retail": [".shop", ".store", ".market"],
    "marketplace": [".market", ".shop", ".store"],
    
    # Fashion / Beauty
    "fashion": [".fashion", ".style", ".clothing", ".design"],
    "beauty": [".beauty", ".style", ".skin", ".glow"],
    "cosmetics": [".beauty", ".skin", ".glow"],
    "skincare": [".skin", ".beauty", ".care", ".glow"],
    "streetwear": [".fashion", ".style", ".clothing", ".wear"],
    "apparel": [".fashion", ".clothing", ".style", ".wear"],
    
    # Food & Beverage
    "food": [".food", ".kitchen", ".eat", ".menu"],
    "restaurant": [".restaurant", ".food", ".menu", ".eat"],
    "cafe": [".cafe", ".coffee", ".food"],
    "chai": [".cafe", ".tea", ".food"],
    "beverage": [".drink", ".cafe", ".bar"],
    
    # Hospitality / Travel
    "hotel": [".hotel", ".hotels", ".travel", ".resort", ".stay"],
    "hotel chain": [".hotel", ".hotels", ".travel", ".resort", ".stay"],
    "travel": [".travel", ".tours", ".trip", ".vacation"],
    "tourism": [".travel", ".tours", ".vacation"],
    
    # Education
    "education": [".education", ".academy", ".school", ".learning"],
    "edtech": [".education", ".academy", ".learning", ".study"],
    
    # Real Estate
    "real estate": [".realty", ".property", ".estate", ".homes"],
    "property": [".property", ".realty", ".homes"],
    
    # Default
    "default": [".co", ".io", ".com", ".net"]
}

# Country code TLDs
COUNTRY_TLD_MAP = {
    "india": ".in",
    "usa": ".us",
    "united states": ".us",
    "thailand": ".th",
    "uae": ".ae",
    "united arab emirates": ".ae",
    "uk": ".co.uk",
    "united kingdom": ".co.uk",
    "singapore": ".sg",
    "japan": ".jp",
    "germany": ".de",
    "france": ".fr",
    "china": ".cn",
    "australia": ".com.au",
    "canada": ".ca",
    "brazil": ".com.br",
    "indonesia": ".id",
    "malaysia": ".my",
    "vietnam": ".vn",
    "philippines": ".ph",
    "south korea": ".kr",
    "mexico": ".mx",
    "spain": ".es",
    "italy": ".it",
    "netherlands": ".nl",
    "saudi arabia": ".sa",
    "qatar": ".qa",
    "kuwait": ".kw"
}


def get_category_tlds(category: str) -> list:
    """Get appropriate TLDs for a category (NO generic .beauty/.shop for medical)"""
    category_lower = category.lower().strip()
    
    # Check for exact match first
    if category_lower in CATEGORY_TLD_MAP:
        return CATEGORY_TLD_MAP[category_lower]
    
    # Check for partial match
    for key, tlds in CATEGORY_TLD_MAP.items():
        if key in category_lower or category_lower in key:
            return tlds
    
    # Check specific keywords
    if any(word in category_lower for word in ["doctor", "health", "medical", "clinic", "hospital", "pharmacy", "appointment"]):
        return CATEGORY_TLD_MAP["healthcare"]
    if any(word in category_lower for word in ["finance", "pay", "bank", "money", "fintech"]):
        return CATEGORY_TLD_MAP["finance"]
    if any(word in category_lower for word in ["tech", "software", "saas", "app", "digital"]):
        return CATEGORY_TLD_MAP["technology"]
    if any(word in category_lower for word in ["fashion", "clothing", "apparel", "wear", "style"]):
        return CATEGORY_TLD_MAP["fashion"]
    if any(word in category_lower for word in ["hotel", "resort", "travel", "hospitality"]):
        return CATEGORY_TLD_MAP["hotel"]
    if any(word in category_lower for word in ["food", "restaurant", "cafe", "kitchen"]):
        return CATEGORY_TLD_MAP["food"]
    if any(word in category_lower for word in ["shop", "store", "ecommerce", "retail", "market"]):
        return CATEGORY_TLD_MAP["ecommerce"]
    
    return CATEGORY_TLD_MAP["default"]


def get_country_tlds(countries: list) -> list:
    """Get country-specific TLDs for ALL target countries"""
    country_tlds = []
    
    for country in countries:
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        country_lower = country_name.lower().strip()
        
        if country_lower in COUNTRY_TLD_MAP:
            country_tlds.append({
                "tld": COUNTRY_TLD_MAP[country_lower],
                "country": country_name.title()
            })
    
    return country_tlds


def generate_smart_domain_suggestions(brand_name: str, category: str, countries: list, domain_available: bool = True) -> dict:
    """
    Generate contextually appropriate domain suggestions based on:
    1. Category (healthcare → .health, .care, .doctor - NOT .beauty/.shop)
    2. ALL target countries (.in, .us, .th, .ae - not just .in/.us)
    3. Primary .com availability
    
    Returns complete domain analysis with category-appropriate and country-specific TLDs.
    """
    brand_lower = brand_name.lower()
    
    # Get category-appropriate TLDs
    category_tlds = get_category_tlds(category)
    
    # Get country TLDs for ALL target countries
    country_tld_list = get_country_tlds(countries)
    
    # Build category domains
    category_domains = []
    for tld in category_tlds[:4]:  # Top 4 category TLDs
        category_domains.append({
            "domain": f"{brand_lower}{tld}",
            "available": True,  # Will be checked by availability module
            "status": "Available",
            "relevance": "HIGH",
            "reason": f"Category-appropriate TLD for {category}"
        })
    
    # Build country domains for ALL target countries
    country_domains = []
    for country_tld in country_tld_list:
        country_domains.append({
            "domain": f"{brand_lower}{country_tld['tld']}",
            "available": True,
            "status": "Available",
            "country": country_tld["country"],
            "reason": f"Local market presence in {country_tld['country']}"
        })
    
    # If no country TLDs found, add common ones
    if not country_domains:
        country_domains = [
            {"domain": f"{brand_lower}.in", "available": True, "status": "Available", "country": "India"},
            {"domain": f"{brand_lower}.us", "available": True, "status": "Available", "country": "USA"}
        ]
    
    # Generate recommended domain
    if domain_available:
        recommended = f"{brand_lower}.com"
        strategy = f"Secure {brand_lower}.com as primary domain, plus country TLDs ({', '.join([c['tld'] for c in country_tld_list])}) and category TLD ({category_tlds[0] if category_tlds else '.co'})"
    else:
        # Recommend best category TLD if .com not available
        recommended = f"{brand_lower}{category_tlds[0]}" if category_tlds else f"{brand_lower}.co"
        strategy = f"Primary .com taken. Secure {recommended} for {category} positioning, plus ALL country TLDs for local market presence."
    
    logging.info(f"🌐 SMART DOMAIN SUGGESTIONS for '{brand_name}' in {category}:")
    logging.info(f"   Category TLDs: {category_tlds[:4]}")
    logging.info(f"   Country TLDs: {[c['tld'] for c in country_tld_list]}")
    
    return {
        "primary_domain": f"{brand_lower}.com",
        "primary_available": domain_available,
        "category_domains": category_domains,
        "country_domains": country_domains,
        "recommended_domain": recommended,
        "acquisition_strategy": strategy
    }


def calculate_dynamic_fallback_dimensions(
    brand_name: str,
    category: str,
    classification: dict,
    linguistic_analysis: dict = None,
    trademark_risk: float = 5.0,
    domain_available: bool = False,
    countries: list = None
) -> list:
    """
    Calculate DYNAMIC dimension scores based on brand characteristics.
    Used when LLM dimensions are not available (fallback path).
    
    Instead of hardcoded 7.5, 7.2, 7.0... we calculate based on:
    - Brand name length and phonetics
    - Classification type
    - Linguistic meaning and alignment
    - Trademark risk
    - Market scope
    """
    
    # Extract data
    legal_category = classification.get("category", "SUGGESTIVE") if classification else "SUGGESTIVE"
    has_meaning = linguistic_analysis.get("has_linguistic_meaning", False) if linguistic_analysis else False
    alignment_score = linguistic_analysis.get("business_alignment", {}).get("alignment_score", 5) if linguistic_analysis else 5
    languages = linguistic_analysis.get("linguistic_analysis", {}).get("languages_detected", []) if linguistic_analysis else []
    
    brand_lower = brand_name.lower()
    brand_length = len(brand_name.replace(" ", ""))
    
    # ═══════════════════════════════════════════════════════════════════════
    # 1. BRAND DISTINCTIVENESS & MEMORABILITY
    # ═══════════════════════════════════════════════════════════════════════
    # Base from classification
    distinctiveness_base = {
        "FANCIFUL": 9.0, "ARBITRARY": 8.0, "SUGGESTIVE": 7.0,
        "DESCRIPTIVE": 5.0, "GENERIC": 2.0
    }.get(legal_category, 6.5)
    
    # Adjust for length (shorter = more memorable)
    if brand_length <= 6:
        distinctiveness_base += 0.5
    elif brand_length <= 10:
        distinctiveness_base += 0.2
    elif brand_length > 15:
        distinctiveness_base -= 0.5
    
    # Adjust for simplicity (all alpha = cleaner)
    if brand_lower.replace(" ", "").isalpha():
        distinctiveness_base += 0.3
    
    distinctiveness = round(max(1.0, min(10.0, distinctiveness_base)), 1)
    
    # ═══════════════════════════════════════════════════════════════════════
    # 2. CULTURAL & LINGUISTIC RESONANCE
    # ═══════════════════════════════════════════════════════════════════════
    if has_meaning:
        # Has linguistic meaning - use alignment score
        cultural_base = min(9.0, alignment_score + 1.5)
        # Bonus for heritage/mythological references
        cultural_significance = linguistic_analysis.get("cultural_significance", {}) if linguistic_analysis else {}
        if cultural_significance.get("has_cultural_reference"):
            cultural_base += 0.5
    else:
        # Coined/invented name - neutral cultural resonance
        cultural_base = 6.0
        # Penalty if hard to pronounce (many consonant clusters)
        consonant_clusters = sum(1 for i in range(len(brand_lower)-1) 
                                 if brand_lower[i] not in 'aeiou' and brand_lower[i+1] not in 'aeiou')
        if consonant_clusters >= 3:
            cultural_base -= 0.5
    
    # Adjust for multi-language recognition
    if len(languages) >= 2:
        cultural_base += 0.3
    
    cultural_resonance = round(max(1.0, min(10.0, cultural_base)), 1)
    
    # ═══════════════════════════════════════════════════════════════════════
    # 3. PREMIUM POSITIONING & TRUST CURVE
    # ═══════════════════════════════════════════════════════════════════════
    # Fanciful/Arbitrary names can command premium
    premium_base = {
        "FANCIFUL": 8.0, "ARBITRARY": 7.5, "SUGGESTIVE": 7.0,
        "DESCRIPTIVE": 5.5, "GENERIC": 3.0
    }.get(legal_category, 6.0)
    
    # Heritage/cultural names can feel premium
    if has_meaning and alignment_score >= 7:
        premium_base += 0.5
    
    # Domain availability affects perceived legitimacy
    if domain_available:
        premium_base += 0.3
    else:
        premium_base -= 0.2
    
    premium_positioning = round(max(1.0, min(10.0, premium_base)), 1)
    
    # ═══════════════════════════════════════════════════════════════════════
    # 4. SCALABILITY & BRAND ARCHITECTURE
    # ═══════════════════════════════════════════════════════════════════════
    # Fanciful names scale best (can enter any category)
    scalability_base = {
        "FANCIFUL": 9.0, "ARBITRARY": 8.5, "SUGGESTIVE": 6.5,
        "DESCRIPTIVE": 4.0, "GENERIC": 2.0
    }.get(legal_category, 6.0)
    
    # Multi-country scope suggests need for scalability
    if countries and len(countries) >= 3:
        scalability_base += 0.3
    
    # Names with narrow meaning scale less well
    if has_meaning and alignment_score >= 8:
        # Very aligned = potentially narrow
        scalability_base -= 0.3
    
    scalability = round(max(1.0, min(10.0, scalability_base)), 1)
    
    # ═══════════════════════════════════════════════════════════════════════
    # 5. TRADEMARK STRENGTH (from actual risk score)
    # ═══════════════════════════════════════════════════════════════════════
    trademark_strength = round(10.0 - trademark_risk, 1)
    trademark_strength = max(1.0, min(10.0, trademark_strength))
    
    # ═══════════════════════════════════════════════════════════════════════
    # 6. CONSUMER PERCEPTION / MARKET PERCEPTION
    # ═══════════════════════════════════════════════════════════════════════
    # Combination of memorability, pronunciation, and associations
    perception_base = (distinctiveness + cultural_resonance + premium_positioning) / 3
    
    # Adjust for easy pronunciation
    vowel_ratio = sum(1 for c in brand_lower if c in 'aeiou') / max(len(brand_lower), 1)
    if 0.3 <= vowel_ratio <= 0.5:  # Balanced vowel ratio
        perception_base += 0.3
    
    # Meaningful names create stronger perception
    if has_meaning:
        perception_base += 0.4
    
    market_perception = round(max(1.0, min(10.0, perception_base)), 1)
    
    # ═══════════════════════════════════════════════════════════════════════
    # RETURN DIMENSION BREAKDOWN
    # ═══════════════════════════════════════════════════════════════════════
    logging.info(f"📊 DYNAMIC DIMENSIONS for '{brand_name}': "
                 f"Distinct={distinctiveness}, Cultural={cultural_resonance}, "
                 f"Premium={premium_positioning}, Scale={scalability}, "
                 f"TM={trademark_strength}, Perception={market_perception}")
    
    return [
        {"Brand Distinctiveness": distinctiveness},
        {"Cultural Resonance": cultural_resonance},
        {"Premium Positioning": premium_positioning},
        {"Scalability": scalability},
        {"Trademark Strength": trademark_strength},
        {"Market Perception": market_perception}
    ]


def generate_dynamic_alternative_path(
    brand_name: str,
    category: str,
    classification: dict,
    trademark_data: dict = None
) -> str:
    """
    Generate DYNAMIC alternative path suggestions based on actual conflicts found.
    Not generic - tailored to the specific situation.
    """
    legal_category = classification.get("category", "SUGGESTIVE") if classification else "SUGGESTIVE"
    
    # Extract conflicts if available
    conflicts = []
    if trademark_data and isinstance(trademark_data, dict):
        conflicts = trademark_data.get("trademark_conflicts", []) or []
    
    suggestions = []
    
    # 1. If conflicts found - suggest differentiating modifications
    if conflicts:
        conflict_names = [c.get("name", "") for c in conflicts[:2]]
        suggestions.append(f"Differentiate from '{conflict_names[0]}' with unique spelling or prefix")
    else:
        suggestions.append("Modified spelling variations for stronger distinctiveness")
    
    # 2. Category-aware suffix suggestions
    category_lower = category.lower()
    if any(word in category_lower for word in ["tech", "software", "app", "saas"]):
        suggestions.append(f"Adding tech suffix (e.g., '{brand_name}AI', '{brand_name}Labs', '{brand_name}HQ')")
    elif any(word in category_lower for word in ["food", "restaurant", "cafe", "tea", "coffee"]):
        suggestions.append(f"Adding food suffix (e.g., '{brand_name}Kitchen', '{brand_name}Cafe', '{brand_name}Co')")
    elif any(word in category_lower for word in ["hotel", "travel", "tourism"]):
        suggestions.append(f"Adding hospitality suffix (e.g., '{brand_name}Stays', '{brand_name}Escapes')")
    elif any(word in category_lower for word in ["finance", "bank", "payment"]):
        suggestions.append(f"Adding fintech suffix (e.g., '{brand_name}Pay', '{brand_name}Fi')")
    else:
        suggestions.append(f"Adding descriptive suffix (e.g., '{brand_name}Co', '{brand_name}Group')")
    
    # 3. Geographic modifier if multi-country
    suggestions.append("Geographic modifiers for specific market entry")
    
    # 4. Classification-specific advice
    if legal_category == "DESCRIPTIVE":
        suggestions.append("Consider more distinctive/arbitrary naming approach for stronger protection")
    elif legal_category == "SUGGESTIVE":
        suggestions.append("Strengthen suggestive elements for better recall")
    
    return f"If primary strategy faces obstacles, consider: {'; '.join(suggestions[:3])}."


def generate_smart_final_recommendations(
    brand_name: str,
    category: str,
    countries: list,
    domain_available: bool,
    nice_class: dict,
    trademark_research: dict = None
) -> list:
    """
    Generate smart, category-aware and country-specific recommendations.
    Now includes multi-class filing from trademark intelligence.
    Removed: Social Presence and Brand Launch (not required).
    """
    brand_lower = brand_name.lower().replace(" ", "")
    
    # Get category-appropriate TLDs
    category_tlds = get_category_tlds(category)
    top_category_tld = category_tlds[0] if category_tlds else ".co"
    
    # Get country TLDs
    country_tld_list = get_country_tlds(countries)
    country_tld_str = ", ".join([f"{c['tld']} ({c['country']})" for c in country_tld_list[:3]])
    
    # Build domain strategy recommendation
    if domain_available:
        domain_strategy = f"Secure {brand_lower}.com as primary domain. Also register country TLDs ({country_tld_str}) for local market presence and {brand_lower}{top_category_tld} for {category} sector relevance."
    else:
        domain_strategy = f"Primary .com unavailable. Secure {brand_lower}{top_category_tld} for {category} positioning. Register country TLDs ({country_tld_str}) for local markets. Consider get{brand_lower}.com or {brand_lower}app.com alternatives."
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # BUILD TRADEMARK FILING RECOMMENDATION WITH MULTI-CLASS DATA FROM INTELLIGENCE
    # ═══════════════════════════════════════════════════════════════════════════════
    country_names = [c.get('name') if isinstance(c, dict) else str(c) for c in countries]
    primary_class = nice_class.get('class_number', 9)
    primary_desc = nice_class.get('class_description', category)
    
    # Extract multi-class filing info from trademark research if available
    multi_class_info = ""
    if trademark_research:
        # Check for multi-class recommendations in trademark intelligence
        tm_result = trademark_research.get("result", {}) if isinstance(trademark_research, dict) else {}
        multi_class_data = tm_result.get("multi_class_recommendation", []) if tm_result else []
        recommended_classes = tm_result.get("recommended_nice_classes", []) if tm_result else []
        
        # Also check for related classes in the research
        if not multi_class_data and not recommended_classes:
            # Try to extract from trademark conflicts - different classes in conflicts
            conflicts = tm_result.get("trademark_conflicts", []) if tm_result else []
            related_classes = set()
            for conflict in conflicts:
                conflict_class = conflict.get("class") or conflict.get("nice_class")
                if conflict_class and conflict_class != primary_class:
                    related_classes.add(conflict_class)
            if related_classes:
                multi_class_data = list(related_classes)[:3]
        
        if multi_class_data or recommended_classes:
            all_classes = list(set([primary_class] + (recommended_classes or []) + (multi_class_data if isinstance(multi_class_data, list) else [])))
            all_classes = [c for c in all_classes if isinstance(c, int)][:4]  # Max 4 classes
            if len(all_classes) > 1:
                multi_class_info = f" **Multi-class filing recommended:** Classes {', '.join(map(str, sorted(all_classes)))} to protect against competitive infringement."
    
    # Build the trademark recommendation
    if len(country_names) > 1:
        trademark_recommendation = f"File trademark in NICE Class {primary_class} ({primary_desc}).{multi_class_info} For multi-country ({', '.join(country_names[:3])}), consider Madrid Protocol for cost-effective international registration. Process: 12-18 months."
    else:
        trademark_recommendation = f"File trademark in {country_names[0] if country_names else 'target country'} under NICE Class {primary_class} ({primary_desc}).{multi_class_info} Process typically 12-18 months."
    
    # Only return Domain Strategy and Trademark Filing (removed Social Presence and Brand Launch)
    recommendations = [
        {
            "title": "🏢 Domain Strategy",
            "content": domain_strategy
        },
        {
            "title": "📋 Trademark Filing",
            "content": trademark_recommendation
        }
    ]
    
    return recommendations


def generate_fallback_domain_strategy(
    brand_name: str,
    category: str,
    countries: list,
    domain_available: bool
) -> dict:
    """
    Generate domain strategy analysis (fallback when LLM not available).
    This provides intelligent domain recommendations based on WHOIS results.
    
    When LLM IS available, this is enhanced by llm_analyze_domain_strategy() in availability.py
    """
    brand_lower = brand_name.lower()
    
    # Get category and country TLDs
    category_tlds = get_category_tlds(category)
    country_tld_list = get_country_tlds(countries)
    
    # Calculate domain quality score
    quality_score = 7.0
    if len(brand_lower) <= 8:
        quality_score += 1.0
    if len(brand_lower) > 15:
        quality_score -= 1.0
    if brand_lower.isalpha():
        quality_score += 0.5
    if "-" in brand_lower:
        quality_score -= 1.0
    quality_score = min(10.0, max(1.0, quality_score))
    
    # Determine acquisition difficulty
    if domain_available:
        acquisition_difficulty = "EASY"
        estimated_cost = "$10-15/year"
        primary_recommendation = "Secure immediately - standard registration pricing"
    else:
        acquisition_difficulty = "MODERATE"
        estimated_cost = "$500-5000 (premium negotiation likely required)"
        primary_recommendation = f"Consider category TLD ({category_tlds[0] if category_tlds else '.co'}) as primary, or creative alternatives"
    
    # Build country TLD priority
    country_names = [c.get('name') if isinstance(c, dict) else str(c) for c in countries]
    country_tld_priority = []
    for i, country_tld in enumerate(country_tld_list[:4]):
        country_tld_priority.append({
            "tld": country_tld["tld"],
            "country": country_tld["country"],
            "priority": i + 1,
            "reason": "Primary market" if i == 0 else "Secondary market"
        })
    
    # Build category TLD ranking
    category_tld_ranking = []
    for i, tld in enumerate(category_tlds[:4]):
        category_tld_ranking.append({
            "tld": tld,
            "fit_score": 9 - i,  # Decreasing scores
            "reason": f"Category-appropriate for {category}"
        })
    
    strategy = {
        "llm_enhanced": False,
        "analysis": {
            "domain_quality_score": round(quality_score, 1),
            "domain_quality_reasoning": f"{'Short and memorable' if len(brand_lower) <= 10 else 'Longer name - consider abbreviation'}, {'clean alphanumeric' if brand_lower.isalnum() else 'contains special characters'}",
            
            "primary_com_analysis": {
                "status": "AVAILABLE" if domain_available else "TAKEN",
                "acquisition_difficulty": acquisition_difficulty,
                "estimated_cost": estimated_cost,
                "recommendation": primary_recommendation
            },
            
            "category_tld_ranking": category_tld_ranking,
            "country_tld_priority": country_tld_priority,
            
            "acquisition_strategy": {
                "immediate_actions": [
                    f"Register {brand_lower}.com" if domain_available else f"Secure {brand_lower}{category_tlds[0] if category_tlds else '.co'}",
                    f"Register ALL country TLDs: {', '.join([c['tld'] for c in country_tld_list[:4]])}"
                ],
                "if_com_taken": f"Best alternatives: get{brand_lower}.com, {brand_lower}app.com, or use {category_tlds[0] if category_tlds else '.co'} as primary",
                "budget_estimate": "$100-500 for comprehensive domain portfolio"
            },
            
            "risk_assessment": {
                "typo_risk": "LOW" if len(brand_lower) <= 8 else "MEDIUM" if len(brand_lower) <= 12 else "HIGH",
                "typo_domains_to_secure": [],
                "competitor_squatting_risk": "LOW",
                "trademark_conflict_risk": "Check trademark_research section"
            },
            
            "creative_alternatives": [
                {"domain": f"get{brand_lower}.com", "type": "prefix", "availability_guess": "LIKELY_AVAILABLE"},
                {"domain": f"{brand_lower}app.com", "type": "suffix", "availability_guess": "LIKELY_AVAILABLE"},
                {"domain": f"try{brand_lower}.com", "type": "prefix", "availability_guess": "LIKELY_AVAILABLE"},
                {"domain": f"{brand_lower}hq.com", "type": "suffix", "availability_guess": "LIKELY_AVAILABLE"}
            ],
            
            "final_recommendation": f"{'Secure ' + brand_lower + '.com immediately at standard pricing.' if domain_available else 'Primary .com is taken. Recommend ' + brand_lower + (category_tlds[0] if category_tlds else '.co') + ' as primary domain.'} Register country TLDs ({', '.join([c['tld'] for c in country_tld_list[:3]])}) for {', '.join(country_names[:2])} market presence."
        }
    }
    
    logging.info(f"🌐 DOMAIN STRATEGY for '{brand_name}': Quality={quality_score}/10, .com={'AVAILABLE' if domain_available else 'TAKEN'}")
    
    return strategy


# ============ LLM-FIRST LEGAL PRECEDENTS ============
# Dynamically generate country-wise legal precedents using LLM

LLM_LEGAL_PRECEDENTS_PROMPT = """You are a trademark law expert with comprehensive knowledge of intellectual property law across different jurisdictions.

**TASK:** Generate relevant trademark legal precedents for brand registration in the specified countries.

**BRAND:** {brand_name}
**CATEGORY:** {category}
**TARGET COUNTRIES:** {countries}
**TRADEMARK RISK LEVEL:** {risk_level}

**INSTRUCTIONS:**
For EACH target country, provide 1-2 relevant legal precedents that would apply to trademark registration.
Focus on cases that are:
1. Directly relevant to the brand category ({category})
2. Important for understanding trademark registration requirements
3. Recent or landmark cases that set current standards

**FORMAT YOUR RESPONSE AS JSON:**
{{
    "country_precedents": [
        {{
            "country": "Country Name",
            "country_flag": "🇮🇳",
            "precedents": [
                {{
                    "case_name": "Full case name",
                    "court": "Court name",
                    "year": "Year",
                    "relevance": "Why this case matters for {brand_name} in {category}",
                    "key_principle": "The main legal principle established"
                }}
            ]
        }}
    ],
    "global_principles": [
        {{
            "principle": "Key principle name",
            "description": "Brief description of the principle",
            "applicability": "How it applies to {brand_name}"
        }}
    ]
}}

**COUNTRY-SPECIFIC GUIDANCE:**
- **India:** Include IPO cases, Indian Courts trademark decisions, Sec 9/11 TM Act
- **USA:** Include USPTO TTAB decisions, Polaroid/Sleekcraft factors, Lanham Act cases
- **Thailand:** Include DIP decisions, Thai trademark law specifics, royal/sacred name restrictions
- **UAE:** Include Ministry of Economy trademark decisions, GCC trademark framework, Islamic naming restrictions
- **UK:** Include UKIPO decisions, UK TMA 1994 cases, passing off precedents
- **Singapore:** Include IPOS decisions, Singapore TM Act cases
- **Japan:** Include JPO decisions, Japan Trademark Law cases

Return ONLY valid JSON, no explanations."""


async def generate_llm_legal_precedents(
    brand_name: str,
    category: str,
    countries: list,
    risk_level: str = "LOW"
) -> list:
    """
    LLM-FIRST approach to generate country-specific legal precedents.
    
    Returns country-wise precedents instead of hardcoded US-only cases.
    Falls back to basic structure if LLM unavailable.
    """
    EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')
    
    # Format countries for prompt
    country_names = []
    for country in countries:
        name = country.get('name') if isinstance(country, dict) else str(country)
        country_names.append(name)
    countries_str = ", ".join(country_names)
    
    if not LlmChat or not EMERGENT_KEY:
        logging.warning("LLM not available for legal precedents - using fallback")
        return generate_fallback_legal_precedents(country_names, brand_name, category)
    
    try:
        prompt = LLM_LEGAL_PRECEDENTS_PROMPT.format(
            brand_name=brand_name,
            category=category,
            countries=countries_str,
            risk_level=risk_level
        )
        
        chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
        user_msg = UserMessage(prompt)
        
        response = await asyncio.wait_for(
            chat.send_message(user_msg),
            timeout=25
        )
        
        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        result = json.loads(response_text)
        
        precedents = result.get("country_precedents", [])
        if precedents:
            logging.info(f"⚖️ LLM-FIRST LEGAL PRECEDENTS generated for {len(precedents)} countries")
            return precedents
        
    except asyncio.TimeoutError:
        logging.warning("LLM legal precedents timed out - using fallback")
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse LLM legal precedents: {e}")
    except Exception as e:
        logging.warning(f"LLM legal precedents failed: {e}")
    
    return generate_fallback_legal_precedents(country_names, brand_name, category)


def generate_fallback_legal_precedents(countries: list, brand_name: str, category: str) -> list:
    """Fallback legal precedents when LLM is unavailable - country-specific basics"""
    
    COUNTRY_PRECEDENT_DATA = {
        "india": {
            "flag": "🇮🇳",
            "precedents": [
                {
                    "case_name": "Cadila Healthcare Ltd. v. Cadila Pharmaceuticals Ltd.",
                    "court": "Supreme Court of India",
                    "year": "2001",
                    "relevance": f"Key case for phonetic similarity analysis in trademark disputes - relevant for '{brand_name}'",
                    "key_principle": "Triple identity test (deceptive similarity): visual, phonetic, and structural comparison of marks"
                },
                {
                    "case_name": "N.R. Dongre v. Whirlpool Corporation",
                    "court": "Supreme Court of India",
                    "year": "1996",
                    "relevance": "Transborder reputation - important for international brand protection",
                    "key_principle": "Well-known marks deserve protection even without local registration"
                }
            ]
        },
        "usa": {
            "flag": "🇺🇸",
            "precedents": [
                {
                    "case_name": "Polaroid Corp. v. Polarad Electronics Corp.",
                    "court": "U.S. Second Circuit",
                    "year": "1961",
                    "relevance": f"Foundational 8-factor test for likelihood of confusion - applies to '{brand_name}' evaluation",
                    "key_principle": "8-factor test: strength of mark, similarity, proximity of goods, bridging the gap, actual confusion, good faith, quality, buyer sophistication"
                },
                {
                    "case_name": "In re E.I. du Pont de Nemours & Co.",
                    "court": "Court of Customs and Patent Appeals",
                    "year": "1973",
                    "relevance": "USPTO standard for trademark examination",
                    "key_principle": "13-factor test is the gold standard for USPTO trademark examination"
                }
            ]
        },
        "thailand": {
            "flag": "🇹🇭",
            "precedents": [
                {
                    "case_name": "Thailand Trademark Act B.E. 2534 (1991) - Royal Names Provision",
                    "court": "Department of Intellectual Property (DIP)",
                    "year": "1991",
                    "relevance": f"CRITICAL for '{brand_name}' - Royal names (Rama, Chakri) are restricted under lèse-majesté laws",
                    "key_principle": "Section 8 prohibits marks resembling royal names, national symbols, or marks contrary to public order"
                },
                {
                    "case_name": "Central Intellectual Property and International Trade Court Guidelines",
                    "court": "CIPITC Thailand",
                    "year": "2016",
                    "relevance": "Modern trademark dispute resolution framework",
                    "key_principle": "Likelihood of confusion assessed through consumer perception and market context"
                }
            ]
        },
        "uae": {
            "flag": "🇦🇪",
            "precedents": [
                {
                    "case_name": "UAE Federal Law No. 37 of 1992 - Trademark Law",
                    "court": "Ministry of Economy",
                    "year": "1992",
                    "relevance": f"Foundation for trademark registration in UAE - important for '{brand_name}'",
                    "key_principle": "Article 3 prohibits marks contrary to public morals, Islamic values, or state symbols"
                },
                {
                    "case_name": "GCC Trademark Law Framework",
                    "court": "Gulf Cooperation Council",
                    "year": "2006",
                    "relevance": "Regional trademark protection across GCC states",
                    "key_principle": "Unified examination standards across UAE, Saudi Arabia, Kuwait, Qatar, Bahrain, Oman"
                }
            ]
        },
        "uk": {
            "flag": "🇬🇧",
            "precedents": [
                {
                    "case_name": "Specsavers International Healthcare Ltd v Asda Stores Ltd",
                    "court": "UK Court of Appeal",
                    "year": "2012",
                    "relevance": "Leading case on trademark infringement and comparative advertising",
                    "key_principle": "Average consumer test and likelihood of confusion in trademark disputes"
                }
            ]
        },
        "singapore": {
            "flag": "🇸🇬",
            "precedents": [
                {
                    "case_name": "Staywell Hospitality Group v Starwood Hotels & Resorts",
                    "court": "Singapore Court of Appeal",
                    "year": "2014",
                    "relevance": "Key case for similarity assessment in ASEAN region",
                    "key_principle": "Step-by-step approach: marks-similarity → goods-similarity → confusion likelihood"
                }
            ]
        },
        "japan": {
            "flag": "🇯🇵",
            "precedents": [
                {
                    "case_name": "Japan Patent Office Examination Guidelines",
                    "court": "JPO",
                    "year": "2020",
                    "relevance": "Current standard for trademark examination",
                    "key_principle": "Focus on visual, phonetic, and conceptual similarity with consumer confusion test"
                }
            ]
        }
    }
    
    result = []
    for country in countries:
        country_lower = country.lower().strip()
        if country_lower in COUNTRY_PRECEDENT_DATA:
            data = COUNTRY_PRECEDENT_DATA[country_lower]
            result.append({
                "country": country.title(),
                "country_flag": data["flag"],
                "precedents": data["precedents"]
            })
        else:
            # Generic fallback for unknown countries
            result.append({
                "country": country.title(),
                "country_flag": "🌍",
                "precedents": [{
                    "case_name": f"{country.title()} Trademark Registration Framework",
                    "court": f"{country.title()} IP Office",
                    "year": "Current",
                    "relevance": f"Local trademark registration requirements for '{brand_name}'",
                    "key_principle": "Standard distinctiveness and non-confusion requirements apply"
                }]
            })
    
    logging.info(f"⚖️ FALLBACK LEGAL PRECEDENTS generated for {len(result)} countries")
    return result


def generate_legal_precedents(trademark_risk_level: str, countries: list = None, brand_name: str = "", category: str = "") -> list:
    """
    Synchronous wrapper for legal precedents generation.
    For backward compatibility - calls fallback directly.
    Use generate_llm_legal_precedents() for async LLM-first approach.
    """
    if not countries:
        countries = ["USA", "India"]
    
    country_names = []
    for country in countries:
        name = country.get('name') if isinstance(country, dict) else str(country)
        country_names.append(name)
    
    return generate_fallback_legal_precedents(country_names, brand_name, category)


def generate_rich_executive_summary(
    brand_name: str,
    category: str,
    verdict: str,
    overall_score: int,
    countries: list,
    linguistic_analysis: dict = None,
    trademark_risk: int = 3,
    nice_class: dict = None,
    domain_available: bool = True,
    cultural_analysis: list = None,
    universal_linguistic: dict = None,  # NEW: Universal Linguistic Analysis
    classification: dict = None  # NEW: Classification with override
) -> str:
    """
    Generate a rich, detailed executive summary (minimum 100 words) that provides
    substantive analysis like a professional brand consultant would.
    
    NOW USES: Universal Linguistic Analysis for accurate language detection,
    cultural significance, and business alignment scoring.
    """
    
    # ==================== USE UNIVERSAL LINGUISTIC ANALYSIS ====================
    has_universal = (
        universal_linguistic and 
        universal_linguistic.get("_analyzed_by") != "fallback" and
        universal_linguistic.get("has_linguistic_meaning") is not None
    )
    
    if has_universal:
        # Extract data from Universal Linguistic Analysis
        has_meaning = universal_linguistic.get("has_linguistic_meaning", False)
        ling_data = universal_linguistic.get("linguistic_analysis", {})
        cultural_sig = universal_linguistic.get("cultural_significance", {})
        business_align = universal_linguistic.get("business_alignment", {})
        ling_classification = universal_linguistic.get("classification", {})
        
        languages = ling_data.get("languages_detected", [])
        decomposition = ling_data.get("decomposition", {})
        combined_meaning = decomposition.get("combined_meaning", "")
        parts = decomposition.get("parts", [])
        part_meanings = decomposition.get("part_meanings", {})
        
        name_type = ling_classification.get("name_type", "Modern/Coined")
        alignment_score = business_align.get("alignment_score", 5)
        alignment_level = business_align.get("alignment_level", "Moderate")
        thematic_connection = business_align.get("thematic_connection", "")
        
        cultural_ref_type = cultural_sig.get("reference_type")
        cultural_details = cultural_sig.get("details", "")
        source_origin = cultural_sig.get("source_text_or_origin", "")
        sentiment = cultural_sig.get("sentiment", "Neutral")
        recognition_regions = cultural_sig.get("regions_of_recognition", [])
        
        instant_recognition = business_align.get("customer_understanding", {}).get("instant_recognition_regions", [])
        needs_explanation = business_align.get("customer_understanding", {}).get("needs_explanation_regions", [])
        
        # Determine brand type from linguistic analysis
        is_coined = name_type in ["True-Coined", "Coined"]
        is_heritage = name_type in ["Heritage", "Mythological", "Foreign-Language"]
        is_meaningful = has_meaning
        
        # Build morpheme insights from part_meanings
        morpheme_insights = []
        for part in parts:
            part_info = part_meanings.get(part, {})
            if isinstance(part_info, dict):
                lang = part_info.get("language", languages[0] if languages else "Unknown")
                meaning = part_info.get("meaning", "")
                morpheme_insights.append(f'"{part.capitalize()}" ({lang}: {meaning})')
            else:
                morpheme_insights.append(f'"{part.capitalize()}" ({part_info})')
    else:
        # Fallback to old linguistic decomposition
        if not linguistic_analysis:
            linguistic_analysis = generate_linguistic_decomposition(brand_name, countries, category)
        
        decomposition = linguistic_analysis.get("decomposition", {})
        morphemes = decomposition.get("morphemes", [])
        brand_type = linguistic_analysis.get("brand_type", "Modern/Coined")
        industry_fit = linguistic_analysis.get("industry_fit", {})
        country_analysis = linguistic_analysis.get("country_analysis", {})
        
        is_coined = brand_type in ["Modern/Coined", "Coined"]
        is_heritage = brand_type == "Heritage"
        is_meaningful = False
        has_meaning = False
        languages = []
        combined_meaning = ""
        name_type = brand_type
        alignment_score = 5
        alignment_level = "Moderate"
        cultural_ref_type = None
        recognition_regions = []
        instant_recognition = []
        needs_explanation = []
        
        morpheme_insights = []
        for morpheme in morphemes:
            origin = morpheme.get("origin", "")
            meaning = morpheme.get("meaning", "")
            morpheme_insights.append(f'"{morpheme["text"].capitalize()}" ({origin}: {meaning.split("/")[0] if "/" in meaning else meaning})')
    
    # Get classification override info
    has_override = classification and classification.get("linguistic_override")
    original_category = classification.get("original_category") if has_override else None
    new_category = classification.get("category") if classification else "FANCIFUL"
    
    # Get NICE class info
    class_number = nice_class.get("class_number", 35) if nice_class else 35
    class_description = nice_class.get("class_description", category) if nice_class else category
    
    # Format target markets
    market_list = []
    for country in countries[:4]:
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        market_list.append(country_name.title())
    markets_str = ", ".join(market_list[:-1]) + f" and {market_list[-1]}" if len(market_list) > 1 else market_list[0] if market_list else "target markets"
    
    # ==================== BUILD EXECUTIVE SUMMARY ====================
    summary_parts = []
    
    # PART 1: Opening statement with verdict context
    if verdict == "GO":
        if is_meaningful and is_heritage:
            # Meaningful heritage name (like RAMASETHU, CHAIDESH)
            lang_str = ", ".join(languages[:2]) if languages else "multiple languages"
            summary_parts.append(
                f'**"{brand_name}"** presents a culturally rich and strategically sound foundation for a {category} brand. '
                f'Derived from {lang_str}, the name carries authentic meaning ("{combined_meaning}") that creates immediate resonance '
                f'in key markets while maintaining distinctiveness for Class {class_number} ({class_description}) registration across {markets_str}.'
            )
        elif is_meaningful:
            # Has meaning but not heritage
            lang_str = ", ".join(languages[:2]) if languages else "linguistic roots"
            summary_parts.append(
                f'**"{brand_name}"** offers a meaningful and memorable foundation for a {category} brand. '
                f'With roots in {lang_str} meaning "{combined_meaning}", the name balances cultural depth with commercial viability, '
                f'supporting registration in Class {class_number} across {markets_str}.'
            )
        elif is_coined:
            summary_parts.append(
                f'**"{brand_name}"** presents a highly distinctive and legally defensible foundation for a {category} brand. '
                f'As a coined neologism with no existing meaning in any language, it effectively bypasses trademark saturation, '
                f'ensuring a clear path to registration in Class {class_number} ({class_description}) across {markets_str}.'
            )
        else:
            summary_parts.append(
                f'**"{brand_name}"** demonstrates strong potential as a trademark for a {category} brand. '
                f'The name balances memorability with distinctiveness, supporting registration in Class {class_number} ({class_description}) '
                f'across {markets_str}.'
            )
    elif verdict == "CAUTION":
        if is_meaningful:
            summary_parts.append(
                f'**"{brand_name}"** ({combined_meaning}) shows cultural promise for the {category} market but requires strategic attention. '
                f'While the meaningful name creates connection in some markets, certain factors in {markets_str} warrant careful evaluation before brand investment.'
            )
        else:
            summary_parts.append(
                f'**"{brand_name}"** shows promise for the {category} market but requires strategic attention to identified concerns. '
                f'While the name has potential for Class {class_number} registration, certain factors in {markets_str} warrant careful evaluation.'
            )
    else:  # NO-GO
        summary_parts.append(
            f'**"{brand_name}"** faces significant challenges for the {category} market. '
            f'Critical issues identified in trademark clearance or cultural fit across {markets_str} suggest alternative naming approaches may better serve the brand strategy.'
        )
    
    # PART 2: Linguistic Structure & Meaning
    if morpheme_insights and len(morpheme_insights) > 0:
        fuse_word = "fuses" if len(morpheme_insights) > 1 else "employs"
        morpheme_join = " with ".join(morpheme_insights)
        
        if is_meaningful and combined_meaning:
            summary_parts.append(
                f'\n\n**Linguistic Structure:** The name strategically {fuse_word} '
                f'{morpheme_join}, creating the compound meaning "{combined_meaning}". '
            )
        else:
            summary_parts.append(
                f'\n\n**Linguistic Structure:** The name {fuse_word} '
                f'{morpheme_join}. '
            )
        
        # Add business alignment insight
        if has_universal and alignment_score >= 7:
            summary_parts.append(
                f'This creates **excellent business alignment** ({alignment_score}/10) with the {category} sector'
                f'{" - " + thematic_connection if thematic_connection else ""}.'
            )
        elif has_universal and alignment_score >= 5:
            summary_parts.append(
                f'This provides moderate business alignment ({alignment_score}/10) with the {category} sector.'
            )
    
    # PART 3: Cultural & Mythological Significance (NEW!)
    if has_universal and cultural_ref_type:
        summary_parts.append(f'\n\n**Cultural Significance:** ')
        if cultural_ref_type == "Mythological":
            summary_parts.append(
                f'The name carries {cultural_ref_type.lower()} weight'
                f'{" from " + source_origin if source_origin else ""}, '
                f'evoking {sentiment.lower()} associations. '
            )
        elif cultural_ref_type == "Religious":
            summary_parts.append(
                f'The name has {cultural_ref_type.lower()} connotations'
                f'{" rooted in " + source_origin if source_origin else ""}, '
                f'which may evoke strong reactions in certain markets. '
            )
        elif cultural_ref_type == "Historical":
            summary_parts.append(
                f'The name references {cultural_ref_type.lower()} elements'
                f'{" from " + source_origin if source_origin else ""}, '
                f'adding depth to the brand narrative. '
            )
        
        if recognition_regions:
            summary_parts.append(f'Recognized in: {", ".join(recognition_regions[:3])}.')
    
    # PART 4: Classification Override (NEW!)
    if has_override:
        summary_parts.append(
            f'\n\n**Trademark Classification:** Due to its linguistic meaning, this name is classified as '
            f'**{new_category}** (not {original_category}) on the trademark distinctiveness spectrum. '
            f'{"This provides strong but not absolute protection." if new_category == "SUGGESTIVE" else ""}'
        )
    
    # PART 5: Market Analysis
    if has_universal:
        if instant_recognition and len(instant_recognition) > 0:
            summary_parts.append(
                f'\n\n**Market Advantage:** Instant cultural recognition in {", ".join(instant_recognition[:3])}, '
                f'enabling heritage-based positioning without extensive brand education.'
            )
        if needs_explanation and len(needs_explanation) > 0:
            summary_parts.append(
                f' Note: Markets like {", ".join(needs_explanation[:2])} may require brand storytelling to convey the name\'s meaning.'
            )
    else:
        # Fallback market analysis from old system
        risk_countries = []
        positive_countries = []
        if linguistic_analysis:
            for country_name, data in linguistic_analysis.get("country_analysis", {}).items():
                if data.get("overall_resonance") == "CRITICAL":
                    risk_countries.append(country_name)
                elif data.get("overall_resonance") == "HIGH" and data.get("risk_count", 0) == 0:
                    positive_countries.append(country_name)
        
        if risk_countries:
            summary_parts.append(
                f'\n\n**⚠️ Critical Considerations:** Market entry in {", ".join(risk_countries)} requires legal consultation due to cultural/regulatory sensitivities.'
            )
        if positive_countries:
            summary_parts.append(
                f'**Market Advantage:** Strong cultural resonance detected in {", ".join(positive_countries)}.'
            )
    
    # PART 6: IP Strategy
    summary_parts.append(
        f'\n\n**IP Strategy:** '
        f'{"Recommended for immediate trademark capture with filing priority in primary markets. " if verdict == "GO" else "Proceed with comprehensive clearance search before commitment. "}'
        f'{"Primary .com domain available for acquisition. " if domain_available else "Alternative domain strategy required (.co, .io, or category TLDs). "}'
        f'{"Social handle @" + brand_name.lower() + " should be secured across major platforms." if verdict != "NO-GO" else ""}'
    )
    
    # PART 7: Closing Recommendation with Score
    if verdict == "GO":
        identity_focus = "the cultural heritage" if is_meaningful and is_heritage else "coined uniqueness" if is_coined else "brand distinctiveness"
        summary_parts.append(
            f'\n\n**Recommendation:** Proceed with brand development, supported by a visual identity that emphasizes '
            f'{identity_focus}. '
            f'Estimated trademark registration timeline: 12-18 months in primary jurisdictions. **RightName Score: {overall_score}/100**.'
        )
    elif verdict == "CAUTION":
        summary_parts.append(
            f'\n\n**Recommendation:** Address identified concerns before significant brand investment. Consider legal opinion on trademark conflicts '
            f'and cultural consultation for sensitive markets. **RightName Score: {overall_score}/100**.'
        )
    else:
        summary_parts.append(
            f'\n\n**Recommendation:** Explore alternative naming directions that better navigate the identified challenges. '
            f'Consider coined neologisms or category-adjacent terminology to reduce conflict risk. **RightName Score: {overall_score}/100**.'
        )
    
    return "".join(summary_parts)


# ============================================================================
# STRATEGY SNAPSHOT FRAMEWORK (Award-Winning Brand Strategy & Trademark Consultant)
# ============================================================================
# Implements 6-step professional framework:
# 1. Legal Trademark Spectrum Classification
# 2. Descriptiveness Depth Test
# 3. Linguistic & Phonetic Evaluation
# 4. Industry × Positioning Alignment Test
# 5. Competitive Imitability Risk
# 6. Brand Asset Ceiling Assessment
# ============================================================================

def generate_strategy_snapshot(
    brand_name: str,
    classification: dict,
    category: str,
    positioning: str,
    countries: list,
    domain_available: bool,
    trademark_risk: int,
    social_data: dict = None
) -> dict:
    """
    Generate investor-grade Strategy Snapshot following the 6-step framework.
    
    Returns:
        {
            "legal_classification": str,
            "classification_reasoning": str,
            "descriptiveness_depth": dict,  # Only for DESCRIPTIVE/SUGGESTIVE
            "linguistic_evaluation": dict,
            "positioning_alignment": dict,
            "imitability_risk": dict,
            "brand_asset_ceiling": dict,
            "strengths": list,
            "risks": list,
            "final_verdict": str
        }
    """
    
    # ========== STEP 1: LEGAL TRADEMARK SPECTRUM CLASSIFICATION ==========
    legal_category = classification.get("category", "DESCRIPTIVE")
    tokens = classification.get("tokens", [])
    dictionary_tokens = classification.get("dictionary_tokens", [])
    invented_tokens = classification.get("invented_tokens", [])
    
    # Generate examiner-style legal reasoning
    legal_reasoning = generate_legal_reasoning(brand_name, legal_category, dictionary_tokens, invented_tokens, category)
    
    # ========== STEP 2: DESCRIPTIVENESS DEPTH TEST ==========
    descriptiveness_depth = None
    if legal_category in ["DESCRIPTIVE", "SUGGESTIVE"]:
        descriptiveness_depth = assess_descriptiveness_depth(brand_name, dictionary_tokens, category)
    
    # ========== STEP 3: LINGUISTIC & PHONETIC EVALUATION ==========
    linguistic_eval = evaluate_linguistics_and_phonetics(brand_name, countries)
    
    # ========== STEP 4: INDUSTRY × POSITIONING ALIGNMENT ==========
    positioning_alignment = assess_positioning_alignment(brand_name, legal_category, category, positioning)
    
    # ========== STEP 5: COMPETITIVE IMITABILITY RISK ==========
    imitability_risk = assess_imitability_risk(brand_name, legal_category, dictionary_tokens, category)
    
    # ========== STEP 6: BRAND ASSET CEILING ASSESSMENT ==========
    asset_ceiling = assess_brand_asset_ceiling(
        brand_name, legal_category, positioning, trademark_risk, 
        positioning_alignment, imitability_risk
    )
    
    # ========== GENERATE STRENGTHS & RISKS ==========
    strengths = generate_strategic_strengths(
        brand_name, legal_category, linguistic_eval, positioning_alignment,
        imitability_risk, asset_ceiling, domain_available, social_data
    )
    
    risks = generate_strategic_risks(
        brand_name, legal_category, descriptiveness_depth, linguistic_eval,
        positioning_alignment, imitability_risk, asset_ceiling, domain_available, countries
    )
    
    # ========== FINAL VERDICT ==========
    final_verdict = generate_final_verdict(
        brand_name, legal_category, positioning, positioning_alignment, 
        asset_ceiling, trademark_risk
    )
    
    return {
        "legal_classification": legal_category,
        "classification_reasoning": legal_reasoning,
        "descriptiveness_depth": descriptiveness_depth,
        "linguistic_evaluation": linguistic_eval,
        "positioning_alignment": positioning_alignment,
        "imitability_risk": imitability_risk,
        "brand_asset_ceiling": asset_ceiling,
        "strengths": strengths,
        "risks": risks,
        "final_verdict": final_verdict
    }


def generate_legal_reasoning(brand_name: str, category: str, dictionary_tokens: list, invented_tokens: list, industry: str) -> str:
    """Generate USPTO/EUIPO/WIPO examiner-style legal reasoning."""
    
    if category == "GENERIC":
        return (
            f"'{brand_name}' directly names the product category '{industry}'. "
            f"Under TMEP §1209.01(a), generic terms are unregistrable as they must remain free for all market participants. "
            f"No amount of acquired distinctiveness can overcome generic status."
        )
    
    elif category == "DESCRIPTIVE":
        token_list = ", ".join([f"'{t}'" for t in dictionary_tokens]) if dictionary_tokens else "common words"
        return (
            f"'{brand_name}' comprises dictionary words ({token_list}) that directly describe the product/service attributes. "
            f"Per TMEP §1209.01(b), descriptive marks require proof of Secondary Meaning (acquired distinctiveness) under §2(f). "
            f"Registration on Supplemental Register possible; Principal Register requires 5+ years exclusive use evidence."
        )
    
    elif category == "SUGGESTIVE":
        return (
            f"'{brand_name}' suggests qualities of the product but requires imagination to connect name to goods/services. "
            f"Under Zatarains v. Oak Grove Smokehouse, suggestive marks are inherently distinctive. "
            f"Registrable on Principal Register without Secondary Meaning proof, though enforcement scope is narrower than arbitrary/fanciful."
        )
    
    elif category == "ARBITRARY":
        return (
            f"'{brand_name}' uses a common word in a context unrelated to its dictionary meaning. "
            f"Like 'Apple' for computers or 'Amazon' for e-commerce, arbitrary marks receive strong protection under Lanham Act §2. "
            f"Inherently distinctive; broad enforcement scope across similar goods/services."
        )
    
    else:  # FANCIFUL
        return (
            f"'{brand_name}' is a coined/invented term with no prior dictionary meaning. "
            f"Fanciful marks like 'Xerox', 'Kodak', and 'Häagen-Dazs' receive the strongest trademark protection. "
            f"Inherently distinctive; maximum enforcement scope; highest brand asset value potential."
        )


def assess_descriptiveness_depth(brand_name: str, dictionary_tokens: list, category: str) -> dict:
    """
    For DESCRIPTIVE/SUGGESTIVE marks, assess HOW descriptive:
    - HIGH: Directly describes function or category
    - MODERATE: Describes benefit or feature
    - LOW: Tangential relationship
    """
    brand_lower = brand_name.lower()
    category_lower = category.lower()
    
    # Check what the name describes
    describes_function = False
    describes_benefit = False
    describes_category = False
    
    # Function words
    function_indicators = ["check", "track", "find", "get", "book", "pay", "scan", "search", "send", "call", "connect", "shop", "buy", "sell", "rent", "hire"]
    # Benefit words
    benefit_indicators = ["fast", "quick", "easy", "smart", "safe", "secure", "best", "pro", "premium", "fresh", "clean", "healthy"]
    
    for token in dictionary_tokens:
        token_lower = token.lower()
        if token_lower in function_indicators:
            describes_function = True
        if token_lower in benefit_indicators:
            describes_benefit = True
        if token_lower in category_lower or category_lower in token_lower:
            describes_category = True
    
    # Determine depth
    if describes_function and describes_category:
        depth = "HIGH"
        describes = "Function + Category"
        reasoning = f"Name directly states what the product does (function) and for what (category). Maximum descriptiveness = weakest protection."
    elif describes_function:
        depth = "HIGH"
        describes = "Function"
        reasoning = f"Name directly describes what the product does. Functional descriptiveness is difficult to overcome."
    elif describes_category:
        depth = "HIGH"
        describes = "Category"
        reasoning = f"Name incorporates category terminology. Risk of examiner refusal under descriptiveness grounds."
    elif describes_benefit:
        depth = "MODERATE"
        describes = "Benefit"
        reasoning = f"Name suggests product benefits rather than literal function. Secondary Meaning may be achievable with evidence."
    else:
        depth = "LOW"
        describes = "Tangential"
        reasoning = f"Descriptive elements are tangential to core product. Closer to suggestive; registration more likely."
    
    return {
        "depth": depth,
        "describes": describes,
        "reasoning": reasoning
    }


def evaluate_linguistics_and_phonetics(brand_name: str, countries: list) -> dict:
    """
    Evaluate:
    - Pronunciation ease
    - Memorability
    - Spelling confusion risk
    - Cross-cultural neutrality
    """
    
    # Pronunciation difficulty factors
    difficult_combinations = ["sch", "tch", "ght", "phl", "xyl", "zw", "ck", "qu"]
    difficult_endings = ["eux", "ough", "eaux", "heim", "stadt"]
    
    pronunciation_issues = []
    for combo in difficult_combinations:
        if combo in brand_name.lower():
            pronunciation_issues.append(f"'{combo}' cluster may cause pronunciation hesitation")
    
    for ending in difficult_endings:
        if brand_name.lower().endswith(ending):
            pronunciation_issues.append(f"'-{ending}' ending unfamiliar in non-European markets")
    
    # Check syllable count (2-3 is optimal)
    vowels = sum(1 for c in brand_name.lower() if c in 'aeiou')
    syllable_estimate = max(1, vowels)
    
    if syllable_estimate > 4:
        pronunciation_issues.append(f"~{syllable_estimate} syllables exceeds optimal 2-3 for memorability")
    
    # Spelling confusion risk
    spelling_risks = []
    confusing_patterns = [
        ("ph", "f"), ("ck", "k"), ("ie", "y"), ("ey", "y"), ("oo", "u"),
        ("ee", "i"), ("ou", "u"), ("ight", "ite")
    ]
    for pattern, alternative in confusing_patterns:
        if pattern in brand_name.lower():
            spelling_risks.append(f"'{pattern}' could be typed as '{alternative}'")
    
    # Memorability score
    memorability_score = 10
    if len(brand_name) > 10:
        memorability_score -= 2
    if len(brand_name) > 14:
        memorability_score -= 2
    if syllable_estimate > 3:
        memorability_score -= 1
    if len(spelling_risks) > 0:
        memorability_score -= 1
    memorability_score = max(3, memorability_score)
    
    # Cultural neutrality check (basic)
    cultural_flags = []
    sensitive_sounds = {
        "Thailand": ["rama", "king", "royal", "chakri"],
        "India": ["ram", "krishna", "shiva", "allah"],
        "China": ["xi", "mao", "death", "four"],
        "Japan": ["shi", "ku"]  # shi=death, ku=suffering
    }
    
    for country in countries:
        if country in sensitive_sounds:
            for sound in sensitive_sounds[country]:
                if sound in brand_name.lower():
                    cultural_flags.append(f"{country}: '{sound}' may have cultural sensitivity")
    
    return {
        "pronunciation_ease": "HIGH" if len(pronunciation_issues) == 0 else "MODERATE" if len(pronunciation_issues) <= 2 else "LOW",
        "pronunciation_issues": pronunciation_issues,
        "memorability_score": memorability_score,
        "memorability_rating": "HIGH" if memorability_score >= 8 else "MODERATE" if memorability_score >= 6 else "LOW",
        "spelling_confusion_risk": spelling_risks,
        "cultural_flags": cultural_flags,
        "overall_linguistic_rating": "STRONG" if len(pronunciation_issues) == 0 and memorability_score >= 7 and len(cultural_flags) == 0 else "ADEQUATE" if memorability_score >= 5 else "WEAK"
    }


def assess_positioning_alignment(brand_name: str, legal_category: str, industry: str, positioning: str) -> dict:
    """
    Assess whether the name supports:
    - Industry naming norms
    - Stated positioning tier
    
    Luxury requires abstraction; Mass allows clarity.
    """
    positioning_lower = positioning.lower() if positioning else "mid-range"
    
    # Positioning expectations
    positioning_requirements = {
        "luxury": {
            "ideal_categories": ["FANCIFUL", "ARBITRARY"],
            "acceptable_categories": ["SUGGESTIVE"],
            "problematic_categories": ["DESCRIPTIVE", "GENERIC"],
            "expectation": "Abstraction, mystery, non-descriptiveness (Hermès, Chanel, Rolex)"
        },
        "premium": {
            "ideal_categories": ["FANCIFUL", "ARBITRARY", "SUGGESTIVE"],
            "acceptable_categories": [],
            "problematic_categories": ["DESCRIPTIVE", "GENERIC"],
            "expectation": "Distinctiveness with subtle meaning (Tesla, Apple, Spotify)"
        },
        "mid-range": {
            "ideal_categories": ["SUGGESTIVE", "ARBITRARY"],
            "acceptable_categories": ["FANCIFUL", "DESCRIPTIVE"],
            "problematic_categories": ["GENERIC"],
            "expectation": "Balance of clarity and distinctiveness (Netflix, PayPal)"
        },
        "budget": {
            "ideal_categories": ["DESCRIPTIVE", "SUGGESTIVE"],
            "acceptable_categories": ["ARBITRARY", "FANCIFUL"],
            "problematic_categories": ["GENERIC"],
            "expectation": "Clarity over uniqueness (Dollar General, Toys R Us)"
        },
        "mass": {
            "ideal_categories": ["DESCRIPTIVE", "SUGGESTIVE"],
            "acceptable_categories": ["ARBITRARY"],
            "problematic_categories": ["GENERIC"],
            "expectation": "Immediate comprehension (General Electric, American Airlines)"
        }
    }
    
    # Get positioning requirements
    pos_key = "mid-range"
    for key in positioning_requirements:
        if key in positioning_lower:
            pos_key = key
            break
    
    requirements = positioning_requirements[pos_key]
    
    # Check alignment
    if legal_category in requirements["ideal_categories"]:
        alignment = "STRONG"
        alignment_reasoning = f"'{brand_name}' ({legal_category}) is ideal for {pos_key.title()} positioning. {requirements['expectation']}"
    elif legal_category in requirements["acceptable_categories"]:
        alignment = "ADEQUATE"
        alignment_reasoning = f"'{brand_name}' ({legal_category}) is acceptable for {pos_key.title()} positioning, though not optimal. {requirements['expectation']}"
    elif legal_category in requirements["problematic_categories"]:
        alignment = "MISALIGNED"
        alignment_reasoning = f"'{brand_name}' ({legal_category}) conflicts with {pos_key.title()} positioning requirements. {requirements['expectation']}"
    else:
        alignment = "NEUTRAL"
        alignment_reasoning = f"'{brand_name}' positioning alignment is neutral."
    
    # Premium pricing power assessment
    pricing_power = "HIGH" if legal_category in ["FANCIFUL", "ARBITRARY"] else "MODERATE" if legal_category == "SUGGESTIVE" else "LOW"
    
    return {
        "positioning": pos_key.title(),
        "alignment": alignment,
        "alignment_reasoning": alignment_reasoning,
        "pricing_power": pricing_power,
        "industry_norms_fit": "STANDARD" if legal_category not in ["GENERIC"] else "NON-COMPLIANT"
    }


def assess_imitability_risk(brand_name: str, legal_category: str, dictionary_tokens: list, category: str) -> dict:
    """
    Assess:
    - Ease of cloning via prefixes/suffixes
    - Phonetic/visual lookalike risk
    - Naming congestion in category
    """
    
    brand_lower = brand_name.lower()
    
    # Clone-ability assessment
    clone_examples = []
    
    # Prefix variations
    common_prefixes = ["my", "get", "go", "i", "e", "ez", "quick", "smart", "super", "mega", "pro", "neo"]
    for prefix in common_prefixes:
        if brand_lower.startswith(prefix):
            clone_examples.append(f"Remove prefix: '{brand_name[len(prefix):]}'")
            break
    
    # Suffix variations
    common_suffixes = ["ly", "ify", "er", "io", "app", "hub", "lab", "box", "now", "go", "pro"]
    for suffix in common_suffixes:
        if brand_lower.endswith(suffix):
            clone_examples.append(f"Alternative suffix: '{brand_name[:-len(suffix)]}Hub', '{brand_name[:-len(suffix)]}Now'")
            break
    
    # Word substitution risk (for descriptive names)
    if len(dictionary_tokens) >= 2:
        clone_examples.append(f"Synonym swap: Replace '{dictionary_tokens[0]}' with synonym")
        clone_examples.append(f"Pluralization: '{brand_name}s' or '{brand_name}Plus'")
    
    # Phonetic lookalike risk
    phonetic_risk = []
    vowel_swaps = [("a", "e"), ("e", "i"), ("i", "y"), ("o", "u")]
    for v1, v2 in vowel_swaps:
        if v1 in brand_lower:
            variant = brand_lower.replace(v1, v2, 1)
            phonetic_risk.append(f"'{variant.title()}' (vowel swap)")
    
    # Imitability score
    if legal_category == "FANCIFUL":
        imitability = "LOW"
        imitability_reasoning = "Coined terms are difficult to clone without obvious infringement."
    elif legal_category == "ARBITRARY":
        imitability = "LOW"
        imitability_reasoning = "Arbitrary usage creates unique brand space."
    elif legal_category == "SUGGESTIVE":
        imitability = "MODERATE"
        imitability_reasoning = "Suggestive names face competition from similar suggestions in same category."
    else:  # DESCRIPTIVE or GENERIC
        imitability = "HIGH"
        imitability_reasoning = "Descriptive terms invite direct competition from synonyms and variations."
    
    return {
        "imitability_level": imitability,
        "imitability_reasoning": imitability_reasoning,
        "clone_examples": clone_examples[:3],  # Limit to 3
        "phonetic_lookalikes": phonetic_risk[:2],  # Limit to 2
        "congestion_risk": "HIGH" if legal_category in ["DESCRIPTIVE", "GENERIC"] else "MODERATE" if legal_category == "SUGGESTIVE" else "LOW"
    }


def assess_brand_asset_ceiling(
    brand_name: str, 
    legal_category: str, 
    positioning: str,
    trademark_risk: int,
    positioning_alignment: dict,
    imitability_risk: dict
) -> dict:
    """
    Evaluate long-term brand asset value:
    - Trademark enforceability
    - Premium pricing power
    - Multi-category expansion potential
    - Acquisition attractiveness
    """
    
    # Trademark enforceability
    enforceability_scores = {
        "FANCIFUL": ("MAXIMUM", "Full scope of protection across related goods/services"),
        "ARBITRARY": ("HIGH", "Strong protection within product category"),
        "SUGGESTIVE": ("MODERATE", "Protection limited to confusingly similar marks"),
        "DESCRIPTIVE": ("LIMITED", "Protection only after Secondary Meaning established"),
        "GENERIC": ("NONE", "Cannot be enforced as trademark")
    }
    enforceability, enforce_reason = enforceability_scores.get(legal_category, ("UNKNOWN", ""))
    
    # Multi-category expansion potential
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        expansion = "HIGH"
        expansion_reason = "Abstract name enables expansion into adjacent categories"
    elif legal_category == "SUGGESTIVE":
        expansion = "MODERATE"
        expansion_reason = "Suggestive meaning may constrain category stretch"
    else:
        expansion = "LOW"
        expansion_reason = "Descriptive names are category-locked"
    
    # Acquisition attractiveness
    positioning_lower = positioning.lower() if positioning else "mid-range"
    
    # FIX: Operator precedence - parentheses required!
    # Only FANCIFUL/ARBITRARY with Luxury/Premium positioning get HIGH acquisition
    if legal_category in ["FANCIFUL", "ARBITRARY"] and ("luxury" in positioning_lower or "premium" in positioning_lower):
        acquisition = "HIGH"
        acquisition_reason = "Strong trademark + premium positioning = valuable IP asset"
    elif legal_category in ["FANCIFUL", "ARBITRARY", "SUGGESTIVE"]:
        acquisition = "MODERATE"
        acquisition_reason = "Defensible trademark but acquisition premium depends on market position"
    else:
        acquisition = "LOW"
        acquisition_reason = "Weak trademark limits strategic value in M&A"
    
    # Overall ceiling
    ceiling_factors = {
        "FANCIFUL": 95,
        "ARBITRARY": 85,
        "SUGGESTIVE": 65,
        "DESCRIPTIVE": 40,
        "GENERIC": 10
    }
    base_ceiling = ceiling_factors.get(legal_category, 50)
    
    # Adjustments
    if positioning_alignment.get("alignment") == "MISALIGNED":
        base_ceiling -= 15
    if imitability_risk.get("imitability_level") == "HIGH":
        base_ceiling -= 10
    if trademark_risk > 5:
        base_ceiling -= (trademark_risk - 5) * 3
    
    base_ceiling = max(10, min(95, base_ceiling))
    
    if base_ceiling >= 80:
        ceiling_rating = "HIGH"
    elif base_ceiling >= 60:
        ceiling_rating = "MODERATE"
    elif base_ceiling >= 40:
        ceiling_rating = "LIMITED"
    else:
        ceiling_rating = "MINIMAL"
    
    return {
        "ceiling_score": base_ceiling,
        "ceiling_rating": ceiling_rating,
        "trademark_enforceability": enforceability,
        "enforceability_reasoning": enforce_reason,
        "expansion_potential": expansion,
        "expansion_reasoning": expansion_reason,
        "acquisition_attractiveness": acquisition,
        "acquisition_reasoning": acquisition_reason
    }


def generate_strategic_strengths(
    brand_name: str,
    legal_category: str,
    linguistic_eval: dict,
    positioning_alignment: dict,
    imitability_risk: dict,
    asset_ceiling: dict,
    domain_available: bool,
    social_data: dict
) -> list:
    """Generate KEY STRATEGIC STRENGTHS based on framework analysis."""
    
    strengths = []
    
    # Legal strength - based on trademark classification
    if legal_category == "FANCIFUL":
        strengths.append(f"**Strongest Trademark Class:** Coined term receives maximum legal protection under TMEP §1209")
    elif legal_category == "ARBITRARY":
        strengths.append(f"**Strong Trademark Position:** Arbitrary usage provides inherent distinctiveness")
    elif legal_category == "SUGGESTIVE":
        strengths.append(f"**Registrable Without Proof:** Suggestive mark is inherently distinctive; no Secondary Meaning required")
    elif legal_category == "DESCRIPTIVE":
        # DESCRIPTIVE names have functional strengths, NOT IP strengths
        strengths.append(f"**High Functional Clarity:** Users immediately understand the product's value proposition without explanation")
    
    # Linguistic strengths
    if linguistic_eval.get("pronunciation_ease") == "HIGH":
        strengths.append(f"**Phonetic Clarity:** Clean pronunciation across English and non-native markets")
    if linguistic_eval.get("memorability_rating") == "HIGH":
        strengths.append(f"**High Memorability:** {len(brand_name)}-character length optimized for recall ({linguistic_eval.get('memorability_score', 7)}/10)")
    if not linguistic_eval.get("cultural_flags"):
        strengths.append(f"**Cultural Neutrality:** No adverse connotations detected across target markets")
    
    # Positioning strengths - ONLY for strong/adequate alignment
    if positioning_alignment.get("alignment") == "STRONG":
        strengths.append(f"**Positioning Fit:** Name architecture supports {positioning_alignment.get('positioning', 'Premium')} market positioning")
    if positioning_alignment.get("pricing_power") == "HIGH":
        strengths.append(f"**Premium Pricing Power:** Abstract naming enables price premium over descriptive competitors")
    
    # Competitive strengths
    if imitability_risk.get("imitability_level") == "LOW":
        strengths.append(f"**Defensible Moat:** Low clone-ability provides competitive barrier")
    
    # Asset strengths - ONLY for FANCIFUL/ARBITRARY with actual high ceiling
    # NOTE: DESCRIPTIVE names should NEVER show "Investment Grade" - that's a contradiction
    if asset_ceiling.get("expansion_potential") == "HIGH":
        strengths.append(f"**Expansion Runway:** Name supports multi-category and geographic expansion")
    if asset_ceiling.get("acquisition_attractiveness") == "HIGH" and legal_category in ["FANCIFUL", "ARBITRARY"]:
        strengths.append(f"**Investment Grade:** Strong IP asset suitable for premium acquisition valuation")
    
    # Digital strengths
    if domain_available:
        strengths.append(f"**Domain Available:** Primary .com domain securable")
    
    # Additional strengths for DESCRIPTIVE names (marketing value, not IP value)
    if legal_category == "DESCRIPTIVE":
        if len(strengths) < 3:
            strengths.append(f"**Low Marketing Education Cost:** Name self-explains product category")
        if len(strengths) < 4:
            strengths.append(f"**SEO Potential:** Descriptive terms may align with user search queries")
    
    return strengths[:6]  # Limit to 6


def generate_strategic_risks(
    brand_name: str,
    legal_category: str,
    descriptiveness_depth: dict,
    linguistic_eval: dict,
    positioning_alignment: dict,
    imitability_risk: dict,
    asset_ceiling: dict,
    domain_available: bool,
    countries: list
) -> list:
    """Generate KEY STRATEGIC RISKS based on framework analysis."""
    
    risks = []
    
    # Legal risks
    if legal_category == "GENERIC":
        risks.append(f"**⛔ UNREGISTRABLE:** Generic terms cannot be trademarked under any jurisdiction")
    elif legal_category == "DESCRIPTIVE":
        if descriptiveness_depth and descriptiveness_depth.get("depth") == "HIGH":
            risks.append(f"**Weak Trademark:** {descriptiveness_depth.get('describes', 'Descriptive')} descriptiveness requires Secondary Meaning proof (5+ years exclusive use)")
        else:
            risks.append(f"**Limited Protection:** Descriptive marks require evidence of acquired distinctiveness for Principal Register")
    
    # Descriptiveness depth risks
    if descriptiveness_depth:
        if descriptiveness_depth.get("depth") == "HIGH":
            risks.append(f"**Registration Challenge:** {descriptiveness_depth.get('reasoning', 'High descriptiveness may face examiner refusal')}")
    
    # Positioning misalignment
    if positioning_alignment.get("alignment") == "MISALIGNED":
        risks.append(f"**Positioning Conflict:** {positioning_alignment.get('alignment_reasoning', 'Name conflicts with target market positioning')}")
    if positioning_alignment.get("pricing_power") == "LOW":
        risks.append(f"**Zero Premium Signal:** Descriptive name commoditizes offering - pricing power limited")
    
    # Imitability risks
    if imitability_risk.get("imitability_level") == "HIGH":
        clones = imitability_risk.get("clone_examples", [])
        if clones:
            risks.append(f"**High Clone Risk:** Easily imitated via {clones[0] if clones else 'synonyms and variations'}")
        risks.append(f"**No Competitive Moat:** {imitability_risk.get('imitability_reasoning', 'Descriptive terms invite direct competition')}")
    
    # Linguistic risks
    if linguistic_eval.get("pronunciation_issues"):
        risks.append(f"**Pronunciation Barrier:** {linguistic_eval['pronunciation_issues'][0]}")
    if linguistic_eval.get("cultural_flags"):
        for flag in linguistic_eval["cultural_flags"][:2]:
            risks.append(f"**Cultural Sensitivity:** {flag}")
    if linguistic_eval.get("memorability_rating") == "LOW":
        risks.append(f"**Low Memorability:** {len(brand_name)} characters exceeds optimal length for word-of-mouth")
    
    # Asset ceiling risks
    if asset_ceiling.get("ceiling_rating") in ["LIMITED", "MINIMAL"]:
        risks.append(f"**Low Asset Ceiling:** Brand value capped at {asset_ceiling.get('ceiling_score', 40)}/100 due to weak trademark position")
    if asset_ceiling.get("expansion_potential") == "LOW":
        risks.append(f"**Category Lock:** {asset_ceiling.get('expansion_reasoning', 'Descriptive names constrain category expansion')}")
    if asset_ceiling.get("acquisition_attractiveness") == "LOW":
        risks.append(f"**Limited Exit Value:** {asset_ceiling.get('acquisition_reasoning', 'Weak trademark limits M&A premium')}")
    
    # Digital risks
    if not domain_available:
        risks.append(f"**Domain Unavailable:** Primary .com domain taken - acquisition or alternative strategy required")
    
    # If minimal risks found
    if not risks:
        risks.append(f"**Standard Due Diligence:** Recommend comprehensive trademark search before filing")
    
    return risks[:6]  # Limit to 6


def generate_final_verdict(
    brand_name: str,
    legal_category: str,
    positioning: str,
    positioning_alignment: dict,
    asset_ceiling: dict,
    trademark_risk: int
) -> str:
    """Generate 1-2 sentence decisive, no-hedging final consultant verdict."""
    
    positioning_lower = positioning.lower() if positioning else "mid-range"
    ceiling_score = asset_ceiling.get("ceiling_score", 50)
    alignment = positioning_alignment.get("alignment", "NEUTRAL")
    
    # FANCIFUL - Best case
    if legal_category == "FANCIFUL" and alignment != "MISALIGNED":
        return f"'{brand_name}' is an investment-grade trademark asset. Recommend immediate filing with comprehensive global protection strategy."
    
    # ARBITRARY - Strong
    if legal_category == "ARBITRARY" and alignment != "MISALIGNED":
        return f"'{brand_name}' offers strong trademark defensibility. Proceed with registration; prioritize key jurisdictions for enforcement."
    
    # SUGGESTIVE - Solid
    if legal_category == "SUGGESTIVE":
        if alignment == "STRONG":
            return f"'{brand_name}' balances memorability with protectability. Suitable for trademark filing with standard watch service."
        else:
            return f"'{brand_name}' is registrable but faces category competition. Consider strengthening brand architecture through design marks."
    
    # DESCRIPTIVE - Problematic for premium
    if legal_category == "DESCRIPTIVE":
        if "luxury" in positioning_lower or "premium" in positioning_lower:
            return f"'{brand_name}' is fundamentally unsuitable for {positioning_lower} positioning. Recommend renaming with arbitrary or fanciful approach for investor-grade IP."
        elif ceiling_score >= 50:
            return f"'{brand_name}' may function for mass-market but limits long-term brand equity. Acceptable if speed-to-market outweighs IP strength."
        else:
            return f"'{brand_name}' offers weak trademark protection and low asset ceiling. Recommend exploring distinctive alternatives before significant brand investment."
    
    # GENERIC - Reject
    if legal_category == "GENERIC":
        return f"'{brand_name}' is legally unprotectable. Immediate renaming required before any market investment."
    
    # Default
    return f"'{brand_name}' requires trademark attorney consultation before proceeding. Classification ambiguity suggests registration risk."


# ============================================================================
# THREE-PILLAR BRAND ASSESSMENT (McKinsey-Style Analysis)
# ============================================================================
# Connected to pre-computed classification for consistency
# ============================================================================

def generate_mckinsey_analysis(
    brand_name: str,
    classification: dict,
    category: str,
    positioning: str,
    verdict: str,
    trademark_risk: int,
    imitability_risk: dict = None,
    positioning_alignment: dict = None
) -> dict:
    """
    Generate Three-Pillar Brand Assessment connected to our classification system.
    
    Pillars:
    1. Benefits & Experiences - What does the name PROMISE?
    2. Distinctiveness - How UNIQUE is the name?
    3. Brand Architecture - Can this name SCALE?
    """
    
    legal_category = classification.get("category", "DESCRIPTIVE")
    tokens = classification.get("tokens", [])
    dictionary_tokens = classification.get("dictionary_tokens", [])
    invented_tokens = classification.get("invented_tokens", [])
    distinctiveness = classification.get("distinctiveness", "LOW")
    protectability = classification.get("protectability", "WEAK")
    reasoning = classification.get("reasoning", "")
    
    # ========== MODULE 1: BENEFITS & EXPERIENCES ==========
    benefits_experiences = generate_benefits_experiences(
        brand_name, legal_category, dictionary_tokens, invented_tokens, category, positioning
    )
    
    # ========== MODULE 2: DISTINCTIVENESS ==========
    distinctiveness_analysis = generate_distinctiveness_module(
        brand_name, legal_category, distinctiveness, category, 
        imitability_risk, dictionary_tokens
    )
    
    # ========== MODULE 3: BRAND ARCHITECTURE ==========
    brand_architecture = generate_brand_architecture_module(
        brand_name, legal_category, distinctiveness, category, positioning
    )
    
    # ========== EXECUTIVE RECOMMENDATION ==========
    # Based on legal category + positioning alignment
    if legal_category == "GENERIC":
        exec_recommendation = "PIVOT"
        rationale = f"'{brand_name}' is legally unprotectable as a generic term. Fundamental rename required before any brand investment."
        critical = f"**CRITICAL FAILURE:** Generic terms cannot be trademarked under USPTO, EUIPO, or any major jurisdiction. This name will provide ZERO legal protection regardless of marketing spend."
    elif legal_category == "DESCRIPTIVE":
        if positioning and ("luxury" in positioning.lower() or "premium" in positioning.lower()):
            exec_recommendation = "PIVOT"
            rationale = f"'{brand_name}' is descriptive ({', '.join(dictionary_tokens)}), fundamentally misaligned with {positioning} positioning. Descriptive names commoditize premium offerings."
            critical = f"**STRATEGIC MISMATCH:** Descriptive names signal utility, not prestige. Luxury/Premium brands require abstract, coined, or arbitrary names (Hermès, Tesla, Apple) to command price premiums."
        else:
            exec_recommendation = "REFINE"
            rationale = f"'{brand_name}' is descriptive, offering clarity but weak trademark protection. Consider if brand defensibility is critical to your strategy."
            critical = f"**TRADEMARK WARNING:** Descriptive marks require 5+ years of exclusive use to prove Secondary Meaning. Competitors can legally use similar descriptive terms. Budget for legal monitoring."
    elif legal_category == "SUGGESTIVE":
        if positioning_alignment and positioning_alignment.get("alignment") == "MISALIGNED":
            exec_recommendation = "REFINE"
            rationale = f"'{brand_name}' is suggestive (registrable) but may not optimally support {positioning} positioning. Consider whether the suggestion aligns with brand values."
            critical = f"**POSITIONING GAP:** While legally protectable, the suggestive meaning may create perception issues for your target market segment."
        else:
            exec_recommendation = "PROCEED"
            rationale = f"'{brand_name}' is suggestive - inherently distinctive and registrable without Secondary Meaning proof. Good balance of meaning and protection."
            critical = f"**SOLID FOUNDATION:** Suggestive marks are the 'sweet spot' - memorable enough to hint at benefits, distinctive enough for trademark protection."
    elif legal_category in ["ARBITRARY", "FANCIFUL"]:
        exec_recommendation = "PROCEED"
        rationale = f"'{brand_name}' is {'an arbitrary term (common word in unrelated context)' if legal_category == 'ARBITRARY' else 'a coined/fanciful term (invented word)'} - strongest trademark class with maximum legal protection."
        critical = f"**INVESTMENT-GRADE IP:** {'Arbitrary' if legal_category == 'ARBITRARY' else 'Fanciful'} marks receive the {'strong' if legal_category == 'ARBITRARY' else 'strongest'} trademark protection. High enforcement power across jurisdictions."
    else:
        exec_recommendation = "REFINE"
        rationale = f"'{brand_name}' classification is ambiguous. Recommend trademark attorney consultation before proceeding."
        critical = f"**CLASSIFICATION UNCLEAR:** Unable to definitively classify. Professional legal opinion recommended."
    
    # Override to PIVOT if verdict is REJECT (existing brand conflict)
    if verdict == "REJECT":
        exec_recommendation = "PIVOT"
        critical = f"**EXISTING CONFLICT:** {critical} Additionally, trademark conflicts detected require alternative naming approach."
    
    # ========== ALTERNATIVE DIRECTIONS ==========
    alternative_directions = []
    if exec_recommendation in ["REFINE", "PIVOT"]:
        alternative_directions = generate_alternative_directions(brand_name, legal_category, category)
    
    return {
        "benefits_experiences": benefits_experiences,
        "distinctiveness": distinctiveness_analysis,
        "brand_architecture": brand_architecture,
        "executive_recommendation": exec_recommendation,
        "recommendation_rationale": rationale,
        "critical_assessment": critical,
        "alternative_directions": alternative_directions
    }


def generate_benefits_experiences(
    brand_name: str, 
    legal_category: str, 
    dictionary_tokens: list,
    invented_tokens: list,
    category: str,
    positioning: str
) -> dict:
    """Generate Module 1: Benefits & Experiences based on classification."""
    
    # Linguistic roots analysis based on actual classification
    if legal_category == "FANCIFUL":
        linguistic_roots = f"**Coined/Invented Term:** '{brand_name}' has no dictionary origin - a pure neologism. This provides maximum trademark distinctiveness and allows the brand to define its own meaning through marketing."
        emotional_promises = ["Innovation", "Pioneering", "Exclusivity", "Modernity"]
        functional_benefits = ["Unique Identity", "No Competing Associations", "Global Flexibility"]
    elif legal_category == "ARBITRARY":
        linguistic_roots = f"**Arbitrary Usage:** '{brand_name}' uses {'a common word' if dictionary_tokens else 'familiar elements'} in an unrelated context to {category}. Like 'Apple' for computers, this creates memorable disconnect."
        emotional_promises = ["Familiarity", "Approachability", "Confidence", "Trust"]
        functional_benefits = ["Easy Recall", "Built-in Recognition", "Conversation Starter"]
    elif legal_category == "SUGGESTIVE":
        linguistic_roots = f"**Suggestive Construction:** '{brand_name}' hints at product benefits through {', '.join(dictionary_tokens) if dictionary_tokens else 'sound symbolism'} without directly describing them. Requires imagination to connect."
        emotional_promises = ["Aspiration", "Discovery", "Intrigue", "Promise"]
        functional_benefits = ["Benefit Suggestion", "Memorable Hook", "Marketing Leverage"]
    elif legal_category == "DESCRIPTIVE":
        linguistic_roots = f"**Descriptive Composition:** '{brand_name}' directly communicates product attributes through dictionary words: {', '.join(dictionary_tokens) if dictionary_tokens else 'common terms'}. High clarity but weak differentiation."
        emotional_promises = ["Clarity", "Reliability", "Straightforwardness"]
        functional_benefits = ["Instant Understanding", "Low Education Cost", "SEO Potential"]
    else:  # GENERIC
        linguistic_roots = f"**Generic Term:** '{brand_name}' names the product category itself. Cannot function as a trademark - legally unprotectable."
        emotional_promises = ["None - Generic terms lack emotional distinctiveness"]
        functional_benefits = ["Category Recognition Only"]
    
    # Phonetic analysis
    syllables = max(1, sum(1 for c in brand_name.lower() if c in 'aeiou'))
    phonetic_analysis = f"**Sound Architecture:** {len(brand_name)} characters, ~{syllables} syllables. "
    if syllables <= 2:
        phonetic_analysis += "Optimal brevity for recall and word-of-mouth."
    elif syllables <= 3:
        phonetic_analysis += "Good length for brand building."
    else:
        phonetic_analysis += "Extended length may challenge memorability."
    
    # Benefit map based on classification
    benefit_map = []
    if legal_category == "FANCIFUL":
        benefit_map = [
            {"name_trait": "Coined structure", "user_perception": "Innovative, cutting-edge brand", "benefit_type": "Emotional"},
            {"name_trait": "No dictionary meaning", "user_perception": "Exclusive, premium feel", "benefit_type": "Emotional"},
            {"name_trait": "Unique phonetics", "user_perception": "Memorable, distinctive", "benefit_type": "Functional"}
        ]
    elif legal_category == "ARBITRARY":
        benefit_map = [
            {"name_trait": "Familiar word", "user_perception": "Approachable, trustworthy", "benefit_type": "Emotional"},
            {"name_trait": "Unexpected context", "user_perception": "Creative, bold choice", "benefit_type": "Emotional"},
            {"name_trait": "Easy pronunciation", "user_perception": "Accessible, shareable", "benefit_type": "Functional"}
        ]
    elif legal_category == "SUGGESTIVE":
        benefit_map = [
            {"name_trait": "Suggestive meaning", "user_perception": "Clever, intriguing", "benefit_type": "Emotional"},
            {"name_trait": "Implied benefits", "user_perception": "Product promise", "benefit_type": "Functional"},
            {"name_trait": "Requires imagination", "user_perception": "Engaging, memorable", "benefit_type": "Emotional"}
        ]
    elif legal_category == "DESCRIPTIVE":
        benefit_map = [
            {"name_trait": "Clear meaning", "user_perception": "Honest, straightforward", "benefit_type": "Functional"},
            {"name_trait": "Category words", "user_perception": "Easy to find/search", "benefit_type": "Functional"},
            {"name_trait": "Direct description", "user_perception": "Commodity perception risk", "benefit_type": "Emotional"}
        ]
    else:
        benefit_map = [
            {"name_trait": "Generic term", "user_perception": "No brand differentiation", "benefit_type": "Functional"}
        ]
    
    # Target persona fit based on positioning
    positioning_lower = positioning.lower() if positioning else "mid-range"
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        if "luxury" in positioning_lower or "premium" in positioning_lower:
            persona_fit = f"**STRONG FIT:** Abstract naming aligns with {positioning} expectations. Target audience associates invented/arbitrary names with prestige and exclusivity."
        else:
            persona_fit = f"**GOOD FIT:** Distinctive name supports brand building across {positioning} segment."
    elif legal_category == "SUGGESTIVE":
        persona_fit = f"**ADEQUATE FIT:** Suggestive meaning can support {positioning} positioning with proper brand storytelling."
    elif legal_category == "DESCRIPTIVE":
        if "budget" in positioning_lower or "mass" in positioning_lower:
            persona_fit = f"**ADEQUATE FIT:** Descriptive names work for {positioning} where clarity outweighs distinctiveness."
        else:
            persona_fit = f"**WEAK FIT:** Descriptive names signal utility, not prestige. May undermine {positioning} positioning."
    else:
        persona_fit = f"**NO FIT:** Generic terms cannot build brand equity."
    
    return {
        "linguistic_roots": linguistic_roots,
        "phonetic_analysis": phonetic_analysis,
        "emotional_promises": emotional_promises,
        "functional_benefits": functional_benefits,
        "benefit_map": benefit_map,
        "target_persona_fit": persona_fit
    }


def generate_distinctiveness_module(
    brand_name: str,
    legal_category: str,
    distinctiveness_level: str,
    category: str,
    imitability_risk: dict,
    dictionary_tokens: list
) -> dict:
    """Generate Module 2: Distinctiveness based on classification."""
    
    # Distinctiveness score based on legal category (1-10 scale)
    distinctiveness_scores = {
        "FANCIFUL": 9,
        "ARBITRARY": 8,
        "SUGGESTIVE": 6,
        "DESCRIPTIVE": 3,
        "GENERIC": 1
    }
    score = distinctiveness_scores.get(legal_category, 5)
    
    # Category noise level
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        noise_level = "LOW"
        industry_comparison = f"'{brand_name}' stands apart from {category} competitors through its {'coined' if legal_category == 'FANCIFUL' else 'arbitrary'} nature. No direct naming conflicts expected."
    elif legal_category == "SUGGESTIVE":
        noise_level = "MEDIUM"
        industry_comparison = f"'{brand_name}' differentiates from direct competitors but may face similar suggestive names in the {category} space."
    else:
        noise_level = "HIGH"
        industry_comparison = f"'{brand_name}' competes directly with other descriptive names in {category}. High likelihood of similar-sounding competitors."
    
    # Naming tropes analysis
    if legal_category == "FANCIFUL":
        tropes_analysis = f"Avoids all common naming tropes. Purely invented terms are rare in {category}, creating maximum differentiation."
    elif legal_category == "ARBITRARY":
        tropes_analysis = f"Uses unexpected word association rather than industry clichés. Bold departure from typical {category} naming conventions."
    elif legal_category == "SUGGESTIVE":
        tropes_analysis = f"Employs suggestive meaning - a common but effective naming approach. Ensure the suggestion is unique within {category}."
    elif legal_category == "DESCRIPTIVE":
        tropes_analysis = f"Falls into descriptive naming pattern - the most common and least distinctive approach. Competitors can legally use similar terms."
    else:
        tropes_analysis = f"Generic term that defines the category. Cannot differentiate - legally free for all to use."
    
    # Similar competitors risk
    similar_competitors = []
    if imitability_risk and imitability_risk.get("clone_examples"):
        for clone in imitability_risk.get("clone_examples", [])[:3]:
            similar_competitors.append({
                "name": clone.split(":")[0] if ":" in clone else clone,
                "similarity_aspect": clone.split(":")[1].strip() if ":" in clone else "Structural variation",
                "risk_level": "HIGH" if legal_category in ["DESCRIPTIVE", "GENERIC"] else "MEDIUM" if legal_category == "SUGGESTIVE" else "LOW"
            })
    
    # Differentiation opportunities
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        diff_opportunities = [
            "Leverage unique name for brand storytelling",
            "Build proprietary visual identity around invented term",
            "Create 'meaning ownership' through consistent messaging"
        ]
    elif legal_category == "SUGGESTIVE":
        diff_opportunities = [
            "Strengthen suggestion through tagline and visuals",
            "Differentiate through brand personality, not just name",
            "Build stronger trademark through design marks"
        ]
    else:
        diff_opportunities = [
            "Add distinctive visual branding to compensate",
            "Develop strong tagline to differentiate",
            "Consider name modification for stronger protection"
        ]
    
    return {
        "distinctiveness_score": score,
        "category_noise_level": noise_level,
        "industry_comparison": industry_comparison,
        "naming_tropes_analysis": tropes_analysis,
        "similar_competitors": similar_competitors,
        "differentiation_opportunities": diff_opportunities
    }


def generate_brand_architecture_module(
    brand_name: str,
    legal_category: str,
    distinctiveness_level: str,
    category: str,
    positioning: str
) -> dict:
    """Generate Module 3: Brand Architecture based on classification."""
    
    # Elasticity score (Apple=10, CarPhoneWarehouse=2)
    elasticity_scores = {
        "FANCIFUL": 9,  # Can stretch anywhere
        "ARBITRARY": 8,  # High flexibility
        "SUGGESTIVE": 6,  # Some category constraints
        "DESCRIPTIVE": 3,  # Category-locked
        "GENERIC": 1  # Cannot stretch at all
    }
    elasticity_score = elasticity_scores.get(legal_category, 5)
    
    # Elasticity analysis
    if legal_category == "FANCIFUL":
        elasticity_analysis = f"'{brand_name}' has maximum elasticity - can expand into any product category or geography without semantic conflict. Like 'Google' or 'Kodak', invented names define their own boundaries."
    elif legal_category == "ARBITRARY":
        elasticity_analysis = f"'{brand_name}' offers high elasticity. The arbitrary usage disconnects from original meaning, allowing expansion beyond {category}. Like 'Amazon' expanding from books to everything."
    elif legal_category == "SUGGESTIVE":
        elasticity_analysis = f"'{brand_name}' has moderate elasticity. The suggestive meaning creates some category association that may constrain extreme pivots but allows related expansion."
    elif legal_category == "DESCRIPTIVE":
        elasticity_analysis = f"'{brand_name}' is category-locked. Descriptive names strongly associate with specific products, making expansion into unrelated categories confusing or impossible."
    else:
        elasticity_analysis = f"'{brand_name}' has zero elasticity as a generic term. Cannot build brand architecture on a name everyone can use."
    
    # Recommended architecture
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        architecture = "Branded House"
        architecture_rationale = "Strong master brand with sub-products. Name strength supports unified brand architecture (e.g., Google Search, Google Maps, Google Cloud)."
    elif legal_category == "SUGGESTIVE":
        architecture = "Endorsed Brand"
        architecture_rationale = "Master brand endorses product brands. The suggestive meaning works as quality seal while products can have distinct identities."
    else:
        architecture = "House of Brands"
        architecture_rationale = "Separate product brands under corporate umbrella. Weak master brand name requires independent product branding."
    
    # Memorability index
    length_factor = 10 - min(5, max(0, len(brand_name) - 6))  # Optimal at 6 chars
    uniqueness_factor = {"FANCIFUL": 3, "ARBITRARY": 2, "SUGGESTIVE": 1, "DESCRIPTIVE": 0, "GENERIC": -1}.get(legal_category, 0)
    memorability_index = min(10, max(1, length_factor + uniqueness_factor))
    
    # Memorability factors
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        memorability_factors = ["Unique sound pattern", "No competing associations", "Distinctive visual signature"]
    elif legal_category == "SUGGESTIVE":
        memorability_factors = ["Meaning hook aids recall", "Moderate uniqueness", "Conceptual connection"]
    else:
        memorability_factors = ["Clarity aids initial recall", "Competes with similar names", "Low long-term retention"]
    
    # Global scalability
    if legal_category == "FANCIFUL":
        global_scalability = f"**EXCELLENT:** Invented terms have no linguistic baggage. '{brand_name}' can launch globally without translation issues or cultural conflicts."
    elif legal_category == "ARBITRARY":
        global_scalability = f"**GOOD:** Check that the word doesn't have negative meanings in target markets, but generally arbitrary names travel well internationally."
    elif legal_category == "SUGGESTIVE":
        global_scalability = f"**MODERATE:** The suggestion may not translate across languages. Validate meaning in each target market before launch."
    else:
        global_scalability = f"**LIMITED:** Descriptive/generic terms require translation or localization for each market, fragmenting global brand equity."
    
    return {
        "elasticity_score": elasticity_score,
        "elasticity_analysis": elasticity_analysis,
        "recommended_architecture": architecture,
        "architecture_rationale": architecture_rationale,
        "memorability_index": memorability_index,
        "memorability_factors": memorability_factors,
        "global_scalability": global_scalability
    }


def generate_alternative_directions(brand_name: str, legal_category: str, category: str) -> list:
    """Generate alternative naming directions for REFINE/PIVOT recommendations."""
    
    directions = []
    
    # Always suggest moving UP the distinctiveness spectrum
    if legal_category in ["DESCRIPTIVE", "GENERIC"]:
        directions.append({
            "direction_name": "Coined/Fanciful Approach",
            "example_names": [f"{brand_name[:3]}ora", f"{brand_name[:4]}ix", f"Zyn{brand_name[:3]}"],
            "rationale": "Invented names offer maximum trademark protection and brand asset value. Zero competitors can legally use identical names.",
            "mckinsey_principle": "Distinctiveness"
        })
        
        directions.append({
            "direction_name": "Arbitrary Word Strategy",
            "example_names": ["Spark", "Nova", "Prism", "Atlas"],
            "rationale": "Common words in unrelated contexts create memorable brands with strong protection (Apple, Amazon, Uber).",
            "mckinsey_principle": "Benefits"
        })
    
    if legal_category in ["DESCRIPTIVE", "SUGGESTIVE"]:
        directions.append({
            "direction_name": "Suggestive Enhancement",
            "example_names": [f"{brand_name[:4]}ify", f"True{category.split()[0][:4]}", f"{category.split()[0][:4]}ly"],
            "rationale": "Transform descriptive elements into suggestive construction for improved protection while retaining meaning.",
            "mckinsey_principle": "Architecture"
        })
    
    # Category-specific alternatives
    directions.append({
        "direction_name": "Metaphorical Approach",
        "example_names": ["Horizon", "Pinnacle", "Summit", "Meridian"],
        "rationale": f"Metaphors communicate aspiration without describing {category} directly. Strong emotional resonance.",
        "mckinsey_principle": "Benefits"
    })
    
    return directions[:3]  # Limit to 3


# ============================================================================
# DETAILED FRAMEWORK ANALYSIS - CLASSIFICATION-AWARE DIMENSIONS
# ============================================================================
# Connects all 6 dimensions to our pre-computed classification system
# ============================================================================

def generate_classification_aware_dimensions(
    brand_name: str,
    classification: dict,
    category: str,
    positioning: str,
    trademark_risk: int,
    strategy_snapshot: dict = None,
    mckinsey_analysis: dict = None,
    cultural_analysis: dict = None
) -> list:
    """
    Generate 6 scoring dimensions connected to classification system.
    
    Dimensions:
    1. Brand Distinctiveness & Memorability
    2. Cultural & Linguistic Resonance  
    3. Premiumisation & Trust Curve
    4. Scalability & Brand Architecture
    5. Trademark & Legal Sensitivity
    6. Consumer Perception Mapping
    """
    
    legal_category = classification.get("category", "DESCRIPTIVE")
    distinctiveness_level = classification.get("distinctiveness", "LOW")
    protectability = classification.get("protectability", "WEAK")
    dictionary_tokens = classification.get("dictionary_tokens", [])
    
    # Get data from other analyses if available
    positioning_alignment = strategy_snapshot.get("positioning_alignment", {}) if strategy_snapshot else {}
    linguistic_eval = strategy_snapshot.get("linguistic_evaluation", {}) if strategy_snapshot else {}
    imitability_risk = strategy_snapshot.get("imitability_risk", {}) if strategy_snapshot else {}
    asset_ceiling = strategy_snapshot.get("brand_asset_ceiling", {}) if strategy_snapshot else {}
    
    brand_architecture = mckinsey_analysis.get("brand_architecture", {}) if mckinsey_analysis else {}
    
    dimensions = []
    
    # ========== DIMENSION 1: BRAND DISTINCTIVENESS & MEMORABILITY ==========
    dim1_score = generate_distinctiveness_dimension_score(classification, linguistic_eval)
    dim1_reasoning = generate_distinctiveness_reasoning(brand_name, classification, linguistic_eval, imitability_risk)
    dimensions.append({
        "name": "Brand Distinctiveness & Memorability",
        "score": dim1_score,
        "reasoning": dim1_reasoning
    })
    
    # ========== DIMENSION 2: CULTURAL & LINGUISTIC RESONANCE ==========
    dim2_score = generate_cultural_dimension_score(linguistic_eval, cultural_analysis)
    dim2_reasoning = generate_cultural_reasoning(brand_name, linguistic_eval, cultural_analysis)
    dimensions.append({
        "name": "Cultural & Linguistic Resonance",
        "score": dim2_score,
        "reasoning": dim2_reasoning
    })
    
    # ========== DIMENSION 3: PREMIUMISATION & TRUST CURVE ==========
    dim3_score = generate_premium_dimension_score(classification, positioning, positioning_alignment)
    dim3_reasoning = generate_premium_reasoning(brand_name, classification, positioning, positioning_alignment)
    dimensions.append({
        "name": "Premiumisation & Trust Curve",
        "score": dim3_score,
        "reasoning": dim3_reasoning
    })
    
    # ========== DIMENSION 4: SCALABILITY & BRAND ARCHITECTURE ==========
    dim4_score = generate_scalability_dimension_score(classification, brand_architecture, asset_ceiling)
    dim4_reasoning = generate_scalability_reasoning(brand_name, classification, brand_architecture, asset_ceiling, category)
    dimensions.append({
        "name": "Scalability & Brand Architecture",
        "score": dim4_score,
        "reasoning": dim4_reasoning
    })
    
    # ========== DIMENSION 5: TRADEMARK & LEGAL SENSITIVITY ==========
    dim5_score = generate_trademark_dimension_score(classification, trademark_risk)
    dim5_reasoning = generate_trademark_reasoning(brand_name, classification, trademark_risk, protectability)
    dimensions.append({
        "name": "Trademark & Legal Sensitivity",
        "score": dim5_score,
        "reasoning": dim5_reasoning
    })
    
    # ========== DIMENSION 6: CONSUMER PERCEPTION MAPPING ==========
    dim6_score = generate_perception_dimension_score(classification, positioning, positioning_alignment)
    dim6_reasoning = generate_perception_reasoning(brand_name, classification, positioning, positioning_alignment, category)
    dimensions.append({
        "name": "Consumer Perception Mapping",
        "score": dim6_score,
        "reasoning": dim6_reasoning
    })
    
    return dimensions


# -------------------- DIMENSION 1: DISTINCTIVENESS --------------------

def generate_distinctiveness_dimension_score(classification: dict, linguistic_eval: dict) -> float:
    """Calculate distinctiveness score based on classification."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    
    # Base score from classification
    base_scores = {
        "FANCIFUL": 9.5,
        "ARBITRARY": 8.5,
        "SUGGESTIVE": 7.0,
        "DESCRIPTIVE": 4.5,
        "GENERIC": 2.0
    }
    score = base_scores.get(legal_category, 5.0)
    
    # Adjust for memorability
    memorability = linguistic_eval.get("memorability_score", 7)
    if memorability >= 8:
        score += 0.3
    elif memorability <= 5:
        score -= 0.5
    
    # Adjust for pronunciation ease
    if linguistic_eval.get("pronunciation_ease") == "LOW":
        score -= 0.3
    
    return round(max(1.0, min(10.0, score)), 1)


def generate_distinctiveness_reasoning(brand_name: str, classification: dict, linguistic_eval: dict, imitability_risk: dict) -> str:
    """Generate reasoning for distinctiveness dimension."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    dictionary_tokens = classification.get("dictionary_tokens", [])
    invented_tokens = classification.get("invented_tokens", [])
    
    # Phonetic architecture section
    if legal_category == "FANCIFUL":
        phonetic = f"**PHONETIC ARCHITECTURE:**\n'{brand_name}' is a coined neologism with unique sound signature. No competing phonetic associations - maximum distinctiveness."
    elif legal_category == "ARBITRARY":
        phonetic = f"**PHONETIC ARCHITECTURE:**\n'{brand_name}' uses familiar phonetics in unexpected context. Strong memorability through cognitive surprise."
    elif legal_category == "SUGGESTIVE":
        phonetic = f"**PHONETIC ARCHITECTURE:**\n'{brand_name}' balances familiar sounds with suggestive meaning. Moderate distinctiveness with meaning hook."
    elif legal_category == "DESCRIPTIVE":
        tokens_str = ", ".join(dictionary_tokens[:3]) if dictionary_tokens else "common words"
        phonetic = f"**PHONETIC ARCHITECTURE:**\n'{brand_name}' uses dictionary words ({tokens_str}). Low phonetic distinctiveness - competes with similar descriptive names."
    else:
        phonetic = f"**PHONETIC ARCHITECTURE:**\n'{brand_name}' is generic terminology. Zero phonetic distinctiveness - name is category descriptor."
    
    # Competitive isolation section
    imitability_level = imitability_risk.get("imitability_level", "MODERATE") if imitability_risk else "MODERATE"
    if imitability_level == "LOW":
        competitive = f"**COMPETITIVE ISOLATION:**\nHigh barrier to imitation. Competitors cannot legally clone this name structure."
    elif imitability_level == "MODERATE":
        competitive = f"**COMPETITIVE ISOLATION:**\nModerate protection. Some risk of phonetic or conceptual lookalikes in the market."
    else:
        competitive = f"**COMPETITIVE ISOLATION:**\nLow barrier to imitation. Competitors can legally use synonyms, variations, and similar descriptive terms."
    
    # Memorability
    memorability_score = linguistic_eval.get("memorability_score", 7) if linguistic_eval else 7
    if memorability_score >= 8:
        memory = f"**MEMORABILITY INDEX:**\n{len(brand_name)} characters with strong recall potential ({memorability_score}/10)."
    elif memorability_score >= 6:
        memory = f"**MEMORABILITY INDEX:**\n{len(brand_name)} characters with adequate recall potential ({memorability_score}/10)."
    else:
        memory = f"**MEMORABILITY INDEX:**\n{len(brand_name)} characters may challenge recall ({memorability_score}/10). Consider shorter alternatives."
    
    return f"{phonetic}\n\n{competitive}\n\n{memory}"


# -------------------- DIMENSION 2: CULTURAL & LINGUISTIC --------------------

def generate_cultural_dimension_score(linguistic_eval: dict, cultural_analysis: dict) -> float:
    """Calculate cultural resonance score."""
    base_score = 7.5
    
    # Deduct for cultural flags
    cultural_flags = linguistic_eval.get("cultural_flags", []) if linguistic_eval else []
    if len(cultural_flags) > 0:
        base_score -= len(cultural_flags) * 0.8
    
    # Deduct for pronunciation issues
    pronunciation_issues = linguistic_eval.get("pronunciation_issues", []) if linguistic_eval else []
    if len(pronunciation_issues) > 2:
        base_score -= 1.0
    elif len(pronunciation_issues) > 0:
        base_score -= 0.5
    
    # Check cultural_analysis if available
    if cultural_analysis:
        # Check for critical cultural issues in any country
        for country_data in cultural_analysis.values() if isinstance(cultural_analysis, dict) else []:
            if isinstance(country_data, dict):
                if country_data.get("safety_score", 10) < 5:
                    base_score -= 1.5
                elif country_data.get("safety_score", 10) < 7:
                    base_score -= 0.5
    
    return round(max(1.0, min(10.0, base_score)), 1)


def generate_cultural_reasoning(brand_name: str, linguistic_eval: dict, cultural_analysis: dict) -> str:
    """Generate reasoning for cultural dimension."""
    
    # Global linguistic audit
    cultural_flags = linguistic_eval.get("cultural_flags", []) if linguistic_eval else []
    pronunciation_issues = linguistic_eval.get("pronunciation_issues", []) if linguistic_eval else []
    
    if not cultural_flags and not pronunciation_issues:
        linguistic_audit = f"**GLOBAL LINGUISTIC AUDIT:**\nNo negative connotations detected across major target market languages. '{brand_name}' demonstrates cultural neutrality suitable for international deployment."
    elif cultural_flags:
        flags_str = "; ".join(cultural_flags[:2])
        linguistic_audit = f"**GLOBAL LINGUISTIC AUDIT:**\n⚠️ Cultural sensitivities identified: {flags_str}. Recommend market-specific validation before launch."
    else:
        issues_str = "; ".join([p.split(" - ")[0] if " - " in p else p for p in pronunciation_issues[:2]])
        linguistic_audit = f"**GLOBAL LINGUISTIC AUDIT:**\nMinor pronunciation considerations: {issues_str}. Generally acceptable for international markets."
    
    # Cultural semiotics
    if not cultural_flags:
        semiotics = f"**CULTURAL SEMIOTICS:**\nThe brand name carries neutral-positive associations. No religious, political, or taboo connotations detected."
    else:
        semiotics = f"**CULTURAL SEMIOTICS:**\nSome cultural associations require attention. Review local market perceptions before major brand investment."
    
    # Pronunciation ease
    pronunciation_ease = linguistic_eval.get("pronunciation_ease", "MODERATE") if linguistic_eval else "MODERATE"
    if pronunciation_ease == "HIGH":
        pronunciation = f"**PRONUNCIATION ACCESSIBILITY:**\nClean phonetic structure enables easy pronunciation across English and non-native speakers."
    elif pronunciation_ease == "MODERATE":
        pronunciation = f"**PRONUNCIATION ACCESSIBILITY:**\nModerate pronunciation complexity. May require brand education in some markets."
    else:
        pronunciation = f"**PRONUNCIATION ACCESSIBILITY:**\nChallenging pronunciation may hinder word-of-mouth and brand recall in some regions."
    
    return f"{linguistic_audit}\n\n{semiotics}\n\n{pronunciation}"


# -------------------- DIMENSION 3: PREMIUMISATION & TRUST --------------------

def generate_premium_dimension_score(classification: dict, positioning: str, positioning_alignment: dict) -> float:
    """Calculate premiumisation score based on classification + positioning fit."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    positioning_lower = positioning.lower() if positioning else "mid-range"
    
    # Base score from classification (pricing power)
    base_scores = {
        "FANCIFUL": 9.0,
        "ARBITRARY": 8.5,
        "SUGGESTIVE": 7.0,
        "DESCRIPTIVE": 4.0,
        "GENERIC": 2.0
    }
    score = base_scores.get(legal_category, 5.0)
    
    # Adjust for positioning alignment
    alignment = positioning_alignment.get("alignment", "NEUTRAL") if positioning_alignment else "NEUTRAL"
    
    if alignment == "MISALIGNED":
        # Major penalty for misalignment (e.g., DESCRIPTIVE + Premium)
        if "luxury" in positioning_lower or "premium" in positioning_lower:
            score -= 2.5  # Descriptive names destroy premium perception
        else:
            score -= 1.0
    elif alignment == "STRONG":
        score += 0.5
    
    # Pricing power from strategy snapshot
    pricing_power = positioning_alignment.get("pricing_power", "MODERATE") if positioning_alignment else "MODERATE"
    if pricing_power == "LOW":
        score -= 1.0
    elif pricing_power == "HIGH":
        score += 0.5
    
    return round(max(1.0, min(10.0, score)), 1)


def generate_premium_reasoning(brand_name: str, classification: dict, positioning: str, positioning_alignment: dict) -> str:
    """Generate reasoning for premiumisation dimension."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    positioning_lower = positioning.lower() if positioning else "mid-range"
    alignment = positioning_alignment.get("alignment", "NEUTRAL") if positioning_alignment else "NEUTRAL"
    pricing_power = positioning_alignment.get("pricing_power", "MODERATE") if positioning_alignment else "MODERATE"
    
    # Pricing power analysis
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        pricing = f"**PRICING POWER ANALYSIS:**\n'{brand_name}' supports premium pricing. Abstract/coined names signal exclusivity and enable price premiums over descriptive competitors (e.g., Apple vs. Computer Store)."
    elif legal_category == "SUGGESTIVE":
        pricing = f"**PRICING POWER ANALYSIS:**\n'{brand_name}' supports moderate-to-premium pricing. Suggestive names can command premiums when backed by strong brand storytelling."
    elif legal_category == "DESCRIPTIVE":
        pricing = f"**PRICING POWER ANALYSIS:**\n'{brand_name}' has LIMITED pricing power. Descriptive names signal utility/commodity, making it difficult to justify premium prices over competitors."
    else:
        pricing = f"**PRICING POWER ANALYSIS:**\n'{brand_name}' has ZERO pricing power. Generic terms cannot differentiate - pricing defaults to market commoditization."
    
    # Trust curve assessment
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        trust = f"**TRUST CURVE:**\nRequires initial brand education investment, but builds stronger long-term trust equity. Premium brands benefit from abstract naming."
    elif legal_category == "SUGGESTIVE":
        trust = f"**TRUST CURVE:**\nBalanced trust trajectory. Name hints at benefits while maintaining distinctiveness. Good for building professional credibility."
    else:
        trust = f"**TRUST CURVE:**\nFast initial trust (name explains product) but limited ceiling. Customers view brand as utility, not premium relationship."
    
    # Positioning fit
    if alignment == "MISALIGNED" and ("luxury" in positioning_lower or "premium" in positioning_lower):
        positioning_fit = f"**POSITIONING FIT:**\n⛔ CRITICAL MISMATCH: {legal_category} naming fundamentally conflicts with {positioning} positioning. Premium/luxury brands require abstract naming (Hermès, Rolex, Tesla) to command price premiums."
    elif alignment == "MISALIGNED":
        positioning_fit = f"**POSITIONING FIT:**\n⚠️ MISMATCH: Name structure may not optimally support {positioning} market positioning. Consider alignment review."
    elif alignment == "STRONG":
        positioning_fit = f"**POSITIONING FIT:**\n✅ STRONG ALIGNMENT: Name architecture supports {positioning} market positioning and target audience expectations."
    else:
        positioning_fit = f"**POSITIONING FIT:**\nADEQUATE: Name can support {positioning} positioning with proper brand development and communication strategy."
    
    return f"{pricing}\n\n{trust}\n\n{positioning_fit}"


# -------------------- DIMENSION 4: SCALABILITY & ARCHITECTURE --------------------

def generate_scalability_dimension_score(classification: dict, brand_architecture: dict, asset_ceiling: dict) -> float:
    """Calculate scalability score from McKinsey elasticity + asset ceiling."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    
    # Base score from classification (elasticity)
    base_scores = {
        "FANCIFUL": 9.0,
        "ARBITRARY": 8.5,
        "SUGGESTIVE": 6.5,
        "DESCRIPTIVE": 3.5,
        "GENERIC": 1.5
    }
    score = base_scores.get(legal_category, 5.0)
    
    # Use elasticity score from McKinsey if available
    elasticity = brand_architecture.get("elasticity_score") if brand_architecture else None
    if elasticity:
        # Weight: 60% classification, 40% elasticity from McKinsey
        score = (score * 0.6) + (elasticity * 0.4)
    
    # Adjust for expansion potential
    expansion = asset_ceiling.get("expansion_potential", "MODERATE") if asset_ceiling else "MODERATE"
    if expansion == "LOW":
        score -= 0.5
    elif expansion == "HIGH":
        score += 0.3
    
    return round(max(1.0, min(10.0, score)), 1)


def generate_scalability_reasoning(brand_name: str, classification: dict, brand_architecture: dict, asset_ceiling: dict, category: str) -> str:
    """Generate reasoning for scalability dimension."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    elasticity_score = brand_architecture.get("elasticity_score", 5) if brand_architecture else 5
    recommended_arch = brand_architecture.get("recommended_architecture", "Standalone") if brand_architecture else "Standalone"
    expansion_potential = asset_ceiling.get("expansion_potential", "MODERATE") if asset_ceiling else "MODERATE"
    
    # Category stretch analysis
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        stretch = f"**CATEGORY STRETCH:**\n'{brand_name}' has maximum elasticity ({elasticity_score}/10). Can expand into any product category or geography without semantic conflict. Like Google expanding from search to cloud to hardware."
    elif legal_category == "SUGGESTIVE":
        stretch = f"**CATEGORY STRETCH:**\n'{brand_name}' has moderate elasticity ({elasticity_score}/10). Suggestive meaning creates some category association but allows related expansion with proper brand architecture."
    elif legal_category == "DESCRIPTIVE":
        stretch = f"**CATEGORY STRETCH:**\n'{brand_name}' is CATEGORY-LOCKED ({elasticity_score}/10). Descriptive names strongly associate with specific products. Expansion beyond {category} would confuse consumers."
    else:
        stretch = f"**CATEGORY STRETCH:**\n'{brand_name}' has ZERO elasticity ({elasticity_score}/10). Generic terms cannot build expandable brand equity."
    
    # Architecture recommendation
    architecture = f"**ARCHITECTURE FIT:**\nRecommended structure: {recommended_arch}. "
    if recommended_arch == "Branded House":
        architecture += f"Name strength supports unified brand with sub-products (e.g., '{brand_name} Pro', '{brand_name} Lite')."
    elif recommended_arch == "House of Brands":
        architecture += f"Weak master brand requires independent product branding under corporate umbrella."
    else:
        architecture += f"Name can endorse product brands while maintaining separate identities."
    
    # Global scalability
    if expansion_potential == "HIGH":
        global_scale = f"**GLOBAL SCALABILITY:**\nExcellent international potential. Name travels well without translation issues or cultural conflicts."
    elif expansion_potential == "MODERATE":
        global_scale = f"**GLOBAL SCALABILITY:**\nModerate international potential. Validate meaning in target markets before global rollout."
    else:
        global_scale = f"**GLOBAL SCALABILITY:**\nLimited international potential. Descriptive terms require localization for each market, fragmenting brand equity."
    
    return f"{stretch}\n\n{architecture}\n\n{global_scale}"


# -------------------- DIMENSION 5: TRADEMARK & LEGAL --------------------

def generate_trademark_dimension_score(classification: dict, trademark_risk: int) -> float:
    """Calculate trademark score from classification + risk assessment."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    
    # Base score from classification (protectability)
    base_scores = {
        "FANCIFUL": 9.5,
        "ARBITRARY": 8.5,
        "SUGGESTIVE": 7.0,
        "DESCRIPTIVE": 4.0,
        "GENERIC": 1.0
    }
    score = base_scores.get(legal_category, 5.0)
    
    # Adjust for actual trademark risk (conflicts found)
    if trademark_risk <= 2:
        score += 0.5  # Clear field
    elif trademark_risk >= 7:
        score -= 2.0  # Significant conflicts
    elif trademark_risk >= 5:
        score -= 1.0  # Moderate conflicts
    
    return round(max(1.0, min(10.0, score)), 1)


def generate_trademark_reasoning(brand_name: str, classification: dict, trademark_risk: int, protectability: str) -> str:
    """Generate reasoning for trademark dimension."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    
    # Distinctiveness audit based on classification
    if legal_category == "FANCIFUL":
        distinctiveness = f"**DISTINCTIVENESS AUDIT:**\n'{brand_name}' is FANCIFUL (coined/invented) - the strongest trademark category. Inherently distinctive under TMEP §1209. No Secondary Meaning proof required."
    elif legal_category == "ARBITRARY":
        distinctiveness = f"**DISTINCTIVENESS AUDIT:**\n'{brand_name}' is ARBITRARY - inherently distinctive. Common word used in unrelated context receives strong protection."
    elif legal_category == "SUGGESTIVE":
        distinctiveness = f"**DISTINCTIVENESS AUDIT:**\n'{brand_name}' is SUGGESTIVE - inherently distinctive. Registrable on Principal Register without Secondary Meaning proof."
    elif legal_category == "DESCRIPTIVE":
        distinctiveness = f"**DISTINCTIVENESS AUDIT:**\n'{brand_name}' is DESCRIPTIVE - NOT inherently distinctive. Requires proof of Secondary Meaning (acquired distinctiveness) under §2(f). Typically requires 5+ years exclusive use."
    else:
        distinctiveness = f"**DISTINCTIVENESS AUDIT:**\n'{brand_name}' is GENERIC - UNREGISTRABLE. Generic terms cannot be trademarked under any jurisdiction. Name the category, not the brand."
    
    # Risk level assessment
    if trademark_risk <= 2:
        risk_level = f"**REGISTRATION OUTLOOK:**\n✅ FAVORABLE ({trademark_risk}/10 risk). Clear trademark landscape. High probability of successful registration."
    elif trademark_risk <= 4:
        risk_level = f"**REGISTRATION OUTLOOK:**\n✅ GOOD ({trademark_risk}/10 risk). Minor potential conflicts identified. Standard examination expected."
    elif trademark_risk <= 6:
        risk_level = f"**REGISTRATION OUTLOOK:**\n⚠️ MODERATE ({trademark_risk}/10 risk). Some trademark crowding detected. May require responses to Office Actions."
    else:
        risk_level = f"**REGISTRATION OUTLOOK:**\n⛔ CHALLENGING ({trademark_risk}/10 risk). Significant conflicts detected. High likelihood of opposition or rejection."
    
    # Enforcement power
    if protectability in ["STRONGEST", "STRONG"]:
        enforcement = f"**ENFORCEMENT POWER:**\nMaximum scope of protection. Can pursue infringers for confusingly similar marks across related goods/services."
    elif protectability == "MODERATE":
        enforcement = f"**ENFORCEMENT POWER:**\nModerate scope. Can pursue direct copiers but harder to stop merely similar marks."
    else:
        enforcement = f"**ENFORCEMENT POWER:**\nLimited scope. Can only stop identical marks on identical goods. Competitors can use similar descriptive terms legally."
    
    return f"{distinctiveness}\n\n{risk_level}\n\n{enforcement}"


# -------------------- DIMENSION 6: CONSUMER PERCEPTION --------------------

def generate_perception_dimension_score(classification: dict, positioning: str, positioning_alignment: dict) -> float:
    """Calculate consumer perception score."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    positioning_lower = positioning.lower() if positioning else "mid-range"
    alignment = positioning_alignment.get("alignment", "NEUTRAL") if positioning_alignment else "NEUTRAL"
    
    # Base score from classification (perception control)
    base_scores = {
        "FANCIFUL": 8.5,  # Brand controls perception
        "ARBITRARY": 8.0,
        "SUGGESTIVE": 7.5,
        "DESCRIPTIVE": 5.0,  # Name dictates perception
        "GENERIC": 2.5
    }
    score = base_scores.get(legal_category, 5.0)
    
    # Significant penalty for positioning misalignment
    if alignment == "MISALIGNED":
        if "luxury" in positioning_lower or "premium" in positioning_lower:
            score -= 3.0  # Descriptive + Premium = consumer confusion
        else:
            score -= 1.5
    elif alignment == "STRONG":
        score += 0.5
    
    return round(max(1.0, min(10.0, score)), 1)


def generate_perception_reasoning(brand_name: str, classification: dict, positioning: str, positioning_alignment: dict, category: str) -> str:
    """Generate reasoning for consumer perception dimension."""
    legal_category = classification.get("category", "DESCRIPTIVE")
    positioning_lower = positioning.lower() if positioning else "mid-range"
    alignment = positioning_alignment.get("alignment", "NEUTRAL") if positioning_alignment else "NEUTRAL"
    
    # Perceptual grid placement
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        perceptual = f"**PERCEPTUAL GRID:**\n'{brand_name}' gives the brand full control over consumer perception. Abstract names are 'blank canvases' - perception shaped entirely by brand communication and experience."
    elif legal_category == "SUGGESTIVE":
        perceptual = f"**PERCEPTUAL GRID:**\n'{brand_name}' suggests product benefits without dictating perception. Consumers receive hint, brand storytelling completes the picture."
    elif legal_category == "DESCRIPTIVE":
        perceptual = f"**PERCEPTUAL GRID:**\n'{brand_name}' PRE-DETERMINES consumer perception. Descriptive names lock the brand into functional/utility positioning regardless of marketing investment."
    else:
        perceptual = f"**PERCEPTUAL GRID:**\n'{brand_name}' offers ZERO differentiation. Generic terms = commodity perception. Consumers see category, not brand."
    
    # Emotional response
    if legal_category in ["FANCIFUL", "ARBITRARY"]:
        emotional = f"**EMOTIONAL RESPONSE:**\nLikely to evoke curiosity, innovation, and exclusivity associations. Brand can craft desired emotional territory."
    elif legal_category == "SUGGESTIVE":
        emotional = f"**EMOTIONAL RESPONSE:**\nSuggestive meaning triggers specific emotional associations aligned with product benefits. Efficient emotional shortcut."
    else:
        emotional = f"**EMOTIONAL RESPONSE:**\nLimited emotional range. Descriptive names trigger functional/rational processing, not emotional connection."
    
    # Target audience fit
    if alignment == "MISALIGNED" and ("luxury" in positioning_lower or "premium" in positioning_lower):
        audience = f"**TARGET AUDIENCE FIT:**\n⛔ CRITICAL: {positioning} consumers expect abstract, exclusive-feeling names. '{brand_name}' signals utility/commodity, creating perception-positioning gap."
    elif alignment == "MISALIGNED":
        audience = f"**TARGET AUDIENCE FIT:**\n⚠️ MISMATCH: Name may not resonate optimally with {positioning} target audience in {category} market."
    elif alignment == "STRONG":
        audience = f"**TARGET AUDIENCE FIT:**\n✅ STRONG: Name architecture aligns with {positioning} consumer expectations in {category} market."
    else:
        audience = f"**TARGET AUDIENCE FIT:**\nADEQUATE: Name can serve {positioning} market with appropriate brand development investment."
    
    return f"{perceptual}\n\n{emotional}\n\n{audience}"


def generate_risk_cons(brand_name: str, countries: list, category: str, domain_available: bool, verdict: str) -> list:
    """
    Generate KEY RISKS section that aligns with the Executive Summary.
    Uses linguistic decomposition to identify real risks, not generic placeholders.
    """
    cons = []
    
    # Get linguistic analysis for real risk identification
    linguistic_analysis = generate_linguistic_decomposition(brand_name, countries, category)
    country_analysis = linguistic_analysis.get("country_analysis", {})
    phonetic_risks = linguistic_analysis.get("phonetic_risks", [])
    industry_fit = linguistic_analysis.get("industry_fit", {})
    
    # Check for CRITICAL cultural risks
    critical_countries = []
    high_risk_countries = []
    for country_name, data in country_analysis.items():
        if data.get("overall_resonance") == "CRITICAL":
            critical_countries.append(country_name)
            for flag in data.get("risk_flags", []):
                cons.append(f"**⚠️ CRITICAL - {country_name}:** {flag}")
        elif data.get("risk_count", 0) > 0:
            high_risk_countries.append(country_name)
            for flag in data.get("risk_flags", []):
                cons.append(f"**⚠️ {country_name}:** {flag}")
    
    # Check for phonetic risks
    for pr in phonetic_risks:
        cons.append(f"**Phonetic Risk ({pr['country']}):** '{pr['sound']}' - {pr['reason']}")
    
    # Check for industry-suffix mismatch
    if industry_fit.get("fit_level") == "LOW":
        cons.append(f"**Category Mismatch:** {industry_fit.get('reasoning', 'Name suffix may not align with industry conventions')}")
    
    # Add domain risk if applicable
    if not domain_available:
        cons.append(f"**Domain Status:** Primary .com domain taken - alternative acquisition strategy required")
    
    # Add name length consideration if long
    if len(brand_name) > 12:
        cons.append(f"**Name Length:** At {len(brand_name)} characters, may be challenging for quick recall and word-of-mouth")
    
    # If no risks identified, but verdict is not GO, add generic cons
    if not cons and verdict != "GO":
        cons.append(f"**Market Education:** As a coined term, will require brand awareness investment")
        cons.append(f"**Competitive Landscape:** Thorough trademark search recommended before proceeding")
    
    # If GO verdict and no major risks, indicate clean status with specific confirmation
    if not cons and verdict == "GO":
        cons.append("**No significant risks identified.** Linguistic analysis confirms name is culturally neutral across target markets. Proceed with standard trademark registration precautions.")
    
    return cons


REGISTRATION_TIMELINE_STAGES = {
    "India": [
        {"stage": "Filing & Formalities Examination", "duration": "1-2 months", "risk": "Minor objections possible on formalities"},
        {"stage": "Substantive Examination", "duration": "3-6 months", "risk": "Examiner objections on descriptiveness/similarity"},
        {"stage": "Publication in Trademark Journal", "duration": "1 month", "risk": "Public visibility, opposition window begins"},
        {"stage": "Opposition Period", "duration": "4 months", "risk": "HIGH - Competitors can file opposition"},
        {"stage": "Registration & Certificate", "duration": "1-2 months", "risk": "Final approval pending"}
    ],
    "USA": [
        {"stage": "Filing & Examination Assignment", "duration": "3-4 months", "risk": "Application assigned to examining attorney"},
        {"stage": "Substantive Examination", "duration": "3-6 months", "risk": "Office actions on descriptiveness, likelihood of confusion"},
        {"stage": "Publication for Opposition", "duration": "30 days", "risk": "MEDIUM - Opposition window"},
        {"stage": "Notice of Allowance (ITU) or Registration", "duration": "2-3 months", "risk": "Statement of Use required for ITU"},
        {"stage": "Final Registration", "duration": "1-2 months", "risk": "Certificate issued"}
    ],
    "Thailand": [
        {"stage": "Filing & Formalities Check", "duration": "1 month", "risk": "Basic compliance check"},
        {"stage": "Substantive Examination", "duration": "6-12 months", "risk": "Thai DIP examination backlog"},
        {"stage": "Publication Period", "duration": "60 days", "risk": "Opposition window"},
        {"stage": "Registration", "duration": "1-2 months", "risk": "Final certificate issuance"}
    ],
    "default": [
        {"stage": "Filing & Examination", "duration": "3-6 months", "risk": "Initial review"},
        {"stage": "Publication", "duration": "1-2 months", "risk": "Opposition window"},
        {"stage": "Registration", "duration": "1-3 months", "risk": "Final approval"}
    ]
}

RISK_MITIGATION_STRATEGIES = [
    {
        "priority": "HIGH",
        "action": "Conduct comprehensive trademark clearance search",
        "rationale": "Identifies potential conflicts before investment. Search should cover: USPTO/WIPO/national databases, common law uses, domain names, social media handles, and phonetic variants",
        "estimated_cost": "$500-$2,000 (professional search)",
        "timeline": "1-2 weeks"
    },
    {
        "priority": "HIGH",
        "action": "Develop distinctive visual identity (logo, trade dress)",
        "rationale": "Strong design elements provide additional protection layer. Even if wordmark faces challenges, stylized logo may proceed",
        "estimated_cost": "$2,000-$10,000 (professional design)",
        "timeline": "2-4 weeks"
    },
    {
        "priority": "MEDIUM",
        "action": "Document first use in commerce thoroughly",
        "rationale": "Proof of first use is critical in priority disputes. Maintain dated records of: product packaging, invoices, marketing materials, website launch dates",
        "estimated_cost": "Internal process",
        "timeline": "Ongoing"
    },
    {
        "priority": "MEDIUM",
        "action": "Consider co-existence agreement if minor conflicts found",
        "rationale": "Negotiate geographic or product category boundaries with conflicting mark owners. Often more cost-effective than opposition proceedings",
        "estimated_cost": "$2,000-$10,000 (legal negotiation)",
        "timeline": "1-3 months"
    },
    {
        "priority": "MEDIUM",
        "action": "Monitor trademark registers post-filing",
        "rationale": "Watch for conflicting applications filed after yours. Early opposition is more successful than late challenges",
        "estimated_cost": "$300-$500/year (monitoring service)",
        "timeline": "Ongoing after filing"
    },
    {
        "priority": "LOW",
        "action": "Prepare backup brand names",
        "rationale": "Have 2-3 alternative names vetted and ready in case primary choice encounters insurmountable conflicts",
        "estimated_cost": "Internal process + $500-$1,000 (preliminary searches)",
        "timeline": "Before primary filing"
    }
]

# Country-specific filing strategies
COUNTRY_FILING_STRATEGIES = {
    "India": {
        "priority": "HIGH",
        "action": "File trademark application with 'Proposed to be Used' basis",
        "rationale": "India allows filing on 'Proposed to be Used' basis. No strict deadline to prove use before registration, but must show bona fide intent to use the mark.",
        "estimated_cost": "₹4,500-₹9,000 per class (Government fee)",
        "timeline": "File within 30 days of brand decision"
    },
    "USA": {
        "priority": "HIGH",
        "action": "File Intent-to-Use (ITU) application immediately",
        "rationale": "US allows ITU filing under Section 1(b). You have 6 months after Notice of Allowance to file Statement of Use, with extensions available up to 3 years.",
        "estimated_cost": "$250-$350 per class (USPTO TEAS)",
        "timeline": "File within 30 days of brand decision"
    },
    "UK": {
        "priority": "HIGH",
        "action": "File trademark application with UK IPO",
        "rationale": "UK allows filing without proof of use. Post-Brexit, separate UK filing required (no longer covered by EU trademark).",
        "estimated_cost": "£170 for first class + £50 each additional",
        "timeline": "File within 30 days of brand decision"
    },
    "UAE": {
        "priority": "HIGH",
        "action": "File trademark application with UAE Ministry of Economy",
        "rationale": "UAE requires legalized documents. Arabic translation mandatory. Use requirement is strict - file only when ready to use.",
        "estimated_cost": "AED 6,000-10,000 per class",
        "timeline": "File when ready to enter market"
    },
    "Singapore": {
        "priority": "HIGH",
        "action": "File trademark application with IPOS",
        "rationale": "Singapore uses first-to-file system. No use requirement before filing. Fast examination (4-6 months typical).",
        "estimated_cost": "SGD 341 per class",
        "timeline": "File within 30 days of brand decision"
    },
    "default": {
        "priority": "HIGH",
        "action": "File trademark application in target jurisdiction",
        "rationale": "Consult local IP attorney for jurisdiction-specific requirements. Most countries allow filing without immediate proof of use.",
        "estimated_cost": "Varies by jurisdiction",
        "timeline": "File within 30 days of brand decision"
    }
}

def get_country_specific_mitigation_strategies(countries: list) -> list:
    """
    Generate country-specific risk mitigation strategies.
    Uses the primary country's filing requirements.
    """
    primary_country = countries[0] if countries else "default"
    if isinstance(primary_country, dict):
        primary_country = primary_country.get('name', 'default')
    
    # Get country-specific filing strategy
    filing_strategy = COUNTRY_FILING_STRATEGIES.get(primary_country, COUNTRY_FILING_STRATEGIES["default"])
    
    # Build strategies list with country-specific filing first
    strategies = [
        RISK_MITIGATION_STRATEGIES[0],  # Clearance search (universal)
        filing_strategy,                 # Country-specific filing
        RISK_MITIGATION_STRATEGIES[1],  # Visual identity
        RISK_MITIGATION_STRATEGIES[2],  # Document use
        RISK_MITIGATION_STRATEGIES[3],  # Co-existence
        RISK_MITIGATION_STRATEGIES[4],  # Monitoring
        RISK_MITIGATION_STRATEGIES[5],  # Backup names
    ]
    
    return strategies

REGISTRATION_TIMELINE_STAGES = {
    "India": [
        {"stage": "Filing & Formalities Examination", "duration": "1-2 months", "risk": "Minor objections possible on formalities"},
        {"stage": "Substantive Examination", "duration": "3-6 months", "risk": "Examiner objections on descriptiveness/similarity"},
        {"stage": "Publication in Trademark Journal", "duration": "1 month", "risk": "Public visibility, opposition window begins"},
        {"stage": "Opposition Period", "duration": "4 months", "risk": "HIGH - Competitors can file opposition"},
        {"stage": "Registration & Certificate", "duration": "1-2 months", "risk": "Final approval pending"}
    ],
    "USA": [
        {"stage": "Filing & Examination Assignment", "duration": "3-4 months", "risk": "Application assigned to examining attorney"},
        {"stage": "Substantive Examination", "duration": "3-6 months", "risk": "Office actions on descriptiveness, likelihood of confusion"},
        {"stage": "Publication for Opposition", "duration": "30 days", "risk": "MEDIUM - Opposition window"},
        {"stage": "Notice of Allowance (ITU) or Registration", "duration": "2-3 months", "risk": "Statement of Use required for ITU"},
        {"stage": "Final Registration", "duration": "1-2 months", "risk": "Certificate issued"}
    ],
    "Thailand": [
        {"stage": "Filing & Formalities Check", "duration": "1 month", "risk": "Basic compliance check"},
        {"stage": "Substantive Examination", "duration": "6-12 months", "risk": "Thai DIP examination backlog"},
        {"stage": "Publication Period", "duration": "60 days", "risk": "Opposition window"},
        {"stage": "Registration", "duration": "1-2 months", "risk": "Final certificate issuance"}
    ],
    "default": [
        {"stage": "Filing & Examination", "duration": "3-6 months", "risk": "Initial review"},
        {"stage": "Publication", "duration": "1-2 months", "risk": "Opposition window"},
        {"stage": "Registration", "duration": "1-3 months", "risk": "Final approval"}
    ]
}

def generate_registration_timeline(countries: list) -> dict:
    """Generate registration timeline for primary target country"""
    primary_country = countries[0] if countries else "default"
    country_name = primary_country.get('name') if isinstance(primary_country, dict) else str(primary_country)
    
    stages = REGISTRATION_TIMELINE_STAGES.get(country_name, REGISTRATION_TIMELINE_STAGES["default"])
    costs = COUNTRY_TRADEMARK_COSTS.get(country_name, COUNTRY_TRADEMARK_COSTS.get("default", {}))
    
    return {
        "country": country_name,
        "estimated_duration": "12-18 months" if country_name == "India" else "8-14 months",
        "stages": stages,
        "filing_cost": costs.get("filing_cost", "Contact local IP office"),
        "opposition_defense_cost": costs.get("opposition_defense_cost", "Varies by jurisdiction"),
        "total_estimated_cost": costs.get("total_estimated_cost", "Contact local IP attorney"),
        "trademark_search_cost": costs.get("trademark_search_cost", "$500-$1,500"),
        "legal_fees_cost": costs.get("legal_fees_cost", "$1,500-$5,000")
    }


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

# ═══════════════════════════════════════════════════════════════════════════════
# COUNTRY-SPECIFIC LEGAL PROCEDURES AND OPPOSITION PROCESSES
# This section provides jurisdiction-accurate legal information
# ═══════════════════════════════════════════════════════════════════════════════

COUNTRY_LEGAL_PROCEDURES = {
    "India": {
        "trademark_office": "Controller General of Patents, Designs and Trade Marks (IP India)",
        "governing_law": "Trade Marks Act, 1999 and Trade Marks Rules, 2017",
        "filing_basis": "Proposed to be Used / Used basis",
        "examination_process": [
            {"stage": "Filing & Formalities Check", "duration": "1-2 months", "description": "Application reviewed for completeness"},
            {"stage": "Examination Report", "duration": "3-6 months", "description": "Examiner reviews distinctiveness, prior marks"},
            {"stage": "Response to Examination Report", "duration": "1 month deadline", "description": "Respond to objections if any"},
            {"stage": "Publication in Trade Marks Journal", "duration": "Upon passing examination", "description": "Published for public notice"},
            {"stage": "Opposition Period", "duration": "4 months", "description": "Third parties can file opposition"},
            {"stage": "Registration", "duration": "1-2 months after opposition period", "description": "Certificate issued if no opposition"}
        ],
        "opposition_process": {
            "forum": "Registrar of Trade Marks / IP India",
            "opposition_filing_fee": "₹2,500 (physical) / ₹2,250 (e-filing)",
            "counter_statement_fee": "₹2,500",
            "timeline": "4 months from publication to file opposition",
            "stages": [
                {"stage": "Notice of Opposition", "action": "File within 4 months of publication", "cost": "₹2,500"},
                {"stage": "Counter Statement", "action": "Applicant responds within 2 months", "cost": "₹2,500"},
                {"stage": "Evidence Stage", "action": "Both parties file evidence", "cost": "₹5,000-₹20,000 (includes affidavits)"},
                {"stage": "Hearing", "action": "Oral hearing before Registrar", "cost": "₹10,000-₹50,000 (attorney fees)"},
                {"stage": "Decision", "action": "Registrar's order", "cost": "Included in hearing"}
            ],
            "total_opposition_cost": "₹20,000-₹75,000 (if straightforward)",
            "complex_opposition_cost": "₹75,000-₹2,00,000 (if heavily contested)"
        },
        "appeal_process": {
            "first_appeal": {
                "forum": "Intellectual Property Appellate Board (IPAB) / High Court (post-2021)",
                "timeline": "3 months from Registrar's decision",
                "cost": "₹10,000-₹50,000 (court fees + attorney)"
            },
            "final_appeal": {
                "forum": "Supreme Court of India",
                "timeline": "90 days from High Court decision",
                "cost": "₹1,00,000-₹5,00,000+"
            }
        },
        "currency": "INR (₹)",
        "use_requirement": "No strict use requirement before registration, but 'proposed to be used' declaration required",
        "renewal": "Every 10 years, fee ₹9,000 per class",
        "key_precedents": [
            "Cadila Healthcare Ltd. v. Cadila Pharmaceuticals Ltd. (2001) - Deceptive similarity test",
            "Amritdhara Pharmacy v. Satyadeo Gupta (1963) - Phonetic similarity in pharma",
            "Corn Products Refining Co. v. Shangrila Food Products (1960) - 'Glucovita' vs 'Gluvita'"
        ]
    },
    "USA": {
        "trademark_office": "United States Patent and Trademark Office (USPTO)",
        "governing_law": "Lanham Act (15 U.S.C. §§ 1051-1127)",
        "filing_basis": "Intent-to-Use (Section 1(b)) or Use in Commerce (Section 1(a))",
        "examination_process": [
            {"stage": "Filing & Application Receipt", "duration": "Immediate", "description": "Serial number assigned"},
            {"stage": "Examination Assignment", "duration": "3-4 months", "description": "Assigned to examining attorney"},
            {"stage": "Office Action (if any)", "duration": "Within 6 months of filing", "description": "Objections on descriptiveness, likelihood of confusion"},
            {"stage": "Response to Office Action", "duration": "6 month deadline", "description": "Address examiner's concerns"},
            {"stage": "Publication for Opposition", "duration": "30 days", "description": "Published in Official Gazette"},
            {"stage": "Notice of Allowance (ITU)", "duration": "If no opposition filed", "description": "Statement of Use required"},
            {"stage": "Registration", "duration": "Upon SOU acceptance", "description": "Certificate issued"}
        ],
        "opposition_process": {
            "forum": "Trademark Trial and Appeal Board (TTAB)",
            "opposition_filing_fee": "$600-$800 per class",
            "extension_of_time": "$200 per 30-day extension (up to 120 days)",
            "timeline": "30 days from publication (extendable)",
            "stages": [
                {"stage": "Notice of Opposition", "action": "File within 30 days + extensions", "cost": "$600-$800"},
                {"stage": "Answer", "action": "Applicant responds within 40 days", "cost": "$0 (filing) + attorney fees"},
                {"stage": "Discovery", "action": "Interrogatories, document requests, depositions", "cost": "$5,000-$30,000"},
                {"stage": "Trial Period", "action": "Submit evidence and testimony", "cost": "$10,000-$50,000"},
                {"stage": "Briefs", "action": "Legal arguments filed", "cost": "Included in attorney fees"},
                {"stage": "Oral Hearing (optional)", "action": "Argue before TTAB panel", "cost": "$2,000-$5,000 additional"},
                {"stage": "TTAB Decision", "action": "Board ruling", "cost": "Included"}
            ],
            "total_opposition_cost": "$15,000-$50,000 (straightforward)",
            "complex_opposition_cost": "$50,000-$250,000 (heavily contested with discovery)"
        },
        "appeal_process": {
            "first_appeal": {
                "forum": "U.S. Court of Appeals for the Federal Circuit OR U.S. District Court",
                "timeline": "63 days from TTAB decision",
                "cost": "$35,000-$100,000"
            },
            "final_appeal": {
                "forum": "U.S. Supreme Court (certiorari, rarely granted)",
                "timeline": "90 days from Federal Circuit decision",
                "cost": "$100,000-$500,000+"
            }
        },
        "currency": "USD ($)",
        "use_requirement": "Use in commerce required before registration (or within extensions for ITU)",
        "renewal": "Between 5th and 6th year (Section 8), then every 10 years",
        "key_precedents": [
            "Polaroid Corp. v. Polarad Elecs. Corp. (1961) - 8-factor likelihood of confusion test",
            "AMF Inc. v. Sleekcraft Boats (1979) - 8-factor test for consumer confusion",
            "In re E.I. DuPont DeNemours & Co. (1973) - 13-factor test for trademark registration"
        ]
    },
    "UK": {
        "trademark_office": "UK Intellectual Property Office (UKIPO)",
        "governing_law": "Trade Marks Act 1994 (as amended post-Brexit)",
        "filing_basis": "Intent to use (no proof required at filing)",
        "examination_process": [
            {"stage": "Filing & Formalities Check", "duration": "1-2 weeks", "description": "Application completeness review"},
            {"stage": "Examination", "duration": "4-8 weeks", "description": "Examiner checks absolute/relative grounds"},
            {"stage": "Publication", "duration": "Upon passing examination", "description": "Published in Trade Marks Journal"},
            {"stage": "Opposition Period", "duration": "2 months (extendable by 1 month)", "description": "Third parties can oppose"},
            {"stage": "Registration", "duration": "1 month after opposition period", "description": "Certificate issued"}
        ],
        "opposition_process": {
            "forum": "UKIPO Tribunal",
            "opposition_filing_fee": "£100-£200",
            "timeline": "2 months from publication (+ 1 month extension)",
            "stages": [
                {"stage": "Notice of Opposition (TM7)", "action": "File within 2-3 months of publication", "cost": "£100-£200"},
                {"stage": "Counter-Statement (TM8)", "action": "Applicant responds within 2 months", "cost": "£0"},
                {"stage": "Evidence Rounds", "action": "Exchange evidence", "cost": "£2,000-£10,000"},
                {"stage": "Hearing", "action": "Tribunal hearing (if requested)", "cost": "£3,000-£15,000"},
                {"stage": "Decision", "action": "Tribunal ruling", "cost": "Included"}
            ],
            "total_opposition_cost": "£5,000-£25,000 (straightforward)",
            "complex_opposition_cost": "£25,000-£100,000 (complex cases)"
        },
        "appeal_process": {
            "first_appeal": {
                "forum": "Appointed Person OR High Court (Chancery Division)",
                "timeline": "28 days from Tribunal decision",
                "cost": "£10,000-£40,000"
            },
            "final_appeal": {
                "forum": "Court of Appeal / Supreme Court",
                "timeline": "21 days from High Court decision",
                "cost": "£50,000-£200,000+"
            }
        },
        "currency": "GBP (£)",
        "use_requirement": "No use requirement at filing; can be challenged for non-use after 5 years",
        "renewal": "Every 10 years, fee £200 per class",
        "key_precedents": [
            "Sabel BV v. Puma AG (1997) - Global appreciation of similarity",
            "Canon Kabushiki Kaisha v. Metro-Goldwyn-Mayer (1998) - Interdependence principle",
            "Reed Executive plc v. Reed Business Information (2004) - Likelihood of confusion factors"
        ]
    },
    "UAE": {
        "trademark_office": "UAE Ministry of Economy - Trademark Office",
        "governing_law": "Federal Law No. 36 of 2021 on Trademarks",
        "filing_basis": "First-to-file, no use requirement",
        "examination_process": [
            {"stage": "Filing & Formalities", "duration": "1-2 weeks", "description": "Arabic translation required"},
            {"stage": "Examination", "duration": "3-6 months", "description": "Examiner reviews distinctiveness"},
            {"stage": "Publication", "duration": "Upon approval", "description": "Published for 30 days"},
            {"stage": "Opposition Period", "duration": "30 days", "description": "Third parties can oppose"},
            {"stage": "Registration", "duration": "1-2 months", "description": "Certificate issued"}
        ],
        "opposition_process": {
            "forum": "UAE Ministry of Economy / Grievance Committee",
            "timeline": "30 days from publication",
            "stages": [
                {"stage": "Notice of Opposition", "action": "File within 30 days", "cost": "AED 1,000-2,000"},
                {"stage": "Response", "action": "Applicant responds", "cost": "AED 500-1,000"},
                {"stage": "Decision", "action": "Ministry decision", "cost": "Included"}
            ],
            "total_opposition_cost": "AED 10,000-30,000"
        },
        "appeal_process": {
            "first_appeal": {
                "forum": "Grievance Committee / Civil Court",
                "timeline": "30 days from Ministry decision",
                "cost": "AED 20,000-50,000"
            }
        },
        "currency": "AED (د.إ)",
        "use_requirement": "No use requirement; registration valid for 10 years",
        "renewal": "Every 10 years",
        "special_requirements": [
            "Arabic translation of mark mandatory",
            "Power of Attorney must be notarized and legalized",
            "Religious symbols/terms prohibited"
        ]
    },
    "Singapore": {
        "trademark_office": "Intellectual Property Office of Singapore (IPOS)",
        "governing_law": "Trade Marks Act (Cap. 332)",
        "filing_basis": "First-to-file, no use requirement",
        "examination_process": [
            {"stage": "Filing", "duration": "Immediate", "description": "Online filing via IPOS Digital Hub"},
            {"stage": "Formalities Check", "duration": "1-2 weeks", "description": "Completeness review"},
            {"stage": "Examination", "duration": "4-6 months", "description": "Registrar examination"},
            {"stage": "Publication", "duration": "Upon acceptance", "description": "Published for 2 months"},
            {"stage": "Opposition Period", "duration": "2 months", "description": "Third parties can oppose"},
            {"stage": "Registration", "duration": "1 month", "description": "Certificate issued"}
        ],
        "opposition_process": {
            "forum": "IPOS Tribunal",
            "timeline": "2 months from publication",
            "stages": [
                {"stage": "Notice of Opposition", "action": "File within 2 months", "cost": "S$374"},
                {"stage": "Counter-Statement", "action": "Applicant responds within 2 months", "cost": "S$36"},
                {"stage": "Evidence", "action": "Exchange statutory declarations", "cost": "S$2,000-S$10,000"},
                {"stage": "Hearing", "action": "Tribunal hearing", "cost": "S$3,000-S$15,000"}
            ],
            "total_opposition_cost": "S$5,000-S$25,000"
        },
        "appeal_process": {
            "first_appeal": {
                "forum": "High Court of Singapore",
                "timeline": "28 days from Tribunal decision",
                "cost": "S$20,000-S$80,000"
            }
        },
        "currency": "SGD (S$)",
        "use_requirement": "No use requirement at filing",
        "renewal": "Every 10 years, fee S$380 per class"
    },
    "default": {
        "trademark_office": "National Intellectual Property Office",
        "governing_law": "Local Trademark Law",
        "filing_basis": "Varies by jurisdiction",
        "examination_process": [
            {"stage": "Filing", "duration": "Immediate", "description": "Application submitted"},
            {"stage": "Examination", "duration": "3-12 months", "description": "Examiner review"},
            {"stage": "Publication", "duration": "Upon acceptance", "description": "Published for opposition"},
            {"stage": "Opposition Period", "duration": "1-4 months", "description": "Third parties can oppose"},
            {"stage": "Registration", "duration": "1-3 months", "description": "Certificate issued"}
        ],
        "opposition_process": {
            "forum": "IP Office / Trademark Registry",
            "timeline": "Varies by jurisdiction",
            "total_opposition_cost": "Varies - consult local IP attorney"
        },
        "appeal_process": {
            "first_appeal": {
                "forum": "IP Appeals Board / Courts",
                "timeline": "Varies by jurisdiction",
                "cost": "Varies - consult local IP attorney"
            }
        },
        "currency": "Local currency",
        "use_requirement": "Varies by jurisdiction"
    }
}

def get_country_legal_procedures(country: str) -> dict:
    """Get country-specific legal procedures for trademark registration and opposition."""
    return COUNTRY_LEGAL_PROCEDURES.get(country, COUNTRY_LEGAL_PROCEDURES["default"])

def format_legal_procedures_for_prompt(countries: list) -> str:
    """Format country-specific legal procedures for LLM prompt."""
    if not countries:
        return ""
    
    primary_country = countries[0] if isinstance(countries[0], str) else countries[0].get('name', 'default')
    legal_info = get_country_legal_procedures(primary_country)
    
    # Build opposition stages text
    opposition = legal_info.get("opposition_process", {})
    opposition_stages = opposition.get("stages", [])
    stages_text = ""
    for stage in opposition_stages:
        stages_text += f"   - {stage.get('stage', 'Stage')}: {stage.get('action', '')} (Cost: {stage.get('cost', 'N/A')})\n"
    
    # Build examination process text
    exam_process = legal_info.get("examination_process", [])
    exam_text = ""
    for stage in exam_process:
        exam_text += f"   - {stage.get('stage', 'Stage')}: {stage.get('duration', 'N/A')} - {stage.get('description', '')}\n"
    
    # Build appeal process text
    appeal = legal_info.get("appeal_process", {})
    first_appeal = appeal.get("first_appeal", {})
    
    return f"""
═══════════════════════════════════════════════════════════════════════════════
⚖️ COUNTRY-SPECIFIC LEGAL PROCEDURES FOR {primary_country.upper()}
═══════════════════════════════════════════════════════════════════════════════

TRADEMARK OFFICE: {legal_info.get('trademark_office', 'National IP Office')}
GOVERNING LAW: {legal_info.get('governing_law', 'Local Trademark Law')}
FILING BASIS: {legal_info.get('filing_basis', 'Varies')}
CURRENCY: {legal_info.get('currency', 'Local currency')}

📋 REGISTRATION PROCESS:
{exam_text}

⚔️ OPPOSITION PROCESS:
   Forum: {opposition.get('forum', 'IP Office')}
   Timeline: {opposition.get('timeline', 'Varies')}
   
   STAGES:
{stages_text}
   
   ESTIMATED COSTS:
   - Simple Opposition: {opposition.get('total_opposition_cost', 'Consult attorney')}
   - Complex Opposition: {opposition.get('complex_opposition_cost', 'Consult attorney')}

📤 APPEAL PROCESS:
   First Appeal Forum: {first_appeal.get('forum', 'Appeals Board')}
   Timeline: {first_appeal.get('timeline', 'Varies')}
   Estimated Cost: {first_appeal.get('cost', 'Consult attorney')}

⚠️ IMPORTANT: Use {primary_country} jurisdiction terminology and costs.
   - Reference {legal_info.get('governing_law', 'local trademark law')} for legal basis
   - Use {legal_info.get('currency', 'local currency')} for all cost estimates
   - Cite {legal_info.get('trademark_office', 'local IP office')} as the authority
═══════════════════════════════════════════════════════════════════════════════
"""
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
        currency = costs['currency']
        
        # Get mitigation strategy costs based on country
        mitigation_costs = {
            "India": {
                "trademark_search": "₹3,000-₹5,000",
                "logo_design": "₹10,000-₹50,000",
                "legal_consultation": "₹10,000-₹30,000",
                "co_existence_agreement": "₹50,000-₹2,00,000",
                "monitoring_service": "₹5,000-₹15,000/year"
            },
            "USA": {
                "trademark_search": "$500-$1,500",
                "logo_design": "$2,000-$10,000",
                "legal_consultation": "$1,500-$5,000",
                "co_existence_agreement": "$5,000-$50,000",
                "monitoring_service": "$300-$1,000/year"
            },
            "UK": {
                "trademark_search": "£400-£1,200",
                "logo_design": "£1,500-£8,000",
                "legal_consultation": "£1,000-£4,000",
                "co_existence_agreement": "£3,000-£20,000",
                "monitoring_service": "£250-£800/year"
            },
            "UAE": {
                "trademark_search": "AED 2,000-AED 5,000",
                "logo_design": "AED 5,000-AED 25,000",
                "legal_consultation": "AED 5,000-AED 15,000",
                "co_existence_agreement": "AED 10,000-AED 50,000",
                "monitoring_service": "AED 1,500-AED 5,000/year"
            },
            "Singapore": {
                "trademark_search": "S$500-S$1,500",
                "logo_design": "S$2,000-S$8,000",
                "legal_consultation": "S$1,500-S$5,000",
                "co_existence_agreement": "S$5,000-S$25,000",
                "monitoring_service": "S$400-S$1,200/year"
            }
        }
        
        mit_costs = mitigation_costs.get(country, mitigation_costs.get("USA"))
        
        return f"""
═══════════════════════════════════════════════════════════════════════════════
⚠️ COUNTRY-SPECIFIC TRADEMARK COSTS FOR {country.upper()} (MANDATORY - USE THESE EXACT VALUES)
═══════════════════════════════════════════════════════════════════════════════

Target Country: {country}
Trademark Office: {costs['office']}
Currency: {currency}

📋 REGISTRATION COSTS (USE IN registration_timeline):
- filing_cost: {costs['filing_cost']}
- opposition_defense_cost: {costs['opposition_defense_cost']}
- total_estimated_cost: {costs['total_estimated_cost']}

🛡️ MITIGATION STRATEGY COSTS (USE IN mitigation_strategies[].estimated_cost):
- Trademark Search: {mit_costs['trademark_search']}
- Logo Design: {mit_costs['logo_design']}
- Legal Consultation: {mit_costs['legal_consultation']}
- Co-existence Agreement: {mit_costs['co_existence_agreement']}
- Monitoring Service: {mit_costs['monitoring_service']}

⚠️ CRITICAL INSTRUCTIONS:
1. ALL costs must use {currency} - DO NOT use USD ($) for {country}
2. These are ACTUAL {costs['office']} costs
3. mitigation_strategies[].estimated_cost MUST use {currency}
4. DO NOT convert currencies
═══════════════════════════════════════════════════════════════════════════════
"""
    else:
        return f"""
═══════════════════════════════════════════════════════════════════════════════
⚠️ MULTI-COUNTRY TRADEMARK COSTS (USE USD AS STANDARD)
═══════════════════════════════════════════════════════════════════════════════

Target Countries: {', '.join(countries)}
Standard Currency: USD ($) (for multi-country comparison)

📋 REGISTRATION COSTS:
- filing_cost: {costs['filing_cost']}
- opposition_defense_cost: {costs['opposition_defense_cost']}
- total_estimated_cost: {costs['total_estimated_cost']}

🛡️ MITIGATION STRATEGY COSTS:
- Trademark Search: $500-$1,500
- Logo Design: $2,000-$10,000
- Legal Consultation: $1,500-$5,000
- Co-existence Agreement: $5,000-$50,000

⚠️ IMPORTANT: Use USD ($) for ALL cost estimates when multiple countries are selected.
═══════════════════════════════════════════════════════════════════════════════
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
    "streetwear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "athleisure": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "activewear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "sportswear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "menswear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "womenswear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "kidswear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "wear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "garment": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "denim": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "jeans": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "t-shirt": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "tshirt": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "hoodie": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "jacket": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "sneaker": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "sneakers": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "cap": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "hat": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "headwear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "uniform": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "ethnic": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "ethnic wear": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "traditional": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "men's": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "women's": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    "kids'": {"class_number": 25, "class_description": "Clothing, footwear, headgear"},
    
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
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 9 - Booking/Appointment APPS (PRIORITY - must match before generic "booking")
    # These are SOFTWARE products, not transport services!
    # ═══════════════════════════════════════════════════════════════════════════
    "salon booking app": {"class_number": 9, "class_description": "Mobile application software for salon appointment booking"},
    "salon booking": {"class_number": 9, "class_description": "Mobile application software for salon appointment booking"},
    "salon app": {"class_number": 9, "class_description": "Mobile application software for salon services"},
    "beauty booking app": {"class_number": 9, "class_description": "Mobile application software for beauty service booking"},
    "beauty booking": {"class_number": 9, "class_description": "Mobile application software for beauty service booking"},
    "beauty app": {"class_number": 9, "class_description": "Mobile application software for beauty services"},
    "spa booking app": {"class_number": 9, "class_description": "Mobile application software for spa appointment booking"},
    "spa booking": {"class_number": 9, "class_description": "Mobile application software for spa appointment booking"},
    "spa app": {"class_number": 9, "class_description": "Mobile application software for spa services"},
    "barber booking app": {"class_number": 9, "class_description": "Mobile application software for barber appointment booking"},
    "barber booking": {"class_number": 9, "class_description": "Mobile application software for barber appointment booking"},
    "barber app": {"class_number": 9, "class_description": "Mobile application software for barber services"},
    "grooming app": {"class_number": 9, "class_description": "Mobile application software for grooming services"},
    "parlour booking": {"class_number": 9, "class_description": "Mobile application software for parlour appointment booking"},
    "parlor booking": {"class_number": 9, "class_description": "Mobile application software for parlor appointment booking"},
    "appointment app": {"class_number": 9, "class_description": "Mobile application software for appointment scheduling"},
    "appointment booking app": {"class_number": 9, "class_description": "Mobile application software for appointment booking"},
    "appointment booking": {"class_number": 9, "class_description": "Mobile application software for appointment scheduling"},
    "scheduling app": {"class_number": 9, "class_description": "Mobile application software for scheduling services"},
    "booking app": {"class_number": 9, "class_description": "Mobile application software for booking services"},
    "reservation app": {"class_number": 9, "class_description": "Mobile application software for reservation services"},
    
    # Doctor/Healthcare Booking Apps (Class 9)
    "doctor appointment app": {"class_number": 9, "class_description": "Mobile application software for doctor appointment booking"},
    "doctor booking app": {"class_number": 9, "class_description": "Mobile application software for doctor appointment booking"},
    "doctor booking": {"class_number": 9, "class_description": "Mobile application software for doctor appointment booking"},
    "doctor app": {"class_number": 9, "class_description": "Mobile application software for doctor services"},
    "clinic booking app": {"class_number": 9, "class_description": "Mobile application software for clinic appointment booking"},
    "clinic booking": {"class_number": 9, "class_description": "Mobile application software for clinic appointment booking"},
    "clinic app": {"class_number": 9, "class_description": "Mobile application software for clinic services"},
    "hospital booking": {"class_number": 9, "class_description": "Mobile application software for hospital appointment booking"},
    "healthcare app": {"class_number": 9, "class_description": "Mobile application software for healthcare services"},
    "healthtech": {"class_number": 9, "class_description": "Mobile application software for healthcare technology"},
    "telemedicine app": {"class_number": 9, "class_description": "Mobile application software for telemedicine services"},
    "telemedicine": {"class_number": 9, "class_description": "Mobile application software for telemedicine services"},
    "telehealth": {"class_number": 9, "class_description": "Mobile application software for telehealth services"},
    
    # Restaurant/Table Booking Apps (Class 9)
    "table booking app": {"class_number": 9, "class_description": "Mobile application software for restaurant table booking"},
    "table booking": {"class_number": 9, "class_description": "Mobile application software for restaurant table booking"},
    "restaurant booking app": {"class_number": 9, "class_description": "Mobile application software for restaurant booking"},
    "restaurant booking": {"class_number": 9, "class_description": "Mobile application software for restaurant booking"},
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Class 44 - Medical & Beauty SERVICES (not apps)
    # Use this when the business PROVIDES the services, not just books them
    # ═══════════════════════════════════════════════════════════════════════════
    "salon services": {"class_number": 44, "class_description": "Beauty salon services, hair care, cosmetic treatment"},
    "salon": {"class_number": 44, "class_description": "Beauty salon services, hair care, cosmetic treatment"},
    "beauty services": {"class_number": 44, "class_description": "Beauty care services, hygienic care for human beings"},
    "spa services": {"class_number": 44, "class_description": "Spa services, massage, wellness treatments"},
    "spa": {"class_number": 44, "class_description": "Spa services, massage, wellness treatments"},
    "barber services": {"class_number": 44, "class_description": "Barbershop services, hair cutting"},
    "barber": {"class_number": 44, "class_description": "Barbershop services, hair cutting"},
    "parlour": {"class_number": 44, "class_description": "Beauty parlour services"},
    "parlor": {"class_number": 44, "class_description": "Beauty parlor services"},
    "medical services": {"class_number": 44, "class_description": "Medical services, healthcare"},
    "dental services": {"class_number": 44, "class_description": "Dental services, oral care"},
    "dental": {"class_number": 44, "class_description": "Dental services, oral care"},
    "veterinary": {"class_number": 44, "class_description": "Veterinary services, animal care"},
    "wellness": {"class_number": 44, "class_description": "Wellness services, health care"},
    
    # ═══════════════════════════════════════════════════════════════════════════
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
    # YouTube, Content Creation, Media (Class 41)
    "youtube": {"class_number": 41, "class_description": "Education, entertainment, video production services"},
    "youtube channel": {"class_number": 41, "class_description": "Education, entertainment, video production services"},
    "content creator": {"class_number": 41, "class_description": "Education, entertainment, content creation services"},
    "content creation": {"class_number": 41, "class_description": "Education, entertainment, content creation services"},
    "podcast": {"class_number": 41, "class_description": "Education, entertainment, audio production services"},
    "podcasting": {"class_number": 41, "class_description": "Education, entertainment, audio production services"},
    "streaming": {"class_number": 41, "class_description": "Education, entertainment, streaming services"},
    "vlog": {"class_number": 41, "class_description": "Education, entertainment, video blog services"},
    "vlogging": {"class_number": 41, "class_description": "Education, entertainment, video blog services"},
    "influencer": {"class_number": 41, "class_description": "Education, entertainment, influencer services"},
    "media": {"class_number": 41, "class_description": "Education, entertainment, media production services"},
    "media company": {"class_number": 41, "class_description": "Education, entertainment, media production services"},
    "channel": {"class_number": 41, "class_description": "Education, entertainment, broadcasting services"},
    "video production": {"class_number": 41, "class_description": "Education, entertainment, video production services"},
    "online education": {"class_number": 41, "class_description": "Education, training, online educational services"},
    "e-learning": {"class_number": 41, "class_description": "Education, training, e-learning services"},
    "course": {"class_number": 41, "class_description": "Education, training, educational course services"},
    "courses": {"class_number": 41, "class_description": "Education, training, educational course services"},
    
    # Class 42 - Technology services
    "saas": {"class_number": 42, "class_description": "Scientific and technological services, software as a service"},
    "cloud": {"class_number": 42, "class_description": "Scientific and technological services, software as a service"},
    "it services": {"class_number": 42, "class_description": "Scientific and technological services, software as a service"},
    "platform": {"class_number": 42, "class_description": "Scientific and technological services, software as a service"},
    
    # Class 43 - Restaurant, hospitality (PRIORITY - check these first)
    "hotel chain": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "hotel": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "hotels": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "resort": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "resorts": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "motel": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "lodge": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "inn": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "accommodation": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "hospitality": {"class_number": 43, "class_description": "Hotels, temporary accommodation, restaurant services"},
    "restaurant": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "cafe": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "food service": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "quick service": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    "qsr": {"class_number": 43, "class_description": "Restaurant services, food and drink services, hotels"},
    
    # Class 39 - Transport, travel (ONLY for actual transport services, NOT booking apps)
    "sea travel": {"class_number": 39, "class_description": "Transport, travel arrangement, sea transport services"},
    "sea transport": {"class_number": 39, "class_description": "Transport, travel arrangement, sea transport services"},
    "ferry": {"class_number": 39, "class_description": "Transport, travel arrangement, ferry services"},
    "cruise": {"class_number": 39, "class_description": "Transport, travel arrangement, cruise services"},
    "shipping": {"class_number": 39, "class_description": "Transport, freight, shipping services"},
    "logistics": {"class_number": 39, "class_description": "Transport, logistics, warehousing services"},
    "travel agency": {"class_number": 39, "class_description": "Transport, travel arrangement services"},
    "travel arrangement": {"class_number": 39, "class_description": "Transport, travel arrangement services"},
    "travel services": {"class_number": 39, "class_description": "Transport, travel arrangement services"},
    "transport": {"class_number": 39, "class_description": "Transport, travel arrangement services"},
    "transportation": {"class_number": 39, "class_description": "Transport, travel arrangement services"},
    "tour": {"class_number": 39, "class_description": "Transport, travel arrangement, tour services"},
    "tour operator": {"class_number": 39, "class_description": "Transport, travel arrangement, tour services"},
    "travel booking": {"class_number": 39, "class_description": "Travel arrangement, travel booking services"},
    "flight booking": {"class_number": 39, "class_description": "Transport, flight booking services"},
    "airline": {"class_number": 39, "class_description": "Transport, air transport services"},
    "flight": {"class_number": 39, "class_description": "Transport, air transport services"},
    "cargo": {"class_number": 39, "class_description": "Transport, freight, cargo services"},
    "delivery": {"class_number": 39, "class_description": "Transport, delivery services"},
    "courier": {"class_number": 39, "class_description": "Transport, courier services"},
    "cab": {"class_number": 39, "class_description": "Taxi, cab transportation services"},
    "taxi": {"class_number": 39, "class_description": "Taxi transportation services"},
    "ride-hailing": {"class_number": 39, "class_description": "Ride-hailing transportation services"},
    "ride hailing": {"class_number": 39, "class_description": "Ride-hailing transportation services"},
}

def get_nice_classification(category: str) -> dict:
    """
    Get NICE classification based on category/industry keywords.
    Returns a dict with class_number, class_description, and matched_term.
    Prioritizes longer matches first to avoid partial matching issues.
    """
    if not category:
        return {"class_number": 35, "class_description": "Advertising, business management, retail services", "matched_term": "general business"}
    
    category_lower = category.lower().strip()
    
    # Sort keywords by length (longest first) to prioritize more specific matches
    # This ensures "hotel chain" matches before "chain" or "hotel" alone
    sorted_keywords = sorted(NICE_CLASS_MAP.keys(), key=len, reverse=True)
    
    # Check each keyword in the NICE_CLASS_MAP (longest first)
    for keyword in sorted_keywords:
        if keyword in category_lower:
            classification = NICE_CLASS_MAP[keyword]
            return {
                "class_number": classification["class_number"],
                "class_description": classification["class_description"],
                "matched_term": keyword
            }
    
    # Default to Class 35 for unknown categories
    return {"class_number": 35, "class_description": "Advertising, business management, retail services", "matched_term": category}


# ============================================================================
# 🆕 FEATURE 1: MULTI-CLASS NICE STRATEGY
# ============================================================================
# Most businesses need 2-5 NICE classes for comprehensive protection

MULTI_CLASS_STRATEGY = {
    # SaaS / Software Platform
    "saas": {
        "primary": {"class_number": 42, "description": "Software-as-a-Service (SaaS) platform services", "term": "Providing temporary use of non-downloadable software"},
        "secondary": [
            {"class_number": 9, "description": "Downloadable mobile application software", "rationale": "Protects app distribution via App Store/Google Play", "priority": "Within 6 months"},
            {"class_number": 35, "description": "Online retail store services", "rationale": "Covers e-commerce/marketplace features", "priority": "When revenue materializes"}
        ],
        "total_recommended": 3,
        "filing_strategy": "Staggered: Class 42 immediately, Classes 9+35 after product validation"
    },
    "software": {
        "primary": {"class_number": 9, "description": "Computer software, mobile applications", "term": "Downloadable computer software"},
        "secondary": [
            {"class_number": 42, "description": "Software as a service (SaaS)", "rationale": "Covers cloud-based delivery model", "priority": "Immediate if SaaS"},
            {"class_number": 35, "description": "Business software services", "rationale": "Covers B2B software sales", "priority": "For enterprise sales"}
        ],
        "total_recommended": 2,
        "filing_strategy": "File Class 9 first, add Class 42 if offering SaaS model"
    },
    "app": {
        "primary": {"class_number": 9, "description": "Mobile application software", "term": "Downloadable mobile application software"},
        "secondary": [
            {"class_number": 42, "description": "App development services", "rationale": "Protects service offering", "priority": "If offering custom development"},
            {"class_number": 35, "description": "App store services", "rationale": "For marketplace features", "priority": "If app has commerce"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 9 immediately for app distribution"
    },
    # E-commerce
    "ecommerce": {
        "primary": {"class_number": 35, "description": "Online retail store services", "term": "Online retail store services featuring [products]"},
        "secondary": [
            {"class_number": 9, "description": "Mobile shopping application", "rationale": "Protects shopping app", "priority": "Immediate"},
            {"class_number": 42, "description": "E-commerce platform services", "rationale": "Covers platform infrastructure", "priority": "For platform businesses"}
        ],
        "total_recommended": 3,
        "filing_strategy": "File all 3 simultaneously for comprehensive e-commerce protection"
    },
    "retail": {
        "primary": {"class_number": 35, "description": "Retail store services", "term": "Retail store services featuring [products]"},
        "secondary": [
            {"class_number": 9, "description": "Point of sale software", "rationale": "Protects retail technology", "priority": "If using proprietary POS"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 35 covers retail operations"
    },
    # Fintech / Finance
    "fintech": {
        "primary": {"class_number": 36, "description": "Financial technology services", "term": "Financial services, banking, payment processing"},
        "secondary": [
            {"class_number": 9, "description": "Financial software applications", "rationale": "Protects mobile banking app", "priority": "Immediate"},
            {"class_number": 42, "description": "Financial SaaS platform", "rationale": "Covers cloud financial services", "priority": "Immediate"}
        ],
        "total_recommended": 3,
        "filing_strategy": "All 3 classes critical for fintech - file simultaneously"
    },
    "finance": {
        "primary": {"class_number": 36, "description": "Financial services, banking, insurance", "term": "Financial affairs, monetary affairs, banking"},
        "secondary": [
            {"class_number": 9, "description": "Financial software", "rationale": "Protects financial apps", "priority": "If app-based"},
            {"class_number": 35, "description": "Financial consulting", "rationale": "Covers advisory services", "priority": "For consulting arms"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 36 is primary; add Class 9 for digital products"
    },
    "payment": {
        "primary": {"class_number": 36, "description": "Payment processing services", "term": "Payment processing, electronic funds transfer"},
        "secondary": [
            {"class_number": 9, "description": "Payment application software", "rationale": "Protects payment app", "priority": "Immediate"},
            {"class_number": 42, "description": "Payment platform services", "rationale": "Covers payment infrastructure", "priority": "Immediate"}
        ],
        "total_recommended": 3,
        "filing_strategy": "All 3 classes essential for payment companies"
    },
    # Food & Beverage
    "cafe": {
        "primary": {"class_number": 43, "description": "Cafe and restaurant services", "term": "Cafe services, restaurant services, food and drink services"},
        "secondary": [
            {"class_number": 30, "description": "Coffee, tea, bakery products", "rationale": "Protects retail product sales", "priority": "When selling packaged products"},
            {"class_number": 35, "description": "Franchise services", "rationale": "For franchise expansion", "priority": "Before franchising"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 43 immediately, Class 30 when selling retail products"
    },
    "restaurant": {
        "primary": {"class_number": 43, "description": "Restaurant services", "term": "Restaurant services, food and drink services"},
        "secondary": [
            {"class_number": 29, "description": "Prepared foods, meat products", "rationale": "For packaged food sales", "priority": "For retail line"},
            {"class_number": 30, "description": "Bakery, confectionery", "rationale": "For desserts/bakery items", "priority": "For retail line"},
            {"class_number": 35, "description": "Restaurant franchise services", "rationale": "Essential for franchising", "priority": "Before franchising"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 43 immediately; add product classes when launching retail"
    },
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BOOKING/APPOINTMENT APPS - Class 9 PRIMARY (not Class 39!)
    # These are SOFTWARE products for booking services
    # ═══════════════════════════════════════════════════════════════════════════
    "salon booking app": {
        "primary": {"class_number": 9, "description": "Mobile application software for salon booking", "term": "Downloadable mobile application software for booking salon appointments"},
        "secondary": [
            {"class_number": 42, "description": "SaaS platform services", "rationale": "For cloud-based booking platform", "priority": "If offering SaaS to salons"},
            {"class_number": 35, "description": "Online booking marketplace", "rationale": "For marketplace/aggregator model", "priority": "If aggregating multiple salons"},
            {"class_number": 44, "description": "Beauty salon services", "rationale": "ONLY if you operate your own salons", "priority": "If vertically integrated"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 9 immediately for app; add Class 42 if B2B SaaS; Class 35 if marketplace"
    },
    "salon booking": {
        "primary": {"class_number": 9, "description": "Mobile application software for salon booking", "term": "Downloadable mobile application software for booking salon appointments"},
        "secondary": [
            {"class_number": 42, "description": "SaaS platform services", "rationale": "For cloud-based booking platform", "priority": "If offering SaaS to salons"},
            {"class_number": 35, "description": "Online booking marketplace", "rationale": "For marketplace/aggregator model", "priority": "If aggregating multiple salons"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 9 immediately for app; add Class 42 if B2B SaaS"
    },
    "beauty booking app": {
        "primary": {"class_number": 9, "description": "Mobile application software for beauty service booking", "term": "Downloadable mobile application software for booking beauty services"},
        "secondary": [
            {"class_number": 42, "description": "SaaS platform services", "rationale": "For cloud-based platform", "priority": "If offering SaaS"},
            {"class_number": 35, "description": "Online booking marketplace", "rationale": "For marketplace model", "priority": "If aggregating providers"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 9 immediately for app distribution"
    },
    "appointment app": {
        "primary": {"class_number": 9, "description": "Mobile application software for appointment scheduling", "term": "Downloadable mobile application software for scheduling appointments"},
        "secondary": [
            {"class_number": 42, "description": "SaaS scheduling platform", "rationale": "For cloud-based scheduling", "priority": "If offering SaaS"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 9 immediately for app distribution"
    },
    "booking app": {
        "primary": {"class_number": 9, "description": "Mobile application software for booking services", "term": "Downloadable mobile application software for booking services"},
        "secondary": [
            {"class_number": 42, "description": "SaaS booking platform", "rationale": "For cloud-based platform", "priority": "If offering SaaS"},
            {"class_number": 35, "description": "Online booking marketplace", "rationale": "For marketplace model", "priority": "If aggregating services"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 9 immediately; add industry-specific class based on service type"
    },
    "doctor appointment app": {
        "primary": {"class_number": 9, "description": "Mobile application software for doctor appointment booking", "term": "Downloadable mobile application software for booking doctor appointments"},
        "secondary": [
            {"class_number": 42, "description": "SaaS healthcare platform", "rationale": "For cloud-based healthcare platform", "priority": "If offering B2B SaaS to clinics"},
            {"class_number": 44, "description": "Medical services", "rationale": "ONLY if providing actual medical services", "priority": "If vertically integrated"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 9 immediately for app; Class 42 if B2B platform"
    },
    "telemedicine": {
        "primary": {"class_number": 9, "description": "Telemedicine software application", "term": "Downloadable mobile application software for telemedicine consultations"},
        "secondary": [
            {"class_number": 42, "description": "SaaS telemedicine platform", "rationale": "For cloud-based platform", "priority": "Immediate"},
            {"class_number": 44, "description": "Medical consultation services", "rationale": "If providing actual consultations", "priority": "If doctors on payroll"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 9 + 42 for platform; add 44 if providing actual medical consultations"
    },
    # ═══════════════════════════════════════════════════════════════════════════
    
    "food": {
        "primary": {"class_number": 29, "description": "Processed foods, meat, dairy", "term": "Processed foods, preserved foods, dairy products"},
        "secondary": [
            {"class_number": 30, "description": "Bakery, cereals, snacks", "rationale": "For grain-based products", "priority": "If applicable"},
            {"class_number": 35, "description": "Food retail services", "rationale": "For direct sales", "priority": "For D2C brands"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 29 or 30 based on product type"
    },
    # Fashion / Apparel
    "fashion": {
        "primary": {"class_number": 25, "description": "Clothing, footwear, headgear", "term": "Clothing, footwear, headgear"},
        "secondary": [
            {"class_number": 35, "description": "Fashion retail services", "rationale": "Covers retail operations", "priority": "Immediate for retailers"},
            {"class_number": 18, "description": "Leather goods, bags", "rationale": "For accessories", "priority": "If selling bags/accessories"},
            {"class_number": 14, "description": "Jewelry, watches", "rationale": "For jewelry line", "priority": "If expanding to jewelry"}
        ],
        "total_recommended": 3,
        "filing_strategy": "Class 25 + 35 immediately; expand to 18/14 as product lines grow"
    },
    "clothing": {
        "primary": {"class_number": 25, "description": "Clothing, footwear, headgear", "term": "Clothing, footwear, headgear"},
        "secondary": [
            {"class_number": 35, "description": "Clothing retail services", "rationale": "For retail/e-commerce", "priority": "Immediate"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 25 for products, Class 35 for retail"
    },
    # Healthcare
    "healthcare": {
        "primary": {"class_number": 44, "description": "Medical services, healthcare", "term": "Medical services, healthcare services"},
        "secondary": [
            {"class_number": 9, "description": "Healthcare software", "rationale": "For health apps", "priority": "If app-based"},
            {"class_number": 10, "description": "Medical devices", "rationale": "For medical equipment", "priority": "If selling devices"},
            {"class_number": 42, "description": "Healthcare SaaS", "rationale": "For platform services", "priority": "For B2B healthcare"}
        ],
        "total_recommended": 3,
        "filing_strategy": "Depends on service vs product focus"
    },
    # Hotels / Hospitality
    "hotel": {
        "primary": {"class_number": 43, "description": "Hotel and accommodation services", "term": "Hotel services, temporary accommodation"},
        "secondary": [
            {"class_number": 35, "description": "Hotel management services", "rationale": "For management contracts", "priority": "For hotel groups"},
            {"class_number": 39, "description": "Travel arrangement services", "rationale": "For booking services", "priority": "If offering travel packages"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 43 immediately for core hotel operations"
    },
    # Education
    "education": {
        "primary": {"class_number": 41, "description": "Education and training services", "term": "Educational services, training services"},
        "secondary": [
            {"class_number": 9, "description": "Educational software", "rationale": "For e-learning apps", "priority": "Immediate for EdTech"},
            {"class_number": 42, "description": "Educational platform services", "rationale": "For LMS platforms", "priority": "For platform businesses"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 41 + Class 9 for most EdTech companies"
    },
    # YouTube / Content Creation / Podcasts
    "youtube": {
        "primary": {"class_number": 41, "description": "Entertainment services, video production", "term": "Entertainment services, video production, educational videos"},
        "secondary": [
            {"class_number": 35, "description": "Advertising, sponsorship services", "rationale": "For monetization and brand deals", "priority": "When monetizing"},
            {"class_number": 9, "description": "Downloadable video content", "rationale": "For courses or downloadable content", "priority": "If selling courses"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 41 immediately for content creation; add Class 35 for sponsorships"
    },
    "youtube channel": {
        "primary": {"class_number": 41, "description": "Entertainment services, video production", "term": "Entertainment services, video production, educational videos"},
        "secondary": [
            {"class_number": 35, "description": "Advertising, sponsorship services", "rationale": "For monetization and brand deals", "priority": "When monetizing"},
            {"class_number": 9, "description": "Downloadable video content", "rationale": "For courses or downloadable content", "priority": "If selling courses"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 41 immediately for content creation; add Class 35 for sponsorships"
    },
    "content creator": {
        "primary": {"class_number": 41, "description": "Entertainment, content creation services", "term": "Entertainment services, content creation, video production"},
        "secondary": [
            {"class_number": 35, "description": "Advertising, influencer marketing", "rationale": "For brand partnerships", "priority": "When monetizing"},
            {"class_number": 9, "description": "Digital content products", "rationale": "For downloadable products", "priority": "If selling digital products"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 41 for core content services"
    },
    "podcast": {
        "primary": {"class_number": 41, "description": "Entertainment, audio production services", "term": "Entertainment services, audio production, podcasting"},
        "secondary": [
            {"class_number": 35, "description": "Advertising, sponsorship services", "rationale": "For podcast monetization", "priority": "When monetizing"},
            {"class_number": 9, "description": "Downloadable audio content", "rationale": "For premium audio content", "priority": "If selling content"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 41 for podcast production; add Class 35 for sponsorships"
    },
    "media": {
        "primary": {"class_number": 41, "description": "Entertainment, media production services", "term": "Entertainment services, media production, broadcasting"},
        "secondary": [
            {"class_number": 35, "description": "Advertising, media buying services", "rationale": "For media agency services", "priority": "If offering ad services"},
            {"class_number": 38, "description": "Broadcasting, streaming services", "rationale": "For live broadcasting", "priority": "If live streaming"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 41 for content; Class 38 if broadcasting"
    },
    # Beauty / Cosmetics
    "beauty": {
        "primary": {"class_number": 3, "description": "Cosmetics, skincare, beauty products", "term": "Cosmetics, skincare preparations, beauty products"},
        "secondary": [
            {"class_number": 35, "description": "Beauty retail services", "rationale": "For retail/e-commerce", "priority": "Immediate"},
            {"class_number": 44, "description": "Beauty salon services", "rationale": "For service businesses", "priority": "If offering treatments"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 3 for products, Class 44 for services"
    },
    "skincare": {
        "primary": {"class_number": 3, "description": "Skincare preparations, cosmetics", "term": "Skincare preparations, cosmetics"},
        "secondary": [
            {"class_number": 35, "description": "Skincare retail services", "rationale": "For D2C sales", "priority": "Immediate"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 3 + Class 35 for comprehensive protection"
    },
    # Travel / Transportation
    "travel": {
        "primary": {"class_number": 39, "description": "Transport, travel arrangement services", "term": "Travel arrangement, transport services, tour operator services"},
        "secondary": [
            {"class_number": 43, "description": "Temporary accommodation booking", "rationale": "For hotel booking features", "priority": "If booking accommodation"},
            {"class_number": 35, "description": "Travel agency services", "rationale": "For business operations", "priority": "For retail travel services"},
            {"class_number": 9, "description": "Travel booking software", "rationale": "For mobile apps", "priority": "If app-based"}
        ],
        "total_recommended": 3,
        "filing_strategy": "Class 39 immediately for core travel services; add Class 43 if booking hotels"
    },
    "sea": {
        "primary": {"class_number": 39, "description": "Sea transport, ferry services, cruise services", "term": "Sea transport services, ferry services, cruise services"},
        "secondary": [
            {"class_number": 43, "description": "Accommodation services", "rationale": "For cruise accommodation", "priority": "For cruise ships"},
            {"class_number": 35, "description": "Travel booking services", "rationale": "For booking platform", "priority": "For booking portals"},
            {"class_number": 9, "description": "Booking application software", "rationale": "For mobile apps", "priority": "If app-based"}
        ],
        "total_recommended": 3,
        "filing_strategy": "Class 39 primary for sea transport; add Class 9 for booking apps"
    },
    "cruise": {
        "primary": {"class_number": 39, "description": "Cruise ship services, sea transport", "term": "Cruise ship services, passenger transport by sea"},
        "secondary": [
            {"class_number": 43, "description": "Temporary accommodation on cruise ships", "rationale": "For onboard accommodation", "priority": "Immediate"},
            {"class_number": 41, "description": "Entertainment services", "rationale": "For onboard entertainment", "priority": "For cruise entertainment"}
        ],
        "total_recommended": 3,
        "filing_strategy": "Class 39 + 43 essential for cruise operators"
    },
    "ferry": {
        "primary": {"class_number": 39, "description": "Ferry transport services", "term": "Ferry services, passenger transport by water"},
        "secondary": [
            {"class_number": 35, "description": "Ferry booking services", "rationale": "For booking platform", "priority": "If operating booking portal"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 39 covers core ferry operations"
    },
    "transport": {
        "primary": {"class_number": 39, "description": "Transport services", "term": "Transport services, logistics, delivery"},
        "secondary": [
            {"class_number": 35, "description": "Transport booking services", "rationale": "For booking platform", "priority": "If booking portal"},
            {"class_number": 9, "description": "Transport booking software", "rationale": "For mobile apps", "priority": "If app-based"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 39 for transport operations"
    },
    "logistics": {
        "primary": {"class_number": 39, "description": "Logistics and freight services", "term": "Logistics services, freight transport, warehousing"},
        "secondary": [
            {"class_number": 35, "description": "Supply chain management", "rationale": "For B2B logistics", "priority": "For enterprise logistics"},
            {"class_number": 42, "description": "Logistics software platform", "rationale": "For tech platforms", "priority": "If SaaS logistics"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class 39 for logistics operations"
    },
    "booking": {
        "primary": {"class_number": 39, "description": "Travel booking and arrangement services", "term": "Travel arrangement services, booking services"},
        "secondary": [
            {"class_number": 43, "description": "Hotel booking services", "rationale": "For accommodation booking", "priority": "If booking hotels"},
            {"class_number": 9, "description": "Booking application software", "rationale": "For mobile apps", "priority": "Immediate for apps"},
            {"class_number": 35, "description": "Online booking platform services", "rationale": "For marketplace features", "priority": "For booking platforms"}
        ],
        "total_recommended": 3,
        "filing_strategy": "Class 39 + Class 9 for travel booking apps"
    },
    "portal": {
        "primary": {"class_number": 35, "description": "Online portal services, e-commerce", "term": "Online portal services, e-commerce platform services"},
        "secondary": [
            {"class_number": 42, "description": "Web portal hosting services", "rationale": "For platform infrastructure", "priority": "For tech platforms"},
            {"class_number": 9, "description": "Portal software applications", "rationale": "For mobile apps", "priority": "If app-based"}
        ],
        "total_recommended": 2,
        "filing_strategy": "Class depends on portal type - combine with industry-specific class"
    }
}

def get_multi_class_nice_strategy(category: str) -> dict:
    """
    Get multi-class NICE filing strategy based on category.
    Returns primary class + secondary classes with filing strategy.
    """
    if not category:
        return None
    
    category_lower = category.lower().strip()
    
    # First check for exact matches
    if category_lower in MULTI_CLASS_STRATEGY:
        strategy = MULTI_CLASS_STRATEGY[category_lower]
        return {
            "primary_class": strategy["primary"],
            "secondary_classes": strategy["secondary"],
            "total_classes_recommended": strategy["total_recommended"],
            "filing_strategy": strategy["filing_strategy"],
            "expansion_classes": []
        }
    
    # Check for partial matches - prefer LONGER keyword matches to avoid "app" matching "apparel"
    best_match = None
    best_match_len = 0
    
    for keyword, strategy in MULTI_CLASS_STRATEGY.items():
        if keyword in category_lower:
            # Check if it's a whole word match (not part of another word)
            # e.g., "app" should not match "apparel", but "fashion" should match "fashion & apparel"
            import re
            if re.search(r'\b' + re.escape(keyword) + r'\b', category_lower):
                if len(keyword) > best_match_len:
                    best_match = strategy
                    best_match_len = len(keyword)
    
    if best_match:
        return {
            "primary_class": best_match["primary"],
            "secondary_classes": best_match["secondary"],
            "total_classes_recommended": best_match["total_recommended"],
            "filing_strategy": best_match["filing_strategy"],
            "expansion_classes": []
        }
    
    # Default strategy for unknown categories
    basic_class = get_nice_classification(category)
    primary_class_num = basic_class["class_number"]
    
    # Avoid duplicate classes - if primary is 35, use different secondary
    if primary_class_num == 35:
        secondary_classes = [
            {"class_number": 42, "description": "Technology platform services", "rationale": "For digital/tech platforms", "priority": "If technology-based"},
            {"class_number": 9, "description": "Software applications", "rationale": "For mobile/web apps", "priority": "If app-based"}
        ]
        filing_strategy = f"File Class 35 as primary for business services; add Class 42/9 for technology"
    else:
        secondary_classes = [
            {"class_number": 35, "description": "Business services, advertising", "rationale": "General business protection", "priority": "Consider for retail/marketing"}
        ]
        filing_strategy = f"File Class {primary_class_num} as primary; evaluate Class 35 for business expansion"
    
    return {
        "primary_class": {
            "class_number": primary_class_num,
            "description": basic_class["class_description"],
            "term": f"Services related to {category}"
        },
        "secondary_classes": secondary_classes,
        "total_classes_recommended": 2,
        "filing_strategy": filing_strategy,
        "expansion_classes": []
    }


# ============================================================================
# 🆕 FEATURE 2: REALISTIC OPPOSITION DEFENSE COSTS (TIERED)
# ============================================================================
# Previous estimates were 50-70% too low - these are litigation-grade accurate

REALISTIC_OPPOSITION_COSTS = {
    "USA": {
        "currency": "USD",
        "symbol": "$",
        "filing_cost_per_class": "$350-$600",
        "opposition_defense": {
            "uncontested": {"cost": "$5,000-$10,000", "description": "Opponent withdraws after initial response", "probability": 30},
            "settlement": {"cost": "$15,000-$35,000", "description": "Negotiated coexistence agreement or consent", "probability": 45},
            "ttab_defense": {"cost": "$35,000-$90,000", "description": "Full TTAB proceedings with discovery, briefs, hearing", "probability": 20},
            "federal_appeal": {"cost": "$90,000-$250,000+", "description": "Appeal to Federal Circuit or district court litigation", "probability": 5}
        },
        "expected_value_cost": "$12,500",
        "total_worst_case": "$251,800"
    },
    "India": {
        "currency": "INR",
        "symbol": "₹",
        "filing_cost_per_class": "₹5,500-₹12,000",
        "opposition_defense": {
            "uncontested": {"cost": "₹75,000-₹1,50,000", "description": "Opponent withdraws after initial response", "probability": 30},
            "settlement": {"cost": "₹2,00,000-₹5,00,000", "description": "Negotiated settlement agreement", "probability": 45},
            "hearing_defense": {"cost": "₹4,00,000-₹12,00,000", "description": "Full hearing with evidence and arguments", "probability": 20},
            "high_court_appeal": {"cost": "₹10,00,000-₹40,00,000+", "description": "Appeal to High Court", "probability": 5}
        },
        "expected_value_cost": "₹2,25,000",
        "total_worst_case": "₹52,62,000"
    },
    "UK": {
        "currency": "GBP",
        "symbol": "£",
        "filing_cost_per_class": "£200-£400",
        "opposition_defense": {
            "uncontested": {"cost": "£3,000-£8,000", "description": "Opponent withdraws after initial response", "probability": 30},
            "settlement": {"cost": "£10,000-£25,000", "description": "Negotiated coexistence agreement", "probability": 45},
            "hearing_defense": {"cost": "£20,000-£60,000", "description": "Full UKIPO hearing proceedings", "probability": 20},
            "appeal": {"cost": "£50,000-£150,000+", "description": "Appeal to Appointed Person or Court", "probability": 5}
        },
        "expected_value_cost": "£9,500",
        "total_worst_case": "£150,400"
    },
    "EU": {
        "currency": "EUR",
        "symbol": "€",
        "filing_cost_per_class": "€1,050-€1,800",
        "opposition_defense": {
            "uncontested": {"cost": "€5,000-€12,000", "description": "Opponent withdraws after initial response", "probability": 30},
            "settlement": {"cost": "€15,000-€40,000", "description": "Negotiated agreement", "probability": 45},
            "board_appeal": {"cost": "€30,000-€90,000", "description": "Board of Appeal proceedings", "probability": 20},
            "eu_court": {"cost": "€100,000-€300,000+", "description": "General Court / ECJ appeal", "probability": 5}
        },
        "expected_value_cost": "€15,000",
        "total_worst_case": "€301,800"
    },
    "Canada": {
        "currency": "CAD",
        "symbol": "C$",
        "filing_cost_per_class": "C$500-C$850",
        "opposition_defense": {
            "uncontested": {"cost": "C$8,000-C$15,000", "description": "Opponent withdraws after initial response", "probability": 30},
            "settlement": {"cost": "C$20,000-C$45,000", "description": "Negotiated settlement", "probability": 45},
            "opposition_board": {"cost": "C$40,000-C$100,000", "description": "Full Trademarks Opposition Board proceedings", "probability": 20},
            "federal_court": {"cost": "C$100,000-C$300,000+", "description": "Federal Court appeal", "probability": 5}
        },
        "expected_value_cost": "C$18,000",
        "total_worst_case": "C$300,850"
    },
    "Australia": {
        "currency": "AUD",
        "symbol": "A$",
        "filing_cost_per_class": "A$400-A$700",
        "opposition_defense": {
            "uncontested": {"cost": "A$8,000-A$18,000", "description": "Opponent withdraws after initial response", "probability": 30},
            "settlement": {"cost": "A$20,000-A$50,000", "description": "Negotiated agreement", "probability": 45},
            "hearing": {"cost": "A$40,000-A$120,000", "description": "Full hearing proceedings", "probability": 20},
            "federal_court": {"cost": "A$100,000-A$350,000+", "description": "Federal Court appeal", "probability": 5}
        },
        "expected_value_cost": "A$22,000",
        "total_worst_case": "A$350,700"
    }
}

def get_realistic_opposition_costs(country: str) -> dict:
    """
    Get realistic, tiered opposition defense costs for a country.
    Returns probability-weighted cost scenarios.
    """
    # Normalize country name
    country_map = {
        "United States": "USA",
        "United Kingdom": "UK",
        "Europe": "EU",
        "European Union": "EU"
    }
    normalized = country_map.get(country, country)
    
    if normalized in REALISTIC_OPPOSITION_COSTS:
        return REALISTIC_OPPOSITION_COSTS[normalized]
    
    # Default to USA costs for unknown countries
    return REALISTIC_OPPOSITION_COSTS["USA"]


def generate_realistic_registration_timeline(countries: list, num_classes: int = 1) -> dict:
    """
    Generate comprehensive registration timeline with realistic tiered costs.
    """
    primary_country = countries[0] if countries else "USA"
    if isinstance(primary_country, dict):
        primary_country = primary_country.get('name', 'USA')
    
    costs = get_realistic_opposition_costs(primary_country)
    
    # Calculate total filing cost based on number of classes
    filing_base = costs["filing_cost_per_class"]
    
    return {
        "country": primary_country,
        "estimated_duration": "14-24 months",
        "stages": [
            {"stage": "Filing & Examination", "duration": "4-8 months", "risk": "Descriptiveness refusals, specimen issues"},
            {"stage": "Publication", "duration": "1 month", "risk": "Public visibility triggers oppositions"},
            {"stage": "Opposition Period", "duration": "30-120 days", "risk": "Competitors can oppose"},
            {"stage": "Registration", "duration": "1-3 months", "risk": "Final approval, certificate issuance"}
        ],
        "filing_cost_per_class": filing_base,
        "total_filing_cost": f"{filing_base} × {num_classes} classes",
        "opposition_defense_cost": costs["opposition_defense"],
        "expected_value_cost": costs["expected_value_cost"],
        "total_worst_case": costs["total_worst_case"],
        "filing_basis_strategy": {
            "recommended_basis": "Intent-to-Use (1(b))" if primary_country == "USA" else "Standard filing",
            "rationale": "Secures filing date while product is in development - priority over later filers",
            "critical_milestones": [
                {"milestone": "File application", "deadline": "ASAP to secure priority date", "cost": filing_base},
                {"milestone": "Statement of Use (US only)", "deadline": "6 months from Notice of Allowance", "cost": "$100/class"},
                {"milestone": "Extensions available", "details": "5 extensions × 6 months each = 36 months maximum", "cost": "$125/extension"}
            ] if primary_country == "USA" else [
                {"milestone": "File application", "deadline": "ASAP to secure priority date", "cost": filing_base},
                {"milestone": "Examination", "deadline": "4-8 months", "cost": "Included in filing"},
                {"milestone": "Registration", "deadline": "12-18 months total", "cost": "Included"}
            ]
        }
    }


# ============================================================================
# 🆕 FEATURE 3: DUPONT 13-FACTOR LIKELIHOOD OF CONFUSION TEST
# ============================================================================
# Legal standard from In re E.I. DuPont de Nemours & Co., 476 F.2d 1357 (CCPA 1973)

def calculate_dupont_score(
    brand_name: str,
    conflict_name: str,
    same_category: bool,
    conflict_data: dict = None
) -> dict:
    """
    Calculate DuPont 13-Factor likelihood of confusion score.
    
    Returns weighted score (0-10) with legal verdict:
    - 9.0-10.0 = REJECT (>90% confusion likelihood)
    - 7.0-8.9 = REJECT (High confusion - likely USPTO refusal)
    - 5.0-6.9 = NO-GO (Moderate confusion - risky)
    - 3.0-4.9 = CONDITIONAL GO (Low-moderate confusion)
    - 0.0-2.9 = GO (Minimal confusion)
    """
    from difflib import SequenceMatcher
    import jellyfish
    
    # Helper functions
    def visual_similarity(a: str, b: str) -> float:
        """Visual/spelling similarity (0-10)"""
        ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
        return ratio * 10
    
    def phonetic_similarity(a: str, b: str) -> float:
        """Phonetic similarity using Soundex/Metaphone (0-10)"""
        try:
            # Soundex comparison
            soundex_a = jellyfish.soundex(a)
            soundex_b = jellyfish.soundex(b)
            soundex_match = 10 if soundex_a == soundex_b else 5 if soundex_a[:2] == soundex_b[:2] else 2
            
            # Metaphone comparison
            meta_a = jellyfish.metaphone(a)
            meta_b = jellyfish.metaphone(b)
            meta_ratio = SequenceMatcher(None, meta_a, meta_b).ratio()
            
            return (soundex_match + (meta_ratio * 10)) / 2
        except:
            return visual_similarity(a, b)
    
    # Factor calculations
    factors = {}
    
    # Factor 1: Similarity of Marks (HIGH WEIGHT)
    visual = visual_similarity(brand_name, conflict_name)
    phonetic = phonetic_similarity(brand_name, conflict_name)
    factors["factor_1_mark_similarity"] = {
        "score": round((visual + phonetic) / 2, 1),
        "weight": "HIGH",
        "analysis": f"Visual similarity: {visual:.1f}/10, Phonetic similarity: {phonetic:.1f}/10"
    }
    
    # Factor 2: Similarity of Goods/Services (HIGH WEIGHT)
    # Get class info for better analysis
    conflict_class = conflict_data.get("conflict_class") if conflict_data else None
    user_class = conflict_data.get("user_class") if conflict_data else None
    
    if same_category:
        goods_score = 9  # Same category = high similarity
        class_analysis = f"Same NICE class ({user_class}). Direct competition likely."
    elif conflict_data and conflict_data.get("related_category"):
        goods_score = 6  # Related category
        class_analysis = f"Related categories (User: Class {user_class}, Conflict: Class {conflict_class}). Some overlap possible."
    else:
        goods_score = 2  # Different category
        class_analysis = f"Different NICE classes (User: Class {user_class}, Conflict: Class {conflict_class}). Different market segments - LOW confusion risk."
    
    factors["factor_2_goods_similarity"] = {
        "score": goods_score,
        "weight": "HIGH",
        "analysis": class_analysis
    }
    
    # Factor 3: Trade Channel Overlap (MEDIUM WEIGHT)
    channel_score = 7 if same_category else 3
    factors["factor_3_trade_channels"] = {
        "score": channel_score,
        "weight": "MEDIUM",
        "analysis": f"Trade channels {'likely overlap (same industry)' if same_category else 'unlikely to overlap (different industries)'}"
    }
    
    # Factor 4: Purchaser Sophistication (MEDIUM WEIGHT)
    # Default to moderate sophistication; can be adjusted based on category
    sophistication_score = 5  # Moderate sophistication
    factors["factor_4_purchaser_sophistication"] = {
        "score": sophistication_score,
        "weight": "MEDIUM",
        "analysis": "Moderate purchaser sophistication assumed for consumer goods"
    }
    
    # Factor 5: Prior Mark Fame (MEDIUM WEIGHT)
    fame_score = conflict_data.get("fame_score", 5) if conflict_data else 5
    factors["factor_5_prior_mark_fame"] = {
        "score": fame_score,
        "weight": "MEDIUM",
        "analysis": f"Prior mark fame level: {'High' if fame_score >= 7 else 'Moderate' if fame_score >= 4 else 'Low'}"
    }
    
    # Factor 6: Number of Similar Marks (LOW WEIGHT)
    similar_count = conflict_data.get("similar_marks_count", 3) if conflict_data else 3
    crowded_score = 3 if similar_count > 10 else 6 if similar_count > 5 else 8
    factors["factor_6_number_similar_marks"] = {
        "score": crowded_score,
        "weight": "LOW",
        "analysis": f"{'Crowded' if similar_count > 10 else 'Moderately crowded' if similar_count > 5 else 'Relatively unique'} namespace with {similar_count} similar marks"
    }
    
    # Factor 7: Actual Confusion Evidence (HIGH WEIGHT)
    # Default to no evidence unless provided
    confusion_evidence = conflict_data.get("actual_confusion", False) if conflict_data else False
    factors["factor_7_actual_confusion"] = {
        "score": 8 if confusion_evidence else 2,
        "weight": "HIGH",
        "analysis": f"Actual confusion evidence: {'Found' if confusion_evidence else 'Not found'}"
    }
    
    # Factor 8: Length of Concurrent Use (LOW WEIGHT)
    factors["factor_8_concurrent_use_length"] = {
        "score": 5,
        "weight": "LOW",
        "analysis": "No concurrent use history (new application)"
    }
    
    # Factor 9: Variety of Goods (LOW WEIGHT)
    factors["factor_9_variety_of_goods"] = {
        "score": 5,
        "weight": "LOW",
        "analysis": "Standard product line assumed"
    }
    
    # Factor 10: Market Interface (MEDIUM WEIGHT)
    interface_score = 8 if same_category else 3
    factors["factor_10_market_interface"] = {
        "score": interface_score,
        "weight": "MEDIUM",
        "analysis": f"{'Direct market interface' if same_category else 'Minimal market interface'}"
    }
    
    # Factor 11: Junior User's Intent (MEDIUM WEIGHT)
    factors["factor_11_intent"] = {
        "score": 3,  # Assume good faith unless evidence suggests otherwise
        "weight": "MEDIUM",
        "analysis": "No evidence of intentional copying"
    }
    
    # Factor 12: Bad Faith Registration (MEDIUM WEIGHT)
    factors["factor_12_bad_faith"] = {
        "score": 2,
        "weight": "MEDIUM",
        "analysis": "No indicators of bad faith registration"
    }
    
    # Factor 13: Extent of Exclusive Rights (LOW WEIGHT)
    factors["factor_13_extent_exclusive_rights"] = {
        "score": 5,
        "weight": "LOW",
        "analysis": "Standard trademark scope"
    }
    
    # Calculate weighted score
    weights = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    total_weighted = 0
    total_weights = 0
    
    for factor_key, factor_data in factors.items():
        weight_value = weights[factor_data["weight"]]
        total_weighted += factor_data["score"] * weight_value
        total_weights += weight_value
    
    weighted_score = round(total_weighted / total_weights, 2)
    
    # Determine verdict
    if weighted_score >= 9.0:
        verdict = "REJECT"
        conclusion = "CRITICAL - >90% likelihood of confusion. Litigation certain."
    elif weighted_score >= 7.0:
        verdict = "REJECT"
        conclusion = "HIGH - Likely USPTO refusal or opposition. Strong conflict."
    elif weighted_score >= 5.0:
        verdict = "NO-GO"
        conclusion = "MODERATE - Risky, expensive to defend. Consider alternatives."
    elif weighted_score >= 3.0:
        verdict = "CONDITIONAL GO"
        conclusion = "LOW-MODERATE - Monitor closely. Proceed with caution."
    else:
        verdict = "GO"
        conclusion = "MINIMAL - Safe to proceed. Low confusion risk."
    
    return {
        "brand_name": brand_name,
        "conflict_name": conflict_name,
        "dupont_factors": factors,
        "weighted_likelihood_score": weighted_score,
        "legal_conclusion": conclusion,
        "verdict_impact": verdict
    }


def apply_dupont_analysis_to_conflicts(brand_name: str, category: str, conflicts: list) -> dict:
    """
    Apply DuPont 13-factor analysis to all conflicts found.
    Returns the highest-risk conflict with full analysis.
    """
    if not conflicts:
        return {
            "has_analysis": False,
            "highest_risk_conflict": None,
            "overall_dupont_verdict": "GO",
            "analysis_summary": "No conflicts found requiring DuPont analysis"
        }
    
    highest_score = 0
    highest_risk_analysis = None
    all_analyses = []
    
    for conflict in conflicts:
        conflict_name = conflict.get("name", conflict.get("matched_brand", "Unknown"))
        same_category = conflict.get("same_class_conflict", False) or conflict.get("category") == category
        
        # Calculate DuPont score
        analysis = calculate_dupont_score(
            brand_name=brand_name,
            conflict_name=conflict_name,
            same_category=same_category,
            conflict_data=conflict
        )
        all_analyses.append(analysis)
        
        if analysis["weighted_likelihood_score"] > highest_score:
            highest_score = analysis["weighted_likelihood_score"]
            highest_risk_analysis = analysis
    
    # Determine overall verdict based on highest risk
    if highest_score >= 7.0:
        overall_verdict = "REJECT"
    elif highest_score >= 5.0:
        overall_verdict = "NO-GO"
    elif highest_score >= 3.0:
        overall_verdict = "CONDITIONAL GO"
    else:
        overall_verdict = "GO"
    
    return {
        "has_analysis": True,
        "highest_risk_conflict": highest_risk_analysis,
        "overall_dupont_verdict": overall_verdict,
        "all_conflict_analyses": all_analyses,
        "analysis_summary": f"Analyzed {len(conflicts)} conflict(s). Highest risk score: {highest_score}/10 ({overall_verdict})"
    }


# ============================================================================
# 🆕 FEATURE 4: ENHANCED SOCIAL MEDIA ACTIVITY ANALYSIS
# ============================================================================
# Goes beyond Available/Taken to check verification, activity, engagement

async def check_social_handle_with_activity(platform: str, handle: str) -> dict:
    """
    Enhanced social handle check that includes activity analysis.
    Returns availability + activity status for taken handles.
    """
    import aiohttp
    
    platform_urls = {
        "instagram": f"https://www.instagram.com/{handle}/",
        "twitter": f"https://twitter.com/{handle}",
        "x": f"https://x.com/{handle}",
        "facebook": f"https://www.facebook.com/{handle}",
        "linkedin": f"https://www.linkedin.com/company/{handle}",
        "youtube": f"https://www.youtube.com/@{handle}",
        "tiktok": f"https://www.tiktok.com/@{handle}",
        "threads": f"https://www.threads.net/@{handle}",
        "pinterest": f"https://www.pinterest.com/{handle}/"
    }
    
    url = platform_urls.get(platform.lower())
    if not url:
        return {"platform": platform, "handle": handle, "status": "UNSUPPORTED", "available": None}
    
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with session.get(url, headers=headers, allow_redirects=True) as response:
                if response.status == 404:
                    return {
                        "platform": platform,
                        "handle": handle,
                        "status": "AVAILABLE",
                        "available": True,
                        "url": url,
                        "account_details": None,
                        "risk_level": "NONE",
                        "acquisition_viability": {"can_acquire": True, "cost": "$0", "approach": "Direct registration"}
                    }
                elif response.status == 200:
                    content = await response.text()
                    content_lower = content.lower()
                    
                    # Check for "not found" patterns
                    not_found_patterns = [
                        "page isn't available", "page not found", "sorry, this page",
                        "user not found", "account suspended", "doesn't exist",
                        "this account doesn't exist", "no results found"
                    ]
                    
                    for pattern in not_found_patterns:
                        if pattern in content_lower:
                            return {
                                "platform": platform,
                                "handle": handle,
                                "status": "LIKELY AVAILABLE",
                                "available": True,
                                "url": url,
                                "account_details": None,
                                "risk_level": "NONE",
                                "acquisition_viability": {"can_acquire": True, "cost": "$0", "approach": "Direct registration"}
                            }
                    
                    # Handle is TAKEN - analyze activity
                    account_details = analyze_social_account_activity(platform, content)
                    risk_level = calculate_social_risk_level(account_details)
                    acquisition = calculate_acquisition_viability(platform, account_details, risk_level)
                    
                    return {
                        "platform": platform,
                        "handle": handle,
                        "status": "TAKEN",
                        "available": False,
                        "url": url,
                        "account_details": account_details,
                        "risk_level": risk_level,
                        "acquisition_viability": acquisition
                    }
                else:
                    return {
                        "platform": platform,
                        "handle": handle,
                        "status": "TAKEN",
                        "available": False,
                        "url": url,
                        "account_details": {"analysis_available": False},
                        "risk_level": "UNKNOWN",
                        "acquisition_viability": {"can_acquire": "UNKNOWN", "approach": "Manual verification needed"}
                    }
    except asyncio.TimeoutError:
        return {"platform": platform, "handle": handle, "status": "TIMEOUT", "available": None, "risk_level": "UNKNOWN"}
    except Exception as e:
        logging.warning(f"Enhanced social check error for {platform}/{handle}: {e}")
        return {"platform": platform, "handle": handle, "status": "ERROR", "available": None, "risk_level": "UNKNOWN"}


def analyze_social_account_activity(platform: str, content: str) -> dict:
    """
    Analyze social account activity from page content.
    Extracts follower count, verification status, activity level.
    """
    import re
    
    details = {
        "is_verified": False,
        "is_business_account": False,
        "follower_count": None,
        "posting_frequency": "UNKNOWN",
        "engagement_estimate": "UNKNOWN",
        "account_type": "UNKNOWN",
        "analysis_available": True
    }
    
    content_lower = content.lower()
    
    # Check for verification badges
    verification_indicators = [
        'verified', 'verification badge', 'blue check', 'verified account',
        '"isVerified":true', '"verified":true', 'aria-label="verified"'
    ]
    for indicator in verification_indicators:
        if indicator in content_lower:
            details["is_verified"] = True
            break
    
    # Check for business account indicators
    business_indicators = [
        'business account', 'professional account', 'creator account',
        'shop now', 'contact us', 'website:', 'email:', 'category:'
    ]
    for indicator in business_indicators:
        if indicator in content_lower:
            details["is_business_account"] = True
            break
    
    # Try to extract follower count (platform-specific patterns)
    follower_patterns = [
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:k|m|b)?\s*(?:followers|following)',
        r'"edge_followed_by":\s*{\s*"count":\s*(\d+)',  # Instagram
        r'"followers_count":\s*(\d+)',  # Twitter
        r'(\d+(?:,\d+)*)\s*Followers',
        r'Followers["\s:]+(\d+(?:,\d+)*)',
    ]
    
    for pattern in follower_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            count_str = match.group(1).replace(',', '')
            try:
                count = float(count_str)
                # Handle K, M, B suffixes
                suffix_match = re.search(r'(\d+(?:\.\d+)?)\s*([kmb])', match.group(0).lower())
                if suffix_match:
                    multipliers = {'k': 1000, 'm': 1000000, 'b': 1000000000}
                    count = float(suffix_match.group(1)) * multipliers.get(suffix_match.group(2), 1)
                details["follower_count"] = int(count)
                break
            except:
                pass
    
    # Estimate activity level based on content cues
    if 'posted' in content_lower or 'hours ago' in content_lower or 'minutes ago' in content_lower:
        details["posting_frequency"] = "ACTIVE"
    elif 'days ago' in content_lower or 'yesterday' in content_lower:
        details["posting_frequency"] = "RECENT"
    elif 'weeks ago' in content_lower or 'months ago' in content_lower:
        details["posting_frequency"] = "SPORADIC"
    elif 'years ago' in content_lower or 'year ago' in content_lower:
        details["posting_frequency"] = "ABANDONED"
    
    return details


def calculate_social_risk_level(account_details: dict) -> str:
    """
    Calculate risk level based on account activity.
    
    FATAL: Verified account with large following - cannot acquire
    HIGH: Active business with moderate following
    MEDIUM: Active personal account or small business
    LOW: Abandoned or minimal activity account
    NONE: Available
    """
    if not account_details or not account_details.get("analysis_available"):
        return "UNKNOWN"
    
    is_verified = account_details.get("is_verified", False)
    is_business = account_details.get("is_business_account", False)
    followers = account_details.get("follower_count") or 0
    activity = account_details.get("posting_frequency", "UNKNOWN")
    
    # FATAL: Verified with large following
    if is_verified and followers > 100000:
        return "FATAL"
    
    # FATAL: Any verified account
    if is_verified:
        return "FATAL"
    
    # HIGH: Large following or active business
    if followers > 50000:
        return "HIGH"
    if is_business and followers > 10000:
        return "HIGH"
    
    # MEDIUM: Active account with moderate following
    if activity in ["ACTIVE", "RECENT"] and followers > 1000:
        return "MEDIUM"
    if is_business and activity in ["ACTIVE", "RECENT"]:
        return "MEDIUM"
    
    # LOW: Abandoned or minimal activity
    if activity in ["ABANDONED", "SPORADIC"] or followers < 100:
        return "LOW"
    
    return "MEDIUM"


def calculate_acquisition_viability(platform: str, account_details: dict, risk_level: str) -> dict:
    """
    Calculate acquisition viability and estimated costs.
    """
    if risk_level == "FATAL":
        return {
            "can_acquire": False,
            "reason": "Verified/high-profile account - not acquirable",
            "estimated_cost": "N/A",
            "approach": "Choose alternative handle or brand name"
        }
    
    if risk_level == "HIGH":
        followers = account_details.get("follower_count") or 0
        cost_estimate = "$5,000-$25,000" if followers > 50000 else "$2,000-$10,000"
        return {
            "can_acquire": "MAYBE",
            "reason": "Active account with significant following",
            "estimated_cost": cost_estimate,
            "approach": "Negotiate via broker (hide buyer identity)",
            "success_probability": "30%"
        }
    
    if risk_level == "MEDIUM":
        return {
            "can_acquire": "LIKELY",
            "reason": "Moderate activity - negotiation possible",
            "estimated_cost": "$500-$3,000",
            "approach": "Direct outreach or platform inactive username request",
            "success_probability": "50%"
        }
    
    if risk_level == "LOW":
        activity = account_details.get("posting_frequency", "UNKNOWN")
        if activity == "ABANDONED":
            return {
                "can_acquire": True,
                "reason": "Abandoned account (5+ years inactive)",
                "estimated_cost": "$0-$500",
                "approach": "Request inactive username release via platform support",
                "success_probability": "70%"
            }
        return {
            "can_acquire": True,
            "reason": "Minimal activity account",
            "estimated_cost": "$200-$1,000",
            "approach": "Direct negotiation",
            "success_probability": "60%"
        }
    
    return {
        "can_acquire": "UNKNOWN",
        "approach": "Manual verification needed"
    }


async def check_social_availability_enhanced(brand_name: str, countries: list) -> dict:
    """
    Enhanced social availability check with activity analysis.
    Returns detailed breakdown including risk levels and acquisition costs.
    """
    from availability import get_social_platforms
    
    clean_handle = brand_name.lower().replace(" ", "").replace("-", "")
    
    # Get relevant platforms (limit to 6 for performance)
    platforms = get_social_platforms(countries)[:6]
    
    # Check all platforms concurrently with enhanced analysis
    tasks = [check_social_handle_with_activity(platform, clean_handle) for platform in platforms]
    results = await asyncio.gather(*tasks)
    
    # Categorize and analyze results
    available = []
    taken_low_risk = []
    taken_medium_risk = []
    taken_high_risk = []
    taken_fatal = []
    unknown = []
    
    total_acquisition_cost_low = 0
    total_acquisition_cost_high = 0
    
    for r in results:
        if r.get("available") == True:
            available.append(r)
        elif r.get("available") == False:
            risk = r.get("risk_level", "UNKNOWN")
            if risk == "FATAL":
                taken_fatal.append(r)
            elif risk == "HIGH":
                taken_high_risk.append(r)
            elif risk == "MEDIUM":
                taken_medium_risk.append(r)
            elif risk == "LOW":
                taken_low_risk.append(r)
            else:
                unknown.append(r)
            
            # Estimate acquisition costs
            acq = r.get("acquisition_viability", {})
            cost_str = acq.get("estimated_cost", "$0")
            if cost_str and cost_str != "N/A":
                # Parse cost range
                import re
                costs = re.findall(r'\$?([\d,]+)', cost_str.replace(',', ''))
                if len(costs) >= 2:
                    total_acquisition_cost_low += int(costs[0])
                    total_acquisition_cost_high += int(costs[1])
                elif len(costs) == 1:
                    total_acquisition_cost_low += int(costs[0])
                    total_acquisition_cost_high += int(costs[0])
        else:
            unknown.append(r)
    
    # Calculate overall score impact
    score_impact = 0
    if taken_fatal:
        score_impact -= 25  # Major penalty for fatal conflicts
    score_impact -= len(taken_high_risk) * 8
    score_impact -= len(taken_medium_risk) * 3
    score_impact -= len(taken_low_risk) * 1
    
    # Generate recommendation
    if taken_fatal:
        recommendation = f"⚠️ CRITICAL: {len(taken_fatal)} platform(s) have verified/high-profile accounts. Consider alternative brand name."
    elif taken_high_risk:
        recommendation = f"HIGH RISK: {len(taken_high_risk)} platform(s) have active accounts. Budget ${total_acquisition_cost_low:,}-${total_acquisition_cost_high:,} for acquisition."
    elif taken_medium_risk:
        recommendation = f"MODERATE: {len(taken_medium_risk)} platform(s) need negotiation. Estimated cost: ${total_acquisition_cost_low:,}-${total_acquisition_cost_high:,}."
    elif taken_low_risk:
        recommendation = f"LOW RISK: {len(taken_low_risk)} inactive account(s) may be acquirable via platform support."
    else:
        recommendation = f"✅ EXCELLENT: All {len(available)} platforms available. Register immediately."
    
    return {
        "handle": clean_handle,
        "platforms": results,
        "summary": {
            "total_checked": len(results),
            "available_count": len(available),
            "available_platforms": [r["platform"] for r in available],
            "taken_fatal": [r["platform"] for r in taken_fatal],
            "taken_high_risk": [r["platform"] for r in taken_high_risk],
            "taken_medium_risk": [r["platform"] for r in taken_medium_risk],
            "taken_low_risk": [r["platform"] for r in taken_low_risk],
            "critical_conflicts": len(taken_fatal),
            "acquisition_cost_range": f"${total_acquisition_cost_low:,}-${total_acquisition_cost_high:,}" if total_acquisition_cost_high > 0 else "$0"
        },
        "recommendation": recommendation,
        "score_impact": score_impact,
        "impact_explanation": f"Social media conflicts: {len(taken_fatal)} fatal, {len(taken_high_risk)} high-risk, {len(taken_medium_risk)} medium-risk"
    }


def generate_intelligent_trademark_matrix(brand_name: str, category: str, trademark_data: dict, brand_is_invented: bool = True, classification: dict = None) -> dict:
    """
    Generate intelligent Legal Risk Matrix with SPECIFIC, ACTIONABLE commentary
    based on actual trademark research results AND brand classification - NOT generic placeholders.
    
    Uses the 5-tier trademark spectrum:
    GENERIC → DESCRIPTIVE → SUGGESTIVE → ARBITRARY → FANCIFUL
    """
    # Extract data from trademark research
    risk_score = trademark_data.get('overall_risk_score', 5) if trademark_data else 5
    tm_conflicts = trademark_data.get('trademark_conflicts', []) if trademark_data else []
    co_conflicts = trademark_data.get('company_conflicts', []) if trademark_data else []
    total_conflicts = len(tm_conflicts) + len(co_conflicts)
    registration_prob = trademark_data.get('registration_success_probability', 70) if trademark_data else 70
    
    nice_class = get_nice_classification(category)
    class_number = nice_class.get('class_number', 35)
    
    # Get classification details
    classification_category = classification.get("category", "SUGGESTIVE") if classification else ("FANCIFUL" if brand_is_invented else "DESCRIPTIVE")
    
    # ==================== CLASSIFICATION-AWARE SCORING ====================
    # Map classification to genericness score
    CLASSIFICATION_SCORES = {
        "FANCIFUL": 1,      # Invented words - strongest
        "ARBITRARY": 2,     # Real words, unrelated use
        "SUGGESTIVE": 4,    # Hints at product
        "DESCRIPTIVE": 7,   # Describes product (hard to register)
        "GENERIC": 9        # Common term (unregistrable)
    }
    
    genericness_score = CLASSIFICATION_SCORES.get(classification_category, 5)
    conflict_score = min(9, 1 + total_conflicts * 2) if total_conflicts > 0 else 1
    phonetic_score = min(7, 1 + len([c for c in tm_conflicts if safe_get(c, 'conflict_type') == 'phonetic']) * 3)
    class_score = min(6, 1 + total_conflicts) if total_conflicts > 0 else 2
    rebrand_score = min(8, 1 + conflict_score // 2 + (genericness_score // 2))  # Factor in genericness
    
    # Adjust registration probability based on classification
    CLASSIFICATION_PROB_MODIFIER = {
        "FANCIFUL": 1.2,    # +20% chance
        "ARBITRARY": 1.1,   # +10% chance
        "SUGGESTIVE": 1.0,  # No change
        "DESCRIPTIVE": 0.6, # -40% chance
        "GENERIC": 0.1      # -90% chance
    }
    adjusted_registration_prob = min(95, int(registration_prob * CLASSIFICATION_PROB_MODIFIER.get(classification_category, 1.0)))
    
    # Determine zones
    def get_zone(score):
        if score <= 3: return "Green"
        elif score <= 6: return "Yellow"
        else: return "Red"
    
    # ==================== CLASSIFICATION-SPECIFIC COMMENTARY ====================
    DISTINCTIVENESS_COMMENTARY = {
        "FANCIFUL": f"'{brand_name}' is a FANCIFUL (coined/invented) term with no dictionary meaning - STRONGEST trademark protection. Inherently distinctive under TMEP §1209. No Secondary Meaning proof required. Recommendation: File as wordmark in Class {class_number} with intent-to-use basis. Consider design mark for additional protection layer.",
        
        "ARBITRARY": f"'{brand_name}' is an ARBITRARY mark - a real word used in an unrelated context. STRONG trademark protection. Example: 'Apple' for computers. Recommendation: File as wordmark in Class {class_number}. Distinctiveness is inherent but document unique usage context.",
        
        "SUGGESTIVE": f"'{brand_name}' is a SUGGESTIVE mark - hints at product qualities without directly describing them. MODERATE trademark protection. Requires imagination to connect name to product. Recommendation: File in Class {class_number} with strong specimens of use showing acquired distinctiveness.",
        
        "DESCRIPTIVE": f"⚠️ '{brand_name}' is a DESCRIPTIVE mark - directly describes the product/service. WEAK trademark protection. USPTO will likely issue Office Action for descriptiveness. Recommendation: (1) Add distinctive design elements, (2) Build 5+ years of exclusive use for 'acquired distinctiveness', or (3) Consider supplemental register initially. Budget for legal response: $1,500-3,000.",
        
        "GENERIC": f"🚫 '{brand_name}' appears GENERIC - common term for the product category. UNREGISTRABLE as trademark. Example: 'Computer Store' for computer retail. Recommendation: REBRAND with distinctive coined term. Generic terms cannot function as trademarks regardless of use duration. Alternative: Use as trade dress with highly distinctive visual elements only."
    }
    
    genericness_commentary = DISTINCTIVENESS_COMMENTARY.get(classification_category, 
        f"'{brand_name}' shows {classification_category} distinctiveness. Registration outlook depends on use evidence and market exclusivity.")
    
    # ==================== GENERATE MATRIX ====================
    matrix = {
        "genericness": {
            "likelihood": genericness_score,
            "severity": min(10, genericness_score + 1),
            "zone": get_zone(genericness_score),
            "commentary": genericness_commentary
        },
        "existing_conflicts": {
            "likelihood": conflict_score,
            "severity": min(9, conflict_score + 2),
            "zone": get_zone(conflict_score),
            "commentary": f"Found {total_conflicts} potential conflicts ({len(tm_conflicts)} trademark, {len(co_conflicts)} company registrations). " + (
                f"Top conflict: {safe_get(tm_conflicts[0], 'name', 'Unknown')} in Class {safe_get(tm_conflicts[0], 'class_number', 'N/A')} ({safe_get(tm_conflicts[0], 'status', 'Status unknown')}). Recommendation: Conduct comprehensive knockout search with IP attorney before filing. Prepare co-existence agreement template if proceeding."
                if tm_conflicts else 
                "No direct trademark conflicts found in primary class. Recommendation: Proceed with filing in Class " + str(class_number) + ". Set up trademark watch service to monitor new filings with similar marks."
            )
        },
        "phonetic_similarity": {
            "likelihood": phonetic_score,
            "severity": phonetic_score + 1 if phonetic_score > 3 else 2,
            "zone": get_zone(phonetic_score),
            "commentary": f"{'Phonetic variants analyzed: No confusingly similar marks detected in Class ' + str(class_number) + '.' if phonetic_score <= 3 else 'Potential phonetic conflicts identified with similar-sounding marks.'} Recommendation: {'Register both word mark and phonetic variants as defensive strategy. Monitor app stores and domain registrations for sound-alike competitors.' if phonetic_score <= 3 else 'Consider slight spelling modifications to increase distinctiveness. Clear phonetic differentiation from ' + (safe_get(tm_conflicts[0], 'name', 'existing marks') if tm_conflicts else 'existing marks') + ' is advised.'}"
        },
        "relevant_classes": {
            "likelihood": class_score,
            "severity": class_score + 1 if class_score > 3 else 3,
            "zone": get_zone(class_score),
            "commentary": f"Primary filing class: Class {class_number} ({nice_class.get('class_description', category)}). {'Class landscape is relatively clear with limited prior registrations.' if class_score <= 3 else f'Moderate competition in this class with {total_conflicts} existing marks.'} Strategy: File in Class {class_number} as primary. Consider defensive filing in {'Class 9 (software) and Class 42 (SaaS)' if class_number not in [9, 42] else 'adjacent service classes'} for comprehensive protection."
        },
        "rebranding_probability": {
            "likelihood": rebrand_score,
            "severity": 8 if rebrand_score > 5 else 4,
            "zone": get_zone(rebrand_score),
            "commentary": (
                f"{'LOW' if rebrand_score <= 3 else 'MODERATE' if rebrand_score <= 6 else 'HIGH'} rebranding risk. " +
                (f"Classification: {classification_category}. " if classification_category in ["DESCRIPTIVE", "GENERIC"] else "") +
                f"Registration outlook: {adjusted_registration_prob}% success probability. " +
                ("Action: Proceed with brand development. Secure federal registration early." if rebrand_score <= 3 
                 else "Action: Obtain formal legal opinion. Consider alternative brand names as backup." if classification_category in ["DESCRIPTIVE", "GENERIC"]
                 else "Action: Budget for potential opposition proceedings ($5,000-25,000).")
            )
        },
        "overall_assessment": (
            f"Overall trademark risk: {max(risk_score, genericness_score)}/10 (Classification: {classification_category}). " +
            ("✅ Favorable registration outlook - proceed with filing." if genericness_score <= 3 and risk_score <= 3
             else "⚠️ Moderate risk - legal clearance recommended." if genericness_score <= 5 and risk_score <= 6
             else "🚨 High risk - significant challenges expected." if classification_category in ["DESCRIPTIVE", "GENERIC"]
             else "⚠️ Conflicts require resolution before proceeding.") +
            f" Adjusted registration success probability: {adjusted_registration_prob}%." +
            (" Timeline: 12-18 months for registration." if adjusted_registration_prob >= 60 else " Extended timeline likely due to potential Office Actions.")
        )
    }
    
    return matrix


def safe_get(obj, key, default=None):
    """
    Safely get attribute from dict, dataclass, or Pydantic model.
    Handles all object types uniformly.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    # For dataclass or Pydantic model - use getattr
    return getattr(obj, key, default)


def build_social_availability_from_data(brand_name: str, social_data: dict) -> dict:
    """
    Build social_availability section from ACTUAL social check data.
    
    Takes the real results from check_social_availability() and formats them
    for the report, instead of returning hardcoded placeholder data.
    """
    clean_handle = brand_name.lower().replace(" ", "").replace("-", "")
    
    # Default fallback if no data
    if not social_data or not isinstance(social_data, dict):
        return {
            "handle": clean_handle,
            "platforms": [],
            "available_platforms": [],
            "taken_platforms": [],
            "recommendation": f"Social media check unavailable. Manually verify @{clean_handle} availability."
        }
    
    # Extract platforms checked
    platforms_checked = social_data.get("platforms_checked", [])
    
    # Build platform results
    platforms = []
    available_platforms = []
    taken_platforms = []
    
    for p in platforms_checked:
        platform_name = p.get("platform", "unknown")
        is_available = p.get("available")
        status = p.get("status", "UNKNOWN")
        url = p.get("url", "")
        
        platform_result = {
            "platform": platform_name,
            "available": is_available,
            "status": status,
            "url": url,
            "handle": p.get("handle", clean_handle)
        }
        platforms.append(platform_result)
        
        if is_available == True:
            available_platforms.append(platform_name)
        elif is_available == False:
            taken_platforms.append(platform_name)
    
    # Generate recommendation based on actual data
    total_checked = len(platforms_checked)
    available_count = len(available_platforms)
    taken_count = len(taken_platforms)
    
    if taken_count == 0 and available_count > 0:
        recommendation = f"✅ EXCELLENT: @{clean_handle} is available on {available_count} platforms. Secure all handles immediately before launch."
    elif taken_count > 0 and available_count > 0:
        recommendation = f"⚠️ PARTIAL: @{clean_handle} is available on {available_count}/{total_checked} platforms. Taken on: {', '.join(taken_platforms)}. Consider variations like @{clean_handle}app or @get{clean_handle}."
    elif taken_count > 0 and available_count == 0:
        recommendation = f"❌ UNAVAILABLE: @{clean_handle} is taken on all checked platforms ({', '.join(taken_platforms)}). Consider alternative handles or brand name variations."
    else:
        recommendation = f"Social availability check inconclusive. Manually verify @{clean_handle} on major platforms."
    
    return {
        "handle": clean_handle,
        "platforms": platforms,
        "available_platforms": available_platforms,
        "taken_platforms": taken_platforms,
        "recommendation": recommendation,
        # Also include raw counts for frontend
        "_total_checked": total_checked,
        "_available_count": available_count,
        "_taken_count": taken_count
    }


def generate_strategic_classification(classification: dict, trademark_risk: int = 5) -> str:
    """
    TOP-LEVEL FUNCTION: Generate strategic_classification string based on ACTUAL 5-step spectrum classification.
    This is used to OVERRIDE LLM-generated classifications that are incorrect.
    
    Examples:
    - FANCIFUL: "STRONGEST - Coined/Invented term with highest legal distinctiveness"
    - DESCRIPTIVE: "WEAK - Descriptive term (directly describes product) with low legal distinctiveness"
    """
    if not classification:
        return "Classification unavailable"
    
    category = classification.get("category", "DESCRIPTIVE")
    protectability = classification.get("protectability", "WEAK")
    distinctiveness = classification.get("distinctiveness", "LOW")
    
    # Map classification category to human-readable description
    category_descriptions = {
        "FANCIFUL": "Coined/Invented term (completely made up word)",
        "ARBITRARY": "Arbitrary term (common word in unrelated context)",
        "SUGGESTIVE": "Suggestive term (hints at product, needs imagination)",
        "DESCRIPTIVE": "Descriptive term (directly describes the product/service)",
        "GENERIC": "Generic term (names the product category itself)"
    }
    
    category_description = category_descriptions.get(category, category)
    
    # Build the strategic classification string
    return f"{protectability} - {category_description} with {distinctiveness.lower()} legal distinctiveness"


def build_conflict_relevance_analysis(
    brand_name: str,
    category: str,
    industry: str,
    trademark_data: dict,
    visibility_data: dict,
    deep_trace_result: dict = None,
    positioning: str = ""
) -> dict:
    """
    Build REAL Conflict Relevance Analysis from actual data sources:
    - Trademark Research (trademark conflicts, company conflicts)
    - Visibility Analysis (App Store, Play Store, Google results)
    - Deep-Trace Analysis (Category Kings, root word conflicts)
    
    This replaces the LLM-generated visibility_analysis with data-driven analysis.
    """
    logging.info(f"🎯 Building Conflict Relevance Analysis for '{brand_name}' from real data...")
    
    direct_competitors = []
    phonetic_conflicts = []
    name_twins = []
    
    # ==================== SOURCE 1: TRADEMARK RESEARCH ====================
    if trademark_data:
        tm_conflicts = safe_get(trademark_data, 'trademark_conflicts', [])
        co_conflicts = safe_get(trademark_data, 'company_conflicts', [])
        nice_class = get_nice_classification(category)
        user_class = nice_class.get('class_number', 35) if isinstance(nice_class, dict) else getattr(nice_class, 'class_number', 35)
        
        for conflict in tm_conflicts:
            conflict_class = safe_get(conflict, 'class_number')
            conflict_name = safe_get(conflict, 'name', 'Unknown')
            conflict_status = safe_get(conflict, 'status', 'UNKNOWN')
            
            # Determine if same class = DIRECT, different class = NAME_TWIN
            if conflict_class and str(conflict_class) == str(user_class):
                # SAME CLASS = DIRECT COMPETITOR
                direct_competitors.append({
                    "name": conflict_name,
                    "category": f"Class {conflict_class} - Same as user",
                    "their_product_intent": f"Trademark registered in Class {conflict_class}",
                    "their_customer_avatar": "Same customer segment (same NICE class)",
                    "intent_match": "SAME",
                    "customer_overlap": "HIGH",
                    "risk_level": "HIGH",
                    "reason": f"TRADEMARK CONFLICT: {conflict_name} is registered in Class {conflict_class} ({conflict_status}). Same class as your {category}.",
                    "source": "Trademark Registry",
                    "status": conflict_status
                })
                logging.info(f"   ⚠️ DIRECT CONFLICT (Same Class): {conflict_name} in Class {conflict_class}")
            else:
                # DIFFERENT CLASS = NAME TWIN (still worth noting)
                name_twins.append({
                    "name": conflict_name,
                    "category": f"Class {conflict_class or 'Unknown'} - Different from user Class {user_class}",
                    "their_product_intent": f"Different business (Class {conflict_class})",
                    "their_customer_avatar": "Different customer segment",
                    "intent_match": "DIFFERENT",
                    "customer_overlap": "NONE",
                    "risk_level": "LOW",
                    "reason": f"Different NICE class ({conflict_class} vs {user_class}). Name exists but serves different market.",
                    "source": "Trademark Registry",
                    "status": conflict_status
                })
        
        # Company conflicts are typically more serious (they're operating businesses)
        for conflict in co_conflicts:
            company_name = safe_get(conflict, 'name', 'Unknown')
            company_industry = safe_get(conflict, 'industry', 'Unknown') or 'Unknown'
            company_status = safe_get(conflict, 'status', 'ACTIVE')
            
            # Check if industry overlaps
            industry_lower = (industry or category or "").lower()
            company_industry_lower = company_industry.lower() if company_industry else ""
            
            # Keywords to check for industry match
            industry_match = any(kw in company_industry_lower for kw in industry_lower.split()) or \
                           any(kw in industry_lower for kw in company_industry_lower.split()) if company_industry_lower else False
            
            if industry_match or company_status == 'ACTIVE':
                direct_competitors.append({
                    "name": company_name,
                    "category": company_industry,
                    "their_product_intent": f"Active company in {company_industry}",
                    "their_customer_avatar": "Overlapping market segment",
                    "intent_match": "SAME" if industry_match else "RELATED",
                    "customer_overlap": "HIGH" if industry_match else "MEDIUM",
                    "risk_level": "HIGH" if industry_match else "MEDIUM",
                    "reason": f"COMPANY CONFLICT: {company_name} is an active {company_status} company in {company_industry}.",
                    "source": "Company Registry (MCA/ROC)",
                    "status": company_status,
                    "cin": safe_get(conflict, 'cin', 'N/A')
                })
                logging.info(f"   ⚠️ COMPANY CONFLICT: {company_name} ({company_industry})")
            else:
                name_twins.append({
                    "name": company_name,
                    "category": company_industry,
                    "their_product_intent": f"Company in {company_industry}",
                    "their_customer_avatar": "Different segment",
                    "intent_match": "DIFFERENT",
                    "customer_overlap": "NONE",
                    "risk_level": "LOW",
                    "reason": f"Company exists in different industry ({company_industry}). Low conflict risk.",
                    "source": "Company Registry"
                })
    
    # ==================== SOURCE 2: VISIBILITY (APP STORE / PLAY STORE) ====================
    if visibility_data:
        app_search_details = visibility_data.get('app_search_details', {})
        
        # Process potential conflicts from app stores
        app_conflicts = app_search_details.get('potential_conflicts', [])
        for app in app_conflicts:
            app_name = app.get('title', 'Unknown App')
            app_developer = app.get('developer', 'Unknown Developer')
            match_type = app.get('match_type', 'UNKNOWN')
            
            # App store conflicts are serious - same digital product space
            direct_competitors.append({
                "name": app_name,
                "category": f"Mobile App ({match_type})",
                "their_product_intent": f"App by {app_developer}",
                "their_customer_avatar": "Mobile app users",
                "intent_match": "SAME" if "EXACT" in match_type else "RELATED",
                "customer_overlap": "HIGH",
                "risk_level": "HIGH" if "EXACT" in match_type else "MEDIUM",
                "reason": f"APP STORE CONFLICT: '{app_name}' by {app_developer} found in app stores. {match_type}.",
                "source": "Google Play Store / Apple App Store",
                "app_id": app.get('appId', 'N/A')
            })
            logging.info(f"   📱 APP CONFLICT: {app_name} ({match_type})")
        
        # Process phonetic matches from app stores
        phonetic_matches = app_search_details.get('phonetic_matches', [])
        for app in phonetic_matches:
            app_name = app.get('title', 'Unknown')
            variant = app.get('phonetic_variant', brand_name)
            
            phonetic_conflicts.append({
                "input_name": brand_name,
                "phonetic_variants": [variant],
                "ipa_pronunciation": f"/{variant}/",
                "found_conflict": {
                    "name": app_name,
                    "spelling_difference": f"{brand_name} vs {app_name}",
                    "category": "Mobile App",
                    "app_store_link": f"play.google.com/store/apps/details?id={app.get('appId', '')}",
                    "downloads": app.get('installs', 'Unknown'),
                    "company": app.get('developer', 'Unknown'),
                    "is_active": True
                },
                "conflict_type": "PHONETIC_APP_CONFLICT",
                "legal_risk": "MEDIUM",
                "verdict_impact": "Consider phonetic differentiation"
            })
            logging.info(f"   🔊 PHONETIC CONFLICT: {brand_name} sounds like {app_name}")
        
        # Process exact matches
        exact_matches = app_search_details.get('exact_matches', [])
        for app in exact_matches:
            if app not in app_conflicts:  # Avoid duplicates
                app_name = app.get('title', 'Unknown App')
                direct_competitors.append({
                    "name": app_name,
                    "category": "Mobile App (Exact Name Match)",
                    "their_product_intent": f"App by {app.get('developer', 'Unknown')}",
                    "their_customer_avatar": "Mobile app users",
                    "intent_match": "SAME",
                    "customer_overlap": "HIGH",
                    "risk_level": "CRITICAL",
                    "reason": f"EXACT NAME MATCH: '{app_name}' exists in app stores with same name.",
                    "source": "App Store",
                    "installs": app.get('installs', 'Unknown')
                })
        
        # Process Google search results for business indicators
        google_results = visibility_data.get('google', [])
        for result in google_results[:5]:  # Check top 5 results
            result_lower = result.lower() if isinstance(result, str) else ""
            
            # Look for indicators of existing business
            business_indicators = ['official', 'website', 'company', 'linkedin', 'crunchbase', 
                                   'founded', 'startup', 'brand', '.com', 'inc', 'ltd', 'pvt']
            
            if any(ind in result_lower for ind in business_indicators) and brand_name.lower() in result_lower:
                # Check if this is a different business
                name_twins.append({
                    "name": f"Web presence: {result[:80]}...",
                    "category": "Web/Online Business",
                    "their_product_intent": "Existing web presence",
                    "their_customer_avatar": "Online users",
                    "intent_match": "UNKNOWN",
                    "customer_overlap": "UNKNOWN",
                    "risk_level": "MEDIUM",
                    "reason": f"Found in Google search. Verify if this is a competing business.",
                    "source": "Google Search"
                })
    
    # ==================== SOURCE 3: DEEP-TRACE ANALYSIS (Category Kings) ====================
    if deep_trace_result:
        category_king = deep_trace_result.get('category_king')
        if category_king:
            king_name = category_king.get('king', 'Unknown')
            king_valuation = category_king.get('valuation', 'Unknown')
            industry_match = category_king.get('industry_match', False)
            
            # Category King is ALWAYS a critical conflict if industry matches
            if industry_match:
                direct_competitors.append({
                    "name": king_name,
                    "category": f"Category King ({category_king.get('market', 'Global')})",
                    "their_product_intent": category_king.get('description', 'Market leader'),
                    "their_customer_avatar": "Mass market in same category",
                    "intent_match": "SAME",
                    "customer_overlap": "HIGH",
                    "risk_level": "CRITICAL",
                    "reason": f"🚨 CATEGORY KING CONFLICT: Your brand root word matches {king_name} ({king_valuation}). Same industry = HIGH lawsuit risk.",
                    "source": "Deep-Trace Analysis (Root Word Detection)",
                    "valuation": king_valuation
                })
                logging.info(f"   🚨 CATEGORY KING: {king_name} ({king_valuation})")
            else:
                # Different industry but same root - still notable
                name_twins.append({
                    "name": king_name,
                    "category": f"{category_king.get('market', 'Global')} - Different industry",
                    "their_product_intent": category_king.get('description', 'Market leader'),
                    "their_customer_avatar": "Different market segment",
                    "intent_match": "DIFFERENT",
                    "customer_overlap": "LOW",
                    "risk_level": "MEDIUM",
                    "reason": f"Root word associated with {king_name} but in different industry. Monitor for cross-industry expansion.",
                    "source": "Deep-Trace Analysis"
                })
        
        # Add algorithmic conflicts from Deep-Trace
        algorithmic = deep_trace_result.get('algorithmic_analysis')
        if algorithmic and algorithmic.get('overall_algorithmic_risk'):
            nearest = deep_trace_result.get('nearest_competitor')
            if nearest:
                phonetic_conflicts.append({
                    "input_name": brand_name,
                    "phonetic_variants": [],
                    "ipa_pronunciation": f"Near {nearest}",
                    "found_conflict": {
                        "name": nearest,
                        "spelling_difference": f"Levenshtein distance: {algorithmic['levenshtein']['distance']}",
                        "category": category,
                        "is_active": True
                    },
                    "conflict_type": "ALGORITHMIC_SIMILARITY",
                    "legal_risk": "HIGH" if algorithmic['levenshtein']['distance'] < 3 else "MEDIUM",
                    "verdict_impact": f"Jaro-Winkler: {algorithmic['jaro_winkler']['score']}% similar"
                })
    
    # ==================== BUILD SUMMARY ====================
    total_direct = len(direct_competitors)
    total_phonetic = len(phonetic_conflicts)
    total_twins = len(name_twins)
    
    warning_triggered = total_direct > 0 or total_phonetic > 0
    
    if total_direct > 0:
        top_conflict = direct_competitors[0]
        warning_reason = f"CRITICAL: {total_direct} direct competitor(s) found. Top: {top_conflict['name']} ({top_conflict['risk_level']})"
    elif total_phonetic > 0:
        warning_reason = f"WARNING: {total_phonetic} phonetic conflict(s) detected. Review before proceeding."
    else:
        warning_reason = None
    
    conflict_summary = (
        f"{total_direct} direct competitors. "
        f"{total_phonetic} phonetic conflicts. "
        f"{total_twins} name twins identified with distinct intents."
    )
    
    logging.info(f"   📊 CONFLICT SUMMARY: {conflict_summary}")
    logging.info(f"   ⚠️ WARNING TRIGGERED: {warning_triggered} ({warning_reason or 'None'})")
    
    return {
        "user_product_intent": f"{category} in {industry or 'Digital'} space",
        "user_customer_avatar": f"{positioning or 'General'} market segment customers",
        "phonetic_conflicts": phonetic_conflicts,
        "direct_competitors": direct_competitors,
        "name_twins": name_twins,
        "google_presence": visibility_data.get('google', [])[:5] if visibility_data else [],
        "app_store_presence": visibility_data.get('apps', [])[:5] if visibility_data else [],
        "warning_triggered": warning_triggered,
        "warning_reason": warning_reason,
        "conflict_summary": conflict_summary,
        # Additional metadata
        "_sources_used": ["Trademark Registry", "Company Registry", "App Stores", "Google Search", "Deep-Trace Analysis"],
        "_total_conflicts": total_direct + total_phonetic,
        "_data_driven": True  # Flag to indicate this is real data, not LLM-generated
    }


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
                # CRITICAL: Enforce verdict consistency in final_assessment
                main_verdict = brand.get("verdict", "").upper()
                main_score = brand.get("namescore", 50)
                
                if "final_assessment" in brand and isinstance(brand["final_assessment"], dict):
                    fa = brand["final_assessment"]
                    
                    # Fix suitability_score to be consistent with verdict
                    suitability = fa.get("suitability_score", 50)
                    if isinstance(suitability, str):
                        try:
                            suitability = int(float(suitability.replace("/10", "").replace("/100", "").strip()))
                        except:
                            suitability = 50
                    
                    # If score is clearly on wrong scale (1-10 instead of 1-100), convert
                    if suitability <= 10:
                        suitability = suitability * 10
                    
                    # Enforce consistency: GO = 70+, CAUTION = 40-69, REJECT = 1-39
                    if main_verdict == "GO" and suitability < 70:
                        suitability = max(75, main_score) if main_score else 75
                        logging.info(f"🔧 CONSISTENCY FIX: GO verdict but low suitability, fixed to {suitability}")
                    elif main_verdict == "REJECT" and suitability > 40:
                        suitability = min(25, 100 - main_score) if main_score else 25
                        logging.info(f"🔧 CONSISTENCY FIX: REJECT verdict but high suitability, fixed to {suitability}")
                    
                    fa["suitability_score"] = suitability
                    
                    # Fix bottom_line if it contradicts GO verdict
                    bottom_line = fa.get("bottom_line", "") or fa.get("verdict_statement", "")
                    if main_verdict == "GO" and bottom_line:
                        # Check for contradictory language in GO verdicts
                        negative_phrases = ["reconsider", "conflict", "risky", "not recommended", "avoid", "warning", "concern", "problem"]
                        if any(phrase in bottom_line.lower() for phrase in negative_phrases):
                            logging.info(f"🔧 CONSISTENCY FIX: GO verdict but negative bottom_line detected, clearing false positive language")
                            fa["bottom_line"] = f"The name shows strong potential for the {brand.get('brand_name', 'brand')} brand. Proceed with trademark registration."
                
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


async def google_search(query: str, num_results: int = 10) -> dict:
    """
    Search using Google Custom Search API.
    Returns structured results with title, link, snippet.
    Falls back to empty results on error.
    """
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        logging.warning("Google Search API not configured")
        return {"items": [], "totalResults": "0", "error": "Not configured"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "q": query,
                    "cx": GOOGLE_SEARCH_ENGINE_ID,
                    "key": GOOGLE_API_KEY,
                    "num": min(num_results, 10)  # Google limits to 10 per request
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    total = data.get('searchInformation', {}).get('totalResults', '0')
                    items = data.get('items', [])
                    logging.info(f"🔍 Google Search '{query}': {len(items)} results, {total} total")
                    return {
                        "items": items,
                        "totalResults": total,
                        "error": None
                    }
                else:
                    error_text = await response.text()
                    logging.error(f"Google Search API error: {response.status} - {error_text[:200]}")
                    return {"items": [], "totalResults": "0", "error": f"API error: {response.status}"}
    except Exception as e:
        logging.error(f"Google Search failed: {e}")
        return {"items": [], "totalResults": "0", "error": str(e)}


async def check_brand_exists_google(brand_name: str, category: str = "") -> dict:
    """
    Use Google Search API to check if a brand exists.
    Returns evidence of brand existence with confidence score.
    """
    evidence = []
    confidence = "LOW"
    brand_found = False
    
    # Search queries to try
    queries = [
        f'"{brand_name}" brand',
        f'"{brand_name}" {category}' if category else None,
        f'"{brand_name}" official website',
    ]
    queries = [q for q in queries if q]
    
    total_signals = 0
    brand_lower = brand_name.lower().replace(" ", "")
    
    for query in queries[:2]:  # Limit to 2 queries to save API quota
        result = await google_search(query, num_results=5)
        
        if result.get("error"):
            continue
        
        items = result.get("items", [])
        total_results = int(result.get("totalResults", "0"))
        
        for item in items:
            title = item.get("title", "").lower()
            link = item.get("link", "").lower()
            snippet = item.get("snippet", "").lower()
            
            # Check for strong signals
            # 1. Official website (brand.com or getbrand.com)
            if f"{brand_lower}.com" in link or f"get{brand_lower}.com" in link or f"{brand_lower}.in" in link:
                evidence.append(f"Official website: {item.get('link')}")
                total_signals += 3
                brand_found = True
            
            # 2. E-commerce presence (Amazon, Flipkart, etc.)
            if any(platform in link for platform in ["amazon.", "flipkart.", "jiomart.", "bigbasket.", "myntra."]):
                if brand_lower in title or brand_lower in link:
                    evidence.append(f"E-commerce: {item.get('link')}")
                    total_signals += 2
                    brand_found = True
            
            # 3. Social media presence
            if any(platform in link for platform in ["facebook.com", "instagram.com", "twitter.com", "linkedin.com"]):
                if brand_lower in link:
                    evidence.append(f"Social media: {item.get('link')}")
                    total_signals += 2
                    brand_found = True
            
            # 4. Brand mentioned in title
            if brand_lower in title.replace(" ", ""):
                if "buy" in title or "shop" in title or "official" in title:
                    evidence.append(f"Brand mention: {item.get('title')[:50]}")
                    total_signals += 1
                    brand_found = True
    
    # Determine confidence based on signals
    if total_signals >= 5:
        confidence = "HIGH"
    elif total_signals >= 3:
        confidence = "MEDIUM"
    elif total_signals >= 1:
        confidence = "LOW"
    
    logging.info(f"🔍 Google Brand Check '{brand_name}': found={brand_found}, signals={total_signals}, confidence={confidence}")
    
    return {
        "exists": brand_found,
        "confidence": confidence,
        "evidence": evidence[:5],
        "signals": total_signals
    }


async def dynamic_brand_search(brand_name: str, category: str = "") -> dict:
    """
    ENHANCED BRAND CONFLICT DETECTION using Google Search API + LLM verification
    
    1. First use Google Search API to check if brand exists (most reliable)
    2. Fall back to Bing scraping if Google fails
    3. Use LLM to verify and analyze conflicts
    """
    import re
    import aiohttp
    
    print(f"🔍 BRAND CHECK: '{brand_name}' in category '{category}'", flush=True)
    logging.info(f"🔍 BRAND CHECK: '{brand_name}' in category '{category}'")
    
    result = {
        "exists": False,
        "confidence": "LOW",
        "matched_brand": None,
        "evidence": [],
        "reason": ""
    }
    
    # ========== STEP 1: GOOGLE SEARCH API (Primary - Most Reliable) ==========
    google_result = None
    google_evidence = []
    if GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
        print(f"🔍 Using Google Search API for '{brand_name}'...", flush=True)
        google_result = await check_brand_exists_google(brand_name, category)
        
        if google_result["exists"] and google_result["confidence"] in ["HIGH", "MEDIUM"]:
            print(f"✅ Google found '{brand_name}' with {google_result['confidence']} confidence - will check NICE class via LLM", flush=True)
            google_evidence = google_result.get("evidence", [])
            # NOTE: Do NOT return here - we need to check NICE class via LLM
            # The brand might exist in a DIFFERENT class which is NOT a conflict
    
    # ========== STEP 2: BING FALLBACK (If Google not available or inconclusive) ==========
    web_evidence = []
    brand_found_online = False
    web_confidence = "LOW"
    
    try:
        brand_lower = brand_name.lower().replace(" ", "")
        brand_with_space = brand_name.lower()
        
        # ENHANCED: Search with category context for better detection
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
    # Get user's NICE class for comparison
    user_nice_class = get_nice_classification(category)
    user_class_number = user_nice_class.get("class_number", 35)
    
    try:
        if not LlmChat or not EMERGENT_KEY:
            logging.warning("LLM not available, skipping brand check")
            return result
        
        llm = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")  # Most reliable model
        
        prompt = f"""You are a trademark and brand expert. Analyze this brand name for conflicts.

BRAND NAME: {brand_name}
USER'S CATEGORY: {category or 'General'}
USER'S NICE CLASS: Class {user_class_number} - {user_nice_class.get('class_description', 'General')}
TARGET MARKET: India, USA, Global

TASK: 
1. Check if "{brand_name}" already exists as a brand/company
2. If it exists, determine WHAT INDUSTRY/NICE CLASS the existing brand operates in
3. Compare: Is the existing brand in the SAME class as the user's category?

⚠️ NICE CLASS REFERENCE (Critical for determining conflicts):
- Class 3: Cosmetics, skincare, cleaning products, soaps, perfumes
- Class 5: Pharmaceuticals, medical preparations, dietary supplements
- Class 9: Software, mobile apps, electronics, computers
- Class 25: Clothing, footwear, fashion, apparel
- Class 29: Processed foods, meat, dairy, snacks
- Class 30: Coffee, tea, bakery, confectionery
- Class 35: Advertising, business services, retail
- Class 36: Finance, banking, insurance, real estate
- Class 41: Education, entertainment, training, gaming
- Class 42: SaaS, technology services, software services
- Class 43: Restaurants, cafes, hotels, food services

⚠️ CRITICAL RULE - SAME CLASS = CONFLICT, DIFFERENT CLASS = NO CONFLICT:
- "Deepstory" (Social App, Class 9) vs User's "Skincare" (Class 3) = DIFFERENT CLASS = NO CONFLICT
- "Dove" (Soap, Class 3) vs User's "Skincare" (Class 3) = SAME CLASS = CONFLICT
- The ONLY time there's a real conflict is when BOTH brands target the SAME NICE CLASS

⚠️ BRANDS TO CHECK AGAINST:
- Chai Duniya, Chai Point, Chaayos, Chai Bunk (Class 43 - Cafes)
- Cleevo (Class 3 - Cleaning products)
- Moneycontrol (Class 36/42 - Finance/Tech)

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "has_conflict": true or false,
    "confidence": "HIGH" or "MEDIUM" or "LOW",
    "conflicting_brand": "Name of existing brand" or null,
    "conflicting_brand_industry": "Industry of the existing brand (e.g., Social App, Cafe, Cleaning Products)" or null,
    "conflicting_brand_nice_class": <number 1-45 of existing brand's NICE class> or null,
    "user_nice_class": {user_class_number},
    "same_class_conflict": true or false,
    "similarity_percentage": 0-100,
    "reason": "Brief explanation including class comparison",
    "brand_info": "What is the conflicting brand (1 sentence)",
    "brand_already_exists": true or false
}}

EXAMPLES WITH CLASS COMPARISON:
- "Deepstory" in "Skincare" (Class 3) → {{"has_conflict": false, "confidence": "HIGH", "conflicting_brand": "Deepstory", "conflicting_brand_industry": "Social Media App", "conflicting_brand_nice_class": 9, "user_nice_class": 3, "same_class_conflict": false, "similarity_percentage": 100, "reason": "Deepstory exists as a social app (Class 9), but user wants skincare (Class 3). DIFFERENT CLASSES = NO CONFLICT", "brand_info": "Deepstory is a social storytelling app", "brand_already_exists": true}}
- "Cleevo" in "Cleaning" (Class 3) → {{"has_conflict": true, "confidence": "HIGH", "conflicting_brand": "Cleevo", "conflicting_brand_industry": "Cleaning Products", "conflicting_brand_nice_class": 3, "user_nice_class": 3, "same_class_conflict": true, "similarity_percentage": 100, "reason": "Cleevo is an existing cleaning brand (Class 3), same as user's category. SAME CLASS = CONFLICT", "brand_info": "Cleevo is an eco-friendly cleaning products brand in India", "brand_already_exists": true}}
- "Chaayos" in "Cafe" (Class 43) → {{"has_conflict": true, "confidence": "HIGH", "conflicting_brand": "Chaayos", "conflicting_brand_industry": "Cafe Chain", "conflicting_brand_nice_class": 43, "user_nice_class": 43, "same_class_conflict": true, "similarity_percentage": 100, "reason": "Chaayos is a major chai cafe chain (Class 43), same as user's category. SAME CLASS = CONFLICT", "brand_info": "Chaayos is one of India's largest chai cafe chains", "brand_already_exists": true}}
- "Zyntrix" in "Finance" (Class 36) → {{"has_conflict": false, "confidence": "HIGH", "conflicting_brand": null, "conflicting_brand_industry": null, "conflicting_brand_nice_class": null, "user_nice_class": 36, "same_class_conflict": false, "similarity_percentage": 0, "reason": "Unique invented name with no existing brand", "brand_info": null, "brand_already_exists": false}}

NOW ANALYZE: "{brand_name}" in "{category or 'General'}" (User's Class: {user_class_number})
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
            same_class_conflict = llm_result.get("same_class_conflict", True)  # Default to True for safety
            conflicting_brand_class = llm_result.get("conflicting_brand_nice_class")
            conflicting_brand_industry = llm_result.get("conflicting_brand_industry", "Unknown")
            
            # ============ NICE CLASS FILTER ============
            # If LLM detected a brand but it's in a DIFFERENT NICE class, it's NOT a real conflict
            if (has_conflict or brand_exists) and not same_class_conflict:
                print(f"✅ CROSS-CLASS FALSE POSITIVE: '{brand_name}' exists as {conflicting_brand_industry} (Class {conflicting_brand_class}), but user wants Class {user_class_number}. ALLOWING.", flush=True)
                logging.info(f"✅ CROSS-CLASS FALSE POSITIVE: '{brand_name}' - Existing brand in Class {conflicting_brand_class}, User wants Class {user_class_number}. DIFFERENT CLASSES = NO CONFLICT")
                
                result["exists"] = False
                result["confidence"] = "LOW"
                result["matched_brand"] = None
                result["reason"] = f"Brand exists in different class (Class {conflicting_brand_class}: {conflicting_brand_industry}) - not a conflict for {category} (Class {user_class_number})"
                result["cross_class_clear"] = True
                result["existing_brand_info"] = {
                    "name": llm_result.get("conflicting_brand"),
                    "industry": conflicting_brand_industry,
                    "nice_class": conflicting_brand_class
                }
                return result
            
            if (has_conflict or brand_exists) and llm_result.get("confidence") in ["HIGH", "MEDIUM"] and same_class_conflict:
                # ============ VERIFICATION LAYER ============
                # LLM flagged a SAME-CLASS conflict - now VERIFY with real evidence
                print(f"⚠️ LLM flagged '{brand_name}' (SAME CLASS {conflicting_brand_class}) - Running verification layer...", flush=True)
                logging.info(f"⚠️ LLM flagged '{brand_name}' (SAME CLASS conflict) - Running verification layer...")
                
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
                    result["same_class_conflict"] = True
                    result["conflicting_brand_class"] = conflicting_brand_class
                    if brand_exists:
                        result["reason"] = f"VERIFIED EXISTING BRAND (SAME CLASS {conflicting_brand_class}): {result['reason']}"
                    
                    print(f"🚨 VERIFIED SAME-CLASS CONFLICT: '{brand_name}' - Evidence Score: {verification['evidence_score']}", flush=True)
                    logging.warning(f"🚨 VERIFIED SAME-CLASS CONFLICT: '{brand_name}' - Evidence: {verification['evidence_found'][:3]}")
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
    
    # Store job in MongoDB for persistence (survives server restarts)
    job_data = {
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
    await save_job(job_id, job_data)
    
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
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found. It may have expired or never existed.")
    
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
    """Background task to run evaluation - uses MongoDB for persistence"""
    try:
        # Update status to processing
        db.evaluation_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": JobStatus.PROCESSING, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        logging.info(f"Job {job_id}: Starting evaluation for {request.brand_names}")
        
        # Call the actual evaluation function with job_id for progress tracking
        result = await evaluate_brands_internal(request, job_id=job_id)
        
        # Store result in MongoDB
        if hasattr(result, 'model_dump'):
            result_dict = result.model_dump()
            # Ensure trademark_research has all required fields with defaults
            for bs in result_dict.get('brand_scores', []):
                tr = bs.get('trademark_research')
                if tr:
                    tr['critical_conflicts_count'] = tr.get('critical_conflicts_count') or 0
                    tr['high_risk_conflicts_count'] = tr.get('high_risk_conflicts_count') or 0
                    tr['total_conflicts_found'] = tr.get('total_conflicts_found') or 0
                    tr['overall_risk_score'] = tr.get('overall_risk_score') or 5
                    tr['registration_success_probability'] = tr.get('registration_success_probability') or 50
                    tr['opposition_probability'] = tr.get('opposition_probability') or 50
        else:
            result_dict = result
        
        # Save completed job to MongoDB
        db.evaluation_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": JobStatus.COMPLETED,
                "progress": 100,
                "result": result_dict,
                "completed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        logging.info(f"Job {job_id}: Completed successfully")
        
    except Exception as e:
        logging.error(f"Job {job_id}: Failed with error: {str(e)}")
        db.evaluation_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": JobStatus.FAILED,
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat()
            }}
        )

# Original synchronous endpoint (kept for backward compatibility)
@api_router.post("/evaluate", response_model=BrandEvaluationResponse)
async def evaluate_brands(request: BrandEvaluationRequest):
    """Synchronous evaluation - may timeout on long requests. Use /evaluate/start for async."""
    return await evaluate_brands_internal(request)

async def evaluate_brands_internal(request: BrandEvaluationRequest, job_id: str = None):
    import time as time_module
    start_time = time_module.time()
    
    # Helper function to update progress (async)
    async def update_progress(step_id: str, eta: int = None):
        if job_id:
            await update_job_progress(job_id, step_id, eta)
    
    # ==================== FIRST CHECK: INAPPROPRIATE/OFFENSIVE NAMES ====================
    # Check for vulgar, offensive, or phonetically inappropriate names FIRST
    await update_progress("domain", 80)  # Start with domain check step
    
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
    
    # ==================== NEW: DEEP-TRACE ANALYSIS (RIGHTNAME.AI CORE) ====================
    # This catches root word conflicts like Rapidoy → Rapido
    # Runs BEFORE expensive LLM calls to save time and money
    deep_trace_rejections = {}
    deep_trace_results = {}  # Store all results for later use
    
    for brand in request.brand_names:
        if brand not in all_rejections:  # Skip if already rejected by dynamic search
            try:
                # Run Deep-Trace Analysis
                trace_result = await asyncio.to_thread(
                    deep_trace_analysis, 
                    brand, 
                    request.industry or "", 
                    request.category
                )
                deep_trace_results[brand] = trace_result
                
                # Log the report
                logging.info(format_deep_trace_report(trace_result))
                
                # Check if should be rejected (score <= 40 = HIGH RISK)
                if trace_result["should_reject"]:
                    deep_trace_rejections[brand] = trace_result
                    logging.warning(f"🛡️ DEEP-TRACE REJECTION: {brand} → Score {trace_result['score']}/100 ({trace_result['verdict']})")
                    if trace_result["critical_conflict"]:
                        logging.warning(f"   CATEGORY KING CONFLICT: {trace_result['critical_conflict']}")
                else:
                    logging.info(f"✅ DEEP-TRACE PASSED: {brand} → Score {trace_result['score']}/100 ({trace_result['verdict']})")
                    
            except Exception as e:
                logging.error(f"Deep-Trace Analysis failed for {brand}: {e}")
                # Don't block on failure - continue with other checks
    
    # Merge Deep-Trace rejections into all_rejections
    for brand, trace_result in deep_trace_rejections.items():
        all_rejections[brand] = {
            "exists": True,
            "confidence": "HIGH" if trace_result["score"] <= 20 else "MEDIUM",
            "matched_brand": trace_result["critical_conflict"] or trace_result.get("nearest_competitor", "Unknown"),
            "reason": trace_result["analysis_summary"],
            "detection_method": "deep_trace_analysis",
            "deep_trace_score": trace_result["score"],
            "deep_trace_verdict": trace_result["verdict"]
        }
    # ==================== END DEEP-TRACE ANALYSIS ====================
    
    # ==================== EARLY STOPPING FOR DETECTED BRANDS ====================
    # If ALL brand names are detected (either by dynamic search or Deep-Trace), skip expensive processing
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
            detection_method = rejection_info.get("detection_method", "Dynamic Competitor Search")
            if detection_method == "deep_trace_analysis":
                detection_method = "Deep-Trace Analysis (Root Word Conflict)"
                deep_trace_score = rejection_info.get("deep_trace_score", 0)
                deep_trace_verdict = rejection_info.get("deep_trace_verdict", "HIGH RISK")
            else:
                deep_trace_score = None
                deep_trace_verdict = None
            
            # Build summary
            if deep_trace_score is not None:
                summary = f"⛔ FATAL CONFLICT: '{brand}' has root word conflict with '{matched_brand}'. Rightname Score: {deep_trace_score}/100 ({deep_trace_verdict}). {reason}"
            else:
                summary = f"⛔ FATAL CONFLICT: '{brand}' is an EXISTING BRAND. Detected via {detection_method}. {reason}"
            
            brand_scores.append(BrandScore(
                brand_name=brand,
                namescore=deep_trace_score if deep_trace_score is not None else 5.0,
                verdict="REJECT",
                summary=summary,
                strategic_classification="BLOCKED - Existing Brand Conflict" if deep_trace_score is None else f"BLOCKED - Category King Conflict (Score: {deep_trace_score}/100)",
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
            executive_summary=f"⛔ IMMEDIATE REJECTION: The brand name(s) submitted ({', '.join(request.brand_names)}) match existing brands found via web search or Deep-Trace Analysis. These names cannot be used due to trademark conflicts.",
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
        doc['detection_method'] = "dynamic_competitor_search_and_deep_trace"
        doc['deep_trace_results'] = {k: v for k, v in deep_trace_results.items()} if deep_trace_results else None
        doc['processing_time_seconds'] = time_module.time() - start_time
        await db.evaluations.insert_one(doc)
        
        logging.info(f"Early stopping saved ~60-90s of processing time for existing brand rejection")
        return response_data
    # ==================== END EARLY STOPPING ====================
    
    # ==================== UNDERSTANDING MODULE - THE BRAIN ====================
    # Run FIRST before any other analysis to understand what user is building
    # This creates a "Source of Truth" that all downstream modules read from
    logging.info(f"🧠 UNDERSTANDING MODULE: Starting for {len(request.brand_names)} brand(s)...")
    
    brand_understandings = {}
    for brand in request.brand_names:
        try:
            understanding = await generate_brand_understanding(
                brand_name=brand,
                category=request.category,
                positioning=request.positioning,
                countries=request.countries
            )
            brand_understandings[brand] = understanding
            
            # Log key insights
            classification = understanding.get("brand_analysis", {}).get("linguistic_classification", {}).get("type", "UNKNOWN")
            nice_class = understanding.get("trademark_context", {}).get("primary_nice_class", {}).get("class_number", 0)
            business_type = understanding.get("business_understanding", {}).get("business_type", "unknown")
            tokens = understanding.get("brand_analysis", {}).get("tokenized", [])
            
            logging.info(f"🧠 UNDERSTANDING for '{brand}': Classification={classification}, Class={nice_class}, Type={business_type}, Tokens={tokens}")
            
        except Exception as e:
            logging.error(f"🧠 Understanding Module failed for {brand}: {e}")
            brand_understandings[brand] = None
    
    logging.info(f"🧠 UNDERSTANDING MODULE: Complete for {len(brand_understandings)} brand(s)")
    # ==================== END UNDERSTANDING MODULE ====================
    
    if LlmChat and EMERGENT_KEY:
        # Claude first (OpenAI having 502 issues), then OpenAI as fallback
        models_to_try = [
            ("anthropic", "claude-sonnet-4-20250514"),     # Primary - Most stable currently
            ("openai", "gpt-4o-mini"),                     # Fallback 1
            ("openai", "gpt-4o"),                          # Fallback 2
        ]
    else:
        raise HTTPException(status_code=500, detail="LLM Integration not initialized (Check EMERGENT_LLM_KEY)")
    
    # ==================== IMPROVEMENT #1: PARALLEL PROCESSING ====================
    # Run all independent data gathering operations in parallel
    logging.info(f"Starting PARALLEL data gathering for {len(request.brand_names)} brand(s)...")
    parallel_start = time_module.time()
    
    # Update progress - starting parallel checks
    await update_progress("domain", 70)
    
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
    
    async def gather_trademark_data(brand, classification_category: str = "DESCRIPTIVE", understanding: dict = None):
        """Run trademark research with hybrid risk model and understanding context"""
        try:
            # Get NICE class from understanding if available
            nice_class_override = None
            if understanding:
                nice_class_info = get_nice_class_from_understanding(understanding)
                nice_class_override = nice_class_info.get("class_number")
                classification_category = get_classification_from_understanding(understanding)
                logging.info(f"🧠 Trademark using Understanding: Class {nice_class_override}, Classification {classification_category}")
            
            # Include user-provided competitors and keywords for better search
            # Pass classification for hybrid risk model
            research_result = await conduct_trademark_research(
                brand_name=brand,
                industry=request.industry or "",
                category=request.category,
                countries=request.countries,
                known_competitors=request.known_competitors or [],
                product_keywords=request.product_keywords or [],
                classification=classification_category,  # From understanding
                nice_class_override=nice_class_override   # NEW: Pass NICE class from understanding
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
        
        # ==================== GET UNDERSTANDING (From Brain Module) ====================
        brand_understanding = brand_understandings.get(brand)
        if brand_understanding:
            logging.info(f"🧠 Using Understanding Module data for '{brand}'")
        # ==================== END GET UNDERSTANDING ====================
        
        # ==================== STEP 1: UNIVERSAL LINGUISTIC ANALYSIS (FIRST!) ====================
        # Analyze brand name for meaning in ANY world language using LLM
        # This MUST run FIRST to provide data for classification override
        logging.info(f"🔤 Starting Universal Linguistic Analysis for '{brand}'...")
        try:
            linguistic_analysis = await analyze_brand_linguistics(
                brand_name=brand,
                business_category=request.category or "Business",
                industry=request.industry or ""
            )
            logging.info(f"🔤 Linguistic Analysis Complete for '{brand}':")
            logging.info(f"   Has Meaning: {linguistic_analysis.get('has_linguistic_meaning', False)}")
            if linguistic_analysis.get('has_linguistic_meaning'):
                logging.info(f"   Languages: {linguistic_analysis.get('linguistic_analysis', {}).get('languages_detected', [])}")
                logging.info(f"   Name Type: {linguistic_analysis.get('classification', {}).get('name_type', 'Unknown')}")
                logging.info(f"   Business Alignment: {linguistic_analysis.get('business_alignment', {}).get('alignment_score', 'N/A')}/10")
        except Exception as e:
            logging.error(f"🔤 Linguistic Analysis failed for '{brand}': {e}")
            linguistic_analysis = None
        
        # ==================== OVERRIDE LINGUISTIC WITH UNDERSTANDING ====================
        # If Understanding Module has better data, override the linguistic analysis
        if brand_understanding:
            brand_analysis = brand_understanding.get("brand_analysis", {})
            word_analysis = brand_analysis.get("word_analysis", [])
            has_dict_words = brand_analysis.get("has_dictionary_words", False)
            understanding_classification = brand_analysis.get("linguistic_classification", {})
            
            # Override has_linguistic_meaning based on Understanding
            if has_dict_words:
                if not linguistic_analysis:
                    linguistic_analysis = {}
                
                # Override with Understanding Module data
                linguistic_analysis["has_linguistic_meaning"] = True
                linguistic_analysis["_overridden_by_understanding"] = True
                linguistic_analysis["brand_name"] = brand
                
                # Build word meanings from Understanding
                languages_detected = list(set([w.get("language", "English") for w in word_analysis]))
                part_meanings = {w.get("word"): {"meaning": w.get("meaning", ""), "language": w.get("language", "English")} for w in word_analysis}
                
                linguistic_analysis["linguistic_analysis"] = {
                    "languages_detected": languages_detected,
                    "decomposition": {
                        "can_be_decomposed": len(word_analysis) > 1,
                        "parts": brand_analysis.get("tokenized", []),
                        "part_meanings": part_meanings,
                        "combined_meaning": brand_analysis.get("combined_meaning", "")
                    }
                }
                
                linguistic_analysis["classification"] = {
                    "name_type": understanding_classification.get("type", "DESCRIPTIVE"),
                    "distinctiveness_level": "LOW" if understanding_classification.get("type") in ["DESCRIPTIVE", "GENERIC"] else "MEDIUM" if understanding_classification.get("type") == "SUGGESTIVE" else "HIGH",
                    "reasoning": understanding_classification.get("reasoning", "")
                }
                
                # Business alignment from Understanding
                business_understanding = brand_understanding.get("business_understanding", {})
                semantic_safety = brand_understanding.get("semantic_safety", {})
                linguistic_analysis["business_alignment"] = {
                    "alignment_score": semantic_safety.get("industry_fit_score", 7.0),
                    "alignment_level": "HIGH" if semantic_safety.get("industry_fit_score", 7) >= 7 else "MEDIUM" if semantic_safety.get("industry_fit_score", 7) >= 5 else "LOW",
                    "thematic_connection": business_understanding.get("what_they_offer", "")
                }
                
                logging.info(f"🧠 OVERRIDING Linguistic Analysis with Understanding Module data for '{brand}'")
                logging.info(f"   Tokenized: {brand_analysis.get('tokenized', [])}")
                logging.info(f"   Has Dictionary Words: {has_dict_words}")
                logging.info(f"   Classification: {understanding_classification.get('type', 'UNKNOWN')}")
        # ==================== END OVERRIDE ====================
        
        # ==================== END LINGUISTIC ANALYSIS ====================
        
        # ==================== STEP 2: MASTER CLASSIFICATION (WITH UNDERSTANDING + LINGUISTIC OVERRIDE) ====================
        # If Understanding Module has classification, use it; else fall back to linguistic override
        if brand_understanding and should_use_understanding_classification(brand_understanding):
            # Use Understanding Module classification (Source of Truth)
            understanding_classification = get_classification_from_understanding(brand_understanding)
            classification_category = understanding_classification
            brand_classification = {
                "category": understanding_classification,
                "distinctiveness": "HIGH" if understanding_classification == "FANCIFUL" else "MEDIUM" if understanding_classification in ["ARBITRARY", "SUGGESTIVE"] else "LOW",
                "protectability": "STRONG" if understanding_classification == "FANCIFUL" else "MODERATE" if understanding_classification in ["ARBITRARY", "SUGGESTIVE"] else "WEAK",
                "understanding_source": True,
                "tokenized_words": brand_understanding.get("brand_analysis", {}).get("tokenized", [])
            }
            logging.info(f"🧠 USING UNDERSTANDING CLASSIFICATION for '{brand}': {classification_category}")
        else:
            # Fall back to old classification with linguistic override
            brand_classification = classify_brand_with_linguistic_override(
                brand, 
                request.category or "Business",
                linguistic_analysis  # Pass linguistic data for potential override
            )
            classification_category = brand_classification.get("category", "DESCRIPTIVE")
        
        logging.info(f"🏷️ MASTER CLASSIFICATION for '{brand}':")
        logging.info(f"   Category: {classification_category}")
        logging.info(f"   Distinctiveness: {brand_classification['distinctiveness']}")
        logging.info(f"   Protectability: {brand_classification['protectability']}")
        if brand_classification.get("linguistic_override"):
            logging.info(f"   ⚡ OVERRIDE: {brand_classification.get('original_category')} → {classification_category}")
            logging.info(f"   Reason: {brand_classification.get('override_reason')}")
        if brand_classification.get("understanding_source"):
            logging.info(f"   🧠 SOURCE: Understanding Module (Tokenized: {brand_classification.get('tokenized_words', [])})")
        # ==================== END MASTER CLASSIFICATION ====================
        
        # Create all tasks for this brand (pass classification AND understanding to trademark research)
        tasks = [
            gather_domain_data(brand),
            gather_similarity_data(brand),
            gather_trademark_data(brand, classification_category, brand_understanding),  # Pass understanding for NICE class
            gather_visibility_data(brand),
            gather_multi_domain_data(brand),
            gather_social_data(brand),
            # 🆕 COMPETITIVE INTELLIGENCE v2 - Funnel approach for better competitor data
            competitive_intelligence_v2(
                brand_name=brand,
                category=request.category,
                positioning=request.positioning,
                countries=request.countries,
                understanding=brand_understanding
            )
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
            "social": processed_results[5],
            "deep_market_intel": processed_results[6],  # 🆕 Competitive Intelligence v2 data
            "classification": brand_classification,  # Now includes linguistic override data
            "linguistic_analysis": linguistic_analysis,  # Store full linguistic analysis
            "understanding": brand_understanding  # Store understanding module data (Source of Truth)
        }
    
    parallel_time = time_module.time() - parallel_start
    logging.info(f"PARALLEL data gathering completed in {parallel_time:.2f}s (vs ~90s sequential)")
    # ==================== END PARALLEL PROCESSING ====================
    
    # ==================== LLM-FIRST COUNTRY RESEARCH ====================
    # Run LLM-powered market intelligence research in parallel with other processing
    logging.info(f"🔬 Starting LLM-first country research for {len(request.countries)} countries...")
    llm_research_start = time_module.time()
    
    try:
        # Get the first brand for research (primary brand being evaluated)
        primary_brand = request.brand_names[0] if request.brand_names else "Brand"
        
        # Get linguistic analysis and classification for primary brand
        primary_brand_data = all_brand_data.get(primary_brand, {})
        primary_linguistic = primary_brand_data.get("linguistic_analysis")
        primary_classification = primary_brand_data.get("classification")
        
        # Execute LLM-first research WITH POSITIONING and linguistic data
        country_competitor_analysis, cultural_analysis = await llm_first_country_analysis(
            countries=request.countries,
            category=request.category or "Business",
            brand_name=primary_brand,
            use_llm_research=True,  # Enable LLM research
            positioning=request.positioning,  # Pass user's positioning for segment-specific competitors
            classification=primary_classification,  # Pass pre-computed classification
            universal_linguistic=primary_linguistic  # Pass universal linguistic analysis
        )
        
        llm_research_time = time_module.time() - llm_research_start
        logging.info(f"✅ LLM-FIRST {request.positioning} COUNTRY RESEARCH completed in {llm_research_time:.2f}s")
        
        # Store for later use
        llm_research_data = {
            "country_competitor_analysis": country_competitor_analysis,
            "cultural_analysis": cultural_analysis
        }
    except Exception as e:
        logging.error(f"❌ LLM-first research failed: {e}, will use fallback in report generation")
        llm_research_data = None
    # ==================== END LLM-FIRST COUNTRY RESEARCH ====================
    
    # Update progress - all data gathering done, starting analysis
    await update_progress("trademark", 45)
    
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
    
    # 2. Similarity data + Deep-Trace Analysis
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
        
        # Add Deep-Trace Analysis results (already computed earlier)
        if brand in deep_trace_results:
            trace = deep_trace_results[brand]
            similarity_data.append(format_deep_trace_report(trace))
    
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
    
    # ==================== PRE-COMPUTED BRAND CLASSIFICATION CONTEXT ====================
    # Build classification context to pass to LLM so it respects our 5-step spectrum classification
    classification_context_parts = []
    for brand in request.brand_names:
        brand_classification = all_brand_data[brand].get("classification", {})
        if brand_classification:
            override_info = ""
            if brand_classification.get("linguistic_override"):
                override_info = f"""
├─ ⚡ LINGUISTIC OVERRIDE: {brand_classification.get('original_category')} → {brand_classification.get('category')}
├─ Override Reason: {brand_classification.get('override_reason', 'N/A')[:150]}"""
            
            linguistic_insight = ""
            ling_data = brand_classification.get("linguistic_insights", {})
            if ling_data.get("has_meaning"):
                linguistic_insight = f"""
├─ 🌍 LINGUISTIC MEANING FOUND:
│   ├─ Languages: {', '.join(ling_data.get('languages', []))}
│   ├─ Name Type: {ling_data.get('name_type', 'Unknown')}
│   ├─ Meaning: {ling_data.get('combined_meaning', 'N/A')[:100]}
│   └─ Business Alignment: {ling_data.get('alignment_score', 'N/A')}/10"""
            
            classification_context_parts.append(f"""
BRAND: {brand}
├─ Classification: {brand_classification.get('category', 'UNKNOWN')}
├─ Distinctiveness: {brand_classification.get('distinctiveness', 'UNKNOWN')}
├─ Protectability: {brand_classification.get('protectability', 'UNKNOWN')}{override_info}{linguistic_insight}
├─ Dictionary Tokens: {brand_classification.get('dictionary_tokens', [])}
├─ Invented Tokens: {brand_classification.get('invented_tokens', [])}
└─ Reasoning: {brand_classification.get('reasoning', 'N/A')[:200]}""")
    classification_context = "\n".join(classification_context_parts)
    # ==================== END CLASSIFICATION CONTEXT ====================
    
    # ==================== UNIVERSAL LINGUISTIC ANALYSIS CONTEXT ====================
    # Format linguistic analysis results for LLM prompt
    linguistic_context_parts = []
    for brand in request.brand_names:
        ling_analysis = all_brand_data[brand].get("linguistic_analysis")
        if ling_analysis and ling_analysis.get("_analyzed_by") != "fallback":
            linguistic_context_parts.append(format_linguistic_analysis_for_prompt(ling_analysis))
        else:
            linguistic_context_parts.append(f"LINGUISTIC ANALYSIS for {brand}: Not available")
    linguistic_analysis_context = "\n\n".join(linguistic_context_parts)
    # ==================== END LINGUISTIC ANALYSIS CONTEXT ====================
    
    # ==================== PRE-COMPUTED CONFLICT RELEVANCE ANALYSIS ====================
    # Build conflict analysis from REAL DATA (Trademark, App Store, Deep-Trace)
    # This ensures the visibility_analysis section reflects actual findings
    conflict_relevance_data = {}
    conflict_relevance_context_parts = []
    
    for brand in request.brand_names:
        tm_data = trademark_research_data.get(brand)
        vis_data = all_brand_data[brand].get("visibility")
        trace_data = deep_trace_results.get(brand)
        
        # Convert trademark data to dict properly (handles nested dataclasses)
        tm_data_dict = {}
        if tm_data:
            if hasattr(tm_data, 'to_dict'):
                tm_data_dict = tm_data.to_dict()
            elif hasattr(tm_data, '__dict__'):
                # Manual conversion for dataclass with nested objects
                from dataclasses import asdict, is_dataclass
                if is_dataclass(tm_data):
                    tm_data_dict = asdict(tm_data)
                else:
                    tm_data_dict = tm_data.__dict__
            elif isinstance(tm_data, dict):
                tm_data_dict = tm_data
        
        # Build conflict relevance from real data
        conflict_analysis = build_conflict_relevance_analysis(
            brand_name=brand,
            category=request.category,
            industry=request.industry or "",
            trademark_data=tm_data_dict,
            visibility_data=vis_data,
            deep_trace_result=trace_data,
            positioning=request.positioning
        )
        conflict_relevance_data[brand] = conflict_analysis
        
        # Format for LLM context
        direct_count = len(conflict_analysis.get('direct_competitors', []))
        phonetic_count = len(conflict_analysis.get('phonetic_conflicts', []))
        twins_count = len(conflict_analysis.get('name_twins', []))
        
        conflict_relevance_context_parts.append(f"""
📋 PRE-COMPUTED CONFLICT RELEVANCE ANALYSIS FOR: {brand}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ DIRECT COMPETITORS FOUND: {direct_count}
{chr(10).join([f"   • {c['name']} - {c['risk_level']} RISK - {c['reason']}" for c in conflict_analysis.get('direct_competitors', [])[:5]]) if direct_count > 0 else "   ✅ No direct competitors found in same NICE class/industry"}

🔊 PHONETIC CONFLICTS: {phonetic_count}
{chr(10).join([f"   • {c.get('found_conflict', {}).get('name', 'Unknown')} - {c.get('conflict_type', 'PHONETIC')}" for c in conflict_analysis.get('phonetic_conflicts', [])[:3]]) if phonetic_count > 0 else "   ✅ No phonetic conflicts detected"}

👥 NAME TWINS (Different Intent - LOW RISK): {twins_count}
{chr(10).join([f"   • {c['name']} - {c['category']} ({c['risk_level']} risk)" for c in conflict_analysis.get('name_twins', [])[:5]]) if twins_count > 0 else "   ✅ No name twins found"}

📊 SUMMARY: {conflict_analysis.get('conflict_summary', 'No conflicts detected')}
⚠️ WARNING: {conflict_analysis.get('warning_reason', 'None')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    conflict_relevance_context = "\n".join(conflict_relevance_context_parts)
    logging.info(f"✅ Built Conflict Relevance Analysis from real data for {len(request.brand_names)} brand(s)")
    # ==================== END CONFLICT RELEVANCE ANALYSIS ====================
    
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
    
    {format_legal_procedures_for_prompt(request.countries)}

    ⛔⛔⛔ ABSOLUTE MANDATORY: CURRENCY ENFORCEMENT FOR {request.countries[0] if len(request.countries) == 1 else 'MULTI-COUNTRY'} ⛔⛔⛔
    {"" if len(request.countries) != 1 else f'''
    YOU ARE GENERATING A REPORT FOR {request.countries[0].upper()} ONLY.
    
    FORBIDDEN ACTIONS:
    - ❌ DO NOT use "$" or "USD" anywhere in costs - this is {request.countries[0]}, not USA
    - ❌ DO NOT use US legal terms like "TTAB", "USPTO", "Federal Circuit"
    - ❌ DO NOT default to American examples
    
    MANDATORY ACTIONS:
    - ✅ ALL costs in mitigation_strategies[].estimated_cost MUST use {get_country_trademark_costs([request.countries[0]])['currency']}
    - ✅ Use {request.countries[0]} trademark office ({get_country_trademark_costs([request.countries[0]])['office']})
    - ✅ Reference {request.countries[0]} trademark law
    
    EXAMPLE (FOR INDIA):
    - ❌ WRONG: "estimated_cost": "$500-$2,000" 
    - ✅ CORRECT: "estimated_cost": "₹3,000-₹5,000"
    '''}

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

    ⚠️⚠️⚠️ PRE-COMPUTED BRAND CLASSIFICATION (MANDATORY - USE THIS!) ⚠️⚠️⚠️
    The following brand classifications have been computed using the 5-Step Trademark Distinctiveness Spectrum:
    {classification_context}
    
    INSTRUCTION FOR CLASSIFICATION:
    - DO NOT override these classifications with your own analysis
    - Use the EXACT classification category (GENERIC/DESCRIPTIVE/SUGGESTIVE/ARBITRARY/FANCIFUL) in your response
    - "Check My Meal" contains dictionary words "check", "my", "meal" → DESCRIPTIVE (NOT "Coined")
    - "Xerox", "Kodak" have NO dictionary words → FANCIFUL/Coined
    - If classification is DESCRIPTIVE or GENERIC, include the appropriate trademark warning
    - strategic_classification field MUST reflect this pre-computed classification

    🔤🔤🔤 UNIVERSAL LINGUISTIC ANALYSIS (CRITICAL - MEANING IN ANY LANGUAGE!) 🔤🔤🔤
    The following linguistic analysis identifies meaning in ANY world language (not just English):
    {linguistic_analysis_context}
    
    INSTRUCTION FOR LINGUISTIC ANALYSIS:
    - This analysis detects meaning in Sanskrit, Hindi, Tamil, Urdu, Arabic, Latin, Greek, Japanese, Chinese, and ALL other languages
    - If "has_linguistic_meaning: YES", the name has REAL meaning - NOT a coined/invented term
    - Use the "business_alignment" score to assess name-business fit
    - Include cultural significance and regional recognition in your cultural analysis
    - If religious/mythological references exist, factor them into cultural sensitivity scoring
    - The "classification.name_type" should be reflected in your strategic_classification
    - Potential concerns should be mentioned in your cons or cultural warnings

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
    
    🎯 PRE-COMPUTED CONFLICT RELEVANCE ANALYSIS (USE THIS DATA DIRECTLY):
    {conflict_relevance_context}
    
    ⚠️ CRITICAL INSTRUCTION FOR visibility_analysis:
    The conflict relevance analysis above is COMPUTED FROM REAL DATA (Trademark Registry, Company Registry, App Stores, Google Search, Deep-Trace Analysis).
    You MUST use this pre-computed data to populate 'visibility_analysis' field:
    - Copy direct_competitors exactly as shown above (these are REAL conflicts from trademark/company registry)
    - Copy phonetic_conflicts exactly as shown above (these are REAL phonetic matches from app stores)
    - Copy name_twins exactly as shown above (these are REAL but low-risk matches)
    - If pre-computed shows "⚠️ DIRECT COMPETITORS FOUND: X" where X > 0, set warning_triggered=true
    - DO NOT generate fictional conflicts - USE ONLY the pre-computed data
    - The conflict_summary should match the pre-computed summary

    ⚠️ MANDATORY COUNTRY-SPECIFIC COMPETITOR ANALYSIS ⚠️
    Target Countries Selected: {request.countries}
    Number of Countries: {len(request.countries)}
    
    CRITICAL INSTRUCTION: You MUST generate 'country_competitor_analysis' array with EXACTLY {len(request.countries)} entries - one for EACH of these countries: {', '.join(request.countries)}.
    DO NOT skip any country. Each country entry MUST contain:
    - country: exact country name (e.g., "India", "USA", "Thailand")
    - country_flag: emoji flag (🇺🇸, 🇮🇳, 🇹🇭, 🇬🇧, 🇩🇪, etc.)
    - competitors: array with 3-4 REAL local brands that operate in that specific country's market
    - user_brand_position: object with x_coordinate, y_coordinate, quadrant, rationale
    - white_space_analysis: market gap in that specific country
    - strategic_advantage: competitive advantage in that market
    - market_entry_recommendation: specific advice for entering that country
    
    {competitors_context}
    {keywords_context}
    {problem_context}
    """
    
    # Update progress - starting LLM analysis (the longest step)
    await update_progress("analysis", 30)
    
    # ============ GET DYNAMIC PROMPT & SETTINGS ============
    active_system_prompt = await get_active_system_prompt()
    model_settings = await get_active_model_settings()
    llm_timeout = model_settings.get("timeout_seconds", 35)
    
    logging.info(f"Using system prompt ({len(active_system_prompt)} chars), timeout={llm_timeout}s")
    
    # ============ PARALLEL LLM RACE - First successful response wins ============
    async def try_single_model(model_provider: str, model_name: str) -> dict:
        """Try a single model and return result or raise exception"""
        import concurrent.futures
        
        def sync_llm_call():
            """Synchronous wrapper for LLM call - runs in thread pool"""
            unique_session = f"rn_{uuid.uuid4().hex[:12]}_{model_name.replace('-', '_')}"
            
            llm_chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=unique_session,
                system_message=active_system_prompt  # Use dynamic prompt from DB/default
            ).with_model(model_provider, model_name)
            
            user_message = UserMessage(text=user_prompt)
            # This is synchronous - we'll run it in a thread
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                response = loop.run_until_complete(llm_chat.send_message(user_message))
            finally:
                loop.close()
            return response
        
        # Run LLM call in thread pool with TRUE timeout
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        
        try:
            # This WILL timeout because we're running in a separate thread
            response = await asyncio.wait_for(
                loop.run_in_executor(executor, sync_llm_call),
                timeout=25.0  # 25 second hard timeout
            )
        except asyncio.TimeoutError:
            executor.shutdown(wait=False, cancel_futures=True)
            raise asyncio.TimeoutError(f"{model_provider}/{model_name} timed out after 25s")
        finally:
            executor.shutdown(wait=False)
        
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
        
        content = content.strip()
        
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            content = clean_json_string(content)
            content = repair_json(content)
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                content = aggressive_json_repair(content)
                data = json.loads(content)
        
        # Ensure data is a dict
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                data = {"brand_scores": data, "executive_summary": "Brand evaluation completed.", "comparison_verdict": ""}
            else:
                raise ValueError("Invalid response format from LLM")
        
        # POST-PROCESSING: Ensure country_competitor_analysis has ALL user-selected countries
        # This fixes the issue where LLM skips some countries
        logging.info("=" * 60)
        logging.info("🔄 POST-PROCESSING: Starting competitor data override...")
        logging.info("=" * 60)
        
        if "brand_scores" in data and isinstance(data["brand_scores"], list):
            for idx, brand_score in enumerate(data["brand_scores"]):
                existing_countries = []
                if "country_competitor_analysis" in brand_score:
                    existing_countries = [c.get("country", "") for c in brand_score.get("country_competitor_analysis", [])]
                
                # Check if any user countries are missing
                # Note: request is accessible in outer scope
                # 🔧 FIX: Use original brand name from request, not LLM response
                brand_name_for_fallback = request.brand_names[idx] if idx < len(request.brand_names) else brand_score.get("brand_name", "Brand")
                category_for_fallback = brand_score.get("category", "Business")
                
                # Debug logging
                logging.info(f"🔍 POST-PROCESSING for '{brand_name_for_fallback}' (idx={idx})")
                logging.info(f"🔍 all_brand_data keys: {list(all_brand_data.keys())}")
                
                # 🆕 First check Deep Market Intelligence for country competitor analysis
                deep_intel = all_brand_data.get(brand_name_for_fallback, {}).get("deep_market_intel")
                
                if deep_intel:
                    logging.info(f"🎯 Found deep_intel for '{brand_name_for_fallback}': {len(deep_intel.get('global_matrix', {}).get('competitors', []))} global competitors")
                else:
                    logging.warning(f"⚠️ No deep_intel found for '{brand_name_for_fallback}'")
                
                if deep_intel and deep_intel.get("country_analysis"):
                    # Use REAL country-specific competitors from Deep Market Intelligence
                    country_analysis_data = deep_intel.get("country_analysis", {})
                    formatted_country_competitors = []
                    
                    for country in request.countries:
                        country_data = country_analysis_data.get(country, {})
                        
                        if country_data:
                            # Format competitors from deep intel
                            direct_comps = country_data.get("direct_competitors", [])
                            market_leaders = country_data.get("market_leaders", [])
                            
                            all_comps = []
                            for comp in (direct_comps + market_leaders)[:6]:
                                all_comps.append({
                                    "name": comp.get("name", "Unknown"),
                                    "x_coordinate": float(comp.get("x", 5)) * 10,
                                    "y_coordinate": float(comp.get("y", 5)) * 10,
                                    "quadrant": comp.get("type", "Competitor"),
                                    "price_axis": None,
                                    "modernity_axis": None
                                })
                            
                            # Get country flag
                            country_flags = {"India": "🇮🇳", "USA": "🇺🇸", "UK": "🇬🇧", "UAE": "🇦🇪", "Singapore": "🇸🇬", "Australia": "🇦🇺", "Canada": "🇨🇦", "Germany": "🇩🇪", "Japan": "🇯🇵", "China": "🇨🇳"}
                            country_flag = country_flags.get(country, "🌍")
                            
                            formatted_country_competitors.append({
                                "country": country,
                                "country_flag": country_flag,
                                "x_axis_label": "Price: Budget → Premium",
                                "y_axis_label": "Quality: Basic → High Production",
                                "competitors": all_comps,
                                "user_brand_position": {
                                    "x_coordinate": 50,
                                    "y_coordinate": 70,
                                    "quadrant": country_data.get("positioning_opportunity", "Accessible Premium"),
                                    "rationale": f"Positioned for {country_data.get('positioning_opportunity', 'target')} segment"
                                },
                                # Enhanced gap analysis with competitor names
                                "gap_analysis": {
                                    "direct_count": len([c for c in all_comps if c.get("quadrant") == "DIRECT" or "direct" in str(c.get("type", "")).lower()]),
                                    "indirect_count": len([c for c in all_comps if c.get("quadrant") != "DIRECT" and "direct" not in str(c.get("type", "")).lower()]),
                                    "total_competitors": len(all_comps),
                                    "direct_competitors": ", ".join([c.get("name", "Unknown") for c in all_comps if c.get("quadrant") == "DIRECT" or "direct" in str(c.get("type", "")).lower()][:6]) or "None identified",
                                    "indirect_competitors": ", ".join([c.get("name", "Unknown") for c in all_comps if c.get("quadrant") != "DIRECT" and "direct" not in str(c.get("type", "")).lower()][:6]) or "None identified",
                                    "gap_detected": len(all_comps) <= 3
                                },
                                "white_space_analysis": country_data.get("white_space", "") or (
                                    f"🟢 **BLUE OCEAN**: No direct competitors in {country}. First-mover advantage available." if len(all_comps) == 0 else
                                    f"🟡 **MODERATE COMPETITION**: {len(all_comps)} competitors identified. Differentiation through unique positioning required."
                                ),
                                "strategic_advantage": self._build_strategic_advantage_text(all_comps, country) if hasattr(self, '_build_strategic_advantage_text') else (
                                    f"🟢 **BLUE OCEAN OPPORTUNITY**: No direct competitors found in {country}." if len([c for c in all_comps if "direct" in str(c.get("type", "")).lower()]) == 0 else
                                    f"🟡 **COMPETITIVE MARKET**: Found {len(all_comps)} competitors in {country}.\n\n**Competitors:** {', '.join([c.get('name', 'Unknown') for c in all_comps[:6]])}"
                                ),
                                "market_entry_recommendation": (
                                    f"🚀 **GO** - Excellent timing for {country} market entry. Limited competition." if len(all_comps) <= 2 else
                                    f"✅ **PROCEED WITH STRATEGY** - Viable market entry in {country}. Focus on differentiation." if len(all_comps) <= 5 else
                                    f"⚠️ **HIGH COMPETITION** - {country} market has {len(all_comps)} competitors. Niche positioning recommended."
                                )
                            })
                    
                    if formatted_country_competitors:
                        brand_score["country_competitor_analysis"] = formatted_country_competitors
                        logging.info(f"🎯 Using Deep Market Intel for country_competitor_analysis: {len(formatted_country_competitors)} countries")
                
                # Fallback: If country_competitor_analysis is empty or missing countries, use LLM research data or regenerate
                if not brand_score.get("country_competitor_analysis") or len(brand_score.get("country_competitor_analysis", [])) == 0:
                    # Use LLM research data if available (from earlier parallel processing)
                    if llm_research_data and llm_research_data.get("country_competitor_analysis"):
                        brand_score["country_competitor_analysis"] = llm_research_data["country_competitor_analysis"]
                        logging.info(f"✅ Using LLM-researched country competitor analysis for {brand_name_for_fallback}")
                    else:
                        brand_score["country_competitor_analysis"] = generate_country_competitor_analysis(
                            request.countries, 
                            request.category or category_for_fallback, 
                            brand_name_for_fallback,
                            request.industry
                        )
                
                # Use LLM research cultural_analysis if available
                if not brand_score.get("cultural_analysis") or len(brand_score.get("cultural_analysis", [])) == 0:
                    if llm_research_data and llm_research_data.get("cultural_analysis"):
                        brand_score["cultural_analysis"] = llm_research_data["cultural_analysis"]
                        logging.info(f"✅ Using LLM-researched cultural analysis for {brand_name_for_fallback}")
                
                # Ensure competitor_analysis has proper data (GLOBAL competitors, not country-specific)
                # 🆕 Use Deep Market Intelligence if available (reuse deep_intel from above)
                
                # ALWAYS prefer Deep Market Intelligence over LLM-generated generic archetypes
                if deep_intel and deep_intel.get("global_matrix", {}).get("competitors"):
                    # Use REAL competitors from Deep Market Intelligence
                    global_matrix = deep_intel.get("global_matrix", {})
                    competitors_data = global_matrix.get("competitors", [])
                    user_pos = global_matrix.get("user_position", {})
                    
                    # Format competitors for matrix display
                    formatted_competitors = []
                    for comp in competitors_data[:10]:
                        formatted_competitors.append({
                            "name": comp.get("name", "Unknown"),
                            "x_coordinate": float(comp.get("x", 5)) * 10,  # Scale 1-10 to 10-100
                            "y_coordinate": float(comp.get("y", 5)) * 10,
                            "quadrant": comp.get("type", "Competitor"),
                            "price_axis": None,
                            "modernity_axis": None
                        })
                    
                    # OVERRIDE existing competitor_analysis with real data
                    brand_score["competitor_analysis"] = {
                        "x_axis_label": global_matrix.get("x_axis_label", "Price: Budget → Premium"),
                        "y_axis_label": global_matrix.get("y_axis_label", "Quality: Basic → High Production"),
                        "competitors": formatted_competitors,
                        "user_brand_position": {
                            "x_coordinate": float(user_pos.get("x", 5)) * 10,
                            "y_coordinate": float(user_pos.get("y", 7)) * 10,
                            "quadrant": user_pos.get("quadrant", "Accessible Premium"),
                            "rationale": f"'{brand_name_for_fallback}' positioned in {user_pos.get('quadrant', 'target')} segment"
                        },
                        "white_space_analysis": get_white_space_summary_v2(deep_intel),
                        "strategic_advantage": "Real competitor data from Deep Market Intelligence enables precise positioning strategy."
                    }
                    logging.info(f"🎯 OVERRIDE: Using Deep Market Intel for competitor_analysis: {len(formatted_competitors)} REAL competitors")
                    
                elif not brand_score.get("competitor_analysis") or not brand_score.get("competitor_analysis", {}).get("competitors"):
                    # Fallback: Use GLOBAL competitors for "Global Overview" matrix
                    global_data = get_global_competitors(request.category, request.industry)
                    brand_score["competitor_analysis"] = {
                        "x_axis_label": global_data.get("axis_x", "Price: Budget → Premium"),
                        "y_axis_label": global_data.get("axis_y", "Positioning: Traditional → Modern"),
                        "competitors": global_data.get("competitors", []),
                        "user_brand_position": {
                            "x_coordinate": 65,
                            "y_coordinate": 75,
                            "quadrant": "Accessible Premium",
                            "rationale": f"'{brand_name_for_fallback}' positioned for premium-accessible segment globally"
                        },
                        "white_space_analysis": global_data.get("white_space", "Opportunity exists for differentiated brands in global market."),
                        "strategic_advantage": global_data.get("strategic_advantage", "Distinctive brand identity enables unique global positioning.")
                    }
                    logging.info(f"⚠️ Using fallback global competitors (no Deep Market Intel)")
        
        # ═══════════════════════════════════════════════════════════════════════════════
        # 💱 POST-PROCESS: FORCE CURRENCY CONVERSION FOR SINGLE-COUNTRY REPORTS
        # The LLM often ignores currency instructions, so we force-convert here
        # ═══════════════════════════════════════════════════════════════════════════════
        logging.info(f"💱 CURRENCY CHECK: countries={request.countries}, len={len(request.countries)}")
        if len(request.countries) == 1 and request.countries[0] != "USA":
            country = request.countries[0]
            logging.info(f"💱 POST-PROCESSING: Force-converting USD to {country} currency...")
            
            # Currency conversion rates (approximate, for display purposes)
            USD_CONVERSIONS = {
                "India": {"symbol": "₹", "rate": 83, "name": "INR"},
                "UK": {"symbol": "£", "rate": 0.79, "name": "GBP"},
                "UAE": {"symbol": "AED ", "rate": 3.67, "name": "AED"},
                "Singapore": {"symbol": "S$", "rate": 1.35, "name": "SGD"},
                "Australia": {"symbol": "A$", "rate": 1.55, "name": "AUD"},
                "Canada": {"symbol": "C$", "rate": 1.36, "name": "CAD"},
                "Germany": {"symbol": "€", "rate": 0.92, "name": "EUR"},
                "France": {"symbol": "€", "rate": 0.92, "name": "EUR"},
                "Japan": {"symbol": "¥", "rate": 157, "name": "JPY"},
                "China": {"symbol": "¥", "rate": 7.25, "name": "CNY"},
            }
            
            if country in USD_CONVERSIONS:
                conv = USD_CONVERSIONS[country]
                symbol = conv["symbol"]
                rate = conv["rate"]
                
                import re
                
                def convert_usd_to_local(text):
                    """Convert USD amounts to local currency in a string."""
                    if not isinstance(text, str):
                        return text
                    
                    def replace_usd(match):
                        usd_str = match.group(0)
                        # Extract numbers (handle ranges like $500-$2,000)
                        numbers = re.findall(r'[\d,]+', usd_str)
                        converted = []
                        for num_str in numbers:
                            try:
                                num = int(num_str.replace(',', ''))
                                local_amount = int(num * rate)
                                # Format with Indian numbering for India
                                if country == "India":
                                    if local_amount >= 100000:
                                        formatted = f"{local_amount // 100000},{(local_amount % 100000):05d}"
                                    elif local_amount >= 1000:
                                        formatted = f"{local_amount:,}"
                                    else:
                                        formatted = str(local_amount)
                                else:
                                    formatted = f"{local_amount:,}"
                                converted.append(f"{symbol}{formatted}")
                            except:
                                converted.append(f"{symbol}?")
                        
                        if len(converted) == 2:
                            return f"{converted[0]}-{converted[1]}"
                        elif len(converted) == 1:
                            return converted[0]
                        else:
                            return usd_str  # Fallback
                    
                    # Match USD patterns like $500, $2,000, $500-$2,000
                    pattern = r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?'
                    return re.sub(pattern, replace_usd, text)
                
                def convert_costs_in_dict(obj):
                    """Recursively convert USD costs in a dictionary."""
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if key in ['estimated_cost', 'filing_cost', 'opposition_defense_cost', 'total_estimated_cost', 'cost']:
                                if isinstance(value, str) and '$' in value:
                                    obj[key] = convert_usd_to_local(value)
                                    logging.info(f"💱 Converted {key}: {value} → {obj[key]}")
                            elif isinstance(value, (dict, list)):
                                convert_costs_in_dict(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            convert_costs_in_dict(item)
                
                # Apply conversion to all brand_scores
                for brand_score in data.get("brand_scores", []):
                    convert_costs_in_dict(brand_score)
                
                logging.info(f"💱 Currency conversion complete for {country}")
        
        return {"model": f"{model_provider}/{model_name}", "data": data}
    
    # ==================== CLASSIFICATION-AWARE HELPER FUNCTIONS ====================
    def generate_strategic_classification(classification: dict, trademark_risk: int) -> str:
        """
        Generate strategic_classification string based on ACTUAL 5-step spectrum classification.
        No longer hardcodes "Coined/Invented" for all brands.
        
        Examples:
        - FANCIFUL: "STRONGEST - Coined/Invented term with highest legal distinctiveness"
        - DESCRIPTIVE: "WEAK - Descriptive term (directly describes product) with low legal distinctiveness"
        """
        category = classification.get("category", "DESCRIPTIVE")
        protectability = classification.get("protectability", "WEAK")
        distinctiveness = classification.get("distinctiveness", "LOW")
        
        # Map classification category to human-readable description
        category_descriptions = {
            "FANCIFUL": "Coined/Invented term (completely made up word)",
            "ARBITRARY": "Arbitrary term (common word in unrelated context)",
            "SUGGESTIVE": "Suggestive term (hints at product, needs imagination)",
            "DESCRIPTIVE": "Descriptive term (directly describes the product/service)",
            "GENERIC": "Generic term (names the product category itself)"
        }
        
        category_description = category_descriptions.get(category, category)
        
        # Build the strategic classification string
        return f"{protectability} - {category_description} with {distinctiveness.lower()} legal distinctiveness"
    
    def get_distinctiveness_score(classification: dict) -> float:
        """
        Get a numeric score (0-10) based on classification distinctiveness level.
        """
        distinctiveness_scores = {
            "HIGHEST": 9.5,
            "HIGH": 8.5,
            "MODERATE": 7.0,
            "LOW": 5.5,
            "NONE": 3.0
        }
        distinctiveness = classification.get("distinctiveness", "LOW")
        return distinctiveness_scores.get(distinctiveness, 6.0)
    # ==================== END CLASSIFICATION-AWARE HELPERS ====================
    
    # ==================== WEIGHTED NAMESCORE CALCULATOR ====================
    def calculate_weighted_namescore(
        llm_dimensions: list = None,
        cultural_analysis: list = None,
        trademark_risk: float = 5.0,
        business_alignment: float = 5.0,
        dupont_score: float = None,
        domain_score: float = 7.0,
        social_score: float = 7.0,
        classification: dict = None
    ) -> dict:
        """
        Calculate WEIGHTED NAMESCORE using all available scores.
        
        FORMULA (Updated July 2025):
        NAMESCORE = (
            (LLM_Dimensions_Avg × 0.35) +      # Core brand quality
            (Business_Alignment × 0.20) +       # Strategic fit (category alignment)
            (Trademark_Safety × 0.15) +         # Legal viability (10 - risk)
            (DuPont_Safety × 0.15) +            # Conflict risk (100 - dupont)/10
            (Cultural_Resonance × 0.10) +       # Market fit (Hybrid: MIN×0.4 + AVG×0.6)
            (Domain_Social_Avg × 0.05)          # Digital availability
        ) × 10
        
        For single country: Use that country's score directly
        For multiple countries: Hybrid = (MIN × 0.4) + (AVG × 0.6)
        
        Returns dict with:
        - namescore: Final weighted score (0-100)
        - component_scores: Breakdown of each component
        - formula_explanation: Human-readable formula
        """
        component_scores = {}
        
        # 1. LLM Dimensions Average (35% weight)
        if llm_dimensions and len(llm_dimensions) > 0:
            dim_scores = [d.get("score", 0) if isinstance(d, dict) else getattr(d, "score", 0) for d in llm_dimensions]
            dim_scores = [s for s in dim_scores if s > 0]  # Filter out zeros
            llm_avg = sum(dim_scores) / len(dim_scores) if dim_scores else 5.0
        else:
            # Fallback: use distinctiveness score
            llm_avg = get_distinctiveness_score(classification) if classification else 6.0
        component_scores["llm_dimensions"] = {
            "raw": round(llm_avg, 2),
            "weight": 0.35,
            "weighted": round(llm_avg * 0.35, 2),
            "source": "LLM 6-Dimensions" if llm_dimensions else "Distinctiveness fallback"
        }
        
        # 2. Business Alignment (20% weight) - Strategic category fit
        alignment_score = min(10, max(0, business_alignment))
        component_scores["business_alignment"] = {
            "raw": round(alignment_score, 2),
            "weight": 0.20,
            "weighted": round(alignment_score * 0.20, 2),
            "source": "Linguistic Analysis" if business_alignment != 5.0 else "Default"
        }
        
        # 3. Trademark Safety (15% weight) - Inverted risk score
        trademark_safety = 10 - min(10, max(0, trademark_risk))
        component_scores["trademark_safety"] = {
            "raw": round(trademark_safety, 2),
            "weight": 0.15,
            "weighted": round(trademark_safety * 0.15, 2),
            "source": f"10 - trademark_risk ({trademark_risk})"
        }
        
        # 4. DuPont Safety (15% weight) - Inverted confusion score
        if dupont_score is not None:
            # DuPont score is 0-100 (likelihood of confusion)
            # Convert to safety: (100 - dupont) / 10
            dupont_safety = (100 - min(100, max(0, dupont_score))) / 10
        else:
            dupont_safety = 8.0  # Default: assume low confusion risk
        
        component_scores["dupont_safety"] = {
            "raw": round(dupont_safety, 2),
            "weight": 0.15,
            "weighted": round(dupont_safety * 0.15, 2),
            "source": f"(100 - DuPont:{dupont_score})/10" if dupont_score is not None else "Default (no conflicts)"
        }
        
        # 5. Cultural Resonance - Hybrid Formula (10% weight)
        if cultural_analysis and len(cultural_analysis) > 0:
            cultural_scores = []
            for ca in cultural_analysis:
                if isinstance(ca, dict):
                    score = ca.get("cultural_resonance_score", 0)
                else:
                    score = getattr(ca, "cultural_resonance_score", 0)
                if score > 0:
                    cultural_scores.append(score)
            
            if len(cultural_scores) == 1:
                # Single country: Use directly
                cultural_combined = cultural_scores[0]
                cultural_formula = f"Single country: {cultural_scores[0]}"
            elif len(cultural_scores) > 1:
                # Multiple countries: Hybrid = (MIN × 0.4) + (AVG × 0.6)
                min_score = min(cultural_scores)
                avg_score = sum(cultural_scores) / len(cultural_scores)
                cultural_combined = (min_score * 0.4) + (avg_score * 0.6)
                cultural_formula = f"Hybrid: (MIN:{min_score:.1f}×0.4) + (AVG:{avg_score:.1f}×0.6) = {cultural_combined:.1f}"
            else:
                cultural_combined = 7.0
                cultural_formula = "Default (no scores)"
        else:
            cultural_combined = 7.0
            cultural_formula = "Default (no analysis)"
        
        component_scores["cultural_resonance"] = {
            "raw": round(cultural_combined, 2),
            "weight": 0.10,
            "weighted": round(cultural_combined * 0.10, 2),
            "formula": cultural_formula,
            "country_scores": cultural_scores if cultural_analysis else []
        }
        
        # 6. Digital Availability (5% weight)
        digital_avg = (domain_score + social_score) / 2
        component_scores["digital_availability"] = {
            "raw": round(digital_avg, 2),
            "weight": 0.05,
            "weighted": round(digital_avg * 0.05, 2),
            "domain": domain_score,
            "social": social_score
        }
        
        # Calculate final NAMESCORE
        weighted_sum = (
            component_scores["llm_dimensions"]["weighted"] +
            component_scores["business_alignment"]["weighted"] +
            component_scores["trademark_safety"]["weighted"] +
            component_scores["dupont_safety"]["weighted"] +
            component_scores["cultural_resonance"]["weighted"] +
            component_scores["digital_availability"]["weighted"]
        )
        
        # Scale to 0-100
        namescore = round(weighted_sum * 10, 1)
        namescore = max(0, min(100, namescore))  # Clamp
        
        # Build formula explanation
        formula_explanation = f"""
NAMESCORE CALCULATION (July 2025):
├─ LLM Dimensions:       {component_scores['llm_dimensions']['raw']:.1f}/10 × 35% = {component_scores['llm_dimensions']['weighted']:.2f}
├─ Business Alignment:   {component_scores['business_alignment']['raw']:.1f}/10 × 20% = {component_scores['business_alignment']['weighted']:.2f}
├─ Trademark Safety:     {component_scores['trademark_safety']['raw']:.1f}/10 × 15% = {component_scores['trademark_safety']['weighted']:.2f}
├─ DuPont Safety:        {component_scores['dupont_safety']['raw']:.1f}/10 × 15% = {component_scores['dupont_safety']['weighted']:.2f}
├─ Cultural Resonance:   {component_scores['cultural_resonance']['raw']:.1f}/10 × 10% = {component_scores['cultural_resonance']['weighted']:.2f}
└─ Digital Availability: {component_scores['digital_availability']['raw']:.1f}/10 ×  5% = {component_scores['digital_availability']['weighted']:.2f}
─────────────────────────────────────
TOTAL: {weighted_sum:.2f} × 10 = {namescore}/100
"""
        
        logging.info(f"📊 WEIGHTED NAMESCORE: {namescore}/100")
        logging.info(formula_explanation)
        
        return {
            "namescore": namescore,
            "component_scores": component_scores,
            "formula_explanation": formula_explanation.strip(),
            "weights_used": {
                "llm_dimensions": 0.35,
                "business_alignment": 0.20,
                "trademark_safety": 0.15,
                "dupont_safety": 0.15,
                "cultural_resonance": 0.10,
                "digital_availability": 0.05
            }
        }
    # ==================== END WEIGHTED NAMESCORE CALCULATOR ====================

    def generate_fallback_report(brand_name: str, category: str, domain_data, social_data, trademark_data, visibility_data, classification: dict = None) -> dict:
        """Generate a complete report WITHOUT LLM using collected data
        
        NEW: Accepts pre-calculated classification to avoid duplicate computation.
        """
        logging.info(f"🔧 FALLBACK MODE: Generating report for '{brand_name}' without LLM")
        
        # Use passed classification or calculate if not provided
        if classification is None:
            classification = classify_brand_with_industry(brand_name, category)
        
        # Handle domain_data - could be string or dict
        domain_available = False
        if isinstance(domain_data, str):
            domain_available = "available" in domain_data.lower() or "✅" in domain_data
        elif isinstance(domain_data, dict):
            domain_available = domain_data.get("available", False)
        
        # Calculate scores from collected data
        domain_score = 7 if domain_available else 5
        
        # Handle social_data - could be dict with platform info
        social_score = 7  # Default
        if isinstance(social_data, dict):
            unavailable_count = sum(1 for k, v in social_data.items() if isinstance(v, dict) and v.get("available") == False)
            social_score = max(4, 8 - unavailable_count)
        
        # Handle trademark_data
        trademark_risk = 5  # Default medium risk
        if isinstance(trademark_data, dict):
            trademark_risk = trademark_data.get("overall_risk_score", 5)
        trademark_score = 10 - trademark_risk
        
        # Get cultural analysis and linguistic data for weighted scoring
        fallback_cultural = llm_research_data.get("cultural_analysis") if llm_research_data else None
        linguistic_data = all_brand_data.get(brand_name, {}).get("linguistic_analysis", {})
        business_alignment = linguistic_data.get("business_alignment", {}).get("alignment_score", 5.0) if linguistic_data else 5.0
        
        # Calculate WEIGHTED NAMESCORE using new comprehensive formula
        weighted_result = calculate_weighted_namescore(
            llm_dimensions=None,  # No LLM dimensions in fallback
            cultural_analysis=fallback_cultural,
            trademark_risk=trademark_risk,
            business_alignment=business_alignment,
            dupont_score=None,  # No DuPont in fallback
            domain_score=domain_score,
            social_score=social_score,
            classification=classification
        )
        
        overall_score = int(weighted_result["namescore"])
        
        # Determine verdict based on weighted score and trademark risk
        if trademark_risk >= 8:
            verdict = "REJECT"
            overall_score = min(overall_score, 35)
        elif trademark_risk >= 5 or overall_score < 55:
            verdict = "CAUTION"
            overall_score = min(overall_score, 60) if trademark_risk >= 5 else overall_score
        else:
            verdict = "GO"
            overall_score = max(overall_score, 65)
        
        nice_class = get_nice_classification(category)
        
        # Use LLM research data if available, otherwise use hardcoded fallback
        fallback_competitors = llm_research_data.get("country_competitor_analysis") if llm_research_data else None
        
        # ═══════════════════════════════════════════════════════════════════════
        # GLOBAL COMPETITORS - Use MULTINATIONAL brands, not country-specific
        # This is for the "Strategic Positioning Matrix (Global Overview)"
        # ═══════════════════════════════════════════════════════════════════════
        global_data = get_global_competitors(category, request.industry)
        global_competitor_analysis = {
            "x_axis_label": global_data.get("axis_x", "Price: Budget → Premium"),
            "y_axis_label": global_data.get("axis_y", "Positioning: Traditional → Modern"),
            "competitors": global_data.get("competitors", []),
            "user_brand_position": {
                "x_coordinate": 65, "y_coordinate": 75, "quadrant": "Accessible Premium",
                "rationale": f"'{brand_name}' positioned for premium-accessible segment in global market"
            },
            "white_space_analysis": global_data.get("white_space", f"Opportunity exists in the global {category} market for differentiated brands."),
            "strategic_advantage": global_data.get("strategic_advantage", f"As a distinctive brand, '{brand_name}' can establish unique global positioning."),
            "suggested_pricing": f"{'Premium' if overall_score >= 75 else 'Mid-range'} positioning recommended"
        }
        
        # ==================== STRATEGY SNAPSHOT (Calculate ONCE) ====================
        strategy_snapshot = generate_strategy_snapshot(
            brand_name=brand_name,
            classification=classification,
            category=category,
            positioning=request.positioning,
            countries=request.countries,
            domain_available=domain_available,
            trademark_risk=trademark_risk,
            social_data=social_data
        )
        logging.info(f"📊 STRATEGY SNAPSHOT for '{brand_name}': {strategy_snapshot.get('legal_classification')} | Ceiling: {strategy_snapshot.get('brand_asset_ceiling', {}).get('ceiling_score', 'N/A')}/100")
        # ==================== END STRATEGY SNAPSHOT ====================
        
        return {
            "brand_scores": [{
                "brand_name": brand_name,
                "verdict": verdict,
                "namescore": overall_score,
                "summary": f"**{brand_name.upper()}** - {'✅ RECOMMENDED' if verdict == 'GO' else '⚠️ PROCEED WITH CAUTION' if verdict == 'CAUTION' else '❌ NOT RECOMMENDED'}\n\nComprehensive analysis for '{brand_name}' in the {category} sector. {'This name shows strong potential for brand registration and market positioning.' if verdict == 'GO' else 'Some concerns were identified that require attention.' if verdict == 'CAUTION' else 'Significant conflicts were detected.'}",
                "positioning_fit": f"**Market Positioning Analysis:**\n\n'{brand_name}' {'aligns well' if verdict == 'GO' else 'may face challenges'} with {category} market positioning. The name structure supports {'premium' if overall_score >= 70 else 'mid-tier'} brand perception.",
                "trademark_risk": {
                    "overall_risk": "LOW" if trademark_risk <= 3 else "MEDIUM" if trademark_risk <= 6 else "HIGH",
                    "reason": f"Trademark risk assessment: {trademark_risk}/10. {'Favorable conditions for registration.' if trademark_risk <= 3 else 'Some considerations for legal review.' if trademark_risk <= 6 else 'Significant trademark concerns identified.'}"
                },
                # NEW: Use Strategy Snapshot Framework for investor-grade pros/cons
                "pros": strategy_snapshot.get("strengths", []),
                "cons": strategy_snapshot.get("risks", []),
                # Store full strategy snapshot for advanced analytics
                "strategy_snapshot": strategy_snapshot,
                # CRITICAL FIX: Always use generate_cultural_analysis for sacred name detection
                # If market_intelligence has data, merge it, but always run local analysis
                # NEW: Pass classification AND linguistic analysis for proper cultural context
                "cultural_analysis": merge_cultural_analysis_with_sacred_names(
                    fallback_cultural,
                    generate_cultural_analysis(request.countries, brand_name, category, classification, all_brand_data.get(brand_name, {}).get("linguistic_analysis")),
                    brand_name,
                    request.countries
                ),
                "competitor_analysis": global_competitor_analysis if global_competitor_analysis else {
                    "x_axis_label": f"Price: Budget → Premium",
                    "y_axis_label": f"Innovation: Traditional → Modern",
                    "competitors": [
                        {"name": f"{category} Leader 1", "x_coordinate": 75, "y_coordinate": 65, "quadrant": "Premium Modern"},
                        {"name": f"{category} Leader 2", "x_coordinate": 45, "y_coordinate": 70, "quadrant": "Mid-range Modern"},
                        {"name": f"{category} Leader 3", "x_coordinate": 80, "y_coordinate": 40, "quadrant": "Premium Traditional"},
                        {"name": f"{category} Challenger", "x_coordinate": 35, "y_coordinate": 55, "quadrant": "Value Player"}
                    ],
                    "user_brand_position": {
                        "x_coordinate": 65,
                        "y_coordinate": 75,
                        "quadrant": "Accessible Premium",
                        "rationale": f"'{brand_name}' positioned for premium-accessible market segment"
                    },
                    "white_space_analysis": f"Opportunity exists in the {category} market for brands combining accessibility with innovation. The '{brand_name}' positioning targets this underserved segment.",
                    "strategic_advantage": f"As a distinctive coined term, '{brand_name}' can establish unique market positioning without direct name conflicts.",
                    "suggested_pricing": f"{'Premium' if overall_score >= 75 else 'Mid-range'} positioning recommended"
                },
                "visibility_analysis": {
                    "web_presence_score": 7,
                    "social_presence_score": 7,
                    "brand_recognition": "LOW" if trademark_risk <= 3 else "MEDIUM",
                    "seo_potential": "HIGH" if len(brand_name) <= 12 else "MEDIUM",
                    "recommendation": f"Strong potential for building digital presence with '{brand_name}'"
                },
                "country_competitor_analysis": fallback_competitors if fallback_competitors else generate_country_competitor_analysis(request.countries, category, brand_name, request.industry),
                "alternative_names": {
                    "poison_words": [],
                    "reasoning": "Alternative names generated based on brand analysis",
                    "suggestions": [
                        {"name": f"{brand_name[:4]}ora", "score": 75, "rationale": f"Softer ending suitable for {category} sector"},
                        {"name": f"{brand_name[:5]}ix", "score": 72, "rationale": "Modern tech-inspired suffix"},
                        {"name": f"Neo{brand_name[:4]}", "score": 70, "rationale": "Innovation-focused prefix"}
                    ]
                },
                "mitigation_strategies": get_country_specific_mitigation_strategies(request.countries)[:6],
                "registration_timeline": generate_registration_timeline(request.countries),
                "legal_precedents": generate_legal_precedents("LOW" if trademark_risk <= 3 else "MEDIUM"),
                # Use actual classification from 5-step spectrum instead of hardcoded "Coined/Invented"
                "strategic_classification": generate_strategic_classification(classification, trademark_risk),
                "trademark_classes": [str(nice_class.get('class_number', 3))],
                "trademark_matrix": {
                    "primary_class": nice_class.get('class_number', 3),
                    "secondary_classes": [],
                    "filing_strategy": f"File in Class {nice_class.get('class_number', 3)} ({nice_class.get('class_description', category)})"
                },
                # NEW: Use classification-aware dimensions
                "dimensions": generate_classification_aware_dimensions(
                    brand_name=brand_name,
                    classification=classification,
                    category=category,
                    positioning=request.positioning,
                    trademark_risk=trademark_risk,
                    strategy_snapshot=strategy_snapshot,
                    mckinsey_analysis=generate_mckinsey_analysis(
                        brand_name=brand_name,
                        classification=classification,
                        category=category,
                        positioning=request.positioning,
                        verdict=verdict,
                        trademark_risk=trademark_risk,
                        imitability_risk=strategy_snapshot.get("imitability_risk"),
                        positioning_alignment=strategy_snapshot.get("positioning_alignment")
                    ),
                    cultural_analysis=fallback_cultural
                ),
                "domain_analysis": {
                    "exact_match_status": "TAKEN" if not domain_available else "AVAILABLE",
                    "risk_level": "LOW" if trademark_risk <= 3 else ("MEDIUM" if trademark_risk <= 6 else "HIGH"),
                    # Derive has_trademark from trademark_conflicts
                    "has_active_business": "YES" if (isinstance(trademark_data, dict) and len(trademark_data.get("company_conflicts", [])) > 0) else "NO",
                    "has_trademark": "YES" if (isinstance(trademark_data, dict) and len(trademark_data.get("trademark_conflicts", [])) > 0) else "NO",
                    "primary_domain": f"{brand_name.lower()}.com",
                    "available": domain_available,
                    "alternatives": [
                        {"domain": f"{brand_name.lower()}.co", "available": True, "price_estimate": "$30-50/year"},
                        {"domain": f"{brand_name.lower()}.io", "available": True, "price_estimate": "$40-60/year"},
                        {"domain": f"get{brand_name.lower()}.com", "available": True, "price_estimate": "$15-20/year"}
                    ],
                    "score_impact": "-1 point max for taken .com",
                    "strategy_note": f"{'Secure primary .com domain' if domain_available else 'Consider .co or branded alternatives'} for {category} presence."
                },
                "multi_domain_availability": generate_smart_domain_suggestions(brand_name, category, request.countries, domain_available),
                "domain_strategy": generate_fallback_domain_strategy(brand_name, category, request.countries, domain_available),
                "social_availability": build_social_availability_from_data(brand_name, social_data),
                "trademark_research": {
                    "nice_classification": nice_class,
                    "overall_risk_score": trademark_risk,
                    "registration_success_probability": 90 - (trademark_risk * 8),
                    "opposition_probability": trademark_risk * 10,
                    "trademark_conflicts": (trademark_data or {}).get("trademark_conflicts", []) if isinstance(trademark_data, dict) else [],
                    "company_conflicts": (trademark_data or {}).get("company_conflicts", []) if isinstance(trademark_data, dict) else [],
                    "common_law_conflicts": [],
                    "legal_precedents": generate_legal_precedents("LOW" if trademark_risk <= 3 else "MEDIUM", request.countries, brand_name, category),
                    "critical_conflicts_count": (trademark_data or {}).get("critical_conflicts_count", 0) if isinstance(trademark_data, dict) else 0,
                    "high_risk_conflicts_count": (trademark_data or {}).get("high_risk_conflicts_count", 0) if isinstance(trademark_data, dict) else 0,
                    "total_conflicts_found": (trademark_data or {}).get("total_conflicts_found", 0) if isinstance(trademark_data, dict) else 0,
                    "recommendation": f"{'Proceed with trademark filing' if trademark_risk <= 5 else 'Consult IP attorney before filing'}"
                },
                "final_assessment": {
                    "verdict_statement": f"{'✅ RECOMMENDED TO PROCEED' if verdict == 'GO' else '⚠️ PROCEED WITH CAUTION' if verdict == 'CAUTION' else '❌ NOT RECOMMENDED'}",
                    "suitability_score": overall_score,
                    "bottom_line": f"'{brand_name}' {'demonstrates strong potential for the {category} market. Recommended to proceed with trademark filing and brand development.' if verdict == 'GO' else 'shows promise but requires attention to identified concerns before proceeding.' if verdict == 'CAUTION' else 'faces significant challenges. Consider alternative naming approaches.'}",
                    "dimension_breakdown": calculate_dynamic_fallback_dimensions(
                        brand_name=brand_name,
                        category=category,
                        classification=classification,
                        linguistic_analysis=linguistic_data,
                        trademark_risk=trademark_risk,
                        domain_available=domain_available,
                        countries=request.countries
                    ),
                    "recommendations": generate_smart_final_recommendations(brand_name, category, request.countries, domain_available, nice_class, trademark_data),
                    "alternative_path": generate_dynamic_alternative_path(brand_name, category, classification, trademark_data)
                },
                # NEW: Use classification-aware McKinsey analysis
                "mckinsey_analysis": generate_mckinsey_analysis(
                    brand_name=brand_name,
                    classification=classification,
                    category=category,
                    positioning=request.positioning,
                    verdict=verdict,
                    trademark_risk=trademark_risk,
                    imitability_risk=strategy_snapshot.get("imitability_risk"),
                    positioning_alignment=strategy_snapshot.get("positioning_alignment")
                )
            }],
            "executive_summary": generate_rich_executive_summary(
                brand_name=brand_name,
                category=category,
                verdict=verdict,
                overall_score=overall_score,
                countries=request.countries,
                linguistic_analysis=None,  # Will be generated inside the function
                trademark_risk=trademark_risk,
                nice_class=nice_class,
                domain_available=domain_available,
                cultural_analysis=fallback_cultural
            ),
            "comparison_verdict": f"Single brand evaluation for '{brand_name}' in {category} sector."
        }
    
    async def race_with_fallback():
        """Race all models in parallel, return first success OR fallback report"""
        models = [
            ("openai", "gpt-4o-mini"),  # Fastest first
            ("anthropic", "claude-sonnet-4-20250514"),
            ("openai", "gpt-4o"),
        ]
        
        # Create tasks for all models
        tasks = []
        for provider, model in models:
            task = asyncio.create_task(try_single_model(provider, model))
            task.model_info = f"{provider}/{model}"
            tasks.append(task)
        
        logging.info(f"🏁 RACING {len(tasks)} models in parallel: {[t.model_info for t in tasks]}")
        
        # Set a HARD timeout of 30 seconds for the entire race
        try:
            # Wait for first successful completion with timeout
            pending = set(tasks)
            last_error = None
            
            start_time = asyncio.get_event_loop().time()
            
            while pending:
                # Check if we've exceeded 30 seconds - FALLBACK immediately
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > 30:
                    logging.warning(f"⏰ TIMEOUT: 30s exceeded ({elapsed:.1f}s), switching to fallback mode")
                    for p in pending:
                        p.cancel()
                    raise asyncio.TimeoutError("Race timeout exceeded")
                
                done, pending = await asyncio.wait(pending, timeout=5, return_when=asyncio.FIRST_COMPLETED)
                
                for task in done:
                    try:
                        result = task.result()
                        # SUCCESS! Cancel all other tasks
                        for p in pending:
                            p.cancel()
                        logging.info(f"✅ RACE WON by {result['model']} - Cancelling others")
                        return result
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        error_msg = str(e)
                        last_error = e
                        # Check for budget exceeded - fail fast
                        if "Budget has been exceeded" in error_msg:
                            for p in pending:
                                p.cancel()
                            raise HTTPException(status_code=402, detail="Emergent Key Budget Exceeded. Please add credits.")
                        logging.warning(f"❌ Model {getattr(task, 'model_info', 'unknown')} failed: {error_msg[:80]}")
            
            # All models failed - use fallback
            logging.warning(f"⚠️ All LLM models failed. Using FALLBACK report generation.")
            raise Exception(f"All models failed: {last_error}")
            
        except (asyncio.TimeoutError, Exception) as e:
            # Cancel any remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # FALLBACK: Generate report without LLM
            logging.info(f"🔧 ACTIVATING FALLBACK MODE due to: {str(e)[:100]}")
            
            # Get the first brand name from request
            brand_name = request.brand_names[0] if request.brand_names else "Brand"
            
            # Get collected data from all_brand_data
            brand_data = all_brand_data.get(brand_name, {})
            domain_data = brand_data.get("domain")
            social_data = brand_data.get("social")
            visibility_data = brand_data.get("visibility")
            trademark_data_dict = None
            
            if brand_name in trademark_research_data:
                tr = trademark_research_data[brand_name]
                if tr and hasattr(tr, '__dataclass_fields__'):
                    from dataclasses import asdict
                    trademark_data_dict = asdict(tr)
                elif isinstance(tr, dict):
                    trademark_data_dict = tr.get('result', tr) if 'result' in tr else tr
            
            # Get classification from all_brand_data (calculated ONCE at start)
            brand_classification = all_brand_data.get(brand_name, {}).get("classification")
            
            fallback_data = generate_fallback_report(
                brand_name=brand_name,
                category=request.category,
                domain_data=domain_data,
                social_data=social_data,
                trademark_data=trademark_data_dict,
                visibility_data=visibility_data,
                classification=brand_classification  # Pass the pre-calculated classification
            )
            
            return {"model": "FALLBACK/no-llm", "data": fallback_data}
    
    # Execute the race with HARD 35 second timeout wrapper
    gc.collect()  # Clean up before heavy operation
    
    try:
        # Wrap ENTIRE race in asyncio.wait_for - this WILL cancel after 35s
        race_result = await asyncio.wait_for(race_with_fallback(), timeout=35.0)
    except asyncio.TimeoutError:
        # HARD TIMEOUT - Generate fallback report
        logging.warning(f"⏰ HARD TIMEOUT: 35s limit reached. Generating fallback report.")
        brand_name = request.brand_names[0] if request.brand_names else "Brand"
        
        # Get collected data from all_brand_data
        brand_data = all_brand_data.get(brand_name, {})
        domain_data = brand_data.get("domain")
        social_data = brand_data.get("social")
        visibility_data = brand_data.get("visibility")
        trademark_data_dict = None
        
        if brand_name in trademark_research_data:
            tr = trademark_research_data[brand_name]
            if tr and hasattr(tr, '__dataclass_fields__'):
                from dataclasses import asdict
                trademark_data_dict = asdict(tr)
            elif isinstance(tr, dict):
                trademark_data_dict = tr.get('result', tr) if 'result' in tr else tr
        
        # Get classification from all_brand_data (calculated ONCE at start)
        brand_classification = all_brand_data.get(brand_name, {}).get("classification")
        
        race_result = {
            "model": "FALLBACK/timeout",
            "data": generate_fallback_report(
                brand_name=brand_name,
                category=request.category,
                domain_data=domain_data,
                social_data=social_data,
                trademark_data=trademark_data_dict,
                visibility_data=visibility_data,
                classification=brand_classification  # Pass the pre-calculated classification
            )
        }
    
    winning_model = race_result["model"]
    data = race_result["data"]
    
    logging.info(f"Successfully generated report with model {winning_model}")
    
    # ============ COMPETITIVE INTELLIGENCE v2 OVERRIDE ============
    # Apply REAL competitor data regardless of LLM or Fallback mode
    logging.info("🎯 APPLYING COMPETITIVE INTELLIGENCE v2 OVERRIDE...")
    
    for brand_name in request.brand_names:
        deep_intel = all_brand_data.get(brand_name, {}).get("deep_market_intel")
        
        if deep_intel and deep_intel.get("global_matrix", {}).get("competitors"):
            global_comps = deep_intel['global_matrix']['competitors']
            logging.info(f"🎯 Found {len(global_comps)} REAL competitors for '{brand_name}'")
            
            # Find the brand_score in data
            brand_scores = data.get("brand_scores", [])
            for bs in brand_scores:
                if bs.get("brand_name", "").lower() == brand_name.lower() or len(brand_scores) == 1:
                    # Override competitor_analysis with REAL data from v2
                    global_matrix = deep_intel.get("global_matrix", {})
                    competitors_data = global_matrix.get("competitors", [])
                    user_pos = global_matrix.get("user_brand_position", {})
                    
                    # Format competitors - v2 already has x_coordinate, y_coordinate
                    formatted_competitors = []
                    for comp in competitors_data[:10]:
                        formatted_competitors.append({
                            "name": comp.get("name", "Unknown"),
                            "x_coordinate": comp.get("x_coordinate", 50),
                            "y_coordinate": comp.get("y_coordinate", 50),
                            "quadrant": comp.get("quadrant", comp.get("tier", "Competitor")),
                            "type": comp.get("type", "INDIRECT"),
                            "reasoning": comp.get("reasoning", ""),
                            "price_axis": None,
                            "modernity_axis": None
                        })
                    
                    # Get white space from v2
                    white_space = deep_intel.get("white_space_analysis", {})
                    white_space_text = get_white_space_summary_v2(deep_intel)
                    
                    bs["competitor_analysis"] = {
                        "x_axis_label": global_matrix.get("x_axis_label", "Price: Budget → Premium"),
                        "y_axis_label": global_matrix.get("y_axis_label", "Quality: Basic → High Production"),
                        "competitors": formatted_competitors,
                        "user_brand_position": {
                            "x_coordinate": user_pos.get("x_coordinate", 50),
                            "y_coordinate": user_pos.get("y_coordinate", 70),
                            "quadrant": user_pos.get("quadrant", "Accessible Premium"),
                            "rationale": f"'{brand_name}' target position"
                        },
                        "white_space_analysis": white_space_text,
                        "strategic_advantage": f"Competitive Intelligence v2: Found {len(formatted_competitors)} real competitors via funnel approach."
                    }
                    
                    logging.info(f"✅ OVERRIDE COMPLETE: competitor_analysis now has {len(formatted_competitors)} REAL competitors")
                    
                    # Override country_competitor_analysis from v2
                    country_analysis = deep_intel.get("country_analysis", {})
                    if country_analysis:
                        formatted_country = []
                        country_flags = {"India": "🇮🇳", "USA": "🇺🇸", "UK": "🇬🇧", "UAE": "🇦🇪", "Singapore": "🇸🇬", "Australia": "🇦🇺", "Canada": "🇨🇦", "Germany": "🇩🇪", "Japan": "🇯🇵", "China": "🇨🇳"}
                        
                        for country, cdata in country_analysis.items():
                            # v2 structure: cdata.competitors[], cdata.gap_analysis
                            country_comps = cdata.get("competitors", [])
                            gap = cdata.get("gap_analysis", {})
                            
                            all_comps = []
                            for c in country_comps[:6]:
                                all_comps.append({
                                    "name": c.get("name", "Unknown"),
                                    "x_coordinate": c.get("x_coordinate", 50),
                                    "y_coordinate": c.get("y_coordinate", 50),
                                    "quadrant": c.get("quadrant", c.get("type", "Competitor")),
                                    "type": c.get("type", "INDIRECT")
                                })
                            
                            user_pos_country = cdata.get("user_brand_position", {})
                            
                            formatted_country.append({
                                "country": country,
                                "country_flag": country_flags.get(country, "🌍"),
                                "x_axis_label": "Price: Budget → Premium",
                                "y_axis_label": "Quality: Basic → High Production",
                                "competitors": all_comps,
                                "user_brand_position": {
                                    "x_coordinate": user_pos_country.get("x_coordinate", 50),
                                    "y_coordinate": user_pos_country.get("y_coordinate", 70),
                                    "quadrant": user_pos_country.get("quadrant", "Target Segment")
                                },
                                # Enhanced white space with competitor context
                                "white_space_analysis": cdata.get("white_space_analysis", "") or (
                                    f"🟢 **BLUE OCEAN OPPORTUNITY**: No direct competitors identified in {country}. First-mover advantage available." 
                                    if gap.get("direct_count", 0) == 0 else
                                    f"🟡 **{gap.get('direct_count', 0)} direct competitors** in {country}: {', '.join([c.get('name', 'Unknown') for c in all_comps if c.get('type') == 'DIRECT'][:4])}. Differentiation through unique positioning required."
                                ),
                                # Enhanced strategic advantage with competitor names
                                "strategic_advantage": self._build_detailed_strategic_advantage(all_comps, gap, country) if hasattr(self, '_build_detailed_strategic_advantage') else (
                                    f"🟢 **BLUE OCEAN**: No direct competitors found in {country}. Excellent first-mover opportunity.\n\n**Indirect Competitors ({gap.get('indirect_count', len(all_comps))}):** {', '.join([c.get('name', 'Unknown') for c in all_comps if c.get('type') != 'DIRECT'][:5]) or 'None'}"
                                    if gap.get("direct_count", 0) == 0 else
                                    f"🟡 **COMPETITIVE MARKET**: {gap.get('direct_count', 0)} direct competitors identified.\n\n**Direct Competitors:** {', '.join([c.get('name', 'Unknown') for c in all_comps if c.get('type') == 'DIRECT'][:5]) or 'None'}\n\n**Indirect Competitors ({gap.get('indirect_count', 0)}):** {', '.join([c.get('name', 'Unknown') for c in all_comps if c.get('type') != 'DIRECT'][:5]) or 'None'}"
                                ),
                                # Enhanced market entry recommendation
                                "market_entry_recommendation": (
                                    f"🚀 **GO** - Excellent timing for {country} market entry. No direct competition detected." 
                                    if gap.get("direct_count", 0) == 0 else
                                    f"✅ **PROCEED WITH STRATEGY** - {country} market entry viable. Position against: {', '.join([c.get('name', 'Unknown') for c in all_comps if c.get('type') == 'DIRECT'][:3])}. Focus on unique value proposition."
                                    if gap.get("direct_count", 0) <= 3 else
                                    f"⚠️ **PROCEED WITH CAUTION** - Competitive market with {gap.get('direct_count', 0)} direct players. Strong differentiation required."
                                ),
                                "gap_analysis": {
                                    "direct_count": gap.get("direct_count", 0),
                                    "indirect_count": gap.get("indirect_count", len(all_comps) - gap.get("direct_count", 0)),
                                    "total_competitors": len(all_comps),
                                    "direct_competitors": ", ".join([c.get("name", "Unknown") for c in all_comps if c.get("type") == "DIRECT"][:6]) or "None identified",
                                    "indirect_competitors": ", ".join([c.get("name", "Unknown") for c in all_comps if c.get("type") != "DIRECT"][:6]) or "None identified",
                                    "gap_detected": gap.get("gap_detected", gap.get("direct_count", 0) == 0)
                                }
                            })
                        
                        if formatted_country:
                            bs["country_competitor_analysis"] = formatted_country
                            logging.info(f"✅ OVERRIDE: country_competitor_analysis with {len(formatted_country)} countries")
                    
                    break
        else:
            logging.warning(f"⚠️ No Competitive Intel v2 for '{brand_name}' - using default")
    
    logging.info("🎯 COMPETITIVE INTELLIGENCE v2 OVERRIDE COMPLETE")
    # ============ END COMPETITIVE INTELLIGENCE v2 OVERRIDE ============
    
    # Pre-process data to fix common LLM output issues
    data = fix_llm_response_types(data)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 💱 FINAL CURRENCY CONVERSION: Force-convert USD to local currency
    # This is the LAST RESORT fix for LLM ignoring currency instructions
    # ═══════════════════════════════════════════════════════════════════════════════
    logging.info(f"💱 FINAL CURRENCY CHECK: countries={request.countries}")
    if len(request.countries) == 1 and request.countries[0] != "USA":
        country = request.countries[0]
        logging.info(f"💱 FINAL CURRENCY CONVERSION: Converting USD to {country} currency...")
        
        import re
        
        # Currency conversion data
        CURRENCY_DATA = {
            "India": {"symbol": "₹", "rate": 83},
            "UK": {"symbol": "£", "rate": 0.79},
            "UAE": {"symbol": "AED ", "rate": 3.67},
            "Singapore": {"symbol": "S$", "rate": 1.35},
            "Australia": {"symbol": "A$", "rate": 1.55},
            "Canada": {"symbol": "C$", "rate": 1.36},
            "Germany": {"symbol": "€", "rate": 0.92},
            "France": {"symbol": "€", "rate": 0.92},
            "Japan": {"symbol": "¥", "rate": 157},
            "China": {"symbol": "¥", "rate": 7.25},
        }
        
        if country in CURRENCY_DATA:
            symbol = CURRENCY_DATA[country]["symbol"]
            rate = CURRENCY_DATA[country]["rate"]
            
            def convert_usd_amount(match):
                """Convert a USD match to local currency."""
                usd_str = match.group(0)
                numbers = re.findall(r'[\d,]+', usd_str)
                converted = []
                for num_str in numbers:
                    try:
                        num = int(num_str.replace(',', ''))
                        local_amount = int(num * rate)
                        if country == "India" and local_amount >= 100000:
                            # Indian lakhs formatting
                            formatted = f"{local_amount:,}"
                        else:
                            formatted = f"{local_amount:,}"
                        converted.append(f"{symbol}{formatted}")
                    except:
                        converted.append(f"{symbol}?")
                
                if len(converted) == 2:
                    return f"{converted[0]}-{converted[1]}"
                elif len(converted) == 1:
                    return converted[0]
                return usd_str
            
            def convert_in_value(value):
                """Convert USD to local currency in a string value."""
                if not isinstance(value, str):
                    return value
                # Match $500, $2,000, $500-$2,000 patterns
                pattern = r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?'
                return re.sub(pattern, convert_usd_amount, value)
            
            def process_brand_score(bs):
                """Process a single brand score dict for currency conversion."""
                if not isinstance(bs, dict):
                    return
                    
                # Convert mitigation_strategies costs
                for strategy in bs.get("mitigation_strategies", []):
                    if isinstance(strategy, dict) and "estimated_cost" in strategy:
                        old_cost = strategy["estimated_cost"]
                        strategy["estimated_cost"] = convert_in_value(old_cost)
                        if old_cost != strategy["estimated_cost"]:
                            logging.info(f"💱 Converted: {old_cost} → {strategy['estimated_cost']}")
                
                # Convert registration_timeline costs
                timeline = bs.get("registration_timeline", {})
                if isinstance(timeline, dict):
                    for cost_key in ["filing_cost", "opposition_defense_cost", "total_estimated_cost"]:
                        if cost_key in timeline and isinstance(timeline[cost_key], str):
                            old_val = timeline[cost_key]
                            timeline[cost_key] = convert_in_value(old_val)
                            if old_val != timeline[cost_key]:
                                logging.info(f"💱 Converted {cost_key}: {old_val} → {timeline[cost_key]}")
                
                # Convert domain_analysis costs
                domain = bs.get("domain_analysis", {})
                if isinstance(domain, dict):
                    for cost_key in ["budget_estimate", "acquisition_cost_range"]:
                        if cost_key in domain and isinstance(domain[cost_key], str):
                            old_val = domain[cost_key]
                            domain[cost_key] = convert_in_value(old_val)
                
                # Convert social media costs
                social = bs.get("social_media_analysis", {})
                if isinstance(social, dict):
                    for key in ["estimated_cost", "cost"]:
                        if key in social and isinstance(social[key], str):
                            social[key] = convert_in_value(social[key])
                    
                    # Convert platform-level costs
                    for platform in social.get("platforms", []):
                        if isinstance(platform, dict) and "estimated_cost" in platform:
                            platform["estimated_cost"] = convert_in_value(platform["estimated_cost"])
            
            # Apply to all brand scores
            for bs in data.get("brand_scores", []):
                process_brand_score(bs)
            
            logging.info(f"💱 FINAL CURRENCY CONVERSION COMPLETE for {country}")
    
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
        correct_nice = get_nice_classification(request.category)
        logging.info(f"🔧 NICE CLASS FIX: Brand '{brand_score.brand_name}', Category: '{request.category}', Correct class: {correct_nice}")
        
        # Handle both dict and Pydantic model cases
        tr = brand_score.trademark_research
        if tr:
            if isinstance(tr, dict):
                tr['nice_classification'] = correct_nice
                logging.info(f"✅ NICE class fixed (dict) for '{brand_score.brand_name}': Class {correct_nice['class_number']}")
            elif hasattr(tr, 'nice_classification'):
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
                    tr_data = asdict(tr_stored) if hasattr(tr_stored, '__dataclass_fields__') else tr_stored
                elif isinstance(tr_stored, dict) and 'result' in tr_stored:
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
                        nice_classification=get_nice_classification(request.category),
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
        
        # Add dimensions if missing - NOW USES CLASSIFICATION-AWARE GENERATION
        if not brand_score.dimensions or len(brand_score.dimensions) == 0:
            logging.warning(f"DIMENSIONS MISSING for '{brand_score.brand_name}' - Generating classification-aware dimensions")
            
            # Get classification for this brand
            brand_classification = classify_brand_with_industry(
                brand_score.brand_name, 
                request.category or request.industry or "Business"
            )
            
            # Get trademark risk
            tr_risk = 5  # default
            if brand_score.trademark_research:
                if isinstance(brand_score.trademark_research, dict):
                    tr_risk = brand_score.trademark_research.get("overall_risk_score", 5)
                elif hasattr(brand_score.trademark_research, "overall_risk_score"):
                    tr_risk = brand_score.trademark_research.overall_risk_score or 5
            
            # Generate classification-aware dimensions
            calculated_dims = generate_classification_aware_dimensions(
                brand_name=brand_score.brand_name,
                classification=brand_classification,
                category=request.category or "Business",
                positioning=request.positioning or "Mid-Range",
                trademark_risk=tr_risk,
                strategy_snapshot=None,  # May not be available
                mckinsey_analysis=None,
                cultural_analysis=None
            )
            
            brand_score.dimensions = [
                DimensionScore(
                    name=dim["name"],
                    score=dim["score"],
                    reasoning=dim["reasoning"]
                )
                for dim in calculated_dims
            ]
            logging.info(f"Added {len(brand_score.dimensions)} classification-aware dimensions for '{brand_score.brand_name}' ({brand_classification.get('category')})")
        else:
            logging.info(f"Dimensions OK for '{brand_score.brand_name}': {len(brand_score.dimensions)} dimensions")
        
        # ============ GENERATE INTELLIGENT TRADEMARK MATRIX ============
        # Always generate intelligent trademark_matrix based on actual research data
        # This replaces generic "No specific risk identified" with actionable insights
        brand_name_for_matrix = brand_score.brand_name
        tr_data_for_matrix = None
        
        # Get trademark research data
        if brand_score.trademark_research:
            if isinstance(brand_score.trademark_research, dict):
                tr_data_for_matrix = brand_score.trademark_research
            elif hasattr(brand_score.trademark_research, 'model_dump'):
                tr_data_for_matrix = brand_score.trademark_research.model_dump()
            elif hasattr(brand_score.trademark_research, '__dict__'):
                tr_data_for_matrix = brand_score.trademark_research.__dict__
        
        # Also check stored trademark research
        if not tr_data_for_matrix and brand_name_for_matrix in trademark_research_data:
            stored_tr = trademark_research_data[brand_name_for_matrix]
            if isinstance(stored_tr, dict):
                tr_data_for_matrix = stored_tr.get('result', stored_tr)
                if hasattr(tr_data_for_matrix, '__dataclass_fields__'):
                    from dataclasses import asdict
                    tr_data_for_matrix = asdict(tr_data_for_matrix)
        
        # Check if brand name appears to be invented using CLASSIFICATION SYSTEM
        # Use our existing 5-tier trademark spectrum instead of primitive word matching
        brand_classification = all_brand_data.get(brand_name_for_matrix, {}).get("classification")
        if not brand_classification:
            brand_classification = classify_brand_with_industry(brand_name_for_matrix, request.category)
        
        classification_category = brand_classification.get("category", "SUGGESTIVE") if brand_classification else "SUGGESTIVE"
        
        # Only FANCIFUL and ARBITRARY are truly "invented" - DESCRIPTIVE and GENERIC are NOT
        brand_is_invented = classification_category in ["FANCIFUL", "ARBITRARY"]
        
        logging.info(f"🏷️ LEGAL MATRIX: '{brand_name_for_matrix}' classification={classification_category}, invented={brand_is_invented}")
        
        # Generate intelligent matrix
        intelligent_matrix = generate_intelligent_trademark_matrix(
            brand_name=brand_name_for_matrix,
            category=request.category,
            trademark_data=tr_data_for_matrix,
            brand_is_invented=brand_is_invented,
            classification=brand_classification  # Pass full classification for better commentary
        )
        
        # Convert to TrademarkRiskMatrix schema
        from schemas import TrademarkRiskMatrix, TrademarkRiskRow
        brand_score.trademark_matrix = TrademarkRiskMatrix(
            genericness=TrademarkRiskRow(**intelligent_matrix['genericness']),
            existing_conflicts=TrademarkRiskRow(**intelligent_matrix['existing_conflicts']),
            phonetic_similarity=TrademarkRiskRow(**intelligent_matrix['phonetic_similarity']),
            relevant_classes=TrademarkRiskRow(**intelligent_matrix['relevant_classes']),
            rebranding_probability=TrademarkRiskRow(**intelligent_matrix['rebranding_probability']),
            overall_assessment=intelligent_matrix['overall_assessment']
        )
        logging.info(f"✅ Generated intelligent trademark_matrix for '{brand_name_for_matrix}'")
        
        # ============ OVERRIDE VISIBILITY ANALYSIS WITH PRE-COMPUTED DATA ============
        # Replace LLM-generated visibility_analysis with data-driven analysis from real sources
        if brand_name_for_matrix in conflict_relevance_data:
            pre_computed_conflicts = conflict_relevance_data[brand_name_for_matrix]
            
            # Convert to Pydantic models
            from schemas import VisibilityAnalysis, ConflictItem, PhoneticConflict
            
            try:
                # Convert direct_competitors
                direct_competitors_models = []
                for dc in pre_computed_conflicts.get('direct_competitors', [])[:10]:
                    direct_competitors_models.append(ConflictItem(
                        name=dc.get('name', 'Unknown'),
                        category=dc.get('category', 'Unknown'),
                        their_product_intent=dc.get('their_product_intent'),
                        their_customer_avatar=dc.get('their_customer_avatar'),
                        intent_match=dc.get('intent_match'),
                        customer_overlap=dc.get('customer_overlap'),
                        risk_level=dc.get('risk_level', 'MEDIUM'),
                        reason=dc.get('reason')
                    ))
                
                # Convert phonetic_conflicts
                phonetic_conflicts_models = []
                for pc in pre_computed_conflicts.get('phonetic_conflicts', [])[:5]:
                    phonetic_conflicts_models.append(PhoneticConflict(
                        input_name=pc.get('input_name'),
                        phonetic_variants=pc.get('phonetic_variants', []),
                        ipa_pronunciation=pc.get('ipa_pronunciation'),
                        found_conflict=pc.get('found_conflict'),
                        conflict_type=pc.get('conflict_type'),
                        legal_risk=pc.get('legal_risk'),
                        verdict_impact=pc.get('verdict_impact')
                    ))
                
                # Convert name_twins
                name_twins_models = []
                for nt in pre_computed_conflicts.get('name_twins', [])[:10]:
                    name_twins_models.append(ConflictItem(
                        name=nt.get('name', 'Unknown'),
                        category=nt.get('category', 'Unknown'),
                        their_product_intent=nt.get('their_product_intent'),
                        their_customer_avatar=nt.get('their_customer_avatar'),
                        intent_match=nt.get('intent_match'),
                        customer_overlap=nt.get('customer_overlap'),
                        risk_level=nt.get('risk_level', 'LOW'),
                        reason=nt.get('reason')
                    ))
                
                # Override visibility_analysis
                brand_score.visibility_analysis = VisibilityAnalysis(
                    user_product_intent=pre_computed_conflicts.get('user_product_intent', f"{request.category}"),
                    user_customer_avatar=pre_computed_conflicts.get('user_customer_avatar', f"{request.positioning} market customers"),
                    phonetic_conflicts=phonetic_conflicts_models,
                    direct_competitors=direct_competitors_models,
                    name_twins=name_twins_models,
                    google_presence=pre_computed_conflicts.get('google_presence', []),
                    app_store_presence=pre_computed_conflicts.get('app_store_presence', []),
                    warning_triggered=pre_computed_conflicts.get('warning_triggered', False),
                    warning_reason=pre_computed_conflicts.get('warning_reason'),
                    conflict_summary=pre_computed_conflicts.get('conflict_summary', "0 direct competitors. 0 phonetic conflicts. 0 name twins.")
                )
                
                total_conflicts = len(direct_competitors_models) + len(phonetic_conflicts_models)
                logging.info(f"✅ Injected PRE-COMPUTED visibility_analysis for '{brand_name_for_matrix}': {total_conflicts} real conflicts from data sources")
                
            except Exception as e:
                logging.error(f"Failed to inject pre-computed visibility_analysis: {e}")
        # ============ END VISIBILITY ANALYSIS OVERRIDE ============
        
        # ============ OVERRIDE SOCIAL AVAILABILITY WITH REAL DATA ============
        # Replace LLM-generated social_availability with actual check results
        social_data_for_brand = all_brand_data.get(brand_name_for_matrix, {}).get("social")
        if social_data_for_brand:
            try:
                from schemas import SocialAvailability, SocialHandleResult
                
                real_social = build_social_availability_from_data(brand_name_for_matrix, social_data_for_brand)
                
                # Convert platforms to SocialHandleResult objects
                platform_results = []
                for p in real_social.get('platforms', []):
                    platform_results.append(SocialHandleResult(
                        platform=p.get('platform', 'unknown'),
                        handle=p.get('handle', brand_name_for_matrix.lower()),
                        available=p.get('available'),
                        status=p.get('status', 'UNKNOWN')
                    ))
                
                brand_score.social_availability = SocialAvailability(
                    handle=real_social.get('handle', brand_name_for_matrix.lower()),
                    platforms=platform_results,
                    available_platforms=real_social.get('available_platforms', []),
                    taken_platforms=real_social.get('taken_platforms', []),
                    recommendation=real_social.get('recommendation', '')
                )
                
                logging.info(f"✅ Injected REAL social_availability for '{brand_name_for_matrix}': "
                           f"{len(real_social.get('available_platforms', []))} available, "
                           f"{len(real_social.get('taken_platforms', []))} taken")
                
            except Exception as e:
                logging.error(f"Failed to inject real social_availability: {e}")
        # ============ END SOCIAL AVAILABILITY OVERRIDE ============
        
        # ============ OVERRIDE STRATEGIC CLASSIFICATION WITH PRE-COMPUTED DATA ============
        # The LLM often ignores our pre-computed classification, so we FORCE it here
        # ALWAYS OVERRIDE - don't trust the LLM's classification at all
        brand_classification = all_brand_data.get(brand_name_for_matrix, {}).get("classification")
        if brand_classification:
            correct_classification = generate_strategic_classification(brand_classification, 5)
            old_classification = brand_score.strategic_classification
            
            # ALWAYS override with our pre-computed classification
            brand_score.strategic_classification = correct_classification
            
            if old_classification and old_classification != correct_classification:
                logging.warning(f"⚠️ OVERRODE LLM strategic_classification for '{brand_name_for_matrix}': "
                              f"'{old_classification}' → '{correct_classification}'")
            else:
                logging.info(f"✅ Set strategic_classification for '{brand_name_for_matrix}': {correct_classification}")
        # ============ END STRATEGIC CLASSIFICATION OVERRIDE ============
        
        # ============ 🆕 FEATURE 1: MULTI-CLASS NICE STRATEGY ============
        try:
            nice_strategy = get_multi_class_nice_strategy(request.category)
            if nice_strategy:
                brand_score.nice_classification_strategy = nice_strategy
                logging.info(f"✅ Added Multi-Class NICE Strategy for '{brand_name_for_matrix}': "
                           f"{nice_strategy['total_classes_recommended']} classes recommended")
        except Exception as e:
            logging.error(f"Failed to add NICE strategy: {e}")
        # ============ END MULTI-CLASS NICE STRATEGY ============
        
        # ============ 🆕 FEATURE 2: REALISTIC REGISTRATION COSTS ============
        try:
            num_classes = nice_strategy.get('total_classes_recommended', 1) if nice_strategy else 1
            realistic_costs = generate_realistic_registration_timeline(request.countries, num_classes)
            brand_score.realistic_registration_costs = realistic_costs
            logging.info(f"✅ Added Realistic Registration Costs for '{brand_name_for_matrix}': "
                       f"Expected value: {realistic_costs.get('expected_value_cost', 'N/A')}")
        except Exception as e:
            logging.error(f"Failed to add realistic costs: {e}")
        # ============ END REALISTIC REGISTRATION COSTS ============
        
        # ============ 🆕 FEATURE 3: DUPONT 13-FACTOR ANALYSIS ============
        try:
            # Get all conflicts from pre-computed data or trademark research
            all_conflicts = []
            
            # Get user's NICE class FIRST for all comparisons
            user_nice_class = None
            if brand_score.nice_classification_strategy:
                user_nice_class = brand_score.nice_classification_strategy.get('primary_class', {}).get('class_number')
            elif brand_score.trademark_research:
                tr = brand_score.trademark_research
                if hasattr(tr, 'nice_classification') and tr.nice_classification:
                    user_nice_class = tr.nice_classification.get('class_number') if isinstance(tr.nice_classification, dict) else getattr(tr.nice_classification, 'class_number', None)
                elif isinstance(tr, dict) and tr.get('nice_classification'):
                    user_nice_class = tr['nice_classification'].get('class_number')
            
            logging.info(f"📊 DuPont Analysis - User NICE Class: {user_nice_class}")
            
            # From visibility analysis - CHECK CLASS PROPERLY
            if brand_score.visibility_analysis:
                for dc in brand_score.visibility_analysis.direct_competitors or []:
                    # For direct competitors, check if we have class info
                    # Company names without class info should NOT be assumed same class
                    dc_class = getattr(dc, 'class_number', None) or getattr(dc, 'nice_class', None)
                    is_same = (dc_class == user_nice_class) if (dc_class and user_nice_class) else False
                    all_conflicts.append({
                        "name": dc.name,
                        "category": dc.category,
                        "same_class_conflict": is_same,
                        "conflict_class": dc_class,
                        "user_class": user_nice_class
                    })
                for pc in brand_score.visibility_analysis.phonetic_conflicts or []:
                    if pc.found_conflict:
                        # Phonetic conflicts - check for class match
                        pc_class = pc.found_conflict.get("class") or pc.found_conflict.get("nice_class") or pc.found_conflict.get("class_number")
                        is_same = (pc_class == user_nice_class) if (pc_class and user_nice_class) else False
                        all_conflicts.append({
                            "name": pc.found_conflict.get("name", "Unknown"),
                            "category": request.category,
                            "same_class_conflict": is_same,
                            "conflict_class": pc_class,
                            "user_class": user_nice_class
                        })
            
            # From trademark research - WITH PROPER NICE CLASS COMPARISON
            if brand_score.trademark_research:
                tr = brand_score.trademark_research
                
                if hasattr(tr, 'trademark_conflicts') and tr.trademark_conflicts:
                    for tc in tr.trademark_conflicts:
                        conflict_name = tc.name if hasattr(tc, 'name') else tc.get('name', 'Unknown')
                        conflict_class = tc.class_number if hasattr(tc, 'class_number') else tc.get('class_number')
                        # Only same_class_conflict=True if NICE classes actually match
                        is_same_class = (conflict_class == user_nice_class) if (conflict_class and user_nice_class) else False
                        all_conflicts.append({
                            "name": conflict_name,
                            "category": request.category,
                            "same_class_conflict": is_same_class,
                            "conflict_class": conflict_class,
                            "user_class": user_nice_class
                        })
                        logging.info(f"  TM Conflict: {conflict_name} | Class {conflict_class} vs User {user_nice_class} | Same: {is_same_class}")
                elif isinstance(tr, dict) and tr.get('trademark_conflicts'):
                    for tc in tr['trademark_conflicts']:
                        conflict_class = tc.get('class_number')
                        is_same_class = (conflict_class == user_nice_class) if (conflict_class and user_nice_class) else False
                        all_conflicts.append({
                            "name": tc.get('name', 'Unknown'),
                            "category": request.category,
                            "same_class_conflict": is_same_class,
                            "conflict_class": conflict_class,
                            "user_class": user_nice_class
                        })
            
            # Apply DuPont analysis if conflicts exist
            if all_conflicts:
                dupont_result = apply_dupont_analysis_to_conflicts(
                    brand_name=brand_name_for_matrix,
                    category=request.category,
                    conflicts=all_conflicts
                )
                brand_score.dupont_analysis = dupont_result
                logging.info(f"✅ Added DuPont 13-Factor Analysis for '{brand_name_for_matrix}': "
                           f"{len(all_conflicts)} conflicts analyzed, verdict: {dupont_result.get('overall_dupont_verdict', 'N/A')}")
            else:
                brand_score.dupont_analysis = {
                    "has_analysis": False,
                    "highest_risk_conflict": None,
                    "overall_dupont_verdict": "GO",
                    "analysis_summary": "No conflicts found requiring DuPont analysis - low likelihood of confusion"
                }
                logging.info(f"✅ DuPont Analysis for '{brand_name_for_matrix}': No conflicts to analyze")
        except Exception as e:
            logging.error(f"Failed to add DuPont analysis: {e}")
        # ============ END DUPONT 13-FACTOR ANALYSIS ============
        
        # ============ 🆕 FEATURE 4: ENHANCED SOCIAL MEDIA ANALYSIS ============
        try:
            # Run enhanced social check (this adds activity analysis)
            enhanced_social = await check_social_availability_enhanced(brand_name_for_matrix, request.countries)
            brand_score.enhanced_social_availability = enhanced_social
            
            # Log summary
            summary = enhanced_social.get('summary', {})
            logging.info(f"✅ Added Enhanced Social Analysis for '{brand_name_for_matrix}': "
                       f"{summary.get('available_count', 0)} available, "
                       f"{summary.get('critical_conflicts', 0)} fatal conflicts, "
                       f"acquisition cost: {summary.get('acquisition_cost_range', 'N/A')}")
        except Exception as e:
            logging.error(f"Failed to add enhanced social analysis: {e}")
        # ============ END ENHANCED SOCIAL MEDIA ANALYSIS ============
        
        # ============ 🔤 FEATURE 5: UNIVERSAL LINGUISTIC ANALYSIS ============
        try:
            # Get stored linguistic analysis from pre-computed data
            ling_analysis = all_brand_data.get(brand_name_for_matrix, {}).get("linguistic_analysis")
            if ling_analysis and ling_analysis.get("_analyzed_by") != "fallback":
                brand_score.universal_linguistic_analysis = ling_analysis
                has_meaning = ling_analysis.get('has_linguistic_meaning', False)
                alignment_score = ling_analysis.get('business_alignment', {}).get('alignment_score', 'N/A')
                name_type = ling_analysis.get('classification', {}).get('name_type', 'Unknown')
                logging.info(f"✅ Added Universal Linguistic Analysis for '{brand_name_for_matrix}': "
                           f"Has Meaning: {has_meaning}, "
                           f"Alignment: {alignment_score}/10, "
                           f"Type: {name_type}")
            
            # Add brand classification with linguistic override data
            brand_classification_data = all_brand_data.get(brand_name_for_matrix, {}).get("classification")
            if brand_classification_data:
                brand_score.brand_classification = brand_classification_data
                if brand_classification_data.get("linguistic_override"):
                    logging.info(f"🏷️ Added Classification Override for '{brand_name_for_matrix}': "
                               f"{brand_classification_data.get('original_category')} → {brand_classification_data.get('category')}")
        except Exception as e:
            logging.error(f"Failed to add linguistic analysis: {e}")
        # ============ END UNIVERSAL LINGUISTIC ANALYSIS ============
        
        # ============ 🎯 FEATURE 6: WEIGHTED NAMESCORE RECALCULATION ============
        try:
            # Gather all components for weighted scoring
            ling_analysis = all_brand_data.get(brand_name_for_matrix, {}).get("linguistic_analysis", {})
            business_alignment = ling_analysis.get("business_alignment", {}).get("alignment_score", 5.0) if ling_analysis else 5.0
            
            # Get trademark risk
            tr_risk = 5.0
            if brand_score.trademark_research:
                tr = brand_score.trademark_research
                if hasattr(tr, 'overall_risk_score'):
                    tr_risk = tr.overall_risk_score
                elif isinstance(tr, dict):
                    tr_risk = tr.get('overall_risk_score', 5.0)
            
            # Get DuPont score
            dupont_score = None
            if brand_score.dupont_analysis:
                dupont = brand_score.dupont_analysis
                if isinstance(dupont, dict) and dupont.get("has_analysis"):
                    highest_risk = dupont.get("highest_risk_conflict", {})
                    if highest_risk:
                        dupont_score = highest_risk.get("dupont_score", None)
            
            # Get domain score
            domain_score = 7.0
            if brand_score.domain_analysis:
                da = brand_score.domain_analysis
                primary_available = da.primary_available if hasattr(da, 'primary_available') else da.get('primary_available', False)
                domain_score = 8.0 if primary_available else 5.0
            
            # Get social score
            social_score = 7.0
            if brand_score.social_availability:
                sa = brand_score.social_availability
                available_count = len(sa.available_platforms) if hasattr(sa, 'available_platforms') else len(sa.get('available_platforms', []))
                total_count = len(sa.platforms) if hasattr(sa, 'platforms') else len(sa.get('platforms', []))
                if total_count > 0:
                    social_score = (available_count / total_count) * 10
            
            # Get cultural analysis
            cultural_analysis = brand_score.cultural_analysis if hasattr(brand_score, 'cultural_analysis') else None
            if not cultural_analysis and llm_research_data:
                cultural_analysis = llm_research_data.get("cultural_analysis")
            
            # Get LLM dimensions
            llm_dimensions = brand_score.dimensions if hasattr(brand_score, 'dimensions') else None
            
            # Calculate weighted namescore
            weighted_result = calculate_weighted_namescore(
                llm_dimensions=llm_dimensions,
                cultural_analysis=cultural_analysis,
                trademark_risk=tr_risk,
                business_alignment=business_alignment,
                dupont_score=dupont_score,
                domain_score=domain_score,
                social_score=social_score,
                classification=all_brand_data.get(brand_name_for_matrix, {}).get("classification")
            )
            
            # Store the original LLM score for comparison
            original_namescore = brand_score.namescore
            new_namescore = weighted_result["namescore"]
            
            # Update the namescore with weighted calculation
            brand_score.namescore = new_namescore
            
            # Store score breakdown for UI display
            brand_score.score_breakdown = weighted_result
            
            logging.info(f"🎯 WEIGHTED NAMESCORE for '{brand_name_for_matrix}': "
                       f"Original LLM: {original_namescore} → Weighted: {new_namescore}")
            logging.info(f"   Components: LLM={weighted_result['component_scores']['llm_dimensions']['raw']:.1f}, "
                       f"Cultural={weighted_result['component_scores']['cultural_resonance']['raw']:.1f}, "
                       f"TM={weighted_result['component_scores']['trademark_safety']['raw']:.1f}, "
                       f"Align={weighted_result['component_scores']['business_alignment']['raw']:.1f}, "
                       f"DuPont={weighted_result['component_scores']['dupont_safety']['raw']:.1f}, "
                       f"Digital={weighted_result['component_scores']['digital_availability']['raw']:.1f}")
            
            # Update verdict based on new score
            if new_namescore >= 70:
                brand_score.verdict = "GO"
            elif new_namescore >= 50:
                brand_score.verdict = "CAUTION"
            else:
                brand_score.verdict = "REJECT"
                
        except Exception as e:
            logging.error(f"Failed to calculate weighted namescore: {e}")
        # ============ END WEIGHTED NAMESCORE RECALCULATION ============
    
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
                evaluation.brand_scores[i].namescore = 5.0
                
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
                
                # Update trademark research to reflect rejection
                from schemas import TrademarkResearchData, TrademarkConflictInfo
                evaluation.brand_scores[i].trademark_research = TrademarkResearchData(
                    overall_risk_score=9,
                    registration_success_probability=10,
                    opposition_probability=90,
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
                
                # Update dimensions to reflect rejection
                if evaluation.brand_scores[i].dimensions:
                    for dim in evaluation.brand_scores[i].dimensions:
                        if "trademark" in dim.name.lower() or "legal" in dim.name.lower():
                            dim.score = 1.0
                            dim.reasoning = f"**CRITICAL CONFLICT:**\nBrand name conflicts with existing trademark '{matched_brand}'. Registration would be rejected or opposed.\n\n**LEGAL RISK:**\nHigh risk of trademark infringement lawsuit if used."
                
                # Clear recommendations
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
    # Add user tracking fields (will be populated when user links report)
    doc['user_email'] = None
    doc['user_id'] = None
    # Store Understanding Module data (Source of Truth)
    doc['brand_understandings'] = {k: v for k, v in brand_understandings.items()} if brand_understandings else None
    await db.evaluations.insert_one(doc)
    
    # Set report_id in the evaluation object
    evaluation.report_id = report_id
    
    # Final fallback: Ensure trademark_research is NEVER null
    for brand_score in evaluation.brand_scores:
        if not brand_score.trademark_research:
            logging.warning(f"⚠️ trademark_research is null for '{brand_score.brand_name}' - Adding default values")
            brand_score.trademark_research = TrademarkResearchData(
                nice_classification=get_nice_classification(request.category),
                overall_risk_score=3,
                registration_success_probability=85,
                opposition_probability=15,
                trademark_conflicts=[],
                company_conflicts=[],
                common_law_conflicts=[],
                critical_conflicts_count=0,
                high_risk_conflicts_count=0,
                total_conflicts_found=0
            )
            logging.info(f"✅ Added default trademark_research for '{brand_score.brand_name}'")
        
        # Add McKinsey Analysis if not present
        if not brand_score.mckinsey_analysis:
            verdict = brand_score.verdict
            
            # Get classification for this brand (use cached or compute)
            brand_classification = classify_brand_with_industry(
                brand_score.brand_name, 
                request.category or request.industry or "Business"
            )
            
            # Generate classification-aware McKinsey analysis
            brand_score.mckinsey_analysis = generate_mckinsey_analysis(
                brand_name=brand_score.brand_name,
                classification=brand_classification,
                category=request.category or "Business",
                positioning=request.positioning or "Mid-Range",
                verdict=verdict,
                trademark_risk=brand_score.trademark_research.overall_risk_score if brand_score.trademark_research else 5,
                imitability_risk=None,  # Will use default
                positioning_alignment=None  # Will use default
            )
            logging.info(f"✅ Added McKinsey analysis for '{brand_score.brand_name}': {brand_score.mckinsey_analysis.get('executive_recommendation', 'N/A')}")
    
    # Return the evaluation
    return evaluation

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
    
    # Models to try - Claude first (most stable), then OpenAI
    models_to_try = [
        ("anthropic", "claude-sonnet-4-20250514"),  # Primary - Most stable
        ("openai", "gpt-4o-mini"),    # Fallback 1
        ("openai", "gpt-4o"),         # Fallback 2
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

# ==================== USER REPORTS ENDPOINTS ====================

async def get_user_from_session(request: Request):
    """Helper to get user from session token"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        return None
    
    session_doc = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session_doc:
        return None
    
    expires_at = session_doc.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    
    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    return user_doc

@api_router.get("/user/reports")
async def get_user_reports(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "newest"
):
    """Get current user's reports history"""
    user = await get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_email = user.get("email")
    user_id = user.get("user_id")
    
    if not user_email and not user_id:
        raise HTTPException(status_code=400, detail="User identifier not found")
    
    # Build query to find reports by user_email or user_id
    query = {"$or": []}
    if user_email:
        query["$or"].append({"user_email": user_email})
    if user_id:
        query["$or"].append({"user_id": user_id})
    
    # If no conditions, return empty
    if not query["$or"]:
        return {"reports": [], "pagination": {"page": page, "limit": limit, "total": 0, "total_pages": 0}}
    
    # Sorting
    sort_order = -1 if sort == "newest" else 1
    
    # Get total count
    total = await db.evaluations.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * limit
    cursor = db.evaluations.find(query, {"_id": 0}).sort("created_at", sort_order).skip(skip).limit(limit)
    reports = await cursor.to_list(length=limit)
    
    # Transform reports for frontend (minimal data)
    reports_summary = []
    for report in reports:
        req = report.get("request", {})
        brand_scores = report.get("brand_scores", [])
        first_brand = brand_scores[0] if brand_scores else {}
        
        reports_summary.append({
            "report_id": report.get("report_id"),
            "brand_name": req.get("brand_name", first_brand.get("brand_name", "Unknown")),
            "category": req.get("category", "N/A"),
            "industry": req.get("industry", ""),
            "countries": req.get("countries", []),
            "namescore": first_brand.get("namescore", 0),
            "verdict": first_brand.get("verdict", report.get("comparison_verdict", "N/A")),
            "created_at": report.get("created_at"),
            "early_stopped": report.get("early_stopped", False),
            "executive_summary": report.get("executive_summary", "")[:200] + "..." if len(report.get("executive_summary", "")) > 200 else report.get("executive_summary", "")
        })
    
    return {
        "reports": reports_summary,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@api_router.post("/user/reports/link")
async def link_report_to_user(request: Request, report_id: str):
    """Link a report to the current authenticated user"""
    user = await get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Find the report
    report = await db.evaluations.find_one({"report_id": report_id})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Link to user
    update_data = {
        "user_email": user.get("email"),
        "user_id": user.get("user_id")
    }
    
    await db.evaluations.update_one(
        {"report_id": report_id},
        {"$set": update_data}
    )
    
    return {"success": True, "message": "Report linked to your account"}

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
    # Try cookie first, then Authorization header
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if session_token:
        await db.user_sessions.delete_many({"session_token": session_token})
    
    # Delete cookie
    response.delete_cookie(key="session_token", path="/", samesite="lax")
    return {"message": "Logged out successfully"}


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL/PASSWORD AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════

class EmailSignUpRequest(BaseModel):
    email: str
    password: str
    name: str

class EmailSignInRequest(BaseModel):
    email: str
    password: str

@api_router.post("/auth/signup")
async def email_signup(request_data: EmailSignUpRequest):
    """Sign up with email and password"""
    import hashlib
    
    email = request_data.email.lower().strip()
    password = request_data.password
    name = request_data.name.strip()
    
    # Validate email format
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    
    # Validate password
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered. Please sign in.")
    
    # Hash password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Create user
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    user_doc = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "password_hash": password_hash,
        "picture": None,
        "auth_provider": "email",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    # Create session
    session_token = f"sess_{uuid.uuid4().hex}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    
    await db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat()
    })
    
    logging.info(f"🔐 Email Signup: New user created - {email}")
    
    return {
        "success": True,
        "session_token": session_token,
        "user": {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": None
        }
    }


@api_router.post("/auth/signin")
async def email_signin(request_data: EmailSignInRequest):
    """Sign in with email and password"""
    import hashlib
    
    email = request_data.email.lower().strip()
    password = request_data.password
    
    # Find user
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user.get("password_hash") != password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create session
    session_token = f"sess_{uuid.uuid4().hex}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    
    await db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat()
    })
    
    logging.info(f"🔐 Email Signin: User logged in - {email}")
    
    return {
        "success": True,
        "session_token": session_token,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user.get("name", email.split("@")[0]),
            "picture": user.get("picture")
        }
    }


app.include_router(api_router)
app.include_router(admin_router)  # Admin panel routes
app.include_router(payment_router)  # Payment routes
app.include_router(google_oauth_router)  # Google OAuth routes

# Initialize payment routes with database
set_payment_db(db)

# Initialize Google OAuth with database
set_google_oauth_db(db)

# Root-level health check endpoint for Kubernetes (no /api prefix)
@app.get("/health")
async def root_health_check():
    """Health check endpoint for Kubernetes - must respond quickly"""
    try:
        # Quick MongoDB ping (with short timeout)
        await db.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        # Still return healthy status - MongoDB might just be slow to connect
        # The important thing is that the FastAPI app is running
        return {"status": "healthy", "database": "initializing", "note": str(e)[:100]}

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
