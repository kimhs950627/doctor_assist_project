# Feature 01 — SNS 콘텐츠 자동화 (브랜딩)

## 목적
블로그, Instagram, Threads에 의학 콘텐츠를 자동으로 생성·발행하여 셀프 브랜딩 및 수익화 기반을 구축한다.

## 콘텐츠 카테고리 (자동 로테이션)
- `가정의학과 의사의 AI 활용기` — 개발자 정체성 브랜딩
- `흔한 증상, 놓치기 쉬운 진단` — 임상 교육
- `초음파로 발견한 것들` — 전문성 시각화
- `KNHANES 데이터로 본 한국인 건강` — 연구 기반 대중화
- `개원의/봉직의가 AI를 쓴다면` — B2B 타겟

## n8n 워크플로우

```
[매일 08:00 스케줄 트리거]
    │
    ├─ Perplexity API → 의학 최신 뉴스 3건 수집
    ├─ Google Keep → 전날 진료 메모 확인
    │
    ▼
[Gemini API — 콘텐츠 생성]
    ├─ 블로그 포스트 초안 (SEO 포함, 900~1,200자)
    ├─ Instagram 캡션 (이모지 + 해시태그 20개)
    └─ Threads 포스트 (500자 이내, 의견형)
    │
    ▼
[대시보드 검토 큐]
    └─ 승인 / 수정 / 거절
    │
    ▼
[자동 발행]
    ├─ 네이버 블로그 또는 WordPress
    ├─ Instagram Graph API v23.0
    └─ Threads API
```

## API 연동

### Instagram Graph API
- 엔드포인트: `https://graph.instagram.com/v23.0/`
- 2단계 발행: 미디어 컨테이너 생성 → `media_publish`
- 장기 액세스 토큰 60일 갱신 자동화

### Threads API
- 엔드포인트: `https://graph.threads.net/v1.0/`
- Instagram API보다 단순한 연동 구조
- n8n HTTP Request 노드로 직접 POST

## 이미지 생성
- Canva API 또는 Google Drive 저장 템플릿 활용
- 추가 이미지 생성 서비스 구독 불필요
