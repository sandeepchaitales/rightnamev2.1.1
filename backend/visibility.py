"""
Visibility Module - Enhanced App Store & Web Search
===================================================
Performs comprehensive visibility checks including:
- Phonetic variant generation
- Combined brand + category searches
- Multiple query strategies
- Graceful error handling
- BOTH Play Store AND iOS App Store searches
"""

from duckduckgo_search import DDGS
from google_play_scraper import search as google_search
# iOS App Store search
try:
    from app_store_scraper import AppStore
    IOS_AVAILABLE = True
except ImportError:
    IOS_AVAILABLE = False
    
import time
import logging
import re

logger = logging.getLogger(__name__)


# Phonetic substitutions for generating variants
PHONETIC_SUBSTITUTIONS = [
    ("que", "que", "q", "k", "ck"),  # que variants
    ("unique", "unque", "uneek", "unik"),  # unique variants
    ("i", "ee", "y"),
    ("e", "i", "ee"),
    ("c", "k", "ck"),
    ("k", "c", "ck"),
    ("ph", "f"),
    ("f", "ph"),
    ("s", "z"),
    ("z", "s"),
    ("ou", "u", "oo"),
    ("oo", "u", "ou"),
]


def generate_phonetic_variants(brand_name: str) -> list:
    """
    Generate phonetic variants of a brand name.
    Critical for finding apps with similar spellings.
    
    Examples:
    - "Unque" -> ["Unique", "Unik", "Uneek"]
    - "Fresha" -> ["Fresher", "Fresh"]
    """
    variants = set()
    name_lower = brand_name.lower()
    
    # Special case mappings for common misspellings/variants
    special_mappings = {
        "unque": ["unique", "unik", "uneek", "uniq", "unike"],
        "unik": ["unique", "unque", "uneek"],
        "unique": ["unque", "unik", "uneek"],
        "fresha": ["fresh", "fresher"],
        "booksy": ["booksie", "booksi"],
        "vagaro": ["vagero", "vegaro"],
        "styleseat": ["style seat", "style-seat"],
    }
    
    # Check special mappings first
    if name_lower in special_mappings:
        variants.update(special_mappings[name_lower])
    
    # Check if any special mapping key is similar to the brand name
    for key, values in special_mappings.items():
        # Check if brand is similar to key (missing letters, extra letters, etc.)
        if len(name_lower) >= 3 and len(key) >= 3:
            # Check if brand is a subset or superset
            if name_lower in key or key in name_lower:
                variants.update(values)
            # Check edit distance (simple check - same length, 1-2 chars different)
            elif abs(len(name_lower) - len(key)) <= 2:
                matching_chars = sum(1 for a, b in zip(name_lower, key) if a == b)
                if matching_chars >= min(len(name_lower), len(key)) - 2:
                    variants.update(values)
    
    # CRITICAL: Check for "que" -> "que" pattern (unque -> unique)
    if "que" in name_lower and "i" not in name_lower:
        # Add version with 'i' before 'que'
        idx = name_lower.find("que")
        variant_with_i = name_lower[:idx] + "i" + name_lower[idx:]
        variants.add(variant_with_i)
        variants.add(variant_with_i.capitalize())
    
    # Apply phonetic substitutions
    phonetic_rules = [
        ("que", "k"), ("que", "q"), ("que", "ck"),
        ("ique", "eek"), ("ique", "ik"), ("ique", "ique"),
        ("i", "ee"), ("i", "y"),
        ("ee", "i"), ("ee", "ea"),
        ("c", "k"), ("k", "c"),
        ("ph", "f"), ("f", "ph"),
        ("s", "z"), ("z", "s"),
        ("ou", "u"), ("u", "ou"),
        ("oo", "u"), ("u", "oo"),
    ]
    
    for old, new in phonetic_rules:
        if old in name_lower:
            variant = name_lower.replace(old, new, 1)
            if variant != name_lower:
                variants.add(variant)
                # Also add capitalized version
                variants.add(variant.capitalize())
    
    # Add common prefix/suffix variants
    if name_lower.endswith("a"):
        variants.add(name_lower[:-1])
        variants.add(name_lower + "h")
    if name_lower.endswith("e"):
        variants.add(name_lower[:-1])
        variants.add(name_lower[:-1] + "a")
    
    # Remove original and empty strings
    variants.discard(name_lower)
    variants.discard(brand_name.lower())
    variants.discard("")
    
    # Prioritize "unique" if it's a variant (most common case)
    variant_list = list(variants)
    if "unique" in variant_list:
        variant_list.remove("unique")
        variant_list.insert(0, "unique")
    
    # Return unique variants (limit to 6 most likely)
    return variant_list[:6]


def get_web_search_results(query, num_results=10):
    """
    Scrapes Web Search Results using DuckDuckGo.
    Returns list of titles/snippets.
    """
    results = []
    try:
        with DDGS() as ddgs:
            ddg_gen = ddgs.text(query, max_results=num_results)
            if ddg_gen:
                for r in ddg_gen:
                    results.append(f"{r['title']} ({r['href']})")
    except Exception as e:
        logger.warning(f"Web search failed for '{query}': {str(e)}")
        pass
            
    return results


def get_play_store_results(query, country='us', timeout=10):
    """
    Searches Google Play Store with ROBUST error handling (Improvement #4).
    Returns list of app info dictionaries.
    
    Improvements:
    - Timeout handling
    - Multiple retry attempts
    - Graceful degradation on failure
    - Better error logging
    """
    results = []
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            res = google_search(
                query,
                lang='en',
                country=country,
                n_hits=5  # Reduced from 10 to avoid rate limiting
            )
            
            if res:
                for app in res:
                    if app and isinstance(app, dict):
                        results.append({
                            "title": app.get('title', 'Unknown'),
                            "developer": app.get('developer', 'Unknown'),
                            "appId": app.get('appId', ''),
                            "score": app.get('score', 0),
                            "installs": app.get('installs', '0'),
                        })
            
            # Success - break retry loop
            break
                        
        except TypeError as e:
            # Handle NoneType errors from google_play_scraper (most common error)
            logger.warning(f"Play Store search type error for '{query}' (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(0.5)  # Short delay before retry
                continue
        except ConnectionError as e:
            logger.warning(f"Play Store connection error for '{query}': {str(e)}")
            break  # Don't retry on connection errors
        except TimeoutError as e:
            logger.warning(f"Play Store timeout for '{query}': {str(e)}")
            break  # Don't retry on timeout
        except Exception as e:
            error_msg = str(e).lower()
            # Check for specific error types that shouldn't be retried
            if any(x in error_msg for x in ['rate limit', 'too many requests', '429', 'forbidden', '403']):
                logger.warning(f"Play Store rate limited for '{query}': {str(e)}")
                break
            logger.warning(f"Play Store search failed for '{query}' (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
    
    # Add delay to avoid rate limiting (even on success)
    time.sleep(0.3)
        
    return results


def get_ios_app_store_results(query, country='us', limit=5):
    """
    Search iOS App Store for apps matching query.
    Uses app-store-scraper library.
    
    Returns list of app info dictionaries.
    """
    if not IOS_AVAILABLE:
        logger.warning("iOS App Store scraper not available")
        return []
    
    results = []
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            # app-store-scraper search method
            from itunes_app_scraper.scraper import AppStoreScraper
            scraper = AppStoreScraper()
            search_results = scraper.get_app_ids_for_query(query, country=country, limit=limit)
            
            for app_id in search_results[:limit]:
                try:
                    app_details = scraper.get_app_details(app_id, country=country)
                    if app_details:
                        results.append({
                            "title": app_details.get('trackName', 'Unknown'),
                            "developer": app_details.get('artistName', 'Unknown'),
                            "appId": str(app_id),
                            "score": app_details.get('averageUserRating', 0),
                            "source": "iOS App Store"
                        })
                except Exception as e:
                    logger.warning(f"Failed to get iOS app details for {app_id}: {e}")
            break
            
        except ImportError:
            # Try alternative method using web search
            logger.info(f"Using web search fallback for iOS apps: '{query}'")
            try:
                web_results = get_web_search_results(f"{query} site:apps.apple.com")
                for res in web_results[:limit]:
                    if 'apps.apple.com' in res.lower():
                        results.append({
                            "title": query,
                            "developer": "Unknown (from web)",
                            "appId": "web_search",
                            "score": 0,
                            "source": "iOS App Store (web search)"
                        })
                        break
            except Exception:
                pass
            break
            
        except Exception as e:
            logger.warning(f"iOS App Store search failed for '{query}' (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
    
    time.sleep(0.2)  # Rate limiting
    return results


def search_both_app_stores(query, countries=['us', 'in']):
    """
    Search BOTH Play Store AND iOS App Store.
    Returns combined results.
    """
    all_results = []
    
    # Play Store search
    for country in countries[:2]:  # Limit countries
        try:
            play_results = get_play_store_results(query, country=country)
            for app in play_results:
                app['source'] = f'Play Store ({country.upper()})'
            all_results.extend(play_results)
        except Exception as e:
            logger.warning(f"Play Store search failed for '{query}' in {country}: {e}")
    
    # iOS App Store search
    for country in countries[:2]:
        try:
            ios_results = get_ios_app_store_results(query, country=country)
            all_results.extend(ios_results)
        except Exception as e:
            logger.warning(f"iOS App Store search failed for '{query}' in {country}: {e}")
    
    return all_results


def search_app_stores_comprehensive(brand_name: str, category: str = "", industry: str = "") -> dict:
    """
    Comprehensive app store search using multiple strategies:
    1. Exact brand name
    2. Brand + category keywords
    3. Phonetic variants
    4. Phonetic variants + category (CRITICAL for finding similar apps)
    5. Category-only search for market context
    
    Returns:
    {
        "exact_matches": [],      # Apps with exact brand name
        "phonetic_matches": [],   # Apps with phonetically similar names
        "category_competitors": [], # Other apps in same category
        "search_queries_used": [], # For transparency
        "potential_conflicts": []  # High-risk matches
    }
    """
    results = {
        "exact_matches": [],
        "phonetic_matches": [],
        "category_competitors": [],
        "search_queries_used": [],
        "potential_conflicts": []
    }
    
    seen_app_ids = set()
    
    # Extract category keywords
    category_keywords = extract_category_keywords(category, industry)
    
    # Get phonetic variants upfront
    phonetic_variants = generate_phonetic_variants(brand_name)
    logger.info(f"Phonetic variants for '{brand_name}': {phonetic_variants}")
    
    # Strategy 1: Exact brand name search (BOTH Play Store AND iOS App Store)
    logger.info(f"App search Strategy 1: Exact brand name '{brand_name}' on BOTH stores")
    results["search_queries_used"].append(f"Exact: {brand_name} (Play Store + iOS)")
    
    # Search BOTH app stores
    exact_results = search_both_app_stores(brand_name, countries=['us', 'in'])
    
    for app in exact_results:
        app_id = app.get("appId", "")
        if app_id and app_id not in seen_app_ids:
            seen_app_ids.add(app_id)
            app_title_lower = app.get("title", "").lower()
            brand_lower = brand_name.lower()
            
            # IMPROVED: Normalize both names for comparison
            app_title_normalized = re.sub(r'[^a-z0-9]', '', app_title_lower)
            brand_normalized = re.sub(r'[^a-z0-9]', '', brand_lower)
            
            # IMPROVED: Also dedupe repeated letters for comparison
            app_title_dedupe = re.sub(r'(.)\1+', r'\1', app_title_normalized)
            brand_dedupe = re.sub(r'(.)\1+', r'\1', brand_normalized)
            
            # Check multiple match conditions
            is_exact_match = (
                brand_lower in app_title_lower or 
                brand_normalized in app_title_normalized or
                brand_dedupe == app_title_dedupe or  # "ludostarr" matches "ludostar"
                app_title_normalized in brand_normalized or
                app_title_dedupe in brand_dedupe
            )
            
            # Check phonetic similarity using normalized forms
            is_phonetic_match = any(
                re.sub(r'(.)\1+', r'\1', re.sub(r'[^a-z0-9]', '', v.lower())) in app_title_dedupe or
                app_title_dedupe in re.sub(r'(.)\1+', r'\1', re.sub(r'[^a-z0-9]', '', v.lower()))
                for v in phonetic_variants
            )
            
            if is_exact_match:
                app["match_type"] = "EXACT"
                app["similarity_note"] = f"'{brand_name}' matches '{app.get('title')}'"
                results["exact_matches"].append(app)
                results["potential_conflicts"].append(app)
                logger.warning(f"🚨 CONFLICT DETECTED: '{brand_name}' matches app '{app.get('title')}' by {app.get('developer')}")
            elif is_phonetic_match:
                matched_variant = next((v for v in phonetic_variants if v.lower() in app_title_lower), brand_name)
                app["match_type"] = "PHONETIC_EXACT"
                app["phonetic_variant"] = matched_variant
                results["phonetic_matches"].append(app)
                results["potential_conflicts"].append(app)
                logger.warning(f"🔊 PHONETIC CONFLICT: '{brand_name}' sounds like '{app.get('title')}'")
            else:
                app["match_type"] = "PARTIAL"
                results["category_competitors"].append(app)
    
    # Strategy 2: Brand + category combined search
    if category_keywords:
        combined_queries = [
            f"{brand_name} {category_keywords[0]}",
        ]
        
        for query in combined_queries:
            logger.info(f"App search Strategy 2: Combined '{query}'")
            results["search_queries_used"].append(f"Combined: {query}")
            
            combined_results = get_play_store_results(query, country='us')
            for app in combined_results:
                app_id = app.get("appId", "")
                if app_id and app_id not in seen_app_ids:
                    seen_app_ids.add(app_id)
                    app_title_lower = app.get("title", "").lower()
                    brand_lower = brand_name.lower()
                    
                    if brand_lower in app_title_lower:
                        app["match_type"] = "COMBINED_EXACT"
                        results["exact_matches"].append(app)
                        results["potential_conflicts"].append(app)
                    elif any(v.lower() in app_title_lower for v in phonetic_variants):
                        matched_variant = next((v for v in phonetic_variants if v.lower() in app_title_lower), "")
                        app["match_type"] = "COMBINED_PHONETIC"
                        app["phonetic_variant"] = matched_variant
                        results["phonetic_matches"].append(app)
                        results["potential_conflicts"].append(app)
                    else:
                        app["match_type"] = "COMBINED"
                        results["category_competitors"].append(app)
    
    # Strategy 3: Phonetic variants alone (only top 2)
    logger.info(f"App search Strategy 3: Phonetic variants {phonetic_variants[:2]}")
    
    for variant in phonetic_variants[:2]:  # Limit to top 2 variants
        results["search_queries_used"].append(f"Phonetic: {variant}")
        
        variant_results = get_play_store_results(variant, country='us')
        for app in variant_results:
            app_id = app.get("appId", "")
            if app_id and app_id not in seen_app_ids:
                seen_app_ids.add(app_id)
                app_title_lower = app.get("title", "").lower()
                
                # Check if app title contains the variant
                if variant.lower() in app_title_lower:
                    app["match_type"] = "PHONETIC"
                    app["phonetic_variant"] = variant
                    results["phonetic_matches"].append(app)
                    
                    # Mark as potential conflict if it's a close match
                    if is_close_match(brand_name, app.get("title", "")):
                        results["potential_conflicts"].append(app)
    
    # Strategy 4: CRITICAL - Phonetic variants + category keywords
    # This is the key to finding "UnQue - Salon Booking App" when searching "Unque"
    if category_keywords and phonetic_variants:
        logger.info(f"App search Strategy 4: Phonetic + Category")
        
        # Only search first variant + first category keyword to reduce API calls
        variant = phonetic_variants[0] if phonetic_variants else brand_name
        keyword = category_keywords[0] if category_keywords else ""
        
        if keyword:
            combo_query = f"{variant} {keyword}"
            results["search_queries_used"].append(f"Phonetic+Category: {combo_query}")
            
            combo_results = get_play_store_results(combo_query, country='in')  # India for salon apps
            for app in combo_results:
                app_id = app.get("appId", "")
                if app_id and app_id not in seen_app_ids:
                    seen_app_ids.add(app_id)
                    app_title_lower = app.get("title", "").lower()
                    brand_lower = brand_name.lower()
                    
                    # Check for brand name or variants in title
                    if brand_lower in app_title_lower:
                        app["match_type"] = "PHONETIC_CATEGORY_EXACT"
                        results["exact_matches"].append(app)
                        results["potential_conflicts"].append(app)
                    elif any(v.lower() in app_title_lower for v in phonetic_variants):
                        matched_variant = next((v for v in phonetic_variants if v.lower() in app_title_lower), variant)
                        app["match_type"] = "PHONETIC_CATEGORY"
                        app["phonetic_variant"] = matched_variant
                        results["phonetic_matches"].append(app)
                        results["potential_conflicts"].append(app)
                    else:
                        app["match_type"] = "CATEGORY_RELATED"
                        results["category_competitors"].append(app)
    
    # Strategy 5: Category-only search for market context
    if category_keywords:
        category_query = " ".join(category_keywords[:2])
        logger.info(f"App search Strategy 5: Category '{category_query}'")
        results["search_queries_used"].append(f"Category: {category_query}")
        
        category_results = get_play_store_results(category_query, country='us')
        for app in category_results[:10]:  # Limit category results
            app_id = app.get("appId", "")
            if app_id and app_id not in seen_app_ids:
                seen_app_ids.add(app_id)
                app["match_type"] = "CATEGORY"
                results["category_competitors"].append(app)
    
    # Deduplicate potential_conflicts
    seen_conflict_ids = set()
    unique_conflicts = []
    for app in results["potential_conflicts"]:
        app_id = app.get("appId", "")
        if app_id not in seen_conflict_ids:
            seen_conflict_ids.add(app_id)
            unique_conflicts.append(app)
    results["potential_conflicts"] = unique_conflicts
    
    logger.info(f"App search complete: {len(results['exact_matches'])} exact, "
                f"{len(results['phonetic_matches'])} phonetic, "
                f"{len(results['potential_conflicts'])} conflicts, "
                f"{len(results['category_competitors'])} competitors")
    
    return results


def extract_category_keywords(category: str, industry: str = "") -> list:
    """
    Extract relevant keywords from category and industry.
    """
    keywords = []
    
    # Combine category and industry
    combined = f"{category} {industry}".lower()
    
    # Remove common filler words
    stopwords = {"and", "the", "a", "an", "for", "of", "in", "on", "with", "app", "application"}
    
    words = re.findall(r'\b[a-z]+\b', combined)
    keywords = [w for w in words if w not in stopwords and len(w) > 2]
    
    # Add common category-specific keywords
    category_expansions = {
        "salon": ["beauty", "booking", "appointment", "hair", "spa"],
        "booking": ["appointment", "scheduling", "reservation"],
        "appointment": ["booking", "scheduling", "calendar"],
        "food": ["delivery", "restaurant", "order"],
        "fitness": ["gym", "workout", "health", "exercise"],
        "finance": ["banking", "money", "payment", "wallet"],
        "education": ["learning", "study", "course", "school"],
    }
    
    for word in list(keywords):
        if word in category_expansions:
            keywords.extend(category_expansions[word][:2])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    
    return unique_keywords[:5]


def is_close_match(brand_name: str, app_title: str) -> bool:
    """
    Determine if an app title is a close match to the brand name.
    Uses simple heuristics for quick matching.
    """
    brand_lower = brand_name.lower()
    title_lower = app_title.lower()
    
    # Exact substring match
    if brand_lower in title_lower:
        return True
    
    # Check phonetic variants
    variants = generate_phonetic_variants(brand_name)
    for variant in variants:
        if variant.lower() in title_lower:
            return True
    
    # Check first word match
    title_first_word = title_lower.split()[0] if title_lower else ""
    if title_first_word and (
        title_first_word == brand_lower or
        title_first_word in [v.lower() for v in variants]
    ):
        return True
    
    return False


def format_app_results_for_llm(app_search_results: dict, brand_name: str) -> str:
    """
    Format app search results into a string for LLM consumption.
    Highlights potential conflicts clearly.
    """
    lines = []
    
    lines.append(f"🔍 APP STORE SEARCH RESULTS FOR '{brand_name}'")
    lines.append("=" * 50)
    
    # Search queries used (for transparency)
    lines.append(f"\nSearch Queries Used: {len(app_search_results.get('search_queries_used', []))}")
    for q in app_search_results.get("search_queries_used", [])[:5]:
        lines.append(f"  - {q}")
    
    # Potential conflicts (CRITICAL)
    conflicts = app_search_results.get("potential_conflicts", [])
    if conflicts:
        lines.append(f"\n🚨 POTENTIAL CONFLICTS FOUND ({len(conflicts)}):")
        for app in conflicts[:5]:
            lines.append(f"  ⚠️ {app.get('title', 'Unknown')}")
            lines.append(f"     Developer: {app.get('developer', 'Unknown')}")
            lines.append(f"     Match Type: {app.get('match_type', 'Unknown')}")
            if app.get("phonetic_variant"):
                lines.append(f"     Phonetic Match: '{app.get('phonetic_variant')}'")
            lines.append(f"     Rating: {app.get('score', 'N/A')} | Installs: {app.get('installs', 'N/A')}")
    else:
        lines.append("\n✅ NO DIRECT APP CONFLICTS FOUND")
    
    # Exact matches
    exact = app_search_results.get("exact_matches", [])
    if exact:
        lines.append(f"\n🎯 EXACT MATCHES ({len(exact)}):")
        for app in exact[:3]:
            lines.append(f"  - {app.get('title', 'Unknown')} by {app.get('developer', 'Unknown')}")
    
    # Phonetic matches
    phonetic = app_search_results.get("phonetic_matches", [])
    if phonetic:
        lines.append(f"\n🔊 PHONETIC/SIMILAR MATCHES ({len(phonetic)}):")
        for app in phonetic[:3]:
            lines.append(f"  - {app.get('title', 'Unknown')} (matched '{app.get('phonetic_variant', 'N/A')}')")
    
    # Category competitors
    competitors = app_search_results.get("category_competitors", [])
    if competitors:
        lines.append(f"\n📱 CATEGORY COMPETITORS ({len(competitors)}):")
        for app in competitors[:5]:
            lines.append(f"  - {app.get('title', 'Unknown')} by {app.get('developer', 'Unknown')}")
    
    return "\n".join(lines)


def check_visibility(brand_name: str, category: str = "", industry: str = "", known_competitors: list = None, product_keywords: list = None):
    """
    Enhanced visibility check with category-aware searching.
    
    Args:
        brand_name: The brand name to search
        category: Product category (e.g., "Salon Appointment Booking App")
        industry: Industry sector (e.g., "Beauty & Wellness")
        known_competitors: User-provided list of known competitors (Improvement #2)
        product_keywords: User-provided product keywords for better search (Improvement #3)
    
    Returns:
        Dictionary with google, apps, and app_search_details
    """
    logger.info(f"Checking visibility for '{brand_name}' in category '{category}'")
    
    # Default empty lists if not provided
    known_competitors = known_competitors or []
    product_keywords = product_keywords or []
    
    # 1. Web Search (brand name + category for better context)
    web_query = f"{brand_name} {category}" if category else brand_name
    web_res = get_web_search_results(web_query)
    
    # Also search just brand name
    if category:
        web_res_brand = get_web_search_results(brand_name)
        web_res = list(set(web_res + web_res_brand))[:10]
    
    # Improvement #3: Also search with product keywords
    if product_keywords:
        for keyword in product_keywords[:2]:  # Limit to 2 keywords
            try:
                keyword_res = get_web_search_results(f"{brand_name} {keyword}")
                web_res = list(set(web_res + keyword_res))[:15]
            except Exception as e:
                logger.warning(f"Keyword search failed for '{brand_name} {keyword}': {e}")
    
    time.sleep(0.3)
    
    # 2. Comprehensive App Store Search
    app_search_results = search_app_stores_comprehensive(brand_name, category, industry)
    
    # Improvement #2: Check user-provided competitors for conflicts
    competitor_matches = []
    if known_competitors:
        logger.info(f"Checking against {len(known_competitors)} user-provided competitors")
        for competitor in known_competitors[:5]:  # Limit to 5 competitors
            # Check if brand name is similar to competitor
            brand_lower = brand_name.lower().replace(" ", "")
            comp_lower = competitor.lower().replace(" ", "")
            
            # Check for substring match
            if brand_lower in comp_lower or comp_lower in brand_lower:
                competitor_matches.append({
                    "title": competitor,
                    "developer": "User-provided competitor",
                    "match_type": "USER_COMPETITOR_MATCH",
                    "appId": f"user_competitor_{competitor.lower().replace(' ', '_')}"
                })
            # Check for phonetic similarity
            elif is_close_match(brand_name, competitor):
                competitor_matches.append({
                    "title": competitor,
                    "developer": "User-provided competitor",
                    "match_type": "USER_COMPETITOR_PHONETIC",
                    "appId": f"user_competitor_{competitor.lower().replace(' ', '_')}"
                })
        
        # Add competitor matches to potential conflicts
        if competitor_matches:
            app_search_results["potential_conflicts"].extend(competitor_matches)
            app_search_results["user_competitor_matches"] = competitor_matches
    
    # 3. Format app results for backward compatibility
    play_res_formatted = []
    
    # Add conflicts first (most important)
    for app in app_search_results.get("potential_conflicts", []):
        match_type = app.get('match_type', '')
        if 'USER_COMPETITOR' in match_type:
            play_res_formatted.append(
                f"🎯 USER COMPETITOR: {app.get('title', 'Unknown')} - DIRECT COMPETITION (user-provided)"
            )
        else:
            play_res_formatted.append(
                f"⚠️ CONFLICT: {app.get('title', 'Unknown')} (Developer: {app.get('developer', 'Unknown')}) - {match_type}"
            )
    
    # Add exact matches
    for app in app_search_results.get("exact_matches", []):
        if app not in app_search_results.get("potential_conflicts", []):
            play_res_formatted.append(
                f"🎯 EXACT: {app.get('title', 'Unknown')} (Developer: {app.get('developer', 'Unknown')})"
            )
    
    # Add phonetic matches
    for app in app_search_results.get("phonetic_matches", []):
        play_res_formatted.append(
            f"🔊 PHONETIC: {app.get('title', 'Unknown')} - matches '{app.get('phonetic_variant', '')}'"
        )
    
    # Add some competitors for context
    for app in app_search_results.get("category_competitors", [])[:5]:
        play_res_formatted.append(
            f"📱 COMPETITOR: {app.get('title', 'Unknown')} (Developer: {app.get('developer', 'Unknown')})"
        )
    
    # Format for LLM
    app_search_summary = format_app_results_for_llm(app_search_results, brand_name)
    
    # Final formatting
    final_web = web_res if web_res else ["Search data unavailable (Manual verification recommended)."]
    final_apps = play_res_formatted if play_res_formatted else ["No matching apps found in Play Store."]
    
    return {
        "google": final_web,
        "apps": final_apps,
        "app_search_details": app_search_results,
        "app_search_summary": app_search_summary,
        "phonetic_variants_checked": generate_phonetic_variants(brand_name),
        "known_competitors_checked": known_competitors,
        "competitor_matches_found": len(competitor_matches) if known_competitors else 0
    }
