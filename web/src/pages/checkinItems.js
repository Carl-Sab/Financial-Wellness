// These choices match pretransaction_questionnaire_compact.pdf. Arousal uses
// five discrete normalized slider stops, not raw wearable units.

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

export const AROUSAL_QUESTION = "How does your body feel compared with usual?";
export const AROUSAL_VALUES = [-2, -1, 0, 1, 2];

export const QUICK_AROUSAL = {
  field: "arousal_z",
  label: "Overall arousal",
  prompt: "Choose your overall arousal level right now.",
  scaleLabels: ["Much lower", "Lower", "Usual", "Higher", "Much higher"],
};

export const DETAILED_AROUSAL = [
  {
    field: "perceived_heart_rate",
    label: "Heart rate",
    prompt: "Compared with usual, how fast is your heart beating?",
    scaleLabels: ["Much slower", "Slower", "Usual", "Faster", "Much faster"],
  },
  {
    field: "perceived_heartbeat_steadiness",
    label: "Heartbeat steadiness",
    prompt: "Compared with usual, how steady does your heartbeat feel?",
    scaleLabels: [
      "Much less steady",
      "Less steady",
      "Usual",
      "More steady",
      "Much steadier",
    ],
  },
  {
    field: "perceived_sweating",
    label: "Sweating / clamminess",
    prompt: "Compared with usual, how sweaty or clammy do you feel?",
    scaleLabels: ["Much drier", "Drier", "Usual", "Sweatier", "Much sweatier"],
  },
  {
    field: "perceived_respiration",
    label: "Breathing",
    prompt: "Compared with usual, how does your breathing feel?",
    scaleLabels: [
      "Much slower",
      "Slower",
      "Usual",
      "Faster",
      "Much faster",
    ],
  },
  {
    field: "perceived_temperature_difference",
    label: "Skin temperature difference",
    prompt: "How much does your skin temperature feel different than usual?",
    scaleLabels: [
      "Much more stable",
      "More stable",
      "Usual",
      "More different",
      "Much more different",
    ],
  },
];

export const QUICK_AROUSAL_HINT =
  "Set one overall value. This value goes directly to prediction and bypasses the arousal model.";
export const DETAILED_AROUSAL_HINT =
  "Set all five values separately. Each slider snaps to -2, -1, 0, 1, or 2.";
