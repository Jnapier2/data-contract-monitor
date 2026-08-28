type Severity = "info" | "warning" | "error" | "critical";

interface Finding {
  severity: Severity;
  category: string;
  rule_id: string;
  title: string;
  message: string;
  column: string | null;
  sample_rows: number[];
}

interface ColumnProfile {
  name: string;
  observed_type: string;
  null_count: number;
  distinct_count: number;
}

interface PiiSignal {
  column: string;
  category: string;
  confidence: string;
  matching_values: number;
  sampled_values: number;
}

interface ValidationResult {
  run_id: string;
  dataset_name: string;
  completed_at: string;
  duration_ms: number;
  summary: {
    status: "passed" | "failed";
    passed: boolean;
    findings_total: number;
    critical: number;
    errors: number;
    warnings: number;
    info: number;
  };
  findings: Finding[];
  profile: {
    row_count: number;
    column_count: number;
    columns: ColumnProfile[];
    pii_signals: PiiSignal[];
  };
}

interface HistoryEntry {
  started_at: string;
  dataset_name: string;
  status: string;
  row_count: number;
  findings_total: number;
  duration_ms: number;
}

const byId = <T extends HTMLElement>(id: string): T => {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing required element: ${id}`);
  return node as T;
};

const form = byId<HTMLFormElement>("validate-form");
const contractFile = byId<HTMLInputElement>("contract-file");
const dataFile = byId<HTMLInputElement>("data-file");
const failOn = byId<HTMLSelectElement>("fail-on");
const statusNode = byId<HTMLDivElement>("status");
const resultsNode = byId<HTMLElement>("results");
const summaryCards = byId<HTMLDivElement>("summary-cards");
const findingsBody = byId<HTMLTableSectionElement>("findings-body");
const profileBody = byId<HTMLTableSectionElement>("profile-body");
const privacyList = byId<HTMLUListElement>("privacy-list");
const findingCount = byId<HTMLParagraphElement>("finding-count");
const severityFilter = byId<HTMLSelectElement>("severity-filter");
const historyBody = byId<HTMLTableSectionElement>("history-body");
let latestResult: ValidationResult | null = null;

const textCell = (text: string): HTMLTableCellElement => {
  const cell = document.createElement("td");
  cell.textContent = text;
  return cell;
};

const setBusy = (message: string, busy: boolean): void => {
  statusNode.textContent = message;
  statusNode.classList.remove("error");
  for (const button of document.querySelectorAll<HTMLButtonElement>("button")) {
    button.disabled = busy;
  }
};

const setError = (message: string): void => {
  statusNode.textContent = message;
  statusNode.classList.add("error");
  for (const button of document.querySelectorAll<HTMLButtonElement>("button")) {
    button.disabled = false;
  }
};

const summaryCard = (value: string, label: string, className = ""): HTMLDivElement => {
  const card = document.createElement("div");
  card.className = "summary-card";
  const valueNode = document.createElement("div");
  valueNode.className = `summary-value ${className}`.trim();
  valueNode.textContent = value;
  const labelNode = document.createElement("div");
  labelNode.className = "summary-label";
  labelNode.textContent = label;
  card.append(valueNode, labelNode);
  return card;
};

const renderSummary = (result: ValidationResult): void => {
  summaryCards.replaceChildren(
    summaryCard(result.summary.status.toUpperCase(), "Validation status", `status-${result.summary.status}`),
    summaryCard(result.profile.row_count.toLocaleString(), "Rows evaluated"),
    summaryCard(String(result.summary.critical), "Critical"),
    summaryCard(String(result.summary.errors), "Errors"),
    summaryCard(String(result.summary.warnings), "Warnings"),
    summaryCard(`${result.duration_ms} ms`, "Runtime"),
  );
};

const renderFindings = (): void => {
  if (!latestResult) return;
  const filter = severityFilter.value;
  const findings = latestResult.findings.filter((item) => filter === "all" || item.severity === filter);
  findingsBody.replaceChildren();
  findingCount.textContent = `${findings.length} of ${latestResult.findings.length} finding(s) shown`;
  if (findings.length === 0) {
    const row = document.createElement("tr");
    const cell = textCell("No findings match this filter.");
    cell.colSpan = 5;
    row.append(cell);
    findingsBody.append(row);
    return;
  }
  for (const finding of findings) {
    const row = document.createElement("tr");
    const severityCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge badge-${finding.severity}`;
    badge.textContent = finding.severity.toUpperCase();
    severityCell.append(badge);
    const ruleCell = document.createElement("td");
    const strong = document.createElement("strong");
    strong.textContent = finding.title;
    const small = document.createElement("div");
    small.className = "muted";
    small.textContent = `${finding.category} · ${finding.rule_id}`;
    ruleCell.append(strong, small);
    row.append(
      severityCell,
      ruleCell,
      textCell(finding.column ?? "—"),
      textCell(finding.message),
      textCell(finding.sample_rows.length ? finding.sample_rows.join(", ") : "—"),
    );
    findingsBody.append(row);
  }
};

const renderProfile = (result: ValidationResult): void => {
  profileBody.replaceChildren();
  for (const column of result.profile.columns) {
    const row = document.createElement("tr");
    row.append(
      textCell(column.name),
      textCell(column.observed_type),
      textCell(String(column.null_count)),
      textCell(String(column.distinct_count)),
    );
    profileBody.append(row);
  }
};

const renderPrivacy = (result: ValidationResult): void => {
  privacyList.replaceChildren();
  if (result.profile.pii_signals.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No potential sensitive-field signals detected.";
    privacyList.append(item);
    return;
  }
  for (const signal of result.profile.pii_signals) {
    const item = document.createElement("li");
    const title = document.createElement("div");
    title.className = "signal-title";
    title.textContent = `${signal.column}: ${signal.category}`;
    const meta = document.createElement("div");
    meta.className = "signal-meta";
    meta.textContent = `${signal.confidence} confidence · ${signal.matching_values}/${signal.sampled_values} sampled values matched`;
    item.append(title, meta);
    privacyList.append(item);
  }
};

const renderResult = (result: ValidationResult): void => {
  latestResult = result;
  resultsNode.hidden = false;
  renderSummary(result);
  renderFindings();
  renderProfile(result);
  renderPrivacy(result);
  statusNode.textContent = `${result.dataset_name}: ${result.summary.status}. ${result.summary.findings_total} finding(s).`;
  statusNode.classList.remove("error");
  for (const button of document.querySelectorAll<HTMLButtonElement>("button")) {
    button.disabled = false;
  }
  resultsNode.scrollIntoView({ behavior: "smooth", block: "start" });
};

const parseResponse = async (response: Response): Promise<ValidationResult> => {
  const payload = await response.json() as ValidationResult | { detail?: string };
  if (!response.ok) {
    const detail = "detail" in payload && payload.detail ? payload.detail : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }
  return payload as ValidationResult;
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!contractFile.files?.[0] || !dataFile.files?.[0]) {
    setError("Choose both a YAML contract and a dataset.");
    return;
  }
  setBusy("Validating locally…", true);
  const body = new FormData();
  body.append("contract", contractFile.files[0]);
  body.append("data", dataFile.files[0]);
  try {
    const response = await fetch(`/api/validate?fail_on=${encodeURIComponent(failOn.value)}`, { method: "POST", body });
    renderResult(await parseResponse(response));
    await loadHistory();
  } catch (error) {
    setError(error instanceof Error ? error.message : "Validation failed.");
  }
});

const runDemo = async (scenario: "good" | "bad"): Promise<void> => {
  setBusy(`Running ${scenario} demonstration…`, true);
  try {
    const response = await fetch(`/api/demo/${scenario}`, { method: "POST" });
    renderResult(await parseResponse(response));
    await loadHistory();
  } catch (error) {
    setError(error instanceof Error ? error.message : "Demo failed.");
  }
};

byId<HTMLButtonElement>("demo-good").addEventListener("click", () => void runDemo("good"));
byId<HTMLButtonElement>("demo-bad").addEventListener("click", () => void runDemo("bad"));
severityFilter.addEventListener("change", renderFindings);

byId<HTMLButtonElement>("download-json").addEventListener("click", () => {
  if (!latestResult) return;
  const blob = new Blob([`${JSON.stringify(latestResult, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `data_contract_result_${latestResult.run_id.slice(0, 12)}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});

const loadHistory = async (): Promise<void> => {
  try {
    const response = await fetch("/api/history?limit=20");
    if (!response.ok) throw new Error("History request failed");
    const entries = await response.json() as HistoryEntry[];
    historyBody.replaceChildren();
    if (entries.length === 0) {
      const row = document.createElement("tr");
      const cell = textCell("No recorded runs yet.");
      cell.colSpan = 6;
      row.append(cell);
      historyBody.append(row);
      return;
    }
    for (const entry of [...entries].reverse()) {
      const row = document.createElement("tr");
      row.append(
        textCell(new Date(entry.started_at).toLocaleString()),
        textCell(entry.dataset_name),
        textCell(entry.status.toUpperCase()),
        textCell(entry.row_count.toLocaleString()),
        textCell(String(entry.findings_total)),
        textCell(`${entry.duration_ms} ms`),
      );
      historyBody.append(row);
    }
  } catch {
    historyBody.replaceChildren();
    const row = document.createElement("tr");
    const cell = textCell("History is unavailable.");
    cell.colSpan = 6;
    row.append(cell);
    historyBody.append(row);
  }
};

byId<HTMLButtonElement>("refresh-history").addEventListener("click", () => void loadHistory());
void loadHistory();
