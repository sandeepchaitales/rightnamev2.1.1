"""
═══════════════════════════════════════════════════════════════════════════════
COMPETITIVE INTELLIGENCE MODULE v2
═══════════════════════════════════════════════════════════════════════════════

FUNNEL APPROACH:
1. ONE parallel LLM search → 50 competitors
2. TAG by country
3. CLASSIFY as DIRECT/INDIRECT
4. ASSIGN X,Y coordinates
5. FILTER into multiple matrices
6. DETECT gaps per country

Author: RIGHTNAME.AI Team
Created: July 2025
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

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
# STEP 1: BROAD SEARCH - LLM Knowledge Query (Parallel per country)
# ═══════════════════════════════════════════════════════════════════════════════

async def search_competitors_for_region(
    category: str,
    theme_keywords: List[str],
    region: str  # "GLOBAL" or country name
) -> List[Dict[str, Any]]:
    """
    Use LLM knowledge to get top competitors in a region.
    Returns list of competitor names with basic info.
    """
    logger.info(f"🔍 Searching competitors for {region}...")
    
    theme_str = ", ".join(theme_keywords[:3]) if theme_keywords else category
    
    prompt = f"""List the top 10 most popular {category} creators/brands in {region}.

Category: {category}
Theme/Niche: {theme_str}
Region: {region}

For each competitor, provide:
1. Name (exact brand/channel name)
2. Brief description (what they do)
3. Approximate audience size (Small <100K, Medium 100K-1M, Large 1M+)

Return ONLY JSON array format:
[
  {{"name": "Brand Name", "description": "What they do", "audience_size": "Large"}},
  ...
]

Focus on REAL, EXISTING brands. Include both:
- Big mainstream players in the category
- Niche players closer to the theme

Return ONLY the JSON array, no explanation."""

    if LlmChat and EMERGENT_KEY:
        try:
            chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
            user_msg = UserMessage(text=prompt)
            
            response = await asyncio.wait_for(
                chat.send_message(user_msg),
                timeout=15
            )
            
            response_text = str(response).strip()
            
            # Clean JSON
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            competitors = json.loads(response_text.strip())
            
            # Tag with region
            for comp in competitors:
                comp["regions"] = [region]
                comp["source"] = "llm_knowledge"
            
            logger.info(f"✅ Found {len(competitors)} competitors for {region}")
            return competitors
            
        except Exception as e:
            logger.error(f"❌ Search failed for {region}: {e}")
            return []
    
    return []


async def broad_search(
    category: str,
    theme_keywords: List[str],
    countries: List[str]
) -> List[Dict[str, Any]]:
    """
    STEP 1: Cast wide net - parallel search across all regions.
    Returns ~50 competitors from GLOBAL + all countries.
    """
    logger.info(f"🌍 BROAD SEARCH: Starting for {len(countries)} countries + GLOBAL")
    
    # Always include GLOBAL
    regions = ["GLOBAL"] + countries
    
    # Parallel search for all regions
    tasks = [
        search_competitors_for_region(category, theme_keywords, region)
        for region in regions
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Merge and deduplicate
    all_competitors = []
    seen_names = {}
    
    for i, result in enumerate(results):
        region = regions[i]
        if isinstance(result, list):
            for comp in result:
                name_lower = comp.get("name", "").lower().strip()
                if name_lower:
                    if name_lower in seen_names:
                        # Add region tag to existing
                        seen_names[name_lower]["regions"].append(region)
                    else:
                        seen_names[name_lower] = comp
                        all_competitors.append(comp)
    
    logger.info(f"🌍 BROAD SEARCH: Found {len(all_competitors)} unique competitors")
    return all_competitors


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 & 3: CLASSIFY + ASSIGN COORDINATES
# ═══════════════════════════════════════════════════════════════════════════════

async def classify_and_score_competitors(
    competitors: List[Dict[str, Any]],
    brand_name: str,
    category: str,
    theme_keywords: List[str]
) -> List[Dict[str, Any]]:
    """
    STEP 2 & 3: Classify DIRECT/INDIRECT and assign X,Y coordinates.
    Single LLM call for efficiency.
    """
    logger.info(f"📊 CLASSIFYING {len(competitors)} competitors...")
    
    if not competitors:
        return []
    
    # Build competitor list for prompt
    comp_list = "\n".join([
        f"- {c.get('name', 'Unknown')}: {c.get('description', 'N/A')[:100]}"
        for c in competitors[:30]  # Limit to 30 for prompt size
    ])
    
    theme_str = ", ".join(theme_keywords[:3]) if theme_keywords else "general"
    
    prompt = f"""Analyze these competitors for a brand entering the "{category}" space with theme "{theme_str}".

Brand being evaluated: {brand_name}

COMPETITORS TO ANALYZE:
{comp_list}

For EACH competitor, determine:

1. TYPE:
   - "DIRECT" = Same theme/niche as "{theme_str}" (direct competition)
   - "INDIRECT" = Same category "{category}" but different theme (indirect competition)

2. X-COORDINATE (Price/Accessibility, scale 1-10):
   - 1-3 = FREE (YouTube, free podcast, social media)
   - 4-6 = FREEMIUM (free content + paid courses/membership)
   - 7-10 = PAID (subscription, premium only)

3. Y-COORDINATE (Production Quality, scale 1-10):
   - RULE: Famous brands (1M+ audience) MUST be 8-10
   - 8-10 = Premium production, studio quality, famous
   - 5-7 = Professional, good quality
   - 1-4 = Basic, UGC, emerging

Return JSON array:
[
  {{
    "name": "Competitor Name",
    "type": "DIRECT" or "INDIRECT",
    "x": 3,
    "y": 9,
    "reasoning": "Brief explanation"
  }}
]

IMPORTANT: Famous/large brands MUST have Y >= 8. Return ONLY JSON."""

    if LlmChat and EMERGENT_KEY:
        try:
            chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
            user_msg = UserMessage(text=prompt)
            
            response = await asyncio.wait_for(
                chat.send_message(user_msg),
                timeout=20
            )
            
            response_text = str(response).strip()
            
            # Clean JSON
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            scored = json.loads(response_text.strip())
            
            # Merge scores back with original data (preserve regions)
            scored_map = {s.get("name", "").lower(): s for s in scored}
            
            for comp in competitors:
                name_lower = comp.get("name", "").lower()
                if name_lower in scored_map:
                    score_data = scored_map[name_lower]
                    comp["type"] = score_data.get("type", "INDIRECT")
                    comp["x"] = score_data.get("x", 5)
                    comp["y"] = score_data.get("y", 5)
                    comp["reasoning"] = score_data.get("reasoning", "")
                else:
                    # Default values
                    comp["type"] = "INDIRECT"
                    comp["x"] = 5
                    comp["y"] = 5
                    comp["reasoning"] = "Not classified"
            
            logger.info(f"📊 CLASSIFIED: {len(scored)} competitors scored")
            return competitors
            
        except Exception as e:
            logger.error(f"❌ Classification failed: {e}")
            # Return with defaults
            for comp in competitors:
                comp["type"] = "INDIRECT"
                comp["x"] = 5
                comp["y"] = 5
            return competitors
    
    return competitors


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: POPULATE MATRICES (Filter, no API calls)
# ═══════════════════════════════════════════════════════════════════════════════

def populate_matrix_for_region(
    all_competitors: List[Dict[str, Any]],
    region: str,
    brand_name: str,
    user_position: Dict[str, int]
) -> Dict[str, Any]:
    """
    Filter competitors for a specific region and build matrix.
    No API calls - just filtering.
    """
    # Filter competitors for this region
    region_competitors = [
        c for c in all_competitors
        if region in c.get("regions", []) or region == "GLOBAL"
    ]
    
    # Separate DIRECT and INDIRECT
    direct = [c for c in region_competitors if c.get("type") == "DIRECT"]
    indirect = [c for c in region_competitors if c.get("type") == "INDIRECT"]
    
    # Sort by Y (quality) descending - best first
    direct.sort(key=lambda x: x.get("y", 0), reverse=True)
    indirect.sort(key=lambda x: x.get("y", 0), reverse=True)
    
    # Build matrix slots
    matrix_competitors = []
    
    # Slot 1: Category King (INDIRECT) - biggest player
    if indirect:
        king = indirect[0]
        matrix_competitors.append({
            "name": king.get("name"),
            "x": king.get("x", 5),
            "y": king.get("y", 8),
            "type": "INDIRECT",
            "tier": "CATEGORY_KING",
            "reasoning": king.get("reasoning", "Market leader in category")
        })
    
    # Slot 2: Adjacent Player (INDIRECT)
    if len(indirect) > 1:
        adjacent = indirect[1]
        matrix_competitors.append({
            "name": adjacent.get("name"),
            "x": adjacent.get("x", 5),
            "y": adjacent.get("y", 7),
            "type": "INDIRECT",
            "tier": "ADJACENT",
            "reasoning": adjacent.get("reasoning", "Alternative positioning")
        })
    
    # Slot 3: Direct Competitor 1
    if direct:
        direct1 = direct[0]
        matrix_competitors.append({
            "name": direct1.get("name"),
            "x": direct1.get("x", 5),
            "y": direct1.get("y", 6),
            "type": "DIRECT",
            "tier": "THEME_MATCH",
            "reasoning": direct1.get("reasoning", "Direct theme competitor")
        })
    
    # Slot 4: Direct Competitor 2 (or GAP)
    if len(direct) > 1:
        direct2 = direct[1]
        matrix_competitors.append({
            "name": direct2.get("name"),
            "x": direct2.get("x", 5),
            "y": direct2.get("y", 5),
            "type": "DIRECT",
            "tier": "DIRECT_LOCAL",
            "reasoning": direct2.get("reasoning", "Direct competitor")
        })
    
    # Gap analysis
    direct_count = len(direct)
    gap_detected = direct_count == 0
    local_direct_count = len([d for d in direct if region in d.get("regions", [])])
    
    return {
        "region": region,
        "competitors": matrix_competitors,
        "user_position": {
            "x": user_position.get("x", 5),
            "y": user_position.get("y", 7),
            "quadrant": _get_quadrant(user_position.get("x", 5), user_position.get("y", 7))
        },
        "gap_analysis": {
            "direct_count": direct_count,
            "indirect_count": len(indirect),
            "local_direct_count": local_direct_count,
            "gap_detected": gap_detected or local_direct_count == 0,
            "gap_description": f"No dedicated theme-specific competitor in {region}" if (gap_detected or local_direct_count == 0) else f"{local_direct_count} direct competitors in {region}"
        },
        "all_direct": [{"name": d.get("name"), "x": d.get("x"), "y": d.get("y")} for d in direct[:5]],
        "all_indirect": [{"name": i.get("name"), "x": i.get("x"), "y": i.get("y")} for i in indirect[:5]]
    }


def _get_quadrant(x: float, y: float) -> str:
    """Determine quadrant based on x,y coordinates."""
    if x >= 6 and y >= 6:
        return "Premium Quality"
    elif x < 6 and y >= 6:
        return "Accessible Premium"
    elif x >= 6 and y < 6:
        return "Value Premium"
    else:
        return "Mass Market"


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: WHITE SPACE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_white_space_analysis(
    matrices: Dict[str, Any],
    brand_name: str,
    category: str,
    theme_keywords: List[str],
    countries: List[str]
) -> Dict[str, Any]:
    """
    Generate white space analysis based on gap detection across all matrices.
    """
    logger.info("🔍 Generating white space analysis...")
    
    # Collect gap info from all matrices
    global_gaps = matrices.get("GLOBAL", {}).get("gap_analysis", {})
    country_gaps = {}
    
    for country in countries:
        country_data = matrices.get(country, {})
        country_gaps[country] = country_data.get("gap_analysis", {})
    
    # Build analysis prompt
    gap_summary = f"GLOBAL: {global_gaps.get('direct_count', 0)} direct competitors\n"
    for country, gap in country_gaps.items():
        gap_summary += f"{country}: {gap.get('local_direct_count', 0)} local direct competitors\n"
    
    theme_str = ", ".join(theme_keywords[:3]) if theme_keywords else category
    
    prompt = f"""Based on competitive analysis for "{brand_name}" in "{category}" (theme: {theme_str}):

GAP ANALYSIS:
{gap_summary}

Countries analyzed: {', '.join(countries)}

Provide WHITE SPACE ANALYSIS:

1. GLOBAL OPPORTUNITY: Is there a gap globally for this theme?
2. COUNTRY-SPECIFIC OPPORTUNITIES: Which countries have NO direct competitors?
3. POSITIONING RECOMMENDATION: Where should the brand position?
4. UNMET NEEDS: What specific content/format gap exists?

Return JSON:
{{
  "global_white_space": "Analysis of global opportunity",
  "country_opportunities": {{
    "India": "Specific opportunity or 'Market has competition'",
    "USA": "..."
  }},
  "positioning_recommendation": "Specific positioning advice",
  "unmet_needs": "What's missing in the market",
  "overall_verdict": "GREEN (big gap) / YELLOW (some gap) / RED (saturated)"
}}

Return ONLY JSON."""

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
            
            return json.loads(response_text.strip())
            
        except Exception as e:
            logger.error(f"❌ White space analysis failed: {e}")
    
    # Fallback
    return {
        "global_white_space": "Analysis unavailable",
        "country_opportunities": {c: "Manual analysis recommended" for c in countries},
        "positioning_recommendation": "Differentiated positioning recommended",
        "unmet_needs": "Further research needed",
        "overall_verdict": "YELLOW"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FUNCTION: COMPETITIVE INTELLIGENCE v2
# ═══════════════════════════════════════════════════════════════════════════════

async def competitive_intelligence_v2(
    brand_name: str,
    category: str,
    positioning: str,
    countries: List[str],
    understanding: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Main entry point for Competitive Intelligence v2.
    
    FUNNEL APPROACH:
    1. Broad search (50 candidates)
    2. Tag by country
    3. Classify DIRECT/INDIRECT
    4. Assign X,Y coordinates
    5. Filter into matrices
    6. Detect gaps
    
    Returns: Global matrix + Country-specific matrices + White space analysis
    """
    import time
    start_time = time.time()
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  🎯 COMPETITIVE INTELLIGENCE v2                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Brand: {brand_name:<55}  ║
║  Category: {category:<53}  ║
║  Countries: {', '.join(countries):<52}  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Extract theme keywords from understanding
    theme_keywords = []
    if understanding:
        comp_context = understanding.get("competitive_context", {})
        theme_keywords = comp_context.get("direct_competitor_search_queries", [])[:5]
        
        # Add from brand analysis
        brand_analysis = understanding.get("brand_analysis", {})
        combined_meaning = brand_analysis.get("combined_meaning", "")
        if combined_meaning:
            theme_keywords.insert(0, combined_meaning)
    
    if not theme_keywords:
        theme_keywords = [category]
    
    logger.info(f"🎯 Theme Keywords: {theme_keywords[:3]}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 1: BROAD SEARCH (Parallel LLM queries)
    # ═══════════════════════════════════════════════════════════════════════════
    all_competitors = await broad_search(category, theme_keywords, countries)
    
    if not all_competitors:
        logger.warning("⚠️ No competitors found in broad search")
        return _empty_result(brand_name, countries)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 2 & 3: CLASSIFY + SCORE (Single LLM call)
    # ═══════════════════════════════════════════════════════════════════════════
    scored_competitors = await classify_and_score_competitors(
        all_competitors, brand_name, category, theme_keywords
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 4: POPULATE MATRICES (No API calls - just filtering)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # User brand position based on positioning
    positioning_map = {
        "Budget": {"x": 2, "y": 5},
        "Mass": {"x": 3, "y": 6},
        "Mid-Range": {"x": 5, "y": 6},
        "Premium": {"x": 7, "y": 8},
        "Luxury": {"x": 9, "y": 9}
    }
    user_position = positioning_map.get(positioning, {"x": 5, "y": 7})
    
    # Build all matrices
    matrices = {}
    
    # Global matrix
    matrices["GLOBAL"] = populate_matrix_for_region(
        scored_competitors, "GLOBAL", brand_name, user_position
    )
    
    # Country-specific matrices
    for country in countries:
        matrices[country] = populate_matrix_for_region(
            scored_competitors, country, brand_name, user_position
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 5: WHITE SPACE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    white_space = await generate_white_space_analysis(
        matrices, brand_name, category, theme_keywords, countries
    )
    
    processing_time = time.time() - start_time
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BUILD FINAL RESULT
    # ═══════════════════════════════════════════════════════════════════════════
    
    result = {
        "global_matrix": _format_matrix_for_output(matrices["GLOBAL"], brand_name, user_position),
        "country_analysis": {
            country: _format_matrix_for_output(matrices[country], brand_name, user_position)
            for country in countries
        },
        "white_space_analysis": white_space,
        "all_competitors": [
            {
                "name": c.get("name"),
                "type": c.get("type"),
                "x": c.get("x"),
                "y": c.get("y"),
                "regions": c.get("regions", [])
            }
            for c in scored_competitors[:20]
        ],
        "meta": {
            "total_competitors_found": len(scored_competitors),
            "countries_analyzed": len(countries) + 1,  # +1 for GLOBAL
            "processing_time_seconds": round(processing_time, 2),
            "theme_keywords": theme_keywords[:3],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    }
    
    # Log summary
    global_direct = matrices["GLOBAL"]["gap_analysis"]["direct_count"]
    logger.info(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  🎯 COMPETITIVE INTELLIGENCE v2 COMPLETE                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Total Competitors: {len(scored_competitors):<43}  ║
║  Global Direct Competitors: {global_direct:<36}  ║
║  Countries Analyzed: {len(countries) + 1:<43}  ║
║  Processing Time: {round(processing_time, 2)}s{' ' * (45 - len(str(round(processing_time, 2))))}  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    return result


def _format_matrix_for_output(
    matrix_data: Dict[str, Any],
    brand_name: str,
    user_position: Dict[str, int]
) -> Dict[str, Any]:
    """Format matrix for API output with detailed competitor insights."""
    competitors = matrix_data.get("competitors", [])
    
    # Format competitors with scaled coordinates (1-10 → 10-100)
    formatted_competitors = []
    direct_competitors = []
    indirect_competitors = []
    
    for comp in competitors:
        comp_data = {
            "name": comp.get("name", "Unknown"),
            "x_coordinate": float(comp.get("x", 5)) * 10,
            "y_coordinate": float(comp.get("y", 5)) * 10,
            "quadrant": comp.get("tier", "Competitor"),
            "type": comp.get("type", "INDIRECT"),
            "reasoning": comp.get("reasoning", "")
        }
        formatted_competitors.append(comp_data)
        
        # Categorize for detailed analysis
        if comp.get("type") == "DIRECT":
            direct_competitors.append(comp.get("name", "Unknown"))
        else:
            indirect_competitors.append(comp.get("name", "Unknown"))
    
    gap = matrix_data.get("gap_analysis", {})
    
    # Build detailed strategic advantage text
    direct_count = len(direct_competitors)
    indirect_count = len(indirect_competitors)
    total = direct_count + indirect_count
    
    # Create competitor list strings
    direct_list = ", ".join(direct_competitors[:6]) if direct_competitors else "None identified"
    indirect_list = ", ".join(indirect_competitors[:6]) if indirect_competitors else "None identified"
    
    # Generate strategic advantage with competitor names
    strategic_advantage_parts = []
    
    if direct_count == 0:
        strategic_advantage_parts.append(f"🟢 **BLUE OCEAN OPPORTUNITY**: No direct competitors found in this specific segment. This represents a significant first-mover advantage.")
    elif direct_count <= 3:
        strategic_advantage_parts.append(f"🟡 **MODERATE COMPETITION**: {direct_count} direct competitors identified ({direct_list}). Market entry is viable with differentiation.")
    else:
        strategic_advantage_parts.append(f"🔴 **COMPETITIVE MARKET**: {direct_count} direct competitors ({direct_list}). Strong differentiation strategy required.")
    
    if indirect_count > 0:
        strategic_advantage_parts.append(f"\n\n**Indirect Competitors ({indirect_count})**: {indirect_list}")
    
    # Generate market entry recommendation
    if direct_count == 0 and indirect_count <= 2:
        market_entry = "🚀 **GO** - Excellent timing for market entry. Limited competition allows for brand building and market share capture."
    elif direct_count <= 2:
        market_entry = f"✅ **PROCEED WITH STRATEGY** - Viable market entry. Position against: {direct_list}. Focus on unique value proposition."
    elif direct_count <= 5:
        market_entry = f"⚠️ **PROCEED WITH CAUTION** - Competitive market with {direct_count} direct players. Differentiation required in: pricing, features, or niche targeting."
    else:
        market_entry = f"🛑 **HIGH COMPETITION** - Saturated market with {direct_count}+ direct competitors. Consider niche positioning or geographic focus."
    
    return {
        "competitors": formatted_competitors,
        "user_brand_position": {
            "x_coordinate": float(user_position.get("x", 5)) * 10,
            "y_coordinate": float(user_position.get("y", 7)) * 10,
            "quadrant": _get_quadrant(user_position.get("x", 5), user_position.get("y", 7)),
            "brand_name": brand_name
        },
        "x_axis_label": "Price: Budget → Premium",
        "y_axis_label": "Quality: Basic → High Production",
        "gap_analysis": {
            "direct_count": direct_count,
            "indirect_count": indirect_count,
            "total_competitors": total,
            "direct_competitors": direct_list,
            "indirect_competitors": indirect_list,
            "gap_detected": gap.get("gap_detected", direct_count == 0),
            "gap_description": gap.get("gap_description", "")
        },
        "white_space_analysis": gap.get("gap_description", "") or f"{'Significant opportunity - no direct competition' if direct_count == 0 else f'{direct_count} direct competitors exist. Look for positioning gaps.'}",
        "strategic_advantage": "\n".join(strategic_advantage_parts),
        "market_entry_recommendation": market_entry
    }
        "y_axis_label": "Quality: Basic → High Production",
        "gap_analysis": {
            "direct_count": gap.get("direct_count", 0),
            "indirect_count": gap.get("indirect_count", 0),
            "gap_detected": gap.get("gap_detected", False),
            "gap_description": gap.get("gap_description", "")
        },
        "white_space_analysis": gap.get("gap_description", "Analysis pending"),
        "strategic_advantage": f"Found {len(formatted_competitors)} competitors via Competitive Intelligence v2"
    }


def _empty_result(brand_name: str, countries: List[str]) -> Dict[str, Any]:
    """Return empty result structure when search fails."""
    return {
        "global_matrix": {
            "competitors": [],
            "user_brand_position": {"x_coordinate": 50, "y_coordinate": 70, "quadrant": "Target"},
            "x_axis_label": "Price: Budget → Premium",
            "y_axis_label": "Quality: Basic → High Production",
            "gap_analysis": {"direct_count": 0, "gap_detected": True},
            "white_space_analysis": "Competitor search unavailable",
            "strategic_advantage": "Manual research recommended"
        },
        "country_analysis": {
            country: {
                "competitors": [],
                "user_brand_position": {"x_coordinate": 50, "y_coordinate": 70},
                "gap_analysis": {"direct_count": 0, "gap_detected": True},
                "white_space_analysis": f"Competitor search unavailable for {country}"
            }
            for country in countries
        },
        "white_space_analysis": {
            "global_white_space": "Analysis unavailable",
            "overall_verdict": "YELLOW"
        },
        "all_competitors": [],
        "meta": {
            "total_competitors_found": 0,
            "error": "Search failed"
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTION FOR SERVER INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def get_white_space_summary_v2(intel_result: Dict[str, Any]) -> str:
    """Get formatted white space summary from v2 result."""
    ws = intel_result.get("white_space_analysis", {})
    
    parts = []
    
    global_ws = ws.get("global_white_space", "")
    if global_ws:
        parts.append(f"**Global:** {global_ws}")
    
    country_opps = ws.get("country_opportunities", {})
    for country, opp in country_opps.items():
        if opp and opp != "Manual analysis recommended":
            parts.append(f"**{country}:** {opp}")
    
    unmet = ws.get("unmet_needs", "")
    if unmet:
        parts.append(f"**Unmet Needs:** {unmet}")
    
    if parts:
        return "\n\n".join(parts)
    
    return "Market opportunity analysis pending."


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "competitive_intelligence_v2",
    "get_white_space_summary_v2"
]
