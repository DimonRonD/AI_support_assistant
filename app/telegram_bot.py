from __future__ import annotations

from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.assistant import AssistantService
from app.config import load_settings

settings = load_settings()
service = AssistantService(settings=settings)


def _session_id(update: Update) -> str:
    return str(update.effective_chat.id) if update.effective_chat else "unknown"


async def _send_text(update: Update, text: str) -> None:
    for chunk in service.split_for_telegram(text):
        await update.message.reply_text(chunk)


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.help_text())


async def cmd_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.set_text_mode(_session_id(update)))


async def cmd_clear(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.clear_memory(_session_id(update)))


async def cmd_rag_source(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.rag_source())


async def cmd_rag_load(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.rag_load())


async def cmd_rag_reload(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.rag_reload())


async def cmd_cache_view(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.cache_view())


async def cmd_rag_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await _send_text(update, "Укажите имя файла: /rag_detail <filename>")
        return
    await _send_text(update, service.rag_detail(context.args[0]))


async def cmd_rag_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await _send_text(update, "Укажите имя файла: /rag_clear <filename>")
        return
    await _send_text(update, service.rag_clear(context.args[0]))


async def cmd_clear_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) == 0:
        await _send_text(update, service.clear_cache())
        return
    if len(context.args) != 2:
        await _send_text(update, "Формат: /clear_cache <N> <YYYY-MM-DD>")
        return
    try:
        n = int(context.args[0])
    except ValueError:
        await _send_text(update, "N должно быть числом.")
        return
    await _send_text(update, service.clear_cache(n=n, older_than=context.args[1]))


async def cmd_rag_add(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.document:
        await _send_text(update, "Прикрепите файл и отправьте с подписью /rag_add.")
        return
    document = message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in {".txt", ".pdf", ".md"}:
        await _send_text(update, "Неподдерживаемый формат. Разрешены TXT, PDF, MD.")
        return
    file = await document.get_file()
    destination = settings.rag_source_dir / (document.file_name or "uploaded.txt")
    await file.download_to_drive(str(destination))
    await _send_text(update, f"Файл {destination.name} загружен в /rag_source.")


async def text_message(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return
    if message.text.startswith("/"):
        return
    sid = _session_id(update)
    if service.storage.get_mode(sid) != "text":
        return
    result = service.ask(session_id=sid, query=message.text)
    await _send_text(update, result.text)


def build_bot() -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN отсутствует в .env")
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("text", cmd_text))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("rag_source", cmd_rag_source))
    app.add_handler(CommandHandler("rag_load", cmd_rag_load))
    app.add_handler(CommandHandler("rag_reload", cmd_rag_reload))
    app.add_handler(CommandHandler("cache_view", cmd_cache_view))
    app.add_handler(CommandHandler("rag_detail", cmd_rag_detail))
    app.add_handler(CommandHandler("rag_clear", cmd_rag_clear))
    app.add_handler(CommandHandler("clear_cache", cmd_clear_cache))
    app.add_handler(CommandHandler("rag_add", cmd_rag_add))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.add_handler(MessageHandler(filters.Document.ALL, cmd_rag_add))
    return app
