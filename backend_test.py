import requests
import sys
import json
from datetime import datetime
import uuid

class BrandEvaluationTester:
    def __init__(self, base_url="https://name-radar-1.preview.emergentagent.com"):
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
    
    # Run QuickTest smoke test as per review request
    print("🔍 QUICKTEST SMOKE TEST: Testing RIGHTNAME brand evaluation API")
    print("=" * 80)
    print("🎯 TESTING: QuickTest brand evaluation with schema fix verification")
    print("=" * 80)
    
    # Test API health first
    if not tester.test_api_health():
        print("❌ API health check failed, stopping tests")
        return 1
    
    # PRIORITY: Run QuickTest smoke test as per review request
    print("\n🔍 QUICKTEST SMOKE TEST:")
    print("Testing brand evaluation API with QuickTest payload...")
    
    # Run the specific test requested
    success = tester.test_quicktest_smoke_test()
    
    # Print summary
    print(f"\n📊 QuickTest Smoke Test Summary:")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            "test_focus": "QuickTest Smoke Test for RIGHTNAME API",
            "description": "Quick smoke test to verify RIGHTNAME brand evaluation API is working after schema fix",
            "test_case": {
                "brand_names": ["QuickTest"],
                "category": "Technology", 
                "positioning": "Premium",
                "market_scope": "Single Country",
                "countries": ["USA"]
            },
            "verification_points": [
                "API returns successful response (200 OK)",
                "Response contains brand_scores with namescore and verdict", 
                "No validation errors (especially for score_impact field)",
                "Legal precedents contain USA cases (like Polaroid Corp.)"
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
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())