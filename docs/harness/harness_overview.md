# Harness Overview — 인프라 전체 구조

## 시스템 아키텍처

```
[통합 웹 대시보드 — 브라우저에서 접근]
         │
         ├─ 섹션 A: 외래 보조 도구 (진료 중 실시간)
         ├─ 섹션 B: 콘텐츠 공장 (블로그/인스타/스레드 자동화)
         ├─ 섹션 C: 연구 어시스턴트
         └─ 섹션 D: 환자 관리 자동화
                  │
         [n8n 자체 호스팅 — 홈 PC 24/7]
                  │
    ┌─────────────┼─────────────────┐
 Gemini API    Google Drive      Meta Graph API
 (무료)        Gmail/Calendar    (Instagram+Threads)
    │
 PubMed E-utilities + HIRA 크롤링 (Grounding)
```

## 구성 요소

| 구성 요소 | 역할 | 참고 문서 |
|---|---|---|
| n8n self-hosted | 워크플로우 자동화 엔진 | harness_n8n_setup.md |
| Gemini API | LLM 백엔드 | harness_gemini_api.md |
| Telegram Bot | 알림 채널 | harness_telegram_bot.md |
| Cloudflare Tunnel | 외부 접근 보안 | harness_cloudflare_tunnel.md |
| PubMed E-utilities | 임상 근거 Grounding | grounding_sources.md |
| HIRA 크롤링 | 보험 고시 Grounding | grounding_sources.md |

---

## Grounding 소스 아키텍처

```
[AI 답변 생성 완료]
        │
        ▼
[Grounding 분기 판단 — n8n Switch 노드]
        │
        ├─ 임상/약물 관련 ──→ PubMed E-utilities (Priority 1)
        │                      ESearch → EFetch → Gemini 검증
        │                      → ✅ / ⚠️ / ❌ 레이블
        │
        ├─ 보험/수가 관련 ──→ HIRA 크롤링 (Priority 2)
        │                      공지사항 → Gemini 요약
        │                      → 근거 확인 or 크롤링 실패 시 Perplexity
        │
        └─ 기타 ────────────→ Perplexity Fallback
                               → "⚠️ Perplexity 참고" 레이블
```

관련 문서: `docs/harness/grounding_sources.md`
