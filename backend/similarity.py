"""
String Similarity Layer for Brand Name Analysis
Uses Levenshtein Distance + Jaro-Winkler to detect similar brand names
"""

import jellyfish
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein
from typing import List, Dict, Tuple, Optional
import re

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

# Major brands with common suffixes - for suffix-based conflict detection
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
    Check if the brand name shares a suffix with a major brand in the same industry.
    
    Examples:
    - "AuraKind" in pharma → matches "Mankind" due to "-kind" suffix
    - "HeadBook" in social media → matches "Facebook" due to "-book" suffix
    """
    input_lower = input_name.lower()
    conflicts = []
    
    # Determine which industry to check
    industry_key = None
    category_lower = category.lower() if category else ""
    
    # Map category to suffix industry
    if "pharma" in category_lower or "health" in industry.lower():
        industry_key = "Healthcare & Pharma"
    elif "social" in category_lower or "media" in category_lower or "platform" in category_lower:
        industry_key = "Social Media & Platforms"
    elif "finance" in industry.lower() or "bank" in category_lower:
        industry_key = "Finance & Banking"
    elif "tech" in industry.lower() or "software" in category_lower:
        industry_key = "Technology & Software"
    
    # Check against suffix-brand map (most important)
    for suffix, brands in SUFFIX_BRAND_MAP.items():
        if input_lower.endswith(suffix):
            for brand in brands:
                # Check if this brand is relevant to the industry
                is_relevant = True
                if suffix == "kind" and "pharma" not in category_lower and "health" not in industry.lower():
                    is_relevant = False
                if suffix in ["book", "gram", "tube", "tok", "chat"] and "social" not in category_lower and "media" not in category_lower:
                    is_relevant = False
                    
                if is_relevant:
                    conflicts.append({
                        "brand": brand,
                        "suffix": suffix,
                        "match_type": "SUFFIX_CONFLICT",
                        "explanation": f"'{input_name}' shares the '-{suffix}' suffix with '{brand}'. In the {category} space, this creates high confusion risk."
                    })
    
    return {
        "has_suffix_conflict": len(conflicts) > 0,
        "conflicts": conflicts
    }


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
    
    # NEW: Check for suffix conflicts (e.g., AuraKind vs Mankind, HeadBook vs Facebook)
    suffix_result = check_suffix_conflict(input_name, industry, category)
    if suffix_result["has_suffix_conflict"]:
        for conflict in suffix_result["conflicts"]:
            # Add to fatal conflicts
            results["fatal_conflicts"].append({
                "brand": conflict["brand"],
                "match_type": "SUFFIX_CONFLICT",
                "suffix": conflict["suffix"],
                "levenshtein": 0,  # Not applicable for suffix match
                "jaro_winkler": 0,
                "fuzzy_ratio": 0,
                "average_similarity": 0,
                "explanation": conflict["explanation"]
            })
            results["should_reject"] = True
            results["rejection_reason"] = f"FATAL: Suffix conflict - '{input_name}' shares '-{conflict['suffix']}' suffix with '{conflict['brand']}' in the same industry"
    
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
