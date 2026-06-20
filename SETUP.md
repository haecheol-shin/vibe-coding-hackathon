# 바이브코딩 대회 — VS Code 세팅 가이드 (Windows)

팀원용 문서입니다. **Windows + VS Code** 기준으로, 음성 코딩 + GitHub Copilot Agent + Azure 배포까지 대회 당일 쓸 환경을 맞추는 방법을 정리했습니다.

## 현재 MVP 실행

개인 생산성 웹앱 MVP는 Python/FastAPI 백엔드가 Vue.js 정적 화면과 CopilotKit SDK 엔드포인트를 함께 서빙합니다.

```powershell
pip install -r requirements.txt
uvicorn main:app --reload
```

- 웹앱: `http://127.0.0.1:8000/`
- 헬스체크: `http://127.0.0.1:8000/health`
- CopilotKit SDK 엔드포인트: `http://127.0.0.1:8000/copilotkit`
- 프런트엔드: Vue.js CDN 기반 MVP. Node.js 설치 후 Vite Vue 구조로 확장 예정.

> 팀 리더가 미리 만들어 둔 공용 프로젝트(`vibe-coding-hackathon`)를 clone하면 `.vscode/` 설정(MCP, 음성, Agent)이 자동으로 따라옵니다.

---

## 목차

1. [필수 계정·구독](#1-필수-계정구독)
2. [설치할 프로그램 (Windows)](#2-설치할-프로그램-windows)
3. [VS Code 익스텐션](#3-vs-code-익스텐션)
4. [Copilot 활성화 (중요)](#4-copilot-활성화-중요)
5. [음성 코딩 설정 (VS Code Speech)](#5-음성-코딩-설정-vs-code-speech)
6. [MCP 서버 설정](#6-mcp-서버-설정)
7. [공용 프로젝트 clone & 확인](#7-공용-프로젝트-clone--확인)
8. [계정 로그인](#8-계정-로그인)
9. [대회 당일 사용법](#9-대회-당일-사용법)
10. [팀 역할 분담](#10-팀-역할-분담)
11. [대회 전 체크리스트](#11-대회-전-체크리스트)
12. [문제 해결](#12-문제-해결)

---

## 1. 필수 계정·구독

| 항목 | 필요 여부 | 설명 |
|------|-----------|------|
| **GitHub 계정** | 필수 | 코드 저장, GitHub MCP |
| **GitHub Copilot 구독** | 필수 | Copilot Chat, Agent 모드 (개인 계정 각자 필요) |
| **Azure 구독** | 필수 | 배포용 (팀 공용 1개 + Contributor 권한 공유 권장) |
| **Docker Desktop** | 필수 | Awesome Copilot MCP 서버용 |

Copilot 무료/유료 플랜은 [GitHub Copilot 요금](https://github.com/features/copilot/plans)에서 확인하세요.

---

## 2. 설치할 프로그램 (Windows)

### 2-1. Visual Studio Code

- 다운로드: https://code.visualstudio.com/
- 설치 후 **한국어 언어 팩** (선택): Extensions에서 `Korean Language Pack` 검색 후 설치

### 2-2. Git

- 다운로드: https://git-scm.com/download/win
- 또는 PowerShell:

```powershell
winget install Git.Git
```

### 2-3. GitHub CLI (`gh`)

```powershell
winget install GitHub.cli
```

설치 확인:

```powershell
gh --version
```

### 2-4. Azure CLI (`az`)

```powershell
winget install Microsoft.AzureCLI
```

설치 확인:

```powershell
az --version
```

### 2-5. Docker Desktop

- 다운로드: https://www.docker.com/products/docker-desktop/
- 설치 후 **Docker Desktop 실행** → 트레이 아이콘이 초록색(Running)인지 확인
- Awesome Copilot MCP 이미지 미리 받기 (선택, 대회 전 권장):

```powershell
docker pull ghcr.io/microsoft/mcp-dotnet-samples/awesome-copilot:latest
```

---

## 3. VS Code 익스텐션

Extensions (`Ctrl+Shift+X`)에서 검색 후 설치하거나, 아래 링크에서 **Install** 클릭.

### 필수

| 익스텐션 | Marketplace ID | 용도 |
|----------|----------------|------|
| **GitHub Copilot** | `GitHub.copilot` | AI 코드 자동완성 |
| **GitHub Copilot Chat** | `GitHub.copilot-chat` | Chat / **Agent 모드** (VS Code 최신 버전은 내장일 수 있음) |
| **VS Code Speech** | `ms-vscode.vscode-speech` | 음성 → 텍스트, Copilot Chat 마이크 |

- Copilot Chat: https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat
- VS Code Speech: https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-speech

### 음성 (한국어, 권장)

| 익스텐션 | Marketplace ID | 용도 |
|----------|----------------|------|
| **VS Code Speech Language Pack (ko-KR)** | `ms-vscode.vscode-speech-language-pack-ko-kr` | 한국어 음성 인식·합성 |

- https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-speech-language-pack-ko-kr

### Azure / 대회 권장

| 익스텐션 | Marketplace ID | 용도 |
|----------|----------------|------|
| **GitHub Copilot for Azure** | `ms-azuretools.vscode-azure-github-copilot` | Azure 배포, `@azure`, DeployToAzure 등 |
| **Web Search for Copilot** | `ms-vscode.vscode-websearchforcopilot` | Copilot이 웹 검색 |
| **Azure Tools** (패키지) | `ms-vscode.vscode-node-azure-pack` | App Service, Functions, Storage 등 Azure 도구 모음 |

- Copilot for Azure: https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azure-github-copilot
- Web Search: https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-websearchforcopilot
- Azure Tools: https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-node-azure-pack

### 터미널에서 한 번에 설치 (선택)

VS Code가 PATH에 등록되어 있을 때:

```powershell
code --install-extension GitHub.copilot
code --install-extension GitHub.copilot-chat
code --install-extension ms-vscode.vscode-speech
code --install-extension ms-vscode.vscode-speech-language-pack-ko-kr
code --install-extension ms-azuretools.vscode-azure-github-copilot
code --install-extension ms-vscode.vscode-websearchforcopilot
code --install-extension ms-vscode.vscode-node-azure-pack
```

> 프로젝트를 clone한 뒤 VS Code로 열면 `.vscode/extensions.json`에 따라 **권장 익스텐션 설치** 팝업이 뜹니다. **Install All** 누르면 됩니다.

---

## 4. Copilot 활성화 (중요)

Copilot Chat / Agent가 안 되면 **Copilot이 꺼져 있는지** 먼저 확인하세요.

### 사용자 설정 (`Ctrl+,` → 우상단 `{}` 아이콘 → settings.json)

아래처럼 **모든 파일 타입에서 Copilot이 켜져 있어야** 합니다:

```json
{
  "github.copilot.enable": {
    "*": true,
    "plaintext": true,
    "markdown": true,
    "scminput": true
  },
  "github.copilot.chat.agent.enabled": true,
  "github.copilot.chat.agent.runTasks": true
}
```

### 확인 방법

1. VS Code 우하단 **Copilot 아이콘** 클릭 → GitHub 로그인
2. `Ctrl+Alt+I` 로 Chat 열기
3. 입력창 아래 모드에서 **Agent** 선택 가능한지 확인
4. Chat 입력창에 **마이크 아이콘**이 보이는지 확인 (VS Code Speech 연동 성공)

---

## 5. 음성 코딩 설정 (VS Code Speech)

### 5-1. Windows 마이크 권한

**설정 → 개인정보 및 보안 → 마이크** 에서 **데스크톱 앱 마이크 액세스** 켜기, VS Code 허용.

### 5-2. 워크스페이스 설정 (프로젝트 clone 시 자동 적용)

`.vscode/settings.json` 내용:

```json
{
  "accessibility.voice.speechLanguage": "ko-KR",
  "accessibility.voice.speechTimeout": 2500,
  "accessibility.voice.autoSynthesize": true,
  "accessibility.voice.keywordActivation": "chatInContext",
  "github.copilot.chat.agent.enabled": true,
  "github.copilot.chat.agent.runTasks": true
}
```

| 설정 | 값 | 설명 |
|------|-----|------|
| `speechLanguage` | `ko-KR` | 한국어 음성 인식 |
| `speechTimeout` | `2500` | 말 멈춘 뒤 2.5초 후 자동 전송 (ms) |
| `autoSynthesize` | `true` | AI 답변을 **소리로 읽어줌** |
| `keywordActivation` | `chatInContext` | **"Hey Code"** 로 어디서든 음성 Chat 시작 |

`keywordActivation` 옵션 참고:

| 값 | 동작 |
|----|------|
| `off` | Hey Code 비활성 (기본) |
| `chatInView` | Chat 뷰에서만 |
| `chatInContext` | VS Code 어디서든 (대회용 추천) |
| `inlineChat` | 에디터 인라인 Chat에서만 |
| `quickChat` | Quick Chat에서만 |

### 5-3. Windows 단축키

| 동작 | 단축키 |
|------|--------|
| **음성 Chat 시작** | `Ctrl + I` |
| **에디터 받아쓰기** | `Ctrl + Alt + V` |
| **음성/합성 중지** | `Esc` |
| **Chat 열기** | `Ctrl + Alt + I` |

**워키토키 모드:** `Ctrl + I`를 **누르고 있는 동안** 말하고, **떼면** 자동 전송.

### 5-4. 추천 keybindings (선택)

`Ctrl+K Ctrl+S` → 우상단 **Open Keyboard Shortcuts (JSON)**:

```json
[
  {
    "key": "ctrl+i",
    "command": "workbench.action.chat.startVoiceChat",
    "when": "!voiceChatInProgress"
  },
  {
    "key": "ctrl+i",
    "command": "workbench.action.chat.stopListeningAndSubmit",
    "when": "voiceChatInProgress"
  }
]
```

### 5-5. 음성 처리 방식

VS Code Speech는 **음성을 로컬 PC에서 처리**합니다. 녹음 파일이 외부 서버로 전송되지 않습니다. (Copilot Chat 본문은 GitHub Copilot 정책을 따릅니다.)

---

## 6. MCP 서버 설정

MCP(Model Context Protocol)는 Copilot Agent가 **GitHub, Awesome Copilot 템플릿** 등 외부 도구를 쓰게 해 줍니다.

프로젝트의 `.vscode/mcp.json`:

```json
{
  "servers": {
    "github": {
      "url": "https://api.githubcopilot.com/mcp/"
    },
    "awesome-copilot": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "ghcr.io/microsoft/mcp-dotnet-samples/awesome-copilot:latest"
      ]
    }
  }
}
```

### 6-1. GitHub MCP 서버

| 항목 | 내용 |
|------|------|
| **URL** | `https://api.githubcopilot.com/mcp/` |
| **인증** | OAuth (PAT 불필요) |
| **Docker** | 불필요 |
| **기능** | repo 생성/조회, issue, PR, 코드 검색 등 |

**설정 방법 (방법 A — UI, 권장)**

1. `Ctrl+Shift+X` → 검색창에 `@mcp github` 입력
2. **GitHub MCP Server** 선택 → **Install**
3. 서버 신뢰(Trust) 확인

**설정 방법 (방법 B — 프로젝트 mcp.json)**

1. `vibe-coding-hackathon` 폴더를 VS Code로 열기 (`.vscode/mcp.json` 자동 로드)
2. `mcp.json` 파일 위 **Auth** CodeLens 클릭 → GitHub OAuth 로그인

**확인**

1. `Ctrl+Shift+P` → **MCP: List Servers**
2. `github` 서버가 목록에 있으면 OK
3. Copilot Chat → **Agent** 모드 → 도구(렌치) 아이콘 → GitHub 관련 도구 표시 확인

- 공식 문서: https://github.com/mcp/github/github-mcp-server

### 6-2. Awesome Copilot MCP 서버

| 항목 | 내용 |
|------|------|
| **이미지** | `ghcr.io/microsoft/mcp-dotnet-samples/awesome-copilot:latest` |
| **인증** | Docker만 실행 중이면 됨 |
| **Docker** | **필수** (대회 전·당일 Docker Desktop 실행) |
| **기능** | chatmode, instructions, prompt 검색·프로젝트에 저장 |

**사용 예 (Agent Chat에서 말하기)**

> awesome-copilot MCP로 Azure 배포용 chatmode 검색해줘

> awesome-copilot에서 FastAPI 관련 instructions 찾아서 `.github/instructions/`에 저장해줘

- 저장소: https://github.com/mcp/microsoft/awesome-copilot
- Awesome Copilot 전체 컬렉션: https://github.com/github/awesome-copilot

**확인**

```powershell
docker ps
docker pull ghcr.io/microsoft/mcp-dotnet-samples/awesome-copilot:latest
```

`MCP: List Servers`에서 `awesome-copilot` 표시 + Agent 도구 목록에 `#search_instructions` 등이 보이면 OK.

### 6-3. MCP 수동 추가 (프로젝트 없이 설정할 때)

`Ctrl+Shift+P` → **MCP: Open User Configuration** 또는 **MCP: Edit Settings** → 위 JSON을 `servers` 블록에 붙여넣기.

---

## 7. 공용 프로젝트 clone & 확인

팀 리더가 만든 repo를 clone합니다 (URL은 팀 리더에게 받기).

```powershell
cd C:\Users\<사용자명>\project
gh repo clone <팀-org-or-user>/vibe-coding-hackathon
cd vibe-coding-hackathon
code .
```

### 프로젝트에 포함된 파일

```
vibe-coding-hackathon/
├── .vscode/
│   ├── extensions.json      # 팀 공통 익스텐션 추천
│   ├── mcp.json               # GitHub + Awesome Copilot MCP
│   └── settings.json          # 음성·Agent 워크스페이스 설정
├── .github/
│   └── instructions/
│       └── hackathon.instructions.md   # Copilot 공통 지침
├── .env.example               # Azure/앱 환경변수 템플릿
├── .gitignore
└── SETUP.md                   # 이 문서
```

### Copilot Instructions

`.github/instructions/hackathon.instructions.md`는 Agent가 자동으로 참고하는 팀 규칙입니다:

- MVP 우선
- Azure 배포
- `.env`에만 비밀값, Git 커밋 금지
- 기능 완료 후 로컬·배포 URL 확인

---

## 8. 계정 로그인

### 8-1. GitHub

**VS Code**

1. 우하단 Copilot 아이콘 → Sign in to GitHub

**터미널 (GitHub MCP / gh CLI용)**

```powershell
gh auth login
```

- GitHub.com → HTTPS → Login with a web browser

확인:

```powershell
gh auth status
```

### 8-2. GitHub Copilot

- Copilot 구독이 있는 GitHub 계정으로 로그인
- Chat에서 `@workspace`, Agent 모드 사용 가능한지 확인

### 8-3. Azure

**터미널**

```powershell
az login
az account list --output table
az account set --subscription "구독이름또는ID"
```

**VS Code (Copilot for Azure)**

1. Copilot Chat → **Agent** 모드
2. 입력:

```
Azure에 로그인하고 사용 중인 구독 알려줘
```

3. 터미널 명령 실행 승인 시 **Continue** 또는 **Always allow**

팀 공용 Azure 구독 ID / 리소스 그룹 이름은 팀 리더와 공유받아 `.env`에 기록 (Git에는 올리지 않음).

---

## 9. 대회 당일 사용법

### 9-1. 기본 루프

1. **Docker Desktop** 실행
2. VS Code에서 `vibe-coding-hackathon`(또는 대회용 repo) 열기
3. Copilot Chat → **Agent** 모드
4. `Ctrl + I` (또는 **"Hey Code"**) 로 말하기
5. Agent가 파일 수정·터미널 실행 제안 → **Accept** / **Continue**
6. `autoSynthesize`로 답변을 듣거나, 스피커 아이콘으로 재생

### 9-2. 자주 쓰는 음성 지시 예시

**프로젝트 시작**

> FastAPI로 헬스체크 API 만들고 README 작성해줘. MVP만.

**기능 추가**

> 사용자 CRUD API 추가하고 SQLite 연결해줘.

**테스트**

> pytest 실행하고 실패하면 고쳐줘.

**Git (GitHub MCP)**

> private GitHub repo 만들고 지금 코드 푸시해줘.

**Azure 배포**

> #DeployToAzure 이 프로젝트를 Azure App Service에 koreacentral 리전으로 배포해줘.

**문서/템플릿 (Awesome Copilot MCP)**

> awesome-copilot MCP로 Azure Static Web App 배포 instructions 검색해서 저장해줘.

**웹 검색 (Web Search 익스텐션)**

> 최신 Azure App Service Python 배포 방법 검색해서 적용해줘.

### 9-3. Copilot for Azure 주요 도구

| 도구 | 용도 |
|------|------|
| **DeployToAzure** | App Service, SWA 등 배포 |
| **Azure_function_codegen_and_deployment** | Azure Functions 생성·배포 |
| **Azure_Static_Web_App** | Static Web Apps |
| **@azure** (Ask 모드) | Azure 리소스 질문, CLI/Bicep 가이드 |

Agent 모드에서 `#DeployToAzure`처럼 도구 이름을 붙이면 해당 도구를 우선 사용합니다.

---

## 10. 팀 역할 분담 (2인 팀 예시)

| 역할 | 담당 | 예시 |
|------|------|------|
| **Driver** | A | 음성으로 Agent에 기능 구현 지시 |
| **Navigator** | B | 결과·에러 확인, 배포·Git 지시 보조 |
| **Git** | 번갈아 | "커밋하고 푸시해줘" |
| **Azure** | A 또는 B | "배포해줘", 구독/리소스 확인 |

- Copilot: **각자 GitHub 계정 + Copilot 구독**
- Azure: **팀 공용 구독 1개** (Contributor 권한)
- API 키·`.env`: **Slack/카톡 등으로만 공유**, Git 금지

---

## 11. 대회 전 체크리스트

### 프로그램

- [ ] VS Code 최신 버전
- [ ] Git, gh, az 설치 및 PATH 확인
- [ ] Docker Desktop 설치, `docker ps` 정상

### 익스텐션

- [ ] GitHub Copilot (+ Copilot Chat)
- [ ] VS Code Speech + 한국어 Language Pack
- [ ] GitHub Copilot for Azure
- [ ] Web Search for Copilot
- [ ] Azure Tools

### 설정

- [ ] `github.copilot.enable` → `"*": true`
- [ ] Chat → **Agent** 모드 선택 가능
- [ ] Chat 입력창 **마이크 아이콘** 표시
- [ ] Windows **마이크 권한** VS Code 허용
- [ ] "Hey Code" 테스트 (`keywordActivation`: `chatInContext`)

### MCP

- [ ] `MCP: List Servers` → `github`, `awesome-copilot`
- [ ] GitHub MCP OAuth 완료
- [ ] Docker 실행 중 + awesome-copilot 이미지 pull

### 계정

- [ ] `gh auth login` 완료
- [ ] `az login` + 올바른 subscription 설정
- [ ] VS Code Copilot 로그인

### 팀

- [ ] `vibe-coding-hackathon` repo clone
- [ ] `.env` 값 팀 리더에게 받아 로컬 `.env` 생성 (Git 제외)
- [ ] 이어폰·마이크 테스트 (대회장 소음 대비)

### 10분 연습

1. Agent: "Python FastAPI 헬스체크 API 만들고 로컬 실행해줘"
2. GitHub MCP: "private repo 만들고 푸시해줘"
3. Azure: "App Service에 배포해줘"

---

## 12. 문제 해결

### 마이크 아이콘이 안 보임

1. **VS Code Speech** 설치 확인
2. **GitHub Copilot Chat** 설치·로그인 확인
3. VS Code **재시작**
4. Windows 마이크 권한 확인

### Copilot Chat / Agent가 안 됨

1. `github.copilot.enable` → `"*": false` 인지 확인 → **true로 변경**
2. Copilot 구독·로그인 상태 확인
3. `github.copilot.chat.agent.enabled`: `true` 확인

### GitHub MCP 연결 실패

1. `Ctrl+Shift+P` → **MCP: List Servers**
2. `mcp.json`의 `Auth` CodeLens로 재로그인
3. `@mcp github`로 Marketplace에서 재설치

### Awesome Copilot MCP 실패

1. **Docker Desktop이 실행 중**인지 확인
2. `docker pull ghcr.io/microsoft/mcp-dotnet-samples/awesome-copilot:latest`
3. VS Code **완전 종료 후 재시작** (Reload Window만으로는 MCP가 안 뜰 때 있음)

### Azure 배포 실패

1. `az login` / `az account show` 로 구독 확인
2. Agent에게: "지금 Azure 구독과 리소스 그룹 알려줘"
3. Copilot for Azure 익스텐션 설치·Azure 도구(렌치) 활성화 확인

### 한국어 음성 인식이 영어로 됨

1. `accessibility.voice.speechLanguage`: `ko-KR`
2. `ms-vscode.vscode-speech-language-pack-ko-kr` 설치
3. 첫 실행 시 추가 언어 팩 설치 안내 → **Install**

### `code` 명령을 찾을 수 없음

VS Code → `Ctrl+Shift+P` → **Shell Command: Install 'code' command in PATH**

---

## 참고 링크

| 리소스 | URL |
|--------|-----|
| VS Code 음성 공식 문서 | https://code.visualstudio.com/docs/configure/accessibility/voice |
| VS Code Speech Marketplace | https://marketplace.visualstudio.com/items?itemName=ms-vscode.vscode-speech |
| GitHub Copilot Chat | https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat |
| GitHub Copilot for Azure 시작 | https://learn.microsoft.com/azure/developer/github-copilot-azure/get-started |
| Azure Agent 모드 배포 퀵스타트 | https://learn.microsoft.com/azure/developer/github-copilot-azure/quickstart-deploy-app-agent-mode |
| GitHub MCP Server | https://github.com/mcp/github/github-mcp-server |
| Awesome Copilot MCP | https://github.com/mcp/microsoft/awesome-copilot |
| Awesome Copilot 컬렉션 | https://github.com/github/awesome-copilot |

---

## 팀 리더에게 받을 것

- [ ] GitHub repo URL (`vibe-coding-hackathon`)
- [ ] Azure 구독 ID / 리소스 그룹 이름 (또는 대회용 Azure Pass)
- [ ] `.env`에 넣을 값 (API 키 등, **Git 제외**)
- [ ] 대회 당일 사용할 Azure 리전 (예: `koreacentral`)

질문은 팀 채팅으로 — **대회 전날 MCP + 음성 + Azure 배포 10분 연습**까지 해두면 당일 훨씬 수월합니다.
