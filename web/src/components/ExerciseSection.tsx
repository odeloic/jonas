import type { AssignmentSection } from "../api/types";
import ExerciseItem from "./ExerciseItem";

interface ExerciseSectionProps {
  section: AssignmentSection;
  answers: string[];
  onAnswerChange: (itemIndex: number, value: string) => void;
  disabled: boolean;
}

export default function ExerciseSection({
  section,
  answers,
  onAnswerChange,
  disabled,
}: ExerciseSectionProps) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">{section.title}</h2>
        <p className="text-sm text-gray-500 mt-0.5">{section.instructions}</p>
      </div>
      {section.items.map((item, i) => (
        <ExerciseItem
          key={i}
          item={item}
          sectionType={section.type}
          index={i + 1}
          value={answers[i] ?? ""}
          onChange={(v) => onAnswerChange(i, v)}
          disabled={disabled}
        />
      ))}
    </section>
  );
}
