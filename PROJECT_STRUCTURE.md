# Project Structure

이 저장소는 충돌을 줄이기 위해 프런트엔드와 백엔드 작업 공간을 분리합니다.

## Ownership

| 영역 | 담당 | 경로 |
|------|------|------|
| 백엔드 | Python/FastAPI 담당 | `backend/` |
| 프런트엔드 | Vue/JavaScript 담당 | `frontend/` |
| 배포 호환 진입점 | 백엔드 담당 | `main.py`, `requirements.txt`, `startup.sh` |
| API 계약 문서 | 백엔드 주도, 프런트와 공유 | `API.md` |

## Backend

백엔드 코드는 `backend/main.py`에 있습니다. 루트의 `main.py`는 Azure App Service와 기존 실행 명령을 깨지 않기 위한 얇은 호환 진입점입니다.

로컬 실행:

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

주요 엔드포인트:

- `GET /health`
- `POST /api/productivity/plan`
- `POST /api/productivity/coach`
- `POST /api/chat`
- `/copilotkit`

## Frontend

프런트엔드 정적 파일은 `frontend/`에 있습니다. 현재 FastAPI가 `/`에서 `frontend/index.html`을 반환하고, `/static/*`에서 `frontend/` 파일을 서빙합니다.

프런트 담당자는 가능한 한 아래 파일만 수정합니다.

- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

Vite/Vue 프로젝트로 확장할 때도 `frontend/` 안에서 진행하고, 백엔드 API 호출 계약은 `API.md`를 기준으로 맞춥니다.