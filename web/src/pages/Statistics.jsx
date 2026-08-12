import DOMPurify from "dompurify";
import { marked } from "marked";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useCardData } from "../hooks/useCardData";
import { useDisplayCurrency } from "../hooks/useDisplayCurrency";
import { apiFetch } from "../lib/api";
import { convertAmount, formatMoney } from "../lib/currency";
import "./Statistics.css";

const RANGE_DAYS = 28;

// Fixed order + colors, validated with the dataviz skill's palette
// checker (adjacent-pair CVD + normal-vision floor) against this app's
// mist surface — see the --mood-* custom properties in Statistics.css.
// Never reuse --color-lime/--color-clay here: both already carry a
// specific meaning elsewhere (primary accent, "over budget") that a mood
// color would collide with.
const MOOD_ORDER = ["unclassified", "stressed", "positive", "neutral", "negative"];
const MOOD_LABELS = {
  unclassified: "Unclassified",
  stressed: "Stressed",
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
};

const BUDGET_SOURCE_LABELS = {
  goal_daily: "your daily budget",
  goal_monthly: "your monthly budget",
  profile: "your average spending",
};

function toISODate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatShortDate(isoDate) {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

async function fetchMoodSpending() {
  const to = new Date();
  const from = new Date(to);
  from.setDate(from.getDate() - (RANGE_DAYS - 1));

  const response = await apiFetch(
    `/api/v1/analysis/mood-spending?from_date=${toISODate(from)}&to_date=${toISODate(to)}&granularity=week`
  );
  if (!response.ok) throw new Error("Failed to load statistics");
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
          className={`statistics__currency-toggle-option ${
            value === code ? "statistics__currency-toggle-option--selected" : ""
          }`}
          onClick={() => onChange(code)}
        >
          {code === "USD" ? "$" : "L.L."}
        </button>
      ))}
    </div>
  );
}

// Chart 1 — spend by mood, one stacked bar per week. Segment order and
// colors are fixed (MOOD_ORDER) so the same mood always reads as the same
// color across both charts and the legend.
function MoodStackChart({ periods, currency, displayCurrency }) {
  const periodTotals = periods.map((period) =>
    period.buckets.reduce(
      (sum, b) => sum + convertAmount(b.total_amount, currency, displayCurrency),
      0
    )
  );
  const maxTotal = Math.max(1, ...periodTotals);

  return (
    <div className="mood-stack">
      {periods.map((period, i) => {
        const byMood = Object.fromEntries(period.buckets.map((b) => [b.mood, b]));
        return (
          <div className="mood-stack__col" key={period.period_start}>
            <span className="mood-stack__total">{formatMoney(periodTotals[i], displayCurrency)}</span>
            <div className="mood-stack__bar">
              {MOOD_ORDER.map((mood) => {
                const amount = convertAmount(byMood[mood]?.total_amount ?? 0, currency, displayCurrency);
                if (amount <= 0) return null;
                const heightPct = (amount / maxTotal) * 100;
                return (
                  <div
                    key={mood}
                    className="mood-stack__segment"
                    style={{ height: `${heightPct}%`, background: `var(--mood-${mood})` }}
                    title={`${MOOD_LABELS[mood]}: ${formatMoney(amount, displayCurrency)}`}
                  />
                );
              })}
            </div>
            <span className="mood-stack__date">{formatShortDate(period.period_start)}</span>
          </div>
        );
      })}
    </div>
  );
}

// The "table view" relief for the low-contrast fills above: exact totals
// in text color, not fill color, for every mood — always present, not
// just on hover.
function MoodLegend({ periods, currency, displayCurrency }) {
  const totals = Object.fromEntries(MOOD_ORDER.map((mood) => [mood, { amount: 0, count: 0 }]));
  for (const period of periods) {
    for (const bucket of period.buckets) {
      const entry = totals[bucket.mood];
      entry.amount += convertAmount(bucket.total_amount, currency, displayCurrency);
      entry.count += bucket.transaction_count;
    }
  }
  const grandTotal = Math.max(
    1,
    Object.values(totals).reduce((sum, t) => sum + t.amount, 0)
  );

  return (
    <ul className="mood-legend">
      {MOOD_ORDER.map((mood) => {
        const { amount, count } = totals[mood];
        return (
          <li className="mood-legend__row" key={mood}>
            <span className="mood-legend__swatch" style={{ background: `var(--mood-${mood})` }} />
            <span className="mood-legend__label">{MOOD_LABELS[mood]}</span>
            <span className="mood-legend__count">
              {count} {count === 1 ? "purchase" : "purchases"}
            </span>
            <span className="mood-legend__amount">{formatMoney(amount, displayCurrency)}</span>
            <span className="mood-legend__share">{Math.round((amount / grandTotal) * 100)}%</span>
          </li>
        );
      })}
    </ul>
  );
}

// Chart 2 — overspend rate per mood, aggregated across every fetched
// period. Bar length is the rate; color is the mood's own identity color
// (same mapping as chart 1), not --color-clay — clay means "over your
// budget line" on the Home/Bank bars specifically, a different metric.
function OverspendRateChart({ periods }) {
  const totals = Object.fromEntries(MOOD_ORDER.map((mood) => [mood, { count: 0, overspend: 0 }]));
  for (const period of periods) {
    for (const bucket of period.buckets) {
      const entry = totals[bucket.mood];
      entry.count += bucket.transaction_count;
      entry.overspend += bucket.overspend_count;
    }
  }

  return (
    <div className="overspend-chart">
      {MOOD_ORDER.map((mood) => {
        const { count, overspend } = totals[mood];
        const ratePct = count > 0 ? Math.round((overspend / count) * 100) : null;
        return (
          <div className="overspend-chart__row" key={mood}>
            <span className="overspend-chart__label">{MOOD_LABELS[mood]}</span>
            <div className="overspend-chart__track">
              {ratePct != null && (
                <div
                  className="overspend-chart__fill"
                  style={{ width: `${ratePct}%`, background: `var(--mood-${mood})` }}
                />
              )}
            </div>
            <span className="overspend-chart__value">
              {ratePct != null ? `${ratePct}%` : "No purchases"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

const CORRELATION_MOOD_LABELS = {
  happiness: "Happiness",
  arousal: "Arousal",
  sadness: "Sadness",
};

async function fetchCorrelation(includeAiReport) {
  const response = await apiFetch(
    `/api/v1/analysis/mood-spend-correlation?include_ai_report=${includeAiReport}`
  );
  if (!response.ok) throw new Error("Failed to load correlation analysis");
  return response.json();
}

function renderMarkdown(markdown) {
  return { __html: DOMPurify.sanitize(marked.parse(markdown)) };
}

// The Pearson r between excess spend and a mood/arousal score is a
// polarity metric (above/below zero), not identity — diverging color job,
// not the categorical mood palette above. Blue/red is the same pair the
// dataviz skill's reference palette documents for diverging data; reused
// here for a different chart than the mood buckets above, so it doesn't
// need to stay distinct from --mood-unclassified.
function CorrelationTable({ correlations }) {
  return (
    <table className="correlation-table">
      <thead>
        <tr>
          <th>Score</th>
          <th>Correlation (r)</th>
          <th>p-value</th>
          <th>n</th>
        </tr>
      </thead>
      <tbody>
        {correlations.map((row) => {
          const r = row.pearson_r;
          const significant = row.p_value != null && row.p_value < 0.05;
          return (
            <tr key={row.mood}>
              <td>{CORRELATION_MOOD_LABELS[row.mood] ?? row.mood}</td>
              <td>
                {r != null ? (
                  <span className="correlation-table__r">
                    <span
                      className="correlation-table__dot"
                      style={{ background: r >= 0 ? "var(--corr-positive)" : "var(--corr-negative)" }}
                    />
                    {r.toFixed(2)}
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td>
                {row.p_value != null ? row.p_value.toFixed(3) : "—"}
                {significant && <span className="correlation-table__sig"> *</span>}
              </td>
              <td>{row.n}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function CorrelationSection() {
  const [status, setStatus] = useState("loading");
  const [data, setData] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    fetchCorrelation(false)
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
  }, [attempt]);

  async function generateReport() {
    setReportLoading(true);
    setReportError(false);
    try {
      const result = await fetchCorrelation(true);
      setData(result);
    } catch {
      setReportError(true);
    } finally {
      setReportLoading(false);
    }
  }

  return (
    <section className="statistics__section">
      <h2 className="statistics__section-title">Mood &amp; spend correlation</h2>
      <p className="statistics__section-body">
        How your excess spend (vs. your own average for that category) tracks against how you
        said you felt at check-in.
      </p>

      {status === "loading" && (
        <div className="statistics__skeleton" aria-hidden="true">
          <span className="statistics__skeleton-row" />
          <span className="statistics__skeleton-row" />
        </div>
      )}

      {status === "error" && (
        <div className="statistics__error" role="alert">
          <p>Couldn&rsquo;t load the correlation analysis.</p>
          <button
            type="button"
            className="statistics__retry"
            onClick={() => setAttempt((a) => a + 1)}
          >
            Try again
          </button>
        </div>
      )}

      {status === "success" && data.transaction_count === 0 && (
        <p className="statistics__empty">
          Not enough check-ins linked to purchases yet to compute a correlation.
        </p>
      )}

      {status === "success" && data.transaction_count > 0 && (
        <>
          <CorrelationTable correlations={data.correlations} />

          <div className="correlation-plots">
            {data.scatter_plot_png_base64 && (
              <img
                className="correlation-plots__img"
                src={`data:image/png;base64,${data.scatter_plot_png_base64}`}
                alt="Scatter plots of excess spend against happiness, arousal, and sadness scores"
              />
            )}
            {data.bar_chart_png_base64 && (
              <img
                className="correlation-plots__img"
                src={`data:image/png;base64,${data.bar_chart_png_base64}`}
                alt="Bar chart of correlation strength (Pearson r) for each mood/arousal score"
              />
            )}
          </div>

          <div className="ai-report">
            {data.ai_report_markdown ? (
              <div
                className="ai-report__content"
                // eslint-disable-next-line react/no-danger -- sanitized via DOMPurify above
                dangerouslySetInnerHTML={renderMarkdown(data.ai_report_markdown)}
              />
            ) : (
              <>
                <button
                  type="button"
                  className="ai-report__generate"
                  onClick={generateReport}
                  disabled={reportLoading}
                >
                  {reportLoading ? "Generating…" : "Generate AI report"}
                </button>
                {reportError && (
                  <p className="statistics__row-error" role="alert">
                    Couldn&rsquo;t generate the report.{" "}
                    <button type="button" className="statistics__retry" onClick={generateReport}>
                      Try again
                    </button>
                  </p>
                )}
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default function Statistics() {
  const { status, data, retry } = useCardData(fetchMoodSpending);
  const [displayCurrency, setDisplayCurrency] = useDisplayCurrency();

  const hasBudget = status === "success" && data.daily_budget.amount != null;
  const totalTransactions =
    hasBudget &&
    data.periods.reduce(
      (sum, p) => sum + p.buckets.reduce((s, b) => s + b.transaction_count, 0),
      0
    );

  return (
    <div className="statistics mood-chart">
      <div className="statistics__topbar">
        <Link to="/home" className="statistics__back">
          &larr; Home
        </Link>
      </div>

      <div className="statistics__content">
        <div className="statistics__header-row">
          <h1 className="statistics__title">Statistics</h1>
          {status === "success" && (
            <CurrencyToggle value={displayCurrency} onChange={setDisplayCurrency} />
          )}
        </div>

        {status === "loading" && (
          <div className="statistics__skeleton" aria-hidden="true">
            <span className="statistics__skeleton-row" />
            <span className="statistics__skeleton-row" />
            <span className="statistics__skeleton-row" />
          </div>
        )}

        {status === "error" && (
          <div className="statistics__error" role="alert">
            <p>Couldn&rsquo;t load your statistics.</p>
            <button type="button" className="statistics__retry" onClick={retry}>
              Try again
            </button>
          </div>
        )}

        {status === "success" && !hasBudget && (
          <p className="statistics__empty">
            Set a budget to see how your spending breaks down by mood.
          </p>
        )}

        {status === "success" && hasBudget && totalTransactions === 0 && (
          <p className="statistics__empty">No purchases in the last 4 weeks.</p>
        )}

        {status === "success" && hasBudget && totalTransactions > 0 && (
          <>
            <p className="statistics__budget-line">
              Daily budget: {formatMoney(
                convertAmount(data.daily_budget.amount, data.currency, displayCurrency),
                displayCurrency
              )}
              {BUDGET_SOURCE_LABELS[data.daily_budget.source] && (
                <> &mdash; based on {BUDGET_SOURCE_LABELS[data.daily_budget.source]}</>
              )}
            </p>

            <section className="statistics__section">
              <h2 className="statistics__section-title">Spend by mood, last 4 weeks</h2>
              <MoodStackChart
                periods={data.periods}
                currency={data.currency}
                displayCurrency={displayCurrency}
              />
              <MoodLegend
                periods={data.periods}
                currency={data.currency}
                displayCurrency={displayCurrency}
              />
            </section>

            <section className="statistics__section">
              <h2 className="statistics__section-title">Overspend rate by mood</h2>
              <p className="statistics__section-body">
                How often a purchase in each mood pushed you past your daily budget for that day.
              </p>
              <OverspendRateChart periods={data.periods} />
            </section>
          </>
        )}

        <CorrelationSection />
      </div>
    </div>
  );
}
