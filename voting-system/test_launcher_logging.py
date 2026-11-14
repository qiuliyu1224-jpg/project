"""Startup failures remain diagnosable even when Finder discards stderr."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parent


class LauncherLoggingTests(unittest.TestCase):
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
