# Doctor Assist Project

임상의사(가정의학과 봉직의/개원의)를 위한 AI Agent 통합 프로젝트입니다.

## 목표
- 외래 진료 보조 (감별진단, 환자 설명문, SOAP 변환)
- 보험 고시 자동 모니터링
- 콘텐츠 자동화 (블로그/인스타/스레드)
- 연구 보조 (논문 큐레이션, PubMed 자동화)

## 기술 스택
- **LLM**: Gemini API (Free tier), Perplexity Web
- **자동화 엔진**: n8n (self-hosted, 24/7 홈 PC)
- **프론트엔드**: Antigravity (웹 대시보드)
- **소스 관리**: Google Drive, Gmail, Google Calendar

## 폴더 구조
```
doctor_assist_project/
├── README.md
├── doctor_assist_bot_plan.md          # 전체 프로젝트 계획
├── docs/
│   ├── feature_specs/                 # 기능별 상세 명세
│   │   ├── feature_01_branding.md
│   │   ├── feature_02_event.md
│   │   ├── feature_03_paper_crawl.md
│   │   ├── feature_04_patient_handout.md
│   │   ├── feature_05_calendar.md
│   │   ├── feature_07_quicknote.md
│   │   ├── feature_12_insurance_monitor.md
│   │   └── feature_13_staff_notice.md
│   ├── harness/                       # 인프라 설정
│   │   ├── harness_overview.md
│   │   ├── harness_n8n_setup.md
│   │   ├── harness_gemini_api.md
│   │   ├── harness_telegram_bot.md
│   │   ├── harness_cloudflare_tunnel.md
│   │   └── grounding_sources.md       # 팩트체킹 소스 정책
│   └── prompts/                       # LLM 프롬프트 명세
│       ├── prompt_patient_explanation.md
│       ├── prompt_insurance_monitor.md
│       └── prompt_staff_notice.md
```

## Grounding 정책 요약
모든 AI 생성 의학 정보는 아래 순서로 검증:
1. **PubMed E-utilities** (임상 근거)
2. **HIRA/NHIS 보험 고시 크롤링** (급여 기준)
3. **Perplexity Web** (Fallback)
