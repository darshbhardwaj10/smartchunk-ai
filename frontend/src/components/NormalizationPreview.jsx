import React from "react";
import { SectionTitle } from "./Common.jsx";

export default function NormalizationPreview({ preview, setStrategy }) {
  if (!preview) return null;
  const info = preview.normalization ?? {};
  const recommendation = preview.strategy_recommendation;
  return (
    <section className="panel">
      <SectionTitle
        eyebrow="NORMALIZATION"
        title="Markdown preview"
        description={`${preview.filename} · ${info.normalized_character_count ?? 0} normalized characters${preview.preview_truncated ? " · preview truncated" : ""}`}
      />
      {info.warnings?.length ? (
        <div className="warning-box">
          <strong>Normalization warnings</strong>
          {info.warnings.map((warning, index) => <p key={`${warning}-${index}`}>{warning}</p>)}
        </div>
      ) : null}
      {recommendation ? (
        <div className="recommendation">
          <strong>Suggested strategy: {recommendation.strategy}</strong>
          <p>{recommendation.reason}</p>
          <div className="chip-row">
            {(recommendation.detected_features ?? []).map((feature) => <span className="type-chip" key={feature}>{feature}</span>)}
          </div>
          <button className="small-button" type="button" onClick={() => setStrategy(recommendation.strategy)}>Use recommendation</button>
        </div>
      ) : null}
      <pre className="markdown-preview">{preview.markdown_preview}</pre>
    </section>
  );
}
