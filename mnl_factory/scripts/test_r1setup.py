#!/usr/bin/env python3
"""Compatibility runner for the modular r1setup test suite."""

from pathlib import Path
import unittest


def load_suite():
    script_dir = Path(__file__).resolve().parent
    tests_dir = script_dir / "tests"
    return unittest.defaultTestLoader.discover(
        start_dir=str(tests_dir),
        pattern="test_*.py",
        top_level_dir=str(script_dir),
    )


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(load_suite())
    raise SystemExit(0 if result.wasSuccessful() else 1)
