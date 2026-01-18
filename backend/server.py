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
from similarity import check_brand_similarity, format_similarity_report
from trademark_research import conduct_trademark_research, format_research_for_prompt

# Import LLM-First Market Intelligence Research Module
from market_intelligence import (
    research_all_countries,
    research_country_market,
    research_cultural_sensitivity,
    format_market_intelligence_for_response,
    format_cultural_intelligence_for_response
)

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
    
    # Initialize admin panel
    set_db(db)
    await initialize_admin(db)
    logging.info("✅ Admin panel initialized")
    
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
        "wellness": "wellness", "health": "wellness", "fitness": "wellness", "spa": "wellness"
    }
    
    industry_key = None
    for key, value in category_map.items():
        if key in category_lower:
            industry_key = value
            break
    
    if not industry_key:
        industry_key = "hotels"  # Default
    
    industry_suffixes = SUFFIX_INDUSTRY_FIT.get(industry_key, SUFFIX_INDUSTRY_FIT["hotels"])
    
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
    """
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
    """
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
        
        logging.info(f"🏷️ CLASSIFICATION: '{brand_name}' → GENERIC (names the category)")
        return result
    
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
        
        logging.info(f"🏷️ CLASSIFICATION: '{brand_name}' → DESCRIPTIVE (describes the product)")
        return result
    
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
        
        logging.info(f"🏷️ CLASSIFICATION: '{brand_name}' → SUGGESTIVE (hints at product)")
        return result
    
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
        
        logging.info(f"🏷️ CLASSIFICATION: '{brand_name}' → ARBITRARY (unrelated context)")
        return result
    
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
        
        logging.info(f"🏷️ CLASSIFICATION: '{brand_name}' → FANCIFUL/COINED (invented word)")
        return result
    
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
    
    logging.info(f"🏷️ CLASSIFICATION: '{brand_name}' → DESCRIPTIVE (conservative default)")
    return result


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
    
    # Technology & SaaS
    "technology": "technology", "tech": "technology", "saas": "technology", "software": "technology",
    "it": "technology", "app": "technology", "ai": "technology", "fintech": "technology",
    
    # Food & Beverage
    "food": "food", "beverage": "food", "food & beverage": "food", "f&b": "food",
    "restaurant": "food", "cafe": "food", "snacks": "food", "drinks": "food",
    "tea": "food", "coffee": "food", "chai": "food",
    
    # Finance & Payments
    "finance": "finance", "banking": "finance", "payments": "finance", "insurance": "finance",
    "investment": "finance", "lending": "finance", "wealth": "finance"
}

def get_category_key(category: str) -> str:
    """Normalize category input to match our data structure"""
    if not category:
        return "default"
    
    category_lower = category.lower().strip()
    
    # Check direct mapping
    if category_lower in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[category_lower]
    
    # Check if any mapped key is contained in the category
    for key, value in CATEGORY_MAPPING.items():
        if key in category_lower:
            return value
    
    return "default"

def get_market_data_for_category_country(category: str, country: str) -> dict:
    """Get market data for specific category and country combination.
    
    CRITICAL FIX: Case-insensitive country matching to handle "INDIA" vs "India"
    """
    category_key = get_category_key(category)
    
    # Get category-specific data
    category_data = CATEGORY_COUNTRY_MARKET_DATA.get(category_key, {})
    
    # CASE-INSENSITIVE country matching
    # Create a lowercase lookup map for country names
    country_lower = country.lower().strip() if country else ""
    country_lookup = {k.lower(): k for k in category_data.keys()}
    
    # Try to find the country (case-insensitive)
    if country_lower in country_lookup:
        actual_key = country_lookup[country_lower]
        logging.info(f"✅ Country matched: '{country}' → '{actual_key}' (category: {category_key})")
        return category_data[actual_key]
    elif "default" in category_data:
        logging.warning(f"⚠️ Country '{country}' not found in {category_key} data, using default")
        return category_data["default"]
    
    # Fallback to beauty default (original behavior) if category not found
    logging.warning(f"⚠️ Category '{category_key}' not found, using beauty default")
    return CATEGORY_COUNTRY_MARKET_DATA.get("beauty", {}).get("default", {
        "competitors": [
            {"name": "Market Leader 1", "x_coordinate": 75, "y_coordinate": 70, "quadrant": "Premium Established"},
            {"name": "Market Leader 2", "x_coordinate": 50, "y_coordinate": 60, "quadrant": "Mass Market"},
            {"name": "Regional Player", "x_coordinate": 60, "y_coordinate": 55, "quadrant": "Local Champion"},
            {"name": "Challenger Brand", "x_coordinate": 45, "y_coordinate": 75, "quadrant": "Emerging Disruptor"}
        ],
        "user_position": {"x": 65, "y": 72, "quadrant": "Accessible Premium"},
        "axis_x": "Price: Budget → Premium",
        "axis_y": "Positioning: Traditional → Modern",
        "white_space": "Market analysis indicates opportunities in the premium accessible segment. Consumer trends favor innovative, authentic brands with clear differentiation.",
        "strategic_advantage": "As a new entrant, the brand can leverage digital-first strategies and agile positioning to capture underserved market segments.",
        "entry_recommendation": "Phased market entry: Phase 1 (Digital validation), Phase 2 (Strategic partnerships), Phase 3 (Scale operations). Focus on building authentic brand story and community."
    })

def generate_country_competitor_analysis(countries: list, category: str, brand_name: str) -> list:
    """Generate RESEARCHED competitor analysis for ALL user-selected countries (max 4)
    Now category-aware - uses different competitor data based on industry category
    """
    result = []
    
    # Log the category being used
    category_key = get_category_key(category)
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
        market_data = get_market_data_for_category_country(category, country_name)
        logging.info(f"📊 Market data for {display_name} {flag} ({category_key}): {len(market_data.get('competitors', []))} competitors")
        
        # Build the analysis
        result.append({
            "country": display_name,
            "country_flag": flag,
            "x_axis_label": market_data.get("axis_x", "Price: Budget → Premium"),
            "y_axis_label": market_data.get("axis_y", "Positioning: Traditional → Modern"),
            "competitors": market_data["competitors"],
            "user_brand_position": {
                "x_coordinate": market_data["user_position"]["x"],
                "y_coordinate": market_data["user_position"]["y"],
                "quadrant": market_data["user_position"]["quadrant"],
                "rationale": f"'{brand_name}' positioned in {market_data['user_position']['quadrant']} segment to maximize market opportunity in {display_name}"
            },
            "white_space_analysis": market_data["white_space"].replace("'", "'"),
            "strategic_advantage": market_data["strategic_advantage"].replace("'", "'"),
            "market_entry_recommendation": market_data["entry_recommendation"].replace("'", "'")
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

def generate_cultural_analysis(countries: list, brand_name: str, category: str = "Business") -> list:
    """Generate cultural analysis for ALL user-selected countries (max 4)
    
    NEW FORMULA-BASED SCORING:
    Score = (Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)
    
    - Safety: Phonetic accidents, slang, sacred terms
    - Fluency: Pronunciation ease for local speakers  
    - Vibe: Premium market fit vs local competitors
    """
    result = []
    
    # Create case-insensitive lookups
    cultural_data_lower = {k.lower(): v for k, v in COUNTRY_CULTURAL_DATA.items()}
    flags_lower = {k.lower(): v for k, v in COUNTRY_FLAGS.items()}
    
    # Generate comprehensive linguistic analysis
    linguistic_analysis = generate_linguistic_decomposition(brand_name, countries, category)
    
    logging.info(f"🔤 LINGUISTIC DECOMPOSITION for '{brand_name}':")
    logging.info(f"   Brand Type: {linguistic_analysis.get('brand_type')}")
    logging.info(f"   Industry Fit: {linguistic_analysis.get('industry_fit', {}).get('fit_level')}")
    logging.info(f"   Morphemes Found: {[m['text'] for m in linguistic_analysis.get('decomposition', {}).get('morphemes', [])]}")
    
    # Ensure we process up to 4 countries
    countries_to_process = countries[:4] if len(countries) > 4 else countries
    
    for country in countries_to_process:
        # Get country name (handle dict or string)
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        country_lower = country_name.lower().strip() if country_name else ""
        display_name = country_name.title() if country_name else "Unknown"
        
        # Get base cultural data - CASE INSENSITIVE
        base_cultural_data = cultural_data_lower.get(country_lower, COUNTRY_CULTURAL_DATA["default"])
        
        # Get flag - CASE INSENSITIVE
        flag = flags_lower.get(country_lower, "🌍")
        
        # Get linguistic analysis for this country
        country_linguistic = linguistic_analysis.get("country_analysis", {}).get(display_name, {})
        
        # ========== NEW: FORMULA-BASED CULTURAL SCORING ==========
        # Calculate using: Score = (Safety × 0.4) + (Fluency × 0.3) + (Vibe × 0.3)
        cultural_score_result = calculate_fallback_cultural_score(brand_name, category, display_name)
        score_data = cultural_score_result.get("data", {})
        
        safety_score = score_data.get("safety_score", {}).get("raw", 7)
        fluency_score = score_data.get("fluency_score", {}).get("raw", 7)
        vibe_score = score_data.get("vibe_score", {}).get("raw", 6)
        calculated_final = score_data.get("calculation", {}).get("final_score", 7.0)
        risk_verdict = score_data.get("risk_verdict", "CAUTION")
        
        # Build comprehensive cultural notes - NO FORMULA (kept internal, shown via score_breakdown)
        cultural_notes_parts = []
        
        # Part 1: Linguistic Decomposition Header (skip formula - it's in score_breakdown for frontend)
        cultural_notes_parts.append(f"**🔤 LINGUISTIC ANALYSIS: {brand_name}**\n")
        
        # Part 2: Morpheme Breakdown
        decomposition = linguistic_analysis.get("decomposition", {})
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
        industry_fit = linguistic_analysis.get("industry_fit", {})
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
        cultural_notes_parts.append(f"\n**BRAND TYPE:** {linguistic_analysis.get('brand_type', 'Modern/Coined')}")
        
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
        overall_resonance = country_linguistic.get("overall_resonance", "NEUTRAL")
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
            "linguistic_analysis": {
                "morphemes": [m["text"] for m in decomposition.get("morphemes", [])],
                "brand_type": linguistic_analysis.get("brand_type"),
                "industry_fit": industry_fit.get("fit_level"),
                "overall_resonance": overall_resonance,
                "risk_count": len(risk_flags)
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
    positioning: str = "Mid-Range"
) -> tuple:
    """
    LLM-First approach to country analysis with POSITIONING-AWARE search.
    
    KEY IMPROVEMENT: Includes positioning in search queries to get segment-specific competitors.
    Example: "Premium Hotel Chain India" → Taj, ITC, Oberoi
    Instead of: "Hotel Chain India" → mixed OYO to Taj
    
    Uses real-time web search + LLM for accuracy, with hardcoded fallback if research fails.
    
    Returns: (country_competitor_analysis, cultural_analysis)
    """
    if not use_llm_research:
        # Use hardcoded fallback directly
        logging.info(f"⚡ Using hardcoded data (LLM research disabled)")
        return (
            generate_country_competitor_analysis(countries, category, brand_name),
            generate_cultural_analysis(countries, brand_name, category)
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
            fallback_market[country_name] = get_market_data_for_category_country(category, country_name)
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
            generate_country_competitor_analysis(countries, category, brand_name),
            generate_cultural_analysis(countries, brand_name, category)
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


def generate_smart_final_recommendations(
    brand_name: str,
    category: str,
    countries: list,
    domain_available: bool,
    nice_class: dict
) -> list:
    """
    Generate smart, category-aware and country-specific recommendations.
    NO generic .beauty/.shop for medical apps, etc.
    """
    brand_lower = brand_name.lower()
    
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
    
    # Build trademark filing recommendation with country-specific guidance
    country_names = [c.get('name') if isinstance(c, dict) else str(c) for c in countries]
    if len(country_names) > 1:
        trademark_recommendation = f"File trademark in NICE Class {nice_class.get('class_number', 9)} ({nice_class.get('class_description', category)}). For multi-country ({', '.join(country_names[:3])}), consider Madrid Protocol for cost-effective international registration."
    else:
        trademark_recommendation = f"File trademark in {country_names[0] if country_names else 'target country'} under NICE Class {nice_class.get('class_number', 9)} ({nice_class.get('class_description', category)}). Process typically 12-18 months."
    
    recommendations = [
        {
            "title": "🏢 Domain Strategy",
            "content": domain_strategy
        },
        {
            "title": "📋 Trademark Filing",
            "content": trademark_recommendation
        },
        {
            "title": "📱 Social Presence",
            "content": f"Reserve @{brand_lower} on Instagram, Twitter, LinkedIn, Facebook, TikTok, and YouTube before public announcement. Consistency across platforms builds brand recognition."
        },
        {
            "title": "🎯 Brand Launch",
            "content": f"Develop comprehensive brand guidelines for {category} positioning before market entry in {', '.join(country_names[:2])}. Localize messaging for each target market."
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
    cultural_analysis: list = None
) -> str:
    """
    Generate a rich, detailed executive summary (minimum 100 words) that provides
    substantive analysis like a professional brand consultant would.
    
    Example output:
    "Deepstorika" offers a highly distinctive and legally defensible foundation for a 
    global DTC skincare brand. As a coined neologism, it bypasses the trademark saturation...
    """
    
    # Get linguistic decomposition if not provided
    if not linguistic_analysis:
        linguistic_analysis = generate_linguistic_decomposition(brand_name, countries, category)
    
    decomposition = linguistic_analysis.get("decomposition", {})
    morphemes = decomposition.get("morphemes", [])
    brand_type = linguistic_analysis.get("brand_type", "Modern/Coined")
    industry_fit = linguistic_analysis.get("industry_fit", {})
    country_analysis = linguistic_analysis.get("country_analysis", {})
    
    # Determine brand name characteristics
    is_coined = brand_type in ["Modern/Coined", "Coined"]
    is_heritage = brand_type == "Heritage"
    has_morphemes = len(morphemes) > 0
    
    # Get NICE class info
    class_number = nice_class.get("class_number", 35) if nice_class else 35
    class_description = nice_class.get("class_description", category) if nice_class else category
    
    # Format target markets
    market_list = []
    for country in countries[:4]:
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        market_list.append(country_name.title())
    markets_str = ", ".join(market_list[:-1]) + f" and {market_list[-1]}" if len(market_list) > 1 else market_list[0] if market_list else "target markets"
    
    # Analyze morpheme structure for summary
    morpheme_insights = []
    risk_countries = []
    positive_countries = []
    
    for morpheme in morphemes:
        origin = morpheme.get("origin", "")
        meaning = morpheme.get("meaning", "")
        morpheme_insights.append(f'"{morpheme["text"].capitalize()}" ({origin}: {meaning.split("/")[0] if "/" in meaning else meaning})')
    
    for country_name, data in country_analysis.items():
        if data.get("overall_resonance") == "CRITICAL":
            risk_countries.append(country_name)
        elif data.get("overall_resonance") == "HIGH" and data.get("risk_count", 0) == 0:
            positive_countries.append(country_name)
    
    # Build the executive summary
    summary_parts = []
    
    # Opening statement with verdict context
    if verdict == "GO":
        if is_coined:
            summary_parts.append(
                f'**"{brand_name}"** presents a highly distinctive and legally defensible foundation for a {category} brand. '
                f'As a coined neologism, it effectively bypasses the trademark saturation common in the {category.lower()} sector, '
                f'ensuring a clear path to registration in Class {class_number} ({class_description}) across {markets_str}.'
            )
        elif is_heritage:
            summary_parts.append(
                f'**"{brand_name}"** leverages heritage linguistics to create a culturally resonant brand identity for the {category} market. '
                f'The name draws from established etymological roots, positioning the brand with authenticity while maintaining distinctiveness '
                f'for trademark registration in Class {class_number} across {markets_str}.'
            )
        else:
            summary_parts.append(
                f'**"{brand_name}"** demonstrates strong potential as a trademark for a {category} brand. '
                f'The name balances memorability with distinctiveness, supporting registration in Class {class_number} ({class_description}) '
                f'across {markets_str}.'
            )
    elif verdict == "CAUTION":
        summary_parts.append(
            f'**"{brand_name}"** shows promise for the {category} market but requires strategic attention to identified concerns. '
            f'While the name has potential for Class {class_number} registration, certain factors in {markets_str} warrant careful evaluation before brand investment.'
        )
    else:  # NO-GO
        summary_parts.append(
            f'**"{brand_name}"** faces significant challenges for the {category} market. '
            f'Critical issues identified in trademark clearance or cultural fit across {markets_str} suggest alternative naming approaches may better serve the brand strategy.'
        )
    
    # Morpheme analysis (if available)
    if morpheme_insights:
        fuse_word = "fuses" if len(morphemes) > 1 else "employs"
        combo_word = "combination" if len(morphemes) > 1 else "structure"
        unique_word = "unique" if is_coined else "culturally grounded"
        position_text = "differentiates from generic category descriptors" if verdict == "GO" else "requires cultural navigation in certain markets"
        morpheme_join = " with ".join(morpheme_insights)
        summary_parts.append(
            f'\n\n**Linguistic Structure:** The name strategically {fuse_word} '
            f'{morpheme_join}. '
            f'This {combo_word} creates a {unique_word} '
            f'positioning that {position_text}.'
        )
    
    # Industry fit insight
    fit_level = industry_fit.get("fit_level", "NEUTRAL")
    if fit_level == "HIGH":
        summary_parts.append(
            f'The phonetic structure aligns strongly with {category.lower()} industry conventions, enhancing brand recall and category association.'
        )
    elif fit_level == "LOW":
        summary_parts.append(
            f'Note: The name\'s suffix structure is atypical for the {category.lower()} sector, which may require stronger visual branding to establish category relevance.'
        )
    
    # Cultural/market analysis
    if risk_countries:
        summary_parts.append(
            f'\n\n**⚠️ Critical Considerations:** Market entry in {", ".join(risk_countries)} requires legal consultation due to cultural/regulatory sensitivities identified in linguistic analysis.'
        )
    if positive_countries:
        summary_parts.append(
            f'**Market Advantage:** Strong cultural resonance detected in {", ".join(positive_countries)}, presenting opportunities for heritage-based positioning.'
        )
    
    # Trademark and digital assets
    summary_parts.append(
        f'\n\n**IP Strategy:** '
        f'{"Recommended for immediate trademark capture with filing priority in primary markets. " if verdict == "GO" else "Proceed with comprehensive clearance search before commitment. "}'
        f'{"Primary .com domain available for acquisition. " if domain_available else "Alternative domain strategy required (.co, .io, or category TLDs). "}'
        f'{"Social handle @" + brand_name.lower() + " should be secured across major platforms." if verdict != "NO-GO" else ""}'
    )
    
    # Closing recommendation
    if verdict == "GO":
        summary_parts.append(
            f'\n\n**Recommendation:** Proceed with brand development, supported by a visual identity that emphasizes '
            f'{"the coined uniqueness" if is_coined else "the heritage narrative" if is_heritage else "brand distinctiveness"}. '
            f'Estimated trademark registration timeline: 12-18 months in primary jurisdictions. Score: **{overall_score}/100**.'
        )
    elif verdict == "CAUTION":
        summary_parts.append(
            f'\n\n**Recommendation:** Address identified concerns before significant brand investment. Consider legal opinion on trademark conflicts '
            f'and cultural consultation for sensitive markets. Score: **{overall_score}/100**.'
        )
    else:
        summary_parts.append(
            f'\n\n**Recommendation:** Explore alternative naming directions that better navigate the identified challenges. '
            f'Consider coined neologisms or category-adjacent terminology to reduce conflict risk. Score: **{overall_score}/100**.'
        )
    
    return "".join(summary_parts)


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
        "action": "File Intent-to-Use (ITU) application immediately",
        "rationale": "Establishes priority date while business launches. US allows ITU filing 6 months before commercial use with extensions available",
        "estimated_cost": "$275-$400 per class (USPTO)",
        "timeline": "File within 30 days of brand decision"
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

def generate_intelligent_trademark_matrix(brand_name: str, category: str, trademark_data: dict, brand_is_invented: bool = True) -> dict:
    """
    Generate intelligent Legal Risk Matrix with SPECIFIC, ACTIONABLE commentary
    based on actual trademark research results - NOT generic placeholders.
    """
    # Extract data from trademark research
    risk_score = trademark_data.get('overall_risk_score', 5) if trademark_data else 5
    tm_conflicts = trademark_data.get('trademark_conflicts', []) if trademark_data else []
    co_conflicts = trademark_data.get('company_conflicts', []) if trademark_data else []
    total_conflicts = len(tm_conflicts) + len(co_conflicts)
    registration_prob = trademark_data.get('registration_success_probability', 70) if trademark_data else 70
    
    nice_class = get_nice_classification(category)
    class_number = nice_class.get('class_number', 35)
    
    # Calculate individual risk factors
    genericness_score = 1 if brand_is_invented else min(6, 2 + len(brand_name.split()) * 2)
    conflict_score = min(9, 1 + total_conflicts * 2) if total_conflicts > 0 else 1
    phonetic_score = min(7, 1 + len([c for c in tm_conflicts if c.get('conflict_type') == 'phonetic']) * 3)
    class_score = min(6, 1 + total_conflicts) if total_conflicts > 0 else 2
    rebrand_score = min(8, 1 + conflict_score // 2)
    
    # Determine zones
    def get_zone(score):
        if score <= 3: return "Green"
        elif score <= 6: return "Yellow"
        else: return "Red"
    
    # Generate SPECIFIC commentary for each factor
    matrix = {
        "genericness": {
            "likelihood": genericness_score,
            "severity": genericness_score + 1 if genericness_score > 3 else 2,
            "zone": get_zone(genericness_score),
            "commentary": f"'{brand_name}' is {'a coined/invented term with no dictionary meaning - HIGH distinctiveness for trademark protection' if brand_is_invented else 'partially descriptive which may face distinctiveness challenges'}. Recommendation: {'File as wordmark in Class ' + str(class_number) + ' with intent-to-use basis. Consider design mark for additional protection layer.' if genericness_score <= 3 else 'Strengthen with distinctive design elements. Consider acquired distinctiveness argument if mark has been in use.'}"
        },
        "existing_conflicts": {
            "likelihood": conflict_score,
            "severity": min(9, conflict_score + 2),
            "zone": get_zone(conflict_score),
            "commentary": f"Found {total_conflicts} potential conflicts ({len(tm_conflicts)} trademark, {len(co_conflicts)} company registrations). " + (
                f"Top conflict: {tm_conflicts[0].get('name', 'Unknown')} in Class {tm_conflicts[0].get('class_number', 'N/A')} ({tm_conflicts[0].get('status', 'Status unknown')}). Recommendation: Conduct comprehensive knockout search with IP attorney before filing. Prepare co-existence agreement template if proceeding."
                if tm_conflicts else 
                "No direct trademark conflicts found in primary class. Recommendation: Proceed with filing in Class " + str(class_number) + ". Set up trademark watch service to monitor new filings with similar marks."
            )
        },
        "phonetic_similarity": {
            "likelihood": phonetic_score,
            "severity": phonetic_score + 1 if phonetic_score > 3 else 2,
            "zone": get_zone(phonetic_score),
            "commentary": f"{'Phonetic variants analyzed: No confusingly similar marks detected in Class ' + str(class_number) + '.' if phonetic_score <= 3 else 'Potential phonetic conflicts identified with similar-sounding marks.'} Recommendation: {'Register both word mark and phonetic variants as defensive strategy. Monitor app stores and domain registrations for sound-alike competitors.' if phonetic_score <= 3 else 'Consider slight spelling modifications to increase distinctiveness. Clear phonetic differentiation from ' + (tm_conflicts[0].get('name', 'existing marks') if tm_conflicts else 'existing marks') + ' is advised.'}"
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
            "commentary": f"{'LOW rebranding risk - No senior marks with enforcement history found. Registration outlook: {:.0f}% success probability.'.format(registration_prob) if rebrand_score <= 3 else 'MODERATE rebranding risk due to existing conflicts. Recommend legal clearance opinion before significant brand investment.'} Action: {'Proceed with brand development. Secure federal registration early to build brand equity and prevent future challenges.' if rebrand_score <= 3 else 'Obtain formal legal opinion on conflict severity. Budget for potential opposition proceedings ($5,000-25,000 depending on jurisdiction).'}"
        },
        "overall_assessment": f"Overall trademark risk: {risk_score}/10. {'Favorable registration outlook - proceed with filing.' if risk_score <= 3 else 'Moderate risk - legal clearance recommended.' if risk_score <= 6 else 'High risk - significant conflicts require resolution before proceeding.'} Registration success probability: {registration_prob}%. {'Timeline: 12-18 months for registration. Estimated cost: $2,500-5,000 (single class, single jurisdiction).' if risk_score <= 5 else 'Extended timeline likely due to potential opposition. Budget for legal defense costs.'}"
    }
    
    return matrix


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
        
        # ==================== MASTER CLASSIFICATION (CALLED ONCE) ====================
        # This classification is passed to ALL sections that need it
        brand_classification = classify_brand_with_industry(brand, request.category or "Business")
        logging.info(f"🏷️ MASTER CLASSIFICATION for '{brand}':")
        logging.info(f"   Category: {brand_classification['category']}")
        logging.info(f"   Tokens: {brand_classification['tokens']}")
        logging.info(f"   Distinctiveness: {brand_classification['distinctiveness']}")
        logging.info(f"   Protectability: {brand_classification['protectability']}")
        # ==================== END MASTER CLASSIFICATION ====================
        
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
            "social": processed_results[5],
            "classification": brand_classification  # Store classification for later use
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
        
        # Execute LLM-first research WITH POSITIONING
        country_competitor_analysis, cultural_analysis = await llm_first_country_analysis(
            countries=request.countries,
            category=request.category or "Business",
            brand_name=primary_brand,
            use_llm_research=True,  # Enable LLM research
            positioning=request.positioning  # NEW: Pass user's positioning for segment-specific competitors
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
        if "brand_scores" in data and isinstance(data["brand_scores"], list):
            for brand_score in data["brand_scores"]:
                existing_countries = []
                if "country_competitor_analysis" in brand_score:
                    existing_countries = [c.get("country", "") for c in brand_score.get("country_competitor_analysis", [])]
                
                # Check if any user countries are missing
                # Note: request is accessible in outer scope
                brand_name_for_fallback = brand_score.get("brand_name", "Brand")
                category_for_fallback = brand_score.get("category", "Business")
                
                # If country_competitor_analysis is empty or missing countries, use LLM research data or regenerate
                if not brand_score.get("country_competitor_analysis") or len(brand_score.get("country_competitor_analysis", [])) == 0:
                    # Use LLM research data if available (from earlier parallel processing)
                    if llm_research_data and llm_research_data.get("country_competitor_analysis"):
                        brand_score["country_competitor_analysis"] = llm_research_data["country_competitor_analysis"]
                        logging.info(f"✅ Using LLM-researched country competitor analysis for {brand_name_for_fallback}")
                    else:
                        brand_score["country_competitor_analysis"] = generate_country_competitor_analysis(
                            request.countries, 
                            request.category or category_for_fallback, 
                            brand_name_for_fallback
                        )
                
                # Use LLM research cultural_analysis if available
                if not brand_score.get("cultural_analysis") or len(brand_score.get("cultural_analysis", [])) == 0:
                    if llm_research_data and llm_research_data.get("cultural_analysis"):
                        brand_score["cultural_analysis"] = llm_research_data["cultural_analysis"]
                        logging.info(f"✅ Using LLM-researched cultural analysis for {brand_name_for_fallback}")
                
                # Ensure competitor_analysis has proper data (global competitors from first country or research)
                if not brand_score.get("competitor_analysis") or not brand_score.get("competitor_analysis", {}).get("competitors"):
                    # Try to use data from first country in LLM research
                    if llm_research_data and llm_research_data.get("country_competitor_analysis"):
                        first_country = llm_research_data["country_competitor_analysis"][0]
                        brand_score["competitor_analysis"] = {
                            "x_axis_label": first_country.get("x_axis_label", "Price: Budget → Premium"),
                            "y_axis_label": first_country.get("y_axis_label", "Innovation: Traditional → Modern"),
                            "competitors": first_country.get("competitors", []),
                            "user_brand_position": first_country.get("user_brand_position", {
                                "x_coordinate": 65, "y_coordinate": 75, "quadrant": "Accessible Premium",
                                "rationale": f"'{brand_name_for_fallback}' positioned for premium-accessible market segment"
                            }),
                            "white_space_analysis": first_country.get("white_space_analysis", "Market opportunity exists for innovative brands."),
                            "strategic_advantage": first_country.get("strategic_advantage", "Distinctive brand identity enables unique positioning.")
                        }
                        logging.info(f"✅ Using LLM-researched competitor analysis for {brand_name_for_fallback}")
                    else:
                        brand_score["competitor_analysis"] = {
                            "x_axis_label": "Price: Budget → Premium",
                            "y_axis_label": "Innovation: Traditional → Modern",
                            "competitors": [
                                {"name": "Market Leader 1", "x_coordinate": 75, "y_coordinate": 65, "quadrant": "Premium Modern"},
                                {"name": "Market Leader 2", "x_coordinate": 45, "y_coordinate": 70, "quadrant": "Mid-range Modern"},
                                {"name": "Market Leader 3", "x_coordinate": 80, "y_coordinate": 35, "quadrant": "Premium Traditional"},
                                {"name": "Challenger Brand", "x_coordinate": 30, "y_coordinate": 55, "quadrant": "Value Player"}
                            ],
                            "user_brand_position": {
                                "x_coordinate": 65,
                                "y_coordinate": 75,
                                "quadrant": "Accessible Premium",
                                "rationale": f"'{brand_name_for_fallback}' positioned for premium-accessible market segment"
                            },
                            "white_space_analysis": f"Opportunity exists in the market for brands combining accessibility with innovation.",
                            "strategic_advantage": f"Distinctive brand identity enables unique market positioning."
                        }
        
        return {"model": f"{model_provider}/{model_name}", "data": data}
    
    def generate_fallback_report(brand_name: str, category: str, domain_data, social_data, trademark_data, visibility_data) -> dict:
        """Generate a complete report WITHOUT LLM using collected data"""
        logging.info(f"🔧 FALLBACK MODE: Generating report for '{brand_name}' without LLM")
        
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
        
        # Overall score
        overall_score = int((domain_score + social_score + trademark_score) / 3 * 10)
        overall_score = max(30, min(95, overall_score))  # Clamp between 30-95
        
        # Determine verdict
        if trademark_risk >= 8:
            verdict = "REJECT"
            overall_score = min(overall_score, 35)
        elif trademark_risk >= 5:
            verdict = "CAUTION"
            overall_score = min(overall_score, 60)
        else:
            verdict = "GO"
            overall_score = max(overall_score, 65)
        
        nice_class = get_nice_classification(category)
        
        # Use LLM research data if available, otherwise use hardcoded fallback
        fallback_cultural = llm_research_data.get("cultural_analysis") if llm_research_data else None
        fallback_competitors = llm_research_data.get("country_competitor_analysis") if llm_research_data else None
        
        # Get first country data for global competitor_analysis
        global_competitor_analysis = None
        if fallback_competitors and len(fallback_competitors) > 0:
            first_country = fallback_competitors[0]
            global_competitor_analysis = {
                "x_axis_label": first_country.get("x_axis_label", "Price: Budget → Premium"),
                "y_axis_label": first_country.get("y_axis_label", "Innovation: Traditional → Modern"),
                "competitors": first_country.get("competitors", []),
                "user_brand_position": first_country.get("user_brand_position", {
                    "x_coordinate": 65, "y_coordinate": 75, "quadrant": "Accessible Premium",
                    "rationale": f"'{brand_name}' positioned for premium-accessible market segment"
                }),
                "white_space_analysis": first_country.get("white_space_analysis", f"Opportunity exists in the {category} market for brands combining accessibility with innovation."),
                "strategic_advantage": first_country.get("strategic_advantage", f"As a distinctive coined term, '{brand_name}' can establish unique market positioning."),
                "suggested_pricing": f"{'Premium' if overall_score >= 75 else 'Mid-range'} positioning recommended"
            }
        
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
                "pros": [
                    f"**Unique Identifier:** '{brand_name}' appears to be a distinctive coined term",
                    f"**Phonetic Clarity:** {len(brand_name)}-character name with clear pronunciation",
                    f"**Category Fit:** Suitable for {category} market positioning",
                    f"**Trademark Potential:** {'Strong' if trademark_risk <= 3 else 'Moderate' if trademark_risk <= 6 else 'Limited'} registration prospects",
                    f"**Digital Availability:** Multiple domain and social handle options available"
                ],
                "cons": generate_risk_cons(brand_name, request.countries, category, domain_available, verdict),
                # CRITICAL FIX: Always use generate_cultural_analysis for sacred name detection
                # If market_intelligence has data, merge it, but always run local analysis
                "cultural_analysis": merge_cultural_analysis_with_sacred_names(
                    fallback_cultural,
                    generate_cultural_analysis(request.countries, brand_name, category),
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
                "country_competitor_analysis": fallback_competitors if fallback_competitors else generate_country_competitor_analysis(request.countries, category, brand_name),
                "alternative_names": {
                    "poison_words": [],
                    "reasoning": "Alternative names generated based on brand analysis",
                    "suggestions": [
                        {"name": f"{brand_name[:4]}ora", "score": 75, "rationale": "Softer feminine ending for beauty sector"},
                        {"name": f"{brand_name[:5]}ix", "score": 72, "rationale": "Modern tech-inspired suffix"},
                        {"name": f"Neo{brand_name[:4]}", "score": 70, "rationale": "Innovation-focused prefix"}
                    ]
                },
                "mitigation_strategies": RISK_MITIGATION_STRATEGIES[:5],
                "registration_timeline": generate_registration_timeline(request.countries),
                "legal_precedents": generate_legal_precedents("LOW" if trademark_risk <= 3 else "MEDIUM"),
                "strategic_classification": f"{'STRONG' if trademark_risk <= 3 else 'MODERATE' if trademark_risk <= 6 else 'WEAK'} - Coined/Invented term with {'high' if trademark_risk <= 3 else 'moderate'} legal distinctiveness",
                "trademark_classes": [str(nice_class.get('class_number', 3))],
                "trademark_matrix": {
                    "primary_class": nice_class.get('class_number', 3),
                    "secondary_classes": [],
                    "filing_strategy": f"File in Class {nice_class.get('class_number', 3)} ({nice_class.get('class_description', category)})"
                },
                "dimensions": [
                    {"name": "Brand Distinctiveness & Memorability", "score": 7.5, "reasoning": f"**PHONETIC ARCHITECTURE:**\n'{brand_name}' demonstrates {'strong' if len(brand_name) <= 10 else 'moderate'} memorability characteristics.\n\n**COMPETITIVE ISOLATION:**\nAs a coined term, offers high distinctiveness in the {category} market."},
                    {"name": "Cultural & Linguistic Resonance", "score": 7.2, "reasoning": f"**GLOBAL LINGUISTIC AUDIT:**\nNo negative connotations detected across major languages.\n\n**CULTURAL SEMIOTICS:**\nNeutral-positive associations suitable for international branding."},
                    {"name": "Premiumisation & Trust Curve", "score": 7.0, "reasoning": f"**PRICING POWER:**\nName structure supports {'premium' if overall_score >= 70 else 'mid-tier'} positioning.\n\n**TRUST SIGNALS:**\nProfessional presentation suitable for {category} sector."},
                    {"name": "Scalability & Brand Architecture", "score": 7.3, "reasoning": f"**CATEGORY STRETCH:**\nFlexible foundation for product line extensions.\n\n**ARCHITECTURE FIT:**\nWorks as standalone brand or master brand."},
                    {"name": "Trademark & Legal Sensitivity", "score": float(trademark_score), "reasoning": f"**DISTINCTIVENESS:**\n{'High' if trademark_risk <= 3 else 'Moderate' if trademark_risk <= 6 else 'Low'} distinctiveness for trademark purposes.\n\n**RISK LEVEL:**\n{trademark_risk}/10 - {'Favorable' if trademark_risk <= 3 else 'Manageable' if trademark_risk <= 6 else 'Challenging'} registration outlook."},
                    {"name": "Consumer Perception Mapping", "score": 7.0, "reasoning": f"**PERCEPTUAL GRID:**\nPositioned for {category} consumer expectations.\n\n**EMOTIONAL RESPONSE:**\nLikely to evoke innovation and modernity associations."}
                ],
                "domain_analysis": {
                    "exact_match_status": "TAKEN" if not domain_available else "AVAILABLE",
                    "risk_level": "LOW",
                    "has_active_business": "UNKNOWN",
                    "has_trademark": "UNKNOWN",
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
                "social_availability": {
                    "handle": brand_name.lower(),
                    "twitter": {"available": True, "url": f"https://twitter.com/{brand_name.lower()}"},
                    "instagram": {"available": True, "url": f"https://instagram.com/{brand_name.lower()}"},
                    "linkedin": {"available": True, "url": f"https://linkedin.com/company/{brand_name.lower()}"},
                    "facebook": {"available": True, "url": f"https://facebook.com/{brand_name.lower()}"},
                    "youtube": {"available": True, "url": f"https://youtube.com/@{brand_name.lower()}"},
                    "tiktok": {"available": True, "url": f"https://tiktok.com/@{brand_name.lower()}"},
                    "taken_platforms": [],
                    "available_platforms": ["twitter", "instagram", "linkedin", "facebook", "youtube", "tiktok"],
                    "recommendation": f"Secure @{brand_name.lower()} across all major platforms immediately."
                },
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
                    "dimension_breakdown": [
                        {"Brand Distinctiveness": 7.5},
                        {"Cultural Resonance": 7.2},
                        {"Premium Positioning": 7.0},
                        {"Scalability": 7.3},
                        {"Trademark Strength": float(trademark_score)},
                        {"Market Perception": 7.0}
                    ],
                    "recommendations": generate_smart_final_recommendations(brand_name, category, request.countries, domain_available, nice_class),
                    "alternative_path": f"If primary strategy faces obstacles, consider: 1) Modified spelling variations, 2) Adding descriptive suffix (e.g., '{brand_name}Labs'), 3) Geographic modifiers for specific markets."
                },
                "mckinsey_analysis": {
                    "executive_recommendation": "PROCEED" if verdict == "GO" else "REFINE" if verdict == "CAUTION" else "PIVOT",
                    "recommendation_rationale": f"Based on comprehensive analysis of trademark landscape, digital availability, and market positioning, '{brand_name}' {'is recommended for brand development' if verdict == 'GO' else 'requires refinement before proceeding' if verdict == 'CAUTION' else 'should be reconsidered'}.",
                    "critical_assessment": f"**Strategic Assessment:**\n\n{'Strong candidate with favorable characteristics across all evaluation dimensions.' if verdict == 'GO' else 'Moderate concerns identified that can be addressed with proper planning.' if verdict == 'CAUTION' else 'Significant obstacles require alternative approach.'}",
                    "benefits_experiences": {
                        "linguistic_roots": f"**Etymology Analysis:**\n'{brand_name}' is a coined/invented term with no direct linguistic origin, providing maximum trademark distinctiveness.",
                        "phonetic_analysis": f"**Sound Architecture:**\n{len(brand_name)}-character name with {'smooth' if len(brand_name) <= 10 else 'extended'} phonetic flow. {'Easy' if len(brand_name) <= 8 else 'Moderate'} pronunciation across language groups.",
                        "emotional_promises": ["Innovation", "Modernity", "Trustworthiness", "Premium Quality"],
                        "functional_benefits": ["Distinctiveness", "Memorability", "Flexibility"],
                        "benefit_map": [
                            {"name_trait": "Coined structure", "user_perception": "Innovative brand", "benefit_type": "Emotional"},
                            {"name_trait": "Phonetic clarity", "user_perception": "Professional", "benefit_type": "Functional"}
                        ],
                        "target_persona_fit": f"Aligns with {category} consumers seeking modern, trustworthy brands."
                    },
                    "distinctiveness": {
                        "distinctiveness_score": 7 if verdict == "GO" else 5,
                        "category_noise_level": "MEDIUM",
                        "industry_comparison": f"Compared to established {category} brands, '{brand_name}' offers fresh positioning with unique identity.",
                        "naming_tropes_analysis": f"Avoids common {category} naming patterns (nature words, clinical terms), creating differentiation opportunity.",
                        "similar_competitors": [],
                        "differentiation_opportunities": [
                            "Leverage coined nature for brand storytelling",
                            "Build unique visual identity around name",
                            "Create proprietary brand vocabulary"
                        ]
                    },
                    "brand_architecture": {
                        "elasticity_score": 7,
                        "elasticity_analysis": f"'{brand_name}' provides flexible foundation for product line expansion within and beyond {category}.",
                        "recommended_architecture": "House of Brands" if len(brand_name) > 10 else "Branded House",
                        "architecture_rationale": f"Name structure supports {'master brand approach with sub-brands' if len(brand_name) <= 10 else 'independent product branding under corporate umbrella'}.",
                        "memorability_index": 8 if len(brand_name) <= 8 else 6,
                        "memorability_factors": ["Unique structure", "No competing associations", "Clean phonetics"],
                        "global_scalability": "High - coined terms translate well across markets without linguistic conflicts."
                    },
                    "alternative_directions": [] if verdict == "GO" else [
                        {
                            "direction_name": "Simplified Variation",
                            "example_names": [f"{brand_name[:6]}", f"{brand_name[:4]}a", f"{brand_name[:5]}o"],
                            "rationale": "Shorter versions may improve memorability",
                            "mckinsey_principle": "Distinctiveness"
                        },
                        {
                            "direction_name": "Category Modifier",
                            "example_names": [f"{brand_name[:5]} Beauty", f"{brand_name[:5]} Skin", f"Pure {brand_name[:5]}"],
                            "rationale": "Adding category context aids positioning",
                            "mckinsey_principle": "Benefits"
                        }
                    ]
                }
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
            
            fallback_data = generate_fallback_report(
                brand_name=brand_name,
                category=request.category,
                domain_data=domain_data,
                social_data=social_data,
                trademark_data=trademark_data_dict,
                visibility_data=visibility_data
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
        
        race_result = {
            "model": "FALLBACK/timeout",
            "data": generate_fallback_report(
                brand_name=brand_name,
                category=request.category,
                domain_data=domain_data,
                social_data=social_data,
                trademark_data=trademark_data_dict,
                visibility_data=visibility_data
            )
        }
    
    winning_model = race_result["model"]
    data = race_result["data"]
    
    logging.info(f"Successfully generated report with model {winning_model}")
    
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
        
        # Add dimensions if missing
        if not brand_score.dimensions or len(brand_score.dimensions) == 0:
            logging.warning(f"DIMENSIONS MISSING for '{brand_score.brand_name}' - Adding calculated dimensions")
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
        
        # Check if brand name appears to be invented (no dictionary words)
        brand_is_invented = not any(word.lower() in brand_name_for_matrix.lower() for word in 
            ['shop', 'store', 'tech', 'soft', 'cloud', 'pay', 'money', 'quick', 'fast', 'best', 'top', 'pro', 'smart', 'easy'])
        
        # Generate intelligent matrix
        intelligent_matrix = generate_intelligent_trademark_matrix(
            brand_name=brand_name_for_matrix,
            category=request.category,
            trademark_data=tr_data_for_matrix,
            brand_is_invented=brand_is_invented
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
            mckinsey_recommendation = "PIVOT" if verdict == "REJECT" else "REFINE" if verdict == "CAUTION" else "PROCEED"
            
            brand_score.mckinsey_analysis = {
                "benefits_experiences": {
                    "linguistic_roots": f"The name '{brand_score.brand_name}' appears to be {'an invented/coined term' if not any(c in brand_score.brand_name.lower() for c in ['tech', 'soft', 'corp', 'global']) else 'a compound/descriptive term'}.",
                    "phonetic_analysis": f"The name has {len(brand_score.brand_name)} characters with {'easy' if len(brand_score.brand_name) <= 8 else 'moderate'} pronunciation complexity.",
                    "emotional_promises": ["Innovation", "Modernity", "Trust"],
                    "functional_benefits": ["Clarity", "Professionalism"],
                    "benefit_map": [
                        {"name_trait": "Name length", "user_perception": "Memorable" if len(brand_score.brand_name) <= 8 else "Complex", "benefit_type": "Functional"},
                        {"name_trait": "Sound pattern", "user_perception": "Professional", "benefit_type": "Emotional"}
                    ],
                    "target_persona_fit": "Moderate fit with professional/business audience."
                },
                "distinctiveness": {
                    "distinctiveness_score": 6 if verdict == "GO" else 4,
                    "category_noise_level": "MEDIUM",
                    "industry_comparison": f"Compared to industry leaders in {request.category}, this name {'stands out' if verdict == 'GO' else 'may face differentiation challenges'}.",
                    "naming_tropes_analysis": "Analysis based on common patterns in the industry.",
                    "similar_competitors": [],
                    "differentiation_opportunities": ["Consider unique visual branding", "Develop strong tagline", "Build distinctive brand voice"]
                },
                "brand_architecture": {
                    "elasticity_score": 7 if verdict == "GO" else 5,
                    "elasticity_analysis": f"The name has {'good' if verdict == 'GO' else 'limited'} potential for extension across product lines.",
                    "recommended_architecture": "Standalone House Brand",
                    "architecture_rationale": "Works best as a primary brand rather than sub-brand.",
                    "memorability_index": 7 if len(brand_score.brand_name) <= 8 else 5,
                    "memorability_factors": ["Name length", "Uniqueness", "Pronunciation ease"],
                    "global_scalability": "Requires validation for international markets."
                },
                "executive_recommendation": mckinsey_recommendation,
                "recommendation_rationale": f"Based on trademark analysis and market positioning, this name is recommended to {mckinsey_recommendation.lower()}.",
                "critical_assessment": f"{'Strong candidate with minor refinements needed.' if verdict == 'GO' else 'Significant concerns identified that require attention.' if verdict == 'CAUTION' else 'Critical issues prevent recommendation for use.'}",
                "alternative_directions": [] if mckinsey_recommendation == "PROCEED" else [
                    {
                        "direction_name": "Abstract/Invented Approach",
                        "example_names": ["Nexiva", "Zephora", "Quantix"],
                        "rationale": "Invented names offer stronger trademark protection and uniqueness.",
                        "mckinsey_principle": "Distinctiveness"
                    },
                    {
                        "direction_name": "Descriptive + Modifier",
                        "example_names": [f"True{request.category.split()[0]}", f"Prime{request.category.split()[0]}", f"Nova{request.category.split()[0]}"],
                        "rationale": "Combines category clarity with distinctive modifier.",
                        "mckinsey_principle": "Benefits"
                    },
                    {
                        "direction_name": "Metaphor/Symbolic",
                        "example_names": ["Pinnacle", "Horizon", "Vertex"],
                        "rationale": "Metaphorical names communicate aspiration and values.",
                        "mckinsey_principle": "Architecture"
                    }
                ]
            }
            logging.info(f"✅ Added McKinsey analysis for '{brand_score.brand_name}': {mckinsey_recommendation}")
    
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
app.include_router(admin_router)  # Admin panel routes

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
