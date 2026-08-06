"""AI write-up for the mood/excess-spend correlation results.

Uses the Pydantic AI Gateway (same key/pattern as the game-store project):
gateway_provider("anthropic", api_key=...) -> AnthropicModel -> Agent. The
agent is given the exact correlation numbers as text (so it never has to
read precise values off a chart) plus the plotted PNGs as image content (so
it can describe shape: clusters, outliers, linearity).
"""

from pathlib import Path

import pandas as pd
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.gateway import gateway_provider

from wellness.config import get_settings

SYSTEM_PROMPT = (
    "You are a data analyst writing a short report for a wellness app team about "
    "whether users' mood/arousal at the moment of a purchase correlates with how "
    "much more they spent than their own usual amount in that category ('excess "
    "spend'). You are given the exact Pearson correlation statistics as text and "
    "the plotted charts as images. Use the text for any numbers you state — never "
    "estimate a value from an image. Use the images only to describe visual shape "
    "(clusters, outliers, how linear the trend looks).\n\n"
    "The happiness and sadness scores are the same underlying valence reading "
    "with the sign flipped, so their correlations with spend are mirror images "
    "of each other by construction (r_sadness = -r_happiness) — say this "
    "plainly and don't present them as two independent findings. Arousal is a "
    "separate, independent signal.\n\n"
    "State clearly which correlation(s) are statistically significant (p < 0.05) "
    "and which aren't, and say plainly when a sample size is too small to trust. "
    "Never claim causation from a correlation. End with a short, plain-language "
    "takeaway for someone with no statistics background. Write in markdown."
)


async def generate_report(correlations: pd.DataFrame, image_paths: list[Path]) -> str:
    settings = get_settings()
    provider = gateway_provider("anthropic", api_key=settings.gateway_api_key)
    model = AnthropicModel(settings.report_model, provider=provider)
    agent = Agent(model, system_prompt=SYSTEM_PROMPT)

    stats_text = correlations.to_string(index=False)
    content: list[str | BinaryContent] = [f"Correlation statistics:\n\n{stats_text}"]
    for path in image_paths:
        content.append(BinaryContent(data=path.read_bytes(), media_type="image/png"))

    result = await agent.run(content)
    return result.output
