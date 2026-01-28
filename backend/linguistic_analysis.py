"""
Universal Linguistic Analysis Module for RIGHTNAME.AI
Analyzes brand names for meaning in ANY world language using LLM
"""

import json
import logging
import os
from typing import Optional, Dict, Any

# Import Emergent Integration
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    LLM_AVAILABLE = True
except ImportError:
    logging.error("emergentintegrations not found for linguistic analysis")
    LLM_AVAILABLE = False
    UserMessage = None

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")

# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY-SPECIFIC SUCCESSFUL BRAND EXAMPLES
# Used to validate LLM responses and provide fallback examples
# ═══════════════════════════════════════════════════════════════════════════════
CATEGORY_BRAND_EXAMPLES = {
    "tea": [
        {"brand": "Teavana", "meaning_origin": "Tea + Nirvana - Sanskrit/English compound", "industry": "Tea", "why_similar_pattern": "Combines product (tea) with aspirational concept"},
        {"brand": "Tea Nation", "meaning_origin": "Descriptive English compound", "industry": "Tea", "why_similar_pattern": "Direct category reference with scale indicator"},
        {"brand": "Chaayos", "meaning_origin": "Chai (Hindi: tea) + suffix", "industry": "Tea", "why_similar_pattern": "Local language root with modern suffix"},
        {"brand": "Tata Tea", "meaning_origin": "Company name + product", "industry": "Tea", "why_similar_pattern": "Heritage brand with clear category"},
    ],
    "coffee": [
        {"brand": "Starbucks", "meaning_origin": "Literary reference (Moby Dick character)", "industry": "Coffee", "why_similar_pattern": "Evocative name with maritime heritage"},
        {"brand": "Blue Tokai", "meaning_origin": "Color + Indian coffee region", "industry": "Coffee", "why_similar_pattern": "Geographic origin reference"},
        {"brand": "Nescafe", "meaning_origin": "Nestle + Cafe compound", "industry": "Coffee", "why_similar_pattern": "Parent brand + category fusion"},
    ],
    "hotel": [
        {"brand": "Taj Hotels", "meaning_origin": "Taj Mahal reference - symbol of grandeur", "industry": "Hotels", "why_similar_pattern": "Heritage/cultural monument association"},
        {"brand": "Marriott", "meaning_origin": "Founder's surname", "industry": "Hotels", "why_similar_pattern": "Personal name conveying trust"},
        {"brand": "Lemon Tree", "meaning_origin": "Nature imagery - freshness", "industry": "Hotels", "why_similar_pattern": "Evocative natural element"},
    ],
    "technology": [
        {"brand": "Microsoft", "meaning_origin": "Microcomputer + Software compound", "industry": "Technology", "why_similar_pattern": "Technical compound describing core business"},
        {"brand": "Infosys", "meaning_origin": "Information + Systems", "industry": "Technology", "why_similar_pattern": "Descriptive tech compound"},
        {"brand": "Zoho", "meaning_origin": "Coined/invented word", "industry": "Technology", "why_similar_pattern": "Short, memorable coined name"},
    ],
    "food": [
        {"brand": "Haldiram's", "meaning_origin": "Founder's name", "industry": "Food", "why_similar_pattern": "Personal name building trust in food"},
        {"brand": "MTR", "meaning_origin": "Mavalli Tiffin Rooms acronym", "industry": "Food", "why_similar_pattern": "Location + offering abbreviated"},
        {"brand": "Bikanervala", "meaning_origin": "Bikaner (city) + wala (from)", "industry": "Food", "why_similar_pattern": "Geographic origin indicator"},
    ],
    "beauty": [
        {"brand": "Nykaa", "meaning_origin": "Sanskrit 'Nayaka' - actress/heroine", "industry": "Beauty", "why_similar_pattern": "Sanskrit root with beauty connotation"},
        {"brand": "Lakme", "meaning_origin": "French opera character (goddess of beauty)", "industry": "Beauty", "why_similar_pattern": "Literary/mythological beauty reference"},
        {"brand": "Mamaearth", "meaning_origin": "Mama + Earth - nurturing nature", "industry": "Beauty", "why_similar_pattern": "Emotional + natural compound"},
    ],
    "finance": [
        {"brand": "PayPal", "meaning_origin": "Pay + Pal - friendly payment", "industry": "Finance", "why_similar_pattern": "Function + approachability compound"},
        {"brand": "Razorpay", "meaning_origin": "Razor (sharp/efficient) + Pay", "industry": "Finance", "why_similar_pattern": "Efficiency descriptor + function"},
        {"brand": "PhonePe", "meaning_origin": "Phone + Pe (Hindi: on)", "industry": "Finance", "why_similar_pattern": "Device + local language suffix"},
    ],
    "default": [
        {"brand": "Apple", "meaning_origin": "Common fruit - arbitrary use", "industry": "Technology", "why_similar_pattern": "Simple word in unrelated context"},
        {"brand": "Amazon", "meaning_origin": "World's largest river", "industry": "E-commerce", "why_similar_pattern": "Geographic feature suggesting scale"},
        {"brand": "Nike", "meaning_origin": "Greek goddess of victory", "industry": "Sports", "why_similar_pattern": "Mythological victory reference"},
    ]
}

def get_category_key(category: str) -> str:
    """Map category to brand examples key"""
    category_lower = category.lower()
    if any(word in category_lower for word in ["tea", "chai"]):
        return "tea"
    elif any(word in category_lower for word in ["coffee", "cafe", "espresso"]):
        return "coffee"
    elif any(word in category_lower for word in ["hotel", "hospitality", "resort", "lodge"]):
        return "hotel"
    elif any(word in category_lower for word in ["tech", "software", "saas", "app", "digital"]):
        return "technology"
    elif any(word in category_lower for word in ["food", "restaurant", "snack", "sweet"]):
        return "food"
    elif any(word in category_lower for word in ["beauty", "cosmetic", "skincare", "makeup"]):
        return "beauty"
    elif any(word in category_lower for word in ["finance", "payment", "bank", "fintech"]):
        return "finance"
    return "default"

def validate_and_fix_similar_brands(similar_brands: list, category: str) -> list:
    """
    Validate that similar brands are from the correct category.
    If LLM returned wrong category examples, replace with correct ones.
    """
    if not similar_brands:
        # Return category-appropriate defaults
        category_key = get_category_key(category)
        return CATEGORY_BRAND_EXAMPLES.get(category_key, CATEGORY_BRAND_EXAMPLES["default"])[:2]
    
    category_key = get_category_key(category)
    category_lower = category.lower()
    
    # Check if any returned brands are from wrong category
    wrong_category_brands = []
    for brand_info in similar_brands:
        brand_industry = (brand_info.get("industry") or "").lower()
        # Check for common mismatches
        if "tea" in category_lower and "coffee" in brand_industry:
            wrong_category_brands.append(brand_info)
        elif "coffee" in category_lower and "tea" in brand_industry:
            wrong_category_brands.append(brand_info)
        elif "hotel" in category_lower and brand_industry not in ["hotel", "hotels", "hospitality"]:
            wrong_category_brands.append(brand_info)
    
    # If more than half are wrong, replace all
    if len(wrong_category_brands) > len(similar_brands) / 2:
        logging.warning(f"🔄 SIMILAR BRANDS FIX: LLM returned wrong category examples for '{category}', replacing with correct ones")
        return CATEGORY_BRAND_EXAMPLES.get(category_key, CATEGORY_BRAND_EXAMPLES["default"])[:2]
    
    # Otherwise return original (may have some good examples)
    return similar_brands

# Linguistic Analysis Prompt - Open-ended, not limited to specific languages
LINGUISTIC_ANALYSIS_PROMPT = """You are a world-class multilingual linguist and brand naming expert with deep knowledge of etymology, morphology, and cultural linguistics across ALL world languages.

BRAND NAME TO ANALYZE: {brand_name}
BUSINESS CATEGORY: {business_category}

YOUR TASK: Determine if this brand name has meaning in ANY language on Earth.

## ANALYSIS STEPS:

### 1. LINGUISTIC DETECTION (Open-ended)
- Does this word/name exist in ANY language? (Do not limit yourself - consider ALL languages including ancient, regional, and dialectal)
- Can it be decomposed into morphemes, roots, prefixes, or suffixes from ANY language?
- Is it phonetically similar to meaningful words in other languages?
- Could it be a transliteration from a non-Latin script?

### 2. MEANING EXTRACTION
If meaning is found:
- What is the exact meaning/translation?
- Which language(s) is it from?
- Is it a real dictionary word, a proper noun, a compound, or phonetically derived?

### 3. CULTURAL/HISTORICAL SIGNIFICANCE
- Mythological references (any religion/culture)
- Historical figures or events
- Literary or epic references
- Regional/community significance
- Sacred or religious connotations

### 4. BUSINESS ALIGNMENT
Compare the discovered meaning to the business category:
- How well does the name's meaning align with what the business does?
- Is the connection obvious, subtle, or non-existent?
- Would customers understand the connection?

### 5. MARKET IMPLICATIONS
- Which regions would instantly recognize this name's meaning?
- Where might it need explanation?
- Any negative connotations in any language/culture to watch for?

## CRITICAL INSTRUCTIONS:
- Be thorough - check etymology deeply
- If you find meaning, explain the connection clearly
- If it's truly coined (no meaning), say so confidently
- Provide confidence levels for your findings
- Do NOT hallucinate meanings - if uncertain, say "Speculative"

## RESPONSE FORMAT (Return ONLY valid JSON, no markdown):
{{
  "brand_name": "{brand_name}",
  "business_category": "{business_category}",
  "has_linguistic_meaning": true/false,
  "is_truly_coined": true/false,
  "linguistic_analysis": {{
    "languages_detected": ["list of languages where meaning found"],
    "primary_language": "main language of origin or null",
    "decomposition": {{
      "can_be_decomposed": true/false,
      "parts": ["part1", "part2"],
      "part_meanings": {{
        "part1": {{"meaning": "meaning", "language": "language", "script_origin": "Latin/Devanagari/etc"}}
      }},
      "combined_meaning": "overall meaning when parts combined"
    }},
    "direct_meaning": {{
      "exists": true/false,
      "meaning": "direct translation if exists",
      "language": "source language"
    }},
    "phonetic_similarity": {{
      "has_similar_sounding_words": true/false,
      "similar_words": [
        {{"word": "similar word", "meaning": "its meaning", "language": "language"}}
      ]
    }}
  }},
  "cultural_significance": {{
    "has_cultural_reference": true/false,
    "reference_type": "Mythological/Historical/Literary/Religious/None",
    "details": "explanation of the reference",
    "source_text_or_origin": "e.g., Ramayana, Greek Mythology, Bible, etc.",
    "regions_of_recognition": ["list of regions/countries"],
    "sentiment": "Sacred/Heroic/Auspicious/Neutral/Cautionary",
    "religious_sensitivity": {{
      "is_sensitive": true/false,
      "religion": "which religion if any",
      "sensitivity_level": "High/Medium/Low/None"
    }}
  }},
  "confidence_assessment": {{
    "overall_confidence": "High/Medium/Low",
    "meaning_certainty": "Definitive/Probable/Speculative/None",
    "reasoning": "why this confidence level"
  }},
  "business_alignment": {{
    "alignment_score": 1-10,
    "alignment_level": "Excellent/Strong/Moderate/Weak/None",
    "explanation": "how name meaning connects to business",
    "thematic_connection": "description of the conceptual link",
    "customer_understanding": {{
      "instant_recognition_regions": ["regions where meaning is obvious"],
      "needs_explanation_regions": ["regions where it won't be understood"],
      "universal_appeal": true/false
    }}
  }},
  "classification": {{
    "name_type": "Heritage/Mythological/Foreign-Language/Compound/Portmanteau/Evocative/Descriptive/True-Coined/Phonetic-Adaptation",
    "distinctiveness_level": "High/Medium/Low",
    "reasoning": "why this classification"
  }},
  "similar_successful_brands": [
    {{
      "brand": "MUST be from SAME category as {business_category} - e.g., if analyzing a Tea Brand, give tea brand examples like 'Teavana', 'Tea Nation', 'Chaayos' - NOT coffee or unrelated brands",
      "meaning_origin": "what it means and from where",
      "industry": "MUST MATCH {business_category} exactly",
      "why_similar_pattern": "why this naming pattern works for THIS specific category"
    }}
  ],
  "_SIMILAR_BRANDS_RULE": "CRITICAL: Only provide brands from the EXACT SAME industry/category. For Tea Brand → tea examples. For Hotel → hotel examples. NEVER mix categories (no coffee brands for tea, no restaurants for hotels).",
  "potential_concerns": [
    {{
      "concern_type": "Negative-Meaning/Pronunciation/Cultural-Sensitivity/Religious",
      "language_or_region": "where this applies",
      "details": "explanation",
      "severity": "High/Medium/Low"
    }}
  ],
  "executive_summary": "2-3 sentence summary of the linguistic analysis and business fit"
}}"""


async def analyze_brand_linguistics(
    brand_name: str,
    business_category: str,
    industry: str = ""
) -> Dict[str, Any]:
    """
    Perform universal linguistic analysis on a brand name.
    Uses LLM to detect meaning in ANY world language.
    
    Args:
        brand_name: The brand name to analyze
        business_category: The business category/type
        industry: Optional industry context
        
    Returns:
        Dict containing linguistic analysis results
    """
    
    if not LLM_AVAILABLE or not EMERGENT_KEY:
        logging.warning("🔤 Linguistic Analysis: LLM not available, returning basic response")
        return _get_fallback_response(brand_name, business_category)
    
    # Combine category and industry for better context
    full_category = f"{business_category}"
    if industry and industry.lower() not in business_category.lower():
        full_category = f"{business_category} ({industry})"
    
    # Build the prompt
    prompt = LINGUISTIC_ANALYSIS_PROMPT.format(
        brand_name=brand_name,
        business_category=full_category
    )
    
    try:
        logging.info(f"🔤 Linguistic Analysis: Analyzing '{brand_name}' for '{full_category}'")
        
        # Call LLM - correct initialization pattern
        chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
        
        # Build the full message with context
        full_message = f"CONTEXT: You are a multilingual linguistic analyst. Return ONLY valid JSON, no markdown formatting.\n\n{prompt}"
        
        # Create UserMessage and send
        user_msg = UserMessage(text=full_message)
        response = await chat.send_message(user_msg)
        
        # Parse response - it's a string directly
        response_text = response.strip() if isinstance(response, str) else str(response).strip()
        
        # Clean up response if wrapped in markdown
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        
        # Parse JSON
        result = json.loads(response_text)
        
        # ═══════════════════════════════════════════════════════════════════════
        # VALIDATE & FIX SIMILAR BRANDS (ensure category-appropriate examples)
        # ═══════════════════════════════════════════════════════════════════════
        if "similar_successful_brands" in result:
            result["similar_successful_brands"] = validate_and_fix_similar_brands(
                result.get("similar_successful_brands", []),
                business_category
            )
        
        # Add metadata
        result["_analysis_version"] = "1.0"
        result["_analyzed_by"] = "universal_linguistic_analyzer"
        
        logging.info(f"🔤 Linguistic Analysis: Complete for '{brand_name}' - Has meaning: {result.get('has_linguistic_meaning', False)}")
        
        return result
        
    except json.JSONDecodeError as e:
        logging.error(f"🔤 Linguistic Analysis: JSON parse error - {e}")
        return _get_fallback_response(brand_name, business_category, error=str(e))
        
    except Exception as e:
        logging.error(f"🔤 Linguistic Analysis: Error - {e}")
        return _get_fallback_response(brand_name, business_category, error=str(e))


def _get_fallback_response(brand_name: str, business_category: str, error: str = None) -> Dict[str, Any]:
    """Return a fallback response when LLM analysis fails"""
    return {
        "brand_name": brand_name,
        "business_category": business_category,
        "has_linguistic_meaning": None,  # Unknown
        "is_truly_coined": None,
        "linguistic_analysis": {
            "languages_detected": [],
            "primary_language": None,
            "decomposition": {
                "can_be_decomposed": None,
                "parts": [],
                "part_meanings": {},
                "combined_meaning": None
            },
            "direct_meaning": {
                "exists": None,
                "meaning": None,
                "language": None
            },
            "phonetic_similarity": {
                "has_similar_sounding_words": None,
                "similar_words": []
            }
        },
        "cultural_significance": {
            "has_cultural_reference": None,
            "reference_type": None,
            "details": None,
            "source_text_or_origin": None,
            "regions_of_recognition": [],
            "sentiment": None,
            "religious_sensitivity": {
                "is_sensitive": None,
                "religion": None,
                "sensitivity_level": None
            }
        },
        "confidence_assessment": {
            "overall_confidence": "Low",
            "meaning_certainty": "None",
            "reasoning": f"Analysis unavailable: {error}" if error else "Analysis service unavailable"
        },
        "business_alignment": {
            "alignment_score": 5,
            "alignment_level": "Unknown",
            "explanation": "Unable to determine alignment - analysis unavailable",
            "thematic_connection": None,
            "customer_understanding": {
                "instant_recognition_regions": [],
                "needs_explanation_regions": [],
                "universal_appeal": None
            }
        },
        "classification": {
            "name_type": "Unknown",
            "distinctiveness_level": "Unknown",
            "reasoning": "Classification unavailable"
        },
        "similar_successful_brands": CATEGORY_BRAND_EXAMPLES.get(get_category_key(business_category), CATEGORY_BRAND_EXAMPLES["default"])[:2],
        "potential_concerns": [],
        "executive_summary": "Linguistic analysis could not be completed. Manual review recommended.",
        "_analysis_version": "1.0",
        "_analyzed_by": "fallback",
        "_error": error
    }


def format_linguistic_analysis_for_prompt(analysis: Dict[str, Any]) -> str:
    """
    Format linguistic analysis results for inclusion in other prompts.
    This is passed to trademark search, cultural fit, and final evaluation.
    """
    if not analysis or analysis.get("_analyzed_by") == "fallback":
        return "LINGUISTIC ANALYSIS: Not available"
    
    sections = []
    sections.append("=" * 60)
    sections.append("LINGUISTIC ANALYSIS RESULTS")
    sections.append("=" * 60)
    
    brand_name = analysis.get("brand_name", "Unknown")
    has_meaning = analysis.get("has_linguistic_meaning", False)
    
    sections.append(f"\nBrand Name: {brand_name}")
    sections.append(f"Has Linguistic Meaning: {'YES' if has_meaning else 'NO (Truly Coined)'}")
    
    if has_meaning:
        ling = analysis.get("linguistic_analysis", {})
        
        # Language origin
        languages = ling.get("languages_detected", [])
        # Filter out None values
        languages = [lang for lang in languages if lang is not None]
        if languages:
            sections.append(f"Language Origin: {', '.join(languages)}")
        
        # Decomposition
        decomp = ling.get("decomposition", {})
        if decomp.get("can_be_decomposed"):
            parts = decomp.get("parts", [])
            meanings = decomp.get("part_meanings", {})
            sections.append(f"\nMorphological Breakdown:")
            for part in parts:
                part_info = meanings.get(part, {})
                if isinstance(part_info, dict):
                    sections.append(f"  • {part} = {part_info.get('meaning', 'unknown')} ({part_info.get('language', 'unknown')})")
                else:
                    sections.append(f"  • {part} = {part_info}")
            
            combined = decomp.get("combined_meaning")
            if combined:
                sections.append(f"  → Combined Meaning: {combined}")
        
        # Direct meaning
        direct = ling.get("direct_meaning", {})
        if direct.get("exists"):
            sections.append(f"\nDirect Translation: {direct.get('meaning')} ({direct.get('language')})")
        
        # Cultural significance
        cultural = analysis.get("cultural_significance", {})
        if cultural.get("has_cultural_reference"):
            sections.append(f"\nCultural Significance:")
            sections.append(f"  Type: {cultural.get('reference_type', 'Unknown')}")
            sections.append(f"  Details: {cultural.get('details', 'N/A')}")
            if cultural.get("source_text_or_origin"):
                sections.append(f"  Source: {cultural.get('source_text_or_origin')}")
            regions = cultural.get("regions_of_recognition", [])
            if regions:
                sections.append(f"  Recognized In: {', '.join(regions)}")
            sections.append(f"  Sentiment: {cultural.get('sentiment', 'Neutral')}")
    
    # Business alignment
    alignment = analysis.get("business_alignment", {})
    sections.append(f"\nBusiness Alignment:")
    sections.append(f"  Score: {alignment.get('alignment_score', 'N/A')}/10 ({alignment.get('alignment_level', 'Unknown')})")
    sections.append(f"  Connection: {alignment.get('thematic_connection', 'N/A')}")
    
    # Classification
    classification = analysis.get("classification", {})
    sections.append(f"\nName Classification: {classification.get('name_type', 'Unknown')}")
    sections.append(f"Distinctiveness: {classification.get('distinctiveness_level', 'Unknown')}")
    
    # Concerns
    concerns = analysis.get("potential_concerns", [])
    if concerns:
        sections.append(f"\nPotential Concerns:")
        for concern in concerns:
            sections.append(f"  ⚠️ [{concern.get('severity', 'Medium')}] {concern.get('concern_type', 'Unknown')}: {concern.get('details', 'N/A')} ({concern.get('language_or_region', 'Global')})")
    
    # Confidence
    confidence = analysis.get("confidence_assessment", {})
    sections.append(f"\nAnalysis Confidence: {confidence.get('overall_confidence', 'Unknown')} ({confidence.get('meaning_certainty', 'Unknown')})")
    
    sections.append("\n" + "=" * 60)
    
    return "\n".join(sections)


def get_linguistic_insights_for_trademark(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract linguistic insights specifically for trademark search enhancement.
    """
    if not analysis or analysis.get("_analyzed_by") == "fallback":
        return {}
    
    insights = {
        "has_meaning": analysis.get("has_linguistic_meaning", False),
        "is_coined": analysis.get("is_truly_coined", True),
        "languages": analysis.get("linguistic_analysis", {}).get("languages_detected", []),
        "primary_language": analysis.get("linguistic_analysis", {}).get("primary_language"),
        "cultural_type": analysis.get("cultural_significance", {}).get("reference_type"),
        "is_religious": analysis.get("cultural_significance", {}).get("religious_sensitivity", {}).get("is_sensitive", False),
        "name_type": analysis.get("classification", {}).get("name_type", "Unknown"),
        "distinctiveness": analysis.get("classification", {}).get("distinctiveness_level", "Medium")
    }
    
    # Add search hints based on linguistic analysis
    search_hints = []
    
    decomp = analysis.get("linguistic_analysis", {}).get("decomposition", {})
    if decomp.get("can_be_decomposed"):
        parts = decomp.get("parts", [])
        search_hints.extend(parts)  # Search for individual parts too
    
    # Add phonetically similar words
    phonetic = analysis.get("linguistic_analysis", {}).get("phonetic_similarity", {})
    if phonetic.get("has_similar_sounding_words"):
        for similar in phonetic.get("similar_words", []):
            if similar.get("word"):
                search_hints.append(similar["word"])
    
    insights["search_hints"] = search_hints
    
    return insights


def get_linguistic_insights_for_cultural_fit(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract linguistic insights specifically for cultural fit analysis.
    """
    if not analysis or analysis.get("_analyzed_by") == "fallback":
        return {}
    
    cultural = analysis.get("cultural_significance", {})
    alignment = analysis.get("business_alignment", {})
    
    return {
        "has_cultural_reference": cultural.get("has_cultural_reference", False),
        "reference_type": cultural.get("reference_type"),
        "cultural_details": cultural.get("details"),
        "source_origin": cultural.get("source_text_or_origin"),
        "recognition_regions": cultural.get("regions_of_recognition", []),
        "sentiment": cultural.get("sentiment"),
        "religious_sensitivity": cultural.get("religious_sensitivity", {}),
        "instant_recognition_regions": alignment.get("customer_understanding", {}).get("instant_recognition_regions", []),
        "needs_explanation_regions": alignment.get("customer_understanding", {}).get("needs_explanation_regions", []),
        "potential_concerns": analysis.get("potential_concerns", [])
    }
