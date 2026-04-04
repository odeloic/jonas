from __future__ import annotations

from datetime import date, timedelta

import structlog
from sqlalchemy import select

from db import async_session
from models.assignment import Assignment
from models.assignment_schema import SubmissionFeedback
from models.grammar_rule import GrammarRule
from models.learner_profile import LearnerProfile
from models.submission import AssignmentSubmission

log = structlog.get_logger()

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
MAX_WEAK_TOPICS = 10


async def update_after_submission(
    chat_id: str,
    submission: AssignmentSubmission,
    assignment: Assignment,
) -> None:
    try:
        async with async_session() as session:
            async with session.begin():
                profile = await _get_or_create(session, chat_id)
                await _update_weak_topics(session, profile, submission, assignment)
                _update_xp(profile, submission.score, submission.max_score)
                _update_streak(profile)
                await _update_cefr_estimate(session, profile, chat_id)

        log.info(
            "learner_profile_updated",
            chat_id=chat_id,
            xp=profile.xp,
            streak=profile.streak_days,
            cefr=profile.cefr_estimate,
        )
    except Exception:
        log.exception("learner_profile_update_failed", chat_id=chat_id)


async def update_after_practice(chat_id: str, topics_corrected: list[str]) -> None:
    """Lightweight profile update after a practice session — tracks weak topics and streak only."""
    if not topics_corrected:
        return
    try:
        async with async_session() as session:
            async with session.begin():
                profile = await _get_or_create(session, chat_id)
                _update_streak(profile)
                topic_errors = {topic: 1 for topic in topics_corrected}
                profile.weak_topics = _merge_weak_topics(profile.weak_topics or {}, topic_errors)

        log.info(
            "practice_profile_updated",
            chat_id=chat_id,
            topics=topics_corrected,
            streak=profile.streak_days,
        )
    except Exception:
        log.exception("practice_profile_update_failed", chat_id=chat_id)


async def _get_or_create(session, chat_id: str) -> LearnerProfile:
    result = await session.execute(
        select(LearnerProfile).where(LearnerProfile.telegram_chat_id == chat_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = LearnerProfile(telegram_chat_id=chat_id)
        session.add(profile)
        await session.flush()
    return profile


def _update_xp(profile: LearnerProfile, score: int, max_score: int) -> None:
    profile.xp += 10
    if max_score > 0 and (score / max_score) >= 0.8:
        profile.xp += 5


def _update_streak(profile: LearnerProfile) -> None:
    today = date.today()
    if profile.last_active_date == today:
        return
    if profile.last_active_date == today - timedelta(days=1):
        profile.streak_days += 1
    else:
        profile.streak_days = 1
    profile.last_active_date = today


def _merge_weak_topics(current: dict, topic_errors: dict[str, int]) -> dict:
    """Merge error counts into weak_topics dict and cap at MAX_WEAK_TOPICS."""
    weak = dict(current)
    today_str = str(date.today())

    for topic, count in topic_errors.items():
        entry = weak.get(topic, {"error_count": 0, "last_seen": today_str})
        entry["error_count"] = entry["error_count"] + count
        entry["last_seen"] = today_str
        weak[topic] = entry

    if len(weak) > MAX_WEAK_TOPICS:
        sorted_topics = sorted(weak.items(), key=lambda x: x[1]["error_count"], reverse=True)
        weak = dict(sorted_topics[:MAX_WEAK_TOPICS])

    return weak


async def _update_weak_topics(
    session, profile: LearnerProfile, submission: AssignmentSubmission, assignment: Assignment
) -> None:
    rule_ids = assignment.grammar_rule_ids or []
    if not rule_ids:
        return

    result = await session.execute(select(GrammarRule).where(GrammarRule.id.in_(rule_ids)))
    rules = result.scalars().all()
    if not rules:
        return

    feedback = SubmissionFeedback.model_validate(submission.feedback)
    has_errors = any(not item.correct for section in feedback.sections for item in section.items)
    if not has_errors:
        return

    topics = {r.topic for r in rules}
    wrong_count = sum(
        1 for section in feedback.sections for item in section.items if not item.correct
    )
    topic_errors = {topic: wrong_count for topic in topics}
    profile.weak_topics = _merge_weak_topics(profile.weak_topics or {}, topic_errors)


async def _update_cefr_estimate(session, profile: LearnerProfile, chat_id: str) -> None:
    """Recalculate CEFR estimate based on recent performance per level."""
    # Get recent submissions for this user (last 10)
    recent_subs = await session.execute(
        select(AssignmentSubmission)
        .join(Assignment, Assignment.id == AssignmentSubmission.assignment_id)
        .order_by(AssignmentSubmission.submitted_at.desc())
        .limit(10)
    )
    submissions = recent_subs.scalars().all()
    if len(submissions) < 5:
        return  # Not enough data

    # Collect all grammar rule IDs from recent assignments
    assignment_ids = [s.assignment_id for s in submissions]
    assignments_result = await session.execute(
        select(Assignment).where(Assignment.id.in_(assignment_ids))
    )
    assignments = {a.id: a for a in assignments_result.scalars().all()}

    all_rule_ids = set()
    for a in assignments.values():
        all_rule_ids.update(a.grammar_rule_ids or [])

    if not all_rule_ids:
        return

    rules_result = await session.execute(
        select(GrammarRule).where(
            GrammarRule.id.in_(all_rule_ids),
            GrammarRule.cefr_level.is_not(None),
        )
    )
    rules_by_id = {r.id: r for r in rules_result.scalars().all()}

    if not rules_by_id:
        return  # No CEFR-tagged rules yet

    # Build per-level score aggregation
    level_scores: dict[str, list[float]] = {}
    for sub in submissions:
        a = assignments.get(sub.assignment_id)
        if not a:
            continue
        rule_ids = a.grammar_rule_ids or []
        levels = {rules_by_id[rid].cefr_level for rid in rule_ids if rid in rules_by_id}
        if not levels or sub.max_score == 0:
            continue
        pct = sub.score / sub.max_score
        for lvl in levels:
            level_scores.setdefault(lvl, []).append(pct)

    # Find highest level with >= 70% average
    best = profile.cefr_estimate
    for lvl in CEFR_LEVELS:
        scores = level_scores.get(lvl)
        if scores and (sum(scores) / len(scores)) >= 0.7:
            best = lvl

    profile.cefr_estimate = best
