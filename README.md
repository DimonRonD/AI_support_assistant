# AI Assistant

Ассистент поддержки с:

- RAG на ChromaDB из файлов `TXT/PDF/MD` в `rag_source`
- памятью последних 5 сообщений в SQLite
- кэшем запросов и ответов в SQLite
- Telegram ботом
- API на FastAPI

## Запуск

1. Установить зависимости:

```bash
pip install -r requirements.txt
```

2. Подготовить `.env`:

```bash
copy .env.example .env
```

3. Запуск API:

```bash
python run_api.py
```

4. Запуск Telegram бота:

```bash
python run_bot.py
```

Подробности по API: `API_GUIDE.md`.
