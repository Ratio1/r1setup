#!/usr/bin/env python3
"""Shared test bootstrap helpers for importing the r1setup script as a module."""

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
R1SETUP_PATH = SCRIPT_DIR / "r1setup"


def load_r1setup_module():
    """Load r1setup as a Python module while suppressing CLI side effects."""
    loader = importlib.machinery.SourceFileLoader("r1setup", str(R1SETUP_PATH))
    spec = importlib.util.spec_from_loader("r1setup", loader, origin=str(R1SETUP_PATH))
    old_argv = sys.argv
    old_no_venv = os.environ.get("R1SETUP_NO_VENV")

    sys.argv = ["r1setup"]
    os.environ["R1SETUP_NO_VENV"] = "1"

    try:
        module = importlib.util.module_from_spec(spec)
        module.__file__ = str(R1SETUP_PATH)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.argv = old_argv
        if old_no_venv is None:
            os.environ.pop("R1SETUP_NO_VENV", None)
        else:
            os.environ["R1SETUP_NO_VENV"] = old_no_venv


r1setup = load_r1setup_module()
