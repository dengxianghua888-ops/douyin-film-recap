import json
import unittest
from test_boundary_apply import apply_fixture
from douyin_film_recap.retrieval import (
    RetrievalRequest, rerank_visual_pool, writer_input_bytes,
    benchmark_supporting_spans, build_retrieval_requests,
)
from douyin_film_recap.planning import _build_visual_pool, _build_visual_pool_r0, build_storyboard


def unit(index, text="person does not leave before reaction", source="s1"):
    return {"unit_id":f"u{index:04d}","source_id":source,"start":index*2,"end":index*2+2,
            "evidence_type":"scene_analysis","visible_facts":[text],"uncertainties":[]}


def request(beat, span=("s1",0,10000), text="does not leave before reaction"):
    return RetrievalRequest(beat_id=beat,query_text=text,query_provenance=("fixture",),
        allowed_source_ids=("s1",),preferred_spans=(span,),allowed_knowledge_event_ids=("allowed",))


class RetrievalTests(unittest.TestCase):
    def test_160_ordinary_and_highlights_separately_unchanged(self):
        ordinary=[unit(i) for i in range(200)]
        highlights=[{**unit(1000+i),"evidence_type":"highlight"} for i in range(3)]
        baseline=ordinary[:160]+highlights
        result=rerank_visual_pool(ordinary,r0_pool=baseline,requests=[request("b")])
        self.assertEqual(result.provenance["ordinary_count"],160)
        self.assertEqual(result.provenance["highlight_append_count"],3)
        self.assertEqual(result.pool[-3:],highlights)
        self.assertLessEqual(writer_input_bytes(result.pool),writer_input_bytes(baseline))
        self.assertFalse(result.provenance["provider_token_budget_verified"])
        self.assertFalse(result.provenance["same_total_compute_cost_verified"])

    def test_short_r1_rows_cannot_buy_extra_ordinary_units(self):
        long_rows=[unit(i,"word "*200) for i in range(3)]
        short_rows=[unit(i+100,"word") for i in range(100)]
        result=rerank_visual_pool(long_rows+short_rows,r0_pool=long_rows,requests=[request("b",text="word")],ordinary_limit=160)
        self.assertLessEqual(result.provenance["ordinary_count"],3)
        self.assertEqual(result.provenance["ordinary_limit"],3)
        self.assertEqual(result.provenance["requested_ordinary_limit"],160)

    def test_budget_matches_actual_pretty_writer_serialization(self):
        baseline=unit(0,"x"*500)
        many=unit(1,"a")
        many["visible_facts"]=["a"]*90
        result=rerank_visual_pool([baseline,many],r0_pool=[baseline],requests=[request("b",text="a")],ordinary_limit=1)
        actual=lambda rows:len(json.dumps({"visual_pool":rows},ensure_ascii=False,indent=2).encode())
        self.assertLessEqual(actual(result.pool),actual([baseline]))
        self.assertNotIn("u0001",result.provenance["pool_unit_ids"])

    def test_same_budget_token_instrumentation_and_long_summary(self):
        units=[unit(i,"x"*10) for i in range(10)]+[unit(10,"reaction "*1000)]
        tokenizer=lambda rows: len(json.dumps(rows,ensure_ascii=False))
        baseline=units[:4]
        result=rerank_visual_pool(units,r0_pool=baseline,requests=[request("b")],ordinary_limit=4,token_counter=tokenizer)
        self.assertLessEqual(result.provenance["writer_tokens"],result.provenance["r0_writer_tokens"])
        self.assertLessEqual(result.provenance["writer_bytes"],result.provenance["r0_writer_bytes"])
        self.assertNotIn("u0010",result.provenance["pool_unit_ids"])
        self.assertTrue(result.provenance["provider_token_budget_verified"])

    def test_more_beats_than_budget_exposes_uncovered_without_overflow(self):
        units=[unit(i) for i in range(20)]
        requests=[request(f"b{i}",("s1",i*2,i*2+2)) for i in range(20)]
        result=rerank_visual_pool(units,r0_pool=units[:6],requests=requests,ordinary_limit=6,exploration_fraction=0)
        self.assertLessEqual(result.provenance["ordinary_count"],6)
        self.assertGreater(result.provenance["ordinary_count"],0)
        self.assertEqual(len(result.provenance["uncovered_beat_ids"]),20-result.provenance["ordinary_count"])
        self.assertNotEqual(set(result.provenance["pool_unit_ids"]),{r["unit_id"] for r in units[:6]})

    def test_late_beats_receive_minimum_when_budget_allows(self):
        units=[unit(i) for i in range(15)]
        requests=[request(f"b{i}",("s1",i*2,i*2+2)) for i in range(15)]
        result=rerank_visual_pool(units,r0_pool=units,requests=requests,ordinary_limit=15,exploration_fraction=0)
        self.assertEqual(result.provenance["uncovered_beat_ids"],[])

    def test_constraints_precede_text_score(self):
        units=[unit(0),unit(1,source="different"),unit(2,"reaction "*20)]
        result=rerank_visual_pool(units,r0_pool=units,requests=[request("b")],ordinary_limit=3,
                                 unit_event_ids={"u0002":["future_reveal"]})
        self.assertEqual([r["unit_id"] for r in result.pool],["u0000"])
        self.assertEqual({r["reason"] for r in result.provenance["exclusions"]["b"]},
                         {"source_constraint","knowledge_constraint"})

    def test_wrong_event_span_allows_bounded_context_exploration(self):
        units=[unit(i,"unrelated distant setting") for i in range(20)]
        units[15]=unit(15,"person does not leave before reaction")
        result=rerank_visual_pool(units,r0_pool=units[:10],requests=[request("b",("s1",0,2))],
            ordinary_limit=10,exploration_fraction=.2)
        self.assertIn("u0015",result.provenance["pool_unit_ids"])
        explored=next(r for r in result.pool if r["unit_id"]=="u0015")
        self.assertEqual(explored["retrieval_role_limit"],"context")
        self.assertTrue(explored["requires_raw_verification"])

    def test_conjunctive_gold_not_inflated_by_one_of_two_supports(self):
        units=[unit(i) for i in range(3)]
        result=rerank_visual_pool(units,r0_pool=units[:1],requests=[request("b")],ordinary_limit=1)
        report=benchmark_supporting_spans(units[:1],result,{"b":[["u0000","u0001"]]})
        self.assertFalse(report["per_beat"]["b"]["r1_writer_pool_recalled"])
        self.assertTrue(report["per_beat"]["b"]["r1_candidates_recalled"])
        self.assertIsNone(report["per_beat"]["b"]["render_consumed_support"])

    def test_empty_gold_not_claimed_quality_result(self):
        result=rerank_visual_pool([],r0_pool=[],requests=[])
        self.assertEqual(benchmark_supporting_spans([],result,{})["quality_status"],"NOT_RUN")

    def test_highlights_cannot_silently_overrun_explicit_budget(self):
        highlights=[{**unit(0),"evidence_type":"highlight"}]
        with self.assertRaisesRegex(ValueError,"highlights alone"):
            rerank_visual_pool([],r0_pool=highlights,requests=[],text_byte_budget=2)

    def test_negation_and_temporal_language_remain_in_queries(self):
        _,kw=apply_fixture()
        kw["plan"].beats[0].change="他没有离开，然后才回头"
        kw["story"].story_graph.events[0].event="does not leave before reaction"
        req=build_retrieval_requests(kw["plan"],kw["story"])[0]
        self.assertIn("没有",req.query_text)
        self.assertIn("before",req.query_text)
        self.assertIn("not",req.query_text)
        self.assertTrue(req.claims_are_derived)

    def test_global_writer_pool_cannot_leak_late_beat_evidence_into_early(self):
        from unittest.mock import patch
        _,kw=apply_fixture()
        kw["config"].format.visual_retrieval="r1"
        board=kw["storyboard"].model_copy(deep=True)
        board.segments=[board.segments[1]]
        board.segments[0].beat_id="early"
        board.segments[0].visuals=[board.segments[0].visuals[0]]
        board.segments[0].visuals[0].visual_role="direct_evidence"
        def fake_payload(*args,**kwargs):
            kwargs["retrieval_report"].update(per_beat_rankings={"early":[],"late":[{
                "unit_id":"u0","in_event_span":True,"requires_raw_verification":False}]},
                context_only_unit_ids=[],exclusions={"early":[{"unit_id":"u0","reason":"knowledge_constraint"}]})
            return {"visual_pool":[{"unit_id":"u0","evidence_type":"scene_analysis","source_id":"s1","start":0,"end":16}],"constraints":{}}
        class Client:
            def chat_json(self,**request):
                return board
        with patch("douyin_film_recap.planning._storyboard_payload",side_effect=fake_payload):
            with self.assertRaisesRegex(ValueError,"Beat source/knowledge"):
                build_storyboard(project_name="fixture",manifest=kw["manifest"],story=kw["story"],
                    highlights=kw["highlights"],plan=kw["plan"],config=kw["config"],client=Client(),
                    scene_index=kw["scene_index"],scene_analysis=kw["scene_analysis"])

    def test_planning_r0_unchanged_and_r1_provenance_is_persisted(self):
        _,kw=apply_fixture()
        args=[kw[k] for k in ("manifest","story","highlights","plan","config","scene_index","scene_analysis")]
        self.assertEqual(_build_visual_pool(*args),_build_visual_pool_r0(*args))
        kw["config"].format.visual_retrieval="r1"
        class Client:
            def chat_json(self,**request):
                self.prompt=request["prompt"]
                return kw["storyboard"].model_copy(deep=True)
        client=Client()
        board=build_storyboard(project_name="fixture",manifest=kw["manifest"],story=kw["story"],
            highlights=kw["highlights"],plan=kw["plan"],config=kw["config"],client=client,
            scene_index=kw["scene_index"],scene_analysis=kw["scene_analysis"])
        self.assertEqual(board.retrieval_provenance["method"],"r1-lexical/1")
        self.assertNotIn("per_beat_rankings",client.prompt)  # audit does not inflate writer prompt
        self.assertEqual(board.retrieval_provenance["highlight_append_count"],1)


if __name__ == "__main__":
    unittest.main()
