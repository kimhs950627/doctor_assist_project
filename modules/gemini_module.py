"""Gemini API 통합 모듈.

Usage::

    from modules.gemini_module import GeminiModule

    gm = GeminiModule()  # GEMINI_API_KEY 환경변수 필요

    # 1. 단순 텍스트 질의
    answer = gm.ask("고혈압 2단계 1차 약제 추천")

    # 2. 이미지 + 텍스트 (초음파 감별)
    answer = gm.ask("이 초음파 소견의 감별 진단 3가지", image_path="/tmp/us.jpg")

    # 3. SOAP 변환
    soap = gm.to_soap("58세 남성, 두통 3일, 혈압 160/100 …")

    # 4. 환자 설명문 생성
    edu = gm.patient_education("제2형 당뇨", grade="중학교", points=["식이","운동","약복용"])

    # 5. 감별 진단 리스트
    ddx = gm.differential_diagnosis(symptoms="우상복부 둔통 3개월, AST/ALT 경미한 상승", n=5)

    # 6. SNS 콘텐츠 초안 (인스타 + 스레드)
    draft = gm.generate_sns_draft(topic="가정의학과 의사의 AI 활용기")

    # 7. 무료 Flash 모델 헬스체크
    ok, detail = gm.ping()
"""
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any

try:
    from google import genai
    from google.genai import errors, types
except ImportError as e:
    raise ImportError(
        "google-genai 패키지가 필요합니다: pip install google-genai"
    ) from e


class GeminiQuotaError(Exception):
    """Gemini API 쿼터 초과 (429 / RESOURCE_EXHAUSTED)."""


class GeminiModule:
    """Gemini API 래퍼. 의사 보조 기능에 특화된 메서드를 제공합니다."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        grounding_model: str = "gemini-2.5-flash",
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY 환경변수 또는 api_key 파라미터가 필요합니다.")
        self.model = model
        self.grounding_model = grounding_model
        self._client = genai.Client(api_key=self.api_key)

    # ── 공통 유틸 ──────────────────────────────────────────

    def ping(self) -> tuple[bool, str]:
        """API 연결 확인 (토큰 소모 없음)."""
        try:
            result = self._client.models.get(model=self.model)
            return True, result.display_name or self.model
        except Exception as exc:
            return False, str(exc)

    def _build_contents(self, prompt: str, image_path: str | None) -> list:
        contents: list = []
        if image_path:
            mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            contents.append(
                types.Part.from_bytes(data=Path(image_path).read_bytes(), mime_type=mime)
            )
        contents.append(prompt)
        return contents

    def _safe_generate(self, prompt: str, image_path: str | None = None, **cfg_kwargs) -> str:
        """generate_content 호출 + 쿼터 에러 변환."""
        try:
            contents = self._build_contents(prompt, image_path)
            if cfg_kwargs:
                resp = self._client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(**cfg_kwargs),
                )
            else:
                resp = self._client.models.generate_content(
                    model=self.model, contents=contents
                )
            return (resp.text or "").strip()
        except Exception as exc:
            if self._is_quota_err(exc):
                raise GeminiQuotaError("Gemini API 쿼터 초과") from exc
            raise

    @staticmethod
    def _is_quota_err(exc: Exception) -> bool:
        if isinstance(exc, errors.APIError):
            return exc.code == 429 or "quota" in str(exc).lower()
        return False

    @staticmethod
    def _strip_markdown_json(text: str) -> str:
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        if "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text

    # ── 의사 보조 기능 ─────────────────────────────────────

    def ask(self, question: str, image_path: str | None = None) -> str:
        """일반 질의응답. 초음파 이미지 첨부 가능."""
        return self._safe_generate(question, image_path)

    def to_soap(
        self,
        raw_note: str,
        image_path: str | None = None,
    ) -> dict[str, str]:
        """진료 메모/음성 전사 → SOAP 구조화 dict 반환.

        Returns: {"S": ..., "O": ..., "A": ..., "P": ...}
        """
        prompt = (
            "다음 진료 메모를 SOAP 형식으로 구조화하세요.\n"
            "JSON으로만 응답하세요: {\"S\": ..., \"O\": ..., \"A\": ..., \"P\": ...}\n\n"
            f"메모:\n{raw_note}"
        )
        raw = self._safe_generate(prompt, image_path)
        try:
            return json.loads(self._strip_markdown_json(raw))
        except Exception:
            return {"S": raw, "O": "", "A": "", "P": ""}

    def patient_education(
        self,
        diagnosis: str,
        grade: str = "중학교",
        points: list[str] | None = None,
        language: str = "한국어",
    ) -> str:
        """환자 교육 설명문 생성."""
        point_str = ", ".join(points) if points else "핵심 3가지"
        prompt = (
            f"진단명 '{diagnosis}'에 대해 {grade} 수준의 언어로 환자 교육 설명문을 작성하세요.\n"
            f"언어: {language}\n"
            f"포함 항목: {point_str}\n"
            f"출력 형식: 글머리 기호(-)로 항목 구분, 200자 이내"
        )
        return self._safe_generate(prompt)

    def differential_diagnosis(
        self,
        symptoms: str,
        n: int = 5,
        image_path: str | None = None,
    ) -> list[dict[str, str]]:
        """감별 진단 리스트 반환.

        Returns: [{"diagnosis": ..., "key_feature": ..., "next_step": ...}, ...]
        """
        prompt = (
            f"증상/소견: {symptoms}\n\n"
            f"가능한 감별 진단 {n}가지를 JSON 배열로 반환하세요.\n"
            "각 항목: {\"diagnosis\": 진단명, \"key_feature\": 핵심 구분 포인트, \"next_step\": 권장 검사/처치}\n"
            "JSON 외 텍스트 없이 배열만 출력."
        )
        raw = self._safe_generate(prompt, image_path)
        try:
            return json.loads(self._strip_markdown_json(raw))
        except Exception:
            return [{"diagnosis": raw, "key_feature": "", "next_step": ""}]

    def check_drug_interaction(
        self,
        current_meds: list[str],
        new_med: str,
    ) -> dict[str, Any]:
        """약물 상호작용 체크.

        Returns: {"has_interaction": bool, "severity": str, "details": str, "recommendation": str}
        """
        med_list = ", ".join(current_meds)
        prompt = (
            f"현재 복용약: {med_list}\n"
            f"추가 예정약: {new_med}\n\n"
            "약물 상호작용을 분석하고 JSON으로 응답:"
            "{\"has_interaction\": bool, \"severity\": 'none|mild|moderate|severe', "
            "\"details\": 설명, \"recommendation\": 임상 권고사항}\n"
            "JSON만 출력."
        )
        raw = self._safe_generate(prompt)
        try:
            return json.loads(self._strip_markdown_json(raw))
        except Exception:
            return {"has_interaction": False, "severity": "unknown", "details": raw, "recommendation": ""}

    def generate_sns_draft(
        self,
        topic: str,
        image_path: str | None = None,
        style: str = "교육적이고 친근한",
    ) -> dict[str, Any]:
        """SNS 콘텐츠 초안 생성 (인스타그램 + 스레드 + 해시태그).

        Returns: {"instagram_caption": ..., "threads_caption": ..., "hashtags": [...], "rationale": ...}
        """
        prompt = (
            f"주제: {topic}\n"
            f"스타일: {style}\n"
            "가정의학과 전문의 + AI 개발자의 관점으로 의사 SNS 콘텐츠 초안을 작성하세요.\n"
            "JSON으로 응답: {\"instagram_caption\": 인스타그램 캡션(이모지 포함), "
            "\"threads_caption\": 스레드용 짧은 버전, "
            "\"hashtags\": 한국어+영어 해시태그 15개 배열, "
            "\"rationale\": 이 방향을 선택한 이유}\n"
            "JSON만 출력."
        )
        raw = self._safe_generate(prompt, image_path)
        try:
            return json.loads(self._strip_markdown_json(raw))
        except Exception:
            return {"instagram_caption": raw, "threads_caption": raw[:280], "hashtags": [], "rationale": ""}

    def ground_search(self, query: str) -> str:
        """Google Search Grounding으로 최신 정보 수집."""
        try:
            resp = self._client.models.generate_content(
                model=self.grounding_model,
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )
            return (resp.text or "").strip()
        except Exception as exc:
            if self._is_quota_err(exc):
                raise GeminiQuotaError("Gemini API 쿼터 초과") from exc
            raise
