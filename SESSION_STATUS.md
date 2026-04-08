# JayAI 상태 정리

작성 기준:
- 날짜: 2026-04-08
- 목적: 세션이 바뀌어도 현재 구조와 서버/로컬 역할을 바로 파악하기 위한 문서

## 현재 방향

기존 채팅형 세션 중심 구조는 사실상 폐기.

폐기 이유:
- 단일 사용자 멀티디바이스 문제에 비해 구조가 과했음
- 대화 저장과 실제 문맥 유지가 분리돼 있었음
- 중앙 서버에 메시지/런을 과도하게 저장했음
- 이전 실행이 안 끝난 상태에서 추가 요청이 들어와 동문서답 발생

현재 목표:
- 프로젝트 메타데이터 + 인계 + 기기별 경로만 중앙 서버에 저장
- 실제 작업은 항상 로컬에서 실행
- `대화 이어쓰기`가 아니라 `인계 이어쓰기`

## 현재 구조

### 중앙 서버

역할:
- 프로젝트 저장
- 장치 등록
- 기기별 워크스페이스 바인딩 저장
- 프로젝트 인계 저장

하지 않는 것:
- 로컬 파일 읽기
- git 실행
- Codex/Claude 실행
- 대화 턴 저장 기반 오케스트레이션

핵심 파일:
- `src/jayai/main.py`
- `src/jayai/routers/projects.py`
- `src/jayai/routers/devices.py`

### 로컬 앱

역할:
- 프로젝트 목록 보기
- 현재 기기 경로 저장
- git clone/pull/status
- 인계 보기/수정
- 로컬 Codex/Claude 실행
- 실행 상태 표시

핵심 파일:
- `src/jayai/local_main.py`
- `src/jayai/routers/local.py`
- `src/jayai/services/job_manager.py`
- `src/jayai/services/orchestrator.py`
- `src/jayai/templates/index.html`

### 데스크톱 셸

목적:
- 브라우저 탭 대신 프로그램처럼 열기
- 로컬 Python UI 서버를 내부에서 띄우고 Electron 창으로 접근

핵심 파일:
- `desktop/package.json`
- `desktop/main.js`
- `start-jayai-desktop.bat`

## 현재 데이터 모델

실사용 모델:
- `projects`
- `devices`
- `workspace_bindings`
- `project_handoffs`

남아 있지만 현재 안 쓰는 구모델:
- `conversations`
- `messages`
- `runs`

주의:
- DB에는 구테이블이 남아 있을 수 있음
- 현재 UI/API는 구테이블을 사용하지 않음

## 중앙 서버 정보

- 서버 IP: `43.203.252.40`
- 중앙 API: `http://43.203.252.40/jayai-api`
- 헬스체크: `http://43.203.252.40/jayai-api/api/health`
- nginx 경로: `/jayai-api/`
- systemd 서비스: `jayai-api.service`
- uvicorn 내부 포트: `127.0.0.1:8030`

## 현재 등록 프로젝트

1. `jayai`
- repo: `git@github.com:JangDongHyek/JayAI.git`
- 현재 PC 경로: `C:\Users\fove1\OneDrive\문서\codex\life\jayai`

2. `ai-macro`
- repo: `git@github.com:JangDongHyek/ai-macro.git`
- 현재 PC 경로: `C:\Users\fove1\OneDrive\문서\codex\life\ai-macro`

## 실행 방법

### 권장

```bat
start-jayai-desktop.bat
```

### 로컬 웹 UI만

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
.\.venv\Scripts\python.exe -m jayai.cli local-ui --open-browser
```

### 중앙 서버 직접 실행

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
.\.venv\Scripts\python.exe -m uvicorn jayai.main:app --host 0.0.0.0 --port 8000
```

## 이미 확인한 것

- 프로젝트 생성 동작 확인
- 현재 기기 경로 저장 확인
- 인계 저장 확인
- `git status` 동작 확인
- 로컬 UI 한글화 반영
- Electron 셸 의존성 설치 완료

## 아직 부족한 것

- 실제 장시간 Codex 실행은 여전히 느릴 수 있음
- 실행 중 세부 단계 스트리밍 없음
- 작업 취소 기능 없음
- 서버 인증 없음
- Electron 패키징/설치본 없음

## 다음 우선순위

1. 집/회사에서 실제 사용 후 불편한 흐름 추가 정리
2. 필요하면 작업 취소 버튼 추가
3. 필요하면 인계 자동 초안 생성 추가
4. 필요하면 서버 인증 추가
