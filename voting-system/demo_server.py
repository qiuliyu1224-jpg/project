"""Concurrent server for small classroom demos, not production hosting."""
import socket
import sys
from socketserver import TCPServer, ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


class DemoServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    request_queue_size = 64
    allow_reuse_address = sys.platform != 'win32'

    def server_bind(self):
        if sys.platform == 'win32':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # This is a local demo server. Reverse DNS is unnecessary and can stall
        # startup when a Mac resolver or its current network is unresponsive.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]
        self.setup_environ()


class DemoHandler(WSGIRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def get_environ(self):
        env = super().get_environ()
        env['wsgi.multithread'] = True
        return env


def create_server(host, port, application):
    return make_server(host, port, application,
                       server_class=DemoServer, handler_class=DemoHandler)
