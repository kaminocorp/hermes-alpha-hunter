---
title: Vulnerability Report Writing
description: Write bounty-ready vulnerability reports in HackerOne format
tags: [security, reporting, hackerone, bounty]
---
# Vulnerability Report Writing

## When to Use
After verifying a vulnerability. Every confirmed finding must have a report.

## Report Standards
- One report per vulnerability (don't bundle)
- Actionable: maintainers can fix from the report alone
- Honest severity: inflated reports damage credibility
- No speculation: only report what you can prove
- Clear reproduction: someone else should be able to verify

## Report Template

Create the file at: `/reports/VULN-{number}-{short-description}.md`

```markdown
# [Vuln Type] in [Component] allows [Impact]

## Summary
One paragraph: what the vulnerability is, where it is, and what an attacker can do.

## Severity
- **Rating**: Critical / High / Medium / Low
- **CVSS 3.1 Score**: X.X
- **CVSS Vector**: CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N
- **Bounty Range**: $X,XXX - $X,XXX (estimated)

## Affected Component
- **Repository**: [org/repo]
- **File**: [path/to/file.ext]
- **Line(s)**: [line numbers]
- **Function**: [function name]
- **Version/Commit**: [commit hash or version tag]

## Vulnerability Details

### Description
Detailed technical explanation of the vulnerability. Include:
- What the code does
- Why it's vulnerable
- What input triggers the vulnerability
- What the dangerous behavior is

### Root Cause
The specific code pattern or logic error that creates the vulnerability.

```[language]
// Vulnerable code (with file path and line numbers in comments)
[paste the vulnerable code block]
```

### Attack Scenario
Step-by-step exploitation path:
1. Attacker does X
2. This causes Y
3. Which results in Z

## Proof of Concept

### Prerequisites
- Account type needed (if any)
- Setup steps

### Steps to Reproduce
1. [Detailed step with exact values]
2. [Next step]
3. [Observe the vulnerability]

### Code-Level Trace
```
User Input: [what the attacker sends]
     ↓
Entry Point: [file:line — function that receives input]
     ↓
Processing: [file:line — how input is handled]
     ↓
Sink: [file:line — where the dangerous operation happens]
     ↓
Impact: [what happens — data leak, code execution, etc.]
```

## Impact Assessment

### Confidentiality
[What data can be accessed? How sensitive is it?]

### Integrity
[What data can be modified? What operations can be performed?]

### Availability
[Can the service be disrupted?]

### Business Impact
[Real-world consequences: user data breach, financial loss, compliance violation]

## Suggested Remediation

### Immediate Fix
```[language]
// Secure version of the vulnerable code
[paste the fixed code]
```

### Long-term Recommendations
- [Architectural improvement]
- [Additional hardening]
- [Testing recommendation]

## References
- [Link to relevant OWASP page]
- [Link to CWE entry]
- [Link to similar CVEs if any]
```

## CVSS 3.1 Quick Reference

### Attack Vector (AV)
- Network (N): Exploitable over the network — most web vulns
- Adjacent (A): Requires same network segment
- Local (L): Requires local access
- Physical (P): Requires physical access

### Attack Complexity (AC)
- Low (L): No special conditions needed
- High (H): Requires specific conditions (race, config, etc.)

### Privileges Required (PR)
- None (N): No auth needed
- Low (L): Normal user account
- High (H): Admin/privileged account

### User Interaction (UI)
- None (N): No user action needed
- Required (R): Victim must click/visit something

### Scope (S)
- Unchanged (U): Impact stays within the vulnerable component
- Changed (C): Impact extends beyond (e.g., XSS affecting other origins)

### Confidentiality/Integrity/Availability (C/I/A)
- None (N): No impact
- Low (L): Limited impact
- High (H): Total compromise of that aspect

### Common Scores
| Vulnerability Type | Typical CVSS | Typical Rating |
|---|---|---|
| Unauthenticated RCE | 9.8 | Critical |
| Auth bypass (full) | 9.1 | Critical |
| SQL injection (auth'd) | 8.5 | High |
| IDOR (read sensitive data) | 7.5 | High |
| IDOR (modify data) | 8.1 | High |
| Stored XSS (admin context) | 8.0 | High |
| SSRF (internal access) | 7.2 | High |
| CSRF (state-changing) | 6.5 | Medium |
| Reflected XSS | 6.1 | Medium |
| Info disclosure (limited) | 5.3 | Medium |
| Open redirect | 4.7 | Medium |
| Missing security headers | 3.7 | Low |

## HackerOne Formatting Tips
- Use markdown (HackerOne renders it)
- Include code blocks with syntax highlighting
- Attach screenshots/videos for UI-related vulns
- Reference CWE numbers (e.g., CWE-639 for IDOR)
- Use their severity ratings: Critical, High, Medium, Low
- Be concise in the summary, detailed in reproduction steps
- Don't include irrelevant scanner output or noise

## Quality Checklist Before Submission
- [ ] Vulnerability is real and confirmed (not theoretical)
- [ ] Exploitation path is clear and complete
- [ ] Impact is assessed honestly (not inflated)
- [ ] Code references include file paths and line numbers
- [ ] Reproduction steps are detailed enough for someone else to verify
- [ ] Suggested fix is correct and addresses the root cause
- [ ] CVSS score matches the actual impact
- [ ] Report is in scope for the bounty program
- [ ] No real credentials or sensitive data included in the report
- [ ] Language is professional and clear

## Summary File
Also create `/reports/SUMMARY.md`:
```markdown
# Security Audit Summary

## Target
- Repository: [org/repo]
- Commit: [hash]
- Date: [YYYY-MM-DD]
- Program: [bounty program URL]

## Findings
| # | Title | Severity | CVSS | File |
|---|-------|----------|------|------|
| 1 | [title] | High | 7.5 | VULN-1-short-desc.md |
| 2 | [title] | Medium | 5.3 | VULN-2-short-desc.md |

## Scope Verification
[Document that the target was confirmed in-scope]

## Methodology
[Brief description of analysis approach and areas covered]

## Areas Not Covered
[Parts of the codebase not analyzed and why]
```
