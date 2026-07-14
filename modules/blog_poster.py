"""
blog_poster.py
--------------
Platform-specific posting modules:
  - Tistory (공식 Open API)
  - Instagram (Meta Graph API)
  - Naver Blog (Playwright RPA, Tistory migration 방식)

사용 흐름:
  1. blog_helpers.elaborate_and_place() → 원고 dict
  2. TistoryPoster.post()     → tistory URL + 이미지 URL 목록
  3. InstagramPoster.post()   → instagram media_id
  4. NaverPoster.post()       → naver URL  (tistory HTML 재사용)
"""

import asyncio
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from playwright.async_api import async_playwright

from blog_helpers import inject_images_into_html, resize_image


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TISTORY
# ═══════════════════════════════════════════════════════════════════════════════

class TistoryPoster:
    """
    티스토리 Open API를 이용한 자동 포스팅.
    공식 API → requests 만으로 완전 자동화 가능.
    """

    BASE = "https://www.tistory.com/apis"

    def __init__(self, access_token: str, blog_name: str):
        self.token = access_token
        self.blog_name = blog_name

    async def _upload_image(self, image_path: Path) -> str:
        """이미지를 티스토리에 업로드하고 URL 반환."""
        url = f"{self.BASE}/post/attach"
        async with httpx.AsyncClient() as client:
            with open(image_path, "rb") as f:
                r = await client.post(
                    url,
                    data={"access_token": self.token, "blogName": self.blog_name, "output": "json"},
                    files={"uploadedfile": (image_path.name, f, "image/jpeg")},
                    timeout=60,
                )
        r.raise_for_status()
        data = r.json()
        return data["tistory"]["replacer"]

    async def post(
        self,
        title: str,
        html: str,
        image_paths: list[Path],
        tags: list[str],
        category_id: str = "0",
        visibility: int = 3,  # 3=공개
    ) -> dict:
        """
        이미지 업로드 → HTML 내 마커 치환 → 글 게시.
        Returns: {"post_id": str, "url": str, "image_urls": list[str]}
        """
        image_urls = []
        for p in image_paths:
            resize_image(p)
            url = await self._upload_image(p)
            image_urls.append(url)

        final_html = inject_images_into_html(html, image_urls)

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.BASE}/post/write",
                data={
                    "access_token": self.token,
                    "output": "json",
                    "blogName": self.blog_name,
                    "title": title,
                    "content": final_html,
                    "visibility": str(visibility),
                    "categoryId": category_id,
                    "tag": ",".join(tags),
                    "acceptComment": "1",
                },
                timeout=30,
            )
        r.raise_for_status()
        data = r.json()["tistory"]
        return {"post_id": data["postId"], "url": data["url"], "image_urls": image_urls}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. INSTAGRAM
# ═══════════════════════════════════════════════════════════════════════════════

class InstagramPoster:
    """
    Meta Content Publishing API를 이용한 인스타그램 포스팅.
    - 단일 이미지: IMAGE 타입
    - 다중 이미지: CAROUSEL 타입
    Business/Creator 계정 + Page 연결 필요.
    """

    GRAPH = "https://graph.instagram.com/v22.0"

    def __init__(self, access_token: str, ig_user_id: str):
        self.token = access_token
        self.user_id = ig_user_id

    def _params(self, extra: dict) -> dict:
        return {"access_token": self.token, **extra}

    async def _create_container(self, image_url: str, caption: str = "") -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.GRAPH}/{self.user_id}/media",
                params=self._params({"image_url": image_url, "caption": caption}),
                timeout=30,
            )
        r.raise_for_status()
        return r.json()["id"]

    async def _create_carousel_item(self, image_url: str) -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.GRAPH}/{self.user_id}/media",
                params=self._params({"image_url": image_url, "is_carousel_item": "true"}),
                timeout=30,
            )
        r.raise_for_status()
        return r.json()["id"]

    async def _publish(self, container_id: str) -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.GRAPH}/{self.user_id}/media_publish",
                params=self._params({"creation_id": container_id}),
                timeout=30,
            )
        r.raise_for_status()
        return r.json()["id"]

    async def post(
        self,
        image_urls: list[str],  # Tistory 업로드 URL 재활용
        caption: str,
        hashtags: list[str],
    ) -> str:
        """
        이미지 1장 → 단일 포스트, 2장 이상 → 캐러셀.
        Returns: instagram media_id
        """
        full_caption = f"{caption}\n\n{'  '.join(hashtags)}"

        if len(image_urls) == 1:
            container_id = await self._create_container(image_urls[0], full_caption)
        else:
            item_ids = await asyncio.gather(
                *[self._create_carousel_item(u) for u in image_urls]
            )
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.GRAPH}/{self.user_id}/media",
                    params=self._params({
                        "media_type": "CAROUSEL",
                        "children": ",".join(item_ids),
                        "caption": full_caption,
                    }),
                    timeout=30,
                )
            r.raise_for_status()
            container_id = r.json()["id"]

        await asyncio.sleep(5)  # Meta 서버 처리 대기
        media_id = await self._publish(container_id)
        return media_id


# ═══════════════════════════════════════════════════════════════════════════════
# 3. NAVER BLOG (Playwright RPA)
# ═══════════════════════════════════════════════════════════════════════════════

class NaverPoster:
    """
    네이버 블로그 Playwright 자동화.
    - 티스토리에서 게시된 HTML을 네이버 호환 형태로 정제 후 SmartEditor에 삽입.
    - 최초 1회 수동 로그인 후 storage_state.json을 저장해두면 이후 재로그인 불필요.
    """

    WRITE_URL = "https://blog.naver.com/{blog_id}/postwrite"

    def __init__(
        self,
        blog_id: str,
        storage_state_path: Path = Path("naver_session.json"),
        headless: bool = True,
    ):
        self.blog_id = blog_id
        self.storage_state_path = storage_state_path
        self.headless = headless

    @staticmethod
    def sanitize_html(html: str) -> str:
        """
        티스토리 HTML → 네이버 SmartEditor 호환 HTML 정제.
        - class/id 속성 제거
        - 허용 태그만 유지: h2, h3, p, strong, em, br, img, ul, ol, li
        - 인라인 스타일 단순화
        """
        html = re.sub(r'\s+(class|id)="[^"]*"', "", html)
        html = re.sub(r"<div[^>]*>", "<p>", html)
        html = re.sub(r"</div>", "</p>", html)
        html = re.sub(r"(<p>\s*</p>)+", "", html)
        return html.strip()

    async def _ensure_session(self, page):
        """세션이 만료됐으면 RuntimeError 발생 (Telegram 알림 유도)."""
        await page.goto("https://www.naver.com")
        login_btn = await page.query_selector("a.MyView-module__link_login___HpHMW")
        if login_btn:
            raise RuntimeError("NAVER_SESSION_EXPIRED")

    async def post(
        self,
        title: str,
        html: str,
        image_paths: list[Path],
    ) -> str:
        """
        네이버 블로그에 글 게시.
        Returns: 게시된 포스트 URL
        """
        sanitized = self.sanitize_html(html)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"],  # Termux 호환
            )
            ctx_kwargs = {}
            if self.storage_state_path.exists():
                ctx_kwargs["storage_state"] = str(self.storage_state_path)

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                **ctx_kwargs,
            )
            page = await context.new_page()

            try:
                await self._ensure_session(page)

                write_url = self.WRITE_URL.format(blog_id=self.blog_id)
                await page.goto(write_url, wait_until="networkidle", timeout=30_000)
                await asyncio.sleep(2)

                title_input = await page.wait_for_selector("#subject", timeout=10_000)
                await title_input.click()
                await title_input.fill(title)
                await asyncio.sleep(0.5)

                editor_frame = await page.wait_for_selector(
                    "iframe[title='se2_iframe'], iframe#se2_iframe", timeout=10_000
                )
                frame = await editor_frame.content_frame()
                await frame.evaluate(
                    "html => document.execCommand('insertHTML', false, html)",
                    sanitized,
                )
                await asyncio.sleep(1)

                if image_paths:
                    attach_btn = await page.query_selector("button[data-name='image']")
                    if attach_btn:
                        for img_path in image_paths:
                            resize_image(img_path)
                            async with page.expect_file_chooser() as fc_info:
                                await attach_btn.click()
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(str(img_path))
                            await asyncio.sleep(2)

                publish_btn = await page.wait_for_selector(
                    "button[data-log='GNB.publish'], #publish", timeout=10_000
                )
                await publish_btn.click()
                await asyncio.sleep(3)

                post_url = page.url
                if "postwrite" in post_url:
                    await page.wait_for_url(
                        lambda u: "blog.naver.com" in u and "postwrite" not in u,
                        timeout=15_000,
                    )
                    post_url = page.url

                await context.storage_state(path=str(self.storage_state_path))
                return post_url

            finally:
                await browser.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. UNIFIED DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

async def publish_all(
    draft: dict,
    image_paths: list[Path],
    tistory: TistoryPoster,
    instagram: InstagramPoster,
    naver: NaverPoster,
) -> dict:
    """
    draft = blog_helpers.elaborate_and_place()의 반환값.
    1. Tistory 게시 (이미지 업로드 → URL 획득)
    2. Instagram 게시 (Tistory 이미지 URL 재활용)
    3. Naver 게시   (Tistory HTML sanitize 후 Playwright)

    Returns:
        {
          "tistory_url": str,
          "instagram_media_id": str,
          "naver_url": str,
        }
    """
    results = {}

    # ── 1. Tistory ─────────────────────────────────────────────────
    tistory_result = await tistory.post(
        title=draft["tistory"]["title"],
        html=draft["tistory"]["html"],
        image_paths=image_paths,
        tags=draft["tistory"]["tags"],
    )
    results["tistory_url"] = tistory_result["url"]
    results["tistory_image_urls"] = tistory_result["image_urls"]

    # ── 2. Instagram (이미지 URL 재활용) ─────────────────────
    if tistory_result["image_urls"]:
        ig_id = await instagram.post(
            image_urls=tistory_result["image_urls"],
            caption=draft["instagram"]["caption"],
            hashtags=draft["instagram"]["hashtags"],
        )
        results["instagram_media_id"] = ig_id

    # ── 3. Naver ───────────────────────────────────────────────
    naver_url = await naver.post(
        title=draft["naver"]["title"],
        html=draft["naver"]["sanitized_html"],
        image_paths=image_paths,
    )
    results["naver_url"] = naver_url

    return results
