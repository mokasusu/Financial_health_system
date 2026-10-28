"""Đường ống tiền xử lý hình ảnh tài liệu quét bằng OpenCV.

Module này cung cấp lớp ImagePreprocessor nhằm nâng cao chất lượng ảnh đầu vào cho OCR:
- Tự động xoay cân chỉnh độ nghiêng văn bản (Deskewing qua minAreaRect).
- Nâng cao độ tương phản chữ và dấu thanh Tiếng Việt (CLAHE LAB kết hợp Unsharp Masking).
- Khử nhiễu quang học (Non-local Means Denoising).
- Nhị phân hóa thích nghi theo khối cục bộ (Adaptive Gaussian Thresholding).
"""
import logging
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Đường ống tiền xử lý hình ảnh dựa trên OpenCV dành cho tài liệu BCTC dạng scan.

    Attributes:
        enable_denoise (bool): Bật/tắt khử nhiễu ảnh.
        enable_deskew (bool): Bật/tắt tự động xoay góc nghiêng.
        enable_binarize (bool): Bật/tắt nhị phân hóa ảnh.
        enable_enhance (bool): Bật/tắt nâng cao độ sắc nét và tương phản chữ Tiếng Việt.
        denoise_strength (int): Cường độ khử nhiễu (h).
        binarize_block_size (int): Kích thước khối lân cận nhị phân hóa (phải là số lẻ).
        binarize_c (int): Hằng số trừ ngưỡng nhị phân hóa.
        max_skew_angle (float): Góc nghiêng tối đa được phép xoay (độ).
        min_skew_angle (float): Góc nghiêng tối thiểu để bắt đầu xoay (độ).
        return_bgr (bool): Trả về ảnh định dạng BGR 3 kênh.
    """

    def __init__(
        self,
        enable_denoise: bool = True,
        enable_deskew: bool = True,
        enable_binarize: bool = True,
        enable_enhance: bool = True,
        denoise_strength: int = 10,
        binarize_block_size: int = 31,
        binarize_c: int = 10,
        max_skew_angle: float = 45.0,
        min_skew_angle: float = 0.5,
        return_bgr: bool = True,
    ) -> None:
        """Khởi tạo bộ tiền xử lý hình ảnh tài liệu.

        Args:
            enable_denoise (bool): Cho phép khử nhiễu quang học.
            enable_deskew (bool): Cho phép căn chỉnh xoay thẳng trang.
            enable_binarize (bool): Cho phép chuyển đổi đen trắng nhị phân.
            enable_enhance (bool): Cho phép tăng cường tương phản CLAHE.
            denoise_strength (int): Cường độ lọc nhiễu fastNlMeans.
            binarize_block_size (int): Kích thước cửa sổ tính ngưỡng thích nghi.
            binarize_c (int): Hệ số bù trừ ngưỡng.
            max_skew_angle (float): Giới hạn góc nghiêng tối đa (tránh xoay lật 90 độ sai hướng).
            min_skew_angle (float): Ngưỡng góc nghiêng tối thiểu kích hoạt xoay.
            return_bgr (bool): Quy định định dạng ảnh đầu ra là BGR 3 kênh.
        """
        self.enable_denoise: bool = enable_denoise
        self.enable_deskew: bool = enable_deskew
        self.enable_binarize: bool = enable_binarize
        self.enable_enhance: bool = enable_enhance
        self.denoise_strength: int = denoise_strength
        # Đảm bảo block_size luôn là số lẻ theo yêu cầu của OpenCV
        self.binarize_block_size: int = (
            binarize_block_size if binarize_block_size % 2 == 1 else binarize_block_size + 1
        )
        self.binarize_c: int = binarize_c
        self.max_skew_angle: float = max_skew_angle
        self.min_skew_angle: float = min_skew_angle
        self.return_bgr: bool = return_bgr

    def to_numpy(self, image: Union[np.ndarray, Image.Image, Path, str]) -> np.ndarray:
        """Chuyển đổi PIL Image, đường dẫn tệp hoặc mảng numpy thành mảng numpy BGR chuẩn mực.

        Args:
            image (Union[np.ndarray, Image.Image, Path, str]): Ảnh đầu vào ở các định dạng khác nhau.

        Returns:
            np.ndarray: Mảng ảnh numpy định dạng BGR.

        Raises:
            ValueError: Khi không thể đọc tệp ảnh từ đường dẫn.
            TypeError: Khi kiểu dữ liệu đầu vào không được hỗ trợ.
        """
        if isinstance(image, (str, Path)):
            path_str = str(image)
            img = cv2.imread(path_str)
            if img is None:
                raise ValueError(f"Could not read image file: {path_str}")
            return img
        elif isinstance(image, Image.Image):
            rgb = np.array(image.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        elif isinstance(image, np.ndarray):
            return image.copy()
        else:
            raise TypeError(
                f"Unsupported image type: {type(image)}. Expected np.ndarray, PIL.Image, or file path."
            )

    def denoise(self, gray: np.ndarray) -> np.ndarray:
        """Áp dụng thuật toán khử nhiễu quang học Non-local Means cho ảnh xám.

        Args:
            gray (np.ndarray): Mảng ảnh xám đơn kênh (grayscale).

        Returns:
            np.ndarray: Ảnh xám đã được khử nhiễu mịn hạt.
        """
        try:
            return cv2.fastNlMeansDenoising(
                gray,
                h=self.denoise_strength,
                templateWindowSize=7,
                searchWindowSize=21,
            )
        except Exception as e:
            logger.warning(f"Denoising failed, fallback to GaussianBlur: {e}")
            return cv2.GaussianBlur(gray, (3, 3), 0)

    def detect_skew_angle(self, gray: np.ndarray) -> float:
        """Tính toán góc nghiêng của tài liệu quét theo độ (degrees) bằng hình chữ nhật bao quanh tối thiểu.

        Args:
            gray (np.ndarray): Ảnh xám đầu vào.

        Returns:
            float: Góc nghiêng tính bằng độ (ví dụ: -2.5, 1.2, hoặc 0.0 nếu thẳng).
        """
        try:
            # Nhị phân hóa Otsu và đảo ngược màu để chữ mang giá trị pixel 255 (trắng)
            thresh = cv2.bitwise_not(cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1])
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) < 100:
                return 0.0

            # Tính hình chữ nhật bao quanh nhỏ nhất của tập tọa độ điểm chữ
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            return float(angle)
        except Exception as e:
            logger.debug(f"Skew detection encountered error: {e}")
            return 0.0

    def deskew(self, image: np.ndarray, angle: Optional[float] = None) -> np.ndarray:
        """Xoay ma trận ảnh để bù góc nghiêng về hướng ngang chuẩn xác.

        Args:
            image (np.ndarray): Mảng ảnh cần xoay.
            angle (Optional[float]): Góc nghiêng đã biết; nếu None sẽ tự động phát hiện.

        Returns:
            np.ndarray: Ảnh đã được xoay thẳng với viền nền trắng.
        """
        if angle is None:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            angle = self.detect_skew_angle(gray)

        # Bỏ qua nếu góc nghiêng quá nhỏ hoặc quá lớn vượt ngưỡng an toàn
        if abs(angle) < self.min_skew_angle or abs(angle) > self.max_skew_angle:
            return image

        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)

        # Viền bổ sung màu trắng khi xoay
        border_val = (255, 255, 255) if len(image.shape) == 3 else 255
        rotated = cv2.warpAffine(
            image,
            rot_mat,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_val,
        )
        return rotated

    def binarize(self, gray: np.ndarray) -> np.ndarray:
        """Áp dụng phân ngưỡng thích nghi (Adaptive Gaussian Thresholding) tạo nền trắng chữ đen rõ nét.

        Args:
            gray (np.ndarray): Mảng ảnh xám.

        Returns:
            np.ndarray: Ảnh nhị phân độ tương phản cao.
        """
        try:
            block_size = max(3, self.binarize_block_size)
            if block_size % 2 == 0:
                block_size += 1
            return cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                block_size,
                self.binarize_c,
            )
        except Exception as e:
            logger.warning(f"Adaptive thresholding failed, fallback to Otsu: {e}")
            _, binarized = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            return binarized

    def enhance_document_text(self, image: Union[np.ndarray, Image.Image]) -> np.ndarray:
        """Tăng cường độ tương phản (CLAHE) và làm sắc nét các nét dấu thanh Tiếng Việt tinh tế.

        Args:
            image (Union[np.ndarray, Image.Image]): Ảnh đầu vào.

        Returns:
            np.ndarray: Ảnh sắc nét và nổi bật ký tự văn bản.
        """
        try:
            img = self.to_numpy(image)
            if img.size == 0 or img.shape[0] < 5 or img.shape[1] < 5:
                return img

            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            # Chuyển sang không gian màu LAB để áp dụng CLAHE trên kênh độ sáng L (Luminance)
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

            # Làm nét ảnh bằng mặt nạ không sắc nét (Unsharp Masking)
            blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=2.0)
            sharpened = cv2.addWeighted(enhanced, 1.3, blurred, -0.3, 0)
            return sharpened
        except Exception as e:
            logger.warning(f"enhance_document_text failed: {e}, falling back to original")
            return self.to_numpy(image)

    def preprocess(self, image: Union[np.ndarray, Image.Image]) -> np.ndarray:
        """Thực thi toàn bộ chuỗi các bước tiền xử lý ảnh theo cấu hình đã thiết lập.

        Thứ tự xử lý:
        1. Chuẩn hóa sang mảng numpy BGR.
        2. Tự động xoay thẳng (Deskewing).
        3. Tăng cường tương phản và độ sắc nét ký tự (Enhance CLAHE).
        4. Khử nhiễu quang học (Denoising).
        5. Nhị phân hóa (Binarization nếu được kích hoạt).

        Args:
            image (Union[np.ndarray, Image.Image]): Ảnh nguồn.

        Returns:
            np.ndarray: Ảnh đã tiền xử lý tối ưu sẵn sàng cho nhận diện OCR.
        """
        try:
            img = self.to_numpy(image)

            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()

            # Bước 1: Xoay thẳng góc nghiêng
            if self.enable_deskew:
                angle = self.detect_skew_angle(gray)
                if abs(angle) >= self.min_skew_angle and abs(angle) <= self.max_skew_angle:
                    gray = self.deskew(gray, angle=angle)
                    if len(img.shape) == 3:
                        img = self.deskew(img, angle=angle)

            # Bước 2: Tăng cường độ tương phản
            if self.enable_enhance:
                img = self.enhance_document_text(img)
                if len(img.shape) == 3:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                else:
                    gray = img.copy()

            # Bước 3: Khử nhiễu
            if self.enable_denoise:
                gray = self.denoise(gray)

            # Bước 4: Nhị phân hóa
            if self.enable_binarize:
                processed = self.binarize(gray)
            else:
                processed = gray if not self.return_bgr else img

            if self.return_bgr and (len(processed.shape) == 2 or processed.shape[2] == 1):
                return cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)

            return processed

        except Exception as e:
            logger.error(f"Image preprocessing failed completely: {e}. Returning raw input.")
            return self.to_numpy(image)
