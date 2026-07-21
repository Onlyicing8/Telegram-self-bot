"""
Inline panel system for the helper bot.

Architecture (Telegram Inline Mode):
  1. Self-bot calls ``client.inline_query(@helper_bot, query)``
  2. Helper bot answers the InlineQuery with one or more results
  3. Self-bot clicks the first result to insert it into the chat
  4. The message appears from the OWNER'S account (with "via @bot")
  5. Callback button presses route back to the helper bot

The helper bot NEVER sends messages directly into chats. All UI is
delivered via Inline Mode so it works everywhere — Saved Messages,
private chats, and groups — without the bot needing to be a member.

Provides:
  - ``send_inline_panel(self_client, event, query)`` — the single
    reusable entry point for all inline panels. Performs the full
    inline-query → click → delete-trigger flow with proper ordering
    and error handling.
  - ``register_inline_query(helper_client)`` — registers the
    InlineQuery handler on the helper bot.
  - ``InlinePanelBuilder`` — builds inline keyboards.
  - ``register_panel / get_panel`` — callback handler registry.
  - ``register_callback_handlers`` — wires the callback router.
"""
import logging
from typing import Awaitable, Callable, Any

from telethon import events
from telethon.tl.custom import Button

from backend.bot.handlers.guard import is_owner
from backend.helper.client import get_bot_username

logger = logging.getLogger(__name__)

PanelHandler = Callable[[events.CallbackQuery.Event, str], Awaitable[None]]
_panels: dict[str, PanelHandler] = {}

# Registry of inline-query builders: query_string -> async callable that
# returns (text, buttons) for the InlineQueryResultArticle.
_inline_builders: dict[str, Callable[[], Awaitable[tuple[str, list]]]] = {}


class InlinePanelBuilder:
    """Builds inline keyboard layouts for the helper bot."""

    def __init__(self):
        self._rows: list[list[Any]] = []

    def add_row(self, text: str, callback_data: str) -> "InlinePanelBuilder":
        self._rows.append([Button.inline(text, callback_data)])
        return self

    def add_buttons(self, *buttons: tuple[str, str]) -> "InlinePanelBuilder":
        row = [Button.inline(text, data) for text, data in buttons]
        self._rows.append(row)
        return self

    def add_url(self, text: str, url: str) -> "InlinePanelBuilder":
        self._rows.append([Button.url(text, url)])
        return self

    def build(self) -> list[list[Any]]:
        return self._rows


def register_panel(panel_id: str, handler: PanelHandler) -> None:
    """Register a callback handler for a panel ID."""
    _panels[panel_id] = handler


def get_panel(panel_id: str) -> PanelHandler | None:
    return _panels.get(panel_id)


def register_inline_builder(
    query: str, builder: Callable[[], Awaitable[tuple[str, list]]]
) -> None:
    """Register an inline-query result builder for a query string."""
    _inline_builders[query] = builder


async def send_inline_panel(self_client, event, query: str) -> bool:
    """
    Reusable helper: send an inline panel via Telegram Inline Mode.

    Flow (strict ordering — trigger is deleted ONLY on success):
      1. client.inline_query(@helper_bot, query)
      2. Verify results count > 0
      3. Click the first result to insert into the current chat
      4. Delete the original command message

    Returns True if the panel was successfully inserted, False otherwise.
    On any failure the original command is left intact (not deleted) and
    the caller is responsible for falling back to ``event.edit(...)``.
    """
    bot_username = get_bot_username()
    if not bot_username:
        logger.warning("INLINE PANEL: no helper bot username — cannot query")
        return False

    logger.info("INLINE QUERY SENT — bot=@%s query=%s chat=%s",
                bot_username, query, event.chat_id)

    try:
        results = await self_client.inline_query(bot_username, query)
    except Exception as exc:
        logger.error("INLINE QUERY FAILED — %s: %s", type(exc).__name__, exc)
        return False

    count = len(results) if results else 0
    logger.info("INLINE RESULTS COUNT — %d", count)

    if not results:
        logger.warning("INLINE QUERY returned 0 results — falling back")
        return False

    logger.info("INLINE RESULT SELECTED — index=0")
    try:
        await results[0].click(event.chat_id)
    except Exception as exc:
        logger.error("INLINE RESULT SEND FAILED — %s: %s", type(exc).__name__, exc)
        return False

    logger.info("INLINE RESULT SENT — chat=%s", event.chat_id)

    try:
        await event.delete()
        logger.info("TRIGGER DELETED — msg_id=%s", event.message.id)
    except Exception as exc:
        logger.warning("TRIGGER DELETE FAILED — %s: %s", type(exc).__name__, exc)

    return True


def register_inline_query(helper_client) -> None:
    """
    Register the InlineQuery handler on the helper bot.

    When the self-bot calls ``client.inline_query(@helper_bot, query)``,
    the helper bot looks up the registered builder for that query string
    and answers with a single InlineQueryResultArticle containing the
    panel text and buttons.
    """

    @helper_client.on(events.InlineQuery())
    async def _inline_query_handler(event):
        query = event.text.strip().lower()
        builder = _inline_builders.get(query)
        if builder is None:
            return

        try:
            text, buttons = await builder()
        except Exception as exc:
            logger.error("INLINE BUILDER ERROR for query '%s' — %s: %s",
                         query, type(exc).__name__, exc)
            return

        try:
            article = await event.builder.article(
                title="LifeOS Panel",
                description="Tap to open",
                text=text,
                buttons=buttons,
            )
            await event.answer([article])
        except Exception as exc:
            logger.error("INLINE ANSWER FAILED — %s: %s", type(exc).__name__, exc)


def register_callback_handlers(client, owner_id: int) -> None:
    """
    Wire the callback query router onto the helper bot client.

    Every callback query is checked against ``is_owner``. The callback data
    must start with ``panel:`` followed by the panel ID and optional extra
    data separated by ``:``.
    """

    @client.on(events.CallbackQuery())
    async def _callback_router(event):
        if not is_owner(event, owner_id):
            return

        data = event.data.decode("utf-8") if event.data else ""
        if not data.startswith("panel:"):
            return

        remainder = data[6:]
        parts = remainder.split(":", 1)
        panel_id = parts[0]
        extra = parts[1] if len(parts) > 1 else ""

        handler = get_panel(panel_id)
        if handler is None:
            logger.warning("No panel registered for id: %s", panel_id)
            return

        try:
            await handler(event, extra)
        except Exception as exc:
            logger.error("Panel handler '%s' error: %s", panel_id, exc)
