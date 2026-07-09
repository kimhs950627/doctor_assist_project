# Harness — Gemini API 설정

## 무료 티어 한도 (2026 기준)
- 요청 수: 1,500 req/일
- 토큰: 1,000,000 TPM (분당)
- 컨텍스트: 최대 1M 토큰
- 모델: gemini-2.0-flash (무료), gemini-2.5-pro (유료)

## API 키 발급
1. https://aistudio.google.com 접속
2. `Get API Key` → 프로젝트 선택
3. API 키 복사 → n8n Credentials에 저장

## n8n HTTP Request 노드 설정

```
Method: POST
URL: https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}
Headers:
  Content-Type: application/json
Body:
  {
    "contents": [{"parts": [{"text": "{{$json.prompt}}"}]}],
    "generationConfig": {
      "temperature": 0.3,
      "maxOutputTokens": 2048
    }
  }
```

## 멀티모달 (이미지 + 텍스트)

```json
{
  "contents": [{
    "parts": [
      {"text": "이 초음파 소견을 분석해줘:"},
      {
        "inline_data": {
          "mime_type": "image/jpeg",
          "data": "{{$json.base64_image}}"
        }
      }
    ]
  }]
}
```

## Gemini Gems (커스텀 AI)
- https://gemini.google.com/gems 접속
- `새 Gem 만들기` → 시스템 프롬프트 + 참고 문서 업로드
- 추천 Gems:
  - 가정의학과 외래 코파일럿
  - 처방 전 약물 상호작용 체크봇
  - 환자 설명 생성기
  - 보험 고시 요약봇
