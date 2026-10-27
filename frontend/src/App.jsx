import React, { useCallback, useEffect, useMemo, useState } from "react";
import DocumentStudio from "./components/DocumentStudio.jsx";
import DocumentChat from "./components/DocumentChat.jsx";
import SafeSyncDashboard from "./components/SafeSyncDashboard.jsx";
import IncidentExplorer from "./components/IncidentExplorer.jsx";
import { apiGet, apiPost, apiPostFile, apiPostJson, API_BASE } from "./services/api.js";
import { errorMessage } from "./utils/format.js";

export default function App() {
  const [activeTab, setActiveTab] = useState("workspace");
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
  const [notice, setNotice] = useState("");
  const [health, setHealth] = useState({ state: "checking", message: "Checking backend…" });

  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(4);
  const [qaHistory, setQaHistory] = useState([]);

  const [reuseDocumentId, setReuseDocumentId] = useState(false);
  const [candidate, setCandidate] = useState(null);
  const [candidateValidation, setCandidateValidation] = useState(null);
  const [safeSyncStatus, setSafeSyncStatus] = useState(null);

  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [incidentReplay, setIncidentReplay] = useState(null);
  const [incidentDocumentId, setIncidentDocumentId] = useState("");
  const [incidentVersionId, setIncidentVersionId] = useState("");
  const [incidentVersions, setIncidentVersions] = useState([]);
  const [incidentType, setIncidentType] = useState("retrieval_regression");
  const [incidentSummary, setIncidentSummary] = useState("");
  const [incidentQuestion, setIncidentQuestion] = useState("");
  const [requiredTerms, setRequiredTerms] = useState("");
  const [forbiddenTerms, setForbiddenTerms] = useState("");

  const selectedDocument = documents.find((item) => item.document_id === selectedDocumentId) ?? null;

  const refreshDocuments = useCallback(async () => {
    const payload = await apiGet("/documents");
    const rows = payload.documents ?? [];
    setDocuments(rows);
    setSelectedDocumentId((previous) => {
      if (previous && rows.some((item) => item.document_id === previous)) return previous;
      return rows[0]?.document_id ?? "";
    });
    return rows;
  }, []);

  const refreshIncidents = useCallback(async () => {
    const payload = await apiGet("/incidents");
    const rows = payload.incidents ?? [];
    setIncidents(rows);
    return rows;
  }, []);

  const refreshIncidentVersions = useCallback(async (documentId) => {
    if (!documentId) {
      setIncidentVersions([]);
      setIncidentVersionId("");
      return [];
    }
    const payload = await apiGet(`/documents/${encodeURIComponent(documentId)}/versions`);
    const rows = payload.versions ?? [];
    setIncidentVersions(rows);
    setIncidentVersionId((previous) => rows.some((item) => item.version_id === previous) ? previous : rows[0]?.version_id ?? "");
    return rows;
  }, []);

  useEffect(() => {
    let alive = true;
    apiGet("/health")
      .then((data) => { if (alive) setHealth({ state: "online", message: `Backend connected · ${data.version ?? "ready"}` }); })
      .catch(() => { if (alive) setHealth({ state: "offline", message: "Backend offline — start FastAPI" }); });
    refreshDocuments().catch(() => {});
    refreshIncidents().catch(() => {});
    return () => { alive = false; };
  }, [refreshDocuments, refreshIncidents]);

  useEffect(() => {
    if (activeTab === "incidents" && incidentDocumentId) {
      refreshIncidentVersions(incidentDocumentId).catch((err) => setError(errorMessage(err)));
    }
  }, [activeTab, incidentDocumentId, refreshIncidentVersions]);

  function clearMessages() {
    setError("");
    setNotice("");
  }

  function handleFileChange(event) {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setResult(null);
    setBenchmark(null);
    setNormalizePreview(null);
    setSelectedChunkIndex(0);
    setCandidate(null);
    setCandidateValidation(null);
    setSafeSyncStatus(null);
    setQaHistory([]);
    clearMessages();
  }

  function validateChunkInputs() {
    if (!file) return "Choose a document first.";
    if (!Number.isInteger(Number(chunkSize)) || Number(chunkSize) < 200 || Number(chunkSize) > 2000) return "Chunk size must be between 200 and 2000 characters.";
    if (!Number.isInteger(Number(overlap)) || Number(overlap) < 0 || Number(overlap) > 400 || Number(overlap) >= Number(chunkSize)) return "Overlap must be between 0 and 400 and smaller than chunk size.";
    return "";
  }

  async function previewNormalization() {
    if (!file) { setError("Choose a document first."); return; }
    setBusyAction("normalize"); clearMessages();
    try {
      const payload = await apiPostFile("/normalize", file);
      setNormalizePreview(payload);
      setNotice("Normalization preview ready.");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function processDocument() {
    const validation = validateChunkInputs();
    if (validation) { setError(validation); return; }
    setBusyAction("process"); clearMessages(); setBenchmark(null); setSelectedChunkIndex(0);
    try {
      const payload = await apiPostFile("/process", file, { strategy, chunk_size: chunkSize, overlap, semantic });
      setResult(payload);
      setSelectedDocumentId(payload.document_id ?? "");
      setQaHistory([]);
      await refreshDocuments();
      setActiveTab("workspace");
      setNotice(`Processed ${payload.filename}. Saved document ${payload.document_id} (${payload.version_id}).`);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function runBenchmark() {
    const validation = validateChunkInputs();
    if (validation) { setError(validation); return; }
    setBusyAction("benchmark"); clearMessages();
    try {
      const payload = await apiPostFile("/benchmark", file, { chunk_size: chunkSize, overlap });
      setBenchmark(payload);
      setNotice("Benchmark complete. Both chunk arrays are available below.");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  function openQAForCurrentResult() {
    if (result?.document_id) setSelectedDocumentId(result.document_id);
    setActiveTab("qa");
    setError("");
  }

  async function askQuestion(event) {
    event.preventDefault();
    if (!selectedDocumentId) { setError("Process a document first, then choose it here."); return; }
    if (!question.trim()) { setError("Enter a question about the selected document."); return; }
    setBusyAction("qa"); clearMessages();
    const submittedQuestion = question.trim();
    try {
      const response = await apiPostJson("/qa/ask", { document_id: selectedDocumentId, question: submittedQuestion, top_k: Number(topK) });
      setQaHistory((previous) => [...previous, { question: submittedQuestion, ...response }]);
      setQuestion("");
      await refreshDocuments().catch(() => {});
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function prepareCandidate(event) {
    event.preventDefault();
    const validation = validateChunkInputs();
    if (validation) { setError(validation); return; }
    if (reuseDocumentId && !selectedDocumentId) { setError("Select an existing document first, or turn off the existing-document option."); return; }
    setBusyAction("prepare"); clearMessages(); setCandidate(null); setCandidateValidation(null);
    try {
      const fields = { strategy, chunk_size: chunkSize, overlap, semantic };
      if (reuseDocumentId) fields.document_id = selectedDocumentId;
      const payload = await apiPostFile("/safesync/prepare", file, fields);
      setCandidate(payload);
      setSafeSyncStatus(null);
      setNotice(`Candidate ${payload.version_id} created. It is not active until validation and publication.`);
      await refreshDocuments();
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function validateCandidate() {
    if (!candidate?.version_id) return;
    setBusyAction("validate"); clearMessages();
    try {
      const response = await apiPost(`/safesync/validate/${encodeURIComponent(candidate.version_id)}`);
      setCandidateValidation(response);
      setNotice(response.passed ? "Candidate passed validation." : "Candidate blocked. Review failed checks before publishing.");
      await refreshIncidents().catch(() => {});
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function publishCandidate() {
    if (!candidate?.version_id || !candidateValidation?.passed) return;
    setBusyAction("publish"); clearMessages();
    try {
      const payload = await apiPost(`/safesync/publish/${encodeURIComponent(candidate.version_id)}`);
      await refreshDocuments();
      const status = await apiGet(`/safesync/status/${encodeURIComponent(candidate.document_id)}`);
      setSafeSyncStatus(status);
      setNotice(payload.message || "Candidate published.");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function refreshSafeSyncStatus() {
    const documentId = candidate?.document_id || selectedDocumentId;
    if (!documentId) { setError("Select or process a document first."); return; }
    setBusyAction("status"); setError("");
    try { setSafeSyncStatus(await apiGet(`/safesync/status/${encodeURIComponent(documentId)}`)); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function createIncident(event) {
    event.preventDefault();
    if (!incidentDocumentId || !incidentVersionId) { setError("Choose a document and version for the incident."); return; }
    if (!incidentSummary.trim()) { setError("Enter a short incident summary."); return; }
    setBusyAction("create-incident"); clearMessages();
    const details = { top_k: Number(topK) };
    if (incidentQuestion.trim()) details.question = incidentQuestion.trim();
    if (requiredTerms.trim()) details.required_evidence_terms = requiredTerms.split("\n").map((item) => item.trim()).filter(Boolean);
    if (forbiddenTerms.trim()) details.must_not_contain = forbiddenTerms.split("\n").map((item) => item.trim()).filter(Boolean);
    const version = incidentVersions.find((item) => item.version_id === incidentVersionId);
    const config = version ? { strategy: version.strategy, chunk_size: version.chunk_size, overlap: version.overlap, semantic: version.semantic } : {};
    try {
      const payload = await apiPostJson("/incidents", { document_id: incidentDocumentId, version_id: incidentVersionId, failure_type: incidentType, summary: incidentSummary.trim(), config, details });
      setIncidentSummary(""); setIncidentQuestion(""); setRequiredTerms(""); setForbiddenTerms("");
      await refreshIncidents();
      await openIncident(payload.incident_id);
      setNotice(`Incident ${payload.incident_id} created.`);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function openIncident(incidentId) {
    if (!incidentId) return;
    setBusyAction("incident-detail"); setError(""); setIncidentReplay(null);
    try {
      const payload = await apiGet(`/incidents/${encodeURIComponent(incidentId)}`);
      setSelectedIncident(payload);
      const replayPayload = await apiGet(`/incidents/${encodeURIComponent(incidentId)}/replays`).catch(() => ({ replays: [] }));
      setIncidentReplay(replayPayload.replays?.[0]?.result ?? null);
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  async function replayIncident() {
    if (!selectedIncident?.incident_id) return;
    setBusyAction("replay"); clearMessages();
    try {
      const payload = await apiPost(`/incidents/${encodeURIComponent(selectedIncident.incident_id)}/replay`);
      setIncidentReplay(payload);
      await refreshIncidents();
      setSelectedIncident(await apiGet(`/incidents/${encodeURIComponent(selectedIncident.incident_id)}`));
      setNotice(payload.resolved ? "Replay completed: all recorded checks passed." : "Replay completed with failing checks. Review the report.");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusyAction(""); }
  }

  const selectedChunkIndexSafe = useMemo(() => {
    const length = result?.chunks?.length ?? 0;
    if (!length) return 0;
    return Math.max(0, Math.min(selectedChunkIndex, length - 1));
  }, [result, selectedChunkIndex]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">SC</div>
        <div className="brand-copy"><p className="eyebrow">EVIDENCE-GROUNDED DOCUMENT INTELLIGENCE</p><h1>SmartChunk <span>AI</span></h1></div>
        <div className={`connection connection-${health.state}`} role="status"><span className="status-dot" />{health.message}</div>
      </header>

      <section className="hero">
        <p className="eyebrow">NORMALIZE · CHUNK · QUESTION · VALIDATE · REPLAY</p>
        <h2>Make document knowledge<br />inspectable and reliable.</h2>
        <p className="hero-copy">Prepare structure-aware chunks, ask questions grounded in a selected document, validate candidate knowledge-base updates and replay failed checks.</p>
        <div className="pipeline-chips"><span>01 Normalize</span><b>→</b><span>02 Chunk</span><b>→</b><span>03 Retrieve</span><b>→</b><span>04 Validate</span></div>
      </section>

      <nav className="main-nav" aria-label="SmartChunk sections">
        {[["workspace", "Document Studio"], ["qa", "Document Q&A"], ["safesync", "SafeSync"], ["incidents", "Incident Replay"]].map(([id, label]) => (
          <button key={id} type="button" className={`nav-tab ${activeTab === id ? "active" : ""}`} onClick={() => { setActiveTab(id); clearMessages(); }}>{label}</button>
        ))}
      </nav>

      {error ? <div className="global-alert alert-error" role="alert"><strong>Something needs attention</strong><span>{error}</span><button type="button" className="alert-close" onClick={() => setError("")} aria-label="Dismiss error">×</button></div> : null}
      {notice ? <div className="global-alert alert-success" role="status"><strong>Done</strong><span>{notice}</span><button type="button" className="alert-close" onClick={() => setNotice("")} aria-label="Dismiss notification">×</button></div> : null}

      {activeTab === "workspace" ? (
        <DocumentStudio
          uploadProps={{ file, onFileChange: handleFileChange, strategy, setStrategy, chunkSize, setChunkSize, overlap, setOverlap, semantic, setSemantic, busyAction, onProcess: processDocument, onPreview: previewNormalization, onBenchmark: runBenchmark }}
          explorerProps={{ result, selectedChunkIndex: selectedChunkIndexSafe, setSelectedChunkIndex, onOpenQA: openQAForCurrentResult }}
          normalizePreview={normalizePreview}
          setStrategy={setStrategy}
          benchmark={benchmark}
        />
      ) : null}

      {activeTab === "qa" ? (
        <DocumentChat documents={documents} selectedDocumentId={selectedDocumentId} setSelectedDocumentId={setSelectedDocumentId} selectedDocument={selectedDocument} question={question} setQuestion={setQuestion} topK={topK} setTopK={setTopK} qaHistory={qaHistory} setQaHistory={setQaHistory} busyAction={busyAction} onAsk={askQuestion} />
      ) : null}

      {activeTab === "safesync" ? (
        <SafeSyncDashboard file={file} onFileChange={handleFileChange} documents={documents} selectedDocumentId={selectedDocumentId} setSelectedDocumentId={setSelectedDocumentId} selectedDocument={selectedDocument} strategy={strategy} setStrategy={setStrategy} chunkSize={chunkSize} setChunkSize={setChunkSize} overlap={overlap} setOverlap={setOverlap} semantic={semantic} setSemantic={setSemantic} reuseDocumentId={reuseDocumentId} setReuseDocumentId={setReuseDocumentId} candidate={candidate} candidateValidation={candidateValidation} safeSyncStatus={safeSyncStatus} busyAction={busyAction} onPrepare={prepareCandidate} onValidate={validateCandidate} onPublish={publishCandidate} onRefreshStatus={refreshSafeSyncStatus} />
      ) : null}

      {activeTab === "incidents" ? (
        <IncidentExplorer documents={documents} incidentDocumentId={incidentDocumentId} setIncidentDocumentId={setIncidentDocumentId} incidentVersions={incidentVersions} incidentVersionId={incidentVersionId} setIncidentVersionId={setIncidentVersionId} incidentType={incidentType} setIncidentType={setIncidentType} incidentSummary={incidentSummary} setIncidentSummary={setIncidentSummary} incidentQuestion={incidentQuestion} setIncidentQuestion={setIncidentQuestion} requiredTerms={requiredTerms} setRequiredTerms={setRequiredTerms} forbiddenTerms={forbiddenTerms} setForbiddenTerms={setForbiddenTerms} incidents={incidents} selectedIncident={selectedIncident} incidentReplay={incidentReplay} busyAction={busyAction} onCreateIncident={createIncident} onRefreshIncidents={() => refreshIncidents().catch((err) => setError(errorMessage(err)))} onOpenIncident={openIncident} onReplayIncident={replayIncident} />
      ) : null}

      <footer><span>SMARTCHUNK AI</span><span>Document intelligence · Q&A · SafeSync · Incident Replay</span><span>API: {API_BASE}</span></footer>
    </main>
  );
}
