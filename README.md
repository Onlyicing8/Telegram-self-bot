# LifeOS Self Bot

A production-grade **Telegram self-bot** (userbot) that turns your own Telegram account into a personal operating system — save anything, search instantly, automate your profile bio, and keep your data organized. Built on **Telethon** with a **Supabase** backend and a **React** dashboard, deployed on **Render**.

LifeOS runs as a single headless `asyncio` process. No bot accounts, no interactive logins, no spam — every command edits the triggering message in-place. It just works.

---

## Features

- **Save Engine** — Forward-save or deep-save (download + re-upload) any media to Saved Messages with full metadata. Preserves the original Telegram media type (Photo, Video, Voice, Animation, Sticker, etc.) — never downgrades to a generic document.
- **Bio Engine** — A timezone-synchronized cron that rewrites your Telegram profile bio every minute using `{time}`, `{mood}`, and `{text}` tokens. Fires exactly at `xx:xx:00`, deduplicates unchanged bios, and handles FloodWait gracefully.
- **Organizer** — Data overview, log cleanup, and multi-message deletion. Delete by count, by message ID range, or by save code.
- **Retrieval** — Preview metadata or forward any saved asset back into any chat with a single command.
- **Search** — Full-text search across captions, filenames, save codes, and MIME types using PostgreSQL trigram indexes. No full-table scans.
- **Compact Codes** — Every save gets a short, human-readable code (e.g. `S391`, `A82`) that's easy to type and remember. Legacy `SV-NNNNNN` codes remain fully supported.
- **Telegram SelfBot** — Operates your own account via Telethon `StringSession`. No bot tokens, no file-based sessions, no interactive prompts. Owner-only access with silent rejection of all other users.
- **Supabase Storage** — All metadata persists in Supabase with automatic in-memory fallback. The bot never crashes if the database is unreachable.
- **Telethon** — The industry-standard Telegram MTProto library for Python, tuned for Render Free tier with auto-reconnect and flood-sleep handling.
- **Render Deployment** — One-click deploy via `render.yaml` Blueprint. Health check on `/health`, graceful SIGTERM shutdown, zero orphaned tasks.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Python asyncio process                 │
│                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────┐  │
│  │ Telethon │   │ Bio Cron │   │  FastAPI + Uvicorn   │  │
│  │  Client  │   │  Engine  │   │  /health  /api/*     │  │
│  └────┬─────┘   └────┬─────┘   └──────────┬───────────┘  │
│       │               │                     │            │
│       └───────────────┴─────────────────────┘            │
│                         │                                │
│                   ┌─────┴──────┐                         │
│                   │  Supabase  │ ← service-role key       │
│                   │  (optional)│   in-memory fallback     │
│                   └────────────┘                         │
└─────────────────────────────────────────────────────────┘
                         │
                   ┌─────┴──────┐
                   │  React     │ ← dark Material 3 dashboard
                   │  Dashboard │   polls /api/* every 30s
                   └────────────┘
```

**Single event loop.** Telethon, the bio cron, and the web server all share one asyncio loop. No threads, no multiprocessing. Clean shutdown cancels every task before disconnect.

### Repository Structure

```
backend/
├── main.py              # asyncio entry point — startup + shutdown orchestration
├── config.py            # env var loader — required vars hard-fail
├── bot/
│   ├── client.py        # Telethon client factory (StringSession)
│   ├── router.py        # registers all handlers
│   └── handlers/
│       ├── guard.py     # is_owner() — single permission gate
│       ├── misc.py      # .ping, .id, .help
│       ├── save.py      # .save f/.s f, .save d/.s d
│       ├── retrieve.py  # .preview/.r/.retrieve, .send
│       ├── delete.py    # .del <n>, .del id, .del <code>
│       ├── discover.py  # .list, .find
│       ├── organize.py  # .organize list, .organize clean
│       └── bio.py       # .bio on/off/template/text/mood/show
├── bio/
│   └── engine.py        # cron loop — minute-sync, dedup, FloodWait
├── db/
│   └── client.py        # Supabase singleton + in-memory fallback
└── web/
    └── app.py           # FastAPI — /health, /api/*, SPA serving

src/                     # React dashboard (TypeScript + Vite + Tailwind)
├── App.tsx
├── components/
│   ├── SavedItems.tsx   # saved items list with media badges
│   ├── BioStatus.tsx    # bio engine status
│   └── LogViewer.tsx    # structured log viewer
└── lib/
    └── api.ts           # typed fetch wrappers

supabase/migrations/     # SQL migrations (applied via Supabase MCP)
```

---

## Command Examples

### Save Engine (reply to a message first)

```
.save f        Forward save — instant, no download
.save d        Deep save — download + re-upload with rich caption
.s f           Alias for .save f
.s d           Alias for .save d
```

After saving, you get a compact confirmation:

```
✅ Saved
Code: S391
Mode: Forward
Type: Photo
Name: vacation.jpg
```

### Discovery

```
.list          Show 10 recent saves (newest first)
.list 20       Show 20 recent saves
.find vacation Search by caption, filename, code, or MIME
```

Example `.list` output:

```
S391 📷 Vacation.jpg
S392 🎬 Clip.mp4
S393 🎵 Song.mp3
S394 📄 Resume.pdf
```

### Retrieval

```
.preview S391   Show metadata for S391
.r S391         Alias
.retrieve S391  Alias
.send S391      Forward the saved asset into this chat
```

### Organizer

```
.del 5            Delete last 5 outgoing messages
.del id 12345     Delete all messages from ID 12345 forward
.del S391         Delete saved item S391 from the index
.organize list    Data overview (saves, logs, bio status)
.organize clean   Purge logs older than 7 days
```

### Bio Engine

```
.bio on                 Start the bio cron
.bio off                Stop the bio cron
.bio template 🕒 {time} | {mood} | {text}
.bio text Working
.bio mood 😊
.bio show               Inspect full bio state
.bio help               Token reference
```

### Utility

```
.ping     Edits message to PONG
.id       Shows Chat ID + Message ID
.help     Shows the full command dashboard
```

---

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the dashboard)
- A Telegram account with API credentials from [my.telegram.org](https://my.telegram.org)
- A Supabase project (optional — the bot works without it)

### 1. Generate SESSION_STRING

You must generate a Telethon `StringSession` **once** on your local machine:

```bash
pip install telethon
python -c "
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id   = int(input('API_ID: '))
api_hash = input('API_HASH: ')

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print('\\n--- SESSION_STRING ---')
    print(client.session.save())
    print('--- copy the line above ---')
"
```

Copy the output string — this is your `SESSION_STRING`.

### 2. Local Development

```bash
# Backend
pip install -r backend/requirements.txt

# Frontend
npm install
npm run build    # builds to dist/ (served by FastAPI)

# Run the bot
python -m backend.main
```

The dashboard is available at `http://localhost:8000`.

### 3. Deploy to Render

1. Push this repository to GitHub.
2. Create a new Web Service on Render, connected to your GitHub repo.
3. Render reads `render.yaml` automatically — or set the start command to `python -m backend.main`.
4. Add all environment variables (see below) in the Render dashboard.
5. Deploy. The health check hits `/health` and must return 200.

---

## Environment Variables

### Required (hard-fail if missing)

| Variable | Description |
|---|---|
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API hash from my.telegram.org |
| `SESSION_STRING` | Telethon StringSession (generated above) |
| `BOT_OWNER_ID` | Your Telegram numeric user ID |

### Optional (with defaults)

| Variable | Default | Description |
|---|---|---|
| `SUPABASE_URL` | `""` | Supabase project URL. Empty = in-memory fallback. |
| `SUPABASE_SERVICE_ROLE_KEY` | `""` | Supabase service role key. Empty = in-memory fallback. |
| `DATABASE_URL` | `""` | PostgreSQL connection string (backup, currently unused). |
| `TZ` | `Asia/Tehran` | Timezone for bio engine and timestamps. |
| `PORT` | `8000` | Web server port (Render sets this automatically). |
| `BIO_UPDATE_ENABLED` | `false` | Set to `true` to auto-start bio cron on boot. |
| `LOG_LEVEL` | `INFO` | Python logging level. |

> **Note:** Supabase is optional. Without it, the bot uses in-memory storage and all commands still work — but data won't persist across restarts.

---

## Database

LifeOS uses three Supabase tables, all with RLS enabled:

| Table | Purpose |
|---|---|
| `saved_items` | Media save records — save code, type, origin, metadata, tags, filename |
| `bio_state` | Singleton bio engine state per owner — template, mood, text, is_active |
| `bot_logs` | Structured activity logs — level, message, JSONB context |

**Schema highlights:**
- `saved_items` has both `save_code` (legacy `SV-NNNNNN`) and `short_code` (new `S391`) columns. Lookups try `short_code` first, then fall back to `save_code`.
- `pg_trgm` extension powers fast ILIKE search across `caption`, `file_name`, `save_code`, `short_code`, and `mime_type`.
- A composite index on `(owner_id, created_at DESC)` powers `.list`.
- RLS: SELECT-only for `anon` + `authenticated` (dashboard reads). All writes go through the backend's service-role key, which bypasses RLS.

**In-memory fallback:** If Supabase is unreachable, every DB operation falls back to a module-level dict. The bot never crashes due to a database error.

---

## Screenshots

> _Screenshots will be added here._

<!-- TODO: Add dashboard screenshots showing Saved Items, Bio Status, and Log Viewer tabs. -->

---

## Roadmap

- [ ] Inline button interactions for quick-save from any chat
- [ ] Scheduled saves with recurring intervals
- [ ] Export saved items index as JSON/CSV
- [ ] Multi-owner support with per-user dashboard auth
- [ ] Full-text search with ranking and relevance scoring
- [ ] Media thumbnail generation for the dashboard
- [ ] Webhook notifications for save events

---

## Project Philosophy

- **Never crash.** Every external operation is wrapped in error handling that degrades gracefully. The bot survives network blips, database outages, and Telegram flood limits.
- **Zero spam.** Every command response edits the triggering message in-place. No new messages are sent (except `.send`, which forwards a saved asset by design).
- **Owner-only.** One permission gate (`is_owner`). Non-owner messages are silently ignored — no response, no error, no log.
- **Edit-first.** All feedback is inline. The bot never pollutes chats with confirmation messages.
- **Deterministic.** The bio cron fires at exact minute boundaries, not fixed intervals. Save codes are atomic via `asyncio.Lock`. No race conditions.
- **Single process.** One asyncio event loop, no threads, no multiprocessing. Telethon, Uvicorn, and the bio cron cooperate.
- **Data safety.** Never `DROP` tables, `DELETE` columns, or change column types. Migrations are additive and idempotent.

---

## Credits

- **[Telethon](https://github.com/LonamiWebs/Telethon)** — Telegram MTProto library
- **[FastAPI](https://fastapi.tiangolo.com/)** — Web framework
- **[Supabase](https://supabase.com/)** — PostgreSQL backend
- **[React](https://react.dev/)** + **[Vite](https://vitejs.dev/)** — Dashboard
- **[Tailwind CSS](https://tailwindcss.com/)** — Styling
- **[Render](https://render.com/)** — Hosting

---

## License

This project is for personal use. See the repository for details.
