import json

import anthropic
import structlog
from anthropic.types import MessageParam, ToolParam

from agent.registry import TOOLS, TOOLS_BY_NAME
from agent.system_prompt import SYSTEM_PROMPT
from config import settings

log = structlog.get_logger()

_API_TOOLS: list[ToolParam] = [
    {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
    for t in TOOLS
]


async def run_agent(
    user_text: str,
    *,
    chat_id: str,
    history: list[MessageParam] | None = None,
    record_calls: list | None = None,
    max_turns: int = 6,
) -> dict:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages: list[MessageParam] = (history or []) + [{"role": "user", "content": user_text}]

    for _ in range(max_turns):
        resp = await client.messages.create(
            model=settings.jonas_agent_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=_API_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"final": text, "messages": messages}

        # stop reason is 'tool_use'
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            tool = TOOLS_BY_NAME[block.name]
            args = tool["input_model"].model_validate(block.input)
            result = await tool["handler"](args, chat_id=chat_id)
            if record_calls is not None:
                record_calls.append({"name": block.name, "input": block.input, "output": result})
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
            )
        messages.append({"role": "user", "content": tool_results})

    return {"final": "(max turns reached)", "messages": messages}
