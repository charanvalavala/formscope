import {
  $,
  safe,
  highlight,
  request,
  sample,
  busy,
  notify,
  savedOnly,
} from "./ui.js";
let activeTicker = "";
let snapshot = savedOnly;
let version = 0;
const money = (value) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("en", {
        notation: "compact",
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      }).format(value);
const percent = (value) =>
  value == null ? "—" : `${(value * 100).toFixed(1)}%`;
function chart(periods) {
  const data = periods.filter((row) => Number.isFinite(row.revenue));
  if (data.length < 2)
    return '<p class="quiet">At least two reported periods are needed for a trend.</p>';
  const values = data.map((row) => row.revenue),
    min = Math.min(...values) * 0.9,
    max = Math.max(...values) * 1.05;
  const points = data.map((row, i) => [
    25 + (i * 650) / (data.length - 1),
    135 - ((row.revenue - min) / (max - min || 1)) * 110,
  ]);
  return `<svg class="chart" role="img" aria-label="Annual reported revenue trend" viewBox="0 0 710 180"><line x1="25" y1="140" x2="675" y2="140" stroke="var(--line)"/><polyline class="series" points="${points.map((point) => point.join(",")).join(" ")}"/>${points.map(([x, y], i) => `<circle class="point" cx="${x}" cy="${y}" r="4"><title>${safe(data[i].as_of)}: ${money(data[i].revenue)}</title></circle><text x="${x}" y="165" text-anchor="middle">${safe(data[i].year)}</text>`).join("")}</svg>`;
}
function companyCard(report, compact = false) {
  const latest = report.periods.at(-1) || {};
  return `<div class="panel"><div class="panel-head"><div><span class="eyebrow">${safe(report.ticker)}</span><h2>${safe(report.company)}</h2></div><a class="inline-link" href="${safe(report.source)}" target="_blank" rel="noopener">SEC facts ↗</a></div><div class="metrics">${[
    ["Revenue", money(latest.revenue)],
    ["Revenue growth", percent(latest.revenue_growth)],
    ["Net income", money(latest.net_income)],
    ["Net margin", percent(latest.net_margin)],
  ]
    .map(
      ([label, value]) =>
        `<div class="metric"><span>${label}</span><strong>${value}</strong><small>Period ended ${safe(latest.as_of || "unavailable")}</small></div>`,
    )
    .join("")}</div>${chart(report.periods)}${
    compact
      ? ""
      : `<div class="table-wrap"><table><thead><tr><th>Period ended</th><th>Revenue</th><th>Growth</th><th>Net income</th><th>Net margin</th></tr></thead><tbody>${[
          ...report.periods,
        ]
          .reverse()
          .map(
            (row) =>
              `<tr><td>${safe(row.as_of)}</td><td>${money(row.revenue)}</td><td>${percent(row.revenue_growth)}</td><td>${money(row.net_income)}</td><td>${percent(row.net_margin)}</td></tr>`,
          )
          .join(
            "",
          )}</tbody></table></div><details><summary>Metric provenance and formulas</summary><p class="mode-note">Growth = current revenue / previous comparable annual revenue − 1. Net margin = net income / revenue. Ratios are omitted when full reporting periods or units do not match.</p><pre>${safe(JSON.stringify(latest.provenance || { note: "Snapshot from previous API version; filing-level provenance only" }, null, 2))}</pre></details><div class="samples">${(report.filings || []).map((f) => `<a class="btn small" href="${safe(f.url)}" target="_blank" rel="noopener">10-K ${safe(f.filed)} ↗</a>`).join("")}</div>`
  }</div>`;
}
async function loadSaved() {
  version++;
  snapshot = true;
  const data = await sample();
  activeTicker = data.company.ticker;
  $("ticker").value = activeTicker;
  $("report").innerHTML = companyCard(data.company);
  $("mode").innerHTML =
    "<strong>Saved SEC snapshot</strong> · Captured " +
    safe(data.captured_at) +
    ". Values are historical. Searches in this mode use the saved example only.";
  $("search-panel").classList.remove("hidden");
  $("filing-question").value = data.search.answer.replace("Saved query: ", "");
  $("filing-question").readOnly = true;
  $("search-results").innerHTML =
    '<p class="quiet">Load the saved passage result below. Open the live app for a different query.</p>';
}
$("saved").addEventListener("click", () => busy($("saved"), loadSaved));
$("company-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy($("analyze"), async () => {
    if (savedOnly) return loadSaved();
    const token = ++version;
    snapshot = false;
    const ticker = $("ticker").value.trim().toUpperCase(),
      other = $("compare-ticker").value.trim().toUpperCase();
    if (!ticker) throw new Error("Enter a company ticker.");
    const report = await request(
      `/api/company?ticker=${encodeURIComponent(ticker)}`,
      { key: "company" },
    );
    const comparison = other
      ? await request(`/api/company?ticker=${encodeURIComponent(other)}`, {
          key: "comparison",
        })
      : null;
    if (token !== version) return;
    activeTicker = report.ticker;
    $("filing-question").readOnly = false;
    $("report").innerHTML = comparison
      ? `<div class="notice">Compare reporting dates and accounting contexts before interpreting differences.</div><div class="compare">${companyCard(report, true)}${companyCard(comparison, true)}</div>`
      : companyCard(report);
    $("mode").textContent =
      "Live SEC data · Retrieved " +
      report.generated_at +
      ". Metric availability varies by issuer.";
    $("search-panel").classList.remove("hidden");
    $("search-results").innerHTML = "";
  });
});
for (const button of document.querySelectorAll("[data-ticker]"))
  button.addEventListener("click", () => {
    $("ticker").value = button.dataset.ticker;
  });
$("filing-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy($("find"), async () => {
    const question = $("filing-question").value.trim();
    const data = snapshot
      ? (await sample()).search
      : await request(
          `/api/filing-search?ticker=${encodeURIComponent(activeTicker)}&question=${encodeURIComponent(question)}`,
          { key: "search", timeout: 120000 },
        );
    $("search-results").innerHTML =
      `<p class="badge">${safe(snapshot ? "Saved query result" : data.mode)}</p>${data.warning ? `<p class="error">${safe(data.warning)}</p>` : ""}<p class="quiet">${safe(data.answer)}</p><div class="evidence-grid">${data.citations.map((item) => `<article class="evidence"><div class="source">Passage ${item.rank}</div><p>${highlight(item.text, question)}</p><a href="${safe(item.url)}" target="_blank" rel="noopener">Open source filing ↗</a><details><summary>Ranking details</summary><p>Score ${Number(item.score).toFixed(4)}</p></details></article>`).join("")}</div>`;
  });
});
if (savedOnly) {
  $("ticker").readOnly = true;
  $("compare-ticker").disabled = true;
  $("analyze").textContent = "Reload saved financials";
  for (const button of document.querySelectorAll("[data-ticker]"))
    button.disabled = true;
  loadSaved().catch((error) => notify(error.message, true));
}
