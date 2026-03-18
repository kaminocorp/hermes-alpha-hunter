## Remediation Recommendations

### Immediate Fix

Implement URL validation before making HTTP requests in `webhook.go`:

```go
// Add these imports at the top of webhook.go
import (
    "net"
    "net/url"
    "strings"
)

// Add validation function
func validateWebhookURL(rawURL string) error {
  ...