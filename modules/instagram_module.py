"""Instagram Graph API 통합 모듈.

sns-doctor-branding 리포의 InstagramClient / ThreadsClient를 doctor_assist_project에서
import 가능하도록 재패키징. 외부 의존성: requests.

Usage::

    from modules.instagram_module import InstagramModule, ThreadsModule, PublishRequest

    ig = InstagramModule()   # INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_USER_ID 환경변수
    th = ThreadsModule()     # THREADS_ACCESS_TOKEN, THREADS_USER_ID 환경변수

    req = PublishRequest(
        text="안녕하세요! 오늘 외래에서 있었던 일 …",
        media_urls=["https://example.com/image.jpg"],
        hashtags=["가정의학과", "AI의사"],
    )
    result = ig.publish(req)   # PublishResult 반환
    print(result.ok, result.permalink)

    result = th.publish(req)
    print(result.ok, result.published_media_id)
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import requests
except ImportError as e:
    raise ImportError("requests가 필요합니다: pip install requests") from e


# ── 데이터 모델 ────────────────────────────────────────────

@dataclass
class PublishRequest:
    """발행 요청 파라미터."""
    text: str = ""
    media_urls: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    location_tag: str | None = None
    alt_text: str | None = None
    dry_run: bool = False


@dataclass
class PublishResult:
    """발행 결과."""
    platform: str
    ok: bool
    dry_run: bool = False
    created_container_id: str | None = None
    published_media_id: str | None = None
    permalink: str | None = None
    error_stage: str | None = None
    error_message: str | None = None
    raw_response_summary: str = ""


# ── 공통 HTTP 헬퍼 ────────────────────────────────────────

class _MetaHttpMixin:
    @staticmethod
    def _join_text(text: str, hashtags: list[str]) -> str:
        joined = text.strip()
        lower = joined.lower()
        unique = [
            (t if t.startswith("#") else f"#{t}")
            for t in hashtags
            if f"#{t.lstrip('#').lower()}" not in lower
        ]
        return f"{joined}\n\n{' '.join(unique)}" if unique else joined

    @staticmethod
    def _post_form(url: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
        r = requests.post(url, data=payload, timeout=timeout)
        try:
            r.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}") from exc
        return r.json()

    @staticmethod
    def _get_json(url: str, params: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
        r = requests.get(url, params=params, timeout=timeout)
        try:
            r.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}") from exc
        return r.json()

    def _failure(self, platform: str, stage: str, msg: str) -> PublishResult:
        return PublishResult(platform=platform, ok=False, error_stage=stage, error_message=msg)

    def _dry_run_result(self, platform: str, request: PublishRequest) -> PublishResult:
        return PublishResult(
            platform=platform,
            ok=True,
            dry_run=True,
            created_container_id="dry-run-container",
            published_media_id="dry-run-media",
            raw_response_summary=f"dry_run | media={len(request.media_urls)}",
        )


# ── Instagram Graph API v23.0 ─────────────────────────────

class InstagramModule(_MetaHttpMixin):
    """Instagram Graph API v23.0 클라이언트."""

    BASE = "https://graph.instagram.com/v23.0"

    def __init__(
        self,
        access_token: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self.access_token = access_token or os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
        self.user_id = user_id or os.environ.get("INSTAGRAM_USER_ID", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token and self.user_id)

    def publish(self, request: PublishRequest) -> PublishResult:
        """이미지/캐러셀 게시물을 발행합니다."""
        if not self.is_configured:
            return self._failure("instagram", "preflight", "INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_USER_ID 미설정")
        if not request.media_urls:
            return self._failure("instagram", "preflight", "Instagram 발행에는 media_url이 최소 1개 필요합니다")
        if request.dry_run:
            return self._dry_run_result("instagram", request)
        try:
            caption = self._join_text(request.text, request.hashtags)
            if len(request.media_urls) == 1:
                cid = self._single_image(request.media_urls[0], caption)
            else:
                children = [self._carousel_child(url) for url in request.media_urls]
                cid = self._carousel_container(children, caption)
            time.sleep(30)  # Meta 서버 처리 대기
            media_id = self._publish_container(cid)
            permalink = self._get_permalink(media_id)
            return PublishResult(
                platform="instagram",
                ok=True,
                created_container_id=cid,
                published_media_id=media_id,
                permalink=permalink,
                raw_response_summary="instagram publish succeeded",
            )
        except Exception as exc:
            return self._failure("instagram", "publish", str(exc))

    def _single_image(self, image_url: str, caption: str) -> str:
        data = self._post_form(
            f"{self.BASE}/{self.user_id}/media",
            {"image_url": image_url, "caption": caption, "access_token": self.access_token},
        )
        return data["id"]

    def _carousel_child(self, image_url: str) -> str:
        data = self._post_form(
            f"{self.BASE}/{self.user_id}/media",
            {"image_url": image_url, "is_carousel_item": "true", "access_token": self.access_token},
        )
        return data["id"]

    def _carousel_container(self, children: list[str], caption: str) -> str:
        data = self._post_form(
            f"{self.BASE}/{self.user_id}/media",
            {
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": caption,
                "access_token": self.access_token,
            },
        )
        return data["id"]

    def _publish_container(self, creation_id: str) -> str:
        data = self._post_form(
            f"{self.BASE}/{self.user_id}/media_publish",
            {"creation_id": creation_id, "access_token": self.access_token},
        )
        return data["id"]

    def _get_permalink(self, media_id: str) -> str | None:
        data = self._get_json(
            f"{self.BASE}/{media_id}",
            {"fields": "permalink", "access_token": self.access_token},
        )
        return data.get("permalink")


# ── Threads API v1.0 ──────────────────────────────────────

class ThreadsModule(_MetaHttpMixin):
    """Threads Graph API v1.0 클라이언트."""

    BASE = "https://graph.threads.net/v1.0"

    def __init__(
        self,
        access_token: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self.access_token = access_token or os.environ.get("THREADS_ACCESS_TOKEN", "")
        self.user_id = user_id or os.environ.get("THREADS_USER_ID", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token and self.user_id)

    def publish(self, request: PublishRequest) -> PublishResult:
        """텍스트/이미지/캐러셀 게시물을 발행합니다."""
        if not self.is_configured:
            return self._failure("threads", "preflight", "THREADS_ACCESS_TOKEN / THREADS_USER_ID 미설정")
        if request.dry_run:
            return self._dry_run_result("threads", request)
        try:
            text = self._join_text(request.text, request.hashtags)
            if not request.media_urls:
                cid = self._text_container(text)
            elif len(request.media_urls) == 1:
                cid = self._image_container(request.media_urls[0], text, request.alt_text)
                time.sleep(30)
            else:
                children = [self._carousel_item(url) for url in request.media_urls]
                cid = self._carousel_container(children, text)
                time.sleep(30)
            media_id = self._publish_container(cid)
            return PublishResult(
                platform="threads",
                ok=True,
                created_container_id=cid,
                published_media_id=media_id,
                raw_response_summary="threads publish succeeded",
            )
        except Exception as exc:
            return self._failure("threads", "publish", str(exc))

    def _text_container(self, text: str) -> str:
        data = self._post_form(
            f"{self.BASE}/{self.user_id}/threads",
            {"media_type": "TEXT", "text": text, "access_token": self.access_token},
        )
        return data["id"]

    def _image_container(self, image_url: str, text: str, alt_text: str | None) -> str:
        payload: dict[str, Any] = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": text,
            "access_token": self.access_token,
        }
        if alt_text:
            payload["alt_text"] = alt_text
        return self._post_form(f"{self.BASE}/{self.user_id}/threads", payload)["id"]

    def _carousel_item(self, image_url: str) -> str:
        data = self._post_form(
            f"{self.BASE}/{self.user_id}/threads",
            {"media_type": "IMAGE", "image_url": image_url, "is_carousel_item": "true", "access_token": self.access_token},
        )
        return data["id"]

    def _carousel_container(self, children: list[str], text: str) -> str:
        data = self._post_form(
            f"{self.BASE}/{self.user_id}/threads",
            {"media_type": "CAROUSEL", "children": ",".join(children), "text": text, "access_token": self.access_token},
        )
        return data["id"]

    def _publish_container(self, creation_id: str) -> str:
        data = self._post_form(
            f"{self.BASE}/{self.user_id}/threads_publish",
            {"creation_id": creation_id, "access_token": self.access_token},
        )
        return data["id"]
