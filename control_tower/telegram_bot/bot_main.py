"""텔레그램 봇 컨트롤 타워.

실행::

    pip install python-telegram-bot google-genai requests
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
    /ddx <증상>  — 감별 진단 5가지
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
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from modules.gemini_module import GeminiModule, GeminiQuotaError
from modules.instagram_module import InstagramModule, PublishRequest, ThreadsModule
from modules.telegram_module import TelegramBot

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() in {"1", "true", "yes"}

# ── 모듈 초기화 ───────────────────────────────────────────
bot = TelegramBot()
bot.register_default_commands()

try:
    gemini = GeminiModule()
    logger.info("Gemini module initialized")
except Exception as exc:
    gemini = None  # type: ignore
    logger.warning("Gemini init failed: %s", exc)

instagram = InstagramModule()
threads = ThreadsModule()

# 대기 중 승인 future 저장
_pending: dict[int, asyncio.Future] = {}


# ── 헬퍼 ─────────────────────────────────────────────────

def _gemini_required(func):
    """Gemini 없으면 에러 메시지 반환 데코레이터."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if gemini is None:
            await update.message.reply_text("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
            return
        await func(update, context)
    return wrapper


# ── 커맨드 핸들러 ─────────────────────────────────────────

@bot.command("soap", description="진료 메모 → SOAP 변환")
@_gemini_required
async def soap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    note = " ".join(context.args).strip()
    if not note:
        await update.message.reply_text("사용법: /soap <진료 메모>\n예: /soap 55세 남성 두통 3일 혈압 160/100")
        return
    await update.message.reply_text("⏳ SOAP 변환 중...")
    try:
        result = gemini.to_soap(note)
        text = f"📋 SOAP 변환 결과\n\nS: {result.get('S','')}\nO: {result.get('O','')}\nA: {result.get('A','')}\nP: {result.get('P','')}"
        await update.message.reply_text(text)
    except GeminiQuotaError:
        await update.message.reply_text("❌ Gemini 쿼터 초과 (무료 한도 도달)")


@bot.command("ddx", description="감별 진단")
@_gemini_required
async def ddx_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symptoms = " ".join(context.args).strip()
    if not symptoms:
        await update.message.reply_text("사용법: /ddx <증상/소견>\n예: /ddx 우상복부 둔통 3개월 AST 상승")
        return
    await update.message.reply_text("⏳ 감별 진단 분석 중...")
    try:
        result = gemini.differential_diagnosis(symptoms, n=5)
        lines = ["🔍 감별 진단 (상위 5개)\n"]
        for i, item in enumerate(result, 1):
            lines.append(
                f"{i}. {item.get('diagnosis','')}\n"
                f"   핵심: {item.get('key_feature','')}\n"
                f"   다음 단계: {item.get('next_step','')}"
            )
        await update.message.reply_text("\n\n".join(lines))
    except GeminiQuotaError:
        await update.message.reply_text("❌ Gemini 쿼터 초과")


@bot.command("edu", description="환자 설명문")
@_gemini_required
async def edu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /edu <진단명>\n예: /edu 제2형 당뇨")
        return
    diagnosis = " ".join(context.args)
    await update.message.reply_text("⏳ 설명문 생성 중...")
    try:
        result = gemini.patient_education(diagnosis)
        await update.message.reply_text(f"📄 {diagnosis} 환자 설명문\n\n{result}")
    except GeminiQuotaError:
        await update.message.reply_text("❌ Gemini 쿼터 초과")


@bot.command("drug", description="약물 상호작용 체크")
@_gemini_required
async def drug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args)
    if "|" not in raw:
        await update.message.reply_text("사용법: /drug <현재 복용약, 쉼표 구분> | <추가 예정약>\n예: /drug 메트포르민, 아스피린 | 클로피도그렐")
        return
    current_str, new_med = raw.split("|", 1)
    current_meds = [m.strip() for m in current_str.split(",") if m.strip()]
    await update.message.reply_text("⏳ 약물 상호작용 분석 중...")
    try:
        result = gemini.check_drug_interaction(current_meds, new_med.strip())
        emoji = "⚠️" if result.get("has_interaction") else "✅"
        text = (
            f"💊 약물 상호작용 분석 {emoji}\n\n"
            f"상호작용: {'있음' if result.get('has_interaction') else '없음'}\n"
            f"심각도: {result.get('severity', '-')}\n\n"
            f"{result.get('details', '')}\n\n"
            f"권고사항: {result.get('recommendation', '')}"
        )
        await update.message.reply_text(text)
    except GeminiQuotaError:
        await update.message.reply_text("❌ Gemini 쿼터 초과")


@bot.command("post", description="SNS 초안 생성 + 발행")
@_gemini_required
async def post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("사용법: /post <SNS 주제>\n예: /post 오늘 외래에서 LDL 상담이 많았다")
        return
    await update.message.reply_text("⏳ SNS 초안 생성 중...")
    try:
        draft = gemini.generate_sns_draft(topic)
    except GeminiQuotaError:
        await update.message.reply_text("❌ Gemini 쿼터 초과")
        return

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
    hashtags = draft.get("hashtags", [])
    ig_req = PublishRequest(text=draft.get("instagram_caption", ""), hashtags=hashtags, dry_run=DRY_RUN)
    th_req = PublishRequest(text=draft.get("threads_caption", ""), hashtags=hashtags, dry_run=DRY_RUN)
    ig_result = instagram.publish(ig_req)
    th_result = threads.publish(th_req)

    mode = "🧪 DRY RUN" if DRY_RUN else "🚀 LIVE"
    await update.message.reply_text(
        f"발행 완료 ({mode})\n"
        f"Instagram: {'✅' if ig_result.ok else '❌'} {ig_result.permalink or ig_result.error_message or ''}\n"
        f"Threads: {'✅' if th_result.ok else '❌'} {th_result.published_media_id or th_result.error_message or ''}"
    )


@bot.command("status", description="모듈 상태")
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    gemini_ok, detail = gemini.ping() if gemini else (False, "미설정")
    mode = "🧪 DRY RUN" if DRY_RUN else "🚀 LIVE"
    text = (
        f"📊 Doctor Assist Bot 상태\n"
        f"{'─' * 20}\n"
        f"모드: {mode}\n"
        f"Gemini: {'✅' if gemini_ok else '❌'} {detail}\n"
        f"Instagram: {'✅' if instagram.is_configured else '❌ 미설정'}\n"
        f"Threads: {'✅' if threads.is_configured else '❌ 미설정'}\n"
        f"대기 중 승인: {len(_pending)}건"
    )
    await update.message.reply_text(text)


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
