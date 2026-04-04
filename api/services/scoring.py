import unicodedata

import structlog

from models.assignment_schema import (
    AssignmentContent,
    ItemFeedback,
    SectionFeedback,
    SectionType,
    SubmissionAnswers,
    SubmissionFeedback,
)
from services.grading_judge import judge_answer
from services.llm_service import LLMService

log = structlog.get_logger()

SEMANTIC_TYPES = frozenset(
    {SectionType.REORDER, SectionType.COMPLETION, SectionType.FILL_IN_THE_BLANK}
)


def normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s.strip().lower())


async def score_submission(
    content: AssignmentContent,
    answers: SubmissionAnswers,
    llm: LLMService,
) -> tuple[int, int, SubmissionFeedback, str | None]:
    """Compare submitted answers against correct answers.

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

            if section.type in SEMANTIC_TYPES:
                result = await judge_answer(
                    student_answer=user_answer,
                    correct_answer=item.correct_answer,
                    question=item.question,
                    llm=llm,
                )
                is_correct = result.is_correct
                if first_trace_id is None and result.raw_result.trace_id:
                    first_trace_id = result.raw_result.trace_id
            else:
                is_correct = normalize(user_answer) == normalize(item.correct_answer)

            if is_correct:
                total_score += 1
            item_feedbacks.append(
                ItemFeedback(
                    correct=is_correct,
                    user_answer=user_answer,
                    correct_answer=item.correct_answer,
                    hint=item.hint if not is_correct else None,
                )
            )
        section_feedbacks.append(SectionFeedback(items=item_feedbacks))

    feedback = SubmissionFeedback(sections=section_feedbacks)
    log.info("submission_scored", score=total_score, max_score=total_max)
    return total_score, total_max, feedback, first_trace_id
