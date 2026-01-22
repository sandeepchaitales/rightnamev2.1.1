#!/usr/bin/env python3
"""
Conflict Relevance Analysis Integration Test
Tests the NEW Conflict Relevance Analysis feature for RIGHTNAME brand evaluation API
"""

import requests
import json
import time
import subprocess

class ConflictAnalysisTest:
    def __init__(self):
        self.base_url = "https://session-summary-15.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []

    def log_result(self, test_name, passed, details=""):
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED: {details}")
        
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })

    def test_luminara_conflict_analysis(self):
        """Test Luminara in Beauty/Cosmetics - should show real conflicts"""
        payload = {
            "brand_names": ["Luminara"],
            "category": "Beauty",
            "industry": "Cosmetics",
            "countries": ["India"],
            "positioning": "Premium",
            "market_scope": "Single Country"
        }
        
        print(f"\n🎯 Testing Luminara Conflict Relevance Analysis...")
        print(f"Expected: Real conflicts from trademark research")
        print(f"Expected: visibility_analysis with populated direct_competitors")
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/evaluate",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=120
            )
            response_time = time.time() - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            if response.status_code != 200:
                self.log_result("Luminara HTTP Response", False, f"HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                self.log_result("Luminara Response Structure", False, "No brand scores returned")
                return False
            
            brand = data["brand_scores"][0]
            
            # Test 1: Check visibility_analysis exists
            visibility_analysis = brand.get("visibility_analysis", {})
            if not visibility_analysis:
                self.log_result("Luminara Visibility Analysis", False, "visibility_analysis section missing")
                return False
            
            print(f"✅ Found visibility_analysis section")
            
            # Test 2: Check direct_competitors array
            direct_competitors = visibility_analysis.get("direct_competitors", [])
            if not direct_competitors:
                self.log_result("Luminara Direct Competitors", False, "direct_competitors array is empty")
                return False
            
            print(f"✅ Found {len(direct_competitors)} direct competitors")
            
            # Test 3: Check warning_triggered
            warning_triggered = visibility_analysis.get("warning_triggered", False)
            print(f"✅ warning_triggered = {warning_triggered}")
            
            # Test 4: Check conflict_summary
            conflict_summary = visibility_analysis.get("conflict_summary", "")
            if "NO DIRECT CONFLICTS" in conflict_summary.upper():
                self.log_result("Luminara Conflict Summary", False, "Still shows 'NO DIRECT CONFLICTS'")
                return False
            
            print(f"✅ Conflict summary: {conflict_summary[:100]}...")
            
            # Test 5: Check trademark research consistency
            trademark_research = brand.get("trademark_research", {})
            if trademark_research:
                tm_conflicts = len(trademark_research.get("trademark_conflicts", []))
                co_conflicts = len(trademark_research.get("company_conflicts", []))
                print(f"📊 Trademark research: {tm_conflicts} TM conflicts, {co_conflicts} company conflicts")
            
            self.log_result("Luminara Conflict Analysis", True, 
                          f"Direct competitors: {len(direct_competitors)}, Warning: {warning_triggered}")
            return True
            
        except requests.exceptions.Timeout:
            self.log_result("Luminara Timeout", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_result("Luminara Exception", False, str(e))
            return False

    def test_rapidoy_category_king_conflict(self):
        """Test Rapidoy - should detect Category King conflict with Rapido"""
        payload = {
            "brand_names": ["Rapidoy"],
            "category": "Ride-hailing",
            "industry": "Transport",
            "countries": ["India"],
            "positioning": "Mid-Range",
            "market_scope": "Single Country"
        }
        
        print(f"\n🎯 Testing Rapidoy Category King Conflict...")
        print(f"Expected: Deep-Trace Analysis detecting Rapido")
        print(f"Expected: Very low score due to Category King conflict")
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/evaluate",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=120
            )
            response_time = time.time() - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            if response.status_code != 200:
                self.log_result("Rapidoy HTTP Response", False, f"HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                self.log_result("Rapidoy Response Structure", False, "No brand scores returned")
                return False
            
            brand = data["brand_scores"][0]
            
            # Test 1: Check NameScore is very low
            namescore = brand.get("namescore", 100)
            if namescore > 30:
                self.log_result("Rapidoy Low Score", False, f"Expected low score, got {namescore}/100")
                return False
            
            print(f"✅ Low NameScore as expected: {namescore}/100")
            
            # Test 2: Check verdict is REJECT
            verdict = brand.get("verdict", "")
            if verdict != "REJECT":
                self.log_result("Rapidoy Verdict", False, f"Expected REJECT, got {verdict}")
                return False
            
            print(f"✅ REJECT verdict as expected")
            
            # Test 3: Check for Rapido detection
            response_text = json.dumps(data).lower()
            rapido_found = "rapido" in response_text
            
            if not rapido_found:
                self.log_result("Rapidoy Rapido Detection", False, "Rapido not found in response")
                return False
            
            print(f"✅ Rapido conflict detected in response")
            
            # Test 4: Check visibility_analysis
            visibility_analysis = brand.get("visibility_analysis", {})
            if visibility_analysis:
                direct_competitors = visibility_analysis.get("direct_competitors", [])
                warning_triggered = visibility_analysis.get("warning_triggered", False)
                print(f"✅ Visibility analysis: {len(direct_competitors)} competitors, warning: {warning_triggered}")
            
            self.log_result("Rapidoy Category King Conflict", True, 
                          f"NameScore: {namescore}/100, Verdict: {verdict}, Rapido detected")
            return True
            
        except requests.exceptions.Timeout:
            self.log_result("Rapidoy Timeout", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_result("Rapidoy Exception", False, str(e))
            return False

    def check_backend_logs(self):
        """Check backend logs for Conflict Relevance Analysis messages"""
        print(f"\n📋 Checking backend logs...")
        
        try:
            result = subprocess.run(
                ["tail", "-n", "200", "/var/log/supervisor/backend.out.log"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                self.log_result("Backend Logs Access", False, "Could not access logs")
                return False
            
            log_content = result.stdout
            
            # Check for expected messages
            expected_messages = [
                "Building Conflict Relevance Analysis",
                "PRE-COMPUTED visibility_analysis",
                "Luminara",
                "Rapidoy"
            ]
            
            found_count = 0
            for message in expected_messages:
                if message in log_content:
                    found_count += 1
                    print(f"✅ Found: {message}")
                else:
                    print(f"❌ Missing: {message}")
            
            if found_count >= 2:
                self.log_result("Backend Logs Analysis", True, f"Found {found_count}/4 expected messages")
                return True
            else:
                self.log_result("Backend Logs Analysis", False, f"Only found {found_count}/4 messages")
                return False
                
        except Exception as e:
            self.log_result("Backend Logs Exception", False, str(e))
            return False

    def run_all_tests(self):
        """Run all Conflict Relevance Analysis tests"""
        print("🎯 NEW CONFLICT RELEVANCE ANALYSIS INTEGRATION TESTS")
        print("="*60)
        
        # Test 1: Luminara in Beauty/Cosmetics
        self.test_luminara_conflict_analysis()
        
        # Test 2: Rapidoy Category King conflict
        self.test_rapidoy_category_king_conflict()
        
        # Test 3: Backend logs verification
        self.check_backend_logs()
        
        # Print summary
        print("\n" + "="*60)
        print("📊 CONFLICT RELEVANCE ANALYSIS TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "0%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL CONFLICT RELEVANCE ANALYSIS TESTS PASSED!")
        else:
            print(f"\n❌ FAILED TESTS:")
            for result in self.results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        return self.tests_passed == self.tests_run

if __name__ == "__main__":
    tester = ConflictAnalysisTest()
    success = tester.run_all_tests()
    exit(0 if success else 1)