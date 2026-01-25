#!/usr/bin/env python3
import requests
import json

def test_health():
    """Test API health endpoint"""
    url = "https://name-validator-4.preview.emergentagent.com/api/health"
    
    try:
        print("🔍 Testing API health...")
        response = requests.get(url, timeout=10)
        print(f"Health Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ API is healthy")
            return True
        else:
            print(f"❌ Health check failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_basic_api():
    """Test basic API endpoint"""
    url = "https://name-validator-4.preview.emergentagent.com/api/"
    
    try:
        print("🔍 Testing basic API endpoint...")
        response = requests.get(url, timeout=10)
        print(f"API Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ API endpoint is accessible")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"❌ API endpoint failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ API endpoint error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Running basic connectivity tests...")
    
    health_ok = test_health()
    api_ok = test_basic_api()
    
    if health_ok and api_ok:
        print("\n✅ Basic connectivity tests passed")
        print("🔍 The API is accessible, but /evaluate endpoint may be slow due to LLM processing")
        exit(0)
    else:
        print("\n❌ Basic connectivity tests failed")
        exit(1)