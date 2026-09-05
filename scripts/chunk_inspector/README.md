# Lumos Chunk Inspector & Visualizer Tool

Công cụ kiểm tra nội dung sau khi chunking và trực quan hóa layout bounding box cho tài liệu PDF / e-book trong hệ sinh thái Lumos.

Script sử dụng trực tiếp logic chia nhỏ văn bản từ [`RecursiveChunker`](file:///home/rookie/Lumos/src/lumos/core/chunker.py) và [`DocumentParser`](file:///home/rookie/Lumos/src/lumos/core/parser.py) để mô phỏng chính xác pipeline RAG thực tế.

---

## 🌟 Tính năng chính

1. **Kiểm tra đầy đủ nội dung sau khi chunking (Post-Chunking Content Inspection)**:
   - Lưu trữ và hiển thị toàn bộ nội dung text của từng chunk (không bị cắt ngắn hay giới hạn 80 ký tự).
   - Đầy đủ metadata: `chunk_id` (SHA-256 deterministic hash), `chunk_index`, `section` (Page X), số ký tự (`char_count`), số từ (`word_count`).

2. **Phân tích và phát hiện Overlap giữa các chunk liền kề**:
   - Tự động so khớp hậu tố của chunk trước và tiền tố của chunk sau để trích xuất chính xác đoạn văn bản gối đầu (`overlap_prev_text`, `overlap_prev_chars`).
   - Đánh dấu nổi bật vùng overlap trên console, trong báo cáo Markdown và trên trang PDF.

3. **Xuất báo cáo Markdown chi tiết (`--save-markdown`)**:
   - Tạo file `.md` chứa bảng thống kê tổng hợp (Min/Avg/Max length, số chunk overlap) và nội dung chi tiết từng chunk được đóng khung rõ ràng.

4. **Xuất file JSON toàn diện (`--save-json`)**:
   - Xuất file `.json` chứa mảng `chunks` với toàn bộ nội dung text gốc sau khi chunking, kèm tọa độ bounding box trên từng trang PDF (`bboxes`, `union_bbox`).

5. **Trực quan hóa trên file PDF & Ảnh xem trước (`--export-images`)**:
   - Tô màu viền và nền riêng biệt cho từng chunk theo chu kỳ màu sắc.
   - Nhãn badge hiển thị số thứ tự chunk, độ dài ký tự và số ký tự overlap (VD: `Chunk #1 | 250c | Overlap 121c`).
   - Đường viền nét đứt màu Hồng cánh sen (`#E91E63`) đánh dấu riêng các khối text thuộc phần overlap.
   - Tự động vẽ bảng chú thích (Legend) ở góc trên trang.

---

## 🚀 Hướng dẫn sử dụng

### 1. Chạy mặc định
Lệnh sẽ phân tích file PDF mặc định, chunking với `chunk_size=512` & `chunk_overlap=100`, và tự động lưu toàn bộ các file kết quả (PDF trực quan, file JSON và Markdown) vào thư mục con cùng tên với file PDF (ví dụ: `data/uploads/BuildingEffectiveAIAgents_Anthropic/`):
```bash
uv run python -m scripts.chunk_inspector.main
# Hoặc chạy trực tiếp file main.py:
uv run python scripts/chunk_inspector/main.py
```

### 2. In toàn bộ nội dung chunk ra Terminal
Để đọc trực tiếp toàn bộ các chunk đã chia nhỏ trong cửa sổ dòng lệnh:
```bash
uv run python -m scripts.chunk_inspector.main --print-chunks
```

### 3. Tùy chỉnh kích thước chunk và overlap
Kiểm tra thử nghiệm với các thông số chunk size khác nhau:
```bash
uv run python -m scripts.chunk_inspector.main \
  --chunk-size 600 \
  --chunk-overlap 100 \
  --preview-chunks 5
```

### 4. Xuất ảnh preview PNG từng trang
```bash
uv run python -m scripts.chunk_inspector.main \
  --export-images \
  --images-dir data/uploads/bbox_previews \
  --max-pages 5
```

---

## 📊 Bảng tham số dòng lệnh

| Tham số | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `-i, --input` | `data/uploads/BuildingEffectiveAIAgents_Anthropic.pdf` | Đường dẫn file PDF hoặc EPUB đầu vào |
| `-o, --output` | `<input_dir>/<file_stem>/<file_stem>_chunk_bbox.pdf` | Đường dẫn lưu file PDF sau khi gắn nhãn bounding box |
| `--chunk-size` | `512` | Số ký tự tối đa cho mỗi chunk (theo logic `RecursiveChunker`) |
| `--chunk-overlap`| `100` | Số ký tự gối đầu (overlap) giữa các chunk liên tiếp |
| `--print-chunks` | `False` | In toàn bộ nội dung text của tất cả các chunk ra terminal |
| `--preview-chunks`| `3` | Số lượng chunk xem trước trên terminal (đặt `0` để tắt) |
| `--save-json` | `True` | Xuất file JSON chứa toàn bộ nội dung và tọa độ bounding box |
| `--json-path` | Tự động | Đường dẫn tùy chọn cho file JSON kết quả |
| `--save-markdown` | `True` | Xuất file Markdown báo cáo kiểm tra chi tiết từng chunk |
| `--markdown-path` | Tự động | Đường dẫn tùy chọn cho file Markdown kết quả |
| `--export-images` | `False` | Render từng trang PDF ra file ảnh PNG có bounding box |
| `--images-dir` | `data/uploads/bbox_previews` | Thư mục lưu ảnh preview PNG |
| `--dpi` | `140` | Độ phân giải của ảnh PNG render |
| `--max-pages` | `None` (tất cả) | Giới hạn số trang xử lý đầu tiên |
| `--show-lines` | `False` | Vẽ thêm viền bao quanh từng dòng text chi tiết bên trong chunk |

---

## 🎨 Bảng quy ước màu sắc

| Thành phần | Màu sắc | Ý nghĩa |
| :--- | :--- | :--- |
| **Chunk Bounding Box** | Xanh dương (`#1E88E5`), Xanh ngọc (`#10B981`), Tím (`#8B5CF6`), Vàng hổ phách (`#F59E0B`) | Khối văn bản thuộc từng chunk tương ứng |
| **Chunk Overlap** | Hồng Magenta (`#E91E63`, nét đứt) | Đoạn text gối đầu được lặp lại từ chunk liền trước |
| **Image / Figure** | Cam Đậm (`#F3722C`) | Hình ảnh, sơ đồ kiến trúc agent |
| **Text Line** | Xanh nhạt (khi bật `--show-lines`) | Đường bao từng dòng text chi tiết |
