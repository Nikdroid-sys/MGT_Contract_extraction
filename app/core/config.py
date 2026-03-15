"""
Application configuration via environment variables.
Works locally (.env file) and on Render (environment variables only).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_file() -> str | None:
    """Path to .env in project root; None if not present (e.g. on Render)."""
    p = Path(__file__).resolve().parent.parent.parent / ".env"
    return str(p) if p.is_file() else None


class Settings(BaseSettings):
    """Load from .env when present (local), else from process env (Render)."""

    model_config = SettingsConfigDict(
        env_file=_env_file(),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    # JWT Auth
    jwt_secret: str = Field(
        default="change-me-in-production-use-env",
        description="Secret for signing JWTs. Set JWT_SECRET on Render.",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm.")
    jwt_expire_minutes: int = Field(default=60, ge=1, le=10080, description="Token expiry in minutes.")

    # Demo user (local / single-user auth). On Render set via env.
    auth_demo_username: str = Field(default="admin", description="Demo login username.")
    auth_demo_password: str = Field(
        default="admin",
        description="Demo login password. Override AUTH_DEMO_PASSWORD on Render.",
    )

    # Optional: API title / env name for health
    app_env: str = Field(default="local", description="Environment name (local, render, staging).")

    # Contract workflow – provider-agnostic LLM (LiteLLM: groq, gemini, azure_openai)
    llm_provider: str = Field(
        default="gemini",
        description="LLM provider: gemini, groq, or azure_openai. Set LLM_PROVIDER.",
    )
    llm_model: str = Field(
        default="gemini-2.5-flash",
        description="Primary extraction model. Set LLM_MODEL.",
    )
    # Model splitting (Free Tier): extraction = 2.5-flash (5 RPM); auxiliary = 1.5-flash-lite (15 RPM)
    llm_model_extraction: str = Field(
        default="gemini-2.5-flash",
        description="Model for extraction node only. Set LLM_MODEL_EXTRACTION.",
    )
    llm_model_auxiliary: str = Field(
        default="gemini-2.5-flash-lite",
        description="Model for Judge/NeMo (evaluation & guardrails; 15 RPM). Set LLM_MODEL_AUXILIARY.",
    )
    groq_api_key: str = Field(default="", description="Groq API key. Set GROQ_API_KEY when LLM_PROVIDER=groq.")
    groq_base_url: str = Field(
        default="https://api.groq.com",
        description="Groq API base (no /openai/v1). Set GROQ_BASE_URL for proxy.",
    )
    gemini_api_key: str = Field(default="", description="Google/Gemini API key. Set GEMINI_API_KEY when LLM_PROVIDER=gemini.")
    azure_openai_api_key: str = Field(default="", description="Azure OpenAI API key. Set AZURE_OPENAI_API_KEY when LLM_PROVIDER=azure_openai.")
    azure_openai_base_url: str = Field(default="", description="Azure OpenAI endpoint URL. Set AZURE_OPENAI_BASE_URL.")
    llm_temperature: float = Field(default=0.1, ge=0, le=2, description="LLM temperature for extraction. Set LLM_TEMPERATURE.")
    llm_eval_temperature: float = Field(default=0.0, ge=0, le=2, description="LLM temperature for DeepEval. Set LLM_EVAL_TEMPERATURE.")
    gsheets_webapp_url: str = Field(default="", description="Google Apps Script Web App URL for logging runs.")
    max_extraction_retries: int = Field(default=2, ge=1, le=5, description="Self-healing retry limit. Set MAX_EXTRACTION_RETRIES.")
    confidence_threshold: float = Field(default=0.8, ge=0, le=1, description="Min score to accept extraction. Set CONFIDENCE_THRESHOLD.")
    audit_timeout_seconds: float = Field(default=15.0, ge=5, le=120, description="Max seconds for DeepEval audit. Set AUDIT_TIMEOUT_SECONDS.")
    # Jittered delay before auditor (seconds) to stay within 15 RPM; ~12s average; 0 to disable
    auditor_delay_min_seconds: float = Field(default=10.0, ge=0, le=60, description="Min delay before audit. Set AUDITOR_DELAY_MIN_SECONDS (0=off).")
    auditor_delay_max_seconds: float = Field(default=14.0, ge=0, le=60, description="Max delay before audit. Set AUDITOR_DELAY_MAX_SECONDS.")
    # Single Judge eval (one LLM call for Faithfulness + Relevancy + Schema); no separate DeepEval metrics
    use_judge_eval: bool = Field(default=True, description="Use single Judge call for audit. Set USE_JUDGE_EVAL.")
    # NeMo: output rails disabled by default (input-only) to save one LLM call
    nemo_output_rails_enabled: bool = Field(default=False, description="Enable NeMo output rails. Set NEMO_OUTPUT_RAILS_ENABLED.")
    # Token reduction: cap input lengths (chars) to control cost without losing schema/accuracy
    max_contract_chars: int = Field(default=12_000, ge=2_000, le=100_000, description="Max contract text length for extractor. Set MAX_CONTRACT_CHARS.")
    max_audit_chars: int = Field(default=4_000, ge=1_000, le=20_000, description="Max input/context length for DeepEval. Set MAX_AUDIT_CHARS.")
    max_nemo_chars: int = Field(default=6_000, ge=1_000, le=30_000, description="Max input length for NeMo guardrails. Set MAX_NEMO_CHARS.")


settings = Settings()
