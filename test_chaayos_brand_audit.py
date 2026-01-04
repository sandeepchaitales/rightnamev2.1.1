#!/usr/bin/env python3
"""
Test script for Brand Audit API with Chaayos test case
Testing after Claude timeout fix and schema validation fix
"""

import sys
import os
sys.path.append('/app')

from backend_test import BrandEvaluationTester

def main():
    print("🔍 BRAND AUDIT API TEST: Testing /api/brand-audit endpoint with Chaayos")
    print("=" * 80)
    print("🎯 TESTING: Brand Audit API with Chaayos (Indian chai cafe)")
    print("🔧 FIXED: 1) Claude timeout (removed Claude, OpenAI only)")
    print("🔧 FIXED: 2) Schema validation (sources.id now accepts Any type)")
    print("🕐 TIMEOUT: 120 seconds allowed")
    print("=" * 80)
    
    tester = BrandEvaluationTester()
    
    # Test API health first
    print("\n🏥 Testing API Health...")
    if not tester.test_api_health():
        print("❌ API health check failed, stopping tests")
        return 1
    
    # Run the specific Chaayos Brand Audit test
    print("\n🔍 BRAND AUDIT TEST:")
    print("Testing Brand Audit API with Chaayos after fixes...")
    
    success = tester.test_brand_audit_chaayos_final()
    
    # Print summary
    print(f"\n📊 Brand Audit Test Summary:")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if success:
        print("🎉 SUCCESS: Brand Audit API test passed!")
        return 0
    else:
        print("❌ FAILED: Brand Audit API test failed!")
        return 1

if __name__ == "__main__":
    exit(main())