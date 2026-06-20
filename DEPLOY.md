# Azure 배포

이 프로젝트는 FastAPI 웹 앱이며 Azure App Service 배포를 기본 경로로 사용합니다.

## 1. 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn main:app --reload
```

`.env`의 `COPILOT_GITHUB_TOKEN`에는 GitHub Copilot SDK가 사용할 토큰을 넣습니다. 토큰은 커밋하지 않습니다.

## 2. Azure App Service 배포

```bash
az login
az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION"
az webapp up \
  --name "<unique-app-name>" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --location "$AZURE_LOCATION" \
  --runtime "PYTHON:3.11" \
  --sku B1
az webapp config set \
  --name "<unique-app-name>" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --startup-file "startup.sh"
az webapp config appsettings set \
  --name "<unique-app-name>" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --settings COPILOT_GITHUB_TOKEN="<token>" COPILOT_MODEL="gpt-5" CORS_ORIGINS="https://<frontend-app>.azurestaticapps.net,http://localhost:5173"
```

배포 후 `https://<unique-app-name>.azurewebsites.net/health`가 `{"status":"ok"}`를 반환하면 웹 앱이 올라온 상태입니다.