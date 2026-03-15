"""
Elephantasm long-term memory hook for Hermes Alpha Hunter.

- session:start  → inject() to load memory pack into system prompt
- agent:end      → extract() to record the session's key events
"""

import logging
import os

logger = logging.getLogger(__name__)

_ANIMA_ID = os.getenv("ELEPHANTASM_ANIMA_ID", "")
_API_KEY = os.getenv("ELEPHANTASM_API_KEY", "")


def _get_client():
    """Lazy-init Elephantasm client."""
    if not _ANIMA_ID or not _API_KEY:
        return None
    try:
        from elephantasm import Elephantasm
        return Elephantasm(api_key=_API_KEY, anima_id=_ANIMA_ID)
    except Exception as e:
        logger.warning("Elephantasm client init failed: %s", e)
        return None


async def handle(event_type: str, context: dict):
    """Handle gateway events for Elephantasm integration."""

    if event_type == "session:start":
        await _on_session_start(context)
    elif event_type == "agent:end":
        await _on_agent_end(context)


async def _on_session_start(context: dict):
    """Inject memory pack into the session's system prompt."""
    client = _get_client()
    if not client:
        return

    try:
        pack = client.inject()
        if pack:
            prompt_addition = pack.as_prompt()
            if prompt_addition.strip():
                # Store in context so the gateway can pick it up
                context["elephantasm_memory"] = prompt_addition
                logger.info(
                    "Elephantasm inject: %d tokens, %d memories, %d knowledge",
                    pack.token_count,
                    pack.long_term_memory_count,
                    pack.knowledge_count,
                )
            else:
                logger.debug("Elephantasm inject: empty prompt (fresh anima)")
        else:
            logger.debug("Elephantasm inject: no pack returned")
    except Exception as e:
        logger.warning("Elephantasm inject failed: %s", e)
    finally:
        client.close()


async def _on_agent_end(context: dict):
    """Extract key events from the agent's session."""
    client = _get_client()
    if not client:
        return

    try:
        from elephantasm import EventType

        # Extract a summary of what happened
        response_text = context.get("response", "")
        if response_text:
            # Record the agent's final response as an outgoing message
            client.extract(
                EventType.MESSAGE_OUT,
                response_text[:4000],  # Cap length
                role="assistant",
                author="hunter",
                meta={
                    "session_id": context.get("session_id", ""),
                    "platform": context.get("platform", "telegram"),
                },
            )

        # Record tool usage summary if available
        tool_calls = context.get("tool_calls_count", 0)
        if tool_calls > 0:
            client.extract(
                EventType.SYSTEM,
                f"Session completed with {tool_calls} tool calls",
                meta={
                    "tool_calls": tool_calls,
                    "session_id": context.get("session_id", ""),
                },
            )

        logger.debug("Elephantasm extract: recorded session events")
    except Exception as e:
        logger.warning("Elephantasm extract failed: %s", e)
    finally:
        client.close()
