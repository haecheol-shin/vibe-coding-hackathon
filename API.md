# Backend API

백엔드는 Python/FastAPI로 제공하고, 프런트엔드는 Vue/JavaScript에서 이 API를 호출합니다.

백엔드 구현은 `backend/`에 있고, 프런트엔드 구현은 `frontend/`에 있습니다.

## Base URL

로컬 백엔드:

```text
http://127.0.0.1:8000
```

Azure 배포:

```text
https://vibe-copilot-mac-06201119.azurewebsites.net
```

## Health Check

```http
GET /health
```

응답:

```json
{"status":"ok"}
```

## Productivity Coach

Copilot SDK를 사용하는 개인 생산성 코치 API입니다.

```http
POST /api/productivity/coach
Content-Type: application/json
```

요청:

```json
{
  "request": "오늘 남은 작업을 기준으로 3단계 실행 계획을 만들어줘.",
  "energy": 3,
  "mood": "calm",
  "focus_sessions": 1,
  "tasks": [
    {"title": "발표 데모 흐름 정리", "priority": "high", "done": false},
    {"title": "Azure 배포 확인", "priority": "medium", "done": true}
  ]
}
```

응답:

```json
{
  "answer": "...",
  "model": "gpt-5",
  "open_tasks": 1,
  "completed_tasks": 1
}
```

`priority`는 `high`, `medium`, `low` 중 하나입니다. Copilot 사용을 위해 Azure App Service 또는 `.env`에 `COPILOT_GITHUB_TOKEN`이 필요합니다.

## Legacy Chat

기존 데모 화면 호환용 API입니다.

```http
POST /api/chat
Content-Type: application/json
```

```json
{
  "prompt": "오늘 계획을 짜줘",
  "context": "Energy: 3/5\nTasks:\n- [open] 발표 준비 (high)"
}
```