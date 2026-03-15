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
            
            # TODO: Actually deploy to Hunter (spawn subprocess, delegate_task, etc.)
            # For now, just log it
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

    async def health_check(self, request: web_request.Request) -> Response:
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "service": "hermes-alpha-hunter-api",
            "timestamp": datetime.utcnow().isoformat()
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
    app.router.add_get("/health", hunter_api.health_check)
    
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