"""Image preprocessing pipeline using OpenCV for scanned documents.

Provides denoising, deskewing, and adaptive binarization to improve
OCR accuracy on low-quality scanned financial statements.
"""
import logging
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """OpenCV-based image preprocessing pipeline for scanned financial documents."""

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
    ):
        """Initialize image preprocessor.

        Args:
            enable_denoise: Apply non-local means denoising or median blur.
            enable_deskew: Automatically detect and correct skew angle.
            enable_binarize: Apply adaptive Gaussian thresholding.
            enable_enhance: Enhance text contrast (CLAHE) and sharpen fine Vietnamese diacritic marks.
            denoise_strength: Filter strength parameter h for fastNlMeans.
            binarize_block_size: Size of a pixel neighborhood for thresholding (must be odd).
            binarize_c: Constant subtracted from the mean or weighted mean.
            max_skew_angle: Maximum skew angle in degrees to correct.
            min_skew_angle: Minimum skew angle in degrees required to trigger correction.
            return_bgr: Whether to convert final single-channel result back to 3-channel BGR.
        """
        self.enable_denoise = enable_denoise
        self.enable_deskew = enable_deskew
        self.enable_binarize = enable_binarize
        self.enable_enhance = enable_enhance
        self.denoise_strength = denoise_strength
        self.binarize_block_size = binarize_block_size if binarize_block_size % 2 == 1 else binarize_block_size + 1
        self.binarize_c = binarize_c
        self.max_skew_angle = max_skew_angle
        self.min_skew_angle = min_skew_angle
        self.return_bgr = return_bgr

    def to_numpy(self, image: Union[np.ndarray, Image.Image, Path, str]) -> np.ndarray:
        """Convert PIL Image, file path, or numpy array to a standardized BGR numpy array."""
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
            raise TypeError(f"Unsupported image type: {type(image)}. Expected np.ndarray, PIL.Image, or file path.")

    def denoise(self, gray: np.ndarray) -> np.ndarray:
        """Apply denoising to grayscale image."""
        try:
            return cv2.fastNlMeansDenoising(
                gray,
                h=self.denoise_strength,
                templateWindowSize=7,
                searchWindowSize=21
            )
        except Exception as e:
            logger.warning(f"Denoising failed, fallback to GaussianBlur: {e}")
            return cv2.GaussianBlur(gray, (3, 3), 0)

    def detect_skew_angle(self, gray: np.ndarray) -> float:
        """Calculate skew angle of grayscale document image in degrees."""
        try:
            # Invert colors so text is foreground (white)
            thresh = cv2.bitwise_not(cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1])
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) < 100:
                return 0.0

            angle = cv2.minAreaRect(coords)[-1]
            # minAreaRect returns angle in [-90, 0)
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            return float(angle)
        except Exception as e:
            logger.debug(f"Skew detection encountered error: {e}")
            return 0.0

    def deskew(self, image: np.ndarray, angle: Optional[float] = None) -> np.ndarray:
        """Rotate image to correct skew angle."""
        if angle is None:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            angle = self.detect_skew_angle(gray)

        if abs(angle) < self.min_skew_angle or abs(angle) > self.max_skew_angle:
            return image

        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Determine white background for rotated borders
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
        """Apply adaptive thresholding to produce clean high-contrast text."""
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
        """Enhance text contrast (CLAHE) and sharpen fine Vietnamese diacritic marks.

        Applies CLAHE on luminance channel followed by mild Unsharp Masking
        to restore delicate Vietnamese diacritic marks (dấu hỏi, ngã, nặng, mũ).
        """
        try:
            img = self.to_numpy(image)
            if img.size == 0 or img.shape[0] < 5 or img.shape[1] < 5:
                return img

            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            # 1. CLAHE on L channel of LAB color space to balance scanned lighting
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

            # 2. Unsharp masking to accentuate fine edges and diacritics
            blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=2.0)
            sharpened = cv2.addWeighted(enhanced, 1.3, blurred, -0.3, 0)
            return sharpened
        except Exception as e:
            logger.warning(f"enhance_document_text failed: {e}, falling back to original")
            return self.to_numpy(image)

    def preprocess(self, image: Union[np.ndarray, Image.Image]) -> np.ndarray:
        """Run complete preprocessing pipeline.

        Args:
            image: Input image as PIL Image or numpy array.

        Returns:
            Preprocessed image as numpy array (BGR if return_bgr=True, else single-channel grayscale).
        """
        try:
            img = self.to_numpy(image)

            # Convert to grayscale for analysis and filtering
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()

            # 1. Deskew
            if self.enable_deskew:
                angle = self.detect_skew_angle(gray)
                if abs(angle) >= self.min_skew_angle and abs(angle) <= self.max_skew_angle:
                    gray = self.deskew(gray, angle=angle)
                    if len(img.shape) == 3:
                        img = self.deskew(img, angle=angle)

            # 2. Text enhancement (CLAHE + Unsharp Mask) for crisp OCR
            if self.enable_enhance:
                img = self.enhance_document_text(img)
                if len(img.shape) == 3:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                else:
                    gray = img.copy()

            # 3. Denoise
            if self.enable_denoise:
                gray = self.denoise(gray)

            # 4. Adaptive Binarization
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
