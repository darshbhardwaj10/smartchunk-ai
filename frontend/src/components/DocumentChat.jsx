import React from "react";
import { EmptyState, SectionTitle, StatusPill } from "./Common.jsx";
import { formatDate } from "../utils/format.js";

export default function DocumentChat({
  documents,
  selectedDocumentId,
  setSelectedDocumentId,
  selectedDocument,
  question,
  setQuestion,
  topK,
  setTopK,
  qaHistory,
  setQaHistory,
  busyAction,
  onAsk,
}) {
  const readyForQA = Boolean(selectedDocument?.active_version_id);
  return (
    <section className="page-grid qa-layout">
      <div className="panel">
        <SectionTitle eyebrow="DOCUMENT Q&A" title="Ask your document" description="Answers use retrieved evidence from the selected document's active version." />
        <label className="field-label" htmlFor="qa-document">Document</label>
        <select id="qa-document" value={selectedDocumentId} onChange={(event) => { setSelectedDocumentId(event.target.value); setQaHistory([]); }}>
          <option value="">Select a processed document</option>
          {documents.map((doc) => <option key={doc.document_id} value={doc.document_id}>{doc.filename} · {doc.document_id.slice(-8)}</option>)}
        </select>
        {selectedDocument ? (
          <div className="document-meta-card">
            <strong>{selectedDocument.filename}</strong>
            <span>Active version: {selectedDocument.active_version_id || "No active version"}</span>
            <span>Updated: {formatDate(selectedDocument.updated_at)}</span>
          </div>
        ) : null}
        {!readyForQA && selectedDocumentId ? <div className="warning-box"><strong>No active version</strong><p>Process and publish a document version before asking questions about it.</p></div> : null}
        <div className="form-grid">
          <label><span className="field-label">Retrieved chunks (top-k)</span><input type="number" min="1" max="10" value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></label>
          <div className="setting-explainer"><span className="field-label">Answer source</span><p>Only chunks from the selected document's active version are used as evidence.</p></div>
        </div>
        <form onSubmit={onAsk} className="question-form">
          <label className="field-label" htmlFor="qa-question">Your question</label>
          <textarea id="qa-question" rows="4" maxLength="4000" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question answered by this document…" />
          <button className="button button-primary" disabled={Boolean(busyAction) || !readyForQA || !question.trim()}>
            {busyAction === "qa" ? "Finding evidence…" : "Ask question"}<span>→</span>
          </button>
        </form>
        <p className="fine-print">Without a configured LLM API key, the backend returns an explicitly labelled extractive fallback. Check the answer mode on each result.</p>
      </div>

      <div className="panel conversation-panel">
        <SectionTitle eyebrow="ANSWERS & EVIDENCE" title="Document conversation" description="Answers include source citations or an insufficient-evidence result." actions={qaHistory.length ? <button className="small-button" type="button" onClick={() => setQaHistory([])}>Clear conversation</button> : null} />
        {!qaHistory.length ? (
          <EmptyState icon="?" title="Ask your first question">Choose a processed document, ask a question, and inspect the evidence used for the answer.</EmptyState>
        ) : (
          <div className="conversation-list">
            {qaHistory.map((item, index) => (
              <article className="conversation-turn" key={`${index}-${item.question}`}>
                <div className="user-question"><span className="message-role">YOU</span><p>{item.question}</p></div>
                <div className="assistant-answer">
                  <div className="answer-heading">
                    <span className="message-role">SMARTCHUNK</span>
                    <StatusPill tone={item.status === "answered" ? "success" : "warning"}>{item.status === "answered" ? "Answer" : "Insufficient evidence"}</StatusPill>
                  </div>
                  <p className="answer-text">{item.answer}</p>
                  <div className="answer-meta"><span>Mode: {item.answer_mode || "unknown"}</span><span>Version: {item.version_id || "—"}</span></div>
                  {item.message ? <p className="muted small-note">{item.message}</p> : null}
                  {item.citations?.length ? (
                    <div className="citation-list">
                      <strong>Sources</strong>
                      {item.citations.map((citation) => (
                        <div className="citation-card" key={`${citation.chunk_id}-${citation.source}`}>
                          <div><strong>{citation.source || "Source document"}</strong><span>{citation.chunk_id}</span></div>
                          <small>{citation.page ? `Page ${citation.page} · ` : ""}{citation.location || "Location not recorded"}</small>
                          {citation.heading_path?.length ? <small>{citation.heading_path.join(" / ")}</small> : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {item.retrieved_chunks?.length ? (
                    <details className="evidence-details">
                      <summary>Inspect retrieved evidence ({item.retrieved_chunks.length} chunks)</summary>
                      {item.retrieved_chunks.map((chunk) => (
                        <article className="evidence-chunk" key={chunk.chunk_id}>
                          <div><strong>{chunk.chunk_id}</strong><span>Score: {Number(chunk.retrieval_score ?? 0).toFixed(3)}</span></div>
                          {chunk.heading_path?.length ? <p className="breadcrumb">{chunk.heading_path.join(" / ")}</p> : null}
                          <p>{chunk.text}</p>
                        </article>
                      ))}
                    </details>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
