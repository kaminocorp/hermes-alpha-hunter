#!/usr/bin/env python3
"""
Hermes Alpha Hunter — API Server
Direct control interface for the Overseer to deploy missions and check status.
"""
import os
import asyncio
import json
import uuid
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
        
        # Ensure workspace exists
        Path("/workspace").mkdir(exist_ok=True)
        
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
            
            # Build Hunter prompt with stability focus
            hunter_prompt = self._build_hunter_prompt(mission)
            
            # Execute with crash recovery and persistence
            await self._run_hunter_with_recovery(mission_id, hunter_prompt)
            
        except Exception as e:
            mission["status"] = "failed"
            mission["error"] = str(e)
            print(f"[!] Mission {mission_id} failed: {e}")

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
        
        # Run Hunter Agent subprocess with timeout and monitoring  
        proc = await asyncio.create_subprocess_exec(
            "hermes", "run",
            "--no-auth",
            "--model", "deepseek/deepseek-chat",
            "--system-prompt-append", prompt,
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
        
        # Monitor process with timeout
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3600)  # 1 hour max
            
            # Log subprocess output for debugging
            print(f"[DEBUG] Mission {mission_id} subprocess output:")
            if stdout:
                print(f"STDOUT: {stdout.decode()}")
            if stderr:
                print(f"STDERR: {stderr.decode()}")
            
            # Update mission with results
            mission["status"] = "completed" 
            mission["completed_at"] = datetime.utcnow().isoformat()
            mission["stdout"] = stdout.decode() if stdout else ""
            mission["stderr"] = stderr.decode() if stderr else ""
            
            # Check for generated reports
            reports = list(workspace_dir.glob("vuln_*.md"))
            mission["reports_generated"] = len(reports)
            
            print(f"[✓] Mission {mission_id} completed with {len(reports)} reports")
            
        except asyncio.TimeoutError:
            proc.kill()
            mission["status"] = "timeout"
            print(f"[!] Mission {mission_id} timed out")
        except Exception as e:
            mission["status"] = "crashed" 
            mission["error"] = str(e)
            print(f"[!] Mission {mission_id} crashed: {e}")
    
    async def get_health(self, request: web_request.Request) -> Response:
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "uptime": datetime.utcnow().isoformat(),
            "active_missions": len([m for m in self.missions.values() if m["status"] == "active"]),
            "version": "v12"
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




async def create_app() -> web.Application:
    """Create the aiohttp application"""
    hunter_api = HunterAPI()
    
    app = web.Application()
    
    # Routes
    app.router.add_post("/api/missions", hunter_api.deploy_mission)
    app.router.add_get("/api/status", hunter_api.get_status)
    app.router.add_get("/api/missions", hunter_api.list_missions)
    app.router.add_get("/api/missions/{mission_id}", hunter_api.get_mission)
    app.router.add_delete("/api/missions/{mission_id}", hunter_api.cancel_mission)
    app.router.add_get("/health", hunter_api.get_health)
    app.router.add_get("/session/status", hunter_api.get_session_status)
    app.router.add_get("/session/messages", hunter_api.get_session_messages)
    
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