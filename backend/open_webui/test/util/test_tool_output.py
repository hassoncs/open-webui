import importlib

import pytest


@pytest.fixture
def tool_output_module(monkeypatch):
    monkeypatch.syspath_prepend('/Users/hassoncs/src/ch5/open-webui/backend')
    module = importlib.import_module('open_webui.utils.tool_output')
    yield module


def test_build_function_call_output_item_marks_failures(tool_output_module):
    item = tool_output_module.build_function_call_output_item(
        item_id='fco_test',
        call_id='call_123',
        output_parts=[{'type': 'input_text', 'text': 'MCP error -32602: Invalid input'}],
        error=True,
    )

    assert item['type'] == 'function_call_output'
    assert item['id'] == 'fco_test'
    assert item['call_id'] == 'call_123'
    assert item['status'] == 'failed'
    assert item['output'][0]['text'] == 'MCP error -32602: Invalid input'


def test_build_function_call_output_item_preserves_success_metadata(tool_output_module):
    item = tool_output_module.build_function_call_output_item(
        item_id='fco_ok',
        call_id='call_ok',
        output_parts=[{'type': 'input_text', 'text': 'ok'}],
        display_files=[{'type': 'image', 'url': 'https://example.com/x.png'}],
        embeds={'score': 0.9},
        error=False,
    )

    assert item['status'] == 'completed'
    assert item['files'] == [{'type': 'image', 'url': 'https://example.com/x.png'}]
    assert item['embeds'] == {'score': 0.9}
