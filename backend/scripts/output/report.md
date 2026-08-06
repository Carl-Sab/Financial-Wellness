# Mood, Arousal, and Excess Spend: What the Data Shows

## Summary of correlations

| Signal | Pearson r | p-value | n | Significant? |
|---|---|---|---|---|
| Arousal | 0.881 | 6.4 × 10⁻⁵⁰ | 150 | **Yes** |
| Happiness | 0.047 | 0.567 | 150 | No |
| Sadness | -0.047 | 0.567 | 150 | No |

## A note on happiness and sadness

Happiness and sadness here are the same underlying valence measurement with the sign flipped — so it's mathematically guaranteed that r_sadness = -r_happiness. These are not two separate findings; they're one weak, non-significant result reported twice with opposite signs. In both cases, p = 0.567, far above the 0.05 threshold, so we cannot conclude that valence (feeling happy vs. sad) has any real relationship with excess spend in this data.

## Arousal is the standout signal

Arousal shows a strong, statistically significant positive correlation with excess spend (r = 0.88, p < 0.001). The scatter plot backs this up visually: points cluster tightly around an upward-sloping line, with no obvious outlier clusters or bends — the relationship looks convincingly linear across the full range of arousal scores. Higher arousal at the moment of purchase lines up with people spending more above their usual category average.

By contrast, the happiness and sadness scatter plots show essentially flat clouds of points at each discrete score level — no visible upward or downward trend, consistent with their near-zero, non-significant correlations.

## Sample size check

With n = 150 for all three measures, the sample is reasonably sized — this is *not* a "too small to trust" situation. The lack of significance for happiness/sadness is a genuine null result here, not just a symptom of insufficient data.

## Caveat

Correlation is not causation. This data cannot tell us whether high arousal *causes* people to overspend, whether overspending *causes* a spike in arousal (e.g., excitement from the purchase itself), or whether some other factor drives both. All we can say is that the two tend to move together.

## Plain-language takeaway

When people are in a more excited, activated state (high arousal), they tend to spend noticeably more than their usual habit in that category — and this pattern is strong and reliable in the data. Whether someone is in a good mood or a bad mood, on the other hand, doesn't seem to matter much for overspending. So if the app wants to flag risky spending moments, arousal level looks like a far more useful signal than happiness or sadness.