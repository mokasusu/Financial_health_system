"""Gói tích hợp hạ tầng AI (Infrastructure AI Client).

Cung cấp máy khách HTTP OpenRouterClient, cấu hình OpenRouterConfig,
và hệ thống phân loại ngoại lệ mạng/xác thực chi tiết.
"""
from src.infrastructure.ai.client import (
    AuthenticationError,
    ConfigurationError,
    DEFAULT_OPENROUTER_BASE_URL,
    NetworkError,
    OpenRouterClient,
    OpenRouterError,
    RateLimitError,
    ResponseValidationError,
    ServerError,
)

__all__ = [
    "AuthenticationError",
    "ConfigurationError",
    "DEFAULT_OPENROUTER_BASE_URL",
    "NetworkError",
    "OpenRouterClient",
    "OpenRouterError",
    "RateLimitError",
    "ResponseValidationError",
    "ServerError",
]
