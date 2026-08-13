import { AROUSAL_VALUES } from "./checkinItems";

export default function ArousalSliderField({ item, value, onChange }) {
  const id = `checkin-arousal-${item.field}`;
  const selectedLabel = item.scaleLabels[AROUSAL_VALUES.indexOf(value)];

  return (
    <div className="checkin-arousal">
      <div className="checkin-arousal__heading">
        <label htmlFor={id} className="checkin-arousal__label">
          {item.label}
        </label>
        <output htmlFor={id} className="checkin-arousal__value">
          {selectedLabel}
        </output>
      </div>
      <p className="checkin-arousal__prompt">{item.prompt}</p>
      <input
        id={id}
        className="checkin-arousal__slider"
        type="range"
        min="-2"
        max="2"
        step="1"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-valuetext={selectedLabel}
      />
      <div className="checkin-arousal__ticks" aria-hidden="true">
        {AROUSAL_VALUES.map((tick, index) => (
          <span key={tick}>{item.scaleLabels[index]}</span>
        ))}
      </div>
    </div>
  );
}
