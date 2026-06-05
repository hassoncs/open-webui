#!/usr/bin/env python3
"""Test signin endpoint directly inside the container using FastAPI TestClient."""

import sys

sys.path.insert(0, '/app/backend')

from fastapi.testclient import TestClient
from open_webui.main import app

client = TestClient(app)

print('Testing /api/v1/auths/signin...')
response = client.post('/api/v1/auths/signin', json={'email': 'owui-pending-check@example.com', 'password': 'Test1234'})
print(f'Status: {response.status_code}')
print(f'Body: {response.text}')
if response.status_code == 200:
    print('SUCCESS - Auth works!')
    print(f'Response JSON: {response.json()}')
