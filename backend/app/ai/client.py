"""
Anthropic API client wrapper (docs Milestone 4, requirement #10/#11).

Isolated in its own module so `investigation_service.py` depends on a
simple `Callable[[str, str], str]` interface (system prompt, user prompt ->
raw response text) rather than the Anthropic SDK directly — this is what
lets tests inject a mock provider with no network access and no real API
key (docs Milestone 4, requirement #21).

The API key is read from server-side configuration only (`app.core.config`)
and is never passed to or exposed by any client-facing response.
"""
from __future__ import annotations

from app.core.config import get_settings


class AIClientError(Exception):
    """Base class for any failure calling the AI provider."""


class AITimeoutError(AIClientError):
    pass


class AIUnavailableError(AIClientError):
    """Raised when no API key is configured — the caller should go straight to fallback."""


# How long we wait for a single investigation call before giving up and
# falling back — an investigation is a single, focused reasoning call, not
# a long-running task, so this stays short.
REQUEST_TIMEOUT_SECONDS = 20
MAX_TOKENS = 800


def call_anthropic(system_prompt: str, user_prompt: str) -> str:
    """
    Call the Anthropic API and return the raw text response.

    Raises `AIUnavailableError` if no API key is configured, `AITimeoutError`
    on a timeout, or `AIClientError` for any other failure (network error,
    rate limit, malformed SDK response, etc). Callers should catch
    `AIClientError` (the common base) and fall back to the deterministic
    engine rather than letting any of these propagate to the user.
    """
    settings = get_settings()
    if not settings.ai_enabled:
        raise AIUnavailableError("ANTHROPIC_API_KEY is not configured.")

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        raise AIClientError(f"anthropic SDK not installed: {exc}") from exc

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=REQUEST_TIMEOUT_SECONDS)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APITimeoutError as exc:
        raise AITimeoutError(str(exc)) from exc
    except anthropic.APIError as exc:
        raise AIClientError(str(exc)) from exc
    except Exception as exc:  # network errors, unexpected SDK issues, etc.
        raise AIClientError(str(exc)) from exc

    text_blocks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    if not text_blocks:
        raise AIClientError("AI response contained no text content.")
    return "".join(text_blocks)
