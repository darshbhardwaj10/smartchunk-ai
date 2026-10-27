import React from "react";
import { EmptyState, MetricCard, SectionTitle } from "./Common.jsx";

function ChunkColumn({ title, tone, chunks }) {
  return (
    <div className={`comparison-panel comparison-${tone}`}>
      <div className="comparison-heading"><strong>{title}</strong><span>{chunks.length} chunks</span></div>
      <div className="comparison-chunks">
        {chunks.map((chunk, index) => (
          <article className="comparison-chunk" key={`${chunk.chunk_id ?? title}-${index}`}>
            <div className="comparison-chunk-meta">
              <strong>{chunk.chunk_id || `chunk_${index + 1}`}</strong>
              <span>{chunk.chunk_type || "content"} · {chunk.char_count ?? chunk.text?.length ?? 0} chars</span>
            </div>
            {chunk.heading_path?.length ? <p className="comparison-heading-path">{chunk.heading_path.join(" / ")}</p> : null}
            <pre>{chunk.text}</pre>
          </article>
        ))}
        {!chunks.length ? <p className="muted">No chunks in this result.</p> : null}
      </div>
    </div>
  );
}

export default function BenchmarkDashboard({ benchmark }) {
  return (
    <section className="panel benchmark-panel">
      <SectionTitle eyebrow="EVALUATION" title="Baseline benchmark" description="Both strategies process the same normalized document with the same configured chunk size and overlap." />
      {!benchmark ? (
        <EmptyState icon="⇄" title="No benchmark run yet">Choose a file and select Compare against baseline. Benchmarking runs separately from normal document processing.</EmptyState>
      ) : (
        <>
          <div className="metric-grid">
            <MetricCard label="Baseline chunks" value={benchmark.baseline?.chunk_count ?? benchmark.baseline_chunks?.length ?? 0} />
            <MetricCard label="SmartChunk chunks" value={benchmark.smartchunk?.chunk_count ?? benchmark.smartchunk_chunks?.length ?? 0} />
            <MetricCard label="Baseline avg. chars" value={benchmark.baseline?.average_characters ?? "—"} />
            <MetricCard label="SmartChunk avg. chars" value={benchmark.smartchunk?.average_characters ?? "—"} />
          </div>
          <div className="metric-grid">
            <MetricCard label="Baseline oversized" value={benchmark.baseline?.oversized_chunk_count ?? 0} />
            <MetricCard label="SmartChunk oversized" value={benchmark.smartchunk?.oversized_chunk_count ?? 0} />
            <MetricCard label="Baseline duplicate rate" value={`${Math.round((benchmark.baseline?.duplicate_rate ?? 0) * 100)}%`} />
            <MetricCard label="SmartChunk duplicate rate" value={`${Math.round((benchmark.smartchunk?.duplicate_rate ?? 0) * 100)}%`} />
          </div>
          <div className="comparison-grid">
            <ChunkColumn title="Fixed-size baseline" tone="baseline" chunks={benchmark.baseline_chunks ?? []} />
            <ChunkColumn title="SmartChunk structure-aware" tone="smartchunk" chunks={benchmark.smartchunk_chunks ?? []} />
          </div>
          {benchmark.note ? <p className="fine-print">{benchmark.note}</p> : <p className="fine-print">These chunk-shape measurements do not directly establish retrieval or answer accuracy.</p>}
        </>
      )}
    </section>
  );
}
