import { FormEvent, useEffect, useMemo, useState } from "react";

type Range = { low: number; expected: number; high: number; unit: string };
type Contribution = { key: string; label: string; value: number; direction: "benefit" | "penalty" | "neutral"; explanation: string };
type Recommendation = {
  rank: number; label: string; confidence: number; score: number;
  score_contributions: Contribution[]; pareto_efficient: boolean; selection_flags: string[];
  configuration: { configuration_id: string; display_name: string; provider: string; model_id: string; deployment: string; settings: Record<string, unknown> };
  reasons: string[]; warnings: string[]; quality: Range; cost: Range; latency: Range;
  evidence: { title: string; url: string | null; observed_at: string }[];
};
type Result = {
  recommendation_id: string; created_at: string; advisor_version: string; catalog_version: string;
  catalog_observed_at: string; non_executing: true;
  analysis: { task_family: string; difficulty: string; estimated_input_tokens: number; uncertainty: number; assessor: { status: string; invoked: boolean; latency_ms: number; fallback_used: boolean } };
  recommendations: Recommendation[];
};
type FeedbackSettings = { feedback_enabled: boolean; personalization_enabled: boolean; personalization_policy_version: string | null; minimum_support: number };
type CatalogSummary = { catalog_version: string; observed_at: string; expires_at: string; freshness_status: string; source: string; signature_verified: boolean; configuration_count: number; providers: string[]; fallback_reason: string | null };
type FeedbackItem = { feedback_id: string; recorded_at: string; task_family: string; difficulty: string; outcome: { outcome: string; used_configuration_id: string | null } };
type PromotionAudit = { promotion_id: string; created_at: string; policy_version: string; decision: string; policy_digest: string };
type BenchmarkRun = { run_id: string; created_at: string; status: string; metrics: Record<string, number | string | boolean | null> | null };

const examples = [
  "Review this Python concurrency design and identify race conditions.",
  "Summarize a 70-page contract and return a strict JSON risk register.",
  "Write a warm two-paragraph welcome email for new customers.",
];
const objectives: Record<string, string> = { balanced: "Balanced", best_quality: "Best quality", lowest_cost: "Lowest cost", fastest: "Fastest" };
const recommendationLabels: Record<string, string> = { recommended: "Recommended", economical_alternative: "Lower-cost option", specialist_alternative: "Quality specialist", privacy_latency_alternative: "Private / fast option" };

function money(value: number) {
  return value === 0 ? "$0 provider fee" : `$${value.toFixed(value < 0.01 ? 5 : 3)}`;
}

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url}`);
  return response.json() as Promise<T>;
}

function App() {
  const [view, setView] = useState<"advisor" | "insights">("advisor");
  const [prompt, setPrompt] = useState(examples[0]);
  const [objective, setObjective] = useState("balanced");
  const [privacy, setPrivacy] = useState("no_training");
  const [assessorMode, setAssessorMode] = useState("off");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [settings, setSettings] = useState<FeedbackSettings | null>(null);
  const [catalog, setCatalog] = useState<CatalogSummary | null>(null);
  const [history, setHistory] = useState<FeedbackItem[]>([]);
  const [audit, setAudit] = useState<PromotionAudit[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchmarkRun[]>([]);
  const [benchmarking, setBenchmarking] = useState(false);

  async function refreshGovernance() {
    const [nextSettings, nextHistory, nextAudit, nextBenchmarks] = await Promise.all([
      getJson<FeedbackSettings>("/v1/feedback/settings"),
      getJson<{ items: FeedbackItem[] }>("/v1/feedback/history"),
      getJson<{ items: PromotionAudit[] }>("/v1/feedback/personalization/audit"),
      getJson<{ items: BenchmarkRun[] }>("/v1/benchmarks/runs"),
    ]);
    setSettings(nextSettings);
    setHistory(nextHistory.items);
    setAudit(nextAudit.items);
    setBenchmarks(nextBenchmarks.items);
  }

  useEffect(() => {
    void getJson<CatalogSummary>("/v1/catalog/summary").then(setCatalog).catch(() => undefined);
    void refreshGovernance().catch(() => undefined);
  }, []);

  const assessorLabel = useMemo(() => {
    if (!result) return "";
    const report = result.analysis.assessor;
    if (report.status === "completed") return `Local assessor · ${report.latency_ms.toFixed(0)} ms`;
    if (report.fallback_used) return "Deterministic fallback";
    return "Deterministic fast path";
  }, [result]);

  async function advise(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/v1/model-recommendations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [{ role: "user", content: prompt }], objective, privacy, assessor_mode: assessorMode, expected_output_tokens: 1000, required_capabilities: [], feedback_profile_id: "local-default" }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Unable to generate advice");
      setResult(body as Result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to generate advice");
    } finally { setLoading(false); }
  }

  async function updateSettings(update: Partial<FeedbackSettings>) {
    const response = await fetch("/v1/feedback/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(update) });
    const body = await response.json();
    if (response.ok) setSettings(body as FeedbackSettings);
    else setNotice(body.detail ?? "Setting could not be changed.");
  }

  async function promotePersonalization() {
    const response = await fetch("/v1/feedback/personalization/promote", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ feedback_profile_id: "local-default" }) });
    const body = await response.json();
    setNotice(body.explanation ?? "Replay could not be completed.");
    await refreshGovernance();
  }

  async function rollbackPersonalization() {
    const response = await fetch("/v1/feedback/personalization/rollback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ feedback_profile_id: "local-default" }) });
    setNotice(response.ok ? "Personalization rolled back. Deterministic advice remains active." : "Rollback failed.");
    await refreshGovernance();
  }

  async function exportFeedback() {
    const response = await fetch("/v1/feedback/export");
    download("routellect-feedback.json", await response.text(), "application/json");
  }

  function exportRecommendation(format: "json" | "markdown") {
    if (!result) return;
    if (format === "json") {
      download(`routellect-${result.recommendation_id}.json`, JSON.stringify(result, null, 2), "application/json");
      return;
    }
    const lines = ["# Routellect advisory report", "", `- Receipt: ${result.recommendation_id}`, `- Advisor: ${result.advisor_version}`, `- Catalog: ${result.catalog_version}`, `- Task: ${result.analysis.task_family} (${result.analysis.difficulty})`, "- Privacy: The raw prompt is not included in this report.", "", ...result.recommendations.flatMap((item) => [`## ${item.rank}. ${item.configuration.display_name}`, "", `Quality ${(item.quality.expected * 100).toFixed(0)}/100 · Cost ${money(item.cost.expected)} · Latency ${(item.latency.expected / 1000).toFixed(1)}s · Confidence ${(item.confidence * 100).toFixed(0)}%`, "", ...item.reasons.map((reason) => `- ${reason}`), ""] )];
    download(`routellect-${result.recommendation_id}.md`, lines.join("\n"), "text/markdown");
  }

  async function resetFeedback() {
    if (!window.confirm("Delete all locally stored feedback? This cannot be undone.")) return;
    const response = await fetch("/v1/feedback", { method: "DELETE" });
    const body = await response.json();
    setNotice(response.ok ? `Deleted ${body.deleted} local feedback item(s).` : "Reset failed.");
    await refreshGovernance();
  }

  async function sendFeedback(outcome: "worked" | "did_not_work") {
    if (!result) return;
    const response = await fetch(`/v1/model-recommendations/${result.recommendation_id}/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ used_recommendation: true, used_configuration_id: result.recommendations[0].configuration.configuration_id, outcome }) });
    setNotice(response.ok ? "Feedback saved locally — thank you." : "Feedback could not be saved.");
    if (response.ok) await refreshGovernance();
  }

  async function runBenchmark() {
    setBenchmarking(true);
    setNotice("");
    try {
      const response = await fetch("/v1/benchmarks/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      if (!response.ok) throw new Error("Benchmark could not run");
      setNotice("Local non-executing benchmark completed.");
      await refreshGovernance();
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : "Benchmark could not run."); }
    finally { setBenchmarking(false); }
  }

  const latestBenchmark = benchmarks[0];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="topbar">
        <button className="brand" type="button" onClick={() => setView("advisor")} aria-label="Routellect advisor home"><span className="brand-mark" aria-hidden="true">R</span><span>Routellect</span></button>
        <nav aria-label="Primary navigation"><button className={view === "advisor" ? "active" : ""} onClick={() => setView("advisor")}>Advisor</button><button className={view === "insights" ? "active" : ""} onClick={() => setView("insights")}>Evidence & learning</button></nav>
        <div className="privacy-note"><span className="status-dot" /> Advisory only · zero target calls</div>
      </header>

      <main id="main-content">
        {view === "advisor" ? <>
          <section className="hero">
            <p className="eyebrow">MODEL INTELLIGENCE, BEFORE INFERENCE</p>
            <h1>Know the right model<br />before you run.</h1>
            <p className="lede">Paste a prompt. Routellect weighs capability, quality, cost, speed, and privacy—then shows exactly why each option earned its place.</p>
            {catalog && <div className="trust-strip" aria-label="Catalog status"><span className={`health-dot ${catalog.freshness_status}`} /><strong>{catalog.configuration_count} configurations</strong><span>{catalog.providers.length} providers</span><span>{catalog.freshness_status} evidence</span><button type="button" onClick={() => setView("insights")}>View provenance →</button></div>}
          </section>

          <section className="workspace" aria-label="Model advisor">
            <form className="advisor-panel" onSubmit={advise}>
              <div className="field-heading"><label htmlFor="prompt">What are you trying to accomplish?</label><span>{prompt.length.toLocaleString()} characters</span></div>
              <textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={200000} required />
              <div className="examples" aria-label="Example prompts">{examples.map((example, index) => <button type="button" key={example} onClick={() => setPrompt(example)}>Example {index + 1}</button>)}</div>
              <fieldset><legend>Optimize for</legend><div className="segmented four">{Object.entries(objectives).map(([value, label]) => <label key={value} className={objective === value ? "active" : ""}><input type="radio" name="objective" value={value} checked={objective === value} onChange={() => setObjective(value)} />{label}</label>)}</div></fieldset>
              <div className="two-columns">
                <label className="select-field">Privacy<select value={privacy} onChange={(event) => setPrivacy(event.target.value)}><option value="standard">Standard</option><option value="no_training">No training · recommended</option><option value="local_only">Local only</option></select></label>
                <label className="select-field">Local assessor<select value={assessorMode} onChange={(event) => setAssessorMode(event.target.value)}><option value="auto">Auto · experimental</option><option value="always">Always</option><option value="off">Off · default</option></select></label>
              </div>
              <button className="primary-action" disabled={loading || !prompt.trim()}>{loading ? "Analyzing locally…" : "Advise me"}<span aria-hidden="true">→</span></button>
              <p className="form-footnote">Processed in memory. Your prompt is not saved or sent to a target model.</p>
              {error && <div className="error" role="alert">{error}</div>}
            </form>

            <aside className={`results-panel ${result ? "has-result" : ""}`} aria-live="polite" aria-busy={loading}>
              {!result ? <div className="empty-state"><div className="radar" aria-hidden="true"><i /><i /><i /><span>R</span></div><h2>Your recommendation will appear here</h2><p>One clear choice, a cost alternative, a protected quality specialist, and the evidence behind each.</p></div> :
              <div className="result-content">
                <div className="result-kicker"><span>Decision receipt</span><span>{assessorLabel}</span></div>
                <div className="analysis-row"><span>{result.analysis.task_family}</span><span>{result.analysis.difficulty}</span><span>≈ {result.analysis.estimated_input_tokens} tokens</span><span>{Math.round((1 - result.analysis.uncertainty) * 100)}% prompt clarity</span></div>
                {result.recommendations.map((item, index) => <article className={`model-card ${index === 0 ? "winner" : ""}`} key={item.configuration.configuration_id}>
                  <div className="card-top"><div><span className="card-label">{recommendationLabels[item.label] ?? item.label}</span><h2>{item.configuration.display_name}</h2><p>{item.configuration.provider} · {item.configuration.deployment} {item.pareto_efficient && <span className="pareto-badge">Pareto-efficient</span>}</p></div><strong>{Math.round(item.confidence * 100)}%<small> confidence</small></strong></div>
                  <div className="metrics"><div><small>QUALITY</small><b>{Math.round(item.quality.expected * 100)}</b><span>/100 catalog prior</span></div><div><small>COST</small><b>{money(item.cost.expected)}</b><span>estimated request</span></div><div><small>LATENCY</small><b>{(item.latency.expected / 1000).toFixed(1)}s</b><span>catalog estimate</span></div></div>
                  {index === 0 && <ul>{item.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
                  <details><summary>{index === 0 ? "Why this ranked here" : "Score explanation"}</summary><div className="contributions">{item.score_contributions.map((part) => <div key={part.key}><span>{part.label}</span><b className={part.direction}>{part.value >= 0 ? "+" : ""}{part.value.toFixed(3)}</b><small>{part.explanation}</small></div>)}</div><p className="score-total">Total score <strong>{item.score.toFixed(3)}</strong></p>{item.warnings.map((warning) => <p className="warning" key={warning}>{warning}</p>)}{item.evidence.map((evidence) => evidence.url && <a key={evidence.url} href={evidence.url} target="_blank" rel="noreferrer">{evidence.title} ↗</a>)}</details>
                </article>)}
                <section className="comparison" aria-labelledby="comparison-title"><div className="section-heading"><div><span className="card-label">TRADE-OFF VIEW</span><h2 id="comparison-title">Compare the shortlist</h2></div><div className="export-actions"><button onClick={() => exportRecommendation("markdown")}>Export report</button><button onClick={() => exportRecommendation("json")}>JSON</button></div></div><div className="comparison-scroll"><table><thead><tr><th>Configuration</th><th>Quality ↑</th><th>Cost ↓</th><th>Latency ↓</th></tr></thead><tbody>{result.recommendations.map((item) => <tr key={item.configuration.configuration_id}><th>{item.configuration.display_name}</th><td><span className="bar"><i style={{ width: `${item.quality.expected * 100}%` }} /></span>{Math.round(item.quality.expected * 100)}</td><td>{money(item.cost.expected)}</td><td>{(item.latency.expected / 1000).toFixed(1)}s</td></tr>)}</tbody></table></div></section>
                {settings?.feedback_enabled && <div className="feedback-box"><span>Did the recommendation work?</span><button onClick={() => void sendFeedback("worked")}>Yes</button><button onClick={() => void sendFeedback("did_not_work")}>Not this time</button></div>}
                {notice && <p className="notice" role="status">{notice}</p>}
                <footer className="receipt">{result.advisor_version} · Catalog {result.catalog_version} · {catalog?.signature_verified ? "signature verified" : "offline builtin"} · No target execution</footer>
              </div>}
            </aside>
          </section>
        </> : <>
          <section className="insights-hero"><p className="eyebrow">EVIDENCE & LEARNING</p><h1>Trust should be inspectable.</h1><p className="lede">See what the advisor knows, what it measured, and whether private feedback is allowed to influence future suggestions.</p></section>
          <section className="insights-grid">
            <article className="insight-card catalog-card"><div className="section-heading"><div><span className="card-label">CATALOG HEALTH</span><h2>{catalog?.catalog_version ?? "Loading…"}</h2></div><span className={`status-pill ${catalog?.freshness_status}`}>{catalog?.freshness_status ?? "unknown"}</span></div>{catalog && <><dl><div><dt>Configurations</dt><dd>{catalog.configuration_count}</dd></div><div><dt>Providers</dt><dd>{catalog.providers.length}</dd></div><div><dt>Source</dt><dd>{catalog.source.replace("_", " ")}</dd></div><div><dt>Signature</dt><dd>{catalog.signature_verified ? "Verified" : "Bundled snapshot"}</dd></div></dl><p>Observed {new Date(catalog.observed_at).toLocaleDateString()} · expires {new Date(catalog.expires_at).toLocaleDateString()}</p>{catalog.fallback_reason && <p className="warning">{catalog.fallback_reason}</p>}</>}</article>
            <article className="insight-card learning-card"><div className="section-heading"><div><span className="card-label">PRIVATE LEARNING</span><h2>{settings?.personalization_enabled ? "Active" : "Deterministic"}</h2></div><span className={`status-pill ${settings?.personalization_enabled ? "active" : "neutral"}`}>{settings?.personalization_enabled ? settings.personalization_policy_version : "off by default"}</span></div><p>Only structured outcomes are stored. Prompts and free text never enter the feedback dataset.</p>{settings && <div className="control-stack"><label><input type="checkbox" checked={settings.feedback_enabled} onChange={(event) => void updateSettings({ feedback_enabled: event.target.checked })} /> Collect local structured outcomes</label><p>At least {settings.minimum_support} matching outcomes are needed before a signal can affect a score.</p><div className="action-row"><button onClick={() => void promotePersonalization()} disabled={!settings.feedback_enabled}>Replay & promote</button><button onClick={() => void rollbackPersonalization()} disabled={!settings.personalization_enabled}>Rollback</button><button onClick={() => void exportFeedback()}>Export</button><button className="danger-link" onClick={() => void resetFeedback()}>Reset</button></div></div>}</article>
            <article className="insight-card benchmark-card"><div className="section-heading"><div><span className="card-label">LOCAL BENCHMARK</span><h2>Decision integrity</h2></div><button className="small-primary" onClick={() => void runBenchmark()} disabled={benchmarking}>{benchmarking ? "Running…" : "Run benchmark"}</button></div>{latestBenchmark?.metrics ? <dl className="benchmark-metrics"><div><dt>Task classification</dt><dd>{Math.round(Number(latestBenchmark.metrics.task_family_accuracy) * 100)}%</dd></div><div><dt>Pareto-safe primary</dt><dd>{Math.round(Number(latestBenchmark.metrics.primary_pareto_rate) * 100)}%</dd></div><div><dt>Specialist coverage</dt><dd>{Math.round(Number(latestBenchmark.metrics.specialist_shortlist_coverage) * 100)}%</dd></div><div><dt>P95 advisory latency</dt><dd>{Number(latestBenchmark.metrics.advisor_latency_p95_ms).toFixed(1)} ms</dd></div></dl> : <p>No local benchmark run yet. This fixture validates software behavior; it does not claim universal model quality.</p>}{latestBenchmark && <p className="muted">Latest: {new Date(latestBenchmark.created_at).toLocaleString()} · zero target-provider calls</p>}</article>
            <article className="insight-card history-card"><div className="section-heading"><div><span className="card-label">FEEDBACK HISTORY</span><h2>{history.length} local outcomes</h2></div><span className="privacy-chip">Prompts excluded</span></div>{history.length ? <div className="history-list">{history.slice(0, 8).map((item) => <div key={item.feedback_id}><span className={`outcome ${item.outcome.outcome}`}>{item.outcome.outcome === "worked" ? "Worked" : "Did not work"}</span><strong>{item.task_family}</strong><small>{item.difficulty} · {new Date(item.recorded_at).toLocaleDateString()}</small></div>)}</div> : <p>No outcomes yet. Use an advisory and tell Routellect whether it worked.</p>}</article>
            <article className="insight-card audit-card"><div className="section-heading"><div><span className="card-label">PROMOTION AUDIT</span><h2>Every decision leaves a receipt</h2></div></div>{audit.length ? <div className="audit-list">{audit.slice(0, 8).map((item) => <div key={item.promotion_id}><span className={`status-pill ${item.decision}`}>{item.decision.replace("_", " ")}</span><strong>{item.policy_version}</strong><code>{item.policy_digest.slice(0, 12)}…</code><small>{new Date(item.created_at).toLocaleString()}</small></div>)}</div> : <p>No promotion attempts yet.</p>}</article>
          </section>
          {notice && <p className="global-notice" role="status">{notice}</p>}
        </>}
      </main>
    </div>
  );
}

export default App;
