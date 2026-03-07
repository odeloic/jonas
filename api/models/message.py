from pydantic import BaseModel


class IncomingMessage(BaseModel):
    object: str
    entry: list[dict]  # raw for now — M2 will type this fully
