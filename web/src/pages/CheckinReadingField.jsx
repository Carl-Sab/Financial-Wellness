/**
 * One physiological reading (heart rate, HRV, EDA, SpO2, skin temp) — a
 * typed exact number with its unit, not a drag slider: unlike a -2..+2
 * "compared with usual" feeling, a real reading is a fact the respondent
 * looks up (wearable, pulse count) and types in. min/max/step come from
 * the reading's entry in checkinItems.js's READINGS, which mirror the
 * DB's own CHECK constraints (wellness/models/checkins.py).
 */
export default function CheckinReadingField({ reading, value, onChange, onBlur }) {
  const id = `checkin-reading-${reading.field}`;

  return (
    <div className="field checkin-reading">
      <label htmlFor={id} className="field__label">
        {reading.label}
      </label>
      <div className="checkin-reading__wrap">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          min={reading.min}
          max={reading.max}
          step={reading.step}
          autoComplete="off"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          className="field__control checkin-reading__input"
          placeholder={`${reading.min}–${reading.max}`}
        />
        <span className="checkin-reading__unit" aria-hidden="true">
          {reading.unit}
        </span>
      </div>
    </div>
  );
}
