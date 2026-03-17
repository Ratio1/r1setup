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

    def test_service_version_tracks_service_template(self):
        group_vars_path = R1SETUP_PATH.parent.parent / "group_vars" / "mnl.yml"
        template_path = R1SETUP_PATH.parent.parent / "roles" / "setup" / "templates" / "edge_node.service.j2"
        metadata_template_path = R1SETUP_PATH.parent.parent / "roles" / "setup" / "templates" / "r1setup-metadata.json.j2"
        dispatcher_template_path = R1SETUP_PATH.parent.parent / "roles" / "setup" / "templates" / "r1service.j2"
        helper_registry_template_path = R1SETUP_PATH.parent.parent / "roles" / "setup" / "templates" / "r1service-instance.env.j2"
        services_tasks_path = R1SETUP_PATH.parent.parent / "roles" / "setup" / "tasks" / "services.yml"
        render_tasks_path = R1SETUP_PATH.parent.parent / "roles" / "setup" / "tasks" / "render_edge_node_definition.yml"
        node_info_playbook_path = R1SETUP_PATH.parent.parent / "playbooks" / "get_node_info.yml"
        group_vars_source = group_vars_path.read_text()
        template_source = template_path.read_text()
        metadata_template_source = metadata_template_path.read_text()
        dispatcher_template_source = dispatcher_template_path.read_text()
        helper_registry_template_source = helper_registry_template_path.read_text()
        services_tasks_source = services_tasks_path.read_text()
        render_tasks_source = render_tasks_path.read_text()
        node_info_playbook_source = node_info_playbook_path.read_text()

        service_version_match = re.search(r'^mnl_service_version:\s*"([^"]+)"', group_vars_source, re.MULTILINE)
        self.assertIsNotNone(service_version_match, "mnl_service_version must be defined in group_vars/mnl.yml")
        self.assertEqual(
            service_version_match.group(1),
            "v1",
            "mnl_service_version should default to a visible service-template revision",
        )

        self.assertIn(
            "{{ mnl_service_version }}",
            template_source,
            "edge_node.service.j2 must embed mnl_service_version for deployed service tracking",
        )
        self.assertIn(
            "R1SETUP_SERVICE_FILE_VERSION",
            template_source,
            "edge_node.service.j2 must expose a machine-readable service version marker",
        )
        self.assertIn(
            "R1SETUP_METADATA_PATH",
            template_source,
            "edge_node.service.j2 must expose the metadata file path to the container",
        )
        self.assertIn(
            "{{ mnl_docker_volume_path }}:{{ mnl_docker_persistent_folder }}",
            template_source,
            "edge_node.service.j2 must continue to mount the main persistent volume",
        )
        self.assertNotIn(
            "{{ mnl_r1setup_metadata_host_path }}:{{ mnl_r1setup_metadata_container_path }}:ro",
            template_source,
            "edge_node.service.j2 should not add a second dedicated metadata mount",
        )

        self.assertIn(
            'mnl_r1setup_metadata_host_path: "{{ mnl_r1setup_metadata_host_dir }}/metadata.json"',
            group_vars_source,
            "mnl.yml must define the canonical host metadata path",
        )
        self.assertIn(
            'mnl_r1setup_metadata_host_dir: "{{ mnl_docker_volume_path }}/_data/r1setup"',
            group_vars_source,
            "mnl.yml must keep metadata under the existing host persistent volume",
        )
        self.assertIn(
            'mnl_r1setup_metadata_container_path: "{{ mnl_r1setup_metadata_container_dir }}/metadata.json"',
            group_vars_source,
            "mnl.yml must define the canonical container metadata path",
        )
        self.assertIn(
            'mnl_r1setup_metadata_container_dir: "{{ mnl_docker_persistent_folder }}/_data/r1setup"',
            group_vars_source,
            "mnl.yml must expose metadata inside the existing container persistent volume",
        )
        self.assertIn(
            'r1setup_helper_mode: "{{ \'expert_dispatcher\' if (r1setup_topology_mode | default(\'standard\')) == \'expert\' else \'standard_helpers\' }}"',
            group_vars_source,
            "mnl.yml must define helper mode from topology",
        )
        self.assertIn(
            'r1setup_helper_registry_dir: "/var/lib/ratio1/r1setup/helpers"',
            group_vars_source,
            "mnl.yml must define the helper registry directory",
        )
        self.assertIn(
            'r1setup_remote_get_node_info_command:',
            group_vars_source,
            "mnl.yml must define a topology-aware node-info helper command",
        )
        self.assertIn(
            '"managed_by": "r1setup"',
            metadata_template_source,
            "r1setup metadata template must identify its manager",
        )
        self.assertIn(
            '"service_file_version": {{ mnl_service_version | to_json }}',
            metadata_template_source,
            "metadata template must expose the service file version",
        )
        self.assertIn(
            '"collection_version": {{ r1setup_collection_version_effective',
            metadata_template_source,
            "metadata template must expose the collection version",
        )
        self.assertIn(
            '"last_applied_action": {{ r1setup_last_applied_action_effective',
            metadata_template_source,
            "metadata template must expose the last applied action",
        )

        image_url_match = re.search(r'^mnl_docker_image_url:\s*"([^"]+)"', group_vars_source, re.MULTILINE)
        self.assertIsNotNone(image_url_match, "mnl_docker_image_url must be defined in group_vars/mnl.yml")
        self.assertIn(
            "{{ mnl_app_env }}",
            image_url_match.group(1),
            "mnl_docker_image_url must continue to use mnl_app_env as the image tag source",
        )
        self.assertNotIn(
            "{{ mnl_service_version }}",
            image_url_match.group(1),
            "mnl_service_version must not change Docker image selection semantics",
        )
        self.assertIn(
            'Usage:',
            dispatcher_template_source,
            "r1service dispatcher must provide operator-facing usage text",
        )
        self.assertIn(
            'REGISTRY_DIR="{{ r1setup_helper_registry_dir }}"',
            dispatcher_template_source,
            "r1service dispatcher must use the shared helper registry directory",
        )
        self.assertIn(
            "EDGE_NODE_SERVICE_NAME='{{ edge_node_service_name }}'",
            helper_registry_template_source,
            "helper registry template must persist the service name",
        )
        self.assertIn(
            'when: r1setup_helper_mode == \'standard_helpers\'',
            services_tasks_source,
            "services.yml must keep standard helpers gated behind standard helper mode",
        )
        self.assertIn(
            'when: r1setup_helper_mode == \'expert_dispatcher\'',
            services_tasks_source,
            "services.yml must install the dispatcher only for expert helper mode",
        )
        self.assertIn(
            'Render helper registry entry',
            render_tasks_source,
            "render_edge_node_definition.yml must maintain the per-instance helper registry",
        )
        self.assertIn(
            '{{ r1setup_remote_get_node_info_command }}',
            node_info_playbook_source,
            "get_node_info.yml must use the topology-aware helper command",
        )
