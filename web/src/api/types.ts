export type SectionType =
  | "REORDER"
  | "COMPLETION"
  | "ADJEKTIV_DEKLINATION"
  | "FILL_IN_THE_BLANK"
  | "MULTIPLE_CHOICE";

export interface AssignmentItem {
  question: string;
  options: string[] | null;
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
  source: string;
  created_at: string;
}

// --- Submission types ---

export interface SectionAnswers {
  items: string[];
}

export interface SubmissionAnswers {
  sections: SectionAnswers[];
}

export interface ItemFeedback {
  correct: boolean;
  user_answer: string;
  correct_answer: string;
  hint: string | null;
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
