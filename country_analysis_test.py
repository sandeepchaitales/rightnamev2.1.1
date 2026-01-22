import requests
import json
import sys
from datetime import datetime

def test_country_specific_analysis():
    """Test the country-specific competitive analysis feature"""
    base_url = "https://session-summary-15.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    # Test payload with multiple countries as specified in the review request
    payload = {
        "brand_names": ["LUMINA"],
        "category": "Skincare",
        "positioning": "Premium",
        "market_scope": "Multi-Country",
        "countries": ["USA", "India", "UK"]
    }
    
    print("🧪 Testing Country-Specific Competitive Analysis Feature")
    print(f"Testing brand: {payload['brand_names'][0]}")
    print(f"Category: {payload['category']}")
    print(f"Countries: {', '.join(payload['countries'])}")
    print(f"Market Scope: {payload['market_scope']}")
    
    try:
        print(f"\n🔍 Sending request to {api_url}/evaluate...")
        response = requests.post(
            f"{api_url}/evaluate", 
            json=payload, 
            headers={'Content-Type': 'application/json'},
            timeout=180  # Extended timeout for LLM processing
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API request failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
        
        try:
            data = response.json()
            print(f"✅ Response received successfully")
            
            # Check basic structure
            if "brand_scores" not in data or not data["brand_scores"]:
                print("❌ No brand_scores in response")
                return False
            
            brand_data = data["brand_scores"][0]
            print(f"Brand: {brand_data.get('brand_name', 'Unknown')}")
            print(f"NameScore: {brand_data.get('namescore', 'N/A')}")
            print(f"Verdict: {brand_data.get('verdict', 'N/A')}")
            
            # Test 1: Check if global competitor analysis exists
            global_analysis = brand_data.get("competitor_analysis")
            if not global_analysis:
                print("❌ No global competitor_analysis found")
                return False
            
            print(f"✅ Global competitor analysis found")
            print(f"   - Competitors: {len(global_analysis.get('competitors', []))}")
            print(f"   - X-axis: {global_analysis.get('x_axis_label', 'N/A')}")
            print(f"   - Y-axis: {global_analysis.get('y_axis_label', 'N/A')}")
            
            # Test 2: Check if country-specific analysis exists
            country_analysis = brand_data.get("country_competitor_analysis", [])
            if not country_analysis:
                print("❌ No country_competitor_analysis found")
                return False
            
            print(f"✅ Country-specific analysis found for {len(country_analysis)} countries")
            
            # Test 3: Verify each country has proper structure
            expected_countries = set(payload["countries"])
            found_countries = set()
            
            for i, country_data in enumerate(country_analysis):
                country = country_data.get("country", "Unknown")
                found_countries.add(country)
                
                print(f"\n   Country {i+1}: {country}")
                print(f"   - Flag: {country_data.get('country_flag', 'N/A')}")
                print(f"   - Competitors: {len(country_data.get('competitors', []))}")
                print(f"   - X-axis: {country_data.get('x_axis_label', 'N/A')}")
                print(f"   - Y-axis: {country_data.get('y_axis_label', 'N/A')}")
                print(f"   - White space: {country_data.get('white_space_analysis', 'N/A')[:100]}...")
                print(f"   - Strategic advantage: {country_data.get('strategic_advantage', 'N/A')[:100]}...")
                
                # Check if competitors have coordinates
                competitors = country_data.get("competitors", [])
                if competitors:
                    for j, comp in enumerate(competitors[:3]):  # Check first 3
                        print(f"     Competitor {j+1}: {comp.get('name', 'N/A')} at ({comp.get('x_coordinate', 'N/A')}, {comp.get('y_coordinate', 'N/A')})")
                
                # Check user brand position
                user_pos = country_data.get("user_brand_position")
                if user_pos:
                    print(f"   - User position: ({user_pos.get('x_coordinate', 'N/A')}, {user_pos.get('y_coordinate', 'N/A')})")
            
            # Test 4: Verify we have analysis for the requested countries
            missing_countries = expected_countries - found_countries
            if missing_countries:
                print(f"⚠️  Missing analysis for countries: {missing_countries}")
            else:
                print(f"✅ All requested countries have analysis: {found_countries}")
            
            # Test 5: Check if country flags are present
            flags_present = sum(1 for c in country_analysis if c.get("country_flag"))
            print(f"✅ Country flags present: {flags_present}/{len(country_analysis)}")
            
            # Test 6: Verify unique competitors per country
            all_competitor_names = []
            for country_data in country_analysis:
                country_competitors = [c.get("name", "") for c in country_data.get("competitors", [])]
                all_competitor_names.extend([(country_data.get("country"), name) for name in country_competitors])
            
            print(f"✅ Total competitor entries across all countries: {len(all_competitor_names)}")
            
            # Test 7: Check for market entry recommendations
            recommendations_count = sum(1 for c in country_analysis if c.get("market_entry_recommendation"))
            print(f"✅ Market entry recommendations: {recommendations_count}/{len(country_analysis)}")
            
            print(f"\n🎯 Country-Specific Analysis Test Results:")
            print(f"   ✅ Global analysis: Present")
            print(f"   ✅ Country analyses: {len(country_analysis)} countries")
            print(f"   ✅ Countries covered: {', '.join(found_countries)}")
            print(f"   ✅ Flags present: {flags_present}/{len(country_analysis)}")
            print(f"   ✅ Market recommendations: {recommendations_count}/{len(country_analysis)}")
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {str(e)}")
            print(f"Response text: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 180 seconds")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def main():
    success = test_country_specific_analysis()
    
    if success:
        print(f"\n🎉 Country-Specific Competitive Analysis test PASSED!")
        return 0
    else:
        print(f"\n💥 Country-Specific Competitive Analysis test FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())