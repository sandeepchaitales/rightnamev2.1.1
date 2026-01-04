from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
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

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Import custom modules
from schemas import BrandEvaluationRequest, BrandEvaluationResponse, StatusCheck, StatusCheckCreate, DimensionScore, BrandScore, BrandAuditRequest, BrandAuditResponse, BrandAuditDimension, SWOTAnalysis, SWOTItem, CompetitorData, MarketData, StrategicRecommendation, CompetitivePosition
from prompts import SYSTEM_PROMPT
from brand_audit_prompt import BRAND_AUDIT_SYSTEM_PROMPT, build_brand_audit_prompt
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

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'rightname_db')]

# Initialize LLM Chat
EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')
if not EMERGENT_KEY:
    logging.warning("EMERGENT_LLM_KEY not found in .env")

# Create the main app
app = FastAPI()

# Router
api_router = APIRouter(prefix="/api")

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
    
    # ========== SIMPLIFIED & RELIABLE BRAND DETECTION ==========
    # PRINCIPLE: If web search finds the brand with category context, it's likely real
    web_evidence = []
    brand_found_online = False
    web_confidence = "LOW"
    
    try:
        import re
        brand_lower = brand_name.lower().replace(" ", "")
        brand_with_space = brand_name.lower()
        
        # Simple search: exact brand name in quotes
        search_query = f'"{brand_name}"'
        search_url = f"https://www.bing.com/search?q={search_query.replace(' ', '+')}"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    html = await response.text()
                    html_lower = html.lower()
                    
                    # Count exact brand mentions
                    brand_pattern = re.escape(brand_with_space)
                    mentions = len(re.findall(brand_pattern, html_lower))
                    
                    # Check for strong signals (platform presence)
                    strong_signals = []
                    if any(f"{brand_lower}.{ext}" in html_lower for ext in ["com", "in", "co.in", "co"]):
                        strong_signals.append("domain")
                    if "zomato" in html_lower and mentions >= 1:
                        strong_signals.append("zomato")
                    if "swiggy" in html_lower and mentions >= 1:
                        strong_signals.append("swiggy")
                    if "justdial" in html_lower and mentions >= 1:
                        strong_signals.append("justdial")
                    
                    print(f"🔎 WEB: '{brand_name}' mentions={mentions}, strong={strong_signals}", flush=True)
                    logging.warning(f"🔎 WEB: '{brand_name}' mentions={mentions}, strong={strong_signals}")
                    
                    # SIMPLE DETECTION RULES:
                    # Rule 1: Platform presence = HIGH confidence
                    if len(strong_signals) >= 1:
                        brand_found_online = True
                        web_confidence = "HIGH"
                        web_evidence = [f"mentions:{mentions}"] + strong_signals
                        logging.warning(f"🌐 WEB HIGH: '{brand_name}' found on business platform!")
                    
                    # Rule 2: Multiple mentions = MEDIUM confidence (trust the count)
                    elif mentions >= 3:
                        brand_found_online = True
                        web_confidence = "MEDIUM"
                        web_evidence = [f"mentions:{mentions}"]
                        logging.warning(f"🌐 WEB MEDIUM: '{brand_name}' has {mentions} search mentions")
                    
                    # Rule 3: Some mentions = LOW confidence
                    elif mentions >= 1:
                        brand_found_online = True
                        web_confidence = "LOW"
                        web_evidence = [f"mentions:{mentions}"]
                        logging.warning(f"🌐 WEB LOW: '{brand_name}' has {mentions} mentions")
                        
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
- Check if there's a company, cafe chain, restaurant, app, or product called "{brand_name}"
- Regional brands in India, USA, or globally count!
- Even small chains with 5-10+ locations should be flagged
- Check Zomato, Swiggy, Google Maps presence

⚠️ INDIAN CAFE/CHAI BRANDS TO CHECK AGAINST:
- Chai Duniya, Chai Point, Chaayos, Chai Sutta Bar, MBA Chai Wala, Chai Break
- Chai Bunk, Chai Kings, Chai Waale, Chai Garam, Chai Time
- Any brand with "Chai" + Hindi word combination

⚠️ STRICT CONFLICT RULES - Flag as conflict if ANY of these apply:
1. EXACT BRAND EXISTS: A company/brand called "{brand_name}" already operates (even regionally)
2. EXACT MATCH: Same name as another brand (case-insensitive)
3. PLURALIZATION: Adding/removing 's' (MoneyControls = Moneycontrol)
4. PHONETIC SIMILARITY: Sounds similar when spoken (BUMBELL ≈ Bumble)
5. LETTER VARIATIONS: Extra/missing letters (Nikee = Nike)
6. SPACING CHANGES: With/without spaces (FaceBook = Facebook)
7. REGIONAL BRANDS: Indian cafes, restaurants, apps, newspapers (Chaayos, Chai Point, etc.)
8. GLOBAL BRANDS: Tech companies, apps, products

IMPORTANT: 
- When in doubt, FLAG AS CONFLICT - it's safer to reject
- If "{brand_name}" sounds like it could be an existing cafe/restaurant/business - CHECK CAREFULLY
- "Chai Duniya" IS an existing chai cafe chain - if this exact name or similar is asked, REJECT IT
- "Red Bucket Biryani" IS an existing biryani chain - if this exact name or similar is asked, REJECT IT

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
                result["exists"] = True
                result["confidence"] = llm_result.get("confidence", "MEDIUM")
                result["matched_brand"] = llm_result.get("conflicting_brand", brand_name)
                result["evidence"] = [
                    f"Similarity: {llm_result.get('similarity_percentage', 0)}%",
                    llm_result.get("brand_info", "")
                ]
                if web_evidence:
                    result["evidence"].extend([f"Web: {e}" for e in web_evidence])
                result["reason"] = llm_result.get("reason", "Conflict detected by AI analysis")
                if brand_exists:
                    result["reason"] = f"EXISTING BRAND: {result['reason']}"
                
                print(f"🚨 LLM DETECTED CONFLICT: '{brand_name}' ~ '{result['matched_brand']}' ({llm_result.get('similarity_percentage')}%)", flush=True)
                logging.warning(f"🚨 LLM DETECTED CONFLICT: '{brand_name}' ~ '{result['matched_brand']}' ({llm_result.get('similarity_percentage')}%)")
            
            # If LLM says no conflict but web search found evidence, check confidence
            elif brand_found_online and not has_conflict:
                # ONLY override LLM when web has HIGH confidence (platform presence)
                # MEDIUM/LOW confidence alone should NOT override LLM
                if web_confidence == "HIGH":
                    print(f"⚠️ WEB OVERRIDE: LLM said no conflict, but web found '{brand_name}' on business platform!", flush=True)
                    logging.warning(f"⚠️ WEB OVERRIDE: LLM missed '{brand_name}' - found on platform")
                    result["exists"] = True
                    result["confidence"] = web_confidence
                    result["matched_brand"] = brand_name
                    result["evidence"] = [f"Web: {e}" for e in web_evidence]
                    result["reason"] = f"Brand '{brand_name}' found on business platform (found: {', '.join(web_evidence[:2])})"
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

@api_router.post("/evaluate", response_model=BrandEvaluationResponse)
async def evaluate_brands(request: BrandEvaluationRequest):
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
        if dynamic_result["exists"] and dynamic_result["confidence"] in ["HIGH", "MEDIUM"]:
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
    
    # 3. Trademark research data
    trademark_research_data = []
    for brand in request.brand_names:
        tm_data = all_brand_data[brand]["trademark"]
        if tm_data and tm_data.get("success"):
            trademark_research_data.append(tm_data.get("prompt_data", ""))
            logging.info(f"Trademark research for '{brand}': Success")
        else:
            trademark_research_data.append(tm_data.get("prompt_data", f"Trademark research unavailable for {brand}") if tm_data else f"Trademark research unavailable for {brand}")
    trademark_research_context = "\n\n".join(trademark_research_data)
    
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
                
                # OVERRIDE: Force REJECT verdict for brands caught by dynamic search
                if all_rejections:
                    for i, brand_score in enumerate(evaluation.brand_scores):
                        brand_name = brand_score.brand_name
                        if brand_name in all_rejections or brand_name.lower() in [b.lower() for b in all_rejections.keys()]:
                            rejection_info = all_rejections.get(brand_name) or all_rejections.get(brand_name.upper()) or list(all_rejections.values())[0]
                            matched_brand = rejection_info.get('matched_brand', 'Unknown')
                            
                            logging.warning(f"OVERRIDING LLM verdict for '{brand_name}' - Conflict detected: {matched_brand}")
                            
                            # Force REJECT verdict
                            evaluation.brand_scores[i].verdict = "REJECT"
                            evaluation.brand_scores[i].namescore = 5.0  # Near-zero score
                            evaluation.brand_scores[i].summary = f"⛔ FATAL CONFLICT: '{brand_name}' is too similar to existing brand '{matched_brand}'. Using this name would constitute trademark infringement. This name CANNOT be used for any business purpose."
                            
                            # Update trademark risk
                            evaluation.brand_scores[i].trademark_risk = {
                                "overall_risk": "CRITICAL",
                                "reason": f"Similar to existing brand '{matched_brand}'. Trademark infringement likely."
                            }
                            
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
    """Perform web search using DuckDuckGo"""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            if results:
                formatted = []
                for i, r in enumerate(results, 1):
                    formatted.append(f"[{i}] {r.get('title', 'No title')}\n{r.get('body', 'No description')}\nURL: {r.get('href', 'No URL')}")
                return "\n\n".join(formatted)
            return "No results found"
    except Exception as e:
        logging.error(f"Web search error for '{query}': {e}")
        return f"Search failed: {str(e)}"

async def gather_brand_audit_research(brand_name: str, brand_website: str, competitor_1: str, 
                                       competitor_2: str, category: str, geography: str) -> dict:
    """Execute 4-phase research workflow for brand audit"""
    
    research_data = {}
    all_queries = []
    
    # Extract domain names for cleaner searches
    brand_domain = brand_website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    comp1_domain = competitor_1.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    comp2_domain = competitor_2.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    comp1_name = comp1_domain.split(".")[0].title()
    comp2_name = comp2_domain.split(".")[0].title()
    
    year_range = "2023 2024 2025"
    
    # PHASE 1: Foundational Brand Research
    logging.info(f"Brand Audit Phase 1: Foundational research for {brand_name}")
    phase1_queries = [
        f"{brand_name} franchise {category} {geography}",
        f"{brand_name} expansion growth {year_range}",
        f"{brand_name} reviews ratings customer sentiment"
    ]
    all_queries.extend(phase1_queries)
    
    phase1_results = []
    for q in phase1_queries:
        result = await perform_web_search(q)
        phase1_results.append(f"Query: {q}\n{result}")
    research_data['phase1_data'] = "\n\n---\n\n".join(phase1_results)
    
    # PHASE 2: Competitive Landscape & Market Sizing
    logging.info(f"Brand Audit Phase 2: Competitive landscape for {brand_name}")
    phase2_queries = [
        f"{brand_name} Instagram followers engagement social media",
        f"{category} {geography} market size growth CAGR {year_range}",
        f"{comp1_name} {comp2_name} {category} comparison {geography}"
    ]
    all_queries.extend(phase2_queries)
    
    phase2_results = []
    for q in phase2_queries:
        result = await perform_web_search(q)
        phase2_results.append(f"Query: {q}\n{result}")
    research_data['phase2_data'] = "\n\n---\n\n".join(phase2_results)
    
    # PHASE 3: Benchmarking & Unit Economics
    logging.info(f"Brand Audit Phase 3: Benchmarking for {brand_name}")
    phase3_queries = [
        f"{comp1_name} {comp2_name} market share {geography} revenue",
        f"{category} franchise investment cost ROI break-even {geography}",
        f"{brand_name} revenue profitability unit economics"
    ]
    all_queries.extend(phase3_queries)
    
    phase3_results = []
    for q in phase3_queries:
        result = await perform_web_search(q)
        phase3_results.append(f"Query: {q}\n{result}")
    research_data['phase3_data'] = "\n\n---\n\n".join(phase3_results)
    
    # PHASE 4: Deep Validation & Strategic Context
    logging.info(f"Brand Audit Phase 4: Deep validation for {brand_name}")
    phase4_queries = [
        f"{brand_name} founder background story",
        f"{brand_name} Google reviews Justdial ratings",
        f"{comp1_name} vs {comp2_name} vs {brand_name} {category} analysis"
    ]
    all_queries.extend(phase4_queries)
    
    phase4_results = []
    for q in phase4_queries:
        result = await perform_web_search(q)
        phase4_results.append(f"Query: {q}\n{result}")
    research_data['phase4_data'] = "\n\n---\n\n".join(phase4_results)
    
    research_data['all_queries'] = all_queries
    
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
    
    # Build prompt
    user_prompt = build_brand_audit_prompt(
        brand_name=request.brand_name,
        brand_website=request.brand_website,
        competitor_1=request.competitor_1,
        competitor_2=request.competitor_2,
        category=request.category,
        geography=request.geography,
        research_data=research_data
    )
    
    # Models to try in order - prioritize stable models that work
    models_to_try = [
        ("openai", "gpt-4o"),
        ("openai", "gpt-4o-mini"),
        ("openai", "gpt-4.1"),
    ]
    
    content = ""
    data = None
    last_error = None
    
    for provider, model in models_to_try:
        try:
            logging.info(f"Brand Audit: Trying {provider}/{model}...")
            llm_chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"brand_audit_{uuid.uuid4()}",
                system_message=BRAND_AUDIT_SYSTEM_PROMPT
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
            break  # Success, exit the retry loop
            
        except asyncio.TimeoutError:
            last_error = f"Timeout after 120s"
            logging.warning(f"Brand Audit: {provider}/{model} timed out")
            continue
        except Exception as e:
            last_error = e
            logging.warning(f"Brand Audit: {provider}/{model} failed: {e}")
            continue  # Try next model
    
    # If all models failed
    if not data:
        logging.error(f"Brand Audit: All models failed. Last error: {last_error}")
        raise HTTPException(status_code=500, detail=f"All LLM models failed. Please try again later.")
    
    logging.info(f"Brand Audit LLM response parsed successfully")
    
    # Build response
    report_id = f"audit_{uuid.uuid4().hex[:16]}"
    
    # Parse dimensions
    dimensions = []
    for dim in data.get('dimensions', []):
        dimensions.append(BrandAuditDimension(
            name=dim.get('name', ''),
            score=float(dim.get('score', 0)),
            reasoning=dim.get('reasoning', ''),
            data_sources=dim.get('data_sources', []),
            confidence=dim.get('confidence', 'MEDIUM')
        ))
    
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
        competitors.append(CompetitorData(
            name=comp.get('name', ''),
            website=comp.get('website', ''),
            founded=comp.get('founded'),
            outlets=comp.get('outlets'),
            rating=comp.get('rating'),
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
    
    immediate_recs = [StrategicRecommendation(**r) if isinstance(r, dict) else StrategicRecommendation(title=str(r), recommended_action=str(r)) 
                     for r in immediate_raw]
    medium_recs = [StrategicRecommendation(**r) if isinstance(r, dict) else StrategicRecommendation(title=str(r), recommended_action=str(r)) 
                  for r in medium_raw]
    long_recs = [StrategicRecommendation(**r) if isinstance(r, dict) else StrategicRecommendation(title=str(r), recommended_action=str(r)) 
                for r in long_raw]
    
    logging.info(f"Brand Audit: Parsed {len(immediate_recs)} immediate, {len(medium_recs)} medium, {len(long_recs)} long-term recommendations")
    
    # Parse market data
    market_data_raw = data.get('market_data', {})
    market_data = MarketData(
        market_size=market_data_raw.get('market_size'),
        cagr=market_data_raw.get('cagr'),
        growth_drivers=market_data_raw.get('growth_drivers', []),
        key_trends=market_data_raw.get('key_trends', [])
    ) if market_data_raw else None
    
    # Build response
    response_data = BrandAuditResponse(
        report_id=report_id,
        brand_name=request.brand_name,
        brand_website=request.brand_website,
        category=request.category,
        geography=request.geography,
        overall_score=float(data.get('overall_score', 0)),
        verdict=data.get('verdict', 'MODERATE'),
        executive_summary=data.get('executive_summary', ''),
        investment_thesis=data.get('investment_thesis'),
        brand_overview=data.get('brand_overview', {}),
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
