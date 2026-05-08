from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    embedding_model: str
    telegram_bot_token: str
    telegram_support_chat_id: str
    sqlite_path: Path
    chroma_path: Path
    rag_source_dir: Path
    max_telegram_message_length: int


def load_settings() -> Settings:
    load_dotenv()
    sqlite_path = Path(os.getenv("SQLITE_PATH", "./data/assistant.db"))
    chroma_path = Path(os.getenv("CHROMA_PATH", "./data/chroma"))
    rag_source_dir = Path(os.getenv("RAG_SOURCE_DIR", "./rag_source"))

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    chroma_path.mkdir(parents=True, exist_ok=True)
    rag_source_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_support_chat_id=os.getenv("TELEGRAM_SUPPORT_CHAT_ID", ""),
        sqlite_path=sqlite_path,
        chroma_path=chroma_path,
        rag_source_dir=rag_source_dir,
        max_telegram_message_length=int(os.getenv("MAX_TELEGRAM_MESSAGE_LENGTH", "4000")),
    )
