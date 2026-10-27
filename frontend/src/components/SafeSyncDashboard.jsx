import React from "react";
import { CheckRow, EmptyState, SectionTitle, StatusPill } from "./Common.jsx";
import { formatBytes, formatDate } from "../utils/format.js";

const ACCEPTED_FILE_TYPES = ".txt,.md,.markdown,.html,.htm,.pdf,.docx";

export default function SafeSyncDashboard({
  file, onFileChange, documents, selectedDocumentId, setSelectedDocumentId, selectedDocument,
  strategy, setStrategy, chunkSize, setChunkSize, overlap, setOverlap, semantic, setSemantic,
  reuseDocumentId, setReuseDocumentId, candidate, candidateValidation, safeSyncStatus,
  busyAction, onPrepare, onValidate, onPublish, onRefreshStatus,
}) {
  return (
    <section className="page-grid safesync-layout">
      <div className="panel">
        <SectionTitle eyebrow="SAFESYNC" title="Prepare a candidate version" description="Prepare and validate an update without replacing the active version prematurely." />
        <form onSubmit={onPrepare} className="stacked-form">
          <label className="upload-zone">
            <input type="file" accept={ACCEPTED_FILE_TYPES} onChange={onFileChange} />
            <span className="upload-icon" aria-hidden="true">↑</span>
            <strong>{file ? file.name : "Choose updated document"}</strong>
            <small>{file ? `${formatBytes(file.size)} · Candidate source` : "Upload the revised version of a document"}</small>
          </label>
          <label className="checkbox-card">
            <input type="checkbox" checked={reuseDocumentId} onChange={(event) => setReuseDocumentId(event.target.checked)} disabled={!selectedDocumentId} />
            <span><strong>Update an existing document</strong><small>{selectedDocumentId ? `Create a candidate version for ${selectedDocument?.filename || selectedDocumentId}.` : "Process a document first to select an existing document ID."}</small></span>
          </label>
          {reuseDocumentId ? <p className="muted">Target document: {selectedDocumentId || "Select an existing document first."}</p> : null}
          <label className="field-label" htmlFor="safe-strategy">Candidate chunking strategy</label>
          <select id="safe-strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)}><option value="structure">Structure-aware</option><option value="fixed">Fixed-size baseline</option></select>
          <div className="form-grid">
            <label><span className="field-label">Chunk size</span><input type="number" min="200" max="2000" value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value))} /></label>
            <label><span className="field-label">Overlap</span><input type="number" min="0" max="400" value={overlap} onChange={(event) => setOverlap(Number(event.target.value))} /></label>
          </div>
          <label className="toggle-row"><span><strong>Semantic boundary mode</strong><small>Requires optional semantic dependencies on the backend.</small></span><input type="checkbox" checked={semantic} onChange={(event) => setSemantic(event.target.checked)} /></label>
          <button className="button button-primary" disabled={Boolean(busyAction) || !file || (reuseDocumentId && !selectedDocumentId)}>
            {busyAction === "prepare" ? "Preparing candidate…" : "Prepare candidate"}<span>→</span>
          </button>
        </form>
        {candidate ? (
          <div className="candidate-card">
            <div className="section-title-row"><div><p className="eyebrow">CANDIDATE CREATED</p><h3>{candidate.version_id}</h3></div><StatusPill tone={candidateValidation?.passed ? "success" : candidateValidation ? "danger" : "warning"}>{candidateValidation?.status || candidate.status || "candidate"}</StatusPill></div>
            <p>{candidate.message || "Candidate created. Validate it before publishing."}</p>
            <div className="metadata-grid"><span>Document ID</span><strong>{candidate.document_id}</strong><span>Version ID</span><strong>{candidate.version_id}</strong><span>Chunk count</span><strong>{candidate.chunk_count ?? "—"}</strong></div>
            <div className="inline-actions">
              <button className="button button-secondary" type="button" disabled={Boolean(busyAction)} onClick={onValidate}>{busyAction === "validate" ? "Validating…" : "Validate candidate"}</button>
              <button className="button button-primary" type="button" disabled={Boolean(busyAction) || !candidateValidation?.passed} onClick={onPublish}>{busyAction === "publish" ? "Publishing…" : "Publish validated version"}<span>→</span></button>
            </div>
            {candidateValidation ? (
              <div className="validation-report"><div className="report-title"><strong>Validation report</strong><StatusPill tone={candidateValidation.passed ? "success" : "danger"}>{candidateValidation.status}</StatusPill></div>{(candidateValidation.checks ?? []).map((check, index) => <CheckRow check={{ ...check, check: `${check.check}-${index}` }} key={`${check.check}-${index}`} />)}{candidateValidation.note ? <p className="muted">{candidateValidation.note}</p> : null}</div>
            ) : null}
          </div>
        ) : <EmptyState icon="◇" title="No candidate prepared">Upload a new version and validate it before making it active.</EmptyState>}

        <div className="divider" />
        <SectionTitle eyebrow="CURRENT VERSION" title="Active version status" description="Inspect the active version and saved version history." />
        <label className="field-label" htmlFor="safe-document">Document</label>
        <select id="safe-document" value={selectedDocumentId} onChange={(event) => setSelectedDocumentId(event.target.value)}>
          <option value="">Select document</option>
          {documents.map((doc) => <option key={doc.document_id} value={doc.document_id}>{doc.filename} · {doc.document_id.slice(-8)}</option>)}
        </select>
        <button className="button button-secondary" type="button" disabled={Boolean(busyAction) || !selectedDocumentId} onClick={onRefreshStatus}>{busyAction === "status" ? "Loading status…" : "Refresh version status"}</button>
        {safeSyncStatus ? (
          <div className="status-report">
            <div className="metadata-grid"><span>Filename</span><strong>{safeSyncStatus.document?.filename || "—"}</strong><span>Active version</span><strong>{safeSyncStatus.active_version?.version_id || "None"}</strong><span>Source hash</span><strong className="hash-text">{safeSyncStatus.active_version?.source_sha256 || "—"}</strong></div>
            <h4>Version history</h4>
            {(safeSyncStatus.versions ?? []).map((version) => (
              <div className="version-row" key={version.version_id}><div><strong>{version.version_id}</strong><small>{formatDate(version.created_at)}</small></div><StatusPill tone={version.status === "active" ? "success" : version.status === "blocked" ? "danger" : version.status === "validated" ? "success" : "neutral"}>{version.status}</StatusPill></div>
            ))}
          </div>
        ) : null}
      </div>

      <div className="panel">
        <SectionTitle eyebrow="RELEASE SAFETY" title="SafeSync validation" description="Prototype release checks; passing them does not prove factual correctness or complete production security." />
        <div className="feature-list">
          <div className="feature-row"><span className="feature-icon">01</span><div><strong>Normalized content exists</strong><p>The candidate contains non-empty normalized Markdown.</p></div></div>
          <div className="feature-row"><span className="feature-icon">02</span><div><strong>Chunks are present</strong><p>At least one non-empty chunk was generated.</p></div></div>
          <div className="feature-row"><span className="feature-icon">03</span><div><strong>Source metadata is present</strong><p>Chunks have IDs, filenames and source locations where required.</p></div></div>
          <div className="feature-row"><span className="feature-icon">04</span><div><strong>Extraction warnings reviewed</strong><p>Suspicious or incomplete PDF extraction needs human review.</p></div></div>
        </div>
        <div className="warning-box"><strong>Prototype limitation</strong><p>SafeSync validates versions in local SQLite storage. It does not automatically synchronize or delete records from an external vector store.</p></div>
      </div>
    </section>
  );
}
