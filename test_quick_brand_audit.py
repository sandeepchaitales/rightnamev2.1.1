#!/usr/bin/env python3
"""
Quick test for Brand Audit API to check if it's responding
"""

import requests
import json
import time

def test_brand_audit_quick():
    url = "https://cultural-fit.preview.emergentagent.com/api/brand-audit"
    payload = {
        "brand_name": "QuickTest",
        "brand_website": "https://quicktest.com",
        "category": "Technology",
        "geography": "USA",
        "competitor_1": "CompA",
        "competitor_2": "CompB"
    }
    
    print("🔍 Quick Brand Audit API Test")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("Timeout: 60 seconds")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        processing_time = time.time() - start_time
        print(f"\nResponse Status: {response.status_code}")
        print(f"Processing Time: {processing_time:.2f} seconds")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ SUCCESS: Got 200 OK with JSON response")
                print(f"Response keys: {list(data.keys())}")
                
                if "report_id" in data:
                    print(f"Report ID: {data['report_id']}")
                if "overall_score" in data:
                    print(f"Overall Score: {data['overall_score']}")
                if "verdict" in data:
                    print(f"Verdict: {data['verdict']}")
                if "dimensions" in data:
                    print(f"Dimensions: {len(data['dimensions'])} items")
                
                return True
            except json.JSONDecodeError as e:
                print(f"❌ JSON Parse Error: {e}")
                print(f"Response text: {response.text[:200]}...")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text[:300]}...")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

if __name__ == "__main__":
    success = test_brand_audit_quick()
    exit(0 if success else 1)