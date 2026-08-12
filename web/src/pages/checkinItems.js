// CATEGORY and VALENCE below still match pretransaction_questionnaire_compact.pdf
// (repo root) verbatim. The physiological READINGS section does not: the PDF
// specified self-reported "-2..+2 compared with usual" sliders with no backend
// anywhere that accepts them. This app links to the OTHER, already-built and
// tested backend piece instead — the real z-score arousal-scoring pipeline in
// wellness/services/arousal.py, which needs actual physiological readings
// (bpm/ms/µS/%/°C), not a self-reported feeling. Field names and range limits
// below match wellness/schemas/checkins.py's CheckinCreate and the DB's own
// CHECK constraints exactly.

// Category codes and labels match categories.code/categories.label in the
// DB (schema.sql) exactly — this is also PDF section 1's store_category
// answer set. Order here is the task's specified tile order, not the
// PDF table's (which is sorted by marketing score M for exposition).
export const CATEGORIES = [
  { code: "groceries", label: "Groceries" },
  { code: "clothing", label: "Clothing" },
  { code: "restaurant", label: "Restaurant" },
  { code: "electronics", label: "Electronics" },
  { code: "mall", label: "Mall" },
  { code: "online", label: "Online" },
  { code: "other", label: "Other" },
];

export const CATEGORY_QUESTION = "Where are you planning to shop?";

// PDF section 2. valence (DB enum, checkins.valence) and valence_z (the
// PDF's -2..+2 score) are the same underlying choice — the backend enum
// string and the PDF's numeric score are just two representations of one
// answer, not two questions.
export const VALENCE_QUESTION = "How pleasant or unpleasant do you feel right now?";

export const VALENCE_LEVELS = [
  { valence: "very_unpleasant", valence_z: -2, label: "Very negative / unpleasant" },
  { valence: "unpleasant", valence_z: -1, label: "Negative" },
  { valence: "neutral", valence_z: 0, label: "Neutral" },
  { valence: "pleasant", valence_z: 1, label: "Positive" },
  { valence: "very_pleasant", valence_z: 2, label: "Very positive / pleasant" },
];

// Real physiological readings the arousal-scoring pipeline actually scores
// (wellness/services/arousal.py's _METRIC_SPEC) — field names match
// CheckinCreate exactly, min/max match the DB's own CHECK constraints.
// `quick: true` = shown in Quick mode; every field shows in Detailed mode.
// All are individually optional — the backend only requires at least one
// non-null reading total (checkins.at_least_one_reading), which is exactly
// the rule the submit button below enforces, not a stricter invented one.
export const READINGS_QUESTION = "What are your readings right now?";
export const READINGS_HINT =
  "Fill in what you know — even one reading is enough. Check a smartwatch or fitness tracker, or count your pulse for 15 seconds and multiply by 4 for heart rate.";

export const READINGS = [
  { field: "heart_rate", label: "Heart rate", unit: "bpm", min: 30, max: 220, step: 1, quick: true },
  { field: "hrv_ms", label: "Heart rate variability", unit: "ms", min: 1, max: 300, step: 1, quick: false },
  {
    field: "eda_microsiemens",
    label: "Skin conductance (EDA)",
    unit: "µS",
    min: 0,
    max: 100,
    step: 0.1,
    quick: false,
  },
  { field: "spo2_percent", label: "Blood oxygen (SpO2)", unit: "%", min: 70, max: 100, step: 1, quick: false },
  {
    field: "skin_temp_c",
    label: "Skin temperature",
    unit: "°C",
    min: 30,
    max: 43,
    step: 0.1,
    quick: false,
  },
];
