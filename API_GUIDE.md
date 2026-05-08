# API Guide for Integrators

## 1) Purpose and Scope

This document describes how an external application integrates with the assistant API.

API scope:
- authorize user with name and email;
- send user messages to assistant;
- receive assistant response;
- retrieve manual support replies for web clients;
- send final rating;
- send optional comment (only after rating);
- request dialogue state and message history.

Out of scope for this API:
- RAG source file management;
- cache administration;
- memory reset commands.

## 2) Connection Basics

- Transport: HTTP/HTTPS
- Payload format: `application/json`
- Base URL (example): `http://localhost:8000`
- OpenAPI/Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- Authentication: not enabled in current version

## 3) User Journey

### Stage A: Start or continue dialogue
1. Your app creates or reuses a stable `session_id` for end user.
2. Your app calls `POST /auth` with `name`, `email`, `session_id`.
3. API returns auth status and previous dialogue history (if found).
4. Your app asks user if previous history should be continued.
5. If user wants clean context, app sends message `очистить историю` to `POST /text`.
6. Then your app continues normal flow with `POST /text`.

### Stage B: Handle support takeover/closed dialogue states
When calling `POST /text`:
- if dialogue is controlled by support, API returns waiting message;
- if dialogue is closed, API returns rating prompt.

### Stage C: Finish dialogue and collect feedback
1. Your app sends rating `1..5` to `POST /rate`.
2. If user wants to add details, your app sends text to `POST /comment`.
3. To display full transcript and final state, your app calls `GET /dialog/{session_id}`.

## 4) Endpoints

### `GET /help`
Returns textual list of API commands.

Response example:
```json
{
  "message": "API команды: ..."
}
```

### `POST /auth`
Authorize user before any dialogue operations.

Request:
```json
{
  "session_id": "crm-user-00042",
  "name": "Ivan Petrov",
  "email": "ivan.petrov@example.com"
}
```

Response:
```json
{
  "message": "Авторизация выполнена.",
  "has_previous_history": true,
  "history": [
    {
      "actor": "user",
      "content": "Здравствуйте",
      "created_at": "2026-05-08 10:01:05"
    },
    {
      "actor": "ai",
      "content": "Здравствуйте! Чем могу помочь?",
      "created_at": "2026-05-08 10:01:06"
    }
  ]
}
```

Notes:
- all auth attempts are stored in auth logs (`session_id`, `name`, `email`, timestamp);
- session becomes allowed for `/text`, `/rate`, `/comment`, `/dialog/{session_id}`.

### `POST /text`
Send one user message to assistant.

Request:
```json
{
  "session_id": "crm-user-00042",
  "query": "Как восстановить пароль?"
}
```

Response:
```json
{
  "answer": "Текст ответа ассистента",
  "from_cache": false
}
```

Notes:
- memory of last 5 messages is included in context;
- RAG context is included in generation;
- answer may be returned from cache;
- dialogue messages are logged with actor marker (`user`/`ai`/`support`).
- if payload query is exactly `очистить историю`, current session history is cleared.

### `POST /rate`
Save final dialogue rating.

Request:
```json
{
  "session_id": "crm-user-00042",
  "rating": 5
}
```

Response:
```json
{
  "message": "Оценка сохранена. При желании добавьте комментарий: /comment <текст>."
}
```

Validation:
- `rating` must be integer in range `1..5`.

### `POST /comment`
Save optional comment for dialogue feedback.

Request:
```json
{
  "session_id": "crm-user-00042",
  "comment": "Вопрос решился быстро."
}
```

Response:
```json
{
  "message": "Комментарий сохранен. Спасибо за обратную связь."
}
```

Validation:
- comment is accepted only after rating was set.

### `GET /dialog/{session_id}`
Return dialogue metadata and message timeline.

Response example:
```json
{
  "dialog": {
    "session_id": "crm-user-00042",
    "status": "closed",
    "controlled_by": "support",
    "rating": 5,
    "comment": "Спасибо",
    "created_at": "2026-05-08 10:01:00",
    "updated_at": "2026-05-08 10:20:00",
    "closed_at": "2026-05-08 10:19:00"
  },
  "messages": [
    {
      "actor": "user",
      "content": "Здравствуйте",
      "created_at": "2026-05-08 10:01:05"
    },
    {
      "actor": "ai",
      "content": "Здравствуйте! Чем могу помочь?",
      "created_at": "2026-05-08 10:01:06"
    },
    {
      "actor": "support",
      "content": "Подключился оператор, уточните номер заказа.",
      "created_at": "2026-05-08 10:05:12"
    }
  ]
}
```

### `GET /support/inbox/{session_id}?after_id=N`
Return support-operator replies for web/API users.

Use case:
- support operator sends `/reply <session_id> <text>` in Telegram support chat;
- web client polls this endpoint and displays new support messages.

Response example:
```json
{
  "session_id": "web-6f58927ca7464bc5",
  "after_id": 0,
  "last_id": 142,
  "dialog_closed": true,
  "messages": [
    {
      "id": 141,
      "actor": "support",
      "content": "Добрый день! Подключился оператор поддержки.",
      "created_at": "2026-05-08 16:12:02"
    },
    {
      "id": 142,
      "actor": "support",
      "content": "Уточните, пожалуйста, номер заказа.",
      "created_at": "2026-05-08 16:12:20"
    }
  ]
}
```

## 5) Error Handling

### HTTP status codes used
- `200 OK`: successful request
- `400 Bad Request`: validation/business rule violation
- `422 Unprocessable Entity`: malformed JSON or missing required fields
- `500 Internal Server Error`: unexpected server-side failure

### Common API error cases

1) `POST /rate` with invalid range
```json
{
  "detail": "rating должен быть от 1 до 5."
}
```

2) `POST /comment` before rating
```json
{
  "detail": "Сначала установите оценку командой /rate <1-5>."
}
```

3) Invalid payload type (example: string instead of integer)
- FastAPI returns `422` with field-level validation details.

4) Access endpoints without auth
```json
{
  "detail": "Сначала выполните авторизацию через POST /auth (name, email, session_id)."
}
```

### Integrator recommendations
- Retry only on transient failures (`5xx`, network timeouts).
- Do not retry `4xx` blindly; fix request data first.
- Log request id/session id and endpoint for observability.

## 6) Best Practices for `session_id`

### Required properties
- stable for one end user dialogue context;
- unique across your integration;
- deterministic and reproducible from your user source id.

### Recommended format
- prefix by source system + unique user key, for example:
  - `crm-user-00042`
  - `tg-67382910`
  - `web-9f3a2c18`

### Practical rules
- use one `session_id` per user conversation thread;
- do not reuse `session_id` for different users;
- store mapping in your system (`external_user_id -> session_id`);
- avoid PII directly in `session_id` (email/phone in plain text).

## 7) Integration Examples (`curl`)

### Send user message
```bash
curl -X POST "http://localhost:8000/text" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"crm-user-00042\",\"query\":\"Какие сроки возврата?\"}"
```

### Authorize user
```bash
curl -X POST "http://localhost:8000/auth" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"crm-user-00042\",\"name\":\"Ivan Petrov\",\"email\":\"ivan.petrov@example.com\"}"
```

### Clear dialogue history
```bash
curl -X POST "http://localhost:8000/text" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"crm-user-00042\",\"query\":\"очистить историю\"}"
```

### Set rating
```bash
curl -X POST "http://localhost:8000/rate" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"crm-user-00042\",\"rating\":4}"
```

### Send comment
```bash
curl -X POST "http://localhost:8000/comment" ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"crm-user-00042\",\"comment\":\"Все понятно\"}"
```

### Fetch dialogue snapshot
```bash
curl -X GET "http://localhost:8000/dialog/crm-user-00042"
```

### Fetch support replies for web user
```bash
curl -X GET "http://localhost:8000/support/inbox/web-6f58927ca7464bc5?after_id=0"
```
