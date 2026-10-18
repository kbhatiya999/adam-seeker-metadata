"""Seeker SDK gemini: runs seeker-sdk-llm tools on Google's Gemini (provider `gemini`)."""

from .provider import API_KEY_ENV, DEFAULT_MODEL, MODEL_ENV, RPM_ENV, GeminiProvider, classify

__all__ = ["API_KEY_ENV", "DEFAULT_MODEL", "MODEL_ENV", "RPM_ENV", "GeminiProvider", "classify"]
__version__ = "0.1.0"
