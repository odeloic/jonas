"""Assignment generation eval — validates the generator prompt against structural invariants.

Acceptance bar:
  0 invariant violations across all cases (hard assert)

Invariants applied per item type (structural shape is already enforced by Pydantic;
this layer catches semantic and prompt-quality issues the validator can't see):
  - MULTIPLE_CHOICE: 3-4 options, no negative framing in question
  - REORDER: tokens non-empty, no punctuation in any token text
  - COMPLETION / FILL_IN_THE_BLANK: question does NOT contain ___ markers
    (the new shape moved blanks out of the question string)

Run with:
  pytest tests/evals/test_generation_eval.py -v -s
"""

import json
import re
from pathlib import Path

import pytest

from models.assignment_schema import (
    AssignmentContent,
    CriterionItem,
    MultipleChoiceItem,
    ReorderItem,
)
from models.extraction import GrammarRule, PageExtraction
from services.assignment import generate_assignment

DATASET_PATH = Path(__file__).parent / "datasets" / "generation_cases.json"

_BLANK_MARKER = re.compile(r"_{2,}")
_NEGATIVE_FRAMING = re.compile(
    r"\bnicht\s+korrekt\b|\bnicht\s+richtig\b|\bfalsch\w*\b|\binkorrekt\w*\b",
    re.IGNORECASE,
)
_PUNCT_IN_TOKEN = re.compile(r"[.,;:!?]")


@pytest.fixture(scope="module")
def generation_cases() -> list[dict]:
    cases = json.loads(DATASET_PATH.read_text())
    assert len(cases) >= 10, f"Expected 10+ cases, got {len(cases)}"
    return cases


def _build_extraction(case: dict) -> PageExtraction:
    return PageExtraction(
        topic=case["topic"],
        grammar_rules=[GrammarRule(**r) for r in case["grammar_rules"]],
        vocabulary=[],
        example_sentences=[],
    )


def _check_invariants(content: AssignmentContent) -> list[str]:
    issues: list[str] = []

    if len(content.sections) < 2:
        issues.append(f"only_{len(content.sections)}_section(s)")

    for si, section in enumerate(content.sections):
        if not section.items:
            issues.append(f"s{si}:empty_section")
            continue

        for ii, item in enumerate(section.items):
            loc = f"s{si}i{ii}[{section.type.value}]"

            if isinstance(item, MultipleChoiceItem):
                if not item.question.strip():
                    issues.append(f"{loc}:empty_question")
                if not (3 <= len(item.options) <= 4):
                    issues.append(f"{loc}:mc_has_{len(item.options)}_options")
                if _NEGATIVE_FRAMING.search(item.question):
                    issues.append(f"{loc}:mc_negative_framing q={item.question!r}")

            elif isinstance(item, ReorderItem):
                if not item.tokens:
                    issues.append(f"{loc}:reorder_empty_tokens")
                bad = [t.text for t in item.tokens if _PUNCT_IN_TOKEN.search(t.text)]
                if bad:
                    issues.append(f"{loc}:reorder_tokens_have_punctuation tokens={bad!r}")

            elif isinstance(item, CriterionItem):
                # The new shape forbids ___ in the question — blanks are structural.
                if _BLANK_MARKER.search(item.question):
                    issues.append(
                        f"{loc}:criterion_has_blank_marker_in_question q={item.question!r}"
                    )
                if not item.blanks:
                    issues.append(f"{loc}:criterion_empty_blanks")

    return issues


async def test_generation_invariants(generation_cases):
    results: list[tuple[dict, list[str]]] = []

    for case in generation_cases:
        try:
            content = await generate_assignment(extractions=[_build_extraction(case)])
            issues = _check_invariants(content)
        except Exception as exc:  # noqa: BLE001
            issues = [f"exception:{type(exc).__name__}:{exc}"]
        results.append((case, issues))

    print("\n=== Assignment Generation Eval ===\n")
    passes = 0
    for case, issues in results:
        status = "PASS" if not issues else "FAIL"
        print(f"  {status} {case['id']:<32}  issues: {issues or 'none'}")
        if not issues:
            passes += 1

    total = len(results)
    print(f"\nPass rate: {passes}/{total} ({passes / total:.0%})")

    all_issues = [f"{c['id']}:{iss}" for c, issues in results for iss in issues]
    assert not all_issues, (
        f"Generation invariants violated ({len(all_issues)} total):\n"
        + "\n".join(f"  - {i}" for i in all_issues)
    )
