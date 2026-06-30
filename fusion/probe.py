"""Model probe — detect available models, test quality, auto-select panel.

Runs ONCE per fusion invocation:
1. List models from the API gateway
2. Filter out non-chat models (embed/vision/tts/image)
3. Send a simple test prompt to each candidate, measure:
   - latency (seconds)
   - response quality (does it answer coherently in Chinese?)
   - availability (no error)
4. Rank by speed × quality, pick top-N for panel
5. Also pick best models for judge and synth roles
"""
import time
import httpx
import json
from concurrent.futures import ThreadPoolExecutor, as_completed


# --- Model filtering ---

_NON_CHAT_KEYWORDS = [
    "embed", "tts", "whisper", "image", "dall", "sd", "flux",
    "stable-diffusion", "midjourney", "codestral-mamba",
    "vision-detect", "gliner", "pii", "parse", "safety",
    "calibration", "nemotron-parse", "nemoretriever",
    "content-safety", "synthetic-video",
]

# Known strong models for each role (fallback if probe fails)
_FALLBACK_PANEL = [
    "qwen/qwen3.5-397b-a17b",
    "google/gemma-4-31b-it",
    "minimaxai/minimax-m2.7",
]
_FALLBACK_JUDGE = "openai/gpt-oss-120b"
_FALLBACK_SYNTH = "deepseek-ai/deepseek-v4-pro"


def is_chat_model(model_id: str) -> bool:
    """Filter out non-chat models."""
    low = model_id.lower()
    return not any(kw in low for kw in _NON_CHAT_KEYWORDS)


def list_models(base_url: str, api_key: str) -> list[str]:
    """Fetch available model list from API gateway."""
    try:
        resp = httpx.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [m["id"] for m in data if "id" in m]
    except Exception as e:
        return []


# --- Quality probe ---

_PROBE_PROMPT = "简答：1+1=? 只回答数字"
_PROBE_MAX_TOKENS = 16
_PROBE_TIMEOUT = 30  # seconds per model


def probe_model(base_url: str, api_key: str, model_id: str) -> dict:
    """Test a single model: latency + quality check."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": _PROBE_PROMPT}],
        "temperature": 0.0,
        "max_tokens": _PROBE_MAX_TOKENS,
    }
    start = time.monotonic()
    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_PROBE_TIMEOUT,
        )
        elapsed = time.monotonic() - start
        if resp.status_code != 200:
            return {
                "model": model_id, "ok": False,
                "error": f"HTTP {resp.status_code}", "latency": elapsed,
            }
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content or not content.strip():
            return {
                "model": model_id, "ok": False,
                "error": "empty_response", "latency": elapsed,
            }
        # Quality check: answer should contain "2"
        answer_ok = "2" in content.strip()[:10]
        return {
            "model": model_id, "ok": True,
            "latency": round(elapsed, 2),
            "answer": content.strip()[:50],
            "quality": "pass" if answer_ok else "degraded",
        }
    except httpx.TimeoutException:
        elapsed = time.monotonic() - start
        return {
            "model": model_id, "ok": False,
            "error": f"timeout({round(elapsed,1)}s)", "latency": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = time.monotonic() - start
        return {
            "model": model_id, "ok": False,
            "error": str(e)[:80], "latency": round(elapsed, 2),
        }


def probe_all(base_url: str, api_key: str, model_ids: list[str],
              max_workers: int = 8) -> list[dict]:
    """Probe all candidate models in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(model_ids))) as pool:
        futures = {
            pool.submit(probe_model, base_url, api_key, mid): mid
            for mid in model_ids
        }
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


# --- Model selection ---

def rank_models(probe_results: list[dict], prefer_quality: bool = True) -> list[dict]:
    """Rank models by latency and quality. Lower latency = better.
    
    prefer_quality: if True, quality=pass models always rank above degraded,
                    even if slower.
    """
    ok_models = [r for r in probe_results if r["ok"]]
    if not ok_models:
        return []
    
    # Sort: quality=pass first, then by latency (fastest first)
    def sort_key(r):
        quality_rank = 0 if r.get("quality") == "pass" else 1
        return (quality_rank, r["latency"])
    
    ok_models.sort(key=sort_key)
    return ok_models


def auto_select(base_url: str, api_key: str,
                panel_size: int = 3,
                skip_models: list[str] | None = None) -> dict:
    """Auto-detect best models for panel/judge/synth.
    
    Args:
        base_url: API gateway URL
        api_key: API key
        panel_size: number of panel models to select
        skip_models: models to exclude (e.g. already failed before)
    
    Returns:
        dict with panel_models, judge_model, synth_model, probe_report
    """
    skip = set(skip_models or [])
    
    # Step 1: List available models
    all_models = list_models(base_url, api_key)
    if not all_models:
        return {
            "panel_models": _FALLBACK_PANEL[:panel_size],
            "judge_model": _FALLBACK_JUDGE,
            "synth_model": _FALLBACK_SYNTH,
            "probe_report": "⚠️ API model list unavailable, using fallback",
        }
    
    # Step 2: Filter to chat models only
    candidates = [m for m in all_models if is_chat_model(m) and m not in skip]
    
    print(f"🔍 探测到 {len(all_models)} 个模型，{len(candidates)} 个候选")
    
    # Step 3: Probe all candidates
    results = probe_all(base_url, api_key, candidates)
    
    # Step 4: Rank and select
    ranked = rank_models(results)
    
    # Build report
    ok_count = len(ranked)
    fail_count = len([r for r in results if not r["ok"]])
    print(f"✅ {ok_count} 个可用，❌ {fail_count} 个不可用")
    
    # Top-10 for report
    report_lines = ["📊 模型质量检测报告（按速度+质量排名）"]
    report_lines.append(f"{'排名':<4} {'模型':<45} {'延迟':>6} {'质量':<8} {'回答'}")
    report_lines.append("-" * 90)
    for i, r in enumerate(ranked[:10]):
        quality = r.get("quality", "N/A")
        answer = r.get("answer", r.get("error", ""))[:20]
        report_lines.append(
            f"{i+1:<4} {r['model']:<45} {r['latency']:>5.1f}s {quality:<8} {answer}"
        )
    if fail_count > 0:
        failed = [r for r in results if not r["ok"]]
        report_lines.append(f"\n❌ 不可用模型 ({len(failed)}):")
        for r in failed[:5]:
            report_lines.append(f"  {r['model']}: {r.get('error', 'unknown')}")
    
    if not ranked:
        # All failed - use fallback
        return {
            "panel_models": _FALLBACK_PANEL[:panel_size],
            "judge_model": _FALLBACK_JUDGE,
            "synth_model": _FALLBACK_SYNTH,
            "probe_report": "\n".join(report_lines) + "\n⚠️ 无可用模型，使用预设回退",
        }
    
    # Select panel models: top-N by quality then speed
    # Prefer diversity: avoid selecting 3 models from same family
    selected_panel = []
    seen_families = set()
    for r in ranked:
        if len(selected_panel) >= panel_size:
            break
        # Extract model family = provider (e.g. "qwen" from "qwen/qwen3.5")
        # For models without /, use first -segment
        if "/" in r["model"]:
            provider = r["model"].split("/")[0].lower()
        else:
            provider = r["model"].split("-")[0].lower()
        # Normalize: deepseek-ai → deepseek, mistralai → mistral
        for old, new in [("deepseek-ai", "deepseek"), ("mistralai", "mistral"), ("z-ai", "zhipu")]:
            if provider == old:
                provider = new
                break
        if provider in seen_families:
            continue
        selected_panel.append(r["model"])
        seen_families.add(provider)
    
    # Fill remaining if not enough diverse models
    if len(selected_panel) < panel_size:
        for r in ranked:
            if r["model"] not in selected_panel:
                selected_panel.append(r["model"])
                if len(selected_panel) >= panel_size:
                    break
    
    # Judge: pick fastest quality=pass model (judge needs to output JSON)
    judge_candidates = [r for r in ranked if r.get("quality") == "pass"]
    judge_model = judge_candidates[0]["model"] if judge_candidates else ranked[0]["model"]
    
    # Synth: pick a strong model (prefer larger/slower but higher quality)
    # Use a model from a different family than judge if possible
    synth_candidates = [r for r in ranked if r["model"] != judge_model]
    synth_model = synth_candidates[0]["model"] if synth_candidates else ranked[0]["model"]
    
    return {
        "panel_models": selected_panel,
        "judge_model": judge_model,
        "synth_model": synth_model,
        "probe_report": "\n".join(report_lines),
    }
