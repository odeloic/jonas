import structlog

from db import async_session
from models.extraction import PageExtraction
from models.grammar_rule import GrammarRule as GrammarRuleRow
from models.source import Source
from models.vocabulary_item import VocabularyItem as VocabularyItemRow
from services.qdrant import ensure_collection, upsert_grammar_rule

log = structlog.get_logger()


async def persist_extractions(extractions: list[PageExtraction]) -> Source:
    """Persist a batch of page extractions to Postgres inside a single transactions"""
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
                    rule_rows.append((row, extraction.topic))

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
            source.status = "complete"

    # Step 2: Embed & Upsert to Qdrant after Postgres Commit
    qdrant_results = []
    for row, topic in rule_rows:
        try:
            result = await upsert_grammar_rule(
                rule_id=row.id,
                topic=topic,
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

    return source
