# Harness — Cloudflare Tunnel 설정

## 목적
홈 PC에서 실행 중인 n8n 대시보드에 병원 외부(외래 중 스마트폰 등)에서 안전하게 접근한다.

## 설치

```bash
# cloudflared 설치 (Linux)
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# 인증
cloudflared tunnel login

# 터널 생성
cloudflared tunnel create doctor-assist-tunnel

# 실행
cloudflared tunnel run --url http://localhost:5678 doctor-assist-tunnel
```

## 무료 임시 터널 (테스트용)

```bash
cloudflared tunnel --url http://localhost:5678
# 자동으로 *.trycloudflare.com URL 발급
```

## 보안 설정
- n8n Basic Auth 필수 활성화
- Cloudflare Access Policy로 이메일 인증 추가 권장
- HTTPS 자동 적용 (Cloudflare 제공)
