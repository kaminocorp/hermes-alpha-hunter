---
description: "Provision isolated sandbox environments for safe security testing and exploit development"
tags: [security, infrastructure, sandboxing, testing]
created: 2026-03-15
---

# Sandbox Provisioning

## When to Use

Use this skill when you need isolated testing environments for:
- Exploit development and testing
- Safe vulnerability verification without affecting production systems  
- Complex multi-component application testing
- Network-level security testing requiring full system access
- Testing scenarios that require specific OS configurations or tools

## Prerequisites

- Confirm testing is within bounty program scope
- Verify explicit permission for any infrastructure provisioning
- Ensure sandbox environments are properly isolated from production networks

## Sandbox Options

### 1. Local Docker Containers (Preferred for most testing)

**Best for:** Application-level testing, quick exploit verification, dependency isolation

```bash
# Create isolated network for testing
docker network create hunter-sandbox

# Basic web application sandbox
docker run -d --name target-app \
  --network hunter-sandbox \
  -p 8080:8080 \
  <target-application-image>

# Attack platform container with tools
docker run -it --name attacker \
  --network hunter-sandbox \
  -v /workspace:/workspace \
  kalilinux/kali-rolling bash

# Install testing tools in attack container
apt update && apt install -y \
  burpsuite \
  sqlmap \
  nmap \
  netcat \
  curl \
  python3-pip \
  git
```

### 2. Fly.io Temporary Machines (For complex scenarios)

**Best for:** Full OS access, network testing, long-running analysis

```bash
# Deploy temporary sandbox machine
cat > sandbox-fly.toml << 'EOF'
app = "hunter-sandbox-${RANDOM}"
primary_region = "sin"

[[vm]]
  size = "shared-cpu-2x" 
  memory = 2048

[env]
  DEBIAN_FRONTEND = "noninteractive"
EOF

# Build sandbox Dockerfile
cat > Dockerfile.sandbox << 'EOF'
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
  curl git python3 python3-pip nodejs npm \
  nmap netcat sqlmap burpsuite \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
CMD ["sleep", "infinity"]
EOF

# Deploy sandbox
flyctl apps create hunter-sandbox-${RANDOM}
flyctl deploy --dockerfile Dockerfile.sandbox
flyctl ssh console
```

### 3. Local VM with Networking (For advanced scenarios)

**Best for:** Full network isolation, OS-level testing, kernel exploits

```bash
# Create VirtualBox VM programmatically
VBoxManage createvm --name "HunterSandbox" --register
VBoxManage modifyvm "HunterSandbox" --memory 2048 --cpus 2
VBoxManage createhd --filename ~/VMs/HunterSandbox.vdi --size 20480
VBoxManage attachstorage "HunterSandbox" --port 0 --device 0 --type hdd --medium ~/VMs/HunterSandbox.vdi

# Create isolated network
VBoxManage hostonlyif create
VBoxManage modifyvm "HunterSandbox" --nic1 hostonly --hostonlyadapter1 vboxnet0
```

## Target Application Setup

### Building from Source Code

```bash
# Clone target repository to sandbox
cd /workspace/targets
git clone <repository-url> target-app
cd target-app

# Analyze build requirements
if [[ -f package.json ]]; then
  # Node.js application
  npm install
  npm start &
  TARGET_PORT=$(grep -r "listen" . | grep -oE "[0-9]+" | head -1)
  
elif [[ -f requirements.txt ]]; then
  # Python application
  pip install -r requirements.txt
  python app.py &
  TARGET_PORT=5000  # Common Flask default
  
elif [[ -f pom.xml ]]; then
  # Java application
  mvn install
  mvn spring-boot:run &
  TARGET_PORT=8080  # Common Spring Boot default
  
elif [[ -f Dockerfile ]]; then
  # Containerized application
  docker build -t target-app .
  docker run -d -P target-app
  TARGET_PORT=$(docker port $(docker ps -lq) | grep -oE "[0-9]+" | tail -1)
fi

echo "Target application running on port: $TARGET_PORT"
```

### Database Setup

```bash
# Set up test database with sample data
if grep -r "postgresql\|psql" . >/dev/null; then
  # PostgreSQL setup
  docker run -d --name test-postgres \
    --network hunter-sandbox \
    -e POSTGRES_PASSWORD=testpass \
    -e POSTGRES_DB=testdb \
    postgres:13
    
  # Create test data
  sleep 10
  docker exec test-postgres psql -U postgres -d testdb -c "
    CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR(50), email VARCHAR(100), role VARCHAR(20));
    INSERT INTO users (username, email, role) VALUES 
      ('admin', 'admin@test.com', 'administrator'),
      ('user1', 'user1@test.com', 'user'),
      ('user2', 'user2@test.com', 'user');
  "
  
elif grep -r "mysql" . >/dev/null; then
  # MySQL setup
  docker run -d --name test-mysql \
    --network hunter-sandbox \
    -e MYSQL_ROOT_PASSWORD=testpass \
    -e MYSQL_DATABASE=testdb \
    mysql:8.0
fi
```

## Testing Tool Configuration

### Burp Suite Configuration

```bash
# Configure Burp Suite for API testing
mkdir -p /workspace/burp-config
cat > /workspace/burp-config/project.json << 'EOF'
{
  "target": {
    "scope": {
      "include": [
        {
          "enabled": true,
          "host": "localhost",
          "port": "8080",
          "protocol": "http"
        }
      ]
    }
  },
  "scanner": {
    "audit_items": {
      "sql_injection": true,
      "command_injection": true,
      "xxe": true,
      "path_traversal": true
    }
  }
}
EOF

# Start Burp with project
burpsuite --project-file=/workspace/burp-config/project.json &
```

### SQLMap Configuration

```bash
# Set up SQLMap for database testing
mkdir -p /workspace/sqlmap-output

# Basic SQLMap config
cat > /workspace/sqlmap.conf << 'EOF'
[Target]
url = http://localhost:8080/vulnerable-endpoint?id=1

[Request]
cookie = session=test-cookie
headers = User-Agent: HunterBot/1.0

[Techniques]  
technique = BEUSTQ
threads = 1
batch = true

[Output]
output-dir = /workspace/sqlmap-output
EOF
```

## Network Monitoring

```bash
# Set up traffic capture for analysis
mkdir -p /workspace/network-capture

# Start packet capture
tcpdump -i any -w /workspace/network-capture/traffic.pcap \
  host localhost and port 8080 &
TCPDUMP_PID=$!

# Monitor HTTP traffic  
ngrep -d any -q -W byline "GET|POST" host localhost and port 8080 &
NGREP_PID=$!

# Create cleanup function
cleanup_monitoring() {
  kill $TCPDUMP_PID $NGREP_PID 2>/dev/null
  echo "Network monitoring stopped"
}
trap cleanup_monitoring EXIT
```

## Exploit Development Environment

### Python Exploit Template

```python
#!/usr/bin/env python3
"""
Exploit template for vulnerability testing
"""
import requests
import sys
import argparse
from urllib.parse import urljoin

class ExploitFramework:
    def __init__(self, target_url, debug=False):
        self.target_url = target_url.rstrip('/')
        self.session = requests.Session()
        self.debug = debug
        
    def log(self, message):
        if self.debug:
            print(f"[DEBUG] {message}")
            
    def exploit_sql_injection(self, endpoint, parameter, payload):
        """Test SQL injection vulnerabilities"""
        url = urljoin(self.target_url, endpoint)
        data = {parameter: payload}
        
        self.log(f"Testing SQL injection: {url} with payload: {payload}")
        response = self.session.post(url, data=data)
        
        # Check for SQL error signatures
        sql_errors = [
            "mysql_fetch", "ORA-", "PostgreSQL", "Warning: pg_",
            "valid MySQL result", "SQL syntax.*MySQL", "Warning.*mysql_.*"
        ]
        
        for error in sql_errors:
            if error.lower() in response.text.lower():
                return True, f"SQL error detected: {error}"
                
        return False, "No SQL injection detected"
        
    def exploit_idor(self, endpoint, id_param, test_ids):
        """Test Insecure Direct Object Reference"""
        results = []
        
        for test_id in test_ids:
            url = f"{self.target_url}/{endpoint}?{id_param}={test_id}"
            self.log(f"Testing IDOR: {url}")
            
            response = self.session.get(url)
            if response.status_code == 200:
                results.append((test_id, len(response.text)))
                
        return results

# Save exploit template
with open('/workspace/exploits/exploit-template.py', 'w') as f:
    f.write(exploit_template)
```

### Bash Testing Script Template

```bash
#!/bin/bash
# Automated vulnerability testing script

TARGET_URL="${1:-http://localhost:8080}"
OUTPUT_DIR="/workspace/exploits/$(basename $TARGET_URL)-$(date +%s)"

mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"

echo "Starting automated vulnerability testing against: $TARGET_URL"

# Test for SQL injection
echo "=== SQL Injection Tests ==="
sqlmap -u "$TARGET_URL/search?q=test" --batch --output-dir="$OUTPUT_DIR/sqlmap"

# Test for XSS
echo "=== XSS Tests ==="
curl -s "$TARGET_URL/search?q=<script>alert('xss')</script>" | grep -i script

# Test for directory traversal
echo "=== Directory Traversal Tests ==="
curl -s "$TARGET_URL/file?path=../../../etc/passwd" | head -10

# Test for SSRF
echo "=== SSRF Tests ==="
curl -s "$TARGET_URL/fetch?url=http://localhost:22" | head -10

echo "Testing complete. Results saved to: $OUTPUT_DIR"
```

## Cleanup and Teardown

```bash
# Function to safely cleanup sandbox environment
cleanup_sandbox() {
  echo "Cleaning up sandbox environment..."
  
  # Stop Docker containers
  docker stop $(docker ps -q --filter "network=hunter-sandbox") 2>/dev/null
  docker rm $(docker ps -aq --filter "network=hunter-sandbox") 2>/dev/null
  docker network rm hunter-sandbox 2>/dev/null
  
  # Cleanup Fly.io machines if used
  if [[ -f sandbox-fly.toml ]]; then
    flyctl apps destroy hunter-sandbox-* --yes 2>/dev/null
  fi
  
  # Archive test results
  if [[ -d /workspace/exploits ]]; then
    tar -czf "/workspace/sandbox-results-$(date +%s).tar.gz" /workspace/exploits/
  fi
  
  echo "Sandbox cleanup complete"
}

# Register cleanup on script exit
trap cleanup_sandbox EXIT
```

## Security Considerations

1. **Network Isolation**: Always isolate test environments from production networks
2. **Resource Limits**: Set appropriate CPU/memory limits to prevent resource exhaustion  
3. **Access Controls**: Ensure sandbox credentials don't grant access to production systems
4. **Data Protection**: Never use real user data in sandbox environments
5. **Monitoring**: Log all sandbox activities for audit purposes
6. **Cleanup**: Always clean up temporary infrastructure to avoid costs and security risks

## Example Usage

```bash
# 1. Set up sandbox environment
setup_docker_sandbox

# 2. Deploy target application
deploy_target_from_source /path/to/target/repo

# 3. Configure testing tools
setup_burp_suite
setup_sqlmap_config

# 4. Run automated tests
./automated-vuln-scan.sh http://localhost:8080

# 5. Develop custom exploits
python3 /workspace/exploits/custom-exploit.py --target localhost:8080

# 6. Cleanup (automatic on exit)
```

This approach provides comprehensive testing capabilities while maintaining proper isolation and security boundaries.