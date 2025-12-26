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
from schemas import BrandEvaluationRequest, BrandEvaluationResponse, StatusCheck, StatusCheckCreate
from prompts import SYSTEM_PROMPT
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
    # Tech Giants
    "apple", "google", "microsoft", "amazon", "meta", "facebook", "instagram", "whatsapp",
    "netflix", "spotify", "uber", "lyft", "airbnb", "twitter", "tiktok", "snapchat", 
    "linkedin", "pinterest", "reddit", "discord", "zoom", "slack", "dropbox", "salesforce",
    "oracle", "sap", "adobe", "nvidia", "intel", "amd", "qualcomm", "cisco", "ibm", "hp",
    "dell", "lenovo", "samsung", "sony", "lg", "panasonic", "toshiba", "huawei", "xiaomi",
    # Automotive
    "tesla", "ford", "gm", "chevrolet", "toyota", "honda", "bmw", "mercedes", "audi",
    "volkswagen", "porsche", "ferrari", "lamborghini", "bentley", "rolls royce", "jaguar",
    # Food & Beverage
    "coca cola", "pepsi", "mcdonalds", "burger king", "wendys", "starbucks", "dunkin",
    "subway", "dominos", "pizza hut", "kfc", "taco bell", "chipotle", "panera",
    "nestle", "kraft", "general mills", "kelloggs", "pepsico", "mondelez",
    # Fashion & Luxury
    "nike", "adidas", "puma", "reebok", "under armour", "lululemon", "gap", "old navy",
    "zara", "h&m", "uniqlo", "forever 21", "asos", "shein", "louis vuitton", "gucci",
    "prada", "chanel", "hermes", "dior", "versace", "armani", "burberry", "coach",
    "michael kors", "ralph lauren", "tommy hilfiger", "calvin klein", "levis",
    # Finance
    "visa", "mastercard", "american express", "paypal", "stripe", "square", "venmo",
    "chase", "bank of america", "wells fargo", "citibank", "goldman sachs", "morgan stanley",
    # Beauty & Personal Care
    "loreal", "maybelline", "mac", "sephora", "ulta", "estee lauder", "clinique",
    "neutrogena", "dove", "pantene", "head shoulders", "gillette", "olay",
    # Entertainment
    "disney", "warner bros", "universal", "paramount", "sony pictures", "mgm",
    "hbo", "showtime", "hulu", "paramount plus", "peacock", "espn", "cnn", "fox",
    # Others
    "fedex", "ups", "usps", "dhl", "amazon prime", "ebay", "etsy", "shopify",
    "alibaba", "aliexpress", "wish", "wayfair", "overstock", "chewy", "petco", "petsmart"
}

def check_famous_brand(brand_name: str) -> dict:
    """
    Check if brand name matches a famous brand (case-insensitive).
    Returns dict with is_famous, matched_brand, and reason.
    """
    normalized = brand_name.lower().strip()
    
    # Exact match
    if normalized in FAMOUS_BRANDS:
        return {
            "is_famous": True,
            "matched_brand": normalized.title(),
            "reason": f"'{brand_name}' is an exact match of the famous brand '{normalized.title()}'. This name is legally protected and cannot be used."
        }
    
    # Check without spaces/hyphens
    normalized_no_space = normalized.replace(" ", "").replace("-", "").replace("_", "")
    for famous in FAMOUS_BRANDS:
        famous_no_space = famous.replace(" ", "").replace("-", "")
        if normalized_no_space == famous_no_space:
            return {
                "is_famous": True,
                "matched_brand": famous.title(),
                "reason": f"'{brand_name}' matches the famous brand '{famous.title()}'. This name is legally protected."
            }
    
    return {"is_famous": False, "matched_brand": None, "reason": None}

@api_router.get("/")
async def root():
    return {"message": "RightName API is running"}

@api_router.post("/evaluate", response_model=BrandEvaluationResponse)
async def evaluate_brands(request: BrandEvaluationRequest):
    
    # 0. FAMOUS BRAND CHECK - Auto-reject famous brands before any other processing
    famous_brand_rejections = {}
    for brand in request.brand_names:
        famous_check = check_famous_brand(brand)
        if famous_check["is_famous"]:
            famous_brand_rejections[brand] = famous_check
            logging.warning(f"FAMOUS BRAND DETECTED: {brand} matches {famous_check['matched_brand']}")
    
    if LlmChat and EMERGENT_KEY:
        # Try primary model first, then fallback
        models_to_try = [
            ("openai", "gpt-4o"),
            ("openai", "gpt-4o-mini"),  # Fallback model
        ]
    else:
        raise HTTPException(status_code=500, detail="LLM Integration not initialized (Check EMERGENT_LLM_KEY)")
    
    # 1. Check Domains
    domain_statuses = []
    for brand in request.brand_names:
        status = check_domain_availability(brand)
        domain_statuses.append(f"- {brand}: {status}")
    domain_context = "\n".join(domain_statuses)

    # 1.5 STRING SIMILARITY CHECK (Levenshtein + Jaro-Winkler)
    similarity_data = []
    similarity_should_reject = {}
    for brand in request.brand_names:
        sim_result = check_brand_similarity(brand, request.industry or "", request.category)
        similarity_data.append(format_similarity_report(sim_result))
        if sim_result['should_reject']:
            similarity_should_reject[brand] = sim_result
    
    similarity_context = "\n\n".join(similarity_data)
    
    # 1.6 TRADEMARK RESEARCH - Real-time web search for trademark conflicts
    trademark_research_data = []
    for brand in request.brand_names:
        try:
            research_result = await conduct_trademark_research(
                brand_name=brand,
                industry=request.industry or "",
                category=request.category,
                countries=request.countries
            )
            trademark_research_data.append(format_research_for_prompt(research_result))
            logging.info(f"Trademark research for '{brand}': Risk {research_result.overall_risk_score}/10, "
                        f"Conflicts: {research_result.total_conflicts_found}")
        except Exception as e:
            logging.error(f"Trademark research failed for '{brand}': {str(e)}")
            trademark_research_data.append(f"⚠️ Trademark research unavailable for {brand}: {str(e)}")
    
    trademark_research_context = "\n\n".join(trademark_research_data)
    
    # 2. Check Visibility (Enhanced with category-aware app store search)
    visibility_data = []
    for brand in request.brand_names:
        # Pass category and industry for comprehensive app store search
        vis = check_visibility(brand, category=request.category, industry=request.industry or "")
        visibility_data.append(f"BRAND: {brand}")
        visibility_data.append("GOOGLE TOP RESULTS:")
        for res in vis['google'][:10]:
            visibility_data.append(f"  - {res}")
        visibility_data.append("APP STORE RESULTS:")
        for res in vis['apps'][:10]:  # Increased limit to show more app results
            visibility_data.append(f"  - {res}")
        # Add phonetic variants that were checked
        if vis.get('phonetic_variants_checked'):
            visibility_data.append(f"PHONETIC VARIANTS CHECKED: {', '.join(vis['phonetic_variants_checked'])}")
        # Add detailed app search summary for LLM
        if vis.get('app_search_summary'):
            visibility_data.append("\nDETAILED APP SEARCH ANALYSIS:")
            visibility_data.append(vis['app_search_summary'])
        visibility_data.append("---")
    
    visibility_context = "\n".join(visibility_data)
    
    # 3. Check Multi-Domain Availability (category + country specific)
    multi_domain_data = []
    for brand in request.brand_names:
        domain_result = await check_multi_domain_availability(brand, request.category, request.countries)
        multi_domain_data.append(f"BRAND: {brand}")
        multi_domain_data.append(f"Category TLDs checked: {domain_result['category_tlds_checked']}")
        multi_domain_data.append(f"Country TLDs checked: {domain_result['country_tlds_checked']}")
        for d in domain_result['checked_domains']:
            status_icon = "✅" if d.get('available') else "❌"
            multi_domain_data.append(f"  {status_icon} {d['domain']}: {d['status']}")
        multi_domain_data.append("---")
    
    multi_domain_context = "\n".join(multi_domain_data)
    
    # 4. Check Social Handle Availability
    social_data = []
    for brand in request.brand_names:
        social_result = await check_social_availability(brand, request.countries)
        social_data.append(f"BRAND: {brand} (Handle: @{social_result['handle']})")
        for p in social_result['platforms_checked']:
            status_icon = "✅" if p.get('available') else "❌" if p.get('available') == False else "❓"
            social_data.append(f"  {status_icon} {p['platform']}: {p['status']}")
        social_data.append("---")
    
    social_context = "\n".join(social_data)
    
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
    """
    
    max_retries = 3
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
            
            # OVERRIDE: Force REJECT verdict for famous brands
            if famous_brand_rejections:
                for i, brand_score in enumerate(evaluation.brand_scores):
                    brand_name = brand_score.brand_name
                    if brand_name in famous_brand_rejections or brand_name.lower() in [b.lower() for b in famous_brand_rejections.keys()]:
                        famous_info = famous_brand_rejections.get(brand_name) or famous_brand_rejections.get(brand_name.upper()) or list(famous_brand_rejections.values())[0]
                        
                        logging.warning(f"OVERRIDING LLM verdict for '{brand_name}' - Famous brand detected: {famous_info['matched_brand']}")
                        
                        # Force REJECT verdict
                        evaluation.brand_scores[i].verdict = "REJECT"
                        evaluation.brand_scores[i].namescore = 5.0  # Near-zero score
                        evaluation.brand_scores[i].summary = f"⛔ FATAL CONFLICT: '{brand_name}' is an EXISTING MAJOR TRADEMARK of {famous_info['matched_brand']}. Using this name would constitute trademark infringement and is legally prohibited. This name CANNOT be used for any business purpose."
                        
                        # Update trademark risk
                        evaluation.brand_scores[i].trademark_risk = {
                            "overall_risk": "CRITICAL",
                            "reason": f"EXACT MATCH of famous brand '{famous_info['matched_brand']}'. Trademark infringement guaranteed."
                        }
                        
                        # Clear recommendations (no point recommending anything for a rejected name)
                        if evaluation.brand_scores[i].domain_analysis:
                            evaluation.brand_scores[i].domain_analysis.alternatives = []
                            evaluation.brand_scores[i].domain_analysis.strategy_note = "N/A - Name rejected due to famous brand conflict"
                        if evaluation.brand_scores[i].multi_domain_availability:
                            evaluation.brand_scores[i].multi_domain_availability.recommended_domain = "N/A - Name rejected"
                            evaluation.brand_scores[i].multi_domain_availability.acquisition_strategy = "N/A - Name rejected"
                        if evaluation.brand_scores[i].social_availability:
                            evaluation.brand_scores[i].social_availability.recommendation = "N/A - Name rejected due to famous brand conflict"
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
            return evaluation
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            if "Budget has been exceeded" in error_msg:
                logging.error(f"LLM Budget Exceeded: {error_msg}")
                raise HTTPException(status_code=402, detail="Emergent Key Budget Exceeded. Please add credits.")
            
            # Retry on 502/Gateway/Service errors AND JSON/Validation errors
            if any(x in error_msg for x in ["502", "BadGateway", "ServiceUnavailable", "Expecting", "JSON", "validation error", "control character"]):
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logging.warning(f"LLM Error (Attempt {attempt+1}/{max_retries}): {error_msg}. Retrying in {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
                continue
            
            logging.error(f"LLM Error: {error_msg}")
            break
            
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
