# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

## 1. Thông tin học viên

- **Họ và tên:** Trần Gia Thành
- **MSSV:** 2A202602626
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/GTee2004/K4-L3-DAY13-TranGiaThanh-2A202602626-Monitoring-LLMOps
- **Commit SHA hiện tại:** `4e8744f0ecfb1cd15d4fc0851501c298e870be21`
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602626`

## 2. Evidence index

| Evidence | Đường dẫn tương đối |
|---|---|
| Pytest cuối | [01-pytest.png](evidence/01-pytest.png) |
| Log validator | [02-log-validator.png](evidence/02-log-validator.png) |
| Dashboard validator | [03-dashboard-validator.png](evidence/03-dashboard-validator.png) |
| Structured log | [04-structured-log.png](evidence/04-structured-log.png) |
| PII redaction | [05-pii-redaction.png](evidence/05-pii-redaction.png) |
| Trace list | [06-trace-list.png](evidence/06-trace-list.png) |
| Trace waterfall | [07-trace-waterfall.png](evidence/07-trace-waterfall.png) |
| Trace metadata | [08-trace-metadata.png](evidence/08-trace-metadata.png) |
| Prompt versions | [09-prompt-versions.png](evidence/09-prompt-versions.png) |
| Prompt rollback | [10-prompt-rollback.png](evidence/10-prompt-rollback.png) |
| Dashboard runtime | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metric | [12-incident-metric.png](evidence/12-incident-metric.png) |
| Incident log | [13-incident-log.png](evidence/13-incident-log.png) |
| Incident trace | [14-incident-trace.png](evidence/14-incident-trace.png) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---:|---:|---|
| `validate_logs.py` | 30/100 | **100/100** | Đủ JSON schema, enrichment, correlation ID và không phát hiện PII leak |
| `validate_dashboard.py` | 6/6 | **6/6** | Đúng dashboard contract gồm sáu panel |
| `pytest` | 22 passed | **31 passed** | Toàn bộ test pass; chỉ có cảnh báo quyền ghi `.pytest_cache`, không ảnh hưởng kết quả |
| Số trace hợp lệ | 10 yêu cầu tối thiểu | **≥55 trace tree đầy đủ** | Evidence hiển thị 75 root agent, 55 retrieval và 55 generation |
| Số PII leak | 0 | **0** | Validator không phát hiện leak; trace PII test hiển thị đủ bốn marker redaction |
| Latency P95 / TTFT P95 | 1037 ms / 50 ms | **153 ms / 50 ms** | Baseline lấy từ dashboard/log, kết quả cuối lấy từ 10 response trong JSONL, không dùng latency client |
| Retrieval success rate | 100% | **100% (10/10)** | Tính trên mọi event có field `tool_success` |

Baseline mở rộng dùng khi đặt SLO trong `config/slo.yaml` là latency P95 khoảng `1042 ms`, TTFT P95 `50 ms`, error rate `0%` và retrieval success `100%`. Chênh lệch nhỏ với ảnh dashboard (`1037 ms`) đến từ cửa sổ log và số mẫu tại thời điểm đo.

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware gọi `clear_contextvars()` ở đầu request, nhận `x-request-id` từ client hoặc sinh `req-` cộng 8 ký tự hexadecimal viết thường. ID được bind vào structured logger, lưu tại `request.state`, truyền vào `LabAgent`, Langfuse metadata và trả lại bằng response header `x-request-id`. Header `x-response-time-ms` chứa thời gian xử lý server; context được dọn trong `finally`.
- **Các metadata được ghi vào structured log:** `ts`, `level`, `event`, `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`; event `response_sent` còn có `latency_ms`, `ttft_ms`, token, cost, quality và trạng thái retrieval.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` được đăng ký trước JSON renderer/file writer. Scrubber duyệt đệ quy message, metadata, dictionary/list/tuple và che email, điện thoại Việt Nam, CCCD 12 chữ số, thẻ thanh toán 13–19 chữ số. `user_id` chỉ xuất hiện dưới dạng SHA-256 rút gọn ổn định `user_id_hash`.
- **Cách kiểm chứng kết quả:** Gửi request có email, điện thoại, CCCD và thẻ giả; log chỉ còn `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, `[REDACTED_CREDIT_CARD]`. `validate_logs.py` đạt `100/100`, PII tests pass và response trả đúng hai header quan sát được trong evidence 04–05.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Evidence 06 hiển thị project `day13-k4-l3b-2A202602626`, tài khoản cá nhân và danh sách workload do tôi chạy; số lượng root observations lớn hơn yêu cầu 10 traces.
- **Cấu trúc root/retrieval/generation observations:** Trace có root `lab-agent-run` loại agent; hai child observations là `retrieval` loại retriever và `generation` loại generation. Cả ba decorator đều tắt tự động capture raw input/output để tránh đưa PII lên Langfuse.
- **Cách nối trace với log:** `correlation_id` được truyền từ middleware vào agent, retrieval và generation metadata. Khi điều tra, lấy `correlation_id` từ `data/logs.jsonl`, lọc đúng trace trên Langfuse rồi so sánh các span.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** Version 3, labels `baseline` và `production` tại thời điểm baseline.
- **Version/label candidate:** Version 4, labels `candidate` và `latest`; được promote sang `production` để so sánh.
- **Trace ID của mỗi version:** Baseline v3: `444041f633720e0d79773b5cf64879e6`; candidate v4: `6c09dffd0443d10e6ec53d99590ac762`.
- **Cách promote và rollback `production`:** Chuyển label `production` từ version 3 sang version 4 để promote, chạy lại cùng workload và kiểm tra trace/prompt version. Sau đó chuyển `production` từ version 4 về version 3 để rollback. Trong evidence 10, khung dưới là trạng thái trước rollback (`production` ở v4), khung trên là trạng thái sau rollback (`production` trở lại v3).
- **An toàn dữ liệu trace:** `capture_input=False` và `capture_output=False` ngăn SDK tự gửi prompt/answer thô. Metadata chỉ chứa giá trị vận hành an toàn; query preview được scrub trước khi gửi. Evidence 08 cho thấy cả bốn loại PII đều đã redacted.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard đọc `data/logs.jsonl`, dùng cửa sổ UTC 60 phút và tự refresh mỗi 30 giây. Sáu panel gồm Latency (P50/P95/P99 và TTFT P95), Traffic, Errors + Retrieval success, Cost, Input/Output tokens và Quality proxy. Mỗi panel có tên, đơn vị, dữ liệu và threshold line; evidence 11 hiển thị đầy đủ sáu panel.
- **SLO và lý do chọn:** `99.5%` request trong mỗi cửa sổ 10.000 request phải có `response_sent` và latency không quá `3000 ms`. Baseline P95 khoảng `1042 ms`, nên ngưỡng 3000 ms tạo headroom cho biến động bình thường nhưng vẫn phát hiện tail latency nghiêm trọng. Cửa sổ theo số request phù hợp workload lab nhỏ và không liên tục.
- **Cách tính error budget:** Error budget là `100% - 99.5% = 0.5%`. Với 10.000 request: `10,000 × 0.005 = 50`; tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms, và ít nhất 9950 request phải đạt SLO.
- **Ba alert và runbook tương ứng:**
  1. `HighLatencyOrTTFT` — warning khi latency P95 > 3000 ms hoặc TTFT P95 > 1000 ms liên tục 5 phút; runbook `docs/alerts.md#alert-1`.
  2. `ErrorsOrRetrievalDegradation` — critical khi error rate > 2% hoặc retrieval success < 90% liên tục 5 phút; runbook `docs/alerts.md#alert-2`.
  3. `CostOrQualityDegradation` — warning khi daily cost > 2.50 USD hoặc quality trung bình < 0.75 liên tục 10 phút; runbook `docs/alerts.md#alert-3`.

Các alert đều symptom-based, owner `student-2A202602626`, gửi tới Slack `#k4-l3b-alerts`; runbook đi theo Metrics → Logs → Traces rồi mới mitigation và prevention.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`.
- **Khoảng thời gian điều tra:** `2026-09-30 05:56:27–05:56:38 UTC`, tương ứng `12:56:27–12:56:38` giờ Việt Nam.
- **Triệu chứng từ metrics:** Panel Latency tăng lên P50 `2653 ms`, P95 `2654 ms`, P99 `2654 ms`, trong khi TTFT P95 vẫn `50 ms`. So với baseline dashboard P95 `1037 ms`, tail latency tăng khoảng `2.56 lần` và vượt ngưỡng challenge `2000 ms`. Error rate vẫn 0% và retrieval success vẫn 100%, nên đây là degradation về thời gian chứ không phải request/retrieval failure.
- **Log line và correlation ID liên quan:** Chọn event `response_sent` lúc `2026-09-30T05:56:30.008204Z`, `correlation_id=req-52bcbd1d`, session `k4-l3b-challenge-s02`, `latency_ms=2652`, `ttft_ms=50`, `tool_success=true`.
- **Trace ID và span gây ảnh hưởng:** Trace `5c045dcda00ad6d418165a7a4feb916f` có cùng `correlation_id=req-52bcbd1d`. Root `lab-agent-run` mất khoảng `2.65 s`; child `retrieval` mất `2.50 s`; child `generation` chỉ mất `0.15 s`. Các span không có trạng thái lỗi.
- **Root cause:** Retrieval bị tăng latency. Span retrieval chiếm khoảng 94% tổng thời gian request, trong khi generation, TTFT, token/cost và trạng thái tool không có dấu hiệu bất thường. Vì vậy nguyên nhân nằm ở đường retrieval chậm, không phải LLM generation hay hàng đợi phía client.
- **Fix action:** Tắt incident bằng `python scripts/inject_incident.py --disable`, chạy lại workload và xác nhận latency P95 trở về baseline. Trong môi trường production, giảm tải hoặc bật fallback trong lúc khôi phục retrieval configuration/dịch vụ về last-known-good.
- **Preventive measure:** Theo dõi riêng retrieval span latency và bổ sung alert khi retrieval P95 > 2000 ms liên tục 5 phút; đặt timeout, bounded retry, circuit breaker/fallback cho retrieval; thêm regression/load test để chặn rollout làm retrieval latency vượt baseline.

Chuỗi bằng chứng nhất quán là: Latency P95 `2654 ms` trên evidence 12 → log có `correlation_id=req-52bcbd1d` trên evidence 13 → trace cùng correlation ID cho thấy retrieval `2.50 s` trên evidence 14.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Tắt capture input/output ở mọi Langfuse observation và chỉ cập nhật metadata an toàn, vì prompt và câu trả lời có thể chứa PII. Managed prompt object vẫn được gắn trực tiếp vào generation để Langfuse liên kết đúng prompt version mà không gửi chuỗi prompt đã compile.
- **Một lỗi/blocker đã gặp:** Regex điện thoại ban đầu không che số điện thoại giả khi ngay sau nó là một CCCD cách bằng khoảng trắng. Negative lookahead đã coi chữ số của CCCD là phần tiếp tục của số điện thoại.
- **Cách tìm nguyên nhân và xử lý:** Dùng đúng chuỗi PII trong evidence để tái hiện, kiểm tra output `scrub_text`, sửa boundary cuối pattern thành `(?!\d)` và thêm regression test chứa đồng thời email, điện thoại, CCCD và thẻ. Sau sửa, output chỉ còn bốn marker redaction và toàn bộ 31 tests pass.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics xác định triệu chứng và khung giờ; logs chọn một request cụ thể bằng correlation ID; trace cùng correlation ID so sánh thời gian/trạng thái các span để khoanh vùng nguyên nhân. Không dùng latency client khi concurrency tạo hàng đợi và không mở trace ngẫu nhiên.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version giúp liên kết thay đổi hành vi với một release cụ thể; token/cost phát hiện prompt hoặc output phình bất thường; SLO/error budget định lượng mức chất lượng được chấp nhận; rollback đưa production về phiên bản last-known-good khi candidate gây regression.
- **Điều quan trọng nhất đã học:** Observability có giá trị khi metric, log và trace dùng chung context/correlation ID, đồng thời telemetry phải an toàn PII. Một dashboard đẹp nhưng không nối được tới request và span cụ thể thì chưa đủ để điều tra incident.
- **Hạn chế hoặc phần chưa hoàn thành:** Chưa cập nhật SHA sau commit cuối và chưa nộp URL/SHA lên LMS. Trước khi commit cần crop thông tin tài khoản cá nhân/public key không cần thiết khỏi screenshot Langfuse, rồi chạy lại tests và validators trên đúng commit nộp.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.