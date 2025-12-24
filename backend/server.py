from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import ConfigDict, Field, BaseModel
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import json
import whois
import asyncio
import random
import re
import httpx

# Import custom modules
from schemas import BrandEvaluationRequest, BrandEvaluationResponse, StatusCheck, StatusCheckCreate
from prompts import SYSTEM_PROMPT
from visibility import check_visibility
from availability import check_full_availability, check_multi_domain_availability, check_social_availability

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
    
    return s

@api_router.get("/")
async def root():
    return {"message": "RightName API is running"}

@api_router.post("/evaluate", response_model=BrandEvaluationResponse)
async def evaluate_brands(request: BrandEvaluationRequest):
    if LlmChat and EMERGENT_KEY:
        llm_chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"rightname_{uuid.uuid4()}",
            system_message=SYSTEM_PROMPT
        ).with_model("openai", "gpt-4o")
    else:
        raise HTTPException(status_code=500, detail="LLM Integration not initialized (Check EMERGENT_LLM_KEY)")
    
    # 1. Check Domains
    domain_statuses = []
    for brand in request.brand_names:
        status = check_domain_availability(brand)
        domain_statuses.append(f"- {brand}: {status}")
    domain_context = "\n".join(domain_statuses)

    # 2. Check Visibility
    visibility_data = []
    for brand in request.brand_names:
        vis = check_visibility(brand)
        visibility_data.append(f"BRAND: {brand}")
        visibility_data.append("GOOGLE TOP RESULTS:")
        for res in vis['google'][:10]:
            visibility_data.append(f"  - {res}")
        visibility_data.append("APP STORE RESULTS:")
        for res in vis['apps'][:5]:
            visibility_data.append(f"  - {res}")
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

    IMPORTANT: Use the above business context to:
    1. Define the user's customer avatar accurately
    2. Define the user's product intent accurately
    3. Compare against found competitors using INTENT MATCHING (not keyword matching)
    4. Ensure brand name fits the specified vibe and USP

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
    """
    
    max_retries = 3
    last_error = None
    
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
                    raise
            
            evaluation = BrandEvaluationResponse(**data)
            
            doc = evaluation.model_dump()
            doc['created_at'] = datetime.now(timezone.utc).isoformat()
            doc['request'] = request.model_dump()
            await db.evaluations.insert_one(doc)
            
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
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
