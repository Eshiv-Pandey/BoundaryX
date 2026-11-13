# Independent peer review of refutation-prefix DAG v2

11 November 2026. V2 fixes all three concrete V1 refusal/bounds findings and independently preserves every retained ordered-language and byte observation. No additional concrete defect was found within this scoped review.

## Exact revision and scope

Reviewed the final [V2 implementation](../../src/interoperability/refutation_prefix_dag_v2.py), [31-test source](../../tests/test_refutation_prefix_dag_v2.py), [guide](refutation-prefix-dag-v2.md) and [comparison receipt](refutation-prefix-dag-comparison-v2.json), against the frozen [V1 defect review](refutation-prefix-dag-peer-review-v1.md) and unchanged semantic checker. The repair owner reported 31 passing tests; this peer reviewer did not rerun that suite. This review ran separate actual adverse reproductions, work/field-set instrumentation, a delegation stub, and retained byte/language recomputation. It executed no admission solver or real semantic checker.

V2 implementation: **15,326 bytes**, SHA-256 `59794e5bd480763152577af37b1428cf4dcb737681dc380d8abd3c3ea3dc8449`. The same source hash was used for the independent recomputation and remained unchanged through final inspection. V2 test source: 21,604 bytes, `584d53584989d63f5719a9d413e24303ad72882244fc34871af2a1cd894c4356`. V2 guide: 5,803 bytes, `e9d04aee30140d0893f2aeea187f8d4a7ccd68eb00a2d0b426f73027de68355e`. V2 comparison receipt: 28,422 bytes, `7323bf3824bf7edd208f302d51d004cb225b3de06865c877a5b1230b277396a1`.

Full source and preserved artifact fingerprints, actual control outcomes and all 26 per-case certificate hashes are in the [V2 peer receipt](refutation-prefix-dag-peer-review-v2.json). The V1 peer files remain untouched because the V2 comparison binds their frozen hashes.

## Independently verified repairs

| V1 finding | V2 mechanism | Actual peer verification |
| --- | --- | --- |
| Huge integer serialization leaks `ValueError` | Exact header integer type and bounded `bit_length()` before decimal conversion; catch serializer `ValueError` while preserving `DagError` | `10**5000` refuses with `DagError` under default bounds even with Python's digit guard disabled. With a raised 30,000-bit allowance, Python's digit refusal becomes `DagError`. Both adapter cases return `False`. |
| Extra keys cause unmetered `set(dict)` work | Exact field counts before key sets; bounded nested payload preflight; minimal delegated result | For 10,000 extra keys, observed field-set inputs are `[]`, `[4]`, `[4,2]`, `[]` at DAG/node/arc/header. No overlarge dictionary reaches `set`. Malformed nested objects refuse before the serializer. The checker stub receives only `decision` and the exact old certificate. |
| Complete supplied certificate input escapes byte bound | Validate shape, then serialize the entire supplied wrapper using the existing allowance before construction/expansion | The original 537-byte/388-limit decode and 9,086-byte/9,000-limit encode reproductions both refuse with `serialized_byte_bound_exceeded`. |

The measured one-word controls charge exactly one budget per operation. Prefix encode, full certificate encode, prefix decode and full certificate decode consume 61, 161, 67 and 119 units respectively. Each succeeds at that exact allowance and refuses at one unit less. The complete input and output passes share the payload's existing allowance. These measurements establish operation accounting for the controls; they do not rank hardware time or memory.

V1's findings remain open in its frozen source. Their fixed dispositions apply to V2 only.

## Language, frame preservation and semantic delegation

The representation algorithm retains terminal flags and equal sorted edge/right-language signatures. The independently validating decoder restores lexicographic words and then the original input permutation. It preserves terminal nodes with outgoing arcs and exact header values. The new `/2` labels identify the distinct representation revision.

The certificate decoder's private preflight bypass is used only after bounded shape validation and full input-envelope serialization. Expansion still independently bounds horizon, word count, total prefix edges, work and restored serialized output. The semantic adapter restores `refinement-exhaustion` and passes only the negative decision and original certificate to unchanged `refinement_oracle.check_certificate`.

The unchanged checker still replays every full prefix from its correlated frame set and retains sticky uncertainty, complete coverage, freshness and horizon obligations. No semantic node cache or global failed-frame shortcut was added. This preserves the delegated semantics; it does not establish a new admission theorem.

## Independent retained comparison

The exact retained input remains 981,178 bytes, SHA-256 `92137f9cc15feac73fb51b9777cd961be307c6161bf6ad5c797ef3464ff1817c`. All 26 `shared_lift` unsupported rows were selected from the same 66-row budget-100000 file; the retained `direct_pruned` comparator uses that identical subset.

Every V2 receipt field matches, including old, DAG, restored and direct certificate digests, original raw JSONL row digests, prefix counts and node/arc counts. A separately implemented DFS reproduces the original ordered words, and separately constructed finite right languages match each node count. The unchanged solver/checker entry points were patched to fail if invoked during this retained recomputation; neither was invoked.

Complete wrappers use sorted-key compact UTF-8 JSON with `ensure_ascii=False` and `allow_nan=False`.

| Case | Old bytes | V2 DAG bytes | Direct bytes | DAG versus old |
| --- | ---: | ---: | ---: | --- |
| `scale-0003` | 201 | 350 | 239 | grows |
| `scale-0007` | 201 | 350 | 239 | grows |
| `scale-0011` | 201 | 350 | 239 | grows |
| `scale-0015` | 201 | 350 | 239 | grows |
| `scale-0018` | 211 | 378 | 242 | grows |
| `scale-0019` | 263 | 462 | 272 | grows |
| `scale-0022` | 211 | 378 | 248 | grows |
| `scale-0023` | 735 | 652 | 338 | smaller |
| `scale-0026` | 231 | 434 | 242 | grows |
| `scale-0027` | 479 | 596 | 272 | grows |
| `scale-0030` | 231 | 434 | 248 | grows |
| `scale-0031` | 8895 | 1736 | 338 | smaller |
| `scale-0035` | 227 | 432 | 349 | grows |
| `scale-0039` | 259 | 540 | 569 | grows |
| `scale-0043` | 263 | 488 | 457 | grows |
| `scale-0047` | 327 | 596 | 893 | grows |
| `scale-0049` | 192 | 296 | 209 | grows |
| `scale-0052` | 192 | 296 | 215 | grows |
| `scale-0056` | 201 | 350 | 239 | grows |
| `scale-0057` | 201 | 350 | 239 | grows |
| `scale-0059` | 201 | 350 | 239 | grows |
| `scale-0060` | 201 | 350 | 239 | grows |
| `scale-0062` | 201 | 350 | 239 | grows |
| `scale-0063` | 201 | 350 | 239 | grows |
| `scale-0065` | 201 | 350 | 239 | grows |
| `scale-0066` | 201 | 350 | 239 | grows |
| **Total** | **15,128** | **11,918** | **7,760** | **2 smaller, 24 grow, 0 ties** |

Every per-case size equals V1, while the new representation version changes DAG certificate hashes. Only `scale-0023` and `scale-0031` shrink. All 24 growth cases are recorded. Direct remains smaller in aggregate and on the largest original proof, where `scale-0031` is 8,895 old / 1,736 DAG / 338 direct bytes.

The frozen V1 implementation, tests, guide, comparison and peer reports retain their hashes. The unchanged semantic checker remains `b17feac87ed2972cd1a2c34557b653bdf231345e75a9ab8a919c0b4f1520477e`; the shared lifter remains `927538f7ddcb21120913c6c4257754b65a45703db384eec8cd6a28ba9e9b280b`.

This review supports the scoped codec repair and deterministic representation observations. It establishes no novelty, faster checker, method advantage, full-study qualification or project-completion credit. Retained semantic validity remains inherited evidence, and serialized untrusted input still requires a separately strict JSON reader.
