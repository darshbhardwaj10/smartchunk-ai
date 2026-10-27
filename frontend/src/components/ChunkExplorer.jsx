import React from "react";
import { EmptyState, MetricCard, SectionTitle, StatusPill } from "./Common.jsx";
import { downloadJson, downloadJsonl } from "../utils/format.js";

export default function ChunkExplorer({ result, selectedChunkIndex, setSelectedChunkIndex, onOpenQA }) {
  const chunks = result?.chunks ?? [];
  const selectedChunk = chunks[selectedChunkIndex] ?? null;
  const chunkTypes = result?.metrics?.chunk_types ?? {};
  const heading = selectedChunk?.heading_path?.length ? selectedChunk.heading_path.join(" / ") : "No heading detected";
  const stem = (result?.filename || "document").replace(/\.[^.]+$/, "").replace(/[^\w-]+/g, "_") || "document";

  return (
    <section className="panel">
      <SectionTitle
        eyebrow="OUTPUT"
        title="Chunk explorer"
        description="Inspect chunk text, source metadata and processing results."
        actions={result ? <button className="small-button" type="button" onClick={() => downloadJson(`${result.document_id}-chunks.json`, result.chunks)}>Export JSON</button> : null}
      />
      {!result ? (
        <EmptyState icon="▤" title="Your chunks will appear here">Choose a document and click Process document to generate and save a document version.</EmptyState>
      ) : (
        <>
          <div className="file-summary">
            <div><strong>{result.filename}</strong><span className="id-line">Document: {result.document_id} · Version: {result.version_id}</span></div>
            <StatusPill tone={result.version_status === "active" ? "success" : "neutral"}>{result.version_status || "saved"}</StatusPill>
          </div>
          <div className="metric-grid">
            <MetricCard label="Total chunks" value={result.metrics?.chunk_count ?? chunks.length} />
            <MetricCard label="Average characters" value={result.metrics?.average_characters ?? "—"} />
            <MetricCard label="Oversized chunks" value={result.metrics?.oversized_chunk_count ?? 0} />
            <MetricCard label="Saved version" value={result.version_id ? "Yes" : "No"} hint="Stored by the backend" />
          </div>
          {result.normalization?.warnings?.length ? (
            <div className="warning-box"><strong>Normalization warnings</strong>{result.normalization.warnings.map((warning, index) => <p key={`${warning}-${index}`}>{warning}</p>)}</div>
          ) : null}
          <div className="type-summary">
            {Object.entries(chunkTypes).map(([type, count]) => <span className="type-chip" key={type}>{type}<b>{count}</b></span>)}
          </div>
          <div className="chunk-layout">
            <div className="chunk-list" aria-label="Generated chunks">
              {chunks.map((chunk, index) => (
                <button className={`chunk-item ${selectedChunkIndex === index ? "selected" : ""}`} type="button" key={`${chunk.chunk_id}-${index}`} onClick={() => setSelectedChunkIndex(index)}>
                  <span className="chunk-number">{String(index + 1).padStart(2, "0")}</span>
                  <span className="chunk-item-copy">
                    <strong>{chunk.heading_path?.at(-1) || chunk.chunk_type || "Chunk"}</strong>
                    <small>{chunk.char_count ?? chunk.text?.length ?? 0} chars · {chunk.chunk_type || "content"}{chunk.oversized ? " · oversized" : ""}</small>
                  </span>
                  <span className="chunk-arrow">›</span>
                </button>
              ))}
              {!chunks.length ? <p className="muted">No chunks were generated.</p> : null}
            </div>
            <div className="chunk-detail">
              {selectedChunk ? (
                <>
                  <div className="detail-top"><span className="type-pill">{selectedChunk.chunk_type || "content"}</span><span className="char-count">{selectedChunk.char_count ?? selectedChunk.text?.length ?? 0} characters</span></div>
                  <h3>{selectedChunk.heading_path?.at(-1) || "Untitled section"}</h3>
                  <p className="breadcrumb">{heading}</p>
                  <pre className="text-block">{selectedChunk.text}</pre>
                  <div className="metadata-grid">
                    <span>Chunk ID</span><strong>{selectedChunk.chunk_id || "—"}</strong>
                    <span>Source file</span><strong>{selectedChunk.source?.file || result.filename}</strong>
                    <span>Location</span><strong>{selectedChunk.source?.location ?? "—"}</strong>
                    {selectedChunk.source?.page ? <><span>Page</span><strong>{selectedChunk.source.page}</strong></> : null}
                    <span>Parent ID</span><strong>{selectedChunk.parent_id || "None"}</strong>
                    <span>Boundary reason</span><strong>{selectedChunk.boundary_reason || "Not recorded by this backend version"}</strong>
                    <span>Oversized</span><strong>{selectedChunk.oversized ? "Yes" : "No"}</strong>
                    {selectedChunk.related_chunk_ids ? <><span>Related chunks</span><strong>{selectedChunk.related_chunk_ids.join(", ") || "None"}</strong></> : null}
                  </div>
                </>
              ) : <p className="muted">No chunk selected.</p>}
            </div>
          </div>
          <div className="inline-actions">
            <button className="button button-secondary" type="button" onClick={() => downloadJsonl(`${stem}-chunks.jsonl`, chunks)}>Export chunks as JSONL</button>
            <button className="button button-secondary" type="button" onClick={onOpenQA}>Ask questions about this document →</button>
          </div>
        </>
      )}
    </section>
  );
}
