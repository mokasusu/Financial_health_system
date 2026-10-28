"""Giao diện trừu tượng (Protocol) cho các nhà cung cấp mô hình AI / LLM Client.

Tuân thủ nguyên tắc Đảo ngược phụ thuộc (Dependency Inversion Principle - DIP):
Tầng Application chỉ tương tác qua giao diện IAIClient, không phụ thuộc trực tiếp
vào bất kỳ thư viện HTTP hay nhà cung cấp cụ thể nào (OpenRouter, OpenAI, Anthropic...).
"""
from typing import Any, Dict, List, Optional, Protocol


class IAIClient(Protocol):
    """Giao thức định nghĩa phương thức bắt buộc cho các AI Completion Client.

    Bất kỳ adapter AI nào trong tầng Infrastructure đều phải thỏa mãn giao thức này.
    """

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Gửi danh sách tin nhắn đối thoại đến API và trả về kết quả JSON đã phân tích cú pháp.

        Args:
            messages (List[Dict[str, str]]): Danh sách các lượt chat (role: system/user/assistant, content: text).
            model (Optional[str]): Tên định danh model (VD: 'openrouter/free', 'anthropic/claude-3.5-sonnet').
            max_tokens (Optional[int]): Giới hạn số token tối đa cho câu trả lời.
            temperature (Optional[float]): Mức độ ngẫu nhiên/sáng tạo (từ 0.0 đến 1.0).
            **kwargs (Any): Các tham số bổ sung khác cho API.

        Returns:
            Dict[str, Any]: Phản hồi từ mô hình AI dưới dạng Dictionary (thường chứa trường 'content' hoặc JSON bóc tách).

        Raises:
            Exception: Khi phát sinh lỗi mạng, lỗi xác thực API hoặc timeout không thể phục hồi.
        """
        ...
