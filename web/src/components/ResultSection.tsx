import type { ExerciseSection, SectionFeedback } from "../api/types";
import ResultItem from "./ResultItem";

interface Props {
  section: ExerciseSection;
  feedback: SectionFeedback;
}

export default function ResultSectionView({ section, feedback }: Props) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">{section.title}</h2>
        <p className="text-sm text-gray-500 mt-0.5">{section.instructions}</p>
      </div>
      {feedback.items.map((fb, i) => (
        <ResultItem
          key={i}
          feedback={fb}
          item={section.items[i]}
          index={i + 1}
        />
      ))}
    </section>
  );
}
