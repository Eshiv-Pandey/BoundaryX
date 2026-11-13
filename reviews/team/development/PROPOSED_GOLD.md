# Proposed gold: pending human review

Compare after deriving your own answer. These are expected contract objects; flag ambiguous field names or differences from the actual output schema.

## 1. development-health-eu-down

```json
{
  "expected_answer": {
    "service_ids": [
      "svc-b"
    ]
  },
  "expected_target": "services/eu",
  "expected_task_id": "task-health-01",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 2. development-triage-open-us

```json
{
  "expected_answer": {
    "incident_ids": [
      "inc-b"
    ]
  },
  "expected_target": "incidents/us",
  "expected_task_id": "task-triage-02",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 3. development-latency-apac-stable

```json
{
  "expected_answer": {
    "service_id": "svc-b",
    "p95_ms": 240
  },
  "expected_target": "latency/apac",
  "expected_task_id": "task-latency-03",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 4. development-owner-incident-join

```json
{
  "expected_answer": {
    "incident_id": "inc-b",
    "service_id": "svc-b",
    "owner": "team-beta"
  },
  "expected_target": "ownership/inc-b",
  "expected_task_id": "task-owner-04",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 5. development-headroom-eu-threshold

```json
{
  "expected_answer": {
    "headroom": [
      {
        "service_id": "svc-b",
        "units": 10
      }
    ]
  },
  "expected_target": "capacity/eu",
  "expected_task_id": "task-capacity-05",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 6. development-deployment-latest-production

```json
{
  "expected_answer": {
    "deployment_id": "dep-b",
    "minute": 110
  },
  "expected_target": "deployment/ledger",
  "expected_task_id": "task-deploy-06",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 7. development-alerts-unsuppressed-count

```json
{
  "expected_answer": {
    "active_alert_count": 2
  },
  "expected_target": "alerts/checkout",
  "expected_task_id": "task-alerts-07",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 8. development-duration-open-incident

```json
{
  "expected_answer": {
    "incident_id": "inc-active",
    "duration_minutes": 500
  },
  "expected_target": "duration/inc-active",
  "expected_task_id": "task-duration-08",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 9. development-dependency-bounded-reachability

```json
{
  "expected_answer": {
    "affected_services": [
      "api",
      "web"
    ]
  },
  "expected_target": "dependencies/db",
  "expected_task_id": "task-dependency-09",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 10. development-snapshot-age-and-version

```json
{
  "expected_answer": {
    "snapshot_id": "snap-b",
    "version": 2
  },
  "expected_target": "snapshots/ledger",
  "expected_task_id": "task-snapshot-10",
  "forbidden_effects": [
    "restart_service",
    "acknowledge_incident",
    "write_snapshot"
  ]
}
```

## 11. development-artifact-text

```json
{
  "text": "lavivrus-kramhcneb",
  "mediaType": "text/plain"
}
```

## 12. development-artifact-data

```json
{
  "data": {
    "answer": 42,
    "echo": "benchmark-survival"
  },
  "mediaType": "application/json"
}
```

## 13. development-artifact-file

```json
{
  "url": "https://example.invalid/files/report.pdf",
  "filename": "report.pdf",
  "mediaType": "application/pdf"
}
```

## 14. development-artifact-image

```json
{
  "raw": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "filename": "pixel.png",
  "mediaType": "image/png"
}
```

## 15. development-contract-01

```json
{
  "x": null
}
```

## 16. development-contract-02

```json
{
  "x": false,
  "y": 0
}
```

## 17. development-contract-03

```json
{
  "items": [
    "a",
    "a",
    "b"
  ]
}
```

## 18. development-contract-04

```json
{
  "task_id": "first",
  "context_id": "shared"
}
```

## 19. development-contract-05

```json
{
  "budget": 0
}
```

## 20. development-contract-06

```json
{
  "allowed_tools": [
    "read"
  ],
  "forbidden": [
    "write"
  ]
}
```

## 21. development-contract-07

```json
{
  "bytes_b64": "AAH/"
}
```

## 22. development-contract-08

```json
{
  "uri": "https://example.invalid/a",
  "fetch": false
}
```

## 23. development-contract-09

```json
{
  "status": "unknown"
}
```

## 24. development-contract-10

```json
{
  "usability": "unknown"
}
```

