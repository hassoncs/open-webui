#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sqlite3
from dataclasses import dataclass
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Inspect Open WebUI users, chats, and messages from a SQLite snapshot.'
    )
    parser.add_argument('--db', required=True, help='Path to a SQLite snapshot or live SQLite file.')

    subparsers = parser.add_subparsers(dest='command', required=True)

    list_parser = subparsers.add_parser('list-user-sessions', help='List chat/session ids for a user email.')
    list_parser.add_argument('--email', required=True, help='User email address.')
    list_parser.add_argument('--json', action='store_true', help='Emit JSON instead of text.')

    search_parser = subparsers.add_parser(
        'search-user-sessions',
        help="Search a user's chats/messages for a term and show matching session ids.",
    )
    search_parser.add_argument('--email', required=True, help='User email address.')
    search_parser.add_argument('--term', required=True, help='Case-insensitive search term.')
    search_parser.add_argument('--json', action='store_true', help='Emit JSON instead of text.')

    dump_parser = subparsers.add_parser(
        'dump-session',
        help='Dump all messages for a chat/session id, with optional term highlighting context.',
    )
    dump_parser.add_argument('--chat-id', required=True, help='Chat/session id.')
    dump_parser.add_argument('--term', help='Optional term to highlight / focus on.')
    dump_parser.add_argument('--json', action='store_true', help='Emit JSON instead of text.')

    return parser.parse_args()


@dataclass
class UserRecord:
    id: str
    email: str
    name: str | None
    role: str | None


@dataclass
class ChatRecord:
    id: str
    user_id: str
    title: str | None
    created_at: int | None
    updated_at: int | None
    archived: int | None
    pinned: int | None
    message_count: int


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


def fetch_user(conn: sqlite3.Connection, email: str) -> UserRecord:
    row = conn.execute('SELECT id, email, name, role FROM user WHERE email = ?', (email,)).fetchone()
    if row is None:
        raise SystemExit(f'user not found for email: {email}')
    return UserRecord(id=row['id'], email=row['email'], name=row['name'], role=row['role'])


def fetch_user_chats(conn: sqlite3.Connection, user_id: str) -> list[ChatRecord]:
    rows = conn.execute(
        """
        SELECT
            c.id,
            c.user_id,
            c.title,
            c.created_at,
            c.updated_at,
            c.archived,
            c.pinned,
            COUNT(cm.id) AS message_count
        FROM chat c
        LEFT JOIN chat_message cm ON cm.chat_id = c.id
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.updated_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [
        ChatRecord(
            id=row['id'],
            user_id=row['user_id'],
            title=row['title'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            archived=row['archived'],
            pinned=row['pinned'],
            message_count=row['message_count'],
        )
        for row in rows
    ]


def safe_json_load(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def flatten_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return '\n'.join(part for item in value if (part := flatten_text(item)))
    if isinstance(value, dict):
        preferred_keys = ['text', 'content', 'name', 'url', 'path', 'title', 'description']
        parts: list[str] = []
        for key in preferred_keys:
            if key in value:
                part = flatten_text(value[key])
                if part:
                    parts.append(part)
        if parts:
            return '\n'.join(parts)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return repr(value)


def shorten(text: str, limit: int = 220) -> str:
    clean = ' '.join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + '…'


def fetch_chat_messages(conn: sqlite3.Connection, chat_id: str) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT id, chat_id, user_id, role, parent_id, content, output, model_id,
               files, sources, embeds, done, status_history, error, usage,
               created_at, updated_at
        FROM chat_message
        WHERE chat_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (chat_id,),
    ).fetchall()

    if rows:
        return rows

    chat_row = conn.execute('SELECT chat FROM chat WHERE id = ?', (chat_id,)).fetchone()
    if chat_row is None:
        raise SystemExit(f'chat not found: {chat_id}')

    chat_blob = safe_json_load(chat_row['chat']) or {}
    messages = ((chat_blob.get('history') or {}).get('messages')) or {}
    fallback_rows = []
    for message_id, message in messages.items():
        fallback_rows.append(
            {
                'id': f'{chat_id}-{message_id}',
                'chat_id': chat_id,
                'user_id': None,
                'role': message.get('role'),
                'parent_id': message.get('parentId'),
                'content': json.dumps(message.get('content')),
                'output': json.dumps(message.get('output')),
                'model_id': message.get('model'),
                'files': json.dumps(message.get('files')),
                'sources': json.dumps(message.get('sources')),
                'embeds': json.dumps(message.get('embeds')),
                'done': message.get('done'),
                'status_history': json.dumps(message.get('statusHistory')),
                'error': json.dumps(message.get('error')),
                'usage': json.dumps(message.get('usage')),
                'created_at': message.get('timestamp'),
                'updated_at': message.get('timestamp'),
            }
        )
    return fallback_rows


def message_search_blob(row: sqlite3.Row | dict[str, Any]) -> str:
    keys = ['content', 'output', 'status_history', 'files', 'sources', 'embeds', 'error']
    parts = [flatten_text(safe_json_load(row.get(key) if isinstance(row, dict) else row[key])) for key in keys]
    if isinstance(row, dict):
        parts.extend([str(row.get('model_id') or ''), str(row.get('role') or '')])
    else:
        parts.extend([str(row['model_id'] or ''), str(row['role'] or '')])
    return '\n'.join(part for part in parts if part)


def list_user_sessions(conn: sqlite3.Connection, email: str, as_json: bool) -> int:
    user = fetch_user(conn, email)
    chats = fetch_user_chats(conn, user.id)
    payload = {
        'user': user.__dict__,
        'chat_count': len(chats),
        'sessions': [
            {
                'chat_id': chat.id,
                'title': chat.title,
                'created_at': epoch_to_iso(chat.created_at),
                'updated_at': epoch_to_iso(chat.updated_at),
                'archived': bool(chat.archived),
                'pinned': bool(chat.pinned),
                'message_count': chat.message_count,
            }
            for chat in chats
        ],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f'user: {user.email} ({user.name or "unknown"}) id={user.id} role={user.role}')
    print(f'sessions: {len(chats)}')
    for chat in chats:
        print(
            f'- {chat.id} | {chat.message_count:>3} msgs | updated {epoch_to_iso(chat.updated_at)} | '
            f'archived={bool(chat.archived)} pinned={bool(chat.pinned)} | {chat.title or "(untitled)"}'
        )
    return 0


def search_user_sessions(conn: sqlite3.Connection, email: str, term: str, as_json: bool) -> int:
    user = fetch_user(conn, email)
    chats = fetch_user_chats(conn, user.id)
    term_lower = term.lower()
    matches: list[dict[str, Any]] = []

    for chat in chats:
        messages = fetch_chat_messages(conn, chat.id)
        hit_messages = []
        for row in messages:
            blob = message_search_blob(row)
            if term_lower in blob.lower():
                hit_messages.append(
                    {
                        'message_id': row['id'] if not isinstance(row, dict) else row['id'],
                        'role': row['role'] if not isinstance(row, dict) else row['role'],
                        'model_id': row['model_id'] if not isinstance(row, dict) else row.get('model_id'),
                        'created_at': epoch_to_iso(
                            row['created_at'] if not isinstance(row, dict) else row.get('created_at')
                        ),
                        'excerpt': shorten(blob),
                    }
                )
        if hit_messages:
            matches.append(
                {
                    'chat_id': chat.id,
                    'title': chat.title,
                    'updated_at': epoch_to_iso(chat.updated_at),
                    'message_matches': hit_messages,
                }
            )

    payload = {'user': user.__dict__, 'term': term, 'matches': matches}
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f'search term: {term}')
    print(f'user: {user.email} ({user.name or "unknown"})')
    print(f'matching sessions: {len(matches)}')
    for match in matches:
        print(f'- {match["chat_id"]} | updated {match["updated_at"]} | {match["title"] or "(untitled)"}')
        for msg in match['message_matches']:
            print(f'    {msg["created_at"]} | {msg["role"]} | {msg["model_id"] or "-"} | {msg["excerpt"]}')
    return 0


def dump_session(conn: sqlite3.Connection, chat_id: str, term: str | None, as_json: bool) -> int:
    chat_row = conn.execute(
        'SELECT id, user_id, title, created_at, updated_at, archived, pinned FROM chat WHERE id = ?',
        (chat_id,),
    ).fetchone()
    if chat_row is None:
        raise SystemExit(f'chat not found: {chat_id}')

    user_row = conn.execute('SELECT email, name FROM user WHERE id = ?', (chat_row['user_id'],)).fetchone()
    messages = fetch_chat_messages(conn, chat_id)

    normalized_messages = []
    for row in messages:
        content = safe_json_load(row['content'] if not isinstance(row, dict) else row.get('content'))
        output = safe_json_load(row['output'] if not isinstance(row, dict) else row.get('output'))
        status_history = safe_json_load(
            row['status_history'] if not isinstance(row, dict) else row.get('status_history')
        )
        files = safe_json_load(row['files'] if not isinstance(row, dict) else row.get('files'))
        sources = safe_json_load(row['sources'] if not isinstance(row, dict) else row.get('sources'))
        error = safe_json_load(row['error'] if not isinstance(row, dict) else row.get('error'))
        message_blob = message_search_blob(row)
        has_term = bool(term and term.lower() in message_blob.lower())

        normalized_messages.append(
            {
                'message_id': row['id'] if not isinstance(row, dict) else row['id'],
                'role': row['role'] if not isinstance(row, dict) else row['role'],
                'model_id': row['model_id'] if not isinstance(row, dict) else row.get('model_id'),
                'created_at': epoch_to_iso(row['created_at'] if not isinstance(row, dict) else row.get('created_at')),
                'done': bool(row['done'] if not isinstance(row, dict) else row.get('done')),
                'content': content,
                'output': output,
                'status_history': status_history,
                'files': files,
                'sources': sources,
                'error': error,
                'search_hit': has_term,
            }
        )

    chat_info = {
        'id': chat_row['id'],
        'user_id': chat_row['user_id'],
        'user_email': user_row['email'] if user_row else None,
        'user_name': user_row['name'] if user_row else None,
        'title': chat_row['title'],
        'created_at': epoch_to_iso(chat_row['created_at']),
        'updated_at': epoch_to_iso(chat_row['updated_at']),
        'archived': bool(chat_row['archived']),
        'pinned': bool(chat_row['pinned']),
    }
    payload = {'chat': chat_info, 'term': term, 'messages': normalized_messages}

    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(
        f'chat: {chat_info["id"]} | {chat_info["title"] or "(untitled)"} | user={chat_info["user_email"]} | '
        f'created={chat_info["created_at"]} updated={chat_info["updated_at"]}'
    )
    for msg in normalized_messages:
        hit = ' [match]' if msg['search_hit'] else ''
        print(f'\n[{msg["created_at"]}] {msg["role"]} model={msg["model_id"] or "-"} done={msg["done"]}{hit}')
        content_text = flatten_text(msg['content'])
        if content_text:
            print(f'content: {content_text}')
        output_text = flatten_text(msg['output'])
        if output_text:
            print(f'output: {output_text}')
        if msg['files']:
            print(f'files: {json.dumps(msg["files"], ensure_ascii=False)}')
        if msg['sources']:
            print(f'sources: {json.dumps(msg["sources"], ensure_ascii=False)}')
        if msg['status_history']:
            print(f'status_history: {json.dumps(msg["status_history"], ensure_ascii=False)}')
        if msg['error']:
            print(f'error: {json.dumps(msg["error"], ensure_ascii=False)}')
    return 0


def main() -> int:
    args = parse_args()
    conn = connect(args.db)
    try:
        if args.command == 'list-user-sessions':
            return list_user_sessions(conn, args.email, args.json)
        if args.command == 'search-user-sessions':
            return search_user_sessions(conn, args.email, args.term, args.json)
        if args.command == 'dump-session':
            return dump_session(conn, args.chat_id, args.term, args.json)
        raise SystemExit(f'unknown command: {args.command}')
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
