from pathlib import Path
from typing import Any

import ollama


CATALOG_PATH = Path(__file__).with_name("catalog.txt")
MODEL = "qwen3:4b"

PROVIDER_SYSTEM_PROMPT = """You are a catalog provider agent managing a product
inventory. Use read_catalog to check stock. Use update_catalog when asked to
remove items after a purchase. Always confirm your actions clearly and concisely."""


def read_catalog() -> str:
    """Read the current product catalog from disk and return available stock."""
    lines = []
    with CATALOG_PATH.open("r", encoding="utf-8") as catalog_file:
        for raw_line in catalog_file:
            line = raw_line.strip()
            if not line:
                continue
            name, quantity = line.split(",", maxsplit=1)
            lines.append(f"{name.strip()}: {int(quantity.strip())} units")
    return "\n".join(lines)


def update_catalog(item: str, quantity_to_remove: int) -> str:
    """Remove a quantity of an item from the catalog if enough stock exists."""
    try:
        quantity_to_remove = int(quantity_to_remove)
    except (TypeError, ValueError):
        return "ERROR: quantity_to_remove must be an integer."

    if quantity_to_remove <= 0:
        return "ERROR: quantity_to_remove must be greater than 0."

    catalog_entries: list[tuple[str, int]] = []
    matched_index: int | None = None

    with CATALOG_PATH.open("r", encoding="utf-8") as catalog_file:
        for raw_line in catalog_file:
            line = raw_line.strip()
            if not line:
                continue
            name, quantity = line.split(",", maxsplit=1)
            clean_name = name.strip()
            clean_quantity = int(quantity.strip())
            if clean_name.casefold() == item.strip().casefold():
                matched_index = len(catalog_entries)
            catalog_entries.append((clean_name, clean_quantity))

    if matched_index is None:
        return "ERROR: item not found."

    current_name, current_quantity = catalog_entries[matched_index]
    if quantity_to_remove > current_quantity:
        return f"ERROR: only {current_quantity} units available."

    remaining_quantity = current_quantity - quantity_to_remove
    catalog_entries[matched_index] = (current_name, remaining_quantity)

    with CATALOG_PATH.open("w", encoding="utf-8") as catalog_file:
        for name, quantity in catalog_entries:
            catalog_file.write(f"{name},{quantity}\n")

    return (
        f"SUCCESS: removed {quantity_to_remove} units of {current_name}. "
        f"Remaining: {remaining_quantity}."
    )


def _message_to_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return message
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", ""),
        "tool_calls": getattr(message, "tool_calls", None),
    }


def _get_message(response: Any) -> Any:
    if isinstance(response, dict):
        return response.get("message", {})
    return response.message


def _get_content(message: Any) -> str:
    if isinstance(message, dict):
        return message.get("content") or ""
    return getattr(message, "content", "") or ""


def _get_tool_calls(message: Any) -> list[Any]:
    if isinstance(message, dict):
        return message.get("tool_calls") or []
    return getattr(message, "tool_calls", None) or []


def _tool_call_name_and_args(tool_call: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(tool_call, dict):
        function = tool_call.get("function", {})
        return function.get("name", ""), function.get("arguments", {}) or {}

    function = tool_call.function
    return function.name, function.arguments or {}


def run_provider(user_message: str) -> tuple[str, list[dict]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": PROVIDER_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    steps: list[dict] = []
    available_tools = {
        "read_catalog": read_catalog,
        "update_catalog": update_catalog,
    }

    while True:
        response = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=[read_catalog, update_catalog],
        )
        message = _get_message(response)
        tool_calls = _get_tool_calls(message)

        if not tool_calls:
            return _get_content(message), steps

        messages.append(_message_to_dict(message))

        for tool_call in tool_calls:
            tool_name, args = _tool_call_name_and_args(tool_call)
            steps.append({"role": "tool_call", "content": f"{tool_name}({args})"})

            tool_func = available_tools.get(tool_name)
            if tool_func is None:
                result = f"ERROR: unknown tool {tool_name}."
            else:
                try:
                    result = str(tool_func(**args))
                except Exception as exc:
                    result = f"ERROR: tool {tool_name} failed: {exc}"

            steps.append({"role": "tool_result", "content": result})
            messages.append(
                {"role": "tool", "tool_name": tool_name, "content": result}
            )
