# RightName.AI - LangGraph Workflow Visualization

## 📊 Overview

This LangGraph represents the **complete website flow** for RightName.AI, a brand name analysis platform. It maps out:

- ✅ User journey from landing page to report download
- ✅ 6-step backend analysis pipeline
- ✅ Payment processing workflow
- ✅ Admin panel access
- ✅ All conditional logic and decision points

---

## 🏗️ Graph Structure

### **Total Components:**
- **17 Nodes** (states/pages)
- **Multiple Edges** (transitions)
- **3 Conditional Branches**

### **Key Nodes:**

#### Frontend Flow:
1. `landing_page` - Entry point
2. `authentication` - OAuth login
3. `dashboard` - User dashboard
4. `brand_input` - Brand name input form

#### Analysis Pipeline (Sequential):
5. `linguistic_analysis` - STEP 1: Phonetics & pronunciation
6. `cultural_analysis` - STEP 2: Cross-cultural validation
7. `trademark_search` - STEP 3: USPTO search
8. `llm_country_analysis` - STEP 4: LLM-based deep validation
9. `market_research` - STEP 5: Competitive analysis
10. `final_scoring` - STEP 6: Weighted score calculation

#### Payment & Reports:
11. `report_preview` - Free preview
12. `payment_gateway` - Payment processing
13. `payment_success` - Payment confirmation
14. `payment_cancel` - Payment failure
15. `full_report_access` - Complete report access
16. `my_reports` - User's saved reports

#### Admin:
17. `admin_panel` - Admin management

---

## 🚀 Installation

```bash
# Install dependencies
pip install langgraph grandalf typing-extensions

# For visualization
pip install matplotlib pillow
```

---

## 💻 Usage

### Run the script to generate visualization:

```bash
python rightname_langgraph_flow.py
```

### Output:
1. **PNG Image**: `rightname_workflow.png` - Visual graph
2. **Mermaid Diagram**: Printed to console
3. **Graph Info**: Node and edge count

---

## 🔄 Workflow Paths

### **Main User Journey:**
```
START → landing_page → authentication → dashboard → brand_input
  ↓
linguistic_analysis → cultural_analysis → trademark_search
  ↓
llm_country_analysis → market_research → final_scoring
  ↓
report_preview → payment_gateway → payment_success
  ↓
full_report_access → my_reports → dashboard → END
```

### **Alternative Paths:**
- **Failed Authentication**: Returns to landing page
- **Payment Cancelled**: Returns to report preview
- **Free Access**: Skips payment gateway
- **Admin Access**: dashboard → admin_panel → END

---

## 🎯 Conditional Logic

### 1. **Authentication Check**
```python
check_authentication()
  ├─ authenticated → dashboard
  └─ not_authenticated → landing_page
```

### 2. **Payment Requirement**
```python
needs_payment()
  ├─ requires_payment → payment_gateway
  └─ free_access → full_report_access
```

### 3. **Payment Status**
```python
check_payment()
  ├─ payment_success → payment_success
  └─ payment_cancel → payment_cancel
```

---

## 📈 Analysis Pipeline Details

### **Scoring System:**
- **Linguistic**: 20% weight
- **Cultural**: 25% weight
- **Trademark**: 30% weight
- **Conflict**: 15% weight
- **Market**: 10% weight

**Final Score = Weighted Average (0-100)**

---

## 🎨 Visualization

The generated graph will show:
- **Nodes**: Circular/rectangular shapes representing states
- **Edges**: Arrows showing transitions
- **Conditional Edges**: Diamond shapes for decisions
- **Color Coding**: Different colors for different flow sections

---

## 🔧 Customization

To modify the workflow:

1. **Add new nodes**: Use `workflow.add_node(name, function)`
2. **Add edges**: Use `workflow.add_edge(from, to)`
3. **Add conditions**: Use `workflow.add_conditional_edges()`

---

## 📝 State Schema

```python
RightNameState:
  - user_id: str
  - session_id: str
  - is_authenticated: bool
  - brand_name: str
  - target_markets: list[str]
  - industry: str
  - linguistic_score: float
  - cultural_score: float
  - trademark_score: float
  - conflict_score: float
  - market_score: float
  - final_score: float
  - report_id: str
  - report_generated: bool
  - payment_required: bool
  - payment_completed: bool
  - current_step: str
  - error_message: str
```

---

## 🎓 Use Cases

1. **Developer Onboarding**: Understand the complete flow
2. **Feature Planning**: Identify integration points
3. **Bug Tracking**: Trace user path for issues
4. **Documentation**: Visual system architecture
5. **Process Optimization**: Identify bottlenecks

---

## 🐛 Troubleshooting

### Error: Module not found
```bash
pip install langgraph
```

### Visualization not generating
```bash
pip install grandalf matplotlib
```

### PNG not saving
Check write permissions in the current directory.

---

## 📚 Additional Resources

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [RightName.AI Documentation](./CODE_FLOW_DESIGN.md)
- [Complete Report Flow](./COMPLETE_REPORT_FLOW.md)

---

## 📄 License

Part of RightName.AI project.

---

**Created by:** RightName.AI Development Team  
**Last Updated:** January 30, 2026
