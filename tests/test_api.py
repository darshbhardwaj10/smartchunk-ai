from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
SAMPLE_MARKDOWN = b"""# Student Handbook

## Attendance Rules

Students should maintain at least 75% attendance in each course.

| Classes attended | Total classes | Attendance |
|---:|---:|---:|
| 36 | 40 | 90% |

```python
def answer():
    return 42
```
"""


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "SmartChunk AI API"
    assert payload["health"] == "/health"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_normalize_markdown_endpoint():
    response = client.post(
        "/normalize",
        files={"file": ("handbook.md", SAMPLE_MARKDOWN, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "handbook.md"
    assert payload["normalization"]["intermediate_format"] == "markdown"
    assert "# Student Handbook" in payload["markdown_preview"]
    assert payload["preview_truncated"] is False


def test_process_structure_strategy():
    response = client.post(
        "/process",
        data={"strategy": "structure", "chunk_size": "700", "overlap": "80", "semantic": "false"},
        files={"file": ("handbook.md", SAMPLE_MARKDOWN, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["strategy"] == "structure"
    assert payload["chunks"]
    assert payload["metrics"]["chunk_count"] == len(payload["chunks"])
    assert all("text" in chunk and "source" in chunk for chunk in payload["chunks"])
    assert any(chunk["chunk_type"] == "table" for chunk in payload["chunks"])
    assert any(chunk["chunk_type"] == "code" for chunk in payload["chunks"])


def test_process_fixed_strategy():
    response = client.post(
        "/process",
        data={"strategy": "fixed", "chunk_size": "700", "overlap": "80", "semantic": "false"},
        files={"file": ("handbook.md", SAMPLE_MARKDOWN, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["strategy"] == "fixed"
    assert payload["chunks"]
    assert payload["metrics"]["chunk_count"] == len(payload["chunks"])


def test_benchmark_endpoint():
    response = client.post(
        "/benchmark",
        data={"chunk_size": "700", "overlap": "80"},
        files={"file": ("handbook.md", SAMPLE_MARKDOWN, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "baseline" in payload and "smartchunk" in payload
    assert payload["baseline"]["chunk_count"] >= 1
    assert payload["smartchunk"]["chunk_count"] >= 1


def test_unsupported_extension_returns_415():
    response = client.post(
        "/process",
        data={"strategy": "structure"},
        files={"file": ("payload.exe", b"not a document", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_empty_file_returns_400():
    response = client.post(
        "/process",
        data={"strategy": "structure"},
        files={"file": ("empty.md", b"", "text/markdown")},
    )
    assert response.status_code == 400


def test_invalid_chunk_size_returns_422():
    response = client.post(
        "/process",
        data={"strategy": "structure", "chunk_size": "100", "overlap": "10"},
        files={"file": ("handbook.md", SAMPLE_MARKDOWN, "text/markdown")},
    )
    assert response.status_code == 422


def test_invalid_overlap_returns_422():
    response = client.post(
        "/benchmark",
        data={"chunk_size": "300", "overlap": "300"},
        files={"file": ("handbook.md", SAMPLE_MARKDOWN, "text/markdown")},
    )
    assert response.status_code == 422
