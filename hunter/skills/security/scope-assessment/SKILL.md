---
title: Scope Assessment
description: Verify target is in-scope for its bug bounty program before any analysis
tags: [security, scope, bounty, compliance]
---
# Scope Assessment

## When to Use
ALWAYS. This is the FIRST step of every mission. Before touching any code, verify the target is in-scope.
Skipping this step is a hard constraint violation.

## Procedure

### 1. Locate the Bounty Program
- If TARGET_PROGRAM URL is provided, navigate to it directly
- Otherwise, search: `web_search("<project-name> bug bounty program")`
- Check common platforms: HackerOne, Bugcrowd, Intigriti, Open Bug Bounty
- Check the repo for SECURITY.md, .github/SECURITY.md, or security policy links

### 2. Read Program Rules
On the program page, extract and document:
- **In-scope assets**: Which repos, domains, APIs are eligible
- **Out-of-scope areas**: Explicitly excluded targets, vuln types, or components
- **Vulnerability types accepted**: What classes of bugs they pay for
- **Severity thresholds**: Minimum severity for payout (some only pay High+)
- **Safe harbor**: Legal protections for researchers
- **Special rules**: Rate limiting, no automated scanning, etc.

### 3. Verify Our Target
Confirm ALL of these:
- [ ] The specific repository/asset we're analyzing is listed as in-scope
- [ ] Source code analysis is permitted (not just live testing)
- [ ] The vulnerability types we hunt for are accepted
- [ ] The program is currently active (not paused/closed)
- [ ] No special restrictions that prevent our methodology

### 4. Document Scope Decision
Write to stdout or a scope file:
```
SCOPE CHECK — <project-name>
Program: <URL>
Status: IN-SCOPE / OUT-OF-SCOPE / UNCLEAR
In-scope assets: <list>
Excluded: <list>
Accepted vuln types: <list>
Min severity: <threshold>
Notes: <any special rules>
```

### 5. Decision Gate
- **IN-SCOPE**: Proceed to reconnaissance
- **OUT-OF-SCOPE**: Write finding to SUMMARY.md explaining why, then STOP
- **UNCLEAR**: Try harder to find the program. If still unclear, document ambiguity and STOP
- **NO PROGRAM FOUND**: Document in SUMMARY.md, STOP. We only target programs with active bounties.

## Common Platforms

### HackerOne
- Program page: `https://hackerone.com/<org>`
- Scope tab shows eligible assets
- Policy section has rules
- "Managed" programs often have stricter rules

### Bugcrowd
- Program page: `https://bugcrowd.com/<org>`
- "Scope" section lists targets
- "Out of Scope" explicitly listed

### GitHub Security Advisories
- Check if the project accepts security reports via GitHub
- Look for SECURITY.md in repo root or .github/

## Red Flags (STOP immediately)
- Program says "no automated scanning" and our approach would violate that
- Target is a dependency/library not directly listed in scope
- Program is in "private" mode and we don't have an invitation
- The repo belongs to a different org than the bounty program covers
