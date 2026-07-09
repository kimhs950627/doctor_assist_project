"""웹 대시보드 컨트롤 타워 — FastAPI 기반.

실행::

    pip install fastapi uvicorn python-multipart
    uvicorn control_tower.web_dashboard.app:app --host 0.0.0.0 --port 7860 --reload

엔드포인트 목록:
    GET  /              → 대시보드 HTML
    POST /api/ask       → Gemini 일반 질의 (텍스트 + 선택적 이미지)
    POST /api/soap      → 진료 메모 → SOAP 변환
    POST /api/ddx       → 감별 진단
    POST /api/edu       → 환자 설명문
    POST /api/drug      → 약물 상호작용 체크
    POST /api/sns_draft → SNS 초안 생성
    POST /api/publish   → 인스타그램 + 스레드 발행
    GET  /api/health    → 모듈 상태 확인
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError as e:
    raise ImportError("fastapi, uvicorn 패키지가 필요합니다: pip install fastapi uvicorn python-multipart") from e

# modules 경로 추가 (프로젝트 루트 기준)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from control_tower.router import DoctorRouter, RouterResult

app = FastAPI(title="Doctor Assist Dashboard", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── 공유 라우터 (Gemini/Instagram/Threads 오케스트레이션) ──
# 두 컨트롤 타워(웹/텔레그램)가 공통으로 사용하는 비즈니스 로직 레이어.
router = DoctorRouter()


# ── 유틸 ─────────────────────────────────────────────────

async def _save_upload(file: UploadFile) -> str | None:
    if file is None or not file.filename:
        return None
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        return tmp.name


def _to_response(res: RouterResult, *, quota_code: int = 429, error_code: int = 503) -> JSONResponse:
    """RouterResult → JSONResponse. 쿼터 초과는 429, 그 외 설정/실패는 503."""
    if res.ok:
        return JSONResponse(res.data)
    code = quota_code if res.error and "쿼터" in res.error else error_code
    return JSONResponse({"error": res.error or "알 수 없는 오류"}, status_code=code)


# ── 헬스체크 ─────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict[str, Any]:
    return router.health()


# ── Gemini 엔드포인트들 ──────────────────────────────────

@app.post("/api/ask")
async def api_ask(
    question: str = Form(...),
    image: UploadFile | None = File(None),
) -> JSONResponse:
    img_path = await _save_upload(image) if image else None
    try:
        res = await asyncio.to_thread(router.handle_ask, question, img_path)
        return _to_response(res)
    finally:
        if img_path:
            Path(img_path).unlink(missing_ok=True)


@app.post("/api/soap")
async def api_soap(
    note: str = Form(...),
    image: UploadFile | None = File(None),
) -> JSONResponse:
    img_path = await _save_upload(image) if image else None
    try:
        res = await asyncio.to_thread(router.handle_soap, note, img_path)
        return _to_response(res)
    finally:
        if img_path:
            Path(img_path).unlink(missing_ok=True)


@app.post("/api/ddx")
async def api_ddx(
    symptoms: str = Form(...),
    n: int = Form(5),
    image: UploadFile | None = File(None),
) -> JSONResponse:
    img_path = await _save_upload(image) if image else None
    try:
        res = await asyncio.to_thread(router.handle_ddx, symptoms, n, img_path)
        return _to_response(res)
    finally:
        if img_path:
            Path(img_path).unlink(missing_ok=True)


@app.post("/api/edu")
async def api_edu(
    diagnosis: str = Form(...),
    grade: str = Form("중학교"),
    points: str = Form(""),
) -> JSONResponse:
    pts = [p.strip() for p in points.split(",") if p.strip()] if points else None
    res = await asyncio.to_thread(router.handle_edu, diagnosis, grade, pts)
    return _to_response(res)


@app.post("/api/drug")
async def api_drug(
    current_meds: str = Form(...),
    new_med: str = Form(...),
) -> JSONResponse:
    meds = [m.strip() for m in current_meds.split(",") if m.strip()]
    res = await asyncio.to_thread(router.handle_drug, meds, new_med)
    return _to_response(res)


@app.post("/api/sns_draft")
async def api_sns_draft(
    topic: str = Form(...),
    style: str = Form("교육적이고 친근한"),
    image: UploadFile | None = File(None),
) -> JSONResponse:
    img_path = await _save_upload(image) if image else None
    try:
        res = await asyncio.to_thread(router.handle_sns_draft, topic, img_path, style)
        if res.ok:
            # 프론트엔드 호환: draft 필드를 평탄화하지 않고 그대로 반환
            return JSONResponse(res.data.get("draft", {}))
        return _to_response(res)
    finally:
        if img_path:
            Path(img_path).unlink(missing_ok=True)


@app.post("/api/publish")
async def api_publish(
    instagram_text: str = Form(""),
    threads_text: str = Form(""),
    media_urls: str = Form(""),
    hashtags: str = Form(""),
    dry_run: bool = Form(True),
) -> JSONResponse:
    urls = [u.strip() for u in media_urls.split(",") if u.strip()]
    tags = [t.strip() for t in hashtags.split(",") if t.strip()]
    # 이미 생성된 캡션/해시태그를 직접 발행: draft 없이 텍스트+미디어로 발행.
    res = await asyncio.to_thread(
        router.handle_sns_publish,
        None,  # draft=None (topic 기반 생성 아님)
        instagram_text=instagram_text,
        threads_text=threads_text,
        media_urls=urls,
        hashtags=tags,
        dry_run=dry_run,
    )
    if res.ok:
        return JSONResponse(res.data)
    return _to_response(res, error_code=502)


# ── 대시보드 HTML ─────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🏥 Doctor Assist Dashboard</title>
<style>
  :root {
    --bg: #f7f6f2; --surface: #ffffff; --primary: #01696f;
    --text: #28251d; --muted: #7a7974; --border: #d4d1ca;
    --radius: 0.75rem; --shadow: 0 4px 12px rgba(0,0,0,.08);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Pretendard', system-ui, sans-serif; background: var(--bg); color: var(--text); }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 1rem 2rem;
           display: flex; align-items: center; gap: 1rem; box-shadow: var(--shadow); }
  header h1 { font-size: 1.25rem; font-weight: 700; color: var(--primary); }
  nav { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-left: auto; }
  nav button { padding: .4rem 1rem; border: 1px solid var(--border); background: var(--bg);
               border-radius: var(--radius); cursor: pointer; font-size: .875rem;
               transition: all .15s; }
  nav button.active, nav button:hover { background: var(--primary); color: #fff; border-color: var(--primary); }
  main { max-width: 960px; margin: 2rem auto; padding: 0 1rem; }
  .panel { display: none; }
  .panel.active { display: block; }
  .card { background: var(--surface); border-radius: var(--radius);
          border: 1px solid var(--border); padding: 1.5rem; margin-bottom: 1.5rem;
          box-shadow: var(--shadow); }
  h2 { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: var(--primary); }
  label { font-size: .875rem; color: var(--muted); display: block; margin-bottom: .25rem; }
  input, textarea, select { width: 100%; border: 1px solid var(--border); border-radius: .5rem;
                             padding: .5rem .75rem; font-size: .9rem; background: var(--bg);
                             margin-bottom: .75rem; }
  textarea { min-height: 80px; resize: vertical; }
  .row { display: flex; gap: .75rem; align-items: flex-end; }
  .row > * { flex: 1; }
  button.primary { background: var(--primary); color: #fff; border: none; border-radius: .5rem;
                   padding: .6rem 1.5rem; cursor: pointer; font-size: .9rem; font-weight: 600;
                   transition: opacity .15s; }
  button.primary:hover { opacity: .85; }
  .output { background: #f0f4f3; border-radius: .5rem; padding: 1rem; min-height: 60px;
            font-size: .875rem; white-space: pre-wrap; margin-top: .75rem; color: var(--text); }
  .tag { display: inline-block; background: var(--primary); color: #fff;
         border-radius: 999px; padding: .15rem .6rem; font-size: .75rem; margin: .1rem; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: .4rem; }
  .ok { background: #43a047; } .err { background: #e53935; }
  #health-bar { display: flex; gap: 1.5rem; font-size: .85rem; padding: .5rem 0; }
</style>
</head>
<body>
<header>
  <span>🏥</span>
  <h1>Doctor Assist Dashboard</h1>
  <div id="health-bar">로딩 중...</div>
  <nav>
    <button class="active" onclick="showPanel('clinic')">🩺 외래</button>
    <button onclick="showPanel('sns')">📱 SNS</button>
    <button onclick="showPanel('publish')">🚀 발행</button>
  </nav>
</header>

<main>
  <!-- 외래 패널 -->
  <div id="clinic" class="panel active">

    <div class="card">
      <h2>🔍 감별 진단 (DDx)</h2>
      <label>증상 / 검사 소견</label>
      <textarea id="ddx-symptoms" placeholder="예: 58세 여성, 우상복부 둔통 3개월, AST/ALT 경미한 상승"></textarea>
      <label>초음파 이미지 첨부 (선택)</label>
      <input type="file" id="ddx-image" accept="image/*">
      <button class="primary" onclick="runDDx()">감별 진단 분석</button>
      <div class="output" id="ddx-out">결과가 여기에 표시됩니다.</div>
    </div>

    <div class="card">
      <h2>📋 진료 메모 → SOAP 변환</h2>
      <textarea id="soap-note" placeholder="예: 55세 남성, 두통 3일, 혈압 160/100, 두통약 복용 중…"></textarea>
      <button class="primary" onclick="runSOAP()">SOAP 변환</button>
      <div class="output" id="soap-out">결과가 여기에 표시됩니다.</div>
    </div>

    <div class="card">
      <h2>📄 환자 설명문 생성</h2>
      <div class="row">
        <div>
          <label>진단명</label>
          <input id="edu-dx" placeholder="예: 제2형 당뇨">
        </div>
        <div>
          <label>이해 수준</label>
          <select id="edu-grade">
            <option>중학교</option><option>초등학교</option><option>고등학교</option>
          </select>
        </div>
      </div>
      <label>핵심 항목 (쉼표 구분)</label>
      <input id="edu-points" placeholder="식이, 운동, 복약 순응도">
      <button class="primary" onclick="runEdu()">설명문 생성</button>
      <div class="output" id="edu-out">결과가 여기에 표시됩니다.</div>
    </div>

    <div class="card">
      <h2>💊 약물 상호작용 체크</h2>
      <label>현재 복용약 (쉼표 구분)</label>
      <input id="drug-current" placeholder="예: 메트포르민, 아스피린, 암로디핀">
      <label>추가 예정 약물</label>
      <input id="drug-new" placeholder="예: 클로피도그렐">
      <button class="primary" onclick="runDrug()">상호작용 분석</button>
      <div class="output" id="drug-out">결과가 여기에 표시됩니다.</div>
    </div>

    <div class="card">
      <h2>💬 Gemini 자유 질의</h2>
      <textarea id="ask-q" placeholder="예: 만성 변비 PEG 1차 실패 후 2단계 프로토콜"></textarea>
      <label>이미지 첨부 (선택)</label>
      <input type="file" id="ask-image" accept="image/*">
      <button class="primary" onclick="runAsk()">질의</button>
      <div class="output" id="ask-out">결과가 여기에 표시됩니다.</div>
    </div>
  </div>

  <!-- SNS 패널 -->
  <div id="sns" class="panel">
    <div class="card">
      <h2>✍️ SNS 콘텐츠 초안 생성</h2>
      <label>주제</label>
      <textarea id="sns-topic" placeholder="예: 가정의학과 의사의 AI 초음파 활용기" style="min-height:60px"></textarea>
      <label>스타일</label>
      <input id="sns-style" value="교육적이고 친근한">
      <label>이미지 첨부 (선택)</label>
      <input type="file" id="sns-image" accept="image/*">
      <button class="primary" onclick="runSNSDraft()">초안 생성</button>
      <div id="sns-out">
        <div class="output" id="sns-ig">인스타그램 캡션이 여기에 표시됩니다.</div>
        <div class="output" id="sns-th" style="margin-top:.5rem">스레드 캡션이 여기에 표시됩니다.</div>
        <div id="sns-tags" style="margin-top:.5rem"></div>
      </div>
    </div>
  </div>

  <!-- 발행 패널 -->
  <div id="publish" class="panel">
    <div class="card">
      <h2>🚀 인스타그램 / 스레드 발행</h2>
      <label>인스타그램 캡션</label>
      <textarea id="pub-ig"></textarea>
      <label>스레드 캡션</label>
      <textarea id="pub-th"></textarea>
      <label>이미지 URL (쉼표 구분, 최대 10개)</label>
      <input id="pub-urls" placeholder="https://example.com/img1.jpg, https://...">
      <label>해시태그 (쉼표 구분)</label>
      <input id="pub-tags" placeholder="가정의학과, AI의사, 건강정보">
      <div class="row" style="margin-top:.5rem">
        <label style="margin:0"><input type="checkbox" id="pub-dry" checked> Dry Run (실제 발행 안 함)</label>
        <button class="primary" onclick="runPublish()">발행</button>
      </div>
      <div class="output" id="pub-out">발행 결과가 여기에 표시됩니다.</div>
    </div>
  </div>
</main>

<script>
function showPanel(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  document.querySelectorAll('nav button').forEach((b,i) => {
    const panels = ['clinic','sns','publish'];
    b.classList.toggle('active', panels[i] === id);
  });
}

async function postForm(url, formData) {
  const r = await fetch(url, {method:'POST', body: formData});
  return r.json();
}

async function runDDx() {
  const out = document.getElementById('ddx-out');
  out.textContent = '분석 중…';
  const fd = new FormData();
  fd.append('symptoms', document.getElementById('ddx-symptoms').value);
  fd.append('n', 5);
  const img = document.getElementById('ddx-image').files[0];
  if (img) fd.append('image', img);
  const d = await postForm('/api/ddx', fd);
  if (d.differential) {
    out.textContent = d.differential.map((x,i) =>
      `${i+1}. ${x.diagnosis}\n   핵심: ${x.key_feature}\n   다음: ${x.next_step}`
    ).join('\n\n');
  } else { out.textContent = d.error || JSON.stringify(d); }
}

async function runSOAP() {
  const out = document.getElementById('soap-out');
  out.textContent = '변환 중…';
  const fd = new FormData();
  fd.append('note', document.getElementById('soap-note').value);
  const d = await postForm('/api/soap', fd);
  if (d.S !== undefined) {
    out.textContent = `S: ${d.S}\nO: ${d.O}\nA: ${d.A}\nP: ${d.P}`;
  } else { out.textContent = d.error || JSON.stringify(d); }
}

async function runEdu() {
  const out = document.getElementById('edu-out');
  out.textContent = '생성 중…';
  const fd = new FormData();
  fd.append('diagnosis', document.getElementById('edu-dx').value);
  fd.append('grade', document.getElementById('edu-grade').value);
  fd.append('points', document.getElementById('edu-points').value);
  const d = await postForm('/api/edu', fd);
  out.textContent = d.education || d.error || JSON.stringify(d);
}

async function runDrug() {
  const out = document.getElementById('drug-out');
  out.textContent = '분석 중…';
  const fd = new FormData();
  fd.append('current_meds', document.getElementById('drug-current').value);
  fd.append('new_med', document.getElementById('drug-new').value);
  const d = await postForm('/api/drug', fd);
  out.textContent = `상호작용: ${d.has_interaction ? '있음 ⚠️' : '없음 ✅'}\n심각도: ${d.severity}\n\n${d.details}\n\n권고: ${d.recommendation}`;
}

async function runAsk() {
  const out = document.getElementById('ask-out');
  out.textContent = '응답 중…';
  const fd = new FormData();
  fd.append('question', document.getElementById('ask-q').value);
  const img = document.getElementById('ask-image').files[0];
  if (img) fd.append('image', img);
  const d = await postForm('/api/ask', fd);
  out.textContent = d.answer || d.error || JSON.stringify(d);
}

async function runSNSDraft() {
  document.getElementById('sns-ig').textContent = '생성 중…';
  const fd = new FormData();
  fd.append('topic', document.getElementById('sns-topic').value);
  fd.append('style', document.getElementById('sns-style').value);
  const img = document.getElementById('sns-image').files[0];
  if (img) fd.append('image', img);
  const d = await postForm('/api/sns_draft', fd);
  document.getElementById('sns-ig').textContent = d.instagram_caption || d.error || '';
  document.getElementById('sns-th').textContent = d.threads_caption || '';
  const tagsDiv = document.getElementById('sns-tags');
  tagsDiv.innerHTML = (d.hashtags || []).map(t => `<span class="tag">${t}</span>`).join('');
  // 발행 패널로 자동 복사
  if (d.instagram_caption) document.getElementById('pub-ig').value = d.instagram_caption;
  if (d.threads_caption) document.getElementById('pub-th').value = d.threads_caption;
  if (d.hashtags) document.getElementById('pub-tags').value = d.hashtags.join(', ');
}

async function runPublish() {
  const out = document.getElementById('pub-out');
  out.textContent = '발행 중…';
  const fd = new FormData();
  fd.append('instagram_text', document.getElementById('pub-ig').value);
  fd.append('threads_text', document.getElementById('pub-th').value);
  fd.append('media_urls', document.getElementById('pub-urls').value);
  fd.append('hashtags', document.getElementById('pub-tags').value);
  fd.append('dry_run', document.getElementById('pub-dry').checked);
  const d = await postForm('/api/publish', fd);
  out.textContent = JSON.stringify(d, null, 2);
}

// 헬스체크
async function loadHealth() {
  const bar = document.getElementById('health-bar');
  try {
    const d = await fetch('/api/health').then(r => r.json());
    bar.innerHTML = [
      `<span><span class="status-dot ${d.gemini.ok ? 'ok' : 'err'}"></span>Gemini</span>`,
      `<span><span class="status-dot ${d.instagram.configured ? 'ok' : 'err'}"></span>Instagram</span>`,
      `<span><span class="status-dot ${d.threads.configured ? 'ok' : 'err'}"></span>Threads</span>`,
    ].join('');
  } catch { bar.innerHTML = '<span>상태 확인 실패</span>'; }
}
loadHealth();
</script>
</body>
</html>
"""
