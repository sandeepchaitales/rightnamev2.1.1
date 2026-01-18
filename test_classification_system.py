#!/usr/bin/env python3
"""
Test script specifically for NEW SINGLE CLASSIFICATION SYSTEM
Tests the two specific test cases requested in the review:
1. "Check My Meal" for Doctor Appointment App - should be DESCRIPTIVE
2. "Zomato" for Food Delivery - should be FANCIFUL
3. Backend logs verification
"""

import sys
import os
sys.path.append('/app')

from backend_test import BrandEvaluationTester

def main():
    print("🏷️ NEW SINGLE CLASSIFICATION SYSTEM TESTING")
    print("="*80)
    print("Testing the NEW SINGLE CLASSIFICATION SYSTEM for RIGHTNAME brand evaluation API")
    print("As requested in review - testing specific classification scenarios")
    print("="*80)
    
    tester = BrandEvaluationTester()
    
    # Test API health first
    if not tester.test_api_health():
        print("❌ API health check failed - stopping tests")
        return False
    
    print("\n🏷️ TESTING NEW SINGLE CLASSIFICATION SYSTEM")
    print("="*60)
    
    # Test Case 1: Check My Meal (should be DESCRIPTIVE)
    print("\n📋 Test Case 1: Check My Meal for Doctor Appointment App")
    print("Expected: DESCRIPTIVE classification (NOT COINED)")
    test1_result = tester.test_new_classification_system_check_my_meal()
    
    # Test Case 2: Zomato (should be FANCIFUL)
    print("\n📋 Test Case 2: Zomato for Food Delivery")
    print("Expected: FANCIFUL classification")
    test2_result = tester.test_new_classification_system_zomato()
    
    # Test Case 3: Backend logs verification
    print("\n📋 Test Case 3: Backend Logs Verification")
    print("Expected: Classification called ONCE per brand")
    test3_result = tester.test_backend_logs_classification_called_once()
    
    # Print summary
    success = tester.print_summary()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)