# Feature 07 — 빠른 메모 → SOAP 변환

## 목적
외래 진료 후 짧은 음성 메모를 SOAP 형식으로 자동 변환하여 차팅 시간을 80% 단축한다.

## 워크플로우

```
[스마트폰 녹음 앱 — 진료 후 10~30초 메모]
    │
    ▼
[Google Drive 자동 업로드]
    │
    ▼
[n8n — 파일 감지 트리거]
    │
    ▼
[Gemini API — 오디오 파일 직접 분석]
    Prompt: 아래 진료 메모를 SOAP 형식으로 변환:
    - Subjective: 환자 주호소
    - Objective: 검사 소견, 바이탈
    - Assessment: 진단/감별
    - Plan: 처방, 추적 계획
    │
    ▼
[대시보드 표시]
    └─ 복사-붙여넣기로 기존 EMR 입력
```

## 기술 사항
- Gemini는 오디오 파일 네이티브 처리 가능 (wav, mp3, m4a)
- EMR 직접 연동 불필요 — 복사-붙여넣기 방식
- 처리 시간: 약 5~10초

## 텍스트 메모 입력 모드
음성 대신 텍스트로 입력 가능:
대시보드의 텍스트 입력창 → `SOAP 변환` 버튼

---

## Grounding 정책 (→ grounding_sources.md 참조)

환자 설명문에 포함되는 의학적 주장은 아래 순서로 검증한다:

1. **PubMed E-utilities** (Priority 1)
   - 진단명 + 치료 키워드로 ESearch → 최신 3편 초록 수집
   - 일치 시 `✅ PubMed n편 확인` 레이블 표시

2. **보험 고시 크롤링** (Priority 2, 처방 관련에 한함)

3. **Perplexity** (Fallback)
   - PubMed 0건 AND 고시 미해당 시에만 사용
   - `⚠️ Perplexity 참고` 레이블 자동 부착

### 빠른 검증 모드 (외래 중 사용)
외래 중 속도가 중요할 때는 grounding을 **비동기**로 실행한다.
설명문을 먼저 표시하고, 백그라운드에서 PubMed 확인 완료 후 레이블 업데이트.
