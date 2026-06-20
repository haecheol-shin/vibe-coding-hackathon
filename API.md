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

## User Profile Summary

사용자 정보 기능의 백엔드 계약입니다. 이름, 여러 가용 시간대, 코스피 투자 여부를 받아 총 가용 시간을 계산합니다.

```http
POST /api/user-profile/summary
Content-Type: application/json
```

요청:

```json
{
  "name": "민수",
  "availability_windows": [
    {"start": "09:00", "end": "10:00"},
    {"start": "14:00", "end": "16:30"}
  ],
  "invests_in_kospi": true
}
```

응답:

```json
{
  "user_profile": {
    "name": "민수",
    "availability_windows": [
      {"start": "09:00", "end": "10:00"},
      {"start": "14:00", "end": "16:30"}
    ],
    "available_minutes": 210,
    "usage_minutes": 210,
    "invests_in_kospi": true
  },
  "total_available_minutes": 210,
  "availability_summary": "09:00-10:00 (1h 0m), 14:00-16:30 (2h 30m)",
  "invests_in_kospi": true
}
```

자정을 넘기는 시간대도 지원합니다. 예를 들어 `22:00`부터 `01:00`까지는 `180`분으로 계산합니다.

## Authenticated User Profile

GitHub OAuth 로그인 후 현재 사용자의 기본 정보를 조회합니다.

```http
GET /api/users/profile
```

로그인 세션이 없으면 `401`을 반환합니다. 로컬 개발에서는 GitHub OAuth 환경 변수가 없을 때 `gh auth login` 토큰을 사용한 로컬 인증 흐름을 지원합니다.

## Productivity Plan

CopilotKit 액션과 같은 사용자 정보 계약을 사용하는 생산성 계획 API입니다.

```http
POST /api/productivity/plan
Content-Type: application/json
```

요청:

```json
{
  "tasks": [
    {"title": "발표 데모 흐름 정리", "duration_minutes": 60, "block_count": 2},
    {"title": "배포 확인", "duration_minutes": 30, "block_count": 1}
  ],
  "user_profile": {
    "name": "민수",
    "availability_windows": [
      {"start": "09:00", "end": "10:00"},
      {"start": "14:00", "end": "16:30"}
    ],
    "invests_in_kospi": true
  }
}
```

응답에는 정규화된 `user_profile`, 30분 단위로 자동 배분된 `focus_blocks`, `next_action`, `copilot_note`가 포함됩니다. `tasks`는 오늘의 투두 리스트이며 각 항목은 작업명 `title`과 소요 시간 `duration_minutes` 또는 블록 수 `block_count`를 보낼 수 있습니다. 한 블록은 30분입니다.

`focus_blocks`는 사용자의 `availability_windows`를 기준으로 `start_time`, `end_time`, `time_range`를 함께 반환합니다. 시간대는 단순히 빠른 순서가 아니라, 오전 집중 시간대와 오후 안정 시간대를 우선하는 추천 점수로 최적화됩니다. 코스피 투자 중이면 장 시작 직후 시간은 집중 블록에서 살짝 뒤로 미룹니다.

```json
{
  "label": "Block 1",
  "minutes": 30,
  "task": "발표 데모 흐름 정리",
  "start_time": "09:00",
  "end_time": "09:30",
  "time_range": "09:00-09:30"
}
```

## Daily Diary

오늘의 일기와 오늘의 기분 점수를 입력받는 API입니다.

```http
POST /api/diaries/today
Content-Type: application/json
```

요청:

```json
{
  "content": "오늘은 집중이 잘 됐지만 오후에는 조금 지쳤다.",
  "mood_score": 7
}
```

응답:

```json
{
  "entry_id": "...",
  "entry_date": "2026-06-20",
  "created_at": "2026-06-20T13:30:00",
  "headline": "오늘은 집중이 잘 됐지만 오후에는 조금 지쳤다.",
  "content": "오늘은 집중이 잘 됐지만 오후에는 조금 지쳤다.",
  "mood_score": 6.87,
  "base_mood_score": 7,
  "kospi_change_rate": -0.13,
  "adjusted_by_kospi": true,
  "mood_sample_count": 3,
  "message": "Diary and KOSPI-adjusted mood score saved."
}
```

저장된 원본 일기는 계속 누적됩니다. `POST /api/diaries/today`와 `GET /api/diaries/today` 응답의 `mood_score`는 오늘 입력된 기분 점수들의 최종 평균이며, `base_mood_score`는 사용자가 입력한 기본 기분 점수들의 평균입니다. 각 원본 입력값은 기본 점수에 KOSPI 최신 등락률(`kospi_change_rate`)을 더하거나 뺀 뒤 `1`부터 `10` 사이로 제한됩니다.

오늘 저장된 일기를 조회할 수 있습니다.

```http
GET /api/diaries/today
```

저장된 오늘 일기가 없으면 `404`를 반환합니다.

감정 차트와 일기 보관함에서 사용할 전체 일기 목록을 조회할 수 있습니다.

```http
GET /api/diaries
```

응답은 최신 작성 시각 순서의 원본 `DiaryEntry` 배열입니다. 일기는 저장할 때마다 누적되며, 프런트엔드는 이 목록을 주식 뉴스 피드처럼 표시합니다. 기분 차트는 이 원본 목록을 날짜별로 묶어 평균 점수를 사용합니다. MVP 데모를 위해 서버 시작 시 최근 기분 점수 목 데이터가 기본 제공됩니다. MVP에서는 서버 메모리에 일기를 보관하며, 서버 재시작 시 초기화됩니다.

## KOSPI Market Chart

KOSPI 차트에 사용할 최근 지수 데이터를 조회하는 API입니다.

```http
GET /api/markets/kospi
```

응답:

```json
[
  {
    "trading_date": "2026-06-19",
    "close": 9052.42,
    "change": -11.42,
    "change_rate": -0.13
  }
]
```

백엔드는 `pykrx`로 KOSPI 지수 티커 `1001`의 최근 데이터를 조회합니다. `pykrx` 지수 조회가 빈 데이터를 반환하는 환경에서는 가짜 데이터나 보조 시세 소스로 대체하지 않고 `503` 오류를 반환합니다. 응답은 서버에서 일 단위로 캐시합니다.

## Productivity Coach

Copilot SDK를 사용하는 개인 생산성 코치 API입니다. 프런트엔드는 오늘의 투두, 가용 시간, 일기, 기분 점수, KOSPI 맥락을 `request`에 합쳐 전달하고, 코치 응답을 화면의 Copilot 코치 탭에 표시합니다.

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
  "user_profile": {
    "name": "민수",
    "availability_windows": [
      {"start": "09:00", "end": "10:00"},
      {"start": "14:00", "end": "16:30"}
    ],
    "invests_in_kospi": true
  },
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
  "model": "auto",
  "open_tasks": 1,
  "completed_tasks": 1
}
```

`request`는 최대 6000자이며, `priority`는 `high`, `medium`, `low` 중 하나입니다. Copilot 사용을 위해 Azure App Service 또는 `.env`에 `COPILOT_GITHUB_TOKEN`이 필요합니다.

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