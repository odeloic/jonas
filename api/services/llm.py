import litellm
import structlog
from pydantic import BaseModel as PydanticBaseModel

from config import settings

log = structlog.get_logger()


async def _call_llm(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 1024,
    **kwargs,
) -> litellm.ModelResponse:
    chosen_model = model or settings.default_model
    try:
        response = await litellm.acompletion(
            model=chosen_model,
            messages=messages,
            max_tokens=max_tokens,
            stream=False,
            **kwargs,
        )
        assert isinstance(response, litellm.ModelResponse)

    except litellm.exceptions.AuthenticationError:
        log.error("llm_auth_failed", model=chosen_model)
        raise

    except litellm.exceptions.APIError as exc:
        log.error("llm_api_error", model=chosen_model, error=str(exc))
        raise

    usage = response.get("usage")
    if usage:
        log.info(
            "llm_call",
            model=chosen_model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )

    return response


async def complete(messages: list[dict], model: str | None = None, max_tokens: int = 1024) -> str:
    response = await _call_llm(messages, model=model, max_tokens=max_tokens)
    return response.choices[0].message.content or ""  # FIXME: error handling


async def complete_structured[T: PydanticBaseModel](
    messages: list[dict],
    response_format: type[T],
    model: str | None = None,
    max_tokens: int = 1024,
) -> T:
    schema = response_format.model_json_schema()
    _enforce_strict_schema(schema)
    response = await _call_llm(
        messages,
        model=model,
        max_tokens=max_tokens,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": response_format.__name__,
                "strict": True,
                "schema": schema,
            },
        },
    )
    choice = response.choices[0]
    raw = choice.message.content or ""
    if not raw:
        log.error(
            "llm_empty_content",
            model=model or settings.default_model,
            schema=response_format.__name__,
            finish_reason=choice.finish_reason,
            refusal=getattr(choice.message, "refusal", None),
        )
        raise ValueError(f"LLM returned empty content for {response_format.__name__}")
    return response_format.model_validate_json(raw)


def _enforce_strict_schema(schema: dict) -> dict:
    """Add additionalProperties: false and require all properties for OpenAI strict mode."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
        if "properties" in schema:
            schema["required"] = list(schema["properties"].keys())
            for prop in schema["properties"].values():
                prop.pop("default", None)
    for key in ("properties", "$defs"):
        if key in schema:
            for v in schema[key].values():
                if isinstance(v, dict):
                    _enforce_strict_schema(v)
    for key in ("items", "anyOf", "allOf", "oneOf"):
        if key in schema:
            target = schema[key]
            if isinstance(target, dict):
                _enforce_strict_schema(target)
            elif isinstance(target, list):
                for item in target:
                    if isinstance(item, dict):
                        _enforce_strict_schema(item)
    return schema
