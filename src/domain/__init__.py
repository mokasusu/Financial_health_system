"""Tầng Domain (Nghiệp vụ cốt lõi) của Hệ thống Sức khỏe Tài chính.

Tầng này độc lập hoàn toàn với framework, cơ sở dữ liệu và giao diện người dùng.
Bao gồm:
- models: Các thực thể nghiệp vụ (Entities) và Value Objects chuẩn Thông tư 200/2014/TT-BTC.
- accounting: Quy tắc chuẩn hóa kế toán, đẳng thức cân đối và từ điển ngữ nghĩa TT200.
- ratios: Động cơ tính 14 tỷ số tài chính bằng số học Decimal tuyệt đối.
- assessment: Động cơ thẩm định sức khỏe tài chính và phân loại rủi ro rule-based.
"""
