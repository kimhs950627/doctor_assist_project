"""텔레그램 봇 컨트롤 타워.

웹 대시보드(control_tower.web_dashboard.app)와 동일한 ``DoctorRouter`` 를 공유하므로
비즈니스 로직 중복이 없다. 이 파일은 텔레그램特有的 입출력(커맨드 파싱, 승인 흐름,
메시지 포맷팅)만 담당한다.

실행::

    pip install python-telegram-bot google-genai requests python-dotenv
    python control_tower/telegram_bot/bot_main.py

환경변수 (.env)::

    TELEGRAM_BOT_TOKEN=...
    BOT_OWNER_CHAT_ID=...
    GEMINI_API_KEY=...
    INSTAGRAM_ACCESS_TOKEN=...
    INSTAGRAM_USER_ID=...
    THREADS_ACCESS_TOKEN=...
    THREADS_USER_ID=...
    DRY_RUN=true   # 실제 발행하려면 false

커맨드 목록::

    /start       — 시작 안내
    /soap <메모> — 진료 메모 → SOAP
    /ddx <증상>  — 감별 진단 5가지 (이미지 첨부 가능)
    /edu <진단명>— 환자 설명문
    /drug <현재약> | <추가약> — 약물 상호작용
    /post <주제> — SNS 초안 생성 후 승인 → 발행
    /status      — 모듈 상태
    /ping        — 생존 확인
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from control_tower.router import DoctorRouter, RouterResult
from modules.telegram_module import TelegramBot

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() in {"1", "true", "yes"}

# ── 컨트롤 타워 초기화 ───────────────────────────────────
bot = TelegramBot()
bot.register_default_commands()

# 공유 라우터: Gemini/Instagram/Threads 오케스트레이션 (lazy init, 키 없어도 safe)
router = DoctorRouter()

# 대기 중 승인 future 저장 (chat_id → Future)
_pending: dict[int, asyncio.Future] = {}


# ── 헬퍼 ─────────────────────────────────────────────────

async def _run(func, *args) -> RouterResult:
    """동기 라우터 메서드를 스레드풀에서 실행 (이벤트 루프 블로킹 방지)."""
    return await asyncio.to_thread(func, *args)


async def _reply_error(update: Update, res: RouterResult) -> None:
    """RouterResult 실패를 사용자 메시지로 변환."""
    if res.error and "쿼터" in res.error:
        await update.message.reply_text("❌ Gemini 쿼터 초과 (무료 한도 도달)")
    elif res.error and "GEMINI_API_KEY" in (res.error or ""):
        await update.message.reply_text("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
    else:
        await update.message.reply_text(f"❌ 오류: {res.error or '알 수 없음'}")


# ── 커맨드 핸들러 ─────────────────────────────────────────

@bot.command("soap", description="진료 메모 → SOAP 변환")
async def soap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note = " ".join(context.args).strip()
    if not note:
        await update.message.reply_text("사용법: /soap <진료 메모>\n예: /soap 55세 남성 두통 3일 혈압 160/100")
        return
    await update.message.reply_text("⏳ SOAP 변환 중...")
    res = await _run(router.handle_soap, note)
    if not res.ok:
        await _reply_error(update, res)
        return
    s = res.data
    await update.message.reply_text(
        f"📋 SOAP 변환 결과\n\nS: {s.get('S','')}\nO: {s.get('O','')}\nA: {s.get('A','')}\nP: {s.get('P','')}"
    )


@bot.command("ddx", description="감별 진단")
async def ddx_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symptoms = " ".join(context.args).strip()
    if not symptoms:
        await update.message.reply_text("사용법: /ddx <증상/소견>\n예: /ddx 우상복부 둔통 3개월 AST 상승")
        return
    await update.message.reply_text("⏳ 감별 진단 분석 중...")

    # 이미지 첨부 처리 (사진과 함께 /ddx 전송 시)
    image_path = None
    if update.message.photo:
        photo = update.message.photo[-1]
        f = await context.bot.get_file(photo.file_id)
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        await f.download_to_drive(tmp.name)
        image_path = tmp.name

    try:
        res = await _run(router.handle_ddx, symptoms, 5, image_path)
    finally:
        if image_path:
            Path(image_path).unlink(missing_ok=True)

    if not res.ok:
        await _reply_error(update, res)
        return
    items = res.data.get("differential", [])
    lines = ["🔍 감별 진단 (상위 5개)\n"]
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. {item.get('diagnosis','')}\n"
            f"   핵심: {item.get('key_feature','')}\n"
            f"   다음 단계: {item.get('next_step','')}"
        )
    await update.message.reply_text("\n\n".join(lines))


@bot.command("edu", description="환자 설명문")
async def edu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /edu <진단명>\n예: /edu 제2형 당뇨")
        return
    diagnosis = " ".join(context.args)
    await update.message.reply_text("⏳ 설명문 생성 중...")
    res = await _run(router.handle_edu, diagnosis)
    if not res.ok:
        await _reply_error(update, res)
        return
    await update.message.reply_text(f"📄 {diagnosis} 환자 설명문\n\n{res.data.get('education', '')}")


@bot.command("drug", description="약물 상호작용 체크")
async def drug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args)
    if "|" not in raw:
        await update.message.reply_text(
            "사용법: /drug <현재 복용약, 쉼표 구분> | <추가 예정약>\n"
            "예: /drug 메트포르민, 아스피린 | 클로피도그렐"
        )
        return
    current_str, new_med = raw.split("|", 1)
    current_meds = [m.strip() for m in current_str.split(",") if m.strip()]
    await update.message.reply_text("⏳ 약물 상호작용 분석 중...")
    res = await _run(router.handle_drug, current_meds, new_med.strip())
    if not res.ok:
        await _reply_error(update, res)
        return
    d = res.data
    emoji = "⚠️" if d.get("has_interaction") else "✅"
    await update.message.reply_text(
        f"💊 약물 상호작용 분석 {emoji}\n\n"
        f"상호작용: {'있음' if d.get('has_interaction') else '없음'}\n"
        f"심각도: {d.get('severity', '-')}\n\n"
        f"{d.get('details', '')}\n\n"
        f"권고사항: {d.get('recommendation', '')}"
    )


@bot.command("post", description="SNS 초안 생성 + 발행")
async def post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("사용법: /post <SNS 주제>\n예: /post 오늘 외래에서 LDL 상담이 많았다")
        return
    await update.message.reply_text("⏳ SNS 초안 생성 중...")
    res = await _run(router.handle_sns_draft, topic)
    if not res.ok:
        await _reply_error(update, res)
        return
    draft = res.data.get("draft", {})

    preview = (
        f"📸 [인스타그램]\n{draft.get('instagram_caption','')}\n\n"
        f"🧵 [스레드]\n{draft.get('threads_caption','')}\n\n"
        f"#태그: {' '.join(draft.get('hashtags',[])[:10])}\n\n"
        f"💡 {draft.get('rationale','')}"
    )
    await update.message.reply_text(preview)
    await update.message.reply_text(
        "초안을 확인하세요.\n"
        "• 승인: yes\n"
        "• 취소: no\n"
        "• 재생성 지시: /echo <수정 지시사항>\n"
        "(300초 무응답 시 자동 취소)"
    )

    chat_id = update.effective_chat.id
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    _pending[chat_id] = future
    context.chat_data["sns_draft"] = draft

    try:
        decision = await asyncio.wait_for(future, timeout=300.0)
    except asyncio.TimeoutError:
        await update.message.reply_text("⏰ 300초 초과 — 취소됩니다.")
        _pending.pop(chat_id, None)
        return
    finally:
        _pending.pop(chat_id, None)

    if decision is False:
        await update.message.reply_text("❌ 취소됨.")
        return

    await update.message.reply_text("🚀 발행 중...")
    # decision 이 str 이면 재생성 지시 → 초안 재생성 후 발행
    final_draft = draft
    if isinstance(decision, str):
        regen = await _run(router.handle_sns_draft, f"{topic} (수정 지시: {decision})")
        if regen.ok:
            final_draft = regen.data.get("draft", draft)
        else:
            await _reply_error(update, regen)
            return

    pub = await _run(
        router.handle_sns_publish,
        final_draft,
        dry_run=DRY_RUN,
    )
    if not pub.ok:
        await _reply_error(update, pub)
        return
    ig = pub.data.get("instagram")
    th = pub.data.get("threads")
    mode = "🧪 DRY RUN" if DRY_RUN else "🚀 LIVE"

    def _fmt(label: str, r) -> str:
        if r == "skipped" or r is None:
            return f"{label}: ⏭ 스킵"
        ok = r.get("ok") if isinstance(r, dict) else False
        detail = ""
        if isinstance(r, dict):
            detail = r.get("permalink") or r.get("media_id") or r.get("error") or ""
        return f"{label}: {'✅' if ok else '❌'} {detail}"

    await update.message.reply_text(
        f"발행 완료 ({mode})\n{_fmt('Instagram', ig)}\n{_fmt('Threads', th)}"
    )


@bot.command("status", description="모듈 상태")
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    h = await _run(router.health)
    mode = "🧪 DRY RUN" if DRY_RUN else "🚀 LIVE"
    g = h.get("gemini", {})
    await update.message.reply_text(
        f"📊 Doctor Assist Bot 상태\n"
        f"{'─' * 20}\n"
        f"모드: {mode}\n"
        f"Gemini: {'✅' if g.get('ok') else '❌'} {g.get('detail', '미설정')}\n"
        f"Instagram: {'✅' if h.get('instagram', {}).get('configured') else '❌ 미설정'}\n"
        f"Threads: {'✅' if h.get('threads', {}).get('configured') else '❌ 미설정'}\n"
        f"대기 중 승인: {len(_pending)}건"
    )


# ── 텍스트 메시지 핸들러 (yes/no 승인) ───────────────────

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    chat_id = update.effective_chat.id
    text = update.message.text.strip().lower()
    if chat_id in _pending:
        future = _pending[chat_id]
        if text in {"yes", "y", "예", "승인"}:
            if not future.done():
                future.set_result(True)
        elif text in {"no", "n", "아니오", "취소"}:
            if not future.done():
                future.set_result(False)
        else:
            await update.message.reply_text("yes / no 로 응답하거나 /echo <수정 지시>를 사용하세요.")


async def echo_cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    instruction = " ".join(context.args).strip()
    if chat_id in _pending and instruction:
        future = _pending[chat_id]
        if not future.done():
            future.set_result(instruction)
    else:
        await update.message.reply_text("대기 중인 초안이 없습니다.")


bot.add_command("echo", echo_cmd_handler)
bot.add_message_handler(text_handler, filter=filters.TEXT & ~filters.COMMAND)


if __name__ == "__main__":
    logger.info("Doctor Assist Telegram Bot starting...")
    bot.run()
