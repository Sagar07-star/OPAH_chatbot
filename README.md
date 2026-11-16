# CREATEchat

CREATEchat is OPAH's in-app assistant for clients booking photo and video production: it reads a client's
account, finds creatives, drafts plans and **proposes** changes that the client approves in the app. This
repository is a complete, runnable prototype built against the supplied contractor brief and prototype kit.

The rule the whole app is built around: **the AI proposes, the client approves, the server applies.** The
model has no tool that can apply a change, charge money, send a message, cancel a project or submit a review.

---

## What it does

- A polished production-management workspace: overview, projects, project detail, talent discovery,
  inspiration boards, documents and settings.
- A real OpenAI-powered assistant with function calling, persona selection, multi-turn memory and
  server-built cards.
- All 22 tools from the prototype contract, executed against the kit's actual JSON data and business rules.
- 17 target client workflows, from a cold-start idea to an approved deliverable, including counter-offers,
  reschedules, checkout and cancellation hand-offs, planning documents, drafts and an account briefing.
- An approval system that is ownership-checked, idempotent and impossible to trigger from chat text.
- Uploads (PDF/JPEG/PNG/WebP) validated by content, with PDF text extraction and image vision where the
  model supports it.

---

## Technology

| Layer | Choice |
| --- | --- |
| Frontend | React 18, Vite 5, TypeScript, Tailwind CSS, Lucide icons, React Router |
| Backend | Python 3.10+, FastAPI, Pydantic, OpenAI Python SDK |
| Assistant | OpenAI Chat Completions with tool calling, one call loop per turn, server-built reply envelope |
| Business data | The prototype kit's JSON dataset through `mock_tools.MockOPAH` (imported unchanged) |
| Assistant state | SQLite (conversations, working memory, uploads, support stubs, reported app errors) |

---

## Architecture

```
Browser (React)
   │  cookies: signed session identity (http-only)
   ▼
FastAPI  /api/chat ──► assistant core
                         ├─ personas        (intro, builder, scout, manager, planner, support)
                         ├─ context blocks  (viewer, project, profile, last search, artifacts, errors)
                         ├─ model loop      (OpenAI tool calling, max 6 rounds)
                         ├─ tool executor   (session identity → MockOPAH, support stubs)
                         ├─ cards           (proposal / hand-off / talent / summary … built from results)
                         └─ turn guards     (false change claims, PII redaction, one question)
   │
   ├─ SQLite: transcripts (200 kept / 20 sent), working memory, uploads
   └─ /api/proposals/{id}/approve | reject   ← the only path that writes a project change
                     │
                     ▼
              MockOPAH (unchanged kit) + data/*.json
```

Identity is decided by the backend from a signed cookie. It is never read from a message, a tool argument,
an uploaded file or model output. Tool results are returned to the model, but the cards the user sees are
built by the server from those same results.

### Personas

| Persona | When |
| --- | --- |
| Intro | No project selected, or a visitor |
| Project builder | Draft missing description, dates, location, budget, role, duration or call time |
| Talent scout | Draft with the core details set |
| Project manager | Paid, in flight, in review, completed or cancelled |
| Creative planner | Detour for shot lists, treatments, schedules, storyboards, scripts, mood boards |
| Support | Detour for "something is broken"; returns to the previous persona afterwards |

Persona selection is deterministic on the server (`app/assistant/personas.py`); the client never picks one.

---

## Getting started

### One command (Linux / macOS)

```bash
./run.sh
```

### One command (Windows)

```bat
run.bat
```

The launcher checks Python and Node, creates `backend/.venv`, installs both dependency sets if needed,
creates `.env` from `.env.example`, starts both servers, waits for health, prints the URLs and stops both on
Ctrl+C. You do not need two terminals.

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend | http://127.0.0.1:8000 |
| API docs | http://127.0.0.1:8000/docs |

### Configure the model

1. Copy `.env.example` to `.env` (the launcher does this for you if missing), or keep backend-only
   secrets in `backend/.env`. Both are read with `python-dotenv`; `backend/.env` wins over the root file
   and a blank assignment never overrides a real value. A real process environment variable beats both.
2. Create a **new** key at <https://platform.openai.com/api-keys> and put it in that file:

   ```dotenv
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini
   ```

3. Restart the backend. `OPENAI_MODEL` is configurable; any tool-calling chat model works.

The key is server-only. It is never sent to the browser, never logged, and never committed (`.env` is
ignored). Without a key the application still runs: projects, proposals, approvals, talent search and the
dashboard work, and the chat returns an explicit "model key not configured" message instead of pretending
to answer. **No hardcoded assistant replies are used anywhere.**

### Manual development

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --port 8000

cd frontend && npm install && npm run dev
```

---

## Demo accounts

Switch from the sidebar (or **Settings → Demo identities**). The signed session decides everything.

| Id | Who | Good for |
| --- | --- | --- |
| `clt_001` | Maya Torres, Coral Bloom Skincare | A project in every status, counter-offer, deliverables, reschedule, cancellation, briefing |
| `clt_002` | Jordan Pike, Pike & Co Realty | Fixed-price packages, checkout ($1,250 + $131 fee = $1,381) |
| `clt_003` | Sam Okafor, new client | Cold start with no projects |
| Visitor | Anonymous | Talent search and package information only |
| Creative | `tal_001` (Hana L.) | Proves creatives are blocked before the model runs |

The dataset day is **2026-11-16, noon Miami**. The mock clock is not replaced with the system date.

Projects to try: `prj_1001` (incomplete draft), `prj_1002` (complete draft; fashion specialist `tal_004` is
busy on its date), `prj_1003` (open counter-offer), `prj_1004` (paid; reschedule and cancellation previews),
`prj_1005` (shoot today), `prj_1006` (two folders waiting), `prj_1007` (completed), `prj_1008` (cancelled),
`prj_2001` (package finding a creative), `prj_2002` (assigned package, date change waiting), `prj_2003`
(completed package), `prj_2004` (draft ready for checkout).

---

## The approval system

1. The client asks for a change in chat.
2. The model calls a staging tool (`update_project`, `create_project`, `add_talent_to_project`,
   `respond_to_counter_offer`, `review_deliverable`, `share_document`, `create_board`).
3. The kit validates ownership, project state and every business rule, then saves a pending proposal with
   exact before/after values. Only a proposal id goes back to the model.
4. The server — not the model — builds the Approve / Decline card from the saved proposal.
5. The client taps Approve. `POST /api/proposals/{id}/approve` re-checks ownership and applies once.
6. A second tap returns `already_applied`; a declined proposal can never be applied; the saved transcript
   card updates to the outcome.

`approve_proposal` is deliberately absent from the tool registry and refused if the model names it. Typing
"yes", "do it" or "I approve" in chat never applies anything. A turn guard also rewrites any reply that
claims a change was made when nothing was applied.

## Hand-offs

Checkout, package booking, cancellation, messages and reviews never write. Each returns a prefilled screen
that the UI opens as a clearly labelled **demo hand-off**: subtotal, 10.5% fee, total and cancellation
terms; refund tier and amount; a typed-but-unsent message; a prefilled review. No card details are
collected, no money moves, nothing is sent or cancelled.

---

## API

All routes are under `/api`; identity comes from the `createchat_session` cookie.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Status, dataset day, model configuration |
| GET | `/api/session` | Current identity, demo accounts, threads, model info |
| POST | `/api/session/switch` | Switch demo identity (validated against the dataset) |
| POST | `/api/session/sign-out` | Back to visitor |
| POST | `/api/session/active-project` | Scope a conversation to a project |
| GET | `/api/session/conversations` | The client's threads |
| GET | `/api/account/summary` | Upcoming shoots, attention items, counts, projects, pending proposals |
| GET | `/api/projects` · `/api/projects/{id}` | Project list and full project |
| POST | `/api/projects/{id}/documents` | Save a planning document (client tap) |
| GET | `/api/documents` · `/api/boards` | Documents and inspiration boards |
| GET | `/api/talent/search` · `/api/talent/{id}` | Creative search and profile |
| GET | `/api/packages` · `/api/options` | Fixed-price packages, option catalogs |
| GET | `/api/deliverables` | Folders waiting for review |
| GET | `/api/proposals` · `/api/proposals/{id}` | Proposals and their state |
| POST | `/api/proposals/{id}/approve` · `/reject` | **The only write path** |
| POST | `/api/chat` | One assistant turn |
| GET | `/api/conversations/{id}/messages` | Saved transcript |
| POST | `/api/uploads` · GET `/api/uploads/{id}/raw` | Attach and preview files |
| GET/POST | `/api/support/tickets` | Support tickets (prototype stub) |
| POST | `/api/support/app-errors` | Client-reported failures for diagnosis |
| POST | `/api/demo/reset` | Reload the kit dataset (demo/testing only) |

---

## Testing

```bash
# The supplied kit's own tests (26, unchanged)
cd createchat-prototype-kit && ../backend/.venv/bin/python -m unittest test_mock_tools.py

# Backend suite (API, approvals, permissions, uploads, memory, assistant orchestration, scenarios)
cd backend && .venv/bin/python -m pytest

# Frontend type-check and production build
cd frontend && npm run build

# All 27 supplied scenarios
backend/.venv/bin/python scripts/run_scenarios.py --mode pipeline
backend/.venv/bin/python scripts/run_scenarios.py --mode live     # needs OPENAI_API_KEY
```

`--mode pipeline` verifies each scenario's contract against the implementation: tool existence, the tool
surface offered to that viewer, project ownership, reply types, and that approval is never a model tool.
`--mode live` runs the conversations against the real model and checks called tools, forbidden tools, reply
type, required/forbidden words and that **no project record changed without an approval**. It needs a key.

The assistant orchestration tests use a scripted model stand-in: they verify the tool loop, cards, guards,
approval rules and permissions deterministically without pretending to measure model quality.

During development this repository reports:

- 26/26 kit tests passing
- 129/129 backend tests passing
- frontend `tsc --noEmit` and `vite build` passing
- 27/27 scenario contracts passing in pipeline mode
- 27/27 scenarios passing in **live** mode against `gpt-4o-mini` with a real key, including the
  no-unapproved-writes check

The live suite is reproducible: `scripts/run_scenarios.py --mode live` needs the key configured in step 2.
- live model scenarios: **not run** (no API key in this environment)

---

## Security and guardrails

- Signed, http-only session cookie; `X-Mock-User` is not accepted from the browser.
- Demo ids validated against `data/clients.json`; foreign project ids resolve exactly like missing ones.
- Creatives are rejected before any model call. Visitors get three public tools only.
- Tool execution is server-side and allow-listed; approval, charging, messaging and cancellation are not tools.
- Uploads are validated by magic bytes, size, PDF page count and declared/actual type; extracted text is
  fenced as untrusted data and cannot change rules or trigger tools.
- Per-identity rate limits (minute/hour, plus visitor lifetime caps on messages and uploads).
- Moderation runs on client messages and assistant replies when a key is configured (fail-open with a log).
- Turn guards: false change claims get one rewrite, then an honest replacement; card numbers, security
  codes and reset links are redacted; every reply ends with exactly one next-step question.
- CORS is limited to the local frontend origins and the same-origin check rejects cross-site mutations.

---

## Folder structure

```
CREATEchat/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app, health, demo reset
│   │   ├── config.py               env/.env configuration
│   │   ├── db.py                   SQLite schema
│   │   ├── assistant/
│   │   │   ├── core.py             the turn: context → model → tools → cards → guards
│   │   │   ├── prompts.py          system prompt and persona prompts
│   │   │   ├── personas.py         deterministic persona selection
│   │   │   ├── tool_executor.py    22 kit tools + labelled support stubs
│   │   │   ├── cards.py            server-built cards from real results
│   │   │   ├── context.py          context blocks
│   │   │   ├── memory.py           transcripts, working memory, uploads
│   │   │   ├── guards.py           honesty, redaction, single-question rule
│   │   │   └── llm.py              OpenAI client + JSON envelope parser
│   │   ├── api/                    session, chat, account, proposals, support
│   │   ├── services/               mock adapter, rate limits, uploads
│   │   ├── schemas/                Pydantic models
│   │   └── security/               identity, moderation
│   ├── tests/                      125 tests
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── components/             shell, chat, cards, modals, UI primitives
│   │   ├── pages/                  Overview, Projects, ProjectDetail, Talent, Boards, Documents, Settings
│   │   ├── hooks/ contexts/ services/ types/ styles/
│   │   └── App.tsx, main.tsx
│   ├── package.json
│   └── vite.config.ts
├── createchat-prototype-kit/       supplied kit, extracted unchanged
├── scripts/run_scenarios.py        scenario runner (pipeline / live)
├── .env.example
├── run.sh · run.bat
└── README.md
```

---

## Known limitations and clearly labelled stubs

| Area | State |
| --- | --- |
| Live assistant replies | Need `OPENAI_API_KEY`. This workspace has one in `backend/.env` and the assistant was verified end to end against the real model; with no key the chat returns an explicit setup error, never fake text |
| Streaming | Not implemented; the UI shows a typing indicator and renders the completed reply |
| Support tickets | Stored in SQLite and the kit's ticket list; **no OPAH support system receives them** |
| Notification settings | Not mocked; `restore_notifications` reports that honestly and changes nothing |
| Moderation | Uses OpenAI's moderation endpoint when a key is set; without it the turn proceeds and logs the gap |
| Checkout / cancellation / review / message screens | Demo hand-off modals; no payment provider, messaging or review API is connected |
| Delivery / review windows | Read from the dataset; no background job auto-approves folders |
| Dataset mutations | Held in memory like the kit's own server; a restart reloads the JSON. `POST /api/demo/reset` does it on demand |
| The kit's aged proposal | `prop_0001` ships without the `payload` its approval path reads. The adapter backfills it from the proposal's own diff so approving it works; the kit file itself is untouched |
| Mobile apps, SMS line, partner widget | Out of scope, as the brief specifies |
| Production hosting/auth | Out of scope; this is a local prototype with demo identities |

Everything named "stub" or "demo" in the interface is a prototype boundary, not a successful integration.
