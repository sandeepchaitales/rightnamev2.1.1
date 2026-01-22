# CONFLICT VERIFICATION - Code Flow

## 📍 WHERE IT'S DISPLAYED

**Frontend:** `/app/frontend/src/pages/Dashboard.js` (Line 1063-1090)

```
┌─────────────────────────────────────────────┐
│ Conflict Verification                       │
│                                             │
│ Active Trademark      [YES] or [NO]         │
│ Operating Business    [YES] or [NO]         │
│                                             │
│ ✅ No trademark or active business found    │
│ -- OR --                                    │
│ ⚠️ Existing trademark found - Review        │
└─────────────────────────────────────────────┘
```

---

## 🔄 DATA FLOW

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 1. TRADEMARK RESEARCH (trademark_research.py)                                   │
│                                                                                 │
│    conduct_trademark_research(brand_name, category, countries)                  │
│    │                                                                            │
│    ├── Web Search (DuckDuckGo + Google)                                        │
│    │   └── Search: "{brand_name} trademark", "{brand_name} company"            │
│    │                                                                            │
│    ├── extract_trademark_conflicts(search_results)                             │
│    │   └── Returns: [{name, status, class, jurisdiction, risk_level}, ...]     │
│    │                                                                            │
│    └── extract_company_conflicts(search_results)                               │
│        └── Returns: [{name, type, jurisdiction, risk_level}, ...]              │
│                                                                                 │
│    RETURNS:                                                                     │
│    {                                                                            │
│      "trademark_conflicts": [                                                   │
│        {"name": "ChaiDesh Inc", "status": "REGISTERED", "class": 30, ...}      │
│      ],                                                                         │
│      "company_conflicts": [                                                     │
│        {"name": "Chaidesh Foods Pvt Ltd", "type": "ACTIVE", ...}               │
│      ]                                                                          │
│    }                                                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 2. BUILD DOMAIN_ANALYSIS (server.py - Line 10792-10806)                        │
│                                                                                 │
│    # DERIVE has_trademark and has_active_business from trademark_data          │
│                                                                                 │
│    "domain_analysis": {                                                         │
│        "exact_match_status": "TAKEN" if not domain_available else "AVAILABLE", │
│        "risk_level": "LOW" if trademark_risk <= 3 else "MEDIUM/HIGH",          │
│                                                                                 │
│        # ═══════════════════════════════════════════════════════════════════   │
│        # CONFLICT VERIFICATION FIELDS (THE FIX!)                               │
│        # ═══════════════════════════════════════════════════════════════════   │
│                                                                                 │
│        "has_active_business": "YES" if len(company_conflicts) > 0 else "NO",   │
│        "has_trademark": "YES" if len(trademark_conflicts) > 0 else "NO",       │
│                                                                                 │
│        "primary_domain": f"{brand_name.lower()}.com",                          │
│        "alternatives": [...],                                                   │
│        ...                                                                      │
│    }                                                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 3. API RESPONSE (BrandScore.domain_analysis)                                    │
│                                                                                 │
│    {                                                                            │
│      "brand_scores": [{                                                         │
│        "domain_analysis": {                                                     │
│          "has_trademark": "YES",        ← Derived from trademark_conflicts     │
│          "has_active_business": "NO",   ← Derived from company_conflicts       │
│          ...                                                                    │
│        }                                                                        │
│      }]                                                                         │
│    }                                                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 4. FRONTEND DISPLAY (Dashboard.js - Line 1063-1090)                            │
│                                                                                 │
│    const domainAnalysis = brand.domain_analysis;                               │
│                                                                                 │
│    <Badge>{domainAnalysis.has_trademark || 'UNKNOWN'}</Badge>                  │
│    <Badge>{domainAnalysis.has_active_business || 'UNKNOWN'}</Badge>            │
│                                                                                 │
│    {/* Dynamic message based on conflict status */}                            │
│    {domainAnalysis.has_trademark === 'YES' ? (                                 │
│        <p>⚠️ Existing trademark found</p>                                      │
│    ) : (                                                                        │
│        <p>✅ No trademark or active business found</p>                         │
│    )}                                                                           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📍 KEY CODE LOCATIONS

| Component | File | Line |
|-----------|------|------|
| Trademark Search | `/app/backend/trademark_research.py` | `conduct_trademark_research()` |
| Extract TM Conflicts | `/app/backend/trademark_research.py` | Line 764: `extract_trademark_conflicts()` |
| Extract Company Conflicts | `/app/backend/trademark_research.py` | Line 837: `extract_company_conflicts()` |
| Build domain_analysis | `/app/backend/server.py` | Line 10792-10806 |
| **has_trademark derivation** | `/app/backend/server.py` | **Line 10797** |
| **has_active_business derivation** | `/app/backend/server.py` | **Line 10796** |
| Frontend Display | `/app/frontend/src/pages/Dashboard.js` | Line 1063-1090 |

---

## 🔧 THE FIX (Applied)

### Before (Always UNKNOWN):
```python
"has_active_business": "UNKNOWN",
"has_trademark": "UNKNOWN",
```

### After (Derived from trademark research):
```python
# Derive has_trademark from trademark_conflicts
"has_active_business": "YES" if (isinstance(trademark_data, dict) and len(trademark_data.get("company_conflicts", [])) > 0) else "NO",
"has_trademark": "YES" if (isinstance(trademark_data, dict) and len(trademark_data.get("trademark_conflicts", [])) > 0) else "NO",
```

---

## 📊 DECISION LOGIC

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CONFLICT VERIFICATION LOGIC                              │
└─────────────────────────────────────────────────────────────────────────────────┘

                    trademark_research.py
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│ trademark_conflicts │         │ company_conflicts   │
│ (Array)             │         │ (Array)             │
│                     │         │                     │
│ Examples:           │         │ Examples:           │
│ - "CHAIDESH" TM     │         │ - "ChaiDesh Pvt Ltd"│
│   Class 30 (Tea)    │         │   CIN: U12345...    │
│ - "Chai Desh" TM    │         │ - "ChaiDesh Foods"  │
│   Status: PENDING   │         │   Status: ACTIVE    │
└─────────┬───────────┘         └───────────┬─────────┘
          │                                 │
          ▼                                 ▼
┌─────────────────────┐         ┌─────────────────────┐
│ len() > 0 ?         │         │ len() > 0 ?         │
│                     │         │                     │
│ YES → has_trademark │         │ YES → has_active_   │
│       = "YES"       │         │       business="YES"│
│                     │         │                     │
│ NO  → has_trademark │         │ NO  → has_active_   │
│       = "NO"        │         │       business="NO" │
└─────────────────────┘         └─────────────────────┘
          │                                 │
          └─────────────┬───────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │ FRONTEND DISPLAY    │
              │                     │
              │ Active Trademark:   │
              │ [YES/NO Badge]      │
              │                     │
              │ Operating Business: │
              │ [YES/NO Badge]      │
              │                     │
              │ Dynamic message:    │
              │ ✅ or ⚠️           │
              └─────────────────────┘
```

---

## 🧪 EXAMPLE SCENARIOS

### Scenario 1: No Conflicts Found
```
trademark_conflicts: []
company_conflicts: []

→ has_trademark: "NO"
→ has_active_business: "NO"
→ Display: "✅ No trademark or active business found"
```

### Scenario 2: Trademark Found Only
```
trademark_conflicts: [{"name": "CHAIDESH", "class": 30, "status": "REGISTERED"}]
company_conflicts: []

→ has_trademark: "YES"
→ has_active_business: "NO"
→ Display: "⚠️ Existing trademark found - Review conflicts"
```

### Scenario 3: Company Found Only
```
trademark_conflicts: []
company_conflicts: [{"name": "ChaiDesh Pvt Ltd", "type": "ACTIVE"}]

→ has_trademark: "NO"
→ has_active_business: "YES"
→ Display: "⚠️ Active business found - Review conflicts"
```

### Scenario 4: Both Found (HIGH RISK)
```
trademark_conflicts: [{"name": "CHAIDESH", ...}]
company_conflicts: [{"name": "ChaiDesh Pvt Ltd", ...}]

→ has_trademark: "YES"
→ has_active_business: "YES"
→ Display: "⚠️ Both trademark and active business found - HIGH RISK"
```
