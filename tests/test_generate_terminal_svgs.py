from __future__ import annotations

import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "generate_terminal_svgs.py"
)
SPEC = importlib.util.spec_from_file_location("terminal_svgs", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load terminal SVG generator")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TerminalSvgTests(unittest.TestCase):
    def test_wrapped_lines_fit_the_terminal_width(self) -> None:
        lines = MODULE.wrapped("word " * 80, indent=2)

        self.assertTrue(all(len(line[0][0]) <= MODULE.WRAP for line in lines))
        self.assertTrue(all(line[0][0].startswith("  ") for line in lines))

    def test_labeled_text_continues_under_its_column(self) -> None:
        lines = MODULE.labeled("Label", "text " * 40, 10, "yellow")

        self.assertEqual(lines[0][0][0], "Label".ljust(10))
        self.assertEqual(lines[1][0][0], " " * 10)

    def test_panels_render_as_valid_svg_with_escaped_text(self) -> None:
        for panel in MODULE.build_panels():
            with self.subTest(panel=panel.name):
                root = ET.fromstring(MODULE.render_panel(panel))
                self.assertTrue(root.tag.endswith("svg"))

        panel = MODULE.Panel("demo", [MODULE.Block("echo", [MODULE.text_line("A & <B>")])])
        self.assertIn("A &amp; &lt;B&gt;", MODULE.render_panel(panel))


if __name__ == "__main__":
    unittest.main()
