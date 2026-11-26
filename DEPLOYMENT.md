# Deployment Information

## Public URL
https://<your-agent>.railway.app

## Platform
Railway (hoặc Render)

## Test Commands

### Health & Readiness Check
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://<your-agent>.railway.app/health"   # 200
curl -sS -o /dev/null -w '%{http_code}\n' "https://<your-agent>.railway.app/ready"    # 200
```

### API Test (401 without key, 200 with key)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://<your-agent>.railway.app/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'  # 401

curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://<your-agent>.railway.app/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'  # 200
```

## Environment Variables Set
- `PORT`
- `ENVIRONMENT`
- `REDIS_URL`
- `AGENT_API_KEY`
- `RATE_LIMIT_PER_MINUTE`
- `DAILY_BUDGET_USD`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
