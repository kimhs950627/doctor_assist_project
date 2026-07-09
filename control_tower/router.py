"""공유 비즈니스 로직 라우터 — 두 컨트롤 타워(웹 대시보드, 텔레그램 봇)가 공통으로 사용.

이 모듈은 ``modules/`` 하위의 Gemini / Instagram / Telegram 모듈을 한 곳에서
오케스트레이션합니다. 두 컨트롤 타워는 각자의 입출력(UI/메시지 포맷)만 담당하고,
실제 AI·발행 로직은 모두 이 라우터에 위임합니다 → 비즈니스 로직 중복 0.

설계 원칙
---------
1. **Lazy init + graceful degradation**: 환경변수(키)가 없어도 import 는 성공.
   호출 시점에 ``RouterResult(ok=False, error=...)`` 로 명확히 보고.
2. **동기 메서드**: 하위 모듈(google-genai, requests)이 동기 블로킹이므로 라우터도 동기.
   비동기 컨텍스트(FastAPI 핸들러, PTB 핸들러)에서는 ``await asyncio.to_thread(...)``
   로 감싸서 호출해 이벤트 루프 블로킹을 피할 것.
3. **GeminiQuotaError 캡처**: 쿼터 초과(429)를 구조화된 결과로 변환.

Usage::

    from control_tower.router import DoctorRouter
    router = DoctorRouter()

    # 웹/텔레그램 어디서든
    res = router.handle_ddx(symptoms="우상복부 둔통 3개월", n=5)
    if res.ok:
        ddx = res.data["differential"]
    else:
        print(res.error)  # "GEMINI_API_KEY ..." / "Gemini 쿼터 초과" 등
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from modules.gemini_module import GeminiModule, GeminiQuotaError
from modules.instagram_module import (
    InstagramModule,
    PublishRequest,
    PublishResult,
    ThreadsModule,
)

logger = logging.getLogger(__name__)


# ── 결과 모델 ────────────────────────────────────────────────

@dataclass
class RouterResult:
    """모든 라우터 핸들러의 공통 반환 타입.

    ``data`` 는 항상 JSON 직렬화 가능한 dict 이어야 한다
    (FastAPI JSONResponse / Telegram 메시지에서 바로 소비 가능).
    """
    action: str
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── 에러 헬퍼 ────────────────────────────────────────────────

def _err(action: str, exc: Exception) -> RouterResult:
    """예외를 RouterResult 로 변환. GeminiQuotaError 는 전용 메시지."""
    if isinstance(exc, GeminiQuotaError):
        return RouterResult(action, ok=False, error="Gemini 쿼터 초과 (무료 한도 도달)")
    return RouterResult(action, ok=False, error=f"{type(exc).__name__}: {exc}")


# ── 라우터 ────────────────────────────────────────────────────

class DoctorRouter:
    """모든 AI·발행 액션을 중앙 라우팅하는 공유 레이어."""

    def __init__(self) -> None:
        # Instagram / Threads 는 생성자에서 키 검사를 하지 않으므로 안전.
        self.ig = InstagramModule()
        self.th = ThreadsModule()

        # Gemini / Telegram 은 키가 없으면 생성자가 raise → lazy 초기화.
        self._gm: GeminiModule | None = None
        self._gm_error: str | None = None
        self._tg = None  # TelegramBot 인스턴스 (필요시 lazy)

    # ── lazy 프로퍼티 ──────────────────────────────────────

    @property
    def gemini(self) -> GeminiModule | None:
        """GeminiModule 을 lazy 초기화. 키 미설정 시 None."""
        if self._gm is None and self._gm_error is None:
            try:
                self._gm = GeminiModule()
            except Exception as exc:  # ValueError 등
                self._gm_error = str(exc)
                logger.warning("Gemini init failed: %s", exc)
        return self._gm

    def _gm_required(self, action: str) -> tuple[GeminiModule, None] | tuple[None, RouterResult]:
        """Gemini 사용 전 검증. (gm, None) 또는 (None, error_result)."""
        gm = self.gemini
        if gm is None:
            return None, RouterResult(
                action, ok=False,
                error=self._gm_error or "GEMINI_API_KEY 가 설정되지 않았습니다.",
            )
        return gm, None

    @property
    def telegram(self):
        """TelegramBot lazy 초기화. 키 미설정 시 None."""
        if self._tg is None:
            try:
                from modules.telegram_module import TelegramBot
                self._tg = TelegramBot()
            except Exception as exc:
                logger.warning("Telegram init failed: %s", exc)
                self._tg = None  # type: ignore[assignment]
        return self._tg

    # ── 상태 ───────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """모든 모듈의 설정/연결 상태 반환 (헬스체크)."""
        gm = self.gemini
        if gm is None:
            gemini_status: dict[str, Any] = {"ok": False, "detail": self._gm_error or "미설정"}
        else:
            ok, detail = gm.ping()
            gemini_status = {"ok": ok, "detail": detail}
        return {
            "gemini": gemini_status,
            "instagram": {"configured": self.ig.is_configured},
            "threads": {"configured": self.th.is_configured},
            "telegram": {"configured": self.telegram is not None},
        }

    # ── 외래 보조 액션 ────────────────────────────────────

    def handle_ask(
        self,
        question: str,
        image_path: str | None = None,
    ) -> RouterResult:
        gm, err = self._gm_required("ask")
        if err:
            return err
        try:
            answer = gm.ask(question, image_path=image_path)  # type: ignore[union-attr]
            return RouterResult("ask", ok=True, data={"answer": answer})
        except Exception as exc:
            return _err("ask", exc)

    def handle_ddx(
        self,
        symptoms: str,
        n: int = 5,
        image_path: str | None = None,
    ) -> RouterResult:
        gm, err = self._gm_required("ddx")
        if err:
            return err
        try:
            ddx = gm.differential_diagnosis(symptoms, n=n, image_path=image_path)  # type: ignore[union-attr]
            return RouterResult("ddx", ok=True, data={"differential": ddx})
        except Exception as exc:
            return _err("ddx", exc)

    def handle_soap(
        self,
        raw_note: str,
        image_path: str | None = None,
    ) -> RouterResult:
        gm, err = self._gm_required("soap")
        if err:
            return err
        try:
            soap = gm.to_soap(raw_note, image_path=image_path)  # type: ignore[union-attr]
            return RouterResult("soap", ok=True, data=soap)
        except Exception as exc:
            return _err("soap", exc)

    def handle_edu(
        self,
        diagnosis: str,
        grade: str = "중학교",
        points: list[str] | None = None,
        language: str = "한국어",
    ) -> RouterResult:
        gm, err = self._gm_required("edu")
        if err:
            return err
        try:
            edu = gm.patient_education(  # type: ignore[union-attr]
                diagnosis, grade=grade, points=points, language=language
            )
            return RouterResult("edu", ok=True, data={"education": edu})
        except Exception as exc:
            return _err("edu", exc)

    def handle_drug(
        self,
        current_meds: list[str],
        new_med: str,
    ) -> RouterResult:
        gm, err = self._gm_required("drug")
        if err:
            return err
        try:
            result = gm.check_drug_interaction(current_meds, new_med)  # type: ignore[union-attr]
            return RouterResult("drug", ok=True, data=result)
        except Exception as exc:
            return _err("drug", exc)

    # ── SNS 콘텐츠 액션 ──────────────────────────────────

    def handle_sns_draft(
        self,
        topic: str,
        image_path: str | None = None,
        style: str = "교육적이고 친근한",
    ) -> RouterResult:
        gm, err = self._gm_required("sns_draft")
        if err:
            return err
        try:
            draft = gm.generate_sns_draft(  # type: ignore[union-attr]
                topic, image_path=image_path, style=style
            )
            return RouterResult("sns_draft", ok=True, data={"draft": draft})
        except Exception as exc:
            return _err("sns_draft", exc)

    def handle_sns_publish(
        self,
        draft: dict[str, Any] | None = None,
        *,
        topic: str | None = None,
        media_urls: list[str] | None = None,
        hashtags: list[str] | None = None,
        instagram_text: str | None = None,
        threads_text: str | None = None,
        dry_run: bool = True,
        publish_ig: bool = True,
        publish_th: bool = True,
    ) -> RouterResult:
        """SNS 발행. ``draft`` 가 없으면 ``topic`` 으로 초안 생성 후 발행.

        - Instagram 은 미디어 URL 이 최소 1개 필요 (없으면 스킵 + 사유 기록).
        - Threads 는 텍스트 단독 발행 가능.
        - ``dry_run=True`` 면 실제 API 호출 없이 시뮬레이션 결과 반환.
        """
        # 1) 발행용 텍스트/해시태그 확보
        if draft is None:
            if topic is None:
                return RouterResult(
                    "sns_publish", ok=False,
                    error="draft 또는 topic 중 하나는 필요합니다.",
                )
            res = self.handle_sns_draft(topic)
            if not res.ok:
                return res
            draft = res.data.get("draft", {})

        ig_text = (instagram_text if instagram_text is not None
                   else draft.get("instagram_caption", ""))
        th_text = (threads_text if threads_text is not None
                   else draft.get("threads_caption", ""))
        tags = hashtags if hashtags is not None else draft.get("hashtags", [])
        urls = media_urls or []

        results: dict[str, Any] = {
            "draft": draft,
            "dry_run": dry_run,
            "instagram": "skipped",
            "threads": "skipped",
        }

        # 2) Instagram 발행 (미디어 URL 필수)
        if publish_ig:
            ig_req = PublishRequest(text=ig_text, media_urls=urls, hashtags=tags, dry_run=dry_run)
            ig_res = self.ig.publish(ig_req)
            results["instagram"] = {
                "ok": ig_res.ok,
                "dry_run": ig_res.dry_run,
                "permalink": ig_res.permalink,
                "media_id": ig_res.published_media_id,
                "error": ig_res.error_message,
            }

        # 3) Threads 발행 (텍스트 단독 가능)
        if publish_th:
            th_req = PublishRequest(text=th_text, media_urls=urls, hashtags=tags, dry_run=dry_run)
            th_res = self.th.publish(th_req)
            results["threads"] = {
                "ok": th_res.ok,
                "dry_run": th_res.dry_run,
                "media_id": th_res.published_media_id,
                "error": th_res.error_message,
            }

        return RouterResult("sns_publish", ok=True, data=results)

    # ── 알림 ─────────────────────────────────────────────

    def notify_owner(self, text: str) -> bool:
        """텔레그램 오너에게 알림. 키 미설정/실패 시 False (best-effort)."""
        tg = self.telegram
        if tg is None:
            logger.info("Telegram 미설정 — 알림 스킵: %s", text[:80])
            return False
        try:
            tg.send_to_owner(text)
            return True
        except Exception as exc:
            logger.warning("Telegram notify failed: %s", exc)
            return False
