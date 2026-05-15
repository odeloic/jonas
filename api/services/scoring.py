import unicodedata

import structlog

from models.assignment_schema import (
    AssignmentContent,
    BlankFeedback,
    CriterionItem,
    ItemFeedback,
    MultipleChoiceItem,
    ReorderItem,
    SectionFeedback,
    SubmissionAnswers,
    SubmissionFeedback,
)
from services.grading_judge import judge_blank
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

    Closed types (MC, REORDER) are graded deterministically.
    Criterion types (COMPLETION, FILL_IN_THE_BLANK) call the LLM judge once per
    blank; per-blank verdicts AND into the item-level verdict.

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
    correct = next(opt.text for opt in item.options if opt.is_correct)
    is_correct = normalize(submitted) == normalize(correct)
    return ItemFeedback(
        correct=is_correct,
        user_answer=user_answer,
        correct_answer=None if is_correct else correct,
        hint=None if is_correct else item.hint,
    )


def _score_reorder(item: ReorderItem, user_answer: list[str]) -> ItemFeedback:
    correct_texts = [t.text for t in item.tokens]
    if len(user_answer) != len(correct_texts):
        is_correct = False
    else:
        is_correct = all(
            normalize(submitted) == normalize(expected)
            for submitted, expected in zip(user_answer, correct_texts, strict=True)
        )
    return ItemFeedback(
        correct=is_correct,
        user_answer=user_answer,
        correct_answer=None if is_correct else " ".join(correct_texts),
        hint=None if is_correct else item.hint,
    )


async def _score_criterion(
    item: CriterionItem, user_answer: list[str], llm: LLMService
) -> tuple[ItemFeedback, str | None]:
    """One judge call per blank. AND verdicts into the item-level verdict.

    Per-blank rationales are aggregated into ItemFeedback.blank_feedbacks. The
    first non-None trace_id is returned so the submission row can link to one
    representative trace.
    """
    # Align student answers to blanks by index; pad with empty strings if short.
    padded_answers = list(user_answer) + [""] * (len(item.blanks) - len(user_answer))

    blank_feedbacks: list[BlankFeedback] = []
    first_trace_id: str | None = None
    all_correct = True

    for blank, student_answer in zip(item.blanks, padded_answers[: len(item.blanks)], strict=True):
        result = await judge_blank(
            question=item.question,
            blank=blank,
            student_answer=student_answer,
            llm=llm,
        )
        if not result.is_correct:
            all_correct = False
        if first_trace_id is None and result.raw_result.trace_id:
            first_trace_id = result.raw_result.trace_id

        blank_feedbacks.append(
            BlankFeedback(
                index=blank.index,
                correct=result.is_correct,
                rationale=result.rationale,
                example_answer=None if result.is_correct else blank.example_answer,
                grading_criterion=None if result.is_correct else blank.grading_criterion,
            )
        )

    # Item-level convenience fields show first failing blank's criterion/example so the
    # existing UI keeps working without per-blank rendering.
    first_failed = next((bf for bf in blank_feedbacks if not bf.correct), None)

    feedback = ItemFeedback(
        correct=all_correct,
        user_answer=user_answer,
        example_answer=first_failed.example_answer if first_failed else None,
        grading_criterion=first_failed.grading_criterion if first_failed else None,
        hint=None if all_correct else item.hint,
        blank_feedbacks=blank_feedbacks,
    )
    return feedback, first_trace_id
