---
title: Security Code Review
description: Deep data-flow tracking and auth bypass pattern detection for finding high-severity vulnerabilities
tags: [security, code-review, data-flow, auth-bypass]
---
# Security Code Review Skill

## Mission
Perform deep, systematic security analysis of source code to identify high-severity vulnerabilities with clear exploit paths.

## Core Methodology

### Phase 1: Architecture Mapping
1. **Identify trust boundaries** - Where does untrusted input enter? Where are privilege checks performed?
2. **Map authentication flows** - Login, session management, token validation, OAuth integrations
3. **Map authorization patterns** - RBAC, permission checks, object-level access controls
4. **Identify data flow paths** - trace user input from entry point to sensitive operations (SQL, file I/O, command execution, network requests)

### Phase 2: Deep Data-Flow Tracking
For each user-controlled input:
1. **Entry point identification**: Request parameters, headers, cookies, file uploads, environment variables, database records
2. **Propagation tracking**: Follow the data through:
   - Variable assignments
   - Function parameters and return values
   - String concatenations and interpolations
   - Object property assignments
   - Template rendering
3. **Sink analysis**: Check if data reaches dangerous sinks:
   - SQL queries (SQL injection)
   - Shell commands (command injection)
   - File paths (path traversal, SSRF)
   - URLs (SSRF, XSS)
   - Reflection/deserialization (RCE)
   - Authentication/authorization checks (auth bypass)

### Phase 3: Auth Bypass Pattern Detection
Critical patterns to identify:

#### 1. Incomplete Authorization Checks
```python
# DANGEROUS: Checks user is logged in but not if they own the resource
def get_user_profile(user_id):
    if not current_user.is_authenticated:  # Only checks auth, not ownership
        return 403
    return db.query("SELECT * FROM users WHERE id = ?", user_id)

# SECURE: Must check ownership
def get_user_profile(user_id):
    if current_user.id != user_id and not current_user.is_admin:
        return 403
    return db.query("SELECT * FROM users WHERE id = ?", user_id)
```

#### 2. Race Conditions in Auth
```python
# DANGEROUS: TOCTOU - time of check to time of use
if user.balance >= amount:  # Check
    user.balance -= amount  # Use - balance could change between check and use
    process_payment(amount)

# Look for: async operations, concurrent requests, missing database transactions
```

#### 3. JWT/Token Validation Flaws
- Algorithm confusion (RS256 → HS256)
- Missing signature verification
- Accepting `alg: none`
- Not checking expiration
- Not validating `iss` (issuer) or `aud` (audience)
- Storing sensitive data in JWT payload (client-readable)

#### 4. OAuth Misconfigurations
- Missing `state` parameter (CSRF)
- Open redirect in callback URL validation
- Improper scope validation
- Token leakage via referrer

#### 5. IDOR (Insecure Direct Object References)
```python
# DANGEROUS: Using user-controlled ID without ownership check
GET /api/documents/{doc_id}
def get_document(doc_id):
    return db.documents.find(doc_id)  # No owner check!

# SECURE: Always verify ownership
def get_document(doc_id, current_user):
    doc = db.documents.find(doc_id)
    if doc.owner_id != current_user.id and not current_user.can_access(doc):
        return 403
    return doc
```

### Phase 4: Severity Calibration

**CRITICAL**: Only assign severity when you can demonstrate an exploit path.

#### Severity Assignment Criteria

**Critical (P1)** - Immediate compromise possible:
- ✅ Unauthenticated RCE
- ✅ SQL injection affecting sensitive data
- ✅ Auth bypass to admin/privileged account
- ✅ IDOR exposing PII at scale
- ✅ SSRF with cloud metadata access
- **Requirement**: Clear step-by-step exploit path documented

**High (P2)** - Significant compromise with minor conditions:
- ✅ Authenticated RCE
- ✅ Auth bypass to regular user accounts
- ✅ IDOR exposing sensitive user data
- ✅ Stored XSS in admin panel
- ✅ CSRF on critical actions (password change, email change)
- **Requirement**: Exploit path with clearly stated prerequisites

**Medium (P3)** - Limited impact or requires complex conditions:
- ✅ Reflected XSS (non-persistent)
- ✅ Information disclosure (non-sensitive)
- ✅ Missing rate limiting (with PoC of feasibility)
- ✅ SSRF limited to internal network scanning
- **Requirement**: Evidence of occurrence + realistic attack scenario

**Low (P4)** - Theoretical or minimal impact:
- ✅ Missing security headers
- ✅ Outdated dependencies (without known exploits)
- ✅ Verbose error messages
- ⚠️ **DO NOT REPORT** findings that require:
  - User to be already compromised
  - Physical access to device
  - Social engineering as primary vector
  
**Key principle**: If you cannot write a 3-step PoC, it's probably not High/Critical.

### Phase 5: Evidence Requirements

For each finding, collect:

1. **Code snippet** - The vulnerable code with file path and line numbers
2. **Data flow diagram** - Input → Transformation → Sink
3. **Exploit scenario** - "Attacker can [action] by [method] resulting in [impact]"
4. **Proof of concept** - Actual payload or request that triggers the vulnerability
5. **Impact assessment** - What data/actions are exposed? How many users affected?

## Red Flags Requiring Immediate Escalation

When you find any of these, mark as Critical and prioritize:

1. Hardcoded credentials or API keys
2. Debug endpoints exposed in production
3. `eval()`, `exec()`, `Function()` with user input
4. Raw SQL queries with string concatenation
5. File uploads without extension/MIME validation
6. Deserialization of user-controlled data
7. Password reset tokens in URL with predictable patterns
8. Session tokens in localStorage or URLs
9. Missing validation on password change (requires old password)
10. Batch APIs without per-object permission checks

## Common Vulnerability Patterns by Technology

### Python/Django/Flask
- `request.GET`/`request.POST` used directly in queries
- `User.objects.get(id=request.GET['id'])` - classic IDOR
- `f"SELECT * FROM users WHERE id = {user_id}"` - SQL injection
- `os.system(f"process {filename}")` - command injection

### Node.js/Express
- `req.query.id` in database queries
- `eval(userInput)`, `new Function(userInput)`
- `res.sendFile(req.params.file)` - path traversal
- Missing `await` in auth checks (race conditions)

### PHP
- `$_GET`, `$_POST`, `$_REQUEST` in SQL
- `include($_GET['page'])` - LFI/RFI
- `unserialize($_POST['data'])` - deserialization RCE
- `extract($_GET)` - variable injection

### Java/Spring
- `@RequestParam` in SQL queries
- `Runtime.getRuntime().exec(userInput)`
- `Class.forName(userInput)` - reflection abuse
- Insecure deserialization of user objects

## Analysis Workflow

1. **Start with entry points**: API routes, controllers, route handlers
2. **Follow the data**: Track user input from entry → processing → sink
3. **Check trust assumptions**: Does the code assume input is safe?
4. **Verify auth logic**: Are there gaps where checks should exist?
5. **Look for dangerous functions**: SQL, shell, file, network, eval
6. **Check error handling**: Do errors leak sensitive information?
7. **Review config**: Debug flags, verbose errors, exposed endpoints

## Quality Standards

- Every finding must have a **reproducible PoC**
- Every High+ finding must show **data flow from input to impact**
- Never report theoretical issues without evidence of occurrence
- Focus on impact over technical complexity
- If unsure whether something is exploitable, **exploit it in a sandbox** before reporting
