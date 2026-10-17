"""Smoke tests: the package is installed, importable, and keeps core free of GUI code."""

import ast
import importlib.metadata
import unittest
from pathlib import Path

import ledger
import ledger.core
import ledger.gui


class SmokeTest(unittest.TestCase):
    """Checks that the project skeleton is wired up correctly."""

    def test_version_matches_installed_metadata(self) -> None:
        """ledger.__version__ agrees with the version in pyproject.toml."""
        installed = importlib.metadata.version("ledger")
        self.assertEqual(ledger.__version__, installed)

    def test_subpackages_import(self) -> None:
        """The core and gui subpackages load from the src folder."""
        for package in (ledger.core, ledger.gui):
            with self.subTest(package=package.__name__):
                package_file = Path(package.__file__)
                self.assertEqual(package_file.name, "__init__.py")
                self.assertIn("src", package_file.parts)

    def test_core_has_no_tkinter_imports(self) -> None:
        """No module in ledger.core imports tkinter (low coupling)."""
        core_dir = Path(ledger.core.__file__).parent
        offenders: list[str] = []
        for path in sorted(core_dir.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                if any(name.split(".")[0] == "tkinter" for name in names):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders, [], f"tkinter imported in core: {offenders}")


if __name__ == "__main__":
    unittest.main()