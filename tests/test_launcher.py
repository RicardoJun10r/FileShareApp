import unittest
from types import SimpleNamespace
from unittest.mock import patch

from launcher import bind_server, network_ip, open_when_ready


class LauncherTest(unittest.TestCase):
    def test_browser_opens_only_when_server_ready(self):
        server = SimpleNamespace(started=True, should_exit=False)
        with patch("launcher.webbrowser.open", return_value=True) as browser:
            open_when_ready(server, "http://192.168.1.2:8000/", True)
            browser.assert_called_once_with("http://192.168.1.2:8000/")
        with patch("launcher.webbrowser.open") as browser:
            open_when_ready(server, "http://127.0.0.1:8000/", False)
            browser.assert_not_called()

    def test_fixed_port_collision_is_reported(self):
        with bind_server("127.0.0.1", 0) as sock:
            sock.listen()
            with self.assertRaises(OSError):
                bind_server("127.0.0.1", sock.getsockname()[1])

    def test_no_network_falls_back_to_localhost(self):
        with patch("launcher.socket.socket", side_effect=OSError):
            self.assertEqual(network_ip(), "127.0.0.1")
