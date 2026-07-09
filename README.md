# Doctor Assist Project

> 가정의학과 봉직의/개원의 AI 통합 어시스턴트  
> **컨트롤 타워 2개**: 웹 대시보드 + 텔레그램 봇

---

## 아키텍처

```
doctor_assist_project/
├── modules/                    ← 공유 통합 모듈 (import해서 사용)
│   ├── gemini_module.py        ← Gemini API 래퍼
│   ├── telegram_module.py      ← Telegram Bot 래퍼
│   └── instagram_module.py     ← Instagram + Threads API 래퍼
│
├── control_tower/
│   ├── web_dashboard/
│   │   └── app.py              ← FastAPI 웹 대시보드 (컨트롤 타워 1)
│   └── telegram_bot/
│       └── bot_main.py         ← Telegram Bot (컨트롤 타워 2)
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## 빠른 시작

### 1. 환경 설정

```bash
cp .env.example .env
# .env 파일에서 API 키 설정
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3-A. 웹 대시보드 실행 (컨트롤 타워 1)

```bash
uvicorn control_tower.web_dashboard.app:app --host 0.0.0.0 --port 7860 --reload
# 브라우저에서 http://localhost:7860 접속
```

### 3-B. 텔레그램 봇 실행 (컨트롤 타워 2)

```bash
python control_tower/telegram_bot/bot_main.py
```

### 3-C. 동시 실행 (홈 서버 추천)

```bash
# 터미널 1
uvicorn control_tower.web_dashboard.app:app --host 0.0.0.0 --port 7860

# 터미널 2
python control_tower/telegram_bot/bot_main.py
```

---

## 모듈 사용법

### GeminiModule

```python
from modules.gemini_module import GeminiModule

gm = GeminiModule()  # GEMINI_API_KEY 환경변수

# 감별 진단 (텍스트 + 초음파 이미지)
ddx = gm.differential_diagnosis("우상복부 둔통 3개월", image_path="/tmp/us.jpg")

# SOAP 변환
soap = gm.to_soap("55세 남성 두통 3일 혈압 160/100")

# 환자 설명문
edu = gm.patient_education("제2형 당뇨", grade="중학교")

# 약물 상호작용
result = gm.check_drug_interaction(["메트포르민", "아스피린"], "클로피도그렐")

# SNS 초안 생성
draft = gm.generate_sns_draft("가정의학과 AI 활용기")
```

### InstagramModule / ThreadsModule

```python
from modules.instagram_module import InstagramModule, ThreadsModule, PublishRequest

ig = InstagramModule()
th = ThreadsModule()

req = PublishRequest(
    text="오늘 외래에서 있었던 일",
    media_urls=["https://example.com/img.jpg"],
    hashtags=["가정의학과", "AI의사"],
    dry_run=True,  # 테스트용
)

ig_result = ig.publish(req)
th_result = th.publish(req)
```

### TelegramBot

```python
from modules.telegram_module import TelegramBot

bot = TelegramBot()
bot.register_default_commands()

@bot.command("hello")
async def hello(update, context):
    await update.message.reply_text("안녕하세요!")

bot.run()
```

---

## 웹 대시보드 기능

| 탭 | 기능 |
|---|---|
| 🩺 외래 | 감별 진단, SOAP 변환, 환자 설명문, 약물 상호작용, Gemini 자유 질의 |
| 📱 SNS | 인스타그램/스레드 콘텐츠 초안 자동 생성 |
| 🚀 발행 | 초안 검토 후 인스타그램/스레드 즉시 발행 |

---

## 텔레그램 봇 커맨드

| 커맨드 | 설명 |
|---|---|
| `/start` | 시작 안내 |
| `/soap <메모>` | 진료 메모 → SOAP |
| `/ddx <증상>` | 감별 진단 5가지 |
| `/edu <진단명>` | 환자 설명문 |
| `/drug <현재약> \| <추가약>` | 약물 상호작용 |
| `/post <주제>` | SNS 초안 생성 + 승인 후 발행 |
| `/status` | 모듈 상태 확인 |
| `/ping` | 생존 확인 |

---

## 환경변수

| 변수명 | 설명 | 필수 |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio API 키 | ✅ |
| `TELEGRAM_BOT_TOKEN` | BotFather 발급 토큰 | 텔레그램 봇 사용 시 |
| `BOT_OWNER_CHAT_ID` | 선생님 텔레그램 채팅 ID | 텔레그램 봇 사용 시 |
| `INSTAGRAM_ACCESS_TOKEN` | Meta 장기 액세스 토큰 | SNS 발행 시 |
| `INSTAGRAM_USER_ID` | Instagram 비즈니스 계정 ID | SNS 발행 시 |
| `THREADS_ACCESS_TOKEN` | Threads 장기 액세스 토큰 | SNS 발행 시 |
| `THREADS_USER_ID` | Threads 계정 ID | SNS 발행 시 |
| `DRY_RUN` | `true`=실제 발행 안 함 | 선택 (기본 true) |

---

## sns-doctor-branding 연관성

이 프로젝트의 `modules/` 폴더는 [sns-doctor-branding](https://github.com/kimhs950627/sns-doctor-branding)의
`app/integrations/` 코드를 doctor_assist_project에 맞게 독립 패키지로 재설계했습니다.
외부 의존성 없이 `from modules.xxx import YYY` 형태로 바로 사용할 수 있습니다.
