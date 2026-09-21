from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_android_topology import check_android_topology, check_topology_manifest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "platforms" / "android" / "architecture.json"


class AndroidTopologyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def check_changed(self, changed: dict[str, object]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "architecture.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            return check_topology_manifest(path)

    def test_repository_topology_is_valid(self) -> None:
        self.assertEqual(check_android_topology(ROOT), [])

    def test_rejects_toolchain_drift(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["toolchain"]["jdk"] = 21
        self.assertIn("Android toolchain drift", self.check_changed(changed))

    def test_rejects_extra_native_export(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["modules"][0]["public_symbols"].append("Java_dev_rmf_unsafe")
        violations = self.check_changed(changed)
        self.assertIn("Android module drift: rmf-android-jni.public_symbols", violations)

    def test_rejects_outward_native_dependency(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["modules"][0]["inward_dependencies"] = ["rmf-runtime", "framework"]
        violations = self.check_changed(changed)
        self.assertIn("Android module drift: rmf-android-jni.inward_dependencies", violations)

    def test_rejects_module_cycle(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["modules"][0]["depends_on"] = ["sample"]
        violations = self.check_changed(changed)
        self.assertIn("cyclic Android module dependency", violations)


if __name__ == "__main__":
    unittest.main()
