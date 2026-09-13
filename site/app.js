const dashboardDataUrl = "data/dashboard.json";

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value ?? 0);
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatTimestamp(value) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[character],
  );
}

function renderBars(containerId, rows, labelKey, valueKey) {
  const container = document.getElementById(containerId);

  if (!rows.length) {
    container.innerHTML = '<p class="empty-state">No curated data yet.</p>';
    return;
  }

  const maximum = Math.max(...rows.map((row) => row[valueKey]));

  container.innerHTML = rows
    .map((row) => {
      const percentage = Math.max((row[valueKey] / maximum) * 100, 2);

      return `
        <div class="bar-row">
          <span class="bar-label">${escapeHtml(row[labelKey])}</span>
          <div class="bar-track">
            <div class="bar-fill" style="width: ${percentage}%"></div>
          </div>
          <span class="bar-value">${formatNumber(row[valueKey])}</span>
        </div>
      `;
    })
    .join("");
}

function renderLatestRun(run) {
  const status = document.getElementById("run-status");
  const details = document.getElementById("latest-run-details");

  if (!run) {
    status.textContent = "No pipeline run available";
    details.innerHTML = '<p class="empty-state">No run ledger found.</p>';
    return;
  }

  status.textContent = `Latest run: ${run.status}`;
  status.classList.add(run.status === "succeeded" ? "success" : "failed");

  const items = [
    ["Run started", formatTimestamp(run.started_at)],
    ["Source dates", `${run.source_dates_succeeded} of ${run.source_dates_planned} succeeded`],
    ["Target records", formatNumber(run.target_records)],
    ["Inserted / updated", `${formatNumber(run.inserted_records)} / ${formatNumber(run.updated_records)}`],
    ["Unchanged", formatNumber(run.unchanged_records)],
    ["Quarantined", formatNumber(run.quarantined_records)],
  ];

  details.innerHTML = items
    .map(
      ([label, value]) =>
        `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`,
    )
    .join("");
}

function renderTopCompanies(companies) {
  const container = document.getElementById("top-companies");

  if (!companies.length) {
    container.innerHTML = '<li class="empty-state">No company data yet.</li>';
    return;
  }

  container.innerHTML = companies
    .map(
      (company) => `
        <li>
          <span>${escapeHtml(company.company_name)}</span>
          <strong>${formatNumber(company.filing_count)}</strong>
        </li>
      `,
    )
    .join("");
}

function renderRecentRuns(runs) {
  const container = document.getElementById("recent-runs");

  if (!runs.length) {
    container.innerHTML =
      '<tr><td colspan="7" class="empty-state">No run history yet.</td></tr>';
    return;
  }

  container.innerHTML = [...runs]
    .reverse()
    .map(
      (run) => `
        <tr>
          <td>
            <span class="run-result ${escapeHtml(run.status)}">
              ${escapeHtml(run.status)}
            </span>
          </td>
          <td>${escapeHtml(formatTimestamp(run.started_at))}</td>
          <td>${formatNumber(run.source_dates_planned)}</td>
          <td>${formatNumber(run.validated_records)}</td>
          <td>${formatNumber(run.quarantined_records)}</td>
          <td>${formatNumber(run.inserted_records)}</td>
          <td>${formatNumber(run.unchanged_records)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderDashboard(data) {
  const { dataset, latest_run: latestRun } = data;

  document.getElementById("generated-at").textContent =
    `Dashboard data generated ${formatTimestamp(data.generated_at)}`;
  document.getElementById("curated-relationships").textContent =
    formatNumber(dataset.curated_relationships);
  document.getElementById("unique-companies").textContent =
    formatNumber(dataset.unique_companies);
  document.getElementById("raw-rows").textContent =
    formatNumber(latestRun?.raw_rows);
  document.getElementById("quarantined-records").textContent =
    formatNumber(latestRun?.quarantined_records);
  document.getElementById("date-range").textContent =
    `${formatDate(dataset.earliest_filing_date)} – ${formatDate(dataset.latest_filing_date)}`;

  renderLatestRun(latestRun);
}

async function loadDashboard() {
  try {
    const response = await fetch(dashboardDataUrl);

    if (!response.ok) {
      throw new Error(`Dashboard data request failed: ${response.status}`);
    }

    const data = await response.json();
    renderDashboard(data);
    renderBars(
      "form-type-chart",
      data.form_type_counts,
      "form_type",
      "filing_count",
    );
    renderBars(
      "filing-date-chart",
      data.filings_by_date,
      "filing_date",
      "filing_count",
    );
    renderTopCompanies(data.top_companies);
    renderRecentRuns(data.recent_runs);
  } catch (error) {
    document.getElementById("run-status").textContent =
      "Dashboard data unavailable";
    document.getElementById("run-status").classList.add("failed");
    console.error(error);
  }
}

loadDashboard();