"""A slow connection must not block other demo users."""
import socket
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from demo_server import create_server


class DemoServerTests(unittest.TestCase):
    def test_local_startup_does_not_require_reverse_dns(self):
        def application(env, start):
            start('200 OK', [('Content-Type', 'text/plain')])
            return [env['SERVER_NAME'].encode('ascii')]

        with patch('socket.getfqdn', side_effect=RuntimeError('Resolver unavailable')):
            with create_server('127.0.0.1', 0, application) as server:
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    with urlopen('http://127.0.0.1:%s/' % server.server_port, timeout=2) as response:
                        self.assertEqual(response.read(), b'127.0.0.1')
                finally:
                    server.shutdown()
                    worker.join(timeout=3)

    def test_incomplete_request_does_not_block_other_users(self):
        def application(env, start):
            start('200 OK', [('Content-Type', 'text/plain')])
            return [b'OK']

        with create_server('127.0.0.1', 0, application) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with socket.create_connection(server.server_address, timeout=2) as slow:
                    slow.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n')
                    with urlopen('http://127.0.0.1:%s/' % server.server_port,
                                 timeout=2) as response:
                        self.assertEqual(response.read(), b'OK')
            finally:
                server.shutdown()
                worker.join(timeout=3)
