# Proposed gold: pending human review

Compare after deriving your own answer. These are expected contract objects; flag ambiguous field names or differences from the actual output schema.

## 1. heldout-01

```json
{
  "ordered_ids": [
    "r2",
    "r3",
    "r4",
    "r1"
  ]
}
```

## 2. heldout-02

```json
{
  "intervals": [
    [
      1,
      8
    ],
    [
      10,
      12
    ]
  ]
}
```

## 3. heldout-03

```json
{
  "total": "2.72",
  "currency": "USD"
}
```

## 4. heldout-04

```json
{
  "pairs": [
    [
      "l1",
      "r1"
    ],
    [
      "l1",
      "r2"
    ],
    [
      "l2",
      "r1"
    ],
    [
      "l2",
      "r2"
    ]
  ]
}
```

## 5. heldout-05

```json
{
  "merged": {
    "y": 5
  },
  "conflicts": {
    "x": {
      "base": 1,
      "left": 3,
      "right": 4
    }
  }
}
```

## 6. heldout-06

```json
{
  "A": "alpha",
  "B": "beta"
}
```

## 7. heldout-07

```json
{
  "valid": false,
  "reason": "flag_type"
}
```

## 8. heldout-08

```json
{
  "selected_tools": [
    "B",
    "C"
  ],
  "total_cost": 3
}
```

## 9. heldout-09

```json
{
  "text": "π\n",
  "reconstructed_bytes": 3,
  "sha256": "d59279f283574337bf8ff32c34b0d17ead2e8290702ca429e9e4f14200939d56"
}
```

## 10. heldout-10

```json
{
  "manifest": [
    {
      "path": "a.txt",
      "bytes": 1,
      "sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
    },
    {
      "path": "b.bin",
      "bytes": 2,
      "sha256": "06eb7d6a69ee19e5fbdf749018d3d2abfa04bcbd1365db312eb86dc7169389b8"
    }
  ]
}
```

## 11. heldout-11

```json
{
  "status": "snapshot_conflict",
  "versions": [
    7,
    8
  ]
}
```

## 12. heldout-12

```json
{
  "ordered_event_ids": [
    "e1",
    "e2"
  ],
  "retry_count": 1
}
```

## 13. heldout-13

```json
{
  "effective": [
    "read"
  ]
}
```

## 14. heldout-14

```json
{
  "metres": [
    {
      "id": "x",
      "value": "1.25"
    },
    {
      "id": "y",
      "value": "-0.5"
    }
  ]
}
```

## 15. heldout-15

```json
{
  "utc": "2024-02-29T18:00:00Z"
}
```

## 16. heldout-16

```json
{
  "sum": "1/4"
}
```

## 17. heldout-17

```json
{
  "status": "normalization_conflict",
  "normalized_key": "é",
  "original_entries": [
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

## 18. heldout-18

```json
{
  "status": "incompatible_schema",
  "lost_required_fields": [
    "integrity"
  ]
}
```

## 19. heldout-19

```json
{
  "origin_task": "task-merkle",
  "leaf_ids": [
    "a",
    "b"
  ],
  "root_sha256": "e5a01fee14e0ed5c48714f22180f25ad8365b53f9779f79dc4a3d7e93963f94a"
}
```

## 20. heldout-20

```json
{
  "task": "root-task",
  "edges": [
    [
      "main",
      "aux"
    ]
  ],
  "uri_bindings": {
    "aux": "urn:artifact:aux"
  }
}
```

