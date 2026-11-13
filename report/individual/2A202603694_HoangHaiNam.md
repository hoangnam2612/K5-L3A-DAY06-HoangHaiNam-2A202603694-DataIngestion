# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline
- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - Chủ đề: tuyển tập truyện ngắn Nam Cao (tiếng Việt), bản số hóa Markdown, repo `https://github.com/khudocmo/truyen-ngan-nam-cao`, commit `049faf18d1313ded145258e4da1a4725cace9fbe` (2026-01-09), truy cập 2026-11-13. Chi tiết nguồn, mã băm từng file và giấy phép nằm trong `data/manifest.json`.
  - Quyền: repo ghi các văn bản nguồn "được cho là thuộc phạm vi công cộng ở Việt Nam" (đây là nhận định, không phải giấy phép cấp quyền) và phần đóng góp của người số hóa theo CC0; người dùng ngoài Việt Nam phải tự kiểm tra luật. Repo không nêu bản in gốc của văn bản.
  - Quy tắc tính: dữ liệu không có phân trang nên mỗi truyện (một file `.md` trong `truoc-cach-mang/` hoặc `sau-cach-mang/`) là một đơn vị nguồn độc lập, cần ≥ 1.500 ký tự chuẩn hóa theo `GUIDE.md`. Có **59 đơn vị** (43 trước cách mạng, 16 sau cách mạng), tổng **1.038.921 ký tự** (ngắn nhất 6.274, trung vị 13.358, dài nhất 63.506), không đơn vị nào dưới ngưỡng. Không tính: thư mục `files/` (sách điện tử gộp lặp lại các truyện), `doc.md`, `README.md`, `metadata.yaml`, `Makefile`, `minimal.css`. `page` trong pipeline là số thứ tự truyện (1–43 trước cách mạng sắp theo tên file, 44–59 sau cách mạng).
- **Chuẩn hóa, lỗi và giới hạn:** NFC, đọc từng file (xử lý CRLF), bỏ dòng tiêu đề `# ...`, đường kẻ ngang, dòng chú thích cuối trang, dòng ảnh và thẻ HTML đứng riêng (tổng 97 dòng: 59 tiêu đề, 26 đường kẻ, 7 ảnh, 4 thẻ, 1 chú thích); gỡ ký hiệu in đậm, nghiêng, link, `[^n]` nhưng giữ chữ. Số dòng của chunk là số dòng thật trong file `.md`. Giới hạn: một chỗ còn dấu `_` thừa trong `nhung-tre-khon-nan` do nguồn gõ sai (ghi trong `data/manifest.json`, không tự sửa); dấu phân cảnh `⁂` và các dòng như "Tiểu thuyết thứ Bảy" hay ngày đăng vẫn nằm trong văn bản; có 4 chunk B rất ngắn (như `1948`) là dòng ngày tháng cuối truyện; không có sự kiện lỗi nào trong `results/ingestion_log.json`.
- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:**
  - Embedding: OpenAI `text-embedding-3-small`, 1536 chiều, SDK `openai` 2.54.0, Python 3.14.4. Cùng một model cho A, B và các câu hỏi.
  - Vector store: PostgreSQL 16 + pgvector 0.8.7 (`pgvector/pgvector:0.8.7-pg16`, Docker 29.8.2), `psycopg` 3.3.8. Metric cosine (toán tử `<=>`), tìm kiếm chính xác (quét toàn bộ, không dùng chỉ mục xấp xỉ). Bảng `chunks` khóa chính `(strategy, chunk_id)`; nạp lại dùng upsert nên không nhân đôi (đã kiểm tra: 2.343 và 1.310 dòng sau mỗi lần chạy).
  - Lệnh (từ `starter/`): `python -m venv .venv`, `python -m pip install -r requirements.txt`, điền `OPENAI_API_KEY` vào `.env`, `docker compose -p day6_student_starter up -d --wait`, `python -I -X utf8 scripts/build_manifest.py`, `python -I -X utf8 scripts/verify_benchmark.py`, `python -m src.run`, `python -I -X utf8 scripts/build_dashboard.py`.
  - Chi phí: lần chạy cuối (2026-11-13 12:00 UTC) dùng 1.176.944 token embedding (63 request), ước tính **0,0235 USD** theo giá công bố 0,02 USD/1M token (giá nhớ từ tài liệu công bố, chưa đối chiếu lại trên trang giá). Tổng thực tế cao hơn: hai lần chạy đầu bị lỗi ở bước tạo bản mẫu audit sau khi đã embed xong, nên tổng ba lần chạy khoảng 3,5 triệu token ≈ 0,07 USD.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:** bắt buộc `document_id` (`namcao`), `source` (đường dẫn file `.md` tương đối), `page` (số thứ tự truyện). Trường lọc bổ sung `period` (`truoc-cach-mang` hoặc `sau-cach-mang`), lấy từ tên thư mục trong repo nguồn, không suy đoán. Trường truy vết thêm: `title`, `unit_id`, `section` (= tên truyện), `line_start`, `line_end`, `page_lines`, `chunk_id`. Lý do chọn `period`: có hai phạm vi phân biệt được, đáng tin vì lấy từ cấu trúc nguồn. Hạn chế: thô (43 so với 16 truyện), và trường `year` không dùng được vì chỉ 1 trong 59 tiêu đề có năm.

## Cấu hình và benchmark
- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):**
  - A: cửa sổ cố định 500 ký tự, overlap 50, không lọc (2.343 chunk).
  - B: theo đoạn, tối đa 1.000 ký tự; đoạn dài hơn được cắt ở cuối câu (1.310 chunk).
  - C: dùng đúng các chunk và vector của B, thêm lọc `period` ở bước truy vấn chỉ cho những câu có filter; câu không có filter chạy không lọc, giống B. Khác biệt duy nhất B–C là filter. A–B chỉ khác ở cách chia chunk. Cùng model, corpus, benchmark, top-3.
- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:** 24 câu tiếng Việt trong `benchmark/benchmark.json`: **18 dev (5 truyện) và 6 test (3 truyện khác hẳn)**, chia theo truyện trước khi truy xuất. Loại câu: 15 trực tiếp, 5 diễn đạt lại, 4 điều kiện/nguyên nhân. Ba câu có filter: d12 (dev, trước cách mạng), d17 (dev, sau cách mạng), t01 (test, trước cách mạng); giá trị filter là ngữ cảnh người dùng cung cấp trước, không suy từ đáp án. Kiểm chứng bằng `scripts/verify_benchmark.py`: đủ trường bắt buộc, evidence nằm đúng trong truyện gold (so khớp sau chuẩn hóa), không xuất hiện ở truyện khác, giá trị filter khớp thời kỳ của truyện gold, đạt mức tối thiểu 20 câu, 15 dev, 5 test, 3 filter có 1 ở test. Bộ câu hỏi được viết trước khi chạy bất kỳ truy xuất nào trên corpus này. Câu hỏi do trợ lý AI (Claude) soạn nháp sau khi đọc 8 trong 59 truyện, tác giả chấp nhận trước khi chạy.
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test:** tiêu chí dưới đây được viết **sau** khi pipeline chạy lần đầu, nên tác giả đã thấy kết quả test trước khi viết. Vì vậy việc chọn chỉ dựa trên dev: (1) Evidence Hit@3 trên dev, (2) coherence, (3) tài nguyên (số chunk, thời gian, chi phí). Không điều chỉnh tham số hay câu hỏi nào sau khi xem kết quả (A 500/50 và B 1.000 giữ nguyên từ đầu).

## Kết quả
Thời gian là thời gian embed và lưu vào DB (đo thật). Chi phí từng chiến lược là ước tính chia theo tỷ lệ ký tự (A 1.157.291, B 1.041.889) từ tổng 0,0235 USD; C không embed thêm. Chưa đo riêng thời gian truy vấn.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 5/18 | 6/18 | 2.343 | 27,8 s | ≈ 0,012 USD |
| A | test | 1/6 | 2/6 | 2.343 | (cùng lần chạy) | (cùng lần chạy) |
| B | dev | 5/18 | 6/18 | 1.310 | 13,3 s | ≈ 0,011 USD |
| B | test | 3/6 | 4/6 | 1.310 | (cùng lần chạy) | (cùng lần chạy) |
| C | dev | 5/18 | 6/18 | 1.310 (của B) | 0 s thêm | 0 |
| C | test | 3/6 | 4/6 | 1.310 (của B) | 0 s thêm | 0 |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1,0 (10 vị trí) | 18/18 | dev 1/2, test 1/1 | 2/2/2; 1,0 |
| B | 1,9 (10 vị trí) | 18/18 | dev 2/2, test 1/1 | 2/0/4; 1,33 |
| C | như B (cùng chunk, không chấm riêng) | 18/18 | dev 2/2, test 1/1 | 2/0/4; 1,33 |

Ghi chú: "Filter tuân thủ" là số câu có filter mà cả top-3 thuộc đúng thời kỳ yêu cầu. B không áp filter nên kết quả tuân thủ của B là ngẫu nhiên theo nội dung truy xuất.

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**
- Trace top-3 đầy đủ (câu hỏi, chunk, score, metadata, nhãn Hit): `results/traces.json`; thống kê `results/metrics.json`, `results/run_info.json`, `results/ingestion_log.json`; cấu hình và giả thuyết `artifacts/experiment_log.csv`; trình xem trực quan `results/dashboard.html`.
- Nhãn thủ công: `results/manual_coherence.csv`, `results/manual_metadata.csv`, `results/manual_grounding.csv`.
- Coherence: 10 vị trí cố định bằng seed `20260101` trong `src/run.py` trước khi xem điểm: chọn ngẫu nhiên 10 truyện, mỗi truyện chọn ngẫu nhiên một đoạn nguồn; cả A và B chấm chunk chứa đúng vị trí đó (dashboard ẩn nhãn A/B mặc định khi tác giả duyệt; người soạn nháp thì biết nhãn). Metadata và grounding: toàn bộ 6 câu test × top-3 × 3 cấu hình (54 bản ghi metadata, 18 dòng grounding).
- Người chấm: nhãn do trợ lý AI (Claude) soạn nháp kèm lý do, **tác giả xem xét và chấp nhận từng nhãn**. Metadata còn được kiểm bằng máy: mỗi bản ghi đối chiếu với file `.md` gốc (file, số thứ tự truyện, tên truyện, thời kỳ, đầu và cuối chunk nằm đúng ở dòng đã ghi), cả 54/54 đúng. Nguy cơ thiên lệch: người soạn nháp biết chunk nào thuộc A hay B, và cũng là người dựng pipeline.

## Phân tích và kết luận
- **So sánh A–B và B–C; 2 ví dụ sai có ID câu và nguồn:**
  - **A–B:** Hit@1 và Hit@3 trên dev bằng nhau (5/18 và 6/18, nhưng là các câu khác nhau); trên test B hơn A (3/6 và 4/6 so với 1/6 và 2/6), chênh hai câu nên rất ít sức nặng. Khác biệt rõ hơn ở chất lượng chunk: coherence 1,9 so với 1,0 (A cắt giữa câu, giữa chữ), grounding trung bình 1,33 so với 1,0, và A làm evidence bị tách qua hai chunk ở 3 câu (d08, d10, t02) trong khi B là 0 câu. B dùng ít chunk hơn (1.310 so với 2.343) và embed nhanh hơn (13,3 s so với 27,8 s). Chunk B dài hơn (trung vị 887,5 so với 500) nên có thể loãng ý.
  - **B–C:** giống hệt trên mọi số đếm. Filter không thêm Hit nào: hai câu filter ở dev (d12, d17) vẫn trượt vì top-3 đã đúng truyện nhưng chunk thiếu evidence, không phải vì lẫn thời kỳ khác; t01 trúng Hit@3 ở cả B lẫn C. Filter chỉ bảo đảm top-3 đúng thời kỳ (tuân thủ 100% ở C), nhưng với 3 câu filter thì chưa đủ để kết luận hiệu quả.
  - **Ví dụ sai 1, câu d01 (truyện 7 `con-meo`, dòng 3), cả A, B và C trượt:** câu hỏi "Nguyên nhân của cuộc cãi vã giữa vợ chồng anh cu là gì?", evidence "Đầu đuôi tại con mèo. Nhưng cũng tại trời bức nữa." không chứa từ về cãi vã. Với B, chunk chứa evidence xếp hạng 779/1.310 (điểm 0,368 so với 0,612 của hạng 1); top-3 là các truyện 35 (`rinh-trom`), 52 (`nhung-ban-tay-dep-ay`), 58 (`vai-net-ghi-qua-vung-vua-giai-phong`). Nguyên nhân chính là câu hỏi quá trừu tượng so với câu evidence và corpus có nhiều cảnh vợ chồng cãi nhau.
  - **Ví dụ sai 2, câu t02 (truyện 24 `ngheo`, dòng 83):** "Chị Chuột nói mình vừa bán những thứ gì, và được bao nhiêu tiền?". Với A, chunk hạng 1 (dòng 69–83) bị cắt ở "…hai buồng chuối non được b", mất "bốn hào" nên evidence bị tách (grounding 1). Với B và C, chunk chứa câu này (`namcao-p024-para-005`, dòng 75–103) gồm 15 đoạn thoại ngắn (11–154 ký tự), xếp hạng 331/1.310; top-3 là các cảnh khác của *Nghèo* (dòng 143–151) và hai truyện khác (grounding 0). Câu t06 (truyện 52 `nhung-ban-tay-dep-ay`, dòng 45) trượt ở cả ba cấu hình, top-3 đều từ truyện *Trần Cừ* và *Từ ngược về xuôi*.
  - Kiểm tra độc lập: tính lại cosine thủ công trên toàn bộ vector trong DB cho kết quả top-3 trùng với kết quả đã lưu (A 24/24 câu; B 23/24, một câu chỉ khác thứ tự do hai chunk bằng điểm), và chấm lại Hit bằng một cách kiểm tra riêng khớp 100% với cờ đã lưu. Vậy các câu trượt là do xếp hạng truy xuất, không phải lỗi pipeline.
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:** chọn **B**, và dùng **C** khi có sẵn ngữ cảnh thời kỳ từ người dùng. Theo tiêu chí ở trên: Hit@3 dev của A và B bằng nhau (6/18) nên xét coherence (B 1,9 so với A 1,0), rồi tài nguyên (B ít chunk, nhanh hơn). B và C bằng nhau trên dev nên chọn B làm mặc định; C không tốn thêm chi phí nhưng chỉ có ý nghĩa khi người dùng cung cấp filter. Đánh đổi: B giữ trọn ý nhưng chunk dài có thể làm loãng vector (như t02); A cho chunk nhỏ, đều nhưng cắt ý. Kết quả chỉ áp dụng cho corpus và 24 câu này.
- **Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí:**
  - Dữ liệu: một tác giả, một ngôn ngữ; giấy phép chỉ là nhận định "được cho là"; không rõ bản in gốc; còn lỗi số hóa nhỏ; embedding trên tiếng Việt có thể yếu hơn tiếng Anh nhưng chưa được kiểm chứng.
  - Benchmark: 24 câu do cùng trợ lý dựng pipeline soạn nháp, chỉ 8/59 truyện có câu hỏi (51 truyện còn lại đóng vai nhiễu); câu thiên về chi tiết cụ thể (số tiền, đồ vật) và nhiều câu chung chung so với câu evidence. Test chỉ 6 câu (một câu lệch là 16,7 điểm phần trăm) và chỉ 1 câu filter; ba câu filter dùng đoạn gây nhiễu khá yếu (trừ t01). Hit đo bằng khớp nguyên văn evidence sau chuẩn hóa nên không tính bằng chứng tương đương (ví dụ chunk chứa một nửa evidence vẫn là trượt).
  - Nhãn: coherence chỉ 10 vị trí; tiêu chí điểm 1 và 2 mang tính chủ quan; người soạn nháp biết chunk thuộc A hay B.
  - Quy trình: tiêu chí chọn được viết sau khi đã thấy kết quả test; trước đó tác giả đã chạy một corpus khác (OpenStax tiếng Anh, nhánh `openstax-english`) rồi chuyển sang corpus này, nên kinh nghiệm đó có thể ảnh hưởng thiết kế. Chi phí từng chiến lược là ước tính theo ký tự; chưa đo thời gian truy vấn; tổng chi phí thực tế (≈ 0,07 USD) cao hơn lần chạy cuối.
- **Nếu làm lại hoặc mở rộng, cải tiến gì?** Viết lại các câu hỏi để có đủ ngữ cảnh phân biệt (tên nhân vật, cảnh) và thêm câu nhiều bước; thử B với giới hạn nhỏ hơn hoặc gộp lời thoại ngắn thông minh hơn để tránh chunk loãng; thử embedding đa ngữ hoặc lớn hơn, và truy xuất lai (BM25 kết hợp vector), chỉ chọn trên dev; mở rộng test và số câu filter với đoạn gây nhiễu mạnh hơn; đo riêng thời gian truy vấn và token từng chiến lược.

## Công cụ AI và cách kiểm tra
- **Công cụ AI:** hỗ trợ viết code. 
- **Cách kiểm tra:** chạy các script kiểm tra benchmark và dữ liệu, đối chiếu kết quả với file nguồn, và lấy số liệu trực tiếp từ các file trong results.
