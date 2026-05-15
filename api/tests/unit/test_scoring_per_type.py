"""Per-type scoring TDD tests for the structured assignment schema.

These tests pin down the scoring contract item-by-item:

- MULTIPLE_CHOICE: byte-equal (after normalize) against the single is_correct option. No judge.
- REORDER: per-index equality between submitted list and stored tokens[].text. No judge.
- COMPLETION / FILL_IN_THE_BLANK: ONE judge call PER BLANK. Verdicts AND into item-level.
  Per-blank rationales aggregated into ItemFeedback.blank_feedbacks.

Closed-type cases pass a stub LLM that raises if invoked — proves they take the
deterministic path. Criterion cases drive a fake judge that records every call so the
test can assert what the judge saw, per blank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from models.assignment_schema import (
    AssignmentContent,
    AssignmentSection,
    Blank,
    CriterionItem,
    MultipleChoiceItem,
    Option,
    ReorderItem,
    ReorderToken,
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
    is_sentence_initial: bool
    student_answer: str


@dataclass
class _FakeJudge:
    """Drop-in replacement for services.grading_judge.judge_blank.

    Configure `verdicts` as a list of bools — each call pops the next verdict.
    Records every call in `calls` for assertion.
    """

    verdicts: list[bool]
    calls: list[_RecordedCall] = field(default_factory=list)

    async def __call__(
        self,
        *,
        question: str,
        blank: Blank,
        student_answer: str,
        llm,  # noqa: ANN001
    ) -> JudgeResult:
        self.calls.append(
            _RecordedCall(
                question=question,
                grading_criterion=blank.grading_criterion,
                example_answer=blank.example_answer,
                is_sentence_initial=blank.is_sentence_initial,
                student_answer=student_answer,
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


def _mc_options() -> list[Option]:
    return [
        Option(index=0, text="A", is_correct=False),
        Option(index=1, text="B", is_correct=True),
        Option(index=2, text="C", is_correct=False),
    ]


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
                options=_mc_options(),
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
                options=_mc_options(),
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
                options=[
                    Option(index=0, text="der Mann", is_correct=False),
                    Option(index=1, text="die Frau", is_correct=True),
                    Option(index=2, text="das Kind", is_correct=False),
                ],
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


def _reorder_tokens(texts: list[str]) -> list[ReorderToken]:
    return [ReorderToken(index=i, text=t) for i, t in enumerate(texts)]


@pytest.mark.asyncio
async def test_reorder_per_position_correct():
    correct = ["Ich", "gehe", "morgen", "ins", "Kino"]
    section = AssignmentSection(
        type=SectionType.REORDER,
        title="Reorder",
        instructions="x",
        items=[ReorderItem(type=SectionType.REORDER, tokens=_reorder_tokens(correct))],
    )
    score, max_score, _, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([list(correct)]),
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
                tokens=_reorder_tokens(["Ich", "gehe", "morgen", "ins", "Kino"]),
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
                tokens=_reorder_tokens(["Ich", "gehe", "morgen", "ins", "Kino"]),
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
# COMPLETION / FILL_IN_THE_BLANK — criterion-based, ONE judge call per blank
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completion_single_blank_judge_sees_blank(monkeypatch):
    fake = _FakeJudge(verdicts=[True])
    monkeypatch.setattr(scoring_module, "judge_blank", fake)

    section = AssignmentSection(
        type=SectionType.COMPLETION,
        title="Completion",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.COMPLETION,
                question="Setze 'das Kind' in den Dativ.",
                blanks=[
                    Blank(
                        index=0,
                        grading_criterion="Dativ Singular Neutrum von 'das Kind'.",
                        example_answer="dem Kind",
                        is_sentence_initial=False,
                    )
                ],
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section), _one_section_answers([["dem Kind"]]), _BoomLLM()
    )

    assert score == 1
    item_fb = feedback.sections[0].items[0]
    assert item_fb.correct is True
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call.grading_criterion == "Dativ Singular Neutrum von 'das Kind'."
    assert call.example_answer == "dem Kind"
    assert call.student_answer == "dem Kind"
    assert call.is_sentence_initial is False
    # Per-blank verdicts attached
    assert item_fb.blank_feedbacks is not None
    assert len(item_fb.blank_feedbacks) == 1
    assert item_fb.blank_feedbacks[0].correct is True


@pytest.mark.asyncio
async def test_completion_wrong_surfaces_first_failed_blank_metadata(monkeypatch):
    fake = _FakeJudge(verdicts=[False])
    monkeypatch.setattr(scoring_module, "judge_blank", fake)

    section = AssignmentSection(
        type=SectionType.COMPLETION,
        title="Completion",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.COMPLETION,
                question="Setze 'das Kind' in den Dativ.",
                blanks=[
                    Blank(
                        index=0,
                        grading_criterion="Dativ Singular Neutrum von 'das Kind'.",
                        example_answer="dem Kind",
                        is_sentence_initial=False,
                    )
                ],
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
    assert fb.blank_feedbacks is not None
    assert fb.blank_feedbacks[0].correct is False


@pytest.mark.asyncio
async def test_completion_multi_blank_one_call_per_blank(monkeypatch):
    fake = _FakeJudge(verdicts=[True, True])
    monkeypatch.setattr(scoring_module, "judge_blank", fake)

    section = AssignmentSection(
        type=SectionType.COMPLETION,
        title="Completion",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.COMPLETION,
                question="Setze Dativ und Genitiv.",
                blanks=[
                    Blank(
                        index=0,
                        grading_criterion="Dativ Singular Neutrum von 'das Kind'.",
                        example_answer="dem Kind",
                        is_sentence_initial=False,
                    ),
                    Blank(
                        index=1,
                        grading_criterion="Genitiv Singular Femininum von 'die Hausaufgabe'.",
                        example_answer="der Hausaufgabe",
                        is_sentence_initial=False,
                    ),
                ],
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([["dem Kind", "der Hausaufgabe"]]),
        _BoomLLM(),
    )
    assert score == 1
    # One judge call PER BLANK
    assert len(fake.calls) == 2
    assert fake.calls[0].student_answer == "dem Kind"
    assert fake.calls[1].student_answer == "der Hausaufgabe"
    item_fb = feedback.sections[0].items[0]
    assert item_fb.blank_feedbacks is not None
    assert len(item_fb.blank_feedbacks) == 2


@pytest.mark.asyncio
async def test_completion_multi_blank_partial_fails(monkeypatch):
    fake = _FakeJudge(verdicts=[True, False])
    monkeypatch.setattr(scoring_module, "judge_blank", fake)

    section = AssignmentSection(
        type=SectionType.COMPLETION,
        title="Completion",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.COMPLETION,
                question="Setze Dativ und Genitiv.",
                blanks=[
                    Blank(
                        index=0,
                        grading_criterion="Dativ.",
                        example_answer="dem Kind",
                        is_sentence_initial=False,
                    ),
                    Blank(
                        index=1,
                        grading_criterion="Genitiv.",
                        example_answer="der Hausaufgabe",
                        is_sentence_initial=False,
                    ),
                ],
            )
        ],
    )
    score, _, feedback, _ = await scoring_module.score_submission(
        _one_section_content(section),
        _one_section_answers([["dem Kind", "die Hausaufgabe"]]),
        _BoomLLM(),
    )
    assert score == 0
    fb = feedback.sections[0].items[0]
    assert fb.correct is False
    # First-failed blank's example surfaces at item level for the existing UI
    assert fb.example_answer == "der Hausaufgabe"
    assert fb.blank_feedbacks is not None
    assert [bf.correct for bf in fb.blank_feedbacks] == [True, False]


@pytest.mark.asyncio
async def test_fill_in_the_blank_routes_through_judge(monkeypatch):
    fake = _FakeJudge(verdicts=[True])
    monkeypatch.setattr(scoring_module, "judge_blank", fake)

    section = AssignmentSection(
        type=SectionType.FILL_IN_THE_BLANK,
        title="Fill",
        instructions="x",
        items=[
            CriterionItem(
                type=SectionType.FILL_IN_THE_BLANK,
                question="Setze einen femininen Genitiv ein.",
                blanks=[
                    Blank(
                        index=0,
                        grading_criterion=(
                            "Genitiv einer femininen Nominalphrase, die eine Person bezeichnet."
                        ),
                        example_answer="meiner Schwester",
                        is_sentence_initial=False,
                    )
                ],
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
    assert fake.calls[0].student_answer == "meiner Freundin"
