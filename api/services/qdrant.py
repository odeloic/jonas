import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config import settings
from services.llm_service import LLMService

log = structlog.get_logger()
_llm = LLMService()

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def ensure_collection():
    """create the grammar_rules collection if it doesnt exist"""
    client = get_client()
    collections = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in collections:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        log.info("qdrant_collection_created", name=settings.qdrant_collection)


async def embed_text(text: str) -> list[float]:
    """Get embedding vector for a text chunk via OpenAI SDK."""
    return await _llm.embed(text)


def _build_chunk_text(topic: str, rule_name: str, explanation: str, examples: list[str]) -> str:
    """Build a single text chunk from a grammar rule for embedding"""
    parts = [f"Thema: {topic}", f"Regel: {rule_name}", f"Erklärung: {explanation}"]
    if examples:
        parts.append("Beispiele: " + " | ".join(examples))
    return "\n".join(parts)


async def upsert_grammar_rule(
    rule_id: int, topic: str, rule_name: str, explanation: str, examples: list[str]
) -> dict:
    """
    Embed a grammar rule and upsert to Qdrant.
    If a near-duplicate texists (cosine >= threshold), merge examples instead.
    Returns {"action": "created" | "merged", "point_id": int}
    """
    client = get_client()
    chunk_text = _build_chunk_text(topic, rule_name, explanation, examples)
    vector = await embed_text(chunk_text)

    hits = client.query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        limit=1,
        score_threshold=settings.qdrant_similarity_threshold,
    ).points

    if hits:
        existing = hits[0]
        if existing.payload is not None:
            existing_examples = existing.payload.get("examples", [])
            merged_examples = list(set(existing_examples + examples))
            merged_text = _build_chunk_text(
                existing.payload["topic"],
                existing.payload["rule_name"],
                existing.payload["explanation"],
                merged_examples,
            )
            merged_vector = await embed_text(merged_text)

            client.upsert(
                collection_name=settings.qdrant_collection,
                points=[
                    PointStruct(
                        id=existing.id,
                        vector=merged_vector,
                        payload={
                            **existing.payload,
                            "examples": merged_examples,
                            "pg_rule_ids": list(
                                set(existing.payload.get("pg_rule_ids", []) + [rule_id])
                            ),
                        },
                    )
                ],
            )
            log.info(
                "qdrant_merged",
                existing=existing.id,
                new_examples=len(examples),
                total_examples=len(merged_examples),
                score=hits[0].score,
            )
            return {"action": "merged", "point_id": existing.id}

    # No duplicates found - create new point
    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            PointStruct(
                id=rule_id,
                vector=vector,
                payload={
                    "topic": topic,
                    "rule_name": rule_name,
                    "explanation": explanation,
                    "examples": examples,
                    "pg_rule_ids": [rule_id],
                },
            )
        ],
    )
    log.info("qdrant_created", point_id=rule_id, topic=topic, rule_name=rule_name)
    return {"action": "created", "point_id": rule_id}
