# Ahoum Sessions Marketplace

A small sessions marketplace: creators publish sessions, users book them, and the booking path is provably safe under concurrent load.

Status: in progress. See [PRD.md](PRD.md) for the full specification and [DECISIONS.md](DECISIONS.md), [DEBUGGING.md](DEBUGGING.md), [PROMPT_LOG.md](PROMPT_LOG.md) for the engineering write-ups.

## Quick start

```bash
cp .env.example .env      # then fill GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET
docker compose up --build
# open http://localhost:8080
```

(Full README written in the documentation phase.)
