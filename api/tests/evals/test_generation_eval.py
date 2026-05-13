"""Assignment generation eval — validates the generator prompt against structural invariants.

Acceptance bar:
  0 invariant violations across all cases (hard assert)

Invariants applied per item type:
  - MULTIPLE_CHOICE: 3-4 options, correct_answer in options, no negative framing
  - REORDER: correct_tokens non-empty, no punctuation in tokens
  - ADJEKTIV_DEKLINATION: question has ___ marker, candidate_endings contains correct_ending
  - COMPLETION / FILL_IN_THE_BLANK: question has ≥1 ___ marker,
    grading_criterion and example_answer non-empty

Run with:
  pytest tests/evals/test_generation_eval.py -v -s
"""

import json
import re
from pathlib import Path

import pytest

from models.assignment_schema import (
    AdjektivDeklinationItem,
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
                elif item.correct_answer not in item.options:
                    issues.append(
                        f"{loc}:mc_correct_answer_not_in_options "
                        f"correct_answer={item.correct_answer!r} options={item.options!r}"
                    )
                if _NEGATIVE_FRAMING.search(item.question):
                    issues.append(f"{loc}:mc_negative_framing q={item.question!r}")

            elif isinstance(item, ReorderItem):
                if not item.correct_tokens:
                    issues.append(f"{loc}:reorder_empty_tokens")
                bad = [t for t in item.correct_tokens if _PUNCT_IN_TOKEN.search(t)]
                if bad:
                    issues.append(f"{loc}:reorder_tokens_have_punctuation tokens={bad!r}")

            elif isinstance(item, AdjektivDeklinationItem):
                if not _BLANK_MARKER.search(item.question):
                    issues.append(f"{loc}:adj_missing_blank q={item.question!r}")
                if item.correct_ending not in item.candidate_endings:
                    issues.append(
                        f"{loc}:adj_correct_not_in_candidates "
                        f"correct={item.correct_ending!r} candidates={item.candidate_endings!r}"
                    )

            elif isinstance(item, CriterionItem):
                if not _BLANK_MARKER.search(item.question):
                    issues.append(f"{loc}:criterion_missing_blank q={item.question!r}")
                if not item.grading_criterion.strip():
                    issues.append(f"{loc}:criterion_empty_grading_criterion")
                if not item.example_answer.strip():
                    issues.append(f"{loc}:criterion_empty_example_answer")

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
