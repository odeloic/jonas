"""Isolated assignment generation test — compare models with full observability.

Uses LLMService (native SDKs, no LiteLLM) to test structured assignment
generation against real grammar rules from Postgres.

Usage: docker compose exec api python scripts/test_assignment.py [OPTIONS]

Examples:
    python scripts/test_assignment.py
    python scripts/test_assignment.py --models gpt-5.4-mini
    python scripts/test_assignment.py --topic "Adjektivdeklination" --verbose

Baseline benchmarks (2026-03-28, 28 grammar rules / 7 topics):
    gpt-5-mini-2025-08-07       178.2s  3 sections / 12 items   3,360 out tokens
    gpt-5.4-mini                  6.0s  3 sections / 12 items     842 out tokens
    claude-haiku-4-5-20251001    13.3s  5 sections / 25 items   1,824 out tokens
    anthropic/claude-sonnet-4-6  20.3s  3 sections / 14 items   1,219 out tokens
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

import structlog
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from db import async_session
from logging_config import configure_logging
from models.assignment_schema import AssignmentContent
from models.extraction import GrammarRule as GrammarRulePydantic
from models.extraction import PageExtraction
from models.grammar_rule import GrammarRule as GrammarRuleRow
from services.assignment import ASSIGNMENT_SYSTEM_PROMPT, _format_rules_context
from services.llm_service import LLMResult, LLMService

log = structlog.get_logger()

DEFAULT_MODELS = (
    "gpt-5-mini-2025-08-07,gpt-5.4-mini,claude-haiku-4-5-20251001,anthropic/claude-sonnet-4-6"
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


async def load_grammar_rules(
    topic: str | None = None,
    limit: int | None = None,
) -> list[PageExtraction]:
    """Query grammar_rules from Postgres and reconstruct PageExtraction objects."""
    stmt = select(GrammarRuleRow).order_by(GrammarRuleRow.created_at.desc())
    if topic:
        stmt = stmt.where(GrammarRuleRow.topic.ilike(f"%{topic}%"))
    if limit:
        stmt = stmt.limit(limit)

    async with async_session() as session:
        rows = (await session.execute(stmt)).scalars().all()

    if not rows:
        return []

    by_topic: dict[str, list[GrammarRuleRow]] = defaultdict(list)
    for row in rows:
        by_topic[row.topic].append(row)

    extractions: list[PageExtraction] = []
    for topic_name, rule_rows in by_topic.items():
        pydantic_rules = [
            GrammarRulePydantic(
                rule_name=r.rule_name,
                explanation=r.explanation,
                pattern=r.pattern,
                examples=r.examples or [],
            )
            for r in rule_rows
        ]
        extractions.append(
            PageExtraction(
                topic=topic_name,
                grammar_rules=pydantic_rules,
                vocabulary=[],
                example_sentences=[],
            )
        )

    total_rules = sum(len(e.grammar_rules) for e in extractions)
    log.info(
        "test_data_loaded",
        topics=len(extractions),
        total_rules=total_rules,
        topic_names=[e.topic for e in extractions],
    )
    return extractions


# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------


def _is_anthropic_model(model: str) -> bool:
    return "claude" in model.lower()


def _has_api_key(model: str) -> bool:
    if _is_anthropic_model(model):
        return bool(settings.anthropic_api_key)
    return bool(settings.openai_api_key)


# ---------------------------------------------------------------------------
# Core test runner
# ---------------------------------------------------------------------------


async def run_model_test(
    llm: LLMService,
    model: str,
    extractions: list[PageExtraction],
) -> dict:
    """Run assignment generation against a single model. Returns a result dict."""
    row: dict = {
        "model": model,
        "success": False,
        "wall_clock": 0.0,
        "input_tokens": None,
        "output_tokens": None,
        "finish_reason": None,
        "raw_response": None,
        "sections": None,
        "items": None,
        "types": None,
        "error": None,
    }

    if not _has_api_key(model):
        row["error"] = "API key not configured"
        log.warning("test_model_skip", model=model, reason=row["error"])
        return row

    log.info("test_model_start", model=model)

    rules_context = _format_rules_context(extractions)
    resolved_topic = extractions[0].topic
    user_content = (
        f"Erstelle Übungen zum Thema: {resolved_topic}\n\nGrammatikregeln:\n{rules_context}"
    )
    messages = [
        {"role": "system", "content": ASSIGNMENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        result: LLMResult[AssignmentContent] = await llm.complete_structured(
            messages=messages,
            response_format=AssignmentContent,
            model=model,
            max_tokens=4096,
        )
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        log.error("test_llm_error", model=model, error=row["error"])
        return row

    row["wall_clock"] = result.wall_clock_seconds
    row["input_tokens"] = result.input_tokens
    row["output_tokens"] = result.output_tokens
    row["finish_reason"] = result.finish_reason
    row["raw_response"] = result.raw_response

    log.info(
        "test_llm_response",
        model=model,
        finish_reason=result.finish_reason,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        wall_clock=result.wall_clock_seconds,
    )

    parsed = result.parsed
    row["success"] = True
    row["sections"] = len(parsed.sections)
    row["items"] = sum(len(s.items) for s in parsed.sections)
    row["types"] = [s.type.value for s in parsed.sections]

    log.info(
        "test_validation_ok",
        model=model,
        sections=row["sections"],
        items=row["items"],
        types=row["types"],
    )
    return row


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

HEADER = ["Model", "Status", "Time", "In Tok", "Out Tok", "Finish", "Sections", "Items", "Error"]
WIDTHS = [30, 8, 7, 9, 9, 10, 10, 7, 40]


def _fmt_row(vals: list[str]) -> str:
    return "│ " + " │ ".join(v.ljust(w) for v, w in zip(vals, WIDTHS, strict=True)) + " │"


def _separator(char: str = "─", left: str = "├", right: str = "┤", mid: str = "┼") -> str:
    return left + mid.join(char * (w + 2) for w in WIDTHS) + right


def print_comparison_table(results: list[dict], verbose: bool = False) -> None:
    print("\n" + _separator("─", "┌", "┐", "┬"))
    print(_fmt_row(HEADER))
    print(_separator())

    for r in results:
        has_raw = r["raw_response"]
        status = "OK" if r["success"] else ("SKIP" if r["error"] and not has_raw else "FAIL")
        error_summary = (r["error"] or "")[:40]
        row = [
            r["model"][:30],
            status,
            f"{r['wall_clock']:.1f}s" if r["wall_clock"] else "-",
            f"{r['input_tokens']:,}" if r["input_tokens"] else "-",
            f"{r['output_tokens']:,}" if r["output_tokens"] else "-",
            r["finish_reason"] or "-",
            str(r["sections"]) if r["sections"] is not None else "-",
            str(r["items"]) if r["items"] is not None else "-",
            error_summary,
        ]
        print(_fmt_row(row))

    print(_separator("─", "└", "┘", "┴"))

    if verbose:
        for r in results:
            if r["raw_response"]:
                print(f"\n{'=' * 60}")
                print(f"RAW RESPONSE: {r['model']}")
                print(f"{'=' * 60}")
                display = r["raw_response"][:2000]
                if len(r["raw_response"]) > 2000:
                    display += f"\n... (truncated, total {len(r['raw_response'])} chars)"
                print(display)

            if r["error"] and r["raw_response"]:
                print(f"\n{'=' * 60}")
                print(f"ERROR: {r['model']}")
                print(f"{'=' * 60}")
                print(r["error"][:3000])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    configure_logging()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    log.info("test_start", models=models, topic=args.topic, limit=args.limit)

    extractions = await load_grammar_rules(topic=args.topic, limit=args.limit)
    if not extractions:
        print("No grammar rules found in database. Run /teach first or check --topic filter.")
        return

    llm = LLMService()
    results: list[dict] = []
    for model in models:
        result = await run_model_test(llm, model, extractions)
        results.append(result)

    print_comparison_table(results, verbose=args.verbose)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test assignment generation across LLM models")
    parser.add_argument(
        "--models",
        default=DEFAULT_MODELS,
        help=f"Comma-separated models to test (default: {DEFAULT_MODELS})",
    )
    parser.add_argument("--topic", help="Filter grammar rules by topic (substring match)")
    parser.add_argument("--limit", type=int, help="Max grammar rules to load from DB")
    parser.add_argument("--verbose", action="store_true", help="Print full raw LLM responses")
    asyncio.run(main(parser.parse_args()))
