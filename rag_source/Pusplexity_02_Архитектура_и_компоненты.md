# Pusplexity — Архитектура и компоненты

## Архитектурный стиль

Проект реализован как модульный Python-монолит с двумя внешними интерфейсами:

- Telegram-бот;
- веб-приложение Flask.

Оба интерфейса используют общие бизнес-компоненты: обработчик OpenAI, RAG-хранилище, логи и пользовательскую память.

## Компонентная схема

### Интерфейсный слой

- `bot.py`
  - обработка Telegram-команд;
  - выбор режимов;
  - загрузка изображений/документов;
  - orchestration запросов к `processor.py` и `rag_store.py`.

- `web_app.py`
  - HTTP API и шаблонный UI;
  - аутентификация/сессии;
  - маршруты `/api/command`, `/api/send`, `/api/upload`, `/api/rag_delete`;
  - те же режимы, что и в Telegram.

### Доменный слой

- `processor.py`
  - единая интеграция с OpenAI:
    - `process` (image edit),
    - `process_create` (text-to-image),
    - `process_text_only`,
    - `process_text_with_image`,
    - `process_text_with_rag_context`.
  - нормализация изображений;
  - извлечение usage по токенам;
  - обработка совместимости legacy-алиасов моделей.

- `rag_store.py`
  - извлечение текста из документов;
  - чанкинг (`CHUNK_SIZE=500`, `CHUNK_OVERLAP=50`);
  - вычисление эмбеддингов (`text-embedding-3-small`);
  - upsert/search/delete в ChromaDB.

### Инфраструктурный слой

- `user_db.py`
  - SQLite-хранилище пользовательского состояния:
    - текущий режим/модель;
    - history text/rag;
    - сохраненный текстовый контекст.

- `action_logs.py`
  - SQLite-аудит событий:
    - `user_request`,
    - `ai_request`,
    - `ai_response`,
    - `error`.
  - агрегированная статистика за сутки;
  - выгрузка CSV;
  - автоочистка старых логов.

- `auth.py`
  - загрузка `users.txt`;
  - проверка email/пароль.

## Потоки данных

### Поток A: Image Edit

1. Пользователь выбирает image-режим.
2. Загружает 1–10 изображений.
3. Отправляет текстовую инструкцию.
4. `processor.process()` вызывает OpenAI `images.edit`.
5. Результат возвращается как PNG + usage.
6. Логируется полный цикл request/response.

### Поток B: Text Chat

1. Выбран text-режим.
2. Пользователь отправляет текст (и опционально 1 изображение).
3. `processor` вызывает chat completions.
4. История диалога обновляется (до 20 сообщений).
5. Ответ и токены логируются.

### Поток C: RAG Query

1. Документы загружены и проиндексированы.
2. Пользователь задает вопрос в `rag_text`.
3. `rag_store.query()` возвращает top-N чанков.
4. Контекст передается в `process_text_with_rag_context`.
5. Пользователь получает ответ + список источников/score.
6. История RAG-диалога и логи обновляются.

## Хранилища и персистентность

- `data/` — исходные документы для RAG.
- `chroma_db/` — persistent vector store (ChromaDB).
- `user_data.db` — пользовательские состояния web-пользователей.
- `action_logs.db` — аудит действий и usage.
- `bot_data.pickle` — persistence Telegram контекста.

В Docker это вынесено в тома для сохранности между рестартами.

## Безопасность

Веб-слой реализует:

- обязательный `FLASK_SECRET_KEY`;
- CSRF-защиту для POST;
- rate limiting API и логина;
- проверку типа загружаемого содержимого;
- `MAX_CONTENT_LENGTH` = 50 МБ;
- security headers (CSP, X-Frame-Options, etc.);
- запуск контейнеров с ограничениями (`no-new-privileges`, `cap_drop: ALL`).

## Масштабирование и ограничения

- Проект рассчитан на малую/среднюю нагрузку.
- Gunicorn в compose запущен с 1 worker (можно масштабировать конфигом).
- Основные bottleneck-зоны:
  - время ответа OpenAI;
  - время индексации документов;
  - рост SQLite/Chroma при большом объеме данных.

## Конфигурация через env

Ключевые переменные:

- `OPENAI_API_KEY`
- `OPENAI_TEXT_MODEL`
- `TELEGRAM_BOT_TOKEN`
- `FLASK_SECRET_KEY`
- `API_RATE_WINDOW_SEC`, `API_RATE_LIMIT_PER_WINDOW`
- `DOC_PARSE_TIMEOUT_SEC`
- `MAX_CONTEXT_CHARS`
- `USER_DATA_RETENTION_DAYS`
- `LOG_RETENTION_DAYS`
- `TRAEFIK_CERT_RESOLVER`

