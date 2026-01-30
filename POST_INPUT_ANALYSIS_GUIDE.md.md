# RightName.AI - Post-Input Analysis Pipeline

## 📊 Post-Input Flow Documentation

This document describes the LangGraph workflow that executes **after the user provides input** (brand name, markets, industry).

---

## 🏗️ Pipeline Overview

When the user clicks "Evaluate", the frontend sends a POST request to `/api/evaluate`. This triggers the following 6-step backend pipeline:

### **1. Linguistic Analysis**
- **Process**: Phonetic structure, pronunciation complexity, and readability.
- **Data**: Linguistic scores and phonetic insights.

### **2. Cultural Analysis**
- **Process**: Scans for slang, offensive meanings, and cultural nuances across multiple languages.
- **Data**: Safety flags and cultural meaning summaries.

### **3. Trademark Search**
- **Process**: Queries USPTO and other databases for similar marks.
- **Data**: List of conflicting marks and similarity percentages.

### **4. LLM Cultural Validation**
- **Process**: High-intelligence LLM review for deep contextual cultural risks.
- **Data**: Risk assessment reports and country-specific context.

### **5. Market Research**
- **Process**: Competitive analysis and market positioning potential.
- **Data**: Competitor lists and SEO/market strength insights.

### **6. Weighted Scoring**
- **Process**: Final calculation based on weighted averages:
  - **Trademark**: 30%
  - **Cultural**: 25%
  - **Linguistic**: 20%
  - **LLM Conflict**: 15%
  - **Market**: 10%
- **Data**: Final Score (0-100) and complete evaluation report.

---

## 🔄 Conditional Logic

### **Error Handling**
Every stage in the pipeline includes a conditional check:
- `continue`: Proceed to the next step if successful.
- `error`: Halt and return the error message if a critical failure occurs.

### **Trademark Risk Decision**
- `auto_approve`: Risk is low enough to proceed automatically.
- `manual_review`: Risk is high (Score < 50), flagged for admin attention (though pipeline continues to LLM for full data).

---

## 💻 Technical Implementation

**File:** `rightname_post_input_analysis.py`

### **How to use:**
1. **Initialize State**: Pass `brand_name`, `markets`, and `industry`.
2. **Execute**: Run the compiled graph.
3. **Output**: Access the `final_score` and generated analysis data.

---

## 🎨 Visualization

To see the visual graph:
```bash
python rightname_post_input_analysis.py
```

**Workflow Path:**
`START → Entry → Linguistic → Cultural → Trademark → LLM → Market → Scoring → END`

---

## 📝 Analysis State Schema

```python
{
    "brand_name": str,
    "markets": list,
    "industry": str,
    "scores": dict,
    "final_score": float,
    "linguistic_data": dict,
    "cultural_data": dict,
    "trademark_conflicts": list,
    "llm_validation": dict,
    "market_insights": dict,
    "is_complete": bool
}
```

---

## 🎓 Use Cases

- **Backend Devs**: Standardizing the evaluation sequence.
- **Product Managers**: Understanding how final scores are derived.
- **QA**: Testing individual nodes for edge cases (e.g., empty trademark results).
- **Client Education**: Explaining the "magic" behind the brand analysis.
