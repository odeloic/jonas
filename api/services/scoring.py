import unicodedata

import structlog

from models.assignment_schema import (
    AdjektivDeklinationItem,
    AssignmentContent,
    CriterionItem,
    ItemFeedback,
    MultipleChoiceItem,
    ReorderItem,
    SectionFeedback,
    SubmissionAnswers,
    SubmissionFeedback,
)
from services.grading_judge import judge_answer
from services.llm_service import LLMService

log = structlog.get_logger()


def normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s.strip().lower())


async def score_submission(
    content: AssignmentContent,
    answers: SubmissionAnswers,
    llm: LLMService,
) -> tuple[int, int, SubmissionFeedback, str | None]:
    """Compare submitted answers against per-item correctness rules.

    Closed types (MC, REORDER, ADJEKTIV_DEKLINATION) are graded deterministically.
    Criterion types (COMPLETION, FILL_IN_THE_BLANK) call the LLM judge once per
    item, passing the criterion as rubric.

    Returns (score, max_score, feedback, langfuse_trace_id).
    """
    total_score = 0
    total_max = 0
    section_feedbacks: list[SectionFeedback] = []
    first_trace_id: str | None = None

    for section, section_answers in zip(content.sections, answers.sections, strict=True):
        item_feedbacks: list[ItemFeedback] = []
        for item, user_answer in zip(section.items, section_answers.items, strict=True):
            total_max += 1

            if isinstance(item, MultipleChoiceItem):
                feedback = _score_mc(item, user_answer)
            elif isinstance(item, ReorderItem):
                feedback = _score_reorder(item, user_answer)
            elif isinstance(item, AdjektivDeklinationItem):
                feedback = _score_adjektiv(item, user_answer)
            elif isinstance(item, CriterionItem):
                feedback, trace_id = await _score_criterion(item, user_answer, llm)
                if first_trace_id is None and trace_id:
                    first_trace_id = trace_id
            else:
                raise TypeError(f"Unknown item type: {type(item).__name__}")

            if feedback.correct:
                total_score += 1
            item_feedbacks.append(feedback)
        section_feedbacks.append(SectionFeedback(items=item_feedbacks))

    feedback = SubmissionFeedback(sections=section_feedbacks)
    log.info("submission_scored", score=total_score, max_score=total_max)
    return total_score, total_max, feedback, first_trace_id


def _score_mc(item: MultipleChoiceItem, user_answer: list[str]) -> ItemFeedback:
    submitted = user_answer[0] if user_answer else ""
    is_correct = normalize(submitted) == normalize(item.correct_answer)
    return ItemFeedback(
        correct=is_correct,
        user_answer=user_answer,
        correct_answer=None if is_correct else item.correct_answer,
        hint=None if is_correct else item.hint,
    )


def _score_reorder(item: ReorderItem, user_answer: list[str]) -> ItemFeedback:
    if len(user_answer) != len(item.correct_tokens):
        is_correct = False
    else:
        is_correct = all(
            normalize(submitted) == normalize(expected)
            for submitted, expected in zip(user_answer, item.correct_tokens, strict=True)
        )
    return ItemFeedback(
        correct=is_correct,
        user_answer=user_answer,
        correct_answer=None if is_correct else " ".join(item.correct_tokens),
        hint=None if is_correct else item.hint,
    )


def _score_adjektiv(item: AdjektivDeklinationItem, user_answer: list[str]) -> ItemFeedback:
    submitted = user_answer[0] if user_answer else ""
    is_correct = normalize(submitted) == normalize(item.correct_ending)
    return ItemFeedback(
        correct=is_correct,
        user_answer=user_answer,
        correct_answer=None if is_correct else item.correct_ending,
        hint=None if is_correct else item.hint,
    )


async def _score_criterion(
    item: CriterionItem, user_answer: list[str], llm: LLMService
) -> tuple[ItemFeedback, str | None]:
    result = await judge_answer(
        question=item.question,
        grading_criterion=item.grading_criterion,
        example_answer=item.example_answer,
        student_answers=user_answer,
        llm=llm,
    )
    feedback = ItemFeedback(
        correct=result.is_correct,
        user_answer=user_answer,
        example_answer=None if result.is_correct else item.example_answer,
        grading_criterion=None if result.is_correct else item.grading_criterion,
        hint=None if result.is_correct else item.hint,
    )
    return feedback, result.raw_result.trace_id
