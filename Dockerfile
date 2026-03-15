# =============================================================================
# Hermes Alpha Hunter — One-shot bug bounty agent for Fly.io Machines
# =============================================================================
# Build:  docker build -t hermes-alpha-hunter .
# Run:    fly machine run hermes-alpha-hunter -e TARGET_REPO=... -e OPENROUTER_API_KEY=...
# =============================================================================

FROM python:3.11-slim

# ── System deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        jq \
        ripgrep \
        ca-certificates \
        gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Application code ────────────────────────────────────────────────────────
WORKDIR /app
COPY . /app

# ── Python deps ──────────────────────────────────────────────────────────────
RUN pip install --no-cache-dir -e '.[all]'

# ── Hermes home structure (~/.hermes) ────────────────────────────────────────
RUN mkdir -p /root/.hermes/skills /root/.hermes/sessions /root/.hermes/logs \
             /root/.hermes/memories /root/.hermes/cron

# SOUL.md — the Hunter's identity and methodology
COPY hunter/SOUL.md /root/.hermes/SOUL.md

# Config — tuned for autonomous security analysis
COPY hunter/config.yaml /root/.hermes/config.yaml

# Skills — copy hunter-specific skills into the agent's skills directory
# (merged with any bundled skills from the repo on first run via skills_sync)
COPY hunter/skills/ /root/.hermes/skills/

# ── Boot script ──────────────────────────────────────────────────────────────
COPY hunter/boot.sh /app/boot.sh
RUN chmod +x /app/boot.sh

# ── Git config (for pushing reports) ─────────────────────────────────────────
RUN git config --global user.name "Hermes Alpha Hunter" \
    && git config --global user.email "hunter@hermes.nousresearch.com" \
    && git config --global init.defaultBranch main

# ── Runtime ──────────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV HERMES_HOME=/root/.hermes
ENV HERMES_YOLO_MODE=1

ENTRYPOINT ["/app/boot.sh"]
