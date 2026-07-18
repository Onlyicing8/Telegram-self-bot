"""
.list [n]       — Show recent saved items (newest first, default 10).
.find <text>   — Search saved items by caption, filename, code, or mime.

Both use indexed DB queries (owner_id + created_at composite index for .list,
trigram indexes for .find). Never scan the entire table.
"""
import logging
from telethon import events
from backend.bot.handlers.guard import is_owner
from backend.db import client as db_client

logger = logging.getLogger(__name__)

_MEDIA_ICON = {
    "Photo": "📷",
    "Video": "🎬",
    "Animation": "🎞",
    "Audio": "🎵",
    "Voice": "🎤",
    "Sticker": "🏷",
    "Document": "📄",
    "Unknown": "📦",
}


def _icon(media_type: str | None) -> str:
    return _MEDIA_ICON.get(media_type or "Unknown", "📦")


def _format_line(row: dict) -> str:
    code = row.get("short_code") or row.get("save_code") or "—"
    icon = _icon(row.get("media_type"))
    name = row.get("file_name") or row.get("media_type") or "—"
    return f"`{code}` {icon} {name}"


def register(client, owner_id: int):

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.list(?:\s+(\d+))?$"))
    async def list_cmd(event):
        if not is_owner(event, owner_id):
            return
        n_str = event.pattern_match.group(1)
        limit = int(n_str) if n_str else 10
        if limit < 1 or limit > 50:
            await event.edit("⚠️ Use a number between 1 and 50.")
            return
        try:
            items = db_client.list_recent_saves(owner_id, limit=limit)
        except Exception as exc:
            logger.error("list db error: %s", exc)
            await event.edit(f"❌ DB error: {exc}")
            return
        if not items:
            await event.edit("📭 No saved items yet.")
            return
        lines = [f"📋 **Recent Saves** ({len(items)})", ""]
        lines.extend(_format_line(r) for r in items)
        await event.edit("\n".join(lines))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.find\s+(.+)$"))
    async def find_cmd(event):
        if not is_owner(event, owner_id):
            return
        query = event.pattern_match.group(1).strip()
        try:
            items = db_client.search_saves(owner_id, query, limit=20)
        except Exception as exc:
            logger.error("find db error: %s", exc)
            await event.edit(f"❌ DB error: {exc}")
            return
        if not items:
            await event.edit(f"🔍 No matches for `{query}`")
            return
        lines = [f"🔍 **Results** for `{query}` ({len(items)})", ""]
        lines.extend(_format_line(r) for r in items)
        await event.edit("\n".join(lines))
