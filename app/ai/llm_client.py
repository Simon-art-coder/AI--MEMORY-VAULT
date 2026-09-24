"""
LLM client — Groq.

Chat/extraction now runs on Groq instead of Gemini. Reason: Gemini's
free-tier generateContent endpoint has been persistently returning 503
(model overloaded) across multiple Gemini models — a known, ongoing
issue reported widely in Google's own developer forums, not something
fixable from this app's side. Groq is a different company on different
infrastructure, decoupling chat reliability from Gemini's current
capacity problems. Embeddings (app/ai/embeddings.py) stay on Gemini,
since that endpoint has been working fine throughout.

Note on reasoning_effort: openai/gpt-oss-120b is a reasoning model --
it spends part of its token budget on internal "thinking" before
producing visible output. This is a documented, known failure mode for
this specific model: with reasoning_effort left at its default
("medium") and max_tokens too low for a given prompt, it can exhaust
the entire budget on invisible reasoning and return a completely empty
response with a 200 OK -- no error, since nothing technically failed on
the API's side. Setting reasoning_effort="low" reduces how much of the
budget goes to reasoning, which matters most for tasks like structured
JSON extraction that don't need deep reasoning anyway.
"""

import time

import httpx

from app.core.config import get_settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
RETRYABLE_STATUS_CODES = {429, 503}


class LLMNotConfiguredError(Exception):
    pass


class LLMRequestError(Exception):
    pass


def generate(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1024,
    max_retries: int = 2,
    reasoning_effort: str = "low",
) -> str:
    settings = get_settings()

    if not settings.groq_api_key:
        raise LLMNotConfiguredError(
            "No GROQ_API_KEY is set. Get a free key at https://console.groq.com/keys "
            "and set it in .env to enable AI answers and extraction."
        )

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = httpx.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": max_tokens,
                    "reasoning_effort": reasoning_effort,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            if not content or not content.strip():
                finish_reason = data["choices"][0].get("finish_reason", "unknown")
                raise LLMRequestError(
                    f"Groq returned an empty response (finish_reason={finish_reason}). "
                    "This is a known failure mode for reasoning models when the token "
                    "budget runs out during internal reasoning before producing visible "
                    "output -- try increasing max_tokens for this call."
                )

            return content

        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise LLMRequestError(f"LLM request failed: {exc}") from exc

        except httpx.RequestError as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise LLMRequestError(f"LLM request failed: {exc}") from exc

        except (KeyError, IndexError) as exc:
            raise LLMRequestError(f"Groq returned no usable response: {exc}") from exc

    raise LLMRequestError(f"LLM request failed after {max_retries} retries: {last_error}")