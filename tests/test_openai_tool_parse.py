from __future__ import annotations

from modules.model.openai_tool_parse import openai_message_to_model_output


def test_text_only_message() -> None:
    out = openai_message_to_model_output({"role": "assistant", "content": "hello"}, provider_id="p")
    assert out.kind == "text"
    assert out.content == "hello"


def test_tool_calls_first_wins() -> None:
    msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "echo", "arguments": '{"text": "hi"}'},
            }
        ],
    }
    out = openai_message_to_model_output(msg, provider_id="p")
    assert out.kind == "tool_call"
    assert out.tool_call is not None
    assert out.tool_call.name == "echo"
    assert out.tool_call.arguments == {"text": "hi"}
    assert out.tool_call.call_id == "call_1"


def test_tool_calls_invalid_json_arguments() -> None:
    msg = {
        "tool_calls": [
            {"function": {"name": "x", "arguments": "not-json"}}
        ],
    }
    out = openai_message_to_model_output(msg, provider_id="p")
    assert out.kind == "tool_call"
    assert out.tool_call is not None
    assert out.tool_call.arguments.get("_parse_error") is True
