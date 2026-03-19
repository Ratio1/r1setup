#!/usr/bin/env python3
"""Tests for empty-machine preparation workflows."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestPrepareRegisteredMachines(unittest.TestCase):
    """Tests for machine-only preparation flow."""

    def test_prepare_registered_machines_updates_machine_states_from_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            playbooks_dir = base_path / "playbooks"
            playbooks_dir.mkdir(parents=True, exist_ok=True)
            (playbooks_dir / "prepare_machine.yml").write_text("---\n")

            fleet_state = {
                "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
                "fleet": {
                    "machines": {
                        "machine-a": {
                            "machine_id": "machine-a",
                            "ansible_host": "10.0.0.10",
                            "ansible_user": "root",
                            "ansible_port": 22,
                            "topology_mode": "standard",
                            "deployment_state": "empty",
                            "instance_names": [],
                        },
                        "machine-b": {
                            "machine_id": "machine-b",
                            "ansible_host": "10.0.0.11",
                            "ansible_user": "root",
                            "ansible_port": 22,
                            "topology_mode": "expert",
                            "deployment_state": "empty",
                            "instance_names": [],
                        },
                    },
                    "instances": {},
                },
            }

            app = r1setup.R1Setup.__new__(r1setup.R1Setup)
            app.config_manager = MagicMock()
            app.config_manager.active_config = {"config_name": "fleet", "deployment_status": "never_deployed"}
            app.config_dir = base_path
            app.settings_manager = MagicMock()
            app.settings_manager.connection_timeout = 30
            app.get_mnl_app_env = MagicMock(return_value="mainnet")
            app.load_configuration = MagicMock()
            app.get_fleet_state_copy = MagicMock(return_value=fleet_state)
            app.select_registered_machines = MagicMock(return_value=["machine-a", "machine-b"])
            app.get_input = MagicMock(return_value="y")
            app.print_header = MagicMock()
            app.print_colored = MagicMock()
            app.wait_for_enter = MagicMock()
            app.upsert_machine_record = MagicMock()
            app.run_registered_machine_playbook = MagicMock(return_value=(
                False,
                "machine output",
                ["machine_a", "machine_b"],
                {
                    "all": {
                        "children": {
                            "gpu_nodes": {
                                "hosts": {
                                    "machine_a": {"r1setup_machine_id": "machine-a"},
                                    "machine_b": {"r1setup_machine_id": "machine-b"},
                                }
                            }
                        }
                    }
                },
            ))
            app._parse_ansible_play_recap = MagicMock(return_value={
                "machine_a": {"status": "connected"},
                "machine_b": {"status": "failed"},
            })
            app.config_manager._format_machine_connection_display.side_effect = (
                lambda machine: f"{machine.get('ansible_user', 'root')}@{machine.get('ansible_host', 'unknown')}"
            )
            app.config_manager._format_machine_specs_summary.return_value = ""

            service = r1setup.DeploymentService(app)
            service.prepare_registered_machines(skip_gpu=False)

            self.assertEqual(app.run_registered_machine_playbook.call_count, 1)
            self.assertEqual(app.upsert_machine_record.call_count, 2)
            app.upsert_machine_record.assert_any_call("machine-a", {
                "machine_id": "machine-a",
                "ansible_host": "10.0.0.10",
                "ansible_user": "root",
                "ansible_port": 22,
                "topology_mode": "standard",
                "deployment_state": "prepared",
                "instance_names": [],
            })
            app.upsert_machine_record.assert_any_call("machine-b", {
                "machine_id": "machine-b",
                "ansible_host": "10.0.0.11",
                "ansible_user": "root",
                "ansible_port": 22,
                "topology_mode": "expert",
                "deployment_state": "error",
                "instance_names": [],
            })

    def test_prepare_registered_machines_handles_no_empty_records(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"config_name": "fleet"}
        app.load_configuration = MagicMock()
        app.get_fleet_state_copy = MagicMock(return_value={
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {"machines": {}, "instances": {}},
        })
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.wait_for_enter = MagicMock()

        service = r1setup.DeploymentService(app)
        service.prepare_registered_machines()

        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("No registered empty machines are available.", rendered_text)
