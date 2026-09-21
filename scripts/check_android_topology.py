#!/usr/bin/env python3
"""Validate the closed Android module, toolchain and artifact topology."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


MANIFEST_FIELDS = {
    "schema_version",
    "status",
    "toolchain",
    "android",
    "modules",
    "artifact_flow",
    "rules",
}
MODULE_FIELDS = {
    "id",
    "kind",
    "location",
    "ownership",
    "visibility",
    "depends_on",
    "inward_dependencies",
    "public_symbols",
}
EXPECTED_TOOLCHAIN = {
    "android_gradle_plugin": "9.4.0",
    "gradle": "9.6.0",
    "jdk": 17,
    "ndk": "28.2.13676358",
    "rust": "1.85.0",
}
EXPECTED_ANDROID = {
    "compile_sdk": 37,
    "target_sdk": 37,
    "min_sdk": 26,
    "abis": {
        "arm64-v8a": "aarch64-linux-android",
        "x86_64": "x86_64-linux-android",
    },
}
EXPECTED_MODULES = {
    "rmf-android-jni": {
        "kind": "rust_cdylib",
        "location": "platforms/android/native/rmf-android-jni",
        "visibility": "internal",
        "depends_on": [],
        "inward_dependencies": ["rmf-runtime"],
        "public_symbols": ["JNI_OnLoad"],
    },
    "framework": {
        "kind": "android_library",
        "location": "platforms/android/framework",
        "visibility": "published",
        "depends_on": ["rmf-android-jni"],
        "inward_dependencies": [],
        "public_symbols": ["dev.rmf.android.RmfSurfaceHost"],
    },
    "sample": {
        "kind": "android_application",
        "location": "platforms/android/sample",
        "visibility": "example",
        "depends_on": ["framework"],
        "inward_dependencies": [],
        "public_symbols": [],
    },
}
EXPECTED_ARTIFACT_FLOW = {
    "native_library": "librmf_android.so",
    "build_mode": "rust_cross_compile_then_stage",
    "staging_directory": "platforms/android/framework/build/generated/rmfJniLibs",
    "packaging_input": "jniLibs",
    "published_artifact": "rmf-android.aar",
    "generated_artifacts_tracked": False,
}
EXPECTED_RULES = [
    "domain_has_no_android_dependency",
    "kotlin_never_calls_domain_directly",
    "jni_contains_no_domain_logic",
    "framework_is_the_only_published_module",
    "sample_is_never_a_production_dependency",
    "generated_native_libraries_are_not_source_files",
    "native_exports_only_jni_on_load",
]


def _cycle(module_by_id: dict[str, dict[str, Any]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_id: str) -> bool:
        if module_id in visiting:
            return True
        if module_id in visited:
            return False
        visiting.add(module_id)
        for dependency in module_by_id[module_id]["depends_on"]:
            if dependency in module_by_id and visit(dependency):
                return True
        visiting.remove(module_id)
        visited.add(module_id)
        return False

    return any(visit(module_id) for module_id in module_by_id)


def check_topology_manifest(path: Path) -> list[str]:
    """Return every violation in one Android topology manifest."""
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot load Android topology: {error}"]
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        return ["Android topology fields are not closed"]

    violations: list[str] = []
    if manifest["schema_version"] != 1 or manifest["status"] != "planned_compile_gated":
        violations.append("unexpected Android topology version or status")
    if manifest["toolchain"] != EXPECTED_TOOLCHAIN:
        violations.append("Android toolchain drift")
    if manifest["android"] != EXPECTED_ANDROID:
        violations.append("Android SDK or ABI drift")
    if manifest["artifact_flow"] != EXPECTED_ARTIFACT_FLOW:
        violations.append("Android native artifact flow drift")
    if manifest["rules"] != EXPECTED_RULES:
        violations.append("Android boundary rules drift")

    modules = manifest["modules"]
    if not isinstance(modules, list) or len(modules) != len(EXPECTED_MODULES):
        violations.append("unexpected Android module count")
        return violations
    if any(not isinstance(module, dict) or set(module) != MODULE_FIELDS for module in modules):
        violations.append("Android module fields are not closed")
        return violations
    sequence_fields = ("depends_on", "inward_dependencies", "public_symbols")
    if any(
        not isinstance(module["id"], str)
        or not module["id"]
        or any(
            not isinstance(module[field], list)
            or any(not isinstance(value, str) for value in module[field])
            for field in sequence_fields
        )
        for module in modules
    ):
        violations.append("invalid Android module field types")
        return violations
    module_ids = [module["id"] for module in modules]
    if len(set(module_ids)) != len(module_ids):
        violations.append("duplicate Android module id")
        return violations
    module_by_id = {module["id"]: module for module in modules}
    if set(module_by_id) != set(EXPECTED_MODULES):
        violations.append("unexpected Android module registry")
        return violations

    for module_id, module in module_by_id.items():
        if not isinstance(module["ownership"], str) or not module["ownership"]:
            violations.append(f"missing ownership for {module_id}")
        for field, expected in EXPECTED_MODULES[module_id].items():
            if module[field] != expected:
                violations.append(f"Android module drift: {module_id}.{field}")
        dependencies = module["depends_on"]
        if any(dependency not in module_by_id for dependency in dependencies):
            violations.append(f"unknown Android dependency from {module_id}")
    if _cycle(module_by_id):
        violations.append("cyclic Android module dependency")
    published = [module["id"] for module in modules if module["visibility"] == "published"]
    if published != ["framework"]:
        violations.append("framework must be the only published Android module")
    return violations


def check_android_topology(root: Path) -> list[str]:
    """Validate the repository's Android topology contract."""
    return check_topology_manifest(root / "platforms" / "android" / "architecture.json")


def main() -> int:
    """Run the Android topology checker from the repository root."""
    violations = check_android_topology(Path(__file__).resolve().parents[1])
    if violations:
        print("Android topology check failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print("Android topology check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
