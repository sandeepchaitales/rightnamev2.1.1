"""
Market Intelligence Research Module
===================================
LLM-First approach to market research using real-time web search.
Prioritizes ACCURACY over speed through actual data research.

Architecture:
1. LLM generates strategic search queries for category + country
2. Web search retrieves REAL competitor data, market trends
3. LLM synthesizes findings into structured intelligence
4. Hardcoded data serves as FALLBACK only if research fails

This replaces hardcoded competitor/white-space data with dynamic research.
"""

import logging
import asyncio
import json
import re
import os
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Emergent LLM
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
except ImportError:
    logger.error("emergentintegrations not found")
    LlmChat = None

EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')


@dataclass
class CompetitorData:
    """Real competitor discovered through research"""
    name: str
    x_coordinate: int  # Market position (0-100)
    y_coordinate: int  # Market position (0-100)
    quadrant: str  # e.g., "Premium Luxury", "Budget Mass"
    market_share: Optional[str] = None
    founded: Optional[str] = None
    headquarters: Optional[str] = None
    key_strength: Optional[str] = None
    source: Optional[str] = None


@dataclass
class MarketIntelligence:
    """Complete market intelligence for a country + category"""
    country: str
    country_flag: str
    category: str
    research_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Market Overview
    market_size: Optional[str] = None
    growth_rate: Optional[str] = None
    key_trends: List[str] = field(default_factory=list)
    
    # Competitors (REAL names from research)
    competitors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Positioning
    x_axis_label: str = "Price: Budget → Premium"
    y_axis_label: str = "Positioning: Traditional → Modern"
    user_brand_position: Dict[str, Any] = field(default_factory=dict)
    
    # Strategic Analysis
    white_space_analysis: str = ""
    strategic_advantage: str = ""
    market_entry_recommendation: str = ""
    
    # Research metadata
    research_quality: str = "HIGH"  # HIGH, MEDIUM, LOW, FALLBACK
    sources_used: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CulturalIntelligence:
    """Cultural analysis with sacred/royal name detection"""
    country: str
    country_flag: str
    brand_name: str
    research_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Cultural resonance
    cultural_resonance_score: float = 7.0
    linguistic_check: str = "PASS"
    
    # Cultural notes (from research)
    cultural_notes: str = ""
    
    # Sacred/Royal name detection
    sacred_name_detected: bool = False
    detected_terms: List[str] = field(default_factory=list)
    cultural_risk_warning: Optional[str] = None
    legal_implications: Optional[str] = None
    
    # Research metadata
    research_quality: str = "HIGH"
    sources_used: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============ WEB SEARCH FUNCTIONS ============

async def web_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Perform web search using DuckDuckGo (free, no API key needed)"""
    try:
        from ddgs import DDGS
        
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=num_results):
                results.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "href": r.get("href", "")
                })
        
        logger.info(f"🔍 Web search for '{query[:50]}...' returned {len(results)} results")
        return results
    except ImportError:
        # Try older package name
        try:
            from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append({
                        "title": r.get("title", ""),
                        "body": r.get("body", ""),
                        "href": r.get("href", "")
                    })
            
            logger.info(f"🔍 Web search for '{query[:50]}...' returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return []


async def search_competitors(category: str, country: str, positioning: str = "Mid-Range") -> str:
    """
    Search for real competitors in a category + country + positioning segment.
    
    The MAGIC: Including positioning in search queries returns RELEVANT competitors
    for the user's target segment, not a mix of all price tiers.
    
    Example:
    - "Budget Hotel Chain India" → OYO, Treebo, FabHotels
    - "Mid-Range Hotel Chain India" → Lemon Tree, Ginger, Keys Hotels  
    - "Premium Hotel Chain India" → Taj, ITC, Oberoi
    """
    # Normalize positioning for search
    positioning_lower = positioning.lower() if positioning else "mid-range"
    
    # Map positioning to search-friendly terms
    positioning_terms = {
        "budget": "budget affordable low-cost",
        "mid-range": "mid-range mid-tier moderate",
        "premium": "premium upscale high-end",
        "luxury": "luxury ultra-luxury five-star",
        "mass": "mass market popular mainstream",
        "ultra-premium": "ultra-luxury exclusive elite"
    }
    
    search_positioning = positioning_terms.get(positioning_lower, positioning_lower)
    primary_positioning = search_positioning.split()[0]  # Get first term
    
    # IMPROVED QUERIES: [Positioning] [Category] [Country]
    queries = [
        f"{primary_positioning} {category} in {country} top brands 2024",
        f"best {primary_positioning} {category} {country} market leaders",
        f"{category} {country} {primary_positioning} segment competitors",
        f"top local {category} brands {country} {primary_positioning}"  # Emphasize LOCAL
    ]
    
    logger.info(f"🎯 POSITIONING-AWARE SEARCH: '{primary_positioning} {category}' in {country}")
    
    all_results = []
    for query in queries:
        results = await web_search(query, num_results=5)
        all_results.extend(results)
    
    # Format results for LLM
    formatted = f"WEB SEARCH RESULTS FOR {positioning.upper()} {category.upper()} COMPETITORS IN {country.upper()}:\n\n"
    formatted += f"USER'S TARGET SEGMENT: {positioning} positioning\n"
    formatted += f"SEARCH FOCUS: Find LOCAL {country} brands in the {positioning} segment, NOT global chains\n\n"
    
    for i, r in enumerate(all_results[:15], 1):
        formatted += f"{i}. {r['title']}\n   {r['body'][:300]}...\n   Source: {r['href']}\n\n"
    
    return formatted


async def search_market_intelligence(category: str, country: str) -> str:
    """Search for market size, trends, white space opportunities"""
    queries = [
        f"{category} market size {country} 2024 billion",
        f"{category} industry trends {country} growth opportunities",
        f"{category} market gaps {country} underserved segments"
    ]
    
    all_results = []
    for query in queries:
        results = await web_search(query, num_results=4)
        all_results.extend(results)
    
    formatted = f"MARKET INTELLIGENCE FOR {category.upper()} IN {country.upper()}:\n\n"
    for i, r in enumerate(all_results[:12], 1):
        formatted += f"{i}. {r['title']}\n   {r['body'][:300]}...\n   Source: {r['href']}\n\n"
    
    return formatted


async def search_cultural_sensitivity(brand_name: str, country: str) -> str:
    """Search for cultural/linguistic issues with brand name in country"""
    queries = [
        f'"{brand_name}" meaning in {country} language',
        f"{brand_name} similar words {country} slang negative connotation",
        f"royal sacred religious names {country} trademark law"
    ]
    
    all_results = []
    for query in queries:
        results = await web_search(query, num_results=3)
        all_results.extend(results)
    
    formatted = f"CULTURAL ANALYSIS FOR '{brand_name}' IN {country.upper()}:\n\n"
    for i, r in enumerate(all_results[:9], 1):
        formatted += f"{i}. {r['title']}\n   {r['body'][:300]}...\n   Source: {r['href']}\n\n"
    
    return formatted


# ============ LLM ANALYSIS FUNCTIONS ============

COMPETITOR_ANALYSIS_PROMPT = """You are a market research analyst specializing in LOCAL market intelligence.

CATEGORY: {category}
COUNTRY: {country}
POSITIONING SEGMENT: {positioning}
BRAND BEING EVALUATED: {brand_name}

WEB SEARCH RESULTS:
{search_results}

YOUR TASK: Extract REAL LOCAL competitors from the search results that match the user's positioning segment.

⚠️ CRITICAL RULES FOR COMPETITOR SELECTION:
1. **PRIORITIZE LOCAL/DOMESTIC BRANDS** that originated from {country}
2. **MATCH THE POSITIONING**: User wants {positioning} segment - return competitors in THAT price tier
3. **AVOID GLOBAL CHAINS** unless they are specifically dominant in that country's segment
4. For India: Prioritize Taj, OYO, ITC, Lemon Tree, Ginger over Marriott, Hilton
5. For Thailand: Prioritize Dusit, Centara, Minor Hotels, Onyx over international chains
6. For USA: Mix of US-origin brands (Marriott, Hilton are US companies) + local boutiques

POSITIONING-SEGMENT MAPPING:
| Positioning | Price Tier | Example Brands (Hotels in India) |
|-------------|------------|----------------------------------|
| Budget | ₹1,000-3,000/night | OYO, Treebo, FabHotels, Zostel |
| Mid-Range | ₹3,000-8,000/night | Lemon Tree, Ginger, Keys Hotels |
| Premium | ₹8,000-20,000/night | Taj, ITC, Oberoi, Leela |
| Luxury | ₹20,000+/night | Taj Palace, Oberoi Udaivilas, Aman |

Return a JSON object with this EXACT structure:
{{
    "competitors": [
        {{
            "name": "LOCAL brand name from {country} matching {positioning} segment",
            "x_coordinate": 65,  // 0-100 scale based on price (0=budget, 100=luxury)
            "y_coordinate": 70,  // 0-100 scale based on experience (0=basic, 100=premium experience)
            "quadrant": "Brief positioning (e.g., 'Local Mid-Range Leader')",
            "market_share": "X%" or "Leading" or "Challenger" if mentioned,
            "key_strength": "One-line strength",
            "origin": "LOCAL" or "INTERNATIONAL"
        }}
    ],
    "market_size": "Market size in LOCAL currency (₹ for India, ฿ for Thailand, $ for USA)",
    "growth_rate": "Annual growth rate if mentioned",
    "x_axis_label": "Price: [local currency] Budget → [local currency] Premium",
    "y_axis_label": "Experience: Basic/Standard → Boutique/Unique",
    "key_trends": ["Trend 1", "Trend 2", "Trend 3"]
}}

VALIDATION CHECKLIST:
✅ At least 2-3 competitors should be LOCAL brands from {country}
✅ All competitors should be in the {positioning} segment (not mixed tiers)
✅ Coordinates should reflect the {positioning} tier (Budget=20-40, Mid=40-60, Premium=60-80, Luxury=80-100)

Return ONLY valid JSON, no explanations."""


WHITE_SPACE_ANALYSIS_PROMPT = """You are a strategic consultant analyzing market opportunities.

CATEGORY: {category}
COUNTRY: {country}
POSITIONING SEGMENT: {positioning}
BRAND BEING EVALUATED: {brand_name}

COMPETITOR DATA:
{competitor_data}

MARKET RESEARCH:
{market_research}

YOUR TASK: Provide strategic analysis based on REAL data from the research.

Return a JSON object with this EXACT structure:
{{
    "white_space_analysis": "2-3 sentences identifying SPECIFIC gaps in the market based on the competitor landscape. Mention specific price points, segments, or positioning opportunities. Reference actual competitors.",
    
    "strategic_advantage": "2-3 sentences explaining how '{brand_name}' can leverage these gaps. Be specific about channels, positioning, and competitive differentiation.",
    
    "market_entry_recommendation": "3-phase market entry strategy with SPECIFIC recommendations for {country}. Include: Phase 1 (validation), Phase 2 (scale), Phase 3 (expansion). Mention specific platforms, retailers, or channels relevant to {country}.",
    
    "user_brand_position": {{
        "x_coordinate": 65,  // Where should the brand position on price axis
        "y_coordinate": 72,  // Where should the brand position on other axis
        "quadrant": "Recommended positioning (e.g., 'Accessible Premium')",
        "rationale": "Why this positioning maximizes opportunity"
    }}
}}

RULES:
1. Be SPECIFIC - use actual company names, platforms, price points
2. Tailor recommendations to {country} market specifically
3. Reference the actual competitors found in research
4. No generic advice - every recommendation should be actionable

Return ONLY valid JSON, no explanations."""


CULTURAL_ANALYSIS_PROMPT = """You are a cultural and linguistic expert analyzing brand names for international markets.

BRAND NAME: {brand_name}
COUNTRY: {country}

WEB SEARCH RESULTS:
{search_results}

YOUR TASK: Analyze if this brand name has any cultural, linguistic, or legal issues in {country}.

CHECK FOR:
1. **Sacred/Royal Names**: Does the brand contain or sound like names of:
   - Royalty (kings, queens, royal families)
   - Religious figures (deities, prophets, saints)
   - Sacred places or concepts
   
2. **Linguistic Issues**:
   - Negative meanings in local language
   - Sounds similar to offensive words
   - Difficult pronunciation
   
3. **Legal Restrictions**:
   - Protected names (royal, religious)
   - Trademark restrictions on certain terms
   - Cultural appropriation concerns

Return a JSON object with this EXACT structure:
{{
    "cultural_resonance_score": 7.5,  // 1-10 scale (10 = excellent cultural fit, 1 = major issues)
    "linguistic_check": "PASS" or "CAUTION" or "FAIL",
    
    "sacred_name_detected": true/false,
    "detected_terms": ["term1", "term2"],  // Sacred/royal terms found, empty if none
    
    "cultural_notes": "Detailed analysis of cultural fit. If sacred name detected, explain the specific concern (e.g., 'Rama refers to Thai Kings Rama I-X of the Chakri Dynasty'). Include any pronunciation issues, local language meanings, or cultural associations.",
    
    "cultural_risk_warning": "If sacred_name_detected is true, provide specific warning about legal/social risks. Otherwise null.",
    
    "legal_implications": "Any legal issues (e.g., lèse-majesté laws, blasphemy laws, trademark restrictions). Null if none."
}}

COUNTRY-SPECIFIC KNOWLEDGE TO APPLY:
- THAILAND: 'Rama' is the title of Thai Kings (Rama I through Rama X). Lèse-majesté laws (Section 112) prohibit insulting royalty.
- INDIA: Hindu deity names (Rama, Krishna, Shiva, Ganesh) may cause commercial concerns
- UAE/SAUDI: Islamic sacred terms (Allah, Muhammad, Mecca) are legally protected
- JAPAN: Imperial terms (Tenno, Chrysanthemum) are protected
- CHINA: Political figures and Tibetan/religious terms are restricted

Return ONLY valid JSON, no explanations."""


async def llm_analyze_competitors(
    category: str, 
    country: str, 
    brand_name: str,
    search_results: str,
    positioning: str = "Mid-Range"
) -> Dict[str, Any]:
    """Use LLM to analyze search results and extract competitor data for specific positioning"""
    if not LlmChat or not EMERGENT_KEY:
        logger.warning("LLM not available for competitor analysis")
        return None
    
    try:
        prompt = COMPETITOR_ANALYSIS_PROMPT.format(
            category=category,
            country=country,
            brand_name=brand_name,
            search_results=search_results,
            positioning=positioning
        )
        
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            model="openai/gpt-4o-mini"  # Fast and cost-effective
        )
        
        response = await asyncio.wait_for(
            chat.send_message_async(prompt),
            timeout=30
        )
        
        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        data = json.loads(response_text)
        logger.info(f"✅ LLM extracted {len(data.get('competitors', []))} {positioning} competitors for {country}")
        return data
        
    except asyncio.TimeoutError:
        logger.error("LLM competitor analysis timed out")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return None
    except Exception as e:
        logger.error(f"LLM competitor analysis failed: {e}")
        return None


async def llm_analyze_white_space(
    category: str,
    country: str,
    brand_name: str,
    competitor_data: str,
    market_research: str,
    positioning: str = "Mid-Range"
) -> Dict[str, Any]:
    """Use LLM to generate strategic white space analysis for specific positioning"""
    if not LlmChat or not EMERGENT_KEY:
        return None
    
    try:
        prompt = WHITE_SPACE_ANALYSIS_PROMPT.format(
            category=category,
            country=country,
            brand_name=brand_name,
            competitor_data=competitor_data,
            market_research=market_research,
            positioning=positioning
        )
        
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            model="openai/gpt-4o-mini"
        )
        
        response = await asyncio.wait_for(
            chat.send_message_async(prompt),
            timeout=30
        )
        
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        data = json.loads(response_text)
        logger.info(f"✅ LLM generated {positioning} white space analysis for {country}")
        return data
        
    except Exception as e:
        logger.error(f"LLM white space analysis failed: {e}")
        return None


async def llm_analyze_cultural(
    brand_name: str,
    country: str,
    search_results: str
) -> Dict[str, Any]:
    """Use LLM to analyze cultural sensitivity"""
    if not LlmChat or not EMERGENT_KEY:
        return None
    
    try:
        prompt = CULTURAL_ANALYSIS_PROMPT.format(
            brand_name=brand_name,
            country=country,
            search_results=search_results
        )
        
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            model="openai/gpt-4o-mini"
        )
        
        response = await asyncio.wait_for(
            chat.send_message_async(prompt),
            timeout=30
        )
        
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        data = json.loads(response_text)
        logger.info(f"✅ LLM analyzed cultural sensitivity for '{brand_name}' in {country}")
        return data
        
    except Exception as e:
        logger.error(f"LLM cultural analysis failed: {e}")
        return None


# ============ MAIN RESEARCH FUNCTIONS ============

async def research_country_market(
    category: str,
    country: str,
    brand_name: str,
    fallback_data: Dict[str, Any] = None,
    positioning: str = "Mid-Range"
) -> MarketIntelligence:
    """
    Research real market intelligence for a category + country + positioning combination.
    Uses LLM + web search for accuracy, with fallback data if research fails.
    
    KEY IMPROVEMENT: Includes positioning in search queries to get segment-specific competitors.
    Example: "Mid-Range Hotel Chain India" returns Lemon Tree, Ginger, Keys
    Instead of: "Hotel Chain India" which returns mixed segments (OYO to Taj)
    """
    country_flags = {
        "India": "🇮🇳", "USA": "🇺🇸", "United States": "🇺🇸", "UK": "🇬🇧", 
        "Thailand": "🇹🇭", "Singapore": "🇸🇬", "UAE": "🇦🇪", "Japan": "🇯🇵",
        "Germany": "🇩🇪", "France": "🇫🇷", "China": "🇨🇳", "Australia": "🇦🇺",
        "Canada": "🇨🇦", "Brazil": "🇧🇷"
    }
    
    logger.info(f"🔬 Starting {positioning} market research for {category} in {country}...")
    
    intelligence = MarketIntelligence(
        country=country,
        country_flag=country_flags.get(country, "🌍"),
        category=category
    )
    
    try:
        # Step 1: Web search for competitors WITH POSITIONING
        competitor_search = await search_competitors(category, country, positioning)
        
        # Step 2: Web search for market intelligence
        market_search = await search_market_intelligence(category, country)
        
        # Step 3: LLM analysis of competitors WITH POSITIONING
        competitor_data = await llm_analyze_competitors(
            category, country, brand_name, competitor_search, positioning
        )
        
        if competitor_data and competitor_data.get("competitors"):
            intelligence.competitors = competitor_data["competitors"]
            intelligence.market_size = competitor_data.get("market_size")
            intelligence.growth_rate = competitor_data.get("growth_rate")
            intelligence.x_axis_label = competitor_data.get("x_axis_label", intelligence.x_axis_label)
            intelligence.y_axis_label = competitor_data.get("y_axis_label", intelligence.y_axis_label)
            intelligence.key_trends = competitor_data.get("key_trends", [])
            intelligence.sources_used.append(f"Web Search + LLM Analysis ({positioning} segment)")
            
            # Step 4: LLM white space analysis WITH POSITIONING
            white_space_data = await llm_analyze_white_space(
                category, country, brand_name,
                json.dumps(competitor_data, indent=2),
                market_search,
                positioning
            )
            
            if white_space_data:
                intelligence.white_space_analysis = white_space_data.get("white_space_analysis", "")
                intelligence.strategic_advantage = white_space_data.get("strategic_advantage", "")
                intelligence.market_entry_recommendation = white_space_data.get("market_entry_recommendation", "")
                intelligence.user_brand_position = white_space_data.get("user_brand_position", {
                    "x_coordinate": 65,
                    "y_coordinate": 72,
                    "quadrant": f"{positioning} Segment",
                    "rationale": f"Optimal {positioning} positioning for {brand_name} in {country}"
                })
                intelligence.research_quality = "HIGH"
            else:
                intelligence.research_quality = "MEDIUM"
                _apply_fallback_strategy(intelligence, fallback_data, brand_name)
        else:
            # Research failed, use fallback
            logger.warning(f"⚠️ Research failed for {country}, using fallback data")
            intelligence.research_quality = "FALLBACK"
            _apply_fallback_data(intelligence, fallback_data, brand_name)
            
    except Exception as e:
        logger.error(f"Market research error for {country}: {e}")
        intelligence.research_quality = "FALLBACK"
        _apply_fallback_data(intelligence, fallback_data, brand_name)
    
    return intelligence


def _apply_fallback_strategy(
    intelligence: MarketIntelligence,
    fallback_data: Dict[str, Any],
    brand_name: str
):
    """Apply fallback strategic analysis when LLM white space fails"""
    if fallback_data:
        intelligence.white_space_analysis = fallback_data.get("white_space", 
            f"Market analysis indicates opportunities in the {intelligence.category} sector.")
        intelligence.strategic_advantage = fallback_data.get("strategic_advantage",
            f"As a new entrant, {brand_name} can leverage digital-first strategies.")
        intelligence.market_entry_recommendation = fallback_data.get("entry_recommendation",
            "Phased entry recommended: Phase 1 (E-commerce), Phase 2 (Retail), Phase 3 (Scale).")
        intelligence.user_brand_position = {
            "x_coordinate": fallback_data.get("user_position", {}).get("x", 65),
            "y_coordinate": fallback_data.get("user_position", {}).get("y", 72),
            "quadrant": fallback_data.get("user_position", {}).get("quadrant", "Accessible Premium"),
            "rationale": f"Positioning for {brand_name} in {intelligence.country}"
        }


def _apply_fallback_data(
    intelligence: MarketIntelligence,
    fallback_data: Dict[str, Any],
    brand_name: str
):
    """Apply full fallback data when research fails completely"""
    if fallback_data:
        intelligence.competitors = fallback_data.get("competitors", [])
        intelligence.x_axis_label = fallback_data.get("axis_x", intelligence.x_axis_label)
        intelligence.y_axis_label = fallback_data.get("axis_y", intelligence.y_axis_label)
        _apply_fallback_strategy(intelligence, fallback_data, brand_name)
    else:
        # Ultimate fallback - generic data
        intelligence.competitors = [
            {"name": "Market Leader", "x_coordinate": 75, "y_coordinate": 70, "quadrant": "Premium Established"},
            {"name": "Challenger Brand", "x_coordinate": 55, "y_coordinate": 65, "quadrant": "Value Innovator"},
        ]
        intelligence.white_space_analysis = f"Market research pending for {intelligence.category} in {intelligence.country}."
        intelligence.strategic_advantage = f"{brand_name} can differentiate through innovation and customer focus."
        intelligence.market_entry_recommendation = "Recommend phased market entry with digital-first strategy."
        intelligence.user_brand_position = {
            "x_coordinate": 65, "y_coordinate": 72, 
            "quadrant": "Accessible Premium",
            "rationale": "Default positioning"
        }


async def research_cultural_sensitivity(
    brand_name: str,
    country: str,
    fallback_data: Dict[str, Any] = None
) -> CulturalIntelligence:
    """
    Research cultural sensitivity for a brand name in a specific country.
    Uses LLM + web search for accuracy, with fallback if research fails.
    """
    country_flags = {
        "India": "🇮🇳", "USA": "🇺🇸", "Thailand": "🇹🇭", "UK": "🇬🇧",
        "Singapore": "🇸🇬", "UAE": "🇦🇪", "Japan": "🇯🇵", "Germany": "🇩🇪",
        "France": "🇫🇷", "China": "🇨🇳", "Australia": "🇦🇺", "Canada": "🇨🇦"
    }
    
    logger.info(f"🔬 Starting cultural research for '{brand_name}' in {country}...")
    
    cultural = CulturalIntelligence(
        country=country,
        country_flag=country_flags.get(country, "🌍"),
        brand_name=brand_name
    )
    
    try:
        # Step 1: Web search for cultural context
        cultural_search = await search_cultural_sensitivity(brand_name, country)
        
        # Step 2: LLM cultural analysis
        analysis = await llm_analyze_cultural(brand_name, country, cultural_search)
        
        if analysis:
            cultural.cultural_resonance_score = analysis.get("cultural_resonance_score", 7.0)
            cultural.linguistic_check = analysis.get("linguistic_check", "PASS")
            cultural.sacred_name_detected = analysis.get("sacred_name_detected", False)
            cultural.detected_terms = analysis.get("detected_terms", [])
            cultural.cultural_notes = analysis.get("cultural_notes", "")
            cultural.cultural_risk_warning = analysis.get("cultural_risk_warning")
            cultural.legal_implications = analysis.get("legal_implications")
            cultural.sources_used.append("Web Search + LLM Analysis")
            cultural.research_quality = "HIGH"
            
            logger.info(f"✅ Cultural analysis complete for {country}: score={cultural.cultural_resonance_score}, sacred_detected={cultural.sacred_name_detected}")
        else:
            logger.warning(f"⚠️ Cultural research failed for {country}, using fallback")
            cultural.research_quality = "FALLBACK"
            _apply_cultural_fallback(cultural, fallback_data)
            
    except Exception as e:
        logger.error(f"Cultural research error for {country}: {e}")
        cultural.research_quality = "FALLBACK"
        _apply_cultural_fallback(cultural, fallback_data)
    
    return cultural


def _apply_cultural_fallback(
    cultural: CulturalIntelligence,
    fallback_data: Dict[str, Any]
):
    """Apply fallback cultural data when research fails"""
    if fallback_data:
        cultural.cultural_resonance_score = fallback_data.get("resonance_score", 7.0)
        cultural.cultural_notes = fallback_data.get("cultural_notes", 
            f"Cultural analysis pending for {cultural.country}. Recommend local validation.")
        cultural.linguistic_check = fallback_data.get("linguistic_check", "ADVISORY")
    else:
        cultural.cultural_notes = f"Recommend local linguistic and cultural validation for {cultural.country} market."
        cultural.linguistic_check = "ADVISORY"


# ============ BATCH RESEARCH FUNCTIONS ============

async def research_all_countries(
    category: str,
    countries: List[Dict[str, str]],
    brand_name: str,
    fallback_market_data: Dict[str, Dict] = None,
    fallback_cultural_data: Dict[str, Dict] = None
) -> tuple:
    """
    Research market intelligence and cultural sensitivity for all countries in parallel.
    Returns (market_intelligence_list, cultural_intelligence_list)
    """
    logger.info(f"🚀 Starting parallel research for {len(countries)} countries...")
    
    # Limit to 4 countries max
    countries_to_process = countries[:4] if len(countries) > 4 else countries
    
    # Create tasks for parallel execution
    market_tasks = []
    cultural_tasks = []
    
    for country in countries_to_process:
        country_name = country.get('name') if isinstance(country, dict) else str(country)
        
        # Get fallback data for this country
        market_fallback = fallback_market_data.get(country_name) if fallback_market_data else None
        cultural_fallback = fallback_cultural_data.get(country_name) if fallback_cultural_data else None
        
        market_tasks.append(
            research_country_market(category, country_name, brand_name, market_fallback)
        )
        cultural_tasks.append(
            research_cultural_sensitivity(brand_name, country_name, cultural_fallback)
        )
    
    # Execute all research in parallel
    market_results = await asyncio.gather(*market_tasks, return_exceptions=True)
    cultural_results = await asyncio.gather(*cultural_tasks, return_exceptions=True)
    
    # Filter out exceptions
    market_intelligence = [r for r in market_results if isinstance(r, MarketIntelligence)]
    cultural_intelligence = [r for r in cultural_results if isinstance(r, CulturalIntelligence)]
    
    logger.info(f"✅ Research complete: {len(market_intelligence)} market, {len(cultural_intelligence)} cultural")
    
    return market_intelligence, cultural_intelligence


def format_market_intelligence_for_response(intelligence: MarketIntelligence) -> Dict[str, Any]:
    """Format market intelligence for API response"""
    return {
        "country": intelligence.country,
        "country_flag": intelligence.country_flag,
        "x_axis_label": intelligence.x_axis_label,
        "y_axis_label": intelligence.y_axis_label,
        "competitors": intelligence.competitors,
        "user_brand_position": intelligence.user_brand_position,
        "white_space_analysis": intelligence.white_space_analysis,
        "strategic_advantage": intelligence.strategic_advantage,
        "market_entry_recommendation": intelligence.market_entry_recommendation,
        "research_quality": intelligence.research_quality
    }


def format_cultural_intelligence_for_response(cultural: CulturalIntelligence) -> Dict[str, Any]:
    """Format cultural intelligence for API response"""
    notes = cultural.cultural_notes
    
    # Prepend warning if sacred name detected
    if cultural.sacred_name_detected and cultural.cultural_risk_warning:
        notes = f"{cultural.cultural_risk_warning}\n\n**Detected terms:** {', '.join(cultural.detected_terms)}\n\n**Original Analysis:** {notes}"
        if cultural.legal_implications:
            notes += f"\n\n**Legal Implications:** {cultural.legal_implications}"
    
    return {
        "country": cultural.country,
        "country_flag": cultural.country_flag,
        "cultural_resonance_score": cultural.cultural_resonance_score,
        "cultural_notes": notes,
        "linguistic_check": cultural.linguistic_check,
        "research_quality": cultural.research_quality
    }
