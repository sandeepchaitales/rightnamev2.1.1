"""
Trademark Research Module
========================
Performs comprehensive trademark research using web search and data aggregation
to identify real trademark conflicts, company registrations, and legal precedents.

Mimics Perplexity's approach:
1. Generate strategic search queries
2. Execute web searches
3. Extract structured conflict data
4. Synthesize findings into actionable intelligence
"""

import logging
import asyncio
import re
import json
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TrademarkConflict:
    """Represents a discovered trademark conflict"""
    name: str
    source: str  # e.g., "IP India", "Tofler", "Web Search"
    conflict_type: str  # "trademark_application", "registered_company", "common_law", "international"
    application_number: Optional[str] = None
    status: Optional[str] = None  # "REGISTERED", "PENDING", "OBJECTED", "ABANDONED"
    owner: Optional[str] = None
    class_number: Optional[str] = None
    filing_date: Optional[str] = None
    similarity_score: Optional[str] = None  # "HIGH", "MEDIUM", "LOW"
    industry_overlap: Optional[str] = None
    geographic_overlap: Optional[str] = None
    risk_level: str = "MEDIUM"  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    details: Optional[str] = None
    url: Optional[str] = None


@dataclass
class CompanyConflict:
    """Represents a discovered company with similar name"""
    name: str
    cin: Optional[str] = None  # Corporate Identification Number
    status: str = "ACTIVE"  # "ACTIVE", "INACTIVE", "DISSOLVED"
    incorporation_date: Optional[str] = None
    industry: Optional[str] = None
    state: Optional[str] = None
    source: str = "Company Registry"
    overlap_analysis: Optional[str] = None
    risk_level: str = "MEDIUM"
    url: Optional[str] = None


@dataclass
class LegalPrecedent:
    """Represents a relevant legal case or precedent"""
    case_name: str
    court: Optional[str] = None
    year: Optional[str] = None
    relevance: str = ""  # Why this case is relevant
    outcome: Optional[str] = None
    key_principle: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None


@dataclass
class TrademarkResearchResult:
    """Complete trademark research findings"""
    brand_name: str
    industry: str
    category: str
    countries: List[str]
    research_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Conflicts discovered
    trademark_conflicts: List[TrademarkConflict] = field(default_factory=list)
    company_conflicts: List[CompanyConflict] = field(default_factory=list)
    common_law_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Legal analysis
    legal_precedents: List[LegalPrecedent] = field(default_factory=list)
    nice_classification: Optional[Dict[str, Any]] = None
    
    # Risk assessment
    overall_risk_score: int = 5  # 1-10
    registration_success_probability: int = 50  # 0-100%
    opposition_probability: int = 50  # 0-100%
    
    # Summary
    critical_conflicts_count: int = 0
    high_risk_conflicts_count: int = 0
    total_conflicts_found: int = 0
    
    # Raw search data for LLM synthesis
    search_results_summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "brand_name": self.brand_name,
            "industry": self.industry,
            "category": self.category,
            "countries": self.countries,
            "research_timestamp": self.research_timestamp,
            "trademark_conflicts": [asdict(c) for c in self.trademark_conflicts],
            "company_conflicts": [asdict(c) for c in self.company_conflicts],
            "common_law_conflicts": self.common_law_conflicts,
            "legal_precedents": [asdict(p) for p in self.legal_precedents],
            "nice_classification": self.nice_classification,
            "overall_risk_score": self.overall_risk_score,
            "registration_success_probability": self.registration_success_probability,
            "opposition_probability": self.opposition_probability,
            "critical_conflicts_count": self.critical_conflicts_count,
            "high_risk_conflicts_count": self.high_risk_conflicts_count,
            "total_conflicts_found": self.total_conflicts_found,
            "search_results_summary": self.search_results_summary
        }


# Nice Classification mapping for common categories
NICE_CLASSIFICATION = {
    "fashion": {"class": 25, "description": "Clothing, footwear, headgear"},
    "apparel": {"class": 25, "description": "Clothing, footwear, headgear"},
    "streetwear": {"class": 25, "description": "Clothing, footwear, headgear"},
    "clothing": {"class": 25, "description": "Clothing, footwear, headgear"},
    "footwear": {"class": 25, "description": "Clothing, footwear, headgear"},
    "jewelry": {"class": 14, "description": "Precious metals, jewelry, watches"},
    "cosmetics": {"class": 3, "description": "Cosmetics, cleaning preparations"},
    "skincare": {"class": 3, "description": "Cosmetics, cleaning preparations"},
    "beauty": {"class": 3, "description": "Cosmetics, cleaning preparations"},
    "software": {"class": 9, "description": "Scientific apparatus, computers, software"},
    "technology": {"class": 9, "description": "Scientific apparatus, computers, software"},
    "tech": {"class": 9, "description": "Scientific apparatus, computers, software"},
    "app": {"class": 9, "description": "Scientific apparatus, computers, software"},
    "saas": {"class": 42, "description": "Scientific and technological services"},
    "food": {"class": 29, "description": "Meat, fish, preserved foods"},
    "restaurant": {"class": 43, "description": "Food and drink services"},
    "cafe": {"class": 43, "description": "Food and drink services"},
    "beverages": {"class": 32, "description": "Beers, mineral waters, soft drinks"},
    "pharmaceutical": {"class": 5, "description": "Pharmaceuticals, medical preparations"},
    "pharma": {"class": 5, "description": "Pharmaceuticals, medical preparations"},
    "healthcare": {"class": 44, "description": "Medical and healthcare services"},
    "education": {"class": 41, "description": "Education, training, entertainment"},
    "edtech": {"class": 41, "description": "Education, training, entertainment"},
    "finance": {"class": 36, "description": "Insurance, financial affairs"},
    "fintech": {"class": 36, "description": "Insurance, financial affairs"},
    "banking": {"class": 36, "description": "Insurance, financial affairs"},
    "real estate": {"class": 36, "description": "Insurance, financial affairs, real estate"},
    "automotive": {"class": 12, "description": "Vehicles, apparatus for locomotion"},
    "toys": {"class": 28, "description": "Games, toys, sporting goods"},
    "gaming": {"class": 28, "description": "Games, toys, sporting goods"},
    "furniture": {"class": 20, "description": "Furniture, mirrors, picture frames"},
    "home decor": {"class": 20, "description": "Furniture, mirrors, picture frames"},
}


# Known trademark data for common searches (cache for faster results)
KNOWN_TRADEMARK_DATA = {
    "luminara": {
        "trademarks": [
            {
                "name": "Luminara",
                "application_number": "7026544",
                "owner": "Luminara Legacy Pvt Ltd",
                "class_number": "1",
                "status": "FORMALITIES CHECK PASS",
                "filing_date": "26 May 2025",
                "source": "IP India / QuickCompany",
                "url": "https://www.quickcompany.in/trademarks/7026544-61bd-luminara-legacy-pvt-ltd"
            },
            {
                "name": "Luminara Elixir",
                "application_number": "6346642",
                "owner": "Usama Fakhruddin Qureshi",
                "class_number": "3",
                "status": "OBJECTED",
                "filing_date": "15 March 2024",
                "source": "IP India / IndiaFilings",
                "url": "https://www.indiafilings.com/search/luminara-elixir-tm-6346642"
            }
        ],
        "companies": [
            {
                "name": "Luminara Enterprises Private Limited",
                "cin": "U85500TZ2025PTC036174",
                "status": "ACTIVE",
                "incorporation_date": "September 2025",
                "industry": "Health Services / Custom Apparel",
                "state": "Tamil Nadu / Telangana",
                "source": "Tofler",
                "url": "https://www.tofler.in/luminara-enterprises-private-limited/company/U85500TZ2025PTC036174"
            },
            {
                "name": "Luminara Legacy Private Limited",
                "cin": "U47737TS2025PTC192828",
                "status": "ACTIVE",
                "incorporation_date": "2025",
                "industry": "Agriculture / Chemicals",
                "state": "Telangana",
                "source": "AllIndiaITR",
                "url": "https://www.allindiaitr.com/company/luminara-legacy-private-limited/U47737TS2025PTC192828"
            },
            {
                "name": "Luminara Solutions Private Limited",
                "cin": "U62011KA2025PTC210346",
                "status": "ACTIVE",
                "incorporation_date": "31 Oct 2025",
                "industry": "IT Services",
                "state": "Karnataka",
                "source": "IndiaFilings",
                "url": "https://www.indiafilings.com/search/luminara-solutions-private-limited-cin-U62011KA2025PTC210346"
            }
        ],
        "common_law": [
            {
                "name": "Luminarae Clothing",
                "platform": "Website/E-commerce",
                "url": "https://luminaraeclothing.com/",
                "industry_match": True,
                "risk_level": "MEDIUM"
            }
        ]
    },
    "zara": {
        "trademarks": [
            {
                "name": "ZARA",
                "application_number": "Multiple",
                "owner": "Industria de Diseño Textil, S.A. (Inditex)",
                "class_number": "25, 35, 18",
                "status": "REGISTERED",
                "filing_date": "Various",
                "source": "WIPO / IP India",
                "url": "https://www.wipo.int/madrid/monitor/en/"
            }
        ],
        "companies": [
            {
                "name": "Zara India Private Limited",
                "cin": "Multiple entities",
                "status": "ACTIVE",
                "industry": "Fashion Retail",
                "state": "Multiple",
                "source": "MCA",
                "url": "https://www.mca.gov.in/"
            }
        ]
    }
}

# Legal precedents database - COUNTRY SPECIFIC
LEGAL_PRECEDENTS_DB = {
    # ============ USA PRECEDENTS ============
    "USA": {
        "phonetic_similarity": [
            {
                "case_name": "Polaroid Corp. v. Polarad Electronics Corp.",
                "court": "U.S. Second Circuit Court of Appeals",
                "year": "1961",
                "relevance": "Established the 8-factor test for trademark likelihood of confusion analysis",
                "key_principle": "Multi-factor analysis including similarity of marks, proximity of goods, and buyer sophistication"
            },
            {
                "case_name": "AMF Inc. v. Sleekcraft Boats",
                "court": "U.S. Ninth Circuit Court of Appeals",
                "year": "1979",
                "relevance": "Set standard for likelihood of confusion in similar product markets",
                "key_principle": "Sound, sight, and meaning test for determining mark similarity"
            },
            {
                "case_name": "In re E.I. DuPont DeNemours & Co.",
                "court": "U.S. Court of Customs and Patent Appeals",
                "year": "1973",
                "relevance": "Established 13-factor test for trademark registration conflicts",
                "key_principle": "DuPont factors are the standard for USPTO trademark examination"
            }
        ],
        "fashion": [
            {
                "case_name": "Christian Louboutin S.A. v. Yves Saint Laurent America",
                "court": "U.S. Second Circuit Court of Appeals",
                "year": "2012",
                "relevance": "Protection of distinctive fashion elements (red sole trademark)",
                "key_principle": "Single color can function as trademark in fashion industry"
            }
        ],
        "general": [
            {
                "case_name": "Two Pesos, Inc. v. Taco Cabana, Inc.",
                "court": "U.S. Supreme Court",
                "year": "1992",
                "relevance": "Landmark case on trade dress protection without secondary meaning",
                "key_principle": "Inherently distinctive trade dress is protectable without proof of secondary meaning"
            }
        ]
    },
    # ============ INDIA PRECEDENTS ============
    "India": {
        "phonetic_similarity": [
            {
                "case_name": "M/S Lakme Ltd. v. M/S Subhash Trading",
                "court": "Delhi High Court",
                "year": "1996",
                "relevance": "Marks 'Lakme' and 'LikeMe' were found phonetically similar despite spelling differences",
                "key_principle": "Phonetic similarity alone can constitute grounds for infringement"
            },
            {
                "case_name": "Consitex SA v. Kamini Jain",
                "court": "Delhi High Court",
                "year": "2019",
                "relevance": "Marks 'ZEGNA' and 'JENYA' were ruled phonetically similar",
                "key_principle": "Visual dissimilarity does not negate phonetic confusion"
            },
            {
                "case_name": "FMI Limited v. Midas Touch Metalloys",
                "court": "Delhi High Court",
                "year": "2018",
                "relevance": "Marks 'INDI' and 'INDEED' found phonetically and structurally similar",
                "key_principle": "Partial phonetic overlap in same industry creates confusion risk"
            }
        ],
        "fashion": [
            {
                "case_name": "Adidas AG v. Ayush Chaddha",
                "court": "Delhi High Court",
                "year": "2021",
                "relevance": "Famous brand protection in fashion/sportswear",
                "key_principle": "Well-known marks get cross-category protection"
            }
        ],
        "general": [
            {
                "case_name": "Cadila Healthcare v. Cadila Pharmaceuticals",
                "court": "Supreme Court of India",
                "year": "2001",
                "relevance": "Landmark case on trademark similarity assessment",
                "key_principle": "Average consumer with imperfect recollection test"
            }
        ]
    },
    # ============ UK PRECEDENTS ============
    "UK": {
        "phonetic_similarity": [
            {
                "case_name": "Sabel BV v. Puma AG",
                "court": "European Court of Justice (applicable in UK)",
                "year": "1997",
                "relevance": "Standard for assessing likelihood of confusion between marks",
                "key_principle": "Global appreciation of visual, aural, and conceptual similarity"
            },
            {
                "case_name": "Specsavers International Healthcare v. Asda Stores",
                "court": "UK Court of Appeal",
                "year": "2012",
                "relevance": "Protection of well-known marks against similar branding",
                "key_principle": "Average consumer comparison considering imperfect recollection"
            },
            {
                "case_name": "Reed Executive Plc v. Reed Business Information Ltd",
                "court": "UK Court of Appeal",
                "year": "2004",
                "relevance": "Confusion analysis for identical words in different business contexts",
                "key_principle": "Similarity of services and customer overlap determines infringement"
            }
        ],
        "fashion": [
            {
                "case_name": "Burberry Ltd v. J.C. Trading Ltd",
                "court": "UK High Court",
                "year": "2014",
                "relevance": "Protection of iconic fashion patterns and designs",
                "key_principle": "Check patterns can be protected as registered trademarks"
            }
        ],
        "general": [
            {
                "case_name": "Arsenal Football Club Plc v. Reed",
                "court": "UK High Court / ECJ",
                "year": "2003",
                "relevance": "Landmark case on trademark use and origin function",
                "key_principle": "Trademark protects the guarantee of origin to consumers"
            }
        ]
    },
    # ============ EU PRECEDENTS ============
    "EU": {
        "phonetic_similarity": [
            {
                "case_name": "Sabel BV v. Puma AG",
                "court": "European Court of Justice",
                "year": "1997",
                "relevance": "Foundational case for EU trademark confusion analysis",
                "key_principle": "Global appreciation considering visual, aural, and conceptual similarity"
            },
            {
                "case_name": "Lloyd Schuhfabrik Meyer v. Klijsen Handel",
                "court": "European Court of Justice",
                "year": "1999",
                "relevance": "Standard for assessing similarity of marks",
                "key_principle": "Average consumer is reasonably well-informed and circumspect"
            },
            {
                "case_name": "Canon Kabushiki Kaisha v. Metro-Goldwyn-Mayer Inc.",
                "court": "European Court of Justice",
                "year": "1998",
                "relevance": "Relationship between mark similarity and goods similarity",
                "key_principle": "Lesser degree of similarity between goods may be offset by greater similarity between marks"
            }
        ],
        "fashion": [
            {
                "case_name": "Adidas-Salomon AG v. Fitnessworld Trading Ltd",
                "court": "European Court of Justice",
                "year": "2003",
                "relevance": "Protection of three-stripe mark in sportswear",
                "key_principle": "Well-known marks protected against dilution even without confusion"
            }
        ],
        "general": [
            {
                "case_name": "L'Oréal SA v. Bellure NV",
                "court": "European Court of Justice",
                "year": "2009",
                "relevance": "Landmark case on trademark dilution and unfair advantage",
                "key_principle": "Taking unfair advantage of reputation is infringement even without confusion"
            }
        ]
    },
    # ============ CANADA PRECEDENTS ============
    "Canada": {
        "phonetic_similarity": [
            {
                "case_name": "Masterpiece Inc. v. Alavida Lifestyles Inc.",
                "court": "Supreme Court of Canada",
                "year": "2011",
                "relevance": "Leading case on trademark confusion analysis in Canada",
                "key_principle": "First impression and imperfect recollection of average consumer"
            },
            {
                "case_name": "Veuve Clicquot Ponsardin v. Boutiques Cliquot Ltée",
                "court": "Supreme Court of Canada",
                "year": "2006",
                "relevance": "Famous marks protection and dilution analysis",
                "key_principle": "Famous marks entitled to broader protection against confusion"
            }
        ],
        "general": [
            {
                "case_name": "Mattel Inc. v. 3894207 Canada Inc.",
                "court": "Supreme Court of Canada",
                "year": "2006",
                "relevance": "Standard for trademark confusion and famous marks",
                "key_principle": "Surrounding circumstances test for likelihood of confusion"
            }
        ]
    },
    # ============ AUSTRALIA PRECEDENTS ============
    "Australia": {
        "phonetic_similarity": [
            {
                "case_name": "Registrar of Trade Marks v. Woolworths Ltd",
                "court": "Federal Court of Australia",
                "year": "1999",
                "relevance": "Standard for deceptive similarity assessment",
                "key_principle": "Ordinary person with imperfect recollection test"
            },
            {
                "case_name": "Shell Co. of Australia Ltd v. Esso Standard Oil (Australia) Ltd",
                "court": "High Court of Australia",
                "year": "1963",
                "relevance": "Foundational case on trademark deceptive similarity",
                "key_principle": "Side-by-side comparison is not the test; imperfect recollection applies"
            }
        ],
        "general": [
            {
                "case_name": "Southern Cross Refrigerating Co v Toowoomba Foundry Pty Ltd",
                "court": "High Court of Australia",
                "year": "1954",
                "relevance": "Landmark case defining substantial identity of trademarks",
                "key_principle": "Essential features comparison for mark similarity"
            }
        ]
    }
}

# Alias mappings for country name variations
COUNTRY_ALIASES = {
    "United States": "USA",
    "US": "USA",
    "America": "USA",
    "United Kingdom": "UK",
    "Britain": "UK",
    "Great Britain": "UK",
    "England": "UK",
    "European Union": "EU",
    "Europe": "EU",
    "Germany": "EU",
    "France": "EU",
    "Italy": "EU",
    "Spain": "EU",
    "Netherlands": "EU",
}


def get_nice_classification(category: str, industry: str = "") -> Dict[str, Any]:
    """Get Nice Classification for a category/industry"""
    search_terms = [category.lower(), industry.lower()]
    
    for term in search_terms:
        for key, value in NICE_CLASSIFICATION.items():
            if key in term or term in key:
                return {
                    "class_number": value["class"],
                    "class_description": value["description"],
                    "matched_term": key
                }
    
    # Default to Class 35 (Advertising, business management) if no match
    return {
        "class_number": 35,
        "class_description": "Advertising, business management, office functions",
        "matched_term": "general business"
    }


def generate_search_queries(brand_name: str, industry: str, category: str, countries: List[str]) -> List[Dict[str, str]]:
    """
    Generate strategic search queries for trademark research.
    Mimics Perplexity's query generation strategy.
    """
    queries = []
    
    # Get phonetic variants
    phonetic_variants = generate_phonetic_variants(brand_name)
    
    # Primary country (first in list)
    primary_country = countries[0] if countries else "India"
    
    # Batch 1: Direct trademark searches
    queries.extend([
        {
            "query": f'"{brand_name}" trademark registered {primary_country}',
            "purpose": "Find registered trademarks with exact name"
        },
        {
            "query": f'"{brand_name}" trademark application status',
            "purpose": "Find pending trademark applications"
        },
        {
            "query": f'{brand_name} trademark class {get_nice_classification(category, industry)["class_number"]}',
            "purpose": "Find trademarks in same Nice class"
        }
    ])
    
    # Batch 2: Brand/business searches
    queries.extend([
        {
            "query": f'"{brand_name}" brand {industry}',
            "purpose": "Find existing brands with same name in industry"
        },
        {
            "query": f'"{brand_name}" {category} company',
            "purpose": "Find companies operating with this name"
        },
        {
            "query": f'{brand_name} {category} existing brands competitors',
            "purpose": "Find market competitors with similar names"
        }
    ])
    
    # Batch 3: Company registry searches
    queries.extend([
        {
            "query": f'"{brand_name}" private limited company {primary_country}',
            "purpose": "Find registered companies"
        },
        {
            "query": f'site:tofler.in "{brand_name}"',
            "purpose": "Search Tofler company database"
        },
        {
            "query": f'site:zaubacorp.com "{brand_name}"',
            "purpose": "Search Zauba Corp company database"
        }
    ])
    
    # Batch 4: Phonetic similarity searches
    if phonetic_variants:
        variant_str = " OR ".join([f'"{v}"' for v in phonetic_variants[:3]])
        queries.append({
            "query": f'({variant_str}) trademark {primary_country} {industry}',
            "purpose": "Find phonetically similar trademarks"
        })
    
    # Batch 5: Legal precedent searches
    queries.extend([
        {
            "query": f'{primary_country} trademark phonetic similarity legal case {category}',
            "purpose": "Find relevant legal precedents"
        },
        {
            "query": f'trademark opposition {category} {primary_country} case law',
            "purpose": "Find opposition case precedents"
        }
    ])
    
    # Batch 6: International searches (if multiple countries)
    if len(countries) > 1:
        for country in countries[1:4]:  # Limit to first 4 countries
            queries.append({
                "query": f'"{brand_name}" trademark {country} {category}',
                "purpose": f"Find trademarks in {country}"
            })
    
    # Batch 7: Aggregator-specific searches
    queries.extend([
        {
            "query": f'site:trademarking.in "{brand_name}"',
            "purpose": "Search trademark aggregator"
        },
        {
            "query": f'site:ipindia.gov.in "{brand_name}"',
            "purpose": "Search IP India official site"
        }
    ])
    
    return queries


def generate_phonetic_variants(brand_name: str) -> List[str]:
    """Generate phonetic variants of a brand name for similarity searches"""
    variants = []
    name = brand_name.lower()
    
    # Common phonetic substitutions
    substitutions = [
        ("i", "ee"), ("i", "y"), ("ee", "i"),
        ("a", "ah"), ("a", "e"),
        ("c", "k"), ("k", "c"),
        ("ph", "f"), ("f", "ph"),
        ("s", "z"), ("z", "s"),
        ("x", "ks"), ("ks", "x"),
        ("ou", "u"), ("u", "ou"),
        ("oo", "u"), ("u", "oo"),
        ("ae", "e"), ("e", "ae"),
    ]
    
    for old, new in substitutions:
        if old in name:
            variants.append(name.replace(old, new, 1))
    
    # Add common suffixes/prefixes variants
    if name.endswith("a"):
        variants.append(name + "e")
        variants.append(name[:-1])
    if name.endswith("e"):
        variants.append(name + "a")
        variants.append(name[:-1])
    
    # Remove duplicates and the original
    variants = list(set([v for v in variants if v != name and v]))
    
    return variants[:5]  # Return top 5 variants


async def execute_web_search(query: str, timeout: int = 15) -> List[Dict[str, Any]]:
    """
    Execute a web search query with timeout protection.
    Uses DuckDuckGo search as a fallback-friendly option.
    """
    try:
        from duckduckgo_search import DDGS
        
        # Run DuckDuckGo search in executor with timeout
        loop = asyncio.get_event_loop()
        
        def _do_search():
            results = []
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=10))
                for r in search_results:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", r.get("link", "")),
                        "snippet": r.get("body", r.get("snippet", "")),
                        "source": "DuckDuckGo"
                    })
            return results
        
        try:
            results = await asyncio.wait_for(
                loop.run_in_executor(None, _do_search),
                timeout=float(timeout)
            )
            return results
        except asyncio.TimeoutError:
            logger.warning(f"Web search timeout for query '{query}'")
            return []
    
    except Exception as e:
        logger.warning(f"Web search failed for query '{query}': {str(e)}")
        return []


def get_known_data(brand_name: str) -> Dict[str, Any]:
    """Get known trademark/company data from cache"""
    brand_lower = brand_name.lower().strip()
    
    # Check for exact match first
    if brand_lower in KNOWN_TRADEMARK_DATA:
        return KNOWN_TRADEMARK_DATA[brand_lower]
    
    # Check for partial matches
    for known_brand, data in KNOWN_TRADEMARK_DATA.items():
        if known_brand in brand_lower or brand_lower in known_brand:
            return data
    
    return {}


def get_relevant_precedents(category: str, industry: str, countries: List[str] = None) -> List[Dict[str, Any]]:
    """Get relevant legal precedents for the category/industry based on selected countries"""
    precedents = []
    
    # Determine which country's precedents to use
    if not countries:
        countries = ["USA"]  # Default to USA
    
    primary_country = countries[0]
    
    # Resolve country aliases
    country_key = COUNTRY_ALIASES.get(primary_country, primary_country)
    
    # If country not found in database, default to USA
    if country_key not in LEGAL_PRECEDENTS_DB:
        country_key = "USA"
    
    country_precedents = LEGAL_PRECEDENTS_DB.get(country_key, LEGAL_PRECEDENTS_DB["USA"])
    
    # Always include phonetic similarity cases for the selected country
    precedents.extend(country_precedents.get("phonetic_similarity", []))
    
    # Add category-specific cases
    category_lower = category.lower()
    if "fashion" in category_lower or "apparel" in category_lower or "clothing" in category_lower or "streetwear" in category_lower:
        precedents.extend(country_precedents.get("fashion", []))
    
    # Add general cases for the country
    precedents.extend(country_precedents.get("general", []))
    
    return precedents[:5]  # Limit to top 5


def extract_trademark_conflicts(search_results: List[Dict[str, Any]], brand_name: str) -> List[TrademarkConflict]:
    """Extract trademark conflict information from search results"""
    conflicts = []
    seen_names = set()
    
    for result in search_results:
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        url = result.get("url", "")
        combined = f"{title} {snippet}"
        
        # Look for trademark application numbers (Indian format: 7 digits)
        app_numbers = re.findall(r'\b(\d{7})\b', combined)
        
        # Look for trademark status keywords
        status = None
        if "registered" in combined:
            status = "REGISTERED"
        elif "pending" in combined:
            status = "PENDING"
        elif "objected" in combined:
            status = "OBJECTED"
        elif "opposed" in combined:
            status = "OPPOSED"
        elif "abandoned" in combined:
            status = "ABANDONED"
        
        # Look for class numbers
        class_match = re.search(r'class\s*(\d{1,2})', combined)
        class_number = class_match.group(1) if class_match else None
        
        # Check if this result mentions the brand name or similar
        brand_lower = brand_name.lower()
        if brand_lower in combined or any(v in combined for v in generate_phonetic_variants(brand_name)):
            # Extract the conflicting name from title
            conflict_name = extract_brand_name_from_text(result.get("title", ""), brand_name)
            
            if conflict_name and conflict_name.lower() not in seen_names:
                seen_names.add(conflict_name.lower())
                
                # Determine source
                source = "Web Search"
                if "trademarking.in" in url:
                    source = "Trademarking.in"
                elif "ipindia" in url:
                    source = "IP India"
                elif "justia" in url:
                    source = "USPTO/Justia"
                
                # Determine risk level
                risk_level = "MEDIUM"
                if status == "REGISTERED":
                    risk_level = "HIGH"
                elif status == "PENDING":
                    risk_level = "MEDIUM"
                elif status == "OBJECTED":
                    risk_level = "LOW"
                
                conflicts.append(TrademarkConflict(
                    name=conflict_name,
                    source=source,
                    conflict_type="trademark_application",
                    application_number=app_numbers[0] if app_numbers else None,
                    status=status,
                    class_number=class_number,
                    risk_level=risk_level,
                    details=result.get("snippet", "")[:200],
                    url=url
                ))
    
    return conflicts


def extract_company_conflicts(search_results: List[Dict[str, Any]], brand_name: str) -> List[CompanyConflict]:
    """Extract company registration information from search results"""
    conflicts = []
    seen_companies = set()
    
    for result in search_results:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("url", "")
        combined = f"{title} {snippet}".lower()
        
        # Look for CIN (Corporate Identification Number) - Indian format
        cin_match = re.search(r'[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}', f"{title} {snippet}", re.IGNORECASE)
        
        # Look for company type indicators
        is_company = any(x in combined for x in [
            "private limited", "pvt ltd", "limited", "llp", 
            "incorporated", "company", "enterprises", "corporation"
        ])
        
        # Check if mentions the brand
        brand_lower = brand_name.lower()
        if (brand_lower in combined or any(v in combined for v in generate_phonetic_variants(brand_name))) and is_company:
            # Extract company name
            company_name = extract_company_name_from_text(title, brand_name)
            
            if company_name and company_name.lower() not in seen_companies:
                seen_companies.add(company_name.lower())
                
                # Determine source
                source = "Web Search"
                if "tofler.in" in url:
                    source = "Tofler"
                elif "zaubacorp" in url:
                    source = "Zauba Corp"
                elif "mca.gov.in" in url:
                    source = "MCA"
                
                # Extract state/location
                state = None
                indian_states = ["maharashtra", "delhi", "karnataka", "tamil nadu", "telangana", 
                               "gujarat", "west bengal", "rajasthan", "kerala", "andhra pradesh"]
                for s in indian_states:
                    if s in combined:
                        state = s.title()
                        break
                
                conflicts.append(CompanyConflict(
                    name=company_name,
                    cin=cin_match.group(0) if cin_match else None,
                    status="ACTIVE" if "active" in combined else "UNKNOWN",
                    industry=extract_industry_from_text(snippet),
                    state=state,
                    source=source,
                    risk_level="HIGH" if brand_lower in company_name.lower() else "MEDIUM",
                    url=url
                ))
    
    return conflicts


def extract_legal_precedents(search_results: List[Dict[str, Any]]) -> List[LegalPrecedent]:
    """Extract legal precedent information from search results"""
    precedents = []
    seen_cases = set()
    
    for result in search_results:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("url", "")
        combined = f"{title} {snippet}".lower()
        
        # Look for case indicators
        is_legal = any(x in combined for x in [
            " v ", " vs ", "case", "judgment", "court", "tribunal",
            "infringement", "passing off", "section 29", "trade marks act"
        ])
        
        if is_legal:
            # Extract case name (usually in format "X v Y" or "X vs Y")
            case_match = re.search(r'([A-Z][a-zA-Z\s]+)\s+(?:v|vs|versus)\.?\s+([A-Z][a-zA-Z\s]+)', title)
            
            if case_match:
                case_name = f"{case_match.group(1).strip()} v. {case_match.group(2).strip()}"
            else:
                case_name = title[:100]
            
            if case_name.lower() not in seen_cases:
                seen_cases.add(case_name.lower())
                
                # Determine court
                court = None
                if "supreme court" in combined:
                    court = "Supreme Court of India"
                elif "delhi" in combined and ("high court" in combined or "hc" in combined):
                    court = "Delhi High Court"
                elif "bombay" in combined and "high court" in combined:
                    court = "Bombay High Court"
                elif "high court" in combined:
                    court = "High Court"
                
                # Extract year
                year_match = re.search(r'\b(19|20)\d{2}\b', combined)
                year = year_match.group(0) if year_match else None
                
                precedents.append(LegalPrecedent(
                    case_name=case_name[:150],
                    court=court,
                    year=year,
                    relevance=snippet[:200],
                    source=url.split("/")[2] if url else "Unknown",
                    url=url
                ))
    
    return precedents[:5]  # Limit to top 5 precedents


def extract_brand_name_from_text(text: str, original_brand: str) -> Optional[str]:
    """Extract a brand/trademark name from text"""
    # Look for quoted names
    quoted = re.findall(r'"([^"]+)"', text)
    if quoted:
        return quoted[0]
    
    # Look for name patterns near trademark indicators
    patterns = [
        r'(\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:trademark|brand|mark)',
        r'(?:trademark|brand|mark)\s+(\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    # Fall back to returning a cleaned version of the original if found
    if original_brand.lower() in text.lower():
        return original_brand
    
    return None


def extract_company_name_from_text(text: str, original_brand: str) -> Optional[str]:
    """Extract a company name from text"""
    # Look for company name patterns
    patterns = [
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:Private Limited|Pvt\.?\s*Ltd\.?|Limited|LLP|Inc\.?)',
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:Enterprises|Corporation|Company)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    return None


def extract_industry_from_text(text: str) -> Optional[str]:
    """Extract industry information from text"""
    industries = {
        "fashion": ["fashion", "apparel", "clothing", "garment", "textile"],
        "technology": ["technology", "software", "tech", "it ", "digital"],
        "cosmetics": ["cosmetic", "beauty", "skincare", "personal care"],
        "food": ["food", "beverage", "restaurant", "cafe", "f&b"],
        "pharma": ["pharmaceutical", "pharma", "medicine", "drug", "healthcare"],
        "finance": ["finance", "banking", "investment", "fintech"],
        "education": ["education", "edtech", "learning", "training"],
    }
    
    text_lower = text.lower()
    for industry, keywords in industries.items():
        if any(kw in text_lower for kw in keywords):
            return industry.title()
    
    return None


# ============================================================================
# HYBRID RISK MODEL - TRADEMARK INTELLIGENCE
# ============================================================================
# Two-Pillar Architecture:
# PILLAR 1: Absolute Grounds (Internal Flaw) - Classification-based
# PILLAR 2: Relative Grounds (External Threat) - Conflict-based
# ============================================================================

# Country-Specific Trademark Statutes
COUNTRY_TRADEMARK_STATUTES = {
    "USA": {
        "statute": "Lanham Act Section 2(e)",
        "refusal_type": "Merely Descriptive",
        "office": "USPTO",
        "action_term": "Office Action",
        "precedent": "Polaroid Corp. v. Polarad Electronics (1961)",
        "precedent_principle": "Eight-factor test for likelihood of confusion"
    },
    "India": {
        "statute": "Section 9(1)(b) of the Trade Marks Act, 1999",
        "refusal_type": "Absolute Grounds for Refusal",
        "office": "Trade Marks Registry",
        "action_term": "Examination Report",
        "precedent": "Cadila Healthcare v. Cadila Pharmaceuticals (2001)",
        "precedent_principle": "Supreme Court established likelihood of confusion test for India"
    },
    "UK": {
        "statute": "Section 3(1)(c) of the Trade Marks Act 1994",
        "refusal_type": "Absolute Grounds (Descriptiveness)",
        "office": "UKIPO",
        "action_term": "Examination Report",
        "precedent": "Nestlé v. Cadbury (2013)",
        "precedent_principle": "Shape marks and acquired distinctiveness standards"
    },
    "UAE": {
        "statute": "Federal Law No. 37 of 1992, Article 3",
        "refusal_type": "Descriptive Marks",
        "office": "Ministry of Economy",
        "action_term": "Rejection Notice",
        "precedent": "N/A - Civil law jurisdiction",
        "precedent_principle": "Registry examination without common law precedent system"
    },
    "Singapore": {
        "statute": "Section 7(1)(c) of the Trade Marks Act",
        "refusal_type": "Descriptive Signs",
        "office": "IPOS",
        "action_term": "Examination Report",
        "precedent": "Polo/Lauren Co. v. Shop-In Department Store (1998)",
        "precedent_principle": "Likelihood of confusion in luxury goods context"
    },
    "Thailand": {
        "statute": "Section 7 of the Trade Marks Act B.E. 2534",
        "refusal_type": "Descriptive Marks",
        "office": "DIP (Department of Intellectual Property)",
        "action_term": "Examination Report",
        "precedent": "N/A",
        "precedent_principle": "Registry-based examination system"
    },
    "Australia": {
        "statute": "Section 41 of the Trade Marks Act 1995",
        "refusal_type": "Lack of Distinctiveness",
        "office": "IP Australia",
        "action_term": "Adverse Report",
        "precedent": "Cantarella Bros v. Modena Trading (2014)",
        "precedent_principle": "High Court ruling on foreign word distinctiveness"
    },
    "Japan": {
        "statute": "Article 3(1)(iii) of the Trademark Act",
        "refusal_type": "Descriptive Marks",
        "office": "JPO (Japan Patent Office)",
        "action_term": "Refusal Decision",
        "precedent": "N/A",
        "precedent_principle": "Strict examination of descriptive elements"
    },
    "China": {
        "statute": "Article 11 of the Trademark Law",
        "refusal_type": "Generic or Descriptive Signs",
        "office": "CNIPA",
        "action_term": "Rejection Notice",
        "precedent": "N/A",
        "precedent_principle": "First-to-file system with strict examination"
    },
    "Germany": {
        "statute": "Section 8(2)(2) of the Markengesetz",
        "refusal_type": "Descriptive Marks",
        "office": "DPMA",
        "action_term": "Examination Report",
        "precedent": "N/A",
        "precedent_principle": "EU harmonized examination standards"
    },
    "France": {
        "statute": "Article L711-2 of the Intellectual Property Code",
        "refusal_type": "Descriptive Signs",
        "office": "INPI",
        "action_term": "Examination Report",
        "precedent": "N/A",
        "precedent_principle": "EU harmonized examination standards"
    },
    "Canada": {
        "statute": "Section 12(1)(b) of the Trademarks Act",
        "refusal_type": "Clearly Descriptive",
        "office": "CIPO",
        "action_term": "Examiner's Report",
        "precedent": "N/A",
        "precedent_principle": "Similar to US standards with some variations"
    }
}

# Default for unlisted countries
DEFAULT_STATUTE = {
    "statute": "Local trademark laws regarding distinctiveness",
    "refusal_type": "Absolute Grounds for Refusal",
    "office": "National Trademark Registry",
    "action_term": "Examination Report",
    "precedent": "N/A",
    "precedent_principle": "Registry-based examination"
}


def get_country_statute(country: str) -> Dict[str, str]:
    """Get country-specific trademark statute information."""
    # Normalize country name
    country_upper = country.upper().strip()
    
    # Handle common variations
    country_map = {
        "UNITED STATES": "USA",
        "US": "USA",
        "UNITED KINGDOM": "UK",
        "BRITAIN": "UK",
        "ENGLAND": "UK",
        "UNITED ARAB EMIRATES": "UAE",
        "EMIRATES": "UAE"
    }
    
    normalized = country_map.get(country_upper, country_upper)
    
    # Try exact match first
    if normalized in COUNTRY_TRADEMARK_STATUTES:
        return COUNTRY_TRADEMARK_STATUTES[normalized]
    
    # Try case-insensitive match
    for key in COUNTRY_TRADEMARK_STATUTES:
        if key.upper() == normalized:
            return COUNTRY_TRADEMARK_STATUTES[key]
    
    return DEFAULT_STATUTE


def calculate_hybrid_trademark_risk(
    classification: str,
    critical_conflicts: int,
    high_conflicts: int,
    medium_conflicts: int,
    total_conflicts: int,
    countries: List[str] = None
) -> Dict[str, Any]:
    """
    HYBRID RISK MODEL - The Attorney Logic Formula
    
    Two Pillars:
    1. ABSOLUTE GROUNDS (Internal Flaw): Classification-based inherent strength
    2. RELATIVE GROUNDS (External Threat): Conflict-based market risk
    
    Args:
        classification: FANCIFUL, ARBITRARY, SUGGESTIVE, DESCRIPTIVE, GENERIC
        critical_conflicts: Identical marks found
        high_conflicts: Similar marks in same class
        medium_conflicts: Somewhat similar marks
        total_conflicts: Total conflict count
        countries: List of target countries for jurisdiction-specific analysis
    
    Returns:
        Complete risk assessment with per-country analysis
    """
    
    # ==================== PILLAR 1: ABSOLUTE GROUNDS ====================
    # Base scores from trademark classification (Internal Strength)
    BASE_SUCCESS = {
        "FANCIFUL": 95,    # Gold Standard - invented word
        "ARBITRARY": 90,   # Excellent - real word, unrelated context
        "SUGGESTIVE": 75,  # Good - requires imagination (examiners may argue)
        "DESCRIPTIVE": 45, # Coin-toss - Section 2(e)/9(1)(b) refusal likely
        "GENERIC": 5       # Dead on arrival - legally impossible
    }
    
    BASE_RISK = {
        "FANCIFUL": 1,     # Minimal risk
        "ARBITRARY": 1,    # Minimal risk
        "SUGGESTIVE": 2,   # Low risk (examiner scrutiny possible)
        "DESCRIPTIVE": 5,  # Moderate risk (refusal likely)
        "GENERIC": 9       # Critical risk (unregistrable)
    }
    
    # Get base scores
    classification_upper = classification.upper() if classification else "DESCRIPTIVE"
    success_prob = BASE_SUCCESS.get(classification_upper, 45)
    risk_score = BASE_RISK.get(classification_upper, 5)
    
    # Attorney notes for each classification
    classification_notes = {
        "FANCIFUL": "Gold Standard - Invented term with maximum inherent distinctiveness",
        "ARBITRARY": "Excellent - Common word used in completely unrelated context",
        "SUGGESTIVE": "Good - Requires imagination to connect to product (examiner may challenge)",
        "DESCRIPTIVE": "Weak - Directly describes product/service attributes. Refusal likely without Secondary Meaning.",
        "GENERIC": "Unregistrable - Names the product category itself. Cannot function as trademark."
    }
    attorney_note = classification_notes.get(classification_upper, "Classification unclear")
    
    # ==================== PILLAR 2: RELATIVE GROUNDS ====================
    # Apply conflict penalties (External Threats) - HIERARCHICAL
    conflict_analysis = []
    
    if critical_conflicts > 0:
        # CRITICAL = Identical mark exists - virtually fatal
        success_prob -= 80
        risk_score += 5
        conflict_analysis.append({
            "severity": "CRITICAL",
            "count": critical_conflicts,
            "impact": "-80% success, +5 risk",
            "explanation": "Identical mark(s) found. Registration legally impossible unless conflicting mark is dead/abandoned."
        })
    elif high_conflicts > 0:
        # HIGH = Similar mark - Likelihood of Confusion refusal
        success_prob -= 40
        risk_score += 3
        conflict_analysis.append({
            "severity": "HIGH",
            "count": high_conflicts,
            "impact": "-40% success, +3 risk",
            "explanation": "Similar mark(s) in same/related class. 'Likelihood of Confusion' refusal probable."
        })
    elif medium_conflicts > 0:
        # MEDIUM = Somewhat similar - may be overcome
        success_prob -= 10
        risk_score += 1
        conflict_analysis.append({
            "severity": "MEDIUM",
            "count": medium_conflicts,
            "impact": "-10% success, +1 risk",
            "explanation": "Potentially conflicting mark(s). May be overcome via coexistence agreement or goods limitation."
        })
    else:
        conflict_analysis.append({
            "severity": "NONE",
            "count": 0,
            "impact": "No penalty",
            "explanation": "No conflicting marks found in search. Clean relative grounds."
        })
    
    # ==================== OPPOSITION PROBABILITY ====================
    # Base calculation from conflicts
    if critical_conflicts > 0:
        opposition_prob = 85  # Almost certain lawsuit
    elif high_conflicts > 0:
        opposition_prob = 60  # Likely opposition
    elif medium_conflicts > 0:
        opposition_prob = 30  # Possible challenge
    else:
        opposition_prob = 10  # Low - no known conflicts
    
    # The "Bully" Modifier - Competitors target weak marks
    if classification_upper in ["DESCRIPTIVE", "GENERIC"]:
        opposition_prob += 10  # Competitors bully descriptive marks to keep language free
    
    # ==================== APPLY FLOOR/CEILING ====================
    success_prob = max(5, min(95, success_prob))
    risk_score = max(1, min(10, risk_score))
    opposition_prob = max(5, min(95, opposition_prob))
    
    # ==================== DETERMINE VERDICT ====================
    if risk_score >= 8:
        verdict = "HIGH RISK"
        verdict_detail = "Rebranding Recommended"
        verdict_color = "red"
    elif risk_score >= 5:
        verdict = "MODERATE RISK"
        verdict_detail = "Refusal Likely - Prepare for Office Action"
        verdict_color = "amber"
    else:
        verdict = "LOW RISK"
        verdict_detail = "Favorable - Proceed with Filing"
        verdict_color = "green"
    
    # ==================== PER-COUNTRY LEGAL ANALYSIS ====================
    country_analyses = []
    countries = countries or ["India"]  # Default
    
    for country in countries:
        statute_info = get_country_statute(country)
        
        # Generate country-specific analysis
        country_analysis = generate_country_legal_analysis(
            country=country,
            classification=classification_upper,
            statute_info=statute_info,
            success_prob=success_prob,
            risk_score=risk_score,
            critical_conflicts=critical_conflicts,
            high_conflicts=high_conflicts,
            medium_conflicts=medium_conflicts,
            total_conflicts=total_conflicts
        )
        country_analyses.append(country_analysis)
    
    return {
        # Core Risk Metrics
        "overall_risk_score": risk_score,
        "registration_success_probability": success_prob,
        "opposition_probability": opposition_prob,
        
        # Verdict
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "verdict_color": verdict_color,
        
        # Conflict Counts
        "critical_conflicts_count": critical_conflicts,
        "high_risk_conflicts_count": high_conflicts,
        "medium_conflicts_count": medium_conflicts,
        "total_conflicts_found": total_conflicts,
        
        # Pillar Analysis
        "absolute_grounds": {
            "classification": classification_upper,
            "base_success": BASE_SUCCESS.get(classification_upper, 45),
            "base_risk": BASE_RISK.get(classification_upper, 5),
            "attorney_note": attorney_note
        },
        "relative_grounds": {
            "conflict_analysis": conflict_analysis,
            "clean_search_warning": classification_upper in ["DESCRIPTIVE", "GENERIC"] and total_conflicts == 0
        },
        
        # Per-Country Legal Analysis
        "country_analyses": country_analyses,
        
        # Strategic Recommendation
        "strategic_recommendation": generate_strategic_recommendation(
            classification_upper, success_prob, risk_score, 
            critical_conflicts, high_conflicts, countries
        )
    }


def generate_country_legal_analysis(
    country: str,
    classification: str,
    statute_info: Dict[str, str],
    success_prob: int,
    risk_score: int,
    critical_conflicts: int,
    high_conflicts: int,
    medium_conflicts: int,
    total_conflicts: int
) -> Dict[str, Any]:
    """Generate country-specific legal analysis for trademark registration."""
    
    office = statute_info["office"]
    statute = statute_info["statute"]
    refusal_type = statute_info["refusal_type"]
    action_term = statute_info["action_term"]
    precedent = statute_info["precedent"]
    precedent_principle = statute_info["precedent_principle"]
    
    # ==================== ABSOLUTE GROUNDS ANALYSIS ====================
    if classification == "GENERIC":
        absolute_analysis = (
            f"**FATAL FLAW:** This is a GENERIC term that names the product category itself. "
            f"The {office} will refuse registration under **{statute}** ({refusal_type}). "
            f"Generic terms cannot function as trademarks under any jurisdiction. "
            f"No amount of evidence or argument can overcome this defect."
        )
    elif classification == "DESCRIPTIVE":
        absolute_analysis = (
            f"**HIGH RISK - DESCRIPTIVE MARK:** The {office} will likely issue an {action_term} "
            f"citing **{statute}** ({refusal_type}). "
            f"The name directly describes product/service attributes, lacking inherent distinctiveness. "
            f"To overcome: Must prove 'acquired distinctiveness' (Secondary Meaning) through 5+ years exclusive use, "
            f"significant advertising spend, and consumer recognition evidence."
        )
    elif classification == "SUGGESTIVE":
        absolute_analysis = (
            f"**MODERATE STRENGTH - SUGGESTIVE MARK:** The name requires imagination to connect to the product. "
            f"While inherently distinctive, the {office} examiner may argue the mark is merely descriptive under **{statute}**. "
            f"Be prepared to argue the 'imagination test' - that consumers need a mental leap to understand the product connection."
        )
    elif classification == "ARBITRARY":
        absolute_analysis = (
            f"**STRONG - ARBITRARY MARK:** Common word used in unrelated context (like 'Apple' for computers). "
            f"Inherently distinctive under **{statute}**. The {office} should not raise descriptiveness objections. "
            f"Focus registration strategy on relative grounds (conflicting marks) rather than absolute grounds."
        )
    else:  # FANCIFUL
        absolute_analysis = (
            f"**STRONGEST - FANCIFUL/COINED MARK:** Invented term with no prior dictionary meaning. "
            f"Maximum inherent distinctiveness under **{statute}**. The {office} will not raise descriptiveness objections. "
            f"This is the 'Gold Standard' for trademark strength. Focus entirely on conflict clearance."
        )
    
    # ==================== RELATIVE GROUNDS ANALYSIS ====================
    if critical_conflicts > 0:
        relative_analysis = (
            f"**CRITICAL CONFLICT DETECTED:** {critical_conflicts} identical or near-identical mark(s) found. "
            f"The {office} will issue an {action_term} citing likelihood of confusion. "
            f"Registration is effectively blocked unless the conflicting mark is abandoned or you obtain consent."
        )
    elif high_conflicts > 0:
        relative_analysis = (
            f"**HIGH CONFLICT RISK:** {high_conflicts} similar mark(s) found in same/related class. "
            f"Expect an {action_term} from the {office} citing likelihood of confusion. "
            f"May require legal argument, coexistence agreement, or limitation of goods/services to overcome."
        )
    elif medium_conflicts > 0:
        relative_analysis = (
            f"**MODERATE CONFLICT RISK:** {medium_conflicts} potentially conflicting mark(s) found. "
            f"The {office} may cite these in examination. Prepare arguments distinguishing your mark. "
            f"Consider coexistence agreement or goods limitation if challenged."
        )
    else:
        if classification in ["DESCRIPTIVE", "GENERIC"]:
            relative_analysis = (
                f"**CLEAN SEARCH - BUT WARNING:** No conflicting marks found in {country} search. "
                f"⚠️ However, this does NOT cure the descriptiveness flaw. "
                f"The risk is from {office} EXAMINER rejection under {statute}, not competitor lawsuit. "
                f"A clean search means no opposition from third parties, but the government may still refuse registration."
            )
        else:
            relative_analysis = (
                f"**CLEAN SEARCH:** No conflicting marks found in {country}. "
                f"Favorable relative grounds. Focus on building brand without trademark conflict concerns."
            )
    
    # ==================== COUNTRY-SPECIFIC RECOMMENDATION ====================
    if classification in ["DESCRIPTIVE", "GENERIC"]:
        recommendation = [
            f"Prepare evidence of acquired distinctiveness (sales figures, advertising spend, consumer surveys)",
            f"Consider filing a logo/device mark to bypass text-only refusal",
            f"Budget for responding to {action_term} from {office}",
            f"Consider adding a distinctive prefix/suffix to strengthen the mark",
            f"Consult local trademark counsel familiar with {office} examination practices"
        ]
    elif classification == "SUGGESTIVE":
        recommendation = [
            f"Prepare 'imagination test' arguments in case examiner challenges distinctiveness",
            f"Document the mental leap required to connect name to product",
            f"File with standard examination - good chance of success",
            f"Monitor for conflicting applications during examination period"
        ]
    else:  # ARBITRARY or FANCIFUL
        recommendation = [
            f"Proceed with standard trademark filing at {office}",
            f"Strong inherent distinctiveness - focus on conflict clearance",
            f"Consider filing in multiple classes if product line may expand",
            f"Register domain names and social handles simultaneously"
        ]
    
    return {
        "country": country,
        "office": office,
        "statute": statute,
        "refusal_type": refusal_type,
        "action_term": action_term,
        "absolute_grounds_analysis": absolute_analysis,
        "relative_grounds_analysis": relative_analysis,
        "precedent": {
            "case_name": precedent,
            "principle": precedent_principle
        },
        "recommendation": recommendation
    }


def generate_strategic_recommendation(
    classification: str,
    success_prob: int,
    risk_score: int,
    critical_conflicts: int,
    high_conflicts: int,
    countries: List[str]
) -> Dict[str, Any]:
    """Generate overall strategic recommendation based on hybrid risk assessment."""
    
    primary_country = countries[0] if countries else "your target market"
    
    if classification == "GENERIC":
        return {
            "action": "REBRAND IMMEDIATELY",
            "urgency": "CRITICAL",
            "summary": f"'{classification}' classification makes registration legally impossible. Invest zero additional resources in this name.",
            "steps": [
                "STOP all brand development activities for this name",
                "Engage naming consultant or agency for alternatives",
                "Consider suggestive or fanciful naming approach",
                "Conduct fresh trademark clearance on alternatives"
            ]
        }
    elif classification == "DESCRIPTIVE" and (critical_conflicts > 0 or high_conflicts > 0):
        return {
            "action": "REBRAND RECOMMENDED",
            "urgency": "HIGH",
            "summary": f"Descriptive name WITH conflicts is a double-jeopardy situation. Both absolute and relative grounds against you.",
            "steps": [
                "Rebranding is the most cost-effective path forward",
                "If proceeding anyway: Expect legal costs of $10K-50K+ to fight both refusals and oppositions",
                "Alternative: Acquire the conflicting mark if possible",
                "Alternative: Negotiate coexistence agreement (expensive, uncertain)"
            ]
        }
    elif classification == "DESCRIPTIVE":
        return {
            "action": "PROCEED WITH CAUTION",
            "urgency": "MODERATE",
            "summary": f"Descriptive name faces examiner refusal risk even with clean search. Plan for {success_prob}% success rate.",
            "steps": [
                f"Gather evidence of acquired distinctiveness BEFORE filing",
                "Consider filing logo/stylized mark simultaneously",
                f"Budget for responding to Office Action/Examination Report",
                "Begin using mark in commerce immediately to build evidence",
                "Alternative: Add distinctive element to strengthen mark"
            ]
        }
    elif critical_conflicts > 0:
        return {
            "action": "REBRAND OR ACQUIRE",
            "urgency": "HIGH",
            "summary": f"Critical conflict blocks registration regardless of name strength. Identical mark exists.",
            "steps": [
                "Option A: Acquire the conflicting mark (negotiate purchase)",
                "Option B: Obtain consent agreement from mark owner",
                "Option C: Rebrand to avoid conflict entirely",
                "Do NOT proceed without resolving conflict - waste of filing fees"
            ]
        }
    elif high_conflicts > 0:
        return {
            "action": "PROCEED WITH LEGAL STRATEGY",
            "urgency": "MODERATE",
            "summary": f"Similar marks exist but may be distinguishable. Prepare legal arguments.",
            "steps": [
                "Engage trademark attorney to assess likelihood of confusion",
                "Prepare arguments distinguishing your mark (different channels, goods, consumers)",
                "Consider coexistence agreement with conflicting mark owner",
                "File with expectation of Office Action - budget accordingly"
            ]
        }
    else:
        return {
            "action": "PROCEED WITH FILING",
            "urgency": "LOW",
            "summary": f"Favorable conditions for registration. {success_prob}% estimated success rate.",
            "steps": [
                f"File trademark application in {primary_country}",
                "Secure matching domain names and social handles",
                "Set up trademark watch service to monitor for new conflicts",
                "Consider filing in additional markets if expansion planned"
            ]
        }


# Legacy wrapper for backward compatibility
def calculate_risk_scores(
    trademark_conflicts: List[TrademarkConflict],
    company_conflicts: List[CompanyConflict],
    common_law_conflicts: List[Dict],
    classification: str = "DESCRIPTIVE",
    countries: List[str] = None
) -> Dict[str, Any]:
    """
    Calculate overall risk scores using the Hybrid Risk Model.
    
    This is a wrapper that maintains backward compatibility while using
    the new hybrid model internally.
    """
    
    # Count conflicts by severity
    critical_count = sum(1 for c in trademark_conflicts if c.risk_level == "CRITICAL")
    critical_count += sum(1 for c in company_conflicts if c.risk_level == "CRITICAL")
    
    high_count = sum(1 for c in trademark_conflicts if c.risk_level == "HIGH")
    high_count += sum(1 for c in company_conflicts if c.risk_level == "HIGH")
    
    medium_count = sum(1 for c in trademark_conflicts if c.risk_level == "MEDIUM")
    medium_count += sum(1 for c in company_conflicts if c.risk_level == "MEDIUM")
    
    total_conflicts = len(trademark_conflicts) + len(company_conflicts) + len(common_law_conflicts)
    
    # Use hybrid model
    hybrid_result = calculate_hybrid_trademark_risk(
        classification=classification,
        critical_conflicts=critical_count,
        high_conflicts=high_count,
        medium_conflicts=medium_count,
        total_conflicts=total_conflicts,
        countries=countries
    )
    
    # Return in legacy format with enhanced data
    return {
        "overall_risk_score": hybrid_result["overall_risk_score"],
        "registration_success_probability": hybrid_result["registration_success_probability"],
        "opposition_probability": hybrid_result["opposition_probability"],
        "critical_conflicts_count": critical_count,
        "high_risk_conflicts_count": high_count,
        "total_conflicts_found": total_conflicts,
        # New hybrid model data
        "verdict": hybrid_result["verdict"],
        "verdict_detail": hybrid_result["verdict_detail"],
        "absolute_grounds": hybrid_result["absolute_grounds"],
        "relative_grounds": hybrid_result["relative_grounds"],
        "country_analyses": hybrid_result["country_analyses"],
        "strategic_recommendation": hybrid_result["strategic_recommendation"]
    }


async def conduct_trademark_research(
    brand_name: str,
    industry: str,
    category: str,
    countries: List[str],
    known_competitors: List[str] = None,
    product_keywords: List[str] = None,
    classification: str = None  # NEW: Accept pre-computed classification
) -> TrademarkResearchResult:
    """
    Conduct trademark research for a brand name using the Hybrid Risk Model.
    
    Args:
        brand_name: The brand name to research
        industry: Industry sector
        category: Product category
        countries: Target countries for registration
        known_competitors: User-provided competitors to check for conflicts
        product_keywords: Additional keywords for more targeted searches
        classification: Pre-computed trademark classification (FANCIFUL, ARBITRARY, SUGGESTIVE, DESCRIPTIVE, GENERIC)
    
    Returns:
        TrademarkResearchResult with hybrid risk assessment
    """
    logger.info(f"Starting trademark research for '{brand_name}' in {industry}/{category} with classification: {classification}")
    
    # Default empty lists
    known_competitors = known_competitors or []
    product_keywords = product_keywords or []
    
    # Initialize result
    result = TrademarkResearchResult(
        brand_name=brand_name,
        industry=industry or "General",
        category=category or "General",
        countries=countries or ["India"]
    )
    
    # Get Nice Classification
    result.nice_classification = get_nice_classification(category, industry)
    
    # Step 1: Check known data cache first (FAST)
    known_data = get_known_data(brand_name)
    
    if known_data:
        logger.info(f"Found known data for '{brand_name}'")
        
        # Add known trademarks
        for tm in known_data.get("trademarks", []):
            result.trademark_conflicts.append(TrademarkConflict(
                name=tm.get("name", brand_name),
                source=tm.get("source", "Known Database"),
                conflict_type="trademark_application",
                application_number=tm.get("application_number"),
                status=tm.get("status"),
                owner=tm.get("owner"),
                class_number=tm.get("class_number"),
                filing_date=tm.get("filing_date"),
                risk_level="HIGH" if tm.get("status") == "REGISTERED" else "MEDIUM",
                url=tm.get("url")
            ))
        
        # Add known companies
        for co in known_data.get("companies", []):
            result.company_conflicts.append(CompanyConflict(
                name=co.get("name", ""),
                cin=co.get("cin"),
                status=co.get("status", "ACTIVE"),
                incorporation_date=co.get("incorporation_date"),
                industry=co.get("industry"),
                state=co.get("state"),
                source=co.get("source", "Known Database"),
                risk_level="HIGH" if category.lower() in co.get("industry", "").lower() else "MEDIUM",
                url=co.get("url")
            ))
        
        # Add common law conflicts
        result.common_law_conflicts = known_data.get("common_law", [])
    
    # Improvement #2: Check similarity with user-provided competitors
    if known_competitors:
        logger.info(f"Checking brand similarity with {len(known_competitors)} user-provided competitors")
        for competitor in known_competitors[:5]:
            # Simple similarity check
            brand_lower = brand_name.lower().replace(" ", "")
            comp_lower = competitor.lower().replace(" ", "")
            
            # Check for substring or significant overlap
            if brand_lower in comp_lower or comp_lower in brand_lower:
                result.company_conflicts.append(CompanyConflict(
                    name=competitor,
                    status="ACTIVE",
                    industry=category,
                    source="User-provided competitor",
                    overlap_analysis="Direct name overlap detected - HIGH trademark risk",
                    risk_level="CRITICAL"
                ))
            elif len(set(brand_lower) & set(comp_lower)) > len(brand_lower) * 0.7:
                result.company_conflicts.append(CompanyConflict(
                    name=competitor,
                    status="ACTIVE",
                    industry=category,
                    source="User-provided competitor",
                    overlap_analysis="Significant character overlap - MEDIUM trademark risk",
                    risk_level="HIGH"
                ))
    
    # Step 2: Quick web search (limited to 3 queries for speed)
    queries = generate_search_queries(brand_name, industry, category, countries)[:3]  # Only first 3 queries
    
    # Improvement #3: Add keyword-enhanced searches
    if product_keywords:
        for keyword in product_keywords[:2]:  # Limit to 2 keywords
            queries.append({
                "query": f'"{brand_name}" {keyword} trademark',
                "purpose": f"keyword_search_{keyword}"
            })
    
    all_search_results = []
    for q in queries:
        try:
            search_results = await execute_web_search(q["query"])
            for r in search_results:
                r["query_purpose"] = q["purpose"]
            all_search_results.extend(search_results)
        except Exception as e:
            logger.warning(f"Search failed: {str(e)}")
    
    # Step 3: Extract conflicts from search results
    search_tm_conflicts = extract_trademark_conflicts(all_search_results, brand_name)
    search_co_conflicts = extract_company_conflicts(all_search_results, brand_name)
    
    # Merge with known data (avoid duplicates)
    existing_tm_names = {c.name.lower() for c in result.trademark_conflicts}
    for c in search_tm_conflicts:
        if c.name.lower() not in existing_tm_names:
            result.trademark_conflicts.append(c)
            existing_tm_names.add(c.name.lower())
    
    existing_co_names = {c.name.lower() for c in result.company_conflicts}
    for c in search_co_conflicts:
        if c.name.lower() not in existing_co_names:
            result.company_conflicts.append(c)
            existing_co_names.add(c.name.lower())
    
    # Step 4: Add relevant legal precedents (COUNTRY-SPECIFIC)
    precedents = get_relevant_precedents(category, industry, countries)
    for p in precedents:
        result.legal_precedents.append(LegalPrecedent(
            case_name=p.get("case_name", ""),
            court=p.get("court"),
            year=p.get("year"),
            relevance=p.get("relevance", ""),
            key_principle=p.get("key_principle")
        ))
    
    # Step 5: Calculate risk scores using HYBRID MODEL with classification
    # Default classification to DESCRIPTIVE if not provided (conservative approach)
    effective_classification = classification or "DESCRIPTIVE"
    
    risk_scores = calculate_risk_scores(
        result.trademark_conflicts,
        result.company_conflicts,
        result.common_law_conflicts,
        classification=effective_classification,
        countries=countries
    )
    
    result.overall_risk_score = risk_scores["overall_risk_score"]
    result.registration_success_probability = risk_scores["registration_success_probability"]
    result.opposition_probability = risk_scores["opposition_probability"]
    result.critical_conflicts_count = risk_scores["critical_conflicts_count"]
    result.high_risk_conflicts_count = risk_scores["high_risk_conflicts_count"]
    result.total_conflicts_found = risk_scores["total_conflicts_found"]
    
    # Store hybrid model analysis in search_results_summary for display
    result.search_results_summary = json.dumps({
        "hybrid_risk_model": {
            "verdict": risk_scores.get("verdict"),
            "verdict_detail": risk_scores.get("verdict_detail"),
            "absolute_grounds": risk_scores.get("absolute_grounds"),
            "relative_grounds": risk_scores.get("relative_grounds"),
            "country_analyses": risk_scores.get("country_analyses"),
            "strategic_recommendation": risk_scores.get("strategic_recommendation")
        }
    }, indent=2)
    
    logger.info(f"Trademark research complete. Verdict: {risk_scores.get('verdict')} | "
                f"Risk: {result.overall_risk_score}/10 | Success: {result.registration_success_probability}% | "
                f"Classification: {effective_classification} | Conflicts: {result.total_conflicts_found}")
    
    return result


def extract_common_law_conflicts(
    search_results: List[Dict[str, Any]], 
    brand_name: str, 
    industry: str
) -> List[Dict[str, Any]]:
    """Extract common law (unregistered) trademark conflicts"""
    conflicts = []
    seen_businesses = set()
    
    for result in search_results:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("url", "")
        combined = f"{title} {snippet}".lower()
        
        # Look for business indicators that suggest operational businesses
        is_business = any(x in combined for x in [
            "shop", "store", "buy", "order", "instagram", "facebook",
            "@", "official", "website", "online", ".com", "ecommerce"
        ])
        
        # Exclude trademark registries and legal sites
        is_registry = any(x in url.lower() for x in [
            "trademark", "ipindia", "wipo", "uspto", "tofler", "mca.gov",
            "court", "legal", "law"
        ])
        
        brand_lower = brand_name.lower()
        if is_business and not is_registry and brand_lower in combined:
            # This might be an operating business without formal trademark
            business_name = extract_business_name(title, brand_name)
            
            if business_name and business_name.lower() not in seen_businesses:
                seen_businesses.add(business_name.lower())
                
                # Determine platform/type
                platform = "Website"
                if "instagram" in url or "instagram" in combined:
                    platform = "Instagram"
                elif "facebook" in url or "facebook" in combined:
                    platform = "Facebook"
                elif "amazon" in url:
                    platform = "Amazon"
                elif "flipkart" in url:
                    platform = "Flipkart"
                
                conflicts.append({
                    "name": business_name,
                    "platform": platform,
                    "industry_match": industry.lower() in combined if industry else False,
                    "url": url,
                    "snippet": snippet[:150],
                    "risk_type": "common_law",
                    "risk_level": "MEDIUM" if industry.lower() in combined else "LOW"
                })
    
    return conflicts[:10]  # Limit to top 10


def extract_business_name(text: str, original_brand: str) -> Optional[str]:
    """Extract business name from text"""
    # Try to extract from common patterns
    patterns = [
        r'(@\w+)',  # Instagram/Twitter handles
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:Official|Shop|Store)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    if original_brand.lower() in text.lower():
        return original_brand
    
    return None


def create_search_summary(search_results: List[Dict[str, Any]], brand_name: str) -> str:
    """Create a summary of search results for LLM processing"""
    summary_parts = []
    
    # Group results by purpose
    by_purpose = {}
    for r in search_results:
        purpose = r.get("query_purpose", "General")
        if purpose not in by_purpose:
            by_purpose[purpose] = []
        by_purpose[purpose].append(r)
    
    for purpose, results in by_purpose.items():
        summary_parts.append(f"\n### {purpose}")
        for r in results[:5]:  # Limit per category
            title = r.get("title", "")[:100]
            snippet = r.get("snippet", "")[:150]
            summary_parts.append(f"- {title}: {snippet}")
    
    return "\n".join(summary_parts)


def format_research_for_prompt(research_result: TrademarkResearchResult) -> str:
    """
    Format the trademark research result for inclusion in LLM prompt.
    This creates a structured context that the LLM can use to generate
    a comprehensive trademark analysis.
    """
    sections = []
    
    # Header
    sections.append(f"""
⚠️ REAL-TIME TRADEMARK RESEARCH DATA ⚠️
========================================
Brand: {research_result.brand_name}
Industry: {research_result.industry}
Category: {research_result.category}
Target Countries: {', '.join(research_result.countries)}
Nice Classification: Class {research_result.nice_classification.get('class_number', 'N/A')} - {research_result.nice_classification.get('class_description', '')}
Research Timestamp: {research_result.research_timestamp}
""")
    
    # Risk Summary
    sections.append(f"""
📊 RISK ASSESSMENT SUMMARY
--------------------------
Overall Risk Score: {research_result.overall_risk_score}/10
Registration Success Probability: {research_result.registration_success_probability}%
Opposition Probability: {research_result.opposition_probability}%
Total Conflicts Found: {research_result.total_conflicts_found}
  - Critical: {research_result.critical_conflicts_count}
  - High Risk: {research_result.high_risk_conflicts_count}
""")
    
    # Trademark Conflicts
    if research_result.trademark_conflicts:
        sections.append("\n🔴 TRADEMARK CONFLICTS FOUND:")
        for i, conflict in enumerate(research_result.trademark_conflicts[:10], 1):
            sections.append(f"""
  {i}. {conflict.name}
     Source: {conflict.source}
     Status: {conflict.status or 'Unknown'}
     Application #: {conflict.application_number or 'N/A'}
     Class: {conflict.class_number or 'N/A'}
     Owner: {conflict.owner or 'N/A'}
     Risk Level: {conflict.risk_level}
""")
    else:
        sections.append("\n✅ NO DIRECT TRADEMARK CONFLICTS FOUND IN SEARCH")
    
    # Company Conflicts
    if research_result.company_conflicts:
        sections.append("\n🏢 COMPANY REGISTRY CONFLICTS:")
        for i, conflict in enumerate(research_result.company_conflicts[:10], 1):
            sections.append(f"""
  {i}. {conflict.name}
     CIN: {conflict.cin or 'N/A'}
     Status: {conflict.status}
     Industry: {conflict.industry or 'N/A'}
     State: {conflict.state or 'N/A'}
     Source: {conflict.source}
     Risk Level: {conflict.risk_level}
""")
    else:
        sections.append("\n✅ NO COMPANY REGISTRY CONFLICTS FOUND")
    
    # Common Law Conflicts
    if research_result.common_law_conflicts:
        sections.append("\n📱 COMMON LAW / ONLINE PRESENCE CONFLICTS:")
        for i, conflict in enumerate(research_result.common_law_conflicts[:5], 1):
            sections.append(f"""
  {i}. {conflict.get('name', 'Unknown')}
     Platform: {conflict.get('platform', 'N/A')}
     Industry Match: {'Yes' if conflict.get('industry_match') else 'No'}
     Risk Level: {conflict.get('risk_level', 'LOW')}
""")
    
    # Legal Precedents
    if research_result.legal_precedents:
        sections.append("\n⚖️ RELEVANT LEGAL PRECEDENTS:")
        for i, precedent in enumerate(research_result.legal_precedents[:5], 1):
            sections.append(f"""
  {i}. {precedent.case_name}
     Court: {precedent.court or 'N/A'}
     Year: {precedent.year or 'N/A'}
     Relevance: {precedent.relevance[:100] if precedent.relevance else 'N/A'}
     Key Principle: {precedent.key_principle or 'N/A'}
""")
    
    # Instructions for LLM
    sections.append("""
📝 INSTRUCTIONS FOR ANALYSIS:
-----------------------------
1. Use the above REAL data to populate the trademark analysis sections
2. If critical/high conflicts exist, explain their specific impact
3. Reference specific application numbers and company names where found
4. Calculate opposition risk based on the actual conflicts discovered
5. Provide mitigation strategies specific to the conflicts found
6. If conflicts exist in the same Nice class, this is HIGH priority
7. Company conflicts in the same industry = common law trademark risk
""")
    
    return "\n".join(sections)


# Export main functions
__all__ = [
    'conduct_trademark_research',
    'format_research_for_prompt',
    'TrademarkResearchResult',
    'TrademarkConflict',
    'CompanyConflict',
    'LegalPrecedent',
    'get_nice_classification'
]
