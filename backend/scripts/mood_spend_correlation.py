"""Correlate mood/arousal with excess spending, plot it, and get an AI report.

Data model (see backend/schema.sql): a transaction may reference the checkin
that preceded it (transactions.checkin_id -> checkins.id). Only transactions
with a linked checkin carry mood data, so this only analyses that subset —
transactions with no checkin are excluded, not treated as "no correlation".

Mood axes:
  - happiness: checkins.valence mapped to a numeric scale (very_unpleasant=-2
    ... very_pleasant=+2). Higher = happier.
  - sadness: the same valence axis, sign-flipped (higher = sadder). Because
    both derive from the single bipolar `valence` field, their correlations
    with spending are mirror images by construction: r_sadness = -r_happiness.
    That's not a bug to fix — it's what a single bipolar scale means — and
    the AI report is told to call it out explicitly rather than treat them as
    two independent findings.
  - arousal: arousal_state.score (0-1), joined via the same checkin_id. Not
    every checkin has a scored arousal_state row, so this axis can have a
    smaller n than the mood axes.

Excess spend:
  excess_amount = transaction.amount - that user's own average transaction
  amount in the same category. Mirrors how arousal itself is already scored
  in this app: relative to the user's own baseline, not an absolute cutoff.

Usage:
    uv run python scripts/mood_spend_correlation.py [--user-id UUID]
    uv run python scripts/mood_spend_correlation.py --skip-ai-report
"""

import argparse
import asyncio
import enum
import sys
import uuid
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import select

from wellness.db import get_session
from wellness.models.arousal import ArousalState
from wellness.models.checkins import Checkin
from wellness.models.transactions import Transaction

VALENCE_TO_NUMERIC = {
    "very_unpleasant": -2,
    "unpleasant": -1,
    "neutral": 0,
    "pleasant": 1,
    "very_pleasant": 2,
}

MOOD_COLUMNS = ["happiness_score", "arousal_score", "sadness_score"]
MOOD_RANGES = {"happiness_score": (-2, 2), "arousal_score": (0, 1), "sadness_score": (-2, 2)}


async def load_data(user_id: uuid.UUID | None) -> pd.DataFrame:
    """One row per transaction that has a linked checkin, with its valence and
    (if scored) arousal reading attached.
    """
    session_gen = get_session()
    session = await anext(session_gen)
    try:
        stmt = (
            select(
                Transaction.user_id,
                Transaction.id.label("transaction_id"),
                Transaction.amount,
                Transaction.category_code,
                Transaction.occurred_at,
                Checkin.valence,
                ArousalState.score.label("arousal_score"),
            )
            .join(Checkin, Transaction.checkin_id == Checkin.id)
            .outerjoin(ArousalState, ArousalState.checkin_id == Checkin.id)
            .where(Transaction.checkin_id.is_not(None))
        )
        if user_id is not None:
            stmt = stmt.where(Transaction.user_id == user_id)
        result = await session.execute(stmt)
        return pd.DataFrame(result.mappings().all())
    finally:
        await session_gen.aclose()


def compute_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add happiness/sadness/excess_amount columns to raw transaction+mood rows."""
    columns = ["user_id", "transaction_id", "amount", "category_code", "occurred_at", "valence", *MOOD_COLUMNS, "excess_amount"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    df = df.copy()
    df["amount"] = df["amount"].astype(float)
    df["valence"] = df["valence"].apply(lambda v: v.value if isinstance(v, enum.Enum) else v)
    df["happiness_score"] = df["valence"].map(VALENCE_TO_NUMERIC)
    df["sadness_score"] = -df["happiness_score"]
    df["excess_amount"] = df["amount"] - df.groupby(["user_id", "category_code"])["amount"].transform("mean")
    return df


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson r between excess spend and each mood axis, ranked by |r|.

    Each axis is dropna'd independently since arousal_score is frequently
    missing (not every checkin gets a scored arousal_state row) while
    happiness/sadness (derived from valence) are not.
    """
    rows = []
    for mood in MOOD_COLUMNS:
        sub = df[[mood, "excess_amount"]].dropna()
        if sub[mood].nunique() < 2 or sub["excess_amount"].nunique() < 2:
            r, p = float("nan"), float("nan")
        else:
            r, p = stats.pearsonr(sub[mood], sub["excess_amount"])
        rows.append({"mood": mood.removesuffix("_score"), "pearson_r": r, "p_value": p, "n": len(sub)})
    return pd.DataFrame(rows).sort_values("pearson_r", key=lambda s: s.abs(), ascending=False)


def plot_results(df: pd.DataFrame, correlations: pd.DataFrame, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, len(MOOD_COLUMNS), figsize=(15, 4.5))
    for ax, mood in zip(axes, MOOD_COLUMNS, strict=True):
        label = mood.removesuffix("_score")
        sub = df[[mood, "excess_amount"]].dropna()
        ax.scatter(sub[mood], sub["excess_amount"], alpha=0.5, s=18)
        if sub[mood].nunique() > 1:
            slope, intercept = np.polyfit(sub[mood], sub["excess_amount"], 1)
            xs = np.linspace(*MOOD_RANGES[mood], 50)
            ax.plot(xs, slope * xs + intercept, color="crimson", linewidth=2)
        row = correlations.loc[correlations["mood"] == label].iloc[0]
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set_title(f"{label} vs excess spend\nr={row.pearson_r:.2f}, p={row.p_value:.3f}, n={row.n:.0f}")
        ax.set_xlabel(f"{label}_score")
        ax.set_ylabel("excess spend (vs. own category average)")
    fig.tight_layout()
    scatter_path = output_dir / "mood_vs_excess_spend_scatter.png"
    fig.savefig(scatter_path, dpi=150)
    plt.close(fig)

    fig2, ax2 = plt.subplots(figsize=(6, 4))
    colors = ["#2e7d32" if r >= 0 else "#c62828" for r in correlations["pearson_r"]]
    ax2.barh(correlations["mood"], correlations["pearson_r"], color=colors)
    ax2.set_xlabel("Pearson r (excess spend vs. mood/arousal score)")
    ax2.set_xlim(-1, 1)
    ax2.axvline(0, color="black", linewidth=0.8)
    fig2.tight_layout()
    bar_path = output_dir / "mood_excess_spend_correlation_strength.png"
    fig2.savefig(bar_path, dpi=150)
    plt.close(fig2)

    return [scatter_path, bar_path]


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

    raw_df = asyncio.run(load_data(args.user_id))
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

    from ai_report import generate_report

    report = asyncio.run(generate_report(correlations, paths))
    report_path = args.output_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nAI report saved to: {report_path}\n")
    print(report)


if __name__ == "__main__":
    main()
