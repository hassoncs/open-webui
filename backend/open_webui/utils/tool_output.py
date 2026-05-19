import ast
import json
from typing import Any


def content_parts_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get('type') == 'text' and part.get('text'):
                texts.append(part['text'])

        if texts:
            return '\n'.join(texts)

    return json.dumps(content, ensure_ascii=False)


def is_tool_error_text(text: str) -> bool:
    return text.startswith('MCP error -') or text.startswith('Error: MCP error -')


def normalize_legacy_tool_result_text(text: str) -> str:
    if not text.startswith("[{'type': 'text'"):
        return text

    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return text

    return content_parts_to_text(parsed)


def update_function_call_status(
    output: list[dict[str, Any]],
    *,
    call_id: str,
    arguments: str,
    failed: bool,
) -> bool:
    for item in output:
        if item.get('type') == 'function_call' and item.get('call_id') == call_id:
            item['status'] = 'failed' if failed else 'completed'
            item['arguments'] = arguments
            return True

    return False


def repair_output_items(output: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    changed = False
    failed_call_ids: set[str] = set()

    for item in output:
        if item.get('type') != 'function_call_output':
            continue

        item_output = item.get('output', [])
        if not isinstance(item_output, list):
            continue

        for part in item_output:
            if not isinstance(part, dict) or part.get('type') != 'input_text':
                continue

            text = part.get('text', '')
            if not isinstance(text, str):
                continue

            normalized = normalize_legacy_tool_result_text(text)
            if normalized != text:
                part['text'] = normalized
                changed = True

            if is_tool_error_text(part.get('text', '')):
                failed_call_ids.add(item.get('call_id', ''))
                if item.get('status') != 'failed':
                    item['status'] = 'failed'
                    changed = True

    for item in output:
        if item.get('type') == 'function_call' and item.get('call_id') in failed_call_ids:
            if item.get('status') != 'failed':
                item['status'] = 'failed'
                changed = True

    return output, changed


def build_function_call_output_item(
    *,
    item_id: str,
    call_id: str,
    output_parts: list[dict[str, Any]],
    display_files: list[dict[str, Any]] | None = None,
    embeds: Any = None,
    error: bool = False,
) -> dict[str, Any]:
    return {
        'type': 'function_call_output',
        'id': item_id,
        'call_id': call_id,
        'output': output_parts,
        'status': 'failed' if error else 'completed',
        **({'files': display_files} if display_files else {}),
        **({'embeds': embeds} if embeds else {}),
    }
