"""
String Similarity Layer for Brand Name Analysis
Uses Levenshtein Distance + Jaro-Winkler + LLM-First Detection for comprehensive brand conflict analysis
"""

import jellyfish
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
from typing import List, Dict, Tuple, Optional
import re
import os
import json
import asyncio
import logging

# Try to import LLM capabilities
try:
    from emergentintegrations.llm.chat import LlmChat
    EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')
    LLM_AVAILABLE = bool(EMERGENT_KEY)
except ImportError:
    LlmChat = None
    EMERGENT_KEY = None
    LLM_AVAILABLE = False

logger = logging.getLogger(__name__)

# Well-known brands by category (expandable)
KNOWN_BRANDS = {
    "Food & Beverage": [
        "Tata", "Tata Salt", "Amul", "Nestle", "Britannia", "Parle", "ITC", "Dabur",
        "Patanjali", "Haldiram", "MTR", "Catch", "Everest", "MDH", "Saffola", "Fortune",
        "Aashirvaad", "Pillsbury", "Maggi", "Knorr", "Kissan", "Heinz", "Kelloggs",
        "PepsiCo", "Coca-Cola", "Pepsi", "Sprite", "Fanta", "Thumbs Up", "Limca",
        "Bisleri", "Kinley", "Aquafina", "Tropicana", "Real", "Paper Boat"
    ],
    "Technology & Software": [
        "Tata", "TCS", "Infosys", "Wipro", "HCL", "Tech Mahindra", "Google", "Microsoft",
        "Apple", "Amazon", "Meta", "Facebook", "Netflix", "Adobe", "Oracle", "SAP",
        "Salesforce", "IBM", "Intel", "Nvidia", "AMD", "Qualcomm", "Samsung", "Sony",
        "OpenAI", "Anthropic", "Zoom", "Slack", "Atlassian", "GitHub", "GitLab"
    ],
    "E-commerce & Retail": [
        "Amazon", "Flipkart", "Myntra", "Ajio", "Nykaa", "Tata Cliq", "Reliance",
        "BigBasket", "Grofers", "Blinkit", "Zepto", "Swiggy", "Zomato", "Dunzo",
        "Meesho", "Shopsy", "JioMart", "DMart", "Spencer's", "More", "Star Bazaar"
    ],
    "Fashion & Apparel": [
        "Zara", "H&M", "Uniqlo", "Nike", "Adidas", "Puma", "Reebok", "Levi's",
        "Raymond", "Allen Solly", "Van Heusen", "Louis Philippe", "Peter England",
        "Fabindia", "Biba", "W", "Global Desi", "AND", "Forever 21", "Mango",
        "Gucci", "Louis Vuitton", "Prada", "Chanel", "Dior", "Burberry", "Armani"
    ],
    "Beauty & Cosmetics": [
        "Nykaa", "Lakme", "Maybelline", "L'Oreal", "MAC", "Revlon", "Colorbar",
        "Sugar", "Plum", "Mamaearth", "WOW", "Biotique", "Forest Essentials",
        "Kama Ayurveda", "Himalaya", "Nivea", "Dove", "Garnier", "Olay", "Neutrogena"
    ],
    "Finance & Banking": [
        "HDFC", "ICICI", "SBI", "Axis", "Kotak", "Yes Bank", "IndusInd", "PNB",
        "Bank of Baroda", "Canara Bank", "Union Bank", "PayTM", "PhonePe", "Google Pay",
        "CRED", "Razorpay", "Stripe", "PayPal", "Visa", "Mastercard", "RuPay"
    ],
    "Healthcare & Pharma": [
        "Apollo", "Fortis", "Max", "Medanta", "AIIMS", "Cipla", "Sun Pharma",
        "Dr. Reddy's", "Lupin", "Ranbaxy", "Biocon", "Zydus", "Torrent", "Glenmark",
        "Pfizer", "Johnson & Johnson", "GSK", "Novartis", "Roche", "AstraZeneca",
        "Mankind", "Mankind Pharma", "Alkem", "Cadila", "Intas", "Macleods", "Abbott",
        "Sanofi", "Merck", "Bayer", "Eli Lilly", "Bristol Myers", "Amgen", "Gilead"
    ],
    "Social Media & Platforms": [
        "Facebook", "Instagram", "Twitter", "TikTok", "Snapchat", "LinkedIn", "Pinterest",
        "Reddit", "Discord", "Telegram", "WhatsApp", "YouTube", "Twitch", "BeReal",
        "Threads", "Mastodon", "Tumblr", "Quora", "Medium", "Substack"
    ],
    "Automotive": [
        "Tata Motors", "Maruti", "Hyundai", "Mahindra", "Toyota", "Honda", "Ford",
        "Volkswagen", "BMW", "Mercedes", "Audi", "Skoda", "Kia", "MG", "Renault",
        "Nissan", "Jeep", "Land Rover", "Jaguar", "Porsche", "Ferrari", "Lamborghini"
    ],
    "Salon Booking": [
        "Urban Company", "Fresha", "Vagaro", "Booksy", "StyleSeat", "Schedulicity",
        "Mindbody", "Zenoti", "Phorest", "Salon Iris", "UnQue", "Glossgenius"
    ],
    "General": [
        "Tata", "Reliance", "Adani", "Birla", "Mahindra", "Godrej", "Bajaj",
        "Larsen & Toubro", "Wipro", "Infosys", "ITC"
    ]
}

# Industry-specific suffixes that indicate potential conflicts
INDUSTRY_SUFFIXES = {
    "Healthcare & Pharma": [
        "kind", "plex", "zol", "cin", "mycin", "pril", "sartan", "statin",
        "mab", "nib", "vir", "tide", "pam", "lol", "done", "ine", "ase"
    ],
    "Social Media & Platforms": [
        "book", "gram", "chat", "tube", "tok", "pin", "link", "feed", "post", "snap"
    ],
    "Finance & Banking": [
        "pay", "bank", "fin", "cash", "money", "credit", "loan", "fund"
    ],
    "Technology & Software": [
        "soft", "tech", "cloud", "data", "ai", "app", "net", "sys", "ware"
    ]
}

# ============ TWO-TIER SUFFIX CONFLICT SYSTEM ============

# TIER 1: MEGA-BRAND SUFFIXES - ALWAYS REJECT (Any Industry)
# These brands are so famous that ANY suffix match is a guaranteed lawsuit
TIER1_MEGA_BRAND_SUFFIXES = {
    # Social Media Giants
    "book": {
        "brand": "Facebook/Meta",
        "reason": "3B+ users, universal recognition. Meta has unlimited legal budget and WILL sue.",
        "examples": ["HeadBook", "StyleBook", "FoodBook", "TravelBook"]
    },
    "gram": {
        "brand": "Instagram",
        "reason": "'Do it for the gram' is cultural. Instagram is a verb now.",
        "examples": ["PhotoGram", "FoodGram", "TravelGram", "FitGram"]
    },
    "tube": {
        "brand": "YouTube",
        "reason": "Synonym for online video. 2B+ monthly users.",
        "examples": ["CookTube", "FitTube", "EduTube", "GameTube"]
    },
    "tok": {
        "brand": "TikTok",
        "reason": "1B+ users, cultural phenomenon. ByteDance aggressively protects IP.",
        "examples": ["FunTok", "DanceTok", "LearnTok"]
    },
    "flix": {
        "brand": "Netflix",
        "reason": "Synonym for streaming. 'Netflix and chill' is cultural.",
        "examples": ["SportFlix", "KidsFlix", "DocuFlix", "GameFlix"]
    },
    # Tech Giants
    "soft": {
        "brand": "Microsoft",
        "reason": "$2T+ company with aggressive IP enforcement.",
        "examples": ["DataSoft", "CloudSoft", "GameSoft"]
    },
    "ogle": {
        "brand": "Google",
        "reason": "'Google it' is a verb. Alphabet has unlimited legal resources.",
        "examples": ["ShopOgle", "TravelOgle"]
    },
    "oogle": {
        "brand": "Google",
        "reason": "'Google it' is a verb. Alphabet has unlimited legal resources.",
        "examples": ["Boogle", "Doogle", "Foogle"]
    },
    # E-commerce Giants
    "zon": {
        "brand": "Amazon",
        "reason": "The everything store. Will expand into ANY industry.",
        "examples": ["FashionZon", "FoodZon", "TechZon"]
    },
    "bay": {
        "brand": "eBay",
        "reason": "E-commerce pioneer with strong trademark portfolio.",
        "examples": ["ShopBay", "DealBay", "TradeBay"]
    },
    "cart": {
        "brand": "Instacart",
        "reason": "Dominant grocery delivery. 'Cart' is their core identity.",
        "examples": ["FreshCart", "QuickCart", "SmartCart"]
    },
    # Apple Ecosystem (VERY Aggressive)
    "pod": {
        "brand": "Apple (iPod)",
        "reason": "Apple sued anyone with 'pod' - even podcast apps.",
        "examples": ["MusicPod", "VideoPod", "FitPod"]
    },
    "phone": {
        "brand": "Apple (iPhone)",
        "reason": "Apple owns 'iPhone' trademark aggressively.",
        "examples": ["SmartPhone brands", "MyPhone"]
    },
    "pad": {
        "brand": "Apple (iPad)",
        "reason": "Apple sued multiple companies over 'pad' suffix.",
        "examples": ["NotePad apps", "DrawPad"]
    },
    # Streaming/Music
    "fy": {
        "brand": "Spotify",
        "reason": "Dominant music streaming. '-ify' is their signature.",
        "examples": ["Musicfy", "Podcastfy", "Listenfy"]
    },
    "ify": {
        "brand": "Spotify",
        "reason": "Dominant music streaming. '-ify' is their signature.",
        "examples": ["Beautify", "Shopify (grandfathered)", "Testify"]
    },
    # Messaging
    "app": {
        "brand": "WhatsApp",
        "reason": "2B+ users. Meta owns it and will protect aggressively.",
        "examples": ["ChatApp", "CallApp", "BizApp"]
    },
    "chat": {
        "brand": "Snapchat/WeChat",
        "reason": "Major messaging platforms with strong IP protection.",
        "examples": ["QuickChat", "BizChat", "VideoChat"]
    },
}

# TIER 2: INDUSTRY-SPECIFIC SUFFIXES - Reject in SAME industry, WARNING in different
TIER2_INDUSTRY_SUFFIXES = {
    "Healthcare & Pharma": {
        "kind": {"brand": "Mankind Pharma", "reason": "Major Indian pharma company"},
        "plex": {"brand": "Various pharma", "reason": "Common pharma suffix"},
        "zol": {"brand": "Various pharma", "reason": "Common drug suffix (omeprazole, etc.)"},
        "mab": {"brand": "Biotech", "reason": "Monoclonal antibody drugs"},
        "nib": {"brand": "Biotech", "reason": "Kinase inhibitor drugs"},
    },
    "Finance & Banking": {
        "pay": {"brand": "PayPal/GPay/ApplePay", "reason": "Dominant payment brands"},
        "cash": {"brand": "Cash App", "reason": "Square's payment app"},
        "venmo": {"brand": "Venmo", "reason": "PayPal subsidiary"},
        "wallet": {"brand": "Google Wallet/Apple Wallet", "reason": "Digital wallet leaders"},
        "bank": {"brand": "Various", "reason": "Regulated term in many jurisdictions"},
    },
    "Food Delivery": {
        "eats": {"brand": "UberEats", "reason": "Major food delivery platform"},
        "dash": {"brand": "DoorDash", "reason": "US food delivery leader"},
        "grub": {"brand": "GrubHub", "reason": "Major food delivery platform"},
        "bite": {"brand": "Various food apps", "reason": "Common food delivery suffix"},
    },
    "E-commerce & Retail": {
        "kart": {"brand": "Flipkart", "reason": "India's largest e-commerce"},
        "mart": {"brand": "Walmart/JioMart", "reason": "Retail giants"},
        "basket": {"brand": "BigBasket", "reason": "Indian grocery leader"},
        "fresh": {"brand": "Amazon Fresh", "reason": "Amazon's grocery arm"},
    },
    "Travel & Hospitality": {
        "bnb": {"brand": "Airbnb", "reason": "Dominant home-sharing platform"},
        "trip": {"brand": "TripAdvisor/MakeMyTrip", "reason": "Major travel brands"},
        "booking": {"brand": "Booking.com", "reason": "Global hotel booking leader"},
        "stay": {"brand": "Various hotel chains", "reason": "Common hospitality suffix"},
    },
    "Social Media & Platforms": {
        "pin": {"brand": "Pinterest", "reason": "Visual discovery platform"},
        "snap": {"brand": "Snapchat", "reason": "Ephemeral messaging pioneer"},
        "tweet": {"brand": "Twitter/X", "reason": "Trademarked term"},
        "thread": {"brand": "Threads (Meta)", "reason": "Meta's Twitter competitor"},
        "link": {"brand": "LinkedIn", "reason": "Professional networking giant"},
    },
}

# Legacy map for backward compatibility
SUFFIX_BRAND_MAP = {
    "kind": ["Mankind"],
    "book": ["Facebook"],
    "gram": ["Instagram"],
    "tube": ["YouTube"],
    "tok": ["TikTok"],
    "chat": ["Snapchat", "WeChat"],
    "pay": ["PayPal", "Google Pay", "Apple Pay", "Samsung Pay"],
    "soft": ["Microsoft"]
}

# Famous global brands to always check against (MUST MATCH server.py FAMOUS_BRANDS)
GLOBAL_FAMOUS_BRANDS = [
    # Fortune 500 / Major Retailers
    "Costco", "Walmart", "Target", "Kroger", "Walgreens", "CVS", "Home Depot", "Lowes",
    "Best Buy", "Macys", "Nordstrom", "Kohls", "JCPenney", "Sears", "IKEA", "Aldi", "Lidl",
    "Whole Foods", "Trader Joes", "Safeway", "Publix", "Wegmans",
    # Tech Giants
    "Apple", "Google", "Microsoft", "Amazon", "Meta", "Facebook", "Instagram", "WhatsApp",
    "Netflix", "Spotify", "Uber", "Lyft", "Airbnb", "Twitter", "TikTok", "Snapchat",
    "LinkedIn", "Pinterest", "Reddit", "Discord", "Zoom", "Slack", "Dropbox", "Salesforce",
    "Oracle", "SAP", "Adobe", "Nvidia", "Intel", "AMD", "Qualcomm", "Cisco", "IBM", "HP",
    "Dell", "Lenovo", "Samsung", "Sony", "LG", "Panasonic", "Toshiba", "Huawei", "Xiaomi",
    # Automotive
    "Tesla", "Ford", "GM", "Chevrolet", "Toyota", "Honda", "BMW", "Mercedes", "Audi",
    "Volkswagen", "Porsche", "Ferrari", "Lamborghini", "Bentley", "Rolls Royce", "Jaguar",
    # Food & Beverage
    "Coca Cola", "Pepsi", "McDonalds", "Burger King", "Wendys", "Starbucks", "Dunkin",
    "Subway", "Dominos", "Pizza Hut", "KFC", "Taco Bell", "Chipotle", "Panera",
    "Nestle", "Kraft", "General Mills", "Kelloggs", "PepsiCo", "Mondelez",
    "Kinley", "Bisleri", "Aquafina", "Dasani", "Evian", "Perrier", "Fiji", "Voss",  # Water brands
    # Fashion & Luxury
    "Nike", "Adidas", "Puma", "Reebok", "Under Armour", "Lululemon", "Gap", "Old Navy",
    "Zara", "H&M", "Uniqlo", "Forever 21", "ASOS", "Shein", "Louis Vuitton", "Gucci",
    "Prada", "Chanel", "Hermes", "Dior", "Versace", "Armani", "Burberry", "Coach",
    "Michael Kors", "Ralph Lauren", "Tommy Hilfiger", "Calvin Klein", "Levis",
    # Finance
    "Visa", "Mastercard", "American Express", "PayPal", "Stripe", "Square", "Venmo",
    "Chase", "Bank of America", "Wells Fargo", "Citibank", "Goldman Sachs", "Morgan Stanley",
    # Beauty & Personal Care
    "Loreal", "Maybelline", "MAC", "Sephora", "Ulta", "Estee Lauder", "Clinique",
    "Neutrogena", "Dove", "Pantene", "Head Shoulders", "Gillette", "Olay",
    # Entertainment
    "Disney", "Warner Bros", "Universal", "Paramount", "Sony Pictures", "MGM",
    "HBO", "Showtime", "Hulu", "Paramount Plus", "Peacock", "ESPN", "CNN", "Fox",
    # Consumer Goods Giants (CRITICAL - Previously Missing!)
    "Kimberly", "Kimberly Clark", "Kleenex", "Huggies", "Kotex", "Scott",
    "Procter Gamble", "P&G", "Tide", "Pampers", "Bounty", "Charmin", "Crest", "Oral B",
    "Unilever", "Colgate", "Palmolive", "Johnson Johnson", "Band Aid", "Tylenol",
    "3M", "Post It", "Scotch", "Henkel", "Persil", "Schwarzkopf",
    "Reckitt", "Lysol", "Dettol", "Durex", "Enfamil", "Mead Johnson",
    "Church Dwight", "Arm Hammer", "OxiClean", "Clorox", "Glad", "Brita",
    "SC Johnson", "Windex", "Glade", "Raid", "Ziploc", "Reynolds",
    # Pharma Giants
    "Pfizer", "Johnson Johnson", "Merck", "AbbVie", "Bristol Myers", "Eli Lilly",
    "AstraZeneca", "Novartis", "Roche", "Sanofi", "GSK", "GlaxoSmithKline", "Bayer",
    # Others
    "FedEx", "UPS", "USPS", "DHL", "Amazon Prime", "eBay", "Etsy", "Shopify",
    "Alibaba", "AliExpress", "Wish", "Wayfair", "Overstock", "Chewy", "Petco", "PetSmart",
    # Indian Major Brands
    "Tata", "Reliance", "Adani", "Birla", "Mahindra", "Godrej", "Bajaj", "Infosys", "Wipro"
]

# Jaro-Winkler threshold for flagging similarity (lowered from implicit 95 to 85)
JARO_WINKLER_DANGER_THRESHOLD = 85.0  # 85%+ similarity = DANGER


# ============ LLM-FIRST SUFFIX DETECTION ============

LLM_SUFFIX_DETECTION_PROMPT = """You are a trademark attorney expert analyzing brand name conflicts.

TASK: Analyze if "{brand_name}" infringes on any famous brand's suffix/naming pattern.

USER'S INDUSTRY: {category}

ANALYSIS REQUIRED:
1. Identify any suffix or naming pattern in "{brand_name}" that matches a famous brand
2. Determine if this is a MEGA-BRAND (globally famous, will sue anyone) or INDUSTRY-SPECIFIC conflict
3. Assess the risk level

MEGA-BRANDS (Always dangerous regardless of industry):
- Facebook (-book), Instagram (-gram), YouTube (-tube), TikTok (-tok)
- Netflix (-flix), Spotify (-fy/-ify), Microsoft (-soft), Google (-oogle/-ogle)
- Amazon (-zon/-azon), Apple (-pod, -pad, -phone), eBay (-bay)
- WhatsApp (-app), Snapchat/WeChat (-chat), PayPal (-pal)
- Disney, Nike, Coca-Cola, McDonald's, Starbucks
- Any brand with 100M+ users or $10B+ valuation

INDUSTRY-SPECIFIC PATTERNS:
- Pharma: -kind (Mankind), -plex, -zol, -mab, -nib
- Fintech: -pay, -cash, -wallet, -coin, -fi
- Food Delivery: -eats, -dash, -grub, -bites
- E-commerce: -kart, -mart, -basket, -fresh, -store
- Travel: -bnb, -trip, -booking, -stay, -inn
- Social: -pin, -snap, -link, -gram, -feed

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "has_conflict": true/false,
    "conflicts": [
        {{
            "detected_pattern": "the suffix/pattern found (e.g., '-book')",
            "conflicting_brand": "Famous brand name (e.g., 'Facebook')",
            "brand_owner": "Parent company if different (e.g., 'Meta')",
            "tier": 1 or 2,
            "tier_reason": "MEGA-BRAND" or "INDUSTRY-SPECIFIC",
            "same_industry": true/false,
            "risk_level": "CRITICAL" or "HIGH" or "MEDIUM" or "LOW",
            "explanation": "Clear explanation of why this is a conflict",
            "lawsuit_probability": "CERTAIN" or "HIGH" or "MEDIUM" or "LOW"
        }}
    ],
    "recommendation": "REJECT" or "WARNING" or "PROCEED",
    "summary": "One-line summary of the analysis"
}}

If no conflicts found, return:
{{
    "has_conflict": false,
    "conflicts": [],
    "recommendation": "PROCEED",
    "summary": "No suffix conflicts detected with major brands"
}}

IMPORTANT RULES:
1. Be AGGRESSIVE in detecting conflicts - when in doubt, flag it
2. MEGA-BRANDS (Tier 1) should ALWAYS result in "REJECT" regardless of industry
3. Industry-specific (Tier 2) conflicts in SAME industry = "REJECT"
4. Industry-specific (Tier 2) conflicts in DIFFERENT industry = "WARNING"
5. Consider phonetic similarities too (e.g., "Fazebook" sounds like "Facebook")

Return ONLY valid JSON, no explanations outside the JSON."""


async def llm_detect_suffix_conflicts(brand_name: str, category: str) -> Dict:
    """
    Use LLM to dynamically detect suffix conflicts with famous brands.
    This catches patterns that static lists might miss.
    
    Returns structured conflict analysis.
    """
    if not LLM_AVAILABLE or not LlmChat:
        logger.warning("LLM not available for suffix detection, using static fallback only")
        return None
    
    try:
        prompt = LLM_SUFFIX_DETECTION_PROMPT.format(
            brand_name=brand_name,
            category=category
        )
        
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            model="openai/gpt-4o-mini"
        )
        
        response = await asyncio.wait_for(
            chat.send_message_async(prompt),
            timeout=15  # Quick timeout for responsiveness
        )
        
        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        result = json.loads(response_text)
        logger.info(f"🤖 LLM Suffix Detection for '{brand_name}': {result.get('recommendation', 'UNKNOWN')} - {result.get('summary', 'No summary')}")
        
        return result
        
    except asyncio.TimeoutError:
        logger.warning(f"LLM suffix detection timed out for '{brand_name}'")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM suffix response: {e}")
        return None
    except Exception as e:
        logger.warning(f"LLM suffix detection failed: {e}")
        return None


def llm_detect_suffix_conflicts_sync(brand_name: str, category: str) -> Dict:
    """Synchronous wrapper for LLM suffix detection"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    llm_detect_suffix_conflicts(brand_name, category)
                )
                return future.result(timeout=20)
        else:
            return loop.run_until_complete(llm_detect_suffix_conflicts(brand_name, category))
    except Exception as e:
        logger.warning(f"Sync LLM suffix detection failed: {e}")
        return None


def check_suffix_conflict_with_llm(input_name: str, industry: str, category: str, use_llm: bool = True) -> Dict:
    """
    HYBRID SUFFIX CONFLICT DETECTION
    
    Combines:
    1. LLM-first detection (dynamic, catches new patterns)
    2. Static list fallback (reliable safety net)
    
    Returns the MORE CONSERVATIVE result (if either says REJECT, reject)
    """
    result = {
        "has_suffix_conflict": False,
        "tier1_conflicts": [],
        "tier2_conflicts": [],
        "tier2_warnings": [],
        "conflicts": [],
        "should_reject": False,
        "rejection_reason": None,
        "llm_analysis": None,
        "detection_method": "STATIC_ONLY"
    }
    
    # Step 1: Run static check first (fast, reliable)
    static_result = check_suffix_conflict(input_name, industry, category)
    
    # Copy static results
    result["tier1_conflicts"] = static_result.get("tier1_conflicts", [])
    result["tier2_conflicts"] = static_result.get("tier2_conflicts", [])
    result["tier2_warnings"] = static_result.get("tier2_warnings", [])
    result["conflicts"] = static_result.get("conflicts", [])
    result["has_suffix_conflict"] = static_result.get("has_suffix_conflict", False)
    result["should_reject"] = static_result.get("should_reject", False)
    result["rejection_reason"] = static_result.get("rejection_reason")
    
    # Step 2: Run LLM detection (if enabled and static didn't already reject)
    if use_llm and LLM_AVAILABLE:
        try:
            llm_result = llm_detect_suffix_conflicts_sync(input_name, category)
            
            if llm_result:
                result["llm_analysis"] = llm_result
                result["detection_method"] = "LLM_ENHANCED"
                
                # If LLM found conflicts that static missed
                if llm_result.get("has_conflict") and llm_result.get("conflicts"):
                    for conflict in llm_result["conflicts"]:
                        # Check if this conflict is already in our static results
                        pattern = conflict.get("detected_pattern", "").lower().replace("-", "")
                        already_found = any(
                            c.get("suffix", "").lower() == pattern 
                            for c in result["conflicts"]
                        )
                        
                        if not already_found:
                            # New conflict found by LLM!
                            new_conflict = {
                                "brand": conflict.get("conflicting_brand", "Unknown"),
                                "suffix": conflict.get("detected_pattern", ""),
                                "match_type": f"LLM_DETECTED_TIER{conflict.get('tier', 1)}",
                                "tier": conflict.get("tier", 1),
                                "severity": "FATAL" if conflict.get("risk_level") in ["CRITICAL", "HIGH"] else "WARNING",
                                "explanation": f"🤖 LLM Detection: {conflict.get('explanation', 'Potential conflict detected')}",
                                "lawsuit_probability": conflict.get("lawsuit_probability", "UNKNOWN")
                            }
                            
                            if conflict.get("tier") == 1 or (conflict.get("tier") == 2 and conflict.get("same_industry")):
                                result["conflicts"].append(new_conflict)
                                result["has_suffix_conflict"] = True
                                
                                if conflict.get("tier") == 1:
                                    result["tier1_conflicts"].append(new_conflict)
                                else:
                                    result["tier2_conflicts"].append(new_conflict)
                            else:
                                result["tier2_warnings"].append(new_conflict)
                    
                    # Update rejection status based on LLM recommendation
                    if llm_result.get("recommendation") == "REJECT" and not result["should_reject"]:
                        result["should_reject"] = True
                        result["rejection_reason"] = f"🤖 LLM DETECTED: {llm_result.get('summary', 'Suffix conflict with major brand')}"
                        
        except Exception as e:
            logger.warning(f"LLM suffix detection failed, using static only: {e}")
            result["detection_method"] = "STATIC_ONLY_LLM_FAILED"
    
    return result


def normalize_name(name: str) -> str:
    """Normalize brand name for comparison"""
    # Convert to lowercase
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [" inc", " ltd", " llc", " corp", " pvt", " private", " limited"]:
        name = name.replace(suffix, "")
    # Remove special characters but keep spaces
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # Remove extra spaces
    name = ' '.join(name.split())
    return name


def calculate_levenshtein_similarity(name1: str, name2: str) -> float:
    """
    Calculate Levenshtein-based similarity (0-100)
    Lower edit distance = higher similarity
    """
    n1, n2 = normalize_name(name1), normalize_name(name2)
    if not n1 or not n2:
        return 0.0
    
    # Get edit distance
    distance = Levenshtein.distance(n1, n2)
    max_len = max(len(n1), len(n2))
    
    if max_len == 0:
        return 100.0
    
    # Convert to similarity percentage
    similarity = (1 - (distance / max_len)) * 100
    return round(similarity, 2)


def calculate_jaro_winkler_similarity(name1: str, name2: str) -> float:
    """
    Calculate Jaro-Winkler similarity (0-100)
    Gives more weight to prefix matches (good for brand names)
    """
    n1, n2 = normalize_name(name1), normalize_name(name2)
    if not n1 or not n2:
        return 0.0
    
    # Jaro-Winkler returns 0-1, multiply by 100
    similarity = jellyfish.jaro_winkler_similarity(n1, n2) * 100
    return round(similarity, 2)


def calculate_fuzzy_ratio(name1: str, name2: str) -> float:
    """
    Calculate fuzzy ratio using RapidFuzz (0-100)
    Good for partial matches and typos
    """
    n1, n2 = normalize_name(name1), normalize_name(name2)
    if not n1 or not n2:
        return 0.0
    
    return round(fuzz.ratio(n1, n2), 2)


def calculate_phonetic_similarity(name1: str, name2: str) -> Tuple[bool, str]:
    """
    Check if two names sound the same using phonetic algorithms
    Returns (is_match, explanation)
    
    IMPORTANT: Only return match if names are reasonably similar in length
    to avoid false positives like HeadBook matching HDFC
    """
    n1, n2 = normalize_name(name1), normalize_name(name2)
    
    # Length check - avoid matching very different length names
    len_ratio = min(len(n1), len(n2)) / max(len(n1), len(n2)) if max(len(n1), len(n2)) > 0 else 0
    if len_ratio < 0.5:  # Names are too different in length
        return False, f"Length mismatch - not a phonetic conflict"
    
    # Soundex comparison
    soundex1 = jellyfish.soundex(n1.replace(" ", ""))
    soundex2 = jellyfish.soundex(n2.replace(" ", ""))
    
    # Metaphone comparison
    metaphone1 = jellyfish.metaphone(n1.replace(" ", ""))
    metaphone2 = jellyfish.metaphone(n2.replace(" ", ""))
    
    soundex_match = soundex1 == soundex2
    metaphone_match = metaphone1 == metaphone2
    
    # Additional check: First 2 letters should be similar for phonetic match to count
    first_letter_match = n1[:2].lower() == n2[:2].lower() if len(n1) >= 2 and len(n2) >= 2 else False
    
    if soundex_match and metaphone_match and first_letter_match:
        return True, f"PHONETIC MATCH: Both Soundex ({soundex1}) and Metaphone ({metaphone1}) codes are identical"
    elif (soundex_match or metaphone_match) and first_letter_match:
        if soundex_match:
            return True, f"SOUNDEX MATCH: Same Soundex code ({soundex1})"
        else:
            return True, f"METAPHONE MATCH: Same Metaphone code ({metaphone1})"
    
    return False, f"No phonetic match"


def check_suffix_conflict(input_name: str, industry: str, category: str) -> Dict:
    """
    TWO-TIER SUFFIX CONFLICT DETECTION
    
    TIER 1: MEGA-BRAND SUFFIXES - ALWAYS REJECT (Any Industry)
            HeadBook → REJECT (even for Hotels) because Facebook will sue
            
    TIER 2: INDUSTRY-SPECIFIC SUFFIXES - Reject in SAME industry, WARNING in different
            AuraKind in Pharma → REJECT (same industry as Mankind)
            AuraKind in Beauty → WARNING (different industry)
    """
    input_lower = input_name.lower()
    category_lower = category.lower() if category else ""
    industry_lower = industry.lower() if industry else ""
    
    result = {
        "has_suffix_conflict": False,
        "tier1_conflicts": [],  # ALWAYS FATAL
        "tier2_conflicts": [],  # FATAL if same industry
        "tier2_warnings": [],   # WARNING if different industry
        "conflicts": [],        # Combined for backward compatibility
        "should_reject": False,
        "rejection_reason": None
    }
    
    # ============ TIER 1: MEGA-BRAND SUFFIXES (ALWAYS REJECT) ============
    for suffix, data in TIER1_MEGA_BRAND_SUFFIXES.items():
        if input_lower.endswith(suffix) or suffix in input_lower:
            conflict = {
                "brand": data["brand"],
                "suffix": suffix,
                "match_type": "TIER1_MEGA_BRAND",
                "tier": 1,
                "severity": "FATAL",
                "explanation": f"⛔ TIER 1 CONFLICT: '{input_name}' contains '-{suffix}' which infringes on {data['brand']}. {data['reason']}",
                "examples": data.get("examples", [])
            }
            result["tier1_conflicts"].append(conflict)
            result["conflicts"].append(conflict)
            result["has_suffix_conflict"] = True
            result["should_reject"] = True
            result["rejection_reason"] = f"FATAL: '{input_name}' infringes on {data['brand']} (-{suffix} suffix). This is a TIER 1 mega-brand that will sue regardless of your industry."
    
    # If TIER 1 conflict found, return immediately (no need to check TIER 2)
    if result["tier1_conflicts"]:
        return result
    
    # ============ TIER 2: INDUSTRY-SPECIFIC SUFFIXES ============
    # Map user's category to our industry keys
    user_industry_keys = []
    
    # Determine which industries the user's category falls into
    category_industry_map = {
        "Healthcare & Pharma": ["pharma", "health", "medical", "drug", "medicine", "hospital", "clinic", "biotech"],
        "Finance & Banking": ["finance", "bank", "payment", "fintech", "insurance", "invest", "loan", "credit"],
        "Food Delivery": ["food", "delivery", "restaurant", "eat", "meal", "kitchen", "catering"],
        "E-commerce & Retail": ["ecommerce", "e-commerce", "retail", "shop", "store", "market", "mall", "grocery"],
        "Travel & Hospitality": ["travel", "hotel", "hospitality", "tourism", "flight", "booking", "vacation", "stay"],
        "Social Media & Platforms": ["social", "media", "platform", "network", "community", "chat", "message"],
    }
    
    for industry_key, keywords in category_industry_map.items():
        if any(kw in category_lower or kw in industry_lower for kw in keywords):
            user_industry_keys.append(industry_key)
    
    # Check TIER 2 suffixes
    for industry_key, suffixes in TIER2_INDUSTRY_SUFFIXES.items():
        for suffix, data in suffixes.items():
            if input_lower.endswith(suffix) or (len(suffix) >= 4 and suffix in input_lower):
                is_same_industry = industry_key in user_industry_keys
                
                conflict = {
                    "brand": data["brand"],
                    "suffix": suffix,
                    "match_type": "TIER2_INDUSTRY_SPECIFIC",
                    "tier": 2,
                    "industry": industry_key,
                    "same_industry": is_same_industry,
                    "severity": "FATAL" if is_same_industry else "WARNING",
                    "explanation": f"{'⛔ TIER 2 CONFLICT' if is_same_industry else '⚠️ TIER 2 WARNING'}: '{input_name}' contains '-{suffix}' ({data['brand']}). {data['reason']}",
                }
                
                if is_same_industry:
                    # SAME INDUSTRY = FATAL
                    result["tier2_conflicts"].append(conflict)
                    result["conflicts"].append(conflict)
                    result["has_suffix_conflict"] = True
                    result["should_reject"] = True
                    result["rejection_reason"] = f"FATAL: '{input_name}' uses '-{suffix}' suffix in {industry_key} industry, directly conflicting with {data['brand']}."
                else:
                    # DIFFERENT INDUSTRY = WARNING ONLY
                    result["tier2_warnings"].append(conflict)
                    # Don't add to conflicts or set should_reject for warnings
    
    return result


def check_brand_similarity(
    input_name: str, 
    industry: str, 
    category: str,
    threshold_high: float = 80.0,  # High similarity threshold
    threshold_medium: float = 65.0  # Medium similarity threshold
) -> Dict:
    """
    Main function to check brand name against known brands
    Returns detailed similarity analysis
    """
    results = {
        "input_name": input_name,
        "normalized_name": normalize_name(input_name),
        "fatal_conflicts": [],
        "high_risk_matches": [],
        "medium_risk_matches": [],
        "phonetic_matches": [],
        "summary": "",
        "should_reject": False,
        "rejection_reason": None
    }
    
    # Get brands to check against
    brands_to_check = set()
    
    # Normalize inputs for matching
    industry_lower = industry.lower() if industry else ""
    category_lower = category.lower() if category else ""
    
    # Add industry-specific brands - FIX: Check if category keywords appear in the key OR key keywords appear in category
    for key, brands in KNOWN_BRANDS.items():
        key_lower = key.lower()
        # Match if: "food" in "food & beverage" OR "beverage" in "food & beverage" OR "food & beverage" in "food"
        key_words = key_lower.replace("&", " ").split()
        category_words = category_lower.replace("&", " ").split()
        industry_words = industry_lower.replace("&", " ").split()
        
        # Check for any word overlap
        if any(word in key_lower for word in category_words) or \
           any(word in key_lower for word in industry_words) or \
           any(word in category_lower for word in key_words) or \
           any(word in industry_lower for word in key_words):
            brands_to_check.update(brands)
    
    # Special handling for food/beverage/water
    if any(word in category_lower for word in ["food", "beverage", "water", "drink", "juice"]):
        brands_to_check.update(KNOWN_BRANDS.get("Food & Beverage", []))
    
    # Special handling for social media
    if "social" in category_lower or "media" in category_lower or "platform" in category_lower:
        brands_to_check.update(KNOWN_BRANDS.get("Social Media & Platforms", []))
    
    # Special handling for tech
    if any(word in category_lower for word in ["tech", "software", "app", "saas", "digital"]):
        brands_to_check.update(KNOWN_BRANDS.get("Technology & Software", []))
    
    # Add general/famous brands - ALWAYS CHECK THESE
    brands_to_check.update(KNOWN_BRANDS.get("General", []))
    brands_to_check.update(GLOBAL_FAMOUS_BRANDS)
    
    # Check against each brand
    for known_brand in brands_to_check:
        if normalize_name(input_name) == normalize_name(known_brand):
            # Exact match (after normalization)
            results["fatal_conflicts"].append({
                "brand": known_brand,
                "match_type": "EXACT_MATCH",
                "levenshtein": 100.0,
                "jaro_winkler": 100.0,
                "fuzzy_ratio": 100.0,
                "explanation": f"'{input_name}' is identical to existing brand '{known_brand}'"
            })
            results["should_reject"] = True
            results["rejection_reason"] = f"FATAL: Exact match with established brand '{known_brand}'"
            continue
        
        # Calculate similarities
        lev_sim = calculate_levenshtein_similarity(input_name, known_brand)
        jw_sim = calculate_jaro_winkler_similarity(input_name, known_brand)
        fuzzy_sim = calculate_fuzzy_ratio(input_name, known_brand)
        
        # Average similarity
        avg_sim = (lev_sim + jw_sim + fuzzy_sim) / 3
        
        # Check phonetic similarity
        phonetic_match, phonetic_explanation = calculate_phonetic_similarity(input_name, known_brand)
        
        match_data = {
            "brand": known_brand,
            "levenshtein": lev_sim,
            "jaro_winkler": jw_sim,
            "fuzzy_ratio": fuzzy_sim,
            "average_similarity": round(avg_sim, 2),
            "phonetic_match": phonetic_match,
            "phonetic_explanation": phonetic_explanation
        }
        
        # Categorize by risk level
        if avg_sim >= threshold_high or phonetic_match:
            match_data["match_type"] = "HIGH_SIMILARITY"
            match_data["explanation"] = f"'{input_name}' is dangerously similar to '{known_brand}' (Avg: {avg_sim:.1f}%)"
            
            if phonetic_match:
                results["phonetic_matches"].append(match_data)
                match_data["explanation"] += f" + {phonetic_explanation}"
            
            results["high_risk_matches"].append(match_data)
            
            # Auto-reject for very high similarity to famous brands
            if avg_sim >= 85 or (phonetic_match and known_brand in GLOBAL_FAMOUS_BRANDS):
                results["fatal_conflicts"].append(match_data)
                results["should_reject"] = True
                results["rejection_reason"] = f"FATAL: High similarity ({avg_sim:.1f}%) to established brand '{known_brand}'"
                
        elif avg_sim >= threshold_medium:
            match_data["match_type"] = "MEDIUM_SIMILARITY"
            match_data["explanation"] = f"'{input_name}' has moderate similarity to '{known_brand}' (Avg: {avg_sim:.1f}%)"
            results["medium_risk_matches"].append(match_data)
    
    # Sort by similarity
    results["high_risk_matches"].sort(key=lambda x: x["average_similarity"], reverse=True)
    results["medium_risk_matches"].sort(key=lambda x: x["average_similarity"], reverse=True)
    
    # ============ HYBRID SUFFIX CONFLICT CHECK (LLM + Static) ============
    # Uses LLM-first detection enhanced with static fallback
    suffix_result = check_suffix_conflict_with_llm(input_name, industry, category, use_llm=LLM_AVAILABLE)
    results["suffix_detection_method"] = suffix_result.get("detection_method", "STATIC_ONLY")
    results["llm_suffix_analysis"] = suffix_result.get("llm_analysis")
    
    if suffix_result["has_suffix_conflict"] or suffix_result.get("should_reject"):
        for conflict in suffix_result.get("conflicts", []):
            # Determine match type based on tier
            tier = conflict.get("tier", 1)
            match_type = f"TIER{tier}_SUFFIX_CONFLICT"
            if "LLM_DETECTED" in conflict.get("match_type", ""):
                match_type = conflict["match_type"]
            
            # Add to fatal conflicts
            results["fatal_conflicts"].append({
                "brand": conflict["brand"],
                "match_type": match_type,
                "suffix": conflict.get("suffix", ""),
                "tier": tier,
                "levenshtein": 0,  # Not applicable for suffix match
                "jaro_winkler": 0,
                "fuzzy_ratio": 0,
                "average_similarity": 0,
                "explanation": conflict.get("explanation", f"Suffix conflict with {conflict['brand']}"),
                "lawsuit_probability": conflict.get("lawsuit_probability", "HIGH")
            })
        
        results["should_reject"] = True
        results["rejection_reason"] = suffix_result.get("rejection_reason") or f"FATAL: Suffix conflict detected"
        
        # Add warnings to results (different industry Tier 2 conflicts)
        results["suffix_warnings"] = suffix_result.get("tier2_warnings", [])
    
    # Generate summary
    if results["fatal_conflicts"]:
        top_conflict = results["fatal_conflicts"][0]
        if top_conflict.get("match_type") == "SUFFIX_CONFLICT":
            results["summary"] = f"⚠️ FATAL CONFLICT: '{input_name}' shares the '-{top_conflict.get('suffix', '')}' suffix with '{top_conflict['brand']}'. In the {category} industry, this creates unacceptable confusion risk."
        else:
            results["summary"] = f"⚠️ FATAL CONFLICT: '{input_name}' matches '{top_conflict['brand']}' ({top_conflict.get('average_similarity', 100):.1f}% similarity). Immediate rejection recommended."
    elif results["high_risk_matches"]:
        top_match = results["high_risk_matches"][0]
        results["summary"] = f"🔴 HIGH RISK: '{input_name}' is very similar to '{top_match['brand']}' ({top_match['average_similarity']:.1f}%). Legal review required."
    elif results["medium_risk_matches"]:
        top_match = results["medium_risk_matches"][0]
        results["summary"] = f"🟡 MEDIUM RISK: '{input_name}' has some similarity to '{top_match['brand']}' ({top_match['average_similarity']:.1f}%). Consider alternatives."
    else:
        results["summary"] = f"🟢 LOW RISK: No significant similarity found for '{input_name}' against {len(brands_to_check)} known brands."
    
    return results


def format_similarity_report(similarity_data: Dict) -> str:
    """Format similarity check results for inclusion in LLM prompt"""
    lines = [
        "=" * 60,
        "STRING SIMILARITY ANALYSIS (Pre-LLM Layer)",
        "=" * 60,
        f"Input Brand: {similarity_data['input_name']}",
        f"Normalized: {similarity_data['normalized_name']}",
        "",
        f"VERDICT: {'🚫 REJECT' if similarity_data['should_reject'] else '✓ PROCEED WITH CAUTION' if similarity_data['high_risk_matches'] else '✓ CLEAR'}",
        ""
    ]
    
    if similarity_data['rejection_reason']:
        lines.append(f"REJECTION REASON: {similarity_data['rejection_reason']}")
        lines.append("")
    
    if similarity_data['fatal_conflicts']:
        lines.append("⚠️ FATAL CONFLICTS:")
        for conflict in similarity_data['fatal_conflicts'][:3]:
            lines.append(f"  • {conflict['brand']}: {conflict.get('average_similarity', 100):.1f}% match")
            lines.append(f"    Levenshtein: {conflict['levenshtein']}%, Jaro-Winkler: {conflict['jaro_winkler']}%")
            if conflict.get('phonetic_match'):
                lines.append(f"    {conflict['phonetic_explanation']}")
        lines.append("")
    
    if similarity_data['high_risk_matches']:
        lines.append("🔴 HIGH RISK MATCHES:")
        for match in similarity_data['high_risk_matches'][:5]:
            lines.append(f"  • {match['brand']}: {match['average_similarity']:.1f}% average similarity")
            lines.append(f"    Levenshtein: {match['levenshtein']}%, Jaro-Winkler: {match['jaro_winkler']}%, Fuzzy: {match['fuzzy_ratio']}%")
        lines.append("")
    
    if similarity_data['phonetic_matches']:
        lines.append("🔊 PHONETIC MATCHES (Same pronunciation):")
        for match in similarity_data['phonetic_matches'][:3]:
            lines.append(f"  • {match['brand']}: {match['phonetic_explanation']}")
        lines.append("")
    
    lines.append(f"SUMMARY: {similarity_data['summary']}")
    lines.append("=" * 60)
    
    return "\n".join(lines)


# Test function
if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("Taata", "Food & Beverage", "Salt"),
        ("Tata", "Food & Beverage", "Salt"),
        ("Nikee", "Fashion & Apparel", "Sportswear"),
        ("Googl", "Technology & Software", "Search Engine"),
        ("Unqueue", "Salon Booking", "Appointment App"),
        ("Lumina", "Technology & Software", "AI Platform"),
    ]
    
    for name, industry, category in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {name} ({industry} / {category})")
        result = check_brand_similarity(name, industry, category)
        print(format_similarity_report(result))
