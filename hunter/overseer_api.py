"""
Overseer API — HTTP endpoint for the Overseer to communicate with the Hunter.

Runs alongside the Telegram gateway. Accepts messages via HTTP POST and injects
them into the gateway's message processing pipeline. Returns the agent's response
synchronously.

Auth: Bearer token via OVERSEER_API_TOKEN env var.

Endpoints:
    POST /api/message       — Send a message, get response back
    GET  /api/status        — Check Hunter status
    GET  /api/health        — Health check (no auth)
    GET  /api/transcripts   — Read recent conversation transcripts
"""

import asyncio
import glob
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)

OVERSEER_API_TOKEN = os.getenv("OVERSEER_API_TOKEN", "")
API_PORT = int(os.getenv("OVERSEER_API_PORT", "8080"))


def _check_auth(request: web.Request) -> bool:
    if not OVERSEER_API_TOKEN:
        return False
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {OVERSEER_API_TOKEN}"


class OverseerAPI:
    def __init__(self, gateway_runner):
        self.gateway = gateway_runner
        self.app = web.Application()
        self.app.router.add_post("/api/message", self.handle_message)
        self.app.router.add_get("/api/status", self.handle_status)
        self.app.router.add_get("/api/health", self.handle_health)
        self.app.router.add_get("/api/transcripts", self.handle_transcripts)
        self._runner = None
        self._start_time = datetime.now()

    async def start(self):
        if not OVERSEER_API_TOKEN:
            logger.warning("OVERSEER_API_TOKEN not set — Overseer API disabled")
            return
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", API_PORT)
        await site.start()
        logger.info("Overseer API listening on port %d", API_PORT)

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "agent": "hermes-alpha-hunter"})

    async def handle_status(self, request: web.Request) -> web.Response:
        if not _check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        report_count = len(glob.glob("/workspace/reports/**/*.md", recursive=True))
        target_dirs = [d for d in glob.glob("/workspace/targets/*") if os.path.isdir(d)]
        uptime = str(datetime.now() - self._start_time)

        # Count active sessions
        sessions_dir = os.path.expanduser("~/.hermes/sessions")
        session_count = 0
        if os.path.exists(sessions_dir):
            session_count = len([f for f in os.listdir(sessions_dir) if f.endswith(".json")])

        return web.json_response({
            "status": "running",
            "uptime": uptime,
            "reports": report_count,
            "targets": len(target_dirs),
            "sessions": session_count,
        })

    async def handle_message(self, request: web.Request) -> web.Response:
        """
        Send a message to the Hunter and wait for the response.

        Body: {"message": "your instruction", "chat_id": "optional", "timeout": 300}
        Returns: {"response": "agent's reply", "message_id": "..."}
        """
        if not _check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        message_text = body.get("message", "").strip()
        if not message_text:
            return web.json_response({"error": "empty message"}, status=400)

        timeout = min(body.get("timeout", 300), 600)  # Max 10 min

        from gateway.platforms.base import MessageEvent, MessageType
        from gateway.session import SessionSource
        from gateway.config import Platform

        chat_id = body.get("chat_id", "overseer-direct")

        source = SessionSource(
            platform=Platform.TELEGRAM,
            chat_id=str(chat_id),
            chat_name="Overseer",
            chat_type="dm",
            user_id="overseer",
            user_name="Hermes Alpha (Overseer)",
        )

        event = MessageEvent(
            text=message_text,
            message_type=MessageType.TEXT,
            source=source,
            message_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
        )

        try:
            # Process synchronously — wait for the agent's response
            response = await asyncio.wait_for(
                self.gateway._handle_message(event),
                timeout=timeout,
            )

            return web.json_response({
                "status": "ok",
                "message_id": event.message_id,
                "response": response or "(no response)",
            })
        except asyncio.TimeoutError:
            return web.json_response({
                "status": "timeout",
                "message_id": event.message_id,
                "response": f"Agent did not respond within {timeout}s. It may still be processing.",
            }, status=504)
        except Exception as e:
            logger.error("Error processing Overseer message: %s", e, exc_info=True)
            return web.json_response({
                "status": "error",
                "error": str(e),
            }, status=500)

    async def handle_transcripts(self, request: web.Request) -> web.Response:
        """Read recent conversation transcripts."""
        if not _check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        limit = int(request.query.get("limit", "20"))
        sessions_dir = os.path.expanduser("~/.hermes/sessions")

        transcripts = []
        if os.path.exists(sessions_dir):
            # Find JSONL transcript files, sorted by modification time
            files = sorted(
                glob.glob(os.path.join(sessions_dir, "*.jsonl")),
                key=os.path.getmtime,
                reverse=True,
            )
            for fpath in files[:3]:  # Last 3 sessions
                try:
                    entries = []
                    with open(fpath) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    entries.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                    # Only return last N entries
                    transcripts.append({
                        "file": os.path.basename(fpath),
                        "entries": entries[-limit:],
                    })
                except Exception as e:
                    logger.warning("Error reading transcript %s: %s", fpath, e)

        return web.json_response({"transcripts": transcripts})
