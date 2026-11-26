# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nguyễn Minh Đức (MSSV: 2A202603960)
**Ngày chạy:** 2026-11-26
**Môi trường:** Linux, Python 3.15.2, Docker 29.9.2 / Docker Compose 5.6.1

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Đảm bảo trải nghiệm phản hồi nhanh cho người dùng cuối; ở mức concurrency ≤ 50, p95 đạt ~318ms |
| Error rate `/ask` | ≤ 2.0 % | Cho phép sai số nhỏ từ mock/network transient error nhưng vẫn giữ độ tin cậy ≥ 98% |
| Accuracy trên golden dataset | ≥ 100 % | Đảm bảo không có regression trên 23 câu hỏi chuẩn trước khi merge/deploy |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.46 | 189.1 | 220.3 | 1700.0 | 0.67% | ✅ PASS |
| 10 | 38.34 | 196.5 | 240.1 | 1707.4 | 2.00% | ✅ PASS |
| 50 | 101.48 | 205.0 | 318.2 | 1703.8 | 1.00% | ✅ PASS |
| 100 | 55.07 | 490.4 | 3477.7 | 3869.6 | 0.33% | ❌ FAIL |

**Nhận xét:** RPS không tăng tuyến tính mãi theo concurrency. Từ c=1 → 50, RPS tăng mạnh (4.46 → 101.48 req/s) nhưng đến c=100 thì RPS tụt xuống 55.07 req/s và p95 vọt lên 3477.7 ms do nghẽn hàng đợi xử lý (saturation) trên 1 process uvicorn.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 193.6 | 224.2 | 237.3 |
| 0.03 (mặc định) | 272.4 | 309.7 | 1703.4 |
| 0.1 | 333.7 | 1692.3 | 1719.2 |

**Nhận xét:** `p95` và `p99` nhạy nhất với request chậm (khi `MOCK_SLOW_RATE=0.1`, `p95` nhảy từ 224.2 ms lên 1692.3 ms). `average` che giấu tail latency vì 90% request nhanh kéo trung bình xuống (~333.7 ms), nên SLO phải đặt theo `p95`/`p99`.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.4 | 109.1 | 113.4 |
| Tổng cost (USD) | $0.000409 | $0.000762 | $0.000789 |
| Cost / câu đúng (USD) | $0.00040875 | $0.00003627 | $0.00003429 |
| Quality gate | ❌ FAIL | ✅ PASS (≥80%) | ✅ PASS (100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt", "xác thực"], ...)` vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["hpa", "kubernetes hpa"], ...)` vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
- v2 tốn nhiều token hơn (~113.4 vs 57.4 tokens/câu) và latency nhỉnh hơn (~203ms vs ~167ms), nhưng accuracy tăng từ 4.3% lên 100% nên **cost / câu đúng** giảm mạnh (~12 lần: từ `$0.00040875` xuống `$0.00003429`).
- **Chặn merge trong CI:** Chạy `python eval/run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json`. Nếu accuracy < ngưỡng hoặc có câu regression, script trả về **exit code 1**, làm step CI fail và chặn merge PR.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) — `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) — `screenshots/jaeger-slow-trace.png`
- [ ] Một trace lỗi trong Jaeger (có event `exception`) — `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với alert đang **firing** — `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Chạy eval định kỳ trên golden dataset (CI/CD quality gate hoặc canary eval) và theo dõi chỉ số chất lượng / feedback người dùng, vì Prometheus chỉ đo infrastructure/Golden Signals (latency, traffic, errors, saturation) chứ không đo độ đúng ngữ nghĩa của câu trả lời.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `e14009fdc4ad2e56526dd6884b0506ba`
- Tổng thời gian: `308 ms`
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`183 ms`, `59.4%`)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 65.31 | 190 | 310 | 1700 | 78 (1.00%) |
| 3 | 65.27 | 200 | 390 | 1700 | 70 (0.90%) |

**Giải thích kết quả:** Scale lên 3 instance không làm tăng RPS hay giảm p95 vì tải 100 users với `locustfile` có `wait_time` đang bị giới hạn bởi tốc độ sinh tải của Locust / độ trễ giả lập cố định của `mock_llm` (~200ms/request), chưa chạm ngưỡng bão hòa CPU của 1 instance.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Latency trung bình che giấu tail latency; SLO phải đặt theo p95/p99.
  2. Quality gate bằng golden dataset + exit code giúp chặn regression tự động trong CI.
  3. Kết hợp Metrics (Prometheus/Grafana) + Traces (Jaeger) + Structured Logs (`trace_id`) giúp debug nguyên nhân gốc rễ nhanh hơn.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Alert theo dõi **cost / giờ** (budget burn rate), **Redis memory/connection**, và **token usage per user**.
