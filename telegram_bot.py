"""
Telegram interface for JARVIS. Run this file to start the bot, then message
your bot on Telegram from your phone — this becomes the "always with you"
part of the assistant before you build the voice interface.
"""

import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from brain.orchestrator import handle_message

load_dotenv()

# Simple in-memory per-chat history (fine for personal use with 1-2 users).
# Swap for a real DB later if you want persistence across restarts.
CONVERSATIONS: dict[int, list[dict]] = {}


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_text = update.message.text
    history = CONVERSATIONS.setdefault(chat_id, [])

    result = handle_message(user_text, history, session_id=f"telegram-{chat_id}")
    reply = result["reply"]
    news_cards = result["cards"]

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    # keep history from growing unbounded
    CONVERSATIONS[chat_id] = history[-20:]

    await update.message.reply_text(reply)

    # Telegram can't show floating windows like the desktop HUD does, so news
    # cards fall back to a simple linked list here instead of going silent.
    if news_cards:
        lines = [f"• [{c['title']}]({c['url']})" for c in news_cards if c["url"]]
        if lines:
            await update.message.reply_text(
                "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
            )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in your .env file first.")

    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("JARVIS Telegram bot running. Message your bot now.")
    app.run_polling()


if __name__ == "__main__":
    main()
