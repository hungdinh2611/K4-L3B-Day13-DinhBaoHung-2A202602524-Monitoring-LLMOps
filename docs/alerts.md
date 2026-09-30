# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests`, ngưỡng latency 3000 ms
- Điều kiện và thời gian duy trì: P95 của `response_sent.latency_ms` lớn hơn 3000 ms liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời đến muộn dù request có thể vẫn trả HTTP 200.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** so sánh P50/P95/P99 và TTFT với baseline trong cửa sổ 60 phút; xác định thời điểm P95 vượt 3000 ms.
  2. **Logs:** lọc `response_sent` trong khoảng đó, chọn `latency_ms` cao và ghi lại `correlation_id`.
  3. **Traces:** mở trace cùng `correlation_id`, so sánh thời lượng `retrieval` và `generation` để định vị bước chậm.
- Mitigation tạm thời: nếu trace cho thấy prompt version mới làm tăng generation latency, chuyển label `production` về version ổn định; nếu retrieval chậm, giảm tải hoặc khôi phục dịch vụ retrieval sau khi xác minh.
- Owner: `student-2A202602524`

## Alert 2

- Tên: `ElevatedRequestErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ request lỗi phải không quá 2%.
- Điều kiện và thời gian duy trì: `request_failed / request_received` lớn hơn 2% liên tục 5 phút.
- Ảnh hưởng tới người dùng: người dùng nhận lỗi thay vì câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** xác nhận error rate và retrieval success trong cùng khoảng thời gian; so sánh với baseline gần nhất.
  2. **Logs:** nhóm `request_failed` theo `error_type` và `tool_success`; lấy `correlation_id` của một lỗi đại diện.
  3. **Traces:** mở trace cùng `correlation_id`, xem span `retrieval` và `generation` để xác định span lỗi hoặc bị thiếu.
- Mitigation tạm thời: nếu lỗi tập trung ở retrieval, giảm tải hoặc tạm dừng thay đổi retrieval; nếu vừa đổi prompt/version, rollback label `production`; xác nhận error rate giảm sau mitigation.
- Owner: `student-2A202602524`

## Alert 3

- Tên: `LowQualityProxy`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: quality proxy trung bình tối thiểu 0.75.
- Điều kiện và thời gian duy trì: trung bình `response_sent.quality_score` thấp hơn 0.75 liên tục 10 phút.
- Ảnh hưởng tới người dùng: câu trả lời có thể thiếu context hoặc không phù hợp dù request vẫn thành công.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** xác nhận mean quality proxy dưới 0.75 và kiểm tra đồng thời retrieval success, tokens và latency.
  2. **Logs:** chọn các `response_sent` trong khoảng đó, đối chiếu `feature`, token count và `correlation_id`; không dùng raw message/answer làm bằng chứng.
  3. **Traces:** mở trace cùng `correlation_id`, kiểm tra số tài liệu ở retrieval và metadata `prompt_name`, `prompt_label`, `prompt_version`.
- Mitigation tạm thời: rollback prompt production về version đã kiểm tra; nếu retrieval success thấp, khôi phục retrieval trước khi đánh giá lại chất lượng.
- Owner: `student-2A202602524`
