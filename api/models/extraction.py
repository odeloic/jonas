from pydantic import BaseModel, Field


class VocabularyItem(BaseModel):
    word: str = Field(
        description=(
            "The bare lemma, never including the article. "
            "For nouns, the singular nominative form only "
            "(e.g. 'Puppe', not 'die Puppe' and not 'Puppen')."
        )
    )
    article: str | None = Field(
        default=None,
        description=(
            "For nouns only: 'der', 'die', or 'das' (singular nominative). Null for non-nouns."
        ),
    )
    plural: str | None = Field(
        default=None,
        description=(
            "For nouns only: the plural form without article "
            "(e.g. 'Puppen'). Null for non-nouns or when no plural exists."
        ),
    )
    word_class: str = Field(
        description=(
            "One of: Nomen, Verb, Adjektiv, Adverb, Präposition, "
            "Konjunktion, Pronomen, Artikel, Numerale, Interjektion. "
            "Always in German, never in English."
        )
    )
    definition_de: str | None = None
    definition_en: str | None = None
    example_sentence: str | None = None


class GrammarRule(BaseModel):
    rule_name: str
    explanation: str
    pattern: str | None = None
    examples: list[str]


class ExampleSentence(BaseModel):
    sentence: str
    annotation: str | None = None


class PageExtraction(BaseModel):
    """Everything extracted from one textbook page / grammar screenshot"""

    topic: str
    page_number: int | None = None  # FIXME But i think this is irrelevant
    grammar_rules: list[GrammarRule]
    vocabulary: list[VocabularyItem]
    example_sentences: list[ExampleSentence]
    source_notes: str | None = None
