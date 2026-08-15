# SKILL: dr7.ai Medical API 사용법 (MedGemma 등)

## 개요
dr7.ai는 MedGemma, Med-PaLM 2, BioGPT 등 15종 이상 의료 특화 모델을 단일 OpenAI 호환 엔드포인트로 제공하는 unified API 서비스임. 본 스킬은 doctor_assist_project 내에서 Gemini API를 dr7.ai API로 교체(또는 병행)할 때 참고하는 가이드임.

## 인증 및 엔드포인트
```
POST https://dr7.ai/api/v1/medical/chat/completions
Authorization: Bearer sk-dr7-your-api-key
Content-Type: application/json
```
요청 바디는 OpenAI chat.completions 포맷과 동일 (`model`, `messages`, `max_tokens`, `temperature`).

## 지원 모델 (텍스트 기준, 2026-08 확인)
| 모델 | 용도 | Input/1K | Output/1K |
|---|---|---|---|
| medgemma-4b-it | 경량 의료 상담 | $0.001 | $0.002 |
| medgemma-27b-it | 고급 진단/추론 | $0.003 | $0.006 |
| med-palm-2 | 임상 QA | $0.001 | $0.002 |
| biogpt | 문헌 마이닝 | $0.001 | $0.002 |
| meditron | 감별진단 | $0.001 | $0.002 |
| chexagent / llava-med / med-flamingo (비전) | 영상 판독 | $0.002 | $0.004 |
| medsiglip-v1 | 영상 임베딩/분류 | $0.005 | $0.002 |

플랜: Free($0, API 미제공) / Standard($9.99/월, $5 크레딧, MedGemma-4B만) / Pro($49.99/월, $25 크레딧, 전체 모델) / Clinical+($199.99/월~).

## Gemini API와 요금 비교 (1M 토큰 기준 환산)
| 구분 | Input/1M | Output/1M |
|---|---|---|
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 |
| Gemini 2.5 Flash | $0.30 | $2.50 |
| Gemini 2.5 Pro (≤200K) | $1.25 | $10.00 |
| MedGemma 4B (dr7.ai) | $1.00 | $2.00 |
| MedGemma 27B (dr7.ai) | $3.00 | $6.00 |

**결론**: dr7.ai를 통한 MedGemma는 동급 Gemini Flash 계열보다 토큰당 단가가 훨씬 비쌈(4B가 Flash-Lite의 약 10배). 다만 MedGemma는 의료 도메인 특화 파인튜닝(Gemma 3 기반, MedQA 등에서 범용 Gemma 대비 고득점)이라 순수 가격만으로 비교는 부적절함. Google이 Hugging Face/Vertex AI로 MedGemma 가중치 자체를 무료 공개(연구/상업 이용 가능)하고 있어, 자체 호스팅(Vertex AI 또는 로컬 GPU) 시 dr7.ai 중개 수수료 없이 컴퓨트 비용만 지불 가능함.

## 웹서칭(보험코드 등) 가능 여부
- dr7.ai 공식 문서(`/docs`, `/access-api`, `/pricing`)에 web search/grounding/tool-use/function-calling 관련 기능 언급 없음. 엔드포인트는 순수 chat completion만 제공함.
- 즉 dr7.ai API 자체로는 실시간 웹 검색(건강보험심사평가원 고시, 수가코드 조회 등)을 수행할 수 없음. 별도 RAG 파이프라인(예: 자체 웹서치 함수를 tool로 정의 후 OpenAI 호환 function-calling 규격으로 붙여야 함)을 구축해야 하나, dr7.ai가 function-calling을 지원하는지도 문서에 명시 안 됨 → 검증 필요(무료 티어로 실제 호출 테스트 권장).
- 반면 Gemini API는 `google_search` 내장 tool을 제공하여 실시간 웹 grounding + 인용을 기본 지원함. 보험코드/고시 정보처럼 최신성이 중요한 태스크는 현재 Gemini 쪽이 구조적으로 유리함.

## 권장 아키텍처 (하이브리드)
1. 보험코드/고시/최신 가이드라인 검색 등 "grounding이 필요한 작업" → Gemini API(`google_search` tool) 유지.
2. 순수 의학 텍스트 추론/감별진단/초음파 소견 요약 등 "도메인 정확도가 중요한 작업" → dr7.ai MedGemma-27B 시범 적용, 비용 대비 성능 A/B 테스트.
3. 두 API를 라우터(`control_tower/router.py`)에서 태스크 종류별로 분기하는 방식을 권장. dr7.ai는 OpenAI 호환 스펙이므로 `openai` SDK의 `base_url`만 교체하면 기존 코드 재사용 가능.

## 로컬/자체 호스팅 대안
- MedGemma 4B/27B는 Hugging Face(`google/medgemma-4b-it`, `google/medgemma-27b-it`)에서 가중치 무료 다운로드 가능(HAI-DEF 이용약관 동의 필요).
- 로컬 실행 시 4B는 VRAM 16GB급, 27B는 48GB급 GPU 권장. 미니PC 환경이면 4B가 현실적.
- Vertex AI Model Garden 배포 시 dr7.ai 중개 없이 Google 인프라 비용만 발생, 최신 버전(MedGemma 1.5) 반영도 더 빠름.

## 미확인/추가 검증 필요 사항
- dr7.ai의 function-calling/tool 지원 여부 (문서 미기재, 실제 API 호출로 확인 필요)
- dr7.ai의 HIPAA/개인정보 처리 방침이 국내 의료정보 보호 규정과 호환되는지
- Free 플랜은 API 접근 자체가 잠겨 있어(🔒) 실사용 테스트는 최소 Standard($9.99) 결제 필요
