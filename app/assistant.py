from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from app.config import Settings
from app.rag import RAGService, SUPPORTED_EXTENSIONS
from app.storage import SqliteStorage


@dataclass
class AssistantResponse:
    text: str
    from_cache: bool = False


class AssistantService:
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
            "/rag_add - загрузка файла в /rag_source\n"
            "/rag_source - список файлов-источников RAG\n"
            "/rag_clear <filename> - удаление файла и его чанков\n"
            "/rag_detail <filename> - показать чанки файла\n"
            "/rag_load - загрузка в RAG только не загруженных файлов\n"
            "/rag_reload - полная пересборка базы RAG\n"
            "/text - режим общения с ассистентом\n"
            "/clear - очистка памяти сессии\n"
            "/clear_cache [N YYYY-MM-DD] - очистка кэша\n"
            "/cache_view - просмотр кэша"
        )

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
        cached = self.storage.get_cached_answer(query)
        if cached is not None:
            self.storage.add_memory(session_id, "user", query)
            self.storage.add_memory(session_id, "assistant", cached)
            return AssistantResponse(text=cached, from_cache=True)

        memories = self.storage.get_last_memories(session_id, limit=5)
        rag_context = self.rag.search(query, top_k=4)
        answer = self._generate_answer(query=query, memories=memories, rag_context=rag_context)

        self.storage.save_cache(query, answer)
        self.storage.add_memory(session_id, "user", query)
        self.storage.add_memory(session_id, "assistant", answer)
        return AssistantResponse(text=answer, from_cache=False)

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
