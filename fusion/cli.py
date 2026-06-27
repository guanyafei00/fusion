"""Fusion CLI — command-line interface."""
import click
from .config import Config
from .pipeline import run


@click.command()
@click.argument("query", required=True)
@click.option("--url", "-u", multiple=True, help="Source URLs to fetch (can specify multiple)")
@click.option("--stability", "-s", default=1, type=int, help="Stability test rounds (default: 1)")
@click.option("--panel-models", default=None, help="Comma-separated panel model IDs")
@click.option("--judge-model", default=None, help="Judge model ID")
@click.option("--synth-model", default=None, help="Synth model ID")
@click.option("--preset", type=click.Choice(["openrouter", "siliconflow"]), default=None,
              help="API provider preset")
@click.option("--api-key", default=None, envvar="FUSION_LLM_API_KEY",
              help="LLM API key (or set FUSION_LLM_API_KEY)")
@click.option("--verbose", "-v", is_flag=True, help="Print intermediate steps")
def main(query, url, stability, panel_models, judge_model, synth_model,
         preset, api_key, verbose):
    """Fusion: Multi-model consensus pipeline.

    QUERY is the question to answer.

    Example:
        fusion "量子计算最新进展" -u https://arxiv.org/abs/2401.12345
        fusion "对比React和Vue" --stability 3
    """
    # Build config from env or preset
    if preset == "openrouter":
        cfg = Config.openrouter(api_key or "")
    elif preset == "siliconflow":
        cfg = Config.siliconflow(api_key or "")
    else:
        cfg = Config()

    # Override models if specified
    if panel_models:
        cfg.panel_models = panel_models.split(",")
    if judge_model:
        cfg.judge_model = judge_model
    if synth_model:
        cfg.synth_model = synth_model

    urls = list(url) if url else None

    if verbose:
        click.echo(f"📂 Panel models: {cfg.panel_models}")
        click.echo(f"⚖️  Judge: {cfg.judge_model}")
        click.echo(f"🔮 Synth: {cfg.synth_model}")
        click.echo(f"🔗 URLs: {urls}")
        click.echo(f"🔄 Stability: {stability}")
        click.echo("---")

    result = run(query, urls=urls, cfg=cfg, stability=stability)
    click.echo(result)


if __name__ == "__main__":
    main()
