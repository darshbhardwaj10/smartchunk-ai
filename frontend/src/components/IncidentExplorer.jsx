import React from "react";
import { CheckRow, EmptyState, SectionTitle, StatusPill, MetricCard } from "./Common.jsx";
import { downloadJson, formatDate } from "../utils/format.js";

export default function IncidentExplorer({
  documents,
  incidentDocumentId,
  setIncidentDocumentId,
  incidentVersions,
  incidentVersionId,
  setIncidentVersionId,
  incidentType,
  setIncidentType,
  incidentSummary,
  setIncidentSummary,
  incidentQuestion,
  setIncidentQuestion,
  requiredTerms,
  setRequiredTerms,
  forbiddenTerms,
  setForbiddenTerms,
  incidents,
  selectedIncident,
  incidentReplay,
  busyAction,
  onCreateIncident,
  onRefreshIncidents,
  onOpenIncident,
  onReplayIncident,
}) {
  return (
    <section className="page-grid incident-layout">
      <div className="panel">
        <SectionTitle eyebrow="INCIDENT REPLAY" title="Create a replayable test" description="Record a known failure or regression against a saved document version." />
        <form onSubmit={onCreateIncident} className="stacked-form">
          <label className="field-label" htmlFor="incident-doc">Document</label>
          <select id="incident-doc" value={incidentDocumentId} onChange={(event) => setIncidentDocumentId(event.target.value)}>
            <option value="">Choose a document</option>
            {documents.map((doc) => <option value={doc.document_id} key={doc.document_id}>{doc.filename} · {doc.document_id.slice(-8)}</option>)}
          </select>
          <label className="field-label" htmlFor="incident-version">Version</label>
          <select id="incident-version" value={incidentVersionId} onChange={(event) => setIncidentVersionId(event.target.value)}>
            <option value="">Choose a version</option>
            {incidentVersions.map((version) => <option key={version.version_id} value={version.version_id}>{version.version_id} · {version.status}</option>)}
          </select>
          <label className="field-label" htmlFor="incident-type">Failure type</label>
          <select id="incident-type" value={incidentType} onChange={(event) => setIncidentType(event.target.value)}>
            <option value="retrieval_regression">Retrieval regression</option>
            <option value="stale_content_detected">Stale content detected</option>
            <option value="chunk_integrity_failure">Chunk integrity failure</option>
            <option value="normalization_issue">Normalization issue</option>
            <option value="manual_review">Manual review</option>
          </select>
          <label className="field-label" htmlFor="incident-summary">Incident summary</label>
          <textarea id="incident-summary" rows="3" maxLength="1000" value={incidentSummary} onChange={(event) => setIncidentSummary(event.target.value)} placeholder="Describe the failure to reproduce…" />
          <label className="field-label" htmlFor="incident-question">Optional evaluation question</label>
          <textarea id="incident-question" rows="2" value={incidentQuestion} onChange={(event) => setIncidentQuestion(event.target.value)} placeholder="What should the system retrieve?" />
          <label className="field-label" htmlFor="required-terms">Required evidence terms (one per line)</label>
          <textarea id="required-terms" rows="3" value={requiredTerms} onChange={(event) => setRequiredTerms(event.target.value)} placeholder="Terms that must be present in retrieved chunks" />
          <label className="field-label" htmlFor="forbidden-terms">Forbidden or stale terms (one per line)</label>
          <textarea id="forbidden-terms" rows="3" value={forbiddenTerms} onChange={(event) => setForbiddenTerms(event.target.value)} placeholder="Obsolete text that must not remain" />
          <button className="button button-primary" disabled={Boolean(busyAction) || !incidentDocumentId || !incidentVersionId || !incidentSummary.trim()}>
            {busyAction === "create-incident" ? "Creating incident…" : "Create incident"}<span>→</span>
          </button>
        </form>
      </div>

      <div className="panel">
        <SectionTitle eyebrow="INCIDENT HISTORY" title="Recorded incidents" description="Select a failure to inspect its record, then replay its checks." actions={<button className="small-button" type="button" disabled={Boolean(busyAction)} onClick={onRefreshIncidents}>Refresh</button>} />
        {!incidents.length ? (
          <EmptyState icon="✓" title="No incidents recorded">Failed SafeSync validation can create incidents automatically. You can also record a known test failure using the form.</EmptyState>
        ) : (
          <div className="incident-list">
            {incidents.map((incident) => (
              <button key={incident.incident_id} type="button" className={`incident-item ${selectedIncident?.incident_id === incident.incident_id ? "selected" : ""}`} onClick={() => onOpenIncident(incident.incident_id)}>
                <div><strong>{incident.summary}</strong><small>{incident.incident_id} · {incident.failure_type} · {formatDate(incident.created_at)}</small></div>
                <StatusPill tone={incident.status === "resolved" ? "success" : "warning"}>{incident.status}</StatusPill>
              </button>
            ))}
          </div>
        )}

        {selectedIncident ? (
          <div className="incident-detail">
            <div className="section-title-row"><div><p className="eyebrow">SELECTED INCIDENT</p><h3>{selectedIncident.incident_id}</h3></div><StatusPill tone={selectedIncident.status === "resolved" ? "success" : "warning"}>{selectedIncident.status}</StatusPill></div>
            <p>{selectedIncident.summary}</p>
            <div className="metadata-grid"><span>Failure type</span><strong>{selectedIncident.failure_type}</strong><span>Document</span><strong>{selectedIncident.document_id}</strong><span>Version</span><strong>{selectedIncident.version_id}</strong><span>Created</span><strong>{formatDate(selectedIncident.created_at)}</strong></div>
            <button className="button button-primary replay-button" type="button" disabled={Boolean(busyAction)} onClick={onReplayIncident}>{busyAction === "replay" ? "Replaying…" : "Replay incident now"}<span>↻</span></button>
            {incidentReplay ? (
              <div className="replay-report">
                <div className="report-title"><strong>Latest replay report</strong><StatusPill tone={incidentReplay.resolved ? "success" : "danger"}>{incidentReplay.resolved ? "Resolved" : "Checks failed"}</StatusPill></div>
                <div className="metric-grid"><MetricCard label="Chunks replayed" value={incidentReplay.replayed_chunk_count ?? "—"} /><MetricCard label="Same as saved output" value={incidentReplay.same_as_saved_chunk_output ? "Yes" : "No"} /><MetricCard label="Failed checks" value={incidentReplay.failed_checks?.length ?? 0} /></div>
                {(incidentReplay.checks ?? []).map((check, index) => <CheckRow key={`${check.check}-${index}`} check={{ ...check, check: `${check.check}-${index}` }} />)}
                <p className="muted small-note">{incidentReplay.note}</p>
                <button className="small-button" type="button" onClick={() => downloadJson(`${selectedIncident.incident_id}-replay.json`, incidentReplay)}>Export replay report</button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
