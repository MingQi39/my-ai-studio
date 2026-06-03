# My AI Studio

A full-stack AI chat workspace: multi-provider LLM connections, streaming chat, session history, system prompts, and a polished React UI with **9-language i18n** (English default).

## Highlights (portfolio / Upwork)

- **International-ready UI** — English, 简体中文, 繁體中文, 日本語, 한국어, Español, Français, Deutsch, Русский
- **Language switcher** on login and in the sidebar; choice persisted in `localStorage`
- **Auto-detect** from browser locale + optional IP hint (never overrides an explicit user choice)
- **Bring-your-own-key** — pick DeepSeek, OpenAI, Gemini, Qwen, OpenRouter, or Ollama; enter API key + model ID in the connection dialog (same flow as FuFan LLM Playground)
- **FastAPI backend** — auth, sessions, streaming SSE chat, encrypted per-user model configs
- **Modern frontend** — React 18, Vite, Tailwind, Radix UI

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Configure DB / env as needed, then:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL (usually `http://localhost:5173`). The app talks to the API on the same host at port `8000` by default.

On first login, if you have no saved connection, the **model connection** dialog opens automatically. Configure a provider, paste your API key, set the model ID (e.g. `deepseek-chat`, `gpt-4o`), test, and save.

### Default language

- First visit (no saved preference): language is chosen from **your IP region** (via ipapi.co), then browser locale if lookup fails, else English.
- Examples: mainland China → `zh-CN`, Taiwan/HK/MO → `zh-TW`, Japan → `ja`, Korea → `ko`, US/UK → `en`.
- Use the **globe icon** to override; that choice is saved in `localStorage` and takes priority over IP on future visits.

## i18n structure

| Path | Role |
|------|------|
| `frontend/src/i18n/index.ts` | i18next init, detection, `setLanguage()`, `bindDocumentLanguage()` |
| `frontend/src/i18n/locales/*.json` | Translation namespaces |
| `frontend/src/components/LanguageSwitcher.tsx` | UI control |

To add a string: add the key to `en.json` first, mirror in other locale files, then use `const { t } = useTranslation()` and `t('section.key')` in components.

## Open source / before publishing

This repo does **not** ship real API keys. See [SECURITY.md](./SECURITY.md) for what stays local (database, `.encryption_key`, `.env`).

Quick check before first push:

```bash
# Should print nothing sensitive (only .env.example placeholders)
rg 'sk-[a-zA-Z0-9]{20,}' --glob '!node_modules' --glob '!.venv' --glob '!frontend/build'

# These must stay untracked
ls backend/.env backend/.encryption_key backend/*.db 2>/dev/null
```

Do not commit `node_modules/`, `backend/.venv/`, `frontend/build/`, `*.db`, or `.encryption_key`.

## License

Add your license file (e.g. MIT, Apache-2.0) before publishing.
