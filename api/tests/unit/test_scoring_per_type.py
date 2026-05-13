"""Per-type scoring TDD tests for ODE assignment correction cutover.

These tests pin down the new scoring contract item-by-item:

- MULTIPLE_CHOICE: byte-equal (after normalize) against `correct_answer`. No judge call.
- REORDER: per-index equality between submitted list and stored `correct_tokens`. No judge.
- ADJEKTIV_DEKLINATION: byte-equal against `correct_ending`. No judge.
- COMPLETION / FILL_IN_THE_BLANK: judge call against `grading_criterion` (one call per item,
  regardless of blank count). `example_answer` is informational only.

The closed-type cases pass a stub LLM that raises if invoked — proving they take the
deterministic path. Criterion cases drive a fake judge that records its arguments so the
test can assert what the judge sees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from models.assignment_schema import (
    AdjektivDeklinationItem,
    AssignmentContent,
    AssignmentSection,
    CriterionItem,
    MultipleChoiceItem,
    ReorderItem,
    SectionAnswers,
    SectionType,
    SubmissionAnswers,
)
from services import scoring as scoring_module
from services.grading_judge import JudgeResult
from services.llm_service import LLMResult


class _BoomLLM:
    """LLMService stand-in. Any attribute access raises — proves no LLM was hit."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"LLM was used unexpectedly (accessed: {name!r})")


@dataclass
class _RecordedCall:
    question: str
    grading_criterion: str
    example_answer: str
    student_answers: list[str]


@dataclass
class _FakeJudge:
    """Drop-in replacement for services.grading_judge.judge_answer.

    Configure `verdicts` as an iterable of bools — each call pops the next verdict.
    Records every call in `calls` for assertion.
    """

    verdicts: list[bool]
    calls: list[_RecordedCall] = field(default_factory=list)

    async def __call__(
        self,
        *,
        question: str,
        grading_criterion: str,
        example_answer: str,
        student_answers: list[str],
        llm,  # noqa: ANN001
    ) -> JudgeResult:
        self.calls.append(
            _RecordedCall(
                question=question,
                grading_criterion=grading_criterion,
                example_answer=example_answer,
                student_answers=list(student_answers),
            )
        )
        if not self.verdicts:
            raise AssertionError("FakeJudge ran out of verdicts")
        is_correct = self.verdicts.pop(0)
        return JudgeResult(
            is_correct=is_correct,
            score=1.0 if is_correct else 0.0,
            rationale="fake",
            raw_result=LLMResult(parsed=None, raw_response="", model="fake"),
        )


def _one_section_content(section: AssignmentSection) -> AssignmentContent:
    return AssignmentContent(sections=[section])


def _one_section_answers(items: list[list[str]]) -> SubmissionAnswers:
    return SubmissionAnswers(sections=[SectionAnswers(items=items)])


# ---------------------------------------------------------------------------
# MULTIPLE_CHOICE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mc_correct_option_matches():
    section = AssignmentSection(
        type=SectionType.MULTIPLE_CHOICE,
        title="MC",
        instructions="x",
        items=[
            MultipleChoiceItem(
                type=SectionType.MULTIPLE_CHOICE,
                question="Was passt?",
                options=["A", "B", "C"],
                correct_answer="B",
            )
        ],
    )
    score, max_score, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section), _one_section_answers([[" B "]]), _BoomLLM()
    )
    assert (score, max_score) == (1, 1)
    assert feedback.sections[0].items[0].correct is True


@pytest.mark.asyncio
async def test_mc_wrong_option_fails():
    section = AssignmentSection(
        type=SectionType.MULTIPLE_CHOICE,
        title="MC",
        instructions="x",
        items=[
            MultipleChoiceItem(
                type=SectionType.MULTIPLE_CHOICE,
                question="Was passt?",
                options=["A", "B", "C"],
                correct_answer="B",
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section), _one_section_answers([["A"]]), _BoomLLM()
    )
    assert score == 0
    fb = feedback.sections[0].items[0]
    assert fb.correct is False
    assert fb.correct_answer == "B"


@pytest.mark.asyncio
async def test_mc_case_insensitive_via_normalize():
    section = AssignmentSection(
        type=SectionType.MULTIPLE_CHOICE,
        title="MC",
        instructions="x",
        items=[
            MultipleChoiceItem(
                type=SectionType.MULTIPLE_CHOICE,
                question="Was passt?",
                options=["der Mann", "die Frau", "das Kind"],
                correct_answer="die Frau",
            )
        ],
    )
    score, _, _, _ = await scoring_module.score_submission(
        _one_section_content(section), _one_section_answers([["DIE FRAU"]]), _BoomLLM()
    )
    assert score == 1


# ---------------------------------------------------------------------------
# REORDER
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reorder_per_position_correct():
    correct_tokens = ["Ich", "gehe", "morgen", "ins", "Kino"]
    section = AssignmentSection(
        type=SectionType.REORDER,
        title="Reorder",
        instructions="x",
        items=[ReorderItem(type=SectionType.REORDER, correct_tokens=correct_tokens)],
    )
    score, max_score, _, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([list(correct_tokens)]),
        _BoomLLM(),
    )
    assert (score, max_score) == (1, 1)


@pytest.mark.asyncio
async def test_reorder_wrong_position_fails():
    section = AssignmentSection(
        type=SectionType.REORDER,
        title="Reorder",
        instructions="x",
        items=[
            ReorderItem(
                type=SectionType.REORDER,
                correct_tokens=["Ich", "gehe", "morgen", "ins", "Kino"],
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([["Ich", "gehe", "ins", "morgen", "Kino"]]),
        _BoomLLM(),
    )
    assert score == 0
    assert feedback.sections[0].items[0].correct is False


@pytest.mark.asyncio
async def test_reorder_wrong_length_fails():
    section = AssignmentSection(
        type=SectionType.REORDER,
        title="Reorder",
        instructions="x",
        items=[
            ReorderItem(
                type=SectionType.REORDER,
                correct_tokens=["Ich", "gehe", "morgen", "ins", "Kino"],
            )
        ],
    )
    score, _, _, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([["Ich", "gehe", "morgen", "ins"]]),
        _BoomLLM(),
    )
    assert score == 0


# ---------------------------------------------------------------------------
# ADJEKTIV_DEKLINATION
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adjektiv_deklination_correct_ending():
    section = AssignmentSection(
        type=SectionType.ADJEKTIV_DEKLINATION,
        title="Adj",
        instructions="x",
        items=[
            AdjektivDeklinationItem(
                type=SectionType.ADJEKTIV_DEKLINATION,
                question="Der nett___ Mann lacht.",
                correct_ending="-e",
                candidate_endings=["-e", "-er", "-en", "-es"],
            )
        ],
    )
    score, _, _, _ = await scoring_module.score_submission(
        _one_section_content(section), _one_section_answers([["-e"]]), _BoomLLM()
    )
    assert score == 1


@pytest.mark.asyncio
async def test_adjektiv_deklination_wrong_ending_fails():
    section = AssignmentSection(
        type=SectionType.ADJEKTIV_DEKLINATION,
        title="Adj",
        instructions="x",
        items=[
            AdjektivDeklinationItem(
                type=SectionType.ADJEKTIV_DEKLINATION,
                question="Der nett___ Mann lacht.",
                correct_ending="-e",
                candidate_endings=["-e", "-er", "-en", "-es"],
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section), _one_section_answers([["-er"]]), _BoomLLM()
    )
    assert score == 0
    assert feedback.sections[0].items[0].correct_answer == "-e"


# ---------------------------------------------------------------------------
# COMPLETION / FILL_IN_THE_BLANK — criterion-based
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completion_single_blank_judge_sees_criterion(monkeypatch):
    fake = _FakeJudge(verdicts=[True])
    monkeypatch.setattr(scoring_module, "judge_answer", fake)

    section = AssignmentSection(
        type=SectionType.COMPLETION,
        title="Completion",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.COMPLETION,
                question="Ich helfe ___ (das Kind).",
                grading_criterion="Dativ Singular Neutrum von 'das Kind'.",
                example_answer="dem Kind",
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section), _one_section_answers([["dem Kind"]]), _BoomLLM()
    )

    assert score == 1
    assert feedback.sections[0].items[0].correct is True
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call.grading_criterion == "Dativ Singular Neutrum von 'das Kind'."
    assert call.example_answer == "dem Kind"
    assert call.student_answers == ["dem Kind"]


@pytest.mark.asyncio
async def test_completion_wrong_shows_example_and_criterion(monkeypatch):
    fake = _FakeJudge(verdicts=[False])
    monkeypatch.setattr(scoring_module, "judge_answer", fake)

    section = AssignmentSection(
        type=SectionType.COMPLETION,
        title="Completion",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.COMPLETION,
                question="Ich helfe ___ (das Kind).",
                grading_criterion="Dativ Singular Neutrum von 'das Kind'.",
                example_answer="dem Kind",
                hint="Dativ-Endung im Neutrum",
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section), _one_section_answers([["das Kind"]]), _BoomLLM()
    )
    assert score == 0
    fb = feedback.sections[0].items[0]
    assert fb.correct is False
    assert fb.example_answer == "dem Kind"
    assert fb.grading_criterion == "Dativ Singular Neutrum von 'das Kind'."
    assert fb.hint == "Dativ-Endung im Neutrum"


@pytest.mark.asyncio
async def test_completion_multi_blank_single_judge_call(monkeypatch):
    fake = _FakeJudge(verdicts=[True])
    monkeypatch.setattr(scoring_module, "judge_answer", fake)

    section = AssignmentSection(
        type=SectionType.COMPLETION,
        title="Completion",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.COMPLETION,
                question="Ich helfe ___ (das Kind) mit ___ (die Hausaufgabe).",
                grading_criterion=(
                    "Beide Lücken: Dativ Singular. "
                    "Lücke 1: 'das Kind' → 'dem Kind'. "
                    "Lücke 2: 'die Hausaufgabe' → 'der Hausaufgabe'."
                ),
                example_answer="dem Kind / der Hausaufgabe",
            )
        ],
    )
    score, _, _, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([["dem Kind", "der Hausaufgabe"]]),
        _BoomLLM(),
    )
    assert score == 1
    # One judge call per item, not per blank
    assert len(fake.calls) == 1
    assert fake.calls[0].student_answers == ["dem Kind", "der Hausaufgabe"]


@pytest.mark.asyncio
async def test_completion_multi_blank_partial_fails(monkeypatch):
    fake = _FakeJudge(verdicts=[False])
    monkeypatch.setattr(scoring_module, "judge_answer", fake)

    section = AssignmentSection(
        type=SectionType.COMPLETION,
        title="Completion",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.COMPLETION,
                question="Ich helfe ___ (das Kind) mit ___ (die Hausaufgabe).",
                grading_criterion="Beide Lücken: Dativ Singular.",
                example_answer="dem Kind / der Hausaufgabe",
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([["dem Kind", "die Hausaufgabe"]]),
        _BoomLLM(),
    )
    assert score == 0
    assert feedback.sections[0].items[0].correct is False


@pytest.mark.asyncio
async def test_fill_in_the_blank_routes_through_judge(monkeypatch):
    fake = _FakeJudge(verdicts=[True])
    monkeypatch.setattr(scoring_module, "judge_answer", fake)

    section = AssignmentSection(
        type=SectionType.FILL_IN_THE_BLANK,
        title="Fill",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.FILL_IN_THE_BLANK,
                question="Die Tasche ___ ist moderner als meine.",
                grading_criterion=(
                    "Genitiv einer femininen Nominalphrase, die eine Person bezeichnet."
                ),
                example_answer="meiner Schwester",
            )
        ],
    )
    score, _, _, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([["meiner Freundin"]]),
        _BoomLLM(),
    )
    assert score == 1
    assert len(fake.calls) == 1
    assert fake.calls[0].student_answers == ["meiner Freundin"]
