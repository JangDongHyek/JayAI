# JayAI 상태 정리

작성 기준:
- 날짜: 2026-04-07
- 목적: 새 세션에서도 현재 구조와 배포 상태를 바로 파악하기 위한 문서

## 현재 구조

JayAI는 두 덩어리로 분리됨.

1. 중앙 서버
- 역할: 프로젝트, 장치, 워크스페이스 바인딩, 대화, 메시지, 실행 기록 저장
- 역할 아님: 로컬 파일 읽기, git 실행, Codex/Claude CLI 실행

2. 로컬 앱
- 역할: 로컬 폴더 읽기, git, Codex/Claude CLI 실행, 결과를 중앙 서버로 동기화
- UI도 로컬 앱에서 띄움

핵심 원칙:
- 서버에는 `Codex CLI`, `Claude Code CLI` 설치하지 않음
- 실제 작업은 항상 로컬에서만 함

## 현재 로컬 경로

- JayAI: `C:\Users\fove1\OneDrive\문서\codex\life\jayai`
- ai-macro: `C:\Users\fove1\OneDrive\문서\codex\life\ai-macro`

## 중앙 서버 정보

- 서버 IP: `43.203.252.40`
- 중앙 API 경로: `http://43.203.252.40/jayai-api`
- 헬스체크: `http://43.203.252.40/jayai-api/api/health`
- nginx 하위 경로: `/jayai-api/`
- systemd 서비스명: `jayai-api.service`
- 서버 내부 uvicorn 포트: `127.0.0.1:8030`

서버 확인 명령:

```bash
sudo systemctl status jayai-api.service
curl http://127.0.0.1:8030/api/health
curl http://127.0.0.1/jayai-api/api/health
```

## 현재 중앙 서버에 등록된 프로젝트

1. `jayai`
- title: `JayAI`
- repo: `git@github.com:JangDongHyek/JayAI.git`
- 현재 PC 바인딩 경로: `C:\Users\fove1\OneDrive\문서\codex\life\jayai`

2. `ai-macro`
- title: `AI Macro`
- repo: `git@github.com:JangDongHyek/ai-macro.git`
- 현재 PC 바인딩 경로: `C:\Users\fove1\OneDrive\문서\codex\life\ai-macro`

현재 장치 등록 정보:
- device name: `dev_pc`

## 로컬 실행 방법

권장:

- 더블클릭: `start-jayai-local.bat`

수동:

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
.\.venv\Scripts\python.exe -m jayai.cli local-ui --open-browser
```

중앙 서버 수동 지정:

```powershell
.\.venv\Scripts\python.exe -m jayai.cli local-ui --server-url http://43.203.252.40/jayai-api --open-browser
```

로컬 설정 파일:
- `data/local-config.json`

현재 기본 서버 주소:
- `http://43.203.252.40/jayai-api`

## UI 상태

- 로컬 UI는 한글 기준으로 바뀜
- 서버 주소 입력/저장 가능
- 프로젝트 목록, 경로 저장, 대화 목록, 실행창 있음
- `git clone / pull / status` 자연어 감지됨

## 현재 가능한 것

- 프로젝트 선택
- 로컬 폴더 경로 바인딩
- 대화 생성/이어쓰기
- 로컬에서 Codex/Claude 실행
- 결과를 중앙 서버에 메시지/실행기록으로 저장

## 현재 아직 없는 것

- 인증
- 스트리밍 응답
- 자연어 `commit / push / PR`
- 패키징된 데스크톱 앱

## 주의

- 중앙 API는 현재 인증 없음
- 사용량 소모 위험은 낮음
  이유: 서버가 CLI를 직접 실행하지 않음
- 대신 프로젝트/세션 데이터는 외부에서 읽고 쓸 수 있음
- 나중에 필요하면 `nginx basic auth` 또는 IP 제한 붙이면 됨

## 관련 핵심 파일

- 로컬 앱 진입: `src/jayai/local_main.py`
- 중앙 서버 진입: `src/jayai/main.py`
- 로컬 라우트: `src/jayai/routers/local.py`
- 중앙 프로젝트 API: `src/jayai/routers/projects.py`
- 오케스트레이터: `src/jayai/services/orchestrator.py`
- 서버 API 클라이언트: `src/jayai/services/server_api.py`
- 로컬 설정 저장: `src/jayai/services/local_config.py`
- 로컬 UI: `src/jayai/templates/index.html`
- 서버 안내 페이지: `src/jayai/templates/server.html`

## 다음에 자주 할 작업

1. 집 컴퓨터에서 repo clone
2. `Codex CLI`, `Claude Code CLI` 설치 및 로그인
3. `start-jayai-local.bat` 실행
4. 서버 주소 확인
5. `ai-macro` 프로젝트 선택
6. 집 컴퓨터 로컬 경로로 다시 바인딩
7. 이전 대화 이어서 작업
