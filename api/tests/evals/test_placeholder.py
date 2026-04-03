"""Smoke test — verifies pytest + LLMService are wired correctly.

Uses `no_langfuse` so it runs without Langfuse keys (local or CI).
"""

import pytest


@pytest.mark.asyncio
async def test_llm_service_completes(llm_service, no_langfuse):
    """LLMService returns a non-empty response for a trivial prompt."""
    result = await llm_service.complete(
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        max_tokens=16,
        trace_name=None,
    )
    assert result.parsed.strip()
    assert result.input_tokens is not None
    assert result.output_tokens is not None
    assert result.wall_clock_seconds > 0
