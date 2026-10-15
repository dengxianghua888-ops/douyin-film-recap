# Cross-window boundary proposals (B1)

`boundary.BoundaryProposal` is an opt-in, immutable-content proposal, separate
from existing `07_highlight_candidates.json`. `validate_boundary_proposal` is a
pure callable; it does not edit sources, candidates or the workspace.

Each proposal freezes the candidate content/revision, full source SHA, current
knowledge hash, verified PTS mapping and ordered unit + analysis revisions.
Coverage is an interval union, not the min/max of distant windows. Missing
coverage, required semantic nodes, original audio or timebase remains `unknown`.
Fallback analysis windows cannot assert real shot identity. Old completeness
booleans do not migrate to semantic acceptance. `semantic_advisory` remains true
for both model accept and reject; deterministic checks are separately reported.

Editorial approval names `proposal_hash()`. It can be made within the existing
authorized editing scope; this API introduces no mandatory per-proposal user
prompt. Approval is independent of validation and does not survive content edits.

New highlight visual references carry `evidence_revision`, `source_sha256`,
`timebase_hash` and `unit_lineage`. Resumed evidence validation enforces these
for original and VO segments, rejecting old naked references to a changed
highlight as well as downgrade to a legacy candidate. Legacy unmodified
artifacts continue using their previous contract. Ordinary VO validation still
accepts the complete analyzed index, including manual evidence.

Synthetic fixtures: `python -m unittest discover -s tests -p test_boundary_contract.py`
(with `PYTHONPATH=src`). These test software contracts, not semantic film quality.
