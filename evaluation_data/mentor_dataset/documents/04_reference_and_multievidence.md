# Temporary System Access Policy

This document is synthetic and intended only for SmartChunk evaluation.

## Default access duration

Temporary VPN access expires after 14 calendar days unless renewed. The expiry clock starts on the date the access request is approved, not the date the account was first created.

## Renewal exception

Employees assigned to a documented high-priority incident may receive one seven-day extension. The exception applies only after the service owner approves the extension.

## Extension approval record

Every extension record must include the ticket identifier, the approver's role, the approval date, and the revised expiry date. A ticket identifier without an approval record is not sufficient evidence that an extension was authorized.

## Access duration by role

Table 1: Maximum initial access duration for the two roles in this synthetic policy.

| Role | Maximum initial duration | Required approval |
|---|---:|---|
| Student contractor | 7 calendar days | Faculty sponsor |
| Staff engineer | 14 calendar days | Service owner |

## Logging and retention

Support logs must omit passwords, API keys and session cookies. Sanitized diagnostic logs are retained for 30 days, measured from the date the incident is closed. A separate legal hold may override ordinary deletion only when authorized by the organization's approved process.

## Explicit reference

For the extension rule, see Section 2, Renewal exception. For the required approval fields, see Section 3, Extension approval record.
