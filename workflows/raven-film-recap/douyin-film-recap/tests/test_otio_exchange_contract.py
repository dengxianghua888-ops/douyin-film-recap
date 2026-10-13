"""Local standard-library runner; pytest also collects these contracts in CI."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from douyin_film_recap import otio_exchange as x


def fixture(root, *, actual_media=False):
    work = root / "work"
    work.mkdir()
    sources, facts = [], {}
    for i in (1, 2):
        path = work / f"source{i}.mp4"
        if actual_media:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                f"color=c={'red' if i == 1 else 'blue'}:s=160x90:r=30:d=4", "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=48000:duration=4", "-c:v", "mpeg4", "-c:a", "aac",
                "-shortest", str(path)], check=True, capture_output=True)
        else:
            path.write_bytes(f"synthetic bytes {i}".encode())
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        sources.append({"source_id": f"source{i}", "path": str(path), "filename": path.name,
            "fingerprint": sha, "duration": 4, "fps": 30, "width": 160, "height": 90,
            "has_audio": True})
        facts[f"source{i}"] = {"cfr": True, "fps": "30/1", "sample_rate": 48000, "channels": 1}
    voice = work / "voice.wav"
    if actual_media:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
            "sine=frequency=600:sample_rate=48000:duration=2", "-c:a", "pcm_s16le", str(voice)],
            check=True, capture_output=True)
    else:
        voice.write_bytes(b"synthetic voice")
    facts["narration:s2"] = {"sha256": hashlib.sha256(voice.read_bytes()).hexdigest(),
        "sample_rate": 48000, "channels": 1, "duration_samples": 96000}
    segments = [{"segment_id": f"s{i}", "beat_id": "beat", "mode": "voiceover" if i == 2 else "original",
        "title": "fixture", "text": "同一句", "notes": "synthetic fixture",
        "audio_owner": "narration" if i == 2 else "action_sound", "planned_duration_sec": 2,
        "visuals": [{"source_id": "source2" if i == 2 else "source1", "start": 1, "end": 3}]}
        for i in range(1, 4)]
    segments[1].update(audio_file=str(voice), audio_duration_sec=2)
    story = {"schema_version": 1, "project_name": "Synthetic cut package", "sources": sources,
        "plan_fingerprint": "fixture", "target_duration_sec": 6, "segments": segments}
    for filename, document in [("09_storyboard.json", story),
        ("00_source_manifest.json", {"schema_version": 2, "sources": sources}),
        ("state.json", {"schema_version": 2, "stages": {}})]:
        (work / filename).write_bytes(x.canonical(document))
    return work, story, facts, {"fps": "30/1", "width": 160, "height": 90}


class ExchangeContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.work, self.story, self.facts, self.profile = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def export(self, name="package", **kwargs):
        return x.export_otio_package(self.work, self.root / name, profile=self.profile,
            media_facts=self.facts, captions=[{"caption_id": "cue-a", "start": 1, "end": 3,
                                             "text": "跨切点字幕"}], **kwargs)

    def save(self):
        (self.work / "09_storyboard.json").write_bytes(x.canonical(self.story))

    def test_complete_package_and_distinct_occurrences(self):
        before = (self.work / "09_storyboard.json").read_bytes()
        result = self.export()
        package = Path(result["package"])
        self.assertEqual(x.verify_package(package)["completion_state"], "COMPLETE")
        projection = json.loads((package / "projection.json").read_bytes())
        clips = projection["tracks"][0]["clips"]
        self.assertNotEqual(clips[0]["instance_id"], clips[2]["instance_id"])
        self.assertEqual(clips[0]["resource_id"], clips[2]["resource_id"])
        otio = json.loads((package / "timeline.otio").read_bytes())
        voice = next(t for t in otio["tracks"]["children"] if t["name"] == "narration")
        self.assertEqual(voice["children"][0]["source_range"]["duration"]["value"], 96000)
        self.assertEqual((self.work / "09_storyboard.json").read_bytes(), before)
        self.assertEqual(result["capability"]["evidence"]["host_import"], "NOT_RUN")
        self.assertIn("跨切点字幕", (package / "captions.srt").read_text())
        with self.assertRaisesRegex(x.ExchangeError, "TARGET_EXISTS"):
            self.export()

    def test_identity_map_survives_segment_reorder_but_never_guesses_changed_legacy_visual(self):
        self.export()
        identity = json.loads((self.root / "package/identity-map.json").read_bytes())
        self.story["segments"].reverse()
        self.save()
        self.export("second", identity_map=identity)
        second = json.loads((self.root / "second/identity-map.json").read_bytes())
        self.assertEqual(identity["segments"], second["segments"])
        self.story["segments"][0]["visuals"][0]["end"] = 4
        self.save()
        with self.assertRaisesRegex(x.ExchangeError, "IDENTITY_AMBIGUOUS"):
            self.export("third", identity_map=identity)

    def test_retime_and_opaque_effect_never_silently_drop(self):
        self.story["segments"][1]["audio_speed"] = 1.5
        self.save()
        with self.assertRaisesRegex(x.ExchangeError, "UNSUPPORTED_EDITABLE_CUTS") as exc:
            self.export()
        self.assertTrue(exc.exception.findings[0]["blocking"])
        self.story["segments"][1]["audio_speed"] = 1
        self.story["future_private"] = {"unknown": [1, 2]}
        self.story["sources"][0]["vendor_unknown"] = {"color_parameter": 9}
        self.save()
        self.export()
        opaque = json.loads((self.root / "package/opaque.json").read_bytes())
        self.assertEqual(opaque["root"]["future_private"], {"unknown": [1, 2]})
        self.assertEqual(opaque["sources"]["source1"]["vendor_unknown"], {"color_parameter": 9})

    def test_media_and_package_drift_rejected(self):
        self.export()
        (self.root / "package/captions.srt").write_bytes(b"change")
        with self.assertRaisesRegex(x.ExchangeError, "HASH_MISMATCH"):
            x.verify_package(self.root / "package")
        Path(self.story["sources"][0]["path"]).write_bytes(b"source changed")
        with self.assertRaisesRegex(x.ExchangeError, "SOURCE_BYTES_CHANGED"):
            self.export("second")
        self.assertFalse((self.root / "second/checksums.json").exists())

    def test_resource_namespace_and_generated_instance_collisions_rejected(self):
        self.story["sources"][0]["source_id"] = "narration:s2"
        for segment in self.story["segments"]:
            if segment["visuals"][0]["source_id"] == "source1":
                segment["visuals"][0]["source_id"] = "narration:s2"
        raw = x.canonical(self.story)
        sha = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(x.ExchangeError, "NAMESPACE_COLLISION"):
            x.compile_cut_projection(self.story, storyboard_sha256=sha,
                authority={"workspace_generation": ".", "storyboard_sha256": sha},
                profile=self.profile, media_facts=self.facts)
        self.story["sources"][0]["source_id"] = "source1"
        for segment in self.story["segments"]:
            if segment["visuals"][0]["source_id"] == "narration:s2":
                segment["visuals"][0]["source_id"] = "source1"
        self.story["segments"][0]["visuals"][0]["clip_instance_id"] = "explicit-a"
        self.story["segments"][2]["visuals"][0]["clip_instance_id"] = "original:explicit-a"
        self.save()
        with self.assertRaisesRegex(x.ExchangeError, "INSTANCE_ID_MISSING_OR_DUPLICATE"):
            self.export()

    def test_unaligned_vfr_different_geometry_and_start_times_rejected(self):
        for field, value, code in [("cfr", False, "VIDEO_CLOCK"), ("fps", 24, "VIDEO_CLOCK"),
            ("start_time", 5, "VIDEO_CLOCK"), ("width", 320, "GEOMETRY")]:
            with self.subTest(field=field):
                old = deepcopy(self.facts)
                self.facts["source1"][field] = value
                with self.assertRaisesRegex(x.ExchangeError, code):
                    self.export(field)
                self.facts = old
        self.story["segments"][0]["visuals"][0]["start"] = 1.001
        self.save()
        with self.assertRaisesRegex(x.ExchangeError, "UNALIGNED"):
            self.export("unaligned")

    def test_safe_paths_and_rational_time(self):
        for path in ("../media.mp4", "https://example/media.mp4", "/media.mp4", "a\\b.mp4"):
            with self.assertRaisesRegex(x.ExchangeError, "UNSAFE"):
                x.safe_relative(path)
        self.assertEqual(x._rt("1001/30000", "30000/1001")["value"], 1)
        with self.assertRaisesRegex(x.ExchangeError, "UNREPRESENTABLE"):
            x._rt(2, "30000/1001")
        with self.assertRaisesRegex(x.ExchangeError, "NONFINITE"):
            x._json(b'{"a":NaN}')
        with self.assertRaisesRegex(x.ExchangeError, "DUPLICATE"):
            x._json(b'{"a":0,"a":1}')

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools absent")
    def test_real_synthetic_media_facts_and_export(self):
        actual = self.root / "actual"
        actual.mkdir()
        work, story, _, profile = fixture(actual, actual_media=True)
        before = {s["path"]: Path(s["path"]).read_bytes() for s in story["sources"]}
        result = x.export_otio_package(work, self.root / "real-package", profile=profile)
        self.assertEqual(result["capability"]["media_facts"], "FFPROBE_FULL_FRAME_SCAN")
        self.assertEqual(result["capability"]["evidence"]["render_equivalence"], "NOT_RUN")
        for path, content in before.items():
            self.assertEqual(Path(path).read_bytes(), content)
        x.verify_package(self.root / "real-package")


if __name__ == "__main__":
    unittest.main()
