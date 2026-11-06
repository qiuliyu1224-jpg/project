"""Start the packaged, local-only VoteLab classroom app."""

import argparse
import logging
import os
from pathlib import Path
import sqlite3
import sys
import threading
from contextlib import closing
from datetime import datetime
import webbrowser

import app
from maintenance import start_maintenance


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
    data_dir.mkdir(parents=True, exist_ok=True)
    app.DB = data_dir / 'voting.sqlite3'
    if sys.stderr is None:
        sys.stderr = (data_dir / 'launcher.log').open('a', encoding='utf-8', buffering=1)
    if sys.stdout is None:
        sys.stdout = sys.stderr
    print(f'VoteLab data directory: {data_dir}', flush=True)
    if args.backup_only:
        snapshot = backup_database(app.DB)
        print(f'Backup: {snapshot}' if snapshot else 'No VoteLab database has been created yet.')
        return

    # Bind first so a second launch cannot run database migrations on the same port.
    with app.create_server('127.0.0.1', args.port, app.app) as server:
        snapshot = backup_database(app.DB)
        if snapshot:
            print(f'Startup backup: {snapshot}', flush=True)
        app.init_db()
        stop, worker = start_maintenance()
        address = f'http://127.0.0.1:{server.server_port}/'
        print(f'VoteLab is ready at {address}', flush=True)
        if not args.no_browser:
            threading.Thread(target=webbrowser.open, args=(address,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            worker.join(timeout=6)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.exception('VoteLab could not start. See the operating instructions for help.')
        raise SystemExit(1)
