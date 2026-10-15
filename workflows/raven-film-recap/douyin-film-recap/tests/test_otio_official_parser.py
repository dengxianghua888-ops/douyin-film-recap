"""Mandatory dev/CI acceptance against the pinned upstream native JSON adapter.

No importorskip: a missing official parser is an incomplete dev installation,
not successful acceptance. No user media or NLE is used by these fixtures.
"""
from fractions import Fraction
from importlib.metadata import version
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

import opentimelineio as otio

from douyin_film_recap import otio_exchange as x
from douyin_film_recap import otio_readback as r
from test_otio_exchange_contract import fixture

PARSER_VERSION = "0.18.1"


class OfficialOTIOParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make_package(self, *, actual_media=False, fractional_rate=False):
        work, story, facts, profile = fixture(self.root, actual_media=actual_media)
        for source in story["sources"]:
            source["identity_schema"] = "sha256-full/2"
        for i, segment in enumerate(story["segments"]):
            segment["visuals"][0]["clip_instance_id"] = f"official-fixture-occurrence-{i}"
        if fractional_rate:
            profile["fps"] = "30000/1001"
            for source in story["sources"]:
                source["fps"] = float(Fraction(30000, 1001))
                facts[source["source_id"]]["fps"] = "30000/1001"
            for segment in story["segments"]:
                segment["visuals"][0].update(start=1.001, end=2.002)
                segment["planned_duration_sec"] = 1.001
            story["segments"][1]["audio_duration_sec"] = 1.001
            facts["narration:s2"]["duration_samples"] = 48048
            story["target_duration_sec"] = 3.003
        (work / "09_storyboard.json").write_bytes(x.canonical(story))
        (work / "00_source_manifest.json").write_bytes(x.canonical({
            "schema_version": 2, "sources": story["sources"]}))
        package = self.root / "package"
        x.export_otio_package(work, package, profile=profile,
            media_facts=None if actual_media else facts,
            captions=[{"caption_id": "official-cue", "start": 1, "end": 3, "text": "跨切点字幕"}])
        projection = json.loads((package / "projection.json").read_bytes())
        return work, package, projection

    def assert_projection(self, parsed, projection):
        self.assertIsInstance(parsed, otio.schema.Timeline)
        self.assertAlmostEqual(parsed.duration().to_seconds(), float(x.fraction(projection["duration"])), places=10)
        expected_tracks = {track["track_id"]: track for track in projection["tracks"] if track["clips"]}
        self.assertEqual(len(parsed.tracks), len(expected_tracks))
        seen_occurrences = set()
        for track in parsed.tracks:
            self.assertIsInstance(track, otio.schema.Track)
            expected = expected_tracks[track.metadata["recap"]["track_id"]]
            self.assertEqual(track.kind, expected["kind"])
            expected_clips = iter(expected["clips"])
            for child in track:
                if isinstance(child, otio.schema.Gap):
                    self.assertGreater(child.duration().to_seconds(), 0)
                    continue
                self.assertIsInstance(child, otio.schema.Clip)
                clip = next(expected_clips)
                iid = child.metadata["recap"]["instance_id"]
                self.assertEqual(iid, clip["instance_id"])
                self.assertNotIn(iid, seen_occurrences)
                seen_occurrences.add(iid)
                resource = projection["resources"][clip["resource_id"]]
                self.assertIsInstance(child.media_reference, otio.schema.ExternalReference)
                self.assertEqual(child.media_reference.target_url, resource["package_path"])
                self.assertEqual(child.media_reference.metadata["recap"]["sha256"], resource["sha256"])
                self.assertAlmostEqual(child.source_range.start_time.to_seconds(),
                    float(x.fraction(clip["source_start"])), places=10)
                self.assertAlmostEqual(child.source_range.duration.to_seconds(),
                    float(x.fraction(clip["duration"])), places=10)
                self.assertAlmostEqual(child.range_in_parent().start_time.to_seconds(),
                    float(x.fraction(clip["target_start"])), places=10)
                self.assertEqual(len(child.effects), 0)
                self.assertEqual(len(child.markers), 0)
                rate = (float(x.fraction(projection["profile"]["fps"])) if track.kind == "Video"
                        else resource["facts"]["sample_rate"])
                self.assertAlmostEqual(child.source_range.duration.rate, rate, places=10)
            self.assertIsNone(next(expected_clips, None), "parser silently omitted a clip")

    def test_pinned_official_distribution_is_dev_only(self):
        self.assertEqual(version("opentimelineio"), PARSER_VERSION)
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        config = tomllib.loads(pyproject.read_text())
        self.assertIn(f"opentimelineio=={PARSER_VERSION}", config["project"]["optional-dependencies"]["dev"])
        self.assertFalse(any("opentimelineio" in dep.lower() for dep in config["project"]["dependencies"]))

    def test_official_parser_accepts_real_synthetic_multitrack_package(self):
        _, package, projection = self.make_package(actual_media=True)
        parsed = otio.adapters.read_from_file(str(package / "timeline.otio"), adapter_name="otio_json")
        self.assert_projection(parsed, projection)
        video = next(track for track in parsed.tracks if track.kind == "Video")
        self.assertEqual(video[0].media_reference.target_url, video[2].media_reference.target_url)
        self.assertNotEqual(video[0].metadata["recap"]["instance_id"], video[2].metadata["recap"]["instance_id"])
        voice = next(track for track in parsed.tracks if track.name == "narration")
        self.assertIsInstance(voice[0], otio.schema.Gap)
        self.assertEqual(voice[0].source_range.duration.rate, 48000)
        self.assertEqual(voice[0].source_range.duration.value, 96000)
        self.assertIn("00:00:01,000 --> 00:00:03,000", (package / "captions.srt").read_text())
        capability = json.loads((package / "capability-report.json").read_bytes())
        # These per-export flags are not rewritten by a separate parser test.
        self.assertEqual(capability["evidence"]["official_otio_parser"], "NOT_RUN")
        self.assertEqual(capability["evidence"]["host_import"], "NOT_RUN")

    def test_official_read_write_read_preserves_projection_and_readback_ids(self):
        work, package, projection = self.make_package()
        before = (work / "09_storyboard.json").read_bytes()
        package_seal = (package / "checksums.json").read_bytes()
        parsed = otio.adapters.read_from_file(str(package / "timeline.otio"), adapter_name="otio_json")
        rewritten = self.root / "official-roundtrip.otio"
        otio.adapters.write_to_file(parsed, str(rewritten), adapter_name="otio_json")
        reparsed = otio.adapters.read_from_file(str(rewritten), adapter_name="otio_json")
        self.assert_projection(reparsed, projection)
        raw = json.loads(rewritten.read_bytes())
        clips = [item for track in raw["tracks"]["children"] for item in track["children"]
                 if item["OTIO_SCHEMA"].startswith("Clip.")]
        self.assertTrue(clips)
        self.assertTrue(all(item["OTIO_SCHEMA"] == "Clip.2" for item in clips))
        snapshot = self.root / "saved-official-roundtrip"
        r.capture_saved_snapshot(rewritten, snapshot, export_package=package, media_root=package)
        proposal = r.propose_saved_readback(package, work, snapshot)
        self.assertEqual(proposal["changes"], [])
        self.assertEqual(proposal["conflicts"], [])
        # Optional new parser fields remain opaque instead of being dropped.
        self.assertIn(proposal["status"], {"NO_CHANGES", "NEEDS_REVIEW"})
        self.assertFalse(proposal["adoption_performed"])
        self.assertEqual((work / "09_storyboard.json").read_bytes(), before)
        self.assertEqual((package / "checksums.json").read_bytes(), package_seal)
        x.verify_package(package)

    def test_official_roundtrip_preserves_fractional_fps_and_audio_sample_clocks(self):
        _, package, projection = self.make_package(fractional_rate=True)
        parsed = otio.adapters.read_from_file(str(package / "timeline.otio"), adapter_name="otio_json")
        self.assert_projection(parsed, projection)
        rewritten = self.root / "fractional-roundtrip.otio"
        otio.adapters.write_to_file(parsed, str(rewritten), adapter_name="otio_json")
        again = otio.adapters.read_from_file(str(rewritten), adapter_name="otio_json")
        self.assert_projection(again, projection)
        video = next(track for track in again.tracks if track.kind == "Video")
        self.assertEqual(video[0].source_range.duration.value, 30)
        self.assertAlmostEqual(video[0].source_range.duration.rate, 30000 / 1001, places=12)
        voice = next(track for track in again.tracks if track.name == "narration")
        self.assertEqual(voice[0].source_range.duration.value, 48048)
        self.assertEqual(voice[0].source_range.duration.rate, 48000)
        self.assertEqual(projection["profile"]["fps"], {"numerator": 30000, "denominator": 1001})

    def test_saved_official_object_edit_retains_confirmed_occurrence_diff(self):
        work, package, _ = self.make_package()
        parsed = otio.adapters.read_from_file(str(package / "timeline.otio"), adapter_name="otio_json")
        clip = next(track for track in parsed.tracks if track.kind == "Video")[0]
        iid = clip.metadata["recap"]["instance_id"]
        clip.source_range = otio.opentime.TimeRange(
            clip.source_range.start_time + otio.opentime.RationalTime(1, 30),
            clip.source_range.duration)
        rewritten = self.root / "official-saved-edit.otio"
        otio.adapters.write_to_file(parsed, str(rewritten), adapter_name="otio_json")
        snapshot = self.root / "saved-official-edit"
        r.capture_saved_snapshot(rewritten, snapshot, export_package=package, media_root=package)
        proposal = r.propose_saved_readback(package, work, snapshot)
        row = next(row for row in proposal["changes"] if row["entity_id"] == iid and row["field"] == "source_start")
        self.assertEqual(row["classification"], "host_only")
        self.assertEqual(row["host"], {"numerator": 31, "denominator": 30})
        # Parser-added unknown optional fields can conservatively block adoption;
        # the test proves field readback, not host behavior or automatic adoption.
        self.assertFalse(any("ID_MISSING" in p["code"] for p in proposal["conflicts"]))
        self.assertFalse(proposal["adoption_performed"])
        self.assertEqual(proposal["claims"]["adopted_roundtrip"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
