"""
Text embeddings.
"""

import hashlib
import logging
import math
import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 256
GEMINI_EMBEDDING_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
)


def embed_text(text: str) -> list[float]:
    settings = get_settings()

    if settings.gemini_api_key:
        try:
            return _embed_with_gemini(text, settings.gemini_api_key)
        except httpx.HTTPError as exc:
            logger.warning("Gemini embedding call failed, using local fallback: %s", exc)
            return _embed_with_hashing_fallback(text)

    if settings.openai_api_key:
        try:
            return _embed_with_openai(text, settings.openai_api_key)
        except httpx.HTTPError as exc:
            logger.warning("OpenAI embedding call failed, using local fallback: %s", exc)
            return _embed_with_hashing_fallback(text)

    return _embed_with_hashing_fallback(text)


def _embed_with_gemini(text: str, api_key: str) -> list[float]:
    response = httpx.post(
        GEMINI_EMBEDDING_URL,
        params={"key": api_key},
        json={"content": {"parts": [{"text": text}]}},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]["values"]


def _embed_with_openai(text: str, api_key: str) -> list[float]:
    response = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": "text-embedding-3-small", "input": text},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def _embed_with_hashing_fallback(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    words = re.findall(r"[a-z0-9]+", text.lower())

    for word in words:
        bucket = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % EMBEDDING_DIM
        vector[bucket] += 1.0

    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]

    return vector


def is_using_real_embeddings() -> bool:
    settings = get_settings()
    return bool(settings.gemini_api_key or settings.openai_api_key)