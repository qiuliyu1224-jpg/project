"""Start the packaged, local-only VoteLab classroom app."""

import argparse
import errno
import hmac
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import closing
from datetime import datetime
import webbrowser
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request


STARTUP_LOG = logging.getLogger('votelab.launcher')
INSTANCE_PATH = '/_votelab/instance'


class StartupProblem(RuntimeError):
    """An actionable startup error that is also shown for a packaged Mac app."""


class NoProbeRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class DataDirectoryLock:
    """One launcher owns a data directory; the OS releases the lock after a crash."""
    def __init__(self, data_dir):
        self.path = data_dir / 'launcher.lock'
        self.handle = None

    def acquire(self):
        self.handle = self.path.open('a+b')
        self.handle.seek(0, os.SEEK_END)
        if self.handle.tell() == 0:
            self.handle.write(b'0')
            self.handle.flush()
        self.handle.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.handle.close()
            self.handle = None
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                return False
            raise
        return True

    def close(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None
        # Keep this file: unlinking a lock file would allow different inode locks.


def launcher_status_app(application, token):
    def dispatch(env, start):
        if env.get('PATH_INFO') == INSTANCE_PATH:
            supplied = env.get('HTTP_X_VOTELAB_INSTANCE', '')
            valid = (env.get('REQUEST_METHOD') == 'GET' and isinstance(supplied, str)
                     and hmac.compare_digest(supplied.encode(), token.encode()))
            start('200 OK' if valid else '403 Forbidden',
                  [('Content-Type', 'application/json'), ('Cache-Control', 'no-store')])
            return [json.dumps({'application': 'VoteLab', 'token': token}
                               if valid else {'error': 'Forbidden'}).encode()]
        return application(env, start)
    return dispatch


def find_running_instance(data_dir, timeout=4):
    """Never mistake a different local app (or a stale state file) for VoteLab."""
    deadline = time.monotonic() + timeout
    opener = build_opener(ProxyHandler({}), NoProbeRedirect())
    while True:
        try:
            state = json.loads((data_dir / 'running-instance.json').read_text(encoding='utf-8'))
            port, token = state['port'], state['token']
            valid = (state.get('application') == 'VoteLab' and type(port) is int
                     and 1 <= port <= 65535 and isinstance(token, str)
                     and len(token) == 48 and all(c in '0123456789abcdef' for c in token))
            if valid:
                address = f'http://127.0.0.1:{port}/'
                request = Request(address.rstrip('/') + INSTANCE_PATH,
                                  headers={'X-VoteLab-Instance': token})
                with opener.open(request, timeout=.5) as response:
                    result = json.loads(response.read(1024))
                    if response.status == 200 and result == {'application': 'VoteLab', 'token': token}:
                        return address
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if time.monotonic() >= deadline:
            return None
        time.sleep(.1)


def write_running_instance(data_dir, port, token):
    state = {'application': 'VoteLab', 'port': port, 'token': token}
    temporary = data_dir / f'running-instance-{os.getpid()}-{token}.tmp'
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                       'w', encoding='utf-8') as stream:
            json.dump(state, stream)
        temporary.replace(data_dir / 'running-instance.json')
    finally:
        temporary.unlink(missing_ok=True)


def open_browser(address):
    try:
        if not webbrowser.open(address):
            STARTUP_LOG.warning('Open this address manually: %s', address)
    except Exception:
        STARTUP_LOG.exception('Browser launch failed; open %s manually.', address)


def report_startup_failure(error):
    STARTUP_LOG.exception('VoteLab could not start.')
    logging.exception('VoteLab could not start. See the operating instructions for help.')
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        detail = str(error) if isinstance(error, StartupProblem) else 'Please check the startup log for the error details.'
        message = detail + '\n\nStartup log: ' + str(user_data_directory() / 'launcher.log')
        # Pass text as an argument, never interpolate it into AppleScript source.
        script = 'on run argv\ndisplay alert "VoteLab could not start" message (item 1 of argv) as warning buttons {"OK"}\nend run'
        try:
            subprocess.run(['/usr/bin/osascript', '-e', script, message], timeout=15,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def configure_startup_logging(data_dir):
    """Finder may provide a discarded stderr instead of None; always keep a log."""
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / 'launcher.log'
    for handler in list(STARTUP_LOG.handlers):
        STARTUP_LOG.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=2,
                                  encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    STARTUP_LOG.addHandler(handler)
    STARTUP_LOG.setLevel(logging.INFO)
    STARTUP_LOG.propagate = False
    if sys.stderr is None:
        sys.stderr = log_path.open('a', encoding='utf-8', buffering=1)
    if sys.stdout is None:
        sys.stdout = sys.stderr
    STARTUP_LOG.info('VoteLab startup: platform=%s frozen=%s', sys.platform,
                     bool(getattr(sys, 'frozen', False)))
    return log_path


def user_data_directory():
    override = os.environ.get('VOTELAB_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == 'win32':
        return Path(os.environ['LOCALAPPDATA']) / 'VoteLab'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'VoteLab'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'VoteLab'


def backup_database(database):
    if not database.exists():
        return None
    backups = database.parent / 'backups'
    backups.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = backups / f'voting-{timestamp}.sqlite3'
    temporary = backup.with_suffix('.partial')
    try:
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(temporary)) as target:
                source.backup(target)
                if target.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise sqlite3.DatabaseError('The backup did not pass SQLite integrity checking.')
        temporary.replace(backup)
        return backup
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--backup-only', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')

    data_dir = user_data_directory()
    configure_startup_logging(data_dir)
    ownership = DataDirectoryLock(data_dir)
    if not ownership.acquire():
        if args.backup_only:
            raise StartupProblem('Backup was not created because VoteLab is running. '
                                 'Quit VoteLab before using --backup-only.')
        address = find_running_instance(data_dir)
        if not address:
            raise StartupProblem('VoteLab is already starting or running for this data folder. '
                                 'Wait a moment and open it again. If it remains unresponsive, '
                                 'quit the known VoteLab process in Activity Monitor (Mac) '
                                 'or Task Manager (Windows) before retrying.')
        message = f'VoteLab is already running at {address}'
        STARTUP_LOG.info(message)
        print(message, flush=True)
        if not args.no_browser:
            open_browser(address)
        return
    try:
        (data_dir / 'running-instance.json').unlink(missing_ok=True)
        # Application imports can fail before the web server exists. Log them too.
        import app
        from maintenance import start_maintenance
        app.DB = data_dir / 'voting.sqlite3'
        print(f'VoteLab data directory: {data_dir}', flush=True)
        if args.backup_only:
            snapshot = backup_database(app.DB)
            print(f'Backup: {snapshot}' if snapshot else 'No VoteLab database has been created yet.')
            return

        token = secrets.token_hex(24)
        # A legacy app has no identity endpoint or lock. Do not migrate its DB or
        # silently start another server when its port may already be in use.
        try:
            server = app.create_server('127.0.0.1', args.port, launcher_status_app(app.app, token))
        except OSError as error:
            if error.errno == errno.EADDRINUSE or getattr(error, 'winerror', None) in (10048, 10013):
                raise StartupProblem(f'Port {args.port} is unavailable or already in use. '
                                     f'Try http://127.0.0.1:{args.port}/ in your browser. '
                                     'To update an earlier VoteLab, quit its process first. '
                                     'Do not stop an unrelated program.') from error
            raise
        with server:
            snapshot = backup_database(app.DB)
            if snapshot:
                print(f'Startup backup: {snapshot}', flush=True)
            app.init_db()
            stop, worker = start_maintenance()
            address = f'http://127.0.0.1:{server.server_port}/'
            write_running_instance(data_dir, server.server_port, token)
            STARTUP_LOG.info('VoteLab is ready at %s', address)
            print(f'VoteLab is ready at {address}', flush=True)
            if not args.no_browser:
                threading.Thread(target=open_browser, args=(address,), daemon=True).start()
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                stop.set()
                worker.join(timeout=6)
    finally:
        try:
            (data_dir / 'running-instance.json').unlink(missing_ok=True)
        finally:
            ownership.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        report_startup_failure(error)
        raise SystemExit(1)
