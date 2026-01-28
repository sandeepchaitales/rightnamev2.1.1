"""
═══════════════════════════════════════════════════════════════════════════════
DEEP MARKET INTELLIGENCE AGENT
═══════════════════════════════════════════════════════════════════════════════

Strategic Market Research Agent that performs rigorous, multi-step investigation
to find REAL competitors with ACCURATE positioning data.

Key Principles:
1. Subject-Matter > Category (find theme-specific competitors)
2. Famous brands MUST have high scores (no coordinate hallucination)
3. Real names in matrix (no generic archetypes)
4. Parallel per-country search

Author: RIGHTNAME.AI Team
Created: July 2025
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Google Custom Search
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")

# LLM Integration
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
except ImportError:
    LlmChat = None
    UserMessage = None
    EMERGENT_KEY = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE CUSTOM SEARCH HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def google_search(query: str, num_results: int = 10) -> List[Dict[str, str]]:
    """
    Perform Google Custom Search and return results.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        logger.warning("Google Custom Search not configured")
        return []
    
    try:
        import aiohttp
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": min(num_results, 10)  # Max 10 per request
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("items", [])
                    
                    results = []
                    for item in items:
                        results.append({
                            "title": item.get("title", ""),
                            "link": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                            "display_link": item.get("displayLink", "")
                        })
                    
                    logger.info(f"🔍 Google Search '{query[:50]}...' returned {len(results)} results")
                    return results
                else:
                    logger.error(f"Google Search failed: {response.status}")
                    return []
                    
    except Exception as e:
        logger.error(f"Google Search error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: NICHE HUNT - Find theme-specific competitors
# ═══════════════════════════════════════════════════════════════════════════════

async def niche_hunt(
    brand_name: str,
    category: str,
    theme_keywords: List[str],
    country: str,
    negative_keywords: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Search for competitors that match the SPECIFIC THEME, not just category.
    
    Args:
        brand_name: User's brand name
        category: Business category (e.g., "YouTube Channel")
        theme_keywords: Theme-specific keywords from Understanding Module
        country: Target country for search
        negative_keywords: Keywords to exclude
    
    Returns:
        List of potential competitors found
    """
    logger.info(f"🎯 NICHE HUNT: Starting for '{brand_name}' in {country}")
    
    negative_keywords = negative_keywords or []
    negative_str = " ".join([f"-{kw}" for kw in negative_keywords]) if negative_keywords else ""
    
    all_results = []
    
    # Build search queries based on theme
    queries = []
    
    # Query 1: Theme-specific search
    for theme in theme_keywords[:3]:  # Limit to 3 theme keywords
        queries.append(f"{theme} {country} {negative_str}")
    
    # Query 2: Category + theme in country
    queries.append(f"top {category} {' '.join(theme_keywords[:2])} {country} {negative_str}")
    
    # Query 3: Similar to brand name
    queries.append(f"{brand_name} similar {category} {country} {negative_str}")
    
    # Query 4: Competitors in category
    queries.append(f"best {category} {country} 2024 2025 {negative_str}")
    
    # Execute searches in parallel
    search_tasks = [google_search(q, num_results=5) for q in queries[:4]]
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    
    # Flatten and deduplicate results
    seen_links = set()
    for result in search_results:
        if isinstance(result, list):
            for item in result:
                link = item.get("link", "")
                if link and link not in seen_links:
                    seen_links.add(link)
                    all_results.append(item)
    
    logger.info(f"🎯 NICHE HUNT: Found {len(all_results)} unique results for {country}")
    return all_results


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: ATTRIBUTE AUDIT - Calculate real X,Y coordinates
# ═══════════════════════════════════════════════════════════════════════════════

async def attribute_audit(
    search_results: List[Dict[str, Any]],
    brand_name: str,
    category: str,
    theme_keywords: List[str],
    country: str
) -> Dict[str, Any]:
    """
    Analyze search results using LLM to extract:
    1. Real competitor names
    2. Accurate X,Y coordinates
    3. Direct vs Indirect classification
    
    CRITICAL RULES:
    - Famous brands MUST have Y (quality) > 8.0
    - Free content = low X (budget), Paid = high X (premium)
    - Direct = same theme, Indirect = same category only
    """
    logger.info(f"📊 ATTRIBUTE AUDIT: Analyzing competitors for {country}")
    
    if not search_results:
        return {
            "direct_competitors": [],
            "market_leaders": [],
            "all_competitors": []
        }
    
    # Build context from search results
    search_context = "\n".join([
        f"- {r.get('title', 'Unknown')} ({r.get('display_link', '')}): {r.get('snippet', '')[:200]}"
        for r in search_results[:15]  # Limit to 15 results
    ])
    
    prompt = f"""You are a Strategic Market Research Analyst. Analyze these search results to identify REAL competitors.

BRAND BEING ANALYZED: {brand_name}
CATEGORY: {category}
THEME/NICHE: {', '.join(theme_keywords)}
COUNTRY: {country}

SEARCH RESULTS:
{search_context}

YOUR TASK:
1. Extract REAL brand/channel/company names from the results (not generic terms)
2. For each competitor, determine:
   - Type: "DIRECT" (same theme/niche) or "INDIRECT" (same category, different theme)
   - X-Coordinate (1-10): Accessibility/Price
     * 1-3 = Free/Ad-supported content
     * 4-6 = Freemium/Some paid content
     * 7-10 = Subscription/Premium/Paid only
   - Y-Coordinate (1-10): Production Quality/Experience
     * 3-5 = UGC/Basic/Single-person
     * 6-7 = Professional/Good production
     * 8-10 = Studio quality/High budget/Famous brands

CRITICAL RULES:
- If a brand is FAMOUS or WELL-KNOWN (millions of followers), Y-score MUST be >= 8
- Free content does NOT mean low quality - YouTube stars are free but high quality
- Be specific - extract actual brand names, not descriptions
- Maximum 5 DIRECT competitors and 3 MARKET LEADERS

OUTPUT FORMAT (JSON only, no explanation):
{{
  "direct_competitors": [
    {{"name": "Actual Brand Name", "x": 3, "y": 8, "reasoning": "Why this position"}}
  ],
  "market_leaders": [
    {{"name": "Famous Brand Name", "x": 2, "y": 9, "reasoning": "Famous, free, high production"}}
  ]
}}

Return ONLY valid JSON. Extract REAL names from the search results."""

    # Call LLM for analysis
    if LlmChat and EMERGENT_KEY:
        try:
            chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
            user_msg = UserMessage(text=prompt)
            
            response = await asyncio.wait_for(
                chat.send_message(user_msg),
                timeout=20
            )
            
            response_text = str(response).strip()
            
            # Clean up JSON
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            
            # Add country to each competitor
            for comp in result.get("direct_competitors", []):
                comp["country"] = country
            for comp in result.get("market_leaders", []):
                comp["country"] = country
            
            logger.info(f"📊 ATTRIBUTE AUDIT: Found {len(result.get('direct_competitors', []))} direct, {len(result.get('market_leaders', []))} leaders in {country}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"📊 ATTRIBUTE AUDIT: JSON parse error: {e}")
        except Exception as e:
            logger.error(f"📊 ATTRIBUTE AUDIT: LLM error: {e}")
    
    # Fallback: Return empty
    return {
        "direct_competitors": [],
        "market_leaders": [],
        "all_competitors": []
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: GAP FINDER - Identify specific white space opportunities
# ═══════════════════════════════════════════════════════════════════════════════

async def gap_finder(
    competitors: Dict[str, Any],
    brand_name: str,
    category: str,
    positioning: str,
    theme_keywords: List[str],
    country: str
) -> Dict[str, str]:
    """
    Analyze competitors to find SPECIFIC structural or content gaps.
    
    BAD output: "Create better content" (generic)
    GOOD output: "Gap exists in short-form documentary format analyzing failure patterns"
    """
    logger.info(f"🔍 GAP FINDER: Analyzing white space for {country}")
    
    direct_comps = competitors.get("direct_competitors", [])
    leaders = competitors.get("market_leaders", [])
    
    if not direct_comps and not leaders:
        return {
            "white_space": f"Limited established competition in {category} space for {country}. First-mover advantage opportunity.",
            "positioning_opportunity": "Pioneer positioning with premium quality"
        }
    
    # Build competitor summary
    comp_summary = "\n".join([
        f"- {c.get('name')}: Position ({c.get('x')}, {c.get('y')}) - {c.get('reasoning', 'N/A')}"
        for c in (direct_comps + leaders)[:8]
    ])
    
    prompt = f"""You are a Strategic Market Positioning Expert. Analyze this competitive landscape to find WHITE SPACE opportunities.

BRAND: {brand_name}
CATEGORY: {category}
POSITIONING: {positioning}
THEME: {', '.join(theme_keywords)}
COUNTRY: {country}

COMPETITORS FOUND:
{comp_summary}

YOUR TASK:
Identify a SPECIFIC, ACTIONABLE gap in the market.

BAD EXAMPLES (too generic):
- "Create better content"
- "Be more authentic"
- "Focus on quality"

GOOD EXAMPLES (specific & actionable):
- "Most competitors use long-form interview format. Gap exists in short-form documentary style with data visualization."
- "All existing players target English speakers. Opportunity in regional language content."
- "Current players focus on success stories. Gap in systematic failure analysis with lessons."

OUTPUT FORMAT (JSON only):
{{
  "white_space": "Specific description of the market gap (2-3 sentences)",
  "positioning_opportunity": "Short label for the opportunity (e.g., 'Premium Vernacular Content')",
  "format_gap": "Specific content/product format that's missing",
  "audience_gap": "Underserved audience segment"
}}

Return ONLY valid JSON."""

    if LlmChat and EMERGENT_KEY:
        try:
            chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
            user_msg = UserMessage(text=prompt)
            
            response = await asyncio.wait_for(
                chat.send_message(user_msg),
                timeout=15
            )
            
            response_text = str(response).strip()
            
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            logger.info(f"🔍 GAP FINDER: Found opportunity - {result.get('positioning_opportunity', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"🔍 GAP FINDER: Error: {e}")
    
    # Fallback
    return {
        "white_space": f"Opportunity to differentiate through unique content approach in {country} market.",
        "positioning_opportunity": "Differentiated positioning",
        "format_gap": "Unique format opportunity",
        "audience_gap": "Underserved segment"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: KILL SWITCH - Critical conflict detection
# ═══════════════════════════════════════════════════════════════════════════════

async def kill_switch_check(
    brand_name: str,
    category: str,
    country: str
) -> Dict[str, Any]:
    """
    Check for deadly conflicts - existing brands with identical or confusingly similar names.
    """
    logger.info(f"⚠️ KILL SWITCH: Checking for critical conflicts - '{brand_name}' in {country}")
    
    # Search for exact name matches
    queries = [
        f'"{brand_name}" {category}',
        f'"{brand_name}" official',
        f'{brand_name} channel podcast'
    ]
    
    conflicts = []
    
    for query in queries:
        results = await google_search(query, num_results=5)
        
        for result in results:
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "").lower()
            brand_lower = brand_name.lower()
            
            # Check for exact or very close matches
            if brand_lower in title or brand_lower in snippet:
                # Check if it's an actual competitor (not news article about the brand)
                link = result.get("link", "")
                if any(platform in link for platform in ["youtube.com", "spotify.com", "apple.com/podcast", "instagram.com", "twitter.com", "linkedin.com"]):
                    conflicts.append({
                        "name": result.get("title", "Unknown"),
                        "link": link,
                        "type": "EXACT_MATCH" if brand_lower == title.split()[0].lower() else "SIMILAR",
                        "snippet": result.get("snippet", "")[:200]
                    })
    
    if conflicts:
        logger.warning(f"⚠️ KILL SWITCH: Found {len(conflicts)} potential conflicts for '{brand_name}'")
        return {
            "critical_conflict_detected": True,
            "conflict_count": len(conflicts),
            "conflicts": conflicts[:3],  # Top 3 conflicts
            "warning_message": f"⚠️ CRITICAL CONFLICT: Existing brand(s) found operating as '{brand_name}' or similar in {category} space."
        }
    
    logger.info(f"✅ KILL SWITCH: No critical conflicts found for '{brand_name}'")
    return {
        "critical_conflict_detected": False,
        "conflict_count": 0,
        "conflicts": [],
        "warning_message": None
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COUNTRY WORKER - Process single country
# ═══════════════════════════════════════════════════════════════════════════════

async def process_country_market(
    brand_name: str,
    category: str,
    positioning: str,
    theme_keywords: List[str],
    negative_keywords: List[str],
    country: str
) -> Dict[str, Any]:
    """
    Process market intelligence for a single country.
    Runs Steps 1-4 for the specified country.
    """
    import time
    start_time = time.time()
    
    logger.info(f"🌍 MARKET INTEL: Starting analysis for {country}...")
    
    try:
        # STEP 1: Niche Hunt
        search_results = await niche_hunt(
            brand_name=brand_name,
            category=category,
            theme_keywords=theme_keywords,
            country=country,
            negative_keywords=negative_keywords
        )
        
        # STEP 2: Attribute Audit
        competitors = await attribute_audit(
            search_results=search_results,
            brand_name=brand_name,
            category=category,
            theme_keywords=theme_keywords,
            country=country
        )
        
        # STEP 3: Gap Finder
        gaps = await gap_finder(
            competitors=competitors,
            brand_name=brand_name,
            category=category,
            positioning=positioning,
            theme_keywords=theme_keywords,
            country=country
        )
        
        # STEP 4: Kill Switch (only run once, not per country - moved to main function)
        # kill_switch handled at merge level
        
        processing_time = time.time() - start_time
        
        return {
            "country": country,
            "direct_competitors": competitors.get("direct_competitors", []),
            "market_leaders": competitors.get("market_leaders", []),
            "white_space": gaps.get("white_space", ""),
            "positioning_opportunity": gaps.get("positioning_opportunity", ""),
            "format_gap": gaps.get("format_gap", ""),
            "audience_gap": gaps.get("audience_gap", ""),
            "search_results_count": len(search_results),
            "processing_time_seconds": round(processing_time, 2),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"🌍 MARKET INTEL: Error processing {country}: {e}")
        return {
            "country": country,
            "direct_competitors": [],
            "market_leaders": [],
            "white_space": f"Analysis unavailable for {country}",
            "positioning_opportunity": "Manual research recommended",
            "success": False,
            "error": str(e)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FUNCTION: DEEP MARKET INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

async def deep_market_intelligence(
    brand_name: str,
    category: str,
    positioning: str,
    countries: List[str],
    understanding: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Main entry point for Deep Market Intelligence Agent.
    
    Performs parallel market research across all specified countries.
    
    Args:
        brand_name: The brand name being evaluated
        category: Business category
        positioning: Brand positioning (Premium, Budget, etc.)
        countries: List of target countries
        understanding: Output from Understanding Module (contains theme keywords)
    
    Returns:
        Complete market intelligence data with real competitor names and coordinates
    """
    import time
    start_time = time.time()
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  🎯 DEEP MARKET INTELLIGENCE AGENT                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Brand: {brand_name:<55}  ║
║  Category: {category:<53}  ║
║  Countries: {', '.join(countries):<52}  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Extract theme keywords from Understanding Module
    theme_keywords = []
    negative_keywords = []
    
    if understanding:
        # Get from competitive_context
        comp_context = understanding.get("competitive_context", {})
        search_queries = comp_context.get("direct_competitor_search_queries", [])
        theme_keywords = search_queries[:5] if search_queries else []
        
        # Get negative keywords
        not_in_category = comp_context.get("NOT_in_category", "")
        if not_in_category:
            negative_keywords = [kw.strip() for kw in not_in_category.split(",")][:5]
        
        # Get business understanding for more context
        business = understanding.get("business_understanding", {})
        if business.get("what_they_offer"):
            theme_keywords.append(business.get("what_they_offer"))
        
        # Get tokenized words for theme
        brand_analysis = understanding.get("brand_analysis", {})
        tokenized = brand_analysis.get("tokenized", [])
        combined_meaning = brand_analysis.get("combined_meaning", "")
        if combined_meaning:
            theme_keywords.append(combined_meaning)
    
    # Fallback theme keywords if not available
    if not theme_keywords:
        theme_keywords = [category, brand_name, f"{category} competitors"]
    
    logger.info(f"🎯 Theme Keywords: {theme_keywords[:5]}")
    logger.info(f"🎯 Negative Keywords: {negative_keywords}")
    
    # Run PARALLEL searches for each country
    country_tasks = [
        process_country_market(
            brand_name=brand_name,
            category=category,
            positioning=positioning,
            theme_keywords=theme_keywords,
            negative_keywords=negative_keywords,
            country=country
        )
        for country in countries
    ]
    
    # Execute all country searches in parallel
    country_results = await asyncio.gather(*country_tasks, return_exceptions=True)
    
    # Run Kill Switch check (once, not per country)
    kill_switch_result = await kill_switch_check(brand_name, category, countries[0] if countries else "Global")
    
    # Process and merge results
    country_analysis = {}
    all_direct_competitors = []
    all_market_leaders = []
    
    for result in country_results:
        if isinstance(result, dict) and result.get("success"):
            country = result.get("country", "Unknown")
            country_analysis[country] = {
                "direct_competitors": result.get("direct_competitors", []),
                "market_leaders": result.get("market_leaders", []),
                "white_space": result.get("white_space", ""),
                "positioning_opportunity": result.get("positioning_opportunity", ""),
                "format_gap": result.get("format_gap", ""),
                "audience_gap": result.get("audience_gap", "")
            }
            
            # Collect all competitors for global matrix
            all_direct_competitors.extend(result.get("direct_competitors", []))
            all_market_leaders.extend(result.get("market_leaders", []))
        elif isinstance(result, Exception):
            logger.error(f"Country processing failed: {result}")
    
    # Build global matrix from all competitors (deduplicated)
    seen_names = set()
    global_competitors = []
    
    # Add market leaders first (they're more important)
    for comp in all_market_leaders:
        name = comp.get("name", "").lower()
        if name and name not in seen_names:
            seen_names.add(name)
            global_competitors.append({
                "name": comp.get("name"),
                "x": comp.get("x", 5),
                "y": comp.get("y", 5),
                "type": "MARKET_LEADER",
                "country": comp.get("country", "Global"),
                "reasoning": comp.get("reasoning", "")
            })
    
    # Add direct competitors
    for comp in all_direct_competitors:
        name = comp.get("name", "").lower()
        if name and name not in seen_names:
            seen_names.add(name)
            global_competitors.append({
                "name": comp.get("name"),
                "x": comp.get("x", 5),
                "y": comp.get("y", 5),
                "type": "DIRECT",
                "country": comp.get("country", "Global"),
                "reasoning": comp.get("reasoning", "")
            })
    
    # Calculate user brand position based on positioning
    positioning_map = {
        "Budget": {"x": 2, "y": 5},
        "Mass": {"x": 3, "y": 6},
        "Mid-Range": {"x": 5, "y": 6},
        "Premium": {"x": 7, "y": 8},
        "Luxury": {"x": 9, "y": 9},
        "Ultra-Premium": {"x": 10, "y": 10}
    }
    user_position = positioning_map.get(positioning, {"x": 5, "y": 7})
    
    # Determine quadrant
    x, y = user_position["x"], user_position["y"]
    if x >= 6 and y >= 6:
        quadrant = "Premium Quality"
    elif x < 6 and y >= 6:
        quadrant = "Accessible Premium"
    elif x >= 6 and y < 6:
        quadrant = "Value Premium"
    else:
        quadrant = "Mass Market"
    
    processing_time = time.time() - start_time
    
    result = {
        "global_matrix": {
            "competitors": global_competitors[:10],  # Max 10 for matrix
            "user_position": {
                "x": user_position["x"],
                "y": user_position["y"],
                "quadrant": quadrant,
                "brand_name": brand_name
            },
            "x_axis_label": "Price: Budget → Premium",
            "y_axis_label": "Quality: Basic → High Production"
        },
        "country_analysis": country_analysis,
        "risk_flags": {
            "critical_conflict_detected": kill_switch_result.get("critical_conflict_detected", False),
            "conflict_count": kill_switch_result.get("conflict_count", 0),
            "conflicts": kill_switch_result.get("conflicts", []),
            "warning_message": kill_switch_result.get("warning_message")
        },
        "meta": {
            "search_engine": "Google Custom Search",
            "processing_time_seconds": round(processing_time, 2),
            "countries_analyzed": len(country_analysis),
            "total_competitors_found": len(global_competitors),
            "theme_keywords_used": theme_keywords[:5],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    }
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  🎯 DEEP MARKET INTELLIGENCE COMPLETE                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Countries Analyzed: {len(country_analysis):<43}  ║
║  Total Competitors Found: {len(global_competitors):<38}  ║
║  Critical Conflicts: {str(kill_switch_result.get('critical_conflict_detected', False)):<43}  ║
║  Processing Time: {round(processing_time, 2)}s{' ' * (45 - len(str(round(processing_time, 2))))}  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def format_competitors_for_matrix(market_intel: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Format competitor data for the strategic positioning matrix display.
    Returns list ready for frontend visualization.
    """
    global_matrix = market_intel.get("global_matrix", {})
    competitors = global_matrix.get("competitors", [])
    
    formatted = []
    for i, comp in enumerate(competitors[:10], 1):
        formatted.append({
            "name": comp.get("name", f"Competitor {i}"),
            "x_coordinate": float(comp.get("x", 5)) * 10,  # Scale to 0-100
            "y_coordinate": float(comp.get("y", 5)) * 10,  # Scale to 0-100
            "quadrant": _get_quadrant(comp.get("x", 5), comp.get("y", 5)),
            "type": comp.get("type", "COMPETITOR"),
            "country": comp.get("country", "Global")
        })
    
    return formatted


def format_country_analysis(market_intel: Dict[str, Any], country: str) -> Dict[str, Any]:
    """
    Get formatted analysis for a specific country.
    """
    country_data = market_intel.get("country_analysis", {}).get(country, {})
    
    if not country_data:
        return None
    
    return {
        "country": country,
        "direct_competitors": [
            {
                "name": c.get("name"),
                "x_coordinate": float(c.get("x", 5)) * 10,
                "y_coordinate": float(c.get("y", 5)) * 10,
                "quadrant": _get_quadrant(c.get("x", 5), c.get("y", 5)),
                "reasoning": c.get("reasoning", "")
            }
            for c in country_data.get("direct_competitors", [])
        ],
        "market_leaders": [
            {
                "name": c.get("name"),
                "x_coordinate": float(c.get("x", 5)) * 10,
                "y_coordinate": float(c.get("y", 5)) * 10,
                "quadrant": _get_quadrant(c.get("x", 5), c.get("y", 5)),
                "reasoning": c.get("reasoning", "")
            }
            for c in country_data.get("market_leaders", [])
        ],
        "white_space_analysis": country_data.get("white_space", ""),
        "positioning_opportunity": country_data.get("positioning_opportunity", ""),
        "format_gap": country_data.get("format_gap", ""),
        "audience_gap": country_data.get("audience_gap", "")
    }


def _get_quadrant(x: float, y: float) -> str:
    """Determine quadrant based on x,y coordinates (1-10 scale)."""
    if x >= 6 and y >= 6:
        return "Premium Quality"
    elif x < 6 and y >= 6:
        return "Accessible Premium"
    elif x >= 6 and y < 6:
        return "Value Premium"
    else:
        return "Mass Market"


def get_white_space_summary(market_intel: Dict[str, Any]) -> str:
    """
    Get a consolidated white space summary from all countries.
    """
    country_analysis = market_intel.get("country_analysis", {})
    
    summaries = []
    for country, data in country_analysis.items():
        white_space = data.get("white_space", "")
        if white_space:
            summaries.append(f"**{country}**: {white_space}")
    
    if summaries:
        return "\n\n".join(summaries)
    
    return "Market analysis indicates opportunity for differentiated positioning."


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "deep_market_intelligence",
    "format_competitors_for_matrix",
    "format_country_analysis",
    "get_white_space_summary"
]
