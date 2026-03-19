"""usage: docker compose exec api python scripts/db_cleanup.py [--all | --source-id n]"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import async_session
from models.source import Source


async def purge_all():
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(Source))
    print("All sources purged (grammar_rules + vocabulary_items cascaded).")


async def delete_source(source_id: int):
    async with async_session() as session:
        async with session.begin():
            source = await session.get(Source, source_id)
            if not source:
                print(f"Source {source_id} not found.")
                return
            await session.delete(source)
    print(f"Source {source_id} has been deleted (grammar_rules + vocabulary_items cascaded).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--source-id", type=int)
    args = parser.parse_args()

    if args.all:
        asyncio.run(purge_all())
    else:
        asyncio.run(delete_source(args.source_id))
