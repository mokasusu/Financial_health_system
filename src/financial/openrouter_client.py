"""OpenRouter API client with secure configuration and defensive transport (Sprint 5).

Implements OpenRouter HTTP gateway integration, runtime model selection,
Bearer authentication, credential redaction, bounded transient retries,
and specific error classifications.
"""
import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from dotenv import load_dotenv
import requests

logger = logging.getLogger(__name__)

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_FACTOR = 0.5


# =============================================================================
# EXCEPTION HIERARCHY
# =============================================================================

class OpenRouterError(Exception):
    """Base exception for all OpenRouter client errors."""
    pass


class ConfigurationError(OpenRouterError):
    """Raised when required environment configuration (API key or model) is missing."""
    pass


class AuthenticationError(OpenRouterError):
    """Raised when OpenRouter returns HTTP 401 or 403 (invalid or unauthorized API key)."""
    pass


class RateLimitError(OpenRouterError):
    """Raised when OpenRouter returns HTTP 429 (rate limit or quota exceeded)."""
    pass


class ServerError(OpenRouterError):
    """Raised when OpenRouter returns HTTP 5xx server errors."""
    pass


class NetworkError(OpenRouterError):
    """Raised when network connectivity fails or request times out."""
    pass


class ResponseValidationError(OpenRouterError):
    """Raised when OpenRouter response format is empty, invalid, or malformed."""
    pass


# =============================================================================
# CREDENTIAL REDACTION HELPER
# =============================================================================

def redact_secret(secret: Optional[str]) -> str:
    """Safely redact secret credentials for logging and exception messages.

    Args:
        secret: Raw secret string.

    Returns:
        Redacted string with only prefix and suffix visible, or '[REDACTED]'.
    """
    if not secret:
        return "[NOT SET]"
    if len(secret) <= 8:
        return "[REDACTED]"
    return f"{secret[:4]}...{secret[-4:]}"


# =============================================================================
# CONFIGURATION OBJECT
# =============================================================================

class OpenRouterConfig:
    """Encapsulates OpenRouter client configuration loaded from environment variables."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        site_url: str = "https://financial-health-system.local",
        app_name: str = "Financial Health System",
    ):
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_OPENROUTER_BASE_URL).rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.site_url = site_url
        self.app_name = app_name

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "OpenRouterConfig":
        """Load configuration from environment variables with backward compatibility.

        Prioritizes OPENROUTER_* variables, falling back to legacy QWEN_* variables.
        Raises ConfigurationError if API key or model is missing or empty.
        """
        # Load environment variables from .env file if explicitly specified
        if env_path:
            load_dotenv(dotenv_path=env_path)

        # 1. API Key resolution
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("QWEN_API_KEY")
        if not api_key or not api_key.strip():
            raise ConfigurationError(
                "Biến môi trường OPENROUTER_API_KEY (hoặc QWEN_API_KEY) chưa được thiết lập hoặc để trống. "
                "Vui lòng cấu hình API key trong file .env trước khi gọi AI interpretation."
            )
        api_key = api_key.strip()

        # 2. Base URL resolution
        base_url = (
            os.getenv("OPENROUTER_BASE_URL")
            or os.getenv("QWEN_BASE_URL")
            or DEFAULT_OPENROUTER_BASE_URL
        ).strip()

        # 3. Model identifier resolution
        model = os.getenv("OPENROUTER_MODEL") or os.getenv("QWEN_MODEL")
        if not model or not model.strip():
            raise ConfigurationError(
                "Biến môi trường OPENROUTER_MODEL (hoặc QWEN_MODEL) chưa được cấu hình. "
                "Vui lòng thiết lập mã định danh model (ví dụ: google/gemma-4-31b-it:free) trong file .env. "
                "Hệ thống không tự ý suy đoán hoặc gán model ngầm định."
            )
        model = model.strip()

        # 4. Timeout resolution
        timeout_str = os.getenv("OPENROUTER_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
        try:
            timeout = int(timeout_str)
        except ValueError:
            timeout = DEFAULT_TIMEOUT_SECONDS

        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
        )


# =============================================================================
# OPENROUTER TRANSPORT CLIENT
# =============================================================================

class OpenRouterClient:
    """HTTP Transport client for communicating with OpenRouter Chat Completions API."""

    def __init__(
        self,
        config: Optional[OpenRouterConfig] = None,
        session: Optional[requests.Session] = None,
    ):
        """Initialize OpenRouter client.

        Args:
            config: OpenRouterConfig object. If None, loaded via OpenRouterConfig.from_env().
            session: Optional requests.Session instance (useful for unit test mocking).
        """
        self.config = config or OpenRouterConfig.from_env()
        self.session = session or requests.Session()

    def _get_chat_endpoint(self) -> str:
        """Construct the full chat completions URL avoiding duplicate path segments."""
        base = self.config.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _get_headers(self) -> Dict[str, str]:
        """Construct required HTTP headers with Bearer token authentication."""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.config.site_url,
            "X-Title": self.config.app_name,
        }
        return headers

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = 2000,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute chat completion request to OpenRouter with bounded retries for transient errors.

        Args:
            messages: List of message dicts: [{"role": "system", ...}, {"role": "user", ...}]
            temperature: Sampling temperature (default: 0.2 for analytical consistency).
            max_tokens: Maximum tokens in response.
            response_format: Optional format dict e.g. {"type": "json_object"}.

        Returns:
            Dict containing:
                - "content": str, the assistant's message content
                - "model": str, the model used by the provider
                - "usage": dict, token usage stats
                - "id": str, response id

        Raises:
            AuthenticationError: HTTP 401/403.
            RateLimitError: HTTP 429.
            ServerError: HTTP 5xx.
            NetworkError: Connection errors or timeouts.
            ResponseValidationError: Empty or malformed responses.
        """
        endpoint = self._get_chat_endpoint()
        headers = self._get_headers()

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format

        # Safe logging without credentials
        logger.info(
            "Sending OpenRouter chat completion to %s using model: %s (API key: %s)",
            endpoint,
            self.config.model,
            redact_secret(self.config.api_key),
        )

        last_exception: Optional[Exception] = None
        max_attempts = 1 + self.config.max_retries

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.config.timeout,
                )

                # 1. Success response
                if response.status_code == 200:
                    return self._parse_success_response(response)

                # 2. Client Authentication Errors (Do NOT retry)
                elif response.status_code in (401, 403):
                    err_msg = (
                        f"Xác thực OpenRouter thất bại (HTTP {response.status_code}). "
                        f"Vui lòng kiểm tra lại OPENROUTER_API_KEY trong file .env."
                    )
                    logger.error(err_msg)
                    raise AuthenticationError(err_msg)

                # 3. Rate Limit Errors (Transient - retry with backoff if attempts remain)
                elif response.status_code == 429:
                    err_msg = (
                        f"OpenRouter Rate Limit (HTTP 429) đối với model '{self.config.model}'. "
                        f"Chi tiết: {response.text[:200]}"
                    )
                    logger.warning(
                        "Attempt %d/%d: %s. Đang chờ thử lại...", attempt, max_attempts, err_msg
                    )
                    if attempt < max_attempts:
                        time.sleep(DEFAULT_BACKOFF_FACTOR * (2 ** (attempt - 1)))
                        continue
                    raise RateLimitError(err_msg)

                # 4. Server Errors (Transient - retry with backoff if attempts remain)
                elif 500 <= response.status_code < 600:
                    err_msg = (
                        f"OpenRouter Server Error (HTTP {response.status_code}). "
                        f"Chi tiết: {response.text[:200]}"
                    )
                    logger.warning(
                        "Attempt %d/%d: %s. Đang chờ thử lại...", attempt, max_attempts, err_msg
                    )
                    if attempt < max_attempts:
                        time.sleep(DEFAULT_BACKOFF_FACTOR * (2 ** (attempt - 1)))
                        continue
                    raise ServerError(err_msg)

                # 5. Other unhandled HTTP errors (400, 422, etc.)
                else:
                    err_msg = (
                        f"Yêu cầu OpenRouter không hợp lệ (HTTP {response.status_code}): {response.text[:300]}"
                    )
                    logger.error(err_msg)
                    raise ResponseValidationError(err_msg)

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
                err_msg = f"Lỗi kết nối mạng hoặc timeout khi gọi OpenRouter ({endpoint}): {net_err}"
                logger.warning(
                    "Attempt %d/%d: %s", attempt, max_attempts, err_msg
                )
                last_exception = NetworkError(err_msg)
                if attempt < max_attempts:
                    time.sleep(DEFAULT_BACKOFF_FACTOR * (2 ** (attempt - 1)))
                    continue
                raise last_exception

        # If loop exits without returning or raising
        if last_exception:
            raise last_exception
        raise OpenRouterError("Không thể hoàn thành yêu cầu OpenRouter sau các lần thử lại.")

    def _parse_success_response(self, response: requests.Response) -> Dict[str, Any]:
        """Validate and parse successful OpenRouter HTTP 200 response."""
        try:
            data = response.json()
        except Exception as json_err:
            raise ResponseValidationError(f"Phản hồi từ OpenRouter không phải JSON hợp lệ: {json_err}")

        if not isinstance(data, dict):
            raise ResponseValidationError("Phản hồi từ OpenRouter không có cấu trúc dict hợp lệ.")

        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            raise ResponseValidationError("Phản hồi từ OpenRouter không chứa trường 'choices' hoặc choices rỗng.")

        first_choice = choices[0]
        message = first_choice.get("message", {})
        content = message.get("content")

        if content is None or not str(content).strip():
            raise ResponseValidationError("Nội dung phản hồi ('content') từ OpenRouter bị trống hoặc rỗng.")

        return {
            "content": str(content).strip(),
            "model": data.get("model", self.config.model),
            "usage": data.get("usage", {}),
            "id": data.get("id", ""),
        }
