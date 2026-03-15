#!/usr/bin/env bash
# =============================================================================
# Hermes Alpha Hunter — Gateway Boot Script
# Persistent Telegram bot mode. Receives missions from the Overseer.
# =============================================================================
set -euo pipefail

# ── Required env vars ────────────────────────────────────────────────────────
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required}"
: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY is required}"

# ── Optional env vars ────────────────────────────────────────────────────────
TELEGRAM_ALLOWED_USERS="${TELEGRAM_ALLOWED_USERS:-}"
TELEGRAM_HOME_CHAT="${TELEGRAM_HOME_CHAT:-}"

echo "=============================================="
echo "  Hermes Alpha Hunter — Gateway Mode"
echo "=============================================="
echo "  Bot: @hermes_hunter_bot"
echo "  Allowed users: ${TELEGRAM_ALLOWED_USERS:-<pairing mode>}"
echo "=============================================="

# ── Write .env for the agent ─────────────────────────────────────────────────
cat > /root/.hermes/.env <<ENVEOF
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
ENVEOF

# Add optional keys if provided
[ -n "${OPENAI_API_KEY:-}" ]       && echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >> /root/.hermes/.env
[ -n "${ANTHROPIC_API_KEY:-}" ]    && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> /root/.hermes/.env
[ -n "${GITHUB_TOKEN:-}" ]         && echo "GITHUB_TOKEN=${GITHUB_TOKEN}" >> /root/.hermes/.env
[ -n "${BROWSERBASE_API_KEY:-}" ]     && echo "BROWSERBASE_API_KEY=${BROWSERBASE_API_KEY}" >> /root/.hermes/.env
[ -n "${TELEGRAM_ALLOWED_USERS:-}" ] && echo "TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}" >> /root/.hermes/.env
[ -n "${TELEGRAM_HOME_CHAT:-}" ]     && echo "TELEGRAM_HOME_CHAT=${TELEGRAM_HOME_CHAT}" >> /root/.hermes/.env
[ -n "${ELEPHANTASM_API_KEY:-}" ]    && echo "ELEPHANTASM_API_KEY=${ELEPHANTASM_API_KEY}" >> /root/.hermes/.env
[ -n "${ELEPHANTASM_ANIMA_ID:-}" ]   && echo "ELEPHANTASM_ANIMA_ID=${ELEPHANTASM_ANIMA_ID}" >> /root/.hermes/.env
[ -n "${OVERSEER_API_TOKEN:-}" ]     && echo "OVERSEER_API_TOKEN=${OVERSEER_API_TOKEN}" >> /root/.hermes/.env

chmod 600 /root/.hermes/.env

# ── Prepare workspace ────────────────────────────────────────────────────────
mkdir -p /workspace /workspace/reports /workspace/targets

# ── Install hunter-specific skills ───────────────────────────────────────────
# Copy security skills into the main skills directory
if [ -d /root/.hermes/skills/security ]; then
    echo "[+] Security skills already in place"
else
    echo "[*] Linking security skills..."
    # They were copied during Docker build to /root/.hermes/skills/
    ls /root/.hermes/skills/security/ 2>/dev/null && echo "[+] Skills found" || echo "[!] No skills found"
fi

# ── Elephantasm: inject long-term memory at boot ────────────────────────────
if [ -n "${ELEPHANTASM_API_KEY:-}" ] && [ -n "${ELEPHANTASM_ANIMA_ID:-}" ]; then
    echo "[*] Injecting Elephantasm long-term memory..."
    python3 -c "
import os, sys
try:
    from elephantasm import Elephantasm
    client = Elephantasm(
        api_key=os.environ['ELEPHANTASM_API_KEY'],
        anima_id=os.environ['ELEPHANTASM_ANIMA_ID']
    )
    pack = client.inject()
    if pack:
        prompt = pack.as_prompt()
        if prompt.strip():
            # Write memory pack to a file the gateway can read
            with open('/root/.hermes/elephantasm_memory.txt', 'w') as f:
                f.write(prompt)
            print(f'[+] Elephantasm: {pack.token_count} tokens, {pack.long_term_memory_count} memories, {pack.knowledge_count} knowledge')
        else:
            print('[*] Elephantasm: fresh anima, no memories yet')
    else:
        print('[*] Elephantasm: no pack returned')
    client.close()
except Exception as e:
    print(f'[!] Elephantasm inject failed: {e}', file=sys.stderr)
" 2>&1

    # If memory was injected, set it as ephemeral system prompt
    if [ -f /root/.hermes/elephantasm_memory.txt ]; then
        export HERMES_EPHEMERAL_SYSTEM_PROMPT="$(cat /root/.hermes/elephantasm_memory.txt)"
        echo "[+] Elephantasm memory loaded into ephemeral system prompt"
    fi
else
    echo "[*] Elephantasm not configured, skipping memory injection"
fi

# ── Start the API server and gateway ──────────────────────────────────────────
echo "[*] Starting Hunter API server on port 8080..."
cd /app
python3 hunter/api_server.py &
API_SERVER_PID=$!

echo "[*] Starting Hermes gateway (Telegram)..."
hermes gateway &
GATEWAY_PID=$!

echo "[+] Hunter services started:"
echo "    - API Server: PID $API_SERVER_PID (port 8080)"
echo "    - Telegram Gateway: PID $GATEWAY_PID"

# Wait for either process to exit and kill the other
wait -n
echo "[*] One service exited, shutting down..."
kill $API_SERVER_PID $GATEWAY_PID 2>/dev/null || true
wait
