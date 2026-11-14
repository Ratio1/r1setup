#!/usr/bin/env python3
"""Tests of the edge_node service definition: the unit template and the files rendered with it."""

# Pattern matching on the template text.
import re
# Finds the Perl interpreter that evaluates the needrestart file.
import shutil
# Runs that interpreter.
import subprocess
# Holds the rendered needrestart file for one test.
import tempfile
# Test framework.
import unittest
# Path of the rendered file.
from pathlib import Path
# Stands in for the application object and records the SSH command of the cleanup step.
from unittest.mock import MagicMock

# Reads the Ansible task files.
import yaml

# Location of the CLI script (the collection root is two folders above it) and the CLI loaded as a module.
from tests.support import R1SETUP_PATH, r1setup


# Root of the Ansible collection (mnl_factory).
COLLECTION_ROOT = R1SETUP_PATH.parent.parent
# The systemd unit template of the node service.
SERVICE_TEMPLATE = COLLECTION_ROOT / "roles" / "setup" / "templates" / "edge_node.service.j2"
# Collection variables, among them the template version marker.
GROUP_VARS = COLLECTION_ROOT / "group_vars" / "mnl.yml"
# The needrestart file rendered beside the unit.
NEEDRESTART_TEMPLATE = COLLECTION_ROOT / "roles" / "setup" / "templates" / "needrestart-edge-node.conf.j2"
# The tasks that render the service definition of one instance.
RENDER_TASKS = COLLECTION_ROOT / "roles" / "setup" / "tasks" / "render_edge_node_definition.yml"
# The playbook that removes an instance.
DELETE_PLAYBOOK = COLLECTION_ROOT / "playbooks" / "delete_edge_node.yml"
# Where the file is installed, with the service name still as a template expression.
NEEDRESTART_DEST = "/etc/needrestart/conf.d/50-r1setup-{{ edge_node_service_name }}.conf"


def _directives(text: str) -> list[str]:
    """Return the lines of a unit template that systemd reads.

    Parameters
    ----------
    text : str
        Template source.

    Returns
    -------
    list[str]
        The lines without blank lines and without ``#`` comment lines, in file
        order.

    Examples
    --------
    >>> _directives("# note\\n[Unit]\\n\\nAfter=a.service\\n")
    ['[Unit]', 'After=a.service']
    """
    # Comments and blank lines carry no setting.
    return [line for line in text.splitlines() if line.strip() and not line.startswith("#")]


def _render_needrestart(service_name: str) -> str:
    """Render the needrestart template for one service name.

    The template has a single expression, the service name passed through
    Ansible's ``regex_escape`` filter, which is Python's ``re.escape``; it is
    filled in here the same way.

    Parameters
    ----------
    service_name : str
        Name of the systemd service, without ``.service``.

    Returns
    -------
    str
        The file as Ansible writes it to the host.

    Examples
    --------
    >>> _render_needrestart("edge_node").splitlines()[-1]
    "$nrconf{override_rc}{'^edge_node\\.service$'} = 0;"
    """
    # Every `{{ edge_node_service_name ... }}` expression of the template, with or without the filter.
    return re.sub(
        r"\{\{ edge_node_service_name( \| regex_escape)? \}\}",
        lambda match: re.escape(service_name) if match.group(1) else service_name,
        NEEDRESTART_TEMPLATE.read_text(),
    )


def _needrestart_verdicts(override: str, *units: str) -> dict:
    """Evaluate a needrestart file with Perl and report what happens to some units.

    The file is evaluated on top of a table that already defers ``docker``,
    like the stock configuration. A unit counts as deferred when at least one
    pattern of the table matches its name and no matching pattern asks for a
    restart, which is how needrestart reads the table.

    Parameters
    ----------
    override : str
        Text of the rendered file.
    *units : str
        Unit names to judge.

    Returns
    -------
    dict
        Unit name to ``"deferred"`` or ``"restart"``.

    Examples
    --------
    >>> _needrestart_verdicts("", "docker.service", "ssh.service")
    {'docker.service': 'deferred', 'ssh.service': 'restart'}
    """
    # The stock table, the evaluation of the file, then one verdict line per unit.
    program = (
        "our %nrconf = (override_rc => { qr(^docker) => 0 });"
        " my $file = shift @ARGV;"
        " do $file;"
        " die $@ if $@;"
        " for my $unit (@ARGV) {"
        "   my @values = map { $nrconf{override_rc}{$_} } grep { $unit =~ /$_/ } keys %{ $nrconf{override_rc} };"
        "   print $unit, '=', ((@values && !grep { $_ } @values) ? 'deferred' : 'restart'), qq(\\n);"
        " }"
    )
    # A throw-away folder for the file.
    with tempfile.TemporaryDirectory() as tmpdir:
        # The rendered file, where Perl can read it.
        path = Path(tmpdir) / "50-r1setup.conf"
        # Same text as on a host.
        path.write_text(override)
        # Evaluate; a file that is not valid Perl makes this fail.
        result = subprocess.run(["perl", "-e", program, str(path), *units], capture_output=True, text=True, check=True)
    # One "unit=verdict" line per unit.
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


class TestNeedrestartDeferral(unittest.TestCase):
    """The file that keeps needrestart from restarting the node unit after a host library upgrade."""

    def test_file_is_one_deferral_for_the_exact_service(self):
        """The rendered file holds one statement: the service's own unit name, anchored, mapped to 0."""
        # Only the lines needrestart evaluates.
        statements = [line for line in _render_needrestart("edge_node").splitlines() if line and not line.startswith("#")]
        # An element assignment (the stock table stays), a single-quoted pattern (no Perl interpolation of the name).
        self.assertEqual(statements, ["$nrconf{override_rc}{'^edge_node\\.service$'} = 0;"])

    @unittest.skipUnless(shutil.which("perl"), "perl evaluates the needrestart file, as needrestart itself does")
    def test_node_unit_is_deferred_and_nothing_else(self):
        """Evaluated like needrestart does, the file defers the instance's unit only and keeps the stock table."""
        # Default name, an expert-mode name, a preserved numbered name and a name with a dash.
        for service in ("edge_node", "edge_node_node_1_canary", "edge_node7", "edge-node.b"):
            # Report a failure under the service name.
            with self.subTest(service=service):
                # What needrestart would do with the unit, with look-alike units, a host daemon and docker.
                verdicts = _needrestart_verdicts(
                    _render_needrestart(service),
                    f"{service}.service", f"{service}2.service", f"x{service}.service", f"{service}.service.d", "containerd.service", "docker.service",
                )
                # Only the instance's own unit is added; docker stays deferred by the stock table.
                self.assertEqual(
                    verdicts,
                    {
                        f"{service}.service": "deferred",
                        f"{service}2.service": "restart",
                        f"x{service}.service": "restart",
                        f"{service}.service.d": "restart",
                        "containerd.service": "restart",
                        "docker.service": "deferred",
                    },
                )
        # A dot in a service name is matched literally, not as "any character".
        self.assertEqual(_needrestart_verdicts(_render_needrestart("edge-node.b"), "edge-nodeXb.service"), {"edge-nodeXb.service": "restart"})

    @unittest.skipUnless(shutil.which("perl"), "perl evaluates the needrestart file, as needrestart itself does")
    def test_without_the_file_the_node_unit_is_restarted(self):
        """With the stock table alone needrestart restarts the node unit: the restart seen at every library upgrade."""
        # No override at all.
        self.assertEqual(_needrestart_verdicts("", "edge_node.service"), {"edge_node.service": "restart"})

    def test_definition_renders_the_file_only_where_needrestart_is(self):
        """The file is rendered with the unit, once per service, compiled first, and only on a host with needrestart."""
        # The tasks of the service definition, by name.
        tasks = {task["name"]: task for task in yaml.safe_load(RENDER_TASKS.read_text())}
        # The probe for needrestart's snippet folder.
        self.assertEqual(tasks["Check for needrestart"]["ansible.builtin.stat"], {"path": "/etc/needrestart/conf.d"})
        # The task that writes the file.
        write = tasks["Defer needrestart restarts of {{ edge_node_service_name }}"]
        # Skipped on a host that has no needrestart.
        self.assertEqual(write["when"], "r1setup_needrestart_conf_dir.stat.exists")
        # The probe result it reads is the one registered above.
        self.assertEqual(tasks["Check for needrestart"]["register"], "r1setup_needrestart_conf_dir")
        # One file per service name, so instances on one machine do not overwrite each other.
        self.assertEqual(write["ansible.builtin.template"]["dest"], NEEDRESTART_DEST)
        # Rendered from the template of this collection.
        self.assertTrue(write["ansible.builtin.template"]["src"].endswith("/roles/setup/templates/needrestart-edge-node.conf.j2"))
        # Compiled before it replaces anything: needrestart stops on a file that is not valid Perl.
        self.assertEqual(write["ansible.builtin.template"]["validate"], "perl -c %s")

    def test_deleting_an_instance_removes_its_file(self):
        """Delete removes the same per-service file the definition installs."""
        # The tasks of the delete play, by name.
        tasks = {task["name"]: task for task in yaml.safe_load(DELETE_PLAYBOOK.read_text())[0]["tasks"]}
        # Same path as the install, state absent.
        self.assertEqual(tasks["Remove the needrestart deferral of the service"]["ansible.builtin.file"], {"path": NEEDRESTART_DEST, "state": "absent"})


class TestServiceTemplateStopLimit(unittest.TestCase):
    """The time the node gets to stop: 120 s from Docker, 150 s from systemd."""

    @classmethod
    def setUpClass(cls):
        """Read the template once for all tests of the class.

        Returns
        -------
        None
        """
        # The template as shipped in the collection.
        cls.template = SERVICE_TEMPLATE.read_text()
        # Only the lines systemd reads.
        cls.directives = _directives(cls.template)

    def test_every_docker_stop_waits_120_seconds(self):
        """Both stop commands of the unit give the node 120 s; the old 20 s cut every observed orderly close."""
        # The grace of each `docker stop` the unit runs, at start and at stop.
        graces = re.findall(r"^Exec(StartPre|Stop)=-?/usr/bin/docker stop -t (\d+) \{\{ mnl_docker_container_name \}\}$", self.template, re.M)
        # One at start (a leftover container) and one at stop, both 120 s.
        self.assertEqual(graces, [("StartPre", "120"), ("Stop", "120")])
        # No other grace is left among the lines systemd reads.
        self.assertEqual([line for line in self.directives if "docker stop" in line and "-t 120 " not in line], [])

    def test_unit_waits_30_seconds_longer_than_docker(self):
        """TimeoutStopSec is 150: systemd must not end `docker stop` before its 120 s grace is over."""
        # The unit's own stop limit.
        limits = re.findall(r"^TimeoutStopSec=(\d+)$", self.template, re.M)
        # Exactly one, 150 s.
        self.assertEqual(limits, ["150"])
        # It belongs to the [Service] section, after the start limit that was already there.
        self.assertGreater(self.directives.index("TimeoutStopSec=150"), self.directives.index("[Service]"))
        # 30 s of margin over the grace of the stop command.
        self.assertGreaterEqual(int(limits[0]) - 120, 30)

    def test_container_is_created_with_the_same_stop_timeout(self):
        """`docker run` carries --stop-timeout 120, so a stop that bypasses the unit gets the same grace."""
        # Where the run command starts.
        start = self.directives.index("ExecStart=/bin/sh -c '/usr/bin/docker run \\")
        # The line that names the image ends the docker command.
        image = next(index for index, line in enumerate(self.directives) if line.strip() == "{{ mnl_docker_image_url }}; \\")
        # The option is one of the run command's own lines, before the image name.
        self.assertIn("    --stop-timeout 120 \\", self.directives[start + 1:image])
        # Exactly once among the lines systemd reads.
        self.assertEqual(sum("--stop-timeout" in line for line in self.directives), 1)
        # Every line of the command still continues onto the next one.
        self.assertEqual([line for line in self.directives[start:image + 1] if not line.endswith("\\")], [])

    def test_unit_is_ordered_after_the_container_runtime(self):
        """After= names containerd as well as docker, so systemd stops the node before the runtime in one transaction."""
        # The ordering line of the unit.
        after = [line for line in self.directives if line.startswith("After=")]
        # Docker as before, plus the container runtime.
        self.assertEqual(after, ["After=docker.service containerd.service"])
        # The hard dependency stays on docker only.
        self.assertIn("Requires=docker.service", self.directives)

    def test_template_version_marks_the_new_stop_limit(self):
        """The template version is v3, so deployed v1 and v2 units are reported as outdated and offered the update."""
        # The marker the CLI compares against each node's deployed unit.
        version = re.search(r'^mnl_service_version:\s*"([^"]+)"', GROUP_VARS.read_text(), re.M)
        # v2 already exists with the 20 s grace; the new limit needs a new version.
        self.assertEqual(version.group(1), "v3")


def _cleanup_wait(connection_timeout: int) -> int:
    """Return how long the CLI waits for the SSH step that stops and removes a service.

    Runs ``MigrationPlanner._cleanup_runtime_artifacts`` with a recording
    stand-in for the SSH call, so no host is contacted.

    Parameters
    ----------
    connection_timeout : int
        The operator's ``connection_timeout`` setting, in seconds.

    Returns
    -------
    int
        The ``timeout`` the step hands to the SSH call, in seconds.

    Examples
    --------
    >>> _cleanup_wait(100)
    300
    """
    # A planner whose application object only carries the setting.
    planner = r1setup.MigrationPlanner(MagicMock(connection_timeout=connection_timeout))
    # Record the SSH call instead of making it.
    planner._run_machine_command = MagicMock(return_value={"status": "success"})
    # The step as a migration rollback runs it against the target: stop the service, then remove its files.
    planner._cleanup_runtime_artifacts({"ansible_host": "192.0.2.10", "ansible_user": "root"}, {"service_name": "edge_node"}, remove_volume=True)
    # The command must start with the synchronous stop this wait is for.
    assert "systemctl stop edge_node" in planner._run_machine_command.call_args.args[1]
    # The wait of that one SSH call.
    return planner._run_machine_command.call_args.kwargs["timeout"]


class TestCleanupWaitsForTheServiceStop(unittest.TestCase):
    """The CLI step that stops a service over SSH waits longer than the unit lets a stop take."""

    def test_default_setting_outlasts_the_unit_stop_limit(self):
        """With the default connection timeout (30 s) the cleanup waits 180 s, 30 s more than the unit's TimeoutStopSec."""
        # The default of the setting gives 3 x 30 = 90 s, which a 120 s close does not fit in.
        self.assertEqual(_cleanup_wait(30), 180)
        # The stop limit of the unit the CLI deploys.
        limit = int(re.search(r"^TimeoutStopSec=(\d+)$", SERVICE_TEMPLATE.read_text(), re.M).group(1))
        # The SSH step must not end before systemd has ended the stop; 30 s are left for the removals after it.
        self.assertGreaterEqual(_cleanup_wait(30) - limit, 30)

    def test_larger_setting_is_not_capped(self):
        """The 180 s are a floor: a connection timeout above 60 s keeps its three-fold wait."""
        # 3 x 100 s, as before the floor.
        self.assertEqual(_cleanup_wait(100), 300)
        # The smallest allowed setting still gets the floor.
        self.assertEqual(_cleanup_wait(30), 180)


if __name__ == "__main__":
    # Lets the file run on its own.
    unittest.main()
