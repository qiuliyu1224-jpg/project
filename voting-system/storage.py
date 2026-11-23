"""Consistent SQLite backups and validated replacement, used by the local operator."""
from contextlib import closing
from datetime import datetime
from pathlib import Path
import os
import sqlite3


SCHEMA_VERSION = 47


def validate(connection):
    if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
        raise ValueError('SQLite integrity check failed.')
    if connection.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('Backup contains broken record links.')
    if connection.execute('PRAGMA user_version').fetchone()[0] > SCHEMA_VERSION:
        raise ValueError('This backup requires a newer VoteLab version.')
    required = {'users': {'id', 'phone', 'salt', 'password_hash'},
                'elections': {'id', 'creator_id', 'title', 'status'},
                'rounds': {'id', 'election_id', 'number'},
                'ballots': {'id', 'round_id', 'user_id'},
                'choices': {'ballot_id', 'candidate_id', 'score'},
                'sessions': {'token', 'user_id', 'expires'}}
    for table, columns in required.items():
        actual = {r[1] for r in connection.execute(f'PRAGMA table_info({table})')}
        if not columns <= actual:
            raise ValueError('Not a compatible VoteLab database: ' + table)


def copy_database(source, target, check_app=False):
    with closing(sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            if check_app:
                validate(dst)
            elif dst.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise ValueError('SQLite integrity check failed.')


def backup_database(database):
    database = Path(database)
    if not database.exists():
        return None
    backups = database.parent / 'backups'
    backups.mkdir(exist_ok=True)
    backup = backups / ('voting-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
    temporary = backup.with_suffix('.partial')
    try:
        copy_database(database, temporary)
        temporary.replace(backup)
        return backup
    finally:
        temporary.unlink(missing_ok=True)


def restore_database(database, backup, prepare=None):
    """Caller must hold the request/maintenance gate and close all DB connections."""
    database, backup = Path(database), Path(backup)
    if database.resolve() == backup.resolve():
        raise ValueError('Select a backup, not the active database.')
    if any(Path(str(database) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('Database sidecar files are present. Quit VoteLab and check the data folder first.')
    temporary = database.with_name('restore-' + os.urandom(8).hex() + '.partial')
    try:
        # Validate a complete independent copy before touching any active data.
        copy_database(backup, temporary, check_app=True)
        if prepare:
            prepare(temporary)
        with closing(sqlite3.connect(temporary)) as staged:
            validate(staged)
            with staged:
                staged.execute('DELETE FROM sessions')
                if staged.execute("SELECT 1 FROM sqlite_master WHERE name='verification_codes' AND type='table'").fetchone():
                    staged.execute('DELETE FROM verification_codes')
        recovery = backup_database(database)
        os.replace(temporary, database)
        return recovery
    finally:
        temporary.unlink(missing_ok=True)
