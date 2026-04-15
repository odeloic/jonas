import structlog
from sqlalchemy import func, select

from db import async_session
from models.grammar_rule import GrammarRule
from models.learner_profile import LearnerProfile

log = structlog.get_logger()


async def select_rules_for_assignment(chat_id: str, count: int = 5) -> list[GrammarRule]:
    """Select grammar rules for assignment generation, prioritising weak topics."""
    async with async_session() as session:
        # Fetch learner profile for weak topic prioritisation
        profile = await session.scalar(
            select(LearnerProfile).where(LearnerProfile.telegram_chat_id == chat_id)
        )
        weak_topics = list((profile.weak_topics or {}).keys()) if profile else []

        rules: list[GrammarRule] = []

        # First: rules matching weak topics
        if weak_topics:
            stmt = (
                select(GrammarRule)
                .where(GrammarRule.topic.in_(weak_topics))
                .order_by(func.random())
                .limit(count)
            )
            result = await session.execute(stmt)
            rules.extend(result.scalars().all())

        # Fill remaining slots with random rules not already selected
        remaining = count - len(rules)
        if remaining > 0:
            existing_ids = [r.id for r in rules]
            stmt = select(GrammarRule).order_by(func.random()).limit(remaining)
            if existing_ids:
                stmt = stmt.where(GrammarRule.id.notin_(existing_ids))
            result = await session.execute(stmt)
            rules.extend(result.scalars().all())

    log.info("rules_selected", chat_id=chat_id, count=len(rules), weak_matched=len(weak_topics))
    return rules
