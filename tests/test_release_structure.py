from importlib.util import find_spec
from pathlib import Path
import pkgutil
import re
import subprocess
import sys
import unittest

from vdi2230 import __version__, ui


class ReleaseStructureTests(unittest.TestCase):
    def test_project_documentation_local_links_resolve(self):
        root = Path(__file__).parents[1]
        for name in ("README.md", "SOFTWARE_SPECIFICATION.md"):
            document = (root / name).read_text(encoding="utf-8")
            targets = re.findall(r"\]\((\./[^)]+)\)", document)
            self.assertTrue(targets, f"{name} must link to project documentation")
            for target in targets:
                with self.subTest(document=name, target=target):
                    self.assertTrue((root / target).is_file(), f"Missing target: {target}")

    def test_software_specification_is_consolidated_and_english(self):
        root = Path(__file__).parents[1]
        specification = (root / "SOFTWARE_SPECIFICATION.md").read_text(encoding="utf-8")
        self.assertNotRegex(specification, r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
        self.assertEqual(
            re.findall(r"^### FR-(\d{2}):", specification, re.MULTILINE),
            [f"{number:02}" for number in range(1, 13)],
        )
        self.assertIn(f"VDI 2230 Bolt Calculator {__version__}", specification)
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("(./SOFTWARE_SPECIFICATION.md)", readme)
        for name in (
            "SOFTWARE_REQUIREMENTS_SPECIFICATION.md",
            "SOFTWARE_ARCHITECTURE_AND_BUILD_PLAN.md",
        ):
            with self.subTest(legacy_document=name):
                self.assertFalse((root / name).exists())
                self.assertNotIn(name, readme)
                self.assertNotIn(name, specification)

    def test_readme_version_and_module_startup_options(self):
        readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"**Version {__version__}**", readme)
        for option, expected in (
            ("--version", f"vdi2230 {__version__}"),
            ("--help", "usage:"),
        ):
            with self.subTest(option=option):
                self.assertIn(f"vdi2230 {option}", readme)
                completed = subprocess.run(
                    [sys.executable, "-m", "vdi2230", option],
                    capture_output=True, text=True, check=False, timeout=15,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn(expected, completed.stdout)

    def test_only_general_tk_modules_are_available(self):
        self.assertEqual(
            {module.name for module in pkgutil.iter_modules(ui.__path__)},
            {"general_model", "general_window"},
        )
        for name in ("web", "ui.main_window", "ui.reference_cases", "ui.forms", "ui.section_view"):
            with self.subTest(module=name):
                self.assertIsNone(find_spec(f"vdi2230.{name}"))

    def test_release_metadata_has_one_entry_point_and_no_browser_dependencies(self):
        manifest = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'^version = "([^"]+)"$', manifest, re.MULTILINE), [__version__])
        self.assertEqual(__version__, "0.0.1")
        scripts = manifest.split("[project.scripts]\n", 1)[1].split("\n[", 1)[0].strip()
        self.assertEqual(scripts, 'vdi2230 = "vdi2230.__main__:main"')
        for removed in ("vdi2230.web", "playwright", "ui-test"):
            self.assertNotIn(removed, manifest)

    def test_form_model_calculates_without_tk_or_http(self):
        completed = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.modules['tkinter'] = None; sys.modules['http.server'] = None; "
             "from vdi2230.ui.general_model import GeneralFormModel; "
             "outcome = GeneralFormModel().calculate(); "
             "assert outcome.ok, outcome.error; assert outcome.report"],
            capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
