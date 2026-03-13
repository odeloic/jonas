import litellm
import structlog

from config import settings

log = structlog.get_logger()


async def complete(messages: list[dict], model: str | None = None, max_tokens: int = 1024) -> str:
    chosen_model = model or settings.default_model
    try:
        response = await litellm.acompletion(
            model=chosen_model, messages=messages, max_tokens=max_tokens, stream=False
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

    return response.choices[0].message.content or ""  # FIXME: error handling
