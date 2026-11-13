# Lossless refutation-prefix DAG codec v1

11 November 2026. Implemented representation experiment; existing admission algorithms, checkers and captured results remain unchanged.

[The new codec](../../src/interoperability/refutation_prefix_dag_v1.py) packages an existing ordered `refuted_prefixes` list as a minimal suffix-shared acyclic finite-language DAG. Its independent decoder validates the representation and restores the exact original ordered list. `check_certificate` expands the original certificate and delegates semantic validity to the unchanged `refinement_oracle.check_certificate`. This changes proof packaging, not admission semantics. It does not supply a new theorem, faster checker, practical method advantage, novelty pass or project-completion credit.

The DAG fields are exactly `schema_version`, `root`, `nodes` and `word_order`. Each indexed node contains a Boolean `terminal` and sorted, uniquely labeled `arcs`; each arc contains exactly `edge` and integer `next`. Root is zero and every reference points to a later node. The encoder hash-conses equal suffix languages after building the prefix trie. `word_order` is a bounded permutation of lexicographic word ranks, preserving the original list order. A terminal may have children so redundant longer prefixes round-trip without deletion. The empty cover is one nonterminal root without arcs.

The certificate wrapper retains `profile_sha256`, `checked_at`, `horizon` and `valid_until`, changes `kind` to `refinement-prefix-dag/1`, and adds exactly `dag`. `encode_certificate` does not establish that a supplied proof is true. The old checker rejects this new kind directly; the adapter restores exactly the old `refinement-exhaustion` certificate before checking it. Positive and unknown results are outside this adapter's scope.

| Default codec bound | Value |
| --- | ---: |
| Horizon | 64 |
| Prefix count | 4,096 |
| Total expanded prefix edges | 65,536 |
| Trie/DAG nodes | 65,536 |
| Trie/DAG arcs | 65,536 |
| Serialized input, DAG or restored output | 4 MiB |
| One UTF-8 edge label | 16,384 bytes |
| Codec work units per operation | 2,000,000 |

The decoder rejects cycles/backward references, dangling or unreachable nodes, duplicated suffix languages, duplicate/unsorted arcs, invalid order permutations, empty prefix words, dead language nodes and extra fields. It separately bounds expansion, so a tiny DAG cannot return exponentially many words or a large expanded JSON payload. Work units are explicit codec operation bounds, not a hardware-cost metric. Refusal raises `DagError`; the checker adapter returns `False` on codec or semantic-checker refusal. These object APIs require an independently strict JSON reader if a caller accepts serialized untrusted input.

[The focused controls](../../tests/test_refutation_prefix_dag_v1.py) passed **25 tests** with:

```powershell
python -B -m unittest discover -s tests -p test_refutation_prefix_dag_v1.py -v
```

They verify minimality against independently constructed finite right languages, exact ordered round trips, suffix sharing and redundant-prefix preservation. Malformed and adverse checks cover structure, counts, labels, bytes, one shared codec allowance across the certificate envelope and inner DAG, profile/clock/horizon changes, incomplete coverage and sticky unknowns. The existing correlated-profile example retains both incoming frames: the `call-A,target-B` path fails while `call-B,target-B` is a modeled witness. Sharing the `finish` suffix cannot globalize the first failure. When both incoming frames really fail, the shared suffix still causes the unchanged checker to replay both prefixes. No admission solver was called by these controls.

## Read-only comparison on retained negative certificates

All **26** unsupported shared-lifting certificates in the retained budget-100000 result file were encoded, independently decoded and compared with the exact original certificate objects. All 26 round-tripped exactly. The [concrete comparison receipt](refutation-prefix-dag-comparison-v1.json) records every selected case, all 24 size increases, original/encoded/restored/direct certificate hashes and the exact input/source fingerprints. This analysis performed no new admission solver or semantic-checker runs on those retained cases; their prior checker outcomes remain inherited evidence.

Sizes below are complete certificate wrappers serialized as UTF-8 JSON with sorted keys, compact separators, `ensure_ascii=False` and `allow_nan=False`. The same serializer measures the retained goal-pruned direct certificates on the identical 26-case subset. Node/arc counts apply only to the new DAG.

| Retained case/subset | Old prefix proof bytes | DAG proof bytes | Direct proof bytes |
| --- | ---: | ---: | ---: |
| `scale-0031`, 256 prefixes, 5 nodes/16 arcs | 8,895 | 1,736 | 338 |
| `scale-0023`, 16 prefixes, 5 nodes/8 arcs | 735 | 652 | 338 |
| `scale-0039`, 2 prefixes, 5 nodes/5 arcs | 259 | 540 | 569 |
| All 26 unsupported cases | 15,128 | 11,918 | 7,760 |

Only **2 of 26** DAG proofs are smaller than their old prefix proofs; **24 grow**, none tie. The large repeated-prefix case drives the aggregate reduction. The direct comparator remains smaller in aggregate and on the largest original proof. These are deterministic representation-size observations, not solver/checker speed, memory, admission coverage or utility results.

The exact retained input is `runs/shared-lifting-scaling/v3-20261110-1/budget-100000/results.jsonl`, 981,178 bytes, SHA-256 `92137f9cc15feac73fb51b9777cd961be307c6161bf6ad5c797ef3464ff1817c`. Its original row/algorithm/certificate data was read without modification. The complete original study and its scope limits remain in [the v3 results](shared-lifting-scaling-results-v3.md).

Implementation SHA-256: `6e1b2012432945c3cec8595cafe077d69d56a6a6189001da7f7d7168f1b34c89` (13,877 bytes). Test source SHA-256: `45a2ad02c179fe34f464d0cdf20abe246856d226caf6e647594a49155f611999` (14,832 bytes). The unchanged checker remains SHA-256 `b17feac87ed2972cd1a2c34557b653bdf231345e75a9ab8a919c0b4f1520477e`; the unchanged shared lifter remains `927538f7ddcb21120913c6c4257754b65a45703db384eec8cd6a28ba9e9b280b`.

Further work would need a separately frozen experimental comparison including codec construction, expanded proof/checker work, refusals, bytes and common process costs. A semantic sharing improvement must preserve the full correlated frame, current history obligations, uncertainty, completeness and horizon; the [feasibility review](compact-refutation-feasibility-v1.md) explains why ordinary DAG compression alone does not resolve the original method contribution.
