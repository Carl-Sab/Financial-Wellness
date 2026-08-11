/**
 * One Block E pair: adjective, five unlabeled position buttons, adjective.
 * Same role="radiogroup"/"radio" + aria-checked pattern as
 * QuestionnaireLikertItem, but the "anchors" are per-row (the two
 * adjectives) rather than shared across the whole screen, so they're
 * spoken via aria-label on the two end buttons instead of a shared legend.
 * value 1 sits nearest leftLabel, value 5 nearest rightLabel — the backend
 * reverses whichever pairs have their favourable adjective on the left, so
 * that placement (not the number) is what "favourable" tracks.
 */
export default function QuestionnaireSemanticDifferentialItem({
  leftLabel,
  rightLabel,
  value,
  onChange,
}) {
  const values = [1, 2, 3, 4, 5];

  return (
    <div className="sd-row">
      <span className="sd-row__label sd-row__label--left">{leftLabel}</span>
      <div
        className="sd-row__scale"
        role="radiogroup"
        aria-label={`${leftLabel} to ${rightLabel}`}
      >
        {values.map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={value === v}
            aria-label={v === 1 ? `1 — ${leftLabel}` : v === 5 ? `5 — ${rightLabel}` : String(v)}
            className={`sd-row__option ${value === v ? "sd-row__option--selected" : ""}`}
            onClick={() => onChange(v)}
          />
        ))}
      </div>
      <span className="sd-row__label sd-row__label--right">{rightLabel}</span>
    </div>
  );
}
