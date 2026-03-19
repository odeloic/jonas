from pydantic import BaseModel


class VocabularyItem(BaseModel):
    word: str
    article: str | None = None
    plural: str | None = None
    word_class: str
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
