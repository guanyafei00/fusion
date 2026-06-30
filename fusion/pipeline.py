"""Fusion pipeline — Panel→Judge→Synth multi-model consensus."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import Config
from .security import RateLimiter
from .llm import chat, chat_json
from .fetchers import fetch_url, fetch_urls
from .probe import auto_select


# --- Step 1: Search & Fetch ---

PANEL_SYSTEM = """你是一个研究助手。根据提供的参考资料，用中文回答问题。
只使用提供的资料，不要编造事实。如果资料不足，明确说明。"""

JUDGE_SYSTEM = """你是评审专家。评估多份回答的质量、事实准确性和一致性。

输出JSON格式：
{
  "scores": {"model_a": 8, "model_b": 7, ...},
  "best": "model_a",
  "fact_conflicts": ["冲突1: ..."],
  "recommendation": "综合建议..."
}"""

SYNTH_SYSTEM = """你是综合分析专家。根据所有收集的资料和评审结果，写一份完整、准确、有深度的最终回答。
要求：
- 以中文回答
- 引用具体来源
- 标注不确定的内容
- 如果资料间有矛盾，说明各方的观点"""


def step_fetch(query: str, urls: list[str] | None, cfg: Config) -> dict[str, str]:
    """Step 1: Fetch content from provided URLs."""
    if not urls:
        return {}
    return fetch_urls(urls, cfg)


# --- Step 2: Panel (multi-model parallel answer) ---

def step_panel(query: str, sources: dict[str, str], cfg: Config) -> dict[str, str]:
    """Step 2: Get answers from multiple models in parallel."""
    source_text = "\n\n---\n\n".join(
        f"[来源: {url}]\n{content[:2000]}" for url, content in sources.items()
    )
    user_msg = f"问题：{query}\n\n参考资料：\n{source_text}" if source_text else f"问题：{query}"
    messages = [{"role": "system", "content": PANEL_SYSTEM}, {"role": "user", "content": user_msg}]

    results = {}
    limiter = RateLimiter(cfg.rpm_limit)

    with ThreadPoolExecutor(max_workers=len(cfg.panel_models)) as pool:
        futures = {}
        for model in cfg.panel_models:
            limiter.wait()
            futures[model] = pool.submit(chat, cfg, model, messages, temperature=0.3)

        for model, fut in futures.items():
            try:
                result = fut.result()
                results[model] = result if result else "[模型返回空内容]"
            except Exception as e:
                results[model] = f"[ERROR] {e}"

    return results


# --- Step 3: Judge (evaluate and score panel answers) ---

def step_judge(query: str, panel_answers: dict[str, str], cfg: Config) -> dict:
    """Step 3: Judge evaluates all panel answers."""
    answers_text = "\n\n---\n\n".join(
        f"## {model}:\n{answer}" for model, answer in panel_answers.items()
    )
    user_msg = (
        f"原问题：{query}\n\n"
        f"以下是多个模型的回答，请评估：\n\n{answers_text}"
    )
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    limiter = RateLimiter(cfg.rpm_limit)
    limiter.wait()
    result = chat_json(cfg, cfg.judge_model, messages, temperature=0.0, retries=1)
    # Graceful fallback if judge fails
    if isinstance(result, dict) and "error" in result:
        # Build a simple equal-score judge result so pipeline can continue
        fallback_scores = {m: 5 for m in panel_answers}
        return {
            "scores": fallback_scores,
            "best": list(panel_answers.keys())[0] if panel_answers else "",
            "fact_conflicts": [],
            "recommendation": f"Judge failed ({result.get('error','unknown')}), using equal scores as fallback.",
        }
    return result


# --- Step 4: Synth (synthesize final answer) ---

def step_synth(query: str, sources: dict[str, str],
               panel_answers: dict[str, str], judge: dict, cfg: Config) -> str:
    """Step 4: Synthesize final answer using judge's evaluation."""
    answers_summary = "\n\n".join(
        f"### {model}:\n{(answer or '[空]')[:1000]}" for model, answer in panel_answers.items()
    )
    judge_text = json.dumps(judge, ensure_ascii=False, indent=2)
    source_text = "\n".join(
        f"- [{url}] {content[:500]}" for url, content in sources.items()
    )

    user_msg = (
        f"原问题：{query}\n\n"
        f"来源资料：\n{source_text}\n\n"
        f"各模型回答摘要：\n{answers_summary}\n\n"
        f"评审结果：\n{judge_text}\n\n"
        f"请综合以上信息，写出最终的完整回答。"
    )
    messages = [
        {"role": "system", "content": SYNTH_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    limiter = RateLimiter(cfg.rpm_limit)
    limiter.wait()
    return chat(cfg, cfg.synth_model, messages, temperature=0.2, max_tokens=4096)


# --- Full pipeline ---

def run(query: str, urls: list[str] | None = None, cfg: Config | None = None,
        stability: int = 1, auto_probe: bool | None = None) -> str:
    """Run full Fusion pipeline: Probe→Fetch→Panel→Judge→Synth.

    Args:
        query: The question to answer.
        urls: Optional list of URLs to fetch as source material.
        cfg: Configuration (loaded from env vars if not provided).
        stability: Number of rounds for stability test (1 = single run).
        auto_probe: If True, auto-detect model quality before running.
                    If None, uses cfg.auto_probe (default: True).

    Returns:
        Final synthesized answer string.
    """
    if cfg is None:
        cfg = Config()

    # Step 0: Auto-probe model quality (runs once per invocation)
    should_probe = auto_probe if auto_probe is not None else cfg.auto_probe
    if should_probe:
        print("\n🔍 Step 0: 模型质量检测...")
        selection = auto_select(
            cfg.llm_base_url, cfg.llm_api_key,
            panel_size=cfg.probe_panel_size,
        )
        print(selection.get("probe_report", ""))
        
        # Override config with probed models
        config_modified = False
        if selection["panel_models"] != cfg.panel_models:
            print(f"  📋 Panel: {cfg.panel_models} → {selection['panel_models']}")
            cfg.panel_models = selection["panel_models"]
            config_modified = True
        if selection["judge_model"] != cfg.judge_model:
            print(f"  ⚖️  Judge: {cfg.judge_model} → {selection['judge_model']}")
            cfg.judge_model = selection["judge_model"]
            config_modified = True
        if selection["synth_model"] != cfg.synth_model:
            print(f"  🔮 Synth: {cfg.synth_model} → {selection['synth_model']}")
            cfg.synth_model = selection["synth_model"]
            config_modified = True
        if not config_modified:
            print("  ✅ 当前配置已是最优，无需调整")

    results = []
    for round_num in range(stability):
        if stability > 1:
            print(f"\n=== Stability round {round_num + 1}/{stability} ===")

        # Step 1: Fetch
        sources = step_fetch(query, urls, cfg)

        # Step 2: Panel
        panel_answers = step_panel(query, sources, cfg)

        # Step 3: Judge
        judge_result = step_judge(query, panel_answers, cfg)

        # Step 4: Synth
        final = step_synth(query, sources, panel_answers, judge_result, cfg)
        results.append(final)

    if stability > 1 and len(set(results)) == 1:
        print("\n✅ Stability PASSED — all rounds identical")
    elif stability > 1:
        print(f"\n⚠️ Stability WARNING — {len(set(results))} distinct outputs across {stability} rounds")
        print("Using last round result.")

    return results[-1]
