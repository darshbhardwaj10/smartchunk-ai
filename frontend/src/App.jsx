import { useEffect, useMemo, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const ACCEPTED_FILE_TYPES = ".txt,.md,.html,.htm,.pdf,.docx";

function MetricCard({ label, value, hint }) {
  return (
    <div className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function errorMessage(error) {
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}

export default function App() {
  const [file, setFile] = useState(null);
  const [strategy, setStrategy] = useState("structure");
  const [chunkSize, setChunkSize] = useState(700);
  const [overlap, setOverlap] = useState(80);
  const [semantic, setSemantic] = useState(false);
  const [result, setResult] = useState(null);
  const [benchmark, setBenchmark] = useState(null);
  const [normalizePreview, setNormalizePreview] = useState(null);
  const [selectedChunkIndex, setSelectedChunkIndex] = useState(0);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");
  const [health, setHealth] = useState({ state: "checking", message: "Checking backend…" });

  useEffect(() => {
    let alive = true;
    fetch(`${API_BASE}/health`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Backend responded with HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (alive) setHealth({ state: "online", message: data.status === "ok" ? "Backend connected" : "Backend response received" });
      })
      .catch(() => {
        if (alive) setHealth({ state: "offline", message: "Backend offline — start FastAPI" });
      });
    return () => { alive = false; };
  }, []);

  const chunks = result?.chunks ?? [];
  const selectedChunk = chunks[selectedChunkIndex] ?? null;
  const chunkTypes = result?.metrics?.chunk_types ?? {};
  const selectedHeading = useMemo(() => {
    if (!selectedChunk) return "No chunk selected";
    return selectedChunk.heading_path?.length ? selectedChunk.heading_path.join(" / ") : "No heading detected";
  }, [selectedChunk]);

  function onSelectFile(event) {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setResult(null);
    setBenchmark(null);
    setNormalizePreview(null);
    setSelectedChunkIndex(0);
    setError("");
  }

  function validateInputs() {
    if (!file) return "Choose a document first.";
    if (!Number.isInteger(Number(chunkSize)) || chunkSize < 200 || chunkSize > 2000) {
      return "Chunk size must be an integer between 200 and 2000 characters.";
    }
    if (!Number.isInteger(Number(overlap)) || overlap < 0 || overlap > 400 || overlap >= chunkSize) {
      return "Overlap must be an integer between 0 and 400, and smaller than chunk size.";
    }
    return "";
  }

  async function postFile(endpoint, fields = {}) {
    const body = new FormData();
    body.append("file", file);
    for (const [key, value] of Object.entries(fields)) {
      body.append(key, String(value));
    }
    const response = await fetch(`${API_BASE}${endpoint}`, { method: "POST", body });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof payload.detail === "string" ? payload.detail : `Request failed with HTTP ${response.status}.`;
      throw new Error(detail);
    }
    return payload;
  }

  async function processDocument() {
    const validation = validateInputs();
    if (validation) { setError(validation); return; }
    setBusyAction("process");
    setError("");
    setBenchmark(null);
    setNormalizePreview(null);
    setResult(null);
    setSelectedChunkIndex(0);
    try {
      const payload = await postFile("/process", {
        strategy,
        chunk_size: chunkSize,
        overlap,
        semantic,
      });
      setResult(payload);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyAction("");
    }
  }

  async function runBenchmark() {
    const validation = validateInputs();
    if (validation) { setError(validation); return; }
    setBusyAction("benchmark");
    setError("");
    try {
      const payload = await postFile("/benchmark", { chunk_size: chunkSize, overlap });
      setBenchmark(payload);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyAction("");
    }
  }

  async function previewNormalization() {
    if (!file) { setError("Choose a document first."); return; }
    setBusyAction("normalize");
    setError("");
    try {
      setNormalizePreview(await postFile("/normalize"));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyAction("");
    }
  }

  function exportJsonl() {
    if (!chunks.length) return;
    const text = `${chunks.map((chunk) => JSON.stringify(chunk)).join("\n")}\n`;
    const blob = new Blob([text], { type: "application/x-ndjson;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const stem = (file?.name || "document").replace(/\.[^.]+$/, "").replace(/[^\w-]+/g, "_");
    anchor.href = url;
    anchor.download = `${stem || "document"}-chunks.jsonl`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  const isBusy = Boolean(busyAction);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">SC</div>
        <div className="brand-copy">
          <p className="eyebrow">STRUCTURE-AWARE RAG PREPROCESSOR</p>
          <h1>SmartChunk <span>AI</span></h1>
        </div>
        <div className={`connection connection-${health.state}`} role="status">
          <span className="status-dot" />{health.message}
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow">DOCUMENT INGESTION · NORMALIZATION · CHUNKING</p>
        <h2>Keep document context<br />together, not just characters.</h2>
        <p className="hero-copy">Normalize supported documents into Markdown, inspect structure-aware chunks, compare a fixed-size baseline, and export metadata-rich JSONL.</p>
        <div className="pipeline-chips" aria-label="Processing steps">
          <span>01&nbsp; Normalize</span><b aria-hidden="true">→</b><span>02&nbsp; Chunk</span><b aria-hidden="true">→</b><span>03&nbsp; Evaluate</span>
        </div>
      </section>

      <section className="workspace">
        <aside className="panel controls-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">WORKSPACE</p><h3>Process a document</h3></div>
            <span className="step-label">STEP 01</span>
          </div>

          <label className="upload-zone">
            <input type="file" accept={ACCEPTED_FILE_TYPES} onChange={onSelectFile} />
            <span className="upload-icon" aria-hidden="true">↑</span>
            <strong>{file ? file.name : "Choose a document"}</strong>
            <small>{file ? `${formatBytes(file.size)} · Ready to process` : "TXT, Markdown, HTML, PDF, or DOCX · Max 10 MB"}</small>
          </label>

          <label className="field-label" htmlFor="strategy">Chunking strategy</label>
          <select id="strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)}>
            <option value="structure">SmartChunk — structure-aware</option>
            <option value="fixed">Baseline — fixed-size</option>
          </select>

          <div className="form-grid">
            <label>
              <span className="field-label">Chunk size (chars)</span>
              <input type="number" min="200" max="2000" step="50" value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value))} />
            </label>
            <label>
              <span className="field-label">Overlap (chars)</span>
              <input type="number" min="0" max="400" step="10" value={overlap} onChange={(event) => setOverlap(Number(event.target.value))} />
            </label>
          </div>

          <label className="toggle-row">
            <span><strong>Semantic boundary mode</strong><small>Optional embeddings; requires extra dependencies and a model download.</small></span>
            <input type="checkbox" checked={semantic} onChange={(event) => setSemantic(event.target.checked)} />
          </label>

          <button className="button button-primary" type="button" disabled={isBusy || !file} onClick={processDocument}>
            {busyAction === "process" ? "Processing…" : "Process document"}<span aria-hidden="true">→</span>
          </button>
          <button className="button button-secondary" type="button" disabled={isBusy || !file} onClick={previewNormalization}>
            {busyAction === "normalize" ? "Normalizing…" : "Preview normalized Markdown"}
          </button>
          <button className="button button-secondary" type="button" disabled={isBusy || !file} onClick={runBenchmark}>
            {busyAction === "benchmark" ? "Benchmarking…" : "Compare against baseline"}
          </button>

          {error ? <div className="error-box" role="alert">{error}</div> : null}
          <p className="fine-print">This prototype sends the selected document to your configured backend. Use non-sensitive test documents during the hackathon.</p>
        </aside>

        <div className="results-column">
          <section className="panel result-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">OUTPUT</p><h3>Chunk explorer</h3></div>
              <span className="step-label">STEP 02</span>
            </div>

            {!result ? (
              <div className="empty-state">
                <div className="empty-icon" aria-hidden="true">▤</div>
                <strong>Your chunks will appear here</strong>
                <p>Choose a document and process it to inspect chunk text, heading paths, source metadata, and content types.</p>
              </div>
            ) : (
              <>
                <div className="file-summary">
                  <strong>{result.filename}</strong>
                  <span>{result.normalization?.source_format || "unknown format"} → {result.normalization?.intermediate_format || "markdown"}</span>
                </div>
                <div className="metric-grid">
                  <MetricCard label="Total chunks" value={result.metrics.chunk_count} />
                  <MetricCard label="Average chars" value={result.metrics.average_characters} />
                  <MetricCard label="Oversized chunks" value={result.metrics.oversized_chunk_count ?? 0} />
                </div>
                {result.normalization?.warnings?.length ? <div className="warning-box"><strong>Extraction warnings</strong>{result.normalization.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div> : null}
                <div className="type-summary" aria-label="Chunk types">
                  {Object.entries(chunkTypes).map(([type, count]) => <span className="type-chip" key={type}>{type}<b>{count}</b></span>)}
                </div>
                <div className="chunk-layout">
                  <div className="chunk-list" aria-label="Generated chunks">
                    {chunks.map((chunk, index) => (
                      <button className={`chunk-item ${selectedChunkIndex === index ? "selected" : ""}`} type="button" key={chunk.chunk_id} onClick={() => setSelectedChunkIndex(index)}>
                        <span className="chunk-number">{String(index + 1).padStart(2, "0")}</span>
                        <span className="chunk-item-copy"><strong>{chunk.heading_path?.at(-1) || chunk.chunk_type}</strong><small>{chunk.char_count} chars · {chunk.chunk_type}{chunk.oversized ? " · oversized" : ""}</small></span>
                        <span className="chunk-arrow" aria-hidden="true">›</span>
                      </button>
                    ))}
                    {!chunks.length ? <p className="muted">No chunks were generated.</p> : null}
                  </div>
                  <div className="chunk-detail">
                    {selectedChunk ? (
                      <>
                        <div className="detail-top"><span className="type-pill">{selectedChunk.chunk_type}</span><span className="char-count">{selectedChunk.char_count} characters</span></div>
                        <h4>{selectedChunk.heading_path?.at(-1) || "Untitled section"}</h4>
                        <p className="breadcrumb">{selectedHeading}</p>
                        <pre>{selectedChunk.text}</pre>
                        <div className="metadata-grid">
                          <span>Source file</span><strong>{selectedChunk.source?.file}</strong>
                          <span>Location</span><strong>{selectedChunk.source?.location}</strong>
                          {selectedChunk.source?.page ? <><span>Page</span><strong>{selectedChunk.source.page}</strong></> : null}
                          <span>Parent ID</span><strong>{selectedChunk.parent_id || "None"}</strong>
                          <span>Oversized</span><strong>{selectedChunk.oversized ? "Yes (kept intact)" : "No"}</strong>
                        </div>
                      </>
                    ) : <p className="muted">No chunk selected.</p>}
                  </div>
                </div>
                <button className="button button-secondary export-button" type="button" disabled={!chunks.length} onClick={exportJsonl}>↓ Export chunks as JSONL</button>
              </>
            )}
          </section>

          {normalizePreview ? (
            <section className="panel">
              <div className="panel-heading"><div><p className="eyebrow">NORMALIZATION</p><h3>Markdown preview</h3></div><span className="step-label">INTERMEDIATE</span></div>
              <p className="muted">{normalizePreview.filename} · {normalizePreview.normalization?.normalized_character_count} normalized characters{normalizePreview.preview_truncated ? " · preview truncated" : ""}</p>
              {normalizePreview.normalization?.warnings?.map((warning) => <div className="warning-box" key={warning}>{warning}</div>)}
              <pre className="markdown-preview">{normalizePreview.markdown_preview}</pre>
            </section>
          ) : null}

          <section className="panel benchmark-panel">
            <div className="panel-heading"><div><p className="eyebrow">EVALUATION</p><h3>Baseline benchmark</h3></div><span className="step-label">STEP 03</span></div>
            {!benchmark ? <p className="muted">Run “Compare against baseline” to calculate metrics for the same document using both strategies.</p> : (
              <>
                <div className="benchmark-grid">
                  <div className="benchmark-card"><span>FIXED-SIZE BASELINE</span><strong>{benchmark.baseline.chunk_count} chunks</strong><small>Average {benchmark.baseline.average_characters} chars</small><div className="bar-track"><i style={{ width: `${Math.min(100, benchmark.baseline.average_characters / Math.max(1, chunkSize) * 100)}%` }} /></div></div>
                  <div className="benchmark-card smart-card"><span>SMARTCHUNK</span><strong>{benchmark.smartchunk.chunk_count} chunks</strong><small>Average {benchmark.smartchunk.average_characters} chars</small><div className="bar-track"><i style={{ width: `${Math.min(100, benchmark.smartchunk.average_characters / Math.max(1, chunkSize) * 100)}%` }} /></div></div>
                </div>
                <div className="comparison-table-wrap">
                  <table className="comparison-table"><thead><tr><th>Metric</th><th>Baseline</th><th>SmartChunk</th></tr></thead><tbody>
                    <tr><td>Min characters</td><td>{benchmark.baseline.min_characters}</td><td>{benchmark.smartchunk.min_characters}</td></tr>
                    <tr><td>Max characters</td><td>{benchmark.baseline.max_characters}</td><td>{benchmark.smartchunk.max_characters}</td></tr>
                    <tr><td>Oversized chunks</td><td>{benchmark.baseline.oversized_chunk_count}</td><td>{benchmark.smartchunk.oversized_chunk_count}</td></tr>
                    <tr><td>Duplicate rate</td><td>{(benchmark.baseline.duplicate_rate * 100).toFixed(1)}%</td><td>{(benchmark.smartchunk.duplicate_rate * 100).toFixed(1)}%</td></tr>
                  </tbody></table>
                </div>
                <p className="benchmark-note">{benchmark.note}</p>
              </>
            )}
          </section>
        </div>
      </section>
      <footer><span>SMARTCHUNK AI</span><span>Hackathon prototype · Normalize → Chunk → Evaluate</span></footer>
    </main>
  );
}
