# Doctor Assist Bot — 전체 프로젝트 계획

## 개요

가정의학과 봉직의/개원의 선생님이 외래 진료, 연구, 브랜딩을 AI로 효율화하기 위한 통합 시스템.

## 핵심 제약 조건
- 추가 LLM 구독 없음 (Gemini API 무료, Perplexity Web, Google AI Pro 기존 구독)
- 추가 장비 구입 없음 (24/7 홈 PC 활용)
- EMR 연동 불확실 → EMR 외부에서 독립 동작
- 외래 진료 중 즉시 사용 가능한 기능 우선

## 도구 역할 분담

| 도구 | 역할 |
|---|---|
| Gemini API (Free) | 메인 LLM 백엔드 (1,500 req/일, 1M 토큰 컨텍스트) |
| Perplexity Web | 실시간 논문/가이드라인 검색 |
| Antigravity | 웹 대시보드 프론트엔드 |
| n8n (self-hosted) | 자동화 워크플로우 엔진 |
| Google Drive | 문서 저장, 초음파 이미지 업로드 |
| Gmail/Calendar | 알림, 환자 리마인더 |
| Meta Graph API | Instagram/Threads 자동 발행 |
| PubMed E-utilities | 임상 근거 Grounding |
| HIRA 크롤링 | 보험 고시 Grounding |

## 전체 기능 목록

### 외래 보조 기능
- Feature 07: 빠른 메모 → SOAP 변환
- Feature 04: 환자 설명문 즉석 생성
- Feature 02: 감별 진단 보조 (초음파 이미지 포함)

### 자동화 기능
- Feature 12: 보험 고시 모니터링
- Feature 13: 직원 공지 자동 생성
- Feature 03: 논문 크롤링 및 큐레이션
- Feature 05: Google Calendar 연동

### 브랜딩/수익화
- Feature 01: SNS 콘텐츠 자동화 (블로그/인스타/스레드)

## 구현 로드맵

| 주차 | 작업 | 예상 시간 |
|---|---|---|
| 1주차 | n8n 홈 서버 설치 + Gemini API 연동 | 2시간 |
| 1주차 | Antigravity 대시보드 기본 틀 | 3시간 |
| 2주차 | 외래 보조 패널 완성 | 4시간 |
| 2주차 | Instagram Graph API 연동 | 3시간 |
| 3주차 | Threads API + 블로그 자동 발행 | 5시간 |
| 4주차 | 콘텐츠 검토-승인-발행 UI | 4시간 |
| 상시 | 야간 자동화 (환자 리마인더, 논문 큐레이션) | 1시간 |

**총 예상 구현 시간**: 약 22시간
**추가 비용**: 0원
