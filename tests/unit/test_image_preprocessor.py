"""Unit tests for ImagePreprocessor."""
import numpy as np
from PIL import Image
import pytest

from src.infrastructure.ocr.preprocessor import ImagePreprocessor


def test_preprocessor_init_defaults():
    preprocessor = ImagePreprocessor()
    assert preprocessor.enable_denoise is True
    assert preprocessor.enable_deskew is True
    assert preprocessor.enable_binarize is True
    assert preprocessor.return_bgr is True
    assert preprocessor.binarize_block_size % 2 == 1


def test_to_numpy():
    preprocessor = ImagePreprocessor()
    
    # PIL input
    pil_img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    arr = preprocessor.to_numpy(pil_img)
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (100, 100, 3)

    # Numpy array input
    np_arr = np.zeros((50, 50, 3), dtype=np.uint8)
    arr2 = preprocessor.to_numpy(np_arr)
    assert arr2.shape == (50, 50, 3)

    # Invalid input
    with pytest.raises(ValueError):
        preprocessor.to_numpy("non_existent_file.png")

    with pytest.raises(TypeError):
        preprocessor.to_numpy(12345)


def test_denoise():
    preprocessor = ImagePreprocessor(denoise_strength=10)
    gray = np.ones((100, 100), dtype=np.uint8) * 200
    # Add random noise
    noise = np.random.randint(0, 50, (100, 100), dtype=np.uint8)
    noisy_img = np.clip(gray + noise, 0, 255).astype(np.uint8)

    denoised = preprocessor.denoise(noisy_img)
    assert denoised.shape == noisy_img.shape
    assert denoised.dtype == np.uint8


def test_binarize():
    preprocessor = ImagePreprocessor(binarize_block_size=31, binarize_c=10)
    gray = np.linspace(0, 255, 10000, dtype=np.uint8).reshape((100, 100))
    binarized = preprocessor.binarize(gray)
    assert binarized.shape == (100, 100)
    # Output should only contain 0 and 255
    unique_vals = np.unique(binarized)
    for v in unique_vals:
        assert v in (0, 255)


def test_deskew_no_skew():
    preprocessor = ImagePreprocessor()
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255
    # Blank image should have near zero angle
    deskewed = preprocessor.deskew(img)
    assert deskewed.shape == img.shape


def test_preprocess_pipeline():
    preprocessor = ImagePreprocessor(return_bgr=True)
    # Synthetic white document with dark text block
    img = np.ones((200, 200, 3), dtype=np.uint8) * 255
    img[50:150, 50:150] = 0

    result = preprocessor.preprocess(img)
    assert isinstance(result, np.ndarray)
    assert result.shape == (200, 200, 3)  # BGR output

    # Check grayscale output option
    preprocessor_gray = ImagePreprocessor(return_bgr=False)
    result_gray = preprocessor_gray.preprocess(img)
    assert result_gray.ndim == 2 or result_gray.shape[2] == 1


def test_preprocess_fallback_on_corrupt():
    preprocessor = ImagePreprocessor()
    # Pass 0-size image or unusual shape
    dummy = np.zeros((1, 1, 3), dtype=np.uint8)
    res = preprocessor.preprocess(dummy)
    assert isinstance(res, np.ndarray)
