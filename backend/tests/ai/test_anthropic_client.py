"""
Direct tests for `app.ai.client.call_anthropic` (Checkpoint 9).

Every other AI test in this project mocks at the `ai_provider` callable
boundary (`investigate_anomaly(db, anomaly_id, ai_provider=...)`), which
never actually exercises `call_anthropic`'s own use of the `anthropic` SDK.
These tests patch `anthropic.Anthropic` itself to confirm the real
integration code — client construction, `messages.create` call shape,
response parsing, and every documented error path — is actually correct
against the installed SDK version, not just correct in the abstract.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.ai.client import AIClientError, AITimeoutError, AIUnavailableError, call_anthropic
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def test_missing_api_key_raises_ai_unavailable_without_touching_the_sdk(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch("anthropic.Anthropic") as mock_client_cls:
        with pytest.raises(AIUnavailableError):
            call_anthropic("system prompt", "user prompt")
        mock_client_cls.assert_not_called()


def test_successful_call_returns_the_text_content(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [_text_block('{"likely_cause": "plumbing_leak"}')]
        mock_client.messages.create.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = call_anthropic("system prompt", "user prompt")

    assert result == '{"likely_cause": "plumbing_leak"}'
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["system"] == "system prompt"
    assert kwargs["messages"] == [{"role": "user", "content": "user prompt"}]
    assert "model" in kwargs
    assert "max_tokens" in kwargs


def test_multiple_text_blocks_are_concatenated(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [_text_block("part one "), _text_block("part two")]
        mock_client.messages.create.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = call_anthropic("system prompt", "user prompt")

    assert result == "part one part two"


def test_non_text_content_blocks_are_ignored(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        non_text_block = MagicMock()
        non_text_block.type = "tool_use"
        mock_response = MagicMock()
        mock_response.content = [non_text_block, _text_block("the real answer")]
        mock_client.messages.create.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = call_anthropic("system prompt", "user prompt")

    assert result == "the real answer"


def test_response_with_no_text_content_raises_ai_client_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []
        mock_client.messages.create.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(AIClientError, match="no text content"):
            call_anthropic("system prompt", "user prompt")


def test_sdk_timeout_error_raises_ai_timeout_error(monkeypatch):
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(request=mock_request)
        mock_client_cls.return_value = mock_client

        with pytest.raises(AITimeoutError):
            call_anthropic("system prompt", "user prompt")


def test_sdk_api_error_raises_ai_client_error(monkeypatch):
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=mock_request)
        mock_client_cls.return_value = mock_client

        with pytest.raises(AIClientError):
            call_anthropic("system prompt", "user prompt")


def test_unexpected_exception_from_the_sdk_still_raises_ai_client_error_not_a_raw_crash(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("something unexpected")
        mock_client_cls.return_value = mock_client

        with pytest.raises(AIClientError):
            call_anthropic("system prompt", "user prompt")


def test_api_key_is_never_included_in_any_raised_error_message(monkeypatch):
    import anthropic

    secret_key = "sk-ant-super-secret-value-do-not-leak"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret_key)
    with patch("anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=mock_request)
        mock_client_cls.return_value = mock_client

        try:
            call_anthropic("system prompt", "user prompt")
        except AIClientError as exc:
            assert secret_key not in str(exc)
