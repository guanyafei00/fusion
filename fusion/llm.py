"""LLM client — OpenAI-compatible, supports any provider."""
import json
import httpx
from .config import Config
from .security import RateLimiter


def _headers(cfg: Config) -> dict:
    return {
        "Authorization": f"Bearer {cfg.llm_api_key}",
        "Content-Type": "application/json",
    }


def chat(cfg: Config, model: str, messages: list[dict], temperature: float = 0.3,
         max_tokens: int = 2048) -> str:
    """Single chat completion call. Returns assistant content string."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = httpx.post(
        f"{cfg.llm_base_url}/chat/completions",
        headers=_headers(cfg),
        json=payload,
        timeout=cfg.llm_timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def chat_json(cfg: Config, model: str, messages: list[dict],
              temperature: float = 0.0, max_tokens: int = 2048,
              retries: int = 1) -> dict:
    """Chat completion that expects JSON response. Retries on parse failure."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(retries + 1):
        try:
            resp = httpx.post(
                f"{cfg.llm_base_url}/chat/completions",
                headers=_headers(cfg),
                json=payload,
                timeout=cfg.llm_timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"].get("content")
            if not content:
                # Model returned empty content (e.g. proxy doesn't support response_format)
                # Fallback: retry without response_format
                if attempt < retries:
                    payload.pop("response_format", None)
                    continue
                return {"error": "empty_content", "raw": None}
            return json.loads(content)
        except (json.JSONDecodeError, TypeError) as e:
            if attempt < retries:
                payload.pop("response_format", None)
                continue
            return {"error": "non_json_response", "raw": str(content)[:500] if content else None}
        except Exception as e:
            if attempt < retries:
                continue
            return {"error": "api_error", "raw": str(e)[:500]}
    return {"error": "no_response"}


def chat_stream(cfg: Config, model: str, messages: list[dict],
                temperature: float = 0.3, max_tokens: int = 2048):
    """Streaming chat completion. Yields content deltas."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    with httpx.stream(
        "POST",
        f"{cfg.llm_base_url}/chat/completions",
        headers=_headers(cfg),
        json=payload,
        timeout=cfg.llm_timeout,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta and delta["content"]:
                    yield delta["content"]
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
