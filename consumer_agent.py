from typing import Any

import ollama

from provider_agent import run_provider


MODEL = "qwen3:4b"
inter_agent_log = []

CONSUMER_SYSTEM_PROMPT = """You are a shopping assistant agent. Help the user
find and purchase products. Use query_provider to check what products and
quantities are available. Use purchase_from_provider when the user wants to buy
something. Always confirm the result of each purchase to the user."""


def query_provider(question: str) -> str:
    """Ask the provider agent a catalog or inventory question."""
    inter_agent_log.append({"from": "consumer", "message": question})
    answer, _ = run_provider(question)
    inter_agent_log.append({"from": "provider", "message": answer})
    return answer


def purchase_from_provider(item: str, quantity: int) -> str:
    """Ask the provider agent to remove purchased items from the catalog."""
    message = f"Please remove {quantity} units of {item} from the catalog."
    inter_agent_log.append({"from": "consumer", "message": message})
    answer, _ = run_provider(message)
    inter_agent_log.append({"from": "provider", "message": answer})
    return answer


def get_inter_agent_log() -> list[dict]:
    return list(inter_agent_log)


def clear_inter_agent_log() -> None:
    global inter_agent_log
    inter_agent_log = []


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


def run_consumer(user_message: str) -> tuple[str, list[dict]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": CONSUMER_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    available_tools = {
        "query_provider": query_provider,
        "purchase_from_provider": purchase_from_provider,
    }

    while True:
        response = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=[query_provider, purchase_from_provider],
        )
        message = _get_message(response)
        tool_calls = _get_tool_calls(message)

        if not tool_calls:
            return _get_content(message), get_inter_agent_log()

        messages.append(_message_to_dict(message))

        for tool_call in tool_calls:
            tool_name, args = _tool_call_name_and_args(tool_call)
            tool_func = available_tools.get(tool_name)
            if tool_func is None:
                result = f"ERROR: unknown tool {tool_name}."
            else:
                try:
                    result = str(tool_func(**args))
                except Exception as exc:
                    result = f"ERROR: tool {tool_name} failed: {exc}"

            messages.append(
                {"role": "tool", "tool_name": tool_name, "content": result}
            )
