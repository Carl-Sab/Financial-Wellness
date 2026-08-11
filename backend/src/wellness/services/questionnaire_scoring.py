"""Signup questionnaire scoring — Blocks A-E.

Source spec: signup_questionnaire_implementation.pdf (repo root). Formulas,
item counts, and reverse-scored item numbers are copied from it, not
derived — if a number in this file looks surprising, check the PDF before
assuming it's a bug.

Blocks A-D reduce to the same computation: reverse-code the items the PDF
marks (R), using that block's reverse constant (6 for the two 1-5 scales —
Blocks A and B; 8 for the two 1-7 scales — Blocks C and D), then average
all items. Block A's PDF wording states this slightly differently
("Score = (responses 1-7 + scored_8 + response 9) / 9") but it's the
identical computation spelled out one item at a time, since item 8 is its
only reversed item — averaging 9 values where one has been reverse-coded.

Block E averages its 8 reverse-coded pairs too (range 1-5, same as the
other blocks), but unlike A-D, "reversed" isn't about item wording — it's
about which adjective is shown on which side of a semantic-differential
row. The frontend keeps polarity fixed (never alternates which side the
favourable adjective sits on), so which pairs are "reversed" is a
per-instrument constant here, not something the client reports per
submission. Per the PDF, that polarity still has to be stored alongside
every raw answer — see raw_responses_with_polarity() — so a later change to
the frontend's pair layout can never silently reinterpret an already-scored
row.

DELIBERATE DEVIATION FROM THE PDF: the PDF specifies Block E as a SUM of
the 8 scored pairs, range 8-40 ("Score = sum of the 8 scored pairs. Valid
output: 8-40."). This implementation uses the MEAN instead, range 1-5, to
match the other four blocks' scale — see migration 0009
(normative_eval_score_to_mean) for the switch and the reasoning. If you're
diffing this file against the PDF, this is the one intentional mismatch;
everything else should match exactly.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class BlockSpec:
    field: str  # item-id prefix: "ibt", "sc", "hed", "util"
    item_count: int
    reverse_items: frozenset[int]  # 1-based item numbers scored (R) in the PDF
    reverse_constant: int
    scale_min: int
    scale_max: int


# Block A - Impulse buying tendency (impulse_tendency_score)
# Rook & Fisher (1995), 9 items, 1-5 scale.
# PDF: "Reverse item 8: scored_8 = 6 - response_8."
BLOCK_A_IBT = BlockSpec(
    field="ibt",
    item_count=9,
    reverse_items=frozenset({8}),
    reverse_constant=6,
    scale_min=1,
    scale_max=5,
)

# Block B - Self-control (self_control_score)
# Tangney et al. (2004), 13 items, 1-5 scale.
# PDF: "Reverse items 2, 3, 4, 5, 7, 9, 10, 12 and 13: scored_i = 6 - response_i."
BLOCK_B_SC = BlockSpec(
    field="sc",
    item_count=13,
    reverse_items=frozenset({2, 3, 4, 5, 7, 9, 10, 12, 13}),
    reverse_constant=6,
    scale_min=1,
    scale_max=5,
)

# Block C - Hedonic motives (hedonic_score)
# Babin et al. (1994), adapted, 11 items, 1-7 scale.
# PDF: "Reverse item 11: scored_11 = 8 - response_11."
BLOCK_C_HED = BlockSpec(
    field="hed",
    item_count=11,
    reverse_items=frozenset({11}),
    reverse_constant=8,
    scale_min=1,
    scale_max=7,
)

# Block D - Utilitarian motives (utilitarian_score)
# Babin et al. (1994), adapted, 4 items, 1-7 scale.
# PDF: "Reverse items 2 and 4: scored_i = 8 - response_i."
BLOCK_D_UTIL = BlockSpec(
    field="util",
    item_count=4,
    reverse_items=frozenset({2, 4}),
    reverse_constant=8,
    scale_min=1,
    scale_max=7,
)

# Block E - Normative evaluation (normative_eval_score)
# 8 semantic-differential pairs rating the impulse-purchase scenario, 1-5
# scale each, averaged for a range of 1-5, same as the other blocks.
# PDF: "Reverse any UI pair whose favourable adjective is shown on the
# left: scored_i = 6 - response_i." The frontend displays every pair as
# (left adjective - right adjective) in this fixed order:
#   1. good - bad                 5. generous - selfish
#   2. wasteful - productive      6. sober - silly
#   3. smart - stupid             7. mature - childish
#   4. acceptable - unacceptable  8. right - wrong
# Every pair's favourable adjective is on the left except pair 2
# ("productive" is favourable and sits on the right) — so pair 2 is the
# only one of the eight that is NOT reverse-coded.
BLOCK_E_NORM = BlockSpec(
    field="norm",
    item_count=8,
    reverse_items=frozenset({1, 3, 4, 5, 6, 7, 8}),
    reverse_constant=6,
    scale_min=1,
    scale_max=5,
)

BLOCKS = (BLOCK_A_IBT, BLOCK_B_SC, BLOCK_C_HED, BLOCK_D_UTIL, BLOCK_E_NORM)


def _scored_values(spec: BlockSpec, responses: Sequence[int]) -> list[int]:
    """responses[i] is the raw 1-based-item-(i+1) answer, for
    i in range(spec.item_count) — e.g. responses[0] is item 1's answer.

    Reverse-codes every item number in spec.reverse_items as
    (spec.reverse_constant - raw), leaves every other item as-is.
    """
    if len(responses) != spec.item_count:
        raise ValueError(
            f"block {spec.field!r} expects {spec.item_count} responses, got {len(responses)}"
        )

    return [
        spec.reverse_constant - raw if (index + 1) in spec.reverse_items else raw
        for index, raw in enumerate(responses)
    ]


def score_block(spec: BlockSpec, responses: Sequence[int]) -> float:
    """Mean of the reverse-coded item values. Used by every block,
    including E — all five scores share this 1-5 (or 1-7) averaged scale."""
    values = _scored_values(spec, responses)
    return sum(values) / spec.item_count


def favourable_side(item_number: int) -> str:
    """Which side of Block E pair `item_number` (1-8) the favourable
    adjective is displayed on, per the fixed layout above."""
    return "left" if item_number in BLOCK_E_NORM.reverse_items else "right"


def raw_responses_with_polarity(payload: Mapping[str, int]) -> dict:
    """The full submitted payload, plus one extra key per Block E pair
    recording which side its favourable adjective was displayed on at
    submission time. Everything else in `payload` passes through
    unchanged. This is what actually gets stored in raw_responses — per
    the PDF, the displayed polarity has to be persisted alongside the raw
    answer for every pair, not just derivable from current frontend code
    (which could change).
    """
    raw = dict(payload)
    for item_number in range(1, BLOCK_E_NORM.item_count + 1):
        raw[f"norm_{item_number}_favourable_side"] = favourable_side(item_number)
    return raw


@dataclass(frozen=True)
class QuestionnaireScores:
    impulse_tendency_score: float
    self_control_score: float
    hedonic_score: float
    utilitarian_score: float
    normative_eval_score: float


def score_questionnaire(
    ibt_responses: Sequence[int],
    sc_responses: Sequence[int],
    hed_responses: Sequence[int],
    util_responses: Sequence[int],
    norm_responses: Sequence[int],
) -> QuestionnaireScores:
    return QuestionnaireScores(
        impulse_tendency_score=score_block(BLOCK_A_IBT, ibt_responses),
        self_control_score=score_block(BLOCK_B_SC, sc_responses),
        hedonic_score=score_block(BLOCK_C_HED, hed_responses),
        utilitarian_score=score_block(BLOCK_D_UTIL, util_responses),
        normative_eval_score=score_block(BLOCK_E_NORM, norm_responses),
    )
