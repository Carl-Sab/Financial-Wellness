const API_BASE_URL = "http://localhost:8000/api/v1";

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text));
}

function formatR(value) {
  if (value === null) return "—";
  return value.toFixed(3);
}

function formatP(value) {
  if (value === null) return "—";
  return value < 0.001 ? value.toExponential(2) : value.toFixed(3);
}

function renderCorrelationTable(correlations) {
  const tbody = document.querySelector("#correlation-table tbody");
  tbody.innerHTML = correlations
    .map((row) => {
      const rClass = row.pearson_r === null ? "" : row.pearson_r >= 0 ? "r-positive" : "r-negative";
      const significant = row.p_value !== null && row.p_value < 0.05;
      return `
        <tr>
          <td>${escapeHtml(row.mood)}</td>
          <td class="${rClass}">${formatR(row.pearson_r)}</td>
          <td class="${significant ? "significant" : ""}">${formatP(row.p_value)}${significant ? " *" : ""}</td>
          <td>${row.n}</td>
        </tr>
      `;
    })
    .join("");
}

async function runAnalysis(event) {
  event.preventDefault();

  const userId = document.getElementById("user-id").value.trim();
  const includeAiReport = document.getElementById("include-ai-report").checked;
  const runBtn = document.getElementById("run-btn");
  const status = document.getElementById("status");
  const results = document.getElementById("results");
  const aiSection = document.getElementById("ai-report-section");

  const params = new URLSearchParams();
  if (userId) params.set("user_id", userId);
  if (includeAiReport) params.set("include_ai_report", "true");

  runBtn.disabled = true;
  status.classList.remove("error");
  status.textContent = includeAiReport
    ? "Running analysis and generating AI report (this can take a bit)…"
    : "Running analysis…";
  results.classList.add("hidden");
  aiSection.classList.add("hidden");

  try {
    const response = await fetch(`${API_BASE_URL}/analysis/mood-spend-correlation?${params}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail ? JSON.stringify(body.detail) : `Request failed (${response.status})`);
    }
    const data = await response.json();

    if (data.transaction_count === 0) {
      status.textContent = "No transactions with a linked checkin found for that user — nothing to correlate.";
      return;
    }

    document.getElementById("transaction-count").textContent =
      `Based on ${data.transaction_count} transactions with a linked check-in.`;
    renderCorrelationTable(data.correlations);
    document.getElementById("scatter-plot").src = `data:image/png;base64,${data.scatter_plot_png_base64}`;
    document.getElementById("bar-plot").src = `data:image/png;base64,${data.bar_chart_png_base64}`;

    if (data.ai_report_markdown) {
      document.getElementById("ai-report-content").innerHTML = renderMarkdown(data.ai_report_markdown);
      aiSection.classList.remove("hidden");
    }

    results.classList.remove("hidden");
    status.textContent = "";
  } catch (err) {
    status.classList.add("error");
    status.textContent = `Error: ${err.message}`;
  } finally {
    runBtn.disabled = false;
  }
}

document.getElementById("analysis-form").addEventListener("submit", runAnalysis);
