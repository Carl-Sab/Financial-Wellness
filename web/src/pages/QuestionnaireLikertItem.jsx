/**
 * One item: its statement, then a row of number buttons — not a dropdown
 * or slider, so the whole scale is visible at a glance and it's fast to
 * tap on mobile. role="radiogroup"/"radio" + aria-checked convey "pick
 * exactly one" to assistive tech the same way a native radio group would;
 * the endpoint buttons also carry the anchor label so that context isn't
 * lost to a screen reader user who tabs straight to a button without
 * reading the shared legend above the list.
 */
export default function QuestionnaireLikertItem({
  statement,
  scaleMin,
  scaleMax,
  anchorMin,
  anchorMax,
  value,
  onChange,
}) {
  const values = [];
  for (let v = scaleMin; v <= scaleMax; v += 1) values.push(v);

  return (
    <div className="likert">
      <p className="likert__statement">{statement}</p>
      <div className="likert__scale" role="radiogroup" aria-label={statement}>
        {values.map((v) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={value === v}
            aria-label={v === scaleMin ? `${v} — ${anchorMin}` : v === scaleMax ? `${v} — ${anchorMax}` : String(v)}
            className={`likert__option ${value === v ? "likert__option--selected" : ""}`}
            onClick={() => onChange(v)}
          >
            {v}
          </button>
        ))}
      </div>
    </div>
  );
}
