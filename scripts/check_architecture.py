#!/usr/bin/env python3
"""Validate dependency direction between Cargo workspace layers."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

try:
    from scripts.check_android_topology import check_android_topology
except ModuleNotFoundError:
    from check_android_topology import check_android_topology


DEPENDENCY_SECTIONS = ("dependencies", "dev-dependencies", "build-dependencies")
LAYERS = (
    (Path("crates/rmf-core"), "core", 0),
    (Path("crates/rmf-reconciliation"), "core-service", 1),
    (Path("crates/rmf-runtime"), "runtime", 2),
    (Path("adapters"), "adapter", 3),
    (Path("platforms"), "adapter", 3),
    (Path("benchmarks"), "composition", 4),
    (Path("examples"), "composition", 4),
)


def load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML document from disk."""
    with path.open("rb") as stream:
        return tomllib.load(stream)


def classify(root: Path, manifest: Path) -> tuple[str, int] | None:
    """Return the declared architecture layer for a package manifest."""
    package_directory = manifest.parent.resolve().relative_to(root.resolve())
    for prefix, name, rank in LAYERS:
        if package_directory == prefix or prefix in package_directory.parents:
            return name, rank
    return None


def workspace_manifests(root: Path) -> list[Path]:
    """Resolve all explicit or globbed workspace member manifests."""
    workspace = load_toml(root / "Cargo.toml").get("workspace", {})
    members = workspace.get("members", [])
    manifests: set[Path] = set()
    for member in members:
        matches = root.glob(member) if any(char in member for char in "*?[") else [root / member]
        for package_directory in matches:
            manifest = package_directory / "Cargo.toml"
            if manifest.is_file():
                manifests.add(manifest.resolve())
    return sorted(manifests)


def dependency_specs(manifest_data: dict[str, Any]) -> list[tuple[str, Any]]:
    """Collect dependency specifications from normal and target-specific tables."""
    specs: list[tuple[str, Any]] = []
    for section_name in DEPENDENCY_SECTIONS:
        section = manifest_data.get(section_name, {})
        if isinstance(section, dict):
            specs.extend(section.items())

    targets = manifest_data.get("target", {})
    if isinstance(targets, dict):
        for target in targets.values():
            if not isinstance(target, dict):
                continue
            for section_name in DEPENDENCY_SECTIONS:
                section = target.get(section_name, {})
                if isinstance(section, dict):
                    specs.extend(section.items())
    return specs


def check_workspace(root: Path) -> list[str]:
    """Return architecture violations; an empty list means the check passed."""
    root = root.resolve()
    violations: list[str] = []
    manifests = workspace_manifests(root)
    manifest_set = set(manifests)

    for manifest in manifests:
        source_layer = classify(root, manifest)
        relative_manifest = manifest.relative_to(root)
        if source_layer is None:
            violations.append(f"unclassified workspace package: {relative_manifest}")
            continue

        source_name, source_rank = source_layer
        for dependency_name, specification in dependency_specs(load_toml(manifest)):
            if not isinstance(specification, dict) or "path" not in specification:
                if source_name in {"core", "core-service"}:
                    violations.append(
                        f"{source_name} package {relative_manifest} has external dependency "
                        f"{dependency_name}"
                    )
                continue

            target_manifest = (manifest.parent / specification["path"] / "Cargo.toml").resolve()
            if target_manifest not in manifest_set:
                continue

            target_layer = classify(root, target_manifest)
            if target_layer is None:
                violations.append(
                    f"dependency target is unclassified: {target_manifest.relative_to(root)}"
                )
                continue

            target_name, target_rank = target_layer
            if target_rank > source_rank:
                violations.append(
                    f"forbidden outward dependency: {relative_manifest} ({source_name}) -> "
                    f"{target_manifest.relative_to(root)} ({target_name})"
                )

    return violations


def main() -> int:
    """Run the checker against the repository containing this script."""
    root = Path(__file__).resolve().parents[1]
    violations = check_workspace(root) + check_android_topology(root)
    if violations:
        print("Architecture check failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print("Architecture check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
