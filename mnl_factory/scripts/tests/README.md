# r1setup Test Suite

This folder contains the modular test suite for `mnl_factory/scripts/r1setup`.

Layout:

- `support.py`: shared bootstrap logic for loading the `r1setup` script as a Python module
- `test_module_helpers.py`: module-level helper coverage
- `test_version_manager.py`: version comparison behavior
- `test_node_status_tracker.py`: node status parsing and state transitions
- `test_r1setup_core.py`: core `R1Setup` instance helpers
- `test_structural_invariants.py`: regression and structural invariants
- `test_settings_manager.py`: settings timeout logic

Compatibility:

- `python3 test_r1setup.py`
- `python3 -m unittest discover tests`
- `python3 -m pytest tests -v`
