# Harness — n8n Self-Hosted 설치 가이드

## 설치 환경
- 홈 PC (24/7 운영)
- Docker 기반 설치 권장
- 외부 접근: Cloudflare Tunnel (→ harness_cloudflare_tunnel.md)

## Docker Compose 설정

```yaml
version: '3.8'
services:
  n8n:
    image: n8nio/n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=YOUR_PASSWORD
      - WEBHOOK_URL=https://your-domain.trycloudflare.com
      - GENERIC_TIMEZONE=Asia/Seoul
    volumes:
      - ~/.n8n:/home/node/.n8n
```

## 실행
```bash
docker-compose up -d
# 접근: http://localhost:5678
```

## 주요 노드 목록

| 노드 | 용도 |
|---|---|
| Schedule Trigger | 스케줄 기반 자동 실행 |
| HTTP Request | PubMed API, HIRA 크롤링, Instagram API |
| Google Drive | 파일 감지, 업로드/다운로드 |
| Gmail | 이메일 발송 |
| Google Calendar | 일정 생성/수정 |
| Code (JavaScript) | 데이터 가공, 키워드 필터 |
| Switch | 조건 분기 (HIGH/MID/LOW) |
| Webhook | 대시보드에서 수동 트리거 |

## API 키 관리
- n8n Credentials 기능으로 모든 API 키 암호화 저장
- Gemini API Key, Google OAuth2, Meta App Token, Telegram Bot Token
