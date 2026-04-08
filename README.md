# JayAI

JayAI는 `단일 사용자 멀티디바이스 프로젝트 이어쓰기` 용도다.

핵심 원칙:

- 중앙 서버는 `프로젝트 / 기기별 경로 / 현재 인계`만 저장
- 실제 작업은 항상 로컬 PC에서 실행
- 대화 기록을 서버에 계속 쌓지 않음
- 집, 회사, 노트북에서 같은 프로젝트를 불러와도 인계만 읽고 새 로컬 작업을 시작

## 구조

### 중앙 서버

저장하는 것:

- 프로젝트 이름
- 슬러그
- git 저장소 주소
- 기본 브랜치
- 기기별 로컬 폴더 경로
- 현재 인계
  - 프로젝트 설명
  - 현재 상태
  - 다음 작업
  - 주의사항

저장하지 않는 것:

- 대화 턴 로그
- 지속 세션 문맥
- 서버에서 실행되는 Codex/Claude 작업

### 로컬 앱

하는 일:

- 중앙 서버에서 프로젝트 목록 읽기
- 현재 기기 경로 저장
- `git clone / pull / status`
- 로컬 폴더 스캔
- 로컬 `Codex CLI`, `Claude Code CLI` 실행
- 실행 상태 표시
- 필요할 때만 인계 수동 저장

## 실행 방식

### 1. 데스크톱 앱 셸

권장:

```bat
start-jayai-desktop.bat
```

첫 실행 시 `desktop/node_modules`가 없으면 Electron 의존성부터 설치한다.

### 2. 로컬 웹 UI만 실행

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
.\.venv\Scripts\python.exe -m jayai.cli local-ui --open-browser
```

### 3. 중앙 서버 실행

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

1. 프로젝트 선택
2. 현재 기기 로컬 경로 확인 또는 저장
3. 필요하면 `clone / pull / status`
4. 현재 인계 확인
5. 로컬에서 Codex 또는 Claude 실행
6. 필요한 내용만 인계에 수동 저장

## 기본 문서 수집

Codex/Claude 실행 시 기본으로 읽는 문서:

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

## 로컬 산출물

로컬 실행 산출물:

- `data/runs/<timestamp>/codex.txt`
- `data/runs/<timestamp>/claude.txt`
- `data/runs/<timestamp>/summary.txt`
- `data/runs/<timestamp>/meta.json`

## 현재 한계

- 실행 진행률은 단계 단위만 표시
- 취소 버튼 없음
- Electron 패키징 전, 실행은 스크립트 기반
- 서버 인증 아직 없음
