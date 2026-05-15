import type { ExerciseSection } from "../api/types";
import ExerciseItemView from "./ExerciseItem";

interface Props {
  section: ExerciseSection;
  answers: string[][];
  onAnswerChange: (itemIndex: number, value: string[]) => void;
  disabled: boolean;
}

export default function ExerciseSectionView({
  section,
  answers,
  onAnswerChange,
  disabled,
}: Props) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">{section.title}</h2>
        <p className="text-sm text-gray-500 mt-0.5">{section.instructions}</p>
      </div>
      {section.items.map((item, i) => (
        <ExerciseItemView
          key={i}
          item={item}
          index={i + 1}
          value={answers[i] ?? []}
          onChange={(v) => onAnswerChange(i, v)}
          disabled={disabled}
        />
      ))}
    </section>
  );
}
