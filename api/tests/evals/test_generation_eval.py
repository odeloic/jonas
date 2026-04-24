"""Assignment generation eval — validates the generator prompt against structural invariants.

Acceptance bar:
  0 invariant violations across all cases (hard assert)

Invariants applied to every generated assignment:
  - At least 2 sections, each non-empty
  - Every item has a non-empty question and correct_answer
  - MULTIPLE_CHOICE: 3-4 options, correct_answer in options, no negative framing
    (no "NICHT korrekt", "falsch", "inkorrekt" — these produce contradictory hints)
  - COMPLETION / FILL_IN_THE_BLANK / ADJEKTIV_DEKLINATION: question contains a blank marker
  - REORDER: word bag in question == word bag in correct_answer (case- and punctuation-normalized)

Run with:
  pytest tests/evals/test_generation_eval.py -v -s
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from models.assignment_schema import AssignmentContent, SectionType
from models.extraction import GrammarRule, PageExtraction
from services.assignment import generate_assignment

DATASET_PATH = Path(__file__).parent / "datasets" / "generation_cases.json"

_BLANK_MARKER = re.compile(r"_{2,}")
_NEGATIVE_FRAMING = re.compile(
    r"\bnicht\s+korrekt\b|\bnicht\s+richtig\b|\bfalsch\w*\b|\binkorrekt\w*\b",
    re.IGNORECASE,
)
_BLANK_TYPES = frozenset(
    {
        SectionType.COMPLETION,
        SectionType.FILL_IN_THE_BLANK,
        SectionType.ADJEKTIV_DEKLINATION,
    }
)


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


def _normalize_token(token: str) -> str:
    return re.sub(r"[^\w]", "", token, flags=re.UNICODE).lower()


def _reorder_bag_diff(question: str, correct_answer: str) -> str | None:
    q_tokens = [_normalize_token(t) for t in question.split("/")]
    a_tokens = [_normalize_token(t) for t in correct_answer.split()]
    q_bag = Counter(t for t in q_tokens if t)
    a_bag = Counter(t for t in a_tokens if t)
    if q_bag == a_bag:
        return None
    only_q = dict(q_bag - a_bag)
    only_a = dict(a_bag - q_bag)
    return f"q={question!r} a={correct_answer!r} question_only={only_q} answer_only={only_a}"


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

            if not item.question.strip():
                issues.append(f"{loc}:empty_question")
            if not item.correct_answer.strip():
                issues.append(f"{loc}:empty_correct_answer")

            if section.type == SectionType.MULTIPLE_CHOICE:
                if not item.options or not (3 <= len(item.options) <= 4):
                    count = len(item.options) if item.options else 0
                    issues.append(f"{loc}:mc_has_{count}_options")
                elif item.correct_answer not in item.options:
                    issues.append(
                        f"{loc}:mc_correct_answer_not_in_options "
                        f"correct_answer={item.correct_answer!r} options={item.options!r}"
                    )
                if _NEGATIVE_FRAMING.search(item.question):
                    issues.append(f"{loc}:mc_negative_framing q={item.question!r}")

            if section.type in _BLANK_TYPES and not _BLANK_MARKER.search(item.question):
                issues.append(f"{loc}:missing_blank_marker q={item.question!r}")

            if section.type == SectionType.REORDER:
                diff = _reorder_bag_diff(item.question, item.correct_answer)
                if diff:
                    issues.append(f"{loc}:reorder_bag_mismatch {diff}")

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
