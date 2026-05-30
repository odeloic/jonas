from pydantic import BaseModel

from services.learner_profile import get_profile


class GetLearnerProfileInput(BaseModel):
    """No fields: chat_id is injected server_side, not chosen by the model"""


async def get_learner_profile(args: GetLearnerProfileInput, *, chat_id: str) -> dict:
    """Fetches learner's profile. Returns { "exists": False } if unprovisioned"""
    profile = await get_profile(chat_id)
    if profile is None:
        return {"exists": False}
    return {
        "exists": True,
        "cefr_estimate": profile.cefr_estimate,
        "xp": profile.xp,
        "streak_days": profile.streak_days,
        "weak_topics": list((profile.weak_topics or {}).keys()),
        "last_active_date": (
            profile.last_active_date.isoformat() if profile.last_active_date else None
        ),
    }
