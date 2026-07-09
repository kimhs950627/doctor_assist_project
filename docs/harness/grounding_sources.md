# Grounding & Fact-Check 소스 정책

## 우선순위 원칙

모든 AI 생성 의학 정보의 팩트체킹 및 근거 검증은 아래 두 소스를 **이 순서대로** 우선한다.

```
[Priority 1] PubMed E-utilities   — 임상 근거 (효능, 안전성, 가이드라인)
[Priority 2] 보험 고시 크롤링     — 급여 기준, 수가, 청구 규칙
[Fallback]   Perplexity Web       — 위 두 소스에서 찾지 못한 경우에만
```

> ⚠️ Gemini, Perplexity 등 LLM의 답변은 반드시 위 소스로 검증 후 제공.
> ⚠️ 소스 미확인 답변에는 "⚠️ 근거 미확인" 레이블을 명시.

---

## Priority 1 — PubMed E-utilities

### 접근 정보
- Base URL: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- API Key: 무료 발급 → https://www.ncbi.nlm.nih.gov/account/
- Rate limit: 키 없이 3req/초 / 키 있으면 10req/초
- 필수 파라미터: `&tool=doctor_assist_bot&email={등록이메일}`

### 표준 Grounding 호출 시퀀스

```
Step 1 — ESearch (PMID 목록 수집)
  URL: /esearch.fcgi?db=pubmed&retmode=json
  &term={MeSH_query}&sort=date&retmax=5
  &datetype=pdat&mindate=2020&maxdate=2026

Step 2 — EFetch (초록 텍스트 수집)
  URL: /efetch.fcgi?db=pubmed
  &id={pmid1},{pmid2},...
  &rettype=abstract&retmode=text

Step 3 — Gemini 검증
  Prompt: "다음 논문 초록들이 아래 주장을 지지하는가?
  주장: {ai_claim}
  초록: {abstracts}
  결과: SUPPORTED / NOT_SUPPORTED / INSUFFICIENT"
```

### MeSH 쿼리 변환 규칙

| 임상 상황 | MeSH 쿼리 패턴 |
|---|---|
| 약물 효능 확인 | `{drug}[MeSH] AND {indication}[MeSH] AND clinical trial[pt]` |
| 안전성/부작용 | `{drug}[MeSH] AND adverse effects[sh] AND 2022:2026[pdat]` |
| 가이드라인 변경 | `{condition}[MeSH] AND practice guideline[pt] AND korea[ad]` |
| 한국인 데이터 | `{condition}[MeSH] AND korea[ad] AND 2020:2026[pdat]` |
| 감별 진단 | `{diagnosis1}[MeSH] AND {diagnosis2}[MeSH] AND diagnosis[sh]` |

### 검증 레이블 기준

| 결과 | 레이블 | 표시 |
|---|---|---|
| 논문 3편 이상 일치 | 근거 확인됨 | ✅ PubMed n편 확인 |
| 논문 1~2편 일치 | 제한적 근거 | ⚠️ 근거 제한적 (n편) |
| 논문 없거나 상충 | 근거 미확인 | ❌ PubMed 근거 없음 |

---

## Priority 2 — 보험 고시 크롤링

### 크롤링 대상 소스

| 소스 | URL | 업데이트 주기 |
|---|---|---|
| 심사평가원 공지사항 | `https://www.hira.or.kr/bbsDummy.do?pgmid=HIRAA020002000100` | 수시 |
| 요양급여 기준 고시 | `https://www.hira.or.kr/bbsDummy.do?pgmid=HIRAA020002000200` | 수시 |
| 의약품 안전나라 | `https://nedrug.mfds.go.kr/pbp/CCBGA01/getItem` | 수시 |
| 건강보험 포털 | `https://www.nhis.or.kr/nhis/policy/wbhada03200m01.do` | 수시 |

### 표준 크롤링 로직

```
Step 1 — 최신 공지 목록 수집
  Method: GET
  URL: HIRA 공지사항 URL
  Headers: User-Agent: Mozilla/5.0 (compatible; doctor-assist-bot)

Step 2 — 제목 필터링
  키워드: ["급여", "수가", "고시", "행위", "약제", "가정의학", "외래", "초음파"]

Step 3 — 상세 페이지 본문 추출
  CSS Selector: ".board_view_content" 또는 ".cont_wrap"

Step 4 — Gemini 요약 + 임상 영향 분석

Step 5 — 분류: HIGH / MID / LOW
  HIGH → Telegram 즉시 알림 + Google Calendar 등록
  MID  → 주간 브리핑에 포함
  LOW  → 아카이브만
```

### 크롤링 실패 대응

```
HTTP 403/429 발생 시:
  1. 재시도 간격: 60초 후 1회 재시도
  2. User-Agent 로테이션 (3종)
  3. 2회 연속 실패 → Telegram으로 수동 확인 요청 알림
```

---

## Fallback — Perplexity Web

위 두 소스에서 관련 내용을 찾지 못한 경우에만 사용한다.

- 사용 조건: ESearch 결과 0건 AND 보험 고시 미수집
- 레이블: "⚠️ Perplexity 참고 (PubMed 미확인)"
- 응답에 반드시 "전문의 재확인 권장" 문구 포함

---

## n8n 공통 Grounding 서브워크플로우

```
[트리거: Grounding 요청]
    │
    ├─ 의약품/임상 관련? → PubMed ESearch → EFetch → Gemini 검증
    │
    ├─ 보험/수가 관련? → HIRA 크롤링 → Gemini 요약
    │
    └─ 둘 다 해당 없음 → Perplexity
                          │
                최종 레이블 부착 → 응답에 ✅/⚠️/❌ 표시
```
