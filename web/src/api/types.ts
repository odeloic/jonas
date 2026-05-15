// --- Grammar types ---

export interface GrammarRule {
  id: number;
  topic: string;
  rule_name: string;
  explanation: string;
  pattern: string | null;
  examples: string[];
  verified: boolean;
  created_at: string;
}

export interface TopicSummary {
  topic: string;
  count: number;
}

// --- Vocabulary types ---

export interface VocabItem {
  id: number;
  word: string;
  article: string | null;
  plural: string | null;
  word_class: string;
  definition_de: string | null;
  definition_en: string | null;
  example_sentence: string | null;
  created_at: string;
}

// --- Stats types ---

export interface Stats {
  grammar_rules: number;
  vocabulary_items: number;
  assignments: number;
  topics: number;
}

// --- Assignment types ---

export type SectionType =
  | "REORDER"
  | "COMPLETION"
  | "FILL_IN_THE_BLANK"
  | "MULTIPLE_CHOICE";

export interface OptionView {
  index: number;
  text: string;
  // is_correct is intentionally NOT exposed — server omits it from the public payload.
}

export interface BlankView {
  index: number;
  // grading_criterion / example_answer / is_sentence_initial are server-side only;
  // the client just needs the count and indices to render labeled inputs.
}

export interface ReorderExerciseItem {
  type: "REORDER";
  // Shuffled bag of token texts. The correct order lives server-side.
  tokens: string[];
}

export interface MultipleChoiceExerciseItem {
  type: "MULTIPLE_CHOICE";
  question: string;
  options: OptionView[];
}

export interface CriterionExerciseItem {
  type: "COMPLETION" | "FILL_IN_THE_BLANK";
  question: string;
  blanks: BlankView[];
}

export type ExerciseItem =
  | ReorderExerciseItem
  | MultipleChoiceExerciseItem
  | CriterionExerciseItem;

export interface ExerciseSection {
  type: SectionType;
  title: string;
  instructions: string;
  items: ExerciseItem[];
}

export interface ExerciseContent {
  sections: ExerciseSection[];
}

export interface AssignmentSummary {
  id: number;
  type: string;
  topic: string;
  source: string;
  sent_at: string | null;
  created_at: string;
}

export interface AssignmentDetail {
  id: number;
  type: string;
  topic: string;
  content: ExerciseContent;
  source: string;
  created_at: string;
}

// --- Flashcard types ---

export interface FlashcardItem {
  id: number;
  word: string;
  article: string | null;
  plural: string | null;
  word_class: string;
  definition_de: string | null;
  definition_en: string | null;
  example_sentence: string | null;
}

export interface FlashcardSetSummary {
  id: number;
  telegram_chat_id: string;
  sent_at: string | null;
  created_at: string;
}

export interface FlashcardSetDetail {
  id: number;
  telegram_chat_id: string;
  items: FlashcardItem[];
  sent_at: string | null;
  created_at: string;
}

// --- Submission types ---

export interface SectionAnswers {
  items: string[][];
}

export interface SubmissionAnswers {
  sections: SectionAnswers[];
}

export interface BlankFeedback {
  index: number;
  correct: boolean;
  rationale: string;
  example_answer: string | null;
  grading_criterion: string | null;
}

export interface ItemFeedback {
  correct: boolean;
  user_answer: string[];
  correct_answer: string | null;
  example_answer: string | null;
  grading_criterion: string | null;
  hint: string | null;
  blank_feedbacks: BlankFeedback[] | null;
}

export interface SectionFeedback {
  items: ItemFeedback[];
}

export interface SubmissionFeedback {
  sections: SectionFeedback[];
}

export interface SubmissionResult {
  id: number;
  assignment_id: number;
  score: number;
  max_score: number;
  feedback: SubmissionFeedback;
  submitted_at: string;
}
