"""Máy khách API OpenRouter với cấu hình bảo mật và vận chuyển phòng thủ.

Module này chịu trách nhiệm tích hợp cổng kết nối HTTP với OpenRouter,
hỗ trợ lựa chọn mô hình linh hoạt trong thời gian chạy, xác thực Bearer token,
che giấu thông tin xác thực (credential redaction) trong nhật ký lỗi,
cơ chế thử lại giới hạn (bounded retries với exponential backoff) đối với lỗi tạm thời,
và phân loại ngoại lệ chi tiết theo chuẩn HTTP.
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
# HỆ THỐNG NGOẠI LỆ (EXCEPTION HIERARCHY)
# =============================================================================

class OpenRouterError(Exception):
    """Ngoại lệ cơ sở cho tất cả các lỗi phát sinh từ máy khách OpenRouter."""
    pass


class ConfigurationError(OpenRouterError):
    """Ngoại lệ phát sinh khi thiếu biến môi trường cấu hình bắt buộc (API key hoặc model)."""
    pass


class AuthenticationError(OpenRouterError):
    """Ngoại lệ phát sinh khi OpenRouter trả về mã HTTP 401 hoặc 403 (khóa API không hợp lệ)."""
    pass


class RateLimitError(OpenRouterError):
    """Ngoại lệ phát sinh khi OpenRouter trả về HTTP 429 (vượt quá hạn ngạch hoặc tần suất gọi)."""
    pass


class ServerError(OpenRouterError):
    """Ngoại lệ phát sinh khi OpenRouter trả về lỗi máy chủ nội bộ HTTP 5xx."""
    pass


class NetworkError(OpenRouterError):
    """Ngoại lệ phát sinh khi mất kết nối mạng hoặc yêu cầu bị quá thời gian chờ (timeout)."""
    pass


class ResponseValidationError(OpenRouterError):
    """Ngoại lệ phát sinh khi dữ liệu phản hồi từ OpenRouter bị rỗng hoặc sai cấu trúc JSON."""
    pass


# =============================================================================
# HÀM BẢO MẬT CHE GIẤU THÔNG TIN XÁC THỰC
# =============================================================================

def redact_secret(secret: Optional[str]) -> str:
    """Che giấu an toàn thông tin khóa bí mật (API key) để ghi log và hiển thị thông báo lỗi.

    Args:
        secret (Optional[str]): Chuỗi bí mật nguyên bản.

    Returns:
        str: Chuỗi đã che giấu chỉ hiển thị 4 ký tự đầu và 4 ký tự cuối (ví dụ: 'sk-o...1234')
            hoặc '[NOT SET]' / '[REDACTED]'.
    """
    if not secret:
        return "[NOT SET]"
    if len(secret) <= 8:
        return "[REDACTED]"
    return f"{secret[:4]}...{secret[-4:]}"


# =============================================================================
# ĐỐI TƯỢNG CẤU HÌNH
# =============================================================================

class OpenRouterConfig:
    """Đóng gói các thông số cấu hình kết nối OpenRouter đọc từ biến môi trường.

    Attributes:
        api_key (Optional[str]): Khóa xác thực API OpenRouter.
        base_url (str): Đường dẫn API cơ sở.
        model (Optional[str]): Mã định danh mô hình ngôn ngữ lớn (ví dụ: google/gemma-4-31b-it:free).
        timeout (int): Thời gian chờ tối đa cho mỗi yêu cầu HTTP (giây).
        max_retries (int): Số lần thử lại tối đa khi gặp lỗi tạm thời.
        site_url (str): Địa chỉ website ứng dụng gửi kèm header OpenRouter.
        app_name (str): Tên ứng dụng gửi kèm header OpenRouter.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        site_url: str = "https://financial-health-system.local",
        app_name: str = "Financial Health System",
    ) -> None:
        """Khởi tạo đối tượng cấu hình OpenRouter.

        Args:
            api_key (Optional[str]): Khóa xác thực API.
            base_url (Optional[str]): Địa chỉ URL gốc.
            model (Optional[str]): Tên mô hình LLM.
            timeout (int): Giới hạn thời gian kết nối.
            max_retries (int): Số lần thử lại tối đa.
            site_url (str): URL ứng dụng.
            app_name (str): Tên hiển thị của ứng dụng.
        """
        self.api_key: Optional[str] = api_key
        self.base_url: str = (base_url or DEFAULT_OPENROUTER_BASE_URL).rstrip("/")
        self.model: Optional[str] = model
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.site_url: str = site_url
        self.app_name: str = app_name

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "OpenRouterConfig":
        """Nạp cấu hình từ biến môi trường với cơ chế tương thích ngược (fallback).

        Hàm ưu tiên các biến `OPENROUTER_*`, sau đó chuyển sang các biến cũ `QWEN_*` nếu có.

        Args:
            env_path (Optional[str]): Đường dẫn tệp `.env` tùy chọn.

        Returns:
            OpenRouterConfig: Đối tượng cấu hình hợp lệ đã kiểm tra.

        Raises:
            ConfigurationError: Nếu API key hoặc mã định danh mô hình bị thiếu hoặc để trống.
        """
        # Nạp biến môi trường từ tệp .env nếu được chỉ định
        if env_path:
            load_dotenv(dotenv_path=env_path)

        # 1. Giải quyết API Key
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("QWEN_API_KEY")
        if not api_key or not api_key.strip():
            raise ConfigurationError(
                "Biến môi trường OPENROUTER_API_KEY (hoặc QWEN_API_KEY) chưa được thiết lập hoặc để trống. "
                "Vui lòng cấu hình API key trong file .env trước khi gọi AI interpretation."
            )
        api_key = api_key.strip()

        # 2. Giải quyết Base URL
        base_url = (
            os.getenv("OPENROUTER_BASE_URL")
            or os.getenv("QWEN_BASE_URL")
            or DEFAULT_OPENROUTER_BASE_URL
        ).strip()

        # 3. Giải quyết mã định danh Model
        model = os.getenv("OPENROUTER_MODEL") or os.getenv("QWEN_MODEL")
        if not model or not model.strip():
            raise ConfigurationError(
                "Biến môi trường OPENROUTER_MODEL (hoặc QWEN_MODEL) chưa được cấu hình. "
                "Vui lòng thiết lập mã định danh model (ví dụ: google/gemma-4-31b-it:free) trong file .env. "
                "Hệ thống không tự ý suy đoán hoặc gán model ngầm định."
            )
        model = model.strip()

        # 4. Giải quyết thời gian chờ Timeout
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
# MÁY KHÁCH VẬN CHUYỂN HTTP OPENROUTER
# =============================================================================

class OpenRouterClient:
    """Máy khách truyền thông HTTP giao tiếp với OpenRouter Chat Completions API.

    Attributes:
        config (OpenRouterConfig): Cấu hình kết nối và mô hình.
        session (requests.Session): Phiên HTTP có khả năng tái sử dụng kết nối mạng.
    """

    def __init__(
        self,
        config: Optional[OpenRouterConfig] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Khởi tạo máy khách OpenRouter.

        Args:
            config (Optional[OpenRouterConfig]): Đối tượng cấu hình. Nếu None sẽ nạp từ môi trường.
            session (Optional[requests.Session]): Phiên requests.Session tùy chọn (hữu ích cho mock test).
        """
        self.config: OpenRouterConfig = config or OpenRouterConfig.from_env()
        self.session: requests.Session = session or requests.Session()

    def _get_chat_endpoint(self) -> str:
        """Xây dựng URL đầy đủ của endpoint chat completions, tránh trùng lặp đường dẫn.

        Returns:
            str: URL hoàn chỉnh (ví dụ: 'https://openrouter.ai/api/v1/chat/completions').
        """
        base = self.config.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _get_headers(self) -> Dict[str, str]:
        """Tạo từ điển tiêu đề HTTP bắt buộc với xác thực Bearer token.

        Returns:
            Dict[str, str]: Tiêu đề HTTP chứa Authorization, Referer, X-Title.
        """
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
        """Gửi yêu cầu hoàn thành chat tới OpenRouter kèm cơ chế thử lại có kiểm soát.

        Args:
            messages (List[Dict[str, str]]): Danh sách các lượt tin nhắn [{"role": "system", ...}, ...].
            temperature (float): Độ biến thiên phản hồi (mặc định 0.2 cho phân tích tài chính ổn định).
            max_tokens (Optional[int]): Giới hạn token đầu ra.
            response_format (Optional[Dict[str, Any]]): Định dạng phản hồi tùy chọn e.g. {"type": "json_object"}.

        Returns:
            Dict[str, Any]: Từ điển chứa:
                - "content": str, nội dung văn bản phản hồi của trợ lý
                - "model": str, mô hình thực tế đã xử lý
                - "usage": dict, thống kê tiêu thụ token
                - "id": str, định danh phản hồi

        Raises:
            AuthenticationError: Khi gặp mã lỗi HTTP 401 hoặc 403.
            RateLimitError: Khi gặp mã lỗi HTTP 429 sau các lần thử lại.
            ServerError: Khi gặp mã lỗi HTTP 5xx từ máy chủ OpenRouter.
            NetworkError: Khi gặp lỗi mạng hoặc timeout.
            ResponseValidationError: Khi phản hồi trống hoặc không thể phân tích cú pháp.
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

        # Ghi log an toàn không để lộ thông tin xác thực nhạy cảm
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

                # 1. Phản hồi thành công HTTP 200
                if response.status_code == 200:
                    return self._parse_success_response(response)

                # 2. Lỗi xác thực khách (Không thử lại vì sai thông tin cấu hình)
                elif response.status_code in (401, 403):
                    err_msg = (
                        f"Xác thực OpenRouter thất bại (HTTP {response.status_code}). "
                        f"Vui lòng kiểm tra lại OPENROUTER_API_KEY trong file .env."
                    )
                    logger.error(err_msg)
                    raise AuthenticationError(err_msg)

                # 3. Lỗi hạn chế tần suất (Tạm thời - thử lại với giãn cách lũy thừa nếu còn lượt)
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

                # 4. Lỗi máy chủ nhà cung cấp (Tạm thời - thử lại với giãn cách lũy thừa nếu còn lượt)
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

                # 5. Các lỗi HTTP khác không xác định (400, 422, v.v.)
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

        # Nếu vòng lặp kết thúc mà không trả về kết quả
        if last_exception:
            raise last_exception
        raise OpenRouterError("Không thể hoàn thành yêu cầu OpenRouter sau các lần thử lại.")

    def _parse_success_response(self, response: requests.Response) -> Dict[str, Any]:
        """Kiểm tra tính hợp lệ và bóc tách dữ liệu từ phản hồi thành công HTTP 200.

        Args:
            response (requests.Response): Đối tượng phản hồi từ thư viện requests.

        Returns:
            Dict[str, Any]: Dữ liệu bóc tách gồm content, model, usage, id.

        Raises:
            ResponseValidationError: Nếu dữ liệu không phải JSON hợp lệ hoặc thiếu trường bắt buộc.
        """
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
