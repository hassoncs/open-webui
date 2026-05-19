#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile


DEFAULT_HOST = 'radbot@macmini.lan'
DEFAULT_CONTAINER = 'open-webui-devmux'
DEFAULT_DB_PATH = '/app/backend/data/webui.db'


REMOTE_SNAPSHOT_SCRIPT = r"""
python3 - <<'PY'
import os
import shutil
import sqlite3
import sys
import tempfile

source_db = os.environ['OWUI_DB_PATH']
tmp = tempfile.NamedTemporaryFile(prefix='open-webui-db-', suffix='.sqlite3', delete=False)
tmp.close()
snapshot_path = tmp.name

src = sqlite3.connect(f'file:{source_db}?mode=ro', uri=True)
dst = sqlite3.connect(snapshot_path)
try:
    src.backup(dst)
finally:
    dst.close()
    src.close()

with open(snapshot_path, 'rb') as fh:
    shutil.copyfileobj(fh, sys.stdout.buffer)

os.unlink(snapshot_path)
PY
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Fetch a consistent Open WebUI SQLite snapshot from the live Docker container.'
    )
    parser.add_argument(
        '--host',
        default=DEFAULT_HOST,
        help=f'SSH target for the host running Open WebUI (default: {DEFAULT_HOST})',
    )
    parser.add_argument(
        '--container',
        default=DEFAULT_CONTAINER,
        help=f'Docker container name (default: {DEFAULT_CONTAINER})',
    )
    parser.add_argument(
        '--db-path',
        default=DEFAULT_DB_PATH,
        help=f'SQLite path inside the container (default: {DEFAULT_DB_PATH})',
    )
    parser.add_argument(
        '--output',
        help='Optional output path for the snapshot. Defaults to a temp file.',
    )
    return parser.parse_args()


def build_command(host: str, container: str, db_path: str) -> list[str]:
    remote_env = f'OWUI_DB_PATH={db_path}'
    return [
        'ssh',
        host,
        'docker',
        'exec',
        '-i',
        '-e',
        remote_env,
        container,
        'sh',
        '-lc',
        REMOTE_SNAPSHOT_SCRIPT,
    ]


def main() -> int:
    args = parse_args()

    if args.output:
        output_path = pathlib.Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        tmp = tempfile.NamedTemporaryFile(prefix='open-webui-db-', suffix='.sqlite3', delete=False)
        tmp.close()
        output_path = pathlib.Path(tmp.name)

    command = build_command(args.host, args.container, args.db_path)

    try:
        with output_path.open('wb') as fh:
            result = subprocess.run(command, stdout=fh, stderr=subprocess.PIPE, check=False)
    except FileNotFoundError as exc:
        print(f'missing executable: {exc}', file=sys.stderr)
        return 1

    if result.returncode != 0:
        if output_path.exists() and output_path.stat().st_size == 0:
            output_path.unlink()
        stderr = result.stderr.decode('utf-8', errors='replace')
        print(stderr.strip() or 'failed to fetch database snapshot', file=sys.stderr)
        return result.returncode

    print(str(output_path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
