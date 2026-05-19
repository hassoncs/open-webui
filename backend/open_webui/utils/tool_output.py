from typing import Any


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
