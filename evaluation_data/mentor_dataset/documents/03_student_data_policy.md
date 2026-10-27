# Student Data Handling Policy — Synthetic Test Copy

## Data minimization

Only collect information required to resolve the reported service issue. A support ticket should not include passwords, session cookies, authentication tokens, government identifiers, or unrelated personal information.

## Roles and responsibilities

- Students report the minimum facts needed to reproduce a problem.
- Service desk agents classify the incident and record a clear next action.
- Service owners investigate the affected application or infrastructure.
- Security staff handle suspected credential exposure using an approved incident process.

## Retention schedule

| Record type | Suggested test retention | Disposal check |
|---|---|---|
| Routine support ticket | 90 days after closure | Confirm no active investigation |
| Sanitized diagnostic log | 30 days after resolution | Remove temporary copies |
| Security incident record | Follow the approved incident schedule | Obtain security-owner approval |
| Benchmark output | For the duration of the evaluation | Remove uploaded source material when no longer needed |

These durations are illustrative dataset values, not legal advice or an actual institutional policy.

## Handling workflow

1. Identify the minimum information needed to investigate.
2. Remove secrets from logs before sharing them.
3. Limit access to people assigned to the incident.
4. Record an audit note when data is exported to another system.
5. Delete temporary copies according to the approved retention process.

## Repeated content example

Security reminder: never put passwords, API tokens, or session cookies into a support ticket.

## Second repeated content example

Security reminder: never put passwords, API tokens, or session cookies into a support ticket.
