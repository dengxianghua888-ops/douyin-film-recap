"""Synthetic contract fixtures; no film quality or model claims."""
import unittest
from douyin_film_recap.boundary import (
    BoundaryProposal, EvidenceUnitBinding, TimebaseBinding, candidate_revision,
    proposal_hash, validate_boundary_proposal, validate_highlight_reference_binding,
)
from douyin_film_recap.models import (
    SourceManifest, SourceInfo, HighlightCandidate, SceneIndex, SceneUnit,
    SceneAnalysisDocument, SceneAnalysisItem, VisualReference,
)
from douyin_film_recap.utils import fingerprint_json


def boundary_fixture(ranges=((0, 16), (16, 32))):
    source = SourceInfo(source_id="s1", path="/synthetic/source.mp4", fingerprint="a" * 64,
                        filename="source.mp4", duration=60, width=32, height=32, fps=30)
    manifest = SourceManifest(sources=[source], config_fingerprint="config")
    candidate = HighlightCandidate(highlight_id="h1", source_id="s1", start=10, end=16,
                                   types=["action"], story_function="synthetic action", selected=True)
    index = SceneIndex(units=[SceneUnit(unit_id=f"u{i}", source_id="s1", start=a, end=b)
                       for i, (a, b) in enumerate(ranges)], source_fingerprints={"s1": source.fingerprint},
                       detector="fixed_interval", detection_status="fallback")
    analysis = SceneAnalysisDocument(provider="fixture", model="none",
        items=[SceneAnalysisItem(unit_id=u.unit_id) for u in index.units],
        unit_fingerprint=fingerprint_json([u.model_dump(mode="json") for u in index.units]))
    timebase = TimebaseBinding(mapping_version="source-pts/1", numerator=1, denominator=90000,
                               method="demux_pts", verified=True)
    proposal = BoundaryProposal(proposal_id="p1", candidate_id="h1",
        candidate_revision=candidate_revision(candidate), source_id="s1", source_sha256=source.fingerprint,
        original_range={"start": 10, "end": 16}, proposed_range={"start": 10, "end": 22},
        original_highlight_hash=fingerprint_json(candidate.model_dump(mode="json")), timebase=timebase,
        context_range={"start": 5, "end": 26}, raw_evidence_ids=["raw1"],
        shot_detection_status="fallback", required_nodes=["action", "reaction"],
        observations=[dict(node=node, state="accept", evidence_ids=["raw1"],
                           observed_range={"start": 10, "end": 22}, modality="video", method="model",
                           reviewer="fixture", version="1", reason="synthetic observation")
                      for node in ("action", "reaction")],
        ordered_evidence_units=[EvidenceUnitBinding(unit_id=u.unit_id,
            unit_revision=fingerprint_json(u.model_dump(mode="json")),
            analysis_revision=fingerprint_json(a.model_dump(mode="json")),
            source_id="s1", source_sha256=source.fingerprint,
            timebase_hash=fingerprint_json(timebase.model_dump(mode="json")))
            for u, a in zip(index.units, analysis.items)],
        knowledge_snapshot_hash="b" * 64, producer="fixture", prompt_version="1")
    proposal.proposal_content_hash = proposal_hash(proposal)
    return proposal, dict(manifest=manifest, candidate=candidate, scene_index=index,
        scene_analysis=analysis, knowledge_snapshot_hash="b" * 64, timebases={"s1": timebase})


class BoundaryContractTests(unittest.TestCase):
    def check(self, proposal, kwargs, expected):
        result = validate_boundary_proposal(proposal, **kwargs)
        self.assertEqual(result.validation_state, expected)
        return result

    def test_cross_16_seconds_is_representable_and_advisory(self):
        p, kw = boundary_fixture()
        result = self.check(p, kw, "accept")
        self.assertTrue(result.semantic_advisory)
        self.assertEqual(result.covered_intervals[0].end, 22)
        self.assertEqual(kw["candidate"].end, 16)

    def test_middle_gap_not_min_max_bridge(self):
        p, kw = boundary_fixture(((0, 16), (18, 32)))
        result = self.check(p, kw, "unknown")
        self.assertEqual([(g.start, g.end) for g in result.coverage_gaps], [(16, 18)])

    def test_source_same_name_changed_bytes_rejected(self):
        p, kw = boundary_fixture()
        kw["manifest"].sources[0].fingerprint = "c" * 64
        self.check(p, kw, "reject")

    def test_stale_candidate_and_index_rejected(self):
        for field in ("candidate", "scene_index"):
            p, kw = boundary_fixture()
            if field == "candidate":
                kw[field].end = 17
            else:
                kw[field].units[0].end = 17
            self.check(p, kw, "reject")

    def test_vfr_requires_actual_mapping(self):
        p, kw = boundary_fixture()
        p.timebase.verified = False
        p.proposal_content_hash = proposal_hash(p)
        self.check(p, kw, "reject")  # unit mapping hash also changed
        p, kw = boundary_fixture()
        kw["timebases"] = {}
        self.check(p, kw, "unknown")

    def test_fallback_cannot_claim_real_shot(self):
        p, kw = boundary_fixture()
        p.evidence_shot_ids = ["pretend-shot"]
        p.proposal_content_hash = proposal_hash(p)
        self.check(p, kw, "reject")

    def test_mixed_detector_cannot_certify_invented_or_other_source_shot(self):
        p, kw = boundary_fixture()
        p.shot_detection_status = "mixed"
        kw["scene_index"].detection_status = "mixed"
        p.evidence_shot_ids = ["nonexistent-shot-from-other-source"]
        p.proposal_content_hash = proposal_hash(p)
        self.check(p, kw, "reject")

    def test_old_true_complete_does_not_become_accept(self):
        p, kw = boundary_fixture()
        self.assertTrue(kw["candidate"].boundary.action_complete)
        p.observations = []
        p.proposal_content_hash = proposal_hash(p)
        self.check(p, kw, "unknown")

    def test_audio_and_silence_do_not_invent_sentence_requirement(self):
        p, kw = boundary_fixture()
        p.must_preserve_source_track = True
        p.proposal_content_hash = proposal_hash(p)
        self.check(p, kw, "unknown")
        p.audio_evidence_ids = ["audio1"]
        p.source_audio_stream_id = "a:0"
        p.observed_audio_roles = ["silence", "ambience"]
        p.observations.append(p.observations[0].model_copy(update={
            "node": "sound", "modality": "audio", "evidence_ids": ["audio1"]}))
        p.proposal_content_hash = proposal_hash(p)
        self.check(p, kw, "accept")
        p.dialogue_required = True
        p.proposal_content_hash = proposal_hash(p)
        self.check(p, kw, "unknown")

    def test_approval_does_not_survive_content_change(self):
        p, kw = boundary_fixture()
        p.editorial_decision = "approved"
        p.approved_proposal_hash = p.proposal_content_hash
        p.proposed_range.end = 23
        self.check(p, kw, "reject")
        self.assertNotEqual(p.approved_proposal_hash, proposal_hash(p))

    def test_reused_id_does_not_rebind_old_visual(self):
        _, kw = boundary_fixture()
        h = kw["candidate"]
        binding = dict(evidence_revision="d" * 64, source_sha256="a" * 64,
                       timebase_hash="e" * 64, unit_lineage=["u0", "u1"])
        for k, v in binding.items():
            setattr(h, k, v)
        v = VisualReference(source_id="s1", start=10, end=16, unit_id="highlight:h1", highlight_id="h1")
        with self.assertRaisesRegex(ValueError, "Stale"):
            validate_highlight_reference_binding(v, h)
        for k, value in binding.items():
            setattr(v, k, value)
        validate_highlight_reference_binding(v, h)
        h.evidence_revision = "f" * 64
        with self.assertRaises(ValueError):
            validate_highlight_reference_binding(v, h)


if __name__ == "__main__":
    unittest.main()
