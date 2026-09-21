#!/usr/bin/env python3
"""Validate the closed design contract for the public Android Kotlin API."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "contracts" / "android-api" / "v1" / "public-api.json"
TOP_LEVEL_FIELDS = {
    "contract_version",
    "artifact",
    "namespace",
    "api_version",
    "stability",
    "declarations",
    "forbidden_surface",
    "compatibility",
    "build_requirements",
}
CLASS_FIELDS = {
    "kind",
    "fq_name",
    "visibility",
    "modality",
    "constructor_visibility",
    "supertypes",
    "annotations",
    "members",
    "documentation_required",
}
MEMBER_FIELDS = {
    "kind",
    "name",
    "owner",
    "visibility",
    "modality",
    "static_for_java",
    "override",
    "parameters",
    "return",
    "threading",
    "idempotent",
    "throws",
    "jvm_descriptor",
    "documentation_required",
}
PARAMETER_FIELDS = {"name", "type", "nullable"}
RETURN_FIELDS = {"type", "nullable"}
EXPECTED_COMPATIBILITY = {
    "policy": "semver_pre_1_0",
    "patch_release": "additive_only",
    "minor_breaking_change": "requires_adr_migration_and_changelog",
    "stable_breaking_change": "major_only",
    "binary": "required",
    "source": "best_effort",
    "behavioral_contracts": [
        "contracts/android-facade/v1/contract.json",
        "contracts/android-ffi/v1/contract.json",
    ],
}
EXPECTED_BUILD_REQUIREMENTS = {
    "kotlin_toolchain_owner": "android_gradle_plugin",
    "built_in_kotlin": True,
    "external_kotlin_android_plugin": False,
    "jvm_target": 17,
    "explicit_api_mode": "strict",
    "abi_validation_task": "checkKotlinAbi",
    "warnings_as_errors": True,
    "public_api_kdoc": True,
}
EXPECTED_FORBIDDEN = {
    "types": [
        "java.nio.ByteBuffer",
        "kotlin.ByteArray",
        "dev.rmf.android.internal.NativeBridge",
    ],
    "features": [
        "public_data_class",
        "public_default_argument",
        "public_inline",
        "public_typealias",
        "published_api",
        "mutable_public_property",
        "native_pointer",
        "partial_surface_handle",
    ],
}
EXPECTED_MEMBERS = {
    "<init>": {
        "kind": "constructor",
        "owner": "instance",
        "static_for_java": False,
        "override": False,
        "parameters": [
            {"name": "container", "type": "android.view.ViewGroup", "nullable": False}
        ],
        "return": {"type": "kotlin.Unit", "nullable": False},
        "threading": "any_thread_marshaled",
        "idempotent": False,
        "jvm_descriptor": "(Landroid/view/ViewGroup;)V",
    },
    "close": {
        "kind": "function",
        "owner": "instance",
        "static_for_java": False,
        "override": True,
        "parameters": [],
        "return": {"type": "kotlin.Unit", "nullable": False},
        "threading": "any_thread_marshaled",
        "idempotent": True,
        "jvm_descriptor": "()V",
    },
}


def _load(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"cannot load Android public API: {error}"]
    if not isinstance(value, dict):
        return None, ["Android public API root must be an object"]
    return value, []


def check_public_api_manifest(path: Path = MANIFEST, root: Path = ROOT) -> list[str]:
    """Return every closed-contract violation found in the API manifest."""
    manifest, violations = _load(path)
    if manifest is None:
        return violations
    if set(manifest) != TOP_LEVEL_FIELDS:
        return ["Android public API fields are not closed"]
    if (
        manifest["contract_version"] != 1
        or manifest["artifact"] != "rmf-android.aar"
        or manifest["namespace"] != "dev.rmf.android"
        or manifest["api_version"] != "0.1.0"
        or manifest["stability"] != "experimental"
    ):
        violations.append("unexpected Android public API identity")
    if manifest["forbidden_surface"] != EXPECTED_FORBIDDEN:
        violations.append("Android public API forbidden-surface drift")
    if manifest["compatibility"] != EXPECTED_COMPATIBILITY:
        violations.append("Android public API compatibility-policy drift")
    if manifest["build_requirements"] != EXPECTED_BUILD_REQUIREMENTS:
        violations.append("Android public API build-requirement drift")

    declarations = manifest["declarations"]
    if not isinstance(declarations, list) or len(declarations) != 1:
        violations.append("Android public API must contain exactly one declaration")
        return violations
    declaration = declarations[0]
    if not isinstance(declaration, dict) or set(declaration) != CLASS_FIELDS:
        violations.append("Android public class fields are not closed")
        return violations
    expected_class = {
        "kind": "class",
        "fq_name": "dev.rmf.android.RmfSurfaceHost",
        "visibility": "public",
        "modality": "final",
        "constructor_visibility": "public",
        "supertypes": ["java.lang.AutoCloseable"],
        "annotations": [],
        "documentation_required": True,
    }
    for field, expected in expected_class.items():
        if declaration[field] != expected:
            violations.append(f"Android public class drift: {field}")

    members = declaration["members"]
    if not isinstance(members, list) or len(members) != len(EXPECTED_MEMBERS):
        violations.append("unexpected Android public member count")
        return violations
    if any(not isinstance(member, dict) or set(member) != MEMBER_FIELDS for member in members):
        violations.append("Android public member fields are not closed")
        return violations
    names = [member["name"] for member in members]
    if len(set(names)) != len(names) or set(names) != set(EXPECTED_MEMBERS):
        violations.append("unexpected Android public member registry")
        return violations

    forbidden_types = set(EXPECTED_FORBIDDEN["types"])
    for member in members:
        name = member["name"]
        common = {
            "visibility": "public",
            "modality": "final",
            "throws": [],
            "documentation_required": True,
        }
        for field, expected in {**common, **EXPECTED_MEMBERS[name]}.items():
            if member[field] != expected:
                violations.append(f"Android public member drift: {name}.{field}")
        parameters = member["parameters"]
        if not isinstance(parameters, list) or any(
            not isinstance(parameter, dict) or set(parameter) != PARAMETER_FIELDS
            for parameter in parameters
        ):
            violations.append(f"invalid Android public parameters: {name}")
            continue
        result = member["return"]
        if not isinstance(result, dict) or set(result) != RETURN_FIELDS:
            violations.append(f"invalid Android public return: {name}")
            continue
        exposed_types = [parameter["type"] for parameter in parameters]
        exposed_types.append(result["type"])
        if forbidden_types.intersection(exposed_types):
            violations.append(f"forbidden Android public type: {name}")
        descriptor = member["jvm_descriptor"]
        if not isinstance(descriptor, str) or not re.fullmatch(r"\([^)]*\).+", descriptor):
            violations.append(f"invalid JVM descriptor: {name}")

    for relative in EXPECTED_COMPATIBILITY["behavioral_contracts"]:
        if not (root / relative).is_file():
            violations.append(f"missing Android behavioral contract: {relative}")
    topology_path = root / "platforms" / "android" / "architecture.json"
    try:
        topology = json.loads(topology_path.read_text(encoding="utf-8"))
        framework = next(
            module for module in topology["modules"] if module["id"] == "framework"
        )
    except (OSError, json.JSONDecodeError, KeyError, StopIteration, TypeError) as error:
        violations.append(f"cannot resolve Android framework ownership: {error}")
    else:
        declared_classes = [declaration["fq_name"] for declaration in declarations]
        if framework.get("public_symbols") != declared_classes:
            violations.append("Android topology and public API symbols differ")
    return violations


def main() -> int:
    """Run the public Android API contract check."""
    violations = check_public_api_manifest()
    if violations:
        print("Android public API check failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print("Android public API check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
