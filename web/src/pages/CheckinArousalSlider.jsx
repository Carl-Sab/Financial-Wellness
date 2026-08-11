import { QUICK_AROUSAL_LEVELS } from "./checkinItems";

/**
 * Quick mode's single slider — five integer stops (-2..+2), all five
 * labeled underneath (unlike CheckinSlider's three anchors), since this
 * replaces four separate questions with one and the whole scale needs to
 * read at a glance.
 */
export default function CheckinArousalSlider({ id, question, value, onChange }) {
  const current = QUICK_AROUSAL_LEVELS.find((level) => level.value === value);

  return (
    <div className="checkin-slider">
      <div className="checkin-slider__head">
        <label htmlFor={id} className="checkin-slider__question">
          {question}
        </label>
        <span className="checkin-slider__value" aria-hidden="true">
          {value > 0 ? `+${value}` : value}
        </span>
      </div>

      <input
        id={id}
        type="range"
        min={-2}
        max={2}
        step={1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="checkin-slider__input"
        aria-label={question}
        aria-valuetext={current?.label ?? String(value)}
      />

      <div className="checkin-arousal__ticks" aria-hidden="true">
        {QUICK_AROUSAL_LEVELS.map((level) => (
          <span
            key={level.value}
            className={`checkin-arousal__tick ${level.value === value ? "checkin-arousal__tick--active" : ""}`}
          >
            {level.label}
          </span>
        ))}
      </div>
    </div>
  );
}
