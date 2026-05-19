#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
from pathlib import Path


def load_tool_output_module(repo_root: Path):
    sys.path.insert(0, str(repo_root / 'backend'))
    return importlib.import_module('open_webui.utils.tool_output')


def repair_rows(db_path: Path, repo_root: Path, apply: bool, limit: int | None) -> dict[str, object]:
    tool_output = load_tool_output_module(repo_root)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        query = 'SELECT id, chat_id, content, output FROM chat_message WHERE output IS NOT NULL ORDER BY created_at ASC'
        if limit:
            query += f' LIMIT {int(limit)}'

        rows = conn.execute(query).fetchall()
        changed_rows = []

        for row in rows:
            if not row['output']:
                continue

            output = json.loads(row['output'])
            if not isinstance(output, list):
                continue

            repaired_output, changed = tool_output.repair_output_items(output)
            if not changed:
                continue

            changed_rows.append(
                {
                    'id': row['id'],
                    'chat_id': row['chat_id'],
                    'output': repaired_output,
                }
            )

        if apply and changed_rows:
            middleware = importlib.import_module('open_webui.utils.middleware')
            for row in changed_rows:
                rendered_content = middleware.serialize_output(row['output'])
                conn.execute(
                    'UPDATE chat_message SET output = ?, content = ? WHERE id = ?',
                    (json.dumps(row['output'], ensure_ascii=False), rendered_content, row['id']),
                )

                chat_row = conn.execute('SELECT chat FROM chat WHERE id = ?', (row['chat_id'],)).fetchone()
                if chat_row is not None and chat_row[0]:
                    chat_blob = json.loads(chat_row[0])
                    history = chat_blob.get('history', {})
                    message_id = row['id'].removeprefix(f'{row["chat_id"]}-')
                    if message_id in history.get('messages', {}):
                        history['messages'][message_id]['output'] = row['output']
                        history['messages'][message_id]['content'] = rendered_content
                        chat_blob['history'] = history
                        conn.execute(
                            'UPDATE chat SET chat = ? WHERE id = ?',
                            (json.dumps(chat_blob, ensure_ascii=False), row['chat_id']),
                        )
            conn.commit()

        preview = []
        for row in changed_rows[:10]:
            function_call_output = next(
                (item for item in row['output'] if item.get('type') == 'function_call_output'),
                None,
            )
            function_call = next(
                (item for item in row['output'] if item.get('type') == 'function_call'),
                None,
            )
            preview.append(
                {
                    'id': row['id'],
                    'function_call_status': function_call.get('status') if function_call else None,
                    'function_call_output_status': function_call_output.get('status') if function_call_output else None,
                    'function_call_output_preview': (
                        function_call_output.get('output', [{}])[0].get('text', '')[:200]
                        if function_call_output
                        else None
                    ),
                }
            )

        return {
            'db_path': str(db_path),
            'changed_row_count': len(changed_rows),
            'applied': apply,
            'preview': preview,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Repair legacy stringified MCP tool outputs in chat_message rows.')
    parser.add_argument('--db', required=True, help='Path to Open WebUI SQLite database')
    parser.add_argument('--repo-root', default='.', help='Path to the repo root containing backend/')
    parser.add_argument('--apply', action='store_true', help='Write repaired output/content back to the database')
    parser.add_argument('--limit', type=int, default=None, help='Limit rows scanned for dry runs or batches')
    args = parser.parse_args()

    result = repair_rows(Path(args.db), Path(args.repo_root).resolve(), args.apply, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
