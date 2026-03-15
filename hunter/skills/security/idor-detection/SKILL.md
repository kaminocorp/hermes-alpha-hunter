---
title: IDOR Detection
description: Find broken access control and insecure direct object reference vulnerabilities
tags: [security, idor, access-control, authorization]
---
# IDOR Detection

## When to Use
When analyzing any application with user-specific resources, multi-tenant data, or role-based access.
IDOR is the #1 bounty-earning vulnerability class. Focus here.

## What is IDOR?
Insecure Direct Object Reference — when an application exposes internal object identifiers (IDs)
and fails to verify that the requesting user is authorized to access the referenced object.

## Procedure

### 1. Identify Object References
Find all places where object IDs appear in:
```bash
# URL parameters
grep -rn "req\.params\." --include="*.js" --include="*.ts"
grep -rn "request\.args\|request\.view_args\|<int:" --include="*.py"
grep -rn "params\[:" --include="*.rb"

# Query strings
grep -rn "req\.query\." --include="*.js" --include="*.ts"
grep -rn "request\.args\.get\|request\.GET" --include="*.py"

# Request body
grep -rn "req\.body\." --include="*.js" --include="*.ts"
grep -rn "request\.json\|request\.form\|request\.data" --include="*.py"

# Headers (less common but possible)
grep -rn "req\.headers\." --include="*.js" --include="*.ts"
```

### 2. Trace to Data Access
For each object reference, trace where it's used to fetch data:
```bash
# Database lookups by ID
grep -rn "findById\|findByPk\|findOne.*_id\|get_object_or_404\|Model\.objects\.get" --include="*.js" --include="*.ts" --include="*.py"

# Generic patterns
grep -rn "\.find(\|\.findOne(\|\.get(\|\.filter(" --include="*.js" --include="*.ts" --include="*.py"
```

### 3. Check Authorization
For each data access, verify:

**Question 1: Is there an auth check at all?**
- Is the endpoint behind auth middleware?
- Can unauthenticated users hit this endpoint?

**Question 2: Is there an ownership check?**
```javascript
// VULNERABLE: Auth check exists, but no ownership verification
router.get('/api/orders/:id', authenticate, async (req, res) => {
    const order = await Order.findById(req.params.id);  // Any user can access any order
    res.json(order);
});

// SECURE: Ownership verified
router.get('/api/orders/:id', authenticate, async (req, res) => {
    const order = await Order.findOne({ _id: req.params.id, userId: req.user.id });
    if (!order) return res.status(404).json({ error: 'Not found' });
    res.json(order);
});
```

**Question 3: Can the authorization be bypassed?**
- Parameter pollution: Can you send `userId` in the request body to override `req.user.id`?
- Type juggling: Does `"1" == 1` cause issues?
- Null/undefined checks: What happens with missing ownership fields?

### 4. Common IDOR Patterns

#### Pattern A: Horizontal Privilege Escalation
User A can access User B's data by changing the ID.
```python
# VULNERABLE
@app.route('/api/profile/<user_id>')
@login_required
def get_profile(user_id):
    return User.query.get(user_id).to_dict()  # No check: user_id == current_user.id
```

#### Pattern B: Vertical Privilege Escalation
Regular user can access admin resources.
```javascript
// VULNERABLE: Only checks auth, not role
router.get('/api/admin/users', authenticate, async (req, res) => {
    const users = await User.find({});  // Any authenticated user gets all users
    res.json(users);
});
```

#### Pattern C: Mass Assignment Leading to IDOR
User updates their own record but can modify the owner/role field.
```javascript
// VULNERABLE: Accepts all body fields including userId
router.put('/api/orders/:id', authenticate, async (req, res) => {
    await Order.findByIdAndUpdate(req.params.id, req.body);  // Can change userId field!
});
```

#### Pattern D: Predictable IDs
Sequential integer IDs that can be enumerated.
```bash
# Check if IDs are sequential integers vs UUIDs
grep -rn "autoIncrement\|SERIAL\|AUTO_INCREMENT\|IntegerField.*primary" --include="*.js" --include="*.py" --include="*.sql"
```

#### Pattern E: Reference in File Paths
```javascript
// VULNERABLE: User controls file path
app.get('/api/documents/download', auth, (req, res) => {
    res.sendFile(`/uploads/${req.query.filename}`);  // Path traversal + IDOR
});
```

#### Pattern F: Nested Resource IDOR
```javascript
// VULNERABLE: Checks parent ownership but not child
router.get('/api/projects/:projectId/tasks/:taskId', auth, async (req, res) => {
    const project = await Project.findOne({ _id: req.params.projectId, owner: req.user.id });
    if (!project) return res.status(404).send();
    const task = await Task.findById(req.params.taskId);  // Task might belong to different project!
    res.json(task);
});
```

### 5. GraphQL-Specific IDOR
```bash
# GraphQL resolvers often lack per-field auth
grep -rn "resolve\|Query\|Mutation" --include="*.js" --include="*.ts" --include="*.py" | grep -i "user\|profile\|account\|order\|document"
```
GraphQL is IDOR-rich because:
- Nested queries can leak data through relationships
- Introspection reveals the full schema
- Batch queries can enumerate IDs
- Resolvers often skip authorization

### 6. API Versioning IDOR
```bash
# Check if old API versions lack auth that new versions have
grep -rn "/api/v1\|/api/v2\|/v1/\|/v2/" --include="*.js" --include="*.ts" --include="*.py"
```
Old API versions often have weaker authorization than newer ones.

## Report Template for IDOR
```
Title: IDOR in [endpoint] allows [action] on other users' [resource]
Severity: High (usually)
CVSS: 7.5-8.5 typical

Description:
The [endpoint] endpoint accepts a [resource] ID as a parameter but does not
verify that the authenticated user owns or has permission to access the
referenced [resource]. An attacker can enumerate or guess [resource] IDs to
access, modify, or delete other users' data.

Affected Code:
File: [path], Line: [number]
[code snippet showing missing ownership check]

Impact:
An authenticated attacker can [read/modify/delete] any user's [resource],
including sensitive data such as [specific data types].
```
