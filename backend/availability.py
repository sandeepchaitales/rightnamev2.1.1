"""
Social Handle & Multi-Domain Availability Checker
Enhanced with LLM-powered domain strategy analysis
"""
import aiohttp
import asyncio
import whois
import logging
import os
import json
import re
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Import Emergent LLM
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
except ImportError:
    logging.warning("emergentintegrations not found for availability module")
    LlmChat = None

EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Country to TLD mapping
COUNTRY_TLDS = {
    "India": [".in", ".co.in"],
    "USA": [".us", ".co"],
    "UK": [".co.uk", ".uk"],
    "Thailand": [".th", ".co.th"],
    "Germany": [".de"],
    "France": [".fr"],
    "Japan": [".jp", ".co.jp"],
    "China": [".cn", ".com.cn"],
    "Australia": [".com.au", ".au"],
    "Canada": [".ca"],
    "Brazil": [".com.br", ".br"],
    "UAE": [".ae"],
    "Singapore": [".sg", ".com.sg"],
    "Indonesia": [".id", ".co.id"],
    "Malaysia": [".my", ".com.my"],
    "South Korea": [".kr", ".co.kr"],
    "Italy": [".it"],
    "Spain": [".es"],
    "Netherlands": [".nl"],
    "Mexico": [".mx", ".com.mx"],
}

# Category to domain extensions mapping
CATEGORY_TLDS = {
    # E-commerce & Retail
    "e-commerce": [".shop", ".store", ".market", ".buy"],
    "online shopping": [".shop", ".store", ".market", ".buy"],
    "retail": [".shop", ".store", ".market"],
    "fashion": [".fashion", ".style", ".boutique", ".shop"],
    "clothing": [".fashion", ".style", ".wear", ".shop"],
    "jewelry": [".jewelry", ".luxury", ".shop"],
    "luxury": [".luxury", ".vip", ".boutique"],
    
    # Technology
    "technology": [".tech", ".io", ".dev", ".ai", ".app"],
    "software": [".io", ".dev", ".app", ".software", ".tech"],
    "saas": [".io", ".app", ".cloud", ".software"],
    "ai": [".ai", ".io", ".tech", ".dev"],
    "fintech": [".finance", ".money", ".io", ".app"],
    
    # Food & Beverage
    "food": [".food", ".kitchen", ".recipes", ".cafe"],
    "restaurant": [".restaurant", ".food", ".menu", ".cafe"],
    "cafe": [".cafe", ".coffee", ".bar"],
    "beverages": [".bar", ".drinks", ".cafe"],
    "energy drinks": [".energy", ".fitness", ".health"],
    
    # Health & Wellness
    "wellness": [".health", ".life", ".fit", ".care"],
    "healthcare": [".health", ".care", ".clinic", ".medical"],
    "fitness": [".fitness", ".fit", ".gym", ".health"],
    "skincare": [".beauty", ".skin", ".care", ".shop"],
    "beauty": [".beauty", ".salon", ".style", ".shop"],
    
    # Finance
    "finance": [".finance", ".money", ".capital", ".fund"],
    "banking": [".bank", ".finance", ".money"],
    "insurance": [".insure", ".insurance", ".finance"],
    "investment": [".fund", ".capital", ".investments"],
    
    # Education
    "education": [".education", ".academy", ".school", ".training"],
    "edtech": [".academy", ".education", ".courses", ".io"],
    
    # Real Estate
    "real estate": [".realty", ".estate", ".property", ".homes"],
    "property": [".property", ".realty", ".homes"],
    
    # Travel & Hospitality
    "travel": [".travel", ".tours", ".holiday", ".voyage"],
    "hospitality": [".hotel", ".resort", ".travel"],
    "tourism": [".travel", ".tours", ".holiday"],
    
    # Media & Entertainment
    "media": [".media", ".news", ".press", ".tv"],
    "entertainment": [".entertainment", ".fun", ".games", ".tv"],
    "gaming": [".games", ".game", ".play", ".fun"],
    
    # Professional Services
    "consulting": [".consulting", ".solutions", ".services", ".pro"],
    "legal": [".legal", ".law", ".attorney"],
    "marketing": [".marketing", ".agency", ".digital", ".media"],
    
    # Default
    "default": [".io", ".co", ".app", ".online"],
}

# Country-specific social platforms
COUNTRY_SOCIAL_PLATFORMS = {
    "China": ["weibo", "wechat", "douyin"],
    "Japan": ["line", "mixi"],
    "South Korea": ["kakaotalk", "naver"],
    "Russia": ["vk", "ok"],
    "India": ["instagram", "twitter", "facebook", "youtube", "linkedin"],
    "default": ["instagram", "twitter", "facebook", "youtube", "linkedin", "tiktok"],
}

# Social platform URL patterns
SOCIAL_PATTERNS = {
    "instagram": "https://www.instagram.com/{handle}/",
    "twitter": "https://twitter.com/{handle}",
    "facebook": "https://www.facebook.com/{handle}",
    "youtube": "https://www.youtube.com/@{handle}",
    "linkedin": "https://www.linkedin.com/company/{handle}",
    "tiktok": "https://www.tiktok.com/@{handle}",
    "pinterest": "https://www.pinterest.com/{handle}/",
    "threads": "https://www.threads.net/@{handle}",
}


def get_category_tlds(category: str) -> List[str]:
    """Get relevant TLDs based on category"""
    category_lower = category.lower()
    
    # Check for exact match first
    if category_lower in CATEGORY_TLDS:
        return CATEGORY_TLDS[category_lower]
    
    # Check for partial matches
    for key, tlds in CATEGORY_TLDS.items():
        if key in category_lower or category_lower in key:
            return tlds
    
    return CATEGORY_TLDS["default"]


def get_country_tlds(countries: List[str]) -> List[str]:
    """Get country-specific TLDs"""
    tlds = []
    for country in countries:
        for key, values in COUNTRY_TLDS.items():
            if key.lower() in country.lower() or country.lower() in key.lower():
                tlds.extend(values)
                break
    return list(set(tlds))  # Remove duplicates


def get_social_platforms(countries: List[str]) -> List[str]:
    """Get relevant social platforms based on countries"""
    platforms = set(COUNTRY_SOCIAL_PLATFORMS["default"])
    
    for country in countries:
        for key, specific_platforms in COUNTRY_SOCIAL_PLATFORMS.items():
            if key.lower() in country.lower():
                platforms.update(specific_platforms)
                break
    
    return list(platforms)


async def check_domain_availability(domain: str) -> Dict:
    """Check if a domain is available using whois with timeout protection"""
    try:
        # Run WHOIS in executor with timeout to prevent blocking
        loop = asyncio.get_event_loop()
        try:
            w = await asyncio.wait_for(
                loop.run_in_executor(None, whois.whois, domain),
                timeout=10.0  # 10 second timeout for WHOIS
            )
            if w.domain_name or w.creation_date:
                return {"domain": domain, "status": "TAKEN", "available": False}
            else:
                return {"domain": domain, "status": "AVAILABLE", "available": True}
        except asyncio.TimeoutError:
            logging.warning(f"WHOIS timeout for {domain}")
            return {"domain": domain, "status": "TIMEOUT", "available": None, "error": "WHOIS timeout"}
    except Exception as e:
        error_str = str(e).lower()
        if "no match" in error_str or "not found" in error_str or "no entries" in error_str:
            return {"domain": domain, "status": "AVAILABLE", "available": True}
        else:
            return {"domain": domain, "status": "UNKNOWN", "available": None, "error": str(e)[:50]}


async def check_social_handle(platform: str, handle: str) -> Dict:
    """Check if a social handle is available"""
    if platform not in SOCIAL_PATTERNS:
        return {"platform": platform, "handle": handle, "status": "UNSUPPORTED", "available": None}
    
    url = SOCIAL_PATTERNS[platform].format(handle=handle)
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as response:
                # Different platforms have different 404 behaviors
                if response.status == 404:
                    return {"platform": platform, "handle": handle, "status": "AVAILABLE", "available": True, "url": url}
                elif response.status == 200:
                    # Check content for "page not found" patterns
                    content = await response.text()
                    not_found_patterns = [
                        "page isn't available",
                        "page not found", 
                        "sorry, this page",
                        "user not found",
                        "account suspended",
                        "doesn't exist",
                        "this account doesn't exist"
                    ]
                    content_lower = content.lower()
                    for pattern in not_found_patterns:
                        if pattern in content_lower:
                            return {"platform": platform, "handle": handle, "status": "LIKELY AVAILABLE", "available": True, "url": url}
                    return {"platform": platform, "handle": handle, "status": "TAKEN", "available": False, "url": url}
                else:
                    return {"platform": platform, "handle": handle, "status": "TAKEN", "available": False, "url": url}
    except asyncio.TimeoutError:
        return {"platform": platform, "handle": handle, "status": "TIMEOUT", "available": None}
    except Exception as e:
        logging.warning(f"Social check error for {platform}/{handle}: {e}")
        return {"platform": platform, "handle": handle, "status": "ERROR", "available": None}


async def check_multi_domain_availability(brand_name: str, category: str, countries: List[str]) -> Dict:
    """
    Check domain availability across multiple TLDs based on category and country
    """
    clean_name = brand_name.lower().replace(" ", "").replace("-", "")
    
    # Get relevant TLDs
    category_tlds = get_category_tlds(category)
    country_tlds = get_country_tlds(countries)
    
    # Always include .com
    all_tlds = [".com"] + category_tlds[:4] + country_tlds[:3]  # Limit to avoid too many checks
    all_tlds = list(dict.fromkeys(all_tlds))  # Remove duplicates while preserving order
    
    # Build domain list
    domains_to_check = [f"{clean_name}{tld}" for tld in all_tlds]
    
    # Check all domains concurrently
    tasks = [check_domain_availability(domain) for domain in domains_to_check]
    results = await asyncio.gather(*tasks)
    
    # Categorize results
    available = [r for r in results if r.get("available") == True]
    taken = [r for r in results if r.get("available") == False]
    unknown = [r for r in results if r.get("available") is None]
    
    return {
        "brand_name": brand_name,
        "checked_domains": results,
        "available_domains": available,
        "taken_domains": taken,
        "unknown_domains": unknown,
        "category_tlds_checked": category_tlds[:4],
        "country_tlds_checked": country_tlds[:3],
        "summary": {
            "total_checked": len(results),
            "available_count": len(available),
            "taken_count": len(taken)
        }
    }


async def check_social_availability(brand_name: str, countries: List[str]) -> Dict:
    """
    Check social handle availability across platforms relevant to the target countries
    """
    clean_handle = brand_name.lower().replace(" ", "").replace("-", "")
    
    # Get relevant platforms
    platforms = get_social_platforms(countries)[:6]  # Limit to 6 platforms
    
    # Check all platforms concurrently
    tasks = [check_social_handle(platform, clean_handle) for platform in platforms]
    results = await asyncio.gather(*tasks)
    
    # Categorize results
    available = [r for r in results if r.get("available") == True]
    taken = [r for r in results if r.get("available") == False]
    unknown = [r for r in results if r.get("available") is None]
    
    return {
        "handle": clean_handle,
        "platforms_checked": results,
        "available_platforms": available,
        "taken_platforms": taken,
        "unknown_platforms": unknown,
        "summary": {
            "total_checked": len(results),
            "available_count": len(available),
            "taken_count": len(taken)
        }
    }


async def check_full_availability(brand_name: str, category: str, countries: List[str]) -> Dict:
    """
    Comprehensive availability check - domains + social handles
    """
    # Run both checks concurrently
    domain_task = check_multi_domain_availability(brand_name, category, countries)
    social_task = check_social_availability(brand_name, countries)
    
    domain_results, social_results = await asyncio.gather(domain_task, social_task)
    
    return {
        "domain_availability": domain_results,
        "social_availability": social_results
    }


# ============ LLM-ENHANCED DOMAIN ANALYSIS ============
# Combines WHOIS factual data with LLM intelligence

LLM_DOMAIN_ANALYSIS_PROMPT = """You are a domain strategy expert helping a brand acquire the best digital real estate.

**BRAND:** {brand_name}
**CATEGORY:** {category}
**TARGET COUNTRIES:** {countries}

**WHOIS RESULTS (FACTUAL DATA):**
{whois_data}

**YOUR TASK:**
Analyze the domain availability data and provide strategic recommendations.

**ANALYZE:**
1. **Primary .com Status**: Is it available? If taken, assess acquisition difficulty.
2. **Category TLD Strategy**: Which category-specific TLDs best fit {category}?
3. **Country TLD Priority**: Rank country TLDs by market importance.
4. **Acquisition Strategy**: If key domains are taken, what's the best approach?
5. **Domain Quality Score**: Rate the brand name's domain potential (1-10).
6. **Risk Assessment**: Typo domains, competitor squatting risks.
7. **Creative Alternatives**: If .com taken, suggest prefix/suffix alternatives.

**RESPOND IN JSON:**
{{
    "domain_quality_score": 8,
    "domain_quality_reasoning": "Short, memorable, no hyphens, clear spelling",
    
    "primary_com_analysis": {{
        "status": "AVAILABLE/TAKEN",
        "acquisition_difficulty": "EASY/MODERATE/HARD/VERY_HARD",
        "estimated_cost": "$10-15/year" or "$5,000-50,000 (premium)" or "Not for sale",
        "recommendation": "Secure immediately" or "Consider alternatives"
    }},
    
    "category_tld_ranking": [
        {{"tld": ".health", "fit_score": 9, "reason": "Perfect for healthcare category"}},
        {{"tld": ".care", "fit_score": 8, "reason": "Conveys caring service"}}
    ],
    
    "country_tld_priority": [
        {{"tld": ".in", "country": "India", "priority": 1, "reason": "Primary market"}},
        {{"tld": ".th", "country": "Thailand", "priority": 2, "reason": "Secondary market"}}
    ],
    
    "acquisition_strategy": {{
        "immediate_actions": ["Register .com if available", "Secure all country TLDs"],
        "if_com_taken": "Try get{brand_name}.com, {brand_name}app.com, or use .health as primary",
        "budget_estimate": "$100-500 for standard registration" or "$5,000+ for premium acquisition"
    }},
    
    "risk_assessment": {{
        "typo_risk": "LOW/MEDIUM/HIGH",
        "typo_domains_to_secure": ["sethworks.com", "stethwork.com"],
        "competitor_squatting_risk": "LOW/MEDIUM/HIGH",
        "trademark_conflict_risk": "LOW/MEDIUM/HIGH"
    }},
    
    "creative_alternatives": [
        {{"domain": "getstethworks.com", "type": "prefix", "availability_guess": "LIKELY_AVAILABLE"}},
        {{"domain": "stethworksapp.com", "type": "suffix", "availability_guess": "LIKELY_AVAILABLE"}},
        {{"domain": "trystethworks.com", "type": "prefix", "availability_guess": "LIKELY_AVAILABLE"}}
    ],
    
    "final_recommendation": "Concise 2-3 sentence domain strategy recommendation"
}}

Return ONLY valid JSON."""


async def llm_analyze_domain_strategy(
    brand_name: str,
    category: str,
    countries: List[str],
    whois_results: Dict
) -> Dict:
    """
    LLM-ENHANCED DOMAIN ANALYSIS
    
    Takes factual WHOIS data and adds intelligent analysis:
    - Domain quality scoring
    - Acquisition strategy
    - Risk assessment
    - Creative alternatives
    
    Falls back to basic analysis if LLM unavailable.
    """
    if not LlmChat or not EMERGENT_KEY:
        logging.warning("🌐 LLM not available for domain analysis - using basic analysis")
        return generate_basic_domain_analysis(brand_name, category, countries, whois_results)
    
    # Format WHOIS data for LLM
    whois_summary = format_whois_for_llm(whois_results)
    countries_str = ", ".join(countries) if isinstance(countries, list) else str(countries)
    
    try:
        prompt = LLM_DOMAIN_ANALYSIS_PROMPT.format(
            brand_name=brand_name,
            category=category,
            countries=countries_str,
            whois_data=whois_summary
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
        
        logging.info(f"🤖 LLM DOMAIN ANALYSIS for '{brand_name}': Quality={result.get('domain_quality_score')}/10")
        
        return {
            "llm_enhanced": True,
            "analysis": result
        }
        
    except asyncio.TimeoutError:
        logging.warning(f"LLM domain analysis timed out for '{brand_name}'")
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse LLM domain analysis: {e}")
    except Exception as e:
        logging.warning(f"LLM domain analysis failed: {e}")
    
    return generate_basic_domain_analysis(brand_name, category, countries, whois_results)


def format_whois_for_llm(whois_results: Dict) -> str:
    """Format WHOIS results into readable text for LLM"""
    lines = []
    
    # Available domains
    available = whois_results.get("available_domains", [])
    if available:
        lines.append(f"✅ AVAILABLE DOMAINS ({len(available)}):")
        for d in available[:6]:
            lines.append(f"   - {d.get('domain', 'unknown')}")
    
    # Taken domains
    taken = whois_results.get("taken_domains", [])
    if taken:
        lines.append(f"❌ TAKEN DOMAINS ({len(taken)}):")
        for d in taken[:6]:
            lines.append(f"   - {d.get('domain', 'unknown')}")
    
    # Unknown/timeout
    unknown = whois_results.get("unknown_domains", [])
    if unknown:
        lines.append(f"❓ UNKNOWN STATUS ({len(unknown)}):")
        for d in unknown[:4]:
            lines.append(f"   - {d.get('domain', 'unknown')} ({d.get('status', 'unknown')})")
    
    # Summary
    summary = whois_results.get("summary", {})
    lines.append(f"\nSUMMARY: {summary.get('available_count', 0)} available, {summary.get('taken_count', 0)} taken out of {summary.get('total_checked', 0)} checked")
    
    return "\n".join(lines)


def generate_basic_domain_analysis(
    brand_name: str,
    category: str,
    countries: List[str],
    whois_results: Dict
) -> Dict:
    """Basic domain analysis when LLM is unavailable"""
    
    available = whois_results.get("available_domains", [])
    taken = whois_results.get("taken_domains", [])
    
    # Check if .com is available
    com_available = any(d.get("domain", "").endswith(".com") and d.get("available") for d in available)
    com_taken = any(d.get("domain", "").endswith(".com") and not d.get("available") for d in taken)
    
    # Calculate domain quality score
    name_lower = brand_name.lower()
    quality_score = 7  # Base score
    
    # Adjust based on name characteristics
    if len(name_lower) <= 8:
        quality_score += 1  # Short names are better
    if len(name_lower) > 15:
        quality_score -= 1  # Long names are harder
    if "-" in name_lower or "_" in name_lower:
        quality_score -= 1  # Hyphens are bad for domains
    if name_lower.isalpha():
        quality_score += 0.5  # All letters is cleaner
    
    quality_score = min(10, max(1, quality_score))
    
    # Build analysis
    analysis = {
        "domain_quality_score": round(quality_score, 1),
        "domain_quality_reasoning": f"{'Short and memorable' if len(name_lower) <= 10 else 'Longer name'}, {'clear spelling' if name_lower.isalpha() else 'contains numbers/special chars'}",
        
        "primary_com_analysis": {
            "status": "AVAILABLE" if com_available else "TAKEN" if com_taken else "UNKNOWN",
            "acquisition_difficulty": "EASY" if com_available else "MODERATE",
            "estimated_cost": "$10-15/year" if com_available else "$500-5000 (estimated)",
            "recommendation": "Secure immediately" if com_available else "Consider category TLD as primary"
        },
        
        "category_tld_ranking": [
            {"tld": tld, "fit_score": 7, "reason": f"Category-appropriate for {category}"}
            for tld in whois_results.get("category_tlds_checked", [])[:3]
        ],
        
        "country_tld_priority": [
            {"tld": tld, "country": countries[i] if i < len(countries) else "Unknown", "priority": i + 1, "reason": "Target market"}
            for i, tld in enumerate(whois_results.get("country_tlds_checked", [])[:4])
        ],
        
        "acquisition_strategy": {
            "immediate_actions": [
                "Register .com" if com_available else f"Register available TLDs",
                "Secure primary country TLDs"
            ],
            "if_com_taken": f"Consider get{name_lower}.com or {name_lower}app.com",
            "budget_estimate": "$100-300 for standard registration"
        },
        
        "risk_assessment": {
            "typo_risk": "LOW" if len(name_lower) <= 8 else "MEDIUM",
            "typo_domains_to_secure": [],
            "competitor_squatting_risk": "LOW",
            "trademark_conflict_risk": "UNKNOWN - requires trademark search"
        },
        
        "creative_alternatives": [
            {"domain": f"get{name_lower}.com", "type": "prefix", "availability_guess": "LIKELY_AVAILABLE"},
            {"domain": f"{name_lower}app.com", "type": "suffix", "availability_guess": "LIKELY_AVAILABLE"},
            {"domain": f"try{name_lower}.com", "type": "prefix", "availability_guess": "LIKELY_AVAILABLE"}
        ],
        
        "final_recommendation": f"{'Secure {}.com immediately as primary domain.' if com_available else 'Primary .com is taken. Consider category-specific TLD or creative alternatives.'} Register country TLDs for {', '.join(countries[:2])} market presence.".format(name_lower)
    }
    
    logging.info(f"📊 BASIC DOMAIN ANALYSIS for '{brand_name}': Quality={quality_score}/10, .com={'available' if com_available else 'taken'}")
    
    return {
        "llm_enhanced": False,
        "analysis": analysis
    }


async def check_full_availability_with_llm(brand_name: str, category: str, countries: List[str]) -> Dict:
    """
    ENHANCED availability check - WHOIS + Social + LLM Analysis
    
    1. WHOIS Check (factual) - Is domain actually available?
    2. Social Check (factual) - Are handles available?
    3. LLM Analysis (intelligent) - Strategy, quality, alternatives
    """
    # Run all checks concurrently
    domain_task = check_multi_domain_availability(brand_name, category, countries)
    social_task = check_social_availability(brand_name, countries)
    
    domain_results, social_results = await asyncio.gather(domain_task, social_task)
    
    # Add LLM analysis on top of WHOIS results
    llm_analysis = await llm_analyze_domain_strategy(
        brand_name, category, countries, domain_results
    )
    
    return {
        "domain_availability": domain_results,
        "social_availability": social_results,
        "domain_strategy": llm_analysis
    }
