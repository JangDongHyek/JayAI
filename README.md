# JayAI

로컬 `Codex CLI`, `Claude Code CLI`를 프로젝트 단위로 묶어서 쓰기 위한 개인용 오케스트레이터.

현재 포함:
- `FastAPI` 기반 중앙 앱
- 프로젝트 / 기기 / 워크스페이스 바인딩 / 세션 / 메시지 DB 스키마
- 로컬 러너 상태 점검
- 최소 웹 UI
- 헤드리스 CLI 진입점

## 구조

- `src/jayai/main.py`
  FastAPI 앱 진입점
- `src/jayai/models.py`
  DB 모델
- `src/jayai/schemas.py`
  API 스키마
- `src/jayai/services/runner.py`
  로컬 환경 점검
- `src/jayai/routers/`
  API 라우터
- `src/jayai/templates/index.html`
  최소 웹 UI

## 빠른 시작

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m uvicorn jayai.main:app --reload
```

브라우저:
- `http://127.0.0.1:8000`

## 기본 DB

기본은 로컬 SQLite.

- `%PROJECT_ROOT%\data\jayai.db`

서버에서 Postgres 쓰려면:

```powershell
$env:JAYAI_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/jayai"
python -m uvicorn jayai.main:app --host 0.0.0.0 --port 8000
```

참고:
- `psycopg`는 아직 의존성에 안 넣음
- Postgres로 갈 때만 별도 설치

## CLI

서버나 헤드리스 환경에서:

```powershell
jayai serve --host 0.0.0.0 --port 8000
jayai probe
jayai scan-workspace C:\path\to\repo
```

## 현재 범위

- 실제 Codex/Claude 작업 실행 orchestration은 다음 단계
- 지금은 저장 구조, 러너 프로브, 프로젝트/세션 관리 뼈대까지
