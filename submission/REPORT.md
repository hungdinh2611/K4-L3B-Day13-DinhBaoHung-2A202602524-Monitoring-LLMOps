# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Dinh Bao Hung
- **MSSV:** 2A202602524
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/hungdinh2611/K4-L3B-Day13-DinhBaoHung-2A202602524-Monitoring-LLMOps
- **Commit SHA cuối:** Chưa commit các thay đổi CP1–CP4 trong phiên này; cập nhật sau commit cuối.
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602524`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | CP3 baseline: 100/100 | CP3 sau challenge: 100/100 | 0 PII leak; không thiếu required/enrichment fields |
| `validate_dashboard.py` | 6/6 hợp lệ | 6/6 hợp lệ | Runtime có đủ sáu panel, ngưỡng và tự refresh |
| `pytest` | CP2: 30 passed | CP4 final: 30 passed | Chạy `python -m pytest -q` sau các thay đổi CP3 |
| Số traces hợp lệ | 10 baseline | 10 baseline + các trace prompt/incident | Trace baseline có đủ retrieval và generation child observations |
| Số PII leak | 0 | 0 | Log validator và test scrubber |
| Latency P95 / TTFT P95 | 691.6 ms / 50 ms (10 CP3 baseline responses) | 2651.8 ms / 50 ms (5 challenge responses) | Challenge threshold: 2000 ms; P95 tăng khoảng 3.8 lần |
| Retrieval success rate | 100% | 100% | Tính trên mọi log record có `tool_success`, gồm success và failure |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware chấp nhận `x-request-id` đúng mẫu `req-` + 8 ký tự hex; nếu thiếu/sai định dạng thì sinh ID mới. ID được bind vào structlog, gửi vào trace metadata và trả trong header `x-request-id`.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env`, `correlation_id`, timestamp và event; response có latency, TTFT, token, cost, quality và trạng thái retrieval.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` xử lý đệ quy các chuỗi trong event trước JSONL writer/renderer; preview còn dùng `summarize_text`. Có pattern email, số điện thoại VN, CCCD và thẻ.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100, 0 PII leak; test và request mẫu xác nhận cả bốn kiểu PII được redact.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Traces được xem và truy vấn từ project `day13-k4-l3b-2A202602524`; baseline CP3 có 10 root trace riêng theo session.
- **Cấu trúc root/retrieval/generation observations:** `day13-agent-request` là trace name; root `lab-agent-run` có child `retrieval` kiểu retriever và `generation` kiểu generation. Input/output không capture.
- **Cách nối trace với log:** Metadata của root chứa `correlation_id`; kiểm tra khớp giữa log và trace trước khi phân tích span.
- **Prompt name:** `day13-chat` (text prompt)
- **Version/label baseline:** v1 / `baseline` (version 1 cũng đã được gắn `production` sau rollback)
- **Version/label candidate:** v2 / `candidate`
- **Trace ID của mỗi version:** baseline v1 `769d3384d1e82aafedc399502e1af8e5`; candidate v2 `0fdbf97ae84644ca7564f895567a3a2b`
- **Cách promote và rollback `production`:** Đã chuyển `production` sang v2; trace `8bd46e2a1ff5c3867aff60691b4f4abd` xác nhận `prompt_version=2`. Sau đó rollback `production` về v1; trace `694ac55d0b852f855af9760779fed609` xác nhận `prompt_version=1`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard local đọc 60 phút log gần nhất, refresh 30 giây, hiển thị latency P50/P95/P99 và TTFT P95, traffic, error rate/retrieval success, cost, token và quality proxy cùng threshold.
- **SLO và lý do chọn:** `fast_successful_requests` đặt mục tiêu 99.5% trong 28 ngày cho request thành công trong 3000 ms; ngưỡng phù hợp mức latency cần giữ cho API.
- **Cách tính error budget:** 100% - 99.5% = 0.5%; với workload giả định 10,000 request, budget là tối đa 50 request không đạt SLO.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (P95 > 3000 ms/5m), `ElevatedRequestErrorRate` (>2%/5m), `LowQualityProxy` (mean <0.75/10m); từng alert có owner, Slack channel và runbook Metrics → Logs → Traces trong `docs/alerts.md`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 2026-09-30 04:53:03Z–04:53:14Z (11:53:03–11:53:14 giờ Việt Nam).
- **Triệu chứng từ metrics:** 10 request baseline có P95 latency 691.6 ms và TTFT P95 50 ms. Trong 5 challenge request, latency P95 là 2651.8 ms; cả 5 đều vượt challenge threshold 2000 ms. TTFT P95 vẫn 50 ms. Đây là latency `latency_ms` trong log, không phải client wall time.
- **Log line và correlation ID liên quan:** `response_sent` lúc `2026-09-30T04:53:03.485377Z`, `correlation_id=req-be9298ec`, `latency_ms=2651`, `ttft_ms=50`.
- **Trace ID và span gây ảnh hưởng:** Trace `38975c2cc8e12e94a9cad87a996ed178`, cùng `correlation_id=req-be9298ec`. Root `lab-agent-run` kéo dài 2.652 s; child `retrieval` kéo dài 2.501 s; child `generation` kéo dài 0.151 s.
- **Root cause:** Incident challenge bật độ trễ ở retrieval. Span retrieval chiếm gần như toàn bộ latency tăng; generation và TTFT vẫn ở mức baseline.
- **Fix action:** Tắt incident challenge; `/health` xác nhận cả `rag_slow`, `tool_fail`, `cost_spike` đều `false`.
- **Preventive measure:** Duy trì cảnh báo P95 > 3000 ms, runbook truy theo correlation ID từ log sang trace, và xác nhận health/incident state sau khi kết thúc practice.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Tắt capture input/output trong root và generation để tránh lưu câu hỏi/câu trả lời có thể chứa PII; vẫn giữ model, token/cost và prompt version để chẩn đoán.
- **Một lỗi/blocker đã gặp:** Cổng API mặc định 8000 không thuộc tiến trình CP2 hiện tại. Hai script load/inject ban đầu hard-code cổng này.
- **Cách tìm nguyên nhân và xử lý:** Xác định API CP2 đang chạy không reload ở cổng 8001, thêm `API_BASE_URL` với mặc định tương thích 8000 vào hai script và dùng biến này cho CP3.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metric chỉ ra thời điểm và độ lớn latency tăng; log chọn request cụ thể bằng correlation ID; trace so sánh thời lượng retrieval và generation để xác định retrieval là nguyên nhân.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version xác định cấu hình đã chạy và cho phép rollback; token/cost theo dõi tiêu thụ; SLO/error budget lượng hóa mức độ chấp nhận được của latency/lỗi.
- **Điều quan trọng nhất đã học:** Không suy root cause từ status HTTP hoặc client latency đơn lẻ; cần ba lớp evidence khớp trên cùng request/time window.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Chưa commit thay đổi nên chưa có SHA cuối; evidence ảnh 01 và 12–14 còn cần chụp/lưu sau khi chạy test cuối và khi xem lại dashboard/trace trên UI.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
