// Item wording is copied verbatim from signup_questionnaire_implementation.pdf
// (repo root) — do not paraphrase or "clean up" punctuation here; the
// backend's raw_responses/scoring assumes these exact 37 items in this
// exact order. (R) markers from the PDF are the backend's reverse-coding
// notes, not respondent-facing text — see backend/src/wellness/services/
// questionnaire_scoring.py for where those live; they're deliberately not
// duplicated here.
//
// items[i] is item (i + 1) — e.g. ibt.items[7] is IBT item 8. Submission
// always keys by that fixed original index (`${id}_${i + 1}`); only the
// on-screen *display* order is shuffled — see Questionnaire.jsx.
//
export const BLOCKS = [
  {
    id: "ibt",
    scaleMin: 1,
    scaleMax: 5,
    anchorMin: "Strongly disagree",
    anchorMax: "Strongly agree",
    items: [
      `I often buy things spontaneously.`,
      `"Just do it" describes the way I buy things.`,
      `I often buy things without thinking.`,
      `"I see it, I buy it" describes me.`,
      `"Buy now, think about it later" describes me.`,
      `Sometimes I feel like buying things on the spur of the moment.`,
      `I buy things according to how I feel at the moment.`,
      `I carefully plan most of my purchases.`,
      `Sometimes I am a bit reckless about what I buy.`,
    ],
  },
  {
    id: "sc",
    scaleMin: 1,
    scaleMax: 5,
    anchorMin: "Not at all like me",
    anchorMax: "Very much like me",
    items: [
      `I am good at resisting temptation.`,
      `I have a hard time breaking bad habits.`,
      `I am lazy.`,
      `I say inappropriate things.`,
      `I do certain things that are bad for me, if they are fun.`,
      `I refuse things that are bad for me.`,
      `I wish I had more self-discipline.`,
      `People would say that I have iron self-discipline.`,
      `Pleasure and fun sometimes keep me from getting work done.`,
      `I have trouble concentrating.`,
      `I am able to work effectively toward long-term goals.`,
      `Sometimes I can't stop myself from doing something, even if I know it is wrong.`,
      `I often act without thinking through all the alternatives.`,
    ],
  },
  {
    id: "hed",
    scaleMin: 1,
    scaleMax: 7,
    anchorMin: "Strongly disagree",
    anchorMax: "Strongly agree",
    items: [
      `Shopping is usually a joy for me.`,
      `I often keep shopping not because I have to, but because I want to.`,
      `Shopping usually feels like an escape for me.`,
      `Compared with other things I could do, time spent shopping is genuinely enjoyable.`,
      `I enjoy being immersed in exciting new products.`,
      `I enjoy shopping for its own sake, not just for what I buy.`,
      `I have a good time shopping because I can act on the spur of the moment.`,
      `When I shop, I feel the excitement of the hunt.`,
      `When I shop, I can forget my problems for a while.`,
      `I feel a sense of adventure when I shop.`,
      `Shopping is usually not a very nice way to spend time.`,
    ],
  },
  {
    id: "util",
    scaleMin: 1,
    scaleMax: 7,
    anchorMin: "Strongly disagree",
    anchorMax: "Strongly agree",
    items: [
      `I usually accomplish just what I wanted to on a shopping trip.`,
      `I often can't buy what I really need.`,
      `When I shop, I usually find just the item(s) I was looking for.`,
      `I'm often disappointed because I have to go to another store to complete my shopping.`,
    ],
  },
];

// Block E - Normative evaluation. Unlike Blocks A-D above, the PDF doesn't
// give this one as a directly-quotable respondent-facing paragraph — its
// "Scenario:" line is written as instructions to the implementer ("Ask the
// respondent to imagine she buys both the socks and the unplanned
// sweater"). The text below keeps every substantive fact and word from
// that line exactly ($25, necessities, two days before payday, socks, $75
// sweater, sale, buys both the socks and the unplanned sweater) and only
// turns the implementer instruction into direct narration.
//
// Pair order and left/right placement are fixed exactly as the PDF lists
// them (good-bad, wasteful-productive, ... right-wrong) and are never
// shuffled or alternated — see Questionnaire.jsx and the backend's
// BLOCK_E_NORM for why. pairs[i] is item (i + 1); submission keys by that
// fixed index the same way the other four blocks do (norm_${i + 1}).
export const NORMATIVE_EVAL = {
  id: "norm",
  scenario: `Mary has $25 left for necessities two days before payday. She needs socks. While she's out, she sees a $75 sweater on sale. Imagine Mary buys both the socks and the unplanned sweater.`,
  pairs: [
    { left: "Good", right: "Bad" },
    { left: "Wasteful", right: "Productive" },
    { left: "Smart", right: "Stupid" },
    { left: "Acceptable", right: "Unacceptable" },
    { left: "Generous", right: "Selfish" },
    { left: "Sober", right: "Silly" },
    { left: "Mature", right: "Childish" },
    { left: "Right", right: "Wrong" },
  ],
};
