from importlib.util import find_spec
from pathlib import Path
import pkgutil
import re
import subprocess
import sys
import unittest

from vdi2230 import __version__, ui


class ReleaseStructureTests(unittest.TestCase):
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
