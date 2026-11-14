#!/usr/bin/env python3
"""Tests of the edge_node service definition: the unit template and the files rendered with it."""

# Pattern matching on the template text.
import re
# Test framework.
import unittest

# Location of the CLI script; the collection root is two folders above it.
from tests.support import R1SETUP_PATH


# Root of the Ansible collection (mnl_factory).
COLLECTION_ROOT = R1SETUP_PATH.parent.parent
# The systemd unit template of the node service.
SERVICE_TEMPLATE = COLLECTION_ROOT / "roles" / "setup" / "templates" / "edge_node.service.j2"
# Collection variables, among them the template version marker.
GROUP_VARS = COLLECTION_ROOT / "group_vars" / "mnl.yml"


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


if __name__ == "__main__":
    # Lets the file run on its own.
    unittest.main()
