import type { AssignmentSection, SectionFeedback } from "../api/types";
import ResultItem from "./ResultItem";

interface ResultSectionProps {
  section: AssignmentSection;
  feedback: SectionFeedback;
}

export default function ResultSection({
  section,
  feedback,
}: ResultSectionProps) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">{section.title}</h2>
        <p className="text-sm text-gray-500 mt-0.5">{section.instructions}</p>
      </div>
      {feedback.items.map((item, i) => (
        <ResultItem
          key={i}
          feedback={item}
          question={section.items[i]?.question ?? ""}
          index={i + 1}
        />
      ))}
    </section>
  );
}
