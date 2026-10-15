import unittest
from pydantic import ValidationError
from douyin_film_recap.config import AppConfig

class RetrievalConfigTests(unittest.TestCase):
    def config(self, **options):
        return AppConfig(models={"llm_model":"unused", "vlm_model":"unused"}, format=options)
    def test_explicit_defaults_keep_existing_identity(self):
        self.assertEqual(self.config().fingerprint(), self.config(visual_retrieval="r0",
            visual_pool_text_budget=None, visual_exploration_fraction=.15).fingerprint())
    def test_nondefault_policy_changes_identity(self):
        self.assertNotEqual(self.config().fingerprint(), self.config(visual_retrieval="r1").fingerprint())
        self.assertNotEqual(self.config().fingerprint(), self.config(visual_pool_text_budget=100).fingerprint())
    def test_invalid_policy_and_budgets_rejected(self):
        for settings in ({"visual_retrieval":"r9"}, {"visual_pool_text_budget":0},
                         {"visual_exploration_fraction":-1}, {"visual_exploration_fraction":1.01}):
            with self.assertRaises(ValidationError): self.config(**settings)

if __name__ == "__main__": unittest.main()
