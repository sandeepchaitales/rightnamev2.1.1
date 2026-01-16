#!/usr/bin/env python3
"""
Quick test for the remaining two critical fixes
"""

import requests
import time
import json

def test_nice_class_cleaning():
    """Test NICE Class for Cleaning Solutions"""
    print("🧽 Testing NICE Class for Cleaning Solutions...")
    
    payload = {
        "brand_names": ["UniqueClean2025"],
        "category": "Cleaning solutions", 
        "positioning": "Premium",
        "market_scope": "Single Country",
        "countries": ["India"]
    }
    
    try:
        # Start job
        response = requests.post(
            "https://namewise-1.preview.emergentagent.com/api/evaluate/start",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"❌ Start failed: {response.status_code}")
            return False
            
        job_data = response.json()
        job_id = job_data.get("job_id")
        print(f"Job ID: {job_id}")
        
        # Poll for 2 minutes
        for i in range(24):  # 24 * 5 = 120 seconds
            time.sleep(5)
            
            status_response = requests.get(
                f"https://namewise-1.preview.emergentagent.com/api/evaluate/status/{job_id}",
                timeout=30
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                if status_data.get("status") == "completed":
                    result = status_data.get("result", {})
                    brand = result.get("brand_scores", [{}])[0]
                    
                    verdict = brand.get("verdict", "")
                    tm_research = brand.get("trademark_research", {})
                    nice_class = tm_research.get("nice_classification", {})
                    class_number = nice_class.get("class_number")
                    
                    print(f"✅ Completed:")
                    print(f"   - Verdict: {verdict}")
                    print(f"   - NICE Class: {class_number}")
                    print(f"   - Description: {nice_class.get('class_description', '')}")
                    
                    if class_number == 3:
                        print("✅ NICE Class 3 CORRECT for Cleaning Solutions!")
                        return True
                    else:
                        print(f"❌ Expected Class 3, got Class {class_number}")
                        return False
                        
                elif status_data.get("status") == "failed":
                    print(f"❌ Job failed: {status_data.get('error')}")
                    return False
                else:
                    print(f"⏳ Status: {status_data.get('status')}")
            else:
                print(f"⚠️ Status check failed: {status_response.status_code}")
        
        print("❌ Timeout after 2 minutes")
        return False
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_nice_class_finance():
    """Test NICE Class for Finance/Payments"""
    print("\n💰 Testing NICE Class for Finance/Payments...")
    
    payload = {
        "brand_names": ["FinoPayX2025"],
        "category": "Finance/Payments",
        "positioning": "Premium", 
        "market_scope": "Single Country",
        "countries": ["India"]
    }
    
    try:
        # Start job
        response = requests.post(
            "https://namewise-1.preview.emergentagent.com/api/evaluate/start",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"❌ Start failed: {response.status_code}")
            return False
            
        job_data = response.json()
        job_id = job_data.get("job_id")
        print(f"Job ID: {job_id}")
        
        # Poll for 2 minutes
        for i in range(24):  # 24 * 5 = 120 seconds
            time.sleep(5)
            
            status_response = requests.get(
                f"https://namewise-1.preview.emergentagent.com/api/evaluate/status/{job_id}",
                timeout=30
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                if status_data.get("status") == "completed":
                    result = status_data.get("result", {})
                    brand = result.get("brand_scores", [{}])[0]
                    
                    verdict = brand.get("verdict", "")
                    tm_research = brand.get("trademark_research", {})
                    nice_class = tm_research.get("nice_classification", {})
                    class_number = nice_class.get("class_number")
                    
                    print(f"✅ Completed:")
                    print(f"   - Verdict: {verdict}")
                    print(f"   - NICE Class: {class_number}")
                    print(f"   - Description: {nice_class.get('class_description', '')}")
                    
                    if class_number == 36:
                        print("✅ NICE Class 36 CORRECT for Finance/Payments!")
                        return True
                    else:
                        print(f"❌ Expected Class 36, got Class {class_number}")
                        return False
                        
                elif status_data.get("status") == "failed":
                    print(f"❌ Job failed: {status_data.get('error')}")
                    return False
                else:
                    print(f"⏳ Status: {status_data.get('status')}")
            else:
                print(f"⚠️ Status check failed: {status_response.status_code}")
        
        print("❌ Timeout after 2 minutes")
        return False
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

if __name__ == "__main__":
    print("🔥 CRITICAL FIXES - NICE CLASS TESTING")
    print("="*50)
    
    result1 = test_nice_class_cleaning()
    result2 = test_nice_class_finance()
    
    print(f"\n📊 RESULTS:")
    print(f"   - Cleaning Solutions → Class 3: {'✅ PASS' if result1 else '❌ FAIL'}")
    print(f"   - Finance/Payments → Class 36: {'✅ PASS' if result2 else '❌ FAIL'}")
    
    if result1 and result2:
        print("🎉 ALL NICE CLASS FIXES WORKING!")
    else:
        print("⚠️ Some NICE class fixes need attention")