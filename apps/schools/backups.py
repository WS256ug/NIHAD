"""Checksummed offline backups. Restore only into an empty database and media root."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def postgres_command(program, extra):
    executable = Path(settings.POSTGRES_BIN_DIR) / (program + '.exe' if os.name == 'nt' else program) if settings.POSTGRES_BIN_DIR else shutil.which(program)
    if not executable or not Path(executable).is_file():
        raise CommandError(f'{program} is required. Configure POSTGRES_BIN_DIR or install PostgreSQL client tools.')
    database = connection.settings_dict
    environment = dict(os.environ)
    environment['PGPASSWORD'] = database.get('PASSWORD', '')
    environment['PGSSLMODE'] = database.get('OPTIONS', {}).get('sslmode', 'require')
    options = database.get('OPTIONS', {})
    if options.get('sslrootcert'):
        environment['PGSSLROOTCERT'] = options['sslrootcert']
    command = [str(executable), '--host=' + database.get('HOST', ''), '--port=' + str(database.get('PORT') or '5432'), '--username=' + database.get('USER', ''), '--dbname=' + database['NAME'], '--no-password', *extra]
    result = subprocess.run(command, env=environment, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise CommandError(f'{program} failed. Check database connectivity, client/server versions and target permissions. No existing target data is overwritten by this tool.')


def create_backup(destination):
    destination = Path(destination).resolve()
    protected = [settings.MEDIA_ROOT, settings.PRIVATE_MEDIA_ROOT, settings.STATIC_ROOT, settings.BASE_DIR / 'static']
    if any(destination.is_relative_to(Path(root).resolve()) for root in protected):
        raise CommandError('Backups must be outside media and static directories.')
    if destination.exists():
        raise CommandError('Choose a new backup directory; existing backups are never overwritten.')
    destination.mkdir(parents=True, mode=0o700)
    if connection.vendor == 'sqlite':
        database_file = destination / 'database.sqlite3'
        connection.ensure_connection()
        with sqlite3.connect(database_file) as target:
            connection.connection.backup(target)
    elif connection.vendor == 'postgresql':
        database_file = destination / 'database.dump'
        postgres_command('pg_dump', ['--format=custom', '--no-owner', '--no-privileges', '--file=' + str(database_file)])
    else:
        raise CommandError('Only SQLite and PostgreSQL backups are supported.')
    private_root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
    if private_root.exists():
        for source in private_root.rglob('*'):
            if source.is_symlink():
                raise CommandError('Private media contains a symbolic link. Remove the link before backing up.')
            if source.is_file():
                target = destination / 'private_media' / source.relative_to(private_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    files = {str(path.relative_to(destination)).replace('\\', '/'): {'sha256': digest(path), 'bytes': path.stat().st_size} for path in destination.rglob('*') if path.is_file()}
    manifest = {'format': 1, 'engine': connection.vendor, 'created_at': datetime.now(timezone.utc).isoformat(), 'database': database_file.name, 'files': files}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return destination


def verify_backup(directory):
    directory = Path(directory).resolve()
    try:
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        if manifest['format'] != 1 or manifest['engine'] not in ('sqlite', 'postgresql') or manifest['database'] not in ('database.sqlite3', 'database.dump'):
            raise ValueError('Unsupported backup format')
        for name, metadata in manifest['files'].items():
            path = (directory / name).resolve()
            if not path.is_relative_to(directory) or path.is_symlink() or not path.is_file():
                raise ValueError('Invalid backup path')
            if name != manifest['database'] and not name.startswith('private_media/'):
                raise ValueError('Unexpected backup file')
            if path.stat().st_size != metadata['bytes'] or digest(path) != metadata['sha256']:
                raise ValueError('Checksum mismatch')
        if manifest['database'] not in manifest['files']:
            raise ValueError('Database backup is missing')
    except (KeyError, TypeError, ValueError, OSError) as error:
        raise CommandError('Backup verification failed: ' + str(error)) from None
    return manifest


def restore_backup(directory):
    directory = Path(directory).resolve()
    manifest = verify_backup(directory)
    if manifest['engine'] != connection.vendor:
        raise CommandError('Backup engine does not match the target. Use the documented data migration procedure for cross-database moves.')
    if connection.introspection.table_names():
        raise CommandError('Restore requires an empty target database. Existing data will not be overwritten.')
    private_root = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
    if private_root.exists() and any(private_root.iterdir()):
        raise CommandError('Restore requires an empty private media directory.')
    if private_root == directory or private_root.is_relative_to(directory) or directory.is_relative_to(private_root):
        raise CommandError('Backup and restored media must be separate directories.')
    if connection.vendor == 'sqlite':
        name = str(connection.settings_dict['NAME'])
        if name == ':memory:' or name.startswith('file:'):
            raise CommandError('Restore to a file-backed SQLite database.')
        target = Path(name).resolve()
        if target.is_relative_to(directory):
            raise CommandError('The database target must be outside the backup directory.')
        connection.close()
        shutil.copy2(directory / manifest['database'], target)
    else:
        postgres_command('pg_restore', ['--no-owner', '--no-privileges', '--exit-on-error', '--single-transaction', str(directory / manifest['database'])])
    private_root.mkdir(parents=True, exist_ok=True)
    for name in manifest['files']:
        if name.startswith('private_media/'):
            relative = Path(name).relative_to('private_media')
            target = (private_root / relative).resolve()
            if not target.is_relative_to(private_root):
                raise CommandError('Invalid private media path.')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(directory / name, target)
    return manifest
