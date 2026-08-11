import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import QuestionnaireLikertItem from "./QuestionnaireLikertItem";
import QuestionnaireSemanticDifferentialItem from "./QuestionnaireSemanticDifferentialItem";
import { BLOCKS, NORMATIVE_EVAL } from "./questionnaireItems";
import "./Questionnaire.css";

const TOTAL_STEPS = BLOCKS.length + 1;
const NORMATIVE_STEP_INDEX = BLOCKS.length; // the 5th, final step

// Fisher-Yates. Each block's order is rolled once per mount (see the
// useState lazy initializer below) and never touched again — that's what
// keeps it stable across re-renders within the session without needing to
// persist it anywhere. Block E is deliberately excluded: the PDF fixes its
// pair order and polarity, and shuffling evaluative pairs about one shared
// scenario doesn't carry the same "avoid a response pattern" rationale the
// trait-statement blocks have.
function shuffledIndices(count) {
  const indices = Array.from({ length: count }, (_, i) => i);
  for (let i = indices.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [indices[i], indices[j]] = [indices[j], indices[i]];
  }
  return indices;
}

function fieldKey(block, originalIndex) {
  return `${block.id}_${originalIndex + 1}`;
}

function normFieldKey(originalIndex) {
  return `norm_${originalIndex + 1}`;
}

export default function Questionnaire() {
  const { questionnaireComplete, refreshQuestionnaireStatus } = useAuth();
  const navigate = useNavigate();

  const [blockIndex, setBlockIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitStatus, setSubmitStatus] = useState("idle"); // idle | loading | error
  const [itemOrders] = useState(() => BLOCKS.map((block) => shuffledIndices(block.items.length)));
  const headingRef = useRef(null);
  const lastFocusedBlockRef = useRef(blockIndex);
  // Same double-submit guard as Signup/Login: a ref, because React batches
  // setSubmitStatus, so two synchronous clicks could both still read
  // "not loading" before either update commits.
  const isSubmittingRef = useRef(false);

  // Already done this (e.g. revisited the URL directly) — nothing to fill
  // out, so don't show the form.
  useEffect(() => {
    if (questionnaireComplete === true) {
      navigate("/home", { replace: true });
    }
  }, [questionnaireComplete, navigate]);

  // Same pattern as Signup's per-step focus management: move focus to the
  // new screen's heading on a real block change, comparing against the
  // last block this effect acted on (not a one-shot flag) so it survives
  // React StrictMode's deliberate double-invocation of mount effects
  // without stealing focus on first load.
  useEffect(() => {
    if (lastFocusedBlockRef.current === blockIndex) return;
    lastFocusedBlockRef.current = blockIndex;
    headingRef.current?.focus();
  }, [blockIndex]);

  if (questionnaireComplete !== false) {
    // Still loading (null) or already complete (redirecting above) —
    // render nothing rather than flash the form.
    return null;
  }

  const isNormativeStep = blockIndex === NORMATIVE_STEP_INDEX;
  const block = isNormativeStep ? null : BLOCKS[blockIndex];
  const order = isNormativeStep ? null : itemOrders[blockIndex];
  const isFirstBlock = blockIndex === 0;
  const isLastStep = blockIndex === TOTAL_STEPS - 1;

  const isStepComplete = isNormativeStep
    ? NORMATIVE_EVAL.pairs.every((_, originalIndex) => answers[normFieldKey(originalIndex)] != null)
    : block.items.every((_, originalIndex) => answers[fieldKey(block, originalIndex)] != null);

  function handleAnswer(originalIndex, value) {
    setAnswers((a) => ({ ...a, [fieldKey(block, originalIndex)]: value }));
  }

  function handleNormAnswer(originalIndex, value) {
    setAnswers((a) => ({ ...a, [normFieldKey(originalIndex)]: value }));
  }

  function handleBack() {
    setBlockIndex((i) => i - 1);
  }

  async function submit() {
    if (isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    setSubmitStatus("loading");

    const payload = {};
    for (const b of BLOCKS) {
      b.items.forEach((_, originalIndex) => {
        payload[fieldKey(b, originalIndex)] = answers[fieldKey(b, originalIndex)];
      });
    }
    NORMATIVE_EVAL.pairs.forEach((_, originalIndex) => {
      payload[normFieldKey(originalIndex)] = answers[normFieldKey(originalIndex)];
    });

    try {
      const response = await apiFetch("/api/v1/questionnaire", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      // 409 means it's already completed — e.g. a second tab finished it
      // first. Either way the state the user wants (a completed
      // questionnaire) is now true, so treat it the same as success.
      if (response.status === 201 || response.status === 409) {
        await refreshQuestionnaireStatus();
        navigate("/onboarding/budget", { replace: true });
        return;
      }

      setSubmitStatus("error");
    } catch {
      setSubmitStatus("error");
    } finally {
      isSubmittingRef.current = false;
    }
  }

  function handleContinue(event) {
    event.preventDefault();
    if (!isStepComplete) return;
    if (isLastStep) {
      submit();
    } else {
      setBlockIndex((i) => i + 1);
    }
  }

  const isLoading = submitStatus === "loading";

  return (
    <div className="questionnaire">
      <a href="#questionnaire-heading" className="skip-link">
        Skip to questions
      </a>

      <div
        className="questionnaire__progress"
        role="progressbar"
        aria-valuenow={blockIndex + 1}
        aria-valuemin={1}
        aria-valuemax={TOTAL_STEPS}
        aria-label={`Step ${blockIndex + 1} of ${TOTAL_STEPS}`}
      >
        <div
          className="questionnaire__progress-fill"
          style={{ width: `${((blockIndex + 1) / TOTAL_STEPS) * 100}%` }}
        />
      </div>

      <div className="questionnaire__content">
        <form onSubmit={handleContinue} noValidate>
          {!isFirstBlock && (
            <button
              type="button"
              className="questionnaire__back"
              onClick={handleBack}
              aria-label="Back to previous step"
            >
              &larr; Back
            </button>
          )}

          <h1
            id="questionnaire-heading"
            className="questionnaire__title"
            ref={headingRef}
            tabIndex={-1}
          >
            Step {blockIndex + 1} of {TOTAL_STEPS}
          </h1>

          {isFirstBlock && (
            <p className="questionnaire__intro">
              A few questions about how you shop. Takes about five minutes — answer honestly,
              there are no right answers.
            </p>
          )}

          {isNormativeStep ? (
            <>
              <div className="questionnaire__scenario">
                <p>{NORMATIVE_EVAL.scenario}</p>
              </div>

              <div className="questionnaire__items">
                {NORMATIVE_EVAL.pairs.map((pair, originalIndex) => (
                  <QuestionnaireSemanticDifferentialItem
                    key={originalIndex}
                    leftLabel={pair.left}
                    rightLabel={pair.right}
                    value={answers[normFieldKey(originalIndex)] ?? null}
                    onChange={(value) => handleNormAnswer(originalIndex, value)}
                  />
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="questionnaire__anchors">
                <span>
                  {block.scaleMin} = {block.anchorMin}
                </span>
                <span>
                  {block.scaleMax} = {block.anchorMax}
                </span>
              </div>

              <div className="questionnaire__items">
                {order.map((originalIndex) => (
                  <QuestionnaireLikertItem
                    key={originalIndex}
                    statement={block.items[originalIndex]}
                    scaleMin={block.scaleMin}
                    scaleMax={block.scaleMax}
                    anchorMin={block.anchorMin}
                    anchorMax={block.anchorMax}
                    value={answers[fieldKey(block, originalIndex)] ?? null}
                    onChange={(value) => handleAnswer(originalIndex, value)}
                  />
                ))}
              </div>
            </>
          )}

          {submitStatus === "error" && (
            <p className="questionnaire__form-error" role="alert">
              Couldn&rsquo;t reach the server. Nothing you answered was lost.{" "}
              <button type="button" className="questionnaire__retry" onClick={submit}>
                Try again
              </button>
            </p>
          )}

          <button
            type="submit"
            className="btn btn--primary questionnaire__submit"
            disabled={!isStepComplete || isLoading}
          >
            {isLastStep ? (isLoading ? "Submitting…" : "Submit") : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
