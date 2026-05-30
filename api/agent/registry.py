from agent.tools import GetLearnerProfileInput, get_learner_profile

TOOLS = [
    {
        "name": "get_learner_profile",
        "description": (
            "Fetch the learner's progress profile: estimated CEFR level, XP, "
            "daily streak, and recurring weak grammar topics. Call only when "
            "you need progress/history to answer (e.g. 'Wie ist mein Fortschritt?', "
            "choosing difficulty, or referencing past mistakes). DO NOT call it just "
            "to correct a single sentence."
        ),
        "input_schema": GetLearnerProfileInput.model_json_schema(),
        "input_model": GetLearnerProfileInput,
        "handler": get_learner_profile,
    },
]


TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}
