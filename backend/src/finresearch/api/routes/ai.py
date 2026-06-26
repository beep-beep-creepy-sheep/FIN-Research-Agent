from __future__ import annotations

from fastapi import APIRouter

from finresearch.ai.ollama import OllamaProvider
from finresearch.settings import get_settings


router = APIRouter()


@router.get("/status")
def ai_status() -> dict[str, object]:
    settings = get_settings()
    if not settings.llm_enabled or settings.llm_provider != "ollama":
        return {"enabled": settings.llm_enabled, "provider": settings.llm_provider, "available": False}
    return {"enabled": True, "provider": "ollama", **OllamaProvider(settings).status()}


@router.post("/warmup")
def ai_warmup() -> dict[str, object]:
    settings = get_settings()
    if not settings.llm_enabled or settings.llm_provider != "ollama":
        return {"ok": False, "reason": "llm_disabled"}
    return OllamaProvider(settings).warmup()
