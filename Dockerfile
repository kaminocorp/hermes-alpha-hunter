# =============================================================================
# Hermes Alpha Hunter — Persistent Telegram gateway for bug bounty hunting
# =============================================================================
# Build:  docker build -t hermes-alpha-hunter .
# Deploy: flyctl deploy --remote-only
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
RUN pip install --no-cache-dir -e '.[all]' && pip install --no-cache-dir aiohttp elephantasm

# ── Hermes home structure (~/.hermes) ────────────────────────────────────────
RUN mkdir -p /root/.hermes/skills /root/.hermes/sessions /root/.hermes/logs \
             /root/.hermes/memories /root/.hermes/cron /workspace/reports \
             /workspace/targets

# SOUL.md — the Hunter's identity and methodology
COPY hunter/SOUL.md /root/.hermes/SOUL.md

# Config — tuned for persistent gateway mode
COPY hunter/config.yaml /root/.hermes/config.yaml

# Skills — security analysis skills
COPY hunter/skills/ /root/.hermes/skills/

# Hooks — Elephantasm long-term memory integration
COPY hunter/hooks/ /root/.hermes/hooks/

# ── Boot script ──────────────────────────────────────────────────────────────
COPY hunter/boot.sh /app/boot.sh
RUN chmod +x /app/boot.sh

# ── Git config (for cloning targets and pushing reports) ─────────────────────
RUN git config --global user.name "Hermes Alpha Hunter" \
    && git config --global user.email "hunter@hermes.nousresearch.com" \
    && git config --global init.defaultBranch main

# ── Runtime ──────────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV HERMES_HOME=/root/.hermes
ENV HERMES_YOLO_MODE=1

ENTRYPOINT ["/app/boot.sh"]
