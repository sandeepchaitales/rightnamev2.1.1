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
