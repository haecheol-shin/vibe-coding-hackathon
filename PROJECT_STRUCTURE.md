# Project Structure

이 저장소는 FastAPI가 Vue 정적 화면과 API를 함께 서빙하는 웹앱 구조입니다.

## Feature Ownership

팀은 프런트엔드/백엔드 역할 분리가 아니라 기능 단위로 담당합니다.

| 영역 | 설명 | 경로 |
|------|------|------|
| 기능 구현 | 맡은 기능에 필요한 화면, API, 문서를 함께 수정 | `frontend/`, `backend/`, `API.md` |
| 배포 호환 진입점 | Azure App Service와 로컬 실행 호환 | `main.py`, `requirements.txt`, `startup.sh` |
| API 계약 문서 | 기능별 API 요청/응답 계약 공유 | `API.md` |

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

화면 수정이 필요한 기능 담당자는 아래 파일을 수정합니다.

- `frontend/index.html`
- `frontend/app.js`
- `frontend/styles.css`

Vite/Vue 프로젝트로 확장할 때도 `frontend/` 안에서 진행하고, API 호출 계약은 `API.md`를 기준으로 맞춥니다.