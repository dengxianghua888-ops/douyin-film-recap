# Reliability optimization plan — 2026-10-13

## Baseline and scope

Reviewed main: `399c286a8d091da0a0e4f6c7e629c7e6ea408da8`, rechecked against the remote before implementation. Work lands on `fix/reliability-optimizations-20261013`; no main updates, merges, deployments, credentials, or paid provider calls are authorized by this plan. Preserve source media, manual edits, audit evidence, and existing fail-closed safety boundaries.

## First implementation batch

Each independently testable fix receives its own commit and remote verification.

1. **Safe forced installation:** keep the lexical target, unlink the installation symlink itself, reject dangerous source/target overlap, and test link/copy reinstalls against disposable fixtures.
2. **Embedded subtitle identity:** make extraction artifacts unambiguous for same-basename and slug-colliding sources; test association and content preservation.
3. **Original audio semantics:** preserve explicitly chosen audio ownership instead of equating all must-hear-original highlights with dialogue; retain dialogue-boundary protection for actual dialogue.
4. **Queue cancellation:** after failure or interruption cancel and drain sibling tasks, stopping queued remote sends while preserving uncertain in-flight request evidence.
5. **Workspace migration:** distinguish absent optional review evidence and explicitly cleaned regenerable debug artifacts from missing required outputs; do not weaken required-file verification.
6. **Manual storyboard resume:** revalidate visual references and source bounds before downstream execution when resuming from edited storyboard content.
7. **OpenCV dependency:** use one headless cv2 provider and remove the conflicting SceneDetect OpenCV extra; inspect resolved dependencies in a clean environment where available.
8. **MCP request validation:** reject malformed params/arguments with protocol errors and keep stdio alive for subsequent valid requests.
9. **Scene fallback evidence:** record the detector actually used, fallback reason and degradation rather than claiming unavailable detection ran successfully.

## Verification and reporting

Read root and nested AGENTS.md/Skill contracts first. Run focused regression tests for every fix, then library structure verification, runtime/packaging regressions, nested skill validation and tests, and fatal Python lint. Use local synthetic fixtures and mocked providers only. Record exact passed, failed and unavailable checks; fix introduced failures. Remote CI results are evidence for the exact tested commit, not content-quality certification. Keep package member inventories consistent if new distributable files are introduced.

## Deferred work, explicitly not delivered by this batch

- Cross-window highlight refinement and whole-film recall require source-boundary design plus annotated long-form fixtures.
- Real licensed-media end-to-end quality evaluation needs authorized material, provider budgets and independent picture/audio review.
- Native host/editor adapters need concrete host APIs, conflict/readback contracts and integration tests.
- Windows portability, controlled retry of known HTTP rejections, and broader filesystem hardening warrant separate scoped designs.
- Source/package, target-client installation, real-content quality and commercial distribution remain separate release gates. No unit-test result upgrades those gates automatically.

## Completion record

All nine first-batch items are implemented as independent commits, with additional fixes for actual SceneDetect dependency resolution, interruption-state persistence, and strict legacy scene-fingerprint compatibility. See [implementation results and verification matrix](optimization-results-20261013.md). Code acceptance commit `c85fe1ce8c4f3a05213d793585c09cf6eb6b1107` passed all three existing CI jobs: 241 film tests and 65 runtime/package tests, zero failures/errors/skips, structure validation and fatal lint. The local full test installation was blocked by a proxy 403; the full-suite result is from clean remote CI, not a claim of local execution. Deferred work above remains deferred.
