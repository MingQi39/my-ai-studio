# Security & secrets (open source)

## What is **not** in this repository

- No real LLM API keys (`sk-...`, OpenRouter, etc.) in source code
- No committed `.env` (only `backend/.env.example` with placeholders)
- `backend/config/providers.yaml` stores **environment variable names** only (`api_key_env`), not key values
- User keys are **not** hardcoded in the frontend; they are submitted at runtime via the connection UI

## What **is** stored when you run the app (local / your server)

| Location | Content | In git? |
|----------|---------|--------|
| `backend/myai_studio.db` | Users, sessions, **encrypted** model API keys | No — `*.db` is gitignored |
| `backend/.encryption_key` | Fernet key used to encrypt API keys in the DB | No — `.encryption_key` is gitignored |
| `backend/.env` | `SECRET_KEY`, `API_KEY_ENCRYPTION_KEY`, optional provider env vars | No — `.env` is gitignored |
| Browser `localStorage` | JWT `auth_token`, user profile, language preference | N/A (client only) |

API keys flow: user enters key in UI → backend encrypts with `API_KEY_ENCRYPTION_KEY` or `.encryption_key` → saved in `model_configs.encrypted_api_key`.

## Before you `git push`

1. Copy `backend/.env.example` → `backend/.env` and set strong random values:
   - `SECRET_KEY` (JWT signing)
   - `API_KEY_ENCRYPTION_KEY` (32-byte Fernet key; or let dev mode create `.encryption_key`)
2. Never commit: `.env`, `.encryption_key`, `*.db`, `*.sqlite`, `node_modules/`, `.venv/`, `frontend/build/`
3. If you already ran the app locally, delete or exclude `backend/myai_studio.db` and `backend/.encryption_key` from any commit
4. Rotate any key that was ever committed by mistake

## Production checklist

- Change default `SECRET_KEY` in `backend/app/config.py` is only a **fallback**; override via `.env`
- Use HTTPS in production; restrict `CORS_ORIGINS` to your real frontend origin
- Treat `myai_studio.db` and `.encryption_key` as sensitive backups

## Optional: OMP local catalog endpoint

`GET /api/v1/models/omp/catalog` reads `~/.omp/agent/models.yml` on the **server host**. It does not return raw API key strings, but may expose file paths and base URLs from that file. Disable or protect this route if you do not use OMP.
