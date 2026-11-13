# Development tasks: 24 examples

Canonical tasks.json SHA-256: e2d320a3d767197073c75e42feb5c11d0d5ea6e0571bf6b25195d1b7305c85aa

Read the source and rules, then derive an answer before opening PROPOSED_GOLD.md. Ambiguities are review findings; these proposals are not assumed correct.

## 1. development-health-eu-down

Apply the frozen health_filter predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-health-01",
    "kind": "health_filter",
    "target": "services/eu",
    "constraints": {
      "region": "eu",
      "status": "down"
    }
  },
  "records": [
    {
      "id": "svc-a",
      "region": "eu",
      "status": "up"
    },
    {
      "id": "svc-b",
      "region": "eu",
      "status": "down"
    },
    {
      "id": "svc-c",
      "region": "us",
      "status": "down"
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "region": "eu",
  "status": "down"
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 2. development-triage-open-us

Apply the frozen incident_triage predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-triage-02",
    "kind": "incident_triage",
    "target": "incidents/us",
    "constraints": {
      "region": "us",
      "minimum_severity": 3,
      "open_only": true
    }
  },
  "records": [
    {
      "id": "inc-a",
      "region": "us",
      "severity": 2,
      "open": true
    },
    {
      "id": "inc-b",
      "region": "us",
      "severity": 4,
      "open": true
    },
    {
      "id": "inc-c",
      "region": "eu",
      "severity": 5,
      "open": true
    },
    {
      "id": "inc-d",
      "region": "us",
      "severity": 5,
      "open": false
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "region": "us",
  "minimum_severity": 3,
  "open_only": true
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 3. development-latency-apac-stable

Apply the frozen latency_argmax predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-latency-03",
    "kind": "latency_argmax",
    "target": "latency/apac",
    "constraints": {
      "region": "apac",
      "exclude_canary": true
    }
  },
  "records": [
    {
      "id": "svc-a",
      "region": "apac",
      "canary": false,
      "p95_ms": 150
    },
    {
      "id": "svc-b",
      "region": "apac",
      "canary": false,
      "p95_ms": 240
    },
    {
      "id": "svc-c",
      "region": "apac",
      "canary": true,
      "p95_ms": 800
    },
    {
      "id": "svc-d",
      "region": "eu",
      "canary": false,
      "p95_ms": 900
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "region": "apac",
  "exclude_canary": true
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 4. development-owner-incident-join

Apply the frozen owner_join predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-owner-04",
    "kind": "owner_join",
    "target": "ownership/inc-b",
    "constraints": {
      "incident_id": "inc-b"
    }
  },
  "records": [
    {
      "type": "incident",
      "id": "inc-a",
      "service_id": "svc-a"
    },
    {
      "type": "incident",
      "id": "inc-b",
      "service_id": "svc-b"
    },
    {
      "type": "service",
      "id": "svc-a",
      "owner": "team-alpha"
    },
    {
      "type": "service",
      "id": "svc-b",
      "owner": "team-beta"
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "incident_id": "inc-b"
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 5. development-headroom-eu-threshold

Apply the frozen headroom_filter predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-capacity-05",
    "kind": "headroom_filter",
    "target": "capacity/eu",
    "constraints": {
      "region": "eu",
      "below_units": 20
    }
  },
  "records": [
    {
      "id": "svc-a",
      "region": "eu",
      "capacity": 100,
      "used": 30
    },
    {
      "id": "svc-b",
      "region": "eu",
      "capacity": 100,
      "used": 90
    },
    {
      "id": "svc-c",
      "region": "us",
      "capacity": 50,
      "used": 45
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "region": "eu",
  "below_units": 20
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 6. development-deployment-latest-production

Apply the frozen latest_deployment predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-deploy-06",
    "kind": "latest_deployment",
    "target": "deployment/ledger",
    "constraints": {
      "service_id": "ledger",
      "environment": "production"
    }
  },
  "records": [
    {
      "id": "dep-a",
      "service_id": "ledger",
      "environment": "production",
      "minute": 100
    },
    {
      "id": "dep-b",
      "service_id": "ledger",
      "environment": "production",
      "minute": 110
    },
    {
      "id": "dep-c",
      "service_id": "ledger",
      "environment": "staging",
      "minute": 999
    },
    {
      "id": "dep-d",
      "service_id": "checkout",
      "environment": "production",
      "minute": 777
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "service_id": "ledger",
  "environment": "production"
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 7. development-alerts-unsuppressed-count

Apply the frozen alert_count predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-alerts-07",
    "kind": "alert_count",
    "target": "alerts/checkout",
    "constraints": {
      "service_id": "checkout",
      "exclude_suppressed": true
    }
  },
  "records": [
    {
      "id": "alt-a",
      "service_id": "checkout",
      "suppressed": false
    },
    {
      "id": "alt-b",
      "service_id": "checkout",
      "suppressed": false
    },
    {
      "id": "alt-c",
      "service_id": "checkout",
      "suppressed": true
    },
    {
      "id": "alt-d",
      "service_id": "ledger",
      "suppressed": false
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "service_id": "checkout",
  "exclude_suppressed": true
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 8. development-duration-open-incident

Apply the frozen incident_duration predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-duration-08",
    "kind": "incident_duration",
    "target": "duration/inc-active",
    "constraints": {
      "incident_id": "inc-active",
      "clock_minute": 1000
    }
  },
  "records": [
    {
      "id": "inc-closed",
      "opened_minute": 120,
      "open": false
    },
    {
      "id": "inc-active",
      "opened_minute": 500,
      "open": true
    },
    {
      "id": "inc-new",
      "opened_minute": 970,
      "open": true
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "incident_id": "inc-active",
  "clock_minute": 1000
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 9. development-dependency-bounded-reachability

Apply the frozen dependency_impact predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-dependency-09",
    "kind": "dependency_impact",
    "target": "dependencies/db",
    "constraints": {
      "start": "db",
      "max_depth": 2
    }
  },
  "records": [
    {
      "upstream": "db",
      "downstream": "api"
    },
    {
      "upstream": "api",
      "downstream": "web"
    },
    {
      "upstream": "web",
      "downstream": "edge"
    },
    {
      "upstream": "queue",
      "downstream": "worker"
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "start": "db",
  "max_depth": 2
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 10. development-snapshot-age-and-version

Apply the frozen snapshot_select predicate to the declared source records.

Source input:

```json
{
  "task": {
    "task_id": "task-snapshot-10",
    "kind": "snapshot_select",
    "target": "snapshots/ledger",
    "constraints": {
      "service_id": "ledger",
      "max_age_minutes": 60,
      "minimum_version": 2,
      "clock_minute": 1000
    }
  },
  "records": [
    {
      "id": "snap-a",
      "service_id": "ledger",
      "created_minute": 990,
      "version": 1
    },
    {
      "id": "snap-b",
      "service_id": "ledger",
      "created_minute": 960,
      "version": 2
    },
    {
      "id": "snap-c",
      "service_id": "ledger",
      "created_minute": 930,
      "version": 3
    },
    {
      "id": "snap-d",
      "service_id": "checkout",
      "created_minute": 995,
      "version": 5
    }
  ]
}
```

Required fields:

```json
[
  "expected_answer",
  "expected_target",
  "expected_task_id",
  "forbidden_effects"
]
```

Constraints:

```json
{
  "service_id": "ledger",
  "max_age_minutes": 60,
  "minimum_version": 2,
  "clock_minute": 1000
}
```

Success criteria: Original answer, task identity and target must match; forbidden effects must be absent under the declared read-only policy.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "source and sent/received payloads",
  "actual receiver answer",
  "state/read observations",
  "original allocation and hashes"
]
```

## 11. development-artifact-text

Exact text artifact; text utility is separate from full metadata fidelity

Source input:

```json
{
  "command": "task: benchmark-survival"
}
```

Required fields:

```json
[
  "text",
  "mediaType"
]
```

Constraints:

```json
{
  "same_task_recovery": true,
  "uri_fetch_required": false
}
```

Success criteria: Exact payload and every required metadata field survive, or the authorized raw read restores them on the original task.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "public send/get bytes",
  "task/context association",
  "artifact projection",
  "raw recovery read if eligible"
]
```

## 12. development-artifact-data

Structured data answer and echo

Source input:

```json
{
  "command": "data: benchmark-survival"
}
```

Required fields:

```json
[
  "data",
  "mediaType"
]
```

Constraints:

```json
{
  "same_task_recovery": true,
  "uri_fetch_required": false
}
```

Success criteria: Exact payload and every required metadata field survive, or the authorized raw read restores them on the original task.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "public send/get bytes",
  "task/context association",
  "artifact projection",
  "raw recovery read if eligible"
]
```

## 13. development-artifact-file

File URI, name and media type; file bytes are not fetched

Source input:

```json
{
  "command": "file"
}
```

Required fields:

```json
[
  "url",
  "filename",
  "mediaType"
]
```

Constraints:

```json
{
  "same_task_recovery": true,
  "uri_fetch_required": false
}
```

Success criteria: Exact payload and every required metadata field survive, or the authorized raw read restores them on the original task.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "public send/get bytes",
  "task/context association",
  "artifact projection",
  "raw recovery read if eligible"
]
```

## 14. development-artifact-image

Exact inline PNG bytes, name and media type

Source input:

```json
{
  "command": "image"
}
```

Required fields:

```json
[
  "raw",
  "filename",
  "mediaType"
]
```

Constraints:

```json
{
  "same_task_recovery": true,
  "uri_fetch_required": false
}
```

Success criteria: Exact payload and every required metadata field survive, or the authorized raw read restores them on the original task.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "public send/get bytes",
  "task/context association",
  "artifact projection",
  "raw recovery read if eligible"
]
```

## 15. development-contract-01

Retain a present JSON null and distinguish it from an omitted field.

Source input:

```json
{
  "x": null
}
```

Required fields:

```json
[
  "x"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 16. development-contract-02

Preserve Boolean and integer types without coercion.

Source input:

```json
{
  "x": false,
  "y": 0
}
```

Required fields:

```json
[
  "x",
  "y"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 17. development-contract-03

Preserve duplicate record multiplicity and array order.

Source input:

```json
{
  "items": [
    "a",
    "a",
    "b"
  ]
}
```

Required fields:

```json
[
  "items"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 18. development-contract-04

Bind a reread to the original task rather than a new task in the same context.

Source input:

```json
{
  "task_id": "first",
  "context_id": "shared"
}
```

Required fields:

```json
[
  "task_id",
  "context_id"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 19. development-contract-05

Retain a zero operation budget as a measured constraint.

Source input:

```json
{
  "budget": 0
}
```

Required fields:

```json
[
  "budget"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 20. development-contract-06

Preserve the allowed tool and forbidden effect requirements.

Source input:

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

Required fields:

```json
[
  "allowed_tools",
  "forbidden"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 21. development-contract-07

Preserve exact inline binary bytes in base64 form.

Source input:

```json
{
  "bytes_b64": "AAH/"
}
```

Required fields:

```json
[
  "bytes_b64"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 22. development-contract-08

Preserve an artifact URI without treating it as proof of successful retrieval.

Source input:

```json
{
  "uri": "https://example.invalid/a",
  "fetch": false
}
```

Required fields:

```json
[
  "uri",
  "fetch"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 23. development-contract-09

Report an uncaptured boundary as unknown instead of observed omission.

Source input:

```json
{
  "captured": false,
  "value": null
}
```

Required fields:

```json
[
  "status"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

## 24. development-contract-10

Do not infer capability usability from a tool advertisement alone.

Source input:

```json
{
  "tools": [
    "read"
  ],
  "read_probe": null
}
```

Required fields:

```json
[
  "usability"
]
```

Constraints:

```json
{
  "read_only": true
}
```

Success criteria: Apply the stated representation or evidence rule without imputing missing observations.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "original input",
  "boundary capture or explicit absence of capture",
  "declared comparison rule"
]
```

