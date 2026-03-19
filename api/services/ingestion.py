import structlog

from db import async_session
from models.extraction import PageExtraction
from models.grammar_rule import GrammarRule as GrammarRuleRow
from models.source import Source
from models.vocabulary_item import VocabularyItem as VocabularyItemRow

log = structlog.get_logger()


async def persist_extractions(extractions: list[PageExtraction]) -> Source:
    """Persist a batch of page extractions to Postgres inside a single transactions"""
    async with async_session() as session:
        async with session.begin():
            source = Source(type="IMAGE", status="pending")
            session.add(source)
            await session.flush()

            for extraction in extractions:
                for rule in extraction.grammar_rules:
                    session.add(
                        GrammarRuleRow(
                            topic=extraction.topic,
                            rule_name=rule.rule_name,
                            explanation=rule.explanation,
                            pattern=rule.pattern,
                            examples=rule.examples,
                            source_id=source.id,
                        )
                    )

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
            source.status = "complete"

    log.info(
        "ingestion_persisted",
        source_id=source.id,
        grammar_rules=sum(len(e.grammar_rules) for e in extractions),
        vocabulary=sum(len(e.vocabulary) for e in extractions),
    )

    return source
