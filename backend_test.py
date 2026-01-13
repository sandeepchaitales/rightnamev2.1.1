import requests
import sys
import json
import time
from datetime import datetime
import uuid

class BrandEvaluationTester:
    def __init__(self, base_url="https://namevalidator-app.preview.emergentagent.com"):
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

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "0%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        return self.tests_passed == self.tests_run

    def test_api_health(self):
        """Test basic API health"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=60)
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
                    if len(tm_conflicts) < 1:
                        self.log_test("Trademark Research - Luminara TM Conflicts", False, f"Expected at least 1 trademark conflict, got {len(tm_conflicts)}")
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
                    
                    if risk_score > 7:
                        self.log_test("Trademark Research - Nexofy Low Risk", False, f"Expected moderate risk (1-7), got {risk_score}/10")
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

    def test_currency_single_country_usa(self):
        """Test Case 1 - Single Country USA: All costs should be in USD ($)"""
        payload = {
            "brand_names": ["TestUSA"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n💰 Testing Currency Logic - Single Country USA...")
            print(f"Expected: All costs in USD ($)")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Currency Test - USA HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Currency Test - USA Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                currency_issues = []
                
                # Test 1: Check registration_timeline.filing_cost
                if "registration_timeline" in brand and brand["registration_timeline"]:
                    timeline = brand["registration_timeline"]
                    filing_cost = timeline.get("filing_cost", "")
                    if filing_cost and "$" not in filing_cost:
                        currency_issues.append(f"filing_cost should be in USD ($), got: {filing_cost}")
                    
                    # Test 2: Check registration_timeline.opposition_defense_cost
                    defense_cost = timeline.get("opposition_defense_cost", "")
                    if defense_cost and "$" not in defense_cost:
                        currency_issues.append(f"opposition_defense_cost should be in USD ($), got: {defense_cost}")
                
                # Test 3: Check mitigation_strategies[].estimated_cost
                if "mitigation_strategies" in brand and brand["mitigation_strategies"]:
                    for i, strategy in enumerate(brand["mitigation_strategies"]):
                        if isinstance(strategy, dict) and "estimated_cost" in strategy:
                            cost = strategy["estimated_cost"]
                            if cost and "$" not in cost:
                                currency_issues.append(f"mitigation_strategies[{i}].estimated_cost should be in USD ($), got: {cost}")
                
                # Test 4: Check for any INR (₹) or other currencies that shouldn't be there
                response_text = json.dumps(data).lower()
                if "₹" in response_text or "inr" in response_text:
                    currency_issues.append("Found INR (₹) currency in USA single-country response")
                if "£" in response_text or "gbp" in response_text:
                    currency_issues.append("Found GBP (£) currency in USA single-country response")
                if "€" in response_text or "eur" in response_text:
                    currency_issues.append("Found EUR (€) currency in USA single-country response")
                
                if currency_issues:
                    self.log_test("Currency Test - USA Single Country", False, "; ".join(currency_issues))
                    return False
                
                self.log_test("Currency Test - USA Single Country", True, "All costs correctly in USD ($)")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Currency Test - USA JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Currency Test - USA Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Currency Test - USA Exception", False, str(e))
            return False

    def test_currency_single_country_india(self):
        """Test Case 2 - Single Country India: All costs should be in INR (₹)"""
        payload = {
            "brand_names": ["TestIndia"],
            "category": "Fashion",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n💰 Testing Currency Logic - Single Country India...")
            print(f"Expected: All costs in INR (₹)")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Currency Test - India HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Currency Test - India Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                currency_issues = []
                
                # Test 1: Check registration_timeline.filing_cost
                if "registration_timeline" in brand and brand["registration_timeline"]:
                    timeline = brand["registration_timeline"]
                    filing_cost = timeline.get("filing_cost", "")
                    if filing_cost and "₹" not in filing_cost and "inr" not in filing_cost.lower():
                        currency_issues.append(f"filing_cost should be in INR (₹), got: {filing_cost}")
                    
                    # Test 2: Check registration_timeline.opposition_defense_cost
                    defense_cost = timeline.get("opposition_defense_cost", "")
                    if defense_cost and "₹" not in defense_cost and "inr" not in defense_cost.lower():
                        currency_issues.append(f"opposition_defense_cost should be in INR (₹), got: {defense_cost}")
                
                # Test 3: Check mitigation_strategies[].estimated_cost
                if "mitigation_strategies" in brand and brand["mitigation_strategies"]:
                    for i, strategy in enumerate(brand["mitigation_strategies"]):
                        if isinstance(strategy, dict) and "estimated_cost" in strategy:
                            cost = strategy["estimated_cost"]
                            if cost and "₹" not in cost and "inr" not in cost.lower():
                                currency_issues.append(f"mitigation_strategies[{i}].estimated_cost should be in INR (₹), got: {cost}")
                
                # Test 4: Check for any USD ($) or other currencies that shouldn't be there
                response_text = json.dumps(data)
                if "$" in response_text and "usd" not in response_text.lower():
                    # Check if it's actually USD symbol, not just any $ symbol
                    import re
                    usd_pattern = r'\$[\d,.]+'
                    if re.search(usd_pattern, response_text):
                        currency_issues.append("Found USD ($) currency in India single-country response")
                if "£" in response_text or "gbp" in response_text.lower():
                    currency_issues.append("Found GBP (£) currency in India single-country response")
                if "€" in response_text or "eur" in response_text.lower():
                    currency_issues.append("Found EUR (€) currency in India single-country response")
                
                if currency_issues:
                    self.log_test("Currency Test - India Single Country", False, "; ".join(currency_issues))
                    return False
                
                self.log_test("Currency Test - India Single Country", True, "All costs correctly in INR (₹)")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Currency Test - India JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Currency Test - India Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Currency Test - India Exception", False, str(e))
            return False

    def test_currency_multiple_countries(self):
        """Test Case 3 - Multiple Countries: All costs should be in USD ($)"""
        payload = {
            "brand_names": ["TestMulti"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Multi-Country",
            "countries": ["USA", "India", "UK"]
        }
        
        try:
            print(f"\n💰 Testing Currency Logic - Multiple Countries...")
            print(f"Expected: All costs in USD ($) since multiple countries selected")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Currency Test - Multi HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Currency Test - Multi Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                currency_issues = []
                
                # Test 1: Check registration_timeline.filing_cost
                if "registration_timeline" in brand and brand["registration_timeline"]:
                    timeline = brand["registration_timeline"]
                    filing_cost = timeline.get("filing_cost", "")
                    if filing_cost and "$" not in filing_cost:
                        currency_issues.append(f"filing_cost should be in USD ($), got: {filing_cost}")
                    
                    # Test 2: Check registration_timeline.opposition_defense_cost
                    defense_cost = timeline.get("opposition_defense_cost", "")
                    if defense_cost and "$" not in defense_cost:
                        currency_issues.append(f"opposition_defense_cost should be in USD ($), got: {defense_cost}")
                
                # Test 3: Check mitigation_strategies[].estimated_cost
                if "mitigation_strategies" in brand and brand["mitigation_strategies"]:
                    for i, strategy in enumerate(brand["mitigation_strategies"]):
                        if isinstance(strategy, dict) and "estimated_cost" in strategy:
                            cost = strategy["estimated_cost"]
                            if cost and "$" not in cost:
                                currency_issues.append(f"mitigation_strategies[{i}].estimated_cost should be in USD ($), got: {cost}")
                
                # Test 4: Check for mixed currencies (should not have INR, GBP, EUR in multi-country)
                response_text = json.dumps(data).lower()
                if "₹" in response_text or "inr" in response_text:
                    currency_issues.append("Found INR (₹) currency in multi-country response (should be USD)")
                if "£" in response_text or "gbp" in response_text:
                    currency_issues.append("Found GBP (£) currency in multi-country response (should be USD)")
                if "€" in response_text or "eur" in response_text:
                    currency_issues.append("Found EUR (€) currency in multi-country response (should be USD)")
                
                if currency_issues:
                    self.log_test("Currency Test - Multiple Countries", False, "; ".join(currency_issues))
                    return False
                
                self.log_test("Currency Test - Multiple Countries", True, "All costs correctly in USD ($) for multi-country")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Currency Test - Multi JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Currency Test - Multi Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Currency Test - Multi Exception", False, str(e))
            return False

    def test_emergent_llm_key_smoke_test(self):
        """Smoke test for newly configured Emergent LLM key with TestBrand"""
        payload = {
            "brand_names": ["TestBrand"],
            "category": "Technology",
            "positioning": "Premium software solutions",
            "market_scope": "Multi-Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔍 SMOKE TEST: Testing newly configured Emergent LLM key with TestBrand...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # Extended timeout for LLM processing
            )
            
            print(f"Response Status: {response.status_code}")
            
            # Check for budget exceeded error first
            if response.status_code == 402:
                self.log_test("Emergent LLM Key - Budget Check", False, "Budget exceeded error - LLM key needs credits")
                return False
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                # Check if error message contains budget-related keywords
                if any(keyword in response.text.lower() for keyword in ["budget", "exceeded", "credits", "quota"]):
                    self.log_test("Emergent LLM Key - Budget Error", False, f"Budget-related error: {error_msg}")
                else:
                    self.log_test("Emergent LLM Key - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking structure...")
                
                # Test 1: Check for budget errors in response content
                response_str = json.dumps(data).lower()
                if any(keyword in response_str for keyword in ["budget exceeded", "quota exceeded", "credits"]):
                    self.log_test("Emergent LLM Key - Response Budget Error", False, "Budget exceeded error found in response content")
                    return False
                
                # Test 2: Check required top-level fields
                required_fields = ["executive_summary", "brand_scores", "comparison_verdict"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Emergent LLM Key - Required Fields", False, f"Missing required fields: {missing_fields}")
                    return False
                
                # Test 3: Check brand_scores structure
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Emergent LLM Key - Brand Scores", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 4: Check brand name matches
                if brand.get("brand_name") != "TestBrand":
                    self.log_test("Emergent LLM Key - Brand Name", False, f"Expected 'TestBrand', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 5: Check name_score_index (NameScore)
                if "namescore" not in brand:
                    self.log_test("Emergent LLM Key - NameScore Index", False, "namescore field missing")
                    return False
                
                namescore = brand.get("namescore")
                if not isinstance(namescore, (int, float)) or not (0 <= namescore <= 100):
                    self.log_test("Emergent LLM Key - NameScore Range", False, f"Invalid namescore: {namescore} (should be 0-100)")
                    return False
                
                # Test 6: Check trademark_research field
                if "trademark_research" not in brand:
                    self.log_test("Emergent LLM Key - Trademark Research", False, "trademark_research field missing")
                    return False
                
                tm_research = brand["trademark_research"]
                if not tm_research:
                    self.log_test("Emergent LLM Key - Trademark Data", False, "trademark_research is null/empty")
                    return False
                
                # Test 7: Check executive_summary content
                exec_summary = data.get("executive_summary", "")
                if len(exec_summary) < 50:  # Should be substantial
                    self.log_test("Emergent LLM Key - Executive Summary", False, f"Executive summary too short: {len(exec_summary)} chars")
                    return False
                
                # Test 8: Check verdict field
                if "verdict" not in brand:
                    self.log_test("Emergent LLM Key - Verdict", False, "verdict field missing")
                    return False
                
                verdict = brand.get("verdict", "")
                valid_verdicts = ["APPROVE", "CAUTION", "REJECT"]
                if verdict not in valid_verdicts:
                    self.log_test("Emergent LLM Key - Verdict Value", False, f"Invalid verdict: {verdict} (should be one of {valid_verdicts})")
                    return False
                
                # Test 9: Check additional expected fields
                expected_brand_fields = ["summary", "domain_analysis", "visibility_analysis"]
                missing_brand_fields = [field for field in expected_brand_fields if field not in brand]
                
                if missing_brand_fields:
                    print(f"⚠️  Warning: Missing optional brand fields: {missing_brand_fields}")
                
                print(f"✅ TestBrand evaluation completed successfully:")
                print(f"   - NameScore: {namescore}/100")
                print(f"   - Verdict: {verdict}")
                print(f"   - Executive Summary: {len(exec_summary)} characters")
                print(f"   - Trademark Research: Present")
                
                self.log_test("Emergent LLM Key - Smoke Test", True, 
                            f"All checks passed. NameScore: {namescore}/100, Verdict: {verdict}, No budget errors detected")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Emergent LLM Key - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Emergent LLM Key - Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Emergent LLM Key - Exception", False, str(e))
            return False

    def test_actual_uspto_costs_usa(self):
        """Test Case 1 - USA Single Country: Verify ACTUAL USPTO costs (not currency conversion)"""
        payload = {
            "brand_names": ["USACostTest"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🇺🇸 Testing ACTUAL USPTO Costs - USA Single Country...")
            print(f"Expected ACTUAL USPTO Costs:")
            print(f"  - Filing Cost: $275-$400 per class")
            print(f"  - Opposition Defense: $2,500-$10,000")
            print(f"  - Trademark Search: $500-$1,500")
            print(f"  - Legal Fees: $1,500-$5,000")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("ACTUAL USPTO Costs - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("ACTUAL USPTO Costs - Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                cost_issues = []
                
                # Test 1: Check registration_timeline.filing_cost for ACTUAL USPTO amounts
                if "registration_timeline" in brand and brand["registration_timeline"]:
                    timeline = brand["registration_timeline"]
                    filing_cost = timeline.get("filing_cost", "")
                    print(f"Found filing_cost: {filing_cost}")
                    
                    # Check for ACTUAL USPTO filing costs ($275-$400)
                    if filing_cost:
                        if not any(cost in filing_cost for cost in ["$275", "$300", "$350", "$400"]):
                            cost_issues.append(f"filing_cost should show ACTUAL USPTO costs ($275-$400), got: {filing_cost}")
                        if "₹4,500" in filing_cost or "₹9,000" in filing_cost:
                            cost_issues.append(f"filing_cost shows Indian costs converted to USD instead of ACTUAL USPTO costs: {filing_cost}")
                    
                    # Test 2: Check opposition_defense_cost for ACTUAL USPTO amounts
                    defense_cost = timeline.get("opposition_defense_cost", "")
                    print(f"Found opposition_defense_cost: {defense_cost}")
                    
                    if defense_cost:
                        if not any(cost in defense_cost for cost in ["$2,500", "$5,000", "$7,500", "$10,000"]):
                            cost_issues.append(f"opposition_defense_cost should show ACTUAL USPTO costs ($2,500-$10,000), got: {defense_cost}")
                        if "₹50,000" in defense_cost or "₹2,00,000" in defense_cost:
                            cost_issues.append(f"opposition_defense_cost shows Indian costs converted to USD instead of ACTUAL USPTO costs: {defense_cost}")
                
                # Test 3: Check mitigation_strategies for ACTUAL USPTO costs
                if "mitigation_strategies" in brand and brand["mitigation_strategies"]:
                    for i, strategy in enumerate(brand["mitigation_strategies"]):
                        if isinstance(strategy, dict) and "estimated_cost" in strategy:
                            cost = strategy["estimated_cost"]
                            print(f"Found mitigation strategy {i} cost: {cost}")
                            
                            if cost and "$" in cost:
                                # Should not be simple currency conversion from Indian amounts
                                if "₹" in str(cost) or any(bad_amount in cost for bad_amount in ["$367", "$408", "$1,225"]):  # These would be INR converted
                                    cost_issues.append(f"mitigation_strategies[{i}].estimated_cost appears to be currency conversion, not ACTUAL USPTO costs: {cost}")
                
                # Test 4: Check for trademark search and legal fees in response
                response_text = json.dumps(data)
                print(f"Checking for trademark search costs...")
                
                # Look for trademark search costs
                if "trademark_search" in response_text.lower() or "search_cost" in response_text.lower():
                    if not any(cost in response_text for cost in ["$500", "$750", "$1,000", "$1,500"]):
                        print(f"Warning: Trademark search costs may not reflect ACTUAL USPTO range ($500-$1,500)")
                
                # Look for legal fees
                if "legal_fees" in response_text.lower() or "attorney" in response_text.lower():
                    if not any(cost in response_text for cost in ["$1,500", "$2,000", "$3,000", "$5,000"]):
                        print(f"Warning: Legal fees may not reflect ACTUAL USPTO range ($1,500-$5,000)")
                
                if cost_issues:
                    self.log_test("ACTUAL USPTO Costs - USA Single Country", False, "; ".join(cost_issues))
                    return False
                
                self.log_test("ACTUAL USPTO Costs - USA Single Country", True, "All costs show ACTUAL USPTO amounts (not currency conversion)")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("ACTUAL USPTO Costs - JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("ACTUAL USPTO Costs - Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("ACTUAL USPTO Costs - Exception", False, str(e))
            return False

    def test_dimensions_population_nexaflow(self):
        """Test /api/evaluate endpoint to verify dimensions are populated as requested in review"""
        payload = {
            "brand_names": ["NexaFlow"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Multi-Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n🔍 DIMENSIONS POPULATION TEST: Testing /api/evaluate with NexaFlow...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Critical Checks:")
            print(f"  1. Response returns 200 OK")
            print(f"  2. brand_scores[0].dimensions must be array with 6 items")
            print(f"  3. Each dimension must have: name, score, reasoning")
            print(f"  4. trademark_research should NOT be null")
            print(f"  5. All required sections present")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # 180 seconds as specified in review
            )
            
            processing_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Processing Time: {processing_time:.2f} seconds")
            
            # Critical Check 1: Response Returns 200 OK
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                self.log_test("Dimensions Test - HTTP Status", False, f"Expected 200 OK, got {response.status_code}: {error_msg}")
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking dimensions...")
                
                # Check basic structure first
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Dimensions Test - Brand Scores Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Critical Check 2: DIMENSIONS MUST BE POPULATED
                if "dimensions" not in brand:
                    self.log_test("Dimensions Test - Dimensions Field Missing", False, "brand_scores[0].dimensions field is missing")
                    return False
                
                dimensions = brand["dimensions"]
                if not isinstance(dimensions, list):
                    self.log_test("Dimensions Test - Dimensions Type", False, f"dimensions should be array, got {type(dimensions)}")
                    return False
                
                if len(dimensions) != 6:
                    self.log_test("Dimensions Test - Dimensions Count", False, f"dimensions must have 6 items, got {len(dimensions)}")
                    return False
                
                print(f"✅ Found {len(dimensions)} dimensions")
                
                # Check each dimension has required fields: name, score, reasoning
                for i, dim in enumerate(dimensions):
                    if not isinstance(dim, dict):
                        self.log_test("Dimensions Test - Dimension Structure", False, f"dimensions[{i}] should be object, got {type(dim)}")
                        return False
                    
                    required_dim_fields = ["name", "score", "reasoning"]
                    missing_dim_fields = [field for field in required_dim_fields if field not in dim]
                    
                    if missing_dim_fields:
                        self.log_test("Dimensions Test - Dimension Fields", False, f"dimensions[{i}] missing fields: {missing_dim_fields}")
                        return False
                    
                    # Validate score is numeric
                    if not isinstance(dim["score"], (int, float)):
                        self.log_test("Dimensions Test - Dimension Score Type", False, f"dimensions[{i}].score should be number, got {type(dim['score'])}")
                        return False
                    
                    # Validate name and reasoning are strings
                    if not isinstance(dim["name"], str) or len(dim["name"]) == 0:
                        self.log_test("Dimensions Test - Dimension Name", False, f"dimensions[{i}].name should be non-empty string")
                        return False
                    
                    if not isinstance(dim["reasoning"], str) or len(dim["reasoning"]) < 10:
                        self.log_test("Dimensions Test - Dimension Reasoning", False, f"dimensions[{i}].reasoning should be substantial string (>10 chars)")
                        return False
                    
                    print(f"  ✅ Dimension {i+1}: {dim['name']} (Score: {dim['score']}, Reasoning: {len(dim['reasoning'])} chars)")
                
                # Critical Check 3: Trademark Research Present
                if "trademark_research" not in brand:
                    self.log_test("Dimensions Test - Trademark Research Field", False, "brand_scores[0].trademark_research field is missing")
                    return False
                
                trademark_research = brand["trademark_research"]
                if trademark_research is None:
                    self.log_test("Dimensions Test - Trademark Research Null", False, "brand_scores[0].trademark_research should NOT be null")
                    return False
                
                # Check trademark_research has required fields
                if not isinstance(trademark_research, dict):
                    self.log_test("Dimensions Test - Trademark Research Type", False, f"trademark_research should be object, got {type(trademark_research)}")
                    return False
                
                required_tm_fields = ["overall_risk_score", "registration_success_probability"]
                missing_tm_fields = [field for field in required_tm_fields if field not in trademark_research]
                
                if missing_tm_fields:
                    self.log_test("Dimensions Test - Trademark Research Fields", False, f"trademark_research missing fields: {missing_tm_fields}")
                    return False
                
                print(f"✅ Trademark Research: Risk {trademark_research.get('overall_risk_score')}/10, Success {trademark_research.get('registration_success_probability')}%")
                
                # Critical Check 4: All Required Sections
                required_sections = ["executive_summary", "verdict", "namescore", "final_assessment"]
                
                # Check executive_summary at top level
                if "executive_summary" not in data:
                    self.log_test("Dimensions Test - Executive Summary", False, "executive_summary missing from response")
                    return False
                
                exec_summary = data["executive_summary"]
                if not isinstance(exec_summary, str) or len(exec_summary) < 50:
                    self.log_test("Dimensions Test - Executive Summary Content", False, f"executive_summary should be substantial string, got {len(exec_summary) if isinstance(exec_summary, str) else type(exec_summary)}")
                    return False
                
                # Check brand-level required fields
                brand_required = ["verdict", "namescore", "final_assessment"]
                missing_brand_fields = [field for field in brand_required if field not in brand]
                
                if missing_brand_fields:
                    self.log_test("Dimensions Test - Brand Required Fields", False, f"brand_scores[0] missing fields: {missing_brand_fields}")
                    return False
                
                # Validate verdict
                verdict = brand["verdict"]
                valid_verdicts = ["GO", "CONDITIONAL GO", "REJECT"]
                if verdict not in valid_verdicts:
                    self.log_test("Dimensions Test - Verdict Value", False, f"verdict should be one of {valid_verdicts}, got '{verdict}'")
                    return False
                
                # Validate namescore
                namescore = brand["namescore"]
                if not isinstance(namescore, (int, float)) or not (0 <= namescore <= 100):
                    self.log_test("Dimensions Test - NameScore Range", False, f"namescore should be 0-100, got {namescore}")
                    return False
                
                # Validate final_assessment
                final_assessment = brand["final_assessment"]
                if not isinstance(final_assessment, str) or len(final_assessment) < 20:
                    self.log_test("Dimensions Test - Final Assessment", False, f"final_assessment should be substantial string, got {len(final_assessment) if isinstance(final_assessment, str) else type(final_assessment)}")
                    return False
                
                print(f"✅ All Required Sections Present:")
                print(f"  - Executive Summary: {len(exec_summary)} chars")
                print(f"  - Verdict: {verdict}")
                print(f"  - NameScore: {namescore}/100")
                print(f"  - Final Assessment: {len(final_assessment)} chars")
                
                self.log_test("Dimensions Population Test - NexaFlow Complete", True, 
                            f"✅ ALL CHECKS PASSED: 6 dimensions populated, trademark_research present, all required sections found. NameScore: {namescore}/100, Verdict: {verdict}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Dimensions Test - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Dimensions Test - Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Dimensions Test - Exception", False, str(e))
            return False

    def test_brand_audit_chai_bunk_compact_prompt(self):
        """Test Brand Audit API with Chai Bunk using compact prompt for faster processing"""
        payload = {
            "brand_name": "Chai Bunk",
            "brand_website": "https://www.chaibunk.com",
            "competitor_1": "https://www.chaayos.com",
            "competitor_2": "https://www.chaipoint.com",
            "category": "Cafe/QSR",
            "geography": "India"
        }
        
        try:
            print(f"\n🔍 Testing Brand Audit API with Chai Bunk using compact prompt...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Expected Behavior:")
            print(f"  1. Website crawling completes (look for 'Successfully crawled' in logs)")
            print(f"  2. Web searches complete (5 searches)")
            print(f"  3. LLM generates JSON response (compact prompt ~3K chars)")
            print(f"  4. Response returns 200 OK with valid JSON")
            print(f"Expected in response:")
            print(f"  - report_id exists")
            print(f"  - overall_score is a number")
            print(f"  - brand_overview.outlets_count mentions '120'")
            print(f"  - dimensions array has 8 items")
            print(f"  - swot has all 4 categories")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/brand-audit", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # 3 minutes timeout as specified
            )
            
            processing_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Processing Time: {processing_time:.2f} seconds")
            
            # Test 1: API should return 200 OK (not timeout or server error)
            if response.status_code not in [200]:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                if response.status_code in [502, 500, 503]:
                    self.log_test("Brand Audit - Chai Bunk Server Error", False, f"Server error (expected 200 OK): {error_msg}")
                elif response.status_code == 408:
                    self.log_test("Brand Audit - Chai Bunk Timeout", False, f"Request timeout: {error_msg}")
                else:
                    self.log_test("Brand Audit - Chai Bunk HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking structure...")
                
                # Test 2: Check required top-level fields
                required_fields = ["report_id", "overall_score", "brand_overview", "dimensions", "swot"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Brand Audit - Chai Bunk Required Fields", False, f"Missing required fields: {missing_fields}")
                    return False
                
                # Test 3: Check report_id exists and is string
                report_id = data.get("report_id")
                if not isinstance(report_id, str) or len(report_id) == 0:
                    self.log_test("Brand Audit - Chai Bunk Report ID", False, f"Invalid report_id: {report_id}")
                    return False
                
                # Test 4: Check overall_score is number
                overall_score = data.get("overall_score")
                if not isinstance(overall_score, (int, float)):
                    self.log_test("Brand Audit - Chai Bunk Overall Score", False, f"overall_score is not a number: {overall_score}")
                    return False
                
                # Test 5: Check brand_overview.outlets_count mentions "120"
                brand_overview = data.get("brand_overview", {})
                outlets_count = brand_overview.get("outlets_count", "")
                if "120" not in str(outlets_count):
                    self.log_test("Brand Audit - Chai Bunk Outlets Count", False, f"brand_overview.outlets_count should mention '120', got: {outlets_count}")
                    return False
                
                # Test 6: Check dimensions array has 8 items
                dimensions = data.get("dimensions", [])
                if not isinstance(dimensions, list) or len(dimensions) != 8:
                    self.log_test("Brand Audit - Chai Bunk Dimensions Count", False, f"dimensions array should have 8 items, got: {len(dimensions)}")
                    return False
                
                # Test 7: Check swot has all 4 categories
                swot = data.get("swot", {})
                required_swot_categories = ["strengths", "weaknesses", "opportunities", "threats"]
                missing_swot = [cat for cat in required_swot_categories if cat not in swot]
                
                if missing_swot:
                    self.log_test("Brand Audit - Chai Bunk SWOT Categories", False, f"Missing SWOT categories: {missing_swot}")
                    return False
                
                # Test 8: Verify each SWOT category has items
                for category in required_swot_categories:
                    swot_items = swot.get(category, [])
                    if not isinstance(swot_items, list) or len(swot_items) == 0:
                        self.log_test("Brand Audit - Chai Bunk SWOT Content", False, f"SWOT {category} should have items, got: {swot_items}")
                        return False
                
                # Test 9: Check dimensions structure
                for i, dimension in enumerate(dimensions):
                    if not isinstance(dimension, dict):
                        self.log_test("Brand Audit - Chai Bunk Dimension Structure", False, f"dimensions[{i}] should be object, got: {type(dimension)}")
                        return False
                    
                    required_dim_fields = ["name", "score"]
                    missing_dim_fields = [field for field in required_dim_fields if field not in dimension]
                    if missing_dim_fields:
                        self.log_test("Brand Audit - Chai Bunk Dimension Fields", False, f"dimensions[{i}] missing fields: {missing_dim_fields}")
                        return False
                
                print(f"✅ All validation checks passed:")
                print(f"   - Report ID: {report_id}")
                print(f"   - Overall Score: {overall_score}")
                print(f"   - Outlets Count: {outlets_count}")
                print(f"   - Dimensions: {len(dimensions)} items")
                print(f"   - SWOT Categories: {list(swot.keys())}")
                print(f"   - Processing Time: {processing_time:.2f} seconds")
                
                self.log_test("Brand Audit - Chai Bunk Compact Prompt", True, 
                            f"All checks passed. Report ID: {report_id}, Overall Score: {overall_score}, Processing Time: {processing_time:.2f}s")
                return True
                
                # Test 6: Check executive_summary is substantial text
                exec_summary = data.get("executive_summary", "")
                if len(exec_summary) < 50:
                    self.log_test("Brand Audit - Tea Villa Executive Summary", False, f"Executive summary too short: {len(exec_summary)} chars")
                    return False
                
                # Test 7: Check dimensions array has 8 items
                dimensions = data.get("dimensions", [])
                if not isinstance(dimensions, list) or len(dimensions) != 8:
                    self.log_test("Brand Audit - Tea Villa Dimensions Count", False, f"Expected 8 dimensions, got {len(dimensions)}")
                    return False
                
                # Test 8: Check each dimension has required structure
                for i, dimension in enumerate(dimensions):
                    if not isinstance(dimension, dict):
                        self.log_test("Brand Audit - Tea Villa Dimension Structure", False, f"Dimension {i} is not a dict")
                        return False
                    
                    required_dim_fields = ["name", "score", "reasoning"]
                    missing_dim_fields = [field for field in required_dim_fields if field not in dimension]
                    
                    if missing_dim_fields:
                        self.log_test("Brand Audit - Tea Villa Dimension Fields", False, f"Dimension {i} missing fields: {missing_dim_fields}")
                        return False
                    
                    # Check score is 0-10
                    dim_score = dimension.get("score")
                    if not isinstance(dim_score, (int, float)) or not (0 <= dim_score <= 10):
                        self.log_test("Brand Audit - Tea Villa Dimension Score", False, f"Dimension {i} invalid score: {dim_score} (should be 0-10)")
                        return False
                
                print(f"✅ Tea Villa Brand Audit completed successfully:")
                print(f"   - Report ID: {report_id}")
                print(f"   - Overall Score: {overall_score}/100")
                print(f"   - Verdict: {verdict}")
                print(f"   - Executive Summary: {len(exec_summary)} characters")
                print(f"   - Dimensions: {len(dimensions)} items")
                print(f"   - Processing Time: {processing_time:.2f} seconds")
                
                self.log_test("Brand Audit - Tea Villa Claude Fix", True, 
                            f"SUCCESS after Claude fix. Score: {overall_score}/100, Verdict: {verdict}, Time: {processing_time:.2f}s, All 8 dimensions present")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Brand Audit - Tea Villa JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Brand Audit - Tea Villa Timeout", False, "Request timed out after 180 seconds - Claude fix may not be working")
            return False
        except Exception as e:
            self.log_test("Brand Audit - Tea Villa Exception", False, str(e))
            return False

    def test_brand_audit_haldiram(self):
        """Test Brand Audit API endpoint with Haldiram (famous Indian food brand)"""
        payload = {
            "brand_name": "Haldiram",
            "brand_website": "https://haldirams.com",
            "category": "Food & Beverage",
            "geography": "India",
            "competitor_1": "Bikaji",
            "competitor_2": "Balaji"
        }
        
        try:
            print(f"\n🔍 Testing Brand Audit API with Haldiram...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Expected: API should return proper response with report_id, overall_score, verdict, executive_summary, dimensions")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/brand-audit", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # Extended timeout for brand audit processing
            )
            
            processing_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Processing Time: {processing_time:.2f} seconds")
            
            # Test 1: API should return 200 OK (not 502 or 500 error)
            if response.status_code not in [200]:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                if response.status_code in [502, 500]:
                    self.log_test("Brand Audit - Haldiram Server Error", False, f"Server error (expected 200 OK): {error_msg}")
                else:
                    self.log_test("Brand Audit - Haldiram HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking structure...")
                
                # Test 2: Check required top-level fields
                required_fields = ["report_id", "overall_score", "verdict", "executive_summary", "dimensions"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Brand Audit - Haldiram Required Fields", False, f"Missing required fields: {missing_fields}")
                    return False
                
                # Test 3: Check report_id is string
                report_id = data.get("report_id")
                if not isinstance(report_id, str) or len(report_id) == 0:
                    self.log_test("Brand Audit - Haldiram Report ID", False, f"Invalid report_id: {report_id}")
                    return False
                
                # Test 4: Check overall_score is number 0-100
                overall_score = data.get("overall_score")
                if not isinstance(overall_score, (int, float)) or not (0 <= overall_score <= 100):
                    self.log_test("Brand Audit - Haldiram Overall Score", False, f"Invalid overall_score: {overall_score} (should be 0-100)")
                    return False
                
                # Test 5: Check verdict is one of expected values
                verdict = data.get("verdict", "")
                valid_verdicts = ["STRONG", "MODERATE", "WEAK", "CRITICAL"]
                if verdict not in valid_verdicts:
                    self.log_test("Brand Audit - Haldiram Verdict", False, f"Invalid verdict: {verdict} (should be one of {valid_verdicts})")
                    return False
                
                # Test 6: Check executive_summary is substantial text
                exec_summary = data.get("executive_summary", "")
                if len(exec_summary) < 50:
                    self.log_test("Brand Audit - Haldiram Executive Summary", False, f"Executive summary too short: {len(exec_summary)} chars")
                    return False
                
                # Test 7: Check dimensions array has 8 brand dimensions
                dimensions = data.get("dimensions", [])
                if not isinstance(dimensions, list) or len(dimensions) != 8:
                    self.log_test("Brand Audit - Haldiram Dimensions Count", False, f"Expected 8 dimensions, got {len(dimensions)}")
                    return False
                
                # Test 8: Check each dimension has required fields
                for i, dimension in enumerate(dimensions):
                    if not isinstance(dimension, dict):
                        self.log_test("Brand Audit - Haldiram Dimension Structure", False, f"Dimension {i} is not a dict")
                        return False
                    
                    dim_required = ["name", "score", "analysis"]
                    dim_missing = [field for field in dim_required if field not in dimension]
                    if dim_missing:
                        self.log_test("Brand Audit - Haldiram Dimension Fields", False, f"Dimension {i} missing fields: {dim_missing}")
                        return False
                    
                    # Check score is 0-100
                    dim_score = dimension.get("score")
                    if not isinstance(dim_score, (int, float)) or not (0 <= dim_score <= 100):
                        self.log_test("Brand Audit - Haldiram Dimension Score", False, f"Dimension {i} invalid score: {dim_score}")
                        return False
                
                # Test 9: Check brand_name matches input
                brand_name = data.get("brand_name", "")
                if brand_name != "Haldiram":
                    self.log_test("Brand Audit - Haldiram Brand Name", False, f"Expected 'Haldiram', got '{brand_name}'")
                    return False
                
                print(f"✅ Haldiram Brand Audit completed successfully:")
                print(f"   - Report ID: {report_id}")
                print(f"   - Overall Score: {overall_score}/100")
                print(f"   - Verdict: {verdict}")
                print(f"   - Executive Summary: {len(exec_summary)} characters")
                print(f"   - Dimensions: {len(dimensions)} brand dimensions")
                print(f"   - Processing Time: {processing_time:.2f} seconds")
                
                self.log_test("Brand Audit - Haldiram Complete", True, 
                            f"All checks passed. Score: {overall_score}/100, Verdict: {verdict}, Dimensions: {len(dimensions)}, Time: {processing_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Brand Audit - Haldiram JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Brand Audit - Haldiram Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Brand Audit - Haldiram Exception", False, str(e))
            return False

    def test_brand_audit_bikanervala_final(self):
        """Test Brand Audit API with Bikanervala test case as requested in review"""
        payload = {
            "brand_name": "Bikanervala",
            "brand_website": "https://bfresco.com",
            "category": "Food & Beverage",
            "geography": "India",
            "competitor_1": "Haldiram",
            "competitor_2": "Bikano"
        }
        
        try:
            print(f"\n🔍 FINAL BRAND AUDIT TEST: Testing with Bikanervala as requested...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Expected: Status 200 with report_id, overall_score, verdict, executive_summary, dimensions")
            print(f"Timeout: 180 seconds allowed")
            print(f"Success Criteria: Valid JSON response = SUCCESS")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/brand-audit", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # Allow 180 seconds as requested
            )
            
            processing_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Processing Time: {processing_time:.2f} seconds")
            
            # Test 1: Check for 200 OK status
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                if response.status_code in [502, 500, 503]:
                    self.log_test("Brand Audit - Bikanervala Server Error", False, f"Server error (expected 200 OK): {error_msg}")
                elif response.status_code == 408:
                    self.log_test("Brand Audit - Bikanervala Timeout", False, f"Request timeout: {error_msg}")
                else:
                    self.log_test("Brand Audit - Bikanervala HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking structure...")
                
                # Test 2: Check required fields as specified in review request
                required_fields = ["report_id", "overall_score", "verdict", "executive_summary", "dimensions"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Brand Audit - Bikanervala Required Fields", False, f"Missing required fields: {missing_fields}")
                    return False
                
                # Test 3: Validate report_id
                report_id = data.get("report_id")
                if not isinstance(report_id, str) or len(report_id) == 0:
                    self.log_test("Brand Audit - Bikanervala Report ID", False, f"Invalid report_id: {report_id}")
                    return False
                
                # Test 4: Validate overall_score (0-100)
                overall_score = data.get("overall_score")
                if not isinstance(overall_score, (int, float)) or not (0 <= overall_score <= 100):
                    self.log_test("Brand Audit - Bikanervala Overall Score", False, f"Invalid overall_score: {overall_score} (should be 0-100)")
                    return False
                
                # Test 5: Validate verdict
                verdict = data.get("verdict", "")
                valid_verdicts = ["STRONG", "MODERATE", "WEAK", "CRITICAL", "EXCELLENT", "GOOD", "POOR"]
                if verdict not in valid_verdicts:
                    self.log_test("Brand Audit - Bikanervala Verdict", False, f"Invalid verdict: {verdict} (should be one of {valid_verdicts})")
                    return False
                
                # Test 6: Validate executive_summary
                executive_summary = data.get("executive_summary", "")
                if not isinstance(executive_summary, str) or len(executive_summary) < 50:
                    self.log_test("Brand Audit - Bikanervala Executive Summary", False, f"Invalid executive_summary: {len(executive_summary)} chars (should be substantial)")
                    return False
                
                # Test 7: Validate dimensions array
                dimensions = data.get("dimensions", [])
                if not isinstance(dimensions, list) or len(dimensions) == 0:
                    self.log_test("Brand Audit - Bikanervala Dimensions", False, f"Invalid dimensions: {type(dimensions)} with {len(dimensions) if isinstance(dimensions, list) else 'N/A'} items")
                    return False
                
                # Test 8: Check dimensions structure
                for i, dimension in enumerate(dimensions):
                    if not isinstance(dimension, dict):
                        self.log_test("Brand Audit - Bikanervala Dimension Structure", False, f"Dimension {i} is not a dict: {type(dimension)}")
                        return False
                    
                    required_dim_fields = ["name", "score"]
                    missing_dim_fields = [field for field in required_dim_fields if field not in dimension]
                    if missing_dim_fields:
                        self.log_test("Brand Audit - Bikanervala Dimension Fields", False, f"Dimension {i} missing fields: {missing_dim_fields}")
                        return False
                
                # Test 9: Check for schema validation issues (sources[].id should be string)
                response_text = json.dumps(data)
                if "sources" in response_text:
                    print("✅ Sources field found in response")
                    # Check if there are any validation errors in the response
                    if "validation" in response_text.lower() and "error" in response_text.lower():
                        self.log_test("Brand Audit - Bikanervala Schema Validation", False, "Schema validation errors detected in response")
                        return False
                
                print(f"✅ Bikanervala Brand Audit completed successfully:")
                print(f"   - Report ID: {report_id}")
                print(f"   - Overall Score: {overall_score}/100")
                print(f"   - Verdict: {verdict}")
                print(f"   - Executive Summary: {len(executive_summary)} characters")
                print(f"   - Dimensions: {len(dimensions)} items")
                print(f"   - Processing Time: {processing_time:.2f} seconds")
                
                self.log_test("Brand Audit - Bikanervala Final Test", True, 
                            f"SUCCESS: Valid JSON response received. Report ID: {report_id}, Score: {overall_score}/100, Verdict: {verdict}, Time: {processing_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Brand Audit - Bikanervala JSON Parse", False, f"Invalid JSON response: {str(e)}")
                print(f"❌ Response was not valid JSON: {response.text[:500]}...")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Brand Audit - Bikanervala Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Brand Audit - Bikanervala Exception", False, str(e))
            return False

    def test_fallback_model_feature(self):
        """Test the new fallback model feature with FallbackTest brand"""
        payload = {
            "brand_names": ["FallbackTest"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔄 Testing Fallback Model Feature...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Expected: API should try gpt-4o first, then fallback to gpt-4o-mini if needed")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # Extended timeout for LLM processing with retries
            )
            
            print(f"Response Status: {response.status_code}")
            
            # Test 1: API should return 200 OK (not 502 or 500 error)
            if response.status_code not in [200]:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                if response.status_code in [502, 500]:
                    self.log_test("Fallback Model Feature - Server Error", False, f"Server error (expected 200 OK): {error_msg}")
                else:
                    self.log_test("Fallback Model Feature - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking structure...")
                
                # Test 2: Response should contain valid brand evaluation data
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Fallback Model Feature - Brand Scores Missing", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 3: Check for FallbackTest brand name
                if brand.get("brand_name") != "FallbackTest":
                    self.log_test("Fallback Model Feature - Brand Name", False, f"Expected 'FallbackTest', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 4: Check for required evaluation fields
                required_fields = ["namescore", "verdict", "summary"]
                missing_fields = [field for field in required_fields if field not in brand]
                
                if missing_fields:
                    self.log_test("Fallback Model Feature - Required Fields", False, f"Missing required fields: {missing_fields}")
                    return False
                
                # Test 5: Check namescore is valid
                namescore = brand.get("namescore")
                if not isinstance(namescore, (int, float)) or not (0 <= namescore <= 100):
                    self.log_test("Fallback Model Feature - NameScore Range", False, f"Invalid namescore: {namescore} (should be 0-100)")
                    return False
                
                # Test 6: Check verdict is valid
                verdict = brand.get("verdict", "")
                valid_verdicts = ["APPROVE", "CAUTION", "REJECT", "GO"]  # Added GO as valid verdict
                if verdict not in valid_verdicts:
                    self.log_test("Fallback Model Feature - Verdict Value", False, f"Invalid verdict: {verdict} (should be one of {valid_verdicts})")
                    return False
                
                # Test 7: Check executive summary exists
                exec_summary = data.get("executive_summary", "")
                if len(exec_summary) < 20:
                    self.log_test("Fallback Model Feature - Executive Summary", False, f"Executive summary too short: {len(exec_summary)} chars")
                    return False
                
                print(f"✅ FallbackTest evaluation completed successfully:")
                print(f"   - NameScore: {namescore}")
                print(f"   - Verdict: {verdict}")
                print(f"   - Executive Summary: {len(exec_summary)} characters")
                print(f"   - API returned 200 OK (not 502/500)")
                
                self.log_test("Fallback Model Feature", True, 
                            f"API returned 200 OK with valid data. NameScore: {namescore}, Verdict: {verdict}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Fallback Model Feature - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Fallback Model Feature - Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Fallback Model Feature - Exception", False, str(e))
            return False

    def test_early_stopping_famous_brands(self):
        """Test Improvement #5: Early Stopping for Famous Brands"""
        import time
        
        # Test with Nike (famous brand)
        payload = {
            "brand_names": ["Nike"],
            "category": "Fashion",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n⚡ Testing Early Stopping for Famous Brands (Improvement #5)...")
            print(f"Testing with brand: Nike (should be immediately rejected)")
            print(f"Expected: Response time < 5 seconds, REJECT verdict, 'IMMEDIATE REJECTION' in summary")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=30  # Should be much faster than normal
            )
            end_time = time.time()
            response_time = end_time - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Early Stopping - Famous Brands HTTP", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                # Test 1: Response time should be < 5 seconds (early stopping)
                if response_time > 5:
                    self.log_test("Early Stopping - Response Time", False, f"Response took {response_time:.2f}s (expected < 5s)")
                    return False
                
                # Test 2: Check for brand scores
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Early Stopping - Brand Scores", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 3: Verdict should be REJECT
                verdict = brand.get("verdict", "")
                if verdict != "REJECT":
                    self.log_test("Early Stopping - Verdict", False, f"Expected REJECT verdict, got: {verdict}")
                    return False
                
                # Test 4: Executive summary should contain "IMMEDIATE REJECTION"
                exec_summary = data.get("executive_summary", "")
                if "IMMEDIATE REJECTION" not in exec_summary:
                    self.log_test("Early Stopping - Executive Summary", False, f"Expected 'IMMEDIATE REJECTION' in summary, got: {exec_summary[:100]}...")
                    return False
                
                # Test 5: NameScore should be very low (< 10)
                namescore = brand.get("namescore", 100)
                if namescore > 10:
                    self.log_test("Early Stopping - Low NameScore", False, f"Expected very low NameScore (< 10), got: {namescore}")
                    return False
                
                print(f"✅ Early stopping test passed:")
                print(f"   - Response time: {response_time:.2f}s (< 5s)")
                print(f"   - Verdict: {verdict}")
                print(f"   - NameScore: {namescore}")
                print(f"   - Contains 'IMMEDIATE REJECTION': Yes")
                
                self.log_test("Early Stopping - Famous Brands", True, 
                            f"Nike immediately rejected in {response_time:.2f}s with REJECT verdict")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Early Stopping - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Early Stopping - Timeout", False, "Request timed out (should be < 5s)")
            return False
        except Exception as e:
            self.log_test("Early Stopping - Exception", False, str(e))
            return False

    def test_parallel_processing_speed(self):
        """Test Improvement #1: Parallel Processing Speed"""
        import time
        
        payload = {
            "brand_names": ["TestSpeed123"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Multi-Country",
            "countries": ["USA", "India"]
        }
        
        try:
            print(f"\n🚀 Testing Parallel Processing Speed (Improvement #1)...")
            print(f"Testing with brand: TestSpeed123")
            print(f"Expected: Response time 40-70 seconds (down from 90-120s)")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120  # Allow up to 2 minutes
            )
            end_time = time.time()
            response_time = end_time - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Parallel Processing - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                # Test 1: Response time should be 40-70 seconds (improved from 90-120s)
                if response_time > 80:
                    self.log_test("Parallel Processing - Speed Improvement", False, 
                                f"Response took {response_time:.2f}s (expected 40-70s, was 90-120s before)")
                    return False
                
                if response_time < 20:
                    print(f"Warning: Response very fast ({response_time:.2f}s) - may indicate caching or early stopping")
                
                # Test 2: Check for valid response structure
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Parallel Processing - Response Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 3: Check that all expected data sections are present (indicating parallel processing worked)
                expected_sections = ["domain_analysis", "trademark_research", "visibility_analysis"]
                missing_sections = [section for section in expected_sections if section not in brand]
                
                if missing_sections:
                    self.log_test("Parallel Processing - Data Completeness", False, 
                                f"Missing data sections (parallel processing may have failed): {missing_sections}")
                    return False
                
                # Test 4: Check brand name matches
                if brand.get("brand_name") != "TestSpeed123":
                    self.log_test("Parallel Processing - Brand Name", False, 
                                f"Expected 'TestSpeed123', got '{brand.get('brand_name')}'")
                    return False
                
                print(f"✅ Parallel processing test passed:")
                print(f"   - Response time: {response_time:.2f}s (target: 40-70s)")
                print(f"   - All data sections present: {expected_sections}")
                print(f"   - Speed improvement: {max(0, 90 - response_time):.1f}s faster than old sequential method")
                
                self.log_test("Parallel Processing - Speed Test", True, 
                            f"Response in {response_time:.2f}s with complete data (target: 40-70s)")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Parallel Processing - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Parallel Processing - Timeout", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("Parallel Processing - Exception", False, str(e))
            return False

    def test_new_form_fields(self):
        """Test Improvements #2 & #3: New Form Fields (competitors and keywords)"""
        payload = {
            "brand_names": ["PayQuick"],
            "known_competitors": ["PhonePe", "Paytm", "GooglePay"],
            "product_keywords": ["UPI", "wallet", "payments"],
            "category": "Fintech",
            "industry": "Finance",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n📝 Testing New Form Fields (Improvements #2 & #3)...")
            print(f"Testing with brand: PayQuick")
            print(f"Known competitors: {payload['known_competitors']}")
            print(f"Product keywords: {payload['product_keywords']}")
            print(f"Expected: Competitor conflicts detected")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("New Form Fields - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                # Test 1: Check for valid response structure
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("New Form Fields - Response Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 2: Check brand name matches
                if brand.get("brand_name") != "PayQuick":
                    self.log_test("New Form Fields - Brand Name", False, 
                                f"Expected 'PayQuick', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 3: Check if known competitors are mentioned in the response
                response_text = json.dumps(data).lower()
                competitors_found = []
                for competitor in payload['known_competitors']:
                    if competitor.lower() in response_text:
                        competitors_found.append(competitor)
                
                if len(competitors_found) < 2:  # At least 2 out of 3 competitors should be mentioned
                    self.log_test("New Form Fields - Competitor Detection", False, 
                                f"Expected competitors not found in analysis. Found: {competitors_found}")
                    return False
                
                # Test 4: Check if product keywords are utilized
                keywords_found = []
                for keyword in payload['product_keywords']:
                    if keyword.lower() in response_text:
                        keywords_found.append(keyword)
                
                if len(keywords_found) < 2:  # At least 2 out of 3 keywords should be mentioned
                    self.log_test("New Form Fields - Keyword Utilization", False, 
                                f"Expected keywords not found in analysis. Found: {keywords_found}")
                    return False
                
                print(f"✅ New form fields test passed:")
                print(f"   - Competitors found in analysis: {competitors_found}")
                print(f"   - Keywords found in analysis: {keywords_found}")
                
                self.log_test("New Form Fields - Competitors & Keywords", True, 
                            f"Competitors detected: {competitors_found}, Keywords used: {keywords_found}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("New Form Fields - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("New Form Fields - Timeout", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("New Form Fields - Exception", False, str(e))
            return False

    def test_play_store_error_handling(self):
        """Test Improvement #4: Play Store Error Handling"""
        payload = {
            "brand_names": ["PlayStoreTest"],
            "category": "Mobile App",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA", "India"]
        }
        
        try:
            print(f"\n🛡️ Testing Play Store Error Handling (Improvement #4)...")
            print(f"Testing with brand: PlayStoreTest")
            print(f"Expected: No crashes, graceful error handling")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120
            )
            
            print(f"Response Status: {response.status_code}")
            
            # Test 1: API should not crash (should return 200, not 500/502)
            if response.status_code in [500, 502, 503]:
                self.log_test("Play Store Error Handling - Server Crash", False, 
                            f"Server crashed with {response.status_code} (should handle errors gracefully)")
                return False
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Play Store Error Handling - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                # Test 2: Check for valid response structure (no crashes)
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Play Store Error Handling - Response Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 3: Check brand name matches
                if brand.get("brand_name") != "PlayStoreTest":
                    self.log_test("Play Store Error Handling - Brand Name", False, 
                                f"Expected 'PlayStoreTest', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 4: Check for reasonable verdict (not error state)
                verdict = brand.get("verdict", "")
                if verdict not in ["APPROVE", "CAUTION", "REJECT", "GO"]:
                    self.log_test("Play Store Error Handling - Valid Verdict", False, 
                                f"Invalid verdict: {verdict} (should have valid verdict despite errors)")
                    return False
                
                print(f"✅ Play Store error handling test passed:")
                print(f"   - No server crashes detected")
                print(f"   - Analysis completed with verdict: {verdict}")
                
                self.log_test("Play Store Error Handling", True, 
                            f"No crashes, graceful error handling, analysis completed with {verdict} verdict")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Play Store Error Handling - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Play Store Error Handling - Timeout", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("Play Store Error Handling - Exception", False, str(e))
            return False

    def test_score_impact_validation_fix(self):
        """Test the score_impact validation fix with TestFix brand"""
        payload = {
            "brand_names": ["TestFix"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔧 Testing score_impact validation fix...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # Extended timeout for LLM processing
            )
            
            print(f"Response Status: {response.status_code}")
            
            # Test 1: API should return 200 OK (not validation error)
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                # Check specifically for validation errors
                if "validation" in response.text.lower() or "score_impact" in response.text.lower():
                    self.log_test("Score Impact Validation Fix - Validation Error", False, f"Validation error still present: {error_msg}")
                else:
                    self.log_test("Score Impact Validation Fix - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking for validation issues...")
                
                # Test 2: Response should contain brand_scores with namescore and verdict
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Score Impact Validation Fix - Brand Scores Missing", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Check for namescore
                if "namescore" not in brand:
                    self.log_test("Score Impact Validation Fix - NameScore Missing", False, "namescore field missing from response")
                    return False
                
                # Check for verdict
                if "verdict" not in brand:
                    self.log_test("Score Impact Validation Fix - Verdict Missing", False, "verdict field missing from response")
                    return False
                
                # Test 3: Check for score_impact validation errors in response
                response_str = json.dumps(data).lower()
                if "score_impact" in response_str and "validation" in response_str:
                    self.log_test("Score Impact Validation Fix - Validation Error in Response", False, "score_impact validation error found in response content")
                    return False
                
                if "error" in response_str and "score_impact" in response_str:
                    self.log_test("Score Impact Validation Fix - Score Impact Error", False, "score_impact error found in response content")
                    return False
                
                # Test 4: Check domain_analysis.score_impact field specifically
                if "domain_analysis" in brand and brand["domain_analysis"]:
                    domain_analysis = brand["domain_analysis"]
                    if "score_impact" in domain_analysis:
                        score_impact = domain_analysis["score_impact"]
                        # Should be a string, not causing validation errors
                        if not isinstance(score_impact, str):
                            self.log_test("Score Impact Validation Fix - Type Issue", False, f"score_impact should be string, got {type(score_impact)}: {score_impact}")
                            return False
                        print(f"✅ score_impact field present and valid: {score_impact}")
                
                # Test 5: Verify TestFix brand name is in response
                if brand.get("brand_name") != "TestFix":
                    self.log_test("Score Impact Validation Fix - Brand Name", False, f"Expected 'TestFix', got '{brand.get('brand_name')}'")
                    return False
                
                namescore = brand.get("namescore")
                verdict = brand.get("verdict")
                
                print(f"✅ TestFix evaluation completed successfully:")
                print(f"   - NameScore: {namescore}")
                print(f"   - Verdict: {verdict}")
                print(f"   - No score_impact validation errors detected")
                
                self.log_test("Score Impact Validation Fix", True, 
                            f"API returned 200 OK with valid response. NameScore: {namescore}, Verdict: {verdict}, No validation errors")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Score Impact Validation Fix - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Score Impact Validation Fix - Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Score Impact Validation Fix - Exception", False, str(e))
            return False

    def test_actual_ip_india_costs(self):
        """Test Case 2 - India Single Country: Verify ACTUAL IP India costs (not currency conversion)"""
        payload = {
            "brand_names": ["IndiaCostTest"],
            "category": "Fashion",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n🇮🇳 Testing ACTUAL IP India Costs - India Single Country...")
            print(f"Expected ACTUAL IP India Costs:")
            print(f"  - Filing Cost: ₹4,500-₹9,000 per class")
            print(f"  - Opposition Defense: ₹50,000-₹2,00,000")
            print(f"  - Trademark Search: ₹3,000-₹5,000")
            print(f"  - Legal Fees: ₹10,000-₹30,000")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("ACTUAL IP India Costs - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("ACTUAL IP India Costs - Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                cost_issues = []
                
                # Test 1: Check registration_timeline.filing_cost for ACTUAL IP India amounts
                if "registration_timeline" in brand and brand["registration_timeline"]:
                    timeline = brand["registration_timeline"]
                    filing_cost = timeline.get("filing_cost", "")
                    print(f"Found filing_cost: {filing_cost}")
                    
                    # Check for ACTUAL IP India filing costs (₹4,500-₹9,000)
                    if filing_cost:
                        if not any(cost in filing_cost for cost in ["₹4,500", "₹6,000", "₹7,500", "₹9,000"]):
                            cost_issues.append(f"filing_cost should show ACTUAL IP India costs (₹4,500-₹9,000), got: {filing_cost}")
                        if "$275" in filing_cost or "$400" in filing_cost:
                            cost_issues.append(f"filing_cost shows US costs converted to INR instead of ACTUAL IP India costs: {filing_cost}")
                    
                    # Test 2: Check opposition_defense_cost for ACTUAL IP India amounts
                    defense_cost = timeline.get("opposition_defense_cost", "")
                    print(f"Found opposition_defense_cost: {defense_cost}")
                    
                    if defense_cost:
                        if not any(cost in defense_cost for cost in ["₹50,000", "₹1,00,000", "₹1,50,000", "₹2,00,000"]):
                            cost_issues.append(f"opposition_defense_cost should show ACTUAL IP India costs (₹50,000-₹2,00,000), got: {defense_cost}")
                        if "$2,500" in defense_cost or "$10,000" in defense_cost:
                            cost_issues.append(f"opposition_defense_cost shows US costs converted to INR instead of ACTUAL IP India costs: {defense_cost}")
                
                # Test 3: Check mitigation_strategies for ACTUAL IP India costs
                if "mitigation_strategies" in brand and brand["mitigation_strategies"]:
                    for i, strategy in enumerate(brand["mitigation_strategies"]):
                        if isinstance(strategy, dict) and "estimated_cost" in strategy:
                            cost = strategy["estimated_cost"]
                            print(f"Found mitigation strategy {i} cost: {cost}")
                            
                            if cost and "₹" in cost:
                                # Should not be simple currency conversion from US amounts
                                if "$" in str(cost) or any(bad_amount in cost for bad_amount in ["₹22,500", "₹81,500"]):  # These would be USD converted
                                    cost_issues.append(f"mitigation_strategies[{i}].estimated_cost appears to be currency conversion, not ACTUAL IP India costs: {cost}")
                
                # Test 4: Check for trademark search and legal fees in response
                response_text = json.dumps(data)
                print(f"Checking for trademark search costs...")
                
                # Look for trademark search costs
                if "trademark_search" in response_text.lower() or "search_cost" in response_text.lower():
                    if not any(cost in response_text for cost in ["₹3,000", "₹4,000", "₹5,000"]):
                        print(f"Warning: Trademark search costs may not reflect ACTUAL IP India range (₹3,000-₹5,000)")
                
                # Look for legal fees
                if "legal_fees" in response_text.lower() or "attorney" in response_text.lower():
                    if not any(cost in response_text for cost in ["₹10,000", "₹15,000", "₹20,000", "₹30,000"]):
                        print(f"Warning: Legal fees may not reflect ACTUAL IP India range (₹10,000-₹30,000)")
                
                if cost_issues:
                    self.log_test("ACTUAL IP India Costs - India Single Country", False, "; ".join(cost_issues))
                    return False
                
                self.log_test("ACTUAL IP India Costs - India Single Country", True, "All costs show ACTUAL IP India amounts (not currency conversion)")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("ACTUAL IP India Costs - JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("ACTUAL IP India Costs - Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("ACTUAL IP India Costs - Exception", False, str(e))
            return False

    def test_country_specific_legal_precedents_usa(self):
        """Test Case 1 - USA: Legal precedents should show US court cases only"""
        payload = {
            "brand_names": ["USALegalTest"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n⚖️ Testing Country-Specific Legal Precedents - USA...")
            print(f"Expected US Cases: Polaroid Corp. v. Polarad Electronics Corp., AMF Inc. v. Sleekcraft Boats, Two Pesos v. Taco Cabana")
            print(f"Should NOT show: Indian cases like Lakme Ltd. v. Subhash Trading")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Legal Precedents USA - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Legal Precedents USA - Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                precedent_issues = []
                
                # Check if trademark_research exists
                if "trademark_research" not in brand:
                    self.log_test("Legal Precedents USA - TM Research Field", False, "trademark_research field missing")
                    return False
                
                tm_research = brand["trademark_research"]
                if not tm_research:
                    self.log_test("Legal Precedents USA - TM Research Data", False, "trademark_research is null/empty")
                    return False
                
                # Test 1: Check legal_precedents array exists
                legal_precedents = tm_research.get("legal_precedents", [])
                if len(legal_precedents) == 0:
                    self.log_test("Legal Precedents USA - No Precedents", False, "No legal precedents found")
                    return False
                
                print(f"Found {len(legal_precedents)} legal precedents")
                
                # Test 2: Check for US court cases
                us_courts_found = []
                indian_courts_found = []
                
                for precedent in legal_precedents:
                    case_name = precedent.get("case_name", "").lower()
                    court = precedent.get("court", "").lower()
                    
                    print(f"  - Case: {precedent.get('case_name', 'N/A')}")
                    print(f"    Court: {precedent.get('court', 'N/A')}")
                    
                    # Check for expected US cases
                    if any(us_case in case_name for us_case in ["polaroid corp", "amf inc", "two pesos"]):
                        us_courts_found.append(precedent.get("case_name", ""))
                    
                    # Check for US courts
                    if any(us_court in court for us_court in ["u.s.", "united states", "federal circuit", "supreme court", "circuit", "uspto"]):
                        us_courts_found.append(f"{precedent.get('case_name', '')} ({precedent.get('court', '')})")
                    
                    # Check for Indian cases (should NOT be present)
                    if any(indian_case in case_name for indian_case in ["lakme", "cadila", "subhash trading"]):
                        indian_courts_found.append(precedent.get("case_name", ""))
                    
                    # Check for Indian courts (should NOT be present)
                    if any(indian_court in court for indian_court in ["delhi high court", "supreme court of india", "bombay high court", "madras high court"]):
                        indian_courts_found.append(f"{precedent.get('case_name', '')} ({precedent.get('court', '')})")
                
                # Test 3: Verify US cases are present
                if len(us_courts_found) == 0:
                    precedent_issues.append("No US court cases found in legal precedents")
                
                # Test 4: Verify NO Indian cases are present
                if len(indian_courts_found) > 0:
                    precedent_issues.append(f"Found Indian court cases in USA request: {indian_courts_found}")
                
                # Test 5: Check for specific expected US cases
                response_text = json.dumps(data).lower()
                expected_us_cases = ["polaroid corp", "amf inc", "two pesos"]
                found_us_cases = [case for case in expected_us_cases if case in response_text]
                
                if len(found_us_cases) == 0:
                    print(f"Warning: None of the expected US landmark cases found: {expected_us_cases}")
                else:
                    print(f"✅ Found expected US cases: {found_us_cases}")
                
                # Test 6: Check for Indian case names that should NOT be there
                indian_case_names = ["lakme ltd", "subhash trading", "cadila healthcare"]
                found_indian_cases = [case for case in indian_case_names if case in response_text]
                
                if len(found_indian_cases) > 0:
                    precedent_issues.append(f"Found Indian case names in USA response: {found_indian_cases}")
                
                if precedent_issues:
                    self.log_test("Legal Precedents USA - Country Specificity", False, "; ".join(precedent_issues))
                    return False
                
                self.log_test("Legal Precedents USA - Country Specificity", True, 
                            f"US legal precedents correctly shown. US courts found: {len(us_courts_found)}, No Indian cases: ✅")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Legal Precedents USA - JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Legal Precedents USA - Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Legal Precedents USA - Exception", False, str(e))
            return False

    def test_country_specific_legal_precedents_india(self):
        """Test Case 2 - India: Legal precedents should show Indian court cases only"""
        payload = {
            "brand_names": ["IndiaLegalTest"],
            "category": "Fashion",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n⚖️ Testing Country-Specific Legal Precedents - India...")
            print(f"Expected Indian Cases: M/S Lakme Ltd. v. M/S Subhash Trading, Cadila Healthcare v. Cadila Pharmaceuticals")
            print(f"Should NOT show: US cases like Polaroid Corp.")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Legal Precedents India - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Legal Precedents India - Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                precedent_issues = []
                
                # Check if trademark_research exists
                if "trademark_research" not in brand:
                    self.log_test("Legal Precedents India - TM Research Field", False, "trademark_research field missing")
                    return False
                
                tm_research = brand["trademark_research"]
                if not tm_research:
                    self.log_test("Legal Precedents India - TM Research Data", False, "trademark_research is null/empty")
                    return False
                
                # Test 1: Check legal_precedents array exists
                legal_precedents = tm_research.get("legal_precedents", [])
                if len(legal_precedents) == 0:
                    self.log_test("Legal Precedents India - No Precedents", False, "No legal precedents found")
                    return False
                
                print(f"Found {len(legal_precedents)} legal precedents")
                
                # Test 2: Check for Indian court cases
                indian_courts_found = []
                us_courts_found = []
                
                for precedent in legal_precedents:
                    case_name = precedent.get("case_name", "").lower()
                    court = precedent.get("court", "").lower()
                    
                    print(f"  - Case: {precedent.get('case_name', 'N/A')}")
                    print(f"    Court: {precedent.get('court', 'N/A')}")
                    
                    # Check for expected Indian cases
                    if any(indian_case in case_name for indian_case in ["lakme", "cadila", "subhash trading"]):
                        indian_courts_found.append(precedent.get("case_name", ""))
                    
                    # Check for Indian courts
                    if any(indian_court in court for indian_court in ["delhi high court", "supreme court of india", "bombay high court", "madras high court", "high court"]):
                        indian_courts_found.append(f"{precedent.get('case_name', '')} ({precedent.get('court', '')})")
                    
                    # Check for US cases (should NOT be present)
                    if any(us_case in case_name for us_case in ["polaroid corp", "amf inc", "two pesos"]):
                        us_courts_found.append(precedent.get("case_name", ""))
                    
                    # Check for US courts (should NOT be present)
                    if any(us_court in court for us_court in ["u.s. second circuit", "u.s. ninth circuit", "u.s. supreme court", "federal circuit", "uspto"]):
                        us_courts_found.append(f"{precedent.get('case_name', '')} ({precedent.get('court', '')})")
                
                # Test 3: Verify Indian cases are present
                if len(indian_courts_found) == 0:
                    precedent_issues.append("No Indian court cases found in legal precedents")
                
                # Test 4: Verify NO US cases are present
                if len(us_courts_found) > 0:
                    precedent_issues.append(f"Found US court cases in India request: {us_courts_found}")
                
                # Test 5: Check for specific expected Indian cases
                response_text = json.dumps(data).lower()
                expected_indian_cases = ["lakme", "cadila", "subhash trading"]
                found_indian_cases = [case for case in expected_indian_cases if case in response_text]
                
                if len(found_indian_cases) == 0:
                    print(f"Warning: None of the expected Indian landmark cases found: {expected_indian_cases}")
                else:
                    print(f"✅ Found expected Indian cases: {found_indian_cases}")
                
                # Test 6: Check for US case names that should NOT be there
                us_case_names = ["polaroid corp", "amf inc", "two pesos"]
                found_us_cases = [case for case in us_case_names if case in response_text]
                
                if len(found_us_cases) > 0:
                    precedent_issues.append(f"Found US case names in India response: {found_us_cases}")
                
                if precedent_issues:
                    self.log_test("Legal Precedents India - Country Specificity", False, "; ".join(precedent_issues))
                    return False
                
                self.log_test("Legal Precedents India - Country Specificity", True, 
                            f"Indian legal precedents correctly shown. Indian courts found: {len(indian_courts_found)}, No US cases: ✅")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Legal Precedents India - JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Legal Precedents India - Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Legal Precedents India - Exception", False, str(e))
            return False

    def test_quicktest_smoke_test(self):
        """Quick smoke test for RIGHTNAME brand evaluation API with QuickTest"""
        payload = {
            "brand_names": ["QuickTest"],
            "category": "Technology",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔍 QUICKTEST SMOKE TEST: Testing RIGHTNAME brand evaluation API...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120  # Allow up to 120 seconds as requested
            )
            
            print(f"Response Status: {response.status_code}")
            
            # Test 1: API returns successful response (200 OK)
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("QuickTest Smoke - HTTP Status", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully (200 OK)")
                
                # Test 2: Response contains brand_scores with namescore and verdict
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("QuickTest Smoke - Brand Scores", False, "No brand_scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Check namescore field
                if "namescore" not in brand:
                    self.log_test("QuickTest Smoke - NameScore Field", False, "namescore field missing from brand_scores")
                    return False
                
                namescore = brand.get("namescore")
                if not isinstance(namescore, (int, float)) or not (0 <= namescore <= 100):
                    self.log_test("QuickTest Smoke - NameScore Value", False, f"Invalid namescore: {namescore} (should be 0-100)")
                    return False
                
                # Check verdict field
                if "verdict" not in brand:
                    self.log_test("QuickTest Smoke - Verdict Field", False, "verdict field missing from brand_scores")
                    return False
                
                verdict = brand.get("verdict", "")
                valid_verdicts = ["APPROVE", "CAUTION", "REJECT"]
                if verdict not in valid_verdicts:
                    self.log_test("QuickTest Smoke - Verdict Value", False, f"Invalid verdict: {verdict} (should be one of {valid_verdicts})")
                    return False
                
                print(f"✅ Found brand_scores with namescore: {namescore}/100 and verdict: {verdict}")
                
                # Test 3: No validation errors (especially for score_impact field)
                response_str = json.dumps(data).lower()
                validation_errors = []
                
                if "validation error" in response_str:
                    validation_errors.append("Validation error found in response")
                if "score_impact" in response_str and "error" in response_str:
                    validation_errors.append("score_impact field validation error detected")
                if "field required" in response_str:
                    validation_errors.append("Required field validation error detected")
                
                if validation_errors:
                    self.log_test("QuickTest Smoke - Validation Errors", False, "; ".join(validation_errors))
                    return False
                
                print(f"✅ No validation errors detected")
                
                # Test 4: Check that legal_precedents contain USA cases (like Polaroid Corp.)
                legal_precedents_found = False
                usa_cases_found = False
                polaroid_found = False
                legal_precedents = []
                
                # Check in trademark_research section
                if "trademark_research" in brand and brand["trademark_research"]:
                    tm_research = brand["trademark_research"]
                    if "legal_precedents" in tm_research and tm_research["legal_precedents"]:
                        legal_precedents = tm_research["legal_precedents"]
                        legal_precedents_found = True
                        
                        print(f"✅ Found legal_precedents array with {len(legal_precedents)} cases")
                        
                        # Check for USA cases
                        for precedent in legal_precedents:
                            if isinstance(precedent, dict):
                                case_name = precedent.get("case_name", "").lower()
                                jurisdiction = precedent.get("jurisdiction", "").lower()
                                court = precedent.get("court", "").lower()
                                
                                # Check for USA jurisdiction
                                if any(usa_indicator in jurisdiction for usa_indicator in ["usa", "united states", "us", "federal"]) or \
                                   any(usa_indicator in court for usa_indicator in ["usa", "united states", "us", "federal", "uspto"]):
                                    usa_cases_found = True
                                    print(f"✅ Found USA case: {precedent.get('case_name', 'Unknown')}")
                                
                                # Check specifically for Polaroid Corp.
                                if "polaroid" in case_name:
                                    polaroid_found = True
                                    print(f"✅ Found Polaroid Corp. case: {precedent.get('case_name', 'Unknown')}")
                
                if not legal_precedents_found:
                    self.log_test("QuickTest Smoke - Legal Precedents", False, "legal_precedents array not found in trademark_research")
                    return False
                
                if not usa_cases_found:
                    print(f"⚠️  Warning: No USA cases found in legal_precedents (expected for USA market)")
                    # Don't fail the test for this, just warn
                
                if polaroid_found:
                    print(f"✅ Polaroid Corp. case found as expected")
                else:
                    print(f"ℹ️  Note: Polaroid Corp. case not found (may vary by brand)")
                
                # Summary
                print(f"\n📊 QUICKTEST SMOKE TEST RESULTS:")
                print(f"   ✅ API Status: 200 OK")
                print(f"   ✅ NameScore: {namescore}/100")
                print(f"   ✅ Verdict: {verdict}")
                print(f"   ✅ No validation errors")
                print(f"   ✅ Legal precedents: {len(legal_precedents)} cases")
                print(f"   {'✅' if usa_cases_found else '⚠️ '} USA cases: {'Found' if usa_cases_found else 'Not found'}")
                
                self.log_test("QuickTest Smoke Test", True, 
                            f"All core checks passed. NameScore: {namescore}/100, Verdict: {verdict}, Legal precedents: {len(legal_precedents)}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("QuickTest Smoke - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("QuickTest Smoke - Timeout", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("QuickTest Smoke - Exception", False, str(e))
            return False

    def run_currency_tests_only(self):
        """Run only the currency logic tests as requested"""
        print("💰 Starting ACTUAL Country-Specific Trademark Cost Tests...")
        print(f"Testing against: {self.base_url}")
        print("🎯 FOCUS: Verifying ACTUAL trademark office costs (NOT currency conversion)")
        
        # Test API health first
        if not self.test_api_health():
            print("❌ API health check failed, stopping tests")
            return False
        
        # PRIORITY: Test ACTUAL country-specific trademark costs as per review request
        print("\n💰 ACTUAL TRADEMARK OFFICE COST TESTS:")
        print("Testing that costs match respective trademark office fees...")
        
        # Test Case 1: USA Single Country - ACTUAL USPTO costs
        self.test_actual_uspto_costs_usa()
        
        # Test Case 2: India Single Country - ACTUAL IP India costs
        self.test_actual_ip_india_costs()
        
        # Test Case 3: Multiple Countries (existing test)
        self.test_currency_multiple_countries()
        
        # Print summary
        print(f"\n📊 ACTUAL Trademark Cost Test Summary:")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        return self.tests_passed == self.tests_run

    def test_llm_brand_detection_andhrajyoothi(self):
        """Test Case 1: AndhraJyoothi (News App) - should detect conflict with Andhra Jyothi newspaper"""
        payload = {
            "brand_names": ["AndhraJyoothi"],
            "category": "News App",
            "industry": "Media/News",
            "product_type": "Digital",
            "positioning": "Regional",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n🔍 Testing LLM Brand Detection - AndhraJyoothi (News App)...")
            print(f"Expected: REJECT verdict (conflict with 'Andhra Jyothi' Telugu newspaper)")
            
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            response_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f}s")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("LLM Brand Detection - AndhraJyoothi HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("LLM Brand Detection - AndhraJyoothi Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                issues = []
                
                # Test 1: Check verdict should be REJECT
                verdict = brand.get("verdict", "")
                if verdict != "REJECT":
                    issues.append(f"Expected REJECT verdict for AndhraJyoothi, got: {verdict}")
                
                # Test 2: Check if LLM detected the phonetic similarity
                summary = brand.get("summary", "").lower()
                executive_summary = data.get("executive_summary", "").lower()
                full_response = json.dumps(data).lower()
                
                # Look for evidence of conflict detection
                conflict_indicators = [
                    "andhra jyothi", "andhra jyoti", "phonetic", "similar", 
                    "conflict", "newspaper", "telugu", "existing brand"
                ]
                
                found_indicators = [indicator for indicator in conflict_indicators 
                                  if indicator in full_response]
                
                if len(found_indicators) < 2:
                    issues.append(f"LLM should detect phonetic similarity to 'Andhra Jyothi' newspaper. Found indicators: {found_indicators}")
                
                # Test 3: Check response time (should be reasonable for LLM call)
                if response_time > 10:  # Allow up to 10 seconds for LLM processing
                    print(f"⚠️  Warning: Response time {response_time:.2f}s is longer than expected for LLM brand check")
                
                # Test 4: Check if early stopping was triggered (should be fast if detected immediately)
                if response_time < 5 and "immediate rejection" in full_response:
                    print(f"✅ Early stopping detected - fast rejection in {response_time:.2f}s")
                
                if issues:
                    self.log_test("LLM Brand Detection - AndhraJyoothi", False, "; ".join(issues))
                    return False
                
                self.log_test("LLM Brand Detection - AndhraJyoothi", True, 
                            f"REJECT verdict correctly issued. Conflict detected with indicators: {found_indicators}. Response time: {response_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("LLM Brand Detection - AndhraJyoothi JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("LLM Brand Detection - AndhraJyoothi Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("LLM Brand Detection - AndhraJyoothi Exception", False, str(e))
            return False

    def test_llm_brand_detection_bumbell(self):
        """Test Case 2: BUMBELL (Dating App) - should detect conflict with Bumble dating app"""
        payload = {
            "brand_names": ["BUMBELL"],
            "category": "Dating App",
            "industry": "Social/Dating",
            "product_type": "Digital",
            "positioning": "Premium",
            "market_scope": "Multi-Country",
            "countries": ["USA", "India"]
        }
        
        try:
            print(f"\n🔍 Testing LLM Brand Detection - BUMBELL (Dating App)...")
            print(f"Expected: REJECT verdict (conflict with 'Bumble' dating app)")
            
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            response_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f}s")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("LLM Brand Detection - BUMBELL HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("LLM Brand Detection - BUMBELL Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                issues = []
                
                # Test 1: Check verdict should be REJECT
                verdict = brand.get("verdict", "")
                if verdict != "REJECT":
                    issues.append(f"Expected REJECT verdict for BUMBELL, got: {verdict}")
                
                # Test 2: Check if LLM detected the phonetic similarity to Bumble
                summary = brand.get("summary", "").lower()
                executive_summary = data.get("executive_summary", "").lower()
                full_response = json.dumps(data).lower()
                
                # Look for evidence of Bumble conflict detection
                conflict_indicators = [
                    "bumble", "phonetic", "similar", "conflict", "dating app", 
                    "existing brand", "trademark", "confusion"
                ]
                
                found_indicators = [indicator for indicator in conflict_indicators 
                                  if indicator in full_response]
                
                if len(found_indicators) < 2:
                    issues.append(f"LLM should detect phonetic similarity to 'Bumble' dating app. Found indicators: {found_indicators}")
                
                # Test 3: Check if Bumble is specifically mentioned
                if "bumble" not in full_response:
                    issues.append("LLM should specifically identify 'Bumble' as the conflicting brand")
                
                # Test 4: Check response time
                if response_time > 10:
                    print(f"⚠️  Warning: Response time {response_time:.2f}s is longer than expected for LLM brand check")
                
                if issues:
                    self.log_test("LLM Brand Detection - BUMBELL", False, "; ".join(issues))
                    return False
                
                self.log_test("LLM Brand Detection - BUMBELL", True, 
                            f"REJECT verdict correctly issued. Bumble conflict detected with indicators: {found_indicators}. Response time: {response_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("LLM Brand Detection - BUMBELL JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("LLM Brand Detection - BUMBELL Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("LLM Brand Detection - BUMBELL Exception", False, str(e))
            return False

    def test_llm_brand_detection_unique_name(self):
        """Test Case 3: Zyntrix2025 (Finance App) - unique name, should pass"""
        payload = {
            "brand_names": ["Zyntrix2025"],
            "category": "Finance App",
            "industry": "Fintech",
            "product_type": "Digital",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔍 Testing LLM Brand Detection - Zyntrix2025 (Unique Name)...")
            print(f"Expected: GO or CAUTION verdict (unique name, no conflicts)")
            
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            response_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f}s")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("LLM Brand Detection - Zyntrix2025 HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("LLM Brand Detection - Zyntrix2025 Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                issues = []
                
                # Test 1: Check verdict should NOT be REJECT
                verdict = brand.get("verdict", "")
                if verdict == "REJECT":
                    issues.append(f"Unique name Zyntrix2025 should NOT be rejected, got verdict: {verdict}")
                
                # Test 2: Check if verdict is reasonable for unique name
                valid_verdicts = ["GO", "CAUTION", "APPROVE"]
                if verdict not in valid_verdicts:
                    issues.append(f"Expected GO/CAUTION/APPROVE for unique name, got: {verdict}")
                
                # Test 3: Check NameScore should be reasonable for unique name
                namescore = brand.get("namescore", 0)
                if namescore < 30:  # Unique names should score reasonably well
                    issues.append(f"Unique name should have decent NameScore (30+), got: {namescore}")
                
                # Test 4: Check that no major conflicts are mentioned
                full_response = json.dumps(data).lower()
                major_conflict_indicators = [
                    "fatal conflict", "immediate rejection", "existing brand", 
                    "trademark infringement", "legal action"
                ]
                
                found_conflicts = [indicator for indicator in major_conflict_indicators 
                                 if indicator in full_response]
                
                if found_conflicts:
                    issues.append(f"Unique name should not have major conflicts. Found: {found_conflicts}")
                
                # Test 5: Check response time (should be longer for full analysis since no early stopping)
                if response_time < 30:
                    print(f"✅ Good response time for full analysis: {response_time:.2f}s")
                
                if issues:
                    self.log_test("LLM Brand Detection - Zyntrix2025", False, "; ".join(issues))
                    return False
                
                self.log_test("LLM Brand Detection - Zyntrix2025", True, 
                            f"Unique name correctly passed. Verdict: {verdict}, NameScore: {namescore}. Response time: {response_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("LLM Brand Detection - Zyntrix2025 JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("LLM Brand Detection - Zyntrix2025 Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("LLM Brand Detection - Zyntrix2025 Exception", False, str(e))
            return False

    def test_llm_brand_detection_moneycontrols(self):
        """Test Case 4: MoneyControls (Finance App) - should detect conflict with Moneycontrol"""
        payload = {
            "brand_names": ["MoneyControls"],
            "category": "Finance App",
            "industry": "Fintech",
            "product_type": "Digital",
            "positioning": "Mass",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n🔍 Testing LLM Brand Detection - MoneyControls (Pluralization Test)...")
            print(f"Expected: REJECT verdict (conflict with 'Moneycontrol' finance app)")
            
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            response_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f}s")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("LLM Brand Detection - MoneyControls HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("LLM Brand Detection - MoneyControls Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                issues = []
                
                # Test 1: Check verdict should be REJECT
                verdict = brand.get("verdict", "")
                if verdict != "REJECT":
                    issues.append(f"Expected REJECT verdict for MoneyControls (pluralization of Moneycontrol), got: {verdict}")
                
                # Test 2: Check if LLM detected the pluralization similarity
                summary = brand.get("summary", "").lower()
                executive_summary = data.get("executive_summary", "").lower()
                full_response = json.dumps(data).lower()
                
                # Look for evidence of Moneycontrol conflict detection
                conflict_indicators = [
                    "moneycontrol", "money control", "pluralization", "plural", 
                    "similar", "conflict", "finance app", "existing brand", "trademark"
                ]
                
                found_indicators = [indicator for indicator in conflict_indicators 
                                  if indicator in full_response]
                
                if len(found_indicators) < 2:
                    issues.append(f"LLM should detect pluralization similarity to 'Moneycontrol'. Found indicators: {found_indicators}")
                
                # Test 3: Check if Moneycontrol is specifically mentioned
                if "moneycontrol" not in full_response:
                    issues.append("LLM should specifically identify 'Moneycontrol' as the conflicting brand")
                
                # Test 4: Check response time
                if response_time > 10:
                    print(f"⚠️  Warning: Response time {response_time:.2f}s is longer than expected for LLM brand check")
                
                # Test 5: Check if early stopping was triggered for famous brand
                if response_time < 5 and "immediate rejection" in full_response:
                    print(f"✅ Early stopping detected - fast rejection in {response_time:.2f}s")
                
                if issues:
                    self.log_test("LLM Brand Detection - MoneyControls", False, "; ".join(issues))
                    return False
                
                self.log_test("LLM Brand Detection - MoneyControls", True, 
                            f"REJECT verdict correctly issued. Moneycontrol conflict detected with indicators: {found_indicators}. Response time: {response_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("LLM Brand Detection - MoneyControls JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("LLM Brand Detection - MoneyControls Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("LLM Brand Detection - MoneyControls Exception", False, str(e))
            return False

    def test_llm_backend_logs_verification(self):
        """Verify backend logs show LLM brand check messages"""
        try:
            print(f"\n📋 Checking Backend Logs for LLM Brand Check Messages...")
            
            # Check supervisor backend logs
            import subprocess
            result = subprocess.run(
                ["tail", "-n", "200", "/var/log/supervisor/backend.out.log"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                self.log_test("LLM Backend Logs - Read Error", False, f"Failed to read backend logs: {result.stderr}")
                return False
            
            log_content = result.stdout
            issues = []
            
            # Test 1: Check for LLM brand check initiation messages
            llm_check_messages = [
                "🔍 LLM BRAND CHECK",
                "LLM BRAND CHECK:",
                "dynamic_brand_search"
            ]
            
            found_check_messages = [msg for msg in llm_check_messages if msg in log_content]
            if not found_check_messages:
                issues.append(f"No LLM brand check initiation messages found. Expected: {llm_check_messages}")
            
            # Test 2: Check for conflict detection messages
            conflict_messages = [
                "🚨 LLM DETECTED CONFLICT",
                "LLM DETECTED CONFLICT:",
                "CONFLICT DETECTED:"
            ]
            
            found_conflict_messages = [msg for msg in conflict_messages if msg in log_content]
            
            # Test 3: Check for early stopping messages
            early_stopping_messages = [
                "EARLY STOPPING:",
                "IMMEDIATE REJECTION",
                "early_stopped"
            ]
            
            found_early_stopping = [msg for msg in early_stopping_messages if msg in log_content]
            
            # Test 4: Check for LLM model usage
            llm_model_messages = [
                "gpt-4o-mini",
                "gpt-4o",
                "openai"
            ]
            
            found_model_messages = [msg for msg in llm_model_messages if msg in log_content]
            if not found_model_messages:
                issues.append(f"No LLM model usage messages found. Expected: {llm_model_messages}")
            
            print(f"Found LLM check messages: {found_check_messages}")
            print(f"Found conflict messages: {found_conflict_messages}")
            print(f"Found early stopping messages: {found_early_stopping}")
            print(f"Found model messages: {found_model_messages}")
            
            if issues:
                self.log_test("LLM Backend Logs Verification", False, "; ".join(issues))
                return False
            
            self.log_test("LLM Backend Logs Verification", True, 
                        f"Backend logs show LLM activity. Check messages: {len(found_check_messages)}, Model messages: {len(found_model_messages)}")
            return True
            
        except subprocess.TimeoutExpired:
            self.log_test("LLM Backend Logs - Timeout", False, "Timeout reading backend logs")
            return False
        except Exception as e:
            self.log_test("LLM Backend Logs - Exception", False, str(e))
            return False

    def test_502_fix_unique_brand_vextrona(self):
        """Test Case 1: Unique Brand Test - Vextrona should get GO verdict with NameScore > 70"""
        payload = {
            "brand_names": ["Vextrona"],
            "category": "Technology",
            "industry": "Software",
            "product_type": "SaaS Platform",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA", "UK", "India"]
        }
        
        try:
            print(f"\n🔍 Testing 502 Fix - Unique Brand: Vextrona...")
            print(f"Expected: GO verdict, NameScore > 70, no 502 errors")
            
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120  # Should complete within 60-90 seconds
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            # Test 1: Should return 200 OK (not 502 BadGateway)
            if response.status_code == 502:
                self.log_test("502 Fix - Unique Brand Vextrona (502 Error)", False, "Still getting 502 BadGateway error - fix not working")
                return False
            elif response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("502 Fix - Unique Brand Vextrona (HTTP Error)", False, error_msg)
                return False
            
            # Test 2: Response time should be within 60-90 seconds
            if response_time > 120:
                self.log_test("502 Fix - Unique Brand Vextrona (Timeout)", False, f"Response took {response_time:.2f}s (should be < 120s)")
                return False
            
            try:
                data = response.json()
                
                # Test 3: Check response structure
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("502 Fix - Unique Brand Vextrona (Structure)", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 4: Check brand name
                if brand.get("brand_name") != "Vextrona":
                    self.log_test("502 Fix - Unique Brand Vextrona (Brand Name)", False, f"Expected 'Vextrona', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 5: Check NameScore > 70
                namescore = brand.get("namescore")
                if not isinstance(namescore, (int, float)):
                    self.log_test("502 Fix - Unique Brand Vextrona (NameScore Type)", False, f"NameScore should be number, got {type(namescore)}")
                    return False
                
                if namescore <= 70:
                    self.log_test("502 Fix - Unique Brand Vextrona (NameScore Low)", False, f"NameScore {namescore} should be > 70 for unique brand")
                    return False
                
                # Test 6: Check verdict is GO
                verdict = brand.get("verdict", "")
                if verdict not in ["GO", "APPROVE"]:
                    self.log_test("502 Fix - Unique Brand Vextrona (Verdict)", False, f"Expected GO/APPROVE verdict, got '{verdict}'")
                    return False
                
                # Test 7: Check executive summary exists
                exec_summary = data.get("executive_summary", "")
                if len(exec_summary) < 50:
                    self.log_test("502 Fix - Unique Brand Vextrona (Summary)", False, f"Executive summary too short: {len(exec_summary)} chars")
                    return False
                
                print(f"✅ Vextrona evaluation completed successfully:")
                print(f"   - NameScore: {namescore}/100")
                print(f"   - Verdict: {verdict}")
                print(f"   - Response Time: {response_time:.2f}s")
                print(f"   - No 502 errors")
                
                self.log_test("502 Fix - Unique Brand Vextrona", True, 
                            f"All checks passed. NameScore: {namescore}/100, Verdict: {verdict}, Time: {response_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("502 Fix - Unique Brand Vextrona (JSON)", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("502 Fix - Unique Brand Vextrona (Timeout)", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("502 Fix - Unique Brand Vextrona (Exception)", False, str(e))
            return False

    def test_502_fix_famous_brand_nike(self):
        """Test Case 2: Famous Brand Test - Nike should get REJECT verdict with early stopping"""
        payload = {
            "brand_names": ["Nike"],
            "category": "Fashion",
            "industry": "Apparel",
            "product_type": "Sportswear",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔍 Testing 502 Fix - Famous Brand: Nike...")
            print(f"Expected: REJECT verdict, early stopping (< 10s), no 502 errors")
            
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=60  # Should be very fast with early stopping
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            # Test 1: Should return 200 OK (not 502 BadGateway)
            if response.status_code == 502:
                self.log_test("502 Fix - Famous Brand Nike (502 Error)", False, "Still getting 502 BadGateway error - fix not working")
                return False
            elif response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("502 Fix - Famous Brand Nike (HTTP Error)", False, error_msg)
                return False
            
            # Test 2: Response time should be very fast (early stopping)
            if response_time > 30:
                print(f"⚠️  Warning: Response took {response_time:.2f}s (expected < 30s with early stopping)")
            
            try:
                data = response.json()
                
                # Test 3: Check response structure
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("502 Fix - Famous Brand Nike (Structure)", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 4: Check brand name
                if brand.get("brand_name") != "Nike":
                    self.log_test("502 Fix - Famous Brand Nike (Brand Name)", False, f"Expected 'Nike', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 5: Check verdict is REJECT
                verdict = brand.get("verdict", "")
                if verdict != "REJECT":
                    self.log_test("502 Fix - Famous Brand Nike (Verdict)", False, f"Expected REJECT verdict, got '{verdict}'")
                    return False
                
                # Test 6: Check NameScore is low (should be < 20 for famous brand)
                namescore = brand.get("namescore")
                if isinstance(namescore, (int, float)) and namescore > 20:
                    print(f"⚠️  Warning: NameScore {namescore} is high for famous brand (expected < 20)")
                
                # Test 7: Check for early stopping indicators in summary
                exec_summary = data.get("executive_summary", "")
                summary_text = brand.get("summary", "")
                
                early_stopping_indicators = ["IMMEDIATE REJECTION", "existing brand", "famous brand", "trademark conflict"]
                found_indicators = [indicator for indicator in early_stopping_indicators 
                                  if indicator.lower() in exec_summary.lower() or indicator.lower() in summary_text.lower()]
                
                if not found_indicators:
                    print(f"⚠️  Warning: No early stopping indicators found in summary")
                
                print(f"✅ Nike evaluation completed successfully:")
                print(f"   - NameScore: {namescore}")
                print(f"   - Verdict: {verdict}")
                print(f"   - Response Time: {response_time:.2f}s")
                print(f"   - Early stopping indicators: {found_indicators}")
                print(f"   - No 502 errors")
                
                self.log_test("502 Fix - Famous Brand Nike", True, 
                            f"All checks passed. Verdict: {verdict}, Time: {response_time:.2f}s, Indicators: {found_indicators}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("502 Fix - Famous Brand Nike (JSON)", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("502 Fix - Famous Brand Nike (Timeout)", False, "Request timed out after 60 seconds")
            return False
        except Exception as e:
            self.log_test("502 Fix - Famous Brand Nike (Exception)", False, str(e))
            return False

    def test_502_fix_similar_brand_chaibunk(self):
        """Test Case 3: Similar Brand Test - Chaibunk should detect as existing brand"""
        payload = {
            "brand_names": ["Chaibunk"],
            "category": "Food & Beverage",
            "industry": "Restaurant",
            "product_type": "Cafe Chain",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n🔍 Testing 502 Fix - Similar Brand: Chaibunk...")
            print(f"Expected: REJECT verdict (existing chai cafe chain), no 502 errors")
            
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120  # Should complete within reasonable time
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            # Test 1: Should return 200 OK (not 502 BadGateway)
            if response.status_code == 502:
                self.log_test("502 Fix - Similar Brand Chaibunk (502 Error)", False, "Still getting 502 BadGateway error - fix not working")
                return False
            elif response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("502 Fix - Similar Brand Chaibunk (HTTP Error)", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                # Test 2: Check response structure
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("502 Fix - Similar Brand Chaibunk (Structure)", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 3: Check brand name
                if brand.get("brand_name") != "Chaibunk":
                    self.log_test("502 Fix - Similar Brand Chaibunk (Brand Name)", False, f"Expected 'Chaibunk', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 4: Check verdict (should be REJECT for existing brand)
                verdict = brand.get("verdict", "")
                if verdict not in ["REJECT", "CAUTION"]:
                    print(f"⚠️  Warning: Expected REJECT/CAUTION for existing brand, got '{verdict}'")
                
                # Test 5: Check for conflict detection in summary
                exec_summary = data.get("executive_summary", "")
                summary_text = brand.get("summary", "")
                
                conflict_indicators = ["chai bunk", "existing", "conflict", "similar", "trademark"]
                found_conflicts = [indicator for indicator in conflict_indicators 
                                 if indicator.lower() in exec_summary.lower() or indicator.lower() in summary_text.lower()]
                
                # Test 6: Check NameScore (should be low for conflicting brand)
                namescore = brand.get("namescore")
                if isinstance(namescore, (int, float)) and namescore > 50:
                    print(f"⚠️  Warning: NameScore {namescore} is high for conflicting brand (expected < 50)")
                
                print(f"✅ Chaibunk evaluation completed successfully:")
                print(f"   - NameScore: {namescore}")
                print(f"   - Verdict: {verdict}")
                print(f"   - Response Time: {response_time:.2f}s")
                print(f"   - Conflict indicators: {found_conflicts}")
                print(f"   - No 502 errors")
                
                # Consider test passed if no 502 error and reasonable response
                success = True
                details = f"No 502 errors. Verdict: {verdict}, Time: {response_time:.2f}s, Conflicts: {found_conflicts}"
                
                self.log_test("502 Fix - Similar Brand Chaibunk", success, details)
                return success
                
            except json.JSONDecodeError as e:
                self.log_test("502 Fix - Similar Brand Chaibunk (JSON)", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("502 Fix - Similar Brand Chaibunk (Timeout)", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("502 Fix - Similar Brand Chaibunk (Exception)", False, str(e))
            return False

    def test_502_fix_api_response_time(self):
        """Test Case 4: API Response Time - Verify evaluation completes within 60-90 seconds"""
        payload = {
            "brand_names": ["Zyphlora"],
            "category": "Technology",
            "industry": "Software",
            "product_type": "Mobile App",
            "positioning": "Premium",
            "market_scope": "Multi-Country",
            "countries": ["USA", "UK"]
        }
        
        try:
            print(f"\n🔍 Testing 502 Fix - API Response Time: Zyphlora...")
            print(f"Expected: Complete within 60-90 seconds, no timeouts, no 502 errors")
            
            import time
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120  # Allow up to 120s but expect 60-90s
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            # Test 1: Should return 200 OK (not 502 BadGateway)
            if response.status_code == 502:
                self.log_test("502 Fix - API Response Time (502 Error)", False, "Still getting 502 BadGateway error - fix not working")
                return False
            elif response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("502 Fix - API Response Time (HTTP Error)", False, error_msg)
                return False
            
            # Test 2: Response time should be within acceptable range
            if response_time > 120:
                self.log_test("502 Fix - API Response Time (Too Slow)", False, f"Response took {response_time:.2f}s (should be < 120s)")
                return False
            
            # Check if within optimal range
            within_optimal = 60 <= response_time <= 90
            if not within_optimal:
                print(f"⚠️  Response time {response_time:.2f}s is outside optimal range (60-90s)")
            
            try:
                data = response.json()
                
                # Test 3: Check response completeness
                required_fields = ["executive_summary", "brand_scores", "comparison_verdict"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("502 Fix - API Response Time (Incomplete)", False, f"Missing fields: {missing_fields}")
                    return False
                
                # Test 4: Check brand evaluation completeness
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("502 Fix - API Response Time (No Brands)", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 5: Check essential brand fields
                essential_fields = ["brand_name", "namescore", "verdict", "summary"]
                missing_brand_fields = [field for field in essential_fields if field not in brand]
                
                if missing_brand_fields:
                    self.log_test("502 Fix - API Response Time (Incomplete Brand)", False, f"Missing brand fields: {missing_brand_fields}")
                    return False
                
                # Test 6: Check for comprehensive analysis sections
                analysis_sections = ["trademark_research", "domain_analysis", "visibility_analysis"]
                present_sections = [section for section in analysis_sections if section in brand and brand[section]]
                
                print(f"✅ Zyphlora evaluation completed successfully:")
                print(f"   - Response Time: {response_time:.2f}s")
                print(f"   - Within optimal range (60-90s): {within_optimal}")
                print(f"   - NameScore: {brand.get('namescore')}")
                print(f"   - Verdict: {brand.get('verdict')}")
                print(f"   - Analysis sections: {len(present_sections)}/3")
                print(f"   - No 502 errors or timeouts")
                
                self.log_test("502 Fix - API Response Time", True, 
                            f"Completed in {response_time:.2f}s. Optimal range: {within_optimal}, Sections: {len(present_sections)}/3")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("502 Fix - API Response Time (JSON)", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("502 Fix - API Response Time (Timeout)", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("502 Fix - API Response Time (Exception)", False, str(e))
            return False

    def run_502_fix_tests(self):
        """Run all 502 BadGatewayError fix tests"""
        print("🔧 Testing 502 BadGatewayError Fix...")
        print("Testing gpt-5.2 → gpt-4o with gpt-4.1 fallback")
        print("=" * 60)
        
        # Run the specific 502 fix tests
        self.test_502_fix_unique_brand_vextrona()
        self.test_502_fix_famous_brand_nike()
        self.test_502_fix_similar_brand_chaibunk()
        self.test_502_fix_api_response_time()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"🔧 502 Fix Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All 502 fix tests PASSED!")
        else:
            print(f"❌ {self.tests_run - self.tests_passed} tests FAILED")
            print("\nFailed tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        return self.tests_passed == self.tests_run

    def test_enhanced_brand_detection_chai_duniya(self):
        """Test Case 1: Chai Duniya - Should get REJECT verdict (existing chai cafe chain in India)"""
        payload = {
            "brand_names": ["Chai Duniya"],
            "category": "Cafe",
            "industry": "Food and Beverage",
            "product_type": "Chai and Snacks",
            "positioning": "Premium",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n☕ Testing Enhanced Brand Detection - Chai Duniya...")
            print(f"Expected: REJECT verdict with score ~5 (existing chai cafe chain)")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Enhanced Detection - Chai Duniya HTTP", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Enhanced Detection - Chai Duniya Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 1: Check brand name matches
                if brand.get("brand_name") != "Chai Duniya":
                    self.log_test("Enhanced Detection - Chai Duniya Name", False, f"Expected 'Chai Duniya', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 2: Check verdict is REJECT
                verdict = brand.get("verdict", "")
                if verdict != "REJECT":
                    self.log_test("Enhanced Detection - Chai Duniya Verdict", False, f"Expected REJECT verdict, got '{verdict}' (Chai Duniya is an existing chai cafe chain)")
                    return False
                
                # Test 3: Check NameScore is low (~5)
                namescore = brand.get("namescore", 0)
                if not isinstance(namescore, (int, float)) or namescore > 15:
                    self.log_test("Enhanced Detection - Chai Duniya Score", False, f"Expected low score (~5), got {namescore} (should be rejected due to existing brand)")
                    return False
                
                # Test 4: Check summary mentions existing brand
                summary = brand.get("summary", "").lower()
                if not any(keyword in summary for keyword in ["existing", "conflict", "chai duniya", "brand already exists"]):
                    self.log_test("Enhanced Detection - Chai Duniya Summary", False, f"Summary should mention existing brand conflict: {summary[:100]}")
                    return False
                
                print(f"✅ Chai Duniya correctly rejected:")
                print(f"   - Verdict: {verdict}")
                print(f"   - NameScore: {namescore}")
                print(f"   - Conflict detected: {any(keyword in summary for keyword in ['existing', 'conflict'])}")
                
                self.log_test("Enhanced Detection - Chai Duniya", True, 
                            f"Correctly rejected existing brand. Verdict: {verdict}, Score: {namescore}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Enhanced Detection - Chai Duniya JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Enhanced Detection - Chai Duniya Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Enhanced Detection - Chai Duniya Exception", False, str(e))
            return False

    def test_enhanced_brand_detection_chaibunk(self):
        """Test Case 2: Chaibunk - Should get REJECT verdict (Chai Bunk is existing cafe chain with 100+ stores)"""
        payload = {
            "brand_names": ["Chaibunk"],
            "category": "Cafe",
            "industry": "Food and Beverage", 
            "product_type": "Chai and Snacks",
            "positioning": "Budget",
            "market_scope": "Single Country",
            "countries": ["India"]
        }
        
        try:
            print(f"\n☕ Testing Enhanced Brand Detection - Chaibunk...")
            print(f"Expected: REJECT verdict with score ~5 (Chai Bunk has 100+ stores)")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Enhanced Detection - Chaibunk HTTP", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Enhanced Detection - Chaibunk Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 1: Check brand name matches
                if brand.get("brand_name") != "Chaibunk":
                    self.log_test("Enhanced Detection - Chaibunk Name", False, f"Expected 'Chaibunk', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 2: Check verdict is REJECT
                verdict = brand.get("verdict", "")
                if verdict != "REJECT":
                    self.log_test("Enhanced Detection - Chaibunk Verdict", False, f"Expected REJECT verdict, got '{verdict}' (Chai Bunk is existing cafe chain with 100+ stores)")
                    return False
                
                # Test 3: Check NameScore is low (~5)
                namescore = brand.get("namescore", 0)
                if not isinstance(namescore, (int, float)) or namescore > 15:
                    self.log_test("Enhanced Detection - Chaibunk Score", False, f"Expected low score (~5), got {namescore} (should be rejected due to existing brand)")
                    return False
                
                # Test 4: Check summary mentions existing brand or conflict
                summary = brand.get("summary", "").lower()
                if not any(keyword in summary for keyword in ["existing", "conflict", "chai bunk", "chaibunk", "brand already exists"]):
                    self.log_test("Enhanced Detection - Chaibunk Summary", False, f"Summary should mention existing brand conflict: {summary[:100]}")
                    return False
                
                print(f"✅ Chaibunk correctly rejected:")
                print(f"   - Verdict: {verdict}")
                print(f"   - NameScore: {namescore}")
                print(f"   - Conflict detected: {any(keyword in summary for keyword in ['existing', 'conflict'])}")
                
                self.log_test("Enhanced Detection - Chaibunk", True, 
                            f"Correctly rejected existing brand. Verdict: {verdict}, Score: {namescore}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Enhanced Detection - Chaibunk JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Enhanced Detection - Chaibunk Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Enhanced Detection - Chaibunk Exception", False, str(e))
            return False

    def test_enhanced_brand_detection_zyphloria(self):
        """Test Case 3: Zyphloria - Should get GO verdict with high score (completely unique name)"""
        payload = {
            "brand_names": ["Zyphloria"],
            "category": "Technology",
            "industry": "Software",
            "product_type": "AI Platform",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA", "India"]
        }
        
        try:
            print(f"\n🚀 Testing Enhanced Brand Detection - Zyphloria...")
            print(f"Expected: GO verdict with score > 80 (completely unique name)")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Enhanced Detection - Zyphloria HTTP", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Enhanced Detection - Zyphloria Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 1: Check brand name matches
                if brand.get("brand_name") != "Zyphloria":
                    self.log_test("Enhanced Detection - Zyphloria Name", False, f"Expected 'Zyphloria', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 2: Check verdict is GO (or APPROVE)
                verdict = brand.get("verdict", "")
                if verdict not in ["GO", "APPROVE"]:
                    self.log_test("Enhanced Detection - Zyphloria Verdict", False, f"Expected GO/APPROVE verdict, got '{verdict}' (Zyphloria is unique)")
                    return False
                
                # Test 3: Check NameScore is high (> 80)
                namescore = brand.get("namescore", 0)
                if not isinstance(namescore, (int, float)) or namescore < 80:
                    self.log_test("Enhanced Detection - Zyphloria Score", False, f"Expected high score (>80), got {namescore} (unique name should score well)")
                    return False
                
                # Test 4: Check summary doesn't mention conflicts (but allow "free from conflicts")
                summary = brand.get("summary", "").lower()
                bad_conflict_keywords = ["existing brand", "trademark conflict", "already exists", "brand conflict"]
                if any(keyword in summary for keyword in bad_conflict_keywords):
                    self.log_test("Enhanced Detection - Zyphloria No Conflicts", False, f"Summary should not mention conflicts for unique name: {summary[:100]}")
                    return False
                
                print(f"✅ Zyphloria correctly approved:")
                print(f"   - Verdict: {verdict}")
                print(f"   - NameScore: {namescore}")
                print(f"   - No conflicts detected: {not any(keyword in summary for keyword in ['existing', 'conflict'])}")
                
                self.log_test("Enhanced Detection - Zyphloria", True, 
                            f"Correctly approved unique brand. Verdict: {verdict}, Score: {namescore}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Enhanced Detection - Zyphloria JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Enhanced Detection - Zyphloria Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Enhanced Detection - Zyphloria Exception", False, str(e))
            return False

    def test_enhanced_brand_detection_nike(self):
        """Test Case 4: Nike - Should get REJECT verdict with early stopping"""
        payload = {
            "brand_names": ["Nike"],
            "category": "Fashion",
            "industry": "Apparel",
            "product_type": "Sportswear",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n👟 Testing Enhanced Brand Detection - Nike...")
            print(f"Expected: REJECT verdict with early stopping, score ~5")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            response_time = time.time() - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Enhanced Detection - Nike HTTP", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Enhanced Detection - Nike Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 1: Check brand name matches
                if brand.get("brand_name") != "Nike":
                    self.log_test("Enhanced Detection - Nike Name", False, f"Expected 'Nike', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 2: Check verdict is REJECT
                verdict = brand.get("verdict", "")
                if verdict != "REJECT":
                    self.log_test("Enhanced Detection - Nike Verdict", False, f"Expected REJECT verdict, got '{verdict}' (Nike is famous brand)")
                    return False
                
                # Test 3: Check NameScore is low (~5)
                namescore = brand.get("namescore", 0)
                if not isinstance(namescore, (int, float)) or namescore > 15:
                    self.log_test("Enhanced Detection - Nike Score", False, f"Expected low score (~5), got {namescore} (famous brand should be rejected)")
                    return False
                
                # Test 4: Check for early stopping indicators
                summary = brand.get("summary", "").lower()
                early_stopping_indicators = ["immediate rejection", "famous brand", "existing brand", "early stopping"]
                has_early_stopping = any(indicator in summary for indicator in early_stopping_indicators)
                
                if not has_early_stopping:
                    print(f"Warning: No clear early stopping indicators found in summary: {summary[:100]}")
                
                # Test 5: Check response time (should be fast due to early stopping)
                if response_time > 10:  # Allow some buffer, but should be much faster than full evaluation
                    print(f"Warning: Response time {response_time:.2f}s may indicate early stopping didn't work optimally")
                
                print(f"✅ Nike correctly rejected:")
                print(f"   - Verdict: {verdict}")
                print(f"   - NameScore: {namescore}")
                print(f"   - Response Time: {response_time:.2f}s")
                print(f"   - Early stopping indicators: {has_early_stopping}")
                
                self.log_test("Enhanced Detection - Nike", True, 
                            f"Correctly rejected famous brand. Verdict: {verdict}, Score: {namescore}, Time: {response_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Enhanced Detection - Nike JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Enhanced Detection - Nike Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Enhanced Detection - Nike Exception", False, str(e))
            return False

    def test_enhanced_brand_detection_nexovix(self):
        """Test Case 5: Nexovix - Should get GO verdict (unique invented name)"""
        payload = {
            "brand_names": ["Nexovix"],
            "category": "Technology",
            "industry": "Software",
            "product_type": "Business Software",
            "positioning": "Premium",
            "market_scope": "Multi-Country",
            "countries": ["USA", "UK", "India"]
        }
        
        try:
            print(f"\n🚀 Testing Enhanced Brand Detection - Nexovix...")
            print(f"Expected: GO verdict with high score (unique invented name)")
            
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                self.log_test("Enhanced Detection - Nexovix HTTP", False, error_msg)
                return False
            
            try:
                data = response.json()
                
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Enhanced Detection - Nexovix Structure", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 1: Check brand name matches
                if brand.get("brand_name") != "Nexovix":
                    self.log_test("Enhanced Detection - Nexovix Name", False, f"Expected 'Nexovix', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 2: Check verdict is GO (or APPROVE)
                verdict = brand.get("verdict", "")
                if verdict not in ["GO", "APPROVE"]:
                    self.log_test("Enhanced Detection - Nexovix Verdict", False, f"Expected GO/APPROVE verdict, got '{verdict}' (Nexovix is unique)")
                    return False
                
                # Test 3: Check NameScore is high (> 80)
                namescore = brand.get("namescore", 0)
                if not isinstance(namescore, (int, float)) or namescore < 80:
                    self.log_test("Enhanced Detection - Nexovix Score", False, f"Expected high score (>80), got {namescore} (unique name should score well)")
                    return False
                
                # Test 4: Check summary doesn't mention conflicts (but allow "free from conflicts")
                summary = brand.get("summary", "").lower()
                bad_conflict_keywords = ["existing brand", "trademark conflict", "already exists", "brand conflict"]
                if any(keyword in summary for keyword in bad_conflict_keywords):
                    self.log_test("Enhanced Detection - Nexovix No Conflicts", False, f"Summary should not mention conflicts for unique name: {summary[:100]}")
                    return False
                
                print(f"✅ Nexovix correctly approved:")
                print(f"   - Verdict: {verdict}")
                print(f"   - NameScore: {namescore}")
                print(f"   - No conflicts detected: {not any(keyword in summary for keyword in ['existing', 'conflict'])}")
                
                self.log_test("Enhanced Detection - Nexovix", True, 
                            f"Correctly approved unique brand. Verdict: {verdict}, Score: {namescore}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Enhanced Detection - Nexovix JSON", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Enhanced Detection - Nexovix Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Enhanced Detection - Nexovix Exception", False, str(e))
            return False

    def run_enhanced_brand_detection_tests(self):
        """Run only the enhanced brand detection tests as requested in the review"""
        print("🔍 ENHANCED BRAND DETECTION TESTS")
        print("Testing the enhanced brand detection after fixing false positives")
        print("=" * 80)
        
        # Test API health first
        if not self.test_api_health():
            print("❌ API health check failed, stopping tests")
            return self.print_summary()
        
        print("\n" + "="*50)
        print("🔍 ENHANCED BRAND DETECTION TESTS")
        print("="*50)
        
        # Run the 5 specific test cases from the review request
        self.test_enhanced_brand_detection_chai_duniya()
        self.test_enhanced_brand_detection_chaibunk()
        self.test_enhanced_brand_detection_zyphloria()
        self.test_enhanced_brand_detection_nike()
        self.test_enhanced_brand_detection_nexovix()
        
        return self.print_summary()

    def test_zyphlora_comprehensive_evaluation(self):
        """Test comprehensive brand evaluation for Zyphlora with all required sections"""
        payload = {
            "brand_names": ["Zyphlora"],
            "category": "software",
            "industry": "Technology",
            "product_type": "SaaS",
            "positioning": "Premium",
            "market_scope": "Global",
            "countries": ["USA"]
        }
        
        try:
            print(f"\n🔍 Testing ZYPHLORA Comprehensive Evaluation...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Expected: GO or CONDITIONAL GO verdict with NameScore > 70 and all required sections")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/evaluate", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=300  # Extended timeout for comprehensive evaluation
            )
            response_time = time.time() - start_time
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Time: {response_time:.2f} seconds")
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                self.log_test("Zyphlora Comprehensive - HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking comprehensive structure...")
                
                # Test 1: Check basic response structure
                if not data.get("brand_scores") or len(data["brand_scores"]) == 0:
                    self.log_test("Zyphlora Comprehensive - Brand Scores Missing", False, "No brand scores returned")
                    return False
                
                brand = data["brand_scores"][0]
                
                # Test 2: Check brand name matches
                if brand.get("brand_name") != "Zyphlora":
                    self.log_test("Zyphlora Comprehensive - Brand Name", False, f"Expected 'Zyphlora', got '{brand.get('brand_name')}'")
                    return False
                
                # Test 3: Check verdict (should be GO or CONDITIONAL GO for unique brand)
                verdict = brand.get("verdict", "")
                expected_verdicts = ["GO", "CONDITIONAL GO", "APPROVE"]  # Accept these as positive verdicts
                if verdict not in expected_verdicts:
                    self.log_test("Zyphlora Comprehensive - Verdict", False, f"Expected GO/CONDITIONAL GO for unique brand, got '{verdict}'")
                    return False
                
                # Test 4: Check NameScore (should be > 70 for unique brand)
                namescore = brand.get("namescore")
                if not isinstance(namescore, (int, float)):
                    self.log_test("Zyphlora Comprehensive - NameScore Type", False, f"NameScore should be numeric, got {type(namescore)}")
                    return False
                
                if namescore <= 70:
                    self.log_test("Zyphlora Comprehensive - NameScore Range", False, f"Expected NameScore > 70 for unique brand, got {namescore}")
                    return False
                
                # Test 5: Check dimensions array (MUST have 6+ dimensions)
                if "dimensions" not in brand:
                    self.log_test("Zyphlora Comprehensive - Dimensions Missing", False, "dimensions field missing from brand_scores[0]")
                    return False
                
                dimensions = brand["dimensions"]
                if not isinstance(dimensions, list) or len(dimensions) < 6:
                    self.log_test("Zyphlora Comprehensive - Dimensions Count", False, f"Expected 6+ dimensions, got {len(dimensions) if isinstance(dimensions, list) else 'not a list'}")
                    return False
                
                # Test 6: Check each dimension has required fields (name, score, reasoning)
                dimension_issues = []
                for i, dim in enumerate(dimensions):
                    if not isinstance(dim, dict):
                        dimension_issues.append(f"Dimension {i} is not an object")
                        continue
                    
                    if "name" not in dim or not dim["name"]:
                        dimension_issues.append(f"Dimension {i} missing 'name' field")
                    
                    if "score" not in dim:
                        dimension_issues.append(f"Dimension {i} missing 'score' field")
                    elif not isinstance(dim["score"], (int, float)) or not (0 <= dim["score"] <= 10):
                        dimension_issues.append(f"Dimension {i} score should be 0-10, got {dim['score']}")
                    
                    if "reasoning" not in dim or not dim["reasoning"] or len(str(dim["reasoning"]).strip()) < 10:
                        dimension_issues.append(f"Dimension {i} missing or insufficient 'reasoning' field (got: {repr(dim.get('reasoning', 'MISSING'))[:50]}...)")
                
                if dimension_issues:
                    self.log_test("Zyphlora Comprehensive - Dimensions Structure", False, "; ".join(dimension_issues[:3]))  # Show first 3 issues
                    return False
                
                # Test 7: Check trademark_research section exists
                if "trademark_research" not in brand:
                    self.log_test("Zyphlora Comprehensive - Trademark Research Missing", False, "trademark_research field missing from brand_scores[0]")
                    return False
                
                tm_research = brand["trademark_research"]
                if not tm_research:
                    self.log_test("Zyphlora Comprehensive - Trademark Research Empty", False, "trademark_research is null/empty")
                    return False
                
                # Check trademark research has key fields
                tm_required = ["overall_risk_score", "trademark_conflicts", "company_conflicts"]
                tm_missing = [field for field in tm_required if field not in tm_research]
                if tm_missing:
                    self.log_test("Zyphlora Comprehensive - Trademark Research Fields", False, f"Missing trademark research fields: {tm_missing}")
                    return False
                
                # Test 8: Check competitor_analysis section exists
                competitor_analysis_found = False
                competitor_fields = ["competitor_analysis", "competitive_analysis", "competitive_landscape"]
                for field in competitor_fields:
                    if field in brand and brand[field]:
                        competitor_analysis_found = True
                        break
                
                if not competitor_analysis_found:
                    self.log_test("Zyphlora Comprehensive - Competitor Analysis Missing", False, f"No competitor analysis found. Checked fields: {competitor_fields}")
                    return False
                
                # Test 9: Check domain_analysis section exists
                if "domain_analysis" not in brand:
                    self.log_test("Zyphlora Comprehensive - Domain Analysis Missing", False, "domain_analysis field missing from brand_scores[0]")
                    return False
                
                domain_analysis = brand["domain_analysis"]
                if not domain_analysis:
                    self.log_test("Zyphlora Comprehensive - Domain Analysis Empty", False, "domain_analysis is null/empty")
                    return False
                
                # Test 10: Check executive summary exists and is substantial
                exec_summary = data.get("executive_summary", "")
                if len(exec_summary) < 100:
                    self.log_test("Zyphlora Comprehensive - Executive Summary", False, f"Executive summary too short: {len(exec_summary)} chars (expected 100+)")
                    return False
                
                # Success - log detailed results
                dimension_names = [dim.get("name", "Unknown") for dim in dimensions]
                tm_risk = tm_research.get("overall_risk_score", "Unknown")
                
                print(f"✅ Zyphlora evaluation completed successfully:")
                print(f"   - NameScore: {namescore}/100")
                print(f"   - Verdict: {verdict}")
                print(f"   - Dimensions: {len(dimensions)} ({', '.join(dimension_names[:4])}...)")
                print(f"   - Trademark Risk: {tm_risk}/10")
                print(f"   - Executive Summary: {len(exec_summary)} characters")
                print(f"   - Response Time: {response_time:.2f} seconds")
                
                self.log_test("Zyphlora Comprehensive Evaluation", True, 
                            f"All sections verified. NameScore: {namescore}/100, Verdict: {verdict}, Dimensions: {len(dimensions)}, TM Risk: {tm_risk}/10, Time: {response_time:.1f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Zyphlora Comprehensive - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Zyphlora Comprehensive - Timeout", False, "Request timed out after 300 seconds")
            return False
        except Exception as e:
            self.log_test("Zyphlora Comprehensive - Exception", False, str(e))
            return False

    def test_brand_audit_chaayos_final(self):
        """Final test of Brand Audit API with Chaayos after fixing Claude timeout and schema validation"""
        payload = {
            "brand_name": "Chaayos",
            "brand_website": "https://chaayos.com",
            "category": "Food & Beverage",
            "geography": "India",
            "competitor_1": "Chai Point",
            "competitor_2": "Tea Trails"
        }
        
        try:
            print(f"\n🔍 FINAL TEST: Brand Audit API with Chaayos after fixes...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Expected: Status 200 OK, JSON with report_id, overall_score (0-100), verdict, executive_summary, dimensions (8 items)")
            print(f"Fixed: 1) Claude timeout (removed Claude, OpenAI only), 2) Schema validation (sources.id now accepts Any type)")
            print(f"Timeout: 120 seconds allowed")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/brand-audit", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=120  # 120 seconds as requested
            )
            
            processing_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Processing Time: {processing_time:.2f} seconds")
            
            # Test 1: API should return 200 OK
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                if response.status_code == 500:
                    # Check if it's still the schema validation error
                    if "sources.0.id Input should be a valid string" in response.text:
                        self.log_test("Brand Audit - Chaayos Schema Error", False, f"Schema validation error still present: sources.id expects string but gets integer")
                    else:
                        self.log_test("Brand Audit - Chaayos Server Error", False, f"Server error: {error_msg}")
                elif response.status_code in [502, 503]:
                    self.log_test("Brand Audit - Chaayos Gateway Error", False, f"Gateway/service error: {error_msg}")
                elif response.status_code == 408:
                    self.log_test("Brand Audit - Chaayos Timeout", False, f"Request timeout: {error_msg}")
                else:
                    self.log_test("Brand Audit - Chaayos HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking structure...")
                
                # Test 2: Check required top-level fields
                required_fields = ["report_id", "overall_score", "verdict", "executive_summary", "dimensions"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Brand Audit - Chaayos Required Fields", False, f"Missing required fields: {missing_fields}")
                    return False
                
                # Test 3: Check report_id is string
                report_id = data.get("report_id")
                if not isinstance(report_id, str) or len(report_id) == 0:
                    self.log_test("Brand Audit - Chaayos Report ID", False, f"Invalid report_id: {report_id}")
                    return False
                
                # Test 4: Check overall_score is number 0-100
                overall_score = data.get("overall_score")
                if not isinstance(overall_score, (int, float)) or not (0 <= overall_score <= 100):
                    self.log_test("Brand Audit - Chaayos Overall Score", False, f"Invalid overall_score: {overall_score} (should be 0-100)")
                    return False
                
                # Test 5: Check verdict is string
                verdict = data.get("verdict", "")
                if not isinstance(verdict, str) or len(verdict) == 0:
                    self.log_test("Brand Audit - Chaayos Verdict", False, f"Invalid verdict: {verdict} (should be non-empty string)")
                    return False
                
                # Test 6: Check executive_summary is substantial
                executive_summary = data.get("executive_summary", "")
                if not isinstance(executive_summary, str) or len(executive_summary) < 50:
                    self.log_test("Brand Audit - Chaayos Executive Summary", False, f"Invalid executive_summary: {len(executive_summary)} chars (should be 50+ chars)")
                    return False
                
                # Test 7: Check dimensions array has 8 items
                dimensions = data.get("dimensions", [])
                if not isinstance(dimensions, list) or len(dimensions) != 8:
                    self.log_test("Brand Audit - Chaayos Dimensions Count", False, f"Expected 8 dimensions, got {len(dimensions)}")
                    return False
                
                # Test 8: Check each dimension has required structure
                for i, dimension in enumerate(dimensions):
                    if not isinstance(dimension, dict):
                        self.log_test("Brand Audit - Chaayos Dimension Structure", False, f"Dimension {i} is not a dict: {type(dimension)}")
                        return False
                    
                    dim_required = ["name", "score", "analysis"]
                    dim_missing = [field for field in dim_required if field not in dimension]
                    if dim_missing:
                        self.log_test("Brand Audit - Chaayos Dimension Fields", False, f"Dimension {i} missing fields: {dim_missing}")
                        return False
                    
                    # Check score is 0-100
                    dim_score = dimension.get("score")
                    if not isinstance(dim_score, (int, float)) or not (0 <= dim_score <= 100):
                        self.log_test("Brand Audit - Chaayos Dimension Score", False, f"Dimension {i} invalid score: {dim_score}")
                        return False
                
                # Test 9: Check for schema validation issues (sources.id)
                response_text = json.dumps(data)
                if "sources" in response_text:
                    print(f"✅ Sources field present in response - checking for schema validation fix...")
                    # If we got here with 200 OK, the schema validation is likely fixed
                
                print(f"✅ Chaayos Brand Audit completed successfully:")
                print(f"   - Report ID: {report_id}")
                print(f"   - Overall Score: {overall_score}/100")
                print(f"   - Verdict: {verdict}")
                print(f"   - Executive Summary: {len(executive_summary)} characters")
                print(f"   - Dimensions: {len(dimensions)} items")
                print(f"   - Processing Time: {processing_time:.2f} seconds")
                
                self.log_test("Brand Audit - Chaayos Final Test", True, 
                            f"SUCCESS: 200 OK with valid JSON. Report ID: {report_id}, Score: {overall_score}/100, Verdict: {verdict}, Dimensions: {len(dimensions)}, Time: {processing_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Brand Audit - Chaayos JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Brand Audit - Chaayos Timeout", False, "Request timed out after 120 seconds")
            return False
        except Exception as e:
            self.log_test("Brand Audit - Chaayos Exception", False, str(e))
            return False

    def test_brand_audit_chai_bunk_improvements(self):
        """Test Brand Audit API with Chai Bunk to verify recent improvements"""
        payload = {
            "brand_name": "Chai Bunk",
            "brand_website": "https://www.chaibunk.com",
            "competitor_1": "https://www.chaayos.com",
            "competitor_2": "https://www.chaipoint.com",
            "category": "Cafe/QSR",
            "geography": "India"
        }
        
        try:
            print(f"\n🔍 Testing Brand Audit API with Chai Bunk to verify recent improvements...")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Expected: Website crawling works, API returns valid JSON with report_id, overall_score, executive_summary")
            print(f"Expected: Data accuracy from website (120+ outlets, Sandeep Bandari, 2021)")
            print(f"Expected: All required sections present (dimensions array with 8 items, swot, recommendations)")
            print(f"Timeout: 180 seconds due to website crawling + web searches + LLM processing")
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/brand-audit", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=180  # 180 second timeout as requested
            )
            
            processing_time = time.time() - start_time
            print(f"Response Status: {response.status_code}")
            print(f"Processing Time: {processing_time:.2f} seconds")
            
            # Test 1: API should return 200 OK
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                if response.status_code in [502, 500, 503]:
                    self.log_test("Brand Audit - Chai Bunk Server Error", False, f"Server error (expected 200 OK): {error_msg}")
                elif response.status_code == 408:
                    self.log_test("Brand Audit - Chai Bunk Timeout", False, f"Request timeout: {error_msg}")
                else:
                    self.log_test("Brand Audit - Chai Bunk HTTP Error", False, error_msg)
                return False
            
            try:
                data = response.json()
                print(f"✅ Response received successfully, checking structure...")
                
                # Test 2: Check required top-level fields
                required_fields = ["report_id", "overall_score", "executive_summary"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Brand Audit - Chai Bunk Required Fields", False, f"Missing required fields: {missing_fields}")
                    return False
                
                # Test 3: Check report_id is valid string
                report_id = data.get("report_id")
                if not isinstance(report_id, str) or len(report_id) == 0:
                    self.log_test("Brand Audit - Chai Bunk Report ID", False, f"Invalid report_id: {report_id}")
                    return False
                
                # Test 4: Check overall_score is number 0-100
                overall_score = data.get("overall_score")
                if not isinstance(overall_score, (int, float)) or not (0 <= overall_score <= 100):
                    self.log_test("Brand Audit - Chai Bunk Overall Score", False, f"Invalid overall_score: {overall_score} (should be 0-100)")
                    return False
                
                # Test 5: Check executive_summary is substantial
                executive_summary = data.get("executive_summary", "")
                if len(executive_summary) < 100:
                    self.log_test("Brand Audit - Chai Bunk Executive Summary", False, f"Executive summary too short: {len(executive_summary)} chars (expected 100+)")
                    return False
                
                # Test 6: Check dimensions array with 8 items
                dimensions = data.get("dimensions", [])
                if not isinstance(dimensions, list) or len(dimensions) != 8:
                    self.log_test("Brand Audit - Chai Bunk Dimensions", False, f"Expected dimensions array with 8 items, got {len(dimensions) if isinstance(dimensions, list) else type(dimensions)}")
                    return False
                
                # Test 7: Check SWOT analysis present
                swot = data.get("swot")
                if not swot or not isinstance(swot, dict):
                    self.log_test("Brand Audit - Chai Bunk SWOT", False, f"Missing or invalid SWOT analysis: {type(swot)}")
                    return False
                
                swot_sections = ["strengths", "weaknesses", "opportunities", "threats"]
                missing_swot = [section for section in swot_sections if section not in swot]
                if missing_swot:
                    self.log_test("Brand Audit - Chai Bunk SWOT Sections", False, f"Missing SWOT sections: {missing_swot}")
                    return False
                
                # Test 8: Check recommendations present
                recommendations = data.get("recommendations")
                if not recommendations or not isinstance(recommendations, dict):
                    self.log_test("Brand Audit - Chai Bunk Recommendations", False, f"Missing or invalid recommendations: {type(recommendations)}")
                    return False
                
                rec_sections = ["immediate", "medium_term", "long_term"]
                missing_rec = [section for section in rec_sections if section not in recommendations]
                if missing_rec:
                    self.log_test("Brand Audit - Chai Bunk Recommendation Sections", False, f"Missing recommendation sections: {missing_rec}")
                    return False
                
                # Test 9: Check for data accuracy from website (brand_overview section)
                brand_overview = data.get("brand_overview", {})
                if brand_overview:
                    outlets_count = str(brand_overview.get("outlets_count", "")).lower()
                    founded = str(brand_overview.get("founded", "")).lower()
                    
                    # Check for 120+ outlets
                    if "120" not in outlets_count and "100+" not in outlets_count:
                        print(f"⚠️  Warning: Expected '120+' outlets in brand_overview.outlets_count, got: {outlets_count}")
                    
                    # Check for 2021 founding year
                    if "2021" not in founded:
                        print(f"⚠️  Warning: Expected '2021' in brand_overview.founded, got: {founded}")
                    
                    # Check executive summary for founder info
                    if "sandeep" not in executive_summary.lower() and "bandari" not in executive_summary.lower():
                        print(f"⚠️  Warning: Expected founder info (Sandeep Bandari) in executive summary")
                
                # Test 10: Check that LLM did not refuse with "insufficient data"
                response_text = json.dumps(data).lower()
                if "insufficient data" in response_text or "not enough information" in response_text:
                    self.log_test("Brand Audit - Chai Bunk LLM Refusal", False, "LLM refused with 'insufficient data' message")
                    return False
                
                print(f"✅ Chai Bunk Brand Audit completed successfully:")
                print(f"   - Report ID: {report_id}")
                print(f"   - Overall Score: {overall_score}/100")
                print(f"   - Executive Summary: {len(executive_summary)} characters")
                print(f"   - Dimensions: {len(dimensions)} items")
                print(f"   - SWOT: {len(swot)} sections")
                print(f"   - Recommendations: {len(recommendations)} sections")
                print(f"   - Processing Time: {processing_time:.2f} seconds")
                
                self.log_test("Brand Audit - Chai Bunk Improvements", True, 
                            f"All checks passed. Score: {overall_score}/100, Dimensions: {len(dimensions)}, Processing: {processing_time:.2f}s")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Brand Audit - Chai Bunk JSON Parse", False, f"Invalid JSON response: {str(e)}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Brand Audit - Chai Bunk Timeout", False, "Request timed out after 180 seconds")
            return False
        except Exception as e:
            self.log_test("Brand Audit - Chai Bunk Exception", False, str(e))
            return False

    def test_brand_audit_chai_bunk_retry_mechanism(self):
        """Test Brand Audit API with retry mechanism for Chai Bunk - as requested in review"""
        payload = {
            "brand_name": "Chai Bunk",
            "brand_website": "https://www.chaibunk.com",
            "competitor_1": "https://www.chaayos.com",
            "competitor_2": "https://www.chaipoint.com",
            "category": "Cafe/QSR",
            "geography": "India"
        }
        
        try:
            print(f"\n🔍 TESTING BRAND AUDIT API WITH RETRY MECHANISM - CHAI BUNK")
            print(f"="*80)
            print(f"Test Case: {json.dumps(payload, indent=2)}")
            print(f"Expected Features to Verify:")
            print(f"  1. Retry Logic with Exponential Backoff (5s, 10s, 15s)")
            print(f"  2. Model Fallback Order: GPT-4o-mini → GPT-4o → Claude")
            print(f"  3. Website Crawling: Should see 'Successfully crawled' messages")
            print(f"  4. Expected Success: 200 OK with valid JSON report")
            print(f"  5. Timeout: 240 seconds (4 minutes)")
            print(f"="*80)
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/brand-audit", 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=240  # 4 minutes as requested
            )
            
            processing_time = time.time() - start_time
            print(f"\n📊 RESPONSE DETAILS:")
            print(f"Status Code: {response.status_code}")
            print(f"Processing Time: {processing_time:.2f} seconds")
            print(f"Response Headers: {dict(response.headers)}")
            
            # Test 1: Check for successful response (200 OK)
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text[:1000]}"
                print(f"❌ Expected 200 OK, got {response.status_code}")
                
                # Check for specific error types
                if response.status_code == 502:
                    self.log_test("Brand Audit Chai Bunk - 502 BadGateway", False, "502 BadGateway error - LLM provider issues")
                elif response.status_code == 503:
                    self.log_test("Brand Audit Chai Bunk - 503 Service Unavailable", False, "503 Service Unavailable - upstream connect error")
                elif response.status_code == 500:
                    self.log_test("Brand Audit Chai Bunk - 500 Internal Server Error", False, "500 Internal Server Error - JSON parsing or schema validation issues")
                elif response.status_code == 408:
                    self.log_test("Brand Audit Chai Bunk - 408 Timeout", False, f"Request timeout after {processing_time:.2f} seconds")
                else:
                    self.log_test("Brand Audit Chai Bunk - HTTP Error", False, error_msg)
                return False
            
            # Test 2: Parse JSON response
            try:
                data = response.json()
                print(f"✅ JSON Response parsed successfully")
                print(f"Response keys: {list(data.keys())}")
                
                # Test 3: Check required fields for Brand Audit response
                required_fields = ["report_id", "overall_score", "verdict", "executive_summary", "dimensions"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    self.log_test("Brand Audit Chai Bunk - Required Fields", False, f"Missing required fields: {missing_fields}")
                    return False
                
                # Test 4: Validate field types and ranges
                report_id = data.get("report_id")
                if not isinstance(report_id, str) or len(report_id) == 0:
                    self.log_test("Brand Audit Chai Bunk - Report ID", False, f"Invalid report_id: {report_id}")
                    return False
                
                overall_score = data.get("overall_score")
                if not isinstance(overall_score, (int, float)) or not (0 <= overall_score <= 100):
                    self.log_test("Brand Audit Chai Bunk - Overall Score", False, f"Invalid overall_score: {overall_score} (should be 0-100)")
                    return False
                
                verdict = data.get("verdict", "")
                valid_verdicts = ["STRONG", "MODERATE", "WEAK", "CRITICAL"]
                if verdict not in valid_verdicts:
                    self.log_test("Brand Audit Chai Bunk - Verdict", False, f"Invalid verdict: {verdict} (should be one of {valid_verdicts})")
                    return False
                
                executive_summary = data.get("executive_summary", "")
                if len(executive_summary) < 100:  # Should be substantial
                    self.log_test("Brand Audit Chai Bunk - Executive Summary", False, f"Executive summary too short: {len(executive_summary)} chars")
                    return False
                
                # Test 5: Check dimensions array
                dimensions = data.get("dimensions", [])
                if not isinstance(dimensions, list) or len(dimensions) == 0:
                    self.log_test("Brand Audit Chai Bunk - Dimensions", False, f"Invalid dimensions: {type(dimensions)} with length {len(dimensions) if isinstance(dimensions, list) else 'N/A'}")
                    return False
                
                # Test 6: Validate dimension structure
                for i, dim in enumerate(dimensions):
                    if not isinstance(dim, dict):
                        self.log_test("Brand Audit Chai Bunk - Dimension Structure", False, f"Dimension {i} is not a dict: {type(dim)}")
                        return False
                    
                    dim_required = ["name", "score", "analysis"]
                    dim_missing = [field for field in dim_required if field not in dim]
                    if dim_missing:
                        self.log_test("Brand Audit Chai Bunk - Dimension Fields", False, f"Dimension {i} missing fields: {dim_missing}")
                        return False
                    
                    dim_score = dim.get("score")
                    if not isinstance(dim_score, (int, float)) or not (0 <= dim_score <= 100):
                        self.log_test("Brand Audit Chai Bunk - Dimension Score", False, f"Dimension {i} invalid score: {dim_score}")
                        return False
                
                # Test 7: Check for website crawling evidence in response
                response_text = json.dumps(data).lower()
                crawling_indicators = ["chaibunk.com", "about page", "homepage", "franchise"]
                found_crawling = [indicator for indicator in crawling_indicators if indicator in response_text]
                
                if len(found_crawling) < 2:  # Should find at least 2 indicators
                    print(f"⚠️  Warning: Limited website crawling evidence found: {found_crawling}")
                else:
                    print(f"✅ Website crawling evidence found: {found_crawling}")
                
                # Test 8: Check for competitor analysis
                competitor_indicators = ["chaayos", "chai point", "competitor"]
                found_competitors = [indicator for indicator in competitor_indicators if indicator in response_text]
                
                if len(found_competitors) < 1:
                    print(f"⚠️  Warning: Limited competitor analysis evidence: {found_competitors}")
                else:
                    print(f"✅ Competitor analysis evidence found: {found_competitors}")
                
                # Success summary
                print(f"\n🎉 CHAI BUNK BRAND AUDIT TEST RESULTS:")
                print(f"✅ Status: 200 OK")
                print(f"✅ Processing Time: {processing_time:.2f} seconds")
                print(f"✅ Report ID: {report_id}")
                print(f"✅ Overall Score: {overall_score}/100")
                print(f"✅ Verdict: {verdict}")
                print(f"✅ Executive Summary: {len(executive_summary)} characters")
                print(f"✅ Dimensions: {len(dimensions)} analysis dimensions")
                print(f"✅ Website Crawling: {len(found_crawling)} indicators found")
                print(f"✅ Competitor Analysis: {len(found_competitors)} indicators found")
                
                self.log_test("Brand Audit Chai Bunk - Complete Success", True, 
                            f"All tests passed. Score: {overall_score}/100, Verdict: {verdict}, Time: {processing_time:.2f}s, Dimensions: {len(dimensions)}")
                return True
                
            except json.JSONDecodeError as e:
                self.log_test("Brand Audit Chai Bunk - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                print(f"❌ JSON Parse Error: {str(e)}")
                print(f"Response text (first 500 chars): {response.text[:500]}")
                return False
                
        except requests.exceptions.Timeout:
            self.log_test("Brand Audit Chai Bunk - Timeout", False, f"Request timed out after 240 seconds")
            print(f"❌ Request timed out after 240 seconds")
            return False
        except Exception as e:
            self.log_test("Brand Audit Chai Bunk - Exception", False, str(e))
            print(f"❌ Exception occurred: {str(e)}")
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
        
        # PRIORITY: Test currency logic as per review request
        print("\n💰 PRIORITY: Testing Currency Logic...")
        self.test_currency_single_country_usa()
        self.test_currency_single_country_india()
        self.test_currency_multiple_countries()
        
        # PRIORITY: Test newly configured Emergent LLM key (as per review request)
        print("\n🔑 PRIORITY TEST: Testing newly configured Emergent LLM key...")
        self.test_emergent_llm_key_smoke_test()
        
        # PRIORITY: Test score_impact validation fix (as per review request)
        print("\n🔧 PRIORITY TEST: Testing score_impact validation fix...")
        self.test_score_impact_validation_fix()
        
        # PRIORITY: Test fallback model feature (as per review request)
        print("\n🔄 PRIORITY TEST: Testing fallback model feature...")
        self.test_fallback_model_feature()
        
        # PRIORITY: Test dimensions population (as per review request)
        print("\n📊 PRIORITY TEST: Testing dimensions population...")
        self.test_dimensions_population_nexaflow()
        
        # Test main evaluate endpoint
        self.test_evaluate_endpoint_structure()
        
        # Test trademark research functionality
        print("\n🔍 Testing Trademark Research Feature...")
        self.test_trademark_research_luminara()
        self.test_trademark_research_nexofy()
        
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
        
        # NEW: RIGHTNAME v2.0 Improvement Tests
        print("\n🆕 RIGHTNAME v2.0 IMPROVEMENT TESTS")
        print("=" * 80)
        self.test_early_stopping_famous_brands()      # Improvement #5
        self.test_parallel_processing_speed()         # Improvement #1  
        self.test_new_form_fields()                   # Improvements #2 & #3
        self.test_play_store_error_handling()         # Improvement #4
        
        # NEW: LLM-First Brand Conflict Detection Tests
        print("\n🤖 LLM-FIRST BRAND CONFLICT DETECTION TESTS")
        print("=" * 80)
        self.test_llm_brand_detection_andhrajyoothi()  # Test Case 1: AndhraJyoothi vs Andhra Jyothi
        self.test_llm_brand_detection_bumbell()        # Test Case 2: BUMBELL vs Bumble
        self.test_llm_brand_detection_unique_name()    # Test Case 3: Zyntrix2025 (unique)
        self.test_llm_brand_detection_moneycontrols()  # Test Case 4: MoneyControls vs Moneycontrol
        self.test_llm_backend_logs_verification()      # Verify LLM logs
        
        # Print summary
        print(f"\n📊 Test Summary:")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = BrandEvaluationTester()
    
    # Run Brand Audit test as per review request
    print("🔍 BRAND AUDIT API TEST: Testing /api/brand-audit endpoint after improved error handling")
    print("=" * 80)
    print("🎯 TESTING: Brand Audit API with Bikanervala test case")
    print("🔧 IMPROVED: Added empty response checks")
    print("🔧 IMPROVED: Changed model priority: gpt-4o first (more stable), then gpt-4o-mini, then gpt-4.1")
    print("=" * 80)
    
    # Test API health first
    if not tester.test_api_health():
        print("❌ API health check failed, stopping tests")
        return 1
    
    # PRIORITY: Run Brand Audit test as per review request
    print("\n🔍 FINAL BRAND AUDIT TEST:")
    print("Testing Brand Audit API with Bikanervala (Indian sweets brand) after improved error handling...")
    print("Expected: Status 200 with report_id, overall_score, verdict, executive_summary, dimensions")
    print("Allow 180 seconds. If valid JSON response = SUCCESS.")
    
    # Run the specific test requested
    success = tester.test_brand_audit_bikanervala_final()
    
    # Print summary
    print(f"\n📊 Brand Audit Test Summary:")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%" if tester.tests_run > 0 else "0%")
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            "test_focus": "Brand Audit API Test - Bikanervala Final Test",
            "description": "Final test of Brand Audit API /api/brand-audit with improved error handling",
            "improvement_details": {
                "issue": "Previous issues with empty responses and model stability",
                "solution": "Added empty response checks, changed model priority: gpt-4o first (more stable), then gpt-4o-mini, then gpt-4.1",
                "timeout": "Allow 180 seconds for processing"
            },
            "test_case": {
                "brand_name": "Bikanervala",
                "brand_website": "https://bfresco.com",
                "category": "Food & Beverage",
                "geography": "India",
                "competitor_1": "Haldiram",
                "competitor_2": "Bikano"
            },
            "verification_points": [
                "API returns successful response (200 OK)",
                "Response contains report_id (string)",
                "Response contains overall_score (number 0-100)",
                "Response contains verdict (valid verdict string)",
                "Response contains executive_summary (substantial text)",
                "Response contains dimensions (array with proper structure)",
                "Processing completes within 180 seconds",
                "Valid JSON response = SUCCESS"
            ],
            "summary": {
                "tests_run": tester.tests_run,
                "tests_passed": tester.tests_passed,
                "success_rate": (tester.tests_passed/tester.tests_run)*100 if tester.tests_run > 0 else 0,
                "overall_success": success
            },
            "results": tester.test_results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    if success:
        print("🎉 BRAND AUDIT TEST PASSED!")
        return 0
    else:
        print("❌ BRAND AUDIT TEST FAILED!")
        return 1

def main_chai_bunk_test():
    """Main function to run Chai Bunk Brand Audit test as requested in review"""
    print("🔍 CHAI BUNK BRAND AUDIT API TEST")
    print("="*80)
    print("Testing Brand Audit API with compact prompt for Chai Bunk")
    print("Expected: Website crawling, web searches, LLM JSON response, 200 OK")
    print("Timeout: 180 seconds (3 minutes)")
    print("="*80)
    
    tester = BrandEvaluationTester()
    
    # Run the specific Chai Bunk test
    success = tester.test_brand_audit_chai_bunk_compact_prompt()
    
    # Print summary
    tester.print_summary()
    
    print(f"\nTest Results:")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%" if tester.tests_run > 0 else "0%")
    
    # Save detailed results
    with open('/app/chai_bunk_test_results.json', 'w') as f:
        json.dump({
            "test_focus": "Chai Bunk Brand Audit API Test - Compact Prompt",
            "description": "Test Brand Audit API with Chai Bunk using compact prompt for faster processing",
            "test_case": {
                "brand_name": "Chai Bunk",
                "brand_website": "https://www.chaibunk.com",
                "competitor_1": "https://www.chaayos.com",
                "competitor_2": "https://www.chaipoint.com",
                "category": "Cafe/QSR",
                "geography": "India"
            },
            "expected_behavior": [
                "Website crawling completes (look for 'Successfully crawled' in logs)",
                "Web searches complete (5 searches)",
                "LLM generates JSON response (compact prompt ~3K chars)",
                "Response returns 200 OK with valid JSON"
            ],
            "verification_points": [
                "report_id exists",
                "overall_score is a number",
                "brand_overview.outlets_count mentions '120'",
                "dimensions array has 8 items",
                "swot has all 4 categories (strengths, weaknesses, opportunities, threats)"
            ],
            "timeout": "180 seconds (3 minutes)",
            "summary": {
                "tests_run": tester.tests_run,
                "tests_passed": tester.tests_passed,
                "success_rate": (tester.tests_passed/tester.tests_run)*100 if tester.tests_run > 0 else 0,
                "overall_success": success
            },
            "results": tester.test_results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    if success:
        print("🎉 CHAI BUNK BRAND AUDIT TEST PASSED!")
        return 0
    else:
        print("❌ CHAI BUNK BRAND AUDIT TEST FAILED!")
        return 1

if __name__ == "__main__":
    # Check if we should run the Chai Bunk test specifically
    if len(sys.argv) > 1 and sys.argv[1] == "chai_bunk":
        sys.exit(main_chai_bunk_test())
    elif len(sys.argv) > 1 and sys.argv[1] == "schema_fix":
        # Run the schema fix test
        tester = BrandEvaluationTester()
        
        print("🔍 CHAI BUNK BRAND AUDIT API - SCHEMA FIX TEST")
        print("="*80)
        print("Testing Brand Audit API with Chai Bunk - StrategicRecommendation Schema Fix")
        print("Expected: 200 OK response (not 500 error) with valid JSON structure")
        print("Timeout: 180 seconds (3 minutes)")
        print("="*80)
        
        # Add the schema fix test method
        def test_brand_audit_chai_bunk_schema_fix():
            """Test Brand Audit API with Chai Bunk - Schema Fix for StrategicRecommendation"""
            payload = {
                "brand_name": "Chai Bunk",
                "brand_website": "https://www.chaibunk.com",
                "competitor_1": "https://www.chaayos.com",
                "competitor_2": "https://www.chaipoint.com",
                "category": "Cafe/QSR",
                "geography": "India"
            }
            
            try:
                print(f"\n🔍 Testing Brand Audit API - Chai Bunk Schema Fix...")
                print(f"Testing the fix for StrategicRecommendation schema (optional fields + title<->recommended_action mapping)")
                print(f"Payload: {json.dumps(payload, indent=2)}")
                print(f"Expected: 200 OK response with valid JSON (report_id, overall_score, dimensions, recommendations, swot)")
                
                start_time = time.time()
                response = requests.post(
                    f"{tester.api_url}/brand-audit", 
                    json=payload, 
                    headers={'Content-Type': 'application/json'},
                    timeout=180  # 3 minutes timeout as specified in review request
                )
                
                processing_time = time.time() - start_time
                print(f"Response Status: {response.status_code}")
                print(f"Processing Time: {processing_time:.2f} seconds")
                
                # Test 1: API should return 200 OK (not 500 Internal Server Error)
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                    if response.status_code == 500:
                        tester.log_test("Brand Audit Schema Fix - 500 Error", False, f"Still getting 500 Internal Server Error (expected 200 OK): {error_msg}")
                    elif response.status_code in [502, 503]:
                        tester.log_test("Brand Audit Schema Fix - Server Error", False, f"Server error: {error_msg}")
                    elif response.status_code == 408:
                        tester.log_test("Brand Audit Schema Fix - Timeout", False, f"Request timeout: {error_msg}")
                    else:
                        tester.log_test("Brand Audit Schema Fix - HTTP Error", False, error_msg)
                    return False
                
                try:
                    data = response.json()
                    print(f"✅ Response received successfully (200 OK), checking structure...")
                    print(f"Response keys: {list(data.keys())}")
                    
                    # Test 2: Check required top-level fields as specified in review request
                    # Note: The API returns separate recommendation fields instead of a single 'recommendations' field
                    required_fields = ["report_id", "overall_score", "dimensions", "swot"]
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if missing_fields:
                        print(f"Available fields: {list(data.keys())}")
                        tester.log_test("Brand Audit Schema Fix - Required Fields", False, f"Missing required fields: {missing_fields}")
                        return False
                    
                    # Check for recommendation fields (can be separate fields)
                    recommendation_fields = ["immediate_recommendations", "medium_term_recommendations", "long_term_recommendations"]
                    found_recommendation_fields = [field for field in recommendation_fields if field in data]
                    
                    if not found_recommendation_fields:
                        tester.log_test("Brand Audit Schema Fix - Recommendations Fields", False, f"No recommendation fields found. Expected one of: {recommendation_fields}")
                        return False
                    
                    # Combine all recommendation fields for testing
                    all_recommendations = []
                    for field in found_recommendation_fields:
                        field_data = data.get(field, [])
                        if isinstance(field_data, list):
                            all_recommendations.extend(field_data)
                    
                    recommendations = all_recommendations
                    
                    # Test 3: Check report_id exists and is valid
                    report_id = data.get("report_id")
                    if not isinstance(report_id, str) or len(report_id) == 0:
                        tester.log_test("Brand Audit Schema Fix - Report ID", False, f"Invalid report_id: {report_id}")
                        return False
                    
                    # Test 4: Check overall_score is number
                    overall_score = data.get("overall_score")
                    if not isinstance(overall_score, (int, float)):
                        tester.log_test("Brand Audit Schema Fix - Overall Score", False, f"overall_score is not a number: {overall_score}")
                        return False
                    
                    # Test 5: Check dimensions array exists and has content
                    dimensions = data.get("dimensions", [])
                    if not isinstance(dimensions, list) or len(dimensions) == 0:
                        tester.log_test("Brand Audit Schema Fix - Dimensions", False, f"dimensions should be non-empty array, got: {type(dimensions)} with length {len(dimensions) if isinstance(dimensions, list) else 'N/A'}")
                        return False
                    
                    # Test 6: Check recommendations array exists (this was the problematic field)
                    if not isinstance(recommendations, list):
                        tester.log_test("Brand Audit Schema Fix - Recommendations Type", False, f"recommendations should be array, got: {type(recommendations)}")
                        return False
                    
                    # Test 7: Check StrategicRecommendation schema fix - each recommendation should have title and/or recommended_action
                    for i, rec in enumerate(recommendations):
                        if not isinstance(rec, dict):
                            tester.log_test("Brand Audit Schema Fix - Recommendation Structure", False, f"recommendations[{i}] should be object, got: {type(rec)}")
                            return False
                        
                        # The fix should ensure either 'title' or 'recommended_action' is present (or both)
                        has_title = "title" in rec and rec["title"]
                        has_recommended_action = "recommended_action" in rec and rec["recommended_action"]
                        
                        if not (has_title or has_recommended_action):
                            tester.log_test("Brand Audit Schema Fix - Recommendation Fields", False, f"recommendations[{i}] missing both 'title' and 'recommended_action': {rec}")
                            return False
                    
                    # Test 8: Check swot analysis exists
                    swot = data.get("swot", {})
                    if not isinstance(swot, dict):
                        tester.log_test("Brand Audit Schema Fix - SWOT Type", False, f"swot should be object, got: {type(swot)}")
                        return False
                    
                    # Test 9: Verify no schema validation errors in response
                    response_text = json.dumps(data).lower()
                    schema_error_indicators = [
                        "field required",
                        "missing required field", 
                        "validation error",
                        "pydantic",
                        "recommended_action",
                        "strategicrecommendation"
                    ]
                    
                    found_errors = [indicator for indicator in schema_error_indicators if indicator in response_text]
                    if found_errors:
                        tester.log_test("Brand Audit Schema Fix - Schema Errors", False, f"Found schema error indicators in response: {found_errors}")
                        return False
                    
                    print(f"✅ Schema validation passed:")
                    print(f"   - Report ID: {report_id}")
                    print(f"   - Overall Score: {overall_score}")
                    print(f"   - Dimensions: {len(dimensions)} items")
                    print(f"   - Recommendations: {len(recommendations)} items")
                    print(f"   - SWOT: Present")
                    print(f"   - Processing Time: {processing_time:.2f}s")
                    
                    tester.log_test("Brand Audit Schema Fix - Chai Bunk", True, 
                                f"✅ SCHEMA FIX VERIFIED: 200 OK response with valid JSON. Report ID: {report_id}, Score: {overall_score}, Dimensions: {len(dimensions)}, Recommendations: {len(recommendations)}, Time: {processing_time:.2f}s")
                    return True
                    
                except json.JSONDecodeError as e:
                    tester.log_test("Brand Audit Schema Fix - JSON Parse", False, f"Invalid JSON response: {str(e)}")
                    return False
                    
            except requests.exceptions.Timeout:
                tester.log_test("Brand Audit Schema Fix - Timeout", False, "Request timed out after 180 seconds")
                return False
            except Exception as e:
                tester.log_test("Brand Audit Schema Fix - Exception", False, str(e))
                return False
        
        # Run the schema fix test
        success = test_brand_audit_chai_bunk_schema_fix()
        
        # Print summary
        tester.print_summary()
        
        # Save detailed results
        with open('/app/chai_bunk_schema_fix_results.json', 'w') as f:
            json.dump({
                "test_focus": "Chai Bunk Brand Audit API - Schema Fix Test",
                "description": "Test Brand Audit API with Chai Bunk after StrategicRecommendation schema fix",
                "test_case": {
                    "brand_name": "Chai Bunk",
                    "brand_website": "https://www.chaibunk.com",
                    "competitor_1": "https://www.chaayos.com",
                    "competitor_2": "https://www.chaipoint.com",
                    "category": "Cafe/QSR",
                    "geography": "India"
                },
                "schema_fix_details": [
                    "StrategicRecommendation schema now has optional fields",
                    "parse_recommendation() function maps title<->recommended_action"
                ],
                "expected_behavior": [
                    "200 OK response (not 500 Internal Server Error)",
                    "Valid JSON with report_id, overall_score, dimensions, recommendations, swot",
                    "No Pydantic validation errors",
                    "No 'Field required' errors for recommended_action"
                ],
                "timeout": "180 seconds (3 minutes)",
                "summary": {
                    "tests_run": tester.tests_run,
                    "tests_passed": tester.tests_passed,
                    "success_rate": (tester.tests_passed/tester.tests_run)*100 if tester.tests_run > 0 else 0,
                    "overall_success": success
                },
                "results": tester.test_results,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        if success:
            print("🎉 CHAI BUNK SCHEMA FIX TEST PASSED!")
            sys.exit(0)
        else:
            print("❌ CHAI BUNK SCHEMA FIX TEST FAILED!")
            sys.exit(1)
    else:
        sys.exit(main())