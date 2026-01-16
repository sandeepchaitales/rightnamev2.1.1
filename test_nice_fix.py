#!/usr/bin/env python3
"""
Quick test for NICE class fix after backend restart
"""

import requests
import time
import json

def test_nice_class_fix():
    print("🔧 Testing NICE Class Fix After Backend Restart")
    print("="*60)
    
    payload = {
        "brand_names": ["TestClean2025"],
        "category": "Cleaning solutions",
        "positioning": "Premium",
        "market_scope": "Single Country", 
        "countries": ["India"]
    }
    
    try:
        # Start evaluation
        response = requests.post(
            "https://namewise-1.preview.emergentagent.com/api/evaluate/start",
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
        
        # Poll for completion
        for i in range(30):  # 30 * 4 = 120 seconds max
            time.sleep(4)
            
            status_response = requests.get(
                f"https://namewise-1.preview.emergentagent.com/api/evaluate/status/{job_id}",
                timeout=10
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                if status_data.get("status") == "completed":
                    result = status_data.get("result", {})
                    brand = result.get("brand_scores", [{}])[0]
                    
                    verdict = brand.get("verdict", "")
                    tm_research = brand.get("trademark_research", {})
                    nice_class = tm_research.get("nice_classification", {}) if tm_research else {}
                    class_number = nice_class.get("class_number")
                    class_description = nice_class.get("class_description", "")
                    
                    print(f"\n✅ Evaluation completed:")
                    print(f"   - Brand: TestClean2025")
                    print(f"   - Category: Cleaning solutions")
                    print(f"   - Verdict: {verdict}")
                    print(f"   - NICE Class: {class_number}")
                    print(f"   - Description: {class_description}")
                    
                    if class_number == 3:
                        print(f"\n🎉 SUCCESS: NICE Class 3 correctly assigned for Cleaning solutions!")
                        return True
                    else:
                        print(f"\n❌ FAILURE: Expected Class 3, got Class {class_number}")
                        print(f"   This indicates the NICE class fix is not working properly")
                        return False
                        
                elif status_data.get("status") == "failed":
                    print(f"❌ Job failed: {status_data.get('error')}")
                    return False
                else:
                    print(f"⏳ Status: {status_data.get('status')} (attempt {i+1}/30)")
            else:
                print(f"⚠️ Status check failed: {status_response.status_code}")
        
        print("❌ Timeout after 2 minutes")
        return False
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

if __name__ == "__main__":
    success = test_nice_class_fix()
    if success:
        print("\n🎯 NICE CLASS FIX IS WORKING!")
    else:
        print("\n⚠️ NICE CLASS FIX NEEDS ATTENTION")