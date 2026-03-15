---
title: Authentication Bypass
description: Find authentication and session management vulnerabilities
tags: [security, authentication, jwt, session, oauth]
---
# Authentication Bypass

## When to Use
When analyzing any application with user authentication. Focus on login flows,
session management, password reset, OAuth, JWT, and 2FA implementations.

## Procedure

### 1. Map the Auth System
```bash
# Find auth-related files
grep -rn "login\|logout\|register\|signup\|signin\|authenticate\|authorize" -l --include="*.js" --include="*.ts" --include="*.py" --include="*.rb" --include="*.java"

# Find middleware/decorators
grep -rn "isAuthenticated\|isAuthorized\|requireAuth\|login_required\|@authenticated\|@auth\|protect\|guard" --include="*.js" --include="*.ts" --include="*.py" --include="*.rb"

# Find the auth strategy
grep -rn "passport\|jwt\|jsonwebtoken\|bcrypt\|session\|cookie\|oauth\|saml\|ldap" -l --include="*.js" --include="*.ts" --include="*.py"
```

### 2. JWT Vulnerabilities

#### 2a. Algorithm Confusion
```bash
grep -rn "algorithm\|algorithms\|jwt\.verify\|jwt\.decode" --include="*.js" --include="*.ts" --include="*.py"
```
```javascript
// VULNERABLE: Accepts 'none' algorithm
jwt.verify(token, secret, { algorithms: ['HS256', 'none'] });

// VULNERABLE: No algorithm restriction
jwt.verify(token, secret);  // Attacker can use 'none' or switch HS256↔RS256

// SECURE: Explicit algorithm
jwt.verify(token, secret, { algorithms: ['HS256'] });
```

#### 2b. Weak Secrets
```bash
# Hardcoded JWT secrets
grep -rn "jwt.*secret\|JWT_SECRET\|token.*secret" --include="*.js" --include="*.ts" --include="*.py" --include="*.env*" --include="*.yaml"
```
Common weak secrets: `secret`, `password`, `123456`, `changeme`, `your-secret-key`, app name

#### 2c. Missing Expiration
```javascript
// VULNERABLE: No expiry — token valid forever
jwt.sign({ userId: user.id }, secret);

// SECURE: Short-lived tokens
jwt.sign({ userId: user.id }, secret, { expiresIn: '1h' });
```

#### 2d. Token Not Invalidated on Logout/Password Change
```bash
# Check logout implementation
grep -rn "logout\|signout\|sign.out" --include="*.js" --include="*.ts" --include="*.py" -A 10
# If it only clears the cookie but doesn't blacklist the token → vulnerability
```

#### 2e. Information Leakage in JWT
```bash
# Check what's stored in JWT payload (decoded tokens reveal data)
grep -rn "jwt\.sign\|encode.*jwt\|create.*token" --include="*.js" --include="*.ts" --include="*.py" -A 5
# Sensitive data in payload: email, role, permissions, internal IDs
```

### 3. Session Management

#### 3a. Session Fixation
```bash
# Check if session ID regenerates after login
grep -rn "regenerate\|session\.id\|session_id\|rotate.*session" --include="*.js" --include="*.ts" --include="*.py" --include="*.rb"
```

#### 3b. Cookie Security
```bash
grep -rn "cookie\|set-cookie\|httpOnly\|secure\|sameSite\|domain\|path" --include="*.js" --include="*.ts" --include="*.py" --include="*.rb"
```
Check: `httpOnly: true`, `secure: true`, `sameSite: 'strict'` or `'lax'`

#### 3c. Session Timeout
```bash
grep -rn "maxAge\|expires\|timeout.*session\|session.*timeout\|SESSION_COOKIE_AGE" --include="*.js" --include="*.ts" --include="*.py"
```

### 4. Password Reset Flaws

```bash
grep -rn "reset.*password\|forgot.*password\|password.*reset\|reset.*token" -l --include="*.js" --include="*.ts" --include="*.py" --include="*.rb"
```

Check for:
- **Token predictability**: Is it a random UUID or derived from user data?
- **Token reuse**: Can a reset token be used multiple times?
- **Token expiry**: Does it expire? How long?
- **Rate limiting**: Can you brute-force short tokens?
- **Email enumeration**: Does "user not found" vs "reset email sent" differ?
- **Host header injection**: Can you manipulate the reset URL domain?

```python
# VULNERABLE: Predictable reset token
import hashlib
token = hashlib.md5(user.email.encode()).hexdigest()

# SECURE: Random token
import secrets
token = secrets.token_urlsafe(32)
```

### 5. OAuth/OIDC Misconfigurations

```bash
grep -rn "oauth\|openid\|oidc\|callback\|redirect_uri\|client_id\|client_secret\|authorization_code\|implicit" --include="*.js" --include="*.ts" --include="*.py" --include="*.rb" -l
```

Check for:
- **Open redirect in callback**: Is `redirect_uri` validated? Can you inject an external URL?
- **State parameter missing**: CSRF on OAuth flow
- **Client secret exposed**: In frontend code or public config
- **Token leakage**: Access tokens in URL fragments, referrer headers
- **Scope escalation**: Can you request more permissions than intended?

### 6. 2FA/MFA Bypasses

```bash
grep -rn "2fa\|mfa\|totp\|otp\|two.factor\|multi.factor\|verification.*code" --include="*.js" --include="*.ts" --include="*.py" -l
```

Check for:
- **Missing 2FA on sensitive operations**: Only on login but not password change?
- **Brute-force OTP**: No rate limiting on code attempts
- **Backup codes**: Predictable or unlimited?
- **Race condition**: Submit login and 2FA simultaneously
- **Direct endpoint access**: Skip 2FA by hitting post-login endpoints directly

### 7. Race Conditions in Auth

```bash
# Check for non-atomic auth operations
grep -rn "if.*exists.*create\|find.*then.*save\|check.*then.*update" --include="*.js" --include="*.ts" --include="*.py" -A 5
```

Time-of-check to time-of-use (TOCTOU) in:
- Registration (duplicate accounts)
- Coupon/code redemption
- Balance/credit operations
- Invitation acceptance

## High-Value Targets
1. JWT implementation flaws (algorithm confusion, weak secrets)
2. IDOR in password reset (access other users' reset flow)
3. OAuth redirect_uri bypass
4. Missing auth middleware on sensitive endpoints
5. Privilege escalation via parameter tampering
