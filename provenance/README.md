# Evidence and migration provenance

history.json and version-families.json record the original source history and legacy generations. source-audit.json records owned-source analysis; inventory is not semantic or scientific verification. The original complete Git bundle and owned-source/delivery archives remain outside the published repository.

migration-files.json records original file identity, final disposition and relocated paths. A byte-preserved status applies to the recorded original import; later explicit derivatives are identified in distribution-redactions.json and distribution-derivatives.json. Do not infer that every file in the original delivery manifest is redistributed.

Distribution ledgers record original/distributed hashes and scopes. Ignored results/local preserves canonical bytes, including content-addressed originals of the broader configuration redaction pass. Scientific task definitions, evaluated historical v2 cells and numerical metrics remain unchanged; configuration/setup packet sizes and hashes describe redacted distribution observations. scientific-preservation-check.json verifies 6,331 scored historical files against canonical import hashes. original-preservation-check.json separately verifies the original checkout's owned files and Git status.

publication-history.json records the pre-publication export of sanitized milestones. Unredacted local objects and preservation refs are not published. No remote history rewrite or force push was used. Current validation receipts distinguish failing attempts, regrading, fresh execution and pending human/scientific review.
