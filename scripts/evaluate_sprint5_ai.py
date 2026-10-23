"""Evaluation script for Sprint 5: AI Financial Interpretation via OpenRouter.

Runs end-to-end on the real CTCP 32 (2020) sample:
Parser -> 14 Ratios -> Assessment Engine -> AI Financial Interpreter.

Usage:
    python scripts/evaluate_sprint5_ai.py
"""
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.parser import FinancialStatementParser
from src.financial.ai_interpreter import AIFinancialInterpreter
from src.financial.assessment import FinancialHealthAssessor
from src.financial.openrouter_client import OpenRouterClient, OpenRouterConfig, redact_secret
from src.financial.ratios import FinancialRatioCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate_sprint5")


def run_evaluation():
    sample_file = PROJECT_ROOT / "data" / "samples" / "conghuy_A32_2020_sample.txt"
    if not sample_file.exists():
        logger.error("Sample file not found: %s", sample_file)
        return

    print("=" * 80)
    print("EVALUATION SPRINT 5: AI FINANCIAL INTERPRETATION PIPELINE")
    print("=" * 80)

    # 1. Pipeline execution: Parser -> Calculator -> Assessor
    with open(sample_file, "r", encoding="utf-8") as f:
        text = f.read()

    print("\n[BƯỚC 1] Bóc tách báo cáo tài chính...")
    parser = FinancialStatementParser()
    statement = parser.parse(text, source_name="conghuy_A32_2020_sample.txt")
    print(f"-> Đơn vị: {statement.company_name} | Năm: {statement.fiscal_year}")

    print("\n[BƯỚC 2] Tính toán 14 chỉ số tài chính (Sprint 4A)...")
    calculator = FinancialRatioCalculator()
    ratio_report = calculator.calculate_all(statement)
    print(f"-> Đã tính toán: {ratio_report.calculated_ratios}/14 chỉ số")

    print("\n[BƯỚC 3] Đánh giá quy tắc và cảnh báo rủi ro (Sprint 4B)...")
    assessor = FinancialHealthAssessor()
    assessment = assessor.assess(ratio_report)
    print(f"-> Trạng thái sức khỏe: {assessment.overall_status.value.upper()}")
    print(f"-> Số chỉ số WATCH: {assessment.watch_count} (3 thanh khoản + 3 đòn bẩy)")
    print(f"-> Số cảnh báo phát sinh: {len(assessment.warnings)}")

    # 2. Check OpenRouter Configuration
    print("\n[BƯỚC 4] Khởi tạo AI Interpreter (Sprint 5)...")
    try:
        config = OpenRouterConfig.from_env()
        print(f"-> Model cấu hình: {config.model}")
        print(f"-> Base URL: {config.base_url}")
        print(f"-> API Key: {redact_secret(config.api_key)}")
        client = OpenRouterClient(config=config)
        has_config = True
    except Exception as e:
        print(f"-> Cấu hình API key chưa sẵn sàng: {e}")
        print("-> Sẽ chạy ở chế độ Deterministic Fallback an toàn...")
        client = None
        has_config = False

    interpreter = AIFinancialInterpreter(client=client) if client else AIFinancialInterpreter(client=OpenRouterClient(config=OpenRouterConfig(api_key="dummy", model="dummy")))

    # 3. Execution
    start_time = time.time()
    try:
        output = interpreter.interpret(assessment, allow_fallback=True)
        elapsed = time.time() - start_time
    except Exception as err:
        logger.error("Lỗi khi thực hiện interpretation: %s", err)
        return

    # 4. Report results
    print("\n" + "=" * 80)
    print("KẾT QUẢ PHÂN TÍCH TÀI CHÍNH AI (STRUCTURED OUTPUT)")
    print("=" * 80)
    print(f"Chế độ thực thi: {'DETERMINISTIC FALLBACK' if output.is_fallback else 'OPENROUTER MODEL'}")
    print(f"Model sử dụng: {output.model_used}")
    print(f"Thời gian phản hồi: {elapsed:.2f} giây")

    print("\n--- 1. TÓM TẮT ĐIỀU HÀNH (EXECUTIVE SUMMARY) ---")
    print(output.executive_summary)

    print(f"\n--- 2. ĐIỂM MẠNH TÀI CHÍNH ({len(output.financial_strengths)}) ---")
    for s in output.financial_strengths:
        if isinstance(s, dict):
            print(f"- {s.get('strength_title')}: {s.get('evidence')}")
        elif hasattr(s, "strength_title"):
            print(f"- {s.strength_title}: {s.evidence}")
        else:
            print(f"- {s}")

    print(f"\n--- 3. RỦI RO TÀI CHÍNH ({len(output.financial_risks)}) ---")
    for r in output.financial_risks:
        print(f"- [{r.severity.upper()}] {r.risk_title}")
        print(f"  Căn cứ: {r.evidence}")
        print(f"  Tác động: {r.implication}")

    print(f"\n--- 4. GIẢI THÍCH CHỈ SỐ MẪU ({len(output.ratio_explanations)} chỉ số) ---")
    for k in ["current_ratio", "debt_to_assets", "net_profit_margin"]:
        if k in output.ratio_explanations:
            print(f"- {k}: {output.ratio_explanations[k]}")

    print(f"\n--- 5. KHUYẾN NGHỊ HÀNH ĐỘNG ({len(output.recommendations)}) ---")
    for rec in output.recommendations:
        print(f"- {rec}")

    print(f"\n--- 6. GIỚI HẠN VÀ TUYÊN BỐ MIỄN TRỪ ---")
    for lim in output.data_limitations[:2]:
        print(f"- {lim}")
    print(f"Disclaimer: {output.disclaimer[:120]}...")

    print("\n" + "=" * 80)
    print("HOÀN THÀNH ĐÁNH GIÁ SPRINT 5 THÀNH CÔNG!")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()
