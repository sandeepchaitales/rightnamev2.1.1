# RIGHTNAME.AI - CODE FLOW DESIGN

## 📁 FILE STRUCTURE & DEPENDENCIES

```
/app/
├── backend/
│   ├── server.py              ← MAIN API (673KB, ~12000 lines)
│   ├── schemas.py             ← Pydantic Models (Request/Response)
│   ├── prompts.py             ← LLM System Prompts
│   ├── linguistic_analysis.py ← Universal Linguistic Analyzer
│   ├── trademark_research.py  ← Trademark Web Search
│   ├── market_intelligence.py ← Country Competitor Research
│   ├── visibility.py          ← Google/App Store Search
│   ├── availability.py        ← Domain/Social Checks
│   ├── similarity.py          ← Phonetic Similarity
│   ├── admin_routes.py        ← Admin Panel API
│   ├── google_oauth.py        ← OAuth Authentication
│   └── payment_routes.py      ← Stripe Integration
│
└── frontend/
    └── src/
        ├── pages/
        │   ├── LandingPage.js  ← User Input Form
        │   ├── Dashboard.js    ← Results Display
        │   └── MyReports.js    ← User Reports History
        ├── components/
        │   └── ElegantLoader.js ← Loading Animation
        └── contexts/
            └── AuthContext.js  ← Authentication State
```

---

## 🔗 IMPORT DEPENDENCIES (server.py)

```python
# server.py - Line 1-60

# ===== FRAMEWORK IMPORTS =====
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient  # MongoDB async driver

# ===== DATA MODELS =====
from schemas import (
    BrandEvaluationRequest,    # Input model
    BrandEvaluationResponse,   # Output model  
    BrandScore,                # Per-brand result
    DimensionScore,            # 6 LLM dimensions
    # ... more models
)

# ===== INTERNAL MODULES =====
from prompts import SYSTEM_PROMPT                    # LLM evaluation prompt
from visibility import check_visibility              # Google/App search
from availability import (
    check_full_availability,                         # Domain check
    check_multi_domain_availability,                 # Multi-TLD check
    check_social_availability,                       # Social handles
    llm_analyze_domain_strategy                      # LLM domain analysis
)
from similarity import (
    check_brand_similarity,                          # Phonetic check
    deep_trace_analysis                              # Category king detection
)
from trademark_research import (
    conduct_trademark_research,                      # Web trademark search
    format_research_for_prompt
)
from market_intelligence import (
    research_all_countries,                          # Country research
    search_competitors                               # Competitor search
)
from linguistic_analysis import (
    analyze_brand_linguistics,                       # Universal linguistic (LLM)
    format_linguistic_analysis_for_prompt
)
```

---

## 📊 DATA MODELS (schemas.py)

```python
# ===== REQUEST MODEL =====
class BrandEvaluationRequest(BaseModel):
    brand_names: List[str]           # ["CHAIDESH"]
    industry: Optional[str]          # "Food & Beverage"
    category: Optional[str]          # "Tea Brand"
    product_type: Optional[str]      # "Physical Product"
    usp: Optional[str]               # "Premium organic"
    brand_vibe: Optional[str]        # "Premium & Authentic"
    positioning: Optional[str]       # "Premium"
    market_scope: Optional[str]      # "Multi-Country"
    countries: List[str]             # ["India", "USA", "UK"]
    known_competitors: List[str]     # ["Tata Tea"]
    product_keywords: List[str]      # ["organic", "tea"]

# ===== RESPONSE MODEL =====
class BrandEvaluationResponse(BaseModel):
    report_id: str
    executive_summary: str
    brand_scores: List[BrandScore]
    comparison_verdict: str

# ===== BRAND SCORE MODEL =====
class BrandScore(BaseModel):
    brand_name: str
    namescore: float                           # 0-100
    verdict: str                               # "GO" / "CAUTION" / "REJECT"
    summary: str
    strategic_classification: str
    pros: List[str]
    cons: List[str]
    dimensions: List[DimensionScore]           # 6 dimensions
    trademark_risk: dict
    domain_analysis: Optional[dict]
    social_availability: Optional[dict]
    cultural_analysis: Optional[List[dict]]
    trademark_research: Optional[dict]
    brand_classification: Optional[dict]       # Classification + override
    universal_linguistic_analysis: Optional[dict]  # Linguistic data
```

---

## 🔄 MAIN API FLOW (server.py)

### Entry Point: POST /api/evaluate

```python
# Line 9410
@app.post("/api/evaluate")
async def evaluate_brands(request: BrandEvaluationRequest):
    return await evaluate_brands_internal(request)
```

### Main Processing Function

```python
# Line 9414
async def evaluate_brands_internal(request: BrandEvaluationRequest, job_id: str = None):
    
    # ══════════════════════════════════════════════════════════════
    # GATE 0: INAPPROPRIATE NAME CHECK
    # ══════════════════════════════════════════════════════════════
    for brand in request.brand_names:
        inappropriate_check = check_inappropriate_name(brand)  # Line 9429
        if inappropriate_check["is_inappropriate"]:
            # IMMEDIATE REJECT - Return early with score 0
            return BrandEvaluationResponse(
                namescore=0.0,
                verdict="REJECT",
                summary="⛔ FATAL: Inappropriate/Offensive content"
            )
    
    # ══════════════════════════════════════════════════════════════
    # GATE 1: FAMOUS BRAND DETECTION (Early Stopping)
    # ══════════════════════════════════════════════════════════════
    # (Located earlier in code, around line 9500-9650)
    early_stop_result = check_early_stopping(brand, request.category)
    if early_stop_result["should_stop"]:
        # IMMEDIATE REJECT - Saves 60-90 seconds
        return BrandEvaluationResponse(...)
    
    # ══════════════════════════════════════════════════════════════
    # MAIN PROCESSING LOOP - For each brand
    # ══════════════════════════════════════════════════════════════
    all_brand_data = {}
    
    for brand in request.brand_names:
        
        # ──────────────────────────────────────────────────────────
        # STEP 1: UNIVERSAL LINGUISTIC ANALYSIS (Line 9750-9769)
        # ──────────────────────────────────────────────────────────
        linguistic_analysis = await analyze_brand_linguistics(
            brand_name=brand,
            business_category=request.category,
            industry=request.industry
        )
        # Returns: {
        #   has_linguistic_meaning: true,
        #   linguistic_analysis: {languages_detected: ["Hindi"], decomposition: {...}},
        #   business_alignment: {alignment_score: 9},
        #   classification: {name_type: "Foreign-Language"}
        # }
        
        # ──────────────────────────────────────────────────────────
        # STEP 2: MASTER CLASSIFICATION WITH OVERRIDE (Line 9771-9787)
        # ──────────────────────────────────────────────────────────
        brand_classification = classify_brand_with_linguistic_override(
            brand, 
            request.category,
            linguistic_analysis  # Pass linguistic data for override
        )
        classification_category = brand_classification.get("category")
        # Returns: {
        #   category: "SUGGESTIVE",  ← Overridden from "FANCIFUL"
        #   linguistic_override: true,
        #   original_category: "FANCIFUL",
        #   override_reason: "Hindi meaning aligns with business"
        # }
        
        # ──────────────────────────────────────────────────────────
        # STEP 3: PARALLEL DATA GATHERING (Line 9789-9810)
        # ──────────────────────────────────────────────────────────
        tasks = [
            gather_domain_data(brand),           # → availability.py
            gather_similarity_data(brand),       # → similarity.py
            gather_trademark_data(brand, classification_category),  # → trademark_research.py
            gather_visibility_data(brand),       # → visibility.py
            gather_multi_domain_data(brand),     # → availability.py
            gather_social_data(brand)            # → availability.py
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_brand_data[brand] = {
            "domain": results[0],
            "similarity": results[1],
            "trademark": results[2],
            "visibility": results[3],
            "multi_domain": results[4],
            "social": results[5],
            "classification": brand_classification,
            "linguistic_analysis": linguistic_analysis
        }
```

---

## 🔍 INTERNAL FUNCTION CALLS

### gather_domain_data() - Line 9654

```python
async def gather_domain_data(brand):
    """Check .com domain availability"""
    try:
        # Calls: availability.py → check_full_availability()
        domain_result = await check_full_availability(brand)
        return domain_result
        # Returns: {available: true/false, whois_data: {...}}
    except Exception as e:
        return {"available": None, "error": str(e)}
```

### gather_similarity_data() - Line 9663

```python
async def gather_similarity_data(brand):
    """Check phonetic similarity with competitors"""
    try:
        # Calls: similarity.py → check_brand_similarity()
        similar_brands = await asyncio.to_thread(
            check_brand_similarity,
            brand,
            request.category,
            request.known_competitors
        )
        return similar_brands
        # Returns: {similar_brands: [...], highest_similarity: 0.85}
    except Exception as e:
        return {"similar_brands": [], "error": str(e)}
```

### gather_trademark_data() - Line 9679

```python
async def gather_trademark_data(brand, classification_category):
    """Conduct trademark research via web search"""
    try:
        # Calls: trademark_research.py → conduct_trademark_research()
        tm_result = await conduct_trademark_research(
            brand_name=brand,
            category=request.category,
            countries=request.countries,
            classification=classification_category
        )
        return {
            "prompt_data": format_research_for_prompt(tm_result),
            "result": tm_result,
            "success": True
        }
        # Returns: {
        #   overall_risk_score: 3,
        #   trademark_conflicts: [...],
        #   company_conflicts: [...],
        #   nice_class: 30
        # }
    except Exception as e:
        return {"prompt_data": f"Error: {e}", "result": None, "success": False}
```

### gather_visibility_data() - Line 9706

```python
async def gather_visibility_data(brand):
    """Check Google, App Store, Play Store presence"""
    try:
        # Calls: visibility.py → check_visibility()
        vis = await asyncio.to_thread(
            check_visibility,
            brand, 
            request.category, 
            request.industry,
            request.known_competitors,
            request.product_keywords
        )
        return vis
        # Returns: {
        #   google: ["result1", "result2"],
        #   apps: ["app1", "app2"],
        #   app_search_details: {...}
        # }
    except Exception as e:
        return {"google": [], "apps": [], "error": str(e)}
```

---

## 🏷️ CLASSIFICATION OVERRIDE LOGIC (Line 1202-1360)

```python
def classify_brand_with_linguistic_override(
    brand_name: str, 
    industry: str, 
    linguistic_analysis: dict = None
) -> dict:
    """
    STEP 1: Run standard English-based classification
    STEP 2: Override based on linguistic analysis
    """
    
    # STEP 1: Standard classification
    base_result = classify_brand_with_industry(brand_name, industry)
    # Returns: {category: "FANCIFUL", distinctiveness: "HIGHEST", ...}
    
    # STEP 2: Check linguistic override conditions
    if not linguistic_analysis:
        return base_result
    
    has_meaning = linguistic_analysis.get("has_linguistic_meaning", False)
    confidence = linguistic_analysis.get("confidence_assessment", {}).get("overall_confidence", "Low")
    
    # Skip override if low confidence
    if not has_meaning or confidence == "Low":
        base_result["linguistic_override"] = False
        return base_result
    
    # Extract linguistic data
    name_type = linguistic_analysis.get("classification", {}).get("name_type")
    alignment_score = linguistic_analysis.get("business_alignment", {}).get("alignment_score", 5)
    languages = linguistic_analysis.get("linguistic_analysis", {}).get("languages_detected", [])
    combined_meaning = linguistic_analysis.get("linguistic_analysis", {}).get("decomposition", {}).get("combined_meaning", "")
    
    original_category = base_result["category"]
    new_category = original_category
    
    # ══════════════════════════════════════════════════════════════
    # OVERRIDE RULES
    # ══════════════════════════════════════════════════════════════
    
    # RULE 1: Mythological/Heritage → SUGGESTIVE
    if name_type in ["Mythological", "Heritage"]:
        if original_category == "FANCIFUL":
            new_category = "SUGGESTIVE"
            override_reason = f"Name has {name_type} origin"
    
    # RULE 2: Foreign-Language → Check alignment
    elif name_type == "Foreign-Language":
        if alignment_score >= 7:
            new_category = "SUGGESTIVE"  # High alignment
        else:
            new_category = "ARBITRARY"   # Low alignment
    
    # RULE 3: Compound/Portmanteau → SUGGESTIVE
    elif name_type in ["Compound", "Portmanteau"]:
        new_category = "SUGGESTIVE"
    
    # RULE 4: Evocative → SUGGESTIVE
    elif name_type == "Evocative":
        new_category = "SUGGESTIVE"
    
    # RULE 5: True-Coined → Keep FANCIFUL
    elif name_type == "True-Coined":
        pass  # No change
    
    # ══════════════════════════════════════════════════════════════
    # RULE 6: CATCH-ALL (Line 1299-1310) ← THE FIX!
    # ══════════════════════════════════════════════════════════════
    if original_category == "FANCIFUL" and new_category == "FANCIFUL" and has_meaning and combined_meaning:
        if alignment_score >= 6:
            new_category = "SUGGESTIVE"
        else:
            new_category = "ARBITRARY"
    
    # Apply override
    if new_category != original_category:
        base_result["category"] = new_category
        base_result["linguistic_override"] = True
        base_result["original_category"] = original_category
        base_result["override_reason"] = override_reason
    
    return base_result
```

---

## 🌍 LINGUISTIC ANALYSIS (linguistic_analysis.py)

```python
# Line 152-224
async def analyze_brand_linguistics(
    brand_name: str,
    business_category: str,
    industry: str = ""
) -> Dict[str, Any]:
    """
    Uses LLM (gpt-4o-mini) to detect meaning in ANY world language
    """
    
    if not LLM_AVAILABLE or not EMERGENT_KEY:
        return _get_fallback_response(brand_name, business_category)
    
    # Build prompt from template
    prompt = LINGUISTIC_ANALYSIS_PROMPT.format(
        brand_name=brand_name,
        business_category=business_category
    )
    
    # Call LLM
    chat = LlmChat(EMERGENT_KEY, "openai", "gpt-4o-mini")
    user_msg = UserMessage(text=prompt)
    response = await chat.send_message(user_msg)
    
    # Parse JSON response
    result = json.loads(response)
    
    return result
    
    # ══════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE
    # ══════════════════════════════════════════════════════════════
    # {
    #   "brand_name": "CHAIDESH",
    #   "business_category": "Tea Brand",
    #   "has_linguistic_meaning": true,
    #   "is_truly_coined": false,
    #   "linguistic_analysis": {
    #     "languages_detected": ["Hindi", "Urdu"],
    #     "primary_language": "Hindi",
    #     "decomposition": {
    #       "can_be_decomposed": true,
    #       "parts": ["CHAI", "DESH"],
    #       "part_meanings": {
    #         "CHAI": {"meaning": "Tea", "language": "Hindi"},
    #         "DESH": {"meaning": "Country/Land", "language": "Hindi"}
    #       },
    #       "combined_meaning": "Tea Country / Land of Tea"
    #     }
    #   },
    #   "cultural_significance": {
    #     "has_cultural_reference": true,
    #     "reference_type": "Heritage",
    #     "regions_of_recognition": ["India", "Pakistan", "Bangladesh"]
    #   },
    #   "business_alignment": {
    #     "alignment_score": 9,
    #     "alignment_level": "Excellent",
    #     "explanation": "Name directly translates to 'Tea Country'"
    #   },
    #   "classification": {
    #     "name_type": "Foreign-Language",
    #     "distinctiveness_level": "High"
    #   }
    # }
```

---

## 📊 WEIGHTED NAMESCORE CALCULATION (Line 11502-11600)

```python
# Calculate weighted namescore
try:
    # Get all components
    ling_analysis = all_brand_data.get(brand_name, {}).get("linguistic_analysis", {})
    business_alignment = ling_analysis.get("business_alignment", {}).get("alignment_score", 5.0)
    
    # Trademark risk (inverse)
    tr_risk = 5.0
    if brand_score.trademark_research:
        tr_risk = brand_score.trademark_research.overall_risk_score
    
    # DuPont score
    dupont_score = None
    if brand_score.dupont_analysis and brand_score.dupont_analysis.get("has_analysis"):
        dupont_score = brand_score.dupont_analysis.get("highest_risk_conflict", {}).get("dupont_score")
    
    # Domain score
    domain_score = 8.0 if domain_available else 5.0
    
    # Social score
    social_score = (available_platforms / total_platforms) * 10
    
    # Cultural resonance (hybrid formula)
    cultural_scores = [ca.get("cultural_score", 7.0) for ca in cultural_analysis]
    if len(cultural_scores) == 1:
        cultural_resonance = cultural_scores[0]
    else:
        cultural_resonance = (min(cultural_scores) * 0.4) + (avg(cultural_scores) * 0.6)
    
    # LLM dimensions average
    llm_avg = sum([d.score for d in dimensions]) / len(dimensions)
    
    # ══════════════════════════════════════════════════════════════
    # WEIGHTED FORMULA
    # ══════════════════════════════════════════════════════════════
    weighted_score = (
        (llm_avg / 10)              * 0.40 +   # 40% - LLM Dimensions
        (cultural_resonance / 10)   * 0.15 +   # 15% - Cultural Resonance
        ((10 - tr_risk) / 10)       * 0.20 +   # 20% - Trademark Safety (inverse)
        (business_alignment / 10)   * 0.10 +   # 10% - Business Alignment
        (dupont_safety / 10)        * 0.10 +   # 10% - DuPont Safety
        (digital_score / 10)        * 0.05     #  5% - Digital Availability
    ) * 100
    
    brand_score.namescore = round(weighted_score, 1)

except Exception as e:
    # Fallback to simple average
    brand_score.namescore = sum([d.score for d in dimensions]) / len(dimensions) * 10
```

---

## 🖥️ FRONTEND FLOW (LandingPage.js → Dashboard.js)

### LandingPage.js - Form Submission (Line 286-374)

```javascript
const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    // Build payload from form data
    const payload = {
        brand_names: formData.brand_names.split(',').map(n => n.trim()),
        industry: formData.industry,
        category: formData.category,
        countries: formData.countries.split(',').map(c => c.trim()),
        positioning: formData.positioning,
        // ... more fields
    };
    
    // Call API with progress callback
    const result = await api.evaluate(payload, (progressData) => {
        setLoadingProgress({
            progress: progressData.progress,
            currentStep: progressData.currentStep,
            etaSeconds: progressData.etaSeconds
        });
    });
    
    // Navigate to dashboard with result
    navigate('/dashboard', { 
        state: { 
            data: result,      // Full API response
            query: payload     // Original request
        } 
    });
};
```

### Dashboard.js - Display Results (Line 3500+)

```javascript
const Dashboard = () => {
    const location = useLocation();
    const { data, query } = location.state || {};
    
    // Extract brand data
    const brand = data?.brand_scores?.[0];
    const linguisticAnalysis = brand?.universal_linguistic_analysis;
    const brandClassification = brand?.brand_classification;
    
    return (
        <>
            {/* Cover Page - Score & Verdict */}
            <CoverSection brand={brand} />
            
            {/* Evaluation Summary - 6 Dimensions Radar */}
            <EvaluationSummary dimensions={brand.dimensions} />
            
            {/* Universal Linguistic Analysis - NEW */}
            <LinguisticAnalysisSection 
                linguisticAnalysis={linguisticAnalysis}
                brandClassification={brandClassification}
            />
            
            {/* Final Assessment */}
            <FinalAssessment brand={brand} />
            
            {/* More sections... */}
        </>
    );
};
```

### LinguisticAnalysisSection Component (Line 1812-2100)

```javascript
const LinguisticAnalysisSection = ({ linguisticAnalysis, brandClassification }) => {
    
    // Extract data
    const hasMeaning = linguisticAnalysis.has_linguistic_meaning;
    const ling = linguisticAnalysis.linguistic_analysis || {};
    const alignment = linguisticAnalysis.business_alignment || {};
    
    // Get classification (with frontend safety override)
    const classificationData = brandClassification || {};
    let displayCategory = classificationData.category;
    
    // ══════════════════════════════════════════════════════════════
    // FRONTEND SAFETY CHECK - Override FANCIFUL if has meaning
    // ══════════════════════════════════════════════════════════════
    if (hasMeaning && displayCategory === 'FANCIFUL') {
        displayCategory = alignment.alignment_score >= 6 ? 'SUGGESTIVE' : 'ARBITRARY';
    }
    
    return (
        <div>
            {/* Name Has Linguistic Meaning / Truly Coined */}
            <h3>{hasMeaning ? '🌍 Name Has Linguistic Meaning' : '✨ Truly Coined Name'}</h3>
            
            {/* Morphological Breakdown */}
            {hasMeaning && ling.decomposition?.can_be_decomposed && (
                <div className="breakdown">
                    {ling.decomposition.parts.map(part => (
                        <span>{part} = {ling.decomposition.part_meanings[part].meaning}</span>
                    ))}
                    <p>Combined: "{ling.decomposition.combined_meaning}"</p>
                </div>
            )}
            
            {/* Trademark Classification Badge */}
            <div className="classification">
                <Badge>{displayCategory}</Badge>
                <p>Reason: {displayReason}</p>
            </div>
            
            {/* Business Alignment Score */}
            <div className="alignment">
                <CircularGauge value={alignment.alignment_score} max={10} />
                <span>{alignment.alignment_level}</span>
            </div>
        </div>
    );
};
```

---

## 📞 FUNCTION CALL SEQUENCE DIAGRAM

```
USER CLICKS "ANALYZE"
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ LandingPage.js::handleSubmit()                                                  │
│   └─> api.evaluate(payload, progressCallback)                                   │
│         └─> POST /api/evaluate                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ server.py::evaluate_brands(request)  [Line 9410]                                │
│   └─> evaluate_brands_internal(request)  [Line 9414]                            │
│         │                                                                       │
│         ├─> check_inappropriate_name(brand)  [GATE 0]                           │
│         │                                                                       │
│         ├─> check_early_stopping(brand)  [GATE 1]                               │
│         │     └─> deep_trace_analysis()  [similarity.py]                        │
│         │                                                                       │
│         │   ╔═══════════════════════════════════════════════════════╗          │
│         │   ║ FOR EACH BRAND:                                       ║          │
│         │   ╚═══════════════════════════════════════════════════════╝          │
│         │                                                                       │
│         ├─> analyze_brand_linguistics(brand)  [STEP 1]                          │
│         │     └─> linguistic_analysis.py::analyze_brand_linguistics()           │
│         │           └─> LlmChat("gpt-4o-mini").send_message()                   │
│         │                                                                       │
│         ├─> classify_brand_with_linguistic_override(brand, linguistic_data)     │
│         │     ├─> classify_brand_with_industry(brand)  [Standard]  [STEP 2]     │
│         │     └─> [OVERRIDE RULES 1-6]                                          │
│         │                                                                       │
│         ├─> asyncio.gather(  [STEP 3 - PARALLEL]                               │
│         │     gather_domain_data(brand),                                        │
│         │     │   └─> availability.py::check_full_availability()                │
│         │     │         └─> whois.whois(domain)                                 │
│         │     │                                                                 │
│         │     gather_similarity_data(brand),                                    │
│         │     │   └─> similarity.py::check_brand_similarity()                   │
│         │     │         └─> Jaro-Winkler, Soundex, Metaphone                   │
│         │     │                                                                 │
│         │     gather_trademark_data(brand),                                     │
│         │     │   └─> trademark_research.py::conduct_trademark_research()       │
│         │     │         └─> DuckDuckGo web search                               │
│         │     │         └─> Google Custom Search API                            │
│         │     │                                                                 │
│         │     gather_visibility_data(brand),                                    │
│         │     │   └─> visibility.py::check_visibility()                         │
│         │     │         └─> DuckDuckGo search                                   │
│         │     │         └─> App Store scraper                                   │
│         │     │                                                                 │
│         │     gather_multi_domain_data(brand),                                  │
│         │     │   └─> availability.py::check_multi_domain_availability()        │
│         │     │                                                                 │
│         │     gather_social_data(brand)                                         │
│         │     │   └─> availability.py::check_social_availability()              │
│         │   )                                                                   │
│         │                                                                       │
│         ├─> generate_cultural_analysis(countries, brand)  [STEP 4]              │
│         │     └─> calculate_fallback_cultural_score()                           │
│         │     └─> check_sacred_royal_names()                                    │
│         │                                                                       │
│         ├─> llm_first_country_analysis(countries, brand)  [STEP 5]              │
│         │     └─> market_intelligence.py::research_all_countries()              │
│         │           └─> LlmChat with web search                                 │
│         │                                                                       │
│         ├─> build_brand_score()  [STEP 6]                                       │
│         │     ├─> generate_intelligent_trademark_matrix()                       │
│         │     ├─> generate_rich_executive_summary()                             │
│         │     └─> [WEIGHTED NAMESCORE CALCULATION]                              │
│         │                                                                       │
│         └─> db.evaluations.insert_one(doc)  [Save to MongoDB]                   │
│                                                                                 │
│   RETURN: BrandEvaluationResponse                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ LandingPage.js                                                                  │
│   └─> navigate('/dashboard', { state: { data: result, query: payload } })       │
└─────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Dashboard.js                                                                    │
│   └─> const { data, query } = location.state                                    │
│   └─> <LinguisticAnalysisSection linguisticAnalysis={...} />                    │
│   └─> <FinalAssessment brand={...} />                                           │
│   └─> ... more sections ...                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📍 KEY LINE NUMBERS (server.py)

| Function | Line | Purpose |
|----------|------|---------|
| `evaluate_brands()` | 9410 | API entry point |
| `evaluate_brands_internal()` | 9414 | Main processing |
| `check_inappropriate_name()` | 9429 | GATE 0 |
| `analyze_brand_linguistics()` | 9755 | STEP 1 - Linguistic |
| `classify_brand_with_linguistic_override()` | 1202 | STEP 2 - Classification |
| `gather_*_data()` | 9654-9743 | STEP 3 - Parallel tasks |
| `generate_cultural_analysis()` | 2637 | STEP 4 - Cultural |
| `llm_first_country_analysis()` | 3016 | STEP 5 - Market research |
| `CATCH-ALL Override Rule` | 1299 | **THE FIX** |
| Weighted score calculation | 11502 | STEP 6 - Final score |
