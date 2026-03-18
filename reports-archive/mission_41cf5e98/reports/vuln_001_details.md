## Vulnerability Details

### Affected Component

**File(s):** `/server/channels/api4/channel.go`
**Function(s):** `addChannelMember()`
**Line Numbers:** 1948-2172
**API Endpoint:** `POST /api/v4/channels/{channel_id}/members`

### Root Cause

The vulnerability exists due to **incomplete authorizati...