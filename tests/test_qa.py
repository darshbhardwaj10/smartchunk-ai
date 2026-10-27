"""Q&A tests: source grounding, citation integrity, and evidence abstention."""
from __future__ import annotations

import pytest


SAMPLE_MARKDOWN = b"""# Campus IT Guide

## Incident escalation

Before escalating an incident, record the incident ID, affected service, occurrence time, and troubleshooting steps.

## Response targets

Priority P1 incidents have a target response time of 15 minutes. Priority P2 incidents have a target response time of 60 minutes.
"""


def _process_guide(client) -> dict:
    response = client.post(
        "/process",
        data={"strategy": "structure", "chunk_size": "400", "overlap": "40", "semantic": "false"},
        files={"file": ("campus_it.md", SAMPLE_MARKDOWN, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_qa_answers_from_active_document_with_citations(client, monkeypatch):
    """Without a configured provider, answers should be extractive and cite source chunks."""
    monkeypatch.delenv("SMARTCHUNK_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    processed = _process_guide(client)

    response = client.post(
        "/qa/ask",
        json={"document_id": processed["document_id"], "question": "What is the P1 response target?", "top_k": 3},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "answered"
    assert "15 minutes" in payload["answer"]
    assert payload["answer_mode"] == "extractive_fallback"
    assert payload["citations"]
    assert payload["retrieved_chunks"]
    retrieved_ids = {item["chunk_id"] for item in payload["retrieved_chunks"]}
    assert all(item["chunk_id"] in retrieved_ids for item in payload["citations"])
    assert any(item["source"] == "campus_it.md" for item in payload["citations"])


def test_qa_abstains_when_no_relevant_evidence_exists(client, monkeypatch):
    """Unanswerable questions should return an explicit abstention, not invented facts."""
    monkeypatch.delenv("SMARTCHUNK_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    processed = _process_guide(client)

    response = client.post(
        "/qa/ask",
        json={
            "document_id": processed["document_id"],
            "question": "quasar xenolith quantum flux capacitor zygomorphic",
            "top_k": 3,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "insufficient_evidence"
    assert payload["answer_mode"] == "abstain"
    assert payload["citations"] == []
    assert payload["retrieved_chunks"] == []
    assert "could not find enough" in payload["answer"].casefold()


def test_qa_rejects_unknown_document(client):
    response = client.post(
        "/qa/ask",
        json={"document_id": "doc-does-not-exist", "question": "What is the response target?"},
    )
    assert response.status_code == 404


def test_qa_validates_top_k_range(client):
    response = client.post(
        "/qa/ask",
        json={"document_id": "doc-12345", "question": "A question", "top_k": 0},
    )
    assert response.status_code == 422


def test_qa_rejects_blank_question(client):
    """Whitespace-only input is rejected by the business layer."""
    processed = _process_guide(client)
    response = client.post(
        "/qa/ask",
        json={"document_id": processed["document_id"], "question": "   "},
    )
    assert response.status_code == 422
