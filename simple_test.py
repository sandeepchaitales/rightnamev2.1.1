#!/usr/bin/env python3
import requests
import json
import time

def test_quicktest_api():
    """Simple test for QuickTest API"""
    url = "https://name-analytics.preview.emergentagent.com/api/evaluate"
    
    payload = {
        "brand_names": ["QuickTest"],
        "category": "Technology",
        "positioning": "Premium",
        "market_scope": "Single Country",
        "countries": ["USA"]
    }
    
    print("🔍 Testing RIGHTNAME API with QuickTest...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        print("⏳ Sending request (timeout: 300 seconds)...")
        start_time = time.time()
        
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=300  # 5 minutes timeout
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"⏱️  Response received in {duration:.1f} seconds")
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ JSON parsing successful")
                
                # Check basic structure
                if "brand_scores" in data and len(data["brand_scores"]) > 0:
                    brand = data["brand_scores"][0]
                    print(f"✅ Brand: {brand.get('brand_name', 'N/A')}")
                    print(f"✅ NameScore: {brand.get('namescore', 'N/A')}/100")
                    print(f"✅ Verdict: {brand.get('verdict', 'N/A')}")
                    
                    # Check for legal precedents
                    if "trademark_research" in brand and brand["trademark_research"]:
                        tm_research = brand["trademark_research"]
                        if "legal_precedents" in tm_research:
                            precedents = tm_research["legal_precedents"]
                            print(f"✅ Legal Precedents: {len(precedents)} cases found")
                            
                            # Check for USA cases
                            usa_cases = []
                            for precedent in precedents:
                                if isinstance(precedent, dict):
                                    case_name = precedent.get("case_name", "")
                                    court = precedent.get("court", "")
                                    if any(usa in court.lower() for usa in ["usa", "united states", "us", "federal"]):
                                        usa_cases.append(case_name)
                                    if "polaroid" in case_name.lower():
                                        print(f"✅ Found Polaroid case: {case_name}")
                            
                            if usa_cases:
                                print(f"✅ USA cases found: {len(usa_cases)}")
                            else:
                                print("⚠️  No USA cases found")
                        else:
                            print("❌ No legal_precedents field found")
                    else:
                        print("❌ No trademark_research field found")
                    
                    print("\n🎉 QUICKTEST SMOKE TEST: SUCCESS")
                    return True
                else:
                    print("❌ No brand_scores found in response")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed: {e}")
                print(f"Response text: {response.text[:500]}...")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text[:500]}...")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 300 seconds")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_quicktest_api()
    exit(0 if success else 1)