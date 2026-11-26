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

## AI Log
- Sử dụng AI hỗ trợ kiểm tra code mẫu, chạy lệnh test local và tổng hợp tài liệu `MISSION_ANSWERS.md`. Mọi kết quả chạy lệnh đều được thực thi và kiểm chứng trực tiếp trên máy.
