# doctor_assist_project 구축 튜토리얼: OpenHands + OpenManus + Gemini Flash/Gemma 완전 가이드

이 문서는 `doctor_assist_project`(https://github.com/kimhs950627/doctor_assist_project)의 기능을 OpenHands와 OpenManus를 조합하여 구현하고, Gemini Flash(빠른 응답)와 Gemma(무료 쿼터 절약)를 함께 쓰는 전체 과정을 클릭 단위로 정리한 튜토리얼임.

## 전체 그림

- **OpenHands**: 코드 작성/수정, 테스트, GitHub commit/push를 대신 수행하는 "개발자 에이전트". 웹 브라우저 UI로 접근함.
- **OpenManus**: 웹 검색 기반 근거 수집을 담당하는 "리서치 워커". doctor_assist_project와 별도 프로세스로 동작함.
- **Gemini Flash**: 응답 속도가 필요한 실시간 작업(SOAP 변환, DDx 등)에 사용.
- **Gemma**: 무료 쿼터가 넉넉해 대량/반복 작업(리서치 요약, 일상 콘텐츠 초안)에 사용.

## 0단계. 사전 준비물 설치

### 0-1. Docker Desktop 설치 (Windows 기준)

1. 브라우저에서 `https://www.docker.com`으로 이동함.
2. 상단 또는 메인 화면의 **Download Docker Desktop** 버튼을 클릭함.
3. 옵션 중 **Download for Windows - AMD64**를 클릭함(대부분의 PC는 이 옵션임. ARM 기반 노트북이면 ARM64 선택).
4. 다운로드가 끝나면 다운로드 폴더에서 `Docker Desktop Installer.exe` 파일을 찾아 마우스 우클릭 후 **관리자 권한으로 실행**을 클릭함.
5. 사용자 계정 컨트롤(UAC) 창이 뜨면 **예**를 클릭함.
6. 설치 마법사 화면에서 **Use WSL 2 instead of Hyper-V** 체크박스가 선택되어 있는지 확인하고 **OK**를 클릭함.
7. 설치가 끝나면 **Close and restart** 버튼을 클릭해 PC를 재시작함.
8. 재시작 후 바탕화면의 **Docker Desktop** 아이콘을 더블클릭해 실행함.
9. 서비스 이용 약관 동의 화면에서 **Accept**를 클릭함.
10. 로그인 화면이 뜨면 Docker 계정으로 로그인하거나 **Skip**을 클릭해 넘어감(설치 검증만 목적이면 스킵 가능).
11. 정상 설치를 확인하려면 시작 메뉴에서 `cmd`를 검색해 명령 프롬프트를 열고 `docker --version`을 입력함. 버전 번호가 출력되면 성공임.

### 0-2. Google AI Studio에서 Gemini API 키 발급

1. 브라우저에서 `https://aistudio.google.com`으로 이동함.
2. 구글 계정으로 로그인함.
3. 최초 접속 시 나오는 이용 약관 동의 모달에서 **I agree**를 체크하고 **Continue**를 클릭함.
4. 화면 좌측 하단(또는 좌측 사이드바)의 **Get API key** 버튼을 클릭함.
5. API Keys 관리 페이지가 열리면 우측 상단의 **Create API key** 버튼을 클릭함.
6. 키 이름을 입력함(예: `doctor-assist-gemini`).
7. **Select a project** 드롭다운에서 기존 Google Cloud 프로젝트를 선택하거나, 프로젝트가 없다면 **Create a new project**를 클릭 후 이름을 입력하고 **Create**를 클릭함.
8. 프로젝트 생성이 완료되면 자동으로 선택된 상태에서 **Create key** 버튼을 클릭함.
9. 몇 초 후 키가 발급되면 **Copy key**(또는 복사 아이콘)를 클릭해 클립보드에 복사함.
10. 이 키 하나로 Gemini Flash와 Gemma 모델을 모두 호출할 수 있으므로 별도 발급이 필요 없음. 안전한 곳(비밀번호 관리자 또는 로컬 `.env` 파일)에만 저장하고 어디에도 노출하지 않음.

### 0-3. GitHub PAT 확인

이미 GitHub Personal Access Token이 등록되어 있으므로 재발급은 필요 없음. OpenHands UI에 입력할 때만 사용하고 채팅창 등에 원문으로 붙여넣지 않음.

## 1단계. OpenHands 설치 및 웹 UI 실행

### 1-1. Docker로 OpenHands 실행

1. 시작 메뉴에서 `cmd` 또는 `PowerShell`을 검색해 터미널을 관리자 권한으로 엶.
2. 아래 명령을 한 줄씩 복사해 붙여넣고 Enter를 누름.

```bash
docker pull docker.all-hands.dev/all-hands-ai/runtime:0.75-nikolaik

docker run -it --rm --pull=always ^
  -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:0.75-nikolaik ^
  -e LOG_ALL_EVENTS=true ^
  -v /var/run/docker.sock:/var/run/docker.sock ^
  -v %USERPROFILE%\.openhands:/.openhands ^
  -p 3000:3000 ^
  --add-host host.docker.internal:host-gateway ^
  --name openhands-app ^
  docker.all-hands.dev/all-hands-ai/openhands:0.75
```

(WSL/Linux/Mac 터미널이면 `^` 대신 `\`를 줄바꿈 기호로 사용함.)

3. 로그에 서버가 준비됐다는 메시지가 뜨면 브라우저를 열고 주소창에 `http://localhost:3000`을 입력함.

### 1-2. 최초 설정 팝업에서 LLM 등록

OpenHands 최초 실행 시 설정 팝업이 자동으로 뜸.

1. **LLM Provider** 드롭다운을 클릭함.
2. 목록에 원하는 모델(gemini 계열)이 안 보이면 팝업 하단의 **see advanced settings**(또는 **Advanced** 토글 스위치)를 클릭함.
3. **Advanced** 토글을 켠 상태에서 **Custom Model** 입력란에 `gemini/gemini-2.0-flash`를 입력함.
4. **Base URL** 입력란은 비워둠(Gemini 프로바이더는 LiteLLM이 자동으로 처리함).
5. **API Key** 입력란에 0-2단계에서 복사한 Gemini API 키를 붙여넣음.
6. 화면 하단의 **Save Changes** 버튼을 클릭함.

이렇게 하면 첫 번째 LLM 프로필(Gemini Flash용)이 생성됨. Gemma용 프로필을 추가로 만들려면:

7. 화면 우측 상단 프로필 아이콘 또는 **Settings** 메뉴로 들어가 좌측 탭에서 **LLM**을 클릭함.
8. **Advanced** 토글을 다시 켠 뒤, **Custom Model**에 `gemini/gemma-3-27b-it`를 입력함.
9. **API Key**에 동일한 Gemini API 키를 붙여넣음.
10. **Save Changes**를 클릭함. 저장 시 자동으로 새 프로필이 생성됨.
11. 이후 채팅 입력창 위쪽의 **프로필 선택 버튼**(현재 활성 프로필명이 표시됨)을 클릭하면 Gemini Flash 프로필과 Gemma 프로필을 작업 종류에 따라 즉시 전환할 수 있음.

### 1-3. GitHub 저장소 연결

1. **Settings** 메뉴에서 좌측 탭의 **Git Providers**(또는 **Integrations**)를 클릭함.
2. **GitHub** 항목의 **Connect** 버튼을 클릭함.
3. 뜨는 입력창에 GitHub PAT를 붙여넣고 **Save** 또는 **Connect**를 클릭함(이 화면 캡처를 남기거나 다시 출력하지 않도록 주의함).
4. 연결이 완료되면 상단 또는 좌측의 **Repository** 선택 드롭다운을 클릭함.
5. 목록에서 `kimhs950627/doctor_assist_project`를 검색해 클릭함.
6. **Launch**(또는 **Start Conversation**) 버튼을 클릭하면 컨테이너 내부에 저장소가 자동으로 클론됨.

## 2단계. OpenHands에게 doctor_assist_project 기능 구현 위임

1. 화면 하단 채팅 입력창을 클릭함.
2. 아래 지시문을 그대로 입력하고 Enter(또는 전송 버튼)를 누름.

```
이 리포지토리의 README.md, doctor_assist_bot_plan.md, ARCHITECTURE.md를 읽고
README의 "Development Order" 섹션 1~3단계
(ResearchRequest/ResearchJob/EvidenceBundle 스키마 정의,
SQLite + 아티팩트 폴더 저장소 구현, 잡 생성/조회/검색 기능)를
control_tower/services/ 하위에 구현해줘.
구현 후 tests/ 에 최소 단위테스트를 추가하고,
git add, commit, push까지 main 브랜치에 수행해줘.
```

3. OpenHands가 파일을 읽고 코드를 작성하는 과정이 채팅창에 실시간으로 표시됨. 완료되면 커밋 해시와 push 로그가 채팅창 하단에 출력됨.
4. 4~8단계(OpenManus 워커 연동, Telegram/웹 탭 추가, Vlog Research mode, 핸드아웃 재사용, 스케일링)도 동일한 방식으로 순서대로 채팅창에 지시함. 한 번에 전체를 요청하지 말고 README의 순서를 지켜 단계별로 요청하는 것이 오류를 줄임.

## 3단계. OpenManus 설치 (리서치 워커)

### 3-1. Miniconda 설치 확인

1. 터미널에서 `conda --version`을 입력해 conda가 이미 설치돼 있는지 확인함.
2. 설치돼 있지 않다면 `https://www.anaconda.com/download`로 이동해 **Download**(운영체제에 맞는 버전) 버튼을 클릭하고 설치 파일을 실행, 기본값으로 **Next**를 눌러가며 설치를 완료함.

### 3-2. OpenManus 클론 및 환경 구성

터미널(맥/리눅스/WSL)에서 아래를 순서대로 입력함.

```bash
mkdir -p ~/services && cd ~/services
conda create -n open_manus python=3.12 -y
conda activate open_manus
git clone https://github.com/FoundationAgents/OpenManus.git
cd OpenManus
pip install -r requirements.txt
playwright install
cp config/config.example.toml config/config.toml
```

### 3-3. config.toml 편집 (Gemini Flash 기본 설정)

1. 파일 탐색기 또는 VS Code로 `~/services/OpenManus/config/config.toml`을 엶.
2. `[llm]` 섹션을 아래처럼 수정함.

```toml
[llm]
model = "gemini-2.0-flash"
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
api_key = "여기에_Gemini_API_키_붙여넣기"
max_tokens = 4096
temperature = 0.0

[llm.vision]
model = "gemini-2.0-flash"
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
api_key = "여기에_Gemini_API_키_붙여넣기"
```

3. 파일을 저장함(Ctrl+S).

### 3-4. Gemma 전용 설정 파일 추가 (대량 리서치용)

1. 터미널에서 아래 명령으로 복사본을 만듦.

```bash
cp config/config.toml config/config_gemma.toml
```

2. `config_gemma.toml`을 열고 `model` 값만 `gemma-3-27b-it`로 바꾸고 저장함.
3. 대량/반복 리서치 잡을 돌릴 때는 실행 시 다음처럼 지정함.

```bash
python main.py --config config/config_gemma.toml
```

### 3-5. 동작 테스트

```bash
conda activate open_manus
cd ~/services/OpenManus
python main.py
```

터미널에 프롬프트가 뜨면 `당뇨병 최신 진료 가이드라인 변경사항을 검색해서 근거와 출처 URL을 정리해줘`를 입력해 정상 응답이 오는지 확인함.

## 4단계. doctor_assist_project와 OpenManus 연결

이 작업도 OpenHands 채팅창에 위임하는 것이 가장 안전하고 빠름.

1. OpenHands 웹 UI(`http://localhost:3000`)로 돌아가서 채팅 입력창에 아래를 입력함.

```
control_tower/workers/openmanus_worker.py 를 새로 만들어줘.
요구사항:
1. subprocess로 conda run -n open_manus python ~/services/OpenManus/main.py 를 호출한다.
   기본은 config/config.toml(Gemini Flash), 대량 작업 플래그가 있으면 config/config_gemma.toml(Gemma)을 사용한다.
2. 타임아웃을 설정하고 stdout/stderr를 sanitize해서 data/research/<jobID>/run.log 에 저장한다.
3. 원본 출력은 openmanus_raw.json 으로, modules/research_schemas.py 의 EvidenceBundle 형식으로
   정규화한 결과는 evidence_bundle.json 으로 저장한다.
4. FastAPI 요청 핸들러 내부에서 직접 실행하지 말고 별도 백그라운드 작업(job queue)으로 실행한다.
구현 후 테스트를 작성하고 git add, commit, push 까지 수행해줘.
```

2. 진행 상황과 커밋 로그를 채팅창에서 확인함.

## 5단계. .env 설정 및 Gemini/Gemma 이중 사용 확정

1. 로컬 터미널에서 doctor_assist_project 폴더로 이동함.

```bash
cd doctor_assist_project
cp .env.example .env
```

2. 텍스트 편집기로 `.env` 파일을 열고 아래처럼 채움.

```
GEMINI_API_KEY=발급받은_Gemini_API_키
GEMINI_MODEL=gemini-2.0-flash
GROUNDING_MODEL=gemini-2.5-flash
DRY_RUN=true
LOG_LEVEL=INFO
```

3. `modules/gemini_module.py`에서 모델을 선택하는 로직에 `gemma-3-27b-it` 옵션을 추가하고 싶으면 OpenHands 채팅창에 다음처럼 요청함.

```
modules/gemini_module.py 에 GEMMA_MODEL 환경변수(기본값 gemma-3-27b-it)를 추가하고,
/post 명령처럼 품질 요구가 낮고 반복량이 많은 일상 콘텐츠 생성 시에는 GEMMA_MODEL을,
/soap, /ddx 처럼 실시간성이 중요한 명령은 GEMINI_MODEL을 사용하도록 분기 로직을 넣어줘.
수정 후 커밋/push 해줘.
```

## 6단계. 전체 시스템 실행

1. 터미널에서 가상환경을 활성화함.

```bash
cd doctor_assist_project
python -m venv .venv
source .venv/bin/activate    # Windows PowerShell은 .venv\Scripts\activate
pip install -r requirements.txt
```

2. 웹 대시보드를 실행함.

```bash
uvicorn control_tower.web_dashboard.app:app --host 0.0.0.0 --port 7860 --reload
```

3. 브라우저에서 `http://localhost:7860`으로 접속함.
4. 좌측 메뉴에서 **Research** 탭을 클릭함.
5. 리서치 주제를 입력창에 작성하고(예: "고지혈증 최신 치료 가이드라인") **Start Job**(또는 실행) 버튼을 클릭함.
6. 잡이 완료되면 **Jobs & System** 탭에서 상태를 확인하고, 완료 후 **Library & Review** 탭에서 결과(`manifest.json`, `evidence_bundle.json`, `sources.json`)를 검토함.
7. 별도 터미널을 하나 더 열어 Telegram 봇도 실행함.

```bash
python control_tower/telegram_bot/bot_main.py
```

## 7단계. 검증 체크리스트

| 확인 항목 | 확인 방법 |
|---|---|
| Docker/OpenHands 정상 구동 | `http://localhost:3000` 접속, 채팅 응답 확인 |
| Gemini Flash 프로필 동작 | 프로필 선택 버튼에서 Flash 프로필 선택 후 빠른 응답 확인 |
| Gemma 프로필 동작 | 프로필 선택 버튼에서 Gemma 프로필 선택 후 대량 요청 응답 확인 |
| GitHub push 정상 | OpenHands 채팅창 로그에 커밋 해시와 브랜치명(`main`) 출력 확인 |
| OpenManus 리서치 정상 | `data/research/` 폴더에 잡 폴더와 evidence_bundle.json 생성 확인 |
| DRY_RUN 유지 | `.env`의 `DRY_RUN=true` 값 확인, 실제 SNS 게시 안 됨 확인 |

## 운영 주의사항

- 환자 식별정보(PHI)는 OpenManus, Gemini, Telegram, Git 어디에도 절대 입력하지 않음.
- Gemini API 키는 `.env`에만 두고 코드나 커밋 메시지에 포함하지 않음.
- 웹 대시보드(`localhost:7860`)는 인증 레이어 구성 전까지 외부에 노출하지 않음.
- OpenManus 잡은 초기 단계에서는 한 번에 하나씩만 실행함(리소스 경합 방지).
- Gemini Flash는 실시간 임상 보조 명령에, Gemma는 무료 쿼터 절약이 필요한 대량 반복 작업(리서치 요약, 일상 콘텐츠)에 배정하는 분업 원칙을 유지함.
