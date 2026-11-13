# Independent peer review of frozen refutation-prefix DAG v1

11 November 2026. V1 preserves the exact ordered finite language and reproduces every retained byte observation, but its documented refusal and input/work bounds have three concrete defects. A separate V2 repair is being reviewed; V1 artifacts remain frozen.

## Reviewed evidence and scope

Reviewed [implementation](../../src/interoperability/refutation_prefix_dag_v1.py), [focused tests](../../tests/test_refutation_prefix_dag_v1.py), [guide](refutation-prefix-dag-v1.md), [comparison receipt](refutation-prefix-dag-comparison-v1.json), and unchanged [semantic checker](../../src/interoperability/refinement_oracle.py). The parent reported 25 passing controls; this peer review did not rerun those controls. It executed independent byte/language recomputation and malformed built-in-object reproductions only. No admission solver or semantic checker was executed in this review. During retained recomputation, both unchanged checker entry points were patched to raise if reached.

Implementation: 13,877 bytes, SHA-256 `6e1b2012432945c3cec8595cafe077d69d56a6a6189001da7f7d7168f1b34c89`. Test source: 14,832 bytes, `45a2ad02c179fe34f464d0cdf20abe246856d226caf6e647594a49155f611999`. Unchanged checker: 25,050 bytes, `b17feac87ed2972cd1a2c34557b653bdf231345e75a9ab8a919c0b4f1520477e`. Exact source, guide, receipt, retained-input and shared-lifter hashes are recorded in the [machine-readable peer receipt](refutation-prefix-dag-peer-review-v1.json).

## Language and semantic delegation

The trie quotient merges only equal suffix languages. Forward references keep the language finite. The decoder separately validates structure and right-language minimality, enumerates words lexicographically, and uses the bounded rank permutation to restore input order. Terminal nodes retain outgoing arcs, so redundant longer refutations remain present. Empty cover behavior is preserved.

A separately implemented DFS restored every retained ordered prefix list, and separately constructed finite right languages matched every encoded node count. The adapter restores the old certificate kind and all header values before calling the unchanged checker. The checker independently replays each full prefix from the initial correlated frame set and retains sticky uncertainty, coverage, freshness and horizon obligations. There is no new correlated-frame or global-failure cache.

## Concrete V1 findings

1. **V1-F1, medium, reproduced:** `checked_at = 10**5000` is an exact integer accepted by header validation. On Python 3.13.1, serialization raises the 4,300-digit integer-conversion `ValueError`. The serializer catches other exception types, and the adapter also omits `ValueError`, so `encode_certificate` and `check_certificate` leak it instead of returning `DagError` and `False`. The checker was never reached. Relevant anchors: implementation lines 74, 265 and 314. Integer conversion also needs an explicit bound before serialization when the interpreter digit guard is disabled.

2. **V1-F2, medium, static and instrumented:** root/node/arc/header validation calls `set(dict)` before checking exact field count. Adding 10,000 extra keys caused actual set traversal lengths of 10,004, 10,002, 10,002 and 10,006 respectively with `max_work_units=1000`. Each object was eventually refused, but the extra-key traversal/allocation is unbounded and unmetered. Relevant anchors: lines 166, 184, 192 and 266. Constant-time exact dictionary length guards should precede field-set comparisons. The adapter's copy of arbitrary outer result fields also merits avoiding or explicitly scoping.

3. **V1-F3, medium, reproduced:** neither certificate direction measures the complete supplied input envelope. A one-word old proof with `checked_at=10**200`, horizon 8, `valid_until=100`, and a zero profile digest serializes to 388 bytes; its DAG wrapper is 537 bytes. `decode_certificate` accepts the 537-byte supplied wrapper at a 388-byte bound because the inner DAG and restored output fit. The 256 words in `itertools.product("ab", repeat=8)` produce a 9,086-byte supplied old certificate accepted by `encode_certificate` at a 9,000-byte bound; its prefix list is 8,705 bytes and generated wrapper 1,975 bytes. Relevant anchors: lines 279 and 290. Full input-envelope size validation should share the existing operation budget.

These findings do not falsify the observed retained round trips. They prevent accepting V1's full bounded-refusal claim.

## Independent retained byte recomputation

Read exactly `runs/shared-lifting-scaling/v3-20261110-1/budget-100000/results.jsonl`: 981,178 bytes, SHA-256 `92137f9cc15feac73fb51b9777cd961be307c6161bf6ad5c797ef3464ff1817c`. Selected all 26 retained `shared_lift` unsupported rows from the 66-row file, and measured the corresponding retained `direct_pruned` certificates on that identical subset.

Every certificate size, old/DAG/restored/direct digest, input-row digest, prefix count and node/arc count in the original receipt matches. Row digests use original JSONL bytes including their line terminator; the peer JSON additionally records canonical row digests. Complete wrappers use sorted-key compact UTF-8 JSON, `ensure_ascii=False` and `allow_nan=False`.

| Case | Old bytes | DAG bytes | Direct bytes | DAG versus old |
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

All 24 growth cases are explicitly included above and in the JSON. The largest original proof, `scale-0031`, changes from 8,895 to 1,736 DAG bytes while its retained direct proof is 338 bytes. Only `scale-0023` and `scale-0031` shrink. Existing semantic validity outcomes remain inherited evidence.

These are representation observations only. No novelty, faster-checker, full-study reexecution, method-advantage or project-completion claim is supported.

## V2 follow-up

Pending the separately owned V2 repair artifacts. This V1 peer receipt will add a clearly identified V2 delta review without rewriting the frozen V1 observations or defects.
