# Campus IT Service Guide

## Purpose and scope

The Campus IT Service Guide explains how students and staff should report technical incidents, track service requests, and recover access to university systems. This guide is synthetic and was created solely to test document normalization and chunk-boundary behavior. It is not an official university policy. Support agents should classify each issue, record the affected service, and give users a clear next step. The original source layout mixes explanatory text with structured records, so a useful chunker should preserve the relationship between a section heading and the information that belongs to it. Please compare content, not only chunk counts.

## Incident priority reference

The table below is an indivisible test block. A structure-aware chunker should preserve the table as one table chunk when possible. If it exceeds the configured size, the system should explicitly mark it as oversized rather than silently cutting through rows.

| Priority | Example incident | Impact | Initial response target | Owner |
|---|---|---|---|---|
| P1 | Campus-wide identity provider unavailable | All sign-ins fail for students and staff | Immediate | Incident commander |
| P1 | Learning platform unavailable during an exam | Large group cannot access a scheduled assessment | Immediate | Learning systems lead |
| P2 | Single department printer outage | Several users in one department are affected | Within 30 minutes | Endpoint support |
| P2 | Student portal loads but grades are missing | A core page is available but a key data panel is absent | Within 30 minutes | Student systems team |
| P3 | One workstation has no audio | One user is affected and work can continue | Same business day | Service desk |
| P3 | Request for software installation | Planned change; no current service interruption | Scheduled queue | Endpoint support |
| P4 | How-to question about Wi-Fi setup | Information request with no reported outage | Two business days | Service desk |
| P2 | Repeated VPN authentication prompt | Remote staff cannot maintain a stable session | Within 30 minutes | Network support |
| P2 | Test scenario 1: a subsystem reports an intermittent failure during routine use | Impact analysis should identify the affected user group, determine whether a workaround exists, and record whether the error is reproducible after a clean retry | Collect timestamp, request identifier, and one sanitized log excerpt before escalating | Service owner 1 |
| P3 | Test scenario 2: a subsystem reports an intermittent failure during routine use | Impact analysis should identify the affected user group, determine whether a workaround exists, and record whether the error is reproducible after a clean retry | Collect timestamp, request identifier, and one sanitized log excerpt before escalating | Service owner 2 |
| P4 | Test scenario 3: a subsystem reports an intermittent failure during routine use | Impact analysis should identify the affected user group, determine whether a workaround exists, and record whether the error is reproducible after a clean retry | Collect timestamp, request identifier, and one sanitized log excerpt before escalating | Service owner 3 |
| P1 | Test scenario 4: a subsystem reports an intermittent failure during routine use | Impact analysis should identify the affected user group, determine whether a workaround exists, and record whether the error is reproducible after a clean retry | Collect timestamp, request identifier, and one sanitized log excerpt before escalating | Service owner 4 |
| P2 | Test scenario 5: a subsystem reports an intermittent failure during routine use | Impact analysis should identify the affected user group, determine whether a workaround exists, and record whether the error is reproducible after a clean retry | Collect timestamp, request identifier, and one sanitized log excerpt before escalating | Service owner 5 |

## Incident identifier handling

The following example is provided to test preservation of fenced code. It is synthetic and does not connect to a real ticketing service.

```python
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

Severity = Literal['P1', 'P2', 'P3', 'P4']

@dataclass
class Incident:
    incident_id: str
    severity: Severity
    service_name: str
    summary: str
    created_at: datetime
    owner: str | None = None

def normalize_incident_id(value: str) -> str:
    # Trim outer whitespace and normalize the stable identifier only.
    candidate = value.strip().upper()
    if not candidate.startswith('INC-'):
        raise ValueError('Incident ID must start with INC-')
    suffix = candidate[4:]
    if not suffix.isdigit() or len(suffix) < 4:
        raise ValueError('Incident ID must contain at least four digits')
    return candidate

def response_deadline(severity: Severity, created_at: datetime) -> datetime:
    # The targets below are illustrative test rules, not a real SLA.
    minutes = {'P1': 5, 'P2': 30, 'P3': 480, 'P4': 960}[severity]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + timedelta(minutes=minutes)

def safe_summary(value: str, limit: int = 240) -> str:
    # Avoid empty summaries and cap display length before logging.
    summary = ' '.join(value.split())
    if not summary:
        raise ValueError('Summary must not be empty')
    return summary[:limit]

def build_audit_record(incident: Incident) -> dict[str, str]:
    return {
        'incident_id': normalize_incident_id(incident.incident_id),
        'severity': incident.severity,
        'service_name': incident.service_name,
        'summary': safe_summary(incident.summary),
        'created_at': incident.created_at.isoformat(),
    }
```

## First-response checklist

- Confirm which service is affected and how many users are affected.
- Record the time, error message, and relevant request or incident identifier.
- Ask whether the issue can be reproduced after a safe retry.
- Capture sanitized logs only; never collect passwords, access tokens, or private keys.
- Assign an owner and communicate the next update time.
- If the incident is P1, notify the on-call coordinator immediately.

## Account access recovery

Users who cannot sign in should first confirm that the account identifier is correct and that the system status page does not report an outage. Support staff should never ask a user to send a password by email or chat. If a second factor is unavailable, staff should follow the approved identity-verification process and record the recovery action in the ticket.

## Portal maintenance

Scheduled maintenance notice: the test portal may be unavailable during the published maintenance window. Save work before maintenance and check the service status page for updates.

## Frequently asked questions

### How do I report a missing grade?

Open a ticket under Student Systems, include the course code and the page where the information is missing, and do not include another student's private information. The support team verifies the data source before escalating to the academic systems owner.

### How do I request software?

Submit a software request with the application name, purpose, and the course or work requirement. Installation must be approved where licensing or device security rules require approval.

## Repeated notice test

Scheduled maintenance notice: the test portal may be unavailable during the published maintenance window. Save work before maintenance and check the service status page for updates.

## Source and benchmark notes

This dataset is synthetic. The incident names, response targets, and examples are designed for software testing and are not official operational instructions. Evaluators should use the same input document and chunk-size settings for both algorithms, inspect actual chunks, and report both successful structural preservation and any failures.
