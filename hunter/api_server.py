#!/usr/bin/env python3
"""
Hermes Alpha Hunter — API Server
Direct control interface for the Overseer to deploy missions and check status.
"""
import os
import asyncio
import json
import uuid
import glob
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from aiohttp import web, web_request
from aiohttp.web_response import Response


class HunterAPI:
    """API server for Hunter control and status"""
    
    def __init__(self):
        self.missions: Dict[str, dict] = {}
        self.status = "idle"
        self.mission_log_path = Path("/workspace/missions.log")
        self.log_subscribers: List[web.StreamResponse] = []
        self.recent_logs: List[dict] = []  # In-memory log buffer for new subscribers
        
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
            mission_id = str(uuid.uuid4())
            
            mission = {
                "id": mission_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "deployed",
                "target": data.get("target"),
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
                f.write(f"{datetime.utcnow().isoformat()} DEPLOY {mission_id} {data.get('target')}\n")
            
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
2. Save intermediate findings immediately using write_file to /workspace/
3. Generate partial reports every 10 minutes as checkpoint files
4. If you discover ANY vulnerability, write it to /workspace/vuln_{{id}}.md immediately
5. Use session timeouts of max 300 seconds to prevent hangs

*** OBJECTIVES ***
{chr(10).join(f"- {obj}" for obj in mission.get('objectives', []))}

*** METHODOLOGY ***
Phase 1: Repository Analysis (NO GIT CLONE - use web_extract)
- Extract source code from GitHub/GitLab web interface  
- Map application structure and entry points
- Identify authentication and authorization mechanisms

Phase 2: Vulnerability Discovery
- Focus on: {', '.join(['Authentication bypasses', 'IDOR', 'Privilege escalation', 'API vulnerabilities'])}
- Document each finding in /workspace/vuln_{{finding_id}}.md immediately
- Generate PoC for each vulnerability (sandbox only)

Phase 3: Report Generation  
- Create detailed vulnerability reports with impact assessment
- Include reproduction steps and remediation advice
- Save all reports to /workspace/ for persistence

Execute this mission systematically. Your goal: find and document high-value vulnerabilities for bug bounty submission.

*** AUTONOMOUS OPERATION PROTOCOL ***
You are operating autonomously. Do NOT ask for user input or guidance. Complete all phases automatically:
1. Analyze authentication mechanisms (JWT, OAuth, session handling)
2. Review API endpoints for IDOR vulnerabilities  
3. Check privilege escalation paths
4. Examine group transfer functionality for IDOR+XSS
5. Generate final vulnerability reports in /workspace/

Continue analyzing through ALL objectives without stopping for input. Make decisions autonomously.
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

        # Run Hunter Agent subprocess with timeout and monitoring
        # Note: Using -q for single query mode with the full mission prompt
        # The Hunter's SOUL.md and skills provide the methodology context
        # Using qwen3.5-plus which is confirmed available on OpenRouter
        proc = await asyncio.create_subprocess_exec(
            "hermes", "chat",
            "-m", "qwen/qwen3.5-plus-02-15",
            "-q", prompt,
            "--yolo",
            "-Q",  # Quiet mode for programmatic use
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/app",
            env={
                **dict(os.environ),
                'HERMES_SESSION_TYPE': 'hunter',
                'HERMES_MISSION_ID': mission_id,
                'HERMES_WORKSPACE': f'/workspace/mission_{mission_id}',
                'HERMES_HOME': '/root/.hermes'
            }
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
            
            # Check for generated reports
            reports = list(workspace_dir.glob("vuln_*.md"))
            mission["reports_generated"] = len(reports)
            
            if reports:
                await self.broadcast_log(f"Generated {len(reports)} vulnerability report(s)", "info")
            
            if reports or proc.returncode == 0:
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
            
            return web.json_response({
                "success": True,
                "id": vuln_id,
                "file": str(vuln_file),
                "content": content,
                "discovered_at": datetime.fromtimestamp(vuln_file.stat().st_mtime).isoformat()
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

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
    app.router.add_get("/api/metrics", hunter_api.get_metrics)
    app.router.add_get("/api/logs/stream", hunter_api.stream_logs)
    
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