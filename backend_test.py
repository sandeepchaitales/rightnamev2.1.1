import requests
import sys
import json
from datetime import datetime
import uuid

class BrandEvaluationTester:
    def __init__(self, base_url="https://nameverdict.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.session_cookies = None
        self.test_user_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        self.test_user_password = "TestPass123!"
        self.test_user_name = "Test User"
        self.test_report_id = None

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def test_api_health(self):
        """Test basic API health"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=30)
            success = response.status_code == 200
            details = f"Status: {response.status_code}, Response: {response.text[:100]}"
            self.log_test("API Health Check", success, details)
            return success
        except Exception as e:
            self.log_test("API Health Check", False, str(e))
            return False

    def test_evaluate_endpoint_structure(self):
        """Test /api/evaluate endpoint with mock payload"""
        payload = {
            "brand_names": ["Astra"],
            "category": "Tech",
            "positioning": "Premium",
            "market_scope": "Multi-Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔍 Testing /api/evaluate with payload: {json.dumps(payload, indent=2)}")
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120  # LLM calls can take time
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Response received, checking structure...")
                    
                    # Check required fields
                    required_fields = ["executive_summary", "brand_scores", "comparison_verdict"]
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        self.log_test("Evaluate Endpoint - Structure", False, f"Missing fields: {missing_fields}")
                        return False
                    
                    # Check brand_scores structure
                    if not data["brand_scores"] or len(data["brand_scores"]) == 0:
                        self.log_test("Evaluate Endpoint - Structure", False, "No brand scores returned")
                        return False
                    
                    brand = data["brand_scores"][0]
                    brand_required = ["brand_name", "namescore", "verdict", "summary"]
                    brand_missing = [field for field in brand_required if field not in brand]
                    
                    if brand_missing:
                        self.log_test("Evaluate Endpoint - Structure", False, f"Missing brand fields: {brand_missing}")
                        return False
                    
                    # Check if Astra is in the response
                    astra_found = any(brand.get("brand_name") == "Astra" for brand in data["brand_scores"])
                    if not astra_found:
                        self.log_test("Evaluate Endpoint - Content", False, "Brand 'Astra' not found in response")
                        return False
                    
                    # Check if NameScore is present
                    astra_brand = next((brand for brand in data["brand_scores"] if brand.get("brand_name") == "Astra"), None)
                    if astra_brand and "namescore" not in astra_brand:
                        self.log_test("Evaluate Endpoint - NameScore", False, "NameScore not found for Astra")
                        return False
                    
                    print(f"✅ Found Astra with NameScore: {astra_brand.get('namescore', 'N/A')}")
                    self.log_test("Evaluate Endpoint - Structure", True, f"All required fields present, Astra NameScore: {astra_brand.get('namescore')}")
                    return True
                    
                except json.JSONDecodeError as e:
                    self.log_test("Evaluate Endpoint - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                    return False
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.log_test("Evaluate Endpoint - HTTP Status", False, error_msg)
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Evaluate Endpoint - Timeout", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("Evaluate Endpoint - Exception", False, str(e))
            return False

    def test_auth_register(self):
        """Test email/password registration"""
        payload = {
            "email": self.test_user_email,
            "password": self.test_user_password,
            "name": self.test_user_name
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/auth/register",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["user_id", "email", "name", "auth_type"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Auth Register - Response Structure", False, f"Missing fields: {missing_fields}")
                    return False
                
                if data["email"] != self.test_user_email.lower():
                    self.log_test("Auth Register - Email Match", False, f"Email mismatch: {data['email']} != {self.test_user_email.lower()}")
                    return False
                
                # Store cookies for subsequent requests
                self.session_cookies = response.cookies
                
                self.log_test("Auth Register", True, f"User registered: {data['user_id']}")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.log_test("Auth Register", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Auth Register", False, str(e))
            return False

    def test_auth_login_email(self):
        """Test email/password login"""
        payload = {
            "email": self.test_user_email,
            "password": self.test_user_password
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/auth/login/email",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["user_id", "email", "name", "auth_type"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Auth Login Email - Response Structure", False, f"Missing fields: {missing_fields}")
                    return False
                
                if data["email"] != self.test_user_email.lower():
                    self.log_test("Auth Login Email - Email Match", False, f"Email mismatch: {data['email']} != {self.test_user_email.lower()}")
                    return False
                
                # Update cookies for subsequent requests
                self.session_cookies = response.cookies
                
                self.log_test("Auth Login Email", True, f"User logged in: {data['user_id']}")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.log_test("Auth Login Email", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Auth Login Email", False, str(e))
            return False

    def test_auth_me(self):
        """Test getting current user info"""
        try:
            response = requests.get(
                f"{self.api_url}/auth/me",
                cookies=self.session_cookies,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["user_id", "email", "name"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Auth Me - Response Structure", False, f"Missing fields: {missing_fields}")
                    return False
                
                self.log_test("Auth Me", True, f"Current user: {data['email']}")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.log_test("Auth Me", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Auth Me", False, str(e))
            return False

    def test_generate_report_with_auth(self):
        """Test generating a report while authenticated to get report_id"""
        payload = {
            "brand_names": ["AuthTestBrand"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Multi-Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔍 Testing /api/evaluate with auth to get report_id...")
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                cookies=self.session_cookies,
                timeout=120  # LLM calls can take time
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Response keys: {list(data.keys())}")
                    
                    if "report_id" in data:
                        self.test_report_id = data["report_id"]
                        self.log_test("Generate Report with Auth", True, f"Report generated: {self.test_report_id}")
                        return True
                    else:
                        # Check if we can find report_id in nested structure
                        print(f"Full response structure: {json.dumps(data, indent=2)[:500]}...")
                        self.log_test("Generate Report with Auth", False, "No report_id in response")
                        return False
                        
                except json.JSONDecodeError as e:
                    self.log_test("Generate Report with Auth - JSON Parse", False, f"Invalid JSON: {str(e)}")
                    return False
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.log_test("Generate Report with Auth", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Generate Report with Auth", False, str(e))
            return False

    def test_get_report_authenticated(self):
        """Test getting report while authenticated"""
        if not self.test_report_id:
            self.log_test("Get Report Authenticated", False, "No report_id available")
            return False
            
        try:
            response = requests.get(
                f"{self.api_url}/reports/{self.test_report_id}",
                cookies=self.session_cookies,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "is_authenticated" not in data:
                    self.log_test("Get Report Authenticated - Auth Flag", False, "Missing is_authenticated field")
                    return False
                
                if not data["is_authenticated"]:
                    self.log_test("Get Report Authenticated - Auth Status", False, "is_authenticated is False")
                    return False
                
                # Check that we have full report data
                required_fields = ["executive_summary", "brand_scores"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Get Report Authenticated - Content", False, f"Missing fields: {missing_fields}")
                    return False
                
                self.log_test("Get Report Authenticated", True, f"Full report retrieved for authenticated user")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.log_test("Get Report Authenticated", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Get Report Authenticated", False, str(e))
            return False

    def test_get_report_unauthenticated(self):
        """Test getting report without authentication"""
        if not self.test_report_id:
            self.log_test("Get Report Unauthenticated", False, "No report_id available")
            return False
            
        try:
            # Make request without cookies
            response = requests.get(
                f"{self.api_url}/reports/{self.test_report_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "is_authenticated" not in data:
                    self.log_test("Get Report Unauthenticated - Auth Flag", False, "Missing is_authenticated field")
                    return False
                
                if data["is_authenticated"]:
                    self.log_test("Get Report Unauthenticated - Auth Status", False, "is_authenticated is True (should be False)")
                    return False
                
                # Should still have basic report data
                required_fields = ["executive_summary", "brand_scores"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Get Report Unauthenticated - Content", False, f"Missing fields: {missing_fields}")
                    return False
                
                self.log_test("Get Report Unauthenticated", True, f"Report retrieved with is_authenticated=False")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.log_test("Get Report Unauthenticated", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Get Report Unauthenticated", False, str(e))
            return False

    def test_auth_logout(self):
        """Test logout functionality"""
        try:
            response = requests.post(
                f"{self.api_url}/auth/logout",
                cookies=self.session_cookies,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_test("Auth Logout", True, f"Logout successful: {data['message']}")
                    return True
                else:
                    self.log_test("Auth Logout", False, "No message in logout response")
                    return False
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.log_test("Auth Logout", False, error_msg)
                return False
                
        except Exception as e:
            self.log_test("Auth Logout", False, str(e))
            return False

    def test_trademark_research_luminara(self):
        """Test trademark research feature with Luminara (Fashion/Streetwear/India)"""
        payload = {
            "brand_names": ["Luminara"],
            "industry": "Fashion and Apparel",
            "category": "Streetwear",
            "product_type": "Clothing",
            "usp": "Premium urban streetwear",
            "brand_vibe": "Modern, Bold",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n🔍 Testing trademark research with Luminara...")
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # Extended timeout for trademark research
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Check if we have brand_scores
                    if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                        self.log_test("Trademark Research - Luminara Structure", False, "No brand scores returned")
                        return False
                    
                    brand = data["brand_scores"][0]
                    
                    # Test 1: Check trademark_research field exists
                    if "trademark_research" not in brand:
                        self.log_test("Trademark Research - Luminara Field", False, "trademark_research field missing")
                        return False
                    
                    tm_research = brand["trademark_research"]
                    if not tm_research:
                        self.log_test("Trademark Research - Luminara Data", False, "trademark_research is null/empty")
                        return False
                    
                    # Test 2: Check overall_risk_score (should be around 6-7/10)
                    risk_score = tm_research.get("overall_risk_score")
                    if risk_score is None:
                        self.log_test("Trademark Research - Luminara Risk Score", False, "overall_risk_score missing")
                        return False
                    
                    if not (5 <= risk_score <= 8):
                        self.log_test("Trademark Research - Luminara Risk Score Range", False, f"Risk score {risk_score} not in expected range 5-8")
                        return False
                    
                    # Test 3: Check trademark_conflicts array
                    tm_conflicts = tm_research.get("trademark_conflicts", [])
                    if len(tm_conflicts) < 2:
                        self.log_test("Trademark Research - Luminara TM Conflicts", False, f"Expected at least 2 trademark conflicts, got {len(tm_conflicts)}")
                        return False
                    
                    # Check for specific expected conflicts
                    conflict_names = [c.get("name", "").lower() for c in tm_conflicts]
                    expected_conflicts = ["luminara", "luminara elixir"]
                    found_conflicts = [name for name in expected_conflicts if any(name in cn for cn in conflict_names)]
                    
                    if len(found_conflicts) < 1:
                        self.log_test("Trademark Research - Luminara Expected Conflicts", False, f"Expected Luminara conflicts not found. Got: {conflict_names}")
                        return False
                    
                    # Test 4: Check company_conflicts array
                    co_conflicts = tm_research.get("company_conflicts", [])
                    if len(co_conflicts) < 1:
                        self.log_test("Trademark Research - Luminara Company Conflicts", False, f"Expected at least 1 company conflict, got {len(co_conflicts)}")
                        return False
                    
                    # Check for Luminara Enterprises
                    company_names = [c.get("name", "").lower() for c in co_conflicts]
                    if not any("luminara enterprises" in cn for cn in company_names):
                        print(f"Warning: Expected 'Luminara Enterprises' not found in companies: {company_names}")
                    
                    # Test 5: Check legal_precedents array
                    legal_precedents = tm_research.get("legal_precedents", [])
                    if len(legal_precedents) < 1:
                        self.log_test("Trademark Research - Luminara Legal Precedents", False, f"Expected at least 1 legal precedent, got {len(legal_precedents)}")
                        return False
                    
                    # Test 6: Check registration_timeline field
                    if "registration_timeline" not in brand:
                        self.log_test("Trademark Research - Luminara Timeline Field", False, "registration_timeline field missing")
                        return False
                    
                    reg_timeline = brand["registration_timeline"]
                    if not reg_timeline:
                        self.log_test("Trademark Research - Luminara Timeline Data", False, "registration_timeline is null/empty")
                        return False
                    
                    # Check timeline structure
                    if "estimated_duration" not in reg_timeline:
                        self.log_test("Trademark Research - Luminara Timeline Duration", False, "estimated_duration missing from timeline")
                        return False
                    
                    duration = reg_timeline.get("estimated_duration", "")
                    if "12-18 months" not in duration and "month" not in duration.lower():
                        self.log_test("Trademark Research - Luminara Timeline Format", False, f"Unexpected duration format: {duration}")
                        return False
                    
                    # Test 7: Check mitigation_strategies array
                    if "mitigation_strategies" not in brand:
                        self.log_test("Trademark Research - Luminara Mitigation Field", False, "mitigation_strategies field missing")
                        return False
                    
                    mitigation = brand["mitigation_strategies"]
                    if not isinstance(mitigation, list) or len(mitigation) == 0:
                        self.log_test("Trademark Research - Luminara Mitigation Data", False, f"Expected mitigation strategies array, got: {type(mitigation)}")
                        return False
                    
                    # Test 8: Check Nice Classification (should be Class 25 for Clothing)
                    nice_class = tm_research.get("nice_classification", {})
                    if nice_class and nice_class.get("class_number") != 25:
                        self.log_test("Trademark Research - Luminara Nice Class", False, f"Expected Class 25 for clothing, got Class {nice_class.get('class_number')}")
                        return False
                    
                    self.log_test("Trademark Research - Luminara Complete", True, 
                                f"All checks passed. Risk: {risk_score}/10, TM conflicts: {len(tm_conflicts)}, Company conflicts: {len(co_conflicts)}, Legal precedents: {len(legal_precedents)}")
                    return True
                    
                except json.JSONDecodeError as e:
                    self.log_test("Trademark Research - Luminara JSON", False, f"Invalid JSON response: {str(e)}")
                    return False
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Trademark Research - Luminara HTTP", False, error_msg)
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Trademark Research - Luminara Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Trademark Research - Luminara Exception", False, str(e))
            return False

    def test_trademark_research_nexofy(self):
        """Test trademark research with unique brand name (should have low risk)"""
        payload = {
            "brand_names": ["Nexofy"],
            "industry": "Technology",
            "category": "SaaS",
            "product_type": "Software",
            "usp": "AI-powered automation",
            "brand_vibe": "Innovative",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA", "UK", "India"]
        }
        
        try:
            print(f"\n🔍 Testing trademark research with Nexofy (unique name)...")
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # Extended timeout for trademark research
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Check if we have brand_scores
                    if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                        self.log_test("Trademark Research - Nexofy Structure", False, "No brand scores returned")
                        return False
                    
                    brand = data["brand_scores"][0]
                    
                    # Test 1: Check trademark_research field exists
                    if "trademark_research" not in brand:
                        self.log_test("Trademark Research - Nexofy Field", False, "trademark_research field missing")
                        return False
                    
                    tm_research = brand["trademark_research"]
                    if not tm_research:
                        self.log_test("Trademark Research - Nexofy Data", False, "trademark_research is null/empty")
                        return False
                    
                    # Test 2: Check overall_risk_score (should be low 1-3/10)
                    risk_score = tm_research.get("overall_risk_score")
                    if risk_score is None:
                        self.log_test("Trademark Research - Nexofy Risk Score", False, "overall_risk_score missing")
                        return False
                    
                    if risk_score > 4:
                        self.log_test("Trademark Research - Nexofy Low Risk", False, f"Expected low risk (1-4), got {risk_score}/10")
                        return False
                    
                    # Test 3: Check registration success probability (should be high 80%+)
                    success_prob = tm_research.get("registration_success_probability")
                    if success_prob is None:
                        self.log_test("Trademark Research - Nexofy Success Prob", False, "registration_success_probability missing")
                        return False
                    
                    if success_prob < 70:
                        self.log_test("Trademark Research - Nexofy High Success", False, f"Expected high success probability (70%+), got {success_prob}%")
                        return False
                    
                    # Test 4: Check Nice Classification (should be Class 42 for Scientific services)
                    nice_class = tm_research.get("nice_classification", {})
                    if nice_class and nice_class.get("class_number") not in [9, 42]:  # Allow both Class 9 (Software) and Class 42 (Services)
                        self.log_test("Trademark Research - Nexofy Nice Class", False, f"Expected Class 9 or 42 for SaaS, got Class {nice_class.get('class_number')}")
                        return False
                    
                    # Test 5: Check that basic structure is present
                    required_fields = ["trademark_conflicts", "company_conflicts", "legal_precedents"]
                    missing_fields = [field for field in required_fields if field not in tm_research]
                    
                    if missing_fields:
                        self.log_test("Trademark Research - Nexofy Structure", False, f"Missing fields: {missing_fields}")
                        return False
                    
                    # Test 6: Check registration_timeline and mitigation_strategies exist
                    if "registration_timeline" not in brand:
                        self.log_test("Trademark Research - Nexofy Timeline", False, "registration_timeline field missing")
                        return False
                    
                    if "mitigation_strategies" not in brand:
                        self.log_test("Trademark Research - Nexofy Mitigation", False, "mitigation_strategies field missing")
                        return False
                    
                    tm_conflicts_count = len(tm_research.get("trademark_conflicts", []))
                    co_conflicts_count = len(tm_research.get("company_conflicts", []))
                    
                    self.log_test("Trademark Research - Nexofy Complete", True, 
                                f"Low risk brand passed. Risk: {risk_score}/10, Success: {success_prob}%, TM conflicts: {tm_conflicts_count}, Company conflicts: {co_conflicts_count}")
                    return True
                    
                except json.JSONDecodeError as e:
                    self.log_test("Trademark Research - Nexofy JSON", False, f"Invalid JSON response: {str(e)}")
                    return False
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Trademark Research - Nexofy HTTP", False, error_msg)
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Trademark Research - Nexofy Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Trademark Research - Nexofy Exception", False, str(e))
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Backend API Tests...")
        print(f"Testing against: {self.base_url}")
        print(f"Test user email: {self.test_user_email}")
        
        # Test API health first
        if not self.test_api_health():
            print("❌ API health check failed, stopping tests")
            return False
        
        # Test main evaluate endpoint
        self.test_evaluate_endpoint_structure()
        
        # Test auth endpoints
        print("\n🔐 Testing Authentication Endpoints...")
        
        # Test registration
        if not self.test_auth_register():
            print("❌ Registration failed, skipping auth-dependent tests")
            return False
        
        # Test login (using same credentials)
        self.test_auth_login_email()
        
        # Test getting current user
        self.test_auth_me()
        
        # Test report generation with auth
        self.test_generate_report_with_auth()
        
        # Test report retrieval with auth
        self.test_get_report_authenticated()
        
        # Test report retrieval without auth
        self.test_get_report_unauthenticated()
        
        # Test logout
        self.test_auth_logout()
        
        # Print summary
        print(f"\n📊 Test Summary:")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = BrandEvaluationTester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            "summary": {
                "tests_run": tester.tests_run,
                "tests_passed": tester.tests_passed,
                "success_rate": (tester.tests_passed/tester.tests_run)*100 if tester.tests_run > 0 else 0
            },
            "results": tester.test_results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())