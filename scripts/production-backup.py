#!/usr/bin/env python3
"""Create a private backup of the production database and media volumes."""
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ['docker', 'compose', '-f', str(ROOT / 'compose.production.yml')]


def main():
    os.umask(0o077)
    target = ROOT / 'production-data' / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target.mkdir(parents=True, exist_ok=False)
    with (target / 'database.dump').open('xb') as output:
        subprocess.run(COMPOSE + ['exec', '-T', 'db', 'sh', '-c',
            'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'], stdout=output, check=True)
    # Application writes should be paused for a coordinated DB/files restore point.
    with (target / 'media.tar').open('xb') as output:
        subprocess.run(COMPOSE + ['exec', '-T', 'web', 'tar', '-C', '/app/data', '-cf', '-', 'public', 'private'],
            stdout=output, check=True)
    (target / 'COMPLETE').touch()
    print(f'Backup completed: {target}')
    print('Keep an encrypted off-machine copy and store encryption keys separately.')


if __name__ == '__main__':
    main()
