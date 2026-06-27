"""Configuration — zero hardcoded secrets, all from env vars."""
import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    val = os.environ.get(name, default)
    if not val and not default:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def _env_opt(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class Config:
    # --- LLM Gateway (any OpenAI-compatible API) ---
    llm_base_url: str = field(default_factory=lambda: _env("FUSION_LLM_BASE_URL"))
    llm_api_key: str = field(default_factory=lambda: _env("FUSION_LLM_API_KEY"))
    llm_timeout: int = field(default_factory=lambda: int(_env_opt("FUSION_LLM_TIMEOUT", "90")))

    # --- Model roster ---
    panel_models: list = field(default_factory=lambda: _env_opt(
        "FUSION_PANEL_MODELS",
        "qwen/qwen3-next-80b-a3b-instruct,google/diffusiongemma-26b-a4b-it,minimaxai/minimax-m2.7"
    ).split(","))
    judge_model: str = field(default_factory=lambda: _env_opt(
        "FUSION_JUDGE_MODEL", "openai/gpt-oss-120b"))
    synth_model: str = field(default_factory=lambda: _env_opt(
        "FUSION_SYNTH_MODEL", "deepseek-ai/deepseek-v4-pro"))

    # --- Search (optional) ---
    tavily_api_key: str = field(default_factory=lambda: _env_opt("FUSION_TAVILY_KEY", ""))

    # --- Fetcher tuning ---
    fetch_timeout: int = field(default_factory=lambda: int(_env_opt("FUSION_FETCH_TIMEOUT", "25")))
    max_content_chars: int = field(default_factory=lambda: int(
        _env_opt("FUSION_MAX_CONTENT_CHARS", "8000")))
    browser_timeout: int = field(default_factory=lambda: int(
        _env_opt("FUSION_BROWSER_TIMEOUT", "25")))

    # --- Rate limiting ---
    rpm_limit: int = field(default_factory=lambda: int(_env_opt("FUSION_RPM_LIMIT", "20")))
    concurrent_fetches: int = field(default_factory=lambda: int(
        _env_opt("FUSION_CONCURRENT_FETCHES", "4")))

    # --- Cache ---
    cache_dir: str = field(default_factory=lambda: _env_opt(
        "FUSION_CACHE_DIR", "/tmp/fusion_cache"))

    # --- Auth (optional, for self-hosted) ---
    auth_token: str = field(default_factory=lambda: _env_opt("FUSION_AUTH_TOKEN", ""))

    # --- API provider presets (convenience) ---
    @classmethod
    def openrouter(cls, api_key: str, **overrides):
        """Preset for OpenRouter (openrouter.ai)."""
        return cls(
            llm_base_url="https://openrouter.ai/api/v1",
            llm_api_key=api_key,
            panel_models=overrides.pop("panel_models", [
                "qwen/qwen3-235b-a14b-instruct",
                "google/gemma-3-27b-it",
                "mistralai/mistral-small-3.1-24b-instruct",
            ]),
            judge_model=overrides.pop("judge_model", "openai/gpt-oss-120b"),
            synth_model=overrides.pop("synth_model", "deepseek/deepseek-chat-v3-0324"),
            **overrides,
        )

    @classmethod
    def siliconflow(cls, api_key: str, **overrides):
        """Preset for 硅基流动 (siliconflow.cn)."""
        return cls(
            llm_base_url="https://api.siliconflow.cn/v1",
            llm_api_key=api_key,
            panel_models=overrides.pop("panel_models", [
                "Qwen/Qwen3-235B-A14B",
                "deepseek-ai/DeepSeek-V3",
                "THUDM/GLM-4-32B-0414",
            ]),
            judge_model=overrides.pop("judge_model", "Qwen/Qwen3-235B-A14B"),
            synth_model=overrides.pop("synth_model", "deepseek-ai/DeepSeek-V3"),
            **overrides,
        )
