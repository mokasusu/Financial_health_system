"""Module tiện ích hệ thống: đường dẫn Windows, logging, caching, và chuẩn hóa chuỗi."""
from pathlib import Path

# Đường dẫn gốc của dự án (tương thích đa nền tảng, chuẩn Windows)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
