"""Keep the film runtime on one explicitly selected OpenCV distribution."""
from pathlib import Path
import re
import tomllib
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


class DependencyContractTests(unittest.TestCase):
    def test_only_headless_opencv_is_requested(self):
        project = tomllib.loads(PROJECT.read_text(encoding="utf-8"))["project"]
        dependencies = list(project["dependencies"])
        for extra in project["optional-dependencies"].values():
            dependencies.extend(extra)
        opencv = [requirement for requirement in dependencies
                  if re.match(r"opencv[-_]", requirement, re.IGNORECASE)]
        self.assertEqual(opencv, ["opencv-python-headless>=4.10,<5"])

    def test_scenedetect_does_not_pull_a_second_opencv_variant(self):
        project = tomllib.loads(PROJECT.read_text(encoding="utf-8"))["project"]
        dependencies = list(project["dependencies"])
        for extra in project["optional-dependencies"].values():
            dependencies.extend(extra)
        scenedetect = [requirement for requirement in dependencies
                       if re.match(r"scenedetect\b", requirement, re.IGNORECASE)]
        self.assertEqual(len(scenedetect), 1)
        self.assertNotIn("[", scenedetect[0])


if __name__ == "__main__":
    unittest.main()
