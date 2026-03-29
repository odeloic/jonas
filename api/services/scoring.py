import unicodedata

import structlog

from models.assignment_schema import (
    AssignmentContent,
    ItemFeedback,
    SectionFeedback,
    SubmissionAnswers,
    SubmissionFeedback,
)

log = structlog.get_logger()


def normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s.strip().lower())


def score_submission(
    content: AssignmentContent,
    answers: SubmissionAnswers,
) -> tuple[int, int, SubmissionFeedback]:
    """Compare submitted answers against correct answers.

    Returns (score, max_score, feedback).
    """
    total_score = 0
    total_max = 0
    section_feedbacks: list[SectionFeedback] = []

    for section, section_answers in zip(content.sections, answers.sections, strict=True):
        item_feedbacks: list[ItemFeedback] = []
        for item, user_answer in zip(section.items, section_answers.items, strict=True):
            is_correct = normalize(user_answer) == normalize(item.correct_answer)
            total_max += 1
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
    return total_score, total_max, feedback
