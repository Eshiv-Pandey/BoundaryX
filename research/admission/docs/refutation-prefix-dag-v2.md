# Lossless refutation-prefix DAG codec v2

11 November 2026. Separate successor to the frozen [V1 codec](refutation-prefix-dag-v1.md). The V1 implementation, tests, comparison receipt, defect review and original solver outputs remain unchanged.

[V2 implementation](../../src/interoperability/refutation_prefix_dag_v2.py) retains lossless ordered-prefix packaging, minimal suffix sharing and semantic delegation to the unchanged `refinement_oracle.check_certificate`. It uses `refutation-prefix-language-dag/2` and certificate kind `refinement-prefix-dag/2`. The new codec does not connect to or modify the existing admission algorithms. It supplies no new semantic theorem, faster-checker claim, practical method advantage, novelty pass or project-completion credit.

The [independent V1 defect review](refutation-prefix-dag-peer-review-v1.md) identified an uncaught Python integer-serialization `ValueError`, oversized dictionary key traversal before shape refusal, and missing complete input-certificate envelope bounds. V2 applies the following concrete repairs:

- Exact dictionary lengths are checked before constructing field-key sets at certificate headers, DAG roots, nodes and arcs. Normal shape checks materialize only bounded key sets.
- Prefix/DAG payloads receive bounded shape preflight before JSON serialization can sort nested keys. The complete input certificate is then size-checked with the same codec allowance before DAG construction or language expansion. Complete output bounds remain separate.
- Every header integer has a default 4,096-bit magnitude bound before decimal conversion, also capped relative to the serialized-byte allowance. This prevents huge clock conversion even if Python's digit guard is disabled. If a caller explicitly raises the bit allowance and Python rejects conversion, serialization `ValueError` becomes `DagError`; the semantic adapter returns `False`.
- The adapter delegates only `decision` and the exact restored certificate. It does not clone arbitrary extra fields from the outer result dictionary.

These are object-API bounds. A caller accepting serialized untrusted input still needs an independently strict JSON reader. Codec work units count declared operations; they are not a hardware-time or memory metric. A codec refusal does not establish an admission decision.

| Default codec bound | Value |
| --- | ---: |
| Horizon | 64 |
| Prefix count | 4,096 |
| Total expanded prefix edges | 65,536 |
| Trie/DAG nodes and arcs, each | 65,536 |
| Serialized prefix input, DAG, restored output and complete certificate envelopes | 4 MiB |
| One UTF-8 edge label | 16,384 bytes |
| Header integer magnitude | 4,096 bits |
| Codec work allowance per complete API call | 2,000,000 |

[V2 controls](../../tests/test_refutation_prefix_dag_v2.py) passed **31 tests**:

```powershell
python -B -m unittest discover -s tests -p test_refutation_prefix_dag_v2.py -v
```

They retain the V1 structural, lossless-language, independent minimality, correlated-frame, sticky-unknown, clock/profile, expansion and shared-budget checks. New actual adverse cases cover `checked_at = 10**5000` with Python's digit guard enabled and disabled, an explicitly raised integer allowance, 10,000 extra dictionary keys, malformed nested payloads before JSON key sorting, and minimal outer-result delegation. The exact full-input cases reject a 537-byte supplied DAG certificate under a 388-byte limit and a 9,086-byte original certificate under a 9,000-byte limit before expansion/construction. No admission solver is called by these controls.

## Fresh read-only comparison on the same retained certificates

The [V2 comparison receipt](refutation-prefix-dag-comparison-v2.json) freshly encodes and independently decodes all **26** retained unsupported shared-lifting certificates, restoring their exact ordered objects and canonical bytes. Every selected row, all 24 size increases, original/encoded/restored/direct certificate hashes, V2 source hashes and preserved V1 fingerprints are recorded. No admission solver or semantic checker was rerun on those retained cases; their original checker outcomes remain inherited evidence.

Complete certificate sizes use UTF-8 JSON, sorted keys, compact separators, `ensure_ascii=False` and `allow_nan=False`. The direct comparison uses the identical 26-case subset, not the full 54 certified cases.

| Retained case/subset | Old prefix proof bytes | V2 DAG proof bytes | Direct proof bytes |
| --- | ---: | ---: | ---: |
| `scale-0031`: 256 prefixes, 5 nodes/16 arcs | 8,895 | 1,736 | 338 |
| `scale-0023`: 16 prefixes, 5 nodes/8 arcs | 735 | 652 | 338 |
| `scale-0039`: 2 prefixes, 5 nodes/5 arcs | 259 | 540 | 569 |
| All 26 unsupported cases | 15,128 | 11,918 | 7,760 |

Only **2 of 26** DAG certificates shrink relative to their old prefix proofs; **24 grow**, none tie. The aggregate bytes equal V1 because the version labels have equal length and the repairs change validation, not the encoded language. Direct remains smaller in aggregate and on the largest original proof. These are representation-size observations, not solver/checker speed, resource rankings, admission coverage or application utility results.

Exact retained input: `runs/shared-lifting-scaling/v3-20261110-1/budget-100000/results.jsonl`, 981,178 bytes, SHA-256 `92137f9cc15feac73fb51b9777cd961be307c6161bf6ad5c797ef3464ff1817c`. V2 implementation: 15,326 bytes, SHA-256 `59794e5bd480763152577af37b1428cf4dcb737681dc380d8abd3c3ea3dc8449`. V2 test source: 21,604 bytes, SHA-256 `584d53584989d63f5719a9d413e24303ad72882244fc34871af2a1cd894c4356`. The V2 comparison receipt binds these inputs and the unchanged semantic checker. Independent whole-study qualification, method assessment and any common-cost performance comparison remain separate work.
