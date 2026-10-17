"""Disabled caching must not force every existing workspace into a new generation."""
import unittest
from douyin_film_recap.config import AppConfig
from douyin_film_recap.utils import fingerprint_json

class CacheConfigIdentityTests(unittest.TestCase):
    def test_default_preserves_legacy_fingerprint(self):
        config = AppConfig(models={"llm_model": "unused", "vlm_model": "unused"})
        legacy = config.model_dump(mode="json")
        legacy["render"].pop("incremental_cache")
        legacy["asr"].pop("alignment")
        for key in ("visual_retrieval", "visual_pool_text_budget", "visual_exploration_fraction"):
            legacy["format"].pop(key)
        self.assertEqual(config.fingerprint(), fingerprint_json({"config": legacy,
            "explicit_format_fields": sorted(config.format.model_fields_set)}))

    def test_enabled_cache_changes_configuration_identity(self):
        config = AppConfig(models={"llm_model": "unused", "vlm_model": "unused"})
        old = config.fingerprint()
        config.render.incremental_cache = True
        self.assertNotEqual(old, config.fingerprint())

if __name__ == "__main__":
    unittest.main()
