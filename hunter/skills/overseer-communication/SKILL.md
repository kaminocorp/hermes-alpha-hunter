# Overseer Communication Protocol

**Category:** hunter-operations  
**Description:** Enables the Hunter to receive and process direct commands and guidance from the Overseer during missions.

---

## Overview

The Overseer can send real-time commands and guidance to you during missions via the API. You must periodically check for new instructions and respond appropriately.

## Communication Channels

### 1. Direct Commands (High Priority)

Commands arrive via the `/api/command` endpoint and are injected into your conversation. They are marked with:

```
[OVERSEER DIRECTIVE - PRIORITY: HIGH/NORMAL]
```

**Response Protocol:**
1. Acknowledge receipt immediately
2. Execute the command with highest priority
3. Report results back

### 2. Guidance File (Asynchronous)

The Overseer writes guidance to `/workspace/overseer_guidance.json`. Check this file periodically during analysis.

**File Format:**
```json
[
  {
    "guidance_id": "uuid",
    "timestamp": "2026-03-19T01:00:00",
    "area": "authentication|idor|ssrf|general",
    "guidance": "Specific hints or context"
  }
]
```

**Check Frequency:** Every 5-10 minutes during long analysis phases.

### 3. Configuration Updates

The Overseer can update your config (`/root/.hermes/config.yaml`) via `/api/config`. Changes take effect on next invocation.

---

## Implementation

Add this to your analysis loop:

```python
# Check for Overseer guidance
import json
from pathlib import Path

guidance_file = Path("/workspace/overseer_guidance.json")
if guidance_file.exists():
    try:
        with open(guidance_file) as f:
            guidance_data = json.load(f)
        if guidance_data:
            latest = guidance_data[-1]
            print(f"📬 Overseer guidance ({latest['area']}): {latest['guidance']}")
            # Process guidance - adjust analysis focus accordingly
    except:
        pass
```

---

## Command Types

### Analysis Commands
- "Focus on authentication flows in /api/v4/auth"
- "Check all userId parameters for IDOR"
- "Review webhook URL handling for SSRF"

### Configuration Commands
- "Switch to deepseek-chat-v3-0324 for complex analysis"
- "Increase max_turns to 150"
- "Enable verbose mode for debugging"

### Mission Control
- "Pause current analysis and generate report"
- "Abort mission - target out of scope"
- "Escalate finding to verified vulnerability"

---

## Best Practices

1. **Always acknowledge** Overseer commands promptly
2. **Prioritize commands** over autonomous analysis
3. **Check guidance file** at natural breakpoints
4. **Report progress** when executing long commands
5. **Ask for clarification** if command is ambiguous (but try first)

---

## Example Command Response

```
✅ RECEIVED OVERSEER COMMAND [priority: high]

Command: "Focus on IDOR in channel access APIs"

Executing:
1. Searching for channel access endpoints...
2. Found /api/v4/channels/{id}/members
3. Checking authorization logic...
4. Testing with different user contexts...

Finding: Potential IDOR in /api/v4/channels/{id}/members
- Missing owner/user authorization check
- Any authenticated user can access any channel's member list

Writing vulnerability report...
```

---

## Emergency Protocol

If you receive a command with `[PRIORITY: CRITICAL]`:
1. STOP all current work immediately
2. Execute the critical command
3. Do not resume previous work until cleared by Overseer
