"""
Provider-agnostic LLM config for LiteLLM.
Switch providers (Gemini, Groq, Azure OpenAI) via LLM_PROVIDER and LLM_MODEL.
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings


def _model_string(provider: str, model: str) -> str:
    if provider == "azure_openai":
        return f"azure_openai/{model}" if "/" not in model else model
    if "/" in model:
        return model
    return f"{provider}/{model}"


def get_llm_model_string() -> str:
    """LiteLLM model string (primary). Use extraction/auxiliary for model splitting."""
    provider = (settings.llm_provider or "gemini").strip().lower()
    model = (settings.llm_model or "gemini-2.5-flash").strip()
    return _model_string(provider, model)


def get_llm_model_string_extraction() -> str:
    """Model for extraction node only (reasoning-heavy; e.g. gemini-2.5-flash, 5 RPM)."""
    provider = (settings.llm_provider or "gemini").strip().lower()
    model = getattr(settings, "llm_model_extraction", None) or settings.llm_model or "gemini-2.5-flash"
    model = (model or "gemini-2.5-flash").strip()
    return _model_string(provider, model)


def get_llm_model_string_auxiliary() -> str:
    """Model for Judge/NeMo (evaluation & guardrails; e.g. gemini-2.5-flash-lite, 15 RPM)."""
    provider = (settings.llm_provider or "gemini").strip().lower()
    model = getattr(settings, "llm_model_auxiliary", None) or "gemini-2.5-flash-lite"
    model = (model or "gemini-2.5-flash-lite").strip()
    return _model_string(provider, model)


def get_llm_api_key() -> str:
    """API key for the current LLM provider."""
    provider = (settings.llm_provider or "gemini").strip().lower()
    if provider == "ollama":
        # Ollama doesn't require API keys.
        return ""
    if provider == "groq":
        return (settings.groq_api_key or "").strip()
    if provider == "gemini":
        return (settings.gemini_api_key or "").strip()
    if provider == "azure_openai":
        return (settings.azure_openai_api_key or "").strip()
    return ""


def get_llm_completion_kwargs() -> dict[str, Any]:
    """Extra kwargs for litellm.completion (api_key, base_url, etc.)."""
    provider = (settings.llm_provider or "gemini").strip().lower()
    kwargs: dict[str, Any] = {}
    api_key = get_llm_api_key()
    if api_key:
        kwargs["api_key"] = api_key
    if provider == "ollama":
        # OpenAI-compatible endpoint exposed by Ollama.
        base = getattr(settings, "ollama_base_url", None) or "http://localhost:11434"
        kwargs["api_base"] = base.rstrip("/")
    if provider == "groq":
        base = (settings.groq_base_url or "https://api.groq.com").rstrip("/")
        if not base.endswith("/openai/v1"):
            base = f"{base}/openai/v1"
        kwargs["api_base"] = base
    if provider == "azure_openai" and (settings.azure_openai_base_url or "").strip():
        kwargs["api_base"] = (settings.azure_openai_base_url or "").strip().rstrip("/")
    return kwargs


def get_llm_temperature() -> float:
    """Temperature for extraction."""
    return getattr(settings, "llm_temperature", 0.1)


def get_llm_eval_temperature() -> float:
    """Temperature for DeepEval metrics."""
    return getattr(settings, "llm_eval_temperature", 0.0)


def get_llm_base_url_for_litellm() -> str | None:
    """OpenAI-compatible base URL for LiteLLM (DeepEval), or None for Gemini."""
    provider = (settings.llm_provider or "gemini").strip().lower()
    if provider == "ollama":
        return (getattr(settings, "ollama_base_url", None) or "http://localhost:11434").rstrip("/")
    if provider == "groq":
        base = (settings.groq_base_url or "https://api.groq.com").rstrip("/")
        return base if base.endswith("/openai/v1") else f"{base}/openai/v1"
    if provider == "azure_openai" and (settings.azure_openai_base_url or "").strip():
        return (settings.azure_openai_base_url or "").strip().rstrip("/")
    return None
