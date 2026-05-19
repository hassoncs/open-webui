import importlib
import sys
import types

import pytest


def _install_mcp_stubs():
    mcp_module = types.ModuleType('mcp')
    setattr(mcp_module, 'ClientSession', object)
    sys.modules['mcp'] = mcp_module

    client_module = types.ModuleType('mcp.client')
    sys.modules['mcp.client'] = client_module

    auth_module = types.ModuleType('mcp.client.auth')
    setattr(auth_module, 'OAuthClientProvider', object)
    setattr(auth_module, 'TokenStorage', object)
    sys.modules['mcp.client.auth'] = auth_module

    streamable_http_module = types.ModuleType('mcp.client.streamable_http')
    setattr(streamable_http_module, 'streamablehttp_client', lambda *args, **kwargs: None)
    sys.modules['mcp.client.streamable_http'] = streamable_http_module

    shared_module = types.ModuleType('mcp.shared')
    sys.modules['mcp.shared'] = shared_module

    shared_auth_module = types.ModuleType('mcp.shared.auth')
    setattr(shared_auth_module, 'OAuthClientInformationFull', object)
    setattr(shared_auth_module, 'OAuthClientMetadata', object)
    setattr(shared_auth_module, 'OAuthToken', object)
    sys.modules['mcp.shared.auth'] = shared_auth_module


def _install_open_webui_env_stub():
    env_module = types.ModuleType('open_webui.env')
    setattr(env_module, 'AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL', True)
    setattr(env_module, 'AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER', None)
    sys.modules['open_webui.env'] = env_module


@pytest.fixture
def mcp_client_module(monkeypatch):
    monkeypatch.syspath_prepend('/Users/hassoncs/src/ch5/open-webui/backend')
    _install_mcp_stubs()
    _install_open_webui_env_stub()
    module = importlib.import_module('open_webui.utils.mcp.client')
    yield module


class FakeToolResult:
    def __init__(self, *, content, is_error):
        self._content = content
        self.isError = is_error

    def model_dump(self, mode='json'):
        assert mode == 'json'
        return {'content': self._content}


class FakeSession:
    def __init__(self, result):
        self._result = result

    async def call_tool(self, function_name, function_args):
        return self._result


def test_content_to_text_joins_text_parts(mcp_client_module):
    text = mcp_client_module.MCPClient._content_to_text(
        [
            {'type': 'text', 'text': 'MCP error -32602: Invalid input', 'annotations': None},
            {'type': 'image', 'url': 'ignored'},
            {'type': 'text', 'text': 'Second line'},
        ]
    )

    assert text == 'MCP error -32602: Invalid input\nSecond line'


@pytest.mark.asyncio
async def test_call_tool_raises_normalized_error_text(mcp_client_module):
    result = FakeToolResult(
        content=[
            {'type': 'text', 'text': 'MCP error -32602: Invalid arguments', 'annotations': None},
            {'type': 'text', 'text': 'path: parent', 'meta': None},
        ],
        is_error=True,
    )
    client = mcp_client_module.MCPClient()
    client.session = FakeSession(result)

    with pytest.raises(Exception) as exc_info:
        await client.call_tool('notion-create-pages', {'foo': 'bar'})

    assert str(exc_info.value) == 'MCP error -32602: Invalid arguments\npath: parent'
    assert "[{'type': 'text'" not in str(exc_info.value)
