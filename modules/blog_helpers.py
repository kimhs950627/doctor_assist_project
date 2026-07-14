"""
blog_helpers.py
---------------
Helper functions shared across all blog/SNS platforms:
  - Gemini API calls (text elaboration + image placement)
  - Image download/resize utilities
  - HTML sanitization for platform compatibility
  - Session buffer for Telegram media groups
"""

import asyncio
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image

# ─── Gemini API ─────────────────────────────────────────────────────────────────────

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

SAFETY = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}


def init_gemini(api_key: str):
    genai.configure(api_key=api_key)


async def elaborate_and_place(
    text_outline: str,
    image_paths: list[Path],
    author_style: str = "가정의학과 전문의, 친근하되 신뢰감 있는 말투",
) -> dict:
    """
    1회 Gemini 호출로 플랫폼별 원고 3종 + 이미지 삽입 위치를 동시에 생성.

    Returns:
        {
          "tistory":   {"title": str, "html": str, "tags": list[str]},
          "instagram": {"caption": str, "hashtags": list[str]},
          "naver":     {"title": str, "sanitized_html": str},
          "image_placement": {"image_1": "소제목_텍스트", ...}
        }
    """
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        safety_settings=SAFETY,
    )

    n = len(image_paths)
    image_marker_note = (
        f"\n- 이미지가 {n}장 제공되었다. html 내 적절한 위치에 {{{{IMAGE_1}}}}~{{{{IMAGE_{n}}}}} 마커를 삽입하라."
        if n > 0 else ""
    )

    prompt = f"""
당신은 {author_style}가 운영하는 건강 정보 블로그의 에디터다.
아래 골자를 바탕으로 세 가지 버전 원고를 **반드시 JSON만** 반환하라. 코드 블록(```) 없이 순수 JSON.

[골자]
{text_outline}
{image_marker_note}

JSON 스키마:
{{
  "tistory": {{
    "title": "SEO 최적화된 제목 (40자 이내)",
    "html": "<h2>소제목</h2><p>본문...</p> (2000~3000자, 소제목 <h2>, 강조 <strong>, 이미지 마커 포함)",
    "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
  }},
  "instagram": {{
    "caption": "300자 이내. 개행으로 단락 구분, 이모지 활용, 핵심만 간결하게.",
    "hashtags": ["#해시태그1", "#해시태그2", "#해시태그3", "#해시태그4", "#해시태그5",
                 "#해시태그6", "#해시태그7", "#해시태그8", "#해시태그9", "#해시태그10"]
  }},
  "naver": {{
    "title": "네이버 검색에 최적화된 제목 (30자 이내)",
    "sanitized_html": "네이버 SmartEditor 호환 HTML (인라인 스타일, <span style=...>, <br> 위주, <h2>/<h3> 허용)"
  }},
  "image_placement": {{
    "image_1": "삽입될 소제목 텍스트 (정확히 일치)",
    "image_2": "삽입될 소제목 텍스트"
  }}
}}
"""

    response = await asyncio.to_thread(model.generate_content, prompt)
    raw = response.text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```$", "", raw).strip()

    import json
    result = json.loads(raw)

    if image_paths:
        result["image_placement"] = await _vision_placement(
            result["tistory"]["html"], image_paths, result.get("image_placement", {})
        )

    return result


async def _vision_placement(html: str, image_paths: list[Path], existing: dict) -> dict:
    """Gemini Vision으로 이미지 내용을 분석해 placement 정확도 향상."""
    vision_model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        safety_settings=SAFETY,
    )
    parts = [f"아래 블로그 본문과 이미지들을 분석하여, 각 이미지가 본문의 어느 <h2> 소제목 바로 뒤에 들어가면 가장 자연스러운지 JSON으로만 반환하라.\n\n[본문]\n{html}\n\n예시: {{\"image_1\": \"소제목 텍스트\"}}"]  
    for p in image_paths:
        img = Image.open(p)
        parts.append(img)
    response = await asyncio.to_thread(vision_model.generate_content, parts)
    raw = response.text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```$", "", raw).strip()
    import json
    return json.loads(raw)


# ─── Image Utilities ─────────────────────────────────────────────────────────────

async def download_image(url: str, dest_dir: Path, filename: str) -> Path:
    """URL에서 이미지를 다운로드하여 dest_dir에 저장."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    async with httpx.AsyncClient() as client:
        r = await client.get(url, follow_redirects=True, timeout=30)
        r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def resize_image(src: Path, max_width: int = 1200, quality: int = 85) -> Path:
    """이미지를 max_width 이하로 리사이즈 후 JPEG로 저장. 원본 덮어쓰기."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
    img.save(src, "JPEG", quality=quality, optimize=True)
    return src


def inject_images_into_html(html: str, image_urls: list[str]) -> str:
    """
    {IMAGE_1} ~ {IMAGE_N} 마커를 실제 <img> 태그로 치환.
    image_urls: 업로드 완료된 URL 목록 (순서대로)
    """
    for i, url in enumerate(image_urls, start=1):
        tag = f'<p style="text-align:center;"><img src="{url}" style="max-width:100%;height:auto;" /></p>'
        html = html.replace(f"{{IMAGE_{i}}}", tag)
    html = re.sub(r"\{IMAGE_\d+\}", "", html)
    return html


# ─── Telegram Session Buffer ──────────────────────────────────────────────────

_media_group_buffer: dict[str, dict] = {}  # media_group_id → {"text": str, "images": list, "ts": float}


async def buffer_media_group(
    media_group_id: str,
    text: Optional[str],
    image_path: Optional[Path],
    flush_after: float = 2.0,
) -> Optional[dict]:
    """
    Telegram 앨범 메시지를 버퍼링 후 flush_after 초 뒤에 반환.
    반환: {"text": str, "images": [Path, ...]} or None (아직 수집 중)
    """
    entry = _media_group_buffer.setdefault(
        media_group_id, {"text": None, "images": [], "ts": asyncio.get_event_loop().time()}
    )
    if text:
        entry["text"] = text
    if image_path:
        entry["images"].append(image_path)
    entry["ts"] = asyncio.get_event_loop().time()

    await asyncio.sleep(flush_after)

    if asyncio.get_event_loop().time() - entry["ts"] >= flush_after - 0.1:
        return _media_group_buffer.pop(media_group_id, None)
    return None
