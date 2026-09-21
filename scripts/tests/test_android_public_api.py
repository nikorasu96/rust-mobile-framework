"""Regression tests for the designed public Android Kotlin API."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_android_public_api import MANIFEST, ROOT, check_public_api_manifest


class AndroidPublicApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def check_changed(self, changed: dict[str, object]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "public-api.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            return check_public_api_manifest(path, ROOT)

    def test_repository_public_api_is_valid(self) -> None:
        self.assertEqual(check_public_api_manifest(), [])

    def test_rejects_additional_public_declaration(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["declarations"].append(copy.deepcopy(changed["declarations"][0]))
        self.assertIn(
            "Android public API must contain exactly one declaration",
            self.check_changed(changed),
        )

    def test_rejects_additional_public_member(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["declarations"][0]["members"].append(
            copy.deepcopy(changed["declarations"][0]["members"][1])
        )
        self.assertIn("unexpected Android public member count", self.check_changed(changed))

    def test_rejects_raw_ffi_bytes_in_public_surface(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["declarations"][0]["members"][0]["parameters"][0]["type"] = (
            "kotlin.ByteArray"
        )
        self.assertIn("forbidden Android public type: <init>", self.check_changed(changed))

    def test_rejects_weakening_idempotent_close(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["declarations"][0]["members"][1]["idempotent"] = False
        self.assertIn(
            "Android public member drift: close.idempotent",
            self.check_changed(changed),
        )

    def test_rejects_compatibility_policy_drift(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["compatibility"]["patch_release"] = "breaking_allowed"
        self.assertIn(
            "Android public API compatibility-policy drift",
            self.check_changed(changed),
        )

    def test_rejects_jvm_descriptor_drift(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["declarations"][0]["members"][1]["jvm_descriptor"] = "()Z"
        self.assertIn(
            "Android public member drift: close.jvm_descriptor",
            self.check_changed(changed),
        )

    def test_rejects_external_kotlin_plugin(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["build_requirements"]["external_kotlin_android_plugin"] = True
        self.assertIn(
            "Android public API build-requirement drift",
            self.check_changed(changed),
        )

    def test_rejects_topology_symbol_mismatch(self) -> None:
        topology = json.loads(
            (ROOT / "platforms" / "android" / "architecture.json").read_text(
                encoding="utf-8"
            )
        )
        topology["modules"][1]["public_symbols"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "contracts" / "android-api" / "v1" / "public-api.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps(self.valid), encoding="utf-8")
            for relative in self.valid["compatibility"]["behavioral_contracts"]:
                contract = root / relative
                contract.parent.mkdir(parents=True, exist_ok=True)
                contract.write_text("{}", encoding="utf-8")
            topology_path = root / "platforms" / "android" / "architecture.json"
            topology_path.parent.mkdir(parents=True)
            topology_path.write_text(json.dumps(topology), encoding="utf-8")
            self.assertIn(
                "Android topology and public API symbols differ",
                check_public_api_manifest(manifest, root),
            )


if __name__ == "__main__":
    unittest.main()
