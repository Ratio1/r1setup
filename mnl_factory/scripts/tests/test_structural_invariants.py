#!/usr/bin/env python3
"""Structural and regression invariants for the r1setup script."""

import re
import unittest
from pathlib import Path

from tests.support import R1SETUP_PATH


class TestStructuralInvariants(unittest.TestCase):
    """Verify code-quality invariants enforced for the script."""

    @classmethod
    def setUpClass(cls):
        with open(R1SETUP_PATH) as handle:
            cls.source = handle.read()
        cls.lines = cls.source.split("\n")

    def test_no_bare_except(self):
        for i, line in enumerate(self.lines, 1):
            if line.strip() == "except:":
                self.fail(f"Bare 'except:' found at line {i}: {line.strip()}")

    def test_no_raw_gpu_hosts_chain(self):
        pattern = re.compile(r"\.get\('gpu_nodes',\s*\{\}\)\.get\('hosts',\s*\{\}\)")
        in_helper = False
        for i, line in enumerate(self.lines, 1):
            if "def _get_gpu_hosts" in line:
                in_helper = True
                continue
            if in_helper and line and not line[0].isspace():
                in_helper = False
            if pattern.search(line) and not in_helper:
                self.fail(f"Raw gpu_hosts chain at line {i}: {line.strip()}")

    def test_no_raw_press_enter_input(self):
        pattern = re.compile(r'input\(["\'].*[Pp]ress [Ee]nter')
        for i, line in enumerate(self.lines, 1):
            if pattern.search(line):
                self.fail(f"Raw Press Enter input() at line {i}: {line.strip()}")

    def test_fromisoformat_only_in_helper(self):
        occurrences = []
        in_helper = False
        for i, line in enumerate(self.lines, 1):
            if "def _parse_iso_to_datetime" in line:
                in_helper = True
            elif in_helper and (line.strip().startswith("def ") or
                                (line.strip().startswith("class ") and not line.startswith(" "))):
                in_helper = False
            if "fromisoformat" in line and not in_helper:
                occurrences.append((i, line.strip()))
        if occurrences:
            details = "\n".join(f"  line {n}: {l}" for n, l in occurrences)
            self.fail(f"fromisoformat found outside helper:\n{details}")

    def test_get_gpu_hosts_not_recursive(self):
        in_func = False
        for i, line in enumerate(self.lines, 1):
            if "def _get_gpu_hosts" in line:
                in_func = True
                continue
            if in_func:
                if line and not line[0].isspace():
                    break
                if "_get_gpu_hosts(" in line:
                    self.fail(f"_get_gpu_hosts calls itself at line {i} — infinite recursion!")

    def test_wait_for_enter_defined_once(self):
        defs = [i for i, line in enumerate(self.lines, 1) if "def wait_for_enter" in line]
        self.assertEqual(len(defs), 1, f"Expected 1 definition, found {len(defs)} at lines {defs}")

    def test_syntax_valid(self):
        import py_compile

        try:
            py_compile.compile(str(R1SETUP_PATH), doraise=True)
        except py_compile.PyCompileError as exc:
            self.fail(f"Syntax error: {exc}")

    def test_no_hardcoded_connect_timeout_10(self):
        pattern = re.compile(r"ConnectTimeout=10['\"]")
        for i, line in enumerate(self.lines, 1):
            if pattern.search(line):
                self.fail(f"Hardcoded ConnectTimeout=10 at line {i}: {line.strip()}")

    def test_no_hardcoded_timeout_30_in_node_run_command(self):
        pattern = re.compile(r"run_command\(.*timeout=30\)")
        for i, line in enumerate(self.lines, 1):
            if pattern.search(line):
                self.fail(f"Hardcoded timeout=30 in run_command at line {i}: {line.strip()}")

    def test_fallback_version_matches_ver_py(self):
        ver_source = Path(R1SETUP_PATH.parent / "ver.py").read_text()
        ver_match = re.search(r"__VER__\s*=\s*['\"]([^'\"]+)['\"]", ver_source)
        self.assertIsNotNone(ver_match, "Unable to find __VER__ in ver.py")

        fallback_match = re.search(r'CLI_VERSION = "([^"]+)"', self.source)
        self.assertIsNotNone(fallback_match, "Unable to find fallback CLI_VERSION in r1setup")

        self.assertEqual(
            fallback_match.group(1),
            ver_match.group(1),
            "r1setup fallback CLI_VERSION must match ver.py __VER__",
        )
