# Heldout tasks: 20 examples

Canonical tasks.json SHA-256: dcc3a6e6b48c9281c27a03421ede77448bbd047874779fe1be6133dbb6a14efa

Read the source and rules, then derive an answer before opening PROPOSED_GOLD.md. Ambiguities are review findings; these proposals are not assumed correct.

## 1. heldout-01

Stable multi-key sorting: category ascending, score descending, equal keys retain source order.

Source input:

```json
{
  "rows": [
    {
      "id": "r1",
      "category": "b",
      "score": 2
    },
    {
      "id": "r2",
      "category": "a",
      "score": 3
    },
    {
      "id": "r3",
      "category": "a",
      "score": 3
    },
    {
      "id": "r4",
      "category": "a",
      "score": 1
    }
  ]
}
```

Required fields:

```json
[
  "ordered_ids"
]
```

Constraints:

```json
{
  "stable_ties": true
}
```

Success criteria: Retain every row exactly once in the specified order.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 2. heldout-02

Union half-open intervals; overlapping or touching intervals merge, gaps stay separate.

Source input:

```json
{
  "intervals": [
    [
      1,
      4
    ],
    [
      3,
      7
    ],
    [
      7,
      8
    ],
    [
      10,
      12
    ]
  ]
}
```

Required fields:

```json
[
  "intervals"
]
```

Constraints:

```json
{
  "half_open": true
}
```

Success criteria: Return the exact disjoint union.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 3. heldout-03

Compute a two-line invoice with exact decimal arithmetic and round the final sum to two decimals using half-even.

Source input:

```json
{
  "lines": [
    {
      "quantity": 3,
      "unit_price": "0.105"
    },
    {
      "quantity": 2,
      "unit_price": "1.20"
    }
  ]
}
```

Required fields:

```json
[
  "total",
  "currency"
]
```

Constraints:

```json
{
  "currency": "USD",
  "rounding": "ROUND_HALF_EVEN"
}
```

Success criteria: Do not round individual lines or use binary-float display as the gold.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 4. heldout-04

Composite-key many-to-many join, retaining all match multiplicities and source left/right order.

Source input:

```json
{
  "left": [
    {
      "k": [
        "a",
        1
      ],
      "id": "l1"
    },
    {
      "k": [
        "a",
        1
      ],
      "id": "l2"
    }
  ],
  "right": [
    {
      "k": [
        "a",
        1
      ],
      "id": "r1"
    },
    {
      "k": [
        "a",
        1
      ],
      "id": "r2"
    },
    {
      "k": [
        "a",
        2
      ],
      "id": "r3"
    }
  ]
}
```

Required fields:

```json
[
  "pairs"
]
```

Constraints:

```json
{
  "key_fields": [
    "name",
    "revision"
  ]
}
```

Success criteria: Match composite keys with no duplicate collapse.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 5. heldout-05

Merge independent edits to a base object and explicitly report a same-field conflict.

Source input:

```json
{
  "base": {
    "x": 1,
    "y": 2
  },
  "left": {
    "x": 3,
    "y": 2
  },
  "right": {
    "x": 4,
    "y": 5
  }
}
```

Required fields:

```json
[
  "merged",
  "conflicts"
]
```

Constraints:

```json
{
  "no_silent_conflict_resolution": true
}
```

Success criteria: Retain competing values and provenance rather than selecting an arbitrary winner.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 6. heldout-06

Correlate interleaved tasks sharing a context; task identity takes precedence over arrival order.

Source input:

```json
{
  "context": "ctx",
  "tasks": [
    {
      "id": "A",
      "expected": "alpha"
    },
    {
      "id": "B",
      "expected": "beta"
    }
  ],
  "received": [
    {
      "task": "B",
      "answer": "beta"
    },
    {
      "task": "A",
      "answer": "alpha"
    }
  ]
}
```

Required fields:

```json
[
  "A",
  "B"
]
```

Constraints:

```json
{
  "cross_task_contamination": false
}
```

Success criteria: Produce the original task association for each answer.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 7. heldout-07

Validate a strict Boolean field and reject an integer value without coercion.

Source input:

```json
{
  "schema": {
    "flag": "boolean",
    "additional_fields": false
  },
  "payload": {
    "flag": 1
  }
}
```

Required fields:

```json
[
  "valid",
  "reason"
]
```

Constraints:

```json
{
  "coercion": false
}
```

Success criteria: A numeric one is not the declared Boolean type.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 8. heldout-08

Select the cheapest legal set of tools covering both required capabilities under a total cost budget; exclude forbidden tools.

Source input:

```json
{
  "required": [
    "c1",
    "c2"
  ],
  "tools": [
    {
      "id": "A",
      "covers": [
        "c1",
        "c2"
      ],
      "cost": 5
    },
    {
      "id": "B",
      "covers": [
        "c1"
      ],
      "cost": 1
    },
    {
      "id": "C",
      "covers": [
        "c2"
      ],
      "cost": 2
    },
    {
      "id": "D",
      "covers": [
        "c1",
        "c2"
      ],
      "cost": 1
    }
  ],
  "forbidden": [
    "D"
  ],
  "budget": 4
}
```

Required fields:

```json
[
  "selected_tools",
  "total_cost"
]
```

Constraints:

```json
{
  "forbidden_tools": [
    "D"
  ],
  "maximum_cost": 4,
  "tie_rule": "lexicographic ordered tool-ID list"
}
```

Success criteria: Return the minimum-cost allowed covering set and preserve the policy/budget evidence.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 9. heldout-09

Decode a UTF-8 stream whose multi-byte code point is split across frame boundaries, retaining exact reconstructed byte evidence.

Source input:

```json
{
  "frames_b64": [
    "zw==",
    "gA==",
    "Cg=="
  ],
  "encoding": "utf-8"
}
```

Required fields:

```json
[
  "text",
  "reconstructed_bytes",
  "sha256"
]
```

Constraints:

```json
{
  "decode_after_ordered_reassembly": true,
  "invalid_utf8": "reject"
}
```

Success criteria: Reassemble frames in order before decoding; no replacement characters, dropped frames or independent per-frame decoding.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 10. heldout-10

Preserve a two-entry artifact manifest with mixed text/binary content and distinct file identities.

Source input:

```json
{
  "entries": {
    "a.txt": "YQ==",
    "b.bin": "AP8="
  }
}
```

Required fields:

```json
[
  "manifest"
]
```

Constraints:

```json
{
  "file_order": [
    "a.txt",
    "b.bin"
  ]
}
```

Success criteria: Keep both entries and verify every individual content digest.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 11. heldout-11

Combine paginated records only when their snapshot versions agree.

Source input:

```json
{
  "pages": [
    {
      "version": 7,
      "items": [
        "a"
      ],
      "next": "p2"
    },
    {
      "version": 8,
      "items": [
        "b"
      ],
      "next": null
    }
  ]
}
```

Required fields:

```json
[
  "status",
  "versions"
]
```

Constraints:

```json
{
  "single_snapshot": true
}
```

Success criteria: Expose version inconsistency rather than silently combining records.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 12. heldout-12

Deduplicate event retries by event identity while preserving the declared dependency order.

Source input:

```json
{
  "events": [
    {
      "id": "e2",
      "after": "e1"
    },
    {
      "id": "e1",
      "after": null
    },
    {
      "id": "e1",
      "after": null
    }
  ]
}
```

Required fields:

```json
[
  "ordered_event_ids",
  "retry_count"
]
```

Constraints:

```json
{
  "identity_based_deduplication": true
}
```

Success criteria: Distinguish a repeated observation from an additional effect.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 13. heldout-13

Intersect parent and child authorization scopes without widening either.

Source input:

```json
{
  "parent": [
    "read",
    "list"
  ],
  "child": [
    "read",
    "write"
  ]
}
```

Required fields:

```json
[
  "effective"
]
```

Constraints:

```json
{
  "scope_rule": "intersection"
}
```

Success criteria: A child request cannot add parent-forbidden capabilities.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 14. heldout-14

Convert measurements using explicit rational unit factors and retain measurement identities.

Source input:

```json
{
  "measurements": [
    {
      "id": "x",
      "millimetres": 1250
    },
    {
      "id": "y",
      "millimetres": -500
    }
  ]
}
```

Required fields:

```json
[
  "metres"
]
```

Constraints:

```json
{
  "factor": "1/1000"
}
```

Success criteria: Preserve sign, units and record association without hidden rounding.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 15. heldout-15

Convert an explicit-offset leap-day timestamp to UTC without changing the instant.

Source input:

```json
{
  "timestamp": "2024-02-29T23:30:00+05:30"
}
```

Required fields:

```json
[
  "utc"
]
```

Constraints:

```json
{
  "timezone_required": true
}
```

Success criteria: Preserve the exact instant and timezone provenance.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 16. heldout-16

Aggregate rational quantities exactly, returning a reduced rational fraction.

Source input:

```json
{
  "quantities": [
    "1/3",
    "1/6",
    "-1/4"
  ]
}
```

Required fields:

```json
[
  "sum"
]
```

Constraints:

```json
{
  "arithmetic": "rational"
}
```

Success criteria: Return 1/4, with no decimal tolerance substitution.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 17. heldout-17

Detect a key collision introduced by NFC normalization and retain both original keys/values without overwriting.

Source input:

```json
{
  "entries": [
    {
      "key": "é",
      "value": 1
    },
    {
      "key": "é",
      "value": 2
    }
  ]
}
```

Required fields:

```json
[
  "status",
  "normalized_key",
  "original_entries"
]
```

Constraints:

```json
{
  "normalization": "NFC",
  "silent_overwrite": false
}
```

Success criteria: Report the normalization-induced collision and preserve both competing original entries.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 18. heldout-18

Reject a schema downgrade that would drop a required v2 integrity field.

Source input:

```json
{
  "source_version": 2,
  "receiver_version": 1,
  "payload": {
    "body": "abc",
    "integrity": "required"
  }
}
```

Required fields:

```json
[
  "status",
  "lost_required_fields"
]
```

Constraints:

```json
{
  "lossy_downgrade_allowed": false
}
```

Success criteria: Report the incompatibility with evidence rather than a partial successful delivery.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 19. heldout-19

Construct an ordered two-leaf Merkle root for task-bound artifact bytes, with distinct leaf identities and no hex-text substitution.

Source input:

```json
{
  "origin_task": "task-merkle",
  "leaves": [
    {
      "id": "a",
      "bytes_b64": "YQ=="
    },
    {
      "id": "b",
      "bytes_b64": "Yg=="
    }
  ]
}
```

Required fields:

```json
[
  "origin_task",
  "leaf_ids",
  "root_sha256"
]
```

Constraints:

```json
{
  "leaf_order": [
    "a",
    "b"
  ],
  "algorithm": "SHA256(SHA256(raw_a) bytes || SHA256(raw_b) bytes)"
}
```

Success criteria: Compute the exact binary digest concatenation and preserve originating task/leaf association; this is content integrity, not authenticated authorship.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

## 20. heldout-20

Preserve a nested artifact attachment reference chain and its originating task.

Source input:

```json
{
  "task": "root-task",
  "artifact": {
    "id": "main",
    "attachments": [
      {
        "id": "aux",
        "parent": "main",
        "uri": "urn:artifact:aux"
      }
    ]
  }
}
```

Required fields:

```json
[
  "task",
  "edges",
  "uri_bindings"
]
```

Constraints:

```json
{
  "no_reference_rebinding": true
}
```

Success criteria: Retain the origin, child identity and URI association.

Protocol assumptions: A2A message/task and MCP tool transports may encode the task; semantic support must be qualified separately. No promise that existing routes solve this new family.

Evidence requirements:

```json
[
  "frozen source/task/gold proposal hashes",
  "source/sent/received captures",
  "task/context binding",
  "actual final output and any tool/effect evidence"
]
```

