# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
Trong `01-localhost-vs-production/develop/app.py` có các anti-pattern sau:
1. **Hardcode secrets trong source code** (dòng 17–18): `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`, `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Khi push lên GitHub sẽ lộ ngay lập tức.
2. **Không có config management** (dòng 21–22): `DEBUG = True`, `MAX_TOKENS = 500` bị gán cứng, không đọc từ biến môi trường theo từng môi trường (`dev`/`staging`/`prod`).
3. **Dùng `print()` thay vì structured logging và log ra secret** (dòng 33–34, 38): `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` vừa khó parse cho hệ thống log aggregator, vừa làm rò rỉ API key ra stdout/log.
4. **Không có health check endpoint (`/health`, `/ready`)** (dòng 42–43): Platform (Docker, Railway, Render, Kubernetes) không biết được process còn sống hay đã sẵn sàng nhận traffic.
5. **Cấu hình server cứng cho localhost** (dòng 49–54): `host="localhost"`, `port=8000`, `reload=True`. Trong container hoặc cloud (Railway/Render), app phải bind `0.0.0.0`, đọc `PORT` từ env và tắt `reload`.

### Exercise 1.2: Test bản develop
Lệnh chạy:
```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```
Kết quả:
```json
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 1.3: Comparison table
| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Why Important? |
|---|---|---|---|
| **Config & Secrets** | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG=True` (dòng 17–22) | Đọc từ biến môi trường qua `config.py` (`settings`) | Tránh lộ secret lên Git; dễ đổi cấu hình giữa dev/staging/prod mà không sửa code |
| **Logging** | `print()` plain text, in cả `OPENAI_API_KEY` (dòng 33–34) | `logging` format JSON, chỉ log metadata (`question_length`, `client_ip`), không log secret (dòng 28–32, 111–115) | Dễ tìm kiếm/lọc trên Datadog/Loki; tuân thủ bảo mật |
| **Health & Readiness** | Không có | Có `/health` (liveness) và `/ready` (readiness) | Cho phép load balancer/orchestrator tự restart khi lỗi và chỉ route traffic khi sẵn sàng |
| **Lifecycle / Shutdown** | Không có | Dùng `lifespan` context manager để khởi tạo và graceful shutdown (dòng 39–68) | Tránh cắt ngang request đang xử lý khi deploy hoặc restart |
| **Network Binding & Port** | `host="localhost"`, `port=8000`, `reload=True` (dòng 49–54) | `0.0.0.0` và đọc `PORT` từ env, tắt reload | Container/cloud yêu cầu bind `0.0.0.0` và nhận `PORT` động từ platform |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image:** `python:3.11` (bản full ~1 GB, chứa nhiều công cụ build không cần thiết khi chạy production).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Thứ tự `COPY requirements.txt` trước `COPY . .`:** Để tận dụng Docker layer cache. Khi chỉ sửa code (`app.py`), layer `pip install` không bị rebuild lại.
4. **Command mặc định:** `CMD ["python", "app.py"]`, expose port `8000`.

### Exercise 2.2: Test container `my-agent:develop`
```bash
docker run -d --rm --name test-p2-dev -p 8000:8000 my-agent:develop
curl -sS -X POST "http://localhost:8000/ask?question=Hello"
# {"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

### Exercise 2.3: Image size comparison (đo bằng `docker images`)
- **Develop (`my-agent:develop`):** `1.15GB` (1,150 MB)
- **Production (`my-agent:advanced`, multi-stage `python:3.11-slim`):** `163MB`
- **Difference:** Giảm **~85.8%** dung lượng (nhờ tách stage `builder` chứa `gcc` và chỉ copy gói đã cài sang stage `runtime` dùng `slim`).

### Exercise 2.4: Docker Compose stack (`02-docker/production/`)
- **Sơ đồ services:** `Client` → `nginx` (port 80, reverse proxy) → `agent` (FastAPI) → `redis` (cache/state) & `qdrant` (vector DB) trên internal network.
- **Kết quả test qua Nginx (`GET http://localhost:80/health`):**
```json
{"status":"ok","uptime_seconds":2.0,"version":"2.0.0","timestamp":"2026-11-26T09:23:16.347215"}
```

---

## Part 4: API Security

### Exercise 4.1–4.3: Test results (API Key, JWT & Rate Limiting)
**1. Bản develop (`AGENT_API_KEY=secret-key-123`) — thiếu key trả `401`, có key trả `200`:**
```http
=== 401 NO KEY ===
HTTP/1.1 401 Unauthorized
content-type: application/json

=== 200 WITH KEY ===
HTTP/1.1 200 OK
content-type: application/json
```

**2. Bản production — lấy JWT tại `POST /auth/token` (`student`/`demo123`) và test rate limit (10 req/phút):**
```text
req 1..10 -> 200
req 11    -> 429
```
Output `curl -i` khi vượt giới hạn (đã che token `Bearer <REDACTED>`):
```http
HTTP/1.1 429 Too Many Requests
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795685093
retry-after: 59
content-type: application/json
```

### Exercise 4.4: Cost guard implementation
- **Cách triển khai (`cost_guard.py`):** Trước khi gọi LLM, `check_budget(user_id)` kiểm tra tổng chi phí trong ngày của user (so với `daily_budget_usd`) và toàn hệ thống (so với `global_daily_budget_usd`). Nếu vượt ngưỡng user → trả `402 Payment Required`; vượt ngưỡng global → trả `503`. Sau khi LLM trả lời, `record_cost()` tính chi phí từ `input_tokens` và `output_tokens` rồi cộng dồn (trong production lưu vào Redis/DB).
- **Vì sao cần cả Rate Limit và Cost Guard:** Rate limit bảo vệ **tốc độ** (tránh spam/DDoS làm quá tải server), còn Cost Guard bảo vệ **ngân sách** (vì một request prompt dài có thể tốn rất nhiều token/tiền dù số lượng request ít).

---

## Part 5: Scaling & Reliability

### Exercise 5.1–5.5: Implementation notes & Stateless test
- **Liveness (`/health`) vs Readiness (`/ready`):**
  - `/health` kiểm tra process còn sống (luôn trả `200`, kể cả khi Redis tạm mất kết nối) để orchestrator không restart oan.
  - `/ready` kiểm tra các dependency như Redis (`503` khi mất kết nối) để Load Balancer tạm ngưng route traffic tới instance đó.
- **Vì sao state trong RAM bị hỏng khi scale nhiều instance:** Mỗi container có bộ nhớ RAM riêng. Khi Nginx round-robin request sang instance khác, instance mới không có lịch sử hội thoại trong RAM. Giải pháp là thiết kế **stateless** và đẩy state sang **Redis** dùng chung.
- **Kết quả chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` + `python test_stateless.py`:**
```text
Total requests: 5
Instances used: {'instance-667337', 'instance-c22de4', 'instance-c191bf'}
✅ All requests served despite different instances!
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

---

## AI Log
- Sử dụng AI hỗ trợ kiểm tra code mẫu, chạy lệnh test local và tổng hợp tài liệu `MISSION_ANSWERS.md`. Mọi kết quả chạy lệnh đều được thực thi và kiểm chứng trực tiếp trên máy.
