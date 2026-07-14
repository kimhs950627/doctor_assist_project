# Doctor Assist Project — System Architecture

> 최종 수정: 2026-07-15  
> 이 문서는 시스템 설계 결정 사항(Architecture Decision Record)을 기록한다.

---

## 1. 설계 원칙

- **Human-in-the-loop**: LLM 생성 결과(환자 설명자료, 블로그 초안, 통계 해석)는 의사 검토 및 승인 후에만 외부로 전달·발행된다.
- **Privacy by default**: 환자 식별 정보(PHI)는 외부 LLM API 호출 전 반드시 비식별화(de-identification)한다. PHI를 Git 이력, Telegram 메시지, 블로그 초안, 공개 터널에 포함하지 않는다.
- **Vendor-agnostic EMR**: EMR 업체 확정 전까지는 CSV/XLSX export 기반으로 시작하고, FHIR/API 연동은 이후 단계에서 추진한다.
- **최소한의 복잡도**: 현재 필요한 것만 구현한다. 투기적 기능 추가를 금지한다.

---

## 2. 시스템 전체 구조

```
[브라우저 / Telegram]
        │
Cloudflare Access (MFA + identity allow list)
        │
Cloudflare Tunnel (HTTPS, 고정 도메인)
        │
Galaxy Note 20 — Termux + Ubuntu (ARM64, proot-distro)
        │
┌───────────────────────────────────────────┐
│  FastAPI (API / Webhook / Orchestration)  │
│  Streamlit  (의사 전용 웹 대시보드)          │
│  Telegram Bot  (모바일 명령 / 알림 채널)     │
│  Job Scheduler + Audit Log               │
│  Encrypted Local SQLite / File Store     │
└───────────────────────────────────────────┘
        │               │               │
   Gemini API     EMR Export       Naver Share
  (비식별화 후 호출)  (CSV/XLSX)    Handoff (수동 발행)
```

---

## 3. 하드웨어 및 OS

| 항목 | 선택 | 비고 |
|---|---|---|
| 기기 | Galaxy Note 20 | Snapdragon 865, RAM 12GB |
| OS | Termux + proot-distro Ubuntu (ARM64) | 루팅 불필요 |
| 서비스 관리 | Termux 서비스 혹은 nohup | systemd 대체 |
| 전원 | 상시 충전 유지 + 배터리 최적화 예외 설정 | 발열 관리 필수 |

---

## 4. 원격 접속 (Remote Access)

- **Cloudflare Tunnel**: `cloudflared` ARM64 바이너리 설치 → 포트 포워딩 없이 외부 HTTPS 고정 도메인 부여.
- **Cloudflare Access**: 브라우저 접근에 MFA + 이메일/디바이스 기반 허용 목록 적용. 인증되지 않은 요청은 Tunnel 진입 전에 차단.
- **Tailscale**: 관리자 SSH 전용 내부망 VPN. 외부 공개 없이 기기 간 안전한 shell 접근.

---

## 5. 핵심 서비스 컴포넌트

| 컴포넌트 | 기술 | 역할 |
|---|---|---|
| API 서버 | FastAPI (async) | 라우팅, LLM 오케스트레이션, Telegram webhook |
| 대시보드 | Streamlit | 의사 전용 UI — 설명자료 검토, EMR 업로드, 통계 |
| Telegram Bot | python-telegram-bot v20+ | 모바일 명령어, job 완료 알림, 승인 링크 전송 |
| LLM 클라이언트 | Gemini API (google-generativeai) | 환자 교육 초안, 통계 해석, 블로그 초안 생성 |
| 데이터 저장 | SQLite (암호화) | 작업 메타데이터, 템플릿, 집계 지표, audit log |

---

## 6. 주요 워크플로우

### A. 환자 맞춤 설명자료 생성
1. 의사가 Streamlit 또는 Telegram에서 최소 필요 임상 정보 입력 (비식별화 확인)
2. FastAPI → Gemini API 호출 → 한국어 설명자료 초안 반환
3. 의사가 대시보드에서 검토·수정·승인
4. PDF/텍스트 출력 (Phase 1에서는 자동 환자 전송 없음)

### B. EMR 운영 통계 분석
1. EMR에서 정기 CSV/XLSX 내보내기 → 보호된 대시보드에 업로드
2. 벤더별 adapter가 컬럼 매핑 → 정규화 스키마로 변환
3. 집계 지표 계산: 외래 건수, 신환/재진 비율, 수가별 mix, 미수금, 팔로업 대상 등
4. Gemini는 집계된 숫자를 해석하는 역할만 수행 (개별 환자 raw data를 LLM에 전달하지 않음)

### C. 네이버 블로그 콘텐츠 자동화
1. Gemini API로 의학 콘텐츠 초안 생성 (환자 정보 절대 포함 금지)
2. 대시보드 review queue에 저장 → 의사 승인
3. 승인 후: **복사-붙여넣기 또는 Naver Share API 핸드오프 → 의사가 직접 최종 발행**
4. 발행 URL 및 승인 이벤트를 audit log에 기록

---

## 7. 네이버 블로그 API 정책 결정

> **결론: 공식 직접 포스팅 API 미지원 → Draft & Manual Publish 정책 채택**

네이버는 로그인 기반 블로그 글쓰기 Open API(`writePost`)를 **2020년 5월 6일부로 종료**하였다.  
종료 사유: 기계적 반복·유사 콘텐츠 대량 발행 어뷰징.  
현행 공식 Open API 목록에는 블로그 게시물 등록 엔드포인트가 없고, Search API와 Share 기능만 제공된다.

**채택하지 않는 방식:**
- Selenium / Playwright 기반 브라우저 자동화 (계정 정지 리스크, 운영 취약성)
- 크리덴셜 스크래핑 / CAPTCHA 우회

**채택하는 방식:**
```
BlogDraftService
  → Gemini 초안 생성
  → 의사 review queue (Streamlit)
  → 승인 후 copy-ready 패키지 또는 Naver Share handoff
  → 의사가 최종 발행 버튼 클릭
  → 발행 URL + audit log 기록
```

---

## 8. 보안 및 개인정보 통제

- **Secrets 관리**: `.env` 파일에만 보관 (GEMINI_API_KEY, Telegram Token, Cloudflare 인증, OAuth). Git commit 절대 금지.
- **PHI 처리 원칙**: 이름, 주민등록번호, 전화번호, 생년월일, EMR ID, 영상, 자유 기술 노트는 법적·보안 검토 없이 외부 LLM에 전송하지 않는다.
- **Audit Log**: 행위자, 시각, 액션, 리소스 ID, 승인 상태, 성공/실패를 기록. 프롬프트 내용·PHI는 로그에 포함하지 않는다.
- **장치 보안**: 저장소 및 백업 암호화, 잠금화면 알림 미리보기 비활성화, 필수 서비스에 한해 Android 배터리 최적화 예외 설정.

---

## 9. 레포지토리 구조

```
doctor_assist_project/
├── control_tower/          # FastAPI 라우터, Telegram 봇, Streamlit 대시보드
├── modules/
│   ├── llm_client.py       # Gemini API wrapper (de-identification boundary)
│   ├── emr_contract.py     # 정규화 스키마 및 컬럼 매핑 검증
│   ├── emr_analytics.py    # 집계 지표 계산 (synthetic fixture 테스트 포함)
│   ├── patient_explainer.py# 환자 설명자료 파이프라인
│   └── blog_drafts.py      # 초안·검토·export·발행 확인 워크플로우
├── data/                   # 런타임 데이터 (Git 제외, .gitignore)
├── docs/                   # 운영 절차, 데이터 계약, 프롬프트 템플릿
├── tests/                  # 합성 데이터 기반 테스트만
├── ARCHITECTURE.md         # 이 문서 (시스템 결정 기록)
├── .env.example            # Secret 이름만 기재, 실제 값 절대 미포함
└── README.md               # 설치 및 운영자 Quick Start
```

---

## 10. 단계별 로드맵 (Phased Delivery)

| Phase | 목표 | 완료 기준 |
|---|---|---|
| 0. Foundation | Note 20 Termux+Ubuntu, Git, `.env`, FastAPI health check | 재시작 후에도 서비스 정상 복구, secret Git 미추적 확인 |
| 1. Protected Control | Cloudflare Access/Tunnel, Tailscale SSH, Telegram allow list | 미인가 요청 차단 확인, audit event 기록 |
| 2. Clinical Drafts | Gemini 환자 설명자료 + 검토/export 워크플로우 | 합성 케이스로 한국어 handout 생성 및 승인 흐름 확인 |
| 3. EMR Analytics | CSV/XLSX contract + 월별 대시보드 | 잘못된 파일 거부, 합성 fixture로 리포트 재현 가능 |
| 4. Content Workflow | 블로그 초안·검토·복사·Share 핸드오프 | 환자 정보 미포함 확인, 발행 전 명시적 승인 필수 |
| 5. Vendor Integration | EMR 공식 인터페이스 검토 | 데이터 계약·인가·보안 검토·통합 테스트 승인 |

---

## 11. 근접 결정 사항 (Near-term Decisions)

1. Note 20 루팅 여부 확인 → 일반 Linux container 사용 가능 여부 결정
2. 첫 번째 비PHI 워크플로우 선택: 환자 교육 초안 vs 합성 EMR 분석
3. EMR 업체 선정 후 샘플 비식별화 CSV만 받아 첫 adapter contract 정의
4. Gemini 프로젝트 등록 + 예산/쿼터 알림 설정 (워크플로우 연결 전)
5. 어떤 대시보드 URL 공개 전에도 Cloudflare Access + Tailscale 먼저 구성
