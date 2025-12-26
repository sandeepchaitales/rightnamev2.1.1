#!/usr/bin/env python3
"""
Quick backend verification tests for the review request
"""

import requests
import json
import sys
from datetime import datetime

def test_api_health():
    """Test basic API health"""
    try:
        response = requests.get("http://localhost:8001/api/", timeout=10)
        if response.status_code == 200:
            print("✅ API Health Check - PASSED")
            return True
        else:
            print(f"❌ API Health Check - FAILED: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API Health Check - FAILED: {str(e)}")
        return False

def test_evaluate_basic():
    """Test basic evaluate endpoint"""
    payload = {
        "brand_names": ["QuickTest"],
        "category": "Technology",
        "positioning": "Premium",
        "market_scope": "Single Country",
        "countries": ["USA"]
    }
    
    try:
        print("🔍 Testing basic evaluate endpoint...")
        response = requests.post(
            "http://localhost:8001/api/evaluate",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            if "brand_scores" in data and len(data["brand_scores"]) > 0:
                brand = data["brand_scores"][0]
                if "namescore" in brand and "verdict" in brand:
                    print(f"✅ Basic Evaluate Test - PASSED (NameScore: {brand['namescore']}, Verdict: {brand['verdict']})")
                    return True
        
        print(f"❌ Basic Evaluate Test - FAILED: {response.status_code}")
        return False
        
    except Exception as e:
        print(f"❌ Basic Evaluate Test - FAILED: {str(e)}")
        return False

def main():
    print("🚀 Quick Backend Verification Tests")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: API Health
    if test_api_health():
        tests_passed += 1
    
    # Test 2: Basic Evaluate
    if test_evaluate_basic():
        tests_passed += 1
    
    print("=" * 40)
    print(f"📊 Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ All quick tests PASSED")
        return 0
    else:
        print("❌ Some tests FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())