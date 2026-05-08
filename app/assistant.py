from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import urlopen

from openai import OpenAI

from app.config import Settings
from app.rag import RAGService, SUPPORTED_EXTENSIONS
from app.storage import SqliteStorage


@dataclass
class AssistantResponse:
    text: str
    from_cache: bool = False


class AssistantService:
    OUT_OF_SCOPE_REPLY = (
        "К сожалению, интересующий вас вопрос не относится к тематике нашего ресурса"
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = SqliteStorage(settings.sqlite_path)
        self.rag = RAGService(
            chroma_path=settings.chroma_path,
            embedding_model=settings.embedding_model,
            openai_api_key=settings.openai_api_key,
        )
        self.openai = OpenAI(api_key=settings.openai_api_key)

    def help_text(self) -> str:
        return (
            "/help - список команд\n"
            "/text - режим общения с ассистентом\n"
            "/themes - показать список тем\n"
            "/themes add <тема> - добавить тему\n"
            "/themes remove <тема> - удалить тему\n"
            "/themes clear - очистить темы\n"
            "/synonimic - показать словарь синонимов\n"
            "/synonimic add <название> | <синоним1,синоним2> - добавить синонимы\n"
            "/synonimic remove <название> - удалить группу синонимов\n"
            "/synonimic clear - очистить словарь синонимов\n"
            "/rag_add - загрузка файла в /rag_source\n"
            "/rag_source - список файлов-источников RAG\n"
            "/rag_clear <filename> - удаление файла и его чанков\n"
            "/rag_detail <filename> - показать чанки файла\n"
            "/rag_load - загрузка в RAG только не загруженных файлов\n"
            "/rag_reload - полная пересборка базы RAG\n"
            "/clear - очистка памяти сессии\n"
            "/clear_cache [N YYYY-MM-DD] - очистка кэша\n"
            "/cache_view - просмотр кэша\n"
            "/rate <1-5> - оценка завершенного диалога\n"
            "/comment <текст> - комментарий к оценке (только после /rate)\n"
            "/dialogs - список диалогов (для поддержки)\n"
            "/take <session_id> - перехватить диалог поддержкой\n"
            "/release <session_id> - вернуть диалог AI\n"
            "/reply <session_id> <текст> - ответить пользователю вручную\n"
            "/close <session_id> - завершить диалог"
        )

    def api_help_text(self) -> str:
        return (
            "API команды:\n"
            "POST /auth - авторизация пользователя (name, email, session_id)\n"
            "POST /text - запрос к ассистенту\n"
            "POST /rate - установить оценку 1..5\n"
            "POST /comment - сохранить комментарий (только после оценки)\n"
            "GET /dialog/{session_id} - данные диалога и сообщения\n"
            "GET /support/inbox/{session_id}?after_id=N - новые ответы оператора"
        )

    def authorize_api_user(self, session_id: str, name: str, email: str) -> dict[str, object]:
        email_norm = self._norm_email(email)
        self.storage.auth_user(session_id=session_id, name=name.strip(), email=email_norm)
        self.storage.ensure_dialogue(session_id)
        previous_session = self.storage.get_previous_session(session_id)
        history: list[dict[str, object]] = []
        if previous_session:
            history = self.storage.get_dialogue_messages(previous_session, limit=20)
        return {
            "message": "Авторизация выполнена.",
            "has_previous_history": bool(history),
            "history": history,
        }

    def is_authorized(self, session_id: str) -> bool:
        return self.storage.is_authorized_session(session_id)

    def rag_add_file(self, source_path: Path) -> str:
        if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return "Неподдерживаемый формат. Разрешены TXT, PDF, MD."
        destination = self.settings.rag_source_dir / source_path.name
        shutil.copy2(source_path, destination)
        return f"Файл {source_path.name} добавлен в папку RAG-источников."

    def rag_source(self) -> str:
        files = self.rag.list_source_files(self.settings.rag_source_dir)
        loaded = self.storage.get_rag_files()
        if not files:
            return "Папка /rag_source пуста."
        lines = []
        for file_path in files:
            chunks = loaded.get(file_path.name)
            if chunks is None:
                lines.append(f"- {file_path.name}: Файл не загружен в базу RAG")
            else:
                lines.append(f"- {file_path.name}: чанков {chunks}")
        return "\n".join(lines)

    def rag_clear(self, filename: str) -> str:
        path = self.settings.rag_source_dir / filename
        if path.exists():
            path.unlink()
        self.rag.clear_filename(filename)
        self.storage.remove_rag_file(filename)
        return f"Файл {filename} и его данные из RAG удалены."

    def rag_detail(self, filename: str) -> str:
        chunks = self.rag.get_chunks_for_filename(filename)
        if not chunks:
            return f"Для файла {filename} чанки не найдены."
        lines = [f"Чанки файла {filename}:"]
        lines.extend([f"[{idx}] {chunk}" for idx, chunk in enumerate(chunks)])
        return "\n\n".join(lines)

    def rag_load(self) -> str:
        files = self.rag.list_source_files(self.settings.rag_source_dir)
        loaded = self.storage.get_rag_files()
        pending = [f for f in files if f.name not in loaded]
        if not pending:
            return "Новых файлов для загрузки в RAG нет."
        lines = []
        for file_path in pending:
            count = self.rag.upsert_file(file_path)
            self.storage.upsert_rag_file(file_path.name, count)
            lines.append(f"- {file_path.name}: загружено чанков {count}")
        return "Загрузка завершена:\n" + "\n".join(lines)

    def rag_reload(self) -> str:
        files = self.rag.list_source_files(self.settings.rag_source_dir)
        self.rag.clear_all()
        self.storage.clear_rag_files()
        lines = []
        for file_path in files:
            count = self.rag.upsert_file(file_path)
            self.storage.upsert_rag_file(file_path.name, count)
            lines.append(f"- {file_path.name}: загружено чанков {count}")
        if not lines:
            return "База RAG очищена. В /rag_source нет файлов для загрузки."
        return "База RAG пересобрана:\n" + "\n".join(lines)

    def set_text_mode(self, session_id: str) -> str:
        self.storage.set_mode(session_id, "text")
        return "Режим /text активирован."

    def clear_memory(self, session_id: str) -> str:
        deleted = self.storage.clear_memory(session_id)
        return f"Память очищена. Удалено сообщений: {deleted}."

    def clear_cache(self, n: int | None = None, older_than: str | None = None) -> str:
        removed = self.storage.clear_cache(max_hits=n, older_than=older_than)
        return f"Удалено записей из кэша: {removed}."

    def cache_view(self) -> str:
        rows = self.storage.get_cache_rows()
        if not rows:
            return "Кэш пуст."
        header = "дата создания | количество совпадений | запрос | ответ"
        lines = [header, "-" * len(header)]
        for row in rows:
            lines.append(
                f"{row['created_at']} | {row['hit_count']} | {row['query']} | {row['answer']}"
            )
        return "\n".join(lines)

    def ask(self, session_id: str, query: str) -> AssistantResponse:
        self.storage.ensure_dialogue(session_id)
        if self._norm(query) == "очистить историю":
            self.storage.clear_session_history(session_id)
            return AssistantResponse(text="История общения очищена.")
        self.storage.append_dialogue_message(session_id, "user", query)
        self._notify_support(session_id, "user", query)
        if len(query) > 250:
            return AssistantResponse(text="Сообщение слишком длинное. Допустимо не более 250 символов.")
        if not self._is_in_scope(query):
            self.storage.append_dialogue_message(session_id, "ai", self.OUT_OF_SCOPE_REPLY)
            self._notify_support(session_id, "ai", self.OUT_OF_SCOPE_REPLY)
            return AssistantResponse(text=self.OUT_OF_SCOPE_REPLY)
        state = self.storage.get_dialogue(session_id)
        if state and state["status"] == "closed":
            return AssistantResponse(
                text="Диалог уже завершен. Пожалуйста, поставьте оценку /rate <1-5>."
            )
        if state and state["controlled_by"] == "support":
            return AssistantResponse(
                text="Диалог передан сотруднику поддержки. Пожалуйста, ожидайте ответа."
            )

        cached = self.storage.get_cached_answer(query)
        if cached is not None:
            self.storage.add_memory(session_id, "user", query)
            self.storage.add_memory(session_id, "assistant", cached)
            self.storage.append_dialogue_message(session_id, "ai", cached)
            self._notify_support(session_id, "ai", cached)
            return AssistantResponse(text=cached, from_cache=True)

        memories = self.storage.get_last_memories(session_id, limit=5)
        rag_context = self.rag.search(query, top_k=4)
        answer = self._generate_answer(query=query, memories=memories, rag_context=rag_context)

        self.storage.save_cache(query, answer)
        self.storage.add_memory(session_id, "user", query)
        self.storage.add_memory(session_id, "assistant", answer)
        self.storage.append_dialogue_message(session_id, "ai", answer)
        self._notify_support(session_id, "ai", answer)
        return AssistantResponse(text=answer, from_cache=False)

    def set_support_control(self, session_id: str, enabled: bool) -> str:
        self.storage.ensure_dialogue(session_id)
        controller = "support" if enabled else "ai"
        self.storage.set_controller(session_id, controller)
        if enabled:
            text = f"Диалог {session_id} передан сотруднику поддержки."
            self.storage.append_dialogue_message(session_id, "support", text)
            return text
        text = f"Диалог {session_id} возвращен AI-ассистенту."
        self.storage.append_dialogue_message(session_id, "support", text)
        return text

    def close_dialogue(self, session_id: str) -> str:
        self.storage.ensure_dialogue(session_id)
        self.storage.close_dialogue(session_id)
        close_text = (
            "Диалог завершен. Пожалуйста, поставьте оценку от 1 до 5: /rate <1-5>. "
            "После этого можно оставить комментарий: /comment <текст>."
        )
        # For web/API clients we persist a support message so UI can show closure immediately.
        self.storage.append_dialogue_message(session_id, "support", close_text)
        return close_text

    def set_rating(self, session_id: str, rating: int) -> str:
        self.storage.ensure_dialogue(session_id)
        if rating < 1 or rating > 5:
            return "Оценка должна быть от 1 до 5."
        self.storage.set_rating(session_id, rating)
        return "Оценка сохранена. При желании добавьте комментарий: /comment <текст>."

    def set_comment(self, session_id: str, comment: str) -> str:
        self.storage.ensure_dialogue(session_id)
        state = self.storage.get_dialogue(session_id)
        if not state or state["rating"] is None:
            return "Сначала установите оценку командой /rate <1-5>."
        self.storage.set_comment(session_id, comment)
        return "Комментарий сохранен. Спасибо за обратную связь."

    def add_support_message(self, session_id: str, text: str) -> None:
        self.storage.ensure_dialogue(session_id)
        self.storage.append_dialogue_message(session_id, "support", text)

    def dialog_snapshot(self, session_id: str) -> dict[str, object]:
        self.storage.ensure_dialogue(session_id)
        return {
            "dialog": self.storage.get_dialogue(session_id),
            "messages": self.storage.get_dialogue_messages(session_id),
        }

    def list_dialogues(self) -> list[dict[str, object]]:
        return self.storage.list_active_dialogues()

    def support_inbox(self, session_id: str, after_id: int = 0) -> dict[str, object]:
        self.storage.ensure_dialogue(session_id)
        messages = self.storage.get_support_messages(session_id, after_id=after_id)
        dialog = self.storage.get_dialogue(session_id) or {}
        last_id = after_id
        if messages:
            last_id = int(messages[-1]["id"])
        return {
            "session_id": session_id,
            "after_id": after_id,
            "last_id": last_id,
            "dialog_closed": dialog.get("status") == "closed",
            "messages": messages,
        }

    def _generate_answer(
        self, query: str, memories: list[dict[str, str]], rag_context: list[str]
    ) -> str:
        context_block = "\n\n".join(rag_context) if rag_context else "Контекст RAG не найден."
        memory_lines = "\n".join([f"{m['role']}: {m['content']}" for m in memories]) or "-"
        system_prompt = (
            "Ты помощник службы поддержки. Отвечай кратко, ясно и по делу. "
            "Учитывай историю сообщений и контекст базы знаний."
        )
        user_prompt = (
            f"История последних 5 сообщений:\n{memory_lines}\n\n"
            f"Контекст RAG:\n{context_block}\n\n"
            f"Запрос пользователя:\n{query}"
        )
        response = self.openai.responses.create(
            model=self.settings.openai_model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.output_text

    def split_for_telegram(self, text: str) -> list[str]:
        max_len = self.settings.max_telegram_message_length
        if len(text) <= max_len:
            return [text]
        parts: list[str] = []
        current = text
        while len(current) > max_len:
            split_at = current.rfind("\n", 0, max_len)
            if split_at <= 0:
                split_at = max_len
            parts.append(current[:split_at])
            current = current[split_at:].lstrip("\n")
        if current:
            parts.append(current)
        return parts

    def _notify_support(self, session_id: str, actor: str, text: str) -> None:
        if not self.settings.telegram_support_chat_id or not self.settings.telegram_bot_token:
            return
        try:
            payload = f"[{session_id}] {actor}: {text}"
            url = (
                f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
                f"?chat_id={quote_plus(self.settings.telegram_support_chat_id)}"
                f"&text={quote_plus(payload)}"
            )
            with urlopen(url, timeout=5):
                pass
        except Exception:
            # Notification failures should not break main assistant flow.
            return

    def themes_command(self, args: list[str]) -> str:
        if not args:
            themes = self.storage.list_themes()
            if not themes:
                return "Тематика не задана. Добавьте темы: /themes add <тема>."
            return "Темы:\n" + "\n".join([f"- {item}" for item in themes])
        action = args[0].lower()
        if action == "add" and len(args) >= 2:
            theme = " ".join(args[1:]).strip()
            self.storage.add_theme(theme)
            return f"Тема добавлена: {theme}"
        if action == "remove" and len(args) >= 2:
            theme = " ".join(args[1:]).strip()
            removed = self.storage.remove_theme(theme)
            if removed == 0:
                return f"Тема не найдена: {theme}"
            return f"Тема удалена: {theme}"
        if action == "clear":
            self.storage.clear_themes()
            return "Список тем очищен."
        return "Формат: /themes | /themes add <тема> | /themes remove <тема> | /themes clear"

    def synonimic_command(self, args: list[str]) -> str:
        if not args:
            groups = self.storage.list_synonyms()
            if not groups:
                return "Список синонимов пуст."
            lines = ["Синонимы:"]
            for canonical, syns in groups.items():
                lines.append(f"- {canonical}: {', '.join(syns)}")
            return "\n".join(lines)
        action = args[0].lower()
        if action == "add" and len(args) >= 2:
            raw = " ".join(args[1:])
            if "|" not in raw:
                return "Формат: /synonimic add <название> | <синоним1,синоним2>"
            canonical_raw, synonyms_raw = raw.split("|", 1)
            canonical = canonical_raw.strip()
            synonyms = [item.strip() for item in synonyms_raw.split(",") if item.strip()]
            if not canonical or not synonyms:
                return "Формат: /synonimic add <название> | <синоним1,синоним2>"
            for item in synonyms:
                self.storage.add_synonym(canonical, item)
            return f"Синонимы добавлены для '{canonical}'."
        if action == "remove" and len(args) >= 2:
            canonical = " ".join(args[1:]).strip()
            removed = self.storage.remove_synonym_group(canonical)
            if removed == 0:
                return f"Группа синонимов не найдена: {canonical}"
            return f"Синонимы удалены для '{canonical}'."
        if action == "clear":
            self.storage.clear_synonyms()
            return "Список синонимов очищен."
        return (
            "Формат: /synonimic | /synonimic add <название> | <синоним1,синоним2> | "
            "/synonimic remove <название> | /synonimic clear"
        )

    def _is_in_scope(self, query: str) -> bool:
        themes = self.storage.list_themes()
        if not themes:
            return True
        normalized_query = self._norm(query)
        terms = {self._norm(theme) for theme in themes}
        for canonical, syns in self.storage.list_synonyms().items():
            canonical_norm = self._norm(canonical)
            if canonical_norm in terms:
                terms.update({self._norm(s) for s in syns})
                terms.add(canonical_norm)
        return any(term and term in normalized_query for term in terms)

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(text.lower().replace("ё", "е").split())

    @staticmethod
    def _norm_email(email: str) -> str:
        return email.strip().lower()
