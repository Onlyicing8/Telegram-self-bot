"""
Helper Bot — inline keyboard / callback query infrastructure.

The helper bot is a *secondary* Telegram client (bot token, not user session)
that handles inline UI concerns only via Telegram Inline Mode:

  1. Self-bot calls ``client.inline_query(@helper_bot, query)``
  2. Helper bot answers with an InlineQueryResultArticle
  3. Self-bot clicks the result to insert it into the chat
  4. Message appears from the OWNER'S account (with "via @bot")
  5. Callback button presses route back to the helper bot

The helper bot NEVER sends messages directly into chats. This is the
official Telegram Inline Mode flow, which works in Saved Messages,
private chats, and groups without the bot needing to be a member.
"""
from backend.helper.client import (
    build_helper,
    disconnect_helper,
    get_bot_id,
    get_bot_username,
    get_client,
    is_available,
)
from backend.helper.panels import (
    InlinePanelBuilder,
    register_panel,
    get_panel,
    register_inline_builder,
    send_inline_panel,
    register_inline_query,
    register_callback_handlers,
)

__all__ = [
    "build_helper",
    "disconnect_helper",
    "get_bot_id",
    "get_bot_username",
    "get_client",
    "is_available",
    "InlinePanelBuilder",
    "register_panel",
    "get_panel",
    "register_inline_builder",
    "send_inline_panel",
    "register_inline_query",
    "register_callback_handlers",
]
