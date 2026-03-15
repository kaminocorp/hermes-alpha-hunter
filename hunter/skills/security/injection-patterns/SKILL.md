---
title: Injection Pattern Detection
description: Find SQL injection, XSS, SSTI, command injection, SSRF, and path traversal
tags: [security, injection, sqli, xss, ssti, ssrf, command-injection]
---
# Injection Pattern Detection

## When to Use
During deep code analysis. Trace all paths from user input to dangerous sinks.

## Core Principle
Every injection follows the same pattern: **untrusted input reaches a sensitive sink without proper sanitization.**

Source (user input) → [missing/broken sanitization] → Sink (dangerous function)

## SQL Injection

### Search Patterns
```bash
# Raw SQL with string formatting
grep -rn "execute.*%s\|execute.*format\|execute.*f'" --include="*.py"
grep -rn "query.*\+.*req\|query.*\$\{\|query.*concat" --include="*.js" --include="*.ts"
grep -rn "execute.*\+.*\|prepareStatement.*\+" --include="*.java"

# ORM bypasses
grep -rn "\.raw(\|\.extra(\|RawSQL\|Sequel\.lit\|Arel\.sql" --include="*.py" --include="*.rb"
grep -rn "sequelize\.query\|knex\.raw\|\$queryRaw\|\$executeRaw" --include="*.js" --include="*.ts"

# Stored procedures with dynamic SQL
grep -rn "EXEC.*\+\|sp_executesql\|PREPARE.*FROM" --include="*.sql"
```

### ORM Bypass Patterns
```python
# Django — these bypass the ORM's parameterization
User.objects.raw(f"SELECT * FROM users WHERE name = '{name}'")
User.objects.extra(where=[f"name = '{name}'"])
User.objects.filter(name__regex=user_input)  # ReDoS + potential injection

# SQLAlchemy
db.engine.execute(f"SELECT * FROM users WHERE name = '{name}'")
db.session.execute(text(f"SELECT * FROM users WHERE name = '{name}'"))
```

```javascript
// Sequelize
sequelize.query(`SELECT * FROM users WHERE name = '${name}'`);
// Knex
knex.raw(`SELECT * FROM users WHERE name = '${name}'`);
// Prisma
prisma.$queryRaw`SELECT * FROM users WHERE name = ${name}`;  // SAFE — tagged template
prisma.$queryRawUnsafe(`SELECT * FROM users WHERE name = '${name}'`);  // VULNERABLE
```

### NoSQL Injection
```bash
grep -rn "\$where\|\$regex\|\$gt\|\$ne\|\$in" --include="*.js" --include="*.ts"
grep -rn "find(.*req\.body\|find(.*req\.query" --include="*.js" --include="*.ts"
```
```javascript
// VULNERABLE: MongoDB operator injection
db.users.find({ username: req.body.username, password: req.body.password });
// Attack: {"username": "admin", "password": {"$ne": ""}}

// SECURE: Type check inputs
const username = String(req.body.username);
```

## Cross-Site Scripting (XSS)

### Search Patterns
```bash
# React
grep -rn "dangerouslySetInnerHTML" --include="*.jsx" --include="*.tsx"

# Vue
grep -rn "v-html" --include="*.vue"

# Angular
grep -rn "bypassSecurityTrust\|innerHTML.*bind" --include="*.ts" --include="*.html"

# Server-side templates
grep -rn "\|safe\|mark_safe\|Markup(" --include="*.py" --include="*.html"  # Django/Jinja2
grep -rn "html_safe\|raw\b" --include="*.rb" --include="*.erb"              # Rails
grep -rn "{!!.*!!}" --include="*.blade.php"                                    # Laravel

# DOM-based XSS
grep -rn "document\.write\|eval(\|\.innerHTML.*=\|location\.hash\|window\.name" --include="*.js" --include="*.ts"
```

### Stored XSS (Highest Impact)
Trace user input that gets stored in DB and displayed to other users:
1. Find user-writable fields (comments, profiles, messages, titles)
2. Trace storage: input → validation → DB write
3. Trace rendering: DB read → template → HTML output
4. Check each step for sanitization

## Server-Side Template Injection (SSTI)

### Search Patterns
```bash
# Python (Jinja2, Mako)
grep -rn "render_template_string\|Template(.*request\|from_string\|MakoTemplate" --include="*.py"
grep -rn "Environment.*\|Template(" --include="*.py" -A 3

# Java (Freemarker, Thymeleaf, Velocity)
grep -rn "process.*template\|processTemplateFragment\|evaluate" --include="*.java"

# JavaScript (Pug, EJS, Handlebars)
grep -rn "ejs\.render\|pug\.render\|Handlebars\.compile" --include="*.js" --include="*.ts"
```

```python
# VULNERABLE: User input directly in template
@app.route('/greet')
def greet():
    name = request.args.get('name')
    return render_template_string(f'Hello {name}!')
    # Attack: {{7*7}} → "Hello 49!"
    # RCE: {{config.__class__.__init__.__globals__['os'].system('id')}}
```

## Command Injection

### Search Patterns
```bash
# Node.js
grep -rn "exec(\|execSync(\|spawn(\|execFile(" --include="*.js" --include="*.ts" -B2 -A2

# Python
grep -rn "os\.system\|os\.popen\|subprocess\.call\|subprocess\.Popen\|subprocess\.run" --include="*.py"
grep -rn "shell=True" --include="*.py"

# Ruby
grep -rn "system(\|exec(\|\`.*\$\|%x{\|IO\.popen" --include="*.rb"

# PHP
grep -rn "exec(\|system(\|passthru(\|shell_exec\|popen(" --include="*.php"
```

```javascript
// VULNERABLE: User input in shell command
const { exec } = require('child_process');
exec(`convert ${req.query.filename} output.png`);
// Attack: filename=;id;

// SECURE: Use execFile (no shell interpretation)
const { execFile } = require('child_process');
execFile('convert', [req.query.filename, 'output.png']);
```

## Server-Side Request Forgery (SSRF)

### Search Patterns
```bash
# User-controlled URLs in server requests
grep -rn "requests\.get\|requests\.post\|urllib\.request\|urlopen\|httpx" --include="*.py" -B3
grep -rn "fetch(\|axios\|http\.get\|https\.get\|got(" --include="*.js" --include="*.ts" -B3
grep -rn "HttpClient\|RestTemplate\|WebClient" --include="*.java" -B3

# Check if URL comes from user input
grep -rn "url.*=.*req\|uri.*=.*req\|endpoint.*=.*params\|webhook.*=.*body\|callback.*=.*" --include="*.js" --include="*.ts" --include="*.py"
```

### SSRF Sinks
- Image/file fetchers (avatar URL, import from URL)
- Webhook delivery
- PDF generators
- URL preview/unfurl
- Proxy/redirect endpoints
- API integration endpoints

### Bypass Patterns to Check For
If URL validation exists, check if it blocks:
- `http://127.0.0.1`, `http://localhost`, `http://0.0.0.0`
- `http://[::1]` (IPv6 localhost)
- `http://169.254.169.254` (cloud metadata)
- DNS rebinding (TOCTOU on DNS resolution)
- URL with credentials: `http://evil@authorized-host/`
- Redirect bypasses: URL to allowed host that 302s to internal

## Path Traversal

### Search Patterns
```bash
# File operations with user input
grep -rn "readFile\|readFileSync\|createReadStream\|sendFile\|send_file\|send_from_directory\|open(" --include="*.js" --include="*.ts" --include="*.py" -B3

# File downloads/uploads
grep -rn "download\|upload\|attachment\|filename.*req\|path.*req" --include="*.js" --include="*.ts" --include="*.py"

# Path construction
grep -rn "path\.join.*req\|os\.path\.join.*request\|\+.*\.\./\|concat.*filename" --include="*.js" --include="*.ts" --include="*.py"
```

```javascript
// VULNERABLE
app.get('/files/:name', (req, res) => {
    res.sendFile(path.join(__dirname, 'uploads', req.params.name));
    // Attack: name=../../etc/passwd
});

// Note: path.join does NOT prevent traversal:
// path.join('/uploads', '../../../etc/passwd') → '/etc/passwd'
```

## Verification Checklist
For each potential injection:
1. Can user input reach the sink? (trace the full path)
2. Is there sanitization? (is it sufficient?)
3. Can the sanitization be bypassed? (encoding, double-encoding, alternate syntax)
4. What's the impact? (data leak, RCE, account takeover)
5. Is there a realistic attack scenario?
