"""Compatibility shim: the NVIDIA-only client became the provider-agnostic LLMService."""

from src.services.llm.llm_service import (  # noqa: F401
    LLMError,
    LLMService,
    LLMUsage,
    Message,
    extract_json,
    get_llm_service,
    get_role_llm,
    set_llm_service,
)

NvidiaLLMService = LLMService
