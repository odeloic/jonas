from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from config import settings
from db import async_session
from models.assignment import Assignment
from models.learner_profile import LearnerProfile
from services.assignment import generate_assignment_from_rules, save_assignment
from services.rule_selection import select_rules_for_assignment

if TYPE_CHECKING:
    from telegram.ext import ContextTypes

log = structlog.get_logger()


async def send_weekly_assignments(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: generate and send weekly assignments to all learners."""
    log.info("weekly_assignment_cron_started")

    async with async_session() as session:
        result = await session.execute(select(LearnerProfile))
        profiles = result.scalars().all()

    if not profiles:
        log.info("weekly_assignment_cron_no_profiles")
        return

    for profile in profiles:
        chat_id = profile.telegram_chat_id
        try:
            rules = await select_rules_for_assignment(chat_id)
            if not rules:
                log.info("weekly_assignment_cron_no_rules", chat_id=chat_id)
                continue

            topics = list({r.topic for r in rules})
            topic = topics[0] if len(topics) == 1 else "Wochenübung"

            content = await generate_assignment_from_rules(
                rules, topic=topic, learner_profile=profile
            )
            assignment = await save_assignment(
                topic,
                content,
                grammar_rule_ids=[r.id for r in rules],
                telegram_chat_id=chat_id,
                source="WEEKLY",
            )

            item_count = sum(len(s.items) for s in content.sections)
            section_count = len(content.sections)

            text = (
                f"\U0001f4cb Deine Wochenübung ist da!\n\n"
                f"Übung #{assignment.id}: "
                f"{section_count} Abschnitte mit {item_count} Aufgaben.\n"
                f"Thema: {topic}"
            )
            if settings.web_base_url:
                url = f"{settings.web_base_url}/assignments/{assignment.id}"
                text += f"\n\nHier starten: {url}"

            await context.bot.send_message(chat_id=chat_id, text=text)

            async with async_session() as session:
                async with session.begin():
                    row = await session.get(Assignment, assignment.id)
                    if row:
                        row.sent_at = datetime.now(UTC)

            log.info(
                "weekly_assignment_sent",
                chat_id=chat_id,
                assignment_id=assignment.id,
            )
        except Exception:
            log.exception("weekly_assignment_cron_failed", chat_id=chat_id)

    log.info("weekly_assignment_cron_finished", profiles=len(profiles))
