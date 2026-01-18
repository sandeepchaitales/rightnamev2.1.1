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
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')
    LLM_AVAILABLE = bool(EMERGENT_KEY)
except ImportError:
    LlmChat = None
    UserMessage = None
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
        
        # Correct LlmChat initialization: (api_key, provider, model)
        chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
        
        # Use synchronous send_message (run in executor for async context)
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, chat.send_message, prompt),
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
    """
    Synchronous LLM suffix detection - directly calls LLM without async complexity.
    """
    if not LLM_AVAILABLE or not LlmChat or not UserMessage:
        logger.warning("LLM not available for suffix detection")
        return None
    
    try:
        prompt = LLM_SUFFIX_DETECTION_PROMPT.format(
            brand_name=brand_name,
            category=category
        )
        
        # Correct LlmChat initialization: (api_key, provider, model)
        chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
        
        # Create UserMessage object
        user_msg = UserMessage(prompt)
        
        # Helper function to run async send_message
        async def _send_message():
            return await chat.send_message(user_msg)
        
        # Run the coroutine synchronously
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            # We're in an async context, need to use run_in_executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _send_message())
                response = future.result(timeout=20)
        else:
            # Not in async context, can run directly
            response = asyncio.run(_send_message())
        
        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        result = json.loads(response_text)
        logger.info(f"🤖 LLM Suffix Detection for '{brand_name}': {result.get('recommendation', 'UNKNOWN')} - {result.get('summary', 'No summary')}")
        
        return result
        
    except Exception as e:
        logger.warning(f"LLM suffix detection failed: {e}")
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


# ============================================================================
# DEEP-TRACE ANALYSIS - Rightname.ai Core Engine
# Protects entrepreneurs from legal suicide by stress-testing brand names
# ============================================================================

# Common startup suffixes to strip for root extraction
STARTUP_SUFFIXES = [
    # Tech/Startup common suffixes (ordered by length - longest first)
    "ify", "ly", "ai", "io", "oy", "ey", "ie", "y",
    "app", "hub", "lab", "labs", "ware", "soft", "tech",
    "ity", "ery", "ary", "ory", "ment", "ness", "tion", "sion",
    "able", "ible", "ful", "less", "ous", "ive", "al", "ic",
    "er", "or", "ist", "ism", "ize", "ise", "en", "fy",
    "co", "go", "do", "to", "no", "so", "ro", "lo", "mo", "po",
    "ex", "ox", "ix", "ax", "ux",
    "a", "e", "i", "o", "u"
]

# CATEGORY KINGS - Famous brands indexed by ROOT WORD + INDUSTRY
# This is the core of Deep-Trace Analysis
CATEGORY_KINGS = {
    # ==================== RIDE-HAILING / TRANSPORT ====================
    "rapid": {
        "industries": ["transport", "ride", "taxi", "bike", "delivery", "logistics", "mobility"],
        "king": "Rapido",
        "valuation": "$5B+",
        "market": "India",
        "description": "India's largest bike taxi platform"
    },
    "uber": {
        "industries": ["transport", "ride", "taxi", "delivery", "food", "logistics", "mobility"],
        "king": "Uber",
        "valuation": "$150B+",
        "market": "Global",
        "description": "Global ride-hailing and delivery giant"
    },
    "ola": {
        "industries": ["transport", "ride", "taxi", "electric", "ev", "mobility", "cab"],
        "king": "Ola",
        "valuation": "$7B+",
        "market": "India",
        "description": "India's largest cab aggregator"
    },
    "grab": {
        "industries": ["transport", "ride", "taxi", "delivery", "food", "fintech", "superapp"],
        "king": "Grab",
        "valuation": "$40B+",
        "market": "Southeast Asia",
        "description": "SEA's leading superapp"
    },
    "lyft": {
        "industries": ["transport", "ride", "taxi", "mobility"],
        "king": "Lyft",
        "valuation": "$5B+",
        "market": "USA",
        "description": "US ride-hailing company"
    },
    "gojek": {
        "industries": ["transport", "ride", "delivery", "food", "fintech", "superapp"],
        "king": "Gojek",
        "valuation": "$10B+",
        "market": "Indonesia",
        "description": "Indonesia's leading superapp"
    },
    "didi": {
        "industries": ["transport", "ride", "taxi", "mobility"],
        "king": "Didi",
        "valuation": "$20B+",
        "market": "China",
        "description": "China's largest ride-hailing platform"
    },
    
    # ==================== FOOD DELIVERY ====================
    "swiggy": {
        "industries": ["food", "delivery", "restaurant", "quick commerce", "grocery"],
        "king": "Swiggy",
        "valuation": "$10B+",
        "market": "India",
        "description": "India's leading food delivery platform"
    },
    "zomato": {
        "industries": ["food", "delivery", "restaurant", "dining", "quick commerce"],
        "king": "Zomato",
        "valuation": "$12B+",
        "market": "India",
        "description": "India's food delivery and restaurant discovery platform"
    },
    "door": {
        "industries": ["food", "delivery", "restaurant"],
        "king": "DoorDash",
        "valuation": "$50B+",
        "market": "USA",
        "description": "US's largest food delivery platform"
    },
    "grub": {
        "industries": ["food", "delivery", "restaurant"],
        "king": "GrubHub",
        "valuation": "$5B+",
        "market": "USA",
        "description": "US food delivery platform"
    },
    "deliveroo": {
        "industries": ["food", "delivery", "restaurant"],
        "king": "Deliveroo",
        "valuation": "$7B+",
        "market": "UK/Europe",
        "description": "European food delivery platform"
    },
    
    # ==================== QUICK COMMERCE / GROCERY ====================
    "blink": {
        "industries": ["grocery", "quick commerce", "delivery", "retail"],
        "king": "Blinkit",
        "valuation": "$2B+",
        "market": "India",
        "description": "India's leading quick commerce platform (Zomato subsidiary)"
    },
    "zepto": {
        "industries": ["grocery", "quick commerce", "delivery", "retail"],
        "king": "Zepto",
        "valuation": "$5B+",
        "market": "India",
        "description": "India's fastest-growing quick commerce platform"
    },
    "insta": {
        "industries": ["grocery", "delivery", "quick commerce", "social", "photo"],
        "king": "Instagram / Instacart / Instamart",
        "valuation": "$100B+ / $10B+",
        "market": "Global",
        "description": "Multiple mega-brands share this root"
    },
    "dunzo": {
        "industries": ["delivery", "quick commerce", "hyperlocal", "errands"],
        "king": "Dunzo",
        "valuation": "$500M+",
        "market": "India",
        "description": "India's hyperlocal delivery platform"
    },
    
    # ==================== E-COMMERCE ====================
    "flip": {
        "industries": ["ecommerce", "retail", "shopping", "marketplace"],
        "king": "Flipkart",
        "valuation": "$37B+",
        "market": "India",
        "description": "India's largest e-commerce platform (Walmart subsidiary)"
    },
    "amazon": {
        "industries": ["ecommerce", "retail", "cloud", "streaming", "everything"],
        "king": "Amazon",
        "valuation": "$1.5T+",
        "market": "Global",
        "description": "The everything store"
    },
    "shop": {
        "industries": ["ecommerce", "retail", "shopping", "marketplace"],
        "king": "Shopify / Shopee",
        "valuation": "$70B+ / $50B+",
        "market": "Global / SEA",
        "description": "E-commerce platform giants"
    },
    "meesho": {
        "industries": ["ecommerce", "social commerce", "reselling"],
        "king": "Meesho",
        "valuation": "$5B+",
        "market": "India",
        "description": "India's leading social commerce platform"
    },
    "myntra": {
        "industries": ["fashion", "ecommerce", "apparel", "lifestyle"],
        "king": "Myntra",
        "valuation": "$3B+",
        "market": "India",
        "description": "India's leading fashion e-commerce platform"
    },
    
    # ==================== FINTECH / PAYMENTS ====================
    "phone": {
        "industries": ["payments", "fintech", "upi", "wallet", "mobile"],
        "king": "PhonePe",
        "valuation": "$12B+",
        "market": "India",
        "description": "India's largest UPI payments app"
    },
    "paytm": {
        "industries": ["payments", "fintech", "wallet", "banking"],
        "king": "Paytm",
        "valuation": "$5B+",
        "market": "India",
        "description": "India's digital payments pioneer"
    },
    "razor": {
        "industries": ["payments", "fintech", "gateway", "b2b"],
        "king": "Razorpay",
        "valuation": "$7.5B+",
        "market": "India",
        "description": "India's leading payment gateway"
    },
    "cred": {
        "industries": ["fintech", "credit", "rewards", "payments"],
        "king": "CRED",
        "valuation": "$6.4B+",
        "market": "India",
        "description": "Credit card bill payments platform"
    },
    "stripe": {
        "industries": ["payments", "fintech", "gateway", "infrastructure"],
        "king": "Stripe",
        "valuation": "$50B+",
        "market": "Global",
        "description": "Global payments infrastructure"
    },
    "paypal": {
        "industries": ["payments", "fintech", "wallet", "transfer"],
        "king": "PayPal",
        "valuation": "$70B+",
        "market": "Global",
        "description": "Global digital payments leader"
    },
    "venmo": {
        "industries": ["payments", "p2p", "social payments"],
        "king": "Venmo",
        "valuation": "PayPal subsidiary",
        "market": "USA",
        "description": "Social payments app"
    },
    "groww": {
        "industries": ["investing", "stocks", "mutual funds", "fintech"],
        "king": "Groww",
        "valuation": "$3B+",
        "market": "India",
        "description": "India's leading investment app"
    },
    "zerodha": {
        "industries": ["trading", "stocks", "broker", "fintech"],
        "king": "Zerodha",
        "valuation": "$2B+",
        "market": "India",
        "description": "India's largest stock broker"
    },
    
    # ==================== SOCIAL MEDIA ====================
    "face": {
        "industries": ["social", "media", "networking", "messaging"],
        "king": "Facebook",
        "valuation": "$1T+ (Meta)",
        "market": "Global",
        "description": "World's largest social network"
    },
    "whats": {
        "industries": ["messaging", "chat", "communication"],
        "king": "WhatsApp",
        "valuation": "Meta subsidiary",
        "market": "Global",
        "description": "World's largest messaging app"
    },
    "snap": {
        "industries": ["social", "messaging", "photo", "ar"],
        "king": "Snapchat",
        "valuation": "$15B+",
        "market": "Global",
        "description": "Ephemeral messaging and AR platform"
    },
    "tik": {
        "industries": ["social", "video", "entertainment", "short video"],
        "king": "TikTok",
        "valuation": "$200B+ (ByteDance)",
        "market": "Global",
        "description": "World's largest short video platform"
    },
    "linked": {
        "industries": ["professional", "networking", "jobs", "social"],
        "king": "LinkedIn",
        "valuation": "Microsoft subsidiary",
        "market": "Global",
        "description": "World's largest professional network"
    },
    "twit": {
        "industries": ["social", "microblogging", "news"],
        "king": "Twitter/X",
        "valuation": "$44B (acquired)",
        "market": "Global",
        "description": "Microblogging platform"
    },
    "pin": {
        "industries": ["social", "visual", "discovery", "inspiration"],
        "king": "Pinterest",
        "valuation": "$15B+",
        "market": "Global",
        "description": "Visual discovery platform"
    },
    "discord": {
        "industries": ["communication", "gaming", "community", "voice"],
        "king": "Discord",
        "valuation": "$15B+",
        "market": "Global",
        "description": "Community communication platform"
    },
    "reddit": {
        "industries": ["social", "forum", "community", "discussion"],
        "king": "Reddit",
        "valuation": "$10B+",
        "market": "Global",
        "description": "Front page of the internet"
    },
    
    # ==================== STREAMING / ENTERTAINMENT ====================
    "net": {
        "industries": ["streaming", "video", "entertainment", "ott"],
        "king": "Netflix",
        "valuation": "$200B+",
        "market": "Global",
        "description": "World's largest streaming service"
    },
    "spot": {
        "industries": ["music", "streaming", "audio", "podcast"],
        "king": "Spotify",
        "valuation": "$60B+",
        "market": "Global",
        "description": "World's largest music streaming service"
    },
    "hot": {
        "industries": ["streaming", "video", "entertainment", "ott", "cricket"],
        "king": "Hotstar",
        "valuation": "Disney subsidiary",
        "market": "India",
        "description": "India's largest streaming platform"
    },
    "prime": {
        "industries": ["streaming", "video", "entertainment", "ecommerce"],
        "king": "Amazon Prime",
        "valuation": "Amazon subsidiary",
        "market": "Global",
        "description": "Amazon's streaming and membership service"
    },
    "disney": {
        "industries": ["entertainment", "streaming", "media", "animation"],
        "king": "Disney",
        "valuation": "$170B+",
        "market": "Global",
        "description": "Entertainment giant"
    },
    "youtube": {
        "industries": ["video", "streaming", "ugc", "entertainment"],
        "king": "YouTube",
        "valuation": "Google subsidiary",
        "market": "Global",
        "description": "World's largest video platform"
    },
    
    # ==================== TRAVEL / HOSPITALITY ====================
    "air": {
        "industries": ["travel", "accommodation", "hospitality", "vacation"],
        "king": "Airbnb",
        "valuation": "$80B+",
        "market": "Global",
        "description": "World's largest vacation rental platform"
    },
    "booking": {
        "industries": ["travel", "hotel", "accommodation"],
        "king": "Booking.com",
        "valuation": "$100B+",
        "market": "Global",
        "description": "World's largest hotel booking platform"
    },
    "make": {
        "industries": ["travel", "booking", "flights", "hotels"],
        "king": "MakeMyTrip",
        "valuation": "$3B+",
        "market": "India",
        "description": "India's largest travel booking platform"
    },
    "trip": {
        "industries": ["travel", "reviews", "booking"],
        "king": "TripAdvisor",
        "valuation": "$5B+",
        "market": "Global",
        "description": "World's largest travel review platform"
    },
    "oyo": {
        "industries": ["hospitality", "hotel", "accommodation", "budget"],
        "king": "OYO",
        "valuation": "$9B+",
        "market": "Global",
        "description": "World's largest budget hotel chain"
    },
    
    # ==================== TECH GIANTS ====================
    "google": {
        "industries": ["search", "tech", "cloud", "ai", "advertising", "everything"],
        "king": "Google",
        "valuation": "$1.8T+ (Alphabet)",
        "market": "Global",
        "description": "World's largest search and advertising company"
    },
    "apple": {
        "industries": ["tech", "hardware", "software", "mobile", "ecosystem"],
        "king": "Apple",
        "valuation": "$3T+",
        "market": "Global",
        "description": "World's most valuable company"
    },
    "micro": {
        "industries": ["tech", "software", "cloud", "enterprise"],
        "king": "Microsoft",
        "valuation": "$2.8T+",
        "market": "Global",
        "description": "Enterprise software giant"
    },
    "meta": {
        "industries": ["social", "vr", "ar", "metaverse"],
        "king": "Meta",
        "valuation": "$1T+",
        "market": "Global",
        "description": "Social media and metaverse company"
    },
    "nvidia": {
        "industries": ["gpu", "ai", "chips", "gaming", "datacenter"],
        "king": "Nvidia",
        "valuation": "$3T+",
        "market": "Global",
        "description": "World's most valuable chip company"
    },
    "open": {
        "industries": ["ai", "llm", "chatbot", "research"],
        "king": "OpenAI",
        "valuation": "$150B+",
        "market": "Global",
        "description": "AI research company behind ChatGPT"
    },
    "zoom": {
        "industries": ["video", "conferencing", "communication", "remote work"],
        "king": "Zoom",
        "valuation": "$20B+",
        "market": "Global",
        "description": "Video conferencing leader"
    },
    "slack": {
        "industries": ["communication", "workplace", "collaboration", "messaging"],
        "king": "Slack",
        "valuation": "Salesforce subsidiary",
        "market": "Global",
        "description": "Workplace communication platform"
    },
    
    # ==================== EDTECH ====================
    "byju": {
        "industries": ["edtech", "education", "learning", "tutoring"],
        "king": "BYJU'S",
        "valuation": "$22B+ (peak)",
        "market": "India",
        "description": "India's largest edtech company"
    },
    "unacademy": {
        "industries": ["edtech", "education", "test prep", "learning"],
        "king": "Unacademy",
        "valuation": "$3.4B+",
        "market": "India",
        "description": "India's leading test prep platform"
    },
    "vedantu": {
        "industries": ["edtech", "tutoring", "live classes"],
        "king": "Vedantu",
        "valuation": "$1B+",
        "market": "India",
        "description": "Live online tutoring platform"
    },
    "coursera": {
        "industries": ["edtech", "mooc", "courses", "certification"],
        "king": "Coursera",
        "valuation": "$3B+",
        "market": "Global",
        "description": "Online learning platform"
    },
    "udemy": {
        "industries": ["edtech", "courses", "skills", "learning"],
        "king": "Udemy",
        "valuation": "$3.5B+",
        "market": "Global",
        "description": "Online course marketplace"
    },
    
    # ==================== GAMING ====================
    "ludo": {
        "industries": ["gaming", "casual", "board game", "mobile game"],
        "king": "Ludo King",
        "valuation": "$500M+",
        "market": "India",
        "description": "India's most downloaded board game"
    },
    "dream": {
        "industries": ["gaming", "fantasy sports", "cricket"],
        "king": "Dream11",
        "valuation": "$8B+",
        "market": "India",
        "description": "India's largest fantasy sports platform"
    },
    "mpl": {
        "industries": ["gaming", "esports", "mobile gaming"],
        "king": "MPL",
        "valuation": "$2.3B+",
        "market": "India",
        "description": "Mobile gaming and esports platform"
    },
    
    # ==================== BEAUTY / WELLNESS ====================
    "nykaa": {
        "industries": ["beauty", "cosmetics", "ecommerce", "fashion"],
        "king": "Nykaa",
        "valuation": "$7B+",
        "market": "India",
        "description": "India's leading beauty e-commerce platform"
    },
    "mama": {
        "industries": ["beauty", "personal care", "natural", "d2c"],
        "king": "Mamaearth",
        "valuation": "$1.2B+",
        "market": "India",
        "description": "India's leading natural personal care brand"
    },
    "sugar": {
        "industries": ["beauty", "cosmetics", "makeup"],
        "king": "Sugar Cosmetics",
        "valuation": "$500M+",
        "market": "India",
        "description": "India's leading makeup brand"
    },
    "plum": {
        "industries": ["beauty", "skincare", "vegan"],
        "king": "Plum",
        "valuation": "$200M+",
        "market": "India",
        "description": "India's vegan beauty brand"
    },
    
    # ==================== HEALTHTECH ====================
    "practo": {
        "industries": ["health", "doctor", "appointment", "telemedicine"],
        "king": "Practo",
        "valuation": "$600M+",
        "market": "India",
        "description": "India's largest healthcare platform"
    },
    "pharmeasy": {
        "industries": ["pharmacy", "medicine", "health", "ecommerce"],
        "king": "PharmEasy",
        "valuation": "$5.6B+",
        "market": "India",
        "description": "India's largest e-pharmacy"
    },
    "netmeds": {
        "industries": ["pharmacy", "medicine", "health"],
        "king": "Netmeds",
        "valuation": "Reliance subsidiary",
        "market": "India",
        "description": "Online pharmacy platform"
    },
    "cult": {
        "industries": ["fitness", "gym", "wellness", "health"],
        "king": "Cult.fit",
        "valuation": "$1.5B+",
        "market": "India",
        "description": "India's leading fitness platform"
    },
    
    # ==================== REAL ESTATE ====================
    "magic": {
        "industries": ["real estate", "property", "housing"],
        "king": "MagicBricks",
        "valuation": "$500M+",
        "market": "India",
        "description": "India's leading real estate portal"
    },
    "housing": {
        "industries": ["real estate", "property", "rental"],
        "king": "Housing.com",
        "valuation": "$300M+",
        "market": "India",
        "description": "Real estate search platform"
    },
    "nobroker": {
        "industries": ["real estate", "rental", "property"],
        "king": "NoBroker",
        "valuation": "$1B+",
        "market": "India",
        "description": "Brokerage-free real estate platform"
    },
    
    # ==================== HR / JOBS ====================
    "naukri": {
        "industries": ["jobs", "recruitment", "hr", "career"],
        "king": "Naukri",
        "valuation": "$6B+ (Info Edge)",
        "market": "India",
        "description": "India's largest job portal"
    },
    "indeed": {
        "industries": ["jobs", "recruitment", "hr"],
        "king": "Indeed",
        "valuation": "Recruit Holdings subsidiary",
        "market": "Global",
        "description": "World's largest job site"
    },
    
    # ==================== NEWS / MEDIA ====================
    "times": {
        "industries": ["news", "media", "publishing"],
        "king": "Times of India / NY Times",
        "valuation": "$5B+ / $8B+",
        "market": "India / Global",
        "description": "Major news publications"
    },
    "news": {
        "industries": ["news", "media", "publishing"],
        "king": "NewsBreak / News18 / etc",
        "valuation": "Various",
        "market": "Global",
        "description": "News platforms"
    },
    "money": {
        "industries": ["finance", "news", "stock market", "investing"],
        "king": "Moneycontrol",
        "valuation": "$500M+",
        "market": "India",
        "description": "India's largest financial news platform"
    },
    
    # ==================== AUTOMOTIVE / EV ====================
    "tesla": {
        "industries": ["ev", "electric", "automotive", "energy"],
        "king": "Tesla",
        "valuation": "$700B+",
        "market": "Global",
        "description": "World's most valuable automaker"
    },
    "ather": {
        "industries": ["ev", "electric scooter", "mobility"],
        "king": "Ather",
        "valuation": "$1B+",
        "market": "India",
        "description": "India's leading electric scooter brand"
    },
    
    # ==================== DATING ====================
    "tinder": {
        "industries": ["dating", "social", "matchmaking"],
        "king": "Tinder",
        "valuation": "Match Group subsidiary",
        "market": "Global",
        "description": "World's most popular dating app"
    },
    "bumble": {
        "industries": ["dating", "social", "matchmaking"],
        "king": "Bumble",
        "valuation": "$5B+",
        "market": "Global",
        "description": "Women-first dating app"
    },
    "hinge": {
        "industries": ["dating", "social", "matchmaking"],
        "king": "Hinge",
        "valuation": "Match Group subsidiary",
        "market": "Global",
        "description": "Dating app designed to be deleted"
    },
}


def extract_root_morpheme(brand_name: str) -> Dict:
    """
    THREAD 1 - DECONSTRUCTION: Extract the root morpheme from a brand name.
    
    Steps:
    1. Strip common startup suffixes (-ly, -ify, -ai, -io, -oy, etc.)
    2. Isolate the root word
    3. Return both root and stripped suffixes
    """
    name = brand_name.lower().strip()
    original = name
    stripped_suffixes = []
    
    # Try stripping suffixes (longest first, only strip if something remains)
    for suffix in sorted(STARTUP_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix) and len(name) > len(suffix) + 2:  # Keep at least 3 chars
            root_candidate = name[:-len(suffix)]
            # Verify root has at least 3 consonants/vowels and isn't just noise
            if len(root_candidate) >= 3:
                stripped_suffixes.append(suffix)
                name = root_candidate
                break  # Only strip one suffix
    
    # Also try common prefixes that might obscure the root
    common_prefixes = ["my", "the", "get", "go", "i", "e", "u", "a"]
    for prefix in common_prefixes:
        if name.startswith(prefix) and len(name) > len(prefix) + 2:
            potential_root = name[len(prefix):]
            # Check if the remaining part is a known root
            if potential_root in CATEGORY_KINGS:
                name = potential_root
                stripped_suffixes.insert(0, f"{prefix}-")
                break
    
    return {
        "original": original,
        "root": name,
        "stripped_suffixes": stripped_suffixes,
        "transformation": f"{original} → {name}" if name != original else "No transformation"
    }


def find_category_king(root: str, industry: str, category: str) -> Optional[Dict]:
    """
    THREAD 1 - CATEGORY KING DETECTION: Check if root word has a dominant player in the industry.
    
    Returns the Category King info if found, None otherwise.
    """
    # Normalize inputs
    root_lower = root.lower().strip()
    industry_lower = industry.lower() if industry else ""
    category_lower = category.lower() if category else ""
    combined_context = f"{industry_lower} {category_lower}"
    
    # Direct root match
    if root_lower in CATEGORY_KINGS:
        king_data = CATEGORY_KINGS[root_lower]
        # Check if any industry keywords match
        for king_industry in king_data["industries"]:
            if king_industry in combined_context or combined_context in king_industry:
                return {
                    "matched_root": root_lower,
                    "king": king_data["king"],
                    "valuation": king_data["valuation"],
                    "market": king_data["market"],
                    "description": king_data["description"],
                    "match_type": "DIRECT_ROOT_MATCH",
                    "industry_match": True
                }
        
        # Even if industry doesn't match exactly, still a concern for famous roots
        return {
            "matched_root": root_lower,
            "king": king_data["king"],
            "valuation": king_data["valuation"],
            "market": king_data["market"],
            "description": king_data["description"],
            "match_type": "ROOT_MATCH_DIFFERENT_INDUSTRY",
            "industry_match": False
        }
    
    # Partial root match (root is contained in a king's root)
    for king_root, king_data in CATEGORY_KINGS.items():
        if len(root_lower) >= 4 and (root_lower in king_root or king_root in root_lower):
            lev_distance = Levenshtein.distance(root_lower, king_root)
            if lev_distance <= 2:  # Very close match
                for king_industry in king_data["industries"]:
                    if king_industry in combined_context:
                        return {
                            "matched_root": king_root,
                            "king": king_data["king"],
                            "valuation": king_data["valuation"],
                            "market": king_data["market"],
                            "description": king_data["description"],
                            "match_type": "PARTIAL_ROOT_MATCH",
                            "industry_match": True,
                            "levenshtein_distance": lev_distance
                        }
    
    return None


def calculate_algorithmic_scores(brand_name: str, competitor_name: str) -> Dict:
    """
    THREAD 2 - ALGORITHMIC MATCHING: Simulate Trademark Office Logic.
    
    Returns:
    - Levenshtein Distance (Risk if < 3)
    - Soundex/Phonetic codes (Risk if match)
    - Jaro-Winkler score (Risk if first 4 letters identical)
    """
    brand_lower = brand_name.lower().strip()
    competitor_lower = competitor_name.lower().strip()
    
    # 1. Levenshtein Distance
    lev_distance = Levenshtein.distance(brand_lower, competitor_lower)
    lev_risk = lev_distance < 3
    
    # 2. Soundex/Phonetic codes
    brand_soundex = jellyfish.soundex(brand_lower)
    competitor_soundex = jellyfish.soundex(competitor_lower)
    soundex_match = brand_soundex == competitor_soundex
    
    brand_metaphone = jellyfish.metaphone(brand_lower)
    competitor_metaphone = jellyfish.metaphone(competitor_lower)
    metaphone_match = brand_metaphone == competitor_metaphone
    
    phonetic_risk = soundex_match or metaphone_match
    
    # 3. Jaro-Winkler (prefix focus)
    jw_score = jellyfish.jaro_winkler_similarity(brand_lower, competitor_lower) * 100
    
    # Check first 4 letters
    prefix_match = brand_lower[:4] == competitor_lower[:4] if len(brand_lower) >= 4 and len(competitor_lower) >= 4 else False
    prefix_risk = prefix_match or jw_score >= 85
    
    return {
        "levenshtein": {
            "distance": lev_distance,
            "risk": lev_risk,
            "assessment": "NEAR" if lev_risk else "FAR"
        },
        "phonetic": {
            "brand_soundex": brand_soundex,
            "competitor_soundex": competitor_soundex,
            "soundex_match": soundex_match,
            "brand_metaphone": brand_metaphone,
            "competitor_metaphone": competitor_metaphone,
            "metaphone_match": metaphone_match,
            "risk": phonetic_risk,
            "assessment": "Yes" if phonetic_risk else "No"
        },
        "jaro_winkler": {
            "score": round(jw_score, 2),
            "prefix_match": prefix_match,
            "risk": prefix_risk,
            "assessment": "NEAR" if prefix_risk else "FAR"
        },
        "overall_algorithmic_risk": lev_risk or phonetic_risk or prefix_risk
    }


def check_linguistic_distinctiveness(brand_name: str, category: str) -> Dict:
    """
    THREAD 3 - LINGUISTICS: Global Sanity Check.
    
    Checks:
    1. Does the name describe the product (Descriptive)?
    2. Is it arbitrary/suggestive/fanciful?
    3. Any problematic translations?
    """
    brand_lower = brand_name.lower()
    category_lower = category.lower() if category else ""
    
    # Common descriptive words by industry
    DESCRIPTIVE_INDICATORS = {
        "fast": ["delivery", "food", "transport", "logistics"],
        "quick": ["delivery", "food", "commerce", "service"],
        "easy": ["service", "app", "booking", "payment"],
        "smart": ["tech", "app", "device", "home"],
        "best": ["any industry"],
        "top": ["any industry"],
        "super": ["any industry"],
        "mega": ["any industry"],
        "ultra": ["any industry"],
        "pro": ["any industry"],
        "prime": ["any industry"],
        "express": ["delivery", "logistics", "transport"],
        "instant": ["delivery", "payment", "service"],
        "direct": ["service", "sales", "commerce"],
        "fresh": ["food", "grocery", "produce"],
        "clean": ["cleaning", "laundry", "hygiene"],
        "safe": ["security", "finance", "insurance"],
        "care": ["health", "beauty", "wellness"],
        "fit": ["fitness", "health", "wellness"],
        "pay": ["payment", "finance", "banking"],
        "shop": ["retail", "ecommerce", "shopping"],
        "book": ["booking", "reservation", "travel"],
        "ride": ["transport", "taxi", "mobility"],
        "cab": ["transport", "taxi"],
        "taxi": ["transport"],
        "food": ["food", "restaurant", "delivery"],
        "meal": ["food", "restaurant"],
        "health": ["health", "medical", "wellness"],
        "med": ["medical", "health", "pharma"],
        "tech": ["technology", "software"],
        "cloud": ["technology", "software", "storage"],
        "data": ["technology", "analytics"],
        "learn": ["education", "edtech"],
        "edu": ["education", "edtech"],
        "home": ["real estate", "interior", "services"],
        "money": ["finance", "payment", "investment"],
        "cash": ["finance", "payment"],
        "stock": ["trading", "investment"],
        "trade": ["trading", "commerce"],
        "travel": ["travel", "tourism"],
        "hotel": ["hospitality", "accommodation"],
        "stay": ["hospitality", "accommodation"],
        "rent": ["rental", "real estate"],
        "job": ["recruitment", "career"],
        "work": ["employment", "productivity"],
    }
    
    # Check for descriptive words
    is_descriptive = False
    descriptive_words_found = []
    
    for word, industries in DESCRIPTIVE_INDICATORS.items():
        if word in brand_lower:
            if "any industry" in industries or any(ind in category_lower for ind in industries):
                is_descriptive = True
                descriptive_words_found.append(word)
    
    # Determine distinctiveness level
    if is_descriptive and len(descriptive_words_found) >= 2:
        distinctiveness = "GENERIC"
        strength = "Unregistrable - Too generic"
    elif is_descriptive:
        distinctiveness = "DESCRIPTIVE"
        strength = "Weak - Hard to trademark, requires secondary meaning"
    elif any(brand_lower.startswith(prefix) for prefix in ["my", "the", "get", "go"]):
        distinctiveness = "SUGGESTIVE"
        strength = "Moderate - May require explanation of connection"
    elif len(brand_lower) <= 4 or not any(c in brand_lower for c in 'aeiou'):
        distinctiveness = "ARBITRARY"
        strength = "Strong - Unrelated to product, good protection"
    else:
        distinctiveness = "FANCIFUL"
        strength = "Strongest - Invented word, maximum protection"
    
    # Problematic translations (common issues)
    TRANSLATION_ISSUES = {
        "nova": "Means 'doesn't go' in Spanish (famous Chevy Nova case)",
        "mist": "Means 'manure' in German",
        "gift": "Means 'poison' in German",
        "bite": "Sounds like 'bitte' (please) in German",
        "pet": "Means 'fart' in French",
        "con": "Vulgar in Spanish",
        "fart": "Means 'speed' in Swedish but vulgar in English",
        "puff": "Slang for brothel in German",
        "sin": "Religious implications in multiple languages",
        "kaka": "Means 'poop' in several languages",
        "baka": "Means 'stupid' in Japanese",
        "culo": "Vulgar in Spanish/Italian",
        "ass": "Universal English issue",
    }
    
    translation_issues = []
    for word, issue in TRANSLATION_ISSUES.items():
        if word in brand_lower:
            translation_issues.append({"word": word, "issue": issue})
    
    return {
        "distinctiveness": distinctiveness,
        "strength": strength,
        "descriptive_words_found": descriptive_words_found,
        "is_descriptive": is_descriptive,
        "translation_issues": translation_issues,
        "meaning_check": translation_issues[0]["issue"] if translation_issues else "No known issues"
    }


def calculate_rightname_score(
    category_king_result: Optional[Dict],
    algorithmic_result: Optional[Dict],
    linguistic_result: Dict
) -> Dict:
    """
    THREAD 4 - SCORING ALGORITHM: Calculate the Rightname Availability Score (0-100).
    
    Scoring Bands:
    - 0-40 (Red): Direct Conflict or Generic Term
    - 41-70 (Yellow): Partial overlap, crowded namespace, weak distinctiveness
    - 71-100 (Green): Unique, arbitrary, distinct root, low phonetic conflict
    """
    score = 100  # Start with perfect score
    deductions = []
    
    # ===== CATEGORY KING DEDUCTIONS (Heaviest) =====
    if category_king_result:
        if category_king_result.get("industry_match"):
            # Same root + Same industry = FATAL
            score -= 70
            deductions.append({
                "reason": f"Direct root conflict with {category_king_result['king']}",
                "points": -70,
                "severity": "CRITICAL"
            })
        else:
            # Same root + Different industry = Still risky
            score -= 40
            deductions.append({
                "reason": f"Root word associated with {category_king_result['king']} (different industry)",
                "points": -40,
                "severity": "HIGH"
            })
    
    # ===== ALGORITHMIC DEDUCTIONS =====
    if algorithmic_result:
        if algorithmic_result["levenshtein"]["risk"]:
            score -= 25
            deductions.append({
                "reason": f"Levenshtein distance < 3 (too similar spelling)",
                "points": -25,
                "severity": "HIGH"
            })
        
        if algorithmic_result["phonetic"]["risk"]:
            score -= 20
            deductions.append({
                "reason": "Phonetic match (sounds like competitor)",
                "points": -20,
                "severity": "HIGH"
            })
        
        if algorithmic_result["jaro_winkler"]["prefix_match"]:
            score -= 15
            deductions.append({
                "reason": "First 4 letters identical to competitor",
                "points": -15,
                "severity": "MEDIUM"
            })
    
    # ===== LINGUISTIC DEDUCTIONS =====
    if linguistic_result["distinctiveness"] == "GENERIC":
        score -= 50
        deductions.append({
            "reason": "Generic term - cannot be trademarked",
            "points": -50,
            "severity": "CRITICAL"
        })
    elif linguistic_result["distinctiveness"] == "DESCRIPTIVE":
        score -= 25
        deductions.append({
            "reason": "Descriptive name - weak trademark protection",
            "points": -25,
            "severity": "MEDIUM"
        })
    elif linguistic_result["distinctiveness"] == "SUGGESTIVE":
        score -= 10
        deductions.append({
            "reason": "Suggestive name - moderate protection",
            "points": -10,
            "severity": "LOW"
        })
    
    if linguistic_result["translation_issues"]:
        score -= 15
        deductions.append({
            "reason": f"Translation issue: {linguistic_result['translation_issues'][0]['issue']}",
            "points": -15,
            "severity": "MEDIUM"
        })
    
    # Ensure score is within bounds
    score = max(0, min(100, score))
    
    # Determine verdict
    if score <= 40:
        verdict = "HIGH RISK"
        color = "RED"
    elif score <= 70:
        verdict = "CAUTION"
        color = "YELLOW"
    else:
        verdict = "AVAILABLE"
        color = "GREEN"
    
    return {
        "score": score,
        "verdict": verdict,
        "color": color,
        "deductions": deductions,
        "total_deductions": sum(d["points"] for d in deductions)
    }


def deep_trace_analysis(brand_name: str, industry: str, category: str) -> Dict:
    """
    MASTER FUNCTION: Rightname.ai Deep-Trace Analysis
    
    Executes 4 simultaneous logic threads:
    1. DECONSTRUCTION - Root extraction & Category King detection
    2. ALGORITHMIC MATCHING - Levenshtein, Soundex, Jaro-Winkler
    3. LINGUISTICS - Distinctiveness & translation checks
    4. SCORING - Calculate final Rightname Score
    
    Returns comprehensive brand safety analysis.
    """
    logger.info(f"🔍 DEEP-TRACE ANALYSIS started for '{brand_name}' in {category}")
    
    # ===== THREAD 1: DECONSTRUCTION =====
    root_analysis = extract_root_morpheme(brand_name)
    logger.info(f"   ROOT EXTRACTION: {root_analysis['transformation']}")
    
    category_king = find_category_king(root_analysis["root"], industry, category)
    if category_king:
        logger.info(f"   ⚠️ CATEGORY KING FOUND: {category_king['king']} ({category_king['match_type']})")
    else:
        logger.info(f"   ✅ No Category King conflict for root '{root_analysis['root']}'")
    
    # ===== THREAD 2: ALGORITHMIC MATCHING =====
    algorithmic_result = None
    competitor_name = None
    if category_king:
        competitor_name = category_king["king"].split("/")[0].split("(")[0].strip()  # Get first/primary name
        algorithmic_result = calculate_algorithmic_scores(brand_name, competitor_name)
        logger.info(f"   ALGORITHMIC: Lev={algorithmic_result['levenshtein']['distance']}, " +
                   f"Phonetic={algorithmic_result['phonetic']['assessment']}, " +
                   f"JW={algorithmic_result['jaro_winkler']['score']}%")
    
    # ===== THREAD 3: LINGUISTICS =====
    linguistic_result = check_linguistic_distinctiveness(brand_name, category)
    logger.info(f"   LINGUISTICS: {linguistic_result['distinctiveness']} - {linguistic_result['strength']}")
    
    # ===== THREAD 4: SCORING =====
    score_result = calculate_rightname_score(category_king, algorithmic_result, linguistic_result)
    logger.info(f"   📊 FINAL SCORE: {score_result['score']}/100 - {score_result['verdict']} ({score_result['color']})")
    
    # Build comprehensive result
    result = {
        "brand_name": brand_name,
        "industry": industry,
        "category": category,
        
        # Thread 1: Deconstruction
        "root_analysis": root_analysis,
        "category_king": category_king,
        
        # Thread 2: Algorithmic
        "algorithmic_analysis": algorithmic_result,
        "nearest_competitor": competitor_name,
        
        # Thread 3: Linguistics
        "linguistic_analysis": linguistic_result,
        
        # Thread 4: Scoring
        "score": score_result["score"],
        "verdict": score_result["verdict"],
        "color": score_result["color"],
        "deductions": score_result["deductions"],
        
        # Summary
        "critical_conflict": category_king["king"] if category_king and category_king.get("industry_match") else None,
        "should_reject": score_result["score"] <= 40,
        "analysis_summary": generate_analysis_summary(brand_name, category_king, algorithmic_result, linguistic_result, score_result)
    }
    
    return result


def generate_analysis_summary(
    brand_name: str,
    category_king: Optional[Dict],
    algorithmic_result: Optional[Dict],
    linguistic_result: Dict,
    score_result: Dict
) -> str:
    """Generate a human-readable summary of the Deep-Trace Analysis."""
    
    if category_king and category_king.get("industry_match"):
        return (f"🚨 CRITICAL: '{brand_name}' shares the root word with {category_king['king']} "
               f"({category_king['valuation']} valuation). In the same industry, this creates "
               f"unacceptable confusion and legal risk. Recommendation: ABANDON NAME.")
    
    if category_king and not category_king.get("industry_match"):
        return (f"⚠️ WARNING: '{brand_name}' shares root with {category_king['king']} but in different industry. "
               f"Cross-industry confusion risk exists. Proceed with caution and legal review.")
    
    if linguistic_result["distinctiveness"] == "GENERIC":
        return (f"🚨 CRITICAL: '{brand_name}' is too generic and cannot be trademarked. "
               f"Descriptive words found: {', '.join(linguistic_result['descriptive_words_found'])}. "
               f"Recommendation: Choose a more distinctive name.")
    
    if linguistic_result["distinctiveness"] == "DESCRIPTIVE":
        return (f"⚠️ WARNING: '{brand_name}' is descriptive and will have weak trademark protection. "
               f"Consider adding distinctive elements or choosing a more arbitrary name.")
    
    if score_result["score"] >= 71:
        return (f"✅ AVAILABLE: '{brand_name}' appears to be distinctive with no major conflicts detected. "
               f"Recommended to proceed with trademark search and registration.")
    
    return f"'{brand_name}' has some concerns. Review the detailed analysis before proceeding."


def format_deep_trace_report(analysis: Dict) -> str:
    """Format Deep-Trace Analysis as a Rightname.ai Report."""
    
    lines = [
        "",
        "=" * 70,
        "🛡️ RIGHTNAME.AI DEEP-TRACE ANALYSIS REPORT",
        "=" * 70,
        f"Brand Name: {analysis['brand_name']}",
        f"Category: {analysis['category']}",
        "",
        f"📊 THE SCORE: {analysis['score']}/100",
        f"🎯 VERDICT: {analysis['verdict']} ({analysis['color']})",
        "",
        "-" * 70,
        "1. 🚨 CRITICAL CONFLICT CHECK",
        "-" * 70,
    ]
    
    if analysis["critical_conflict"]:
        lines.extend([
            f"   Direct Competitor Match: {analysis['critical_conflict']}",
            f"   Conflict Type: Root Word + Same Industry",
            f"   Analysis: {analysis['analysis_summary']}"
        ])
    elif analysis["category_king"]:
        lines.extend([
            f"   Potential Conflict: {analysis['category_king']['king']}",
            f"   Conflict Type: {analysis['category_king']['match_type']}",
            f"   Analysis: {analysis['analysis_summary']}"
        ])
    else:
        lines.append("   ✅ No direct competitor match detected")
    
    lines.extend([
        "",
        "-" * 70,
        "2. 🧮 ALGORITHMIC STRESS TEST",
        "-" * 70,
    ])
    
    root = analysis["root_analysis"]
    lines.append(f"   Root Word: {root['root']} ({root['transformation']})")
    
    if analysis["algorithmic_analysis"]:
        alg = analysis["algorithmic_analysis"]
        lines.extend([
            f"   Spelling Distance: {alg['levenshtein']['assessment']} (Edit distance: {alg['levenshtein']['distance']})",
            f"   Phonetic Match: {alg['phonetic']['assessment']}",
            f"   Jaro-Winkler: {alg['jaro_winkler']['score']}%"
        ])
    else:
        lines.append("   No competitor found for algorithmic comparison")
    
    lines.extend([
        "",
        "-" * 70,
        "3. 🧠 LINGUISTIC & BRAND STRENGTH",
        "-" * 70,
    ])
    
    ling = analysis["linguistic_analysis"]
    lines.extend([
        f"   Distinctiveness: {ling['distinctiveness']}",
        f"   Strength: {ling['strength']}",
        f"   Meaning Check: {ling['meaning_check']}"
    ])
    
    if ling["descriptive_words_found"]:
        lines.append(f"   Descriptive Words: {', '.join(ling['descriptive_words_found'])}")
    
    lines.extend([
        "",
        "-" * 70,
        "4. 💡 RECOMMENDATION",
        "-" * 70,
    ])
    
    if analysis["score"] <= 40:
        lines.append("   🚫 ABANDON NAME - High legal risk detected")
    elif analysis["score"] <= 70:
        lines.append("   ⚠️ PROCEED WITH CAUTION - Address identified concerns")
    else:
        lines.append("   ✅ GREAT NAME - Proceed with trademark registration")
    
    lines.append(f"   {analysis['analysis_summary']}")
    
    lines.extend([
        "",
        "=" * 70,
        "Disclaimer: Rightname.ai provides AI-driven analysis, not legal advice.",
        "Consult a trademark attorney for final clearance.",
        "=" * 70,
        ""
    ])
    
    return "\n".join(lines)


# Test function
if __name__ == "__main__":
    # Test cases including the Rapidoy case
    test_cases = [
        ("Rapidoy", "Transport", "Ride-hailing"),
        ("Uberify", "Transport", "Ride-hailing"),
        ("Swiggify", "Food", "Food Delivery"),
        ("QuickCab", "Transport", "Taxi Service"),
        ("Zyntrix", "Technology", "AI Platform"),
        ("FastFood", "Food", "Restaurant"),
    ]
    
    for name, industry, category in test_cases:
        print(f"\n{'='*70}")
        print(f"Testing: {name} ({industry} / {category})")
        result = deep_trace_analysis(name, industry, category)
        print(format_deep_trace_report(result))
