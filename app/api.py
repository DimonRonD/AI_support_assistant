from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.assistant import AssistantService
from app.config import load_settings

settings = load_settings()
service = AssistantService(settings=settings)
app = FastAPI(title="AI Assistant API", version="1.0.0")


class AskRequest(BaseModel):
    session_id: str
    query: str


class AuthRequest(BaseModel):
    session_id: str
    name: str
    email: str


class RateRequest(BaseModel):
    session_id: str
    rating: int


class CommentRequest(BaseModel):
    session_id: str
    comment: str


@app.get("/help")
def api_help() -> dict[str, str]:
    return {"message": service.api_help_text()}


@app.post("/auth")
def api_auth(request: AuthRequest) -> dict[str, object]:
    if "@" not in request.email:
        raise HTTPException(status_code=400, detail="Некорректный email.")
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Имя не может быть пустым.")
    result = service.authorize_api_user(
        session_id=request.session_id,
        name=request.name,
        email=request.email,
    )
    return result


@app.post("/text")
def api_text(request: AskRequest) -> dict[str, str | bool]:
    if not service.is_authorized(request.session_id):
        raise HTTPException(
            status_code=401,
            detail="Сначала выполните авторизацию через POST /auth (name, email, session_id).",
        )
    result = service.ask(session_id=request.session_id, query=request.query)
    return {"answer": result.text, "from_cache": result.from_cache}


@app.post("/rate")
def api_rate(request: RateRequest) -> dict[str, str]:
    if not service.is_authorized(request.session_id):
        raise HTTPException(status_code=401, detail="Сессия не авторизована.")
    if request.rating < 1 or request.rating > 5:
        raise HTTPException(status_code=400, detail="rating должен быть от 1 до 5.")
    return {"message": service.set_rating(request.session_id, request.rating)}


@app.post("/comment")
def api_comment(request: CommentRequest) -> dict[str, str]:
    if not service.is_authorized(request.session_id):
        raise HTTPException(status_code=401, detail="Сессия не авторизована.")
    message = service.set_comment(request.session_id, request.comment)
    if message.startswith("Сначала установите оценку"):
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


@app.get("/dialog/{session_id}")
def api_dialog(session_id: str) -> dict[str, object]:
    if not service.is_authorized(session_id):
        raise HTTPException(status_code=401, detail="Сессия не авторизована.")
    return service.dialog_snapshot(session_id)
