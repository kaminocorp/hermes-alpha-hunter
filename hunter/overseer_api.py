"""
Overseer API — HTTP endpoint for the Overseer to communicate with the Hunter.

Runs alongside the Telegram gateway. Accepts messages via HTTP POST and injects
them into the gateway's message processing pipeline as if they came from an
authorized user on Telegram.

Responses are sent to the configured Telegram chat (home channel).

Endpoints:
    POST /api/message       — Send a message to the Hunter
    GET  /api/status        — Check Hunter status
    GET  /api/health        — Health check
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# Auth token for Overseer -> Hunter communication
OVERSEER_API_TOKEN = os.getenv("OVERSEER_API_TOKEN", "")
API_PORT = int(os.getenv("OVERSEER_API_PORT", "8080"))


def _check_auth(request: web.Request) -> bool:
    """Validate bearer token."""
    if not OVERSEER_API_TOKEN:
        return False  # No token configured = API disabled
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {OVERSEER_API_TOKEN}"


class OverseerAPI:
    """HTTP API server for Overseer -> Hunter communication."""

    def __init__(self, gateway_runner):
        self.gateway = gateway_runner
        self.app = web.Application()
        self.app.router.add_post("/api/message", self.handle_message)
        self.app.router.add_get("/api/status", self.handle_status)
        self.app.router.add_get("/api/health", self.handle_health)
        self._runner = None

    async def start(self):
        """Start the HTTP server."""
        if not OVERSEER_API_TOKEN:
            logger.warning("OVERSEER_API_TOKEN not set — Overseer API disabled")
            return

        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", API_PORT)
        await site.start()
        logger.info("Overseer API listening on port %d", API_PORT)

    async def stop(self):
        """Stop the HTTP server."""
        if self._runner:
            await self._runner.cleanup()

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check — no auth required."""
        return web.json_response({"status": "ok", "agent": "hermes-alpha-hunter"})

    async def handle_status(self, request: web.Request) -> web.Response:
        """Return Hunter status."""
        if not _check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        # Gather status info
        import glob
        report_count = len(glob.glob("/workspace/reports/**/*.md", recursive=True))
        target_count = len(glob.glob("/workspace/targets/*"))

        status = {
            "status": "running",
            "reports": report_count,
            "targets": target_count,
            "uptime": str(datetime.now() - self.gateway._start_time) if hasattr(self.gateway, "_start_time") else "unknown",
        }
        return web.json_response(status)

    async def handle_message(self, request: web.Request) -> web.Response:
        """
        Accept a message from the Overseer and inject it into the gateway.

        Body: {"message": "your instruction here", "chat_id": "optional"}
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

        # Build a MessageEvent that looks like it came from the Overseer on Telegram
        from gateway.platforms.base import MessageEvent, MessageType
        from gateway.session import SessionSource
        from gateway.config import Platform

        # Use the Telegram home channel as the target chat, or a specified chat_id
        chat_id = body.get("chat_id", os.getenv("TELEGRAM_HOME_CHAT", "overseer"))

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

        # Process the message through the gateway pipeline
        # This runs async — we don't wait for the full agent response
        asyncio.create_task(self._process_and_respond(event, chat_id))

        return web.json_response({
            "status": "accepted",
            "message_id": event.message_id,
            "note": "Message queued for processing. Response will be sent to Telegram."
        })

    async def _process_and_respond(self, event, chat_id: str):
        """Process message and send response to Telegram."""
        try:
            response = await self.gateway._handle_message(event)

            # If we have a Telegram adapter, send the response there too
            from gateway.config import Platform
            adapter = self.gateway.adapters.get(Platform.TELEGRAM)
            if adapter and response and chat_id != "overseer":
                # Prefix so the Creator knows this is from an Overseer interaction
                await adapter.send(chat_id, f"[Overseer → Hunter]\n\n{response}")
        except Exception as e:
            logger.error("Error processing Overseer message: %s", e, exc_info=True)
