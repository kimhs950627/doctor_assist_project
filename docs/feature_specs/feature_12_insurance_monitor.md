# Feature 12 — 보험 고시 자동 모니터링

## 목적
심사평가원(HIRA) 및 건강보험공단(NHIS) 고시를 매일 자동 크롤링하여 진료에 영향을 주는 변경 사항을 즉시 알린다.

## 크롤링 대상

| 소스 | URL |
|---|---|
| 심사평가원 공지사항 | `https://www.hira.or.kr/bbsDummy.do?pgmid=HIRAA020002000100` |
| 요양급여 기준 고시 | `https://www.hira.or.kr/bbsDummy.do?pgmid=HIRAA020002000200` |
| 의약품안전나라 | `https://nedrug.mfds.go.kr/pbp/CCBGA01/getItem` |
| 건강보험 포털 | `https://www.nhis.or.kr/nhis/policy/wbhada03200m01.do` |

## n8n 워크플로우

```
[매일 06:00 스케줄 트리거]
    │
    ▼
[HTTP Request — 공지 목록 수집]
    Headers: User-Agent: Mozilla/5.0 (compatible; doctor-assist-bot)
    │
    ▼
[Code 노드 — 키워드 필터]
    포함 키워드: ["급여", "수가", "고시", "행위", "약제", "가정의학", "외래", "초음파"]
    │
    ▼
[HTTP Request — 상세 페이지 본문 추출]
    CSS Selector: ".board_view_content" 또는 ".cont_wrap"
    │
    ▼
[Gemini API — 요약 + 임상 영향 분석]
    → prompt_insurance_monitor.md 프롬프트 사용
    │
    ▼
[Switch 노드 — HIGH / MID / LOW 분류]
    HIGH → Telegram 즉시 알림 + Google Calendar 등록
    MID  → 주간 브리핑에 포함
    LOW  → 아카이브만
```

## 크롤링 실패 대응
```
HTTP 403/429 발생 시:
  1. 재시도 간격: 60초 후 1회 재시도
  2. User-Agent 로테이션 (3종)
  3. 2회 연속 실패 → Telegram 수동 확인 요청 알림
```

---

## Grounding 정책 (→ grounding_sources.md 참조)

기능 12는 **보험 고시 크롤링이 Primary 소스**다.

### 데이터 흐름
```
HIRA 공지사항 크롤링 (매일 06:00)
    │
    ├─ 급여 기준 변경 감지
    │       └─ PubMed 연계: 변경된 약물/행위의 최신 임상 근거 자동 수집
    │
    └─ 수가 변경 감지
            └─ 보험 포털 교차 검증 (NHIS 공지)

임상 근거 ↔ 보험 고시 불일치 시:
  → "⚠️ 임상 근거 충분하나 급여 제한" 또는
    "⚠️ 급여 인정되나 임상 근거 제한적" 레이블 부착
```

### 크롤링 실패 시 Fallback
HIRA 크롤링 2회 연속 실패 → Perplexity로 동일 키워드 검색
→ 결과에 `⚠️ 크롤링 실패, Perplexity 대체` 명시
