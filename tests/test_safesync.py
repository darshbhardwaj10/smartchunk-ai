"""SafeSync tests: candidate validation, publish gating, and rollback safety."""
from __future__ import annotations


SOURCE_V1 = b"""# Service Runbook

## Priority One

P1 incidents have a response target of 15 minutes. Record the incident ID before escalation.
"""

SOURCE_V2 = b"""# Service Runbook

## Priority One

P1 incidents have a response target of 10 minutes. Record the incident ID before escalation.
"""


def _process_source(client, name: str, source: bytes) -> dict:
    response = client.post(
        "/process",
        data={"strategy": "structure", "chunk_size": "350", "overlap": "30"},
        files={"file": (name, source, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_candidate_is_not_active_until_validation_and_publish(client, store):
    initial = _process_source(client, "runbook.md", SOURCE_V1)
    document_id = initial["document_id"]
    old_version_id = initial["version_id"]

    candidate_response = client.post(
        "/safesync/prepare",
        data={
            "document_id": document_id,
            "strategy": "structure",
            "chunk_size": "350",
            "overlap": "30",
        },
        files={"file": ("runbook.md", SOURCE_V2, "text/markdown")},
    )
    assert candidate_response.status_code == 200, candidate_response.text
    candidate = candidate_response.json()
    candidate_id = candidate["version_id"]

    assert candidate["status"] == "candidate"
    assert store.get_document(document_id)["active_version_id"] == old_version_id
    assert store.get_version(candidate_id)["status"] == "candidate"

    premature_publish = client.post(f"/safesync/publish/{candidate_id}")
    assert premature_publish.status_code == 409
    assert store.get_document(document_id)["active_version_id"] == old_version_id

    validation = client.post(f"/safesync/validate/{candidate_id}")
    assert validation.status_code == 200, validation.text
    assert validation.json()["passed"] is True
    assert store.get_version(candidate_id)["status"] == "validated"
    # Validation alone must not switch the active version.
    assert store.get_document(document_id)["active_version_id"] == old_version_id

    publish = client.post(f"/safesync/publish/{candidate_id}")
    assert publish.status_code == 200, publish.text
    assert publish.json()["published"] is True
    assert store.get_document(document_id)["active_version_id"] == candidate_id
    assert store.get_version(candidate_id)["status"] == "active"
    assert store.get_version(old_version_id)["status"] == "superseded"


def test_failed_candidate_is_blocked_and_cannot_replace_active_version(client, store):
    initial = _process_source(client, "runbook.md", SOURCE_V1)
    document_id = initial["document_id"]
    old_version_id = initial["version_id"]

    # Build a deliberately invalid candidate directly to exercise the hard release gate.
    invalid_id = store.save_version(
        document_id=document_id,
        filename="runbook.md",
        source_bytes=b"empty candidate",
        normalized_markdown="",
        normalization={"warnings": []},
        chunks=[],
        strategy="structure",
        chunk_size=350,
        overlap=30,
        status="candidate",
    )

    validation = client.post(f"/safesync/validate/{invalid_id}")
    assert validation.status_code == 200, validation.text
    report = validation.json()
    assert report["passed"] is False
    assert report["status"] == "BLOCK"
    assert "normalized_content_present" in report["failed_checks"]
    assert "chunks_present" in report["failed_checks"]
    assert store.get_version(invalid_id)["status"] == "blocked"

    publish = client.post(f"/safesync/publish/{invalid_id}")
    assert publish.status_code == 409
    assert store.get_document(document_id)["active_version_id"] == old_version_id


def test_validation_report_contains_explicit_checks(client):
    processed = _process_source(client, "runbook.md", SOURCE_V1)
    candidate = client.post(
        "/safesync/prepare",
        data={"document_id": processed["document_id"], "chunk_size": "350", "overlap": "30"},
        files={"file": ("runbook.md", SOURCE_V2, "text/markdown")},
    )
    assert candidate.status_code == 200, candidate.text

    report_response = client.post(f"/safesync/validate/{candidate.json()['version_id']}")
    assert report_response.status_code == 200
    payload = report_response.json()
    check_names = {check["check"] for check in payload["checks"]}
    assert {
        "normalized_content_present",
        "chunks_present",
        "chunk_text_present",
        "chunk_ids_present",
        "source_metadata_present",
        "no_known_empty_pdf_extraction",
    }.issubset(check_names)
