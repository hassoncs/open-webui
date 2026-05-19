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


def test_repair_output_items_normalizes_legacy_mcp_error_and_marks_pair_failed(tool_output_module):
    output = [
        {
            'type': 'function_call',
            'id': 'fc_1',
            'call_id': 'call_1',
            'name': 'ntn_notion-create-pages',
            'arguments': '{}',
            'status': 'completed',
        },
        {
            'type': 'function_call_output',
            'id': 'fco_1',
            'call_id': 'call_1',
            'status': 'completed',
            'output': [
                {
                    'type': 'input_text',
                    'text': "[{'type': 'text', 'text': 'MCP error -32602: Invalid input', 'annotations': None, 'meta': None}]",
                }
            ],
        },
    ]

    repaired, changed = tool_output_module.repair_output_items(output)

    assert changed is True
    assert repaired[0]['status'] == 'failed'
    assert repaired[1]['status'] == 'failed'
    assert repaired[1]['output'][0]['text'] == 'MCP error -32602: Invalid input'


def test_update_function_call_status_marks_failed_pair(tool_output_module):
    output = [
        {
            'type': 'function_call',
            'id': 'fc_2',
            'call_id': 'call_2',
            'name': 'tool',
            'arguments': '{}',
            'status': 'in_progress',
        }
    ]

    changed = tool_output_module.update_function_call_status(
        output,
        call_id='call_2',
        arguments='{"foo":"bar"}',
        failed=True,
    )

    assert changed is True
    assert output[0]['status'] == 'failed'
    assert output[0]['arguments'] == '{"foo":"bar"}'
