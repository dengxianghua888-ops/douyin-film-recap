# Agent Operating Contract

1. Read `SKILL.md` before handling a film-recap request.
2. Treat `09_storyboard.json` as the only render truth source.
3. Do not edit, rename, overwrite, or delete the user's source media.
4. Do not bypass `pre_qc` or `post_qc` to obtain an MP4.
5. A playable file is not proof of task success. Report `PASSED`, `DEGRADED`, or `BLOCKED` exactly as the QC artifacts state.
6. Do not silently replace a configured model, TTS engine, subtitle path, or render strategy with a lower-quality fallback.
7. When the user requests automatic production, run without strategy confirmation unless a hard gate blocks. Preserve all audit artifacts.
8. Never download copyrighted film material, remove watermarks, evade content detection, or publish on the user's behalf.
9. Model observations about story or aesthetics are advisory unless independently corroborated by deterministic evidence.
10. On failure, preserve `state.json`, the last valid artifact, and the error stage so the run can resume.
