---
title: OWASP Top 10 Pattern Recognition
description: Detect OWASP Top 10 (2021) vulnerability patterns in source code
tags: [security, owasp, vulnerability-patterns]
---
# OWASP Top 10 (2021) — Code Pattern Recognition

## When to Use
During the deep analysis phase. Use these patterns to systematically scan for each vulnerability class.

## A01: Broken Access Control (Most Critical for Bounties)

### What to Search For
```bash
# Missing auth middleware
grep -rn "router\.\(get\|post\|put\|delete\)" --include="*.js" --include="*.ts" | grep -v "auth\|middleware\|protect\|guard\|verify"

# Direct object references without ownership check
grep -rn "findById\|findOne\|get.*ById\|params\.id\|req\.params" --include="*.js" --include="*.ts" --include="*.py"

# Admin routes without role checks
grep -rn "admin\|/api/admin\|isAdmin" --include="*.js" --include="*.ts" --include="*.py" --include="*.rb"

# Missing authorization after authentication
grep -rn "req\.user\|current_user\|request\.user" --include="*.js" --include="*.ts" --include="*.py" | grep -v "role\|permission\|authorize\|can\?\|ability"
```

### Vulnerable Patterns
```javascript
// BAD: No ownership check — any authenticated user can access any record
app.get('/api/documents/:id', auth, async (req, res) => {
    const doc = await Document.findById(req.params.id);
    res.json(doc);
});

// GOOD: Ownership check included
app.get('/api/documents/:id', auth, async (req, res) => {
    const doc = await Document.findOne({ _id: req.params.id, owner: req.user.id });
    if (!doc) return res.status(404).json({ error: 'Not found' });
    res.json(doc);
});
```

### Key Checks
- Can user A access user B's resources by changing IDs?
- Can a regular user access admin endpoints?
- Are CORS policies properly restrictive?
- Can auth tokens be reused across different accounts?

## A02: Cryptographic Failures

### What to Search For
```bash
# Weak hashing
grep -rn "md5\|sha1\b" --include="*.py" --include="*.js" --include="*.java" --include="*.rb" --include="*.go"

# Hardcoded keys/secrets
grep -rn "SECRET_KEY.*=.*['"]\|JWT_SECRET.*=.*['"]\|ENCRYPTION_KEY.*=.*['"]" --include="*.py" --include="*.js" --include="*.env*" --include="*.yaml" --include="*.yml"

# Weak encryption modes
grep -rn "ECB\|DES\|RC4\|Blowfish" --include="*.py" --include="*.js" --include="*.java"

# Missing HTTPS enforcement
grep -rn "http://\|secure.*false\|verify.*false\|rejectUnauthorized.*false" --include="*.py" --include="*.js" --include="*.yaml"

# Sensitive data in logs
grep -rn "log.*password\|log.*token\|log.*secret\|console\.log.*auth" --include="*.py" --include="*.js" --include="*.ts"
```

### Key Checks
- Passwords stored as MD5/SHA1 instead of bcrypt/argon2/scrypt?
- Secrets hardcoded rather than from environment?
- Sensitive data in URL parameters (logged by proxies)?
- TLS certificate validation disabled?

## A03: Injection

### What to Search For
```bash
# SQL Injection
grep -rn "query.*\$\|query.*+\|execute.*%s\|execute.*format\|raw.*sql\|\.raw(\|\.extra(" --include="*.py" --include="*.js" --include="*.ts" --include="*.java" --include="*.rb" --include="*.go"

# Command Injection
grep -rn "exec(\|execSync\|spawn(\|system(\|popen\|subprocess\.call.*shell.*True\|os\.system" --include="*.py" --include="*.js" --include="*.ts" --include="*.rb"

# XSS (Server-side rendering)
grep -rn "innerHTML\|dangerouslySetInnerHTML\|v-html\|\|safe\|html_safe\|raw(\|{!!.*!!}" --include="*.js" --include="*.jsx" --include="*.tsx" --include="*.vue" --include="*.py" --include="*.html" --include="*.erb" --include="*.blade.php"

# LDAP Injection
grep -rn "ldap.*search\|ldap.*filter" --include="*.py" --include="*.js" --include="*.java"

# Template Injection (SSTI)
grep -rn "render_template_string\|Template(.*request\|Jinja2.*from_string\|Mako.*Template" --include="*.py"
grep -rn "new Function(\|eval(\|compile(" --include="*.js" --include="*.ts"
```

### Vulnerable Patterns (SQL Injection)
```python
# BAD: String interpolation in SQL
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
cursor.execute("SELECT * FROM users WHERE name = '%s'" % name)

# GOOD: Parameterized query
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

```javascript
// BAD: String concatenation in query
db.query("SELECT * FROM users WHERE id = " + req.params.id);

// GOOD: Parameterized
db.query("SELECT * FROM users WHERE id = $1", [req.params.id]);
```

## A04: Insecure Design

Look for:
- Missing rate limiting on auth endpoints
- No account lockout after failed attempts
- Password reset tokens that don't expire
- Business logic flaws in multi-step workflows
- Missing server-side validation (client-only checks)

```bash
# Rate limiting
grep -rn "rate.limit\|rateLimit\|throttle\|brute" --include="*.js" --include="*.ts" --include="*.py" -l
# If no results, check if rate limiting middleware exists at all

# Password reset
grep -rn "reset.*password\|forgot.*password\|password.*reset" --include="*.js" --include="*.ts" --include="*.py" -l
# Check token expiry and single-use enforcement
```

## A05: Security Misconfiguration

```bash
# Debug mode
grep -rn "DEBUG.*=.*True\|NODE_ENV.*development\|debug.*true" --include="*.py" --include="*.js" --include="*.yaml" --include="*.env*"

# Default credentials
grep -rn "admin.*admin\|password.*password\|default.*password" --include="*.py" --include="*.js" --include="*.yaml" --include="*.env*"

# Unnecessary features enabled
grep -rn "swagger\|graphiql\|playground\|__debug__" --include="*.py" --include="*.js" --include="*.yaml"

# Permissive CORS
grep -rn "Access-Control-Allow-Origin.*\*\|cors.*origin.*true\|cors.*origin.*\*" --include="*.py" --include="*.js" --include="*.ts"

# Directory listing
grep -rn "autoindex\|directory.*listing\|serveIndex" --include="*.conf" --include="*.js" --include="*.py"
```

## A06: Vulnerable and Outdated Components

```bash
# Check for known vulnerable packages
cat package.json | jq '.dependencies, .devDependencies'
cat requirements.txt
cat Gemfile.lock
# Cross-reference versions against CVE databases
```

## A07: Identification and Authentication Failures

```bash
# Weak password policies
grep -rn "password.*length\|minlength.*password\|password.*min" --include="*.py" --include="*.js" --include="*.ts"

# Session management
grep -rn "session\|cookie\|httpOnly\|secure\|sameSite\|maxAge\|expires" --include="*.py" --include="*.js" --include="*.ts"

# JWT issues
grep -rn "jwt\.sign\|jwt\.verify\|jwt\.decode\|jsonwebtoken" --include="*.js" --include="*.ts" --include="*.py"
# Check: algorithm, expiry, secret strength, token storage
```

## A08: Software and Data Integrity Failures

```bash
# Deserialization
grep -rn "pickle\.loads\|yaml\.load\|unserialize\|ObjectInputStream\|Marshal\.load\|eval(" --include="*.py" --include="*.java" --include="*.rb" --include="*.php"

# Missing integrity checks on updates/CI
grep -rn "curl.*|.*sh\|wget.*|.*bash\|pip install.*--trusted-host" --include="*.sh" --include="*.yaml" --include="*.yml" --include="Dockerfile"
```

## A09: Security Logging and Monitoring Failures

```bash
# Check if auth events are logged
grep -rn "login.*log\|auth.*log\|failed.*attempt\|audit" --include="*.py" --include="*.js" --include="*.ts" -l
```

## A10: Server-Side Request Forgery (SSRF)

```bash
# User-controlled URLs in server requests
grep -rn "requests\.get.*req\|fetch(.*req\|axios.*req\|http\.get.*req\|urllib.*req\|HttpClient.*req" --include="*.py" --include="*.js" --include="*.ts" --include="*.java"

# URL parameters used in server-side requests
grep -rn "url.*=.*req\.\|uri.*=.*req\.\|endpoint.*=.*req\." --include="*.py" --include="*.js" --include="*.ts"

# Webhook/callback URLs from user input
grep -rn "webhook\|callback.*url\|redirect.*url\|return.*url" --include="*.py" --include="*.js" --include="*.ts"
```

## Priority for Bounty Hunting
1. **A01 Broken Access Control** — Highest payout, most common in web apps
2. **A03 Injection** — Classic, high-severity when found
3. **A07 Auth Failures** — JWT/session bugs pay well
4. **A10 SSRF** — Increasingly valuable, often missed
5. **A02 Crypto** — Depends on impact, but hardcoded secrets are easy wins
