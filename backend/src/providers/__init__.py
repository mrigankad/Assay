"""Assay provider layer: catalogue, auto-detection and routing for every model provider."""

from .catalog import PROVIDERS, BY_ID, ProviderSpec
from .detection import detect, Detected
from .router import LLMRouter, get_llm, embed, rerank, resolve, detected, ROLES

__all__ = ["PROVIDERS", "BY_ID", "ProviderSpec", "detect", "Detected", "LLMRouter", "get_llm",
           "embed", "rerank", "resolve", "detected", "ROLES"]
