"""Correlate mood states with spending and plot the result.

For each transaction, finds the most recent mood reading at or before the
purchase (per user), then reports the Pearson correlation between spend
amount and each of the three mood scores (joyful, stressed, sad) — plus a
scatter plot per dimension and a bar chart ranking them by strength.

Deliberately does not assume any particular database schema (the actual
tables are someone else's to design) — data is supplied either as CSV files
or as SQL queries run against the existing DB connection, and only needs to
have these columns:

    transactions: user_id, occurred_at, amount
    moods:        user_id, ts, joyful_score, stressed_score, sad_score

Usage:
    uv run python scripts/mood_spend_correlation.py \\
        --transactions-csv transactions.csv --moods-csv moods.csv

    uv run python scripts/mood_spend_correlation.py \\
        --transactions-sql "SELECT user_id, occurred_at, amount FROM ..." \\
        --moods-sql "SELECT user_id, ts, joyful_score, stressed_score, sad_score FROM ..."
"""

import argparse
import asyncio
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from wellness.db import get_session

MOOD_COLUMNS = ["joyful_score", "stressed_score", "sad_score"]
REQUIRED_TX_COLUMNS = {"user_id", "occurred_at", "amount"}
REQUIRED_MOOD_COLUMNS = {"user_id", "ts", *MOOD_COLUMNS}


async def load_sql(query: str) -> pd.DataFrame:
    session_gen = get_session()
    session = await anext(session_gen)
    try:
        result = await session.execute(text(query))
        return pd.DataFrame(result.mappings().all())
    finally:
        await session_gen.aclose()


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{label} data is missing required column(s): {', '.join(sorted(missing))}")


def build_dataframe(tx_df: pd.DataFrame, mood_df: pd.DataFrame) -> pd.DataFrame:
    """Join each transaction to the most recent mood reading at/before it, per user."""
    empty_columns = ["user_id", "occurred_at", "amount", *MOOD_COLUMNS]
    if tx_df.empty or mood_df.empty:
        return pd.DataFrame(columns=empty_columns)

    _require_columns(tx_df, REQUIRED_TX_COLUMNS, "transactions")
    _require_columns(mood_df, REQUIRED_MOOD_COLUMNS, "mood")

    tx_df = tx_df.copy()
    tx_df["user_id"] = tx_df["user_id"].astype(str)
    tx_df["occurred_at"] = pd.to_datetime(tx_df["occurred_at"], utc=True)
    tx_df = tx_df.sort_values("occurred_at")

    mood_df = mood_df.copy()
    mood_df["user_id"] = mood_df["user_id"].astype(str)
    mood_df["ts"] = pd.to_datetime(mood_df["ts"], utc=True)
    mood_df = mood_df.sort_values("ts")

    merged = pd.merge_asof(
        tx_df,
        mood_df,
        left_on="occurred_at",
        right_on="ts",
        by="user_id",
        direction="backward",
    )
    return merged.dropna(subset=MOOD_COLUMNS)


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson r between spend amount and each mood score, ranked by |r|."""
    rows = []
    for mood in MOOD_COLUMNS:
        if df[mood].nunique() < 2 or df["amount"].nunique() < 2:
            r, p = float("nan"), float("nan")
        else:
            r, p = stats.pearsonr(df[mood], df["amount"])
        rows.append({"mood": mood.removesuffix("_score"), "pearson_r": r, "p_value": p, "n": len(df)})
    return pd.DataFrame(rows).sort_values("pearson_r", key=lambda s: s.abs(), ascending=False)


def plot_results(df: pd.DataFrame, correlations: pd.DataFrame, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, len(MOOD_COLUMNS), figsize=(15, 4.5))
    for ax, mood in zip(axes, MOOD_COLUMNS, strict=True):
        label = mood.removesuffix("_score")
        ax.scatter(df[mood], df["amount"], alpha=0.5, s=18)
        if df[mood].nunique() > 1:
            slope, intercept = np.polyfit(df[mood], df["amount"], 1)
            xs = np.linspace(df[mood].min(), df[mood].max(), 50)
            ax.plot(xs, slope * xs + intercept, color="crimson", linewidth=2)
        row = correlations.loc[correlations["mood"] == label].iloc[0]
        ax.set_title(f"{label} vs spend\nr={row.pearson_r:.2f}, p={row.p_value:.3f}")
        ax.set_xlabel(f"{label}_score (0-100)")
        ax.set_ylabel("amount")
    fig.tight_layout()
    scatter_path = output_dir / "mood_vs_spend_scatter.png"
    fig.savefig(scatter_path, dpi=150)
    plt.close(fig)

    fig2, ax2 = plt.subplots(figsize=(6, 4))
    colors = ["#2e7d32" if r >= 0 else "#c62828" for r in correlations["pearson_r"]]
    ax2.barh(correlations["mood"], correlations["pearson_r"], color=colors)
    ax2.set_xlabel("Pearson r (spend amount vs mood score)")
    ax2.set_xlim(-1, 1)
    ax2.axvline(0, color="black", linewidth=0.8)
    fig2.tight_layout()
    bar_path = output_dir / "mood_spend_correlation_strength.png"
    fig2.savefig(bar_path, dpi=150)
    plt.close(fig2)

    return [scatter_path, bar_path]


def main() -> None:
    parser = argparse.ArgumentParser(description="Correlate mood states with spending")

    tx_source = parser.add_mutually_exclusive_group(required=True)
    tx_source.add_argument("--transactions-csv", type=Path, help="CSV: user_id, occurred_at, amount")
    tx_source.add_argument("--transactions-sql", type=str, help="Query returning: user_id, occurred_at, amount")

    mood_source = parser.add_mutually_exclusive_group(required=True)
    mood_source.add_argument(
        "--moods-csv", type=Path, help="CSV: user_id, ts, joyful_score, stressed_score, sad_score"
    )
    mood_source.add_argument(
        "--moods-sql", type=str, help="Query returning: user_id, ts, joyful_score, stressed_score, sad_score"
    )

    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "output")
    args = parser.parse_args()

    tx_df = load_csv(args.transactions_csv) if args.transactions_csv else asyncio.run(
        load_sql(args.transactions_sql)
    )
    mood_df = load_csv(args.moods_csv) if args.moods_csv else asyncio.run(load_sql(args.moods_sql))

    if tx_df.empty or mood_df.empty:
        print("No transactions or mood rows found — nothing to correlate.")
        return

    df = build_dataframe(tx_df, mood_df)
    if df.empty:
        print("No transaction could be matched to a preceding mood reading.")
        return

    correlations = compute_correlations(df)
    paths = plot_results(df, correlations, args.output_dir)

    print(f"Matched {len(df)} transactions to mood readings.\n")
    print(correlations.to_string(index=False))

    strongest = correlations.iloc[0]
    direction = "more" if strongest.pearson_r > 0 else "less"
    print(
        f"\nStrongest correlation: '{strongest.mood}' "
        f"(r={strongest.pearson_r:.2f}, p={strongest.p_value:.3f}) — "
        f"spend tends to be {direction} as {strongest.mood} score rises."
    )
    print("\nSaved plots:")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
