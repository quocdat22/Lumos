# 📓 Lumos RAG Evaluation Notebooks

Thư mục `notebooks/` chứa các Jupyter Notebooks phục vụ công tác nghiên cứu, đo kiểm thực nghiệm (benchmarking) và đánh giá chất lượng toàn diện của hệ thống **Lumos RAG**. 

Các notebook được thiết kế theo tư duy **Native Python**, tách biệt rõ ràng hai khâu cốt lõi (**Retrieval** và **Generation**), tích hợp cơ chế bộ nhớ đệm trên đĩa (**Disk Caching**) và phòng chống lỗi quá tải API (**Rate Limit Handling**).

---

## 📂 Danh Mục Các Notebook

| Tên Notebook | Khâu Đánh Giá | Tập Dữ Liệu | Phương Pháp & Kỹ Thuật | File Cache Liên Quan |
| :--- | :--- | :--- | :--- | :--- |
| **[`evaluate_retrieval_chunk_size.ipynb`](file:///home/rookie/Lumos/notebooks/evaluate_retrieval_chunk_size.ipynb)** | **Retrieval** (Truy xuất) | 9 test cases đa dạng (3 cuốn sách) | • Khảo sát 9 tổ hợp `chunk_size` & `chunk_overlap`<br>• Đo lường Hit@K, MRR@5, Context Coverage, Cosine Similarity<br>• `CachedEmbedder` lưu trữ vector query | [`eval/cache/embeddings_cache.pkl`](file:///home/rookie/Lumos/eval/cache/embeddings_cache.pkl) |
| **[`evaluate_generation_llm_judge.ipynb`](file:///home/rookie/Lumos/notebooks/evaluate_generation_llm_judge.ipynb)** | **Generation** (Sinh câu trả lời) | 9 test cases chuẩn ban đầu | • Phương pháp **LLM-as-a-Judge** độc lập<br>• 4 tiêu chí: Faithfulness, Relevance, Correctness, Citations<br>• Radar chart trực quan hóa năng lực mô hình | [`eval/cache/generation_eval_results.json`](file:///home/rookie/Lumos/eval/cache/generation_eval_results.json) |
| **[`evaluate_rag_hard_benchmark.ipynb`](file:///home/rookie/Lumos/notebooks/evaluate_rag_hard_benchmark.ipynb)** | **End-to-End** (Retrieval + Generation) | **30 test cases nâng cao** (*Designing ML Systems* - Chip Huyen) | • Khung 4 trụ cột tăng độ khó (Semantic Gap, Trade-offs...)<br>• Tích hợp `CachedEmbedder` & chống HTTP 429 Jina API<br>• Tương quan Coverage vs Correctness & hàm `inspect_evaluation` | [`eval/cache/hard_retrieval_benchmark_results.json`](file:///home/rookie/Lumos/eval/cache/hard_retrieval_benchmark_results.json)<br>[`eval/cache/hard_generation_eval_results.json`](file:///home/rookie/Lumos/eval/cache/hard_generation_eval_results.json) |

---

## 🔬 Chi Tiết Từng Notebook

### 1. `evaluate_retrieval_chunk_size.ipynb` — Tối Ưu Hóa Kích Thước Đoạn Văn

* **Mục tiêu**: Tìm ra điểm cân bằng tối ưu giữa tính toàn vẹn ngữ nghĩa và độ phân giải khi truy xuất văn bản.
* **Tổ hợp thực nghiệm**:
  * **3 mức `chunk_size`**: `256`, `512`, `1024` ký tự.
  * **3 mức `chunk_overlap`**: `40`, `100`, `200` ký tự.
* **Hệ thống chỉ số (Metrics)**:
  * **Hit@1, Hit@3, Hit@5**: Tỷ lệ xuất hiện của chunk mang bằng chứng trong top $K$ kết quả.
  * **MRR@5 (Mean Reciprocal Rank)**: Vị trí trung bình của kết quả đúng đầu tiên ($1/\text{rank}$).
  * **Cumulative Context Coverage@5**: Tỷ lệ bao phủ từ vựng ngữ cảnh gốc trong top 5 chunks.
  * **Search Latency & Embedding Cost**: Thời gian tìm kiếm trung bình (ms) và số lượng vector sinh ra.
* **Kết luận thực nghiệm**: Cấu hình **`chunk_size = 512, chunk_overlap = 100`** đạt hiệu quả tổng thể vượt trội nhất (Hit@3 = 100%, Coverage cao, cân đối chi phí vector hóa).

---

### 2. `evaluate_generation_llm_judge.ipynb` — Đánh Giá Chất Lượng Sinh Bằng LLM Judge

* **Mục tiêu**: Đánh giá độ tin cậy và sự tuân thủ format của câu trả lời do LLM sinh ra mà không cần các thư viện cồng kềnh như Ragas hay TruLens.
* **4 Tiêu chí đánh giá cốt lõi (Thang điểm 1 - 5)**:
  1. **Faithfulness (Groundedness)**: Câu trả lời có căn cứ tuyệt đối vào ngữ cảnh trích xuất không? (Chống hallucination).
  2. **Answer Relevance**: Câu trả lời có trực diện, đầy đủ và đúng trọng tâm câu hỏi không?
  3. **Answer Correctness**: Tính chính xác về mặt sự kiện khi so sánh với Ground Truth Reference.
  4. **Citation Compliance**: Mức độ tuân thủ định dạng trích dẫn nguồn chuẩn `[Source: <Book Title>, <Section>]`.
* **Cơ chế hoạt động**: Sử dụng prompt evaluator có định dạng JSON schema nghiêm ngặt, kết hợp trích xuất điểm số và reasoning giải thích chi tiết cho từng tiêu chí.

---

### 3. `evaluate_rag_hard_benchmark.ipynb` — Benchmark Toàn Diện Trên Bộ Dữ Liệu Nâng Cao

* **Mục tiêu**: Đánh giá toàn diện cả 2 khâu Retrieval và Generation trên bộ dữ liệu **30 câu hỏi phức tạp** trích xuất từ 30 đoạn ngẫu nhiên trong toàn bộ cuốn sách kỹ thuật *"Designing Machine Learning Systems"* (Chip Huyen).
* **Khung 4 Trụ Cột Nâng Cao Độ Khó (4-Pillar Difficulty Framework)**:
  1. **Semantic Gap**: Triệt tiêu hiện tượng trùng lặp từ khóa máy móc (lexical overlap); sử dụng ngôn ngữ bài toán thực tế để thử thách Dense Embedding.
  2. **Multi-part & Trade-off Reasoning**: Đòi hỏi lập luận đa tầng, giải thích cơ chế ("How/Why") và phân tích sự đánh đổi kỹ thuật.
  3. **Negative & Boundary Constraints**: Đặt các câu hỏi bẫy, điều kiện phủ định ("khi nào KHÔNG nên dùng..."), kiểm tra kỷ luật chống bịa đặt của mô hình.
  4. **Strict Multi-point Ground Truth**: Đáp án chuẩn gồm 3 cấu phần: *Luận điểm cốt lõi + Cơ chế giải thích + Khuyến nghị thực tế*.
* **Cơ chế chống lỗi Jina API Rate Limit (Kế thừa từ Commit `74756e2b`)**:
  * Tích hợp lớp `CachedEmbedder` lưu trữ vĩnh viễn vector query vào [`eval/cache/embeddings_cache.pkl`](file:///home/rookie/Lumos/eval/cache/embeddings_cache.pkl).
  * Hỗ trợ cơ chế **Exponential Backoff có Jitter ngẫu nhiên** và tự động phân tích header `Retry-After` khi gặp HTTP 429.
  * Cơ chế **Auto-Healing**: Tự động phát hiện và sinh bù các câu hỏi thiếu citation (`citations_count == 0`) do lỗi mạng/rate-limit cũ.
* **Phân tích nâng cao**:
  * Biểu đồ hộp (Boxplot) phân bố điểm số theo từng tiêu chí.
  * Biểu đồ tán xạ (Scatter plot) kèm đường xu hướng (Trendline) thể hiện mối tương quan thuận giữa **Độ phủ ngữ cảnh (Coverage@3)** và **Độ chính xác (Correctness)**.
  * Hàm chẩn đoán chuyên sâu `inspect_evaluation(tc_id)` hiển thị toàn văn câu hỏi, context, câu trả lời sinh ra và nhận xét của Judge.

---

## 📊 Kết Quả Thực Nghiệm Mới Nhất (Hard Benchmark N=30)

### 1. Năng Lực Retrieval (2.279 Chunks trong Vector Store)
* **Hit@1**: `70.0%`
* **Hit@3**: `86.7%`
* **Hit@5**: `90.0%`
* **MRR@5**: `0.779`
* **Context Coverage@3**: `91.4%`
* **Context Coverage@5**: `93.9%`

### 2. Năng Lực Generation (LLM-as-a-Judge, Thang 1 - 5)
* **Faithfulness**: `4.97 / 5.0` (±0.18) — *96.7% đạt điểm tối đa 5/5*
* **Answer Relevance**: `4.87 / 5.0` (±0.51) — *90.0% đạt điểm tối đa 5/5*
* **Correctness**: `4.80 / 5.0` (±0.76) — *86.7% đạt điểm tối đa 5/5*
* **Citation Compliance**: `4.73 / 5.0` (±1.01) — *86.7% trích dẫn chuẩn mực*
* **OVERALL COMPOSITE SCORE**: `4.84 / 5.0`
* **Tỷ lệ trích dẫn**: `100% (30/30 câu)` đều có đủ $\ge 3$ citations sau khi áp dụng `CachedEmbedder`.

---

## 🛠️ Hướng Dẫn Chạy & Phát Triển

### 1. Chuẩn Bị Môi Trường
Đảm bảo đã kích hoạt môi trường ảo `uv` của dự án:
```bash
# Kiểm tra các thư viện phụ thuộc đã cài đặt đầy đủ
uv sync
```

### 2. Thiết Lập Biến Môi Trường (`.env`)
Đảm bảo file `.env` ở thư mục gốc có đầy đủ các khóa API:
```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=deepseek/deepseek-v4-flash-0731
JINA_API_KEY=jina_...
```

### 3. Khởi Chạy Notebook
Bạn có thể mở và thực thi trực tiếp trên VS Code, Cursor hoặc qua Jupyter Lab:
```bash
uv run jupyter lab
```
* **Lưu ý về Kernel**: Hãy chọn đúng Python Kernel tại đường dẫn `.venv/bin/python`.
* **Cơ chế Cache**: Toàn bộ kết quả retrieval và generation được lưu tại `eval/cache/`. Nếu muốn chạy lại hoàn toàn từ đầu (fresh run), bạn chỉ cần xóa các file `.json` tương ứng trong thư mục cache.
