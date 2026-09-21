from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_architecture import check_workspace


class ArchitectureCheckTests(unittest.TestCase):
    def create_workspace(self, root: Path, members: list[str]) -> None:
        member_lines = ", ".join(f'"{member}"' for member in members)
        (root / "Cargo.toml").write_text(
            f"[workspace]\nmembers = [{member_lines}]\nresolver = \"3\"\n",
            encoding="utf-8",
        )

    def create_package(
        self,
        root: Path,
        relative_path: str,
        package_name: str,
        dependencies: str = "",
    ) -> None:
        directory = root / relative_path
        directory.mkdir(parents=True)
        (directory / "Cargo.toml").write_text(
            f'[package]\nname = "{package_name}"\nversion = "0.1.0"\n{dependencies}',
            encoding="utf-8",
        )

    def test_accepts_inward_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_workspace(root, ["crates/rmf-core", "crates/rmf-runtime"])
            self.create_package(root, "crates/rmf-core", "rmf-core")
            self.create_package(
                root,
                "crates/rmf-runtime",
                "rmf-runtime",
                '\n[dependencies]\nrmf-core = { path = "../rmf-core" }\n',
            )

            self.assertEqual(check_workspace(root), [])

    def test_rejects_outward_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_workspace(root, ["crates/rmf-core", "crates/rmf-runtime"])
            self.create_package(
                root,
                "crates/rmf-core",
                "rmf-core",
                '\n[dependencies]\nrmf-runtime = { path = "../rmf-runtime" }\n',
            )
            self.create_package(root, "crates/rmf-runtime", "rmf-runtime")

            violations = check_workspace(root)

            self.assertEqual(len(violations), 1)
            self.assertIn("forbidden outward dependency", violations[0])

    def test_rejects_unclassified_workspace_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_workspace(root, ["unknown/package"])
            self.create_package(root, "unknown/package", "unknown")

            violations = check_workspace(root)

            self.assertEqual(len(violations), 1)
            self.assertIn("unclassified workspace package", violations[0])

    def test_rejects_external_dependency_in_core(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_workspace(root, ["crates/rmf-core"])
            self.create_package(
                root,
                "crates/rmf-core",
                "rmf-core",
                '\n[dependencies]\nexternal = "1"\n',
            )

            violations = check_workspace(root)

            self.assertEqual(len(violations), 1)
            self.assertIn("has external dependency external", violations[0])

    def test_accepts_benchmark_composition_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_workspace(root, ["crates/rmf-core", "benchmarks/rmf-bench"])
            self.create_package(root, "crates/rmf-core", "rmf-core")
            self.create_package(
                root,
                "benchmarks/rmf-bench",
                "rmf-bench",
                '\n[dependencies]\nrmf-core = { path = "../../crates/rmf-core" }\n',
            )

            self.assertEqual(check_workspace(root), [])

    def test_accepts_reconciliation_dependency_on_core(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_workspace(root, ["crates/rmf-core", "crates/rmf-reconciliation"])
            self.create_package(root, "crates/rmf-core", "rmf-core")
            self.create_package(
                root,
                "crates/rmf-reconciliation",
                "rmf-reconciliation",
                '\n[dependencies]\nrmf-core = { path = "../rmf-core" }\n',
            )

            self.assertEqual(check_workspace(root), [])

    def test_rejects_core_dependency_on_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_workspace(root, ["crates/rmf-core", "crates/rmf-reconciliation"])
            self.create_package(
                root,
                "crates/rmf-core",
                "rmf-core",
                '\n[dependencies]\nrmf-reconciliation = { path = "../rmf-reconciliation" }\n',
            )
            self.create_package(root, "crates/rmf-reconciliation", "rmf-reconciliation")

            violations = check_workspace(root)

            self.assertEqual(len(violations), 1)
            self.assertIn("forbidden outward dependency", violations[0])

    def test_rejects_external_dependency_in_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_workspace(root, ["crates/rmf-core", "crates/rmf-reconciliation"])
            self.create_package(root, "crates/rmf-core", "rmf-core")
            self.create_package(
                root,
                "crates/rmf-reconciliation",
                "rmf-reconciliation",
                '\n[dependencies]\nexternal = "1"\n',
            )

            violations = check_workspace(root)

            self.assertEqual(len(violations), 1)
            self.assertIn("has external dependency external", violations[0])


if __name__ == "__main__":
    unittest.main()
