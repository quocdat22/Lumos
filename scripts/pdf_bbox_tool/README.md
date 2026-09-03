# PDF Bounding Box Visualizer Tool

Công cụ trực quan hóa cấu trúc layout và bounding box cho tài liệu PDF trong hệ sinh thái Lumos.

## Tính năng
- **Text Block Bounding Box**: Đóng khung các khối văn bản (paragraph, header, footer) với màu Xanh Dương (`#1E88E5`). Kèm nhãn số hiệu block và số dòng (`B{index}: Text ({lines}L)`).
- **Image / Figure Bounding Box**: Đóng khung các hình ảnh, biểu đồ kiến trúc agent với màu Cam (`#F3722C`). Kèm nhãn kích thước pixel (`IMG {index}: {W}x{H}`).
- **Line Bounding Box** (tùy chọn `--show-lines`): Đóng khung chi tiết từng dòng văn bản bên trong block với màu Xanh Ngọc nhạt (`#00B4D8`).
- **Legend trực quan**: Tự động chèn bảng chú thích màu sắc ở góc trên bên phải mỗi trang.
- **Xuất ảnh xem trước** (tùy chọn `--export-images`): Render từng trang thành file PNG để người dùng có thể xem nhanh không cần mở trình đọc PDF.
- **Xuất JSON tọa độ** (tùy chọn `--save-json`): Xuất toàn bộ tọa độ `[x0, y0, x1, y1]` phục vụ nghiên cứu hoặc tích hợp vào pipeline chunking theo layout.

## Cài đặt phụ thuộc
Dự án sử dụng thư viện `pymupdf` (đã được cấu hình trong `pyproject.toml`):
```bash
uv sync
```

## Hướng dẫn sử dụng

### 1. Chạy mặc định với file PDF của bạn
Lệnh này sẽ tự động lấy file `data/uploads/BuildingEffectiveAIAgents_Anthropic.pdf` và lưu các file kết quả vào thư mục con cùng tên `data/uploads/BuildingEffectiveAIAgents_Anthropic/`:
```bash
uv run python -m scripts.pdf_bbox_tool.main
# Hoặc chạy trực tiếp file script:
uv run python scripts/pdf_bbox_tool/main.py
```

### 2. Chạy với tùy chọn xuất ảnh preview và hiển thị line
```bash
uv run python -m scripts.pdf_bbox_tool.main --show-lines --export-images --save-json
```

### 3. Tùy chỉnh đường dẫn file vào và ra
```bash
uv run python -m scripts.pdf_bbox_tool.main \
  --input data/uploads/BuildingEffectiveAIAgents_Anthropic.pdf \
  --output data/uploads/output_bbox.pdf \
  --max-pages 5
```

## Bảng quy ước màu sắc
| Thành phần | Màu sắc | Ý nghĩa |
| :--- | :--- | :--- |
| **Text Block** | Xanh Dương (`#1E88E5`) | Khối văn bản (đoạn văn, tiêu đề). Nền mờ 7% |
| **Image/Figure** | Cam Đậm (`#F3722C`) | Hình ảnh, sơ đồ biểu đồ. Nền mờ 12% |
| **Text Line** | Xanh Ngọc (`#00B4D8`) | Từng dòng text chi tiết (khi bật `--show-lines`) |
