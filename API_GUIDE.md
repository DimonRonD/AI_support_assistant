# API Guide

## 1. Base info

- Framework: FastAPI
- Base URL (local): `http://localhost:8000`
- Content type: `application/json` for JSON endpoints
- RAG file upload endpoint uses `multipart/form-data`

Run API:

```bash
python run_api.py
```

Swagger UI:

- [http://localhost:8000/docs](http://localhost:8000/docs)

## 2. Environment setup

1. Copy `.env.example` to `.env`
2. Set values:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL` (for example `gpt-5-nano-2025-08-07`)
   - `TELEGRAM_BOT_TOKEN` (for Telegram bot)
   - storage paths if needed

## 3. Endpoint list

### `GET /help`

Returns command list.

Response:

```json
{
  "message": "..."
}
```

### `POST /rag_add`

Upload TXT/PDF/MD file into `/rag_source`.

- Body: `multipart/form-data`
- Field: `file`

Response:

```json
{
  "message": "Файл <name> загружен в /rag_source."
}
```

### `GET /rag_source`

List source files and RAG status (`чанков N` or `Файл не загружен в базу RAG`).

### `POST /rag_clear`

Delete a file from `/rag_source` and remove its chunks from RAG.

Request:

```json
{
  "filename": "manual.pdf"
}
```

### `POST /rag_detail`

Return chunks for file.

Request:

```json
{
  "filename": "manual.pdf"
}
```

### `POST /rag_load`

Load only files that are not loaded into RAG yet.

### `POST /rag_reload`

Clear RAG completely, then rebuild from all files in `/rag_source`.

### `POST /text`

Main assistant endpoint (chat mode), with memory + cache + RAG context.

Request:

```json
{
  "session_id": "user-123",
  "query": "Как оформить возврат?"
}
```

Response:

```json
{
  "answer": "Текст ответа",
  "from_cache": false
}
```

### `POST /mode_text/{session_id}`

Set session mode to text.

### `POST /clear/{session_id}`

Clear memory for session.

### `POST /clear_cache`

Without params:
- deletes entries where hit count is only first request (`hit_count <= 1`)
- and create date is older than 3 months

With params:

```json
{
  "n": 3,
  "date": "2026-01-01"
}
```

Deletes records where:
- `hit_count < n`
- `created_at < date`

### `GET /cache_view`

Returns cache as text table with fields:
- дата создания
- количество совпадений
- запрос
- ответ

## 4. Request examples

### Ask assistant

```bash
curl -X POST "http://localhost:8000/text" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"demo\",\"query\":\"Как восстановить пароль?\"}"
```

### Upload RAG file

```bash
curl -X POST "http://localhost:8000/rag_add" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@faq.md"
```

### Reload all RAG data

```bash
curl -X POST "http://localhost:8000/rag_reload"
```

## 5. Telegram parity

All business operations available in Telegram commands are mirrored in API:

- `/help` -> `GET /help`
- `/rag_add` -> `POST /rag_add`
- `/rag_source` -> `GET /rag_source`
- `/rag_clear` -> `POST /rag_clear`
- `/rag_detail` -> `POST /rag_detail`
- `/rag_load` -> `POST /rag_load`
- `/rag_reload` -> `POST /rag_reload`
- `/text` -> `POST /text`
- `/clear` -> `POST /clear/{session_id}`
- `/clear_cache` -> `POST /clear_cache`
- `/cache_view` -> `GET /cache_view`

## 6. Notes on internals

- RAG vector store: ChromaDB (`CHROMA_PATH`)
- Source docs folder: `RAG_SOURCE_DIR` (default `./rag_source`)
- Memory and cache DB: SQLite (`SQLITE_PATH`)
- Memory window: 5 last messages per session
- Telegram message split limit: configurable with `MAX_TELEGRAM_MESSAGE_LENGTH` (default 4000)
