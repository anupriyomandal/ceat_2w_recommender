#!/usr/bin/env python3
"""
CEAT 2W Tyre Recommender — Telegram Bot
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rag_engine import TyreRAG

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Global RAG instance (initialised in main())
rag: TyreRAG | None = None

# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

WELCOME_TEXT = (
    "👋 *Welcome to the CEAT Tyre Advisor!*\n\n"
    "Tell me your motorcycle — brand, model, and variant — and I'll "
    "recommend the right CEAT tyre for you\\.\n\n"
    "Examples:\n"
    "• _Bajaj Pulsar NS 200 tyre_\n"
    "• _What tyre fits Honda Unicorn 160?_\n"
    "• _Royal Enfield Classic 350 front and rear tyres_\n\n"
    "Type /help to see more examples\\."
)

HELP_TEXT = (
    "*How to use:*\n\n"
    "Just type your motorcycle details and I'll suggest the right CEAT tyre\\.\n\n"
    "*Sample queries:*\n"
    "• Hero Splendor Plus 100cc tyre\n"
    "• KTM Duke 390 tubeless tyre\n"
    "• Yamaha R15 V4 front tyre specs\n"
    "• Bajaj Avenger Cruise 220 tyre recommendation\n\n"
    "I'll tell you the SKU, tyre name, aspect ratio, rim size, and construction type\\."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN_V2
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN_V2)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        return

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    try:
        # Run blocking RAG call in thread pool
        answer = await asyncio.get_event_loop().run_in_executor(
            None, lambda: rag.recommend(query)
        )

        # Telegram Markdown v2 escaping for special chars in answer
        # Use MarkdownV2 for bold/bullet support; escape problematic chars
        safe_answer = _escape_md(answer)
        await update.message.reply_text(safe_answer, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        logger.error("Error processing query: %s", e)
        await update.message.reply_text(
            "Sorry, I ran into an issue. Please try again."
        )


def _escape_md(text: str) -> str:
    """
    Escape Telegram MarkdownV2 special characters while preserving
    intentional **bold** and *italic* markers.
    """
    # Characters to escape in MarkdownV2 (outside of formatting)
    special = r"_[]()~`>#+=|{}.!"
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        # Preserve bold markers **...**
        if ch == "*":
            result.append(ch)
        elif ch == "\\":
            result.append("\\\\")
        elif ch in special:
            result.append(f"\\{ch}")
        else:
            result.append(ch)
        i += 1
    return "".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global rag

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN is not set.")

    logger.info("Initialising RAG engine…")
    rag = TyreRAG()
    logger.info("RAG engine ready.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
