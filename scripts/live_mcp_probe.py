#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
import uuid


sys.path.insert(0, '/app/backend')

from fastapi.testclient import TestClient

from open_webui.main import app
from open_webui.utils.mcp.client import MCPClient
from open_webui.utils.auth import create_token


MODEL = 'minimax-coding-plan/MiniMax-M2.7'
SERVER_ID = 'ntn'
DB_PATH = '/app/backend/data/webui.db'


def fail(message: str) -> None:
    print(json.dumps({'status': 'error', 'message': message}))
    raise SystemExit(1)


async def get_mcp_specs_and_token(user_id: str) -> tuple[list[dict], str]:
    connection = None
    for candidate in app.state.config.TOOL_SERVER_CONNECTIONS:
        if candidate.get('type') == 'mcp' and candidate.get('info', {}).get('id') == SERVER_ID:
            connection = candidate
            break

    if connection is None:
        fail(f'MCP server {SERVER_ID} not found')

    oauth_token = await app.state.oauth_client_manager.get_oauth_token(user_id, f'mcp:{SERVER_ID}')
    if not oauth_token:
        fail(f'No OAuth token for MCP server {SERVER_ID} and user {user_id}')

    headers = {'Authorization': f'Bearer {oauth_token.get("access_token", "")}'}
    client = MCPClient()
    try:
        await client.connect(connection.get('url', ''), headers=headers)
        specs = await client.list_tool_specs()
        return specs, connection.get('url', '')
    finally:
        await client.disconnect()


def get_user_with_mcp_session() -> tuple[str, str]:
    db = sqlite3.connect(DB_PATH)
    try:
        row = db.execute(
            """
            SELECT u.id, u.email
            FROM oauth_session o
            JOIN user u ON u.id = o.user_id
            WHERE o.provider = ?
            ORDER BY o.updated_at DESC
            LIMIT 1
            """,
            (f'mcp:{SERVER_ID}',),
        ).fetchone()
    finally:
        db.close()

    if row is None:
        fail(f'No Open WebUI user has OAuth session for mcp:{SERVER_ID}')

    return row[0], row[1]


def fetch_chat_row(chat_id: str):
    db = sqlite3.connect(DB_PATH)
    try:
        return db.execute('SELECT id, title FROM chat WHERE id = ?', (chat_id,)).fetchone()
    finally:
        db.close()


def fetch_chat_messages(chat_id: str):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """
            SELECT id, role, content, output, error, done, model_id, created_at
            FROM chat_message
            WHERE chat_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (chat_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def wait_for_chat_tasks_to_finish(client: TestClient, token: str, chat_id: str, timeout_seconds: int = 90) -> list[str]:
    last_task_ids: list[str] = []
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        res = client.get(f'/api/tasks/chat/{chat_id}', headers={'Authorization': f'Bearer {token}'})
        if res.status_code != 200:
            fail(f'task polling failed with {res.status_code}: {res.text[:400]}')

        body = res.json()
        task_ids = body.get('task_ids', []) if isinstance(body, dict) else []
        last_task_ids = task_ids
        if not task_ids:
            return last_task_ids

        time.sleep(1)

    return last_task_ids


def main() -> None:
    client = TestClient(app)

    user_id, user_email = get_user_with_mcp_session()
    token = create_token(data={'id': user_id})

    specs, mcp_url = asyncio.run(get_mcp_specs_and_token(user_id))
    spec_names = [spec.get('name') for spec in specs]
    if 'notion-create-pages' not in spec_names:
        fail('notion-create-pages spec not available from MCP server')

    chat_seed = client.post(
        '/api/v1/chats/new',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'chat': {
                'title': 'MCP Probe Chat',
                'history': {
                    'messages': {},
                    'currentId': None,
                },
            },
            'folder_id': None,
        },
    )
    if chat_seed.status_code != 200:
        fail(f'chat seed failed with {chat_seed.status_code}: {chat_seed.text[:400]}')

    seeded_chat = chat_seed.json()
    chat_id = seeded_chat.get('id')
    if not chat_id:
        fail('chat seed response missing id')

    chat_row = fetch_chat_row(chat_id)
    if chat_row is None:
        fail(
            f'chat seed id {chat_id} was not persisted; response was {json.dumps(seeded_chat, ensure_ascii=False)[:400]}'
        )

    message_id = f'msg-{uuid.uuid4()}'
    now = int(time.time())

    payload = {
        'model': MODEL,
        'stream': False,
        'messages': [
            {
                'role': 'user',
                'content': (
                    'Call the tool ntn_notion-create-pages exactly once with invalid arguments. '
                    'Use this JSON: '
                    '{"pages":[{"properties":{"title":"OWUI MCP Probe"},"content":"probe"}],"parent":{"type":"page_id"}}. '
                    'Do not explain, do not retry, just call the tool.'
                ),
            }
        ],
        'tool_ids': ['server:mcp:ntn'],
        'features': {},
        'chat_id': chat_id,
        'id': message_id,
        'background_tasks': {'title_generation': False, 'tags_generation': False, 'follow_up_generation': False},
        'timestamp': now,
    }

    response = client.post('/api/chat/completions', headers={'Authorization': f'Bearer {token}'}, json=payload)
    if response.status_code != 200:
        fail(f'chat completion failed with {response.status_code}: {response.text[:400]}')

    body = response.json()
    remaining_task_ids = wait_for_chat_tasks_to_finish(client, token, chat_id)

    persisted_messages = []
    for _ in range(20):
        persisted_messages = fetch_chat_messages(chat_id)
        if len(persisted_messages) > 1 or remaining_task_ids == []:
            break
        time.sleep(1)

    assistant_outputs = []
    for row in persisted_messages:
        output = json.loads(row['output']) if row.get('output') else None
        assistant_outputs.append(
            {
                'id': row['id'],
                'role': row['role'],
                'done': row['done'],
                'model_id': row['model_id'],
                'output_types': [item.get('type') for item in output] if isinstance(output, list) else None,
                'content_preview': str(row.get('content'))[:220],
                'error': row.get('error'),
            }
        )

    print(
        json.dumps(
            {
                'status': 'ok',
                'chat_id': chat_id,
                'request_message_id': message_id,
                'user_email': user_email,
                'seeded_chat_title': seeded_chat.get('title'),
                'model': MODEL,
                'mcp_url': mcp_url,
                'available_spec_count': len(spec_names),
                'notion_create_pages_available': True,
                'seeded_chat_persisted': True,
                'persisted_message_count': len(persisted_messages),
                'remaining_task_ids': remaining_task_ids,
                'persisted_messages': assistant_outputs,
                'response_keys': sorted(body.keys()) if isinstance(body, dict) else None,
                'response_preview': (
                    json.dumps(body, ensure_ascii=False)[:600] if isinstance(body, (dict, list)) else str(body)[:600]
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == '__main__':
    main()
