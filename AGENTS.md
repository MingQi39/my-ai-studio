# AGENTS.md

## Working Style

- Communicate with the user in Chinese unless they ask for another language.
- Prefer small, complete changes; read nearby files and follow local patterns before inventing abstractions.
- Do not do drive-by refactors while solving an unrelated task.
- Pause for non-obvious product decisions, destructive ops, auth/security, or deploy/env changes.

## Skill Routing

完整用法目录（怎么选、主流程、复制口令）见 [`docs/agents/skills-guide.md`](docs/agents/skills-guide.md)。

Unsure which skill → `/which-skill`. Matt engineering map only → `/ask-matt`.

- New feature / requirement change in this codebase → start with `/grill-with-docs` (builds shared language via `CONTEXT.md` / ADRs).
- After alignment, multi-session work → `/to-spec` → `/to-tickets` → `/implement` per ticket (fresh context each).
- Small, concrete behaviour → `/tdd` or `/implement` in the same session.
- Hard bugs / flakes / perf regressions → `/diagnosing-bugs`.
- Codebase becoming hard for agents → `/improve-codebase-architecture`.
- First-time engineering-skill use in a fresh clone → `/setup-matt-pocock-skills` (already done if `docs/agents/*` exists).

## Project Snapshot

- Product: Qi AI Studio — full-stack AI chat workbench + travel-planning agent.
- Backend: FastAPI (`backend/`), JWT auth, SSE chat, BYOK model configs, travel tools under `/api/v1/travel/*`.
- Frontend: React 18 + Vite + Tailwind + Radix (`frontend/`), 9-language i18n.
- Ops: local `./scripts/start-macos-linux.sh`; Docker via `./scripts/docker-deploy.sh` (frontend published on port 8081).

## Agent skills

- Skill usage guide → [`docs/agents/skills-guide.md`](docs/agents/skills-guide.md).

### Issue tracker

Issues live in GitHub Issues for `MingQi39/my-ai-studio` (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.

## Commands

- Local dev: `./scripts/start-macos-linux.sh` (env: `backend/.env`)
- Frontend: http://localhost:11010 · Backend: http://localhost:10011 · API docs: http://localhost:10011/docs
- Docker: `./scripts/docker-deploy.sh` (env: root `.env`)

## Verification Rules

- Prefer the smallest relevant check for the change (targeted test, API hit, or UI smoke).
- Docs/config-only usually needs diff review only.
- If verification was skipped, say so in the final response.

## Final Response

- Briefly list what changed, what was verified, and any assumptions or follow-up risks.
