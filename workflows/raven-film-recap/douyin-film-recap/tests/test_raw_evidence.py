"""Local generated media only. Tests prove isolation/binding, not film semantics."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest
from pydantic import ValidationError
from douyin_film_recap.boundary import Interval
from douyin_film_recap.models import SourceInfo, SourceManifest
from douyin_film_recap.raw_evidence import (
    RawEvidenceCard, DerivedClaim, create_raw_evidence_card, verify_raw_evidence, verify_claim,
)
from douyin_film_recap.utils import content_fingerprint, run_command


class RawEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        cls.source_path=cls.root/"synthetic.mkv"
        run_command(["ffmpeg","-v","error","-nostdin","-n","-f","lavfi","-i",
            "color=c=red:s=32x32:r=5:d=2","-f","lavfi","-i","sine=frequency=440:sample_rate=8000:duration=2",
            "-c:v","ffv1","-c:a","pcm_s16le",str(cls.source_path)],timeout=30)
        source=SourceInfo(source_id="s1",path=str(cls.source_path),fingerprint=content_fingerprint(cls.source_path),
            filename="synthetic.mkv",duration=2,width=32,height=32,fps=5,has_audio=True)
        cls.manifest=SourceManifest(sources=[source],config_fingerprint="fixture")
        cls.card=create_raw_evidence_card(manifest=cls.manifest,source_id="s1",
            source_range=Interval(start=.2,end=1.8),evidence_root=cls.root,
            include_video=True,include_audio=True,sample_times=[.4],evidence_id="raw1")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def claim(self,kind="action"):
        return DerivedClaim(claim_id="claim1",generation_revision="a"*64,exact_text="A synthetic red frame appears.",
            claim_type=kind,proposed_support_ids=["raw1"])

    def verify(self,claim=None,cards=None,observer=None,judge=None):
        return verify_claim(claim or self.claim(), cards if cards is not None else [self.card],
            manifest=self.manifest,evidence_root=self.root,observer=observer,judge=judge,
            reviewer="fixture-observer",version="1")

    @staticmethod
    def observes(payload,relation="support"):
        return [{"node":"claim","evidence_id":a["evidence_id"],"asset_id":a["asset_id"],
            "modality":a["modality"],"source_time":a["sample_time"] or a["source_range"]["start"],
            "observation":"Synthetic decoded content observed", "relation":relation} for a in payload["assets"]]

    def test_source_assets_redecoded_and_return_actual_bytes(self):
        raw=verify_raw_evidence(self.card,manifest=self.manifest,evidence_root=self.root)
        self.assertEqual({a["kind"] for a in raw["assets"]},{"video_clip","audio_pcm","video_frame"})
        for asset in raw["assets"]:
            self.assertIsInstance(asset["bytes"],bytes)
            self.assertEqual(hashlib.sha256(asset["bytes"]).hexdigest(),asset["sha256"])

    def test_no_reviewer_means_unknown_not_fake_pass(self):
        result=self.verify()
        self.assertEqual(result.status,"UNKNOWN")
        self.assertEqual(result.structural_state,"accept")
        self.assertEqual(result.advisory_verdict,"unknown")
        self.assertFalse(result.qc_upgrade_allowed)

    def test_observer_consumes_bytes_without_claim_answer_then_judge(self):
        calls=[]
        def observe(payload):
            self.assertNotIn("exact_text",str(payload["target"]))
            self.assertNotIn("generation_revision",str(payload["target"]))
            self.assertNotIn(self.claim().exact_text,str(payload))
            for asset in payload["assets"]:
                self.assertEqual(hashlib.sha256(asset["bytes"]).hexdigest(),asset["sha256"])
            calls.append("observe")
            return self.observes(payload)
        def judge(payload):
            self.assertEqual(calls,["observe"])
            self.assertEqual(payload["claim"]["exact_text"],self.claim().exact_text)
            self.assertIn("observations",payload)
            self.assertNotIn("story",payload)
            calls.append("judge")
            return {"state":"accept","reason":"Synthetic fixture supports limited statement"}
        result=self.verify(observer=observe,judge=judge)
        self.assertEqual(calls,["observe","judge"])
        self.assertEqual((result.status,result.advisory_verdict),("ADVISORY","accept"))
        for key in ("observation_input_hash","observation_output_hash","judgment_input_hash","judgment_output_hash"):
            self.assertEqual(len(getattr(result,key)),64)
        self.assertTrue(result.advisory)
        self.assertFalse(result.qc_upgrade_allowed)

    def test_required_nodes_cannot_leak_derived_answer(self):
        value=self.claim().model_dump(mode="json")
        value["required_nodes"]=[value["exact_text"]]
        with self.assertRaises(ValidationError):
            DerivedClaim.model_validate(value)

    def test_observer_gets_opaque_provenance_labels(self):
        card=self.card.model_copy(deep=True)
        card.evidence_id="THE_KILLER_IS_X"
        for asset in card.assets:
            asset.asset_id="DERIVED_ANSWER_"+asset.asset_id
        claim=self.claim();claim.proposed_support_ids=[card.evidence_id]
        def observe(payload):
            metadata=[{k:v for k,v in a.items() if k!="bytes"} for a in payload["assets"]]
            self.assertNotIn("THE_KILLER",str(metadata))
            self.assertNotIn("DERIVED_ANSWER",str(metadata))
            return self.observes(payload)
        result=self.verify(claim,[card],observer=observe,judge=lambda p:{"state":"accept","reason":"fixture"})
        self.assertEqual(result.advisory_verdict,"accept")
        self.assertEqual(result.observations[0].evidence_id,card.evidence_id)

    def test_small_asset_cannot_certify_larger_requested_window(self):
        card=create_raw_evidence_card(manifest=self.manifest,source_id="s1",source_range=Interval(start=.2,end=.6),
            evidence_root=self.root,include_video=True,evidence_id="raw1")
        card.requested_range=Interval(start=.2,end=1.8)
        card.coverage_gaps=[]
        result=self.verify(cards=[card],observer=self.observes,judge=lambda p:{"state":"accept","reason":"tiny crop"})
        self.assertEqual(result.advisory_verdict,"unknown")
        self.assertIn("independent_video_coverage_gap",result.reason)

    def test_model_reject_also_remains_advisory(self):
        result=self.verify(observer=lambda p:self.observes(p,"contradict"),
            judge=lambda p:{"state":"reject","reason":"Located synthetic contradiction"})
        self.assertEqual((result.status,result.advisory_verdict),("ADVISORY","reject"))
        self.assertFalse(result.final_render_review_inherited)

    def test_sarcasm_cannot_be_accepted_without_audio(self):
        card=self.card.model_copy(deep=True)
        card.assets=[a for a in card.assets if a.modality=="video"]
        result=self.verify(self.claim("tone"),[card],observer=self.observes,
            judge=lambda p:{"state":"accept","reason":"looks sarcastic"})
        self.assertEqual(result.advisory_verdict,"unknown")
        self.assertIn("missing_modalities:audio",result.reason)

    def test_speaker_requires_audio_and_video(self):
        card=self.card.model_copy(deep=True)
        card.assets=[a for a in card.assets if a.modality=="audio"]
        result=self.verify(self.claim("speaker"),[card],observer=self.observes,
            judge=lambda p:{"state":"accept","reason":"voice sounded like person"})
        self.assertEqual(result.advisory_verdict,"unknown")
        self.assertIn("missing_modalities:video",result.reason)

    def test_frames_do_not_prove_continuous_action(self):
        card=self.card.model_copy(deep=True)
        card.assets=[a for a in card.assets if a.kind=="video_frame"]
        result=self.verify(cards=[card],observer=self.observes,
            judge=lambda p:{"state":"accept","reason":"one frame"})
        self.assertEqual(result.advisory_verdict,"unknown")
        self.assertIn("continuous_video_not_observed",result.reason)

    def test_motivation_not_promoted_to_visible_fact(self):
        result=self.verify(self.claim("motivation"),observer=self.observes,
            judge=lambda p:{"state":"accept","reason":"inferred motive"})
        self.assertEqual(result.advisory_verdict,"unknown")
        self.assertIn("internal_motivation",result.reason)

    def test_derived_summary_cannot_enter_raw_schema(self):
        data=self.card.model_dump(mode="json")
        data["story_graph"]={"answer":"killer"}
        with self.assertRaises(ValidationError):
            RawEvidenceCard.model_validate(data)

    def test_empty_decoded_window_cannot_be_a_raw_video_asset(self):
        manifest=self.manifest.model_copy(deep=True)
        manifest.sources[0].duration=20
        with self.assertRaises((ValueError,RuntimeError)):
            create_raw_evidence_card(manifest=manifest,source_id="s1",source_range=Interval(start=10,end=11),
                evidence_root=self.root,include_video=True,evidence_id="empty")

    def test_qc_adapter_does_not_turn_semantic_reject_into_hard_block(self):
        from douyin_film_recap.raw_evidence import claim_verification_finding
        result=self.verify(observer=lambda p:self.observes(p,"contradict"),
            judge=lambda p:{"state":"reject","reason":"synthetic model concern"})
        finding=claim_verification_finding(result)
        self.assertFalse(finding.blocking)
        self.assertFalse(finding.deterministic)
        self.assertEqual(finding.rule_id,"source_claim_advisory")

    def test_changed_source_or_asset_hash_is_structural_block(self):
        card=self.card.model_copy(deep=True)
        card.source_sha256="b"*64
        result=self.verify(cards=[card])
        self.assertEqual(result.status,"BLOCKED")
        card=self.card.model_copy(deep=True)
        card.assets[0].sha256="c"*64
        result=self.verify(cards=[card])
        self.assertEqual(result.status,"BLOCKED")

    def test_arbitrary_same_hash_rebound_picture_rejected_by_redecode(self):
        from PIL import Image
        card=self.card.model_copy(deep=True)
        card.assets=[a for a in card.assets if a.kind=="video_frame"]
        fake=self.root/"unrelated.png"
        Image.new("RGB",(32,32),"blue").save(fake)
        card.assets[0].relative_path=fake.name
        card.assets[0].sha256=content_fingerprint(fake)
        result=self.verify(cards=[card])
        self.assertEqual(result.status,"BLOCKED")
        self.assertIn("NOT_SOURCE_CONTENT",result.reason)

    def test_png_metadata_cannot_leak_claim_into_observer_bytes(self):
        from PIL import Image, PngImagePlugin
        card=self.card.model_copy(deep=True)
        original=next(a for a in card.assets if a.kind=="video_frame")
        metadata=PngImagePlugin.PngInfo()
        metadata.add_text("derived_claim",self.claim().exact_text)
        altered=self.root/"answer-in-metadata.png"
        with Image.open(self.root/original.relative_path) as img:
            img.save(altered,pnginfo=metadata)
        original.relative_path=altered.name
        original.sha256=content_fingerprint(altered)
        self.assertIn(self.claim().exact_text.encode(),altered.read_bytes())
        def observer(payload):
            for asset in payload["assets"]:
                self.assertNotIn(self.claim().exact_text.encode(),asset["bytes"])
                self.assertEqual(hashlib.sha256(asset["bytes"]).hexdigest(),asset["sha256"])
            return self.observes(payload)
        result=self.verify(cards=[card],observer=observer,judge=lambda p:{"state":"accept","reason":"source pixels only"})
        key=f"raw1/{original.asset_id}"
        self.assertEqual(result.raw_asset_hashes[key],original.sha256)
        self.assertNotEqual(result.raw_asset_hashes[key],result.consumed_asset_hashes[key])
        self.assertEqual(result.advisory_verdict,"accept")

    def test_unlocated_review_cannot_accept(self):
        def bad(payload):
            rows=self.observes(payload)
            rows[0]["source_time"]=99
            return rows
        result=self.verify(observer=bad,judge=lambda p:{"state":"accept","reason":"bad time"})
        self.assertEqual(result.status,"UNKNOWN")
        self.assertIn("TIME_OUTSIDE",result.reason)

    def test_boundary_raw_cards_are_frozen_by_approval_hash(self):
        from test_boundary_contract import boundary_fixture
        from douyin_film_recap.raw_evidence import verify_boundary_raw_evidence
        from douyin_film_recap.boundary import proposal_hash
        from douyin_film_recap.utils import fingerprint_json
        p,_=boundary_fixture()
        p.source_sha256=self.card.source_sha256
        p.timebase=self.card.timebase
        p.proposed_range=self.card.requested_range
        p.raw_evidence_ids=["raw1"];p.audio_evidence_ids=["raw1"]
        p.must_preserve_source_track=True
        p.raw_evidence_card_hashes={"raw1":fingerprint_json(self.card.model_dump(mode="json"))}
        approved=proposal_hash(p)
        report=verify_boundary_raw_evidence(p,[self.card],manifest=self.manifest,evidence_root=self.root)
        self.assertEqual(report["state"],"verified_source_bindings")
        self.assertFalse(report["historical_model_consumption_verified"])
        self.assertFalse(report["qc_upgrade_allowed"])
        self.assertEqual(report["proposal_hash"],approved)
        changed=self.card.model_copy(deep=True);changed.budget_exhausted=True
        with self.assertRaisesRegex(ValueError,"HASH_CHANGED"):
            verify_boundary_raw_evidence(p,[changed],manifest=self.manifest,evidence_root=self.root)
        p.raw_evidence_card_hashes["raw1"]="f"*64
        self.assertNotEqual(proposal_hash(p),approved)

    def test_declared_boundary_raw_cards_cannot_be_missing(self):
        from test_boundary_apply import apply_fixture
        from douyin_film_recap.boundary_apply import prepare_boundary_revision,BoundaryApplyError
        from douyin_film_recap.boundary import proposal_hash
        p,kw=apply_fixture()
        p.raw_evidence_card_hashes={"raw1":"a"*64}
        p.proposal_content_hash=proposal_hash(p);p.approved_proposal_hash=p.proposal_content_hash
        with self.assertRaisesRegex(BoundaryApplyError,"DECLARED_RAW"):
            prepare_boundary_revision(p,**kw)

    def test_budget_and_coverage_gaps_remain_unknown(self):
        card=self.card.model_copy(deep=True)
        card.budget_exhausted=True
        card.coverage_gaps=[Interval(start=.5,end=.6)]
        result=self.verify(cards=[card],observer=self.observes,
            judge=lambda p:{"state":"accept","reason":"would like to pass"})
        self.assertEqual(result.advisory_verdict,"unknown")
        self.assertIn("budget_exhausted",result.reason)


if __name__=="__main__":
    unittest.main()
