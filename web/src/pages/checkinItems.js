// Question wording, response scales, and ordering are copied verbatim from
// pretransaction_questionnaire_compact.pdf (repo root) — do not paraphrase.
// "Show the screens in this exact order" (PDF, p.1) — CATEGORY, then
// VALENCE, then the four perceived-state sliders in the order below.
// Section 3 (heart rate) is deliberately not represented here: the PDF is
// explicit that "No question is shown" for it — z_hr is computed
// backend-side from the wearable feed, never typed by the respondent.

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

// PDF sections 4-7. field matches the PDF's "Frontend field" name exactly.
// left/right are that question's own "Direction" wording verbatim; every
// one of the four uses "0.0 = normal" for the center.
export const SLIDERS = [
  {
    field: "perceived_hrv",
    question: "How steady and calm does your heartbeat feel compared with usual?",
    leftLabel: "Much less steady / more irregular",
    rightLabel: "Much steadier / calmer",
  },
  {
    field: "perceived_eda",
    question: "How sweaty or clammy do you feel compared with usual?",
    leftLabel: "Much drier",
    rightLabel: "Much sweatier / clammier",
  },
  {
    field: "perceived_respiration",
    question: "How fast or shallow is your breathing compared with usual?",
    leftLabel: "Much slower / deeper",
    rightLabel: "Much faster / shallower",
  },
  {
    field: "perceived_skin_temperature",
    question: "How warm or flushed does your skin feel compared with usual?",
    leftLabel: "Much colder",
    rightLabel: "Much warmer / more flushed",
  },
];

// Quick mode: not from the PDF — a single-slider alternative to the four
// sliders above, for the common case of checking in before every purchase.
// Same -2..+2 scale and integer-only ("no decimals" — five stops, not the
// 41-value continuous sliders above).
export const QUICK_AROUSAL_QUESTION = "How low or high is your arousal right now?";

export const QUICK_AROUSAL_LEVELS = [
  { value: -2, label: "Very low arousal" },
  { value: -1, label: "Low arousal" },
  { value: 0, label: "Neutral" },
  { value: 1, label: "High arousal" },
  { value: 2, label: "Very high arousal" },
];
