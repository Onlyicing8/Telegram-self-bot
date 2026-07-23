"""
Inline Engine — the core of the Inline Mode architecture.

The helper bot answers InlineQuery events by generating panel results.
The self-bot triggers inline mode via ``client.inline_query(bot_username, query)``
and auto-sends the first result.

Flow:
  1. Self-bot command (e.g. ``.help``) fires.
  2. Self-bot calls ``inline_engine.trigger(client, chat_id, query)``.
  3. Helper bot receives InlineQuery, generates results via registered
     inline result builders.
  4. Self-bot auto-sends the first result — message appears as
     ``OwnerName via @HelperBot`` with inline buttons.
  5. Callbacks work exactly as before — no changes to callback architecture.

Inline result builders are registered per "query key". The query string
passed to the helper bot's inline mode encodes which panel to show:
  ``<panel_id>`` or ``<panel_id>:<extra>``

The builder returns a list of InputBotInlineResult objects (usually one).
"""
import asyncio
import logging
import time
from typing import Awaitable, Callable, Any

from telethon import events, types
from telethon.tl.custom import Button

from backend.bot.handlers.guard import is_owner
from backend.helper.context import truncate_callback_data

logger = logging.getLogger(__name__)

InlineResultBuilder = Callable[[events.InlineQuery.Event, str], Awaitable[list]]

_builders: dict[str, InlineResultBuilder] = {}
_self_client = None
_helper_username: str = ""
_owner_id: int = 0


def _now_ms() -> float:
    return time.monotonic() * 1000.0


def set_self_client(client) -> None:
    global _self_client
    _self_client = client


def set_helper_username(username: str) -> None:
    global _helper_username
    username = username.lstrip("@") if username else ""
    _helper_username = username


def set_owner_id(owner_id: int) -> None:
    global _owner_id
    _owner_id = owner_id


def get_helper_username() -> str:
    return _helper_username


def register_inline_builder(query_key: str, builder: InlineResultBuilder) -> None:
    """Register a builder that returns inline results for a query key."""
    _builders[query_key] = builder
    logger.info("[INLINE] Builder registered: key='%s' (total=%d)", query_key, len(_builders))


def get_inline_builder(query_key: str) -> InlineResultBuilder | None:
    return _builders.get(query_key)


async def trigger(self_client, chat_id: int, query: str) -> bool:
    """Trigger inline mode and auto-send the first result.

    Returns True on success, False on failure.
    """
    t_enter = _now_ms()
    logger.info("[TIMING] trigger ENTER: t=%.1fms, chat_id=%s, query='%s'", t_enter, chat_id, query)

    logger.info("HELP STEP 5 - helper username: '%s'", _helper_username)
    if not _helper_username:
        logger.error("HELP STEP 5 - trigger() ABORT: helper username not set (_helper_username='%s') — REASON: set_helper_username() was never called or get_bot_username() returned empty", _helper_username)
        return False

    t_before_iq = _now_ms()
    logger.info("[TIMING] trigger BEFORE inline_query: t=%.1fms, elapsed=%.1fms, bot='@%s', query='%s'",
                t_before_iq, t_before_iq - t_enter, _helper_username, query)

    try:
        results = await self_client.inline_query(_helper_username, query)
        t_after_iq = _now_ms()
        logger.info("[TIMING] trigger AFTER inline_query: t=%.1fms, elapsed=%.1fms, type=%s, results_count=%d",
                    t_after_iq, t_after_iq - t_enter,
                    type(results).__name__, len(results) if results else 0)
        logger.info("HELP STEP 7 - inline_query() returned: type=%s, results_count=%d",
                    type(results).__name__, len(results) if results else 0)

        if results:
            logger.info("HELP STEP 8 - results count: %d", len(results))
            logger.info("HELP STEP 9 - clicking results[0] to chat_id=%s (result type=%s, id=%s)",
                        chat_id, type(results[0]).__name__, getattr(results[0], 'result', None))

            t_before_click = _now_ms()
            logger.info("[TIMING] trigger BEFORE click: t=%.1fms, elapsed=%.1fms",
                        t_before_click, t_before_click - t_enter)
            try:
                sent_msg = await results[0].click(chat_id)
                t_after_click = _now_ms()
                logger.info("[TIMING] trigger AFTER click: t=%.1fms, elapsed=%.1fms, sent_msg=%s",
                            t_after_click, t_after_click - t_enter, sent_msg)
                logger.info("HELP STEP 10 - result sent successfully: sent_msg=%s", sent_msg)
                return True
            except Exception as click_exc:
                t_after_click = _now_ms()
                logger.info("[TIMING] trigger click FAILED: t=%.1fms, elapsed=%.1fms",
                            t_after_click, t_after_click - t_enter)
                logger.exception("HELP STEP 10 - click() FAILED: %s", click_exc)
                return False
        else:
            t_zero = _now_ms()
            logger.warning("[TIMING] trigger zero results: t=%.1fms, elapsed=%.1fms, query='%s', helper='@%s'",
                           t_zero, t_zero - t_enter, query, _helper_username)
            logger.warning("HELP STEP 8 - zero results: query='%s', helper_username='@%s', returned_object=%s — REASON: helper bot InlineQuery handler did not answer or returned empty list",
                           query, _helper_username, repr(results))
            return False
    except Exception as exc:
        t_exc = _now_ms()
        logger.info("[TIMING] trigger inline_query EXCEPTION: t=%.1fms, elapsed=%.1fms",
                    t_exc, t_exc - t_enter)
        logger.exception("HELP STEP 7 - inline_query() FAILED: %s", exc)
        return False


def register_inline_handler(helper_client, owner_id: int) -> None:
    """Wire the InlineQuery handler onto the helper bot client."""

    @helper_client.on(events.InlineQuery())
    async def _inline_router(event):
        t_enter = _now_ms()
        logger.info("[TIMING] _inline_router ENTER: t=%.1fms, query='%s', user_id=%s",
                    t_enter, event.query, event.sender_id)
        logger.info("HELP STEP 8a - InlineQuery handler entered: query='%s', user_id=%s",
                    event.query, event.sender_id)

        t_before_owner = _now_ms()
        if not is_owner(event, owner_id):
            t_after_owner = _now_ms()
            logger.warning("[TIMING] _inline_router owner check FAILED: elapsed=%.1fms, sender_id=%s, owner_id=%s",
                           t_after_owner - t_enter, event.sender_id, owner_id)
            logger.warning("HELP STEP 8a - owner check FAILED: sender_id=%s, owner_id=%s",
                        event.sender_id, owner_id)
            try:
                await event.answer([])
            except Exception:
                logger.exception("HELP STEP 8a - failed to answer empty results on owner check fail")
            return

        t_after_owner = _now_ms()
        logger.info("[TIMING] _inline_router owner check PASS: elapsed=%.1fms", t_after_owner - t_enter)
        logger.info("HELP STEP 8a - owner check passed")

        raw_query = event.query.strip()
        if not raw_query:
            logger.warning("HELP STEP 8a - empty query — answering with empty list")
            try:
                await event.answer([])
            except Exception:
                logger.exception("HELP STEP 8a - failed to answer empty results on empty query")
            return

        parts = raw_query.split(":", 1)
        panel_id = parts[0]
        extra = parts[1] if len(parts) > 1 else ""

        logger.info("HELP STEP 8a - parsed: panel_id='%s', extra='%s'", panel_id, extra)

        builder = get_inline_builder(panel_id)
        if builder is None:
            logger.warning("HELP STEP 8a - no builder for panel_id='%s' (registered: %s) — REASON: register_inline_builder() was never called for this key",
                           panel_id, list(_builders.keys()))
            try:
                await event.answer([])
            except Exception:
                logger.exception("HELP STEP 8a - failed to answer empty results on missing builder")
            return

        logger.info("HELP STEP 8a - builder found for '%s' — invoking", panel_id)
        t_before_build = _now_ms()
        logger.info("[TIMING] _inline_router BEFORE builder: elapsed=%.1fms, panel_id='%s'",
                    t_before_build - t_enter, panel_id)
        try:
            results = await builder(event, extra)
            t_after_build = _now_ms()
            logger.info("[TIMING] _inline_router AFTER builder: elapsed=%.1fms, results_count=%d",
                        t_after_build - t_enter, len(results) if results else 0)
            logger.info("HELP STEP 8a - builder returned: results_count=%d",
                        len(results) if results else 0)

            if not results:
                logger.warning("HELP STEP 8a - builder returned empty list for panel_id='%s' — REASON: builder function returned []", panel_id)

            t_before_answer = _now_ms()
            logger.info("[TIMING] _inline_router BEFORE event.answer: elapsed=%.1fms, results_count=%d",
                        t_before_answer - t_enter, len(results) if results else 0)
            logger.info("HELP STEP 8a - about to call event.answer(results)")
            await event.answer(results)
            t_after_answer = _now_ms()
            logger.info("[TIMING] _inline_router AFTER event.answer: elapsed=%.1fms",
                        t_after_answer - t_enter)
            logger.info("HELP STEP 8a - event.answer() succeeded")
        except Exception as exc:
            t_build_err = _now_ms()
            logger.info("[TIMING] _inline_router builder/answer EXCEPTION: elapsed=%.1fms",
                        t_build_err - t_enter)
            logger.exception("HELP STEP 8a - builder '%s' FAILED: %s", panel_id, exc)
            try:
                await event.answer([])
            except Exception:
                logger.exception("HELP STEP 8a - failed to answer empty results on builder error")


def make_result(
    title: str,
    description: str = "",
    panel_id: str = "",
    extra: str = "",
    buttons: list | None = None,
    query_id: int = 0,
) -> types.InputBotInlineResult:
    """Build a single InputBotInlineResult with a text message and buttons.

    The result body is a InputBotInlineMessageTextAuto (auto-detected type).
    """
    body_text = title
    if description:
        body_text = f"{title}\n\n{description}"

    if buttons is None:
        buttons = []

    msg = types.InputBotInlineMessageTextAuto(
        message=body_text,
        reply_markup=types.ReplyInlineMarkup(rows=buttons) if buttons else None,
    )

    return types.InputBotInlineResult(
        id="0",
        type="article",
        title=title.split("\n")[0][:255] if title else "LifeOS",
        send_message=msg,
    )


def make_button_rows(buttons_data: list[list[tuple[str, str]]]) -> list:
    """Convert a list of button rows into ReplyInlineMarkup rows.

    Each row is a list of (text, callback_data) tuples.
    """
    rows = []
    for row_data in buttons_data:
        row_buttons = []
        for text, data in row_data:
            row_buttons.append(
                types.KeyboardButtonCallback(
                    text=text,
                    data=truncate_callback_data(data).encode("utf-8"),
                )
            )
        rows.append(row_buttons)
    return rows
