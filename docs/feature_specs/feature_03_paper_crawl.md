# Feature 03 — 논문 자동 큐레이션

## 목적
매주 최신 의학 논문을 자동 수집·요약하여 연구 생산성을 높이고 콘텐츠 소재로 활용한다.

## n8n 워크플로우

```
[매주 월요일 00:00 스케줄 트리거]
    │
    ▼
[PubMed E-utilities — ESearch]
    queries:
    - primary care[MeSH] AND artificial intelligence AND 2026[pdat]
    - functional constipation[MeSH] AND treatment AND 2026[pdat]
    - causal inference AND chronic disease AND korea AND 2026[pdat]
    - abdominal ultrasound AND deep learning AND 2026[pdat]
    - hypertension management AND primary care AND 2026[pdat]
    │
    ▼
[EFetch — 초록 텍스트 수집]
    │
    ▼
[Gemini API — 요약]
    Prompt: 이 5편의 논문에서 임상의로서 당장 활용 가능한
            내용 3가지를 한국어로 요약
    │
    ▼
[Google Docs 자동 저장 + Gmail 발송]
```

## 케이스 리포트 자동화

```
[Google Keep 메모 감지]
    │
    ▼
[Gemini — MeSH 키워드 3개 추출]
    │
    ▼
[ESearch → EFetch → ELink (유사 논문)]
    │
    ▼
[Gemini — 케이스 리포트 초안 작성]
    ├─ Introduction
    └─ 문헌 요약 섹션
    │
    ▼
[Google Docs 저장]
```

## 스노볼 샘플링 자동화
ELink `pubmed_pubmed_refs` 사용:
특정 논문이 인용한 모든 참고문헌 PMID 자동 수집
→ 베이지안 네트워크 연구 문헌 탐색에 적용

## Grounding
→ `docs/harness/grounding_sources.md` Priority 1 (PubMed E-utilities)
