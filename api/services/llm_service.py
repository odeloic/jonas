"""Provider-routed LLM service — Anthropic SDK for Claude, OpenAI SDK for GPT.

No LiteLLM middleman. Each provider gets native structured output support.
"""

import re
import time
from dataclasses import dataclass

import anthropic
import openai
import structlog
from pydantic import BaseModel as PydanticBaseModel

from config import settings

log = structlog.get_logger()

_DATA_URI_RE = re.compile(r"^data:(image/\w+);base64,(.+)$", re.DOTALL)


@dataclass
class LLMResult[T]:
    """Rich result from an LLM call — carries parsed output + observability."""

    parsed: T
    raw_response: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    model: str = ""
    wall_clock_seconds: float = 0.0


class LLMService:
    """Routes LLM calls to the appropriate SDK based on model name."""

    def __init__(self) -> None:
        self._anthropic: anthropic.AsyncAnthropic | None = None
        self._openai: openai.AsyncOpenAI | None = None

    def _get_anthropic(self) -> anthropic.AsyncAnthropic:
        if self._anthropic is None:
            self._anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._anthropic

    def _get_openai(self) -> openai.AsyncOpenAI:
        if self._openai is None:
            self._openai = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai

    @staticmethod
    def _is_anthropic(model: str) -> bool:
        return "claude" in model.lower()

    @staticmethod
    def _bare_model(model: str) -> str:
        """Strip provider prefix: 'anthropic/claude-...' → 'claude-...'."""
        return model.split("/", 1)[-1] if "/" in model else model

    # ------------------------------------------------------------------
    # Message format conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_content_for_anthropic(content: list[dict]) -> list[dict]:
        """Convert OpenAI image_url blocks to Anthropic image blocks."""
        converted = []
        for block in content:
            if block.get("type") == "image_url":
                url = block["image_url"]["url"]
                match = _DATA_URI_RE.match(url)
                if match:
                    converted.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": match.group(1),
                                "data": match.group(2),
                            },
                        }
                    )
                else:
                    converted.append({"type": "image", "source": {"type": "url", "url": url}})
            else:
                converted.append(block)
        return converted

    @classmethod
    def _prepare_anthropic_messages(cls, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Split system message and convert vision content for Anthropic SDK."""
        system_msg = None
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                msg = dict(m)
                if isinstance(msg.get("content"), list):
                    msg["content"] = cls._convert_content_for_anthropic(msg["content"])
                user_messages.append(msg)
        return system_msg, user_messages

    # ------------------------------------------------------------------
    # Structured output
    # ------------------------------------------------------------------

    async def complete_structured[T: PydanticBaseModel](
        self,
        messages: list[dict],
        response_format: type[T],
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResult[T]:
        chosen = model or settings.default_model
        if self._is_anthropic(chosen):
            return await self._anthropic_structured(chosen, messages, response_format, max_tokens)
        return await self._openai_structured(chosen, messages, response_format, max_tokens)

    async def _anthropic_structured[T: PydanticBaseModel](
        self,
        model: str,
        messages: list[dict],
        response_format: type[T],
        max_tokens: int,
    ) -> LLMResult[T]:
        client = self._get_anthropic()
        bare = self._bare_model(model)
        system_msg, user_messages = self._prepare_anthropic_messages(messages)

        kwargs: dict = {}
        if system_msg:
            kwargs["system"] = system_msg

        t0 = time.perf_counter()
        response = await client.messages.parse(
            model=bare,
            max_tokens=max_tokens,
            messages=user_messages,
            output_format=response_format,
            **kwargs,
        )
        elapsed = round(time.perf_counter() - t0, 2)

        text_blocks = [b for b in response.content if b.type == "text"]
        raw = text_blocks[0].text if text_blocks else ""

        if response.parsed_output is None:
            log.error(
                "llm_no_parsed_output",
                model=model,
                stop_reason=response.stop_reason,
            )
            raise ValueError(
                f"Anthropic returned no parsed output for {response_format.__name__} "
                f"(stop_reason={response.stop_reason})"
            )

        result = LLMResult(
            parsed=response.parsed_output,
            raw_response=raw,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason,
            model=model,
            wall_clock_seconds=elapsed,
        )

        log.info(
            "llm_call",
            model=model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            wall_clock=elapsed,
        )
        return result

    async def _openai_structured[T: PydanticBaseModel](
        self,
        model: str,
        messages: list[dict],
        response_format: type[T],
        max_tokens: int,
    ) -> LLMResult[T]:
        client = self._get_openai()

        t0 = time.perf_counter()
        response = await client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_format,
            max_completion_tokens=max_tokens,
        )
        elapsed = round(time.perf_counter() - t0, 2)

        choice = response.choices[0]
        raw = choice.message.content or ""

        if choice.message.parsed is None:
            refusal = getattr(choice.message, "refusal", None)
            log.error(
                "llm_no_parsed_output",
                model=model,
                finish_reason=choice.finish_reason,
                refusal=refusal,
            )
            raise ValueError(
                f"OpenAI returned no parsed output for {response_format.__name__} "
                f"(finish_reason={choice.finish_reason}, refusal={refusal})"
            )

        result = LLMResult(
            parsed=choice.message.parsed,
            raw_response=raw,
            input_tokens=response.usage.prompt_tokens if response.usage else None,
            output_tokens=response.usage.completion_tokens if response.usage else None,
            finish_reason=choice.finish_reason,
            model=model,
            wall_clock_seconds=elapsed,
        )

        log.info(
            "llm_call",
            model=model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            wall_clock=elapsed,
        )
        return result

    # ------------------------------------------------------------------
    # Plain text completion
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResult[str]:
        chosen = model or settings.default_model
        if self._is_anthropic(chosen):
            return await self._anthropic_complete(chosen, messages, max_tokens)
        return await self._openai_complete(chosen, messages, max_tokens)

    async def _anthropic_complete(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
    ) -> LLMResult[str]:
        client = self._get_anthropic()
        bare = self._bare_model(model)
        system_msg, user_messages = self._prepare_anthropic_messages(messages)

        kwargs: dict = {}
        if system_msg:
            kwargs["system"] = system_msg

        t0 = time.perf_counter()
        response = await client.messages.create(
            model=bare,
            max_tokens=max_tokens,
            messages=user_messages,
            **kwargs,
        )
        elapsed = round(time.perf_counter() - t0, 2)

        text_blocks = [b for b in response.content if b.type == "text"]
        text = text_blocks[0].text if text_blocks else ""

        result = LLMResult(
            parsed=text,
            raw_response=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason,
            model=model,
            wall_clock_seconds=elapsed,
        )

        log.info(
            "llm_call",
            model=model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            wall_clock=elapsed,
        )
        return result

    async def _openai_complete(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
    ) -> LLMResult[str]:
        client = self._get_openai()

        t0 = time.perf_counter()
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
        elapsed = round(time.perf_counter() - t0, 2)

        choice = response.choices[0]
        text = choice.message.content or ""

        result = LLMResult(
            parsed=text,
            raw_response=text,
            input_tokens=response.usage.prompt_tokens if response.usage else None,
            output_tokens=response.usage.completion_tokens if response.usage else None,
            finish_reason=choice.finish_reason,
            model=model,
            wall_clock_seconds=elapsed,
        )

        log.info(
            "llm_call",
            model=model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            wall_clock=elapsed,
        )
        return result

    # ------------------------------------------------------------------
    # Embeddings (OpenAI only)
    # ------------------------------------------------------------------

    async def embed(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float]:
        client = self._get_openai()
        chosen = model or settings.embedding_model
        response = await client.embeddings.create(model=chosen, input=[text])
        return response.data[0].embedding
