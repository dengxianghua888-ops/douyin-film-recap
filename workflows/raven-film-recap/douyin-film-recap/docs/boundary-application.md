# Consistent boundary adoption (B2)

`boundary_apply.prepare_boundary_revision(...)` is a read-only, opt-in preparation
call. `apply_boundary_proposal(work_dir, proposal=..., base=..., config=...,
timebases=...)` invokes I2's existing generation transaction and repeats the full
preparation under its lock. The immutable base is obtained with
`revision.freeze_revision`. No alternate writable project head is introduced.

`collect_boundary_timebases(manifest)` independently binds full source bytes
before/after ffprobe and reads the first video stream time_base/start_pts and
start_time. Missing or contradictory clocks reject rather than inventing CFR.
This is a clock-identity check, not frame-perfect seek or audio alignment proof.
The mapping may be used by proposal creation and must be re-collected at apply.

The frozen approval and 07/08/09 hashes must match. Event, character and revealed
knowledge sets are recalculated against the complete new range, not the old
window. Quotes/cues are re-extracted; partial dialogue without reliable word
boundaries blocks. Source audio and dialogue requirements cannot be downgraded.
Deterministic score inputs (story significance/spoiler) and final weighted score
are refreshed; existing model scores are not falsely represented as a new model
observation. Full dedup/selection is re-evaluated on copies; a changed selected
set requires an explicit replan rather than silently changing unrelated beats.

Original segments use the approved continuous range and revised cues. Valid VO
subranges retain their range/TTS and receive only the new evidence binding.
Manual original subrange conflicts and protected content stop adoption. Beat
original/total budgets and the plan binding are updated. Reveal placement and
original ratio use the shared source/audio output clock, not planned VO budgets.
Invalid source ranges now reject during normalization instead of being clamped.

07, 08, 09 and `.receipts/boundary-adoption.json` publish through a single
workspace pointer switch. The transaction preserves old bytes, stores hashes of
the final published documents, and invalidates downstream QC/delivery. Model
accept remains advisory and no old final review is inherited. Render-current
continues with the adopted 09; it never silently regenerates the boundary.

The highlight generation ledger now retains candidates excluded by initial pool
budget and dedup, with reasons. Selected highlights alone remain writer inputs.

Synthetic verification: 12 unittest cases in `test_boundary_apply.py`, including
actual generation adoption, stale retry, source/quote synchronization, old-ref
rejection, VO subrange preservation, manual conflicts, clock mismatch, and PTS
collection. No real-film, model, or content-quality claims are made.
