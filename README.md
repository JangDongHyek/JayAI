# JayAI

JayAI는 두 덩어리로 나뉜다.

- 중앙 서버
  프로젝트, 장치, 워크스페이스 바인딩, 대화, 메시지, 실행 기록 저장만 담당
- 로컬 앱
  브라우저 UI를 열고, 로컬 파일을 읽고, `Codex CLI`와 `Claude Code CLI`를 실행한 뒤 결과를 중앙 서버에 동기화

의도한 흐름도 이 구조다.

1. 각 PC에 CLI 설치 및 로그인
2. 프로젝트/세션 데이터는 중앙 서버에 저장
3. 각 PC에서 로컬 폴더만 다시 바인딩해서 이어서 작업

## 현재 상태 빠른 확인

- 중앙 API: `http://43.203.252.40/jayai-api`
- 헬스체크: `http://43.203.252.40/jayai-api/api/health`
- 현재 수동 등록 프로젝트:
  - `jayai`
  - `ai-macro`
- 상세 인수인계 문서:
  - `SESSION_STATUS.md`

## 구조

### 중앙 서버

- 로컬 파일 접근 안 함
- `Codex` / `Claude` 실행 안 함
- 데이터/API 전용

핵심 파일:

- `src/jayai/main.py`
- `src/jayai/routers/projects.py`
- `src/jayai/routers/devices.py`
- `src/jayai/templates/server.html`

### 로컬 앱

- 로컬 브라우저 UI
- 로컬 워크스페이스 스캔
- 로컬 git 작업
- 로컬 `Codex` / `Claude` 실행
- 중앙 서버로 실행 결과 동기화

핵심 파일:

- `src/jayai/local_main.py`
- `src/jayai/routers/local.py`
- `src/jayai/services/orchestrator.py`
- `src/jayai/services/server_api.py`
- `src/jayai/services/local_config.py`
- `src/jayai/templates/index.html`
- `start-jayai-local.bat`

## 로컬 실행

권장:

- `start-jayai-local.bat` 더블클릭

수동:

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
.\.venv\Scripts\python.exe -m jayai.cli local-ui --open-browser
```

처음 한 번만 서버 주소를 강제로 넣고 띄우려면:

```powershell
.\.venv\Scripts\python.exe -m jayai.cli local-ui --server-url http://43.203.252.40/jayai-api --open-browser
```

저장 위치:

- `data/local-config.json`

## 중앙 서버 실행

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
.\.venv\Scripts\python.exe -m uvicorn jayai.main:app --host 0.0.0.0 --port 8000
```

nginx 하위 경로로 붙일 때:

```powershell
$env:JAYAI_BASE_PATH="/jayai-api"
.\.venv\Scripts\python.exe -m uvicorn jayai.main:app --host 0.0.0.0 --port 8000
```

## 기본 작업 흐름

1. 로컬 앱 열기
2. 중앙 서버 주소 확인
3. 로컬 CLI 상태 점검
4. 프로젝트 선택
5. 로컬 폴더 경로 바인딩
6. 기존 대화 열기 또는 새 대화 생성
7. 프롬프트 실행

예시:

- `README 읽고 핵심 구조 5줄로 요약`
- `git status 보여줘`
- `repo 가져오고 최신으로 pull`

## 프로젝트 문서 수집

기본으로 읽는 파일:

- `AGENTS.md`
- `README.md`
- `README*.md`
- `CLAUDE.md`
- `SESSION_STATUS.md`
- `docs/**/*.md`

프로젝트 루트 설정 파일:

- `.jayai.json`
- `jayai.json`
- `.orchestrator.json`
- `orchestrator.json`

기본 동작:

- 무거운 문맥은 `Codex` 우선
- `Claude`는 검토와 반박 담당

## 데이터 경로

중앙 서버 기본 DB:

- `data/jayai.db`

로컬 실행 산출물:

- `data/runs/<timestamp>/`

포함 파일:

- `codex.txt`
- `claude.txt`
- `summary.txt`
- `meta.json`

## 한계

- 아직 패키징된 데스크톱 앱 아님
- 토큰 스트리밍 뷰 없음
- 백그라운드 러너 서비스 없음
- 자연어 `commit / push / PR` 없음
