# AI Assistant

Ассистент поддержки с:

- RAG на ChromaDB из файлов `TXT/PDF/MD` в `rag_source`
- памятью последних 5 сообщений в SQLite
- кэшем запросов и ответов в SQLite
- Telegram ботом
- API на FastAPI

## Установка и настройка

1. Установить зависимости:

```bash
pip install -r requirements.txt
```

2. Подготовить `.env`:

```bash
copy .env.example .env
```

3. Заполнить переменные в `.env`:

- `OPENAI_API_KEY` - API-ключ OpenAI
- `OPENAI_MODEL` - модель ответов (например `gpt-5-nano-2025-08-07`)
- `OPENAI_EMBEDDING_MODEL` - модель эмбеддингов
- `TELEGRAM_BOT_TOKEN` - токен Telegram-бота
- `TELEGRAM_SUPPORT_CHAT_ID` - chat id операторского чата поддержки
- `SQLITE_PATH` - путь к SQLite базе
- `CHROMA_PATH` - путь к хранилищу ChromaDB
- `RAG_SOURCE_DIR` - папка файлов для RAG
- `MAX_TELEGRAM_MESSAGE_LENGTH` - лимит длины сообщения Telegram (по умолчанию 4000)

## Запуск

### API

```bash
python run_api.py
```

### Telegram бот

```bash
python run_bot.py
```

## Docker

Профили:
- `api-only` - только API
- `full` - API + Telegram-бот

Запуск только API:

```bash
docker compose --profile api-only up --build -d
```

Запуск полного стека (API + бот):

```bash
docker compose --profile full up --build -d
```

Проверить логи:

```bash
docker compose logs -f api
docker compose logs -f bot
```

Остановка:

```bash
docker compose down
```

Проверить health API:

```bash
docker compose ps
```

В колонке `STATE` у сервиса `api` должно быть `healthy`.

## Краткий flow API (с авторизацией)

1. Авторизовать пользователя:
   - `POST /auth` с `session_id`, `name`, `email`.
2. Проверить ответ:
   - если `has_previous_history = true`, показать пользователю историю и спросить, продолжать ли.
3. Если пользователь не хочет продолжать:
   - отправить `POST /text` с `query = "очистить историю"`.
4. Для обычного общения:
   - отправлять сообщения в `POST /text`.
5. По завершении:
   - `POST /rate`, затем (опционально) `POST /comment`.
6. Для просмотра состояния и лога:
   - `GET /dialog/{session_id}`.

Минимальные примеры:

```bash
curl -X POST "http://localhost:8000/auth" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"crm-user-00042\",\"name\":\"Ivan Petrov\",\"email\":\"ivan.petrov@example.com\"}"
```

```bash
curl -X POST "http://localhost:8000/text" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"crm-user-00042\",\"query\":\"Здравствуйте\"}"
```

```bash
curl -X POST "http://localhost:8000/text" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"crm-user-00042\",\"query\":\"очистить историю\"}"
```

## Команды Telegram

- `/help` - список команд
- `/text` - режим общения с ассистентом
- `/themes` - показать список тем
- `/themes add <тема>` - добавить тему
- `/themes remove <тема>` - удалить тему
- `/themes clear` - очистить список тем
- `/synonimic` - показать словарь синонимов
- `/synonimic add <название> | <синоним1,синоним2>` - добавить синонимы
- `/synonimic remove <название>` - удалить группу синонимов
- `/synonimic clear` - очистить словарь синонимов
- `/rag_add` - загрузка файла в папку RAG-источников
- `/rag_source` - список файлов-источников RAG
- `/rag_clear <filename>` - удаление файла и его данных из RAG
- `/rag_detail <filename>` - просмотр чанков файла
- `/rag_load` - загрузка в RAG только новых файлов
- `/rag_reload` - полная пересборка RAG
- `/clear` - очистка памяти сессии
- `/clear_cache [N YYYY-MM-DD]` - очистка кэша
- `/cache_view` - просмотр кэша
- `/rate <1-5>` - оценка диалога
- `/comment <текст>` - комментарий к оценке (после `/rate`)
- `/dialogs` - список диалогов (команда чата поддержки)
- `/take <session_id>` - перехват диалога сотрудником поддержки
- `/release <session_id>` - возврат диалога AI-ассистенту
- `/reply <session_id> <текст>` - ручной ответ сотрудника пользователю
- `/close <session_id>` - завершение диалога сотрудником поддержки

Подробности по API: `API_GUIDE.md`.
