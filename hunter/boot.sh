#!/usr/bin/env bash
# =============================================================================
# Hermes Alpha Hunter — Boot Script
# One-shot execution: analyse target, write reports, push results, exit.
# =============================================================================
set -euo pipefail

# ── Required env vars ────────────────────────────────────────────────────────
: "${TARGET_REPO:?TARGET_REPO is required (e.g. https://github.com/org/repo)}"
: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY is required}"

# ── Optional env vars ────────────────────────────────────────────────────────
TARGET_PROGRAM="${TARGET_PROGRAM:-}"           # Bug bounty program URL (HackerOne, Bugcrowd, etc.)
MISSION_ID="${MISSION_ID:-$(date +%Y%m%d_%H%M%S)_$$}"
REPORTS_REPO="${REPORTS_REPO:-}"               # Git remote to push reports to
REPORTS_BRANCH="${REPORTS_BRANCH:-reports}"     # Branch name for reports
MAX_TURNS="${MAX_TURNS:-100}"                  # Override max agent turns
HUNTER_MODEL="${HUNTER_MODEL:-anthropic/claude-sonnet-4-20250514}"

echo "=============================================="
echo "  Hermes Alpha Hunter — Mission ${MISSION_ID}"
echo "=============================================="
echo "  Target repo:    ${TARGET_REPO}"
echo "  Bounty program: ${TARGET_PROGRAM:-<not specified>}"
echo "  Model:          ${HUNTER_MODEL}"
echo "  Max turns:      ${MAX_TURNS}"
echo "=============================================="

# ── Write .env for the agent ─────────────────────────────────────────────────
cat > /root/.hermes/.env <<ENVEOF
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
ENVEOF

# Add optional keys if provided
[ -n "${OPENAI_API_KEY:-}" ]    && echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >> /root/.hermes/.env
[ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> /root/.hermes/.env
[ -n "${GITHUB_TOKEN:-}" ]      && echo "GITHUB_TOKEN=${GITHUB_TOKEN}" >> /root/.hermes/.env

chmod 600 /root/.hermes/.env

# ── Clone the target ─────────────────────────────────────────────────────────
WORK_DIR="/workspace/${MISSION_ID}"
mkdir -p "${WORK_DIR}"
echo "[*] Cloning ${TARGET_REPO} ..."

clone_args=(--depth 50)  # Shallow clone — enough history for git blame/log
if [ -n "${GITHUB_TOKEN:-}" ]; then
    # Inject token for private repos
    AUTHED_URL="$(echo "${TARGET_REPO}" | sed "s|https://|https://${GITHUB_TOKEN}@|")"
    git clone "${clone_args[@]}" "${AUTHED_URL}" "${WORK_DIR}/repo" 2>&1 || \
        git clone "${clone_args[@]}" "${TARGET_REPO}" "${WORK_DIR}/repo" 2>&1
else
    git clone "${clone_args[@]}" "${TARGET_REPO}" "${WORK_DIR}/repo" 2>&1
fi

echo "[+] Clone complete: $(du -sh "${WORK_DIR}/repo" | cut -f1)"

# ── Prepare reports directory ────────────────────────────────────────────────
REPORTS_DIR="${WORK_DIR}/reports"
mkdir -p "${REPORTS_DIR}"

# ── Build mission prompt ─────────────────────────────────────────────────────
MISSION_PROMPT="# Mission ${MISSION_ID}

## Target
- **Repository**: ${TARGET_REPO}
- **Local path**: ${WORK_DIR}/repo
- **Bounty program**: ${TARGET_PROGRAM:-Not specified — search for it using web_search}

## Objective
Perform a thorough security audit of the repository at \`${WORK_DIR}/repo\`.

Follow the methodology defined in your SOUL.md precisely:
1. **SCOPE CHECK** — Verify the bounty program scope. If TARGET_PROGRAM is provided, check that URL. Otherwise, search for the project's security policy and bounty program.
2. **RECONNAISSANCE** — Map the codebase architecture, identify attack surface areas, find entry points.
3. **DEEP ANALYSIS** — Systematically analyze high-value targets for real, exploitable vulnerabilities.
4. **VERIFICATION** — For each finding, verify it's exploitable. Build a proof-of-concept or trace the vulnerable code path.
5. **REPORTING** — Write detailed vulnerability reports to \`${REPORTS_DIR}/\`.

## Report Format
For each vulnerability found, create a file in \`${REPORTS_DIR}/\` named:
\`VULN-{number}-{short-description}.md\`

Each report should include:
- Title and severity (Critical/High/Medium/Low)
- CVSS score estimate
- Affected component and code location
- Description of the vulnerability
- Step-by-step reproduction / proof-of-concept
- Impact assessment
- Suggested remediation

Also create a summary file: \`${REPORTS_DIR}/SUMMARY.md\` with an overview of all findings.

## Rules
- Source code analysis ONLY. Do NOT probe any live systems.
- Do NOT extract or store real credentials/secrets.
- Work methodically. Quality over quantity.
- If the target has no bounty program or is out of scope, document that in SUMMARY.md and stop.

Begin."

# ── Run the agent ────────────────────────────────────────────────────────────
echo "[*] Starting Hermes agent ..."
cd "${WORK_DIR}/repo"

# Use hermes CLI in query mode (non-interactive, single query, exits on completion)
hermes chat \
    -q "${MISSION_PROMPT}" \
    -m "${HUNTER_MODEL}" \
    --yolo \
    2>&1 | tee "${WORK_DIR}/agent.log"

AGENT_EXIT=$?
echo "[*] Agent exited with code ${AGENT_EXIT}"

# ── Push reports (if any, and if a reports repo is configured) ───────────────
REPORT_COUNT=$(find "${REPORTS_DIR}" -name "*.md" 2>/dev/null | wc -l)
echo "[*] Reports generated: ${REPORT_COUNT}"

if [ "${REPORT_COUNT}" -gt 0 ] && [ -n "${REPORTS_REPO}" ]; then
    echo "[*] Pushing reports to ${REPORTS_REPO} (branch: ${REPORTS_BRANCH}) ..."

    cd "${REPORTS_DIR}"
    git init
    git checkout -b "${REPORTS_BRANCH}"

    if [ -n "${GITHUB_TOKEN:-}" ]; then
        AUTHED_REPORTS="$(echo "${REPORTS_REPO}" | sed "s|https://|https://${GITHUB_TOKEN}@|")"
        git remote add origin "${AUTHED_REPORTS}"
    else
        git remote add origin "${REPORTS_REPO}"
    fi

    git add -A
    git commit -m "Hunter mission ${MISSION_ID}: ${REPORT_COUNT} findings

Target: ${TARGET_REPO}
Program: ${TARGET_PROGRAM:-unknown}
Model: ${HUNTER_MODEL}
Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

    git push -u origin "${REPORTS_BRANCH}" --force 2>&1 || \
        echo "[!] Failed to push reports (non-fatal)"

    echo "[+] Reports pushed successfully"
elif [ "${REPORT_COUNT}" -gt 0 ]; then
    echo "[*] Reports written to ${REPORTS_DIR} (no REPORTS_REPO configured, skipping push)"
    echo "[*] Report files:"
    ls -la "${REPORTS_DIR}/"
else
    echo "[*] No reports generated"
fi

# ── Log mission summary ─────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  Mission ${MISSION_ID} — Complete"
echo "  Reports: ${REPORT_COUNT}"
echo "  Agent exit code: ${AGENT_EXIT}"
echo "=============================================="

# One-shot — the machine dies here
exit ${AGENT_EXIT}
