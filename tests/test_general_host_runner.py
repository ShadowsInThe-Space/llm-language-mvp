"""Restart evidence requires the old host port to close, even if npm has exited."""

import unittest
from unittest.mock import Mock, patch

from scripts.run_general_host_acceptance import stop


class HostShutdownTests(unittest.TestCase):
    def test_missing_launcher_group_does_not_hide_a_still_listening_worker(self):
        connection = Mock()
        connection.connect_ex.return_value = 0
        with (
            patch("scripts.run_general_host_acceptance.os.killpg",
                  side_effect=ProcessLookupError),
            patch("scripts.run_general_host_acceptance.socket.socket") as sockets,
            patch("scripts.run_general_host_acceptance.time.monotonic", side_effect=[0, 0, 11]),
            patch("scripts.run_general_host_acceptance.time.sleep"),
        ):
            sockets.return_value.__enter__.return_value = connection
            with self.assertRaisesRegex(RuntimeError, "restart evidence is invalid"):
                stop(Mock(pid=123))

    def test_exited_group_with_closed_port_is_a_completed_shutdown(self):
        connection = Mock()
        connection.connect_ex.return_value = 111
        with (
            patch("scripts.run_general_host_acceptance.os.killpg",
                  side_effect=ProcessLookupError),
            patch("scripts.run_general_host_acceptance.socket.socket") as sockets,
        ):
            sockets.return_value.__enter__.return_value = connection
            stop(Mock(pid=123))


if __name__ == "__main__":
    unittest.main()
