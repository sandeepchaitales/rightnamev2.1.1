#!/usr/bin/env python3
"""
Quick test for trademark research functionality only
"""
import requests
import json
import sys

def test_trademark_research():
    """Test the trademark research feature with Luminara"""
    base_url = "https://brand-guard.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    # Test Case 1: Luminara (Fashion/Streetwear/India)
    payload = {
        "brand_names": ["Luminara"],
        "industry": "Fashion and Apparel",
        "category": "Streetwear",
        "product_type": "Clothing",
        "usp": "Premium urban streetwear",
        "brand_vibe": "Modern, Bold",
        "positioning": "Premium",
        "market_scope": "Single Country",
        "countries": ["India"]
    }
    
    print("🔍 Testing trademark research with Luminara...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{api_url}/evaluate", 
            json=payload, 
            headers={'Content-Type': 'application/json'},
            timeout=120
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check basic structure
            if not data.get("brand_scores"):
                print("❌ No brand_scores in response")
                return False
            
            brand = data["brand_scores"][0]
            print(f"✅ Brand name: {brand.get('brand_name')}")
            print(f"✅ NameScore: {brand.get('namescore')}")
            print(f"✅ Verdict: {brand.get('verdict')}")
            
            # Check trademark research
            if "trademark_research" not in brand:
                print("❌ trademark_research field missing")
                return False
            
            tm_research = brand["trademark_research"]
            if not tm_research:
                print("❌ trademark_research is null/empty")
                return False
            
            print(f"✅ Overall Risk Score: {tm_research.get('overall_risk_score')}/10")
            print(f"✅ Registration Success Probability: {tm_research.get('registration_success_probability')}%")
            print(f"✅ Opposition Probability: {tm_research.get('opposition_probability')}%")
            
            # Check conflicts
            tm_conflicts = tm_research.get("trademark_conflicts", [])
            co_conflicts = tm_research.get("company_conflicts", [])
            legal_precedents = tm_research.get("legal_precedents", [])
            
            print(f"✅ Trademark Conflicts Found: {len(tm_conflicts)}")
            for i, conflict in enumerate(tm_conflicts[:3], 1):
                print(f"   {i}. {conflict.get('name')} (App #{conflict.get('application_number', 'N/A')}) - {conflict.get('risk_level')}")
            
            print(f"✅ Company Conflicts Found: {len(co_conflicts)}")
            for i, conflict in enumerate(co_conflicts[:3], 1):
                print(f"   {i}. {conflict.get('name')} (CIN: {conflict.get('cin', 'N/A')}) - {conflict.get('risk_level')}")
            
            print(f"✅ Legal Precedents Found: {len(legal_precedents)}")
            for i, precedent in enumerate(legal_precedents[:2], 1):
                print(f"   {i}. {precedent.get('case_name')} ({precedent.get('year', 'N/A')})")
            
            # Check registration timeline
            if "registration_timeline" in brand:
                timeline = brand["registration_timeline"]
                print(f"✅ Registration Timeline: {timeline.get('estimated_duration')}")
                print(f"✅ Filing Cost: {timeline.get('filing_cost', 'N/A')}")
                print(f"✅ Total Cost: {timeline.get('total_estimated_cost', 'N/A')}")
            else:
                print("❌ registration_timeline field missing")
                return False
            
            # Check mitigation strategies
            if "mitigation_strategies" in brand:
                strategies = brand["mitigation_strategies"]
                print(f"✅ Mitigation Strategies: {len(strategies)} found")
                for i, strategy in enumerate(strategies[:2], 1):
                    print(f"   {i}. {strategy.get('action', 'N/A')} (Priority: {strategy.get('priority', 'N/A')})")
            else:
                print("❌ mitigation_strategies field missing")
                return False
            
            # Check Nice Classification
            nice_class = tm_research.get("nice_classification", {})
            if nice_class:
                print(f"✅ Nice Classification: Class {nice_class.get('class_number')} - {nice_class.get('class_description')}")
            else:
                print("⚠️ Nice Classification not found")
            
            print("\n🎉 Trademark research test PASSED!")
            return True
            
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_nexofy():
    """Test with unique brand name"""
    base_url = "https://brand-guard.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    # Test Case 2: Nexofy (unique name)
    payload = {
        "brand_names": ["Nexofy"],
        "industry": "Technology",
        "category": "SaaS",
        "product_type": "Software",
        "usp": "AI-powered automation",
        "brand_vibe": "Innovative",
        "positioning": "Premium",
        "market_scope": "Global",
        "countries": ["USA", "UK", "India"]
    }
    
    print("\n🔍 Testing trademark research with Nexofy (unique name)...")
    
    try:
        response = requests.post(
            f"{api_url}/evaluate", 
            json=payload, 
            headers={'Content-Type': 'application/json'},
            timeout=120
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            brand = data["brand_scores"][0]
            tm_research = brand["trademark_research"]
            
            risk_score = tm_research.get("overall_risk_score")
            success_prob = tm_research.get("registration_success_probability")
            
            print(f"✅ Risk Score: {risk_score}/10 (Expected: Low)")
            print(f"✅ Success Probability: {success_prob}% (Expected: High)")
            
            if risk_score <= 4 and success_prob >= 70:
                print("🎉 Nexofy test PASSED - Low risk as expected!")
                return True
            else:
                print(f"❌ Nexofy test FAILED - Risk too high or success too low")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Trademark Research Tests...")
    
    success1 = test_trademark_research()
    success2 = test_nexofy()
    
    if success1 and success2:
        print("\n✅ All trademark research tests PASSED!")
        sys.exit(0)
    else:
        print("\n❌ Some tests FAILED!")
        sys.exit(1)