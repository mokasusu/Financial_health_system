"""Unit tests for OpenRouterClient transport and configuration (Sprint 5).

All tests use mocked HTTP requests and do NOT make real API calls or require credentials.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.infrastructure.ai.client import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    OpenRouterClient,
    OpenRouterConfig,
    OpenRouterError,
    RateLimitError,
    ResponseValidationError,
    ServerError,
    redact_secret,
)


class TestOpenRouterConfig:
    """Test environment variable loading and validation in OpenRouterConfig."""

    def test_load_config_from_openrouter_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-abc123def456")
        monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        monkeypatch.setenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
        monkeypatch.setenv("OPENROUTER_TIMEOUT", "45")

        config = OpenRouterConfig.from_env()
        assert config.api_key == "sk-or-v1-abc123def456"
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.model == "google/gemma-4-31b-it:free"
        assert config.timeout == 45

    def test_backward_compatibility_fallback_to_qwen_env(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

        monkeypatch.setenv("QWEN_API_KEY", "legacy-qwen-key-999")
        monkeypatch.setenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        monkeypatch.setenv("QWEN_MODEL", "qwen-plus")

        config = OpenRouterConfig.from_env()
        assert config.api_key == "legacy-qwen-key-999"
        assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert config.model == "qwen-plus"

    def test_missing_api_key_raises_configuration_error(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("QWEN_API_KEY", raising=False)
        monkeypatch.setenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")

        with pytest.raises(ConfigurationError) as exc_info:
            OpenRouterConfig.from_env()
        assert "OPENROUTER_API_KEY" in str(exc_info.value)

    def test_empty_api_key_raises_configuration_error(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "   ")
        monkeypatch.setenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")

        with pytest.raises(ConfigurationError):
            OpenRouterConfig.from_env()

    def test_missing_model_raises_configuration_error(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-valid-key")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
        monkeypatch.delenv("QWEN_MODEL", raising=False)

        with pytest.raises(ConfigurationError) as exc_info:
            OpenRouterConfig.from_env()
        assert "OPENROUTER_MODEL" in str(exc_info.value)
        assert "không tự ý suy đoán" in str(exc_info.value)


class TestOpenRouterClientTransport:
    """Test HTTP transport, header formulation, retries, and error handling in OpenRouterClient."""

    @pytest.fixture
    def mock_config(self):
        return OpenRouterConfig(
            api_key="sk-or-v1-secret-test-key-12345",
            base_url="https://openrouter.ai/api/v1",
            model="google/gemma-4-31b-it:free",
            timeout=30,
            max_retries=2,
        )

    def test_endpoint_construction_avoids_duplicate_segments(self, mock_config):
        client = OpenRouterClient(config=mock_config)
        assert client._get_chat_endpoint() == "https://openrouter.ai/api/v1/chat/completions"

        # Edge case: base_url already contains /chat/completions
        mock_config.base_url = "https://openrouter.ai/api/v1/chat/completions"
        client2 = OpenRouterClient(config=mock_config)
        assert client2._get_chat_endpoint() == "https://openrouter.ai/api/v1/chat/completions"

    def test_headers_and_authorization_format(self, mock_config):
        client = OpenRouterClient(config=mock_config)
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer sk-or-v1-secret-test-key-12345"
        assert headers["Content-Type"] == "application/json"
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    def test_successful_chat_completion(self, mock_config):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "gen-12345",
            "model": "google/gemma-4-31b-it:free",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '{"executive_summary": "Phân tích tài chính mẫu"}',
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_session.post.return_value = mock_response

        client = OpenRouterClient(config=mock_config, session=mock_session)
        result = client.create_chat_completion(
            messages=[{"role": "user", "content": "Phân tích BCTC"}],
            temperature=0.2,
        )

        assert result["content"] == '{"executive_summary": "Phân tích tài chính mẫu"}'
        assert result["model"] == "google/gemma-4-31b-it:free"
        assert result["usage"]["total_tokens"] == 150
        assert result["id"] == "gen-12345"

        # Verify post payload
        mock_session.post.assert_called_once()
        _, kwargs = mock_session.post.call_args
        assert kwargs["json"]["model"] == "google/gemma-4-31b-it:free"
        assert kwargs["json"]["temperature"] == 0.2
        assert kwargs["timeout"] == 30

    def test_http_401_authentication_failure_no_retry(self, mock_config):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized: Invalid API key"
        mock_session.post.return_value = mock_response

        client = OpenRouterClient(config=mock_config, session=mock_session)
        with pytest.raises(AuthenticationError) as exc_info:
            client.create_chat_completion(messages=[{"role": "user", "content": "Test"}])

        assert "Xác thực OpenRouter thất bại" in str(exc_info.value)
        # Verify 401 was NOT retried
        assert mock_session.post.call_count == 1

    def test_http_429_rate_limit_retries_and_raises(self, mock_config):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too many requests"
        mock_session.post.return_value = mock_response

        # max_retries = 2 -> 3 attempts total
        client = OpenRouterClient(config=mock_config, session=mock_session)
        with patch("time.sleep", return_value=None):
            with pytest.raises(RateLimitError) as exc_info:
                client.create_chat_completion(messages=[{"role": "user", "content": "Test"}])

        assert "Rate Limit" in str(exc_info.value)
        assert mock_session.post.call_count == 3

    def test_http_500_server_error_retries_and_raises(self, mock_config):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_session.post.return_value = mock_response

        client = OpenRouterClient(config=mock_config, session=mock_session)
        with patch("time.sleep", return_value=None):
            with pytest.raises(ServerError):
                client.create_chat_completion(messages=[{"role": "user", "content": "Test"}])

        assert mock_session.post.call_count == 3

    def test_network_timeout_retries_and_raises(self, mock_config):
        mock_session = MagicMock()
        mock_session.post.side_effect = requests.exceptions.Timeout("Connection timed out")

        client = OpenRouterClient(config=mock_config, session=mock_session)
        with patch("time.sleep", return_value=None):
            with pytest.raises(NetworkError) as exc_info:
                client.create_chat_completion(messages=[{"role": "user", "content": "Test"}])

        assert "Lỗi kết nối mạng hoặc timeout" in str(exc_info.value)
        assert mock_session.post.call_count == 3

    def test_empty_choices_raises_response_validation_error(self, mock_config):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123", "choices": []}
        mock_session.post.return_value = mock_response

        client = OpenRouterClient(config=mock_config, session=mock_session)
        with pytest.raises(ResponseValidationError) as exc_info:
            client.create_chat_completion(messages=[{"role": "user", "content": "Test"}])
        assert "không chứa trường 'choices'" in str(exc_info.value)

    def test_empty_content_raises_response_validation_error(self, mock_config):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "123",
            "choices": [{"message": {"role": "assistant", "content": "   "}}],
        }
        mock_session.post.return_value = mock_response

        client = OpenRouterClient(config=mock_config, session=mock_session)
        with pytest.raises(ResponseValidationError) as exc_info:
            client.create_chat_completion(messages=[{"role": "user", "content": "Test"}])
        assert "bị trống hoặc rỗng" in str(exc_info.value)


class TestCredentialRedaction:
    """Ensure sensitive credentials are never leaked in logs or representation."""

    def test_redact_secret_utility(self):
        assert redact_secret("sk-or-v1-1234567890abcdef") == "sk-o...cdef"
        assert redact_secret("short") == "[REDACTED]"
        assert redact_secret("") == "[NOT SET]"
        assert redact_secret(None) == "[NOT SET]"

    def test_error_messages_do_not_contain_raw_api_key(self, monkeypatch):
        secret_key = "super_secret_openrouter_api_key_do_not_leak"
        monkeypatch.setenv("OPENROUTER_API_KEY", secret_key)
        monkeypatch.setenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")

        config = OpenRouterConfig.from_env()
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_session.post.return_value = mock_response

        client = OpenRouterClient(config=config, session=mock_session)
        try:
            client.create_chat_completion(messages=[{"role": "user", "content": "Test"}])
        except AuthenticationError as e:
            # Secret key must NOT be present in exception string
            assert secret_key not in str(e)
