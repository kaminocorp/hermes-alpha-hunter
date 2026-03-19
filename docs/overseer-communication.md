# Overseer Communication Guide

Direct communication channels with the Hunter agent deployed on Fly.io.

---

## Base URL

```
https://hermes-alpha-hunter.fly.dev
```

## Authentication

All endpoints require Bearer token authentication:

```bash
export OVERSEER_TOKEN="RGUOk8GKQtttlJ3FS8IMSoe-fnaiBP0_uBIKbcamCVg"
```

---

## Endpoints

### 1. Send Direct Command (Synchronous)

**Endpoint:** `POST /api/command`

Send an immediate instruction to the Hunter and wait for its response.

**Request:**
```json
{
  "command": "Focus analysis on authentication bypasses in the /api/v4/auth endpoints",
  "timeout": 300,
  "priority": "normal"
}
```

**Response:**
```json
{
  "status": "ok",
  "command_id": "8776b0bb-d5d9-4fb6-801d-521e14eb9256",
  "response": "ACK received. Focusing on authentication bypasses in /api/v4/auth...",
  "exit_code": 0
}
```

**Status codes:**
- `ok` - Command executed successfully
- `timeout` - Hunter didn't respond within timeout (may still be processing)
- `error` - Execution failed

**Example:**
```bash
curl -sL -X POST https://hermes-alpha-hunter.fly.dev/api/command \
  -H "Authorization: Bearer $OVERSEER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "Generate a summary of findings so far",
    "timeout": 120,
    "priority": "high"
  }'
```

---

### 2. Send Guidance (Asynchronous)

**Endpoint:** `POST /api/guidance`

Provide hints and context for the Hunter to read during its analysis loop. Less urgent than direct commands.

**Request:**
```json
{
  "guidance": "The target uses JWT for authentication - check for algorithm confusion vulnerabilities",
  "area": "authentication"
}
```

**Response:**
```json
{
  "status": "ok",
  "guidance_id": "83901773-0d0e-447a-8484-360b99e0822c",
  "message": "Guidance saved. Hunter will read on next iteration."
}
```

**Areas:** `authentication`, `idor`, `ssrf`, `xss`, `general`, or any custom label

**Example:**
```bash
curl -sL -X POST https://hermes-alpha-hunter.fly.dev/api/guidance \
  -H "Authorization: Bearer $OVERSEER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "guidance": "Check all userId and channelId parameters for IDOR - this is a collaboration app",
    "area": "idor"
  }'
```

---

### 3. Update Configuration

**Endpoint:** `POST /api/config`

Dynamically update Hunter configuration. Changes take effect on next Hunter invocation.

**Request:**
```json
{
  "model": "deepseek/deepseek-chat-v3-0324",
  "reasoning_effort": "high",
  "max_turns": 150
}
```

**Response:**
```json
{
  "status": "ok",
  "changes": ["model=deepseek/deepseek-chat-v3-0324", "reasoning_effort=high"],
  "message": "Config updated. Takes effect on next Hunter invocation."
}
```

**Configurable fields:**
- `model` - Change the LLM model (e.g., `deepseek/deepseek-chat-v3-0324`, `qwen/qwen3.5-plus-02-15`)
- `reasoning_effort` - `low`, `medium`, or `high`
- `max_turns` - Maximum turns per session

**Example - Switch to cheaper model for routine work:**
```bash
curl -sL -X POST https://hermes-alpha-hunter.fly.dev/api/config \
  -H "Authorization: Bearer $OVERSEER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen/qwen2.5-7b-instruct",
    "reasoning_effort": "medium"
  }'
```

---

### 4. Get Session State

**Endpoint:** `GET /api/session`

Retrieve current session information and command history.

**Response:**
```json
{
  "active_sessions": [
    {
      "session_id": "hunter-20260319-001",
      "last_activity": "2026-03-19T02:00:00",
      "message_count": 47
    }
  ],
  "command_history": [
    {
      "command_id": "8776b0bb-d5d9-4fb6-801d-521e14eb9256",
      "timestamp": "2026-03-19T02:01:00",
      "command": "Test command from Overseer",
      "priority": "normal",
      "timeout": 30
    }
  ],
  "hunter_status": "mission_active"
}
```

**Example:**
```bash
curl -sL https://hermes-alpha-hunter.fly.dev/api/session \
  -H "Authorization: Bearer $OVERSEER_TOKEN"
```

---

### 5. General Status (No Auth Required)

**Endpoint:** `GET /api/status`

Check if Hunter is idle or running a mission.

**Response:**
```json
{
  "status": "mission_active",
  "active_missions": 1,
  "total_missions": 3,
  "uptime": "2026-03-19T02:00:00"
}
```

---

## Usage Patterns

### 1. Check Status Before Sending Command

```bash
# Check if Hunter is busy
STATUS=$(curl -sL https://hermes-alpha-hunter.fly.dev/api/status)
ACTIVE=$(echo $STATUS | jq -r '.active_missions')

if [ "$ACTIVE" -gt 0 ]; then
  echo "Hunter is active - sending guidance..."
  curl -sL -X POST https://hermes-alpha-hunter.fly.dev/api/guidance \
    -H "Authorization: Bearer $OVERSEER_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"guidance": "Focus on IDOR in user endpoints", "area": "idor"}'
else
  echo "Hunter is idle - no action needed"
fi
```

### 2. Switch Model for Cost Optimization

```bash
# Use cheaper model for initial recon
curl -sL -X POST https://hermes-alpha-hunter.fly.dev/api/config \
  -H "Authorization: Bearer $OVERSEER_TOKEN" \
  -d '{"model": "qwen/qwen2.5-7b-instruct"}'

# Switch to powerful model for complex analysis
curl -sL -X POST https://hermes-alpha-hunter.fly.dev/api/config \
  -H "Authorization: Bearer $OVERSEER_TOKEN" \
  -d '{"model": "deepseek/deepseek-chat-v3-0324", "reasoning_effort": "high"}'
```

### 3. Direct Command with Fallback

```bash
RESPONSE=$(curl -sL -X POST https://hermes-alpha-hunter.fly.dev/api/command \
  -H "Authorization: Bearer $OVERSEER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "List all findings so far", "timeout": 60}')

STATUS=$(echo $RESPONSE | jq -r '.status')

if [ "$STATUS" = "timeout" ]; then
  echo "Command timed out - Hunter still processing"
  echo "Sending follow-up guidance instead..."
  curl -sL -X POST https://hermes-alpha-hunter.fly.dev/api/guidance \
    -H "Authorization: Bearer $OVERSEER_TOKEN" \
    -d '{"guidance": "When you have a moment, list all findings", "area": "general"}'
elif [ "$STATUS" = "ok" ]; then
  echo "Command executed successfully"
  echo $RESPONSE | jq -r '.response'
fi
```

---

## Best Practices

1. **Use guidance for non-urgent hints** - Let Hunter read them at natural breakpoints
2. **Use commands for immediate action** - Hunter will respond synchronously
3. **Set appropriate timeouts** - 60s for simple queries, 300s for complex analysis
4. **Monitor command history** - Use `/api/session` to track what you've sent
5. **Update config between missions** - Not during active analysis

---

## Troubleshooting

**Command returns timeout:**
- Hunter may be in a long-running tool call
- Try shorter command or use guidance instead
- Check session state with `/api/session`

**Unauthorized error:**
- Verify token is correct
- Check `Authorization: Bearer $TOKEN` header format

**Config changes not taking effect:**
- Config updates apply on next Hunter invocation
- Current session continues with old config
- Wait for next mission deployment

---

## API Reference Summary

| Endpoint | Method | Auth | Purpose | Timeout |
|----------|--------|------|---------|---------|
| `/api/command` | POST | Yes | Direct instruction (sync) | 5-600s |
| `/api/guidance` | POST | Yes | Async hints | 10s |
| `/api/config` | POST | Yes | Update config | 10s |
| `/api/session` | GET | Yes | Session state | 10s |
| `/api/status` | GET | No | Hunter status | 10s |
| `/api/missions` | GET | No | List missions | 10s |
| `/api/vulnerabilities` | GET | No | List findings | 10s |

---

## Implementation Notes

- All responses include CORS headers for browser-based dashboards
- Command history is limited to last 100 entries
- Guidance file (`/workspace/overseer_guidance.json`) is limited to last 20 entries
- Hunter checks guidance file every 5-10 minutes during analysis
- Commands override autonomous analysis immediately
