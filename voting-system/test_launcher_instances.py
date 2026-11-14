"""Process-level launch recovery checks, using only isolated temporary data."""
from contextlib import closing, contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


SOURCE = Path(__file__).resolve().parent
READY = re.compile(r'VoteLab is ready at (http://127\.0\.0\.1:(\d+)/)')
LOCAL_HTTP = build_opener(ProxyHandler({}))


@contextmanager
def foreign_server(legacy=False):
    """Even a page branded VoteLab must not count as an authenticated instance."""
    class ForeignHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/_votelab/instance':
                body = (b'not found' if legacy else
                        b'{"application":"Other program","token":"not-the-instance-token"}')
                self.send_response(404 if legacy else 200)
            else:
                body = b'<html><title>VoteLab</title>Existing local program</html>'
                self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    # This synthetic server tests occupied-port handling, never DNS behavior.
    with patch('socket.getfqdn', return_value='127.0.0.1'):
        server = HTTPServer(('127.0.0.1', 0), ForeignHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class LauncherInstanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='votelab-instance-test-')
        self.work = Path(self.temporary.name)
        self.data = self.work / 'data'
        self.data.mkdir()
        self.processes = []
        self.streams = []

    def tearDown(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for stream in self.streams:
            stream.close()
        self.temporary.cleanup()

    def environment(self):
        return dict(os.environ, VOTELAB_DATA_DIR=str(self.data), PYTHONUNBUFFERED='1')

    def command(self, port):
        return [sys.executable, str(SOURCE / 'run_votelab.py'),
                '--no-browser', '--port', str(port)]

    def start(self, port=0):
        console = self.work / f'process-{len(self.processes)}.txt'
        stream = console.open('w', encoding='utf-8')
        self.streams.append(stream)
        process = subprocess.Popen(self.command(port), cwd=self.work,
                                   env=self.environment(), stdout=stream,
                                   stderr=subprocess.STDOUT)
        self.processes.append(process)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            output = console.read_text(encoding='utf-8', errors='replace')
            match = READY.search(output)
            if match:
                # A printed ready URL may precede serve_forever by a few instructions.
                with LOCAL_HTTP.open(match.group(1), timeout=5) as response:
                    self.assertEqual(response.status, 200)
                return process, match.group(1), int(match.group(2))
            if process.poll() is not None:
                self.fail(f'Primary launcher exited {process.returncode}: {output}')
            time.sleep(.05)
        self.fail('Primary launcher did not become ready: ' +
                  console.read_text(encoding='utf-8', errors='replace'))

    def launch_again(self, port):
        return subprocess.run(self.command(port), cwd=self.work,
                              env=self.environment(), capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=12)

    def snapshot(self):
        database = self.data / 'voting.sqlite3'
        backups = self.data / 'backups'
        return (hashlib.sha256(database.read_bytes()).hexdigest(),
                sorted(item.name for item in backups.iterdir()) if backups.exists() else [])

    def test_second_launch_reuses_exact_instance_without_database_or_backup_changes(self):
        process, address, port = self.start()
        before = self.snapshot()
        result = self.launch_again(port)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('VoteLab is already running at ' + address, result.stdout)
        self.assertNotIn('VoteLab is ready at ', result.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(process.poll())

    def test_other_requested_port_still_reuses_same_data_directory_instance(self):
        _, address, port = self.start()
        before = self.snapshot()
        different_port = port + 1 if port < 65535 else port - 1
        result = self.launch_again(different_port)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('VoteLab is already running at ' + address, result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_simultaneous_launches_have_one_owner_and_one_existing_instance(self):
        consoles = []
        for number in range(2):
            path = self.work / f'simultaneous-{number}.txt'
            stream = path.open('w', encoding='utf-8')
            self.streams.append(stream)
            process = subprocess.Popen(self.command(0), cwd=self.work,
                                       env=self.environment(), stdout=stream,
                                       stderr=subprocess.STDOUT)
            self.processes.append(process)
            consoles.append(path)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            outputs = [path.read_text(encoding='utf-8', errors='replace') for path in consoles]
            ready = [READY.search(output) for output in outputs]
            existing = [re.search(r'VoteLab is already running at (http://127\.0\.0\.1:\d+/)', output)
                        for output in outputs]
            if sum(bool(item) for item in ready) == sum(bool(item) for item in existing) == 1:
                owner = next(index for index, item in enumerate(ready) if item)
                secondary = 1 - owner
                self.assertEqual(self.processes[secondary].wait(timeout=5), 0, '\n'.join(outputs))
                self.assertIsNone(self.processes[owner].poll())
                self.assertEqual(ready[owner].group(1), existing[secondary].group(1))
                self.assertFalse((self.data / 'backups').exists())
                return
            for process in self.processes:
                if process.poll() not in (None, 0):
                    self.fail('Concurrent launcher failed: ' + '\n'.join(outputs))
            time.sleep(.05)
        self.fail('Concurrent launchers did not reach one shared instance: ' + '\n'.join(outputs))

    def test_restart_releases_os_lock_and_ignores_stale_instance_record(self):
        process, _, port = self.start()
        with closing(sqlite3.connect(self.data / 'voting.sqlite3')) as connection:
            with connection:
                connection.execute('CREATE TABLE launcher_persistence_test (message TEXT)')
                connection.execute('INSERT INTO launcher_persistence_test VALUES (?)',
                                   ('Keep existing user records on restart',))
        process.terminate()
        process.wait(timeout=10)
        state = self.data / 'running-instance.json'
        stale_token = '0' * 48
        state.write_text(json.dumps({'application': 'VoteLab', 'port': port,
                                     'token': stale_token}), encoding='utf-8')
        _, _, new_port = self.start()
        current = json.loads(state.read_text(encoding='utf-8'))
        self.assertEqual(current['port'], new_port)
        self.assertNotEqual(current['token'], stale_token)
        with closing(sqlite3.connect(self.data / 'voting.sqlite3')) as connection:
            self.assertEqual(connection.execute('SELECT message FROM launcher_persistence_test').fetchone(),
                             ('Keep existing user records on restart',))
        self.assertTrue(list((self.data / 'backups').glob('voting-*.sqlite3')))

    def assert_foreign_occupant_refused(self, legacy):
        sentinel = b'Existing user database - leave unchanged when local port is occupied'
        database = self.data / 'voting.sqlite3'
        database.write_bytes(sentinel)
        with foreign_server(legacy=legacy) as port:
            result = self.launch_again(port)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn('VoteLab is already running at ', result.stdout)
            self.assertNotIn('VoteLab is ready at ', result.stdout)
            log_path = self.data / 'launcher.log'
            combined = result.stdout + result.stderr
            if log_path.exists():
                combined += log_path.read_text(encoding='utf-8', errors='replace')
            self.assertRegex(combined.lower(), r'address already in use|port.{0,100}(?:occupied|in use|busy)')
            self.assertEqual(database.read_bytes(), sentinel)
            self.assertFalse((self.data / 'backups').exists())

    def test_unrelated_http_server_is_not_reused_and_cannot_trigger_database_writes(self):
        self.assert_foreign_occupant_refused(legacy=False)

    def test_legacy_branded_server_without_identity_is_not_silently_reused(self):
        self.assert_foreign_occupant_refused(legacy=True)

    def test_ready_endpoint_requires_the_matching_instance_secret(self):
        _, address, _ = self.start()
        token = json.loads((self.data / 'running-instance.json').read_text(encoding='utf-8'))['token']
        endpoint = address + '_votelab/instance'
        for supplied in (None, 'f' * 48):
            headers = {} if supplied is None else {'X-VoteLab-Instance': supplied}
            with self.assertRaises(HTTPError) as caught:
                LOCAL_HTTP.open(Request(endpoint, headers=headers), timeout=3)
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
        with LOCAL_HTTP.open(Request(endpoint, headers={'X-VoteLab-Instance': token}), timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {'application': 'VoteLab', 'token': token})

    def test_backup_only_refuses_running_instance_without_opening_browser_or_claiming_success(self):
        self.start()
        before = self.snapshot()
        browser_marker = self.work / 'browser-was-opened.txt'
        script = '''
from pathlib import Path
import runpy, sys, webbrowser
sys.path.insert(0, sys.argv[1])
marker = Path(sys.argv[2])
def record_browser(address, *args, **kwargs):
    marker.write_text(address)
    return True
webbrowser.open = record_browser
sys.argv = ['run_votelab.py', '--backup-only']
runpy.run_path(str(Path(sys.path[0]) / 'run_votelab.py'), run_name='__main__')
'''
        result = subprocess.run([sys.executable, '-c', script, str(SOURCE), str(browser_marker)],
                                cwd=self.work, env=self.environment(), capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=12)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('backup', (result.stdout + result.stderr).lower())
        self.assertFalse(browser_marker.exists())
        self.assertEqual(self.snapshot(), before)

    def test_instance_probe_does_not_follow_redirects_or_forward_its_secret(self):
        from run_votelab import find_running_instance
        token = 'a' * 48
        redirected_requests = []

        class RedirectTarget(BaseHTTPRequestHandler):
            def do_GET(self):
                redirected_requests.append(self.headers.get('X-VoteLab-Instance'))
                body = json.dumps({'application': 'VoteLab', 'token': token}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        with patch('socket.getfqdn', return_value='127.0.0.1'):
            target = HTTPServer(('127.0.0.1', 0), RedirectTarget)

        class RedirectSource(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location', f'http://127.0.0.1:{target.server_port}/capture')
                self.send_header('Content-Length', '0')
                self.end_headers()

            def log_message(self, *args):
                pass

        with patch('socket.getfqdn', return_value='127.0.0.1'):
            source = HTTPServer(('127.0.0.1', 0), RedirectSource)
        threads = [threading.Thread(target=server.serve_forever, daemon=True)
                   for server in (source, target)]
        for thread in threads:
            thread.start()
        try:
            (self.data / 'running-instance.json').write_text(
                json.dumps({'application': 'VoteLab', 'port': source.server_port, 'token': token}),
                encoding='utf-8')
            self.assertIsNone(find_running_instance(self.data, timeout=.1))
            self.assertEqual(redirected_requests, [])
        finally:
            for server in (source, target):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
