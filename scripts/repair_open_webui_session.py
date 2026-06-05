#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class RepairAnalysis:
    chat_id: str
    title: str | None
    current_id_before: str | None
    current_id_after: str | None
    invalid_message_ids: list[str]
    unresolved_parent_ids: list[str]
    changed: bool
    message_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Analyze and repair malformed Open WebUI chat history rows.')
    parser.add_argument('--db', required=True, help='Path to SQLite DB file.')
    parser.add_argument('--chat-id', required=True, help='Chat/session id to inspect.')
    parser.add_argument('--apply', action='store_true', help='Write repaired history back to the DB.')
    parser.add_argument('--json', action='store_true', help='Emit JSON instead of text.')
    return parser.parse_args()


def connect(db_path: str) -> sqlite3.Connection:
    path = pathlib.Path(db_path).expanduser().resolve()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def epoch_to_iso(value: Any) -> str | None:
    if value in (None, ''):
        return None
    ts = int(value)
    if ts > 10_000_000_000:
        ts = ts / 1000
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat()


def load_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    if isinstance(value, str):
        return json.loads(value)
    return value


def is_history_message_valid(message_id: str, message: Any) -> bool:
    if not isinstance(message, dict):
        return False
    if message.get('id') != message_id:
        return False
    if not message.get('role'):
        return False
    parent_id = message.get('parentId')
    if parent_id is not None and not isinstance(parent_id, str):
        return False
    children_ids = message.get('childrenIds')
    if children_ids is not None and not isinstance(children_ids, list):
        return False
    return True


def get_unresolved_parent_ids(messages: dict[str, dict[str, Any]]) -> set[str]:
    return {
        message['parentId']
        for message in messages.values()
        if isinstance(message, dict) and message.get('parentId') and message['parentId'] not in messages
    }


def select_current_id(messages: dict[str, dict[str, Any]], preferred_id: str | None) -> str | None:
    if preferred_id and preferred_id in messages and is_history_message_valid(preferred_id, messages.get(preferred_id)):
        return preferred_id

    leaf_candidates: list[tuple[int, str]] = []
    for message_id, message in messages.items():
        if not isinstance(message, dict):
            continue
        children = message.get('childrenIds') or []
        if len(children) == 0:
            leaf_candidates.append((int(message.get('timestamp') or 0), message_id))

    if leaf_candidates:
        leaf_candidates.sort()
        return leaf_candidates[-1][1]

    return next(iter(messages), None)


def get_normalized_messages(conn: sqlite3.Connection, chat_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, role, parent_id, content, output, model_id,
               files, sources, embeds, done, status_history, error, usage, created_at
        FROM chat_message
        WHERE chat_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (chat_id,),
    ).fetchall()

    prefix = f'{chat_id}-'
    messages: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_id = row['id'][len(prefix) :] if row['id'].startswith(prefix) else row['id']
        message: dict[str, Any] = {
            'id': raw_id,
            'role': row['role'],
            'content': load_json(row['content']),
            'done': bool(row['done']),
            'timestamp': row['created_at'],
        }
        if row['parent_id'] is not None:
            message['parentId'] = row['parent_id']
        if row['model_id'] is not None:
            message['model'] = row['model_id']

        for key, column in (
            ('output', 'output'),
            ('files', 'files'),
            ('sources', 'sources'),
            ('embeds', 'embeds'),
            ('statusHistory', 'status_history'),
            ('error', 'error'),
            ('usage', 'usage'),
        ):
            value = load_json(row[column])
            if value is not None:
                message[key] = value

        messages[raw_id] = message

    for message in messages.values():
        message['childrenIds'] = []

    for message_id, message in messages.items():
        parent_id = message.get('parentId')
        if parent_id and parent_id in messages:
            messages[parent_id]['childrenIds'].append(message_id)

    return messages


def repair_chat(conn: sqlite3.Connection, chat_id: str, apply: bool) -> tuple[RepairAnalysis, dict[str, Any] | None]:
    row = conn.execute('SELECT id, title, chat FROM chat WHERE id = ?', (chat_id,)).fetchone()
    if row is None:
        raise SystemExit(f'chat not found: {chat_id}')

    chat_data = load_json(row['chat'])
    if not isinstance(chat_data, dict):
        raise SystemExit(f'chat payload is not an object: {chat_id}')

    history = chat_data.get('history')
    if not isinstance(history, dict):
        raise SystemExit(f'chat history missing or malformed: {chat_id}')

    messages = history.get('messages')
    if not isinstance(messages, dict):
        raise SystemExit(f'chat history.messages missing or malformed: {chat_id}')

    invalid_message_ids = sorted(
        message_id for message_id, message in messages.items() if not is_history_message_valid(message_id, message)
    )

    repaired_messages = messages
    unresolved_parent_ids: set[str] = set()
    normalized_messages = get_normalized_messages(conn, chat_id)
    if normalized_messages:
        unresolved_parent_ids = get_unresolved_parent_ids(normalized_messages)
        valid_legacy_messages = {
            message_id: messages[message_id]
            for message_id in unresolved_parent_ids
            if message_id in messages and is_history_message_valid(message_id, messages[message_id])
        }
        if valid_legacy_messages:
            normalized_messages.update(valid_legacy_messages)

        if invalid_message_ids or unresolved_parent_ids:
            repaired_messages = {**messages, **normalized_messages}

    changed = repaired_messages is not messages

    for message_id, message in list(repaired_messages.items()):
        if not isinstance(message, dict):
            continue
        if message.get('id') != message_id:
            message['id'] = message_id
            changed = True
        children = message.get('childrenIds')
        if not isinstance(children, list):
            message['childrenIds'] = []
            changed = True
        else:
            filtered_children = [child_id for child_id in children if child_id in repaired_messages]
            if filtered_children != children:
                message['childrenIds'] = filtered_children
                changed = True

    current_id_before = history.get('currentId')
    current_id_after = select_current_id(repaired_messages, current_id_before)
    if current_id_before != current_id_after:
        history['currentId'] = current_id_after
        changed = True

    if repaired_messages is not messages:
        history['messages'] = repaired_messages
        changed = True

    chat_data['history'] = history

    if apply and changed:
        conn.execute('UPDATE chat SET chat = ? WHERE id = ?', (json.dumps(chat_data, ensure_ascii=False), chat_id))
        conn.commit()

    analysis = RepairAnalysis(
        chat_id=chat_id,
        title=row['title'],
        current_id_before=current_id_before,
        current_id_after=current_id_after,
        invalid_message_ids=invalid_message_ids,
        unresolved_parent_ids=sorted(unresolved_parent_ids),
        changed=changed,
        message_count=len(repaired_messages),
    )
    return analysis, chat_data


def main() -> int:
    args = parse_args()
    conn = connect(args.db)
    try:
        analysis, chat_data = repair_chat(conn, args.chat_id, args.apply)
    finally:
        conn.close()

    payload = {
        'chat_id': analysis.chat_id,
        'title': analysis.title,
        'current_id_before': analysis.current_id_before,
        'current_id_after': analysis.current_id_after,
        'invalid_message_ids': analysis.invalid_message_ids,
        'unresolved_parent_ids': analysis.unresolved_parent_ids,
        'changed': analysis.changed,
        'message_count': analysis.message_count,
        'applied': bool(args.apply and analysis.changed),
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f'chat: {analysis.chat_id} | {analysis.title or "(untitled)"}')
    print(f'messages: {analysis.message_count}')
    print(f'currentId: {analysis.current_id_before} -> {analysis.current_id_after}')
    print(f'invalid nodes: {len(analysis.invalid_message_ids)}')
    for message_id in analysis.invalid_message_ids:
        print(f'  - {message_id}')
    print(f'unresolved normalized parents: {len(analysis.unresolved_parent_ids)}')
    print(f'changed: {analysis.changed}')
    print(f'applied: {bool(args.apply and analysis.changed)}')

    if chat_data is not None and analysis.invalid_message_ids:
        print('\nExample repaired node source:')
        for message_id in analysis.invalid_message_ids[:1]:
            node = chat_data.get('history', {}).get('messages', {}).get(message_id)
            print(json.dumps(node, indent=2, ensure_ascii=False))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
