# Smart Campus API Integration Guide

## Authentication

The demonstration API uses a synthetic local environment. Never paste credentials into benchmark documents. Production authentication and authorization are outside the scope of this chunking prototype.

## Endpoint reference

| Method | Path | Purpose | Required body | Expected result |
|---|---|---|---|---|
| GET | /health | Check API process status | None | JSON status object |
| POST | /normalize | Extract and normalize one document | multipart file | Markdown preview and warnings |
| POST | /process | Run one chunking strategy | file and settings | Chunk records and metrics |
| POST | /benchmark | Compare both chunking strategies | file and settings | Two metric sets and chunk arrays |

## Request example

The following request is illustrative. It assumes the local API is listening on port 8000.

```bash
curl -X POST 'http://127.0.0.1:8000/process' \
  -F 'file=@sample_manual.md' \
  -F 'strategy=structure' \
  -F 'chunk_size=700' \
  -F 'overlap=80' \
  -F 'semantic=false'
```

## Response contract

A chunk record should include the original source filename, its location where known, a heading path, content type, character count, and an optional parent identifier. The `oversized` flag indicates that a structural block was retained intact even though it exceeded the requested chunk size.

```json
{
  "chunk_id": "sample_manual_chunk_001",
  "text": "Section: API > Response contract\n\nA chunk contains source-aware text.",
  "heading_path": ["API", "Response contract"],
  "chunk_type": "prose",
  "source": {"file": "sample_manual.md", "location": "lines 30-31"},
  "parent_id": null,
  "char_count": 68,
  "oversized": false
}
```

## Error handling

- 400: empty, unreadable, or invalid extracted content.
- 413: upload size exceeds the configured limit.
- 415: unsupported file extension.
- 422: invalid chunk size, overlap, or request fields.

## Operational guidance

Keep the API and frontend running in separate development terminals. Avoid exposing an unauthenticated development backend to the public internet. Benchmark results describe chunk properties; they do not establish that answers from a downstream generative model are correct.
