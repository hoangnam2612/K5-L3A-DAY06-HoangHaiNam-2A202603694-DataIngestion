# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.

## Bài làm: cách setup và chạy

Hoàng Hải Nam · 2A202603694 · Corpus: 59 truyện ngắn Nam Cao (tiếng Việt, Markdown). Báo cáo: [report/individual/2A202603694_HoangHaiNam.md](report/individual/2A202603694_HoangHaiNam.md).

**1. Dữ liệu** (không commit vào repo). Đặt vào `starter/data/raw/nam-cao/`:

```bash
git clone https://github.com/khudocmo/truyen-ngan-nam-cao.git
cd truyen-ngan-nam-cao && git checkout 049faf18d1313ded145258e4da1a4725cace9fbe
# chép thư mục truoc-cach-mang/, sau-cach-mang/ và LICENSE.md vào starter/data/raw/nam-cao/
```

`data/manifest.json` đã có sẵn (nguồn, giấy phép, quy tắc đếm, mã băm từng file). Chỉ khi tạo lại manifest bằng `scripts/build_manifest.py` mới cần thêm file `starter/data/raw/nam-cao/SOURCE.txt` (các dòng `url`, `commit`, `commit_date`, `accessed_at`, `excluded`).

**2. Môi trường và database** (chạy từ `starter/`):

```bash
python -m venv .venv                      # kích hoạt: .venv\Scripts\Activate.ps1 (Windows) hoặc source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env                      # điền OPENAI_API_KEY (không commit .env)
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

**3. Kiểm tra benchmark, chạy pipeline, xem kết quả** (chạy từ `starter/`):

```bash
python -I -X utf8 scripts/verify_benchmark.py   # kiểm chứng evidence của 24 câu, trước khi chạy truy xuất
python -m src.run                                # chunk A/B/C, embed, lưu pgvector, top-3, chỉ số; mất khoảng 1 phút, ≈ 0,02 USD
python -I -X utf8 scripts/build_dashboard.py    # tạo results/dashboard.html để xem trực quan
```

**4. Đường dẫn chính**

| Nội dung | Đường dẫn |
|---|---|
| Code pipeline | `starter/src/` |
| Manifest dữ liệu | `data/manifest.json` |
| Benchmark (câu hỏi, split, gold evidence) | `benchmark/benchmark.json` |
| Log cấu hình và giả thuyết A/B/C | `artifacts/experiment_log.csv` |
| Trace top-3, thống kê, log nạp dữ liệu | `results/traces.json`, `results/metrics.json`, `results/run_info.json`, `results/ingestion_log.json` |
| Nhãn thủ công | `results/manual_coherence.csv`, `results/manual_metadata.csv`, `results/manual_grounding.csv` |
| Báo cáo cá nhân | `report/individual/2A202603694_HoangHaiNam.md` |
