from __future__ import annotations

from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.assistant import AssistantService
from app.config import load_settings

settings = load_settings()
service = AssistantService(settings=settings)
APP_REF: Application | None = None


def _session_id(update: Update) -> str:
    return str(update.effective_chat.id) if update.effective_chat else "unknown"


async def _send_text(update: Update, text: str) -> None:
    if not update.message:
        return
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


def _is_support_chat(update: Update) -> bool:
    support_id = settings.telegram_support_chat_id
    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    return bool(support_id) and chat_id == support_id


async def _notify_support(text: str) -> None:
    if not settings.telegram_support_chat_id or APP_REF is None:
        return
    await APP_REF.bot.send_message(chat_id=int(settings.telegram_support_chat_id), text=text)


async def cmd_dialogs(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_support_chat(update):
        await _send_text(update, "Команда доступна только сотруднику поддержки.")
        return
    dialogs = service.list_dialogues()
    if not dialogs:
        await _send_text(update, "Диалоги не найдены.")
        return
    lines = ["Список диалогов:"]
    for item in dialogs:
        lines.append(
            f"- {item['session_id']} | status={item['status']} | controller={item['controlled_by']} | "
            f"rating={item['rating'] if item['rating'] is not None else '-'}"
        )
    await _send_text(update, "\n".join(lines))


async def cmd_take(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_support_chat(update):
        await _send_text(update, "Команда доступна только сотруднику поддержки.")
        return
    if len(context.args) != 1:
        await _send_text(update, "Формат: /take <session_id>")
        return
    await _send_text(update, service.set_support_control(context.args[0], enabled=True))


async def cmd_release(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_support_chat(update):
        await _send_text(update, "Команда доступна только сотруднику поддержки.")
        return
    if len(context.args) != 1:
        await _send_text(update, "Формат: /release <session_id>")
        return
    await _send_text(update, service.set_support_control(context.args[0], enabled=False))


async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_support_chat(update):
        await _send_text(update, "Команда доступна только сотруднику поддержки.")
        return
    if len(context.args) != 1:
        await _send_text(update, "Формат: /close <session_id>")
        return
    sid = context.args[0]
    close_message = service.close_dialogue(sid)
    delivered = False
    if APP_REF is not None:
        try:
            await APP_REF.bot.send_message(chat_id=int(sid), text=close_message)
            delivered = True
        except ValueError:
            delivered = False
    if delivered:
        await _send_text(update, f"Диалог {sid} завершен, пользователю отправлен запрос оценки.")
    else:
        await _send_text(
            update,
            f"Диалог {sid} завершен. Для API-пользователя запрос оценки должен показать веб-клиент.",
        )


async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_support_chat(update):
        await _send_text(update, "Команда доступна только сотруднику поддержки.")
        return
    if len(context.args) < 2:
        await _send_text(update, "Формат: /reply <session_id> <текст>")
        return
    sid = context.args[0]
    text = " ".join(context.args[1:])
    service.add_support_message(sid, text)
    delivered = False
    if APP_REF is not None:
        try:
            await APP_REF.bot.send_message(chat_id=int(sid), text=text)
            delivered = True
        except ValueError:
            delivered = False
    if delivered:
        await _send_text(update, f"Ответ отправлен в диалог {sid}.")
    else:
        await _send_text(
            update,
            f"Ответ сохранен для API-пользователя {sid}. Заберите его через GET /support/inbox/{sid}.",
        )


async def cmd_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await _send_text(update, "Формат: /rate <1-5>")
        return
    try:
        rating = int(context.args[0])
    except ValueError:
        await _send_text(update, "Оценка должна быть числом от 1 до 5.")
        return
    await _send_text(update, service.set_rating(_session_id(update), rating))


async def cmd_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await _send_text(update, "Формат: /comment <текст>")
        return
    await _send_text(update, service.set_comment(_session_id(update), " ".join(context.args)))


async def cmd_themes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.themes_command(context.args))


async def cmd_synonimic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_text(update, service.synonimic_command(context.args))


async def text_message(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return
    if message.text.startswith("/"):
        return
    sid = _session_id(update)
    service.storage.ensure_dialogue(sid)
    state = service.storage.get_dialogue(sid)
    if state and state["status"] == "closed":
        await _send_text(update, "Диалог завершен. Поставьте оценку: /rate <1-5>.")
        return
    if state and state["controlled_by"] == "support":
        await _notify_support(f"[{sid}] user: {message.text}")
        await _send_text(update, "Ваш запрос передан сотруднику поддержки. Ожидайте ответа.")
        return
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
    app.add_handler(CommandHandler("dialogs", cmd_dialogs))
    app.add_handler(CommandHandler("take", cmd_take))
    app.add_handler(CommandHandler("release", cmd_release))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("reply", cmd_reply))
    app.add_handler(CommandHandler("rate", cmd_rate))
    app.add_handler(CommandHandler("comment", cmd_comment))
    app.add_handler(CommandHandler("themes", cmd_themes))
    app.add_handler(CommandHandler("synonimic", cmd_synonimic))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.add_handler(MessageHandler(filters.Document.ALL, cmd_rag_add))
    global APP_REF
    APP_REF = app
    return app
