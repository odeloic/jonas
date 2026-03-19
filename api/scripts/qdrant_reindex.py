"""
Re-index all grammar rules from Postgres into Qdrant.

Usage: docker compose exec api python scripts/qdrant_reindex.py [--wipe]
--wipe Delete the existing collection before re-indexing
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from config import settings
from db import async_session
from models.grammar_rule import GrammarRule
from services.qdrant import ensure_collection, get_client, upsert_grammar_rule


async def reindex(wipe: bool = False):
    client = get_client()

    if wipe:
        collections = [c.name for c in client.get_collections().collections]
        if settings.qdrant_collection in collections:
            client.delete_collection(settings.qdrant_collection)
            print(f"Deleted collection '{settings.qdrant_collection}'")

    ensure_collection()

    async with async_session() as session:
        result = await session.execute(select(GrammarRule))
        rules = result.scalars().all()

        if not rules:
            print("No grammar rules found in Postgres. Nothing to index")
            return

        print(f"Re-indexing {len(rules)} grammar rules")

        created = 0
        merged = 0
        failed = 0

        for rule in rules:
            try:
                result = await upsert_grammar_rule(
                    rule_id=rule.id,
                    topic=rule.topic,
                    rule_name=rule.rule_name,
                    explanation=rule.explanation,
                    examples=rule.examples or [],
                )

                if result["action"] == "created":
                    created += 1
                else:
                    merged += 1
            except Exception as e:
                print(f" Failed rule {rule.id} ({rule.rule_name}): {e}")
                failed += 1
        print(f"Done. Created: {created}, Merged: {merged}, Failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true", help="Delete collection before re-indexing")
    args = parser.parse_args()
    asyncio.run(reindex(wipe=args.wipe))
