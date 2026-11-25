"""Startup failures remain diagnosable even when Finder discards stderr."""
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parent


class LauncherLoggingTests(unittest.TestCase):
    def test_valid_identity_from_an_older_version_is_not_reused(self):
        from run_votelab import APP_VERSION, find_running_instance
        import app
        self.assertEqual(APP_VERSION, app.VERSION)
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            token = 'a' * 48
            (data / 'running-instance.json').write_text(json.dumps(
                {'application': 'VoteLab', 'port': 8765, 'token': token}))
            for version, expected in ((None, None), ('0.4.5', None),
                                      (APP_VERSION, 'http://127.0.0.1:8765/')):
                result = {'application': 'VoteLab', 'token': token}
                if version is not None:
                    result['version'] = version
                with patch('run_votelab.build_opener') as factory:
                    response = factory.return_value.open.return_value.__enter__.return_value
                    response.status = 200
                    response.read.return_value = json.dumps(result).encode()
                    self.assertEqual(find_running_instance(data, timeout=0), expected)

    def test_desktop_launch_preserves_deliberate_browser_language(self):
        from run_votelab import open_browser
        with patch('run_votelab.webbrowser.open', return_value=True) as browser:
            open_browser('http://127.0.0.1:8765/')
        browser.assert_called_once_with('http://127.0.0.1:8765/')

    def run_failure(self, root, *, import_failure=False):
        data = root / 'data'
        data.mkdir()
        database = data / 'voting.sqlite3'
        sentinel = b'Existing user database must remain untouched by a failed import'
        database.write_bytes(sentinel)
        script = '''
import builtins, runpy, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
if sys.argv[2] == 'import':
    def fail_import(name, *args, **kwargs):
        if name == 'app':
            raise ImportError('Synthetic packaged app import failure')
        return original_import(name, *args, **kwargs)
    builtins.__import__ = fail_import
else:
    import app
    def fail_bind(*args, **kwargs):
        raise OSError('Synthetic occupied local port')
    app.create_server = fail_bind
sys.argv = ['run_votelab.py', '--no-browser']
runpy.run_path(str(Path(sys.path[0]) / 'run_votelab.py'), run_name='__main__')
'''
        env = dict(os.environ, VOTELAB_DATA_DIR=str(data))
        result = subprocess.run([sys.executable, '-c', script, str(SOURCE),
                                 'import' if import_failure else 'bind'],
                                env=env, cwd=root, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(database.read_bytes(), sentinel)
        self.assertFalse((data / 'backups').exists())
        return (data / 'launcher.log').read_text(encoding='utf-8')

    def test_import_failure_is_logged_without_console(self):
        with tempfile.TemporaryDirectory() as folder:
            log = self.run_failure(Path(folder), import_failure=True)
        self.assertIn('Synthetic packaged app import failure', log)
        self.assertIn('Traceback', log)

    def test_port_failure_is_logged_without_console(self):
        with tempfile.TemporaryDirectory() as folder:
            log = self.run_failure(Path(folder))
        self.assertIn('Synthetic occupied local port', log)
        self.assertIn('Traceback', log)


if __name__ == '__main__':
    unittest.main()
