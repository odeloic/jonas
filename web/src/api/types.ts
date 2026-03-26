export type SectionType =
  | "REORDER"
  | "COMPLETION"
  | "ADJEKTIV_DEKLINATION"
  | "FILL_IN_THE_BLANK"
  | "MULTIPLE_CHOICE";

export interface AssignmentItem {
  question: string;
  correct_answer: string;
  options: string[] | null;
  hint: string | null;
}

export interface AssignmentSection {
  type: SectionType;
  title: string;
  instructions: string;
  items: AssignmentItem[];
}

export interface AssignmentContent {
  sections: AssignmentSection[];
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
  content: AssignmentContent;
  grammar_rule_ids: number[];
  source: string;
  sent_at: string | null;
  created_at: string;
}
