#!/usr/bin/env python3
"""
Hermes Alpha Hunter — API Server
Direct control interface for the Overseer to deploy missions and check status.

Overseer Communication Endpoints:
  POST /api/command     — Send direct instruction to Hunter (get response)
  POST /api/guidance    — Provide guidance/hints for current analysis
  POST /api/config      — Update Hunter configuration (model, params)
  GET  /api/session     — Get current session state
"""
import os
import asyncio
import json
import uuid
import glob
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from aiohttp import web, web_request
from aiohttp.web_response import Response


# Overseer API Token for authentication
OVERSEER_TOKEN = os.getenv("OVERSEER_API_TOKEN", "")


def _check_overseer_auth(request: web_request.Request) -> bool:
    """Validate Overseer API token from Authorization header"""
    if not OVERSEER_TOKEN:
        return True  # No token set = no auth required
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {OVERSEER_TOKEN}"


class HunterAPI:
    """API server for Hunter control and status"""
    
    def __init__(self):
        self.missions: Dict[str, dict] = {}
        self.status = "idle"
        self.mission_log_path = Path("/workspace/missions.log")
        self.log_subscribers: List[web.StreamResponse] = []
        self.recent_logs: List[dict] = []
        self.command_history: List[dict] = []
        self.hunter_session_id: Optional[str] = None
        
        # Ensure workspace exists
        Path("/workspace").mkdir(exist_ok=True)
    async def _validate_hunter_tools(self) -> List[str]:
        """Validate Hunter has all required tools configured"""
        errors = []
        
        # Check essential environment variables
        required_env_vars = [
            "OPENROUTER_API_KEY"
        ]
        
        for var in required_env_vars:
            if not os.getenv(var):
                errors.append(f"Missing {var}")
        
        # Basic tool availability check
        try:
            import subprocess
            result = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                errors.append("Hermes CLI not available or configured")
        except Exception as e:
            errors.append(f"Hermes CLI check failed: {e}")
            
        return errors

        
    async def deploy_mission(self, request: web_request.Request) -> Response:
        """Deploy a new mission to the Hunter"""
        try:
            data = await request.json()
            target = data.get("target", "")
            
            # BLOCKED TARGETS - Reject test/demo repos
            blocked_targets = [
                "juice-shop", "juiceshop", "owasp juice",
                "dvwa", "damn vulnerable web",
                "webgoat", "owasp webgoat",
                "vulnerable-by-design", "intentionally vulnerable",
                "test-target", "test-targets", "demo-target"
            ]
            
            target_lower = target.lower()
            for blocked in blocked_targets:
                if blocked in target_lower:
                    return web.json_response({
                        "success": False,
                        "error": f"BLOCKED: '{target}' is a test/demo repo. Hunter only tests REAL bounty programs. Assign a target with an active bounty (HackerOne, Bugcrowd, etc.)."
                    }, status=400)
            
            # Require bounty_program field for real targets
            if not data.get("bounty_program"):
                return web.json_response({
                    "success": False,
                    "error": "MISSING BOUNTY PROGRAM: All missions must have a verified bounty program. Include 'bounty_program' field with program name (e.g., 'Mattermost Bug Bounty (HackerOne)')."
                }, status=400)
            
            mission_id = str(uuid.uuid4())
            
            mission = {
                "id": mission_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "deployed",
                "target": target,
                "bounty_program": data.get("bounty_program"), 
                "repository": data.get("repository"),
                "objectives": data.get("objectives", []),
                "scope_verification": data.get("scope_verification", []),
                "rules": data.get("rules", []),
                "bounty_range": data.get("bounty_range"),
                "progress": []
            }
            
            self.missions[mission_id] = mission
            
            # Log the mission
            with open(self.mission_log_path, "a") as f:
                f.write(f"{datetime.utcnow().isoformat()} DEPLOY {mission_id} {target} [{data.get('bounty_program')}]\n")
            
            # Deploy mission to Hunter Agent via subprocess
            asyncio.create_task(self._execute_mission(mission_id))
            self.status = "mission_active"
            
            return web.json_response({
                "success": True,
                "mission_id": mission_id,
                "status": "deployed"
            })
            
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=400)
    
    async def get_status(self, request: web_request.Request) -> Response:
        """Get Hunter status and active missions"""
        return web.json_response({
            "status": self.status,
            "active_missions": len([m for m in self.missions.values() if m["status"] in ["deployed", "active"]]),
            "total_missions": len(self.missions),
            "uptime": datetime.utcnow().isoformat()
        }, headers={
            'Access-Control-Allow-Origin': '*'
        })
    
    async def get_mission(self, request: web_request.Request) -> Response:
        """Get specific mission details"""
        mission_id = request.match_info.get("mission_id")
        
        if mission_id not in self.missions:
            return web.json_response({
                "success": False,
                "error": "Mission not found"
            }, status=404)
        
        return web.json_response({
            "success": True,
            "mission": self.missions[mission_id]
        })
    
    async def list_missions(self, request: web_request.Request) -> Response:
        """List all missions"""
        return web.json_response({
            "success": True,
            "missions": list(self.missions.values())
        })

    async def _execute_mission(self, mission_id: str):
        """Execute mission using Hunter Agent with crash recovery"""
        mission = self.missions[mission_id]
        
        try:
            # Update mission status
            mission["status"] = "active"
            mission["started_at"] = datetime.utcnow().isoformat()
            
            # Broadcast mission start
            await self.broadcast_log(f"Mission {mission_id[:8]} started: {mission.get('target', 'Unknown')}", "info")
            
            # Build Hunter prompt with stability focus
            hunter_prompt = self._build_hunter_prompt(mission)
            
            # Execute with crash recovery and persistence
            await self._run_hunter_with_recovery(mission_id, hunter_prompt)
            
            # Broadcast mission completion
            status = mission.get("status", "unknown")
            await self.broadcast_log(f"Mission {mission_id[:8]} completed with status: {status}", "info" if status == "completed" else "warning")
            
        except Exception as e:
            mission["status"] = "failed"
            mission["error"] = str(e)
            print(f"[!] Mission {mission_id} failed: {e}")
            await self.broadcast_log(f"Mission {mission_id[:8]} failed: {str(e)}", "error")

    def _build_hunter_prompt(self, mission: dict) -> str:
        """Build comprehensive Hunter prompt with crash recovery instructions"""
        return f"""
MISSION {mission['id']}: VULNERABILITY DISCOVERY

TARGET: {mission['target']}
BOUNTY PROGRAM: {mission['bounty_program']}
REPOSITORY: {mission.get('repository', 'N/A')}
BOUNTY RANGE: {mission.get('bounty_range', 'N/A')}

*** CRITICAL STABILITY PROTOCOL ***
1. NEVER use git clone - crashes DeepSeek-V3. Use web_extract for code analysis.
2. Save intermediate findings immediately using write_file to /workspace/mission_{mission['id']}/
3. Generate partial reports every 10 minutes as checkpoint files
4. If you discover ANY vulnerability, write it to /workspace/mission_{mission['id']}/vuln_{{id}}.md immediately
5. Use session timeouts of max 300 seconds to prevent hangs

*** REPORT WRITING PROTOCOL - CRITICAL ***
When you discover a vulnerability, write the report in SECTIONS to avoid truncation:
1. First write the header + title + summary (use write_file with overwrite=False to create)
2. Then APPEND each section separately (Description, PoC, Impact, Remediation)
3. NEVER write the entire report in one call - split into 3-4 separate write operations
4. Each section must be complete before moving to the next
5. Target report size: 2000-5000 bytes minimum for a complete finding

*** VULNERABILITY REPORT TEMPLATE - MANDATORY ***
Every vulnerability report MUST follow this exact structure. Copy this template:

```markdown
# Vulnerability Report

**Mission ID:** {mission['id']}
**Target:** {mission['target']}
**Bounty Program:** {mission['bounty_program']}
**Repository:** {mission.get('repository', 'N/A')}
**Discovery Date:** YYYY-MM-DD
**Report ID:** VULN-{{sequential_number}}
---

## Executive Summary

{{2-3 sentences describing the vulnerability in plain language. What is it? Where is it? Why does it matter?}}

## Severity Assessment

**CVSS Score:** {{e.g., 7.5 High}}
**Bounty Severity:** {{Low/Medium/High/Critical}}
**Likelihood:** {{Easy/Moderate/Difficult to exploit}}
**Impact:** {{What an attacker can achieve}}

## Vulnerability Details

### Affected Component

**File(s):** `{{path/to/file.go}}`
**Function(s):** `{{functionName()}}`
**Line Numbers:** {{start-end}}
**API Endpoint:** `{{/api/v4/endpoint}}` (if applicable)

### Root Cause

{{Explain WHY this vulnerability exists. What assumption was wrong? What check is missing? What validation is insufficient?}}

### Technical Description

{{Detailed explanation of the vulnerability mechanism. Include code snippets showing the vulnerable code.}}

```go
{{// Vulnerable code snippet - 10-20 lines showing the issue}}
```

## Proof of Concept

### Prerequisites

- {{What the attacker needs: user account, specific permissions, etc.}}

### Attack Steps

1. {{Step 1: specific action}}
2. {{Step 2: specific action}}
3. {{Step 3: what happens}}
4. {{Step 4: the exploit succeeds}}

### HTTP Request/Response (if applicable)

```http
POST /api/v4/vulnerable-endpoint HTTP/1.1
Host: target.com
Authorization: Bearer {{token}}

{{request_body}}
```

```http
HTTP/1.1 200 OK
{{response showing the vulnerability}}
```

### Exploit Code (if applicable)

```bash
{{curl command or script that demonstrates the vulnerability}}
```

## Impact Analysis

### What Attackers Can Achieve

- {{Specific capability 1}}
- {{Specific capability 2}}
- {{Specific capability 3}}

### Business Impact

{{How this affects the target organization: data breach, account takeover, financial loss, reputation damage, etc.}}

### Affected Users

{{Who is impacted: all users, admins only, specific roles, etc.}}

## Reproduction Steps

{{Numbered list that anyone can follow to reproduce this vulnerability in a test environment}}

1. {{Step 1}}
2. {{Step 2}}
3. {{Step 3}}
4. {{Verify the vulnerability}}

## Remediation Recommendations

### Immediate Fix

{{Code-level fix with example}}

```go
{{// Fixed code snippet showing proper validation/checks}}
```

### Additional Hardening

- {{Additional security measure 1}}
- {{Additional security measure 2}}
- {{Additional security measure 3}}

## References

- {{Relevant OWASP Top 10 category}}
- {{Similar CVEs or security advisories}}
- {{Framework documentation links}}

## Appendix: Full Code Context

{{If helpful, include 30-50 lines of surrounding code for full context}}
```

---

## OBJECTIVES

{chr(10).join(f"- {obj}" for obj in mission.get('objectives', []))}

---

## METHODOLOGY

### Phase 1: Repository Analysis (NO GIT CLONE - use web_extract)
- Extract source code from GitHub/GitLab web interface  
- Map application structure and entry points
- Identify authentication and authorization mechanisms

### Phase 2: Vulnerability Discovery
- Focus on: {', '.join(['Authentication bypasses', 'IDOR', 'Privilege escalation', 'API vulnerabilities', 'SSRF in integrations/webhooks', 'XSS vectors'])}
- For EACH finding: write a COMPLETE report following the template above
- Generate PoC for each vulnerability (sandbox only - NEVER test against production)

### Phase 3: Report Generation  
- Ensure every report has ALL sections from the template
- Minimum report size: 2000 bytes (reject incomplete reports)
- Save all reports to /workspace/mission_{mission['id']}/ for persistence

---

## AUTONOMOUS OPERATION PROTOCOL

You are operating autonomously. Do NOT ask for user input or guidance. Complete all phases automatically:

1. Analyze authentication mechanisms (JWT, OAuth, session handling, SSO)
2. Review API endpoints for IDOR vulnerabilities (check userId, channelId, teamId parameters)
3. Check privilege escalation paths (role changes, permission checks, admin functions)
4. Examine webhooks/integrations for SSRF (URL parameters, outgoing requests)
5. Look for XSS vectors (user input rendered without escaping)
6. For EACH vulnerability found: write a COMPLETE report using the template above

**CRITICAL**: Write reports in SECTIONS using multiple write_file calls:
- Call 1: Header + Executive Summary + Severity
- Call 2: Vulnerability Details + Root Cause + Code Snippets  
- Call 3: PoC + Impact Analysis
- Call 4: Remediation + References

**DO NOT** write the entire report in one write_file call - it will truncate.

---

## QUALITY STANDARDS

A report is NOT complete until it has:
✅ Executive Summary (what/where/why)
✅ Severity Assessment (CVSS score, bounty severity)
✅ Affected Component (files, functions, lines, endpoints)
✅ Root Cause Explanation (why the bug exists)
✅ Technical Description with code snippets
✅ Proof of Concept (steps + HTTP requests or exploit code)
✅ Impact Analysis (what attackers achieve, business impact)
✅ Reproduction Steps (numbered, reproducible)
✅ Remediation Recommendations (with fixed code example)
✅ Minimum 2000 bytes total

If any section is missing, the report is INCOMPLETE. Go back and fill it in.

---

Continue analyzing through ALL objectives without stopping for input. Make decisions autonomously.
When you find a vulnerability, STOP analysis and write the COMPLETE report BEFORE continuing.
"""

    async def _run_hunter_with_recovery(self, mission_id: str, prompt: str):
        """Run Hunter Agent with crash detection and recovery"""
        mission = self.missions[mission_id]
        
        # Create workspace directories
        workspace_dir = Path(f"/workspace/mission_{mission_id}")
        workspace_dir.mkdir(exist_ok=True)
        
        # Save mission prompt for recovery
        with open(workspace_dir / "mission_prompt.txt", "w") as f:
            f.write(prompt)
        
        # Pre-flight tool validation
        tool_validation_errors = await self._validate_hunter_tools()
        if tool_validation_errors:
            mission["status"] = "failed"
            mission["error"] = f"Tool validation failed: {', '.join(tool_validation_errors)}"
            print(f"[!] Mission {mission_id} failed tool validation: {mission['error']}")
            return

        # Inject Elephantasm memory at mission start
        elephantasm_memory = await self._inject_elephantasm_memory()
        if elephantasm_memory:
            prompt = elephantasm_memory + "\n\n" + prompt
            await self.broadcast_log(f"Elephantasm memory injected: {len(elephantasm_memory)} chars", "info")

        # Run Hunter Agent subprocess with timeout and monitoring
        # Note: Using -q for single query mode with the full mission prompt
        # The Hunter's SOUL.md and skills provide the methodology context
        # Using qwen3.5-plus which is confirmed available on OpenRouter
        # Ensure Elephantasm env vars are explicitly passed (critical for memory capture)
        hunter_env = {
            **dict(os.environ),
            'HERMES_SESSION_TYPE': 'hunter',
            'HERMES_MISSION_ID': mission_id,
            'HERMES_WORKSPACE': f'/workspace/mission_{mission_id}',
            'HERMES_HOME': '/root/.hermes'
        }
        
        # Explicitly ensure Elephantasm credentials are inherited
        # These are set as Fly.io secrets and must be passed to subprocess
        elephantasm_key = os.getenv('ELEPHANTASM_API_KEY')
        elephantasm_id = os.getenv('ELEPHANTASM_ANIMA_ID')
        
        # Log debug info about Elephantasm config
        import sys
        sys.stdout.flush()
        print(f"[DEBUG] Parent process - Elephantasm API key: {'SET' if elephantasm_key else 'MISSING'}")
        print(f"[DEBUG] Parent process - Elephantasm Anima ID: {elephantasm_id or 'MISSING'}")
        print(f"[DEBUG] hunter_env has ELEPHANTASM_API_KEY: {'ELEPHANTASM_API_KEY' in hunter_env}")
        print(f"[DEBUG] hunter_env has ELEPHANTASM_ANIMA_ID: {'ELEPHANTASM_ANIMA_ID' in hunter_env}")
        sys.stdout.flush()
        
        if elephantasm_key:
            hunter_env['ELEPHANTASM_API_KEY'] = elephantasm_key
        if elephantasm_id:
            hunter_env['ELEPHANTASM_ANIMA_ID'] = elephantasm_id
        
        print(f"[DEBUG] After assignment - ELEPHANTASM_API_KEY in hunter_env: {'ELEPHANTASM_API_KEY' in hunter_env}")
        print(f"[DEBUG] After assignment - ELEPHANTASM_ANIMA_ID in hunter_env: {'ELEPHANTASM_ANIMA_ID' in hunter_env}")
        sys.stdout.flush()
        
        # Note: Remove -Q to get verbose output including Elephantasm events
        # Quiet mode suppresses all logger output including Elephantasm extraction logs
        # Test: Write Hunter's environment to a file for debugging
        with open(f"/workspace/mission_{mission_id}/hunter_env.txt", "w") as f:
            for key, val in sorted(hunter_env.items()):
                if 'KEY' in key or 'TOKEN' in key or 'SECRET' in key:
                    f.write(f"{key}=***REDACTED***\n")
                else:
                    f.write(f"{key}={val}\n")
        
        print(f"[DEBUG] hunter_env written to /workspace/mission_{mission_id}/hunter_env.txt")
        import sys
        sys.stdout.flush()
        
        proc = await asyncio.create_subprocess_exec(
            "hermes", "chat",
            "-m", "qwen/qwen3.5-plus-02-15",
            "-q", prompt,
            "--yolo",
            # Removed -Q flag to allow Elephantasm extraction logs to appear in stdout
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/app",
            env=hunter_env
        )
        
        # Monitor process with timeout and stream logs
        start_time = datetime.utcnow()
        try:
            # Read stdout/stderr line by line for real-time streaming
            stdout_lines = []
            stderr_lines = []
            
            async def read_stream(stream, lines_list, prefix):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode()
                    lines_list.append(decoded)
                    # Also print to console for Fly.io logs
                    print(f"[{prefix}] {decoded.strip()}")
                    # Broadcast to SSE subscribers
                    await self.broadcast_log(f"{prefix}: {decoded.strip()}", "info")
            
            # Run communicate and stream reading concurrently
            stdout_task = asyncio.create_task(read_stream(proc.stdout, stdout_lines, "HUNTER"))
            stderr_task = asyncio.create_task(read_stream(proc.stderr, stderr_lines, "ERROR"))
            
            # Wait for process with timeout
            await asyncio.wait_for(proc.wait(), timeout=3600)
            await stdout_task
            await stderr_task
            
            stdout = b''.join([l.encode() for l in stdout_lines])
            stderr = b''.join([l.encode() for l in stderr_lines])
            
            # Check for completion status based on actual work done
            runtime_seconds = (datetime.utcnow() - start_time).total_seconds()
            
            # Extract to Elephantasm at mission end
            await self._extract_elephantasm_memory(mission_id, stdout.decode(), stderr.decode())
            
            reports = list(workspace_dir.glob("vuln_*.md"))
            valid_reports = []
            invalid_reports = []
            
            for report_file in reports:
                file_size = report_file.stat().st_size
                if file_size < 1000:
                    invalid_reports.append((report_file.name, file_size, "Too small (<1000 bytes)"))
                else:
                    with open(report_file, 'r') as f:
                        content = f.read()
                    # Check for required sections
                    required_sections = [
                        "Executive Summary",
                        "Severity",
                        "Vulnerability Details",
                        "Proof of Concept",
                        "Impact",
                        "Remediation"
                    ]
                    missing = [s for s in required_sections if s not in content]
                    if missing:
                        invalid_reports.append((report_file.name, file_size, f"Missing sections: {', '.join(missing)}"))
                    else:
                        valid_reports.append(report_file)
            
            mission["reports_generated"] = len(valid_reports)
            mission["reports_invalid"] = len(invalid_reports)
            
            if valid_reports:
                await self.broadcast_log(f"Generated {len(valid_reports)} VALID vulnerability report(s)", "info")
            if invalid_reports:
                for name, size, reason in invalid_reports:
                    await self.broadcast_log(f"INVALID REPORT: {name} - {size} bytes - {reason}", "error")
                await self.broadcast_log(f"WARNING: {len(invalid_reports)} incomplete reports detected. Re-run analysis for these findings.", "warning")
            
            if valid_reports or proc.returncode == 0:
                mission["status"] = "completed"
                await self.broadcast_log(f"Mission analysis complete in {runtime_seconds:.1f}s", "info")
            elif runtime_seconds < 10:
                # Less than 10 seconds = likely crash or immediate failure
                print(f"[!] Mission {mission_id} completed suspiciously fast: {runtime_seconds}s")
                await self.broadcast_log(f"WARNING: Mission completed too quickly ({runtime_seconds}s)", "warning")
                mission["status"] = "failed"
                mission["error"] = f"Mission completed too quickly ({runtime_seconds}s < 10s minimum)"
                mission["runtime_warning"] = True
            else:
                mission["status"] = "completed"
                await self.broadcast_log(f"Mission analysis complete in {runtime_seconds:.1f}s", "info")
            
            if reports:
                await self.broadcast_log(f"Generated {len(reports)} vulnerability report(s)", "info")
            
            # Update mission with results
            mission["completed_at"] = datetime.utcnow().isoformat()
            mission["stdout"] = stdout.decode() if stdout else ""
            mission["stderr"] = stderr.decode() if stderr else ""
            mission["duration"] = f"{runtime_seconds:.1f}s"
            
            # Log Elephantasm status for debugging
            elephantasm_status = "ENABLED" if os.getenv('ELEPHANTASM_API_KEY') else "DISABLED (no API key)"
            anima_id = os.getenv('ELEPHANTASM_ANIMA_ID', 'NOT SET')
            await self.broadcast_log(f"Elephantasm: {elephantasm_status}, Anima: {anima_id}", "info")
            
        except asyncio.TimeoutError:
            proc.kill()
            mission["status"] = "timeout"
            await self.broadcast_log(f"Mission timed out after 1 hour", "error")
            print(f"[!] Mission {mission_id} timed out")
        except Exception as e:
            mission["status"] = "crashed" 
            mission["error"] = str(e)
            await self.broadcast_log(f"Mission crashed: {str(e)}", "error")
            print(f"[!] Mission {mission_id} crashed: {e}")
    
    async def _inject_elephantasm_memory(self) -> str:
        """Inject Elephantasm memory at mission start"""
        api_key = os.getenv('ELEPHANTASM_API_KEY')
        anima_id = os.getenv('ELEPHANTASM_ANIMA_ID')
        
        if not api_key or not anima_id:
            print("[Elephantasm] Not configured")
            return ""
        
        try:
            from elephantasm import Elephantasm
            client = Elephantasm(api_key=api_key, anima_id=anima_id)
            pack = client.inject()
            if pack:
                prompt_text = pack.as_prompt()
                client.close()
                if prompt_text.strip():
                    print(f"[Elephantasm] Injected: {pack.token_count} tokens")
                    return prompt_text
            client.close()
            return ""
        except Exception as e:
            print(f"[Elephantasm] Inject failed: {e}")
            return ""
    
    async def _extract_elephantasm_memory(self, mission_id: str, stdout: str, stderr: str) -> None:
        """Extract mission summary to Elephantasm"""
        api_key = os.getenv('ELEPHANTASM_API_KEY')
        anima_id = os.getenv('ELEPHANTASM_ANIMA_ID')
        
        if not api_key or not anima_id:
            return
        
        try:
            from elephantasm import Elephantasm, EventType
            client = Elephantasm(api_key=api_key, anima_id=anima_id)
            summary = f"Mission {mission_id[:8]} completed"
            if "vuln_" in stdout:
                count = stdout.count("vuln_")
                summary += f". Generated {count} vulnerability reports"
            client.extract(EventType.SYSTEM, summary[:2000], meta={"mission_id": mission_id})
            client.close()
            print(f"[Elephantasm] Extracted mission summary")
        except Exception as e:
            print(f"[Elephantasm] Extract failed: {e}")
    
    async def get_health(self, request: web_request.Request) -> Response:
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "uptime": datetime.utcnow().isoformat(),
            "active_missions": len([m for m in self.missions.values() if m["status"] == "active"]),
            "version": "v13"
        })

    async def get_session_status(self, request: web_request.Request) -> Response:
        """Session status endpoint"""
        active_missions = [m for m in self.missions.values() if m["status"] == "active"]
        return web.json_response({
            "status": "active" if active_missions else "idle",
            "active_missions": active_missions,
            "total_vulnerabilities": sum(m.get("reports_generated", 0) for m in self.missions.values())
        })

    async def get_session_messages(self, request: web_request.Request) -> Response:
        """Get session messages (mission logs)"""
        limit = int(request.query.get('limit', 50))
        
        # Read mission log
        messages = []
        if self.mission_log_path.exists():
            with open(self.mission_log_path, 'r') as f:
                lines = f.readlines()[-limit:]
                for line in lines:
                    parts = line.strip().split(' ', 3)
                    if len(parts) >= 3:
                        messages.append({
                            "timestamp": parts[0],
                            "role": "system", 
                            "content": ' '.join(parts[1:])
                        })
        
        return web.json_response({"messages": messages})

    async def get_vulnerabilities(self, request: web_request.Request) -> Response:
        """Get all discovered vulnerabilities from workspace files"""
        vulnerabilities = []
        
        # Search all mission workspaces for vuln files
        for vuln_file in Path("/workspace").glob("**/vuln_*.md"):
            try:
                with open(vuln_file, 'r') as f:
                    content = f.read()
                
                # Extract metadata from filename
                filename = vuln_file.name
                vuln_id = filename.replace('vuln_', '').replace('.md', '')
                
                vulnerabilities.append({
                    "id": vuln_id,
                    "file": str(vuln_file),
                    "mission_id": vuln_file.parent.name.replace('mission_', ''),
                    "discovered_at": datetime.fromtimestamp(vuln_file.stat().st_mtime).isoformat(),
                    "preview": content[:200] + "..." if len(content) > 200 else content
                })
            except Exception as e:
                print(f"Error reading vulnerability file {vuln_file}: {e}")
        
        return web.json_response({
            "success": True,
            "count": len(vulnerabilities),
            "vulnerabilities": vulnerabilities
        })

    async def get_vulnerability(self, request: web_request.Request) -> Response:
        """Get specific vulnerability report"""
        vuln_id = request.match_info.get("vuln_id")
        
        # Search for the vulnerability file
        vuln_file = None
        for f in Path("/workspace").glob(f"**/vuln_{vuln_id}.md"):
            vuln_file = f
            break
        
        if not vuln_file:
            return web.json_response({
                "success": False,
                "error": "Vulnerability not found"
            }, status=404)
        
        try:
            with open(vuln_file, 'r') as f:
                content = f.read()
            
            # Extract mission_id from path
            mission_id = vuln_file.parent.name.replace('mission_', '')
            mission = self.missions.get(mission_id, {})
            
            return web.json_response({
                "success": True,
                "id": vuln_id,
                "file": str(vuln_file),
                "mission_id": mission_id,
                "target_context": {
                    "target": mission.get("target", "Unknown"),
                    "bounty_program": mission.get("bounty_program", "Unknown"),
                    "repository": mission.get("repository", "N/A")
                },
                "content": content,
                "discovered_at": datetime.fromtimestamp(vuln_file.stat().st_mtime).isoformat()
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def get_reports(self, request: web_request.Request) -> Response:
        """Get all vulnerability reports with full mission context"""
        reports = []
        
        # Search all mission workspaces for report files
        for report_file in Path("/workspace").glob("**/*.md"):
            if not report_file.name.startswith(("vuln_", "MISSION_", "QUICK_")):
                continue
                
            try:
                with open(report_file, 'r') as f:
                    content = f.read()
                
                # Extract mission_id from path
                mission_id = report_file.parent.name.replace('mission_', '')
                mission = self.missions.get(mission_id, {})
                
                reports.append({
                    "file": str(report_file),
                    "filename": report_file.name,
                    "mission_id": mission_id,
                    "target_context": {
                        "target": mission.get("target", "Unknown"),
                        "bounty_program": mission.get("bounty_program", "Unknown"),
                        "repository": mission.get("repository", "N/A"),
                        "mission_objectives": mission.get("objectives", [])
                    },
                    "discovered_at": datetime.fromtimestamp(report_file.stat().st_mtime).isoformat(),
                    "preview": content[:300] + "..." if len(content) > 300 else content
                })
            except Exception as e:
                print(f"Error reading report file {report_file}: {e}")
        
        return web.json_response({
            "success": True,
            "count": len(reports),
            "reports": reports
        })

    async def get_metrics(self, request: web_request.Request) -> Response:
        """Get real-time system and performance metrics"""
        # Collect metrics
        active_missions = [m for m in self.missions.values() if m["status"] == "active"]
        completed_missions = [m for m in self.missions.values() if m["status"] == "completed"]
        failed_missions = [m for m in self.missions.values() if m["status"] in ["failed", "timeout", "crashed"]]
        
        # Count vulnerabilities
        vuln_count = len(list(Path("/workspace").glob("**/vuln_*.md")))
        
        # Build metrics response
        metrics = {
            "status": "healthy",
            "uptime": datetime.utcnow().isoformat(),
            "missions": {
                "active": len(active_missions),
                "completed": len(completed_missions),
                "failed": len(failed_missions),
                "total": len(self.missions)
            },
            "vulnerabilities": {
                "total": vuln_count
            },
            "performance": {
                "avg_mission_duration": self._calculate_avg_duration(completed_missions),
                "success_rate": self._calculate_success_rate()
            },
            "system": {
                "workspace_size_mb": self._get_workspace_size(),
                "log_entries": len(self.recent_logs)
            }
        }
        
        return web.json_response(metrics, headers={
            'Access-Control-Allow-Origin': '*'
        })

    def _calculate_avg_duration(self, completed_missions: List[dict]) -> str:
        """Calculate average mission duration"""
        if not completed_missions:
            return "N/A"
        
        durations = []
        for m in completed_missions:
            if "duration" in m:
                try:
                    # Parse duration string like "123.4s"
                    dur = float(m["duration"].replace("s", ""))
                    durations.append(dur)
                except:
                    pass
        
        if not durations:
            return "N/A"
        
        avg = sum(durations) / len(durations)
        return f"{avg:.1f}s"

    def _calculate_success_rate(self) -> str:
        """Calculate mission success rate"""
        total = len(self.missions)
        if total == 0:
            return "N/A"
        
        completed = len([m for m in self.missions.values() if m["status"] == "completed"])
        rate = (completed / total) * 100
        return f"{rate:.1f}%"

    def _get_workspace_size(self) -> float:
        """Get total workspace size in MB"""
        total_size = 0
        for path in Path("/workspace").rglob("*"):
            if path.is_file():
                total_size += path.stat().st_size
        return round(total_size / (1024 * 1024), 2)

    async def stream_logs(self, request: web_request.Request) -> Response:
        """Server-Sent Events endpoint for real-time log streaming"""
        response = web.StreamResponse(
            status=200,
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
            }
        )
        await response.prepare(request)
        
        # Add to subscribers list
        self.log_subscribers.append(response)
        
        # Send recent logs buffer to new subscriber
        for log_entry in self.recent_logs[-50:]:  # Last 50 entries
            await response.write(f"data: {json.dumps(log_entry)}\n\n".encode())
        
        try:
            # Keep connection open - client will close
            while True:
                await asyncio.sleep(0.5)
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            # Remove from subscribers
            if response in self.log_subscribers:
                self.log_subscribers.remove(response)
        
        return response

    async def broadcast_log(self, message: str, log_type: str = "info"):
        """Broadcast a log message to all SSE subscribers"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": log_type,
            "message": message
        }
        
        # Add to buffer
        self.recent_logs.append(log_entry)
        if len(self.recent_logs) > 1000:
            self.recent_logs = self.recent_logs[-1000:]  # Keep last 1000
        
        # Broadcast to subscribers
        dead_subscribers = []
        for subscriber in self.log_subscribers:
            try:
                await subscriber.write(f"data: {json.dumps(log_entry)}\n\n".encode())
            except Exception:
                dead_subscribers.append(subscriber)
        
        # Clean up dead connections
        for sub in dead_subscribers:
            if sub in self.log_subscribers:
                self.log_subscribers.remove(sub)

    async def cancel_mission(self, request: web_request.Request) -> Response:
        """Cancel an active mission"""
        mission_id = request.match_info.get("mission_id")
        
        if mission_id not in self.missions:
            return web.json_response({
                "success": False,
                "error": "Mission not found"  
            }, status=404)
        
        self.missions[mission_id]["status"] = "cancelled"
        self.missions[mission_id]["cancelled_at"] = datetime.utcnow().isoformat()
        
        return web.json_response({
            "success": True,
            "message": f"Mission {mission_id} cancelled"
        })

    async def send_command(self, request: web_request.Request) -> Response:
        """
        Send a direct command/instruction to the Hunter agent.
        
        Body: {
            "command": "your instruction",
            "timeout": 300,  # optional, max 600
            "priority": "normal"  # or "high" for urgent
        }
        
        Returns: {
            "status": "ok|timeout|error",
            "response": "agent's reply",
            "command_id": "..."
        }
        """
        if not _check_overseer_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        
        command_text = body.get("command", "").strip()
        if not command_text:
            return web.json_response({"error": "empty command"}, status=400)
        
        timeout = min(body.get("timeout", 300), 600)
        priority = body.get("priority", "normal")
        command_id = str(uuid.uuid4())
        
        # Log the command
        cmd_entry = {
            "command_id": command_id,
            "timestamp": datetime.utcnow().isoformat(),
            "command": command_text,
            "priority": priority,
            "timeout": timeout
        }
        self.command_history.append(cmd_entry)
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]
        
        await self.broadcast_log(f"[OVERSEER COMMAND] {command_text[:100]}...", "info")
        
        # Execute command via hermes chat
        try:
            # Build the command prompt
            prompt = f"""[OVERSEER DIRECTIVE - PRIORITY: {priority.upper()}]

The Overseer has issued a direct command. Follow this instruction immediately:

{command_text}

Acknowledge receipt and execute this command. Report back your actions."""
            
            # Get current active mission context
            active_mission = None
            for m in self.missions.values():
                if m.get("status") in ["active", "deployed"]:
                    active_mission = m
                    break
            
            if active_mission:
                prompt = f"""Context: You are on mission {active_mission['id'][:8]} analyzing {active_mission.get('target', 'unknown')}

{prompt}"""
            
            # Run hermes chat with the command
            proc = await asyncio.create_subprocess_exec(
                "hermes", "chat",
                "-m", "qwen/qwen3.5-plus-02-15",
                "-q", prompt,
                "--yolo",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="/app",
                env=os.environ
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                response = stdout.decode() if stdout else ""
                
                return web.json_response({
                    "status": "ok",
                    "command_id": command_id,
                    "response": response[:5000] if response else "(no output)",
                    "exit_code": proc.returncode
                })
                
            except asyncio.TimeoutError:
                await self.broadcast_log(f"[OVERSEER COMMAND TIMEOUT] Command {command_id[:8]} exceeded {timeout}s", "warning")
                proc.kill()
                return web.json_response({
                    "status": "timeout",
                    "command_id": command_id,
                    "response": f"Command timed out after {timeout}s. Hunter may still be processing."
                }, status=504)
                
        except Exception as e:
            await self.broadcast_log(f"[OVERSEER COMMAND ERROR] {str(e)}", "error")
            return web.json_response({
                "status": "error",
                "command_id": command_id,
                "error": str(e)
            }, status=500)

    async def send_guidance(self, request: web_request.Request) -> Response:
        """
        Provide guidance/hints to the Hunter for current analysis.
        Less urgent than commands - adds context rather than direct orders.
        
        Body: {"guidance": "your hints/context", "area": "optional focus area"}
        """
        if not _check_overseer_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        
        guidance_text = body.get("guidance", "").strip()
        area = body.get("area", "general")
        
        if not guidance_text:
            return web.json_response({"error": "empty guidance"}, status=400)
        
        guidance_id = str(uuid.uuid4())
        
        # Write guidance to a file the Hunter can read
        guidance_file = Path("/workspace/overseer_guidance.json")
        guidance_data = {
            "guidance_id": guidance_id,
            "timestamp": datetime.utcnow().isoformat(),
            "area": area,
            "guidance": guidance_text
        }
        
        # Append to existing guidance or create new
        existing = []
        if guidance_file.exists():
            try:
                with open(guidance_file) as f:
                    existing = json.load(f)
            except:
                existing = []
        
        existing.append(guidance_data)
        if len(existing) > 20:
            existing = existing[-20:]
        
        with open(guidance_file, "w") as f:
            json.dump(existing, f, indent=2)
        
        await self.broadcast_log(f"[OVERSEER GUIDANCE] Area: {area} - {guidance_text[:80]}...", "info")
        
        return web.json_response({
            "status": "ok",
            "guidance_id": guidance_id,
            "message": "Guidance saved. Hunter will read on next iteration."
        })

    async def update_config(self, request: web_request.Request) -> Response:
        """
        Update Hunter configuration dynamically.
        
        Body: {
            "model": "deepseek/deepseek-chat-v3-0324",  # optional
            "reasoning_effort": "high",  # optional
            "max_turns": 100  # optional
        }
        """
        if not _check_overseer_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        
        config_path = Path("/root/.hermes/config.yaml")
        if not config_path.exists():
            return web.json_response({"error": "config file not found"}, status=500)
        
        import yaml
        
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            changes = []
            
            # Update model settings
            if "model" in body:
                if "model" not in config:
                    config["model"] = {}
                config["model"]["default"] = body["model"]
                changes.append(f"model={body['model']}")
            
            if "reasoning_effort" in body:
                if "agent" not in config:
                    config["agent"] = {}
                config["agent"]["reasoning_effort"] = body["reasoning_effort"]
                changes.append(f"reasoning_effort={body['reasoning_effort']}")
            
            if "max_turns" in body:
                if "agent" not in config:
                    config["agent"] = {}
                config["agent"]["max_turns"] = body["max_turns"]
                changes.append(f"max_turns={body['max_turns']}")
            
            if not changes:
                return web.json_response({"error": "no valid config keys provided"}, status=400)
            
            # Write updated config
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            
            await self.broadcast_log(f"[CONFIG UPDATE] {', '.join(changes)}", "info")
            
            return web.json_response({
                "status": "ok",
                "changes": changes,
                "message": "Config updated. Takes effect on next Hunter invocation."
            })
            
        except Exception as e:
            return web.json_response({"error": f"config update failed: {e}"}, status=500)

    async def get_session(self, request: web_request.Request) -> Response:
        """Get current Hunter session state"""
        if not _check_overseer_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        
        sessions_dir = Path("/root/.hermes/sessions")
        active_sessions = []
        
        if sessions_dir.exists():
            for f in sessions_dir.glob("*.json"):
                try:
                    with open(f) as sf:
                        data = json.load(sf)
                        active_sessions.append({
                            "session_id": f.stem,
                            "last_activity": data.get("last_activity", "unknown"),
                            "message_count": len(data.get("messages", []))
                        })
                except:
                    pass
        
        return web.json_response({
            "active_sessions": active_sessions,
            "command_history": self.command_history[-20:],
            "hunter_status": self.status
        })




# CORS headers for all responses
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}

async def create_app() -> web.Application:
    """Create the aiohttp application"""
    hunter_api = HunterAPI()
    
    app = web.Application()
    
    # Add CORS middleware that wraps responses
    @web.middleware
    async def cors_middleware(request, handler):
        try:
            resp = await handler(request)
            # Add CORS headers to all responses
            for key, value in CORS_HEADERS.items():
                resp.headers[key] = value
            return resp
        except web.HTTPException as e:
            # Also add CORS to error responses
            for key, value in CORS_HEADERS.items():
                if key not in e.headers:
                    e.headers[key] = value
            raise
    
    app.middlewares.append(cors_middleware)
    
    # Routes
    app.router.add_post("/api/missions", hunter_api.deploy_mission)
    app.router.add_get("/api/status", hunter_api.get_status)
    app.router.add_get("/api/missions", hunter_api.list_missions)
    app.router.add_get("/api/missions/{mission_id}", hunter_api.get_mission)
    app.router.add_delete("/api/missions/{mission_id}", hunter_api.cancel_mission)
    app.router.add_get("/health", hunter_api.get_health)
    app.router.add_get("/session/status", hunter_api.get_session_status)
    app.router.add_get("/session/messages", hunter_api.get_session_messages)
    
    # New endpoints for live data
    app.router.add_get("/api/vulnerabilities", hunter_api.get_vulnerabilities)
    app.router.add_get("/api/vulnerabilities/{vuln_id}", hunter_api.get_vulnerability)
    app.router.add_get("/api/reports", hunter_api.get_reports)
    app.router.add_get("/api/metrics", hunter_api.get_metrics)
    app.router.add_get("/api/logs/stream", hunter_api.stream_logs)
    
    # Overseer direct communication endpoints
    app.router.add_post("/api/command", hunter_api.send_command)
    app.router.add_post("/api/guidance", hunter_api.send_guidance)
    app.router.add_post("/api/config", hunter_api.update_config)
    app.router.add_get("/api/session", hunter_api.get_session)
    
    return app


async def main():
    """Main function to start the API server"""
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    print(f"[*] Hunter API starting on http://0.0.0.0:8080")
    await site.start()
    
    # Keep the server running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("[*] Hunter API shutting down...")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())