---
title: Secure Code Review Methodology
description: Systematic approach to security-focused source code review
tags: [security, code-review, methodology]
---
# Secure Code Review Methodology

## When to Use
After scope check passes and reconnaissance is complete. This is the core analysis methodology.

## Procedure

### Phase 1: Map the Application

#### 1.1 Identify the Stack
```bash
# Check package files
cat package.json 2>/dev/null          # Node.js/Express
cat requirements.txt Pipfile 2>/dev/null  # Python/Django/Flask
cat Gemfile 2>/dev/null               # Ruby/Rails
cat pom.xml build.gradle 2>/dev/null  # Java/Spring
cat composer.json 2>/dev/null         # PHP/Laravel
cat go.mod 2>/dev/null                # Go
cat Cargo.toml 2>/dev/null            # Rust
```

#### 1.2 Map Entry Points
- **Routes/endpoints**: Find all URL handlers
  - Express: `grep -rn "app\.\(get\|post\|put\|delete\|patch\|all\|use\)" --include="*.js" --include="*.ts"`
  - Django: `grep -rn "path(\|url(" --include="*.py" urls.py */urls.py`
  - Flask: `grep -rn "@app\.route\|@blueprint\.route" --include="*.py"`
  - Rails: `cat config/routes.rb`
  - Spring: `grep -rn "@\(Get\|Post\|Put\|Delete\|Request\)Mapping\|@\(Get\|Post\|Put\|Delete\)Mapping" --include="*.java"`
  - Laravel: `cat routes/web.php routes/api.php`
  - Go/Gin: `grep -rn "\.GET\|\.POST\|\.PUT\|\.DELETE\|\.Handle" --include="*.go"`

#### 1.3 Identify Auth System
```bash
# Find auth middleware/decorators
grep -rn "auth\|login\|session\|jwt\|token\|passport\|guard" --include="*.py" --include="*.js" --include="*.ts" --include="*.java" --include="*.rb" --include="*.go" -l
# Find password handling
grep -rn "password\|bcrypt\|argon\|scrypt\|hash" --include="*.py" --include="*.js" --include="*.ts" -l
```

#### 1.4 Find Data Models
```bash
# ORM models / DB schemas
grep -rn "class.*Model\|Schema\|Entity\|migration\|CREATE TABLE" -l
# Find where user data is stored
grep -rn "class User\|model User\|users table" -l
```

### Phase 2: Identify Trust Boundaries

A trust boundary exists wherever data crosses between different privilege levels:
1. **External → Application**: HTTP requests, file uploads, webhooks, WebSocket messages
2. **Application → Database**: Queries with user input
3. **Application → OS**: Command execution, file system operations
4. **Application → External services**: API calls, SSRF vectors
5. **User → Admin**: Privilege boundaries within the application
6. **Authenticated → Unauthenticated**: Auth-required vs public endpoints

For each boundary, ask: **Is the data validated/sanitized before crossing?**

### Phase 3: Trace Data Flows

For each entry point:
1. **Source**: Where does user input enter? (req.body, req.params, req.query, headers, cookies)
2. **Transform**: How is it processed? (validation, sanitization, type casting)
3. **Sink**: Where does it end up? (DB query, HTML output, command exec, file path)

**Dangerous sinks by category:**
| Category | Sinks |
|----------|-------|
| SQL Injection | Raw queries, string concatenation in SQL, `.raw()`, `.execute()` |
| XSS | innerHTML, dangerouslySetInnerHTML, template unescaped output, document.write |
| Command Injection | exec, spawn, system, popen, backticks, subprocess |
| Path Traversal | fs.readFile with user input, open() with user path, file downloads |
| SSRF | HTTP client calls with user-controlled URLs |
| Deserialization | pickle.loads, unserialize, yaml.load, JSON.parse of untrusted |

### Phase 4: Check Auth at Every Boundary

For every endpoint that handles sensitive data or actions:
- [ ] Is authentication required? (middleware, decorator, guard)
- [ ] Is authorization checked? (role check, ownership validation)
- [ ] Can the auth check be bypassed? (missing middleware, wrong order)
- [ ] Are there privilege escalation paths? (role manipulation, parameter tampering)

### Phase 5: Framework-Specific Checks

#### Express/Node.js
- Missing `helmet()` security headers
- `cors({ origin: '*' })` overly permissive CORS
- `express.json()` without size limits (DoS)
- Missing CSRF protection on state-changing endpoints
- `eval()` or `Function()` with user input
- `child_process.exec` with string interpolation

#### Django
- `@csrf_exempt` on state-changing views
- `.raw()` or `.extra()` SQL queries
- `|safe` template filter on user content
- `ALLOWED_HOSTS = ['*']`
- Missing `@login_required` on sensitive views
- `pickle` deserialization of user data
- DEBUG=True in production settings

#### Flask
- Missing `@login_required` decorators
- `render_template_string()` with user input (SSTI)
- `send_file()` / `send_from_directory()` with user-controlled paths
- Missing CSRF (Flask-WTF not configured)

#### Rails
- `params.permit!` (mass assignment)
- `html_safe` or `raw` on user content
- `find_by_sql` with string interpolation
- Missing `protect_from_forgery`
- `send_file` with user-controlled path
- Weak `before_action` chains that can be skipped

#### Spring Boot
- Missing `@PreAuthorize` or `@Secured`
- SpEL injection in `@Value` or `@PreAuthorize`
- XML External Entity (XXE) in XML parsers
- Mass assignment via `@ModelAttribute`
- Actuator endpoints exposed without auth (`/actuator/env`, `/actuator/heapdump`)

#### Laravel
- Mass assignment (missing `$fillable` / `$guarded`)
- Raw DB queries with `DB::raw()`
- Blade `{!! !!}` unescaped output
- Missing middleware on routes
- Insecure deserialization in queued jobs

### Phase 6: Review Crypto & Secrets

```bash
# Hardcoded secrets
grep -rn "password\s*=\s*['"]\|secret\s*=\s*['"]\|api_key\s*=\s*['"]\|token\s*=\s*['"]" --include="*.py" --include="*.js" --include="*.ts" --include="*.rb" --include="*.java" --include="*.go" --include="*.env*"
# Weak crypto
grep -rn "md5\|sha1\|DES\|ECB\|RC4" --include="*.py" --include="*.js" --include="*.java"
# JWT issues
grep -rn "algorithm.*none\|verify.*false\|HS256" --include="*.py" --include="*.js" --include="*.ts"
```

## Priority Order
1. Auth/authz boundaries (highest bounty value)
2. Input handling at trust boundaries
3. Data access patterns (IDOR)
4. Crypto and secrets
5. Configuration issues
