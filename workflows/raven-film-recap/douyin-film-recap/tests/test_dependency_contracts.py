"""Check both requested and actually installed headless dependency providers.

PySceneDetect's supported headless distribution is documented at
https://www.scenedetect.com/download/. Declaration-only tests cannot detect
transitive dependencies; the installed checks must run after installing .[dev].
"""
from importlib import metadata
from pathlib import Path
import re
import tomllib
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
OPENCV_DISTRIBUTIONS = {
    "opencv-python", "opencv-python-headless",
    "opencv-contrib-python", "opencv-contrib-python-headless",
}
SCENEDETECT_DISTRIBUTIONS = {"scenedetect", "scenedetect-headless", "scenedetect-core"}


def installed_providers(names: set[str]) -> list[str]:
    installed = []
    for distribution in metadata.distributions():
        name = re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower()
        if name in names:
            installed.append(name)
    return sorted(installed)


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
        self.assertEqual(scenedetect, ["scenedetect-headless>=0.7.2,<0.8"])


class InstalledDependencyContractTests(unittest.TestCase):
    """These intentionally fail, rather than skip, for a missing or mixed install."""

    def test_only_headless_opencv_distribution_is_installed(self):
        self.assertEqual(installed_providers(OPENCV_DISTRIBUTIONS), ["opencv-python-headless"])

    def test_only_headless_scenedetect_distribution_is_installed(self):
        self.assertEqual(installed_providers(SCENEDETECT_DISTRIBUTIONS), ["scenedetect-headless"])

    def test_cv2_import_matches_headless_distribution_and_supported_version(self):
        import cv2
        import numpy as np

        distribution = metadata.distribution("opencv-python-headless")
        owned_files = {Path(distribution.locate_file(path)).resolve()
                       for path in distribution.files or []}
        self.assertIn(Path(cv2.__file__).resolve(), owned_files)
        expected_version = ".".join(distribution.version.split(".")[:3])
        self.assertEqual(cv2.__version__, expected_version)
        version = tuple(int(part) for part in cv2.__version__.split(".")[:3])
        self.assertGreaterEqual(version, (4, 10, 0))
        self.assertLess(version, (5, 0, 0))
        self.assertRegex(cv2.getBuildInformation(), r"(?m)^\s*GUI:\s+NONE\s*$")
        red_pixel = np.array([[[0, 0, 255]]], dtype=np.uint8)
        self.assertEqual(int(cv2.cvtColor(red_pixel, cv2.COLOR_BGR2GRAY)[0, 0]), 76)

    def test_scenedetect_import_and_used_api_match_headless_distribution(self):
        import scenedetect
        from scenedetect import ContentDetector, SceneManager, open_video

        distribution = metadata.distribution("scenedetect-headless")
        owned_files = {Path(distribution.locate_file(path)).resolve()
                       for path in distribution.files or []}
        self.assertIn(Path(scenedetect.__file__).resolve(), owned_files)
        self.assertEqual(scenedetect.__version__, distribution.version)
        self.assertTrue(callable(open_video))
        manager = SceneManager()
        manager.add_detector(ContentDetector(threshold=27.0, min_scene_len=15))


if __name__ == "__main__":
    unittest.main()
