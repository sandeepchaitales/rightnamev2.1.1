#!/usr/bin/env python3
"""
Debug script to check the actual API response structure
"""

import requests
import json

def debug_api_response():
    api_url = "https://cultural-fit.preview.emergentagent.com/api"
    
    payload = {
        "brand_names": ["Check My Meal"],
        "category": "Doctor Appointment App",
        "positioning": "Mid-Range",
        "market_scope": "Multi-Country",
        "countries": ["India", "USA"]
    }
    
    print("🔍 Debugging API Response Structure...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{api_url}/evaluate", 
            json=payload, 
            headers={'Content-Type': 'application/json'},
            timeout=150
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print("\n📋 TOP-LEVEL KEYS:")
            for key in data.keys():
                print(f"  - {key}")
            
            if "brand_scores" in data and len(data["brand_scores"]) > 0:
                brand = data["brand_scores"][0]
                print(f"\n📋 BRAND OBJECT KEYS for '{brand.get('brand_name', 'Unknown')}':")
                for key in sorted(brand.keys()):
                    value = brand[key]
                    if isinstance(value, dict):
                        print(f"  - {key}: dict with {len(value)} keys")
                        for subkey in sorted(value.keys())[:5]:  # Show first 5 subkeys
                            print(f"    - {subkey}")
                        if len(value) > 5:
                            print(f"    - ... and {len(value) - 5} more")
                    elif isinstance(value, list):
                        print(f"  - {key}: list with {len(value)} items")
                    else:
                        print(f"  - {key}: {type(value).__name__}")
                
                # Look for classification-related fields
                print(f"\n🔍 SEARCHING FOR CLASSIFICATION FIELDS:")
                classification_fields = []
                for key, value in brand.items():
                    if "classif" in key.lower() or "category" in key.lower() or "type" in key.lower():
                        classification_fields.append(key)
                        print(f"  ✅ Found: {key} = {value}")
                
                if not classification_fields:
                    print("  ❌ No classification fields found")
                
                # Check cultural analysis structure
                if "cultural_analysis" in brand:
                    cultural = brand["cultural_analysis"]
                    print(f"\n🌍 CULTURAL ANALYSIS STRUCTURE:")
                    if isinstance(cultural, dict):
                        for key in sorted(cultural.keys())[:10]:
                            print(f"  - {key}")
                    else:
                        print(f"  Type: {type(cultural)}")
                
            else:
                print("❌ No brand_scores found in response")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    debug_api_response()