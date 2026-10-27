"""Incident replay tests: capture, deterministic reproduction, and failure cases."""
from __future__ import annotations


GUIDE = b"""# Campus IT Guide

## Escalation checklist

Record the incident ID, affected service, and troubleshooting steps before escalation.

## Response target

Priority P1 incidents have a target response time of 15 minutes.
"""


def _create_processed_document(client) -> dict:
    response = client.post(
        "/process",
        data={"strategy": "structure", "chunk_size": "400", "overlap": "35", "semantic": "false"},
        files={"file": ("incident_guide.md", GUIDE, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_incident(client, processed: dict, **overrides) -> dict:
    payload = {
        "document_id": processed["document_id"],
        "version_id": processed["version_id"],
        "failure_type": "chunk_regression",
        "summary": "Reproduce a deterministic chunking case.",
        "config": {"strategy": "structure", "chunk_size": 400, "overlap": 35, "semantic": False},
        "details": {"must_contain": ["15 minutes"], "must_not_contain": ["obsolete response target"]},
    }
    payload.update(overrides)
    response = client.post("/incidents", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_incident_replay_reproduces_saved_output(client):
    processed = _create_processed_document(client)
    incident = _create_incident(client, processed)

    replay = client.post(f"/incidents/{incident['incident_id']}/replay")
    assert replay.status_code == 200, replay.text
    result = replay.json()
    assert result["same_as_saved_chunk_output"] is True
    assert result["resolved"] is True
    assert result["replayed_chunk_count"] == len(processed["chunks"])
    assert result["replay_id"]

    replay_list = client.get(f"/incidents/{incident['incident_id']}/replays")
    assert replay_list.status_code == 200
    assert len(replay_list.json()["replays"]) == 1


def test_repeated_replay_is_deterministic_and_records_each_run(client):
    processed = _create_processed_document(client)
    incident = _create_incident(client, processed)
    incident_id = incident["incident_id"]

    first = client.post(f"/incidents/{incident_id}/replay").json()
    second = client.post(f"/incidents/{incident_id}/replay").json()

    assert first["same_as_saved_chunk_output"] is True
    assert second["same_as_saved_chunk_output"] is True
    assert first["resolved"] is True and second["resolved"] is True
    assert first["replay_id"] != second["replay_id"]
    replay_list = client.get(f"/incidents/{incident_id}/replays").json()["replays"]
    assert len(replay_list) == 2


def test_incident_replay_fails_when_required_text_is_missing(client):
    processed = _create_processed_document(client)
    incident = _create_incident(
        client,
        processed,
        details={"must_contain": ["this phrase is not in the source document"]},
    )

    response = client.post(f"/incidents/{incident['incident_id']}/replay")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["same_as_saved_chunk_output"] is True
    assert result["resolved"] is False
    assert any(item.startswith("required_text:") for item in result["failed_checks"])


def test_unknown_incident_returns_404(client):
    response = client.post("/incidents/inc-does-not-exist/replay")
    assert response.status_code == 404


def test_invalid_recorded_chunk_settings_return_422_on_replay(client):
    processed = _create_processed_document(client)
    incident = _create_incident(
        client,
        processed,
        config={"strategy": "structure", "chunk_size": 400, "overlap": 400},
    )

    response = client.post(f"/incidents/{incident['incident_id']}/replay")
    assert response.status_code == 422
