import structlog
from sqlalchemy import select

from db import async_session
from models.extraction import PageExtraction
from models.grammar_rule import GrammarRule as GrammarRuleRow
from models.processed_image import ProcessedImage
from models.source import Source
from models.vocabulary_item import VocabularyItem as VocabularyItemRow
from services.qdrant import ensure_collection, upsert_grammar_rule

log = structlog.get_logger()


async def check_processed_images(file_unique_ids: list[str]) -> set[str]:
    """Return the subset of file_unique_ids that have already been processed."""
    if not file_unique_ids:
        return set()
    async with async_session() as session:
        result = await session.execute(
            select(ProcessedImage.file_unique_id).where(
                ProcessedImage.file_unique_id.in_(file_unique_ids)
            )
        )
        return set(result.scalars().all())


async def persist_extractions(
    extractions: list[PageExtraction],
    image_metadata: list[tuple[str, str]] | None = None,
) -> tuple[Source, list[int]]:
    """Persist a batch of page extractions to Postgres inside a single transaction.
    Returns the source and a list of grammar rule IDs that were created.

    image_metadata: optional list of (file_unique_id, file_id) pairs to record
    as processed images, committed atomically with the content.
    """
    ensure_collection()
    async with async_session() as session:
        async with session.begin():
            source = Source(type="IMAGE", status="pending")
            session.add(source)
            await session.flush()

            rule_rows = []
            for extraction in extractions:
                for rule in extraction.grammar_rules:
                    row = GrammarRuleRow(
                        topic=extraction.topic,
                        rule_name=rule.rule_name,
                        explanation=rule.explanation,
                        pattern=rule.pattern,
                        examples=rule.examples,
                        source_id=source.id,
                    )
                    session.add(row)
                    rule_rows.append(row)

                for vocab in extraction.vocabulary:
                    session.add(
                        VocabularyItemRow(
                            word=vocab.word,
                            article=vocab.article,
                            plural=vocab.plural,
                            word_class=vocab.word_class,
                            definition_de=vocab.definition_de,
                            definition_en=vocab.definition_en,
                            example_sentence=vocab.example_sentence,
                            source_id=source.id,
                        )
                    )
            await session.flush()  # Flush to get rule IDs before Qdrant upsert
            rule_ids = [row.id for row in rule_rows]

            if image_metadata:
                for unique_id, fid in image_metadata:
                    session.add(
                        ProcessedImage(
                            file_unique_id=unique_id,
                            file_id=fid,
                            source_id=source.id,
                        )
                    )

            source.status = "complete"

    # Step 2: Embed & Upsert to Qdrant after Postgres Commit
    qdrant_results = []
    for row in rule_rows:
        try:
            result = await upsert_grammar_rule(
                rule_id=row.id,
                topic=row.topic,
                rule_name=row.rule_name,
                explanation=row.explanation,
                examples=row.examples or [],
            )
            qdrant_results.append(result)
        except Exception:
            log.exception("qdrant_upsert_failed", rule_id=row.id)

    log.info(
        "ingestion_persisted",
        source_id=source.id,
        grammar_rules=sum(len(e.grammar_rules) for e in extractions),
        vocabulary=sum(len(e.vocabulary) for e in extractions),
        qdrant_created=sum(1 for r in qdrant_results if r["action"] == "created"),
        qdrant_merged=sum(1 for r in qdrant_results if r["action"] == "merged"),
    )

    return source, rule_ids
