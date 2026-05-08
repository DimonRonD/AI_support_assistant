from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.assistant import AssistantService
from app.config import load_settings

settings = load_settings()
service = AssistantService(settings=settings)
app = FastAPI(title="AI Assistant API", version="1.0.0")


class AskRequest(BaseModel):
    session_id: str
    query: str


class CacheClearRequest(BaseModel):
    n: int | None = None
    date: str | None = None


class FilenameRequest(BaseModel):
    filename: str


@app.get("/help")
def api_help() -> dict[str, str]:
    return {"message": service.help_text()}


@app.post("/rag_add")
async def api_rag_add(file: UploadFile = File(...)) -> dict[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".pdf", ".md"}:
        raise HTTPException(status_code=400, detail="Поддерживаются только TXT, PDF, MD.")
    destination = settings.rag_source_dir / (file.filename or "uploaded.txt")
    content = await file.read()
    destination.write_bytes(content)
    return {"message": f"Файл {destination.name} загружен в /rag_source."}


@app.get("/rag_source")
def api_rag_source() -> dict[str, str]:
    return {"message": service.rag_source()}


@app.post("/rag_clear")
def api_rag_clear(request: FilenameRequest) -> dict[str, str]:
    return {"message": service.rag_clear(request.filename)}


@app.post("/rag_detail")
def api_rag_detail(request: FilenameRequest) -> dict[str, str]:
    return {"message": service.rag_detail(request.filename)}


@app.post("/rag_load")
def api_rag_load() -> dict[str, str]:
    return {"message": service.rag_load()}


@app.post("/rag_reload")
def api_rag_reload() -> dict[str, str]:
    return {"message": service.rag_reload()}


@app.post("/text")
def api_text(request: AskRequest) -> dict[str, str | bool]:
    result = service.ask(session_id=request.session_id, query=request.query)
    return {"answer": result.text, "from_cache": result.from_cache}


@app.post("/mode_text/{session_id}")
def api_mode_text(session_id: str) -> dict[str, str]:
    return {"message": service.set_text_mode(session_id)}


@app.post("/clear/{session_id}")
def api_clear(session_id: str) -> dict[str, str]:
    return {"message": service.clear_memory(session_id)}


@app.post("/clear_cache")
def api_clear_cache(request: CacheClearRequest) -> dict[str, str]:
    if (request.n is None) != (request.date is None):
        raise HTTPException(status_code=400, detail="Передайте либо оба параметра n и date, либо ни одного.")
    return {"message": service.clear_cache(request.n, request.date)}


@app.get("/cache_view")
def api_cache_view() -> dict[str, str]:
    return {"message": service.cache_view()}
