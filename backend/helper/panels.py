"""
Inline panel system for the helper bot.

Provides:
  - ``InlinePanelBuilder`` — builds inline keyboards with rows of buttons.
  - ``register_panel(panel_id, handler)`` — registers a callback handler
    for a panel ID. Future commands call this to wire up their inline UI.
  - ``get_panel(panel_id)`` — retrieves a registered panel handler.
  - ``register_callback_handlers(client, owner_id)`` — wires the callback
    query router onto the helper bot client.

Panel IDs are short strings embedded in callback data as ``panel:<id>``.
The callback router dispatches to the registered handler, passing the
callback event and any extra data after the colon.

Usage by future command handlers:

    from backend.helper import InlinePanelBuilder, register_panel

    async def my_panel_handler(event, extra):
        # extra is the string after "panel:my_panel" in callback data
        builder = InlinePanelBuilder()
        builder.add_row("Option A", "action:a")
        builder.add_row("Back", "panel:main")
        await event.edit("Choose:", buttons=builder.build())

    register_panel("my_panel", my_panel_handler)

Then from a self-bot command, the helper bot can send an inline message:

    from backend.helper.client import get_client
    helper = get_client()
    if helper:
        await helper.send_message(
            event.chat_id, "Choose:", buttons=builder.build()
        )
"""
import logging
from typing import Awaitable, Callable, Any

from telethon import events
from telethon.tl.custom import Button

from backend.bot.handlers.guard import is_owner

logger = logging.getLogger(__name__)

PanelHandler = Callable[[events.CallbackQuery.Event, str], Awaitable[None]]
_panels: dict[str, PanelHandler] = {}


class InlinePanelBuilder:
    """Builds inline keyboard layouts for the helper bot."""

    def __init__(self):
        self._rows: list[list[Any]] = []

    def add_row(self, text: str, callback_data: str) -> "InlinePanelBuilder":
        """Add a single button row."""
        self._rows.append([Button.inline(text, callback_data)])
        return self

    def add_buttons(self, *buttons: tuple[str, str]) -> "InlinePanelBuilder":
        """Add multiple buttons in a single row."""
        row = [Button.inline(text, data) for text, data in buttons]
        self._rows.append(row)
        return self

    def add_url(self, text: str, url: str) -> "InlinePanelBuilder":
        """Add a URL button row."""
        self._rows.append([Button.url(text, url)])
        return self

    def build(self) -> list[list[Any]]:
        """Return the keyboard layout for Telethon's ``buttons=`` parameter."""
        return self._rows


def register_panel(panel_id: str, handler: PanelHandler) -> None:
    """Register a callback handler for a panel ID."""
    _panels[panel_id] = handler
    logger.debug("Panel registered: %s", panel_id)


def get_panel(panel_id: str) -> PanelHandler | None:
    """Retrieve a registered panel handler by ID."""
    return _panels.get(panel_id)


def register_callback_handlers(client, owner_id: int) -> None:
    """
    Wire the callback query router onto the helper bot client.

    Every callback query is checked against ``is_owner`` — non-owner
    callbacks are silently ignored. The callback data must start with
    ``panel:`` followed by the panel ID. Any data after the panel ID
    (separated by ``:``) is passed as the ``extra`` argument.
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
