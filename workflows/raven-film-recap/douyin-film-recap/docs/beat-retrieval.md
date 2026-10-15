# R1 Beat-query retrieval against R0

Default `format.visual_retrieval: r0` retains the existing event-span,
Beat-stratified equal-sampling ordinary pool. The default ordinary limit is 160;
selected highlights are appended separately under exactly the same rule.

Opt in with `format.visual_retrieval: r1`. The real storyboard-writing path calls
`retrieval.rerank_visual_pool`: dependency-free lexical query re-ranking and
round-robin allocation. Query provenance retains exact event/Beat wording,
negation and sequence; internal-motivation wording is excluded. Names/aliases
are used only from non-temporary canonical character entries. This still searches
derived observations and does not independently prove the story is correct.

Source and planned knowledge-event constraints filter before scoring. Bounded
exploration outside an event's possibly-wrong spans defaults to 15% of the
ordinary limit (`format.visual_exploration_fraction`). Exploratory records are
explicitly context-only and require raw verification; generated direct-evidence
use fails rather than silently asserting support. Nothing automatically rewrites
the StoryGraph. Full current analyzed-index/manual evidence remains accepted by
resumed visual validation, independent of the retriever's writer pool.

## Fairness is measured, not assumed

R1 uses R0's actual pretty-printed UTF-8 writer-pool fragment size (matching the prompt's indentation and nesting) as its text envelope. Optional
`format.visual_pool_text_budget` further caps both runs, including highlights.
Highlights alone exceeding it is an error. Long summaries, duplicate units and
separate highlight append counts are included. The ordinary unit ceiling never
grows to compensate for extra Beats. A stable-ID round-robin schedule avoids
always favoring early narrative Beats; uncovered Beats remain explicitly UNKNOWN.

The persisted `Storyboard.retrieval_provenance` records per-Beat rankings,
exclusion reasons, missing coverage, selected IDs, exact serialized bytes, remote
request count (zero for retrieval) and comparison work. It is not added to the
writer prompt. This existing text-only writer sends zero retrieval images.

Serialized bytes are NOT provider tokens. Without an instrumented tokenizer,
`provider_token_budget_verified=false`, token counts are null and no same-token
or same-total-compute-cost claim is made. The public reranker accepts a
`token_counter` callback for actual tokenizer instrumentation, then additionally
caps R1 at R0's measured token count. Feature/model reranking is not implemented;
no dependency, encoder, weight or remote request is introduced.

`benchmark_supporting_spans` supports conjunctions of required evidence and
alternative supporting sets. It separates full-ranked candidate recall, writer
pool recall and actual render-consumed support (UNKNOWN unless supplied).
Empty gold is NOT_RUN. These diagnostics do not claim accuracy or quality gains.

14 synthetic unittest cases cover 160+highlights accounting, real text envelopes,
instrumented token limits, Beat starvation, knowledge/source exclusions, wrong
span exploration, conjunctive gold, negation and actual storyboard integration.
