# Harness — Telegram Bot 알림 설정

## 봇 생성
1. Telegram에서 @BotFather 검색
2. `/newbot` 명령 → 봇 이름/username 설정
3. API Token 발급 → n8n Credentials에 저장

## 알림 채널 구성

| 채널 | 용도 |
|---|---|
| 개인 DM | HIGH 등급 보험 고시, 크롤링 실패 알림 |
| 직원 그룹 | MID 등급 공지, 주간 브리핑 |

## n8n Telegram 노드 설정

```
Operation: Send Message
Chat ID: {{$env.TELEGRAM_CHAT_ID}}
Text: {{$json.message}}
Parse Mode: Markdown
```

## 메시지 포맷 예시

```
⚠️ *보험 고시 변경 감지*

📋 제목: 초음파 급여 기준 변경
📅 고시일: 2026-07-10
🏷️ 등급: HIGH

*요약*
복부 초음파 연간 급여 횟수 변경...

🔗 [원문 보기](https://hira.or.kr/...)
```
