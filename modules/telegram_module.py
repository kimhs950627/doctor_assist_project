"""Telegram Bot 통합 모듈.

Usage::

    from modules.telegram_module import TelegramBot, TelegramCommand

    bot = TelegramBot()  # TELEGRAM_BOT_TOKEN, BOT_OWNER_CHAT_ID 환경변수 필요

    # 커맨드 핸들러 등록 (데코레이터 방식)
    @bot.command("soap")
    async def soap_cmd(update, context):
        text = " ".join(context.args)
        # ... Gemini 호출 등
        await update.message.reply_text(result)

    # 봇 실행 (blocking)
    bot.run()

    # 단일 메시지 전송 (외부에서 호출)
    bot.send_message(chat_id=12345678, text="검사 결과 이상 감지")
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

try:
    from telegram import Bot, Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError as e:
    raise ImportError(
        "python-telegram-bot이 필요합니다: pip install python-telegram-bot"
    ) from e

logger = logging.getLogger(__name__)


class TelegramCommand:
    """Telegram 커맨드 정의 헬퍼."""

    def __init__(self, name: str, handler: Callable, description: str = "") -> None:
        self.name = name
        self.handler = handler
        self.description = description


class TelegramBot:
    """Telegram Bot 래퍼. 커맨드 등록 → 실행을 단순화합니다."""

    def __init__(
        self,
        token: str | None = None,
        owner_chat_id: int | None = None,
    ) -> None:
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN 환경변수 또는 token 파라미터가 필요합니다.")
        _owner = owner_chat_id or os.environ.get("BOT_OWNER_CHAT_ID", "")
        self.owner_chat_id: int | None = int(_owner) if _owner else None
        self._app: Application | None = None
        self._extra_handlers: list[tuple] = []

    def _get_app(self) -> Application:
        if self._app is None:
            self._app = Application.builder().token(self.token).build()
        return self._app

    # ── 커맨드 등록 ───────────────────────────────────────

    def command(self, name: str, description: str = ""):
        """데코레이터: async 함수를 /{name} 커맨드로 등록."""
        def decorator(func: Callable):
            self._get_app().add_handler(CommandHandler(name, func))
            logger.info("Registered command: /%s", name)
            return func
        return decorator

    def add_command(self, name: str, handler: Callable) -> None:
        """명시적 커맨드 등록."""
        self._get_app().add_handler(CommandHandler(name, handler))

    def add_message_handler(self, handler: Callable, filter=filters.TEXT) -> None:
        """텍스트/사진 등 메시지 핸들러 등록."""
        self._get_app().add_handler(MessageHandler(filter, handler))

    # ── 메시지 전송 (동기) ────────────────────────────────

    def send_message(self, chat_id: int | None, text: str, **kwargs) -> None:
        """비동기 없이 메시지 전송. 외부 스크립트/n8n 호출에서 사용."""
        target = chat_id or self.owner_chat_id
        if not target:
            raise ValueError("chat_id 또는 BOT_OWNER_CHAT_ID가 필요합니다.")
        bot = Bot(token=self.token)
        asyncio.run(bot.send_message(chat_id=target, text=text, **kwargs))

    def send_photo(self, chat_id: int | None, photo_path: str, caption: str = "") -> None:
        """사진 전송 (파일 경로)."""
        target = chat_id or self.owner_chat_id
        if not target:
            raise ValueError("chat_id 또는 BOT_OWNER_CHAT_ID가 필요합니다.")
        bot = Bot(token=self.token)
        with open(photo_path, "rb") as f:
            asyncio.run(bot.send_photo(chat_id=target, photo=f, caption=caption))

    def send_to_owner(self, text: str, **kwargs) -> None:
        """오너 채팅방에 알림 전송."""
        self.send_message(self.owner_chat_id, text, **kwargs)

    # ── 봇 실행 ───────────────────────────────────────────

    def run(self) -> None:
        """Polling 방식으로 봇 실행 (blocking)."""
        logger.info("Telegram bot starting (polling)...")
        self._get_app().run_polling()

    def run_webhook(self, webhook_url: str, port: int = 8443) -> None:
        """Webhook 방식으로 봇 실행."""
        logger.info("Telegram bot starting (webhook) | url=%s port=%d", webhook_url, port)
        self._get_app().run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
        )

    # ── 기본 커맨드 세트 (선택적 로드) ───────────────────

    def register_default_commands(self) -> None:
        """기본 /start, /help, /ping 커맨드를 자동 등록."""

        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            await update.message.reply_text(
                "🏥 Doctor Assist Bot\n"
                "/soap — 진료 메모 → SOAP\n"
                "/ddx — 감별 진단\n"
                "/edu — 환자 설명문\n"
                "/drug — 약물 상호작용\n"
                "/post — SNS 초안 생성\n"
                "/ping — 상태 확인"
            )

        async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            await update.message.reply_text("✅ Bot alive")

        self.add_command("start", start)
        self.add_command("help", start)
        self.add_command("ping", ping)
