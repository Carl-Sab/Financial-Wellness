import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useDisplayCurrency } from "../hooks/useDisplayCurrency";
import { apiFetch } from "../lib/api";
import { convertAmount, currencySymbol, formatMoney } from "../lib/currency";
import "./Statistics.css";

const VIEW_LABELS = {
  weekly: "Week",
  monthly: "Month",
  yearly: "Year",
};

const VIEW_TITLES = {
  weekly: "Daily spending",
  monthly: "Weekly spending",
  yearly: "Monthly spending",
};

const CATEGORY_VIEW_LABELS = {
  daily: "Day",
  weekly: "Week",
  monthly: "Month",
  yearly: "Year",
};

const PERIOD_NOUNS = {
  daily: "day",
  weekly: "week",
  monthly: "month",
  yearly: "year",
};

function toISODate(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseDate(value) {
  return new Date(`${value}T00:00:00`);
}

function formatDate(value, options) {
  return parseDate(value).toLocaleDateString(undefined, options);
}

function periodLabel(view, start, end) {
  if (view === "daily") {
    return formatDate(start, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  }
  if (view === "yearly") return String(parseDate(start).getFullYear());
  if (view === "monthly") {
    return formatDate(start, { month: "long", year: "numeric" });
  }
  const startLabel = formatDate(start, { month: "short", day: "numeric" });
  const endLabel = formatDate(end, { month: "short", day: "numeric", year: "numeric" });
  return `${startLabel} – ${endLabel}`;
}

function shiftAnchor(anchor, view, direction) {
  const next = parseDate(anchor);
  if (view === "daily") next.setDate(next.getDate() + direction);
  if (view === "weekly") next.setDate(next.getDate() + direction * 7);
  if (view === "monthly") next.setMonth(next.getMonth() + direction, 1);
  if (view === "yearly") next.setFullYear(next.getFullYear() + direction, 0, 1);
  return toISODate(next);
}

function formatBudgetPercentage(normalized) {
  if (normalized == null) return "—";
  const percentage = normalized * 50;
  return `${percentage.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: percentage >= 1000 ? 0 : 1,
  })}%`;
}

function formatCompactMoney(amount, currencyCode) {
  const formatted = Number(amount).toLocaleString("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  });
  return `${currencySymbol(currencyCode)}${formatted}`;
}

async function fetchStatistics(view, anchor, categoryView, categoryAnchor) {
  const response = await apiFetch(
    `/api/v1/analysis/statistics?view=${view}&anchor=${anchor}&category_view=${categoryView}&category_anchor=${categoryAnchor}`
  );
  if (!response.ok) throw new Error("Failed to load statistics");
  return response.json();
}

async function fetchCorrelationSummary(view, anchor) {
  const response = await apiFetch("/api/v1/analysis/correlation-summary", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ view, anchor }),
  });
  if (!response.ok) throw new Error("Failed to load correlation summary");
  return response.json();
}

function CurrencyToggle({ value, onChange }) {
  return (
    <div className="statistics__currency-toggle" role="radiogroup" aria-label="Display currency">
      {["LBP", "USD"].map((code) => (
        <button
          key={code}
          type="button"
          role="radio"
          aria-checked={value === code}
          className={`statistics__currency-option ${
            value === code ? "statistics__currency-option--selected" : ""
          }`}
          onClick={() => onChange(code)}
        >
          {code === "USD" ? "$" : "L.L."}
        </button>
      ))}
    </div>
  );
}

function PeriodControls({ view, anchor, data, onViewChange, onAnchorChange }) {
  return (
    <div className="review-controls">
      <div className="review-controls__views" role="tablist" aria-label="Review period">
        {Object.entries(VIEW_LABELS).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={view === key}
            className={`review-controls__view ${
              view === key ? "review-controls__view--selected" : ""
            }`}
            onClick={() => onViewChange(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="review-controls__navigator">
        <button
          type="button"
          className="review-controls__arrow"
          aria-label={`Previous ${view.slice(0, -2)}`}
          onClick={() => onAnchorChange(shiftAnchor(anchor, view, -1))}
        >
          ←
        </button>
        <strong className="review-controls__period">
          {data ? periodLabel(view, data.range_start, data.range_end) : "Loading…"}
        </strong>
        <button
          type="button"
          className="review-controls__arrow"
          aria-label={`Next ${view.slice(0, -2)}`}
          onClick={() => onAnchorChange(shiftAnchor(anchor, view, 1))}
        >
          →
        </button>
      </div>
    </div>
  );
}

function ReviewChart({ buckets, currency, displayCurrency }) {
  const levels = buckets.map((bucket) => bucket.normalized_spending ?? 0);
  const maxLevel = Math.max(2.5, Math.ceil(Math.max(...levels, 0) * 2) / 2);
  const budgetLinePosition = (2 / maxLevel) * 100;

  return (
    <div className="review-chart" aria-label="Spending compared with allocated budget">
      <div className="review-chart__plot">
        <span className="review-chart__axis-top">{formatBudgetPercentage(maxLevel)}</span>
        <span
          className="review-chart__axis-budget"
          style={{ bottom: `calc(${budgetLinePosition}% - 0.45rem)` }}
        >
          100%
        </span>
        <span className="review-chart__axis-zero">0%</span>
        <div
          className="review-chart__budget-line"
          style={{ bottom: `${budgetLinePosition}%` }}
        >
          <span>Budget</span>
        </div>
        <div className="review-chart__columns">
          {buckets.map((bucket) => {
            const level = bucket.normalized_spending ?? 0;
            const title = `${bucket.label}: ${formatMoney(
              convertAmount(bucket.spent_amount, currency, displayCurrency),
              displayCurrency
            )} spent of ${formatMoney(
              convertAmount(bucket.budget_amount, currency, displayCurrency),
              displayCurrency
            )} allocated`;
            return (
              <div className="review-chart__column" key={bucket.period_start} title={title}>
                <span className="review-chart__value">
                  <strong>{formatBudgetPercentage(bucket.normalized_spending)}</strong>
                  <small>
                    {formatCompactMoney(
                      convertAmount(bucket.spent_amount, currency, displayCurrency),
                      displayCurrency
                    )}
                  </small>
                </span>
                <div
                  className={`review-chart__bar ${
                    bucket.overspent ? "review-chart__bar--over" : ""
                  }`}
                  style={{ height: `${(level / maxLevel) * 100}%` }}
                />
                <span className="review-chart__label">{bucket.label}</span>
              </div>
            );
          })}
        </div>
      </div>
      <p className="review-chart__caption">
        <strong>100%</strong> is the allocated budget. Each bar shows budget used and the amount spent.
      </p>
    </div>
  );
}

function MoodScatter({ title, metric, points, xMin, xMax, ticks, color, yMax, currency, displayCurrency }) {
  const chartPoints = points.filter((point) => point[metric] != null);
  const width = 420;
  const height = 250;
  const margin = { top: 18, right: 18, bottom: 42, left: 48 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const x = (value) => margin.left + ((value - xMin) / (xMax - xMin)) * plotWidth;
  const y = (value) => margin.top + plotHeight - (value / yMax) * plotHeight;
  const yTicks = Array.from(new Set([0, 2, yMax])).sort((a, b) => a - b);

  return (
    <article className="mood-scatter">
      <div className="mood-scatter__heading">
        <div>
          <h3>{title}</h3>
          <p>One amount-weighted point per day</p>
        </div>
        <span className="mood-scatter__swatch" style={{ background: color }} />
      </div>
      {chartPoints.length === 0 ? (
        <p className="statistics__empty mood-scatter__empty">No linked check-ins in this period.</p>
      ) : (
        <svg
          className="mood-scatter__svg"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${title} scatter plot. The budget boundary is at 100 percent.`}
        >
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={margin.left}
                x2={width - margin.right}
                y1={y(tick)}
                y2={y(tick)}
                className={tick === 2 ? "mood-scatter__budget-line" : "mood-scatter__grid"}
              />
              <text x={margin.left - 9} y={y(tick) + 4} textAnchor="end" className="mood-scatter__tick">
                {formatBudgetPercentage(tick)}
              </text>
            </g>
          ))}
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={x(tick)}
                x2={x(tick)}
                y1={margin.top}
                y2={height - margin.bottom}
                className={tick === 0 && xMin < 0 ? "mood-scatter__zero-line" : "mood-scatter__grid"}
              />
              <text x={x(tick)} y={height - margin.bottom + 19} textAnchor="middle" className="mood-scatter__tick">
                {tick}
              </text>
            </g>
          ))}
          <text
            x={14}
            y={margin.top + plotHeight / 2}
            textAnchor="middle"
            className="mood-scatter__axis-label"
            transform={`rotate(-90 14 ${margin.top + plotHeight / 2})`}
          >
            Spending level
          </text>
          <text x={margin.left + plotWidth / 2} y={height - 4} textAnchor="middle" className="mood-scatter__axis-label">
            {title.replace(" and spending", "")}
          </text>
          {chartPoints.map((point) => {
            const rawX = point[metric];
            const plottedX = Math.min(xMax, Math.max(xMin, rawX));
            const pointX = x(plottedX);
            const pointY = y(Math.min(yMax, point.normalized_spending));
            const showLabel = chartPoints.length <= 7;
            const labelOnLeft = pointX > width - 130;
            return (
              <g key={point.day}>
                <circle
                  cx={pointX}
                  cy={pointY}
                  r="5.5"
                  fill={color}
                  className="mood-scatter__point"
                >
                  <title>
                    {`${formatDate(point.day, { month: "short", day: "numeric" })}: ${rawX.toFixed(
                      2
                    )}, ${formatBudgetPercentage(point.normalized_spending)} · ${formatMoney(
                      convertAmount(point.spent_amount, currency, displayCurrency),
                      displayCurrency
                    )}`}
                  </title>
                </circle>
                {showLabel && (
                  <text
                    x={pointX + (labelOnLeft ? -9 : 9)}
                    y={pointY - 8}
                    textAnchor={labelOnLeft ? "end" : "start"}
                    className="mood-scatter__point-label"
                  >
                    {formatBudgetPercentage(point.normalized_spending)} · {formatCompactMoney(
                      convertAmount(point.spent_amount, currency, displayCurrency),
                      displayCurrency
                    )}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      )}
      {chartPoints.length > 0 && (
        <p className="mood-scatter__caption">Y-axis: budget used. Hover a point for its full amount.</p>
      )}
    </article>
  );
}

function CorrelationSummary({ status, result, onRetry }) {
  const items = result
    ? [
        {
          key: "positive_mood",
          label: "Positive mood",
          text: result.summary.positive_mood,
        },
        {
          key: "negative_mood",
          label: "Negative mood",
          text: result.summary.negative_mood,
        },
        { key: "arousal", label: "Arousal", text: result.summary.arousal },
      ]
    : [];

  return (
    <aside className="correlation-summary" aria-live="polite">
      <div className="correlation-summary__heading">
        <div>
          <span className="statistics__eyebrow">Personalized summary</span>
          <h3>What your patterns suggest</h3>
        </div>
        {status === "success" && (
          <span className="correlation-summary__source">
            {result.source === "ai" ? "AI generated" : "Pattern summary"}
          </span>
        )}
      </div>

      {status === "loading" && (
        <div className="correlation-summary__loading">
          <span />
          <span />
          <span />
        </div>
      )}

      {status === "error" && (
        <div className="correlation-summary__error">
          <p>We couldnâ€™t summarize these patterns right now.</p>
          <button type="button" onClick={onRetry}>Try again</button>
        </div>
      )}

      {status === "success" && result && (
        <>
          <p className="correlation-summary__overall">{result.summary.overall}</p>
          <div className="correlation-summary__items">
            {items.map((item) => (
              <div className="correlation-summary__item" key={item.key}>
                <span
                  className={`correlation-summary__dot correlation-summary__dot--${item.key}`}
                />
                <div>
                  <strong>{item.label}</strong>
                  <p>{item.text}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="correlation-summary__note">{result.summary.data_note}</p>
        </>
      )}
    </aside>
  );
}

function CategorySummary({
  summary,
  currency,
  displayCurrency,
  view,
  anchor,
  onViewChange,
  onAnchorChange,
}) {
  return (
    <section className="statistics__section">
      <div className="statistics__section-heading">
        <div>
          <span className="statistics__eyebrow">Category recap</span>
          <h2 className="statistics__section-title">Spending by category</h2>
        </div>
        <div className="category-summary__total">
          <span>Total spent</span>
          <strong>
            {formatMoney(
              convertAmount(summary.total_spent, currency, displayCurrency),
              displayCurrency
            )}
          </strong>
        </div>
      </div>

      <div className="category-controls">
        <div className="category-controls__views" role="tablist" aria-label="Category period">
          {Object.entries(CATEGORY_VIEW_LABELS).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={view === key}
              className={`category-controls__view ${
                view === key ? "category-controls__view--selected" : ""
              }`}
              onClick={() => onViewChange(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="category-controls__navigator">
          <button
            type="button"
            aria-label={`Previous ${PERIOD_NOUNS[view]}`}
            onClick={() => onAnchorChange(shiftAnchor(anchor, view, -1))}
          >
            ←
          </button>
          <strong>{periodLabel(view, summary.range_start, summary.range_end)}</strong>
          <button
            type="button"
            aria-label={`Next ${PERIOD_NOUNS[view]}`}
            onClick={() => onAnchorChange(shiftAnchor(anchor, view, 1))}
          >
            →
          </button>
        </div>
      </div>

      {summary.categories.length === 0 ? (
        <p className="statistics__empty">No spending recorded in this period.</p>
      ) : (
        <div className="category-bars">
          {summary.categories.map((category) => (
            <div className="category-bars__row" key={category.category_code ?? "uncategorized"}>
              <div className="category-bars__meta">
                <span>{category.label}</span>
                <span>
                  {(category.share * 100).toFixed(1)}% · {formatMoney(
                    convertAmount(category.spent_amount, currency, displayCurrency),
                    displayCurrency
                  )}
                </span>
              </div>
              <div className="category-bars__track">
                <div className="category-bars__fill" style={{ width: `${category.share * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function Statistics() {
  const [view, setView] = useState("weekly");
  const [anchor, setAnchor] = useState(() => toISODate(new Date()));
  const [categoryView, setCategoryView] = useState("yearly");
  const [categoryAnchor, setCategoryAnchor] = useState(() => toISODate(new Date()));
  const [status, setStatus] = useState("loading");
  const [data, setData] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [summaryStatus, setSummaryStatus] = useState("loading");
  const [correlationSummary, setCorrelationSummary] = useState(null);
  const [summaryAttempt, setSummaryAttempt] = useState(0);
  const [displayCurrency, setDisplayCurrency] = useDisplayCurrency();

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    fetchStatistics(view, anchor, categoryView, categoryAnchor)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setStatus("success");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [view, anchor, categoryView, categoryAnchor, attempt]);

  useEffect(() => {
    let cancelled = false;
    setSummaryStatus("loading");
    fetchCorrelationSummary(view, anchor)
      .then((result) => {
        if (cancelled) return;
        setCorrelationSummary(result);
        setSummaryStatus("success");
      })
      .catch(() => {
        if (cancelled) return;
        setSummaryStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [view, anchor, summaryAttempt]);

  const totals = useMemo(() => {
    if (!data) return { spent: 0, budget: 0, normalized: null };
    const spent = data.review.reduce((sum, bucket) => sum + Number(bucket.spent_amount), 0);
    const budget = data.review.reduce((sum, bucket) => sum + Number(bucket.budget_amount), 0);
    return { spent, budget, normalized: budget > 0 ? (2 * spent) / budget : null };
  }, [data]);

  const moodYMax = useMemo(() => {
    const maximum = Math.max(
      2.5,
      ...(data?.daily_mood.map((point) => point.normalized_spending) ?? [])
    );
    return Math.ceil(maximum * 2) / 2;
  }, [data]);

  return (
    <div className="statistics">
      <div className="statistics__topbar">
        <Link to="/home" className="statistics__back">← Home</Link>
      </div>

      <main className="statistics__content">
        <div className="statistics__header-row">
          <div>
            <span className="statistics__eyebrow">Your patterns</span>
            <h1 className="statistics__title">Spending review</h1>
          </div>
          {status === "success" && (
            <CurrencyToggle value={displayCurrency} onChange={setDisplayCurrency} />
          )}
        </div>

        <PeriodControls
          view={view}
          anchor={anchor}
          data={data}
          onViewChange={setView}
          onAnchorChange={setAnchor}
        />

        {status === "loading" && (
          <div className="statistics__skeleton" aria-hidden="true">
            <span /><span /><span />
          </div>
        )}

        {status === "error" && (
          <div className="statistics__error" role="alert">
            <p>Couldn’t load your spending review.</p>
            <button type="button" onClick={() => setAttempt((value) => value + 1)}>Try again</button>
          </div>
        )}

        {status === "success" && data && (
          <>
            <section className="statistics__section statistics__section--review">
              <div className="statistics__section-heading">
                <div>
                  <span className="statistics__eyebrow">{VIEW_LABELS[view]}ly review</span>
                  <h2 className="statistics__section-title">{VIEW_TITLES[view]}</h2>
                </div>
                <div className={`review-status ${totals.normalized > 2 ? "review-status--over" : ""}`}>
                  <span>
                    {totals.normalized == null
                      ? "No budget in this period"
                      : totals.normalized > 2
                        ? "Over budget"
                        : "Within budget"}
                  </span>
                  <strong>
                    <span>{formatBudgetPercentage(totals.normalized)}</span>
                    <small>
                      {formatMoney(
                        convertAmount(totals.spent, data.currency, displayCurrency),
                        displayCurrency
                      )}
                    </small>
                  </strong>
                </div>
              </div>
              <p className="statistics__section-body">
                {formatMoney(convertAmount(totals.spent, data.currency, displayCurrency), displayCurrency)} spent of {formatMoney(
                  convertAmount(totals.budget, data.currency, displayCurrency),
                  displayCurrency
                )} allocated.
              </p>
              <ReviewChart
                buckets={data.review}
                currency={data.currency}
                displayCurrency={displayCurrency}
              />
            </section>

            <CategorySummary
              summary={data.category_summary}
              currency={data.currency}
              displayCurrency={displayCurrency}
              view={categoryView}
              anchor={categoryAnchor}
              onViewChange={setCategoryView}
              onAnchorChange={setCategoryAnchor}
            />

            <section className="statistics__section">
              <span className="statistics__eyebrow">Daily relationship</span>
              <h2 className="statistics__section-title">Mood, arousal &amp; spending</h2>
              <p className="statistics__section-body">
                Each day becomes one point. Mood and arousal are weighted by every checked-in purchase’s share of that day’s checked-in spending.
              </p>
              <div className="mood-scatter-grid">
                <MoodScatter
                  title="Positive mood and spending"
                  metric="positive_mood"
                  points={data.daily_mood}
                  xMin={0}
                  xMax={2}
                  ticks={[0, 1, 2]}
                  color="var(--stats-positive)"
                  yMax={moodYMax}
                  currency={data.currency}
                  displayCurrency={displayCurrency}
                />
                <MoodScatter
                  title="Negative mood and spending"
                  metric="negative_mood"
                  points={data.daily_mood}
                  xMin={0}
                  xMax={2}
                  ticks={[0, 1, 2]}
                  color="var(--stats-negative)"
                  yMax={moodYMax}
                  currency={data.currency}
                  displayCurrency={displayCurrency}
                />
                <MoodScatter
                  title="Arousal and spending"
                  metric="arousal"
                  points={data.daily_mood}
                  xMin={-2}
                  xMax={2}
                  ticks={[-2, -1, 0, 1, 2]}
                  color="var(--stats-arousal)"
                  yMax={moodYMax}
                  currency={data.currency}
                  displayCurrency={displayCurrency}
                />
              </div>
              <CorrelationSummary
                status={summaryStatus}
                result={correlationSummary}
                onRetry={() => setSummaryAttempt((value) => value + 1)}
              />
            </section>
          </>
        )}
      </main>
    </div>
  );
}
