"use strict";
const byId = (id) => {
    const node = document.getElementById(id);
    if (!node)
        throw new Error(`Missing required element: ${id}`);
    return node;
};
const form = byId("validate-form");
const contractFile = byId("contract-file");
const dataFile = byId("data-file");
const referenceFiles = byId("reference-files");
const failOn = byId("fail-on");
const executionMode = byId("execution-mode");
const statusNode = byId("status");
const resultsNode = byId("results");
const summaryCards = byId("summary-cards");
const findingsBody = byId("findings-body");
const profileBody = byId("profile-body");
const privacyList = byId("privacy-list");
const findingCount = byId("finding-count");
const severityFilter = byId("severity-filter");
const historyBody = byId("history-body");
let latestResult = null;
let activeJobId = null;
const cancelJobButton = byId("cancel-job");
const textCell = (text) => {
    const cell = document.createElement("td");
    cell.textContent = text;
    return cell;
};
const setBusy = (message, busy) => {
    statusNode.textContent = message;
    statusNode.classList.remove("error");
    for (const button of document.querySelectorAll("button")) {
        button.disabled = busy && button !== cancelJobButton;
    }
    cancelJobButton.hidden = !busy || activeJobId === null;
};
const setError = (message) => {
    statusNode.textContent = message;
    statusNode.classList.add("error");
    for (const button of document.querySelectorAll("button")) {
        button.disabled = false;
    }
};
const summaryCard = (value, label, className = "") => {
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
const renderSummary = (result) => {
    summaryCards.replaceChildren(summaryCard(result.summary.status.toUpperCase(), "Validation status", `status-${result.summary.status}`), summaryCard(result.profile.row_count.toLocaleString(), "Rows evaluated"), summaryCard(String(result.summary.critical), "Critical"), summaryCard(String(result.summary.errors), "Errors"), summaryCard(String(result.summary.warnings), "Warnings"), summaryCard(`${result.duration_ms} ms`, "Runtime"), summaryCard(result.execution_mode.toUpperCase(), "Execution mode"));
};
const renderFindings = () => {
    if (!latestResult)
        return;
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
        row.append(severityCell, ruleCell, textCell(finding.column ?? "—"), textCell(finding.message), textCell(finding.sample_rows.length ? finding.sample_rows.join(", ") : "—"));
        findingsBody.append(row);
    }
};
const renderProfile = (result) => {
    profileBody.replaceChildren();
    for (const column of result.profile.columns) {
        const row = document.createElement("tr");
        row.append(textCell(column.name), textCell(column.observed_type), textCell(String(column.null_count)), textCell(`${column.distinct_count_exact === false ? "≥" : ""}${column.distinct_count}`));
        profileBody.append(row);
    }
};
const renderPrivacy = (result) => {
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
const renderResult = (result) => {
    latestResult = result;
    resultsNode.hidden = false;
    renderSummary(result);
    renderFindings();
    renderProfile(result);
    renderPrivacy(result);
    statusNode.textContent = `${result.dataset_name}: ${result.summary.status}. ${result.summary.findings_total} finding(s).`;
    statusNode.classList.remove("error");
    for (const button of document.querySelectorAll("button")) {
        button.disabled = false;
    }
    resultsNode.scrollIntoView({ behavior: "smooth", block: "start" });
};
const parseResponse = async (response) => {
    const payload = await response.json();
    if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : `Request failed with status ${response.status}`;
        throw new Error(detail);
    }
    return payload;
};
const sleep = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
const parseJobSubmission = async (response) => {
    const payload = await response.json();
    if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : `Request failed with status ${response.status}`;
        throw new Error(detail);
    }
    return payload;
};
const waitForJob = async (jobId) => {
    const deadline = Date.now() + 5 * 60 * 1000;
    while (Date.now() < deadline) {
        const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" });
        if (!response.ok)
            throw new Error(`Job status failed with status ${response.status}`);
        const job = await response.json();
        statusNode.textContent = `${job.progress}% · ${job.message}`;
        if (job.state === "completed" && job.result)
            return job.result;
        if (job.state === "failed")
            throw new Error(job.error ?? "Validation job failed.");
        if (job.state === "cancelled")
            throw new Error("Validation job was cancelled.");
        await sleep(250);
    }
    throw new Error("Validation job exceeded the dashboard wait limit.");
};
form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!contractFile.files?.[0] || !dataFile.files?.[0]) {
        setError("Choose both a YAML contract and a dataset.");
        return;
    }
    const body = new FormData();
    body.append("contract", contractFile.files[0]);
    body.append("data", dataFile.files[0]);
    for (const reference of Array.from(referenceFiles.files ?? []))
        body.append("references", reference);
    try {
        const response = await fetch(`/api/jobs/validate?fail_on=${encodeURIComponent(failOn.value)}&execution_mode=${encodeURIComponent(executionMode.value)}`, { method: "POST", body });
        const submission = await parseJobSubmission(response);
        activeJobId = submission.job_id;
        setBusy("Queued locally…", true);
        const result = await waitForJob(submission.job_id);
        activeJobId = null;
        renderResult(result);
        cancelJobButton.hidden = true;
        await loadHistory();
    }
    catch (error) {
        activeJobId = null;
        cancelJobButton.hidden = true;
        setError(error instanceof Error ? error.message : "Validation failed.");
    }
});
const runDemo = async (scenario) => {
    setBusy(`Running ${scenario} demonstration…`, true);
    try {
        const response = await fetch(`/api/demo/${scenario}`, { method: "POST" });
        renderResult(await parseResponse(response));
        await loadHistory();
    }
    catch (error) {
        setError(error instanceof Error ? error.message : "Demo failed.");
    }
};
cancelJobButton.addEventListener("click", async () => {
    if (!activeJobId)
        return;
    cancelJobButton.disabled = true;
    try {
        await fetch(`/api/jobs/${encodeURIComponent(activeJobId)}`, { method: "DELETE" });
        statusNode.textContent = "Cancellation requested…";
    }
    finally {
        cancelJobButton.disabled = false;
    }
});
byId("demo-good").addEventListener("click", () => void runDemo("good"));
byId("demo-bad").addEventListener("click", () => void runDemo("bad"));
severityFilter.addEventListener("change", renderFindings);
byId("download-json").addEventListener("click", () => {
    if (!latestResult)
        return;
    const blob = new Blob([`${JSON.stringify(latestResult, null, 2)}\n`], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `data_contract_result_${latestResult.run_id.slice(0, 12)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
});
const loadHistory = async () => {
    try {
        const response = await fetch("/api/history?limit=20");
        if (!response.ok)
            throw new Error("History request failed");
        const entries = await response.json();
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
            row.append(textCell(new Date(entry.started_at).toLocaleString()), textCell(entry.dataset_name), textCell(entry.status.toUpperCase()), textCell(entry.row_count.toLocaleString()), textCell(String(entry.findings_total)), textCell(`${entry.duration_ms} ms`));
            historyBody.append(row);
        }
    }
    catch {
        historyBody.replaceChildren();
        const row = document.createElement("tr");
        const cell = textCell("History is unavailable.");
        cell.colSpan = 6;
        row.append(cell);
        historyBody.append(row);
    }
};
byId("refresh-history").addEventListener("click", () => void loadHistory());
void loadHistory();
