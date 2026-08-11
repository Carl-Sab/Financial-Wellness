/**
 * One perceived-state slider (heartbeat steadiness / sweating / breathing /
 * skin warmth) — 41 values, -2.0 to +2.0 in steps of 0.1, per
 * pretransaction_questionnaire_compact.pdf. leftLabel/rightLabel are that
 * question's own direction wording verbatim (each of the four sliders
 * means something different at -2/+2, e.g. "much drier" vs. "much less
 * steady" — there's no single generic end-label safe to reuse across all
 * four), and 0.0 is always "normal" per the PDF's own wording for every
 * slider.
 */
export default function CheckinSlider({ id, question, leftLabel, rightLabel, value, onChange }) {
  const display = value > 0 ? `+${value.toFixed(1)}` : value.toFixed(1);

  return (
    <div className="checkin-slider">
      <div className="checkin-slider__head">
        <label htmlFor={id} className="checkin-slider__question">
          {question}
        </label>
        <span className="checkin-slider__value" aria-hidden="true">
          {display}
        </span>
      </div>

      <input
        id={id}
        type="range"
        min={-2}
        max={2}
        step={0.1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="checkin-slider__input"
        aria-label={question}
        aria-valuetext={`${display} — ${value === 0 ? "normal" : value < 0 ? leftLabel : rightLabel}`}
      />

      <div className="checkin-slider__anchors">
        <span>{leftLabel}</span>
        <span className="checkin-slider__anchor-center">Normal</span>
        <span>{rightLabel}</span>
      </div>
    </div>
  );
}
