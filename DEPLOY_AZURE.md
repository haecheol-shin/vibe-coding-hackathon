# Azure App Service 배포 가이드

## 1. 사전 준비
- Azure CLI 로그인: az login
- Azure Developer CLI 설치: azd version
- 구독 선택: az account set --subscription <구독ID 또는 구독명>

## 2. 환경 변수 확인
- .env.example 값을 참고해서 필요한 값을 채웁니다.

## 3. 배포 미리보기
- 인프라 변경사항 확인: azd provision --preview

## 4. 전체 배포
- 인프라 + 앱 배포: azd up

## 5. 배포 확인
- 출력된 URL의 /health 호출
- 예시: https://<app-url>/health

## 참고
- azd는 azure.yaml 과 infra/main.bicep 을 기준으로 배포합니다.
- 앱 시작 명령은 azure.yaml 의 startupCommand 를 사용합니다.
