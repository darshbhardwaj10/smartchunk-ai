import React from "react";
import DocumentUpload from "./DocumentUpload.jsx";
import ChunkExplorer from "./ChunkExplorer.jsx";
import NormalizationPreview from "./NormalizationPreview.jsx";
import BenchmarkDashboard from "./BenchmarkDashboard.jsx";

export default function DocumentStudio(props) {
  return (
    <section className="workspace">
      <DocumentUpload {...props.uploadProps} />
      <div className="results-column">
        <ChunkExplorer {...props.explorerProps} />
        <NormalizationPreview preview={props.normalizePreview} setStrategy={props.setStrategy} />
        <BenchmarkDashboard benchmark={props.benchmark} />
      </div>
    </section>
  );
}
