#!/usr/bin/env python3
"""
Test Finance NICE class fix
"""

import requests
import time
import json

def test_finance_nice_class():
    print("💰 Testing NICE Class for Finance/Payments...")
    
    payload = {
        "brand_names": ["TestFinance2025"],
        "category": "Finance/Payments",
        "positioning": "Premium",
        "market_scope": "Single Country", 
        "countries": ["India"]
    }
    
    try:
        # Start evaluation
        response = requests.post(
            "https://rightname-enhance.preview.emergentagent.com/api/evaluate/start",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Start failed: {response.status_code}")
            return False
            
        job_data = response.json()
        job_id = job_data.get("job_id")
        print(f"Job ID: {job_id}")
        
        # Wait for completion
        time.sleep(60)  # Wait 1 minute
        
        status_response = requests.get(
            f"https://rightname-enhance.preview.emergentagent.com/api/evaluate/status/{job_id}",
            timeout=10
        )
        
        if status_response.status_code == 200:
            status_data = status_response.json()
            
            if status_data.get("status") == "completed":
                result = status_data.get("result", {})
                brand = result.get("brand_scores", [{}])[0]
                
                tm_research = brand.get("trademark_research", {})
                nice_class = tm_research.get("nice_classification", {}) if tm_research else {}
                class_number = nice_class.get("class_number")
                class_description = nice_class.get("class_description", "")
                matched_term = nice_class.get("matched_term", "")
                
                print(f"\n✅ Evaluation completed:")
                print(f"   - Brand: TestFinance2025")
                print(f"   - Category: Finance/Payments")
                print(f"   - NICE Class: {class_number}")
                print(f"   - Description: {class_description}")
                print(f"   - Matched Term: {matched_term}")
                
                if class_number == 36:
                    print(f"\n🎉 SUCCESS: NICE Class 36 correctly assigned for Finance/Payments!")
                    return True
                else:
                    print(f"\n❌ FAILURE: Expected Class 36, got Class {class_number}")
                    return False
            else:
                print(f"Status: {status_data.get('status')}")
                return False
        else:
            print(f"Status check failed: {status_response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

if __name__ == "__main__":
    success = test_finance_nice_class()
    if success:
        print("\n🎯 FINANCE NICE CLASS FIX IS WORKING!")
    else:
        print("\n⚠️ FINANCE NICE CLASS FIX NEEDS ATTENTION")