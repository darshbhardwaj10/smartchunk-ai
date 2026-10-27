import React from "react";
import { formatBytes } from "../utils/format.js";
import { SectionTitle } from "./Common.jsx";

const ACCEPTED_FILE_TYPES = ".txt,.md,.markdown,.html,.htm,.pdf,.docx";

export default function DocumentUpload({
  file,
  onFileChange,
  strategy,
  setStrategy,
  chunkSize,
  setChunkSize,
  overlap,
  setOverlap,
  semantic,
  setSemantic,
  busyAction,
  onProcess,
  onPreview,
  onBenchmark,
}) {
  return (
    <aside className="panel controls-panel">
      <SectionTitle eyebrow="DOCUMENT STUDIO" title="Process a document" description="Normalize, chunk and inspect a source file." />
      <label className="upload-zone">
        <input type="file" accept={ACCEPTED_FILE_TYPES} onChange={onFileChange} />
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
          <span className="field-label">Chunk size (characters)</span>
          <input type="number" min="200" max="2000" step="50" value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value))} />
        </label>
        <label>
          <span className="field-label">Overlap (characters)</span>
          <input type="number" min="0" max="400" step="10" value={overlap} onChange={(event) => setOverlap(Number(event.target.value))} />
        </label>
      </div>

      <label className="toggle-row">
        <span><strong>Semantic boundary mode</strong><small>Optional embeddings. Install the semantic dependencies and model before enabling.</small></span>
        <input type="checkbox" checked={semantic} onChange={(event) => setSemantic(event.target.checked)} />
      </label>

      <div className="button-stack">
        <button className="button button-primary" type="button" disabled={Boolean(busyAction) || !file} onClick={onProcess}>
          {busyAction === "process" ? "Processing…" : "Process document"}<span>→</span>
        </button>
        <button className="button button-secondary" type="button" disabled={Boolean(busyAction) || !file} onClick={onPreview}>
          {busyAction === "normalize" ? "Normalizing…" : "Preview normalized Markdown"}
        </button>
        <button className="button button-secondary" type="button" disabled={Boolean(busyAction) || !file} onClick={onBenchmark}>
          {busyAction === "benchmark" ? "Benchmarking…" : "Compare against baseline"}
        </button>
      </div>
      <p className="fine-print">Use non-sensitive test files. Processed document versions are stored in the backend's local SQLite database.</p>
    </aside>
  );
}
