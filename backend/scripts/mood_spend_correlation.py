"""CLI wrapper around wellness.analysis.mood_spend / wellness.analysis.report.

See wellness/analysis/mood_spend.py for the actual logic (shared with the
GET /api/v1/analysis/mood-spend-correlation endpoint).

Usage:
    uv run python scripts/mood_spend_correlation.py [--user-id UUID]
    uv run python scripts/mood_spend_correlation.py --skip-ai-report
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from wellness.analysis.mood_spend import compute_correlations, compute_derived_columns, load_data, plot_results
from wellness.db import get_session


async def _load_data_standalone(user_id: uuid.UUID | None):
    session_gen = get_session()
    session = await anext(session_gen)
    try:
        return await load_data(session, user_id)
    finally:
        await session_gen.aclose()


def main() -> None:
    # Windows consoles default to cp1252, which can't encode characters the
    # AI report or the "—" in messages below may contain.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Correlate mood/arousal with excess spending")
    parser.add_argument("--user-id", type=uuid.UUID, default=None, help="Limit to one user")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "output")
    parser.add_argument("--skip-ai-report", action="store_true", help="Only produce plots, skip the AI write-up")
    args = parser.parse_args()

    raw_df = asyncio.run(_load_data_standalone(args.user_id))
    if raw_df.empty:
        print("No transactions with a linked checkin found — nothing to correlate.")
        return

    df = compute_derived_columns(raw_df)
    correlations = compute_correlations(df)
    paths = plot_results(df, correlations, args.output_dir)

    print(f"Analysed {len(df)} transactions with a linked checkin.\n")
    print(correlations.to_string(index=False))

    strongest = correlations.iloc[0]
    direction = "more" if strongest.pearson_r > 0 else "less"
    print(
        f"\nStrongest correlation: '{strongest.mood}' "
        f"(r={strongest.pearson_r:.2f}, p={strongest.p_value:.3f}, n={strongest.n:.0f}) — "
        f"excess spend tends to be {direction} as {strongest.mood} score rises."
    )
    print("\nSaved plots:")
    for path in paths:
        print(f"  {path}")

    if args.skip_ai_report:
        return

    from wellness.config import get_settings

    if not get_settings().gateway_api_key:
        print(
            "\nSkipping AI report: API_KEY_SECRET_FROM_EURISKO is not set in .env "
            "(pass --skip-ai-report to silence this)."
        )
        return

    from wellness.analysis.report import generate_report

    report = asyncio.run(generate_report(correlations, paths))
    report_path = args.output_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nAI report saved to: {report_path}\n")
    print(report)


if __name__ == "__main__":
    main()
