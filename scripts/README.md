# Lumos Scripts & Developer Tooling

Thư mục `scripts/` chứa các bộ công cụ phát triển (developer tools), phân tích dữ liệu và trực quan hóa hỗ trợ quá trình nghiên cứu, tinh chỉnh và kiểm thử pipeline RAG trong hệ thống Lumos.

---

## 📂 Danh mục công cụ

| Tên công cụ | Thư mục | Mục đích chính | Lệnh chạy nhanh |
| :--- | :--- | :--- | :--- |
| **`pdf_bbox_tool`** | [`scripts/pdf_bbox_tool/`](file:///home/rookie/Lumos/scripts/pdf_bbox_tool/) | Trực quan hóa cấu trúc layout thô (blocks, lines, images) từ PyMuPDF | `uv run python -m scripts.pdf_bbox_tool.main` |
| **`chunk_inspector`** | [`scripts/chunk_inspector/`](file:///home/rookie/Lumos/scripts/chunk_inspector/) | Kiểm tra nội dung text sau chunking, phân tích overlap và đóng khung chunk trên PDF | `uv run python -m scripts.chunk_inspector.main` |

---

## ⚖️ So sánh `pdf_bbox_tool` và `chunk_inspector`

| Tiêu chí | `pdf_bbox_tool` | `chunk_inspector` |
| :--- | :--- | :--- |
| **Trọng tâm phân tích** | Cấu trúc layout vật lý của PDF | Ngữ cảnh nội dung văn bản sau khi chia chunk |
| **Logic xử lý** | Đọc trực tiếp layout block thô qua PyMuPDF | Dùng `DocumentParser` + `RecursiveChunker` |
| **Dữ liệu văn bản** | Xem trước ngắn gọn (`preview[:80]`) | **Lưu trữ 100% nội dung text đầy đủ của từng chunk** |
| **Phân tích Overlap** | Không | Tự động phát hiện đoạn text gối đầu & độ dài overlap |
| **Báo cáo Markdown** | Không | Xuất báo cáo Markdown chi tiết (`.md`) |
| **Xuất JSON** | Tọa độ block thô | Metadata chunk + Full text + Bounding boxes |
| **Vẽ nhãn trên PDF** | Nhãn số hiệu Block (`B0: Text (1L)`) | Nhãn số hiệu Chunk + số ký tự + overlap (`Chunk #0 \| 755c`) |

---

## 🚀 Hướng dẫn sử dụng chi tiết

### 1. `pdf_bbox_tool` (Trực quan hóa layout thô)

Dùng khi cần kiểm tra cách PyMuPDF nhận diện khối văn bản (paragraphs, headers) và hình ảnh (figures/diagrams) trên trang.

```bash
# Chạy mặc định với file mẫu
uv run python -m scripts.pdf_bbox_tool.main

# Xuất kèm ảnh PNG preview và file JSON tọa độ layout
uv run python -m scripts.pdf_bbox_tool.main --save-json --export-images

# Vẽ chi tiết bounding box đến từng dòng văn bản (line-level)
uv run python -m scripts.pdf_bbox_tool.main --show-lines --export-images

# Tùy chọn file đầu vào và giới hạn trang
uv run python -m scripts.pdf_bbox_tool.main -i path/to/document.pdf --max-pages 5
```

Chi tiết tài liệu xem tại: [`scripts/pdf_bbox_tool/README.md`](file:///home/rookie/Lumos/scripts/pdf_bbox_tool/README.md).

---

### 2. `chunk_inspector` (Kiểm tra nội dung sau khi chunking)

Dùng khi cần thẩm định chất lượng chunking, độ dài văn bản, đoạn gối đầu (overlap) và kiểm tra chính xác nội dung trước khi đưa vào embedding.

```bash
# Chạy mặc định với file mẫu (tự động xuất PDF, JSON và Markdown)
uv run python -m scripts.chunk_inspector.main

# In toàn bộ nội dung text của tất cả các chunk ra Terminal
uv run python -m scripts.chunk_inspector.main --print-chunks

# Thử nghiệm với cấu hình kích thước chunk và overlap tùy biến
uv run python -m scripts.chunk_inspector.main --chunk-size 600 --chunk-overlap 100 --preview-chunks 5

# Xuất ảnh PNG preview trực quan từng trang
uv run python -m scripts.chunk_inspector.main --export-images --max-pages 5

# Tùy chọn file đầu vào (hỗ trợ cả PDF và EPUB)
uv run python -m scripts.chunk_inspector.main -i path/to/book.pdf
```

Chi tiết tài liệu xem tại: [`scripts/chunk_inspector/README.md`](file:///home/rookie/Lumos/scripts/chunk_inspector/README.md).

---

## 📁 Cấu trúc thư mục đầu ra chuẩn hóa

Cả hai công cụ đều **tự động gom nhóm toàn bộ kết quả vào một thư mục con riêng biệt** mang tên file tài liệu gốc (đặt cùng cấp với file đầu vào, thay vì để các file đầu ra nằm ngang hàng lộn xộn):

```
data/uploads/
├── BuildingEffectiveAIAgents_Anthropic.pdf             # File tài liệu đầu vào
│
└── BuildingEffectiveAIAgents_Anthropic/                # Thư mục đầu ra riêng biệt
    ├── BuildingEffectiveAIAgents_Anthropic_bbox.pdf        # PDF layout thô (pdf_bbox_tool)
    ├── BuildingEffectiveAIAgents_Anthropic_bbox.json       # JSON tọa độ layout (pdf_bbox_tool)
    ├── BuildingEffectiveAIAgents_Anthropic_chunk_bbox.pdf  # PDF phân chia chunk (chunk_inspector)
    ├── BuildingEffectiveAIAgents_Anthropic_chunks.json     # JSON đầy đủ text chunk (chunk_inspector)
    ├── BuildingEffectiveAIAgents_Anthropic_chunks.md       # Báo cáo Markdown chi tiết (chunk_inspector)
    └── bbox_previews/                                      # Thư mục ảnh PNG preview
        ├── page_01_bbox.png
        ├── page_01_chunk_bbox.png
        └── ...
```

---

## 🛠 Hướng dẫn phát triển & mở rộng thêm script mới

Khi bổ sung script/công cụ tiện ích mới vào `scripts/`, vui lòng tuân thủ các quy tắc sau:

1. **Đóng gói độc lập**: Mỗi công cụ được đặt trong một thư mục con riêng (ví dụ: `scripts/<tool_name>/`) với file `__init__.py`, `main.py` và `README.md`.
2. **Khả năng thực thi**: Đảm bảo công cụ có thể chạy linh hoạt cả dưới dạng module lẫn script:
   - `uv run python -m scripts.<tool_name>.main`
   - `uv run python scripts/<tool_name>/main.py`
3. **Quy ước đường dẫn đầu ra**: Luôn tạo thư mục con mang tên file tài liệu (`input_path.parent / input_path.stem`) để lưu kết quả, tránh ghi file lung tung ra thư mục cha.
4. **Kiểm thử tự động**: Viết unit test tương ứng trong thư mục `tests/` và đảm bảo `uv run pytest` vượt qua 100%.
